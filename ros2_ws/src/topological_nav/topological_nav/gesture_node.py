import os
import sys
import time

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

import cv2
import mediapipe as mp
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Int32

GESTURE_NONE = 0
GESTURE_ONE = 1
GESTURE_TWO = 2
GESTURE_THREE = 3
GESTURE_FIVE = 5
GESTURE_WAVE = 10

FINGER_TIPS = [8, 12, 16, 20]
FINGER_PIPS = [6, 10, 14, 18]

STATE_QOS = QoSProfile(
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class GestureNode(Node):
    def __init__(self):
        super().__init__('gesture_node')

        self.pub = self.create_publisher(Int32, '/gesture', 10)
        self.bridge = CvBridge()

        self.image_topics = [
            '/oakd/rgb/image_raw',
            '/oakd/rgb/preview/image_raw',
            '/camera/color/image_raw',
            '/color/image_raw',
        ]
        self._image_subs = []
        for topic in self.image_topics:
            self._image_subs.append(
                self.create_subscription(
                    Image,
                    topic,
                    lambda msg, topic=topic: self.image_callback(msg, topic),
                    qos_profile_sensor_data,
                )
            )
        self.create_subscription(
            Bool, '/gesture_mode_enabled', self.mode_callback, STATE_QOS
        )

        self.enabled = False
        self._last_process = 0.0
        self.PROCESS_INTERVAL = 0.25
        self.last_image_topic = None

        self.wrist_x_history = []
        self.WAVE_WINDOW = 8
        self.WAVE_THRESHOLD = 0.18

        self.gesture_buffer = []
        self.BUFFER_LEN = 3
        self.last_published = GESTURE_NONE
        self.last_publish_time = 0.0
        self.COOLDOWN_S = 2.0

        self.hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            model_complexity=1,
            max_num_hands=1,
            min_detection_confidence=0.15,
            min_tracking_confidence=0.15,
        )

        self.get_logger().info(
            'Gesture node ready - waiting for gesture mode on '
            + ', '.join(self.image_topics)
        )

    def mode_callback(self, msg: Bool):
        if msg.data == self.enabled:
            return
        self.enabled = msg.data
        self.gesture_buffer.clear()
        self.wrist_x_history.clear()
        self.last_published = GESTURE_NONE
        self.last_publish_time = 0.0
        state = 'ENABLED' if self.enabled else 'DISABLED'
        self.get_logger().info(f'Gesture mode {state}')

    def image_callback(self, msg: Image, topic: str):
        if not self.enabled:
            return

        now = time.time()
        if now - self._last_process < self.PROCESS_INTERVAL:
            return
        self._last_process = now
        if topic != self.last_image_topic:
            self.last_image_topic = topic
            self.get_logger().info(f'Gesture images received from {topic}')

        rgb_frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='rgb8')
        h, w = rgb_frame.shape[:2]

        # MediaPipe is noticeably more reliable on the tiny preview stream
        # if we upscale before inference.
        if min(h, w) < 400:
            scale = max(2, int(640 / min(h, w)))
            rgb_frame = cv2.resize(
                rgb_frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
            )

        rgb_frame.flags.writeable = False
        result = self.hands.process(rgb_frame)
        rgb_frame.flags.writeable = True

        gesture = GESTURE_NONE
        if result.multi_hand_landmarks:
            lm = result.multi_hand_landmarks[0].landmark
            if self._is_wave(lm):
                gesture = GESTURE_WAVE
            else:
                fingers_up = self._fingers_up(lm)
                total = self._count_fingers(lm)
                if fingers_up == 4:
                    gesture = GESTURE_FIVE
                elif total in (1, 2, 3):
                    gesture = total
        else:
            self.get_logger().info(
                f'No hand detected on {topic} ({w}x{h})',
                throttle_duration_sec=2.0,
            )

        self._update_buffer(gesture)

    def _fingers_up(self, lm):
        return sum(
            1 for tip, pip in zip(FINGER_TIPS, FINGER_PIPS)
            if lm[tip].y < lm[pip].y
        )

    def _count_fingers(self, lm):
        count = self._fingers_up(lm)
        if lm[4].x < lm[3].x:
            count += 1
        return count

    def _is_wave(self, lm):
        self.wrist_x_history.append(lm[0].x)
        if len(self.wrist_x_history) > self.WAVE_WINDOW:
            self.wrist_x_history.pop(0)
        if len(self.wrist_x_history) < self.WAVE_WINDOW:
            return False
        return (max(self.wrist_x_history) - min(self.wrist_x_history)) > self.WAVE_THRESHOLD

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
        if gesture == self.last_published and (now - self.last_publish_time) < self.COOLDOWN_S:
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
