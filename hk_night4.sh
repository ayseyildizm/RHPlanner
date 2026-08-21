#!/bin/bash
# hk_night4.sh — replaces hk_night3.sh. Order requested by Ayşe: K=20 first,
# then H=4.
#
# Three bugs in night3 are fixed here.
#
# 1. The cap killed a healthy run. K=20's planning cost is not constant: it
#    grew 1725 -> 4528 s per iteration while K=5 and K=10 stay flat near 230 s.
#    Six iterations took the whole 5 h budget even though every one of the
#    seven commanded motions succeeded. A full 20-view run is estimated at
#    25-35 h, so K=20 gets 36 h here and H=4 keeps 8 h. The cap is a backstop
#    against a wedged stack, not a schedule.
#
# 2. The dead-run gate never fired. It tested whether coverage started with
#    "0.0", so H=4 frozen at 0.4695 for six iterations passed it and only the
#    failed-motion counter stopped the run. It now aborts when the last five
#    coverage readings are identical, which is what a frozen run looks like.
#    Healthy runs repeat a value at most twice, so the threshold is safe.
#
# 3. The log snapshot overwrote an older run's log, because it was named after
#    the tag alone. Last night's H=4 snapshot destroyed the log of the healthy
#    30 July attempt. The name now carries the run's start time.
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
    local tag=$1 h=$2 k=$3 cap=$4 before pid rc dir iters fails frozen aborted=0 limit stamp
    before=$(date +%s)
    stamp=$(date +%Y%m%d_%H%M%S)
    limit=$(( before + cap * 3600 ))
    : > "$PLOG"
    say "START $tag  H=$h K=$k (headless, cap ${cap}h)"
    env L4_TARGET=mug L4_OCCS=panels3 L4_PLANNERS=rh L4_TRIALS=1 \
        RH_H="$h" RH_K="$k" ./run_ladder4.sh > "$LOGS/hk2_${tag}_${stamp}.log" 2>&1 &
    pid=$!

    while kill -0 "$pid" 2>/dev/null; do
        sleep 120
        iters=$(grep -c "\[RH\] coverage=" "$PLOG" 2>/dev/null || echo 0)
        fails=$(grep -c "Arm motion failed" "$PLOG" 2>/dev/null || echo 0)
        # a frozen run repeats the same coverage value; healthy ones do not
        # repeat more than twice, so five identical readings means it is stuck
        frozen=$(grep -oE "coverage=[0-9.]+" "$PLOG" 2>/dev/null | tail -5 \
                 | sort -u | wc -l)
        if [ "$fails" -ge 5 ]; then
            say "ABORT $tag: $fails failed motions at iteration $iters (gate allows 4)"
            aborted=1
        elif [ "$iters" -ge 6 ] && [ "$frozen" = 1 ]; then
            say "ABORT $tag: coverage frozen for five readings at iteration $iters"
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

    # run_ladder4.sh overwrites $PLOG on every run and an aborted run has its
    # directory deleted below, so this snapshot is the only surviving evidence
    cp -f "$PLOG" "$LOGS/hk2_live_${tag}_${stamp}.log" 2>/dev/null

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

# H=4 runs first. It answers quickly: when it fails it does so within about
# two hours, and the horizon question is the one the defence needs. K=20 is
# optional sensitivity and would otherwise hold the machine for 36 h before
# H=4 even started.
say "=== NIGHT4 START (H=4 then K=20, caps 8h / 36h) ==="
run_cfg H4K10d 4 10 8
run_cfg H3K20c 3 20 36
say "=== NIGHT4 COMPLETE ==="
