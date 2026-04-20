"""
Single-launch navigation stack:
  t=0s   robot_description  (robot_state_publisher → /tf_static for AMCL)
  t=0s   localization        (map_server + AMCL)
  t=20s  set_initial_pose    (publishes home pose; waits up to 30s for map TF)
  t=60s  nav2                (starts after set_initial_pose has had time to confirm)

The robot's /tf_static (rplidar_link→base_link etc.) uses TRANSIENT_LOCAL QoS
and does not reliably reach the laptop over a remote discovery server.
robot_state_publisher re-publishes those same static TFs locally so AMCL
can transform laser scans and update the particle filter.
"""
import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, IncludeLaunchDescription, TimerAction, LogInfo
)
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    map_arg = DeclareLaunchArgument(
        'map',
        default_value='/home/louq0001/map.yaml',
        description='Full path to map yaml',
    )
    model_arg = DeclareLaunchArgument(
        'model',
        default_value='standard',
        description='TurtleBot4 model (standard or lite)',
    )

    nav_dir   = get_package_share_directory('turtlebot4_navigation')
    this_dir  = get_package_share_directory('topological_nav')
    desc_dir  = get_package_share_directory('turtlebot4_description')

    # ── Robot description — publishes /tf_static locally so AMCL can use scans
    robot_description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(desc_dir, 'launch', 'robot_description.launch.py')
        ),
        launch_arguments={
            'model':      LaunchConfiguration('model'),
            'namespace':  '',
            'robot_name': '',
        }.items(),
    )

    # ── Localization (map_server + AMCL) ──────────────────────────────────────
    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav_dir, 'launch', 'localization.launch.py')
        ),
        launch_arguments={'map': LaunchConfiguration('map')}.items(),
    )

    # ── Initial pose — fires after AMCL lifecycle activation (~15-20 s) ───────
    set_initial_pose = TimerAction(
        period=20.0,
        actions=[
            LogInfo(msg='[nav_stack] Setting initial pose...'),
            Node(
                package='topological_nav',
                executable='set_initial_pose',
                output='screen',
            ),
        ],
    )

    # ── Nav2 — fires after set_initial_pose has had time to confirm (30 s max) -
    nav2 = TimerAction(
        period=60.0,
        actions=[
            LogInfo(msg='[nav_stack] Starting nav2...'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(nav_dir, 'launch', 'nav2.launch.py')
                ),
                launch_arguments={
                    'params_file': os.path.join(this_dir, 'config', 'nav2.yaml'),
                }.items(),
            ),
        ],
    )

    return LaunchDescription([
        map_arg,
        model_arg,
        robot_description,
        localization,
        set_initial_pose,
        nav2,
    ])
