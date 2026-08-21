#!/bin/bash
# hk_chain2.sh — H/K ablation, part 2 (2026-07-28).
# Queue agreed with Ayşe:
#   1) H=1 K=30 rerun  (the 2026-07-27 equal-compute control was invalid:
#      the arm service wedged at iter 12, moves 12-20 all failed)
#   2) baseline H=3 K=10, 3 trials   (trial 0 = fixed start = repeatability
#      check vs the 07-07 baseline; trials 1-2 = randomized starts)
#   3) H=1 K=10, 3 trials
# Each finished run dir is renamed abtest_<tag>_* so the mug table generator
# keeps picking the frozen 07-07 baseline.
# NEW file; run_ladder4.sh untouched.
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
CHAIN=$LOGS/hk_ablation_chain2_20260728.log
mkdir -p "$LOGS"
cd "$RH_DIR" || exit 1

say() { echo "[$(date +%Y-%m-%d_%H:%M:%S)] $*" >> "$CHAIN"; }

run_cfg() {  # $1 tag  $2 H  $3 K  $4 trials
    local tag=$1 h=$2 k=$3 tr=$4
    local before rc dir new
    before=$(date +%s)
    say "START $tag  H=$h K=$k trials=$tr"
    env L4_TARGET=mug L4_OCCS=panels3 L4_PLANNERS=rh L4_TRIALS="$tr" \
        RH_H="$h" RH_K="$k" ./run_ladder4.sh > "$LOGS/hk2_${tag}.log" 2>&1
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

say "=== CHAIN2 START (H1K30 rerun -> H3K10 x3 -> H1K10 x3) ==="
run_cfg H1K30b   1 30 1
run_cfg H3K10x3  3 10 3
run_cfg H1K10x3  1 10 3
say "=== CHAIN2 COMPLETE ==="
