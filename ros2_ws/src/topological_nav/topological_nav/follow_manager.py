import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Int32

# State machine controlled by gesture 5 (open hand).
#
# IDLE      → robot stopped, gesture scanning active, QR scanning OFF
# FOLLOWING → person_follow active, QR scanning ON, gesture 5 stops it
#
# /gesture (Int32)          → consumed here
# /person_follow_active (Bool) → published here, gates person_follow_node and qr_node

GESTURE_FIVE = 5


class FollowManager(Node):

    def __init__(self):
        super().__init__('follow_manager')

        self.follow_pub = self.create_publisher(Bool, '/person_follow_active', 10)
        self.create_subscription(Int32, '/gesture', self.gesture_callback, 10)

        self.following = False

        # Publish initial IDLE state after 1 s so other nodes have time to start
        self._init_timer = self.create_timer(1.0, self._send_initial_state)

        self.get_logger().info(
            'Follow manager ready — show 5 fingers to start/stop following')

    def _send_initial_state(self):
        self._publish(False)
        self.destroy_timer(self._init_timer)
        self.get_logger().info('Initial state: IDLE (following OFF)')

    def gesture_callback(self, msg: Int32):
        if msg.data != GESTURE_FIVE:
            return

        self.following = not self.following
        self._publish(self.following)

        if self.following:
            self.get_logger().info('Gesture 5 → FOLLOWING started (QR scanning ON)')
        else:
            self.get_logger().info('Gesture 5 → IDLE (following stopped, QR scanning OFF)')

    def _publish(self, state: bool):
        out = Bool()
        out.data = state
        self.follow_pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = FollowManager()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
