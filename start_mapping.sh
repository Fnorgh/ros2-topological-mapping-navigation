#!/usr/bin/env bash
# ─────────────────────────────────────────────
#  CHANGE THESE FOR YOUR ROBOT
# ─────────────────────────────────────────────
ROBOT_NAME="softshell"
ROS_DOMAIN_ID="9"
ROS_DISCOVERY_SERVER=";;;;;;;;;10.194.16.59:11811;"
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

echo "==> Opening mapping terminals..."

# Terminal 1: SLAM — builds the occupancy grid as you drive
gnome-terminal --title="SLAM" -- bash -c "
$ROS_ENV
ros2 launch turtlebot4_navigation slam.launch.py
exec bash"

sleep 3

# Terminal 2: RViz — watch the map being built
gnome-terminal --title="RViz" -- bash -c "
$ROS_ENV
ros2 launch turtlebot4_viz view_robot.launch.py
exec bash"

sleep 2

# Terminal 3: Teleop — drive the robot
gnome-terminal --title="Teleop" -- bash -c "
$ROS_ENV
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -p stamped:=true
exec bash"

sleep 2

# Terminal 4: Mark home position and save map
gnome-terminal --title="Mark Home + Save" -- bash -c "
$ROS_ENV
ros2 run topological_nav landmark_saver_node
exec bash"

echo ""
echo "══════════════════════════════════════════════════"
echo "  MAPPING PHASE"
echo "  1. Drive around the entire area to build the map"
echo "  2. Return to your START position"
echo "  3. In the 'Mark Home + Save' terminal:"
echo "       h  → mark current spot as Home"
echo "       s  → save ~/map.yaml + landmarks.yaml"
echo ""
echo "  When done, run:  ./start_landmarks.sh"
echo "══════════════════════════════════════════════════"
