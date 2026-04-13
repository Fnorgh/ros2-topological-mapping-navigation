import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from std_msgs.msg import Bool, Int32

# State machine controlled by gesture 5 (open hand).
#
# IDLE      → robot stopped, gesture scanning OFF, QR scanning OFF
# FOLLOWING → person_follow active, QR scanning ON, gesture 5 stops it
#
# /gesture (Int32)             → consumed here
# /person_follow_active (Bool) → published here with transient_local (latched)
#                                so late-starting nodes always get current state

GESTURE_FIVE = 5

# Transient-local = ROS2 equivalent of a latched topic.
# Any node that subscribes after the last publish still receives the current value.
_LATCHED_QOS = QoSProfile(
    depth=1,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
)


class FollowManager(Node):

    def __init__(self):
        super().__init__('follow_manager')

        self.follow_pub = self.create_publisher(Bool, '/person_follow_active', _LATCHED_QOS)
        self.create_subscription(Int32, '/gesture', self.gesture_callback, 10)

        self.following = False

        # Publish IDLE immediately — transient_local ensures any node that
        # starts later (e.g. person_follow_node) still receives this value.
        self._publish(False)
        self.get_logger().info(
            'Follow manager ready — IDLE. Show 5 fingers to start/stop following.')

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
