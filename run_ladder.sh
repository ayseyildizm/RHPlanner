#!/bin/bash
# run_ladder.sh — full difficulty-ladder experiment, publication run.
# Scenarios: none -> panels1 -> ... -> panels6
# (2026-07-06 relayout v2: 1=side wall, 2=+other side (TUNNEL), 3=+front (U),
#  4=4 walls, 5=+bottom lid flush under the walls (top open),
#  6=+top lid resting on the wall tops (sealed; bunny ears clip through it —
#  real target will be a coffee mug). ALL stages use identical panels.
#  Pre-2026-07-06 panels5 = full-height sealed box, and pre-2026-07-05
#  panelsN used DIFFERENT stages again — labels NOT comparable!)
# Planners per scenario: GradientNBV (baseline), then RH-NBV.
# Per scenario the Gazebo stack is restarted with the matching OCC world.
# Progress: results/_explogs/ladder_progress.log
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
PROGRESS=$LOGS/ladder_progress.log
mkdir -p "$LOGS"

say() { echo "[$(date +%H:%M:%S)] $*" >> "$PROGRESS"; }

kill_stack() {
    # Planner leftovers die hard; the stack gets a GRACEFUL shutdown first —
    # SIGKILLing gz/DDS mid-flight leaves stale transport state that produced
    # zombie stacks (failed controllers + empty sensor renders) on 2026-07-04.
    pkill -9 -f "test_rh_node.py" 2>/dev/null
    pkill -9 -f "test_gradient_node.py" 2>/dev/null
    pkill -INT -f "move_group_gz_ur5e.launch.py" 2>/dev/null
    for _ in $(seq 1 15); do
        pgrep -f "worlds/ur5e_world" >/dev/null || break
        sleep 2
    done
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
        OCC=$1 exec ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py" \
        > "$LOGS/stack_$1.log" 2>&1 &
    for _ in $(seq 1 80); do
        grep -q "serving move_arm_to_pose" "$LOGS/stack_$1.log" 2>/dev/null && { sleep 5; return 0; }
        sleep 3
    done
    say "FATAL: stack for $1 not ready in 4 min"
    return 1
}

run_one() {  # $1 = OCC, $2 = rh|gradient
    cd "$RH_DIR"
    for attempt in 1 2; do
        say "START $1 $2 (attempt $attempt)"
        if [ "$2" = "rh" ]; then
            timeout 9000 env OCC="$1" NUM_TRIALS=1 EXPERIMENT=C \
                ./run_ros2.sh > "$LOGS/run_${1}_rh.log" 2>&1
        else
            timeout 6000 env OCC="$1" PLANNER=gradient RVIZ=0 NUM_TRIALS=1 EXPERIMENT=C \
                ./run_ros2_gz.sh > "$LOGS/run_${1}_gradient.log" 2>&1
        fi
        rc=$?
        say "END $1 $2 rc=$rc (attempt $attempt)"
        # 137 = SIGKILL (kernel OOM). Wait for pressure to ease, retry once.
        [ "$rc" -ne 137 ] && break
        say "OOM RETRY $1 $2"
        sleep 30
    done
}

# Wait for any in-flight planner (smoke test) to finish before taking over.
while pgrep -f "test_rh_node.py|test_gradient_node.py" > /dev/null; do sleep 20; done

say "=== LADDER START (none, panels1..6 x gradient,rh) ==="
for occ in none panels1 panels2 panels3 panels4 panels5 panels6; do
    if start_stack "$occ"; then
        run_one "$occ" gradient
        run_one "$occ" rh
    fi
done
kill_stack
say "=== LADDER COMPLETE ==="
