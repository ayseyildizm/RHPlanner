#!/bin/bash
# run_tree.sh — tree/tomato variant of run_ros2.sh / run_ros2_gz.sh.
# Same environment setup (kept in sync by copy — bunny/mug runners untouched),
# but launches the tree wrapper nodes.
#
# PREREQUISITE — robot stack running with a prebuilt tree world, e.g.:
#   OCC=panels_tree_fruit_y090 ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py
# (worlds built once by:  python3 make_tree_world.py)
#
# Usage:
#   PLANNER=rh|gradient (default rh), plus the tree env vars:
#   OCC=panels_tree_fruit_y090 TOMATO_TARGET=fruit TREE_YAW=90 ROI_HALF=0.105 ./run_tree.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS2_WS="$HOME/ros2_ws"
CONDA_PYTHON="$HOME/miniconda3/envs/rh_nbv_ros2/bin/python"

case "${PLANNER:-rh}" in
    rh)       NODE="test_rh_tree_node.py" ;;
    gradient) NODE="test_gradient_tree_node.py" ;;
    *) echo "[ERROR] PLANNER must be rh or gradient (got '${PLANNER}')"; exit 1 ;;
esac

# Clear any stale ROS1/Humble environment so Jazzy starts clean
unset ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH
unset ROS_PACKAGE_PATH PYTHONPATH LD_LIBRARY_PATH

# Source ROS 2 Jazzy
source /opt/ros/jazzy/setup.bash

# Source the abb_interfaces colcon workspace
if [ -f "$ROS2_WS/install/setup.bash" ]; then
    source "$ROS2_WS/install/setup.bash"
else
    echo "[ERROR] $ROS2_WS/install/setup.bash not found."
    exit 1
fi

# Python path: project source trees + ROS 2 Jazzy packages
export PYTHONPATH=\
$SCRIPT_DIR/src/viewpoint_planning/src:\
$SCRIPT_DIR/src/robot/abb_control/src:\
$SCRIPT_DIR/src/common/utils/src:\
/opt/ros/jazzy/lib/python3.12/site-packages:\
$ROS2_WS/install/abb_interfaces/lib/python3.12/site-packages

export LD_LIBRARY_PATH=/opt/ros/jazzy/lib:$ROS2_WS/install/abb_interfaces/lib:$ROS2_WS/install/abb_control/lib
export PYTHONUNBUFFERED=1

exec "$CONDA_PYTHON" -u \
    "$SCRIPT_DIR/src/viewpoint_planning/src/$NODE" "$@"
