"""RH-NBV vs GradientNBV on the matched bunny/panels1 pair (20 views, seed 42).

Outputs: headtohead_panels1.{pdf,png}
"""

import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
THESIS = os.path.expanduser("~/Downloads/LaTeX_thesis_template_draft/figures")

RUNS = [
    ("RH-NBV (K=10, H=3)", "run_20260817_022810_expC_panels1_K10_H3_box"),
    ("GradientNBV", "run_20260817_055117_expC_panels1_GradientNBV"),
]


def load(run):
    path = glob.glob(os.path.join(HERE, "results", run, "trial_00", "metrics_*.json"))[0]
    return json.load(open(path))


data = [(label, load(run)) for label, run in RUNS]

fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))

panels = [
    ("coverages", "ROI coverage (%)"),
    ("occluded_recall_series", "Occluded-region recall"),
    ("distances", "Path length (m)"),
]

for ax, (key, ylabel) in zip(axes, panels):
    for label, d in data:
        ax.plot(d[key], marker="o", markersize=3, label=label)
    ax.set_xlabel("Viewpoint")
    ax.set_ylabel(ylabel)
    ax.set_xlim(0, 20)
    ax.set_xticks(range(0, 21, 5))
    ax.grid(True, alpha=0.3)

axes[0].legend(fontsize=8)

fig.tight_layout()
for out_dir in (OUT, THESIS):
    if os.path.isdir(out_dir):
        for ext in ("pdf", "png"):
            fig.savefig(os.path.join(out_dir, f"headtohead_panels1.{ext}"), dpi=300)

for label, d in data:
    print(f"{label}: coverage {d['final_coverage']:.2f}, F1 {d['f1_scores'][-1]:.4f}, "
          f"occl recall {d['occluded_recall_series'][-1]:.3f}, "
          f"path {d['distances'][-1]:.2f} m, rays {d['total_ray_calls']}, "
          f"AUC {d['coverage_auc']:.2f}")
print("wrote headtohead_panels1.{pdf,png}")
