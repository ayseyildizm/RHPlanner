#!/usr/bin/env python3
# Cumulative camera path length against viewpoint number, one line per planner.
import glob, json, os, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
THESIS = os.path.expanduser("~/Downloads/LaTeX_thesis_template_draft/figures")

ROOTS = {
    "Coffee mug": [os.path.expanduser("~/Desktop/MUG/" + p)
                   for p in ("GradientNBV", "RH", "PSO", "Random")],
    "Stanford bunny": [os.path.join(HERE, "results")]
                      + [os.path.expanduser("~/Desktop/BUNNY/" + p)
                         for p in ("GradientNBV", "RH", "PSO", "Random")]
                      + [os.path.expanduser("~/Downloads/BUNNY/" + p)
                         for p in ("RH", "GradientNBV")],
}
RUN = re.compile(r"run_(\d{8})_\d{6}_expC_(none|panels\d)_"
                 r"(GradientNBV|K10_H3_box|PSO|Random)$")
SESSION_END = "20260801"          # August re-runs are a different session
NAMES = {"K10_H3_box": "RH-NBV", "GradientNBV": "GradientNBV",
         "PSO": "PSO", "Random": "Random"}
PLANNERS = ["RH-NBV", "GradientNBV", "PSO", "Random"]
COLORS = ["#009E73", "#D55E00", "#0072B2", "#CC79A7"]
MARKERS = ["o", "s", "^", "D"]
BUDGET = 20


def collect(field, non_empty_only=False):
    """{(object, planner): [series, ...]} for one metrics field.

    With non_empty_only, a viewpoint is dropped from a run when nothing was
    reconstructed there (tp + fp == 0). Precision is undefined in that case and
    the stored 0 would otherwise be averaged in as if it were a bad score.
    """
    series = {}
    for obj, roots in ROOTS.items():
        for root in roots:
            for run in glob.glob(os.path.join(root, "run_*")):
                m = RUN.match(os.path.basename(run))
                if not m or m.group(1) >= SESSION_END:
                    continue
                for f in glob.glob(os.path.join(run, "trial_*", "metrics_*.json")):
                    with open(f) as fh:
                        run_metrics = json.load(fh)
                    values = run_metrics.get(field)
                    if not values:
                        continue
                    if non_empty_only:
                        tp = run_metrics.get("tp_series", [])
                        fp = run_metrics.get("fp_series", [])
                        values = [v if i < len(tp) and tp[i] + fp[i] > 0 else None
                                  for i, v in enumerate(values)]
                    series.setdefault((obj, NAMES[m.group(3)]), []).append(values)
    return series


def average(runs):
    """Mean at each viewpoint, over the runs that have a value there.

    Returns the viewpoint numbers alongside the means, because a viewpoint can
    be missing for every run (nothing is reconstructed before the first
    measurement, so precision has no value at viewpoint 0).
    """
    xs, ys = [], []
    for i in range(BUDGET + 1):
        values = [r[i] for r in runs if len(r) > i and r[i] is not None]
        if len(values) >= 2:
            xs.append(i)
            ys.append(sum(values) / len(values))
    return xs, ys


def draw(field, ylabel, name, scale=1.0, non_empty_only=False):
    series = collect(field, non_empty_only)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), sharey=True)

    for ax, obj in zip(axes, ROOTS):
        for planner, color, marker in zip(PLANNERS, COLORS, MARKERS):
            runs = series.get((obj, planner), [])
            if not runs:
                continue
            xs, mean = average(runs)
            mean = [v * scale for v in mean]
            ax.plot(xs, mean, color=color, marker=marker,
                    markersize=4, linewidth=1.6,
                    label=f"{planner} (n={len(runs)})")
        ax.set_title(obj, fontsize=10)
        ax.set_xlabel("Viewpoint")
        ax.set_xticks(range(0, BUDGET + 1, 4))
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

    axes[0].set_ylabel(ylabel)
    fig.tight_layout()
    out = os.path.join(HERE, "figures_secondary", name + ".pdf")
    fig.savefig(out, bbox_inches="tight")
    if os.path.isdir(THESIS):
        import shutil
        shutil.copy(out, THESIS)
    print("wrote", out)


def main():
    draw("distances", "Cumulative path length (m)", "trajectory_distance")
    draw("times", "Cumulative computation time (s)", "computation_time")
    draw("precisions", "Precision of reconstructed target voxels (%)",
         "precision_curves", scale=100, non_empty_only=True)
    draw("recalls", "Recall of reconstructed target voxels (%)",
         "recall_curves", scale=100)


if __name__ == "__main__":
    main()
