import os
import sys
import time

# Add venv site-packages if a venv exists in the workspace root.
# COLCON_PREFIX_PATH is set by sourcing install/setup.bash and points to
# the install directory, so the workspace root is one level up.
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

import cv2
import mediapipe as mp
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Int32

# Gesture codes published on /gesture
GESTURE_NONE = 0
GESTURE_ONE = 1
GESTURE_TWO = 2
GESTURE_THREE = 3
GESTURE_FIVE = 5
GESTURE_WAVE = 10

# Finger tip and PIP landmark IDs (MediaPipe hand model)
FINGER_TIPS = [8, 12, 16, 20]  # index, middle, ring, pinky
FINGER_PIPS = [6, 10, 14, 18]


class GestureNode(Node):
    def __init__(self):
        super().__init__('gesture_node')

        self.pub = self.create_publisher(Int32, '/gesture', 10)
        self.bridge = CvBridge()
        self.image_topic = self.declare_parameter(
            'image_topic', '/oakd/rgb/preview/image_raw'
        ).value

        self.create_subscription(
            Image,
            self.image_topic,
            self.image_callback,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            Bool,
            '/person_follow_active',
            self._follow_callback,
            10,
        )

        self._following = False

        # Track between frames so detection is less fragile once the hand appears.
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            model_complexity=0,
            max_num_hands=1,
            min_detection_confidence=0.2,
            min_tracking_confidence=0.2,
        )

        # Process at ~5 fps - fast enough to feel responsive on a local machine.
        self._last_process = 0.0
        self.PROCESS_INTERVAL = 0.2

        # Wave detection.
        self.wrist_x_history = []
        self.WAVE_WINDOW = 8
        self.WAVE_THRESHOLD = 0.18

        # Debounce: gesture must be consistent for N frames before publishing.
        self.gesture_buffer = []
        self.BUFFER_LEN = 4

        # Cooldown so one gesture does not fire repeatedly.
        self.last_published = GESTURE_NONE
        self.last_publish_time = 0.0
        self.COOLDOWN_S = 2.0

        self.get_logger().info(
            f'Gesture node ready - listening on {self.image_topic}'
        )

    def _follow_callback(self, msg: Bool):
        self._following = msg.data

    def image_callback(self, msg: Image):
        self.get_logger().info('frame received', throttle_duration_sec=2.0)

        now = time.time()
        if now - self._last_process < self.PROCESS_INTERVAL:
            return
        self._last_process = now

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False
        result = self.hands.process(rgb_frame)
        rgb_frame.flags.writeable = True

        gesture = GESTURE_NONE
        num_hands = (
            len(result.multi_hand_landmarks)
            if result.multi_hand_landmarks
            else 0
        )
        if num_hands > 0:
            lm = result.multi_hand_landmarks[0].landmark
            if self._is_wave(lm):
                self.get_logger().info('HAND: wave')
                gesture = GESTURE_WAVE
            else:
                fingers_up = self._fingers_up(lm)
                total = self._count_fingers(lm)
                self.get_logger().info(
                    f'HAND: {fingers_up} fingers up (total w/thumb={total})'
                )
                if fingers_up == 4:
                    gesture = GESTURE_FIVE
                elif total in (1, 2, 3):
                    gesture = total
        else:
            self.wrist_x_history.clear()
            self.get_logger().info('NO HAND - hold open hand close to camera')

        self._update_buffer(gesture)

    def _fingers_up(self, lm):
        """Count the four main fingers that are extended."""
        return sum(
            1
            for tip, pip in zip(FINGER_TIPS, FINGER_PIPS)
            if lm[tip].y < lm[pip].y
        )

    def _count_fingers(self, lm):
        """Count extended fingers including the thumb."""
        count = self._fingers_up(lm)
        # Thumb check assumes a mirrored image or left-hand presentation.
        if lm[4].x < lm[3].x:
            count += 1
        return count

    def _is_wave(self, lm):
        """Detect horizontal wrist movement across recent frames."""
        self.wrist_x_history.append(lm[0].x)
        if len(self.wrist_x_history) > self.WAVE_WINDOW:
            self.wrist_x_history.pop(0)
        if len(self.wrist_x_history) < self.WAVE_WINDOW:
            return False
        return (
            max(self.wrist_x_history) - min(self.wrist_x_history)
        ) > self.WAVE_THRESHOLD

    def _update_buffer(self, gesture):
        self.gesture_buffer.append(gesture)
        if len(self.gesture_buffer) > self.BUFFER_LEN:
            self.gesture_buffer.pop(0)

        if len(self.gesture_buffer) < self.BUFFER_LEN:
            return
        if not all(g == gesture for g in self.gesture_buffer):
            return
        if gesture == GESTURE_NONE:
            return

        now = time.time()
        if (
            gesture == self.last_published
            and (now - self.last_publish_time) < self.COOLDOWN_S
        ):
            return

        msg = Int32()
        msg.data = gesture
        self.pub.publish(msg)
        self.last_published = gesture
        self.last_publish_time = now
        self.get_logger().info(f'Gesture published: {gesture}')


def main(args=None):
    rclpy.init(args=args)
    node = GestureNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
