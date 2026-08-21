#!/bin/bash
# run_ladder4.sh — 4-planner panel ladder: RH, GradientNBV, PSO, Random
# back-to-back per scenario (Ayşe 2026-07-19: "pes pese calistir hepsini").
#
# Scenarios: none -> panels1..6 -> panels8 (L-shape, regenerated for bunny
# 2026-07-19; manifest scenario "lshape-bunny").
# Per scenario the Gazebo stack is restarted with the matching OCC world and
# TARGET (default bunny). NUM_TRIALS default 5 (Ayşe's manual recipe).
#
# NEW file — run_ladder.sh (frozen bunny/mug finals) is not touched.
# Hardened patterns carried over from run_tree_ladder.sh: launch-parent + gz
# hard kill, camera-stream wait after arm service, completion-marker watchdog
# (drivers can hang in ROS shutdown after results are on disk), zero-data
# (zombie stack) retry, rc 134/137 transient retry.
#
# Overrides:
#   L4_OCCS="panels8" L4_PLANNERS="pso random" L4_TRIALS=1 ./run_ladder4.sh
#
# Progress: results/_explogs/ladder4_progress.log
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
PROGRESS=$LOGS/ladder4_progress.log
mkdir -p "$LOGS"

OCCS="${L4_OCCS:-none panels1 panels2 panels3 panels4 panels5 panels6 panels8}"
PLANNERS="${L4_PLANNERS:-rh gradient pso random}"
TRIALS="${L4_TRIALS:-5}"
TGT="${L4_TARGET:-bunny}"

say() { echo "[$(date +%H:%M:%S)] $*" >> "$PROGRESS"; }

kill_stack() {
    # Graceful-first shutdown; SIGKILLing gz/DDS mid-flight leaves stale
    # transport state -> zombie stacks (failed controllers, empty renders).
    pkill -9 -f "test_rh_node.py" 2>/dev/null
    pkill -9 -f "test_gradient_node.py" 2>/dev/null
    pkill -9 -f "test_baseline_node.py" 2>/dev/null
    pkill -INT -f "move_group_gz_ur5e.launch.py" 2>/dev/null
    for _ in $(seq 1 15); do
        pgrep -f "worlds/ur5e_world" >/dev/null || break
        sleep 2
    done
    # The ros2 launch PARENT can survive INT and overlap every later stack
    # (zombie-stack incident 2026-07-11). Kill it and gz hard first.
    pkill -9 -f "move_group_gz_ur5e.launch.py" 2>/dev/null
    pkill -9 -f "gz sim" 2>/dev/null
    pkill -9 -f "moveit_ros_move_group" 2>/dev/null
    pkill -9 -f "arm_control_node" 2>/dev/null
    pkill -9 -f "parameter_bridge" 2>/dev/null
    pkill -9 -f "worlds/ur5e_world" 2>/dev/null
    pkill -9 -f "robot_state_publisher" 2>/dev/null
    pkill -9 -f "rviz2" 2>/dev/null
    sleep 4
    rm -f /dev/shm/fastrtps_* /dev/shm/fast_datasharing* 2>/dev/null
    sleep 4
}

start_stack() {  # $1 = OCC label
    kill_stack
    nohup bash -c "source /opt/ros/jazzy/setup.bash && \
        source \$HOME/ros2_ws/install/setup.bash && \
        export GZ_SIM_RESOURCE_PATH=\$GZ_SIM_RESOURCE_PATH:\$HOME/ros2_ws/install/ur5e_l515_description/share && \
        export DISPLAY=:0 && \
        OCC=$1 TARGET=$TGT exec ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py" \
        > "$LOGS/stack_l4_$1.log" 2>&1 &
    for _ in $(seq 1 80); do
        if grep -q "serving move_arm_to_pose" "$LOGS/stack_l4_$1.log" 2>/dev/null; then
            # Arm service up; wait for the camera stream too — after a stack
            # restart the gz->ROS bridge can lag by minutes.
            if bash -c "source /opt/ros/jazzy/setup.bash && \
                    source \$HOME/ros2_ws/install/setup.bash && \
                    timeout 180 ros2 topic echo --once /camera/color/image_rect_color" \
                    >/dev/null 2>&1; then
                sleep 3
                return 0
            fi
            say "WARN: camera stream not up 3 min after arm service for $1 — starting anyway"
            return 0
        fi
        sleep 3
    done
    say "FATAL: stack for $1 not ready in 4 min"
    return 1
}

