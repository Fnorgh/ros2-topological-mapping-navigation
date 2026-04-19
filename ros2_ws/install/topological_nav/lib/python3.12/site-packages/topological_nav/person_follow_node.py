import sys
import os
import time
from enum import Enum, auto

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
from std_msgs.msg import Bool, String
from cv_bridge import CvBridge
from ultralytics import YOLO

# ── Proportional control ──────────────────────────────────────────────────────
KP_ANGULAR        = 1.5   # rad/s per normalised pixel offset
LINEAR_SPEED      = 0.15  # m/s forward when person is not yet close
STOP_HEIGHT_RATIO = 0.80  # stop driving when person bbox height > 80 % of frame
MIN_CONF          = 0.25  # minimum YOLO detection confidence
SEARCH_TURN_SPEED = 0.0   # rad/s while searching for person
QR_STOP_DELAY     = 5.0   # seconds stopped before switching to QR_READING


class State(Enum):
    FOLLOWING  = auto()   # actively following the person
    QR_READING = auto()   # fully stopped, QR scanner active


class PersonFollowNode(Node):

    def __init__(self):
        super().__init__('person_follow_node')

        self.bridge = CvBridge()
        self.active = False
        self.state  = State.FOLLOWING
        self._frame_count = 0
        self.PROCESS_EVERY = 3

        self.model = YOLO('yolov8n.pt')
        self.get_logger().info('YOLOv8n loaded')

        self.cmd_pub     = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        self.speak_pub   = self.create_publisher(String, '/speak', 10)
        self.qr_scan_pub = self.create_publisher(Bool, '/qr_scan_active', 10)

        self.create_subscription(
            Image, '/oakd/rgb/preview/image_raw', self.image_callback, 10)
        self.create_subscription(
            Bool, '/person_follow_active', self.active_callback, 10)
        self.create_subscription(
            String, '/qr_detected', self.qr_detected_callback, 10)

        self.person_visible     = False
        self.last_announce_time = 0.0
        self.ANNOUNCE_INTERVAL  = 1.0

        self._stopped_since = None  # timestamp when robot first stopped with person visible

        self.get_logger().info('Person follow node ready — waiting on /person_follow_active')

    # ── Enable / disable ──────────────────────────────────────────────────────

    def active_callback(self, msg: Bool):
        if msg.data == self.active:
            return
        self.active = msg.data
        self.get_logger().info(
            f'Person following {"ENABLED" if self.active else "DISABLED"}')
        if self.active:
            self._enter_following()
        else:
            self._publish_stop()

    # ── QR detected — result is in; stay stopped ──────────────────────────────

    def qr_detected_callback(self, msg: String):
        if self.state == State.QR_READING:
            self.get_logger().info(f'QR read: "{msg.data}" — staying stopped')

    # ── Image callback ────────────────────────────────────────────────────────

    def image_callback(self, msg: Image):
        if not self.active:
            return

        # In QR_READING state the robot is fully stopped — publish zero vel
        # to hold position and do nothing else.
        if self.state == State.QR_READING:
            self._publish_stop()
            return

        # ── FOLLOWING state ───────────────────────────────────────────────────
        self._frame_count += 1
        if self._frame_count % self.PROCESS_EVERY != 0:
            return

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        h, w  = frame.shape[:2]
        small = frame[::2, ::2]

        results = self.model(small, classes=[0], conf=MIN_CONF, verbose=False)
        box = self._largest_person(results)
        if box is not None:
            x1, y1, x2, y2 = box
            box = (x1 * 2, y1 * 2, x2 * 2, y2 * 2)

        now = time.time()

        if box is None:
            self.get_logger().info('No person detected')
            self.person_visible = False
            self._stopped_since = None
            cmd = TwistStamped()
            cmd.twist.angular.z = SEARCH_TURN_SPEED
            self.cmd_pub.publish(cmd)
            return

        # Announce detection
        if not self.person_visible or (now - self.last_announce_time) >= self.ANNOUNCE_INTERVAL:
            self.person_visible     = True
            self.last_announce_time = now
            speak = String()
            speak.data = 'feet detected'
            self.speak_pub.publish(speak)

        x1, y1, x2, y2 = box
        cx       = (x1 + x2) / 2.0
        box_h    = y2 - y1
        offset   = (cx / w) - 0.5
        angular_z    = -KP_ANGULAR * offset
        height_ratio = box_h / h
        linear_x     = 0.0 if height_ratio >= STOP_HEIGHT_RATIO else LINEAR_SPEED

        cmd = TwistStamped()
        cmd.twist.linear.x  = linear_x
        cmd.twist.angular.z = angular_z
        self.cmd_pub.publish(cmd)

        # Track consecutive stopped time while person is visible and close
        if linear_x == 0.0:
            if self._stopped_since is None:
                self._stopped_since = now
            elif now - self._stopped_since >= QR_STOP_DELAY:
                self._enter_qr_reading()
        else:
            self._stopped_since = None

        self.get_logger().info(
            f'[{self.state.name}]  offset={offset:+.2f}  '
            f'h_ratio={height_ratio:.2f}  lin={linear_x:.2f}  ang={angular_z:+.2f}')

    # ── State transitions ─────────────────────────────────────────────────────

    def _enter_following(self):
        self.state          = State.FOLLOWING
        self._stopped_since = None
        self.person_visible = False
        self.get_logger().info('State → FOLLOWING')

    def _enter_qr_reading(self):
        self.state = State.QR_READING
        self._publish_stop()
        self.get_logger().info('State → QR_READING — robot stopped, activating QR scanner')
        qr_msg = Bool()
        qr_msg.data = True
        self.qr_scan_pub.publish(qr_msg)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _largest_person(self, results):
        best_area, best_box = 0, None
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
