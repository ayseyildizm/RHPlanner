#!/usr/bin/env python3
"""
plot_tree_curves_4p.py — 4-planner per-view curves for the baseline
comparison subsection (tab:tree-baselines companion figure).

3x2 grid: rows = attention levels (fruit/blossom/all), columns = ROI
coverage | F1. Gradient/RH/Random curves come from analyze_tree_results.
load_runs (validity-gated, latest run per yaw); PSO is loaded directly from
its run dirs BYPASSING the 16/20 move gate (no PSO run passes it — the tex
footnote covers this), mirroring the table.

The two-planner figures of the main subsections are left untouched; colors
keep entity identity (RH blue, Gradient amber as published) and PSO/Random
take the remaining leading categorical slots; linestyle is the color-free
secondary encoding.

Outputs figures/tree/baselines_curves.{png,pdf}.

Run:  ~/miniconda3/envs/rh_nbv_ros2/bin/python plot_tree_curves_4p.py
"""
import glob
import json
import os
import re

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analyze_tree_results import load_runs, RESULTS
from plot_tree_curves import curves, INK, GRID, OUT_DIR

STYLE = {
    "GradientNBV": dict(color="#eda100", linestyle="--"),
    "RH-NBV":      dict(color="#2a78d6", linestyle="-"),
    "PSO":         dict(color="#008300", linestyle="-."),
    "Random":      dict(color="#e87ba4", linestyle=":"),
}
PLANNER_ORDER = ("GradientNBV", "RH-NBV", "PSO", "Random")
STAGE_ORDER = ("fruit", "blossom", "all")
STAGE_TITLE = {"fruit": "Fruit level", "blossom": "Blossom level",
               "all": "Whole-plant level"}


def load_pso_ungated():
    """{stage: {yaw: metrics}} for PSO, newest run per yaw, no validity gate."""
    out = {}
    pat = re.compile(r"run_(\d{8}_\d{6})_exp\w_panels_tree_(\w+?)_y(\d{3})_PSO$")
    newest = {}
    for d in sorted(glob.glob(os.path.join(RESULTS, "run_*_panels_tree_*_PSO"))):
        m = pat.search(os.path.basename(d))
        if not m:
            continue
        ts, stage, yaw = m.group(1), m.group(2), int(m.group(3))
        mf = glob.glob(os.path.join(d, "trial_00", "metrics_*.json"))
        if mf:
            newest[(stage, yaw)] = mf[0]  # sorted glob -> last wins = newest
    for (stage, yaw), mf in newest.items():
        with open(mf) as f:
            out.setdefault(stage, {})[yaw] = json.load(f)
    return out


def band(ax, yaw_runs, which, style):
    n = min(len(m["coverages"]) for m in yaw_runs.values())
    rows = []
    for m in yaw_runs.values():
        cov, f1 = curves(m)
        rows.append((cov if which == "cov" else f1)[:n])
    arr = np.vstack(rows)
    x = np.arange(n)
    mean, std = arr.mean(axis=0), arr.std(axis=0)
    ax.plot(x, mean, linewidth=2, **style)
    ax.fill_between(x, mean - std, mean + std, color=style["color"],
                    alpha=0.15, linewidth=0)
    return mean


def main():
    gated = load_runs()
    pso = load_pso_ungated()

    fig, axes = plt.subplots(3, 2, figsize=(9.5, 10.2), sharex=True)
    panels = [("cov", "ROI coverage (%)", (0, 100)), ("f1", "F1 score", (0, 1.0))]

    for row, stage in enumerate(STAGE_ORDER):
        for col, (which, ylabel, ylim) in enumerate(panels):
            ax = axes[row][col]
            for planner in PLANNER_ORDER:
                yaw_runs = (pso.get(stage, {}) if planner == "PSO"
                            else gated.get((stage, planner), {}))
                if not yaw_runs:
                    continue
                band(ax, yaw_runs, which, STYLE[planner])
            ax.set_ylim(*ylim)
            ax.set_xlim(0, 20)
            ax.set_xticks(range(0, 21, 5))
            ax.grid(True, color=GRID, linewidth=0.6)
            ax.tick_params(colors=INK, labelsize=9)
            for s in ax.spines.values():
                s.set_color(GRID)
            if col == 0:
                ax.set_ylabel(f"{STAGE_TITLE[stage]}\n{ylabel}",
                              color=INK, fontsize=10)
            else:
                ax.set_ylabel(ylabel, color=INK, fontsize=10)
            if row == 2:
                ax.set_xlabel("Viewpoint", color=INK, fontsize=10)

    handles = [plt.Line2D([], [], linewidth=2, **STYLE[p]) for p in PLANNER_ORDER]
    fig.legend(handles, PLANNER_ORDER, loc="upper center", ncol=4,
               frameon=False, fontsize=10, labelcolor=INK,
               bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.965))

    os.makedirs(OUT_DIR, exist_ok=True)
    for ext in ("png", "pdf"):
        path = os.path.join(OUT_DIR, f"baselines_curves.{ext}")
        fig.savefig(path, dpi=150)
        print("saved", path)


if __name__ == "__main__":
    main()
