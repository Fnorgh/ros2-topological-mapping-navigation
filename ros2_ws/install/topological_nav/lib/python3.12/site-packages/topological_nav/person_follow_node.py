import sys
import os
import time
import math
import yaml
from enum import Enum, auto

# Add venv site-packages for YOLO
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
from rclpy.action import ActionClient
from geometry_msgs.msg import TwistStamped, PoseStamped
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, String, Int32
from cv_bridge import CvBridge
from nav2_msgs.action import NavigateToPose
import tf2_ros
from ultralytics import YOLO

# ── Constants ─────────────────────────────────────────────────────────────────
KP_ANGULAR        = 1.5
LINEAR_SPEED      = 0.15
STOP_HEIGHT_RATIO = 0.80
MIN_CONF          = 0.25
SEARCH_TURN_SPEED = 0.0
QR_STOP_DELAY     = 5.0   # seconds stopped → switch to WAITING_GESTURE

GESTURE_ONE  = 1   # → go to landmark 1
GESTURE_TWO  = 2   # → go to landmark 2
GESTURE_THREE= 3   # → go to landmark 3
GESTURE_FOUR = 4   # → go to closest landmark
GESTURE_FIVE = 5   # → go home

LANDMARKS_FILE = os.path.expanduser(
    '~/robotics/ros2-topological-mapping-navigation/landmarks.yaml'
)


def _load_landmarks():
    if not os.path.exists(LANDMARKS_FILE):
        return {}, None
    with open(LANDMARKS_FILE) as f:
        data = yaml.safe_load(f) or {}
    landmarks = {int(k): tuple(v) for k, v in data.get('landmarks', {}).items()}
    home = tuple(data['home']) if data.get('home') else None
    return landmarks, home


class State(Enum):
    FOLLOWING       = auto()  # following the person
    WAITING_GESTURE = auto()  # stopped, watching for 4 or 5 fingers
    NAVIGATING      = auto()  # driving to a landmark via nav2
    QR_READING      = auto()  # at landmark, QR scanner active
    GOING_HOME      = auto()  # driving back to home position


