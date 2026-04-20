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

if [ ! -f "$MAP" ]; then
    echo "ERROR: $MAP not found. Run ./start_mapping.sh first."
    exit 1
fi

echo "==> Pulling latest changes..."
cd $REPO && git pull

echo "==> Building package..."
cd $WS && colcon build --base-paths src --packages-select topological_nav
source $WS/install/setup.bash

# ── Navigation stack (all-in-one) ─────────────────────────────────────────────
# localization_nav2.launch.py handles:
#   t=0s   → localization (map_server + AMCL)
#   t=20s  → set_initial_pose (same ROS domain as AMCL, waits for map TF)
#   t=60s  → nav2
echo "==> Starting navigation stack (one terminal)..."
gnome-terminal --title="Nav Stack" -- bash -c "
$ROS_ENV
ros2 launch topological_nav localization_nav2.launch.py map:=$MAP
exec bash"

# Wait for full nav2 activation:
#   60s (nav2 launch delay) + ~25s (route_server + lifecycle activation) = ~85s
echo "    Waiting 90 s for the full nav stack to activate..."
echo "    (localization t=0s, initial pose t=20s, nav2 t=60s)"
for i in $(seq 90 -10 10); do
    echo "    ... $i s remaining"
    sleep 10
done

# ── Person follow (state machine + YOLO + TTS) ────────────────────────────────
echo "==> Starting person follow launch..."
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

echo ""
echo "==> All terminals launched."
echo "    Robot will follow a person."
echo "    Stop 5 s → show fingers: 1/2/3 = landmark, 4 = nearest, 5 = home."
