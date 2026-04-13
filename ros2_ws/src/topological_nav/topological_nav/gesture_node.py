import sys
import os

# Add venv site-packages if a venv exists in the workspace root.
# COLCON_PREFIX_PATH is set by sourcing install/setup.bash and points to
# the install directory, so the workspace root is one level up.
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
from std_msgs.msg import Int32
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import mediapipe as mp
import time

# Gesture codes published on /gesture
GESTURE_NONE  = 0
GESTURE_ONE   = 1
GESTURE_TWO   = 2
GESTURE_THREE = 3
GESTURE_FIVE  = 5
GESTURE_WAVE  = 10

# Finger tip and PIP landmark IDs (MediaPipe hand model)
FINGER_TIPS = [8, 12, 16, 20]   # index, middle, ring, pinky
FINGER_PIPS = [6, 10, 14, 18]


class GestureNode(Node):

    def __init__(self):
        super().__init__('gesture_node')

        self.pub = self.create_publisher(Int32, '/gesture', 10)
        self.bridge = CvBridge()

        self.create_subscription(
            Image, '/oakd/rgb/preview/image_raw', self.image_callback, 10)

        # static_image_mode=False uses cheap tracking between detections
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.3,
            min_tracking_confidence=0.3,
        )

        # Only process 1 frame per second to save CPU on RPi
        self.PROCESS_EVERY_S  = 1.0
        self._last_process    = 0.0

        # Wave detection: track wrist x over a short history
        self.wrist_x_history = []
        self.WAVE_WINDOW      = 5     # reduced (fewer frames at 1 fps)
        self.WAVE_THRESHOLD   = 0.18  # normalized image width

        # Debounce: gesture must be consistent for N checks before publishing
        self.gesture_buffer = []
        self.BUFFER_LEN     = 3      # reduced to match lower frame rate

        # Cooldown so one gesture doesn't fire repeatedly
        self.last_published      = GESTURE_NONE
        self.last_publish_time   = 0.0
        self.COOLDOWN_S          = 2.0

        self.get_logger().info('Gesture node ready — listening on /oakd/rgb/preview/image_raw')

    # ------------------------------------------------------------------
    # Image callback
    # ------------------------------------------------------------------

    def image_callback(self, msg):
        now = time.time()
        if now - self._last_process < self.PROCESS_EVERY_S:
            return
        self._last_process = now

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='rgb8')
        result = self.hands.process(frame)

        gesture = GESTURE_NONE
        if result.multi_hand_landmarks:
            lm = result.multi_hand_landmarks[0].landmark
            if self._is_wave(lm):
                gesture = GESTURE_WAVE
            else:
                fingers_up = self._fingers_up(lm)
                total = self._count_fingers(lm)
                self.get_logger().info(
                    f'Hand detected: fingers_up={fingers_up} total={total}',
                    throttle_duration_sec=0.5)
                # Open hand: all 4 main fingers extended → GESTURE_FIVE
                # (thumb detection is skipped — unreliable across hand orientations)
                if fingers_up == 4:
                    gesture = GESTURE_FIVE
                elif total in (1, 2, 3):
                    gesture = total
        else:
            self.get_logger().info('No hand detected', throttle_duration_sec=2.0)

        self._update_buffer(gesture)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fingers_up(self, lm):
        """Count the 4 main fingers (index–pinky) that are extended."""
        return sum(
            1 for tip, pip in zip(FINGER_TIPS, FINGER_PIPS)
            if lm[tip].y < lm[pip].y
        )

    def _count_fingers(self, lm):
        """Count extended fingers including thumb (thumb uses x comparison)."""
        count = self._fingers_up(lm)
        # Thumb: works for left hand / mirrored image
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
        self.last_published    = gesture
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
