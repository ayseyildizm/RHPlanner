#!/bin/bash
# run_tree_dump.sh — run_tree.sh with the candidate-data dump enabled.
# Same environment setup (kept in sync by copy — run_tree.sh untouched), but
# launches test_rh_dump_node.py, which installs plots/candidate_dump.py and
# then runs the stock tree node underneath.
#
# The run behaves exactly like ./run_tree.sh PLANNER=rh and produces
# everything it normally would, plus candidates_data_<occ>.npz in the trial
# directory. Turn that into the thesis figures with:
#
#   python3 src/viewpoint_planning/src/plots/plot_candidates_thesis.py \
#       <trial_dir>/candidates_data_<occ>.npz --out <trial_dir>
#
# PREREQUISITE — robot stack running with a prebuilt tree world, e.g.:
#   OCC=panels_tree_all_y000 ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py
#
# Usage (the scene used for the RH search figure in the thesis):
#   OCC=panels_tree_all_y000 TOMATO_TARGET=all TREE_YAW=0 ./run_tree_dump.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS2_WS="$HOME/ros2_ws"
CONDA_PYTHON="$HOME/miniconda3/envs/rh_nbv_ros2/bin/python"

NODE="test_rh_dump_node.py"
export INNER_NODE="${INNER_NODE:-test_rh_tree_node.py}"

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
