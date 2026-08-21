#!/bin/bash
# run_tree_f1dump.sh — run_tree.sh's environment, but the entry point is the
# F1-sweep dump wrapper. run_tree.sh itself is NOT modified.
#
# Usage (same env as run_tree.sh, plus PLANNER picks the inner node):
#   PLANNER=rh     OCC=panels_tree_fruit_y000 TOMATO_TARGET=fruit TREE_YAW=0 \
#       ROI_HALF=0.105 F1_THRESH=0.006 ./run_tree_f1dump.sh
#   PLANNER=random ... ./run_tree_f1dump.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS2_WS="$HOME/ros2_ws"
CONDA_PYTHON="$HOME/miniconda3/envs/rh_nbv_ros2/bin/python"

case "${PLANNER:-rh}" in
    rh)         export INNER_NODE="test_rh_tree_node.py" ;;
    gradient)   export INNER_NODE="test_gradient_tree_node.py" ;;
    pso|random) export INNER_NODE="test_baseline_tree_node.py" ;;
    *) echo "[ERROR] PLANNER must be rh, gradient, pso or random (got '${PLANNER}')"; exit 1 ;;
esac

unset ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH
unset ROS_PACKAGE_PATH PYTHONPATH LD_LIBRARY_PATH

source /opt/ros/jazzy/setup.bash
source "$ROS2_WS/install/setup.bash"

export PYTHONPATH=\
$SCRIPT_DIR/src/viewpoint_planning/src:\
$SCRIPT_DIR/src/robot/abb_control/src:\
$SCRIPT_DIR/src/common/utils/src:\
/opt/ros/jazzy/lib/python3.12/site-packages:\
$ROS2_WS/install/abb_interfaces/lib/python3.12/site-packages

export LD_LIBRARY_PATH=/opt/ros/jazzy/lib:$ROS2_WS/install/abb_interfaces/lib:$ROS2_WS/install/abb_control/lib
export PYTHONUNBUFFERED=1

exec "$CONDA_PYTHON" -u \
    "$SCRIPT_DIR/src/viewpoint_planning/src/test_tree_f1dump_node.py" "$@"
