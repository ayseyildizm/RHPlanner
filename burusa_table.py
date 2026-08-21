#!/usr/bin/env python3
"""
burusa_table.py — Burusa et al. (2024) Table I, rebuilt on our plant data.

Same layout as their occlusion-handling table: metric groups side by side,
viewpoint checkpoints {0,5,10,15,20} as sub-columns, one row per planner,
averaged over all experiments. Ours adds an F1 group.

Averaging pool: 3 attention levels x 4 plant orientations = 12 experiments
(Burusa averaged 16). Trial selection follows the protocol already used for
Table 5.x in the thesis: per (level, planner, yaw) take the trial with the
highest motion-success rate (tie -> lowest index), requiring >= 80 % motion
success and camera data at view 1; PSO passes that gate nowhere and is
reported over its executed views only.

Usage:
    python3 burusa_table.py                 # console + LaTeX to stdout
    python3 burusa_table.py --per-level     # also one table per level
    python3 burusa_table.py --out tab.tex
"""
import argparse
import glob
import json
import os

import numpy as np

PLANT = os.path.expanduser("~/Desktop/PLANT")
LEVELS = ["FRUIT", "BLOSSOM", "ALL"]
LEVEL_NAME = {"FRUIT": "Fruit", "BLOSSOM": "Blossom", "ALL": "Whole plant"}
PLANNERS = ["RH-NBV", "GradientNBV", "PSO", "Random"]
PLANNER_DIR = {"RH-NBV": "RH", "GradientNBV": "GradientNBV",
               "PSO": "PSO", "Random": "Random"}
YAWS = ["y000", "y090", "y180", "y270"]
CHECKPOINTS = [0, 5, 10, 15, 20]
# Planners whose ray-tracing counter is meaningful. The counter was only ever
# wired into RH-NBV and GradientNBV; PSO and Random cast rays too, but their
# zeros are missing values, not measurements (Section sec:secondary-cost).
RAYS = {"RH-NBV": True, "GradientNBV": True, "PSO": None, "Random": None}
DEPLOYABLE = ["RH-NBV", "GradientNBV", "Random"]  # PSO excluded from bold


def load_trial(path):
    f = glob.glob(os.path.join(path, "metrics_*.json"))
    if not f:
        return None
    with open(f[0]) as fh:
        return json.load(fh)


def pick_trial(level, planner, yaw):
    """Highest motion-success trial that passes the validity gate; if none
    passes (PSO), the highest-success trial regardless, flagged as ungated."""
    pat = os.path.join(PLANT, PLANNER_DIR[planner], level, f"run_*_{yaw}_*")
    trials = []
    for run in sorted(glob.glob(pat)):
        for t in sorted(glob.glob(os.path.join(run, "trial_*"))):
            m = load_trial(t)
            if m:
                trials.append((int(os.path.basename(t).split("_")[1]), m, t))
    if not trials:
        return None, None, False

    def gated(m):
        cov = m.get("coverages", [])
        return (m.get("move_success_rate", 0) >= 80.0
                and not (len(cov) > 1 and cov[1] == 0))

    ok = [t for t in trials if gated(t[1])]
    pool, is_gated = (ok, True) if ok else (trials, False)
    # highest motion success, tie -> lowest trial index
    idx, m, path = max(pool, key=lambda t: (t[1].get("move_success_rate", 0), -t[0]))
    return m, path, is_gated


def series(m, key):
    """Value at each checkpoint; arrays are cumulative and 21 long."""
    a = m[key]
    return [a[c] if c < len(a) else a[-1] for c in CHECKPOINTS]


def collect(levels):
    """{planner: {metric: [mean per checkpoint]}} plus per-cell std and n."""
    out, ungated = {}, {}
    for p in PLANNERS:
        acc = {"coverages": [], "f1_scores": [], "ray_tracing_calls": [],
               "distances": []}
        bad = []
        for lv in levels:
            for yaw in YAWS:
                m, path, is_gated = pick_trial(lv, p, yaw)
                if m is None:
                    print(f"  !! missing {lv}/{p}/{yaw}")
                    continue
                if not is_gated:
                    bad.append(f"{LEVEL_NAME[lv]}/{yaw} "
                               f"({m.get('move_success_rate', 0):.0f}%)")
                for k in acc:
                    acc[k].append(series(m, k))
        out[p] = {k: (np.array(v, float) if v else np.zeros((0, len(CHECKPOINTS))))
                  for k, v in acc.items()}
        ungated[p] = bad
    return out, ungated


def fmt_cell(planner, metric, mean, best):
    if metric == "ray_tracing_calls":
        if RAYS[planner] is not True:
            return r"n/a$^{\ddagger}$"
        s = f"{mean:.0f}"
    elif metric == "coverages":
        s = f"{mean:.1f}"
    elif metric in ("f1_scores", "occluded_recall_series"):
        s = f"{mean:.3f}"
    else:
        s = f"{mean:.2f}"
    return r"\textbf{" + s + "}" if best else s


METRICS = [("coverages", r"ROI coverage (\%) $\uparrow$"),
           ("f1_scores", r"$F_1$ score $\uparrow$"),
           ("ray_tracing_calls", r"Ray-tracing calls (\#) $\downarrow$"),
           ("distances", r"Trajectory distance (m) $\downarrow$")]
OCC_RECALL = ("occluded_recall_series", r"Occluded recall $\uparrow$")


