#!/usr/bin/env bash
# ─────────────────────────────────────────────
#  Set the robot name — everything else is auto-filled from robot_config.sh
# ─────────────────────────────────────────────
ROBOT="${1:-leatherback}"
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

echo "==> Using robot: $ROBOT"
echo "==> ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
echo "==> ROS_DISCOVERY_SERVER=$ROS_DISCOVERY_SERVER"
echo "==> Restarting ROS daemon with this environment..."
unset ROS_LOCALHOST_ONLY
export ROS_DOMAIN_ID=$ROS_DOMAIN_ID
export ROS_DISCOVERY_SERVER="$ROS_DISCOVERY_SERVER"
export ROS_SUPER_CLIENT=True
ros2 daemon stop || true
ros2 daemon start

echo "==> Checking remote camera topic on this computer..."
if ! timeout 8s ros2 topic echo --once /oakd/rgb/preview/image_raw > /dev/null 2>&1; then
  echo "ERROR: This computer cannot see /oakd/rgb/preview/image_raw for robot '$ROBOT'."
  echo "       The robot may be on a different domain/discovery server, or the camera topic is not reaching this machine."
  echo "       Verify the robot name and network first, then try:"
  echo "       unset ROS_LOCALHOST_ONLY"
  echo "       export ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
  echo "       export ROS_DISCOVERY_SERVER=\"$ROS_DISCOVERY_SERVER\""
  echo "       export ROS_SUPER_CLIENT=True"
  echo "       ros2 daemon stop && ros2 daemon start"
  echo "       ros2 topic list | grep oakd"
  exit 1
fi
echo "==> Camera stream is visible from this computer."

echo "==> Opening terminals..."

# Terminal 1: All nodes (person follow, gesture, QR, follow manager, TTS)
# Show 5 fingers to start following; show 5 again to stop and return to idle.
gnome-terminal --title="Person Follow" -- bash -c "
$ROS_ENV
ros2 launch topological_nav person_follow.launch.xml robot_name:=$ROBOT
exec bash"

# Terminal 2: Speak listener (audio plays on this computer)
gnome-terminal --title="Speak Listener" -- bash -c "
$ROS_ENV
python3 $REPO/ros2_ws/src/topological_nav/topological_nav/speak_listener.py
exec bash"


echo "==> Person follow launched — show 5 fingers to start/stop following."
