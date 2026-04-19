"""
Laptop-side QR display node.
Subscribes to /qr_detected and prints the corresponding output.
QR codes should contain 'test1', 'test2', or 'test3'.
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class QRDisplayNode(Node):

    def __init__(self):
        super().__init__('qr_display_node')
        self.create_subscription(String, '/qr_detected', self._cb, 10)
        self.get_logger().info('QR display node ready — listening on /qr_detected')

    def _cb(self, msg: String):
        print(f'\n*** QR OUTPUT: {msg.data} ***\n', flush=True)
        self.get_logger().info(f'QR detected: "{msg.data}"')


def main(args=None):
    rclpy.init(args=args)
    node = QRDisplayNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
