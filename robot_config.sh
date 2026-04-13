#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Looks up ROS_DOMAIN_ID and ROS_DISCOVERY_SERVER for a given robot name
#  by calling robot-setup.sh (the same script used in the launch files).
#
#  Usage in any start script:
#    ROBOT="galapagos"
#    source "$(dirname "$0")/robot_config.sh" || exit 1
# ─────────────────────────────────────────────────────────────────────────────

if [ -z "$ROBOT" ]; then
  echo "ERROR: ROBOT is not set"
  exit 1
fi

# Run robot-setup.sh with the robot name and capture the resulting environment
_tmp=$(mktemp)
bash -c "printf '%s' '$ROBOT' | robot-setup.sh && env" 2>/dev/null > "$_tmp"

if [ ! -s "$_tmp" ]; then
  echo "ERROR: robot-setup.sh failed or not found for robot '$ROBOT'"
  rm -f "$_tmp"
  exit 1
fi

ROS_DOMAIN_ID=$(grep '^ROS_DOMAIN_ID=' "$_tmp" | cut -d= -f2- | tr -d '[:space:]')
ROS_DISCOVERY_SERVER=$(grep '^ROS_DISCOVERY_SERVER=' "$_tmp" | cut -d= -f2-)
rm -f "$_tmp"

ROBOT_NAME="$ROBOT"

if [ -n "$ROS_DOMAIN_ID_OVERRIDE" ]; then
  ROS_DOMAIN_ID="$ROS_DOMAIN_ID_OVERRIDE"
fi

if [ -n "$ROS_DISCOVERY_SERVER_OVERRIDE" ]; then
  ROS_DISCOVERY_SERVER="$ROS_DISCOVERY_SERVER_OVERRIDE"
fi

if [ -z "$ROS_DOMAIN_ID" ]; then
  echo "ERROR: Could not determine ROS_DOMAIN_ID for robot '$ROBOT'"
  exit 1
fi

echo "==> Robot: $ROBOT_NAME  |  Domain: $ROS_DOMAIN_ID  |  Discovery: $ROS_DISCOVERY_SERVER"
