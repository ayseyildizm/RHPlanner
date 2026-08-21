#!/usr/bin/env python3
"""plot_lambda.py — motion-cost weight figure for the ablation section.

Regenerates figures/lambda_curves.{pdf,png} from the three lambda runs of the
2026-07-28 batch only. Left panel is ROI coverage, right panel is the
cumulative executed camera path, which is what the lambda term is supposed to
act on; F1 is flat near 0.15 for all three runs and carries no information
here. Nothing in plots.py is modified: this file imports its loader and its
line styles and writes the same file name.

    python3 plot_lambda.py
"""
import os
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from plots import COLORS, DASHES, OUT, THESIS, load

# All three collected in the same batch, same seed, H=3, K=10; only lambda
# differs. The lambda = 2.0 run is the reference of the comparison.
RUNS = [
    (r"$\lambda = 2.0$ (default)",
     "abtest_H3K10rep_run_20260728_091340_expC_panels3_K10_H3_box"),
    (r"$\lambda = 1$",
     "abtest_lam1_run_20260728_193351_expC_panels3_K10_H3_box"),
    (r"$\lambda = 0$ (no penalty)",
     "abtest_lam0_run_20260728_151336_expC_panels3_K10_H3_box"),
]


# IK-filter figure: the filtered run against the unfiltered run of the same
# batch, which is the lambda = 2.0 run above. Two curves only.
IK_RUNS = [
    ("clamp (unfiltered)",
     "abtest_H3K10rep_run_20260728_091340_expC_panels3_K10_H3_box"),
    ("IK-filtered",
     "abtest_ikfilter_run_20260729_111003_expC_panels3_K10_H3_box"),
]


def ik_filter():
    """Coverage and F1 for the IK-filter ablation."""
    fig, (ax_cov, ax_f1) = plt.subplots(1, 2, figsize=(10, 4))

    for i, (label, folder) in enumerate(IK_RUNS):
        m = load(folder)
        views = range(len(m["coverages"]))
        ax_cov.plot(views, m["coverages"], label=label,
                    color=COLORS[i], linestyle=DASHES[i], linewidth=2)
        ax_f1.plot(views, m["f1_scores"], label=label,
                   color=COLORS[i], linestyle=DASHES[i], linewidth=2)

    ax_cov.set_ylabel("ROI coverage [%]")
    ax_f1.set_ylabel("F1")
    for ax in (ax_cov, ax_f1):
        ax.set_xlabel("viewpoint")
        ax.set_xticks(range(0, 21, 2))
        ax.grid(alpha=0.3)

    handles, labels = ax_cov.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(labels),
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("(RH-NBV) Reachability-filtered sampling "
                 "(coffee mug & panels3)")
    fig.tight_layout(rect=[0, 0.06, 1, 1])

    os.makedirs(OUT, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"ik_filter_curves.{ext}"), dpi=200)
    plt.close(fig)
    if os.path.isdir(THESIS):
        shutil.copy(os.path.join(OUT, "ik_filter_curves.pdf"), THESIS)
    print("wrote ik_filter_curves")


def main():
    fig, (ax_cov, ax_path) = plt.subplots(1, 2, figsize=(10, 4))

    for i, (label, folder) in enumerate(RUNS):
        m = load(folder)
        views = range(len(m["coverages"]))
        ax_cov.plot(views, m["coverages"], label=label,
                    color=COLORS[i], linestyle=DASHES[i], linewidth=2)
        ax_path.plot(views, m["distances"], label=label,
                     color=COLORS[i], linestyle=DASHES[i], linewidth=2)
        # A flat segment is a failed motion: the camera did not move, so the
        # cumulative path is unchanged between two consecutive views.
        failed = [v for v, ok in enumerate(m["move_successes"], start=1) if not ok]
        ax_path.plot(failed, [m["distances"][v] for v in failed], "x",
                     color=COLORS[i], markersize=5, linestyle="none")

    ax_cov.set_ylabel("ROI coverage [%]")
    ax_path.set_ylabel("executed path [m]")
    for ax in (ax_cov, ax_path):
        ax.set_xlabel("viewpoint")
        ax.set_xticks(range(0, 21, 2))
        ax.grid(alpha=0.3)

    handles, labels = ax_cov.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(labels),
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("(RH-NBV) Effect of the motion-cost weight "
                 "(coffee mug & panels3)")
    fig.tight_layout(rect=[0, 0.06, 1, 1])

    os.makedirs(OUT, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"lambda_curves.{ext}"), dpi=200)
    plt.close(fig)
    if os.path.isdir(THESIS):
        shutil.copy(os.path.join(OUT, "lambda_curves.pdf"), THESIS)
    print("wrote lambda_curves")


if __name__ == "__main__":
    main()
    ik_filter()
