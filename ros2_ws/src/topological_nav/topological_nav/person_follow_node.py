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

import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, String
from ultralytics import YOLO

KP_ANGULAR = 1.5
LINEAR_SPEED = 0.15
STOP_HEIGHT_RATIO = 0.80
MIN_CONF = 0.25
SEARCH_TURN_SPEED = 0.0
NO_PERSON_TIMEOUT_S = 5.0

STATE_QOS = QoSProfile(
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
        self.PROCESS_EVERY = 6

        self.model = YOLO('yolov8n.pt')
        self.get_logger().info('YOLOv8n loaded')

        self.cmd_pub = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        self.speak_pub = self.create_publisher(String, '/speak', 10)
        self.timeout_pub = self.create_publisher(Bool, '/person_follow_timeout', 10)

        self.create_subscription(
            Image, '/oakd/rgb/preview/image_raw', self.image_callback, qos_profile_sensor_data
        )
        self.create_subscription(
            Bool, '/person_follow_active', self.active_callback, STATE_QOS
        )

        self.person_visible = False
        self.last_announce_time = 0.0
        self.ANNOUNCE_INTERVAL = 1
        self.last_person_time = time.time()
        self.timeout_sent = False

        self.get_logger().info('Person follow node ready - waiting on /person_follow_active')

    def active_callback(self, msg: Bool):
        if msg.data == self.active:
            return
        self.active = msg.data
        self.get_logger().info(
            f'Person following {"ENABLED" if self.active else "DISABLED"}'
        )
        self.last_person_time = time.time()
        self.timeout_sent = False
        if not self.active:
            self._publish_stop()

    def image_callback(self, msg: Image):
        if not self.active:
            return

        self._frame_count += 1
        if self._frame_count % self.PROCESS_EVERY != 0:
            return

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        h, w = frame.shape[:2]
        small = frame[::2, ::2]

        results = self.model(small, classes=[0], conf=MIN_CONF, verbose=False)
        box = self._largest_person(results)
        if box is not None:
            x1, y1, x2, y2 = box
            box = (x1 * 2, y1 * 2, x2 * 2, y2 * 2)

        if box is None:
            self.get_logger().info('No person detected')
            self.person_visible = False
            cmd = TwistStamped()
            cmd.twist.angular.z = SEARCH_TURN_SPEED
            self.cmd_pub.publish(cmd)

            now = time.time()
            if (now - self.last_person_time) >= NO_PERSON_TIMEOUT_S and not self.timeout_sent:
                timeout_msg = Bool()
                timeout_msg.data = True
                self.timeout_pub.publish(timeout_msg)
                self.timeout_sent = True
                self.get_logger().info('No person for 5 seconds - requesting gesture mode')
            return

        self.last_person_time = time.time()
        self.timeout_sent = False

        now = time.time()
        if not self.person_visible or (now - self.last_announce_time) >= self.ANNOUNCE_INTERVAL:
            self.person_visible = True
            self.last_announce_time = now
            msg = String()
            msg.data = 'feet detected'
            self.speak_pub.publish(msg)

        x1, y1, x2, y2 = box
        cx = (x1 + x2) / 2.0
        box_h = y2 - y1
        offset = (cx / w) - 0.5

        angular_z = -KP_ANGULAR * offset
        height_ratio = box_h / h
        linear_x = 0.0 if height_ratio >= STOP_HEIGHT_RATIO else LINEAR_SPEED

        cmd = TwistStamped()
        cmd.twist.linear.x = linear_x
        cmd.twist.angular.z = angular_z
        self.cmd_pub.publish(cmd)

        self.get_logger().info(
            f'offset={offset:+.2f}  h_ratio={height_ratio:.2f}  '
            f'lin={linear_x:.2f}  ang={angular_z:+.2f}'
        )

    def _largest_person(self, results):
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
