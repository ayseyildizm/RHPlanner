#!/bin/bash
# hk_day_20260730.sh — daytime queue, H=4 first (Ayşe chose this order on 07-30
# after the baseline-reproducibility concern was raised: H=4 is the missing
# piece of the H=3 defence, K=20 is the optional candidate-count row).
#
#   1. H=4, K=10  (tag H4K10d, cap 8 h)  — last night's clean attempt was
#      healthy (7 ok / 2 failed, coverage 14.7->23.4) and was only stopped by
#      hk_night2.sh's misapplied 04:00 deadline at iteration 8.
#   2. H=3, K=20  (tag H3K20c, cap 5 h)  — the 07-28 run took 11 h with the GUI
#      and ended at 8/20 motions; headless should be far cheaper.
#
# Changes against hk_night3.sh:
#  a) Counter bug fixed.  `grep -c pat file || echo 0` returns "0\n0" when there
#     are no matches (grep prints 0 AND exits 1), so $iters was multi-line and
#     every `[ "$iters" -ge 4 ]` died with "integer expression expected" -- the
#     dead-run gate never actually ran last night, and the chain log recorded
#     "at iteration 0\n0".  Counted with a plain assignment + empty fallback now.
#  b) The ">=5 failed motions" abort is GONE.  Metrics json is only written when
#     a run finishes, so killing at failure 5 destroys the run for nothing: a
#     run that misses the >=80% gate is still usable in the thesis as a "could
#     not be evaluated" row plus a failure-mode breakdown (that is exactly how
#     lam0 and ikfilter are cited).  Only a genuinely dead run (no coverage at
#     all) or the per-run time cap aborts now.
#  c) Planner and stack logs are copied out at the end of every run, abort or
#     not.  run_ladder4.sh overwrites run_l4_<occ>_<planner>.log each time and
#     an aborted dir carries no metrics, so that log is the only salvage path
#     for the per-view curves (that is where the H=4 partial data came from).
#     hk_logsnap.sh still does this every 60 s; this is the belt-and-braces end
#     copy.  New tags (d/c) so last night's hk2_live_H4K10c.log survives.
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
CHAIN=$LOGS/hk_ablation_chain2_20260728.log
PLOG=$LOGS/run_l4_panels3_rh.log
SLOG=$LOGS/stack_l4_panels3.log
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

count() {  # count matches without the "0\n0" trap
    local n
    n=$(grep -c "$1" "$2" 2>/dev/null)
    [ -z "$n" ] && n=0
    echo "$n"
}

# $1 tag  $2 H  $3 K  $4 cap in hours
run_cfg() {
    local tag=$1 h=$2 k=$3 cap=$4 before pid rc dir iters fails cov aborted=0 limit
    before=$(date +%s)
    limit=$(( before + cap * 3600 ))
    : > "$PLOG"
    say "START $tag  H=$h K=$k (headless, cap ${cap}h, no fail-count abort)"
    env L4_TARGET=mug L4_OCCS=panels3 L4_PLANNERS=rh L4_TRIALS=1 \
        RH_H="$h" RH_K="$k" ./run_ladder4.sh > "$LOGS/hk2_${tag}.log" 2>&1 &
    pid=$!

    while kill -0 "$pid" 2>/dev/null; do
        sleep 120
        iters=$(count "\[RH\] coverage=" "$PLOG")
        fails=$(count "Arm motion failed" "$PLOG")
        cov=$(grep -oE "coverage=[0-9.]+" "$PLOG" 2>/dev/null | tail -1 | cut -d= -f2)
        if [ "$iters" -ge 4 ] && [ "${cov:0:3}" = "0.0" ]; then
            say "ABORT $tag: no coverage after $iters iterations (dead run, $fails failed motions)"
            aborted=1
        elif [ "$(date +%s)" -ge "$limit" ]; then
            say "ABORT $tag: ${cap}h cap reached at iteration $iters ($fails failed motions)"
            aborted=1
        fi
        if [ "$aborted" = 1 ]; then
            kill -9 "$pid" 2>/dev/null   # ladder first: killing the planner
            sleep 2                      # first gives rc=137 -> ladder retries
            pkill -9 -f "test_rh_nod[e].py" 2>/dev/null
            break
        fi
    done
    wait "$pid" 2>/dev/null; rc=$?

    # salvage the logs before kill_stack / the next run overwrite them
    [ -f "$PLOG" ] && cp -f "$PLOG" "$LOGS/hk2_live_${tag}.log"
    [ -f "$SLOG" ] && cp -f "$SLOG" "$LOGS/hk2_stack_${tag}.log"
    kill_stack

    dir=$(find "$RH_DIR/results" -maxdepth 1 -type d \
              -name "run_*_expC_panels3_K${k}_H${h}_box" -newermt "@$before" | sort | tail -1)
    if [ -n "$dir" ]; then
        if [ ! -f "$dir/trial_00/metrics_rh_nbv_panels3.json" ]; then
            rm -rf "$dir"
            say "END   $tag rc=$rc aborted=$aborted NO METRICS (dir removed, log kept as hk2_live_${tag}.log)"
        else
            mv "$dir" "$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
            say "END   $tag rc=$rc aborted=$aborted dir=results/abtest_${tag}_$(basename "$dir")"
        fi
    else
        say "END   $tag rc=$rc NO RUN DIR FOUND (aborted=$aborted)"
    fi
}

say "=== DAY 07-30 START (H=4 first, then K=20; per-run caps) ==="
run_cfg H4K10d 4 10 8
run_cfg H3K20c 3 20 5
say "=== DAY 07-30 COMPLETE ==="
