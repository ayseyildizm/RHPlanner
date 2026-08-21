"""RH-NBV vs GradientNBV on the matched bunny/panels8 pair (20 views, seed 42).

RH run  : results/run_20260816_232310_expC_panels8_K10_H3_box
Grad run: ~/Desktop/BUNNY/GradientNBV/run_20260721_142529_expC_panels8_GradientNBV
          (override with --grad; --tag renames the output files)

Outputs: headtohead_panels8[<tag>].{pdf,png},
         headtohead_panels8[<tag>]_recon.{pdf,png}
"""

import argparse
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
THESIS = os.path.expanduser("~/Downloads/LaTeX_thesis_template_draft/figures")

DEFAULT_RH = os.path.join(HERE, "results", "run_20260816_232310_expC_panels8_K10_H3_box")
DEFAULT_GRAD = os.path.expanduser("~/Desktop/BUNNY/GradientNBV/"
                                  "run_20260721_142529_expC_panels8_GradientNBV")

ap = argparse.ArgumentParser()
ap.add_argument("--rh", default=DEFAULT_RH)
ap.add_argument("--grad", default=DEFAULT_GRAD)
ap.add_argument("--tag", default="", help="suffix appended to the output file names")
args = ap.parse_args()

BASE = f"headtohead_panels8{args.tag}"

RUNS = [
    ("RH-NBV (K=10, H=3)", args.rh),
    ("GradientNBV", args.grad),
]


def load(run_dir):
    path = glob.glob(os.path.join(run_dir, "trial_00", "metrics_*.json"))[0]
    return json.load(open(path))


data = [(label, load(run)) for label, run in RUNS]

# ---------------------------------------------------------------- curves
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


# ------------------------------------------------- final reconstructions
def trim(img):
    """Drop the ground-truth half and the surrounding white margin."""
    img = img[:, : img.shape[1] // 2]
    ink = img[..., :3].min(axis=2) < 0.97
    rows, cols = np.where(ink)
    if rows.size == 0:
        return img
    return img[rows.min():rows.max() + 1, cols.min():cols.max() + 1]


fig2, axes2 = plt.subplots(1, 2, figsize=(9, 4.2))
for ax, (label, run_dir) in zip(axes2, RUNS):
    shots = sorted(glob.glob(os.path.join(run_dir, "trial_00", "reconstruction_*.png")))
    shots = [p for p in shots if "evolution" not in os.path.basename(p)]
    ax.axis("off")
    if shots:
        ax.imshow(trim(plt.imread(shots[0])))
    d = dict(data)[label]
    ax.set_title(f"{label}\ncoverage {d['final_coverage']:.1f}%, "
                 f"F1 {d['f1_scores'][-1]:.3f}, "
                 f"occluded recall {d['occluded_recall_series'][-1]:.2f}", fontsize=9)
fig2.suptitle("Reconstructed target voxels after 20 views (panels8; "
              "ground truth: 35,947 points)", fontsize=10)
fig2.tight_layout()

# ----------------------------------------------------------------- write
for out_dir in (OUT, THESIS):
    if os.path.isdir(out_dir):
        for ext in ("pdf", "png"):
            fig.savefig(os.path.join(out_dir, f"{BASE}.{ext}"), dpi=300)
            fig2.savefig(os.path.join(out_dir, f"{BASE}_recon.{ext}"), dpi=300)

for label, d in data:
    print(f"{label}: coverage {d['final_coverage']:.2f}, F1 {d['f1_scores'][-1]:.4f}, "
          f"occl recall {d['occluded_recall_series'][-1]:.3f}, "
          f"path {d['distances'][-1]:.2f} m, rays {d['total_ray_calls']}, "
          f"time {d['total_time'] / 60.0:.1f} min, AUC {d['coverage_auc']:.2f}, "
          f"moves ok {d['move_success_rate']:.0f}%, "
          f"views to F1 thr {d['views_to_f1_threshold']}")
print(f"wrote {BASE}{{,_recon}}.{{pdf,png}}")
