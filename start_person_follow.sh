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
MAP=/home/louq0001/map.yaml

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

# ── Step 1: Start localization (AMCL + map server) ───────────────────────────
echo "==> Step 1/3 — Starting localization..."
gnome-terminal --title="Localization" -- bash -c "
$ROS_ENV
ros2 launch turtlebot4_navigation localization.launch.py map:=$MAP
exec bash"

echo "    Waiting 15 s for AMCL to start..."
sleep 15

# ── Step 2: Set initial pose — blocks until map TF is confirmed ──────────────
echo "==> Step 2/3 — Setting initial pose (will wait until AMCL confirms)..."
eval "$ROS_ENV"
ros2 run topological_nav set_initial_pose
echo "    Initial pose confirmed. Waiting 3 s before starting nav2..."
sleep 3

# ── Step 3: Start nav2 now that AMCL has the map transform ───────────────────
echo "==> Step 3/3 — Starting nav2..."
gnome-terminal --title="Nav2" -- bash -c "
$ROS_ENV
ros2 launch turtlebot4_navigation nav2.launch.py
exec bash"

sleep 5

# ── Remaining nodes ───────────────────────────────────────────────────────────
gnome-terminal --title="Person Follow" -- bash -c "
$ROS_ENV
ros2 launch topological_nav person_follow.launch.xml robot_name:=$ROBOT_NAME
exec bash"

sleep 2

gnome-terminal --title="Enable Follow" -- bash -c "
$ROS_ENV
echo 'Enabling person following...'
ros2 topic pub /person_follow_active std_msgs/Bool 'data: true'
exec bash"

gnome-terminal --title="QR Display" -- bash -c "
$ROS_ENV
ros2 run topological_nav qr_display_node
exec bash"

gnome-terminal --title="Speak Listener" -- bash -c "
$ROS_ENV
python3 $REPO/ros2_ws/src/topological_nav/topological_nav/speak_listener.py
exec bash"

echo "==> All terminals launched."
echo "==> Robot will follow a person. After stopping 5 s → show 4 fingers for landmark, 5 to go home."
