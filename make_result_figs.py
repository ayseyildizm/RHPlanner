#!/usr/bin/env python3
"""make_result_figs.py — qualitative figures for the results chapter.

Every panel here is an image a run already wrote to its own trial directory;
nothing is re-simulated and no number is recomputed. The script only crops the
per-run title bands, trims the white margins matplotlib leaves around a 3D
axes, and lays the panels out side by side with one shared caption label per
panel, so that two planners can be compared at the same scale on one page.

The runs referenced below are the same ones that supply the numbers in the
tables of the results chapter; the coverage value in each panel label is read
back out of that run's metrics file rather than typed in, so a wrong path
fails loudly instead of mislabelling a figure.

    python3 make_result_figs.py
"""
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HOME = os.path.expanduser("~/Desktop")
THESIS = os.path.join(HOME, "LaTeX_thesis_template1__1_(1)", "figures")
OUT = os.path.expanduser("~/Desktop/RecedingHorizon/figures")


def metric(run_dir, key="final_coverage"):
    """Read one metric out of a run directory, so labels cannot drift."""
    js = glob.glob(os.path.join(run_dir, "metrics_*.json"))
    if not js:
        raise SystemExit(f"no metrics file in {run_dir}")
    return json.load(open(js[0]))[key]


def load(path, cut_top=0.0, half=None):
    """Read a panel image, drop its title band, keep one half, trim margins.

    cut_top removes the per-run title that would otherwise repeat in every
    panel; half='left' keeps the reconstruction panel of a
    reconstruction-vs-ground-truth image and half='right' its ground truth.
    """
    img = plt.imread(path)
    if cut_top:
        img = img[int(cut_top * img.shape[0]):]
    if half == "left":
        img = img[:, : img.shape[1] // 2]
    elif half == "right":
        img = img[:, img.shape[1] // 2:]

    # Trim uniform white border: keep rows/columns that contain any ink.
    grey = img[..., :3].mean(axis=2) if img.ndim == 3 else img
    ink = grey < 0.97
    rows, cols = np.where(ink.any(axis=1))[0], np.where(ink.any(axis=0))[0]
    if len(rows) and len(cols):
        img = img[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    return img


def grid(panels, filename, ncols=None, figwidth=10, panel_h=3.4):
    """Lay panels out in a row (or grid) and write pdf+png."""
    n = len(panels)
    ncols = ncols or n
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(figwidth, panel_h * nrows))
    axes = np.atleast_1d(axes).ravel()

    for ax, (label, img) in zip(axes, panels):
        ax.imshow(img)
        ax.set_title(label, fontsize=9)
        ax.axis("off")
    for ax in axes[n:]:
        ax.axis("off")

    fig.tight_layout()
    os.makedirs(OUT, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{filename}.{ext}"), dpi=200,
                    bbox_inches="tight")
    plt.close(fig)
    if os.path.isdir(THESIS):
        import shutil
        shutil.copy(os.path.join(OUT, f"{filename}.pdf"), THESIS)
    print("wrote", filename)


# --- the runs ---------------------------------------------------------------
# Each entry is the trial directory that supplies the corresponding table row.
MUG_P3_RH = f"{HOME}/MUG/RH/run_20260707_180342_expC_panels3_K10_H3_box/trial_00"
MUG_P3_GR = f"{HOME}/MUG/GradientNBV/run_20260708_180244_expC_panels3_GradientNBV/trial_00"
BUN_P3_RH = f"{HOME}/BUNNY/RH/run_20260705_142853_expC_panels3_K10_H3_box/trial_00"
BUN_P3_GR = f"{HOME}/BUNNY/GradientNBV/run_20260705_113000_expC_panels3_GradientNBV/trial_00"
FRUIT = {
    "RH-NBV": f"{HOME}/PLANT/RH/FRUIT/run_20260711_164843_expC_panels_tree_fruit_y000_K10_H3_box/trial_00",
    "GradientNBV": f"{HOME}/PLANT/GradientNBV/FRUIT/run_20260711_163629_expC_panels_tree_fruit_y000_GradientNBV/trial_00",
    "Random": f"{HOME}/PLANT/Random/FRUIT/run_20260718_123908_expC_panels_tree_fruit_y000_Random/trial_00",
    "PSO": f"{HOME}/PLANT/PSO/FRUIT/run_20260718_125508_expC_panels_tree_fruit_y000_PSO/trial_00",
}
# Whole plant, psi = 180 deg: the orientation behind the low end of RH-NBV's
# spread in the plant table. RH-NBV's valid trial there is trial_01, because
# trial_00 executed only 50 % of its commanded motions.
ALL_RH = f"{HOME}/PLANT/RH/ALL/run_20260712_120102_expC_panels_tree_all_y180_K10_H3_box/trial_01"
ALL_GR = f"{HOME}/PLANT/GradientNBV/ALL/run_20260712_110819_expC_panels_tree_all_y180_GradientNBV/trial_00"
# Horizon ablation, coffee mug at panels3.
ABL = os.path.expanduser("~/Desktop/RecedingHorizon/results")
ABL_H1 = f"{ABL}/abtest_H1K10_run_20260726_233435_expC_panels3_K10_H1_box/trial_00"
ABL_H1K30 = f"{ABL}/abtest_H1K30b_run_20260728_063458_expC_panels3_K30_H1_box/trial_00"

TRAJ_CUT = 0.10   # per-run bold title + legend box
RECON_CUT = 0.04  # main title only; the voxel-count subtitle is kept


def traj(run_dir, pattern="trajectory_3d_*.png"):
    hits = glob.glob(os.path.join(run_dir, pattern))
    if not hits:
        raise SystemExit(f"no trajectory image in {run_dir}")
    return load(hits[0], cut_top=TRAJ_CUT)


def recon(run_dir, half="left"):
    hits = [p for p in glob.glob(os.path.join(run_dir, "reconstruction_*.png"))
            if "evolution" not in os.path.basename(p)]
    if not hits:
        raise SystemExit(f"no reconstruction image in {run_dir}")
    return load(hits[0], cut_top=RECON_CUT, half=half)


def main():
    # 1. Reachability: how many of the commanded viewpoints survive execution.
    # The trajectory plots draw executed poses only, so the number of crosses
    # is the motion-success count, which is the point of the figure.
    def moves(d):
        return int(round(metric(d, "move_success_rate")
                         * metric(d, "total_moves") / 100))
    grid([(f"(a) RH-NBV, {moves(FRUIT['RH-NBV'])}/20 motions executed",
           traj(FRUIT["RH-NBV"])),
          (f"(b) PSO, {moves(FRUIT['PSO'])}/20 motions executed",
           traj(FRUIT["PSO"]))],
         "qual_reach_traj", figwidth=10, panel_h=4.2)

    # 2. The same contrast on the bunny.
    grid([(f"(a) RH-NBV, {metric(BUN_P3_RH):.2f}% coverage", traj(BUN_P3_RH)),
          (f"(b) GradientNBV, {metric(BUN_P3_GR):.2f}% coverage", traj(BUN_P3_GR))],
         "qual_bunny_panels3_traj", figwidth=10, panel_h=4.2)

    # 3. Fruit level: four planners plus the ground truth they are scored on.
    panels = [(f"({c}) {name}, {metric(d):.2f}% coverage", recon(d))
              for (c, (name, d)) in zip("abcd", FRUIT.items())]
    panels.append(("(e) ground truth", recon(FRUIT["RH-NBV"], half="right")))
    grid(panels, "qual_fruit_recon", ncols=5, figwidth=13, panel_h=3.0)

    # 4. Whole plant at psi = 180 deg: the reversal.
    grid([(f"(a) RH-NBV, {metric(ALL_RH):.2f}% coverage", recon(ALL_RH)),
          (f"(b) GradientNBV, {metric(ALL_GR):.2f}% coverage", recon(ALL_GR)),
          ("(c) ground truth", recon(ALL_RH, half="right"))],
         "qual_allplant_recon", ncols=3, figwidth=12, panel_h=3.6)

    # 5. Horizon ablation: what the camera does when the look-ahead is removed.
    grid([(f"(a) $H=3$, $K=10$, {metric(MUG_P3_RH):.2f}% coverage", traj(MUG_P3_RH)),
          (f"(b) $H=1$, $K=10$, {metric(ABL_H1):.2f}% coverage", traj(ABL_H1)),
          (f"(c) $H=1$, $K=30$, {metric(ABL_H1K30):.2f}% coverage", traj(ABL_H1K30))],
         "qual_horizon_traj", ncols=3, figwidth=13, panel_h=3.8)


if __name__ == "__main__":
    main()
