#!/usr/bin/env bash
# ─────────────────────────────────────────────
#  Set the robot name — everything else is auto-filled from robot_config.sh
# ─────────────────────────────────────────────
ROBOT="leatherback"
# ─────────────────────────────────────────────

WS=~/robotics/ros2-topological-mapping-navigation/ros2_ws
REPO=~/robotics/ros2-topological-mapping-navigation

ROS_ENV="source /opt/ros/jazzy/setup.bash && source $WS/install/setup.bash"

echo "==> Pulling latest changes..."
cd $REPO && git pull

echo "==> Building package..."
cd $WS && colcon build --packages-select topological_nav
source $WS/install/setup.bash

echo "==> Opening terminals..."

# Terminal 1: All nodes (person follow, gesture, QR, follow manager, TTS)
# Show 5 fingers to start following; show 5 again to stop and return to idle.
gnome-terminal --title="Person Follow" -- bash -c "
$ROS_ENV
ros2 launch topological_nav person_follow.launch.xml
exec bash"

# Terminal 2: Speak listener (audio plays on this computer)
gnome-terminal --title="Speak Listener" -- bash -c "
$ROS_ENV
python3 $REPO/ros2_ws/src/topological_nav/topological_nav/speak_listener.py
exec bash"


echo "==> Person follow launched — show 5 fingers to start/stop following."
