#!/bin/bash
# run_tree_ladder.sh — tree (single tomato plant, natural occlusion) experiment.
#
# Design (Burusa 2024-style, adapted to ONE plant):
#   * Difficulty ladder = attention/ROI level, not artificial panels — the
#     plant's own leaves are the occluders:
#       all      whole plant   ROI_HALF=0.31, grid 0.38x0.6x0.62, voxel 5mm
#       blossom  3 blossoms    ROI_HALF=0.22, grid 0.30x0.6x0.46, voxel 4mm
#       fruit    4 fruits      ROI_HALF=0.105, default grid,      voxel 3mm
#     (grid/voxel deviate from the bunny defaults only where the plant/ROI
#      doesn't fit; within a stage both planners get identical settings.)
#   * Trial variation = plant yaw about its own axis (default 0/90/180/270) —
#     each orientation hides different fruits behind different leaves.
#     Yaw values must have prebuilt worlds:  python3 make_tree_world.py
#   * Planners per (stage, yaw): GradientNBV baseline, then RH-NBV, same
#     stack. RH params stay at the bunny/mug values (K/H from env if set).
#
# Fully separate from run_ladder.sh — no bunny/mug file is touched or reused
# except read-only (base world, drivers via the tree wrappers).
#
# Override examples:
#   TREE_STAGES="fruit" TREE_YAWS="0 90" ./run_tree_ladder.sh
#
# Progress: results/_explogs/tree_ladder_progress.log
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
PROGRESS=$LOGS/tree_ladder_progress.log
mkdir -p "$LOGS"

STAGES="${TREE_STAGES:-all blossom fruit}"
YAWS="${TREE_YAWS:-0 90 180 270}"
PLANNERS="${TREE_PLANNERS:-gradient rh}"

say() { echo "[$(date +%H:%M:%S)] $*" >> "$PROGRESS"; }

