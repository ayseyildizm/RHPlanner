#!/usr/bin/env python3
"""
analyze_tree_results.py — aggregate tree-ladder results across yaws.

For each (stage, planner) pair, takes the LATEST run per yaw, computes
per-run summary metrics, and prints mean ± std over the yaws — the tree
counterpart of Burusa's 12-orientation averages.

Usage:
    python3 analyze_tree_results.py                 # all stages found
    python3 analyze_tree_results.py --stage fruit
"""
import argparse
import glob
import json
import os
import re
from collections import defaultdict

import numpy as np

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
RUN_RE = re.compile(
    r"run_(\d{8}_\d{6})_exp\w_panels_tree_(\w+?)_y(\d{3})_(GradientNBV|K10_H3_box)$")
PLANNER_NAME = {"GradientNBV": "GradientNBV", "K10_H3_box": "RH-NBV"}


def views_to(cov, tau):
    for i, c in enumerate(cov):
        if c >= tau:
            return i
    return None


def _run_valid(m, stage, planner, yaw, ts):
    """Data-quality gates. A run that fails one measures the stack, not the
    planner (arm_control wedge / camera-bridge lag of 2026-07-11)."""
    ms = m.get("move_successes")
    if ms and sum(ms) / len(ms) < 0.8:
        print(f"  !! skip {stage}/{planner}/y{yaw:03d} ({ts}): only "
              f"{sum(ms)}/{len(ms)} arm moves succeeded")
        return False
    if len(m.get("coverages", [])) > 1 and m["coverages"][1] == 0:
        print(f"  !! skip {stage}/{planner}/y{yaw:03d} ({ts}): no camera data "
              f"at view 1 (degraded start)")
        return False
    return True


def load_runs():
    """{(stage, planner): {yaw: metrics}} — newest VALID run wins per
    (stage,yaw,planner); an invalid newer run falls back to an older valid one."""
    candidates = defaultdict(list)
    for d in sorted(glob.glob(os.path.join(RESULTS, "run_*_panels_tree_*"))):
        m = RUN_RE.search(os.path.basename(d))
        if not m:
            continue
        ts, stage, yaw, planner = m.groups()
        mf = glob.glob(os.path.join(d, "trial_00", "metrics_*.json"))
        if not mf:
            continue
        candidates[(stage, PLANNER_NAME[planner], int(yaw))].append((ts, mf[0]))

    out = defaultdict(dict)
    for (stage, planner, yaw), runs in candidates.items():
        for ts, path in sorted(runs, reverse=True):  # newest first
            with open(path) as f:
                m = json.load(f)
            if _run_valid(m, stage, planner, yaw, ts):
                out[(stage, planner)][yaw] = m
                break
        else:
            print(f"  !! NO VALID RUN for {stage}/{planner}/y{yaw:03d} — needs rerun")
    return out


def summarize_run(m):
    cov = m["coverages"]
    rec, pre = m["recalls"], m["precisions"]
    f1 = [2 * p * r / (p + r) if p + r > 0 else 0 for p, r in zip(pre, rec)]
    return {
        "final_cov": cov[-1],
        "final_f1": f1[-1],
        "final_recall": rec[-1],
        "f1@3": f1[3] if len(f1) > 3 else float("nan"),
        "views80": views_to(cov, 80),
        "views90": views_to(cov, 90),
        "cov_auc": m.get("coverage_auc", float("nan")),
        "dist_m": m.get("final_distance", float("nan")),
    }


def fmt(vals, nd=1):
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and np.isnan(v))]
    if not vals:
        return "n/a"
    a = np.array(vals, dtype=float)
    return f"{a.mean():.{nd}f} ± {a.std():.{nd}f}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default=None)
    args = ap.parse_args()

    runs = load_runs()
    stages = sorted({s for s, _ in runs} if not args.stage
                    else {args.stage} & {s for s, _ in runs})
    if not stages:
        raise SystemExit("no matching tree runs found")

    cols = [("final_cov", "Final coverage %", 1), ("final_f1", "Final F1", 3),
            ("final_recall", "Final recall", 3), ("f1@3", "F1 @3 views", 3),
            ("views80", "#views to 80% cov", 1), ("views90", "#views to 90% cov", 1),
            ("cov_auc", "Coverage AUC", 1), ("dist_m", "Trajectory (m)", 2)]

    for stage in stages:
        print(f"\n=== STAGE: {stage} ===")
        for planner in ("GradientNBV", "RH-NBV"):
            yaw_runs = runs.get((stage, planner), {})
            if not yaw_runs:
                print(f"  {planner}: no runs")
                continue
            summaries = {y: summarize_run(m) for y, m in sorted(yaw_runs.items())}
            print(f"  {planner}  (yaws: {sorted(summaries)})")
            for key, label, nd in cols:
                per_yaw = [summaries[y][key] for y in sorted(summaries)]
                shown = ", ".join("None" if v is None else f"{v:.{nd}f}" for v in per_yaw)
                print(f"    {label:<20} mean {fmt(per_yaw, nd):<14} | per-yaw: {shown}")
