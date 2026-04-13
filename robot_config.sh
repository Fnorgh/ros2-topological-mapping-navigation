#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Robot name → ROS config lookup
#  Add a new robot by copying one of the blocks below.
#  Usage in any start script:
#    ROBOT="snapper"
#    source "$(dirname "$0")/robot_config.sh"
# ─────────────────────────────────────────────────────────────────────────────

case "$ROBOT" in
  snapper)
    ROBOT_NAME="snapper"
    ROS_DOMAIN_ID="4"
    ROS_DISCOVERY_SERVER=";;;;10.194.16.39:11811;"
    ;;
  # add more robots below:
  # robotics4)
  #   ROBOT_NAME="robotics4"
  #   ROS_DOMAIN_ID="1"
  #   ROS_DISCOVERY_SERVER=";10.194.16.36:11811;"
  #   ;;
  *)
    echo "ERROR: Unknown robot '$ROBOT'"
    echo "       Add it to robot_config.sh"
    exit 1
    ;;
esac

echo "==> Robot: $ROBOT_NAME  |  Domain: $ROS_DOMAIN_ID  |  Discovery: $ROS_DISCOVERY_SERVER"
