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

# Sanity check — map must exist before we can localize
if [ ! -f "$MAP" ]; then
    echo "ERROR: $MAP not found."
    echo "       Run ./start_mapping.sh first, press h then s to save the map."
    exit 1
fi

echo "==> Building package..."
cd $WS && colcon build --base-paths src --packages-select topological_nav
source $WS/install/setup.bash

# ── Step 1: Start localization (AMCL + map server) ───────────────────────────
echo "==> Step 1/3 — Starting localization with saved map..."
gnome-terminal --title="Localization" -- bash -c "
$ROS_ENV
ros2 launch turtlebot4_navigation localization.launch.py map:=$MAP
exec bash"

echo "    Waiting 15 s for AMCL to start..."
sleep 15

# ── Step 2: Set initial pose from saved home position ────────────────────────
echo "==> Step 2/3 — Setting initial pose at Home (will wait for AMCL)..."
eval "$ROS_ENV"
ros2 run topological_nav set_initial_pose
echo "    Initial pose confirmed. Waiting 3 s..."
sleep 3

# ── Step 3: RViz + Teleop + Landmark saver ───────────────────────────────────
echo "==> Step 3/3 — Opening landmark marking terminals..."

gnome-terminal --title="RViz" -- bash -c "
$ROS_ENV
ros2 launch turtlebot4_viz view_robot.launch.py
exec bash"

sleep 2

gnome-terminal --title="Teleop" -- bash -c "
$ROS_ENV
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -p stamped:=true
exec bash"

sleep 2

gnome-terminal --title="Landmark Saver" -- bash -c "
$ROS_ENV
ros2 run topological_nav landmark_saver_node
exec bash"

echo ""
echo "══════════════════════════════════════════════════"
echo "  LANDMARK MARKING PHASE"
echo "  Robot is localized at Home on the saved map."
echo "  1. Drive to each landmark location"
echo "  2. In the 'Landmark Saver' terminal:"
echo "       1 / 2 / 3  → mark current spot as that landmark"
echo "       s          → save landmarks.yaml"
echo ""
echo "  When done, run:  ./start_person_follow.sh"
echo "══════════════════════════════════════════════════"
