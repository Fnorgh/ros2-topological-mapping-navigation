"""
Local speak listener — run this on your connecting computer (no sudo needed).
Subscribes to /speak and announces using spd-say, festival, or terminal bell.
"""
import subprocess
import sys
import os
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def _tts(text: str):
    """Try available TTS engines in order, fall back to terminal output."""
    for cmd in (
        ['spd-say', text],
        ['festival', '--tts'],           # reads from stdin
        ['espeak', '-s', '140', text],
    ):
        try:
            if cmd[0] == 'festival':
                subprocess.run(cmd, input=text.encode(), timeout=10)
            else:
                subprocess.run(cmd, timeout=10)
            return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # No TTS engine — print with terminal bell
    print(f'\a\n*** {text.upper()} ***\n', flush=True)


class SpeakListener(Node):

    def __init__(self):
        super().__init__('speak_listener')
        self.create_subscription(String, '/speak', self._cb, 10)
        self.get_logger().info('speak_listener ready — listening on /speak')

    def _cb(self, msg: String):
        self.get_logger().info(f'Speaking: "{msg.data}"')
        _tts(msg.data)


def main():
    rclpy.init()
    node = SpeakListener()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
