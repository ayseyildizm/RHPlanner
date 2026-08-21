#!/bin/bash
# run_lamprobe.sh — short instrumented run that measures how large lambda would
# have to be before the motion penalty changes which candidate the planner picks.
#
# Runs test_rh_lamprobe_node.py, which patches RHPlanner.evaluate_sequence in
# memory to record the discounted gain G and discounted motion cost C of every
# candidate at every iteration. The flip weight lambda* = dG/dC then follows
# directly (analyze_lamprobe.py).
#
# Only a handful of iterations are needed, because the ratio between the gain
# spread and the cost spread is a property of the scene and the sampler, not of
# how long the run goes on. Default is 5.
#
# NEW file. run_ros2_gz.sh and run_ladder4.sh are not touched; the environment
# block below mirrors run_ros2_gz.sh and the stack handling mirrors
# run_ladder4.sh.
#
#   ./run_lamprobe.sh                       # mug, panels3, 5 iterations
#   LP_OCC=panels5 LP_ITERS=8 ./run_lamprobe.sh
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
ROS2_WS="$HOME/ros2_ws"
CONDA_PYTHON="$HOME/miniconda3/envs/rh_nbv_ros2/bin/python"
LOGS=$RH_DIR/results/_explogs
mkdir -p "$LOGS"

OCC="${LP_OCC:-panels3}"
TGT="${LP_TARGET:-mug}"
ITERS="${LP_ITERS:-5}"
LAM="${LP_LAMBDA:-2.0}"
STACK_LOG="$LOGS/stack_lamprobe_${OCC}.log"
RUN_LOG="$LOGS/lamprobe_${OCC}_$(date +%Y%m%d_%H%M%S).log"

kill_stack() {
    pkill -INT -f "move_group_gz_ur5e.launch.py" 2>/dev/null
    sleep 3
    pkill -9 -f "move_group_gz_ur5e.launch.py" 2>/dev/null
    pkill -9 -f "gz sim" 2>/dev/null
    rm -f /dev/shm/fastrtps_* /dev/shm/fast_datasharing* 2>/dev/null
    sleep 4
}

start_stack() {
    kill_stack
    nohup bash -c "source /opt/ros/jazzy/setup.bash && \
        source \$HOME/ros2_ws/install/setup.bash && \
        export GZ_SIM_RESOURCE_PATH=\$GZ_SIM_RESOURCE_PATH:\$HOME/ros2_ws/install/ur5e_l515_description/share && \
        export DISPLAY=:0 && \
        OCC=$OCC TARGET=$TGT exec ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py" \
        > "$STACK_LOG" 2>&1 &
    for _ in $(seq 1 80); do
        if grep -q "serving move_arm_to_pose" "$STACK_LOG" 2>/dev/null; then
            bash -c "source /opt/ros/jazzy/setup.bash && \
                source \$HOME/ros2_ws/install/setup.bash && \
                timeout 180 ros2 topic echo --once /camera/color/image_rect_color" \
                >/dev/null 2>&1
            sleep 3
            return 0
        fi
        sleep 3
    done
    echo "[lamprobe] FATAL: stack not ready in 4 min" | tee -a "$RUN_LOG"
    return 1
}

echo "[lamprobe] target=$TGT occ=$OCC iters=$ITERS lambda=$LAM" | tee "$RUN_LOG"
start_stack || exit 1

# Environment as in run_ros2_gz.sh
unset ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH
unset ROS_PACKAGE_PATH PYTHONPATH LD_LIBRARY_PATH
set +u                       # ROS setup scripts reference unset variables
source /opt/ros/jazzy/setup.bash
source "$ROS2_WS/install/setup.bash"
set -u
export PYTHONPATH=\
$RH_DIR/src/viewpoint_planning/src:\
$RH_DIR/src/robot/abb_control/src:\
$RH_DIR/src/common/utils/src:\
/opt/ros/jazzy/lib/python3.12/site-packages:\
$ROS2_WS/install/abb_interfaces/lib/python3.12/site-packages
export LD_LIBRARY_PATH=/opt/ros/jazzy/lib:/opt/ros/jazzy/opt/gz_transport_vendor/lib:$ROS2_WS/install/abb_interfaces/lib:$ROS2_WS/install/abb_control/lib
export PYTHONUNBUFFERED=1
export USE_SIM_TIME=true

cd "$RH_DIR"
OCC="$OCC" TARGET="$TGT" EXPERIMENT=C RVIZ=0 \
NUM_ITERS="$ITERS" NUM_TRIALS=1 RH_LAMBDA="$LAM" RH_H=3 RH_K=10 \
    timeout 7200 "$CONDA_PYTHON" -u \
        src/viewpoint_planning/src/test_rh_lamprobe_node.py \
        --ros-args -p use_sim_time:=true >> "$RUN_LOG" 2>&1
rc=$?
echo "[lamprobe] planner exited rc=$rc" | tee -a "$RUN_LOG"
kill_stack
echo "[lamprobe] log: $RUN_LOG"
ls -t "$RH_DIR"/results/_lamprobe/lamprobe_*.json 2>/dev/null | head -1
