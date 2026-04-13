import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import Bool, Int32

GESTURE_NONE = 0
GESTURE_FIVE = 5

STATE_QOS = QoSProfile(
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class FollowManager(Node):
    def __init__(self):
        super().__init__('follow_manager')

        self.follow_pub = self.create_publisher(Bool, '/person_follow_active', STATE_QOS)
        self.gesture_mode_pub = self.create_publisher(Bool, '/gesture_mode_enabled', STATE_QOS)

        self.create_subscription(Int32, '/gesture', self.gesture_callback, 10)
        self.create_subscription(Bool, '/person_follow_timeout', self.timeout_callback, 10)

        # Start in YOLO-follow mode. Gesture mode is only enabled after timeout.
        self.following = True
        self.gesture_mode = False

        self._startup_count = 0
        self._startup_timer = self.create_timer(1.0, self._startup_publish)
        self.create_timer(3.0, self._status_log)

        self.get_logger().info(
            'Follow manager ready - FOLLOWING. If no person is seen for 5 seconds, gesture mode will start.'
        )

    def _status_log(self):
        if self.following:
            state = 'FOLLOWING - YOLO active, gesture mode disabled'
        else:
            state = 'GESTURE MODE - show 5 fingers to resume following'
        self.get_logger().info(f'State: {state}')

    def _startup_publish(self):
        self._publish_state()
        self._startup_count += 1
        if self._startup_count >= 10:
            self.destroy_timer(self._startup_timer)
            self.get_logger().info('Startup broadcast done')

    def gesture_callback(self, msg: Int32):
        gesture = msg.data
        if not self.gesture_mode:
            return

        if gesture == GESTURE_FIVE:
            self.following = True
            self.gesture_mode = False
            self._publish_state()
            self.get_logger().info('Gesture 5 -> FOLLOWING resumed')
        elif gesture != GESTURE_NONE:
            self.get_logger().info(f'Gesture {gesture} ignored - show 5 fingers to resume following')

    def timeout_callback(self, msg: Bool):
        if not msg.data or not self.following:
            return

        self.following = False
        self.gesture_mode = True
        self._publish_state()
        self.get_logger().info('No person detected for 5 seconds -> switched to gesture mode')

    def _publish_state(self):
        follow_msg = Bool()
        follow_msg.data = self.following
        self.follow_pub.publish(follow_msg)

        gesture_msg = Bool()
        gesture_msg.data = self.gesture_mode
        self.gesture_mode_pub.publish(gesture_msg)


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
