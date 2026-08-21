#!/usr/bin/env python3
"""hk_plot.py — coverage / F1 vs. viewpoint for the H ablation (mug, panels3).

Draws one curve per horizon setting (mean over valid trials, shaded min-max
band when a configuration has more than one trial).  Output:
    figures/hk/horizon_curves.{png,pdf}

New file; reads the same run dirs as hk_table.py.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from hk_table import collect, trials, BASELINE_07, RESULTS  # noqa: E402
import glob
import json

OUT = os.path.expanduser("~/Desktop/RecedingHorizon/figures/hk")
COLORS = {1: "#d95f02", 2: "#7570b3", 3: "#1b9e77"}


def series_by_config():
    """{(H, K): [(coverages, f1_scores), ...]} over valid trials only."""
    valid = {(r["run"], r["trial"]): r for r in collect() if r["valid"]}
    out = {}
    runs = [BASELINE_07] + sorted(glob.glob(os.path.join(RESULTS, "abtest_H*K*_run_*panels3*")))
    for path in runs:
        if not os.path.isdir(path):
            continue
        for tname, d in trials(path):
            key = (os.path.basename(path), tname)
            if key not in valid:
                continue
            cfg = (d["params"]["horizon"], d["params"]["num_candidates"])
            out.setdefault(cfg, []).append((d["coverages"], d["f1_scores"]))
    return out


def band(ax, curves, color, label, ls="solid"):
    n = min(len(c) for c in curves)
    xs = range(n)
    mean = [sum(c[i] for c in curves) / len(curves) for i in xs]
    ax.plot(xs, mean, color=color, lw=2, linestyle=ls, label=label)
    if len(curves) > 1:
        lo = [min(c[i] for c in curves) for i in xs]
        hi = [max(c[i] for c in curves) for i in xs]
        ax.fill_between(xs, lo, hi, color=color, alpha=0.18, linewidth=0)


def main():
    data = series_by_config()
    if not data:
        print("no valid runs yet")
        return
    os.makedirs(OUT, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    # Colour encodes the horizon, dash pattern the candidate count, so the
    # two knobs stay visually separable when both are varied.
    styles = {5: (0, (4, 2)), 10: "solid", 20: (0, (1, 1.5)), 30: (0, (6, 2, 1, 2))}
    for (h, k), curves in sorted(data.items()):
        lbl = f"$H={h}$, $K={k}$"
        color = COLORS.get(h, "#666666")
        ls = styles.get(k, "solid")
        band(axes[0], [c[0] for c in curves], color, lbl, ls)
        band(axes[1], [c[1] for c in curves], color, lbl, ls)
    axes[0].set_ylabel("ROI coverage [%]")
    axes[1].set_ylabel("F1")
    for ax in axes:
        ax.set_xlabel("viewpoint")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("RH-NBV Planning — coffee mug experiment with panels3")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"horizon_curves.{ext}"), dpi=200)
    print("wrote", os.path.join(OUT, "horizon_curves.png"))


if __name__ == "__main__":
    main()
