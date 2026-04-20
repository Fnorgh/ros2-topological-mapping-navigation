import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


class QRNode(Node):

    def __init__(self):
        super().__init__('qr_node')

        self.pub = self.create_publisher(String, '/qr_detected', 10)

        self.create_subscription(
            Image, '/oakd/rgb/preview/image_raw', self.image_callback, 10)

        self.bridge      = CvBridge()
        self.detector    = cv2.QRCodeDetector()
        self.active      = True   # active immediately — parent kills this process when done
        self.last_result = ''

        self.get_logger().info('QR node ready — scanning')

    def image_callback(self, msg):
        if not self.active:
            return

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        data, _, _ = self.detector.detectAndDecode(frame)

        if data and data != self.last_result:
            self.last_result = data
            self.active = False
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
