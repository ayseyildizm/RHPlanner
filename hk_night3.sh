#!/bin/bash
# hk_night3.sh — replaces hk_night2.sh, whose absolute 04:00 deadline was meant
# only for the H=4 hand-over but applied to every watchdog run and killed the
# K=20 run two minutes after it started.
#
# Here each run gets its own budget measured from its own start:
#   1. K=20, H=3   — fills the "could not be evaluated" row (cap 5 h)
#   2. H=4, K=10   — the missing piece for defending H=3; the clean attempt was
#      healthy (7/2 motions, coverage climbing) and only stopped by that bug's
#      deadline at iteration 8 (cap 8 h)
# Abort rules per run: >=5 failed motions, or no coverage by iteration 4, or the
# per-run cap. Ladder is killed before the planner, otherwise rc=137 makes
# run_ladder4.sh retry the whole configuration.
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
CHAIN=$LOGS/hk_ablation_chain2_20260728.log
PLOG=$LOGS/run_l4_panels3_rh.log
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

# $1 tag  $2 H  $3 K  $4 cap in hours
run_cfg() {
    local tag=$1 h=$2 k=$3 cap=$4 before pid rc dir iters fails cov aborted=0 limit
    before=$(date +%s)
    limit=$(( before + cap * 3600 ))
    : > "$PLOG"
    say "START $tag  H=$h K=$k (headless, cap ${cap}h)"
    env L4_TARGET=mug L4_OCCS=panels3 L4_PLANNERS=rh L4_TRIALS=1 \
        RH_H="$h" RH_K="$k" ./run_ladder4.sh > "$LOGS/hk2_${tag}.log" 2>&1 &
    pid=$!

    while kill -0 "$pid" 2>/dev/null; do
        sleep 120
        iters=$(grep -c "\[RH\] coverage=" "$PLOG" 2>/dev/null || echo 0)
        fails=$(grep -c "Arm motion failed" "$PLOG" 2>/dev/null || echo 0)
        cov=$(grep -oE "coverage=[0-9.]+" "$PLOG" 2>/dev/null | tail -1 | cut -d= -f2)
        if [ "$fails" -ge 5 ]; then
            say "ABORT $tag: $fails failed motions at iteration $iters (gate allows 4)"
            aborted=1
        elif [ "$iters" -ge 4 ] && [ "${cov:0:3}" = "0.0" ]; then
            say "ABORT $tag: no coverage after $iters iterations (dead run)"
            aborted=1
        elif [ "$(date +%s)" -ge "$limit" ]; then
            say "ABORT $tag: ${cap}h cap reached at iteration $iters"
            aborted=1
        fi
        if [ "$aborted" = 1 ]; then
            kill -9 "$pid" 2>/dev/null
            sleep 2
            pkill -9 -f "test_rh_nod[e].py" 2>/dev/null
            break
        fi
    done
    wait "$pid" 2>/dev/null; rc=$?
    kill_stack

    # run_ladder4.sh overwrites $PLOG on every run, and an aborted run has its
    # directory deleted below, so this snapshot is the only surviving evidence
    # (pose commands, OMPL messages, failure modes) for that attempt.
    cp -f "$PLOG" "$LOGS/hk2_live_${tag}.log" 2>/dev/null

    dir=$(find "$RH_DIR/results" -maxdepth 1 -type d \
              -name "run_*_expC_panels3_K${k}_H${h}_box" -newermt "@$before" | sort | tail -1)
    if [ -n "$dir" ]; then
        if [ "$aborted" = 1 ] && [ ! -f "$dir/trial_00/metrics_rh_nbv_panels3.json" ]; then
            rm -rf "$dir"
            say "END   $tag ABORTED (empty run dir removed)"
        else
            mv "$dir" "$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
            say "END   $tag rc=$rc dir=$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
        fi
    else
        say "END   $tag rc=$rc NO RUN DIR FOUND (aborted=$aborted)"
    fi
}

# H=4 runs first: it is the missing piece of the H=3 defence, while K=20 is
# optional sensitivity. If only one of the two survives the night, it should be
# this one.
say "=== NIGHT3 START (H=4 then K=20, per-run caps) ==="
run_cfg H4K10c 4 10 8
run_cfg H3K20b 3 20 5
say "=== NIGHT3 COMPLETE ==="
