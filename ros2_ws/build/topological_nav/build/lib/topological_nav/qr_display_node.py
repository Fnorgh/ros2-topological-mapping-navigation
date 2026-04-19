"""
Laptop-side QR display node.
Subscribes to /qr_detected, maps task1/task2/task3 to landmark scripts,
prints the text and speaks it aloud using the laptop speakers.
"""
import subprocess
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

LANDMARK_SCRIPTS = {
    'task1': (
        "Bizzell Memorial Library. "
        "Bizzell Memorial Library is one of the most recognizable and historically significant "
        "buildings on campus. Built in 1929, it stands as a symbol of academic life at OU, "
        "with its red brick exterior and Collegiate Gothic architecture reflecting the "
        "university's long-standing traditions. The library was named in honor of William "
        "Bennett Bizzell, a former university president who played a major role in shaping "
        "OU's academic identity. "
        "Inside, the Great Reading Room is often considered the heart of the building. "
        "With its high vaulted ceilings, large windows, and rows of wooden desks, it creates "
        "a quiet and inspiring atmosphere for studying. The space feels almost cathedral-like, "
        "emphasizing the importance of knowledge and scholarship. Over the years, Bizzell "
        "Library has expanded to include modern research facilities while still preserving "
        "its historic character, making it a blend of past and present."
    ),
    'task2': (
        "Evans Hall, The Clock Tower. "
        "Evans Hall is best known for its tall clock tower, which has become a defining "
        "feature of the OU skyline. Completed in 1954, Evans Hall primarily houses classrooms "
        "and faculty offices, especially for math and science departments. Its height and "
        "central location make it easy to spot from almost anywhere on campus. "
        "The clock tower itself serves as both a practical and symbolic landmark. Students "
        "often use it as a meeting point, and it helps orient visitors navigating the "
        "university grounds. At different times of day, especially during sunrise or sunset, "
        "the tower stands out dramatically against the Oklahoma sky, making it a favorite "
        "subject for photos. For many students, Evans Hall becomes associated with challenging "
        "courses and long study sessions, making it an unforgettable part of their academic journey."
    ),
    'task3': (
        "The South Oval. "
        "South Oval is the scenic and social heart of the OU campus. Lined with trees and "
        "wide walkways, it connects many of the university's most important buildings and "
        "serves as a central gathering place for students, faculty, and visitors. Throughout "
        "the year, the South Oval transforms with the seasons, from vibrant green in the "
        "summer to colorful leaves in the fall. "
        "Beyond its beauty, the South Oval plays a major role in campus life. It's where "
        "students relax between classes, campus organizations set up events, and traditions "
        "unfold. The space encourages a sense of community, making it more than just a "
        "walkway. It's a place where everyday college experiences happen. Whether it's a "
        "quiet walk to class or a busy afternoon filled with activity, the South Oval "
        "captures the energy and spirit of OU."
    ),
}


def _speak(text: str):
    """Speak text aloud using the best available TTS engine."""
    for cmd in (
        ['spd-say', text],
        ['espeak', '-s', '150', text],
        ['festival', '--tts'],
    ):
        try:
            if cmd[0] == 'festival':
                subprocess.run(cmd, input=text.encode(), timeout=120)
            else:
                subprocess.run(cmd, timeout=120)
            return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    print(f'\a[NO TTS] {text}', flush=True)


class QRDisplayNode(Node):

    def __init__(self):
        super().__init__('qr_display_node')
        self.create_subscription(String, '/qr_detected', self._cb, 10)
        self.get_logger().info('QR display node ready — listening on /qr_detected')

    def _cb(self, msg: String):
        script = LANDMARK_SCRIPTS.get(msg.data)
        if script is None:
            self.get_logger().warn(f'Unknown QR code: "{msg.data}"')
            return

        self.get_logger().info(f'QR detected: "{msg.data}" — speaking landmark script')
        print(f'\n{"="*60}\n{script}\n{"="*60}\n', flush=True)
        _speak(script)


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
