#!/usr/bin/env bash

ROBOT="leatherback"
AUTO_FOLLOW=false
ENABLE_GESTURE=true
ENABLE_QR=true
ENABLE_FOLLOW_MANAGER=true
LAUNCH_FILE="person_follow.launch.xml"
DIRECT_CMD=""

for arg in "$@"; do
  case "$arg" in
    leatherback|galapagos|snapper|loggerhead|testudo|terrapin|hawksbill|matamata|softshell)
      ROBOT="$arg"
      ;;
    --auto-follow)
      AUTO_FOLLOW=true
      ;;
    --no-gesture)
      ENABLE_GESTURE=false
      ENABLE_FOLLOW_MANAGER=false
      ;;
    --no-qr)
      ENABLE_QR=false
      ;;
    --yolo-only)
      AUTO_FOLLOW=true
      ENABLE_GESTURE=false
      ENABLE_QR=false
      ENABLE_FOLLOW_MANAGER=false
      DIRECT_CMD="~/robotics/ros2-topological-mapping-navigation/ros2_ws/venv/bin/python -m topological_nav.person_follow_node --ros-args -p start_active:=true"
      ;;
  esac
done

source "$(dirname "$0")/robot_config.sh" || exit 1

WS=~/robotics/ros2-topological-mapping-navigation/ros2_ws
REPO=~/robotics/ros2-topological-mapping-navigation

ROS_ENV="unset ROS_LOCALHOST_ONLY && \
export ROS_DOMAIN_ID=$ROS_DOMAIN_ID && \
export ROS_DISCOVERY_SERVER=\"$ROS_DISCOVERY_SERVER\" && \
export ROS_SUPER_CLIENT=True && \
source $WS/install/setup.bash"

echo "==> Pulling latest changes..."
cd "$REPO" && git pull

echo "==> Building package..."
cd "$WS" && colcon build --packages-select topological_nav
source "$WS/install/setup.bash"

echo "==> Using robot: $ROBOT"
echo "==> ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
echo "==> ROS_DISCOVERY_SERVER=$ROS_DISCOVERY_SERVER"
echo "==> LAUNCH_FILE=$LAUNCH_FILE  AUTO_FOLLOW=$AUTO_FOLLOW  ENABLE_GESTURE=$ENABLE_GESTURE  ENABLE_QR=$ENABLE_QR"
echo "==> Restarting ROS daemon with this environment..."
unset ROS_LOCALHOST_ONLY
export ROS_DOMAIN_ID="$ROS_DOMAIN_ID"
export ROS_DISCOVERY_SERVER="$ROS_DISCOVERY_SERVER"
export ROS_SUPER_CLIENT=True
ros2 daemon stop || true
ros2 daemon start

echo "==> Opening terminals..."

# Terminal 1: All nodes for offboard person-follow compute, without audio.
if [ -n "$DIRECT_CMD" ]; then
  gnome-terminal --title="Person Follow" -- bash -c "
$ROS_ENV
$DIRECT_CMD
exec bash"
else
  gnome-terminal --title="Person Follow" -- bash -c "
$ROS_ENV
ros2 launch topological_nav $LAUNCH_FILE robot_name:=$ROBOT auto_follow:=$AUTO_FOLLOW
exec bash"
fi

echo "==> Person follow launched silently - show 5 fingers to start/stop following."
