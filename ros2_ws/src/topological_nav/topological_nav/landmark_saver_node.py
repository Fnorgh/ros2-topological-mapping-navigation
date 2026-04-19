"""
Landmark saver — run this during the mapping phase.
Drive the robot to each landmark with teleop, then press:
  1 / 2 / 3  →  save current map-frame pose as that landmark
  h          →  save current pose as HOME
  s          →  write landmarks.yaml and print summary
  q          →  save and quit

Reads position from the map→base_link TF (requires SLAM to be running).
"""
import sys
import math
import os
import subprocess
import threading
import tty
import termios
import yaml

import rclpy
from rclpy.node import Node
import tf2_ros

MAP_FILE = os.path.expanduser('~/map')

LANDMARKS_FILE = os.path.expanduser(
    '~/robotics/ros2-topological-mapping-navigation/landmarks.yaml'
)


class LandmarkSaverNode(Node):

    def __init__(self):
        super().__init__('landmark_saver_node')

        self.tf_buffer   = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        self.landmarks: dict[int, list] = {}
        self.home: list | None = None

        # Load any previously saved landmarks
        if os.path.exists(LANDMARKS_FILE):
            with open(LANDMARKS_FILE) as f:
                data = yaml.safe_load(f) or {}
            for k, v in data.get('landmarks', {}).items():
                self.landmarks[int(k)] = list(v)
            if data.get('home'):
                self.home = list(data['home'])

        self._print_instructions()

        kbd = threading.Thread(target=self._keyboard_loop, daemon=True)
        kbd.start()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _print_instructions(self):
        print('\n' + '=' * 52)
        print('  LANDMARK SAVER — drive to each spot, then:')
        print('    1 / 2 / 3  →  mark as Landmark 1 / 2 / 3')
        print('    h          →  mark as Home position')
        print('    s          →  save to landmarks.yaml')
        print('    q          →  save and quit')
        print('=' * 52)
        self._print_status()

    def _print_status(self):
        print('\nSaved so far:')
        for i in (1, 2, 3):
            pos = self.landmarks.get(i)
            if pos:
                print(f'  Landmark {i}: x={pos[0]:.3f}  y={pos[1]:.3f}  yaw={math.degrees(pos[2]):.1f}°')
            else:
                print(f'  Landmark {i}: (not saved)')
        if self.home:
            print(f'  Home:       x={self.home[0]:.3f}  y={self.home[1]:.3f}  yaw={math.degrees(self.home[2]):.1f}°')
        else:
            print('  Home:       (not saved)')
        print()

    # ── TF lookup ─────────────────────────────────────────────────────────────

    def _get_pose(self):
        """Return (x, y, yaw) in the map frame, or None if TF unavailable."""
        try:
            t = self.tf_buffer.lookup_transform(
                'map', 'base_link', rclpy.time.Time())
            x   = t.transform.translation.x
            y   = t.transform.translation.y
            qz  = t.transform.rotation.z
            qw  = t.transform.rotation.w
            yaw = 2.0 * math.atan2(qz, qw)
            return (x, y, yaw)
        except Exception as e:
            self.get_logger().warn(f'TF lookup failed: {e}')
            return None

    # ── File I/O ──────────────────────────────────────────────────────────────

    def _save(self):
        # Save landmark coordinates
        data = {
            'landmarks': {k: v for k, v in self.landmarks.items()},
            'home': self.home,
        }
        with open(LANDMARKS_FILE, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
        print(f'\nSaved → {LANDMARKS_FILE}')

        # Save the SLAM map image (map.yaml + map.pgm)
        print(f'Saving map → {MAP_FILE}.yaml / {MAP_FILE}.pgm ...')
        result = subprocess.run(
            ['ros2', 'run', 'nav2_map_server', 'map_saver_cli', '-f', MAP_FILE],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            print(f'Map saved → {MAP_FILE}.yaml')
        else:
            print(f'Map save failed: {result.stderr.strip()}')

        self._print_status()

    # ── Keyboard loop (runs in its own thread) ────────────────────────────────

    def _keyboard_loop(self):
        fd  = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while rclpy.ok():
                ch = sys.stdin.read(1)

                if ch in ('1', '2', '3'):
                    pose = self._get_pose()
                    if pose:
                        self.landmarks[int(ch)] = list(pose)
                        print(f'\r→ Landmark {ch} saved: '
                              f'x={pose[0]:.3f}  y={pose[1]:.3f}  '
                              f'yaw={math.degrees(pose[2]):.1f}°\n')
                    else:
                        print('\r→ Cannot read position — is SLAM running?\n')

                elif ch == 'h':
                    pose = self._get_pose()
                    if pose:
                        self.home = list(pose)
                        print(f'\r→ Home saved: '
                              f'x={pose[0]:.3f}  y={pose[1]:.3f}  '
                              f'yaw={math.degrees(pose[2]):.1f}°\n')
                    else:
                        print('\r→ Cannot read position — is SLAM running?\n')

                elif ch == 's':
                    self._save()

                elif ch == 'q':
                    self._save()
                    rclpy.shutdown()
                    break

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main(args=None):
    rclpy.init(args=args)
    node = LandmarkSaverNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
