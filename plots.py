import json
import os
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = os.path.expanduser("~/Desktop/RecedingHorizon")
THESIS = os.path.expanduser("~/Desktop/LaTeX_thesis_template1__1_(1)/figures")
OUT = os.path.join(REPO, "figures")

BASELINE = os.path.expanduser(
    "~/Desktop/MUG/RH/run_20260707_180342_expC_panels3_K10_H3_box")

# --- which runs go into which figure ----
RUNS = [
    ("H=3, K=10 (default)", BASELINE),
    ("H=2, K=10",  "abtest_H2K10_run_20260727_040500_expC_panels3_K10_H2_box"),
    ("H=1, K=10",  "abtest_H1K10_run_20260726_233435_expC_panels3_K10_H1_box"),
    ("H=1, K=30",  "abtest_H1K30b_run_20260728_063458_expC_panels3_K30_H1_box"),
    ("H=3, K=5",   "abtest_H3K5_run_20260728_221919_expC_panels3_K5_H3_box"),
]

# Same-configuration control collected in the same batch as the lambda and
# IK-filter runs. The default row above comes from a much earlier session, and
# a repeat of that identical configuration lands 39 coverage points lower, so
# any lambda effect has to be read against this control, not against BASELINE.
REPEAT = "abtest_H3K10rep_run_20260728_091340_expC_panels3_K10_H3_box"

LAMBDA_RUNS = [
    ("lambda = 2.0 (default)", BASELINE),
    ("lambda = 1", "abtest_lam1_run_20260728_193351_expC_panels3_K10_H3_box"),
    ("lambda = 0", "abtest_lam0_run_20260728_151336_expC_panels3_K10_H3_box"),
]

# --- how the lines look -----
COLORS = ["#26e083", "#d95f02", "#202ADE", "#CD1F1F", "#e45bf1"]
DASHES = ["solid", (0, (5, 2)), (0, (1, 1.5)), (0, (6, 2, 1, 2)), (0, (3, 1, 1, 1))]


def load(folder):
    """Read the metrics file of a run folder"""
    path = folder if os.path.isabs(folder) else os.path.join(REPO, "results", folder)
    path = os.path.join(path, "trial_00")
    name = [f for f in os.listdir(path) if f.startswith("metrics_")][0]
    return json.load(open(os.path.join(path, name)))


def curves(runs, filename, title=None):
    """Coverage and F1 against viewpoint number, one line per run."""
    fig, (ax_cov, ax_f1) = plt.subplots(1, 2, figsize=(10, 4))

    for i, (label, folder) in enumerate(runs):
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
        ax.set_xticks(range(0, 21, 2))   # viewpoints are whole numbers
        ax.grid(alpha=0.3)
    # One legend for both panels, below the figure: repeating it inside each
    # panel costs plot area and hides curves.
    handles, labels = ax_cov.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(labels),
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.02))
    if title:
        fig.suptitle(title)
    fig.tight_layout(rect=[0, 0.06, 1, 1])

    os.makedirs(OUT, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{filename}.{ext}"), dpi=200)
    plt.close(fig)

    if os.path.isdir(THESIS):
        shutil.copy(os.path.join(OUT, f"{filename}.pdf"), THESIS)
    print("wrote", filename)


def motions_bar(filename):
    """How many of the 20 commanded motions the arm actually executed."""
    labels, values = [], []
    for label, folder in RUNS + LAMBDA_RUNS[1:]:
        m = load(folder)
        rate = m.get("move_success_rate")
        if rate is None:
            d = m["distances"]
            zeros = sum(1 for i in range(1, len(d)) if abs(d[i] - d[i - 1]) < 1e-9)
            executed = len(d) - 1 - zeros
        else:
            executed = round(rate * m["total_moves"] / 100)
        labels.append(label)
        values.append(executed)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(labels, values, color=COLORS[0])
    ax.axhline(16, color="#d95f02", linestyle=(0, (5, 2)), linewidth=2,
               label="80 % criterion")
    ax.set_ylabel("motions executed (of 20)")
    ax.set_ylim(0, 21)
    ax.legend(fontsize=8)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{filename}.{ext}"), dpi=200)
    plt.close(fig)
    if os.path.isdir(THESIS):
        shutil.copy(os.path.join(OUT, f"{filename}.pdf"), THESIS)
    print("wrote", filename)


HORIZON_RUNS = RUNS

# Candidate-budget figure: the default against both directions, K=5 and K=20.
# The K=20 run executed its first 8 motions and then failed 12 in a row, so its
# curve is flat from viewpoint 8 on. It is plotted rather than dropped: the
# failures are the planner's own commanded poses, and the flat tail is what
# that costs.
BUDGET_RUNS = [
    RUNS[0],                                    # H=3, K=10 (default)
    ("H=3, K=5",  "abtest_H3K5_run_20260728_221919_expC_panels3_K5_H3_box"),
    ("H=3, K=20", "abtest_H3K20_run_20260728_235316_expC_panels3_K20_H3_box"),
]


# Reachability-filtered run
# it is a separate experiment, not part of the ablation table above.
IK_RUNS = [
    ("H=3, K=10 (default)", BASELINE),
    ("H=3, K=10, same-batch repeat", REPEAT),
    ("H=3, K=10, IK-filtered",
     "abtest_ikfilter_run_20260729_111003_expC_panels3_K10_H3_box"),
]


if __name__ == "__main__":
      curves(HORIZON_RUNS, "horizon_curves", title="(RH-NBV) Effect of the planning horizon (coffee mug & panels3)")
      curves(BUDGET_RUNS, "budget_curves", title="(RH-NBV) Effect of the candidate budget (coffee mug & panels3)")
      motions_bar("motion_success")
      # lambda_curves and ik_filter_curves are owned by plot_lambda.py, which
      # draws them from the same-batch runs that results.tex describes. Both
      # scripts used to write these two filenames, so whichever ran last won.