class PersonFollowNode(Node):

    def __init__(self):
        super().__init__('person_follow_node')

        self.landmarks, self.home = _load_landmarks()
        self.get_logger().info(
            f'Loaded {len(self.landmarks)} landmark(s), '
            f'home {"set" if self.home else "NOT SET"}')

        self.bridge = CvBridge()
        self.model  = YOLO('yolov8n.pt')
        self.get_logger().info('YOLOv8n loaded')

        # TF for current map-frame position
        self.tf_buffer   = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # Nav2
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # Publishers
        self.cmd_pub     = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        self.speak_pub   = self.create_publisher(String,       '/speak',   10)
        self.qr_scan_pub = self.create_publisher(Bool,         '/qr_scan_active', 10)

        # Subscriptions
        self.create_subscription(
            Image,  '/oakd/rgb/preview/image_raw', self.image_callback, 10)
        self.create_subscription(
            Bool,   '/person_follow_active',        self.active_callback, 10)
        self.create_subscription(
            Int32,  '/gesture',                     self.gesture_callback, 10)
        self.create_subscription(
            String, '/qr_detected',                 self.qr_callback,     10)

        # State
        self.active          = False
        self.state           = State.FOLLOWING
        self._frame_count    = 0
        self.PROCESS_EVERY   = 3
        self.person_visible  = False
        self._had_person     = False  # True once a person has been seen this session
        self.last_announce   = 0.0
        self.ANNOUNCE_INTERVAL = 1.0
        self._stopped_since  = None

        self.get_logger().info('Person follow node ready — waiting on /person_follow_active')

    # ── Enable / disable ──────────────────────────────────────────────────────

    def active_callback(self, msg: Bool):
        if msg.data == self.active:
            return
        self.active = msg.data
        self.get_logger().info(
            f'Person following {"ENABLED" if self.active else "DISABLED"}')
        if self.active:
            self._enter(State.FOLLOWING)
        else:
            self._publish_stop()

    # ── Gesture callback ──────────────────────────────────────────────────────

    def gesture_callback(self, msg: Int32):
        if self.state != State.WAITING_GESTURE:
            return

        g = msg.data

        # 1/2/3 fingers → go directly to that landmark
        if g in (GESTURE_ONE, GESTURE_TWO, GESTURE_THREE):
            pose = self.landmarks.get(g)
            if pose is None:
                self._speak(f'Landmark {g} not saved.')
                return
            self.get_logger().info(f'Gesture {g} → navigating to landmark {g}')
            self._speak(f'Heading to landmark {g}.')
            self._enter(State.NAVIGATING)
            self._navigate_to(*pose, on_complete=self._arrived_at_landmark)

        # 4 fingers → closest landmark
        elif g == GESTURE_FOUR:
            target = self._closest_landmark()
            if target is None:
                self._speak('No landmarks saved yet.')
                return
            lm_id, pose = target
            self.get_logger().info(f'Gesture 4 → navigating to closest landmark {lm_id}')
            self._speak(f'Heading to landmark {lm_id}.')
            self._enter(State.NAVIGATING)
            self._navigate_to(*pose, on_complete=self._arrived_at_landmark)

        # 5 fingers → go home
        elif g == GESTURE_FIVE:
            if self.home is None:
                self._speak('Home position not saved.')
                return
            self.get_logger().info('Gesture 5 → going home')
            self._speak('Returning home.')
            self._enter(State.GOING_HOME)
            self._navigate_to(*self.home, on_complete=self._arrived_home)

    # ── QR callback ───────────────────────────────────────────────────────────

    def qr_callback(self, msg: String):
        if self.state != State.QR_READING:
            return
        self.get_logger().info(f'QR read: "{msg.data}" → back to WAITING_GESTURE')
        self._enter(State.WAITING_GESTURE)

    # ── Image callback ────────────────────────────────────────────────────────

    def image_callback(self, msg: Image):
        if not self.active:
            return

        if self.state in (State.WAITING_GESTURE, State.QR_READING,
                          State.NAVIGATING, State.GOING_HOME):
            self._publish_stop()
            return

        # ── FOLLOWING ─────────────────────────────────────────────────────────
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
            self.person_visible = False
            # Only start the timer if we've already seen a person this session
            if self._had_person:
                if self._stopped_since is None:
                    self._stopped_since = now
                elif now - self._stopped_since >= QR_STOP_DELAY:
                    self._enter(State.WAITING_GESTURE)
            cmd = TwistStamped()
            cmd.twist.angular.z = SEARCH_TURN_SPEED
            self.cmd_pub.publish(cmd)
            return

        if not self.person_visible or (now - self.last_announce) >= self.ANNOUNCE_INTERVAL:
            self.person_visible = True
            self._had_person    = True
            self._stopped_since = None  # reset timer — person is back
            self.last_announce  = now
            speak = String()
            speak.data = 'feet detected'
            self.speak_pub.publish(speak)

        x1, y1, x2, y2 = box
        cx           = (x1 + x2) / 2.0
        box_h        = y2 - y1
        offset       = (cx / w) - 0.5
        angular_z    = -KP_ANGULAR * offset
        height_ratio = box_h / h
        linear_x     = 0.0 if height_ratio >= STOP_HEIGHT_RATIO else LINEAR_SPEED

        cmd = TwistStamped()
        cmd.twist.linear.x  = linear_x
        cmd.twist.angular.z = angular_z
        self.cmd_pub.publish(cmd)

        # Track stopped time → transition to WAITING_GESTURE
        if linear_x == 0.0:
            if self._stopped_since is None:
                self._stopped_since = now
            elif now - self._stopped_since >= QR_STOP_DELAY:
                self._enter(State.WAITING_GESTURE)
        else:
            self._stopped_since = None

        self.get_logger().info(
            f'[{self.state.name}] offset={offset:+.2f} '
            f'h={height_ratio:.2f} lin={linear_x:.2f}')

    # ── State transitions ─────────────────────────────────────────────────────

    def _enter(self, state: State):
        self.state = state
        self.get_logger().info(f'State → {state.name}')

        if state == State.FOLLOWING:
            self._stopped_since = None
            self.person_visible = False
            self._had_person    = False

        elif state == State.WAITING_GESTURE:
            self._publish_stop()
            self._speak('Stopped. Show 4 fingers to go to nearest landmark, or 5 to go home.')

        elif state == State.QR_READING:
            self._publish_stop()
            self._speak('Arrived. Scanning QR code.')
            qr = Bool()
            qr.data = True
            self.qr_scan_pub.publish(qr)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _closest_landmark(self):
        """Return (id, (x, y, yaw)) of the landmark nearest to the robot."""
        pos = self._get_map_pose()
        if pos is None or not self.landmarks:
            return None
        rx, ry = pos[0], pos[1]
        best_id, best_dist = min(
            self.landmarks.items(),
            key=lambda kv: math.hypot(kv[1][0] - rx, kv[1][1] - ry)
        )
        return best_id, self.landmarks[best_id]

    def _get_map_pose(self):
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
            x   = t.transform.translation.x
            y   = t.transform.translation.y
            qz  = t.transform.rotation.z
            qw  = t.transform.rotation.w
            yaw = 2.0 * math.atan2(qz, qw)
            return (x, y, yaw)
        except Exception:
            return None

    def _navigate_to(self, x, y, yaw, on_complete):
        if not self.nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('Nav2 not available')
            self._enter(State.WAITING_GESTURE)
            return
        goal                         = NavigateToPose.Goal()
        goal.pose                    = PoseStamped()
        goal.pose.header.frame_id    = 'map'
        goal.pose.header.stamp       = self.get_clock().now().to_msg()
        goal.pose.pose.position.x    = float(x)
        goal.pose.pose.position.y    = float(y)
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)
        future = self.nav_client.send_goal_async(goal)
        future.add_done_callback(lambda f: self._goal_response(f, on_complete))

    def _goal_response(self, future, on_complete):
        handle = future.result()
        if not handle.accepted:
            self.get_logger().error('Navigation goal rejected')
            self._enter(State.WAITING_GESTURE)
            return
        handle.get_result_async().add_done_callback(
            lambda f: on_complete())

    def _arrived_at_landmark(self):
        self._enter(State.QR_READING)

    def _arrived_home(self):
        self._speak('Home. Ready to follow again.')
        self._enter(State.FOLLOWING)

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

    def _speak(self, text: str):
        msg = String()
        msg.data = text
        self.speak_pub.publish(msg)


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
