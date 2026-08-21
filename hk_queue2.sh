#!/bin/bash
# hk_queue2.sh — reorder the remaining runs (Ayşe, 2026-07-29): K=20 first,
# H=5 last.
#
# hk_h4.sh is already running H=4 and would continue with H=5. A running bash
# script cannot be edited safely, so this queue waits for the H=4 result line
# in the chain log, stops hk_h4.sh before its H=5 step can get going, and then
# runs the remaining two configurations itself:
#   1. K=20, H=3   (headless rerun; the earlier attempt executed 8/20 motions,
#      seven of them lost to controller aborts while the Gz GUI was running)
#   2. H=5, K=10
# Both run with HEADLESS=1, which is what made the H=4 retry healthy.
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
CHAIN=$LOGS/hk_ablation_chain2_20260728.log
export HEADLESS=1
cd "$RH_DIR" || exit 1
say() { echo "[$(date +%Y-%m-%d_%H:%M:%S)] $*" >> "$CHAIN"; }

kill_stack() {
    pkill -9 -f "test_rh_nod[e].py" 2>/dev/null
    pkill -INT -f "move_group_gz_ur5e.launch.p[y]" 2>/dev/null
    sleep 8
    for p in "move_group_gz_ur5e.launch.p[y]" "g[z] sim" "moveit_ros_move_grou[p]" \
             "arm_control_nod[e]" "parameter_bridg[e]" "worlds/ur5e_worl[d]" \
             "robot_state_publishe[r]"; do
        pkill -9 -f "$p" 2>/dev/null
    done
    sleep 4
    rm -f /dev/shm/fastrtps_* /dev/shm/fast_datasharing* 2>/dev/null
    sleep 4
}

run_cfg() {  # $1 tag  $2 H  $3 K
    local tag=$1 h=$2 k=$3 before rc dir
    before=$(date +%s)
    say "START $tag  H=$h K=$k lambda=2.0 trials=1 (headless)"
    env L4_TARGET=mug L4_OCCS=panels3 L4_PLANNERS=rh L4_TRIALS=1 \
        RH_H="$h" RH_K="$k" ./run_ladder4.sh > "$LOGS/hk2_${tag}.log" 2>&1
    rc=$?
    dir=$(find "$RH_DIR/results" -maxdepth 1 -type d \
              -name "run_*_expC_panels3_K${k}_H${h}_box" -newermt "@$before" \
          | sort | tail -1)
    if [ -n "$dir" ]; then
        mv "$dir" "$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
        say "END   $tag rc=$rc dir=$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
    else
        say "END   $tag rc=$rc NO RUN DIR FOUND"
    fi
}

# Wait for H=4 to report, then stop hk_h4.sh before it starts H=5.
while ! grep -q "END   H4K10" "$CHAIN"; do sleep 20; done
say "H4K10 finished; taking over the queue (K=20 next, H=5 last)"
pkill -9 -f "hk_h[4].sh" 2>/dev/null
sleep 2
pkill -9 -f "run_ladder[4].sh" 2>/dev/null
kill_stack

run_cfg H3K20b 3 20
run_cfg H5K10  5 10
say "=== QUEUE2 COMPLETE (K=20 rerun + H=5) ==="
