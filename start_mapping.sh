#!/usr/bin/env bash
# ─────────────────────────────────────────────
#  Set the robot name — everything else is auto-filled from robot_config.sh
# ─────────────────────────────────────────────
ROBOT="snapper"
source "$(dirname "$0")/robot_config.sh" || exit 1
# ─────────────────────────────────────────────

WS=~/robotics/ros2-topological-mapping-navigation/ros2_ws
REPO=~/robotics/ros2-topological-mapping-navigation

ROS_ENV="unset ROS_LOCALHOST_ONLY && \
export ROS_DOMAIN_ID=$ROS_DOMAIN_ID && \
export ROS_DISCOVERY_SERVER=\"$ROS_DISCOVERY_SERVER\" && \
export ROS_SUPER_CLIENT=True && \
source $WS/install/setup.bash"

echo "==> Pulling latest changes..."
cd $REPO && git pull

echo "==> Building package..."
cd $WS && colcon build --packages-select topological_nav
source $WS/install/setup.bash

echo "==> Opening terminals..."

# Terminal 1: SLAM + RViz + gesture + QR + tour manager
gnome-terminal --title="Mapping" -- bash -c "
$ROS_ENV
ros2 launch topological_nav mapping.launch.xml robot_name:=$ROBOT_NAME
exec bash"

sleep 3

# Terminal 2: Keyboard teleop
gnome-terminal --title="Teleop" -- bash -c "
$ROS_ENV
ros2 daemon stop && ros2 daemon start
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -p stamped:=true
exec bash"

echo "==> Mapping terminals launched."
echo "    Drive the robot around to build the map."
echo "    When done, save the map with:"
echo "    ros2 run nav2_map_server map_saver_cli -f ~/map"
