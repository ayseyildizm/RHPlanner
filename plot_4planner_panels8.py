"""Four planners on the matched panels8 pair (expC, 20 views, 1 trial each).

RH  : results/run_20260816_232310_expC_panels8_K10_H3_box
Grad: results/run_20260817_091838_expC_panels8_GradientNBV
Rand: results/run_20260817_173242_expC_panels8_Random
PSO : results/run_20260817_174807_expC_panels8_PSO

Outputs (figures/ and, if present, the thesis figures folder):
  fourplanner_panels8_curves.{pdf,png}   coverage / F1 / occluded recall / path
  fourplanner_panels8_bars.{pdf,png}     final coverage, F1, AUC, path, moves, time
  fourplanner_panels8_recon.{pdf,png}    final reconstructions side by side

Ray-tracing calls are deliberately left out: the counter is not wired up for
PSO and Random (both report 0), so the numbers are not comparable.
"""

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
RES = os.path.join(HERE, "results")

RUNS = [
    ("RH-NBV (K=10, H=3)", "run_20260816_232310_expC_panels8_K10_H3_box"),
    ("GradientNBV",        "run_20260817_091838_expC_panels8_GradientNBV"),
    ("PSO",                "run_20260817_174807_expC_panels8_PSO"),
    ("Random",             "run_20260817_173242_expC_panels8_Random"),
]

COLORS = ["#26e083", "#d95f02", "#202ADE", "#CD1F1F"]
DASHES = ["solid", (0, (5, 2)), (0, (1, 1.5)), (0, (6, 2, 1, 2))]


def load(folder):
    path = glob.glob(os.path.join(RES, folder, "trial_00", "metrics_*.json"))[0]
    return json.load(open(path))


data = [(label, folder, load(folder)) for label, folder in RUNS]

# ---------------------------------------------------------------- curves
panels = [
    ("coverages", "ROI coverage (%)"),
    ("f1_scores", "F1 score"),
    ("occluded_recall_series", "Occluded-region recall"),
    ("distances", "Path length (m)"),
]

fig, axes = plt.subplots(1, 4, figsize=(16, 3.8))
for ax, (key, ylabel) in zip(axes, panels):
    for label, _, m in data:
        ax.plot(m[key], marker="o", markersize=3, label=label)
    ax.set_xlabel("Viewpoint")
    ax.set_ylabel(ylabel)
    ax.set_xlim(0, 20)
    ax.set_xticks(range(0, 21, 5))
    ax.grid(True, alpha=0.3)
axes[0].legend(fontsize=8)
fig.tight_layout()

# ------------------------------------------------------------------ bars
bars = [
    ("Final ROI coverage (%)", lambda m: m["final_coverage"]),
    ("Final F1", lambda m: m["f1_scores"][-1]),
    ("Coverage AUC", lambda m: m["coverage_auc"]),
    ("Path length (m)", lambda m: m["distances"][-1]),
    ("Move success (%)", lambda m: m["move_success_rate"]),
    ("Planning time (min)", lambda m: m["total_time"] / 60.0),
]

labels = [label for label, _, _ in data]
short = ["RH-NBV", "GradientNBV", "PSO", "Random"]

fig2, axes2 = plt.subplots(2, 3, figsize=(12, 6))
for ax, (title, fn) in zip(axes2.ravel(), bars):
    vals = [fn(m) for _, _, m in data]
    ax.bar(short, vals, color=COLORS)
    ax.set_title(title, fontsize=10)
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=8)
    span = max(vals) if max(vals) else 1.0
    for x, v in enumerate(vals):
        ax.text(x, v + 0.02 * span, f"{v:.2f}" if span < 10 else f"{v:.1f}",
                ha="center", fontsize=8)
    ax.set_ylim(0, span * 1.18)
fig2.suptitle("Final metrics, panels8 (lower is better for path length and time)",
              fontsize=11)
fig2.tight_layout()


# ------------------------------------------------- final reconstructions
def trim(img):
    """Drop the ground-truth half and the surrounding white margin."""
    img = img[:, : img.shape[1] // 2]
    ink = img[..., :3].min(axis=2) < 0.97
    rows, cols = np.where(ink)
    if rows.size == 0:
        return img
    return img[rows.min():rows.max() + 1, cols.min():cols.max() + 1]


fig3, axes3 = plt.subplots(1, 4, figsize=(15, 4.8))
for ax, (label, folder, m) in zip(axes3, data):
    shots = sorted(glob.glob(os.path.join(RES, folder, "trial_00",
                                          "reconstruction_*.png")))
    shots = [p for p in shots if "evolution" not in os.path.basename(p)]
    ax.axis("off")
    if shots:
        ax.imshow(trim(plt.imread(shots[0])))
    ax.set_title(f"{label}\ncoverage {m['final_coverage']:.1f}%, "
                 f"F1 {m['f1_scores'][-1]:.3f}\n"
                 f"occluded recall {m['occluded_recall_series'][-1]:.2f}",
                 fontsize=9)
fig3.suptitle("Reconstructed target voxels after 20 views (panels8)", fontsize=11)
fig3.tight_layout(rect=(0, 0, 1, 0.93))

# ----------------------------------------------------------------- write
for out_dir in (OUT, THESIS):
    if os.path.isdir(out_dir):
        for ext in ("pdf", "png"):
            fig.savefig(os.path.join(out_dir, f"fourplanner_panels8_curves.{ext}"),
                        dpi=300)
            fig2.savefig(os.path.join(out_dir, f"fourplanner_panels8_bars.{ext}"),
                         dpi=300)
            fig3.savefig(os.path.join(out_dir, f"fourplanner_panels8_recon.{ext}"),
                         dpi=300)

hdr = (f"{'planner':<20}{'cov%':>7}{'F1':>8}{'occlR':>8}{'AUC':>7}"
       f"{'path m':>8}{'move%':>7}{'min':>7}{'stag':>6}{'seed':>6}")
print(hdr)
print("-" * len(hdr))
for label, _, m in data:
    seed = m["params"].get("seed")
    print(f"{label:<20}{m['final_coverage']:>7.2f}{m['f1_scores'][-1]:>8.4f}"
          f"{m['occluded_recall_series'][-1]:>8.3f}{m['coverage_auc']:>7.2f}"
          f"{m['distances'][-1]:>8.2f}{m['move_success_rate']:>7.0f}"
          f"{m['total_time'] / 60.0:>7.1f}{m['stagnation_count']:>6}"
          f"{str(seed):>6}")
print("\nwrote fourplanner_panels8_{curves,bars,recon}.{pdf,png}")
