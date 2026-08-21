#!/bin/bash
# hk_night2.sh — overnight queue for 2026-07-30 (Ayşe left; autonomy granted:
# "temiz H=4'ü başlat, gerekli görürsen durdurup K=20'ye geç, sabaha bitmiş ol").
#
#   1. H=4, K=10  — clean headless attempt. H=3 is the default the thesis has
#      to defend, so the upper side of it needs a valid run. Three earlier
#      attempts died: two with the Gz GUI running, one headless that degraded
#      as it got longer.
#   2. K=20, H=3  — fills the "could not be evaluated" row of the table.
#
# H=4 is abandoned early if it cannot produce a usable run, so that K=20 still
# fits before morning:
#   * >=5 failed motions (the 80% gate allows 4) -> abort
#   * still no coverage by iteration 4           -> abort (dead run)
#   * not finished by DEADLINE                   -> abort
# Aborting kills run_ladder4.sh FIRST, then the planner: killing the planner
# alone returns 137 and the ladder would retry the whole configuration.
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
CHAIN=$LOGS/hk_ablation_chain2_20260728.log
PLOG=$LOGS/run_l4_panels3_rh.log
DEADLINE=$(date -d "04:00" +%s)   # hand the machine to K=20 at 04:00 at the latest
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

# $1 tag  $2 H  $3 K  $4 watchdog(1|0)
run_cfg() {
    local tag=$1 h=$2 k=$3 guard=$4 before pid rc dir iters fails cov aborted=0
    before=$(date +%s)
    : > "$PLOG"
    say "START $tag  H=$h K=$k (headless, watchdog=$guard)"
    env L4_TARGET=mug L4_OCCS=panels3 L4_PLANNERS=rh L4_TRIALS=1 \
        RH_H="$h" RH_K="$k" ./run_ladder4.sh > "$LOGS/hk2_${tag}.log" 2>&1 &
    pid=$!

    while kill -0 "$pid" 2>/dev/null; do
        sleep 120
        [ "$guard" = 1 ] || continue
        iters=$(grep -c "\[RH\] coverage=" "$PLOG" 2>/dev/null || echo 0)
        fails=$(grep -c "Arm motion failed" "$PLOG" 2>/dev/null || echo 0)
        cov=$(grep -oE "coverage=[0-9.]+" "$PLOG" 2>/dev/null | tail -1 | cut -d= -f2)
        if [ "$fails" -ge 5 ]; then
            say "ABORT $tag: $fails failed motions at iteration $iters (gate allows 4)"
            aborted=1
        elif [ "$iters" -ge 4 ] && [ "${cov%%.*}" = "0" ] && [ "${cov:0:3}" = "0.0" ]; then
            say "ABORT $tag: no coverage after $iters iterations (dead run)"
            aborted=1
        elif [ "$(date +%s)" -ge "$DEADLINE" ]; then
            say "ABORT $tag: deadline reached at iteration $iters, handing the machine to the next run"
            aborted=1
        fi
        if [ "$aborted" = 1 ]; then
            kill -9 "$pid" 2>/dev/null          # ladder first, so it cannot retry
            sleep 2
            pkill -9 -f "test_rh_nod[e].py" 2>/dev/null
            break
        fi
    done
    wait "$pid" 2>/dev/null; rc=$?
    kill_stack

    dir=$(find "$RH_DIR/results" -maxdepth 1 -type d \
              -name "run_*_expC_panels3_K${k}_H${h}_box" -newermt "@$before" | sort | tail -1)
    if [ -n "$dir" ]; then
        if [ "$aborted" = 1 ] && [ ! -f "$dir/trial_00/metrics_rh_nbv_panels3.json" ]; then
            rm -rf "$dir"                        # aborted before any metrics landed
            say "END   $tag ABORTED (empty run dir removed)"
        else
            mv "$dir" "$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
            say "END   $tag rc=$rc dir=$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
        fi
    else
        say "END   $tag rc=$rc NO RUN DIR FOUND (aborted=$aborted)"
    fi
}

say "=== NIGHT2 START (clean H=4 with watchdog, then K=20) ==="
run_cfg H4K10c 4 10 1
run_cfg H3K20b 3 20 1
say "=== NIGHT2 COMPLETE ==="