run_one() {  # $1 = OCC, $2 = rh|gradient|pso|random
    local occ=$1 planner=$2
    cd "$RH_DIR"
    # Timeouts sized for NUM_TRIALS=5 (caps, not waits).
    local tmo=45000 marker="All trials complete"
    case "$planner" in
        gradient)   tmo=24000; marker="baseline complete" ;;
        pso)        tmo=30000; marker="baseline complete" ;;
        random)     tmo=9000;  marker="baseline complete" ;;
    esac
    local log="$LOGS/run_l4_${occ}_${planner}.log"
    for attempt in 1 2; do
        say "START $occ $planner trials=$TRIALS (attempt $attempt)"
        timeout $tmo env OCC="$occ" TARGET="$TGT" PLANNER="$planner" \
            NUM_TRIALS="$TRIALS" EXPERIMENT=C RVIZ=0 \
            ./run_ros2_gz.sh > "$log" 2>&1 &
        local pid=$!
        # Drivers can hang in ROS shutdown AFTER results are on disk: once
        # the completion marker appears, grace period then kill the leftover.
        while kill -0 "$pid" 2>/dev/null; do
            if grep -q "$marker" "$log" 2>/dev/null; then
                sleep 15
                pkill -9 -f "test_rh_node.py" 2>/dev/null
                pkill -9 -f "test_gradient_node.py" 2>/dev/null
                pkill -9 -f "test_baseline_node.py" 2>/dev/null
                break
            fi
            sleep 15
        done
        wait "$pid"
        rc=$?
        # A kill after the marker is a SUCCESS, not a failure.
        grep -q "$marker" "$log" 2>/dev/null && rc=0
        # Zombie-stack detection: a "successful" run whose every iteration
        # reports coverage=0.0000 got no sensor data. Restart stack, retry.
        if [ "$rc" -eq 0 ] && ! grep -qE "coverage=([1-9]|0\.[0-9]*[1-9])" "$log"; then
            say "ZERO-DATA $occ $planner (zombie stack?) attempt $attempt"
            rc=1
            if [ "$attempt" = 1 ]; then
                start_stack "$occ" || return 1
                continue
            fi
        fi
        say "END $occ $planner rc=$rc (attempt $attempt)"
        # 137 = SIGKILL (kernel OOM); 134 = SIGABRT (transient torch clock
        # assert). Wait for pressure to ease, retry once.
        { [ "$rc" -ne 137 ] && [ "$rc" -ne 134 ]; } && break
        say "TRANSIENT RETRY $occ $planner (rc=$rc)"
        sleep 30
    done
}

# Wait for any in-flight planner to finish before taking over.
while pgrep -f "test_rh_node.py|test_gradient_node.py|test_baseline_node.py" > /dev/null; do sleep 20; done

say "=== LADDER4 START (occs: $OCCS | planners: $PLANNERS | trials: $TRIALS | target: $TGT) ==="
for occ in $OCCS; do
    if [ "$occ" != "none" ]; then
        wf=$HOME/ros2_ws/install/ur5e_l515_description/share/ur5e_l515_description/worlds/ur5e_world_$occ.sdf
        if [ ! -f "$wf" ]; then
            say "SKIP $occ: world $wf not found"
            continue
        fi
    fi
    if start_stack "$occ"; then
        for planner in $PLANNERS; do
            run_one "$occ" "$planner"
        done
    fi
done
kill_stack
say "=== LADDER4 COMPLETE ==="
