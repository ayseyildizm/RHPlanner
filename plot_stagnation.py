"""Stagnation figures for the mug and bunny occlusion ladders.

The stagnation column was pulled out of tab:planner_comparison_mug and is drawn
here instead: how many of the 20 commanded viewpoints produced no ROI-coverage
gain, per planner, as the panel ladder gets harder.

Counts are read straight from each run's metrics JSON (`stagnation_count`), not
transcribed from the thesis tables, so both objects come from one source. Where
that differs from Table 5.2 see NOTE below.

Outputs: stagnation_mug, stagnation_bunny, stagnation_ladder (both objects).
"""

import glob
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
THESIS = os.path.expanduser("~/Downloads/LaTeX_thesis_template_draft/figures")

OBJECTS = {
    "Coffee mug": os.path.expanduser("~/Desktop/MUG"),
    "Stanford bunny": os.path.expanduser("~/Desktop/BUNNY"),
}

BUDGET = 20  # viewpoints per run

STAGES = ["none", "panels1", "panels2", "panels3",
          "panels4", "panels5", "panels6", "panels8"]
STAGE_LABELS = [s if s != "panels8" else "panels8\n(L-shape)" for s in STAGES]

# folder name -> label, in the fixed order the bars are drawn in
PLANNERS = [
    ("RH", "RH-NBV ($K{=}10$, $H{=}3$)"),
    ("GradientNBV", "GradientNBV"),
    ("PSO", "PSO"),
    ("Random", "Random"),
]

# Aborted duplicate: the mug panels2 Random stage was run twice and the first
# attempt died at iteration 0 (coverage 0.00, stagnation 20). The thesis reports
# the second one, so the dead run is skipped here too.
SKIP_RUNS = {"run_20260722_032241_expC_panels2_Random"}

# NOTE: Table 5.2 dashes four mug cells that do have a logged run behind them
# (Random panels3 and panels8, RH-NBV panels8). They are drawn here. Setting
# this to True blanks them again, so the figure matches the printed table.
FAITHFUL_TO_TABLE = False
TABLE_DASHES = {("Coffee mug", "RH", "panels8"),
                ("Coffee mug", "Random", "panels3"),
                ("Coffee mug", "Random", "panels8")}

# Okabe-Ito, fixed order: one hue per planner, never recycled.
COLORS = ["#0072B2", "#D55E00", "#009E73", "#666666"]

INK = "#1a1a1a"
MUTED = "#6e6e6e"


def stagnation_counts(root, obj):
    """{planner: [(count, status) per stage]} for one object's run tree.

    status is 'ok', 'missing' (no run logged), 'nomotion' (a run exists but the
    arm never moved) or 'nodetect' (the arm moved and the target was never
    seen). The last two are 20/20 by construction: stagnation only measures
    stalled progress once there is progress to stall, and a run that never
    detects the target is already reported by its zero coverage.
    """
    out = {}
    for planner, _ in PLANNERS:
        per_stage = {s: (None, "missing") for s in STAGES}
        for run in sorted(glob.glob(os.path.join(root, planner, "run_*"))):
            name = os.path.basename(run)
            if name in SKIP_RUNS:
                continue
            stage = re.search(r"expC_(\w+?)_(?:K10|GradientNBV|PSO|Random)", name)
            if stage is None or stage.group(1) not in per_stage:
                continue
            metrics = glob.glob(os.path.join(run, "trial_00", "metrics_*.json"))
            if not metrics:
                continue
            d = json.load(open(metrics[0]))
            # A run whose executed path is zero metres never left the start
            # pose: every viewpoint is trivially stagnant and the count is an
            # artefact of the run, not a property of the planner.
            if d["distances"][-1] == 0:
                status = "nomotion"
            elif max(d["coverages"]) == 0:
                status = "nodetect"
            else:
                status = "ok"
            if per_stage[stage.group(1)][1] == "ok" and status != "ok":
                continue  # keep the run that actually moved
            per_stage[stage.group(1)] = (d["stagnation_count"], status)
        if FAITHFUL_TO_TABLE:
            for _, p, s in (k for k in TABLE_DASHES if k[0] == obj and k[1] == planner):
                per_stage[s] = (None, "missing")
        out[planner] = [per_stage[s] for s in STAGES]
    return out


