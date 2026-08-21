#!/bin/bash
# hk_chain3.sh — overnight queue for 2026-07-28/29 (Ayşe: lambda=1 + K sensitivity).
#   1) lambda = 1   (H=3, K=10)  -> completes tab:lambda_ablation (0 / 1 / 2.0)
#   2) K = 5        (H=3, lambda=2.0)
#   3) K = 20       (H=3, lambda=2.0)
# Waits for the running lambda=0 job to exit first (its ladder tears down the
# Gazebo stack itself; overlapping ladders share DDS topics -> corrupt runs).
# Tags are chosen so hk_table.py's globs pick the dirs up (abtest_H*K*_ / abtest_lam*_).
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
CHAIN=$LOGS/hk_ablation_chain2_20260728.log
cd "$RH_DIR" || exit 1
say() { echo "[$(date +%Y-%m-%d_%H:%M:%S)] $*" >> "$CHAIN"; }

run_cfg() {  # $1 tag  $2 H  $3 K  $4 lambda
    local tag=$1 h=$2 k=$3 lam=$4
    local before rc dir new
    before=$(date +%s)
    say "START $tag  H=$h K=$k lambda=$lam trials=1"
    env L4_TARGET=mug L4_OCCS=panels3 L4_PLANNERS=rh L4_TRIALS=1 \
        RH_H="$h" RH_K="$k" RH_LAMBDA="$lam" ./run_ladder4.sh \
        > "$LOGS/hk2_${tag}.log" 2>&1
    rc=$?
    dir=$(find "$RH_DIR/results" -maxdepth 1 -type d \
              -name "run_*_expC_panels3_K${k}_H${h}_box" -newermt "@$before" \
          | sort | tail -1)
    if [ -n "$dir" ]; then
        new="$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
        mv "$dir" "$new"
        say "END   $tag rc=$rc dir=$new"
    else
        say "END   $tag rc=$rc NO RUN DIR FOUND"
    fi
}

# Hold until the lambda=0 job is completely done (script, not just planner).
while pgrep -f "hk_lambda[0].sh" > /dev/null; do sleep 60; done
sleep 30

say "=== CHAIN3 START (lambda=1 -> K=5 -> K=20, all H=3) ==="
run_cfg lam1   3 10 1.0
run_cfg H3K5   3 5  2.0
run_cfg H3K20  3 20 2.0
say "=== CHAIN3 COMPLETE ==="