kill_stack() {
    # Same graceful-first shutdown as run_ladder.sh (SIGKILLing gz/DDS
    # mid-flight leaves stale transport state -> zombie stacks).
    pkill -9 -f "test_rh_tree_node.py" 2>/dev/null
    pkill -9 -f "test_gradient_tree_node.py" 2>/dev/null
    pkill -INT -f "move_group_gz_ur5e.launch.py" 2>/dev/null
    for _ in $(seq 1 15); do
        pgrep -f "worlds/ur5e_world" >/dev/null || break
        sleep 2
    done
    # The ros2 launch PARENT can survive INT (observed 2026-07-11: a 14:00
    # zombie parent overlapped every later stack and broke the controller
    # spawners -> zero-data runs). Kill it and gz hard before the rest.
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

start_stack() {  # $1 = OCC label (world is prebuilt; no TARGET needed here)
    kill_stack
    nohup bash -c "source /opt/ros/jazzy/setup.bash && \
        source \$HOME/ros2_ws/install/setup.bash && \
        export GZ_SIM_RESOURCE_PATH=\$GZ_SIM_RESOURCE_PATH:\$HOME/ros2_ws/install/ur5e_l515_description/share && \
        export DISPLAY=:0 && \
        OCC=$1 exec ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py" \
        > "$LOGS/stack_$1.log" 2>&1 &
    for _ in $(seq 1 80); do
        if grep -q "serving move_arm_to_pose" "$LOGS/stack_$1.log" 2>/dev/null; then
            # Arm service up; now wait for the camera stream too. After a
            # stack restart the gz->ROS bridge can lag by minutes, and a
            # planner started early burns its first views on "No data from
            # camera" (observed on the y090 makeup run, 2026-07-11).
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

run_one() {  # $1=OCC  $2=rh|gradient  $3=TOMATO_TARGET  $4=yaw  $5=ROI_HALF  $6=grid("" = default)  $7=voxel("" = default)  $8=F1_THRESH
    local occ=$1 planner=$2 tt=$3 yaw=$4 roi=$5 grid=$6 vox=$7 f1t=$8
    cd "$RH_DIR"
    local tmo=9000 marker="All trials complete"
    if [ "$planner" = "gradient" ]; then tmo=6000; marker="baseline complete"; fi
    local log="$LOGS/run_${occ}_${planner}.log"
    for attempt in 1 2; do
        say "START $occ $planner (attempt $attempt)"
        timeout $tmo env OCC="$occ" PLANNER="$planner" \
            TARGET=tomato TOMATO_TARGET="$tt" TREE_YAW="$yaw" ROI_HALF="$roi" \
            ${grid:+GRID_SIZE="$grid"} ${vox:+VOXEL_SIZE="$vox"} \
            F1_THRESH="$f1t" \
            NUM_TRIALS=1 EXPERIMENT=C RVIZ=0 \
            ./run_tree.sh > "$log" 2>&1 &
        local pid=$!
        # The drivers can hang in ROS shutdown AFTER all results are on disk
        # (observed with the gradient node 2026-07-11). Don't burn the whole
        # timeout waiting: once the completion marker is printed, give the
        # process a grace period and kill the leftover.
        while kill -0 "$pid" 2>/dev/null; do
            if grep -q "$marker" "$log" 2>/dev/null; then
                sleep 15
                pkill -9 -f "test_rh_tree_node.py" 2>/dev/null
                pkill -9 -f "test_gradient_tree_node.py" 2>/dev/null
                break
            fi
            sleep 15
        done
        wait "$pid"
        rc=$?
        # A kill after the marker is a SUCCESS, not a failure.
        grep -q "$marker" "$log" 2>/dev/null && rc=0
        # Zombie-stack detection: a "successful" run whose every iteration
        # reports coverage=0.0000 got no sensor data (controllers never
        # spawned). Restart the stack and retry once.
        if [ "$rc" -eq 0 ] && ! grep -qE "coverage=([1-9]|0\.[0-9]*[1-9])" "$log"; then
            say "ZERO-DATA $occ $planner (zombie stack?) attempt $attempt"
            rc=1
            if [ "$attempt" = 1 ]; then
                start_stack "$occ" || return 1
                continue
            fi
        fi
        say "END $occ $planner rc=$rc (attempt $attempt)"
        # 137 = SIGKILL (kernel OOM). Wait for pressure to ease, retry once.
        { [ "$rc" -ne 137 ] && [ "$rc" -ne 134 ]; } && break  # 134=SIGABRT (transient torch clock assert 2026-07-11)
        say "OOM RETRY $occ $planner"
        sleep 30
    done
}

# Wait for any in-flight planner to finish before taking over.
while pgrep -f "test_rh_node.py|test_gradient_node.py|test_rh_tree_node.py|test_gradient_tree_node.py" > /dev/null; do sleep 20; done

say "=== TREE LADDER START (stages: $STAGES | yaws: $YAWS | planners: $PLANNERS) ==="
for stage in $STAGES; do
    # F1T = F1 match threshold = 2x voxel size. The default (4x voxel = 12mm)
    # was tuned for the bunny; on 20-70mm fruits it saturates F1 at ~1.0 from
    # view 1. DIAG on fruit_y000 measured the actual voxel->surface offset as
    # med 1.5mm / max 4.8mm, so 2x voxel keeps precision intact.
    case $stage in
        all)     TT=all;     ROI=0.31;  GRID="0.38,0.6,0.62"; VOX=0.005; F1T=0.010 ;;
        blossom) TT=blossom; ROI=0.22;  GRID="0.3,0.6,0.46";  VOX=0.004; F1T=0.008 ;;
        fruit)   TT=fruit;   ROI=0.105; GRID="";              VOX="";    F1T=0.006 ;;
        *) say "SKIP unknown stage '$stage'"; continue ;;
    esac
    for yaw in $YAWS; do
        occ=$(printf 'panels_tree_%s_y%03d' "$stage" "$yaw")
        wf=$HOME/ros2_ws/install/ur5e_l515_description/share/ur5e_l515_description/worlds/ur5e_world_$occ.sdf
        if [ ! -f "$wf" ]; then
            say "SKIP $occ: world not built — run 'python3 make_tree_world.py' first"
            continue
        fi
        if start_stack "$occ"; then
            for planner in $PLANNERS; do
                run_one "$occ" "$planner" "$TT" "$yaw" "$ROI" "$GRID" "$VOX" "$F1T"
            done
        fi
    done
done
kill_stack
say "=== TREE LADDER COMPLETE ==="
