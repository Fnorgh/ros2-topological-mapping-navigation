"""
Publishes the home position from landmarks.yaml as the AMCL initial pose.
Keeps publishing until AMCL confirms it has a valid pose (map TF appears).
"""
import math
import os
import time
import yaml

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
import tf2_ros

LANDMARKS_FILE = os.path.expanduser(
    '~/robotics/ros2-topological-mapping-navigation/landmarks.yaml'
)


class InitialPoseNode(Node):

    def __init__(self):
        super().__init__('set_initial_pose')
        self.pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 10)
        self.tf_buffer   = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

    def map_tf_ready(self):
        try:
            self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
            return True
        except Exception:
            return False

    def publish_pose(self, x, y, yaw):
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id    = 'map'
        msg.header.stamp       = rclpy.time.Time().to_msg()  # zero → AMCL uses latest TF
        msg.pose.pose.position.x    = float(x)
        msg.pose.pose.position.y    = float(y)
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        msg.pose.covariance[0]  = 0.25
        msg.pose.covariance[7]  = 0.25
        msg.pose.covariance[35] = 0.07
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)

    if not os.path.exists(LANDMARKS_FILE):
        print('No landmarks.yaml found — skipping initial pose')
        return

    with open(LANDMARKS_FILE) as f:
        data = yaml.safe_load(f) or {}
    home = data.get('home')
    if not home:
        print('No home position in landmarks.yaml — skipping initial pose')
        return

    x, y, yaw = home
    node = InitialPoseNode()

    print(f'Setting initial pose: x={x:.3f} y={y:.3f} yaw={math.degrees(yaw):.1f}°')
    print('Publishing to /initialpose until map→base_link TF appears...')

    deadline = time.time() + 30.0   # give up after 30 s
    published = 0

    while time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)
        node.publish_pose(x, y, yaw)
        published += 1

        if node.map_tf_ready():
            print(f'map→base_link TF confirmed after {published} publishes. AMCL ready.')
            break

        if published % 5 == 0:
            print(f'  still waiting... ({published} publishes sent)')
        time.sleep(0.5)
    else:
        print('Warning: map TF did not appear within 30 s — nav2 may not navigate correctly')

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
