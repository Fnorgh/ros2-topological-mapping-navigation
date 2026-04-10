import sys
import os

# Add venv site-packages if a venv exists in the workspace root.
_colcon_prefix = os.environ.get('COLCON_PREFIX_PATH', '')
if _colcon_prefix:
    _ws_root = os.path.dirname(_colcon_prefix.split(':')[0])
    _venv_sp = os.path.join(
        _ws_root, 'venv', 'lib',
        f'python{sys.version_info.major}.{sys.version_info.minor}',
        'site-packages',
    )
    if os.path.isdir(_venv_sp):
        sys.path.insert(0, _venv_sp)

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from cv_bridge import CvBridge
from ultralytics import YOLO

# ── Proportional control ──────────────────────────────────────────────────────
KP_ANGULAR       = 1.5    # rad/s per normalised pixel offset
LINEAR_SPEED     = 0.15   # m/s forward when person is not yet close
STOP_HEIGHT_RATIO = 0.80  # stop driving when person bbox height > 80 % of frame
MIN_CONF         = 0.25   # minimum YOLO detection confidence

# Slow rotation used to search when no person is visible
SEARCH_TURN_SPEED = 0.0   # rad/s


class PersonFollowNode(Node):

    def __init__(self):
        super().__init__('person_follow_node')

        self.bridge = CvBridge()
        self.active = False

        # YOLOv8n – downloads weights (~6 MB) on first run
        self.model = YOLO('yolov8n.pt')
        self.get_logger().info('YOLOv8n loaded')

        self.cmd_pub = self.create_publisher(TwistStamped, '/cmd_vel', 10)

        self.create_subscription(
            Image, '/oakd/rgb/preview/image_raw', self.image_callback, 10)

        # Publish True/False on this topic to enable / disable following.
        # e.g.:  ros2 topic pub /person_follow_active std_msgs/Bool "data: true"
        self.create_subscription(
            Bool, '/person_follow_active', self.active_callback, 10)

        self.get_logger().info(
            'Person follow node ready – waiting on /person_follow_active')

    # ── Enable / disable ─────────────────────────────────────────────────────

    def active_callback(self, msg: Bool):
        if msg.data == self.active:
            return
        self.active = msg.data
        self.get_logger().info(
            f'Person following {"ENABLED" if self.active else "DISABLED"}')
        if not self.active:
            self._publish_stop()

    # ── Image callback ────────────────────────────────────────────────────────

    def image_callback(self, msg: Image):
        if not self.active:
            return

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        h, w = frame.shape[:2]

        # Detect people only (COCO class 0)
        results = self.model(frame, classes=[0], conf=MIN_CONF, verbose=False)
        box = self._largest_person(results)

        if box is None:
            self.get_logger().info('No person detected')
            cmd = TwistStamped()
            cmd.twist.angular.z = SEARCH_TURN_SPEED
            self.cmd_pub.publish(cmd)
            return

        x1, y1, x2, y2 = box
        cx = (x1 + x2) / 2.0
        box_h = y2 - y1

        # Normalised horizontal offset: −0.5 (full left) … +0.5 (full right)
        offset = (cx / w) - 0.5

        # Turn to centre the person; drive forward unless they fill the frame
        angular_z = -KP_ANGULAR * offset
        height_ratio = box_h / h
        linear_x = 0.0 if height_ratio >= STOP_HEIGHT_RATIO else LINEAR_SPEED

        cmd = TwistStamped()
        cmd.twist.linear.x = linear_x
        cmd.twist.angular.z = angular_z
        self.cmd_pub.publish(cmd)

        self.get_logger().info(
            f'offset={offset:+.2f}  h_ratio={height_ratio:.2f}  '
            f'lin={linear_x:.2f}  ang={angular_z:+.2f}')

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _largest_person(self, results):
        """Return xyxy bbox of the largest detected person, or None."""
        best_area = 0
        best_box  = None
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                area = (x2 - x1) * (y2 - y1)
                if area > best_area:
                    best_area = area
                    best_box  = (x1, y1, x2, y2)
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
