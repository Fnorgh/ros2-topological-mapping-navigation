import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Int32

# State machine controlled by gesture 5 (open hand).
#
# IDLE      → robot stopped, gesture scanning OFF, QR scanning OFF
# FOLLOWING → person_follow active, QR scanning ON, gesture 5 stops it
#
# /gesture (Int32)             → consumed here
# /person_follow_active (Bool) → published here (default QoS)

GESTURE_FIVE = 5


class FollowManager(Node):

    def __init__(self):
        super().__init__('follow_manager')

        self.follow_pub = self.create_publisher(Bool, '/person_follow_active', 10)
        self.create_subscription(Int32, '/gesture', self.gesture_callback, 10)

        self.following = False

        # Re-publish the current state every second for the first 10 s so any
        # node that starts late still receives the initial IDLE (False) value.
        self._startup_count = 0
        self._startup_timer = self.create_timer(1.0, self._startup_publish)

        # Print current state every 3 s so it's always visible in the terminal
        self.create_timer(3.0, self._status_log)

        self.get_logger().info(
            'Follow manager ready — IDLE. Show 5 fingers to start/stop following.')

    def _status_log(self):
        state = 'FOLLOWING (gesture 5 to stop)' if self.following else 'IDLE — show 5 fingers to start'
        self.get_logger().info(f'State: {state}')

    def _startup_publish(self):
        self._publish(self.following)
        self._startup_count += 1
        if self._startup_count >= 10:
            self.destroy_timer(self._startup_timer)
            self.get_logger().info('Startup broadcast done — waiting for gesture 5')

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
