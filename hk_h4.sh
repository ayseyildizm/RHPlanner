#!/bin/bash
# hk_h4.sh — H=4 (and optionally H=5) on mug/panels3, K=10, lambda=2.0.
# The ablation so far only covers H in {1,2,3}, so the upper side of the
# default is untested: a longer horizon might do better, and the thesis
# currently cannot say. Same scenario and parameters as the frozen 07-07
# reference run (63.82 % coverage, F1 0.892, 19/20 motions).
# Run dirs are renamed abtest_H4K10_* / abtest_H5K10_* for hk_table.py.
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
CHAIN=$LOGS/hk_ablation_chain2_20260728.log
cd "$RH_DIR" || exit 1
say() { echo "[$(date +%Y-%m-%d_%H:%M:%S)] $*" >> "$CHAIN"; }

run_cfg() {  # $1 tag  $2 H
    local tag=$1 h=$2 before rc dir
    before=$(date +%s)
    say "START $tag  H=$h K=10 lambda=2.0 trials=1"
    env L4_TARGET=mug L4_OCCS=panels3 L4_PLANNERS=rh L4_TRIALS=1 \
        RH_H="$h" RH_K=10 ./run_ladder4.sh > "$LOGS/hk2_${tag}.log" 2>&1
    rc=$?
    dir=$(find "$RH_DIR/results" -maxdepth 1 -type d \
              -name "run_*_expC_panels3_K10_H${h}_box" -newermt "@$before" \
          | sort | tail -1)
    if [ -n "$dir" ]; then
        mv "$dir" "$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
        say "END   $tag rc=$rc dir=$RH_DIR/results/abtest_${tag}_$(basename "$dir")"
    else
        say "END   $tag rc=$rc NO RUN DIR FOUND"
    fi
}

# Wait for anything still running (the IK job tears down its own stack).
while pgrep -f "hk_ikrun.s[h]|run_ladder[4].sh" > /dev/null; do sleep 60; done
sleep 30

run_cfg H4K10 4
run_cfg H5K10 5
say "=== H4/H5 COMPLETE ==="
