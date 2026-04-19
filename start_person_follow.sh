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

# Terminal 1: Person follow node + TTS node
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

# Terminal 3: QR node — scans camera, activates when /qr_scan_active is True
# (triggered automatically after robot stops moving for 5 seconds)
gnome-terminal --title="QR Node" -- bash -c "
$ROS_ENV
ros2 run topological_nav qr_node
exec bash"

# Terminal 4: QR display node — prints task1/task2/task3 on this laptop
gnome-terminal --title="QR Display" -- bash -c "
$ROS_ENV
ros2 run topological_nav qr_display_node
exec bash"

# Terminal 5: Speak listener — audio output on this laptop
gnome-terminal --title="Speak Listener" -- bash -c "
$ROS_ENV
python3 $REPO/ros2_ws/src/topological_nav/topological_nav/speak_listener.py
exec bash"

echo "==> All terminals launched."
echo "==> Robot will follow a person. After stopping for 5 s, QR scanner activates automatically."