def build(data, levels, label, caption, metrics=None, checkpoints=None):
    metrics = metrics or METRICS
    cps = checkpoints or CHECKPOINTS
    ncp = len(cps)
    means = {p: {k: data[p][k].mean(axis=0) for k, _ in metrics} for p in PLANNERS}

    # best deployable planner per (metric, checkpoint); skip the 0 column and
    # the ray-call column, where only two planners report a number
    best = {}
    for k, _ in metrics:
        # the ray-call column restates K x H rather than measuring anything
        # (Section sec:secondary-cost), so nothing is marked best there
        if k == "ray_tracing_calls":
            continue
        for j, c in enumerate(cps):
            if c == 0:
                continue
            cand = DEPLOYABLE
            lower = k in ("ray_tracing_calls", "distances")
            pick = (min if lower else max)(cand, key=lambda p: means[p][k][j])
            best[(k, j)] = pick

    ncol = 1 + len(metrics) * ncp
    L = []
    L.append(r"\begin{table}[H]")
    L.append(r"\centering")
    L.append(r"\caption{" + caption + "}")
    L.append(r"\label{" + label + "}")
    L.append(r"\resizebox{\textwidth}{!}{%")
    L.append(r"\begin{tabular}{l|" + "|".join(["c" * ncp] * len(metrics)) + "}")
    L.append(r"\toprule")
    L.append(" & " + " & ".join(
        r"\multicolumn{" + str(ncp) + "}{c" + ("|" if i < len(metrics) - 1 else "") + "}{" + t + "}"
        for i, (_, t) in enumerate(metrics)) + r" \\")
    L.append(r"\# Viewpoints & " +
             " & ".join(" & ".join(f"${c}$" for c in cps)
                        for _ in metrics) + r" \\")
    L.append(r"\midrule")
    for p in PLANNERS:
        name = p + (r"$^{\dagger}$" if p == "PSO" else "")
        cells = []
        for k, _ in metrics:
            # an uninstrumented counter is one statement, not five cells
            if k == "ray_tracing_calls" and RAYS[p] is None:
                cells.append(r"\multicolumn{" + str(ncp) + r"}{c|}{n/a$^{\ddagger}$}")
                continue
            for j in range(ncp):
                cells.append(fmt_cell(p, k, means[p][k][j], best.get((k, j)) == p))
        L.append(name + " & " + " & ".join(cells) + r" \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}%")
    L.append(r"}")
    L.append(r"\end{table}")
    return "\n".join(L), means


def console(means, title, n):
    print(f"\n=== {title} (n = {n} experiments) ===")
    hdr = f"{'':<12}" + "".join(
        f"{('v%d' % c):>9}" for _ in range(4) for c in CHECKPOINTS)
    print(f"{'':<12}" + f"{'ROI coverage (%)':^45}{'F1':^45}"
          f"{'ray calls':^45}{'traj (m)':^45}")
    print(hdr)
    for p in PLANNERS:
        row = f"{p:<12}"
        for k, nd in (("coverages", 1), ("f1_scores", 3),
                      ("ray_tracing_calls", 0), ("distances", 2)):
            for j in range(len(CHECKPOINTS)):
                v = means[p][k][j]
                row += ("        -" if (k == "ray_tracing_calls"
                                        and RAYS[p] is not True)
                        else f"{v:>9.{nd}f}")
        print(row)


CAPTION_ALL = (
    r"Results for the occlusion-handling behaviour on the tomato plant, in the "
    r"layout of \citet{akshay_henten_kootstra_2023}. The average performance "
    r"across $12$ experiments ($3$ attention levels $\times$ $4$ plant "
    r"orientations) is shown. View $0$ is the common predefined start pose, "
    r"which is reached before any measurement is taken, so every planner "
    r"starts from zero here. Best value per column among the deployable "
    r"planners in bold. "
    r"$^{\dagger}$\,PSO's commanded poses were largely unreachable for the arm "
    r"(motion success $2/20$--$10/20$, Section~\ref{sec:results-reach}); its "
    r"values reflect executed views only and are excluded from the bold "
    r"comparison. "
    r"$^{\ddagger}$\,The ray-tracing counter was wired into RH-NBV and "
    r"GradientNBV only; PSO and Random also cast rays, but their zeros are "
    r"missing values. Even where it is recorded the column restates the "
    r"configuration ($K \times H = 30$ per iteration against one gradient "
    r"step) rather than reporting a measurement, so no value in it is marked "
    r"best (Section~\ref{sec:secondary-cost}).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-level", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--out-levels", default=None,
                    help="write the per-level tables to their own file")
    args = ap.parse_args()

    blocks, level_blocks = [], []
    data, ungated = collect(LEVELS)
    tex, means = build(data, LEVELS, "tab:tree-burusa", CAPTION_ALL)
    console(means, "All levels", len(data["RH-NBV"]["coverages"]))
    blocks.append(tex)

    if args.per_level or args.out_levels:
        for lv in LEVELS:
            d, _ = collect([lv])
            cap = (f"Occlusion-handling behaviour at the {LEVEL_NAME[lv].lower()} "
                   r"level; average over the $4$ plant orientations. "
                   r"Conventions as in Table~\ref{tab:tree-burusa}.")
            t, m = build(d, [lv], f"tab:tree-burusa-{lv.lower()}", cap)
            console(m, LEVEL_NAME[lv], len(d["RH-NBV"]["coverages"]))
            (level_blocks if args.out_levels else blocks).append(t)

    print("\n--- ungated (reported over executed views only) ---")
    for p, bad in ungated.items():
        if bad:
            print(f"  {p}: {', '.join(bad)}")

    out = "\n\n".join(blocks) + "\n"
    if args.out_levels:
        with open(args.out_levels, "w") as f:
            f.write("\n\n".join(level_blocks) + "\n")
        print(f"\nwrote {args.out_levels}")
    if args.out:
        with open(args.out, "w") as f:
            f.write(out)
        print(f"\nwrote {args.out}")
    else:
        print("\n" + out)
