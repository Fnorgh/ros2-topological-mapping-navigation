#!/usr/bin/env bash
# Usage: ros_launch_node.sh <robot_name> <command...>
#
# Calls robot-setup.sh for the given robot name, evals the export lines
# to set ROS_DOMAIN_ID and ROS_DISCOVERY_SERVER, then runs the command.
#
ROBOT_NAME="$1"; shift
WS=~/robotics/ros2-topological-mapping-navigation/ros2_ws

# Eval the export lines from robot-setup.sh so env vars are actually set
eval "$(printf '%s' "$ROBOT_NAME" | robot-setup.sh 2>/dev/null | grep '^export')"

unset ROS_LOCALHOST_ONLY
export ROS_SUPER_CLIENT=True

source "$WS/install/setup.bash"

exec "$@"
