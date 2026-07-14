#!/usr/bin/env python3
"""
plot_tree_curves.py — per-view coverage & F1 curves for the tree experiments.

For each stage, plots the mean over valid yaw runs (quality gates inherited
from analyze_tree_results.load_runs) with a +/- std band, RH-NBV vs
GradientNBV — the single-plant counterpart of Burusa et al. (2024) Fig. 13.

Outputs figures/tree/<stage>_curves.png and .pdf.

Run:  ~/miniconda3/envs/rh_nbv_ros2/bin/python plot_tree_curves.py [--stage fruit]
"""
import argparse
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analyze_tree_results import load_runs

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "figures", "tree")

# Categorical slots 1 & 3 of the validated reference palette (blue/amber is
# the most CVD-robust two-hue axis); linestyle adds a color-free encoding.
STYLE = {
    "RH-NBV":      dict(color="#2a78d6", linestyle="-"),
    "GradientNBV": dict(color="#eda100", linestyle="--"),
}
INK = "#3d3d3a"       # text
GRID = "#d9d8d2"      # recessive grid


def curves(m):
    cov = np.asarray(m["coverages"], dtype=float)
    rec = np.asarray(m["recalls"], dtype=float)
    pre = np.asarray(m["precisions"], dtype=float)
    denom = rec + pre
    f1 = np.where(denom > 0, 2 * rec * pre / np.where(denom == 0, 1, denom), 0.0)
    return cov, f1


def stack(yaw_runs, which):
    n = min(len(m["coverages"]) for m in yaw_runs.values())
    rows = []
    for m in yaw_runs.values():
        cov, f1 = curves(m)
        rows.append((cov if which == "cov" else f1)[:n])
    return np.arange(n), np.vstack(rows)


def plot_stage(stage, runs, out_dir):
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6))
    panels = [("cov", "ROI coverage (%)", (0, 100)),
              ("f1", "F1 score", (0, 1.0))]

    for ax, (which, ylabel, ylim) in zip(axes, panels):
        for planner in ("GradientNBV", "RH-NBV"):
            yaw_runs = runs.get((stage, planner), {})
            if not yaw_runs:
                continue
            x, ys = stack(yaw_runs, which)
            mean, std = ys.mean(axis=0), ys.std(axis=0)
            st = STYLE[planner]
            label = f"{planner} (n={len(yaw_runs)})"
            ax.plot(x, mean, linewidth=2, label=label, **st)
            ax.fill_between(x, mean - std, mean + std,
                            color=st["color"], alpha=0.15, linewidth=0)
        ax.set_xlabel("# viewpoints", color=INK)
        ax.set_ylabel(ylabel, color=INK)
        ax.set_ylim(*ylim)
        ax.set_xlim(left=0)
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.grid(True, color=GRID, linewidth=0.6)
        ax.tick_params(colors=INK)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(GRID)
        ax.legend(frameon=False, loc="lower right", fontsize=9,
                  labelcolor=INK)

    fig.suptitle(f"Tree experiment — {stage} level "
                 f"(mean ± std over plant orientations)",
                 color=INK, fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    os.makedirs(out_dir, exist_ok=True)
    for ext in ("png", "pdf"):
        path = os.path.join(out_dir, f"{stage}_curves.{ext}")
        fig.savefig(path, dpi=150)
        print(f"saved {path}")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default=None)
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()

    runs = load_runs()
    stages = sorted({s for s, _ in runs} if not args.stage
                    else {args.stage} & {s for s, _ in runs})
    if not stages:
        raise SystemExit("no matching tree runs found")
    for stage in stages:
        plot_stage(stage, runs, args.out)