def draw(ax, counts, panel_title, xlabels=True):
    n = len(PLANNERS)
    x = np.arange(len(STAGES))
    width = 0.78 / n

    for i, (planner, label) in enumerate(PLANNERS):
        pos = x + (i - (n - 1) / 2) * width
        values = counts[planner]
        # a zero-gain run gets a visible stub, so an empty slot never reads as
        # a missing run (those are labelled n/a instead)
        heights = [0 if s != "ok" else max(v, 0.12) for v, s in values]
        ax.bar(pos, heights, width * 0.92, label=label, color=COLORS[i],
               edgecolor="white", linewidth=0.6, zorder=3)
        for xi, (v, status) in zip(pos, values):
            if status == "ok":
                ax.text(xi, v + 0.35, str(v), ha="center", va="bottom",
                        fontsize=5.8, color=MUTED, zorder=4)
            else:
                note = {"missing": "n/a", "nomotion": "no motion",
                        "nodetect": "never detected"}[status]
                ax.text(xi, 0.35, note, ha="center", va="bottom",
                        fontsize=5.5, color=MUTED, rotation=90, zorder=4)

    ax.axhline(BUDGET, color=MUTED, linestyle=(0, (4, 3)), linewidth=0.9, zorder=2)
    ax.text(-0.52, BUDGET - 0.55, "whole 20-view budget stagnant",
            ha="left", va="top", fontsize=6.5, color=MUTED)
    ax.text(-0.52, BUDGET + 0.9, panel_title, ha="left", va="bottom",
            fontsize=8.5, color=INK, style="italic")

    ax.set_ylim(0, BUDGET + 0.5)
    ax.set_xlim(-0.6, len(STAGES) - 0.4)
    ax.set_xticks(x)
    ax.set_xticklabels(STAGE_LABELS if xlabels else [""] * len(STAGES),
                       fontsize=8, color=INK)
    ax.set_ylabel("Stagnant viewpoints (of 20)", fontsize=8.5, color=INK)
    if xlabels:
        ax.set_xlabel("Occlusion stage", fontsize=8.5, color=INK, labelpad=2)
    ax.tick_params(axis="y", labelsize=7.5, colors=INK, length=0)
    ax.tick_params(axis="x", length=0)

    ax.set_yticks(range(0, BUDGET + 1, 5))
    ax.yaxis.grid(True, color="#dcdcdc", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#bbbbbb")
    for xi in x[:-1]:
        ax.axvline(xi + 0.5, color="#eeeeee", linewidth=0.8, zorder=1)


def save(fig, filename):
    for out_dir in (OUT, THESIS):
        if os.path.isdir(out_dir):
            for ext in ("pdf", "png"):
                fig.savefig(os.path.join(out_dir, f"{filename}.{ext}"), dpi=300)
    plt.close(fig)


def single(obj, counts, filename):
    fig, ax = plt.subplots(figsize=(9, 3.7))
    draw(ax, counts, obj)
    ax.legend(ncol=4, frameon=False, fontsize=7.5, loc="upper center",
              bbox_to_anchor=(0.5, 1.20), handlelength=1.2, columnspacing=1.6,
              labelcolor=INK)
    fig.tight_layout()
    save(fig, filename)


def both(all_counts, filename="stagnation_ladder"):
    fig, axes = plt.subplots(2, 1, figsize=(9, 6.4), sharex=True)
    for ax, (obj, counts) in zip(axes, all_counts.items()):
        draw(ax, counts, obj, xlabels=(ax is axes[-1]))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=4, frameon=False, fontsize=8,
               loc="upper center", bbox_to_anchor=(0.5, 1.0),
               handlelength=1.2, columnspacing=1.8, labelcolor=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.subplots_adjust(hspace=0.30)
    save(fig, filename)


if __name__ == "__main__":
    all_counts = {}
    for obj, root in OBJECTS.items():
        all_counts[obj] = stagnation_counts(root, obj)
    single("Coffee mug", all_counts["Coffee mug"], "stagnation_mug")
    single("Stanford bunny", all_counts["Stanford bunny"], "stagnation_bunny")
    both(all_counts)
    for obj, counts in all_counts.items():
        print(obj)
        for planner, _ in PLANNERS:
            print(f"  {planner:12s} " + " ".join(
                f"{s}={v if st == 'ok' else st}"
                for s, (v, st) in zip(STAGES, counts[planner])))
    print("wrote stagnation_{mug,bunny,ladder}.{pdf,png}")
