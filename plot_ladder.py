#!/usr/bin/env python3
"""
plot_ladder.py — 4-planner figures for the bunny / mug panel ladder.

Run selection, the validity gate and the trial averaging all come from
analyze_bunny_results, so every point here matches a row of that table.

  summary: final coverage and F1 against occlusion level, one line per planner
  curves:  coverage (or F1) against viewpoint, one panel per scenario

Hollow markers / dashed segments mark cells where no trial passed the gate;
crosses mark cells where calculate_F1 returned early (F1=0 is not a score).

Run:  ~/miniconda3/envs/rh_nbv_ros2/bin/python plot_ladder.py --target bunny
"""
import argparse
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analyze_bunny_results import (OCC_ORDER, PLANNER_ORDER, TARGET_ROOTS,
                                   collect, no_eval, select)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "figures", "ladder")
INK = "#22221f"
GRID = "#d8d6d0"

STYLE = {
    "GradientNBV": dict(color="#eda100", linestyle="--", marker="s"),
    "RH-NBV":      dict(color="#2a78d6", linestyle="-",  marker="o"),
    "PSO":         dict(color="#008300", linestyle="-.", marker="^"),
    "Random":      dict(color="#e87ba4", linestyle=":",  marker="D"),
}
OCC_LABEL = {"none": "none", "panels8": "8 (L)"}
SPLIT = OCC_ORDER.index("panels8")  # L-shape sits off the count axis
TARGET_TITLE = {"bunny": "Stanford bunny", "mug": "Coffee mug"}
PLANNER_ALIAS = {"gradient": "GradientNBV", "gradientnbv": "GradientNBV",
                 "rh": "RH-NBV", "rh-nbv": "RH-NBV", "rhnbv": "RH-NBV",
                 "pso": "PSO", "random": "Random"}
SHORT = {"GradientNBV": "grad", "RH-NBV": "rh", "PSO": "pso", "Random": "rnd"}


def cell(runs, occ, planner, agg):
    """Aggregated series + flags for one (scenario, planner) cell."""
    picked = select(runs, occ, planner, agg)
    if picked is None:
        return None
    _, _, trials, _, gate_ok = picked
    n = min(len(m["coverages"]) for m in trials)
    return {
        "cov": np.array([m["coverages"][:n] for m in trials], dtype=float),
        "f1": np.array([m["f1_scores"][:n] for m in trials], dtype=float),
        "gate_ok": gate_ok,
        "no_eval": all(no_eval(m) for m in trials),
        "n": len(trials),
    }


def style_axes(ax):
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.tick_params(colors=INK, labelsize=9)
    for s in ax.spines.values():
        s.set_color(GRID)


def save(fig, name):
    os.makedirs(OUT_DIR, exist_ok=True)
    for ext in ("png", "pdf"):
        path = os.path.join(OUT_DIR, f"{name}.{ext}")
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print("saved", path)
    plt.close(fig)


PANEL_SPEC = {"cov": ("Final ROI coverage (%)", (0, 100)),
              "f1": ("Final F1 score", (0, 1.02))}


