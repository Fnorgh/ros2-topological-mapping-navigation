#!/usr/bin/env bash
# ─────────────────────────────────────────────
#  CHANGE THESE FOR YOUR ROBOT
# ─────────────────────────────────────────────
ROBOT_NAME="galapagos"
ROS_DOMAIN_ID="4"
ROS_DISCOVERY_SERVER=";;;;10.194.16.39:11811;"
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
cd $WS && colcon build --base-paths src --packages-select topological_nav
source $WS/install/setup.bash

echo "==> Opening terminals..."

# Terminal 1: Person follow + gesture node
gnome-terminal --title="Person Follow" -- bash -c "
$ROS_ENV
ros2 launch topological_nav person_follow.launch.xml robot_name:=$ROBOT_NAME
exec bash"

sleep 3

# Terminal 2: Enable person following
gnome-terminal --title="Enable Follow" -- bash -c "
$ROS_ENV
ros2 daemon stop && ros2 daemon start
echo 'Enabling person following...'
ros2 topic pub /person_follow_active std_msgs/Bool 'data: true'
exec bash"

# Terminal 3: Speak listener (audio plays on this computer)
gnome-terminal --title="Speak Listener" -- bash -c "
$ROS_ENV
python3 $REPO/ros2_ws/src/topological_nav/topological_nav/speak_listener.py
exec bash"

echo "==> Person follow terminals launched."
