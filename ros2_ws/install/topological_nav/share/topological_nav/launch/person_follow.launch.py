import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess

WS     = os.path.expanduser('~/robotics/ros2-topological-mapping-navigation/ros2_ws')
SCRIPT = os.path.join(WS, 'src/topological_nav/scripts/ros_launch_node.sh')
VENV   = os.path.join(WS, 'venv/bin/python')
ROBOT  = os.environ.get('ROBOT', 'leatherback')


def node_cmd(module):
    return ExecuteProcess(
        cmd=['bash', '-lc', f'{SCRIPT} {ROBOT} {VENV} -m {module}'],
        output='screen',
    )


def generate_launch_description():
    return LaunchDescription([
        node_cmd('topological_nav.person_follow_node'),
        node_cmd('topological_nav.gesture_node'),
        node_cmd('topological_nav.qr_node'),
        node_cmd('topological_nav.follow_manager'),
        ExecuteProcess(
            cmd=['bash', '-lc', f'{SCRIPT} {ROBOT} ros2 run topological_nav tts_node'],
            output='screen',
        ),
    ])
