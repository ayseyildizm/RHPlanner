#!/bin/bash
# hk_ikrun.sh — reachability-aware RH-NBV run (mug, panels3, H=3, K=10),
# to be compared against the frozen 2026-07-07 baseline run of the identical
# configuration (63.82 % coverage, F1 0.892, 20/20 motions).
#
# Waits for the overnight chain (hk_chain3.sh) to finish, brings up its own
# Gazebo stack, runs test_rh_ik_node.py through run_ik_gz.sh, then tears the
# stack down and renames the run dir to abtest_ikfilter_*.
#
# Stack start/stop mirrors run_ladder4.sh (launch-parent + gz hard kill,
# camera-stream wait); run_ladder4.sh itself is not touched or reused because
# it hardcodes the four planner entry points.
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
CHAIN=$LOGS/hk_ablation_chain2_20260728.log
OCC=panels3
cd "$RH_DIR" || exit 1
say() { echo "[$(date +%Y-%m-%d_%H:%M:%S)] $*" >> "$CHAIN"; }

kill_stack() {
    pkill -9 -f "test_rh_ik_node.p[y]" 2>/dev/null
    pkill -9 -f "test_rh_node.p[y]" 2>/dev/null
    pkill -INT -f "move_group_gz_ur5e.launch.p[y]" 2>/dev/null
    for _ in $(seq 1 15); do
        pgrep -f "worlds/ur5e_worl[d]" >/dev/null || break
        sleep 2
    done
    pkill -9 -f "move_group_gz_ur5e.launch.p[y]" 2>/dev/null
    pkill -9 -f "g[z] sim" 2>/dev/null
    pkill -9 -f "moveit_ros_move_grou[p]" 2>/dev/null
    pkill -9 -f "arm_control_nod[e]" 2>/dev/null
    pkill -9 -f "parameter_bridg[e]" 2>/dev/null
    pkill -9 -f "worlds/ur5e_worl[d]" 2>/dev/null
    pkill -9 -f "robot_state_publishe[r]" 2>/dev/null
    sleep 4
    rm -f /dev/shm/fastrtps_* /dev/shm/fast_datasharing* 2>/dev/null
    sleep 4
}

start_stack() {
    kill_stack
    nohup bash -c "source /opt/ros/jazzy/setup.bash && \
        source \$HOME/ros2_ws/install/setup.bash && \
        export GZ_SIM_RESOURCE_PATH=\$GZ_SIM_RESOURCE_PATH:\$HOME/ros2_ws/install/ur5e_l515_description/share && \
        export DISPLAY=:0 && \
        OCC=$OCC TARGET=mug exec ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py" \
        > "$LOGS/stack_ik_$OCC.log" 2>&1 &
    for _ in $(seq 1 80); do
        if grep -q "serving move_arm_to_pose" "$LOGS/stack_ik_$OCC.log" 2>/dev/null; then
            bash -c "source /opt/ros/jazzy/setup.bash && \
                source \$HOME/ros2_ws/install/setup.bash && \
                timeout 180 ros2 topic echo --once /camera/color/image_rect_color" \
                >/dev/null 2>&1 || say "WARN: camera stream not up after arm service"
            sleep 3
            return 0
        fi
        sleep 10
    done
    say "ERROR: stack did not come up"
    return 1
}

# Hold until the overnight chain is completely finished.
while pgrep -f "hk_chain[3].sh" > /dev/null; do sleep 60; done
while pgrep -f "run_ladder[4].sh" > /dev/null; do sleep 60; done
sleep 30

before=$(date +%s)
say "START ikfilter  H=3 K=10 lambda=2.0 IK-filtered trials=1"
if start_stack; then
    timeout 45000 env OCC="$OCC" TARGET=mug PLANNER=rh NUM_TRIALS=1 EXPERIMENT=C RVIZ=0 \
        RH_H=3 RH_K=10 RH_IK_FILTER=1 \
        ./run_ik_gz.sh > "$LOGS/hk2_ikfilter.log" 2>&1
    rc=$?
else
    rc=1
fi
kill_stack

dir=$(find "$RH_DIR/results" -maxdepth 1 -type d \
          -name "run_*_expC_${OCC}_K10_H3_box" -newermt "@$before" | sort | tail -1)
if [ -n "$dir" ]; then
    mv "$dir" "$RH_DIR/results/abtest_ikfilter_$(basename "$dir")"
    say "END   ikfilter rc=$rc dir=$RH_DIR/results/abtest_ikfilter_$(basename "$dir")"
else
    say "END   ikfilter rc=$rc NO RUN DIR FOUND"
fi