def fig_summary(runs, target, agg, occs, metrics, planners, name):
    """Final value against occlusion stage — the ladder read left to right."""
    fig, axes = plt.subplots(1, len(metrics),
                             figsize=(5.8 * len(metrics), 4.2), squeeze=False)
    axes = axes[0]
    x = np.arange(len(occs))
    # panels8 is an L-shape, not a further rung of the panel count; keep it off
    # the connecting line whenever it is on the axis at all.
    split = occs.index("panels8") if "panels8" in occs else len(occs)

    for ax, which in zip(axes, metrics):
        ylabel, ylim = PANEL_SPEC[which]
        for planner in planners:
            st = STYLE[planner]
            xs, ys, es, open_pts, bail_pts = [], [], [], [], []
            for i, occ in enumerate(occs):
                c = cell(runs, occ, planner, agg)
                if c is None:
                    continue
                finals = c[which][:, -1]
                xs.append(i)
                ys.append(finals.mean())
                es.append(finals.std())
                if not c["gate_ok"]:
                    open_pts.append((i, finals.mean()))
                if which == "f1" and c["no_eval"]:
                    bail_pts.append((i, finals.mean()))
            if not xs:
                continue
            for lo, hi in ((0, split), (split, len(occs))):
                seg = [(a, b, c) for a, b, c in zip(xs, ys, es) if lo <= a < hi]
                if not seg:
                    continue
                sx, sy, se = zip(*seg)
                ax.errorbar(sx, sy, yerr=se, color=st["color"],
                            linestyle=st["linestyle"], linewidth=2,
                            marker=st["marker"], markersize=7, capsize=3,
                            elinewidth=1, zorder=3,
                            label=planner if lo == 0 else None)
            if open_pts:
                ox, oy = zip(*open_pts)
                ax.plot(ox, oy, linestyle="none", marker=st["marker"],
                        markersize=7, markerfacecolor="white",
                        markeredgecolor=st["color"], markeredgewidth=1.6,
                        zorder=4)
            if bail_pts:
                bx, by = zip(*bail_pts)
                ax.plot(bx, by, linestyle="none", marker="x", markersize=9,
                        color=INK, markeredgewidth=1.6, zorder=5)

        if split < len(occs):
            ax.axvline(split - 0.5, color=GRID, linewidth=1.2,
                       linestyle=(0, (4, 3)), zorder=1)
        ax.set_ylim(*ylim)
        ax.set_xlim(-0.35, len(occs) - 0.65)
        ax.set_xticks(x)
        ax.set_xticklabels([OCC_LABEL.get(o, o.replace("panels", "")) for o in occs])
        ax.set_xlabel("Occlusion stage (panels)", color=INK, fontsize=10)
        ax.set_ylabel(ylabel, color=INK, fontsize=10)
        style_axes(ax)

    handles, labels = axes[0].get_legend_handles_labels()
    handles.append(plt.Line2D([], [], linestyle="none", marker="o",
                              markerfacecolor="white", markeredgecolor=INK,
                              markersize=7))
    labels.append("no trial passed the gate")
    if "f1" in metrics:
        handles.append(plt.Line2D([], [], linestyle="none", marker="x",
                                  color=INK, markersize=9))
        labels.append("F1 not evaluated (tp=fp=fn=0)")
    fig.legend(handles, labels, loc="upper center", ncol=len(labels),
               frameon=False, fontsize=9, labelcolor=INK,
               bbox_to_anchor=(0.5, 1.06))
    what = " and ".join(PANEL_SPEC[m][0].replace("Final ", "").split(" (")[0]
                        for m in metrics)
    fig.suptitle(f"{TARGET_TITLE[target]} — {what} across the occlusion stages",
                 color=INK, fontsize=11, y=1.13)
    save(fig, name)


