import os
import sys
import time

# Add venv site-packages if a venv exists in the workspace root.
_colcon_prefix = os.environ.get('COLCON_PREFIX_PATH', '')
if _colcon_prefix:
    _ws_root = os.path.dirname(_colcon_prefix.split(':')[0])
    _venv_sp = os.path.join(
        _ws_root,
        'venv',
        'lib',
        f'python{sys.version_info.major}.{sys.version_info.minor}',
        'site-packages',
    )
    if os.path.isdir(_venv_sp):
        sys.path.insert(0, _venv_sp)

import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
    qos_profile_sensor_data,
)
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, String
from ultralytics import YOLO

# Person-follow control.
KP_ANGULAR = 0.9          # rad/s per normalized pixel offset
MAX_ANGULAR_SPEED = 0.45  # clamp turn rate to reduce overshoot
LINEAR_SPEED = 0.15       # m/s forward when person is not yet close
STOP_HEIGHT_RATIO = 0.80  # stop driving when person bbox height > 80% of frame
MIN_CONF = 0.25           # minimum YOLO detection confidence
CENTER_DEADBAND = 0.08    # ignore tiny horizontal errors near image center
TURN_SLOWDOWN_AT = 0.22   # stop forward motion when target is far off-center
OFFSET_FILTER_ALPHA = 0.35  # lower = smoother but slower response

# Slow rotation used to search when no person is visible.
SEARCH_TURN_SPEED = 0.0

FOLLOW_STATE_QOS = QoSProfile(
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class PersonFollowNode(Node):
    def __init__(self):
        super().__init__('person_follow_node')

        self.bridge = CvBridge()
        self.active = False
        self._frame_count = 0
        self.PROCESS_EVERY = 6  # only run YOLO on every Nth frame (~2.5 fps)

        # YOLOv8n downloads weights on first run if needed.
        self.model = YOLO('yolov8n.pt')
        self.get_logger().info('YOLOv8n loaded')

        self.cmd_pub = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        self.speak_pub = self.create_publisher(String, '/speak', 10)

        self.create_subscription(
            Image,
            '/oakd/rgb/preview/image_raw',
            self.image_callback,
            qos_profile_sensor_data,
        )

        self.create_subscription(
            Bool,
            '/person_follow_active',
            self.active_callback,
            FOLLOW_STATE_QOS,
        )

        self.person_visible = False
        self.last_announce_time = 0.0
        self.ANNOUNCE_INTERVAL = 1
        self.filtered_offset = 0.0

        self.get_logger().info(
            'Person follow node ready - waiting on /person_follow_active'
        )

    def active_callback(self, msg: Bool):
        if msg.data == self.active:
            return
        self.active = msg.data
        self.get_logger().info(
            f'Person following {"ENABLED" if self.active else "DISABLED"}'
        )
        if not self.active:
            self.filtered_offset = 0.0
            self._publish_stop()

    def image_callback(self, msg: Image):
        if not self.active:
            return

        self._frame_count += 1
        if self._frame_count % self.PROCESS_EVERY != 0:
            return

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        h, w = frame.shape[:2]

        # Resize to speed up inference.
        small = frame[::2, ::2]

        # Detect people only (COCO class 0).
        results = self.model(small, classes=[0], conf=MIN_CONF, verbose=False)
        box = self._largest_person(results)

        # Scale box coords back to original frame size.
        if box is not None:
            x1, y1, x2, y2 = box
            box = (x1 * 2, y1 * 2, x2 * 2, y2 * 2)

        if box is None:
            self.get_logger().info('No person detected')
            self.person_visible = False
            self.filtered_offset = 0.0
            cmd = TwistStamped()
            cmd.twist.angular.z = SEARCH_TURN_SPEED
            self.cmd_pub.publish(cmd)
            return

        # Keep publishing to /speak for compatibility, though person-follow
        # startup now runs silently unless a listener is launched separately.
        now = time.time()
        if (
            not self.person_visible
            or (now - self.last_announce_time) >= self.ANNOUNCE_INTERVAL
        ):
            self.person_visible = True
            self.last_announce_time = now
            msg = String()
            msg.data = 'feet detected'
            self.speak_pub.publish(msg)

        x1, y1, x2, y2 = box
        cx = (x1 + x2) / 2.0
        box_h = y2 - y1

        # Normalized horizontal offset: -0.5 (full left) ... +0.5 (full right)
        raw_offset = (cx / w) - 0.5
        self.filtered_offset = (
            (1.0 - OFFSET_FILTER_ALPHA) * self.filtered_offset
            + OFFSET_FILTER_ALPHA * raw_offset
        )
        offset = self.filtered_offset
        if abs(offset) < CENTER_DEADBAND:
            offset = 0.0

        # Turn to center the person and only drive while mostly centered.
        angular_z = -KP_ANGULAR * offset
        angular_z = max(-MAX_ANGULAR_SPEED, min(MAX_ANGULAR_SPEED, angular_z))

        height_ratio = box_h / h
        if height_ratio >= STOP_HEIGHT_RATIO:
            linear_x = 0.0
        elif abs(offset) >= TURN_SLOWDOWN_AT:
            linear_x = 0.0
        else:
            turn_scale = max(0.35, 1.0 - (abs(offset) / TURN_SLOWDOWN_AT))
            linear_x = LINEAR_SPEED * turn_scale

        cmd = TwistStamped()
        cmd.twist.linear.x = linear_x
        cmd.twist.angular.z = angular_z
        self.cmd_pub.publish(cmd)

        self.get_logger().info(
            f'offset={offset:+.2f} raw={raw_offset:+.2f} '
            f'h_ratio={height_ratio:.2f} lin={linear_x:.2f} ang={angular_z:+.2f}'
        )

    def _largest_person(self, results):
        """Return xyxy bbox of the largest detected person, or None."""
        best_area = 0
        best_box = None
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                area = (x2 - x1) * (y2 - y1)
                if area > best_area:
                    best_area = area
                    best_box = (x1, y1, x2, y2)
        return best_box

    def _publish_stop(self):
        self.cmd_pub.publish(TwistStamped())


def main(args=None):
    rclpy.init(args=args)
    node = PersonFollowNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
