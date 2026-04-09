import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import subprocess
import threading

# Subscribes to /speak (String) and speaks the text using espeak.
# Falls back to festival if espeak is not installed.


class TTSNode(Node):

    def __init__(self):
        super().__init__('tts_node')
        self.create_subscription(String, '/speak', self.speak_callback, 10)
        self.get_logger().info('TTS node ready — listening on /speak')

    def speak_callback(self, msg):
        text = msg.data
        self.get_logger().info(f'Speaking: "{text}"')
        threading.Thread(target=self._speak, args=(text,), daemon=True).start()

    def _speak(self, text):
        try:
            subprocess.run(['espeak', '-s', '140', '-p', '50', text], check=True)
        except FileNotFoundError:
            try:
                subprocess.run(
                    ['festival', '--tts'],
                    input=text.encode(),
                    check=True,
                )
            except FileNotFoundError:
                self.get_logger().error(
                    'No TTS engine found. Install espeak: sudo apt install espeak'
                )


def main(args=None):
    rclpy.init(args=args)
    node = TTSNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
