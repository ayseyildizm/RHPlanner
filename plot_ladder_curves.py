#!/usr/bin/env python3
# Coverage and F1 across the occlusion ladder, one line per planner.
import glob, json, os, re
from statistics import median
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
# Every planner was run in one July session; a few cells were re-run in
# August on a much slower machine. Keeping one session per planner avoids
# mixing them.
SESSION_END = "20260801"
# Two runs sitting in the bunny root results/ are mug runs: their stored
# reconstruction figures show the 938-point mug mesh as ground truth, not the
# 35,947-point bunny. They were counted in the bunny curve until 2026-08-19.
MISFILED_MUG = {
    "run_20260709_031028_expC_panels4_K10_H3_box",
    "run_20260709_022623_expC_panels2_GradientNBV",
}
NAMES = {"K10_H3_box": "RH-NBV", "GradientNBV": "GradientNBV",
         "PSO": "PSO", "Random": "Random"}
PLANNERS = ["RH-NBV", "GradientNBV", "PSO", "Random"]
COLORS = ["#009E73", "#D55E00", "#0072B2", "#CC79A7"]
MARKERS = ["o", "s", "^", "D"]
STAGES = ["none", "panels1", "panels2", "panels3", "panels4", "panels5", "panels6"]


def collect():
    """{(object, stage, planner): {"coverage": [...], "f1": [...]}}"""
    data = {}
    for obj, roots in ROOTS.items():
        # Desktop/BUNNY and Downloads/BUNNY hold the same run directories, so
        # the same trial is reachable through two roots. Count it once.
        seen = set()
        for root in roots:
            for run in sorted(glob.glob(os.path.join(root, "run_*"))):
                name = os.path.basename(run)
                m = RUN.match(name)
                if not m:
                    continue
                if m.group(1) >= SESSION_END:
                    continue
                if obj == "Stanford bunny" and name in MISFILED_MUG:
                    continue
                key = (obj, m.group(2), NAMES[m.group(3)])
                for f in sorted(glob.glob(os.path.join(run, "trial_*",
                                                       "metrics_*.json"))):
                    tag = (obj, name, os.path.basename(os.path.dirname(f)))
                    if tag in seen:
                        continue
                    seen.add(tag)
                    with open(f) as fh:
                        run_metrics = json.load(fh)
                    entry = data.setdefault(key, {"coverage": [], "f1": []})
                    entry["coverage"].append(run_metrics["final_coverage"])
                    entry["f1"].append(run_metrics["final_f1"] * 100)
    return data


def curve(data, obj, planner, metric):
    """Median per stage; None where that stage was never run.

    At panels6 the object is sealed inside the box and nothing of it can be
    observed, so the stage is reported as zero for every planner. The residual
    values in the stored metrics files come from the lid, which sits partly
    inside the ROI and is counted as observed volume.
    """
    out = []
    for stage in STAGES:
        if stage == "panels6":
            out.append(0.0)
            continue
        values = data.get((obj, stage, planner), {}).get(metric, [])
        out.append(median(values) if values else None)
    return out


def main():
    data = collect()
    fig, axes = plt.subplots(2, 2, figsize=(8, 5.5), sharex=True, sharey=True)

    for row, obj in enumerate(ROOTS):
        for col, (metric, label) in enumerate([("coverage", "ROI coverage (%)"),
                                               ("f1", "$F_1$ (%)")]):
            ax = axes[row][col]
            for planner, color, marker in zip(PLANNERS, COLORS, MARKERS):
                ax.plot(curve(data, obj, planner, metric), color=color,
                        marker=marker, markersize=4, linewidth=1.6,
                        label=planner)
            ax.set_title(obj + " - " + label, fontsize=10)
            ax.set_ylim(0, 100)
            ax.grid(axis="y", alpha=0.3)
            ax.set_ylabel(label, fontsize=9)
            if row == 1:
                ax.set_xticks(range(len(STAGES)))
                ax.set_xticklabels(["none", "1", "2", "3", "4", "5", "6"])
                ax.set_xlabel("Number of occluding panels", fontsize=9)

    axes[0][0].legend(fontsize=9)
    fig.tight_layout()
    out = os.path.join(HERE, "figures_secondary", "ladder_curves.pdf")
    png = out.replace(".pdf", ".png")
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(png, dpi=200, bbox_inches="tight")
    if os.path.isdir(THESIS):
        import shutil
        shutil.copy(out, THESIS)
        shutil.copy(png, THESIS)
    print("wrote", out, "and", png)


if __name__ == "__main__":
    main()
