#!/usr/bin/env bash
# ─────────────────────────────────────────────
#  CHANGE THESE TWO VALUES FOR YOUR ROBOT
# ─────────────────────────────────────────────
ROBOT_NAME="snapper"
ROS_DOMAIN_ID="4"
ROS_DISCOVERY_SERVER=";;;;10.194.16.39:11811;"
# ─────────────────────────────────────────────

WS=~/robotics/ros2-topological-mapping-navigation/ros2_ws
REPO=~/robotics/ros2-topological-mapping-navigation
VENV=$WS/venv/bin/python

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

# Terminal 1: SLAM + all nodes via launch file
gnome-terminal --title="Launch" -- bash -c "
$ROS_ENV
ros2 launch topological_nav topological_nav.launch.xml robot_name:=$ROBOT_NAME
exec bash"

sleep 3

# Terminal 2: Person follow node (uses venv for ultralytics)
gnome-terminal --title="Person Follow" -- bash -c "
$ROS_ENV
$VENV -m topological_nav.person_follow_node
exec bash"

sleep 2

# Terminal 3: Enable person following
gnome-terminal --title="Enable Follow" -- bash -c "
$ROS_ENV
echo 'Publishing person_follow_active...'
ros2 topic pub /person_follow_active std_msgs/Bool 'data: true'
exec bash"

# Terminal 4: Speak listener (plays audio on this computer)
gnome-terminal --title="Speak Listener" -- bash -c "
$ROS_ENV
python3 $REPO/ros2_ws/src/topological_nav/topological_nav/speak_listener.py
exec bash"

echo "==> All terminals launched."
