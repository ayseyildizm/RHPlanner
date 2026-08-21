#!/bin/bash
# hk_k20_full.sh — one K=20, H=3 run allowed to finish all 20 views.
#
# Three K=20 attempts have now ended without a metrics file: the 28 July run
# wedged, the 30 July run hit a 5 h cap while healthy, and the 31 July run was
# stopped by the frozen-coverage gate at iteration 12. Each abort saved machine
# time and cost the data.
#
# The point here is different. run_ladder4.sh writes metrics only when a run
# completes its 20 views, and a run that stalls still answers the question the
# ablation asks -- whether a larger candidate budget helps. The 31 July run was
# frozen at 27.92 % coverage with F1 0.257 from its eighth view on, which is a
# result if it reaches the end and produces a file.
#
# So no quality gates here. Only a wall-clock backstop against a wedged stack.
# Whether the run meets the 80 % motion criterion is then decided from its
# metrics, not by this script.
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
CHAIN=$LOGS/hk_ablation_chain2_20260728.log
PLOG=$LOGS/run_l4_panels3_rh.log
CAP_H=12
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

tag=H3K20full
stamp=$(date +%Y%m%d_%H%M%S)
before=$(date +%s)
limit=$(( before + CAP_H * 3600 ))
: > "$PLOG"
say "START $tag  H=3 K=20 (headless, no quality gates, backstop ${CAP_H}h)"

env L4_TARGET=mug L4_OCCS=panels3 L4_PLANNERS=rh L4_TRIALS=1 \
    RH_H=3 RH_K=20 ./run_ladder4.sh > "$LOGS/hk2_${tag}_${stamp}.log" 2>&1 &
pid=$!

aborted=0
while kill -0 "$pid" 2>/dev/null; do
    sleep 120
    if [ "$(date +%s)" -ge "$limit" ]; then
        say "ABORT $tag: ${CAP_H}h backstop reached at iteration $(grep -c '\[RH\] coverage=' "$PLOG" 2>/dev/null)"
        aborted=1
        kill -9 "$pid" 2>/dev/null
        sleep 2
        pkill -9 -f "test_rh_nod[e].py" 2>/dev/null
        break
    fi
done
wait "$pid" 2>/dev/null; rc=$?
kill_stack
cp -f "$PLOG" "$LOGS/hk2_live_${tag}_${stamp}.log" 2>/dev/null

dir=$(find "$RH_DIR/results" -maxdepth 1 -type d \
          -name "run_*_expC_panels3_K20_H3_box" -newermt "@$before" | sort | tail -1)
if [ -n "$dir" ]; then
    # kept even without metrics: the partial series is the only record
    mv "$dir" "$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
    say "END   $tag rc=$rc aborted=$aborted dir=$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
else
    say "END   $tag rc=$rc NO RUN DIR FOUND (aborted=$aborted)"
fi
