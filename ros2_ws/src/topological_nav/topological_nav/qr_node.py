import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
    qos_profile_sensor_data,
)
from std_msgs.msg import String, Bool
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import time

# Published to /qr_detected (String) when a QR code is read.
# Scanning is active only while /person_follow_active (Bool True) is received.
# Same code will not re-fire within COOLDOWN_SEC seconds.

COOLDOWN_SEC = 2.0
FOLLOW_STATE_QOS = QoSProfile(
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class QRNode(Node):

    def __init__(self):
        super().__init__('qr_node')

        self.pub = self.create_publisher(String, '/qr_detected', 10)

        self.create_subscription(
            Image,
            '/oakd/rgb/preview/image_raw',
            self.image_callback,
            qos_profile_sensor_data)
        self.create_subscription(
            Bool, '/person_follow_active', self.active_callback, FOLLOW_STATE_QOS)

        self.bridge      = CvBridge()
        self.detector    = cv2.QRCodeDetector()
        self.active      = False
        self.last_result = ''
        self.last_time   = 0.0

        self.get_logger().info('QR node ready — scanning active when /person_follow_active is True')

    def active_callback(self, msg):
        self.active = msg.data
        if self.active:
            self.last_result = ''
            self.get_logger().info('QR scanning activated (person follow active)')
        else:
            self.get_logger().info('QR scanning deactivated (person follow inactive)')

    def image_callback(self, msg):
        if not self.active:
            return

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        data, _, _ = self.detector.detectAndDecode(frame)

        now = time.monotonic()
        if data and (data != self.last_result or now - self.last_time > COOLDOWN_SEC):
            self.last_result = data
            self.last_time   = now
            out = String()
            out.data = data
            self.pub.publish(out)
            self.get_logger().info(f'QR detected: {data}')


def main(args=None):
    rclpy.init(args=args)
    node = QRNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
