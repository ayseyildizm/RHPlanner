#!/bin/bash
# hk_lambda0.sh — single lambda=0 run (mug, panels3, RH, H=3 K=10) to close
# the H3 motion-cost hypothesis, which is currently "Open" in results.tex.
# Compared against the frozen 2026-07-07 baseline (lambda=2.0: 3.46 m,
# 63.82 % coverage, F1 0.892, 4403 s).
# Run dir is renamed abtest_lam0_* so the mug table generator ignores it.
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
CHAIN=$LOGS/hk_ablation_chain2_20260728.log
cd "$RH_DIR" || exit 1
say() { echo "[$(date +%Y-%m-%d_%H:%M:%S)] $*" >> "$CHAIN"; }

before=$(date +%s)
say "START lam0  H=3 K=10 lambda=0 trials=1"
env L4_TARGET=mug L4_OCCS=panels3 L4_PLANNERS=rh L4_TRIALS=1 \
    RH_H=3 RH_K=10 RH_LAMBDA=0 ./run_ladder4.sh > "$LOGS/hk2_lam0.log" 2>&1
rc=$?
dir=$(find "$RH_DIR/results" -maxdepth 1 -type d \
          -name "run_*_expC_panels3_K10_H3_box" -newermt "@$before" | sort | tail -1)
if [ -n "$dir" ]; then
    mv "$dir" "$RH_DIR/results/abtest_lam0_$(basename "$dir")"
    say "END   lam0 rc=$rc dir=$RH_DIR/results/abtest_lam0_$(basename "$dir")"
else
    say "END   lam0 rc=$rc NO RUN DIR FOUND"
fi
