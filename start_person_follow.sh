#!/usr/bin/env bash
# Set the robot name here or pass it as the first argument.

ROBOT="${1:-galapagos}"
source "$(dirname "$0")/robot_config.sh" || exit 1

WS=~/robotics/ros2-topological-mapping-navigation/ros2_ws
REPO=~/robotics/ros2-topological-mapping-navigation

ROS_ENV="unset ROS_LOCALHOST_ONLY && \
export ROS_DOMAIN_ID=$ROS_DOMAIN_ID && \
export ROS_DISCOVERY_SERVER=\"$ROS_DISCOVERY_SERVER\" && \
export ROS_SUPER_CLIENT=True && \
source $WS/install/setup.bash"

echo "==> Using local checkout at $REPO"
cd "$REPO" || exit 1

echo "==> Building package..."
cd "$WS" && colcon build --packages-select topological_nav
source "$WS/install/setup.bash"

echo "==> Opening terminals..."

gnome-terminal --title="Person Follow" -- bash -c "
$ROS_ENV
ros2 launch topological_nav person_follow.launch.xml
exec bash"

echo "==> Person follow launched silently."
echo "    YOLO follow starts immediately."
echo "    If no person is seen for 5 seconds, gesture mode activates."
echo "    Show 5 fingers to resume following."
