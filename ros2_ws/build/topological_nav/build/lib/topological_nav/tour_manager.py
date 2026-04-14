import math

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from std_msgs.msg import Int32, String, Bool
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose

# ---------------------------------------------------------------------------
# Landmark configuration
# ---------------------------------------------------------------------------

# Fill in x, y (meters) and yaw (radians) after the manual mapping run.
# These are the robot poses at each landmark in the /map frame.
LANDMARK_POSITIONS = {
    1: (0.0, 0.0, 0.0),   # TODO: set after mapping
    2: (0.0, 0.0, 0.0),   # TODO: set after mapping
    3: (0.0, 0.0, 0.0),   # TODO: set after mapping
}

HOME_POSITION = (0.0, 0.0, 0.0)  # TODO: set after mapping

# QR code content → spoken description.
# The string stored on each physical QR code is the key here.
LANDMARK_DESCRIPTIONS = {
    'landmark_1': 'Welcome to the first stop on your tour. This area showcases ...',
    'landmark_2': 'You have reached the second landmark. Here you can see ...',
    'landmark_3': 'This is the third and final stop. This location features ...',
}

# ---------------------------------------------------------------------------
# State machine states
# ---------------------------------------------------------------------------

STATE_HOME        = 'HOME'
STATE_NAVIGATING  = 'NAVIGATING'
STATE_AT_LANDMARK = 'AT_LANDMARK'
STATE_RETURNING   = 'RETURNING'

GESTURE_WAVE = 10


class TourManager(Node):

    def __init__(self):
        super().__init__('tour_manager')

        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # Subscriptions
        self.create_subscription(Int32,  '/gesture',     self.gesture_callback, 10)
        self.create_subscription(String, '/qr_detected', self.qr_callback,      10)

        # Publishers
        self.speak_pub    = self.create_publisher(String, '/speak',          10)
        self.qr_active_pub = self.create_publisher(Bool,  '/qr_scan_active', 10)

        self.state            = STATE_HOME
        self.current_landmark = None

        self.get_logger().info('Tour manager ready')
        self._speak('Tour guide ready. Hold up one, two, or three fingers to go to a landmark.')

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def gesture_callback(self, msg):
        gesture = msg.data

        if self.state == STATE_NAVIGATING:
            self.get_logger().info('Gesture ignored — navigation in progress')
            return

        if gesture in (1, 2, 3):
            self._go_to_landmark(gesture)
        elif gesture == GESTURE_WAVE:
            if self.state == STATE_AT_LANDMARK:
                self._go_home()
            else:
                self.get_logger().info('Wave ignored — already at home')

    def qr_callback(self, msg):
        if self.state != STATE_AT_LANDMARK:
            return
        content     = msg.data
        description = LANDMARK_DESCRIPTIONS.get(content, content)
        self._speak(description)
        self._speak(
            'Hold up one, two, or three fingers to visit another landmark, '
            'or wave to return home.'
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_to_landmark(self, landmark_num):
        self.state            = STATE_NAVIGATING
        self.current_landmark = landmark_num
        self.get_logger().info(f'Navigating to Landmark {landmark_num}')
        self._speak(f'Heading to landmark {landmark_num}. Please follow me.')
        x, y, yaw = LANDMARK_POSITIONS[landmark_num]
        self._navigate_to(x, y, yaw, on_complete=self._arrived_at_landmark)

    def _go_home(self):
        self.state = STATE_RETURNING
        self.get_logger().info('Returning home')
        self._speak('Returning to the starting position. Thank you for joining the tour.')
        x, y, yaw = HOME_POSITION
        self._navigate_to(x, y, yaw, on_complete=self._arrived_home)

    def _arrived_at_landmark(self):
        self.state = STATE_AT_LANDMARK
        self.get_logger().info(f'Arrived at Landmark {self.current_landmark} — scanning QR')
        self._speak('Arrived. Scanning the landmark now.')
        msg      = Bool()
        msg.data = True
        self.qr_active_pub.publish(msg)

    def _arrived_home(self):
        self.state            = STATE_HOME
        self.current_landmark = None
        self.get_logger().info('Arrived home')
        self._speak('Back home. Hold up fingers to select a landmark.')

    # ------------------------------------------------------------------
    # Nav2 action helpers
    # ------------------------------------------------------------------

    def _navigate_to(self, x, y, yaw, on_complete):
        if not self.nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('Nav2 action server not available')
            self.state = STATE_HOME
            return

        goal                              = NavigateToPose.Goal()
        goal.pose                         = PoseStamped()
        goal.pose.header.frame_id         = 'map'
        goal.pose.header.stamp            = self.get_clock().now().to_msg()
        goal.pose.pose.position.x         = float(x)
        goal.pose.pose.position.y         = float(y)
        goal.pose.pose.orientation.z      = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w      = math.cos(yaw / 2.0)

        future = self.nav_client.send_goal_async(goal)
        future.add_done_callback(lambda f: self._goal_response(f, on_complete))

    def _goal_response(self, future, on_complete):
        handle = future.result()
        if not handle.accepted:
            self.get_logger().error('Navigation goal rejected')
            self.state = STATE_HOME
            return
        handle.get_result_async().add_done_callback(
            lambda f: self._nav_done(f, on_complete)
        )

    def _nav_done(self, future, on_complete):
        on_complete()

    # ------------------------------------------------------------------
    # TTS helper
    # ------------------------------------------------------------------

    def _speak(self, text):
        msg      = String()
        msg.data = text
        self.speak_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = TourManager()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
