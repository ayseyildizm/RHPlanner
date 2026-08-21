#!/usr/bin/env python3
"""test_rh_lamprobe_node.py — measure how large lambda would have to be.

The RH-NBV objective scores a candidate sequence as

    J(lambda) = sum_k gamma^k * gain_k  -  lambda * sum_k gamma^k * cost_k
              = G                       -  lambda * C

so for two candidates i and j the planner's choice flips at

    lambda* = (G_i - G_j) / (C_i - C_j)

whenever that value is positive. The lambda ablation of the thesis found no
effect for lambda <= 2, and the per-viewpoint traces showed the penalty never
changing which candidate won. This probe measures the quantity that explains
why: it records G and C for every candidate at every planning iteration, from
which the smallest lambda that would change the winner can be computed directly
instead of guessed.

G and C are recovered exactly, without duplicating the scoring code, by calling
the planner's own evaluate_sequence twice with lambda set to 0 and to 1:

    J(0) = G,   J(1) = G - C   ->   C = J(0) - J(1)

evaluate_sequence is side-effect free (it clones the voxel grid and the start
position), so the extra call cannot disturb the run. The value returned to the
planner is recomputed with the run's real lambda, so the trajectory this probe
produces is identical to an unpatched run with the same seed.

Nothing in the planner or the existing nodes is modified: this file patches the
method in memory and then executes test_rh_node.py as it stands.

Usage (from the repo root, with the Gz stack already up):

    NUM_ITERS=5 RH_LAMBDA=2.0 OCC=panels3 TARGET=mug \
        python3 src/viewpoint_planning/src/test_rh_lamprobe_node.py

Writes results/_lamprobe/lamprobe_<timestamp>.json.
"""
import datetime
import json
import os
import runpy
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from viewpoint_planners.rh_planner import RHPlanner  # noqa: E402

OUT_DIR = os.path.expanduser("~/Desktop/RecedingHorizon/results/_lamprobe")

# One list of (G, C) pairs per planning iteration.
ITERATIONS = []

_orig_evaluate = RHPlanner.evaluate_sequence
_orig_rh_view = RHPlanner.rh_view


def _evaluate_and_record(self, sequence, start_pos):
    lam = self.lambda_cost
    try:
        self.lambda_cost = 0.0
        gain = float(_orig_evaluate(self, sequence, start_pos))
        self.lambda_cost = 1.0
        gain_minus_cost = float(_orig_evaluate(self, sequence, start_pos))
    finally:
        self.lambda_cost = lam
    cost = gain - gain_minus_cost
    if ITERATIONS:
        ITERATIONS[-1].append((gain, cost))
    return gain - lam * cost


def _rh_view_new_iteration(self, *args, **kwargs):
    ITERATIONS.append([])
    try:
        return _orig_rh_view(self, *args, **kwargs)
    finally:
        _dump()          # one file per process, rewritten after every iteration


_STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _dump():
    """Write the probe to disk, with the flip lambda already computed."""
    if not ITERATIONS:
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"lamprobe_{_STAMP}.json")
    json.dump({
        "lambda_used": float(os.environ.get("RH_LAMBDA", 2.0)),
        "occlusion": os.environ.get("OCC", "?"),
        "target": os.environ.get("TARGET", "?"),
        "iterations": [
            [{"gain": g, "cost": c} for g, c in it] for it in ITERATIONS
        ],
    }, open(path, "w"), indent=1)
    print(f"[lamprobe] wrote {path} ({len(ITERATIONS)} iterations)")


RHPlanner.evaluate_sequence = _evaluate_and_record
RHPlanner.rh_view = _rh_view_new_iteration

if __name__ == "__main__":
    try:
        runpy.run_path(os.path.join(_HERE, "test_rh_node.py"),
                       run_name="__main__")
    finally:
        _dump()