def fig_curves(runs, target, agg, planners, which, name):
    """Per-viewpoint curves, one panel per scenario."""
    ylabel, ylim = (("ROI coverage (%)", (0, 100)) if which == "cov"
                    else ("F1 score", (0, 1.02)))
    fig, axes = plt.subplots(4, 2, figsize=(9.5, 12), sharex=True, sharey=True)

    for idx, occ in enumerate(OCC_ORDER):
        ax = axes[idx // 2][idx % 2]
        for planner in planners:
            c = cell(runs, occ, planner, agg)
            if c is None:
                continue
            st = STYLE[planner]
            series = c[which]
            mean = series.mean(axis=0)
            xs = np.arange(len(mean))
            ax.plot(xs, mean, color=st["color"], linewidth=2,
                    linestyle=st["linestyle"], alpha=1.0 if c["gate_ok"] else 0.45,
                    label=planner, zorder=3)
            ax.plot(xs[-1], mean[-1], marker=st["marker"], markersize=7,
                    color=st["color"], zorder=4,
                    markerfacecolor=st["color"] if c["gate_ok"] else "white",
                    markeredgecolor=st["color"], markeredgewidth=1.6)
            if series.shape[0] > 1:
                sd = series.std(axis=0)
                ax.fill_between(xs, mean - sd, mean + sd, color=st["color"],
                                alpha=0.15, linewidth=0)
        ax.set_title(f"panels {OCC_LABEL.get(occ, occ.replace('panels', ''))}",
                     color=INK, fontsize=10)
        ax.set_ylim(*ylim)
        ax.set_xlim(-0.4, 20.7)
        ax.set_xticks(range(0, 21, 5))
        style_axes(ax)
        if idx % 2 == 0:
            ax.set_ylabel(ylabel, color=INK, fontsize=10)
        if idx // 2 == 3:
            ax.set_xlabel("Viewpoint", color=INK, fontsize=10)

    handles = [plt.Line2D([], [], linewidth=2, color=STYLE[p]["color"],
                          linestyle=STYLE[p]["linestyle"]) for p in planners]
    labels = list(planners)
    handles.append(plt.Line2D([], [], linewidth=2, color=INK, alpha=0.45,
                              marker="o", markersize=7, markerfacecolor="white",
                              markeredgecolor=INK))
    labels.append("no trial passed the gate")
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False,
               fontsize=10, labelcolor=INK, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle(f"{TARGET_TITLE[target]} — {ylabel.split(' (')[0]} per viewpoint",
                 color=INK, fontsize=11, y=1.025)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    save(fig, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=sorted(TARGET_ROOTS), default="bunny")
    ap.add_argument("--fig", choices=("summary", "curves", "both"), default="both")
    ap.add_argument("--metric", choices=("cov", "f1", "both"), default="cov",
                    help="metric shown by both figure types")
    ap.add_argument("--occs", help="comma-separated subset, e.g. none,panels1,panels3")
    ap.add_argument("--planners", help="comma-separated subset, e.g. gradient,rh")
    ap.add_argument("--name", help="output file stem (default derived)")
    ap.add_argument("--agg", choices=("mean", "trial0"), default="mean")
    args = ap.parse_args()

    occs = ([o.strip() for o in args.occs.split(",") if o.strip()]
            if args.occs else list(OCC_ORDER))
    bad = [o for o in occs if o not in OCC_ORDER]
    if bad:
        raise SystemExit(f"unknown scenario(s): {', '.join(bad)}")
    metrics = ("cov", "f1") if args.metric == "both" else (args.metric,)

    if args.planners:
        planners = []
        for raw in args.planners.split(","):
            key = raw.strip().lower()
            if key not in PLANNER_ALIAS:
                raise SystemExit(f"unknown planner: {raw.strip()}")
            planners.append(PLANNER_ALIAS[key])
        planners = [p for p in PLANNER_ORDER if p in planners]
    else:
        planners = list(PLANNER_ORDER)
    psuffix = ("" if len(planners) == len(PLANNER_ORDER)
               else "_" + "".join(SHORT[p] for p in planners))

    runs = collect(TARGET_ROOTS[args.target], args.target)
    if args.fig in ("summary", "both"):
        stem = args.name or (f"ladder_summary_{args.target}{psuffix}"
                             if len(occs) == len(OCC_ORDER)
                             else f"ladder_{'_'.join(metrics)}_{args.target}"
                                  f"_{len(occs)}stage{psuffix}")
        fig_summary(runs, args.target, args.agg, occs, metrics, planners, stem)
    if args.fig in ("curves", "both"):
        for which in metrics:
            stem = f"ladder_curves_{args.target}_{which}{psuffix}"
            fig_curves(runs, args.target, args.agg, planners, which, stem)


if __name__ == "__main__":
    main()
