import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from irobot_create_msgs.msg import HazardDetectionVector, HazardDetection
import math
import random

TELEOP_TIMEOUT  = 0.25
ONE_FOOT_M      = 0.3048  # 1 ft


class ReactiveController(Node):

    def __init__(self):
        super().__init__('reactive_controller')

        self.cmd_pub = self.create_publisher(TwistStamped, '/cmd_vel', 10)

        self.scan_sub = self.create_subscription(
            LaserScan, '/scan', self.scan_callback, 10)

        self.teleop_sub = self.create_subscription(
            TwistStamped, '/teleop_cmd_vel', self.teleop_callback, 10)

        self.hazard_sub = self.create_subscription(
            HazardDetectionVector, '/hazard_detection', self.hazard_callback, 10)

        self.odom_sub = self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10)

        self.timer_period = 0.05
        self.timer = self.create_timer(self.timer_period, self.control_loop)

        # Sensors
        self.front_distance = float('inf')
        self.left_distance  = float('inf')
        self.right_distance = float('inf')
        self.bump_detected  = False
        self.last_odom_x    = None
        self.last_odom_y    = None
        self.track_distance = False

        # Speeds
        self.slow_speed   =  0.1   # m/s forward
        self.backup_speed = -0.1   # m/s backward
        self.turn_speed   =  0.5   # rad/s

        # Teleop state
        self.teleop_cmd       = None
        self.last_teleop_time = None

        # Lidar cone
        self.FRONT_DEG = 30
        self.FRONT_RAD = math.radians(self.FRONT_DEG)

        # Obstacle detection
        self.OBSTACLE_DIST      = 0.6  # meters
        self.SYMMETRY_THRESHOLD = 0.3  # meters each side

        # Behavior 5
        self.MAX_TURN_DEG           = 15
        self.forward_distance_accum = 0.0
        self.is_turning             = False
        self.turn_end_time          = None
        self.current_turn_direction = 0.0

        # Behavior 4
        self.avoid_turn_direction = 0.0

        # Behavior 3
        self.is_escaping           = False
        self.escape_phase          = None
        self.escape_phase_end_time = None
        self.escape_turn_direction = 0.0
        self.escape_turn_angle_deg = 180.0

        self.shutdown_requested = False

    #
    # Sensor callbacks
    #

    def scan_callback(self, msg):
        n               = len(msg.ranges)
        angle_increment = msg.angle_increment

        # Index pointing directly forward
        forward_index = int(round((3 * math.pi / 2 - msg.angle_min) / angle_increment)) % n
        front_range   = int(self.FRONT_RAD / angle_increment)

        center_range = int(math.radians(10) / angle_increment)  # front: ±10 deg
        left_ranges  = []
        right_ranges = []
        front_ranges = []

        # Front
        for i in range(-center_range, center_range + 1):
            r = msg.ranges[(forward_index + i) % n]
            if math.isfinite(r) and r > 0.01:
                front_ranges.append(r)

        # Left
        for i in range(center_range + 1, front_range + 1):
            r = msg.ranges[(forward_index + i) % n]
            if math.isfinite(r) and r > 0.01:
                left_ranges.append(r)

        # Right
        for i in range(center_range + 1, front_range + 1):
            r = msg.ranges[(forward_index - i) % n]
            if math.isfinite(r) and r > 0.01:
                right_ranges.append(r)

        self.front_distance = min(front_ranges) if front_ranges else float('inf')
        self.left_distance  = min(left_ranges)  if left_ranges  else float('inf')
        self.right_distance = min(right_ranges) if right_ranges else float('inf')

    def hazard_callback(self, msg):
        self.bump_detected = any(
            h.type == HazardDetection.BUMP for h in msg.detections
        )

    def odom_callback(self, msg):
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y

        if self.last_odom_x is not None and self.last_odom_y is not None and self.track_distance:
            dx = x - self.last_odom_x
            dy = y - self.last_odom_y
            self.forward_distance_accum += math.hypot(dx, dy)

        self.last_odom_x = x
        self.last_odom_y = y

    def teleop_callback(self, msg):
        self.teleop_cmd       = msg
        self.last_teleop_time = self.get_clock().now()

    def _teleop_active(self):
        if self.last_teleop_time is None:
            return False
        elapsed = (self.get_clock().now() - self.last_teleop_time).nanoseconds * 1e-9
        return elapsed < TELEOP_TIMEOUT

    #
    # Maneuver starters
    #

    def _start_escape(self):
        """Behavior 3: back up 1 s then spin about 180 deg (+/- 30 deg)."""
        self.is_escaping           = True
        self.escape_phase          = 'backing'
        self.escape_phase_end_time = self.get_clock().now().nanoseconds * 1e-9 + 1.0
        self.escape_turn_direction = 1.0 if random.random() > 0.5 else -1.0
        self.escape_turn_angle_deg = random.uniform(150.0, 210.0)
        self.get_logger().info("Symmetric obstacle – escaping: backing up")

    def _start_avoidance(self):
        """Behavior 4: make one reactive steering step toward the open side."""
        self.avoid_turn_direction = 1.0 if self.left_distance >= self.right_distance else -1.0
        self.get_logger().info(
            f"Asymmetric obstacle (L:{self.left_distance:.2f} R:{self.right_distance:.2f}) – "
            f"steering {'left' if self.avoid_turn_direction > 0 else 'right'} this cycle"
        )

    def _start_random_turn(self):
        """Behavior 5: random turn uniformly sampled within 15 degrees."""
        angle_deg = random.uniform(-self.MAX_TURN_DEG, self.MAX_TURN_DEG)
        angle_rad = math.radians(angle_deg)
        if abs(angle_rad) < 1e-3:
            angle_rad = math.radians(5.0)
        turn_duration               = abs(angle_rad) / self.turn_speed
        self.is_turning             = True
        self.current_turn_direction = 1.0 if angle_rad > 0.0 else -1.0
        self.turn_end_time          = self.get_clock().now().nanoseconds * 1e-9 + turn_duration
        self.get_logger().info(
            f"Reached 1 ft – random turn {angle_deg:.1f} deg for {turn_duration:.2f} s"
        )

    #
    # Publish helpers
    #

    def _publish_stop(self):
        self.track_distance = False
        self.cmd_pub.publish(TwistStamped())

    def _publish_forward(self):
        self.track_distance = True
        cmd = TwistStamped()
        cmd.twist.linear.x = self.slow_speed
        self.cmd_pub.publish(cmd)

    def _publish_backup(self):
        self.track_distance = False
        cmd = TwistStamped()
        cmd.twist.linear.x = self.backup_speed
        self.cmd_pub.publish(cmd)

    def _publish_turn(self, direction):
        self.track_distance = False
        cmd = TwistStamped()
        cmd.twist.angular.z = direction * self.turn_speed
        self.cmd_pub.publish(cmd)

    def _halt_and_shutdown(self):
        if self.shutdown_requested:
            return

        self.shutdown_requested = True
        self.is_turning = False
        self.is_escaping = False
        self.teleop_cmd = None
        self._publish_stop()
        rclpy.shutdown()

    #
    # Main control loop
    #

    def control_loop(self):
        now_sec = self.get_clock().now().nanoseconds * 1e-9

        self.get_logger().info(
            f"Front:{self.front_distance:.2f}  L:{self.left_distance:.2f}  R:{self.right_distance:.2f}"
        )

        # Priority 1: obstacle too close
        if self.front_distance < 0.3 or self.bump_detected:
            self.get_logger().info(f"Too close ({self.front_distance:.2f} m) – full halt")
            self._halt_and_shutdown()
            return

        # Priority 2: human teleop
        if self._teleop_active():
            self.is_turning  = False
            self.is_escaping = False
            self.track_distance = False
            self.get_logger().info("Teleop active – forwarding human input")
            self.cmd_pub.publish(self.teleop_cmd)
            return

        # If a new obstacle appears and we are not already maneuvering, decide what to do
        if self.front_distance < self.OBSTACLE_DIST and not self.is_escaping:
            self.is_turning = False
            asymmetry = abs(self.left_distance - self.right_distance)
            if asymmetry <= self.SYMMETRY_THRESHOLD:
                # Priority 3: escape symmetric obstacle
                self._start_escape()
            else:
                # Priority 4: avoid asymmetric obstacle
                self._start_avoidance()
                self._publish_turn(self.avoid_turn_direction)
                return

        # Priority 3 continued: execute escape
        if self.is_escaping:
            if self.escape_phase == 'backing':
                if now_sec < self.escape_phase_end_time:
                    self._publish_backup()
                else:
                    self.escape_phase          = 'turning'
                    self.escape_phase_end_time = now_sec + math.radians(self.escape_turn_angle_deg) / self.turn_speed
                    self.get_logger().info("Escape: backup done – spinning 90 deg")
                    self._publish_turn(self.escape_turn_direction)
            else:  # 'turning'
                if now_sec < self.escape_phase_end_time:
                    self._publish_turn(self.escape_turn_direction)
                else:
                    self.is_escaping            = False
                    self.escape_phase           = None
                    self.forward_distance_accum = 0.0
                    self.get_logger().info("Escape complete – resuming forward drive")
                    self._publish_forward()
            return

        # Priority 5: random turn every 1 ft
        if self.is_turning:
            if now_sec < self.turn_end_time:
                self._publish_turn(self.current_turn_direction)
            else:
                self.is_turning             = False
                self.forward_distance_accum = 0.0
                self.get_logger().info("Random turn complete – resuming forward drive")
                self._publish_forward()
            return

        # Priority 6: drive forward
        if self.forward_distance_accum >= ONE_FOOT_M:
            self._start_random_turn()
            self._publish_turn(self.current_turn_direction)
        else:
            self._publish_forward()


def main(args=None):
    rclpy.init(args=args)
    node = ReactiveController()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
