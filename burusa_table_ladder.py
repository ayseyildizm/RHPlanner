#!/usr/bin/env python3
"""
burusa_table_ladder.py — Burusa Table I layout for the bunny and the mug.

Same table as burusa_table.py builds for the plant, but the averaging pool is
the staged panel ladder instead of the attention levels: one table per object,
averaged over the occlusion stages.

The pool is balanced on purpose. A stage enters the average only if all four
planners have a usable run there, so every row is an average over the same
scenes. On the mug that drops three stages (see EXCLUDED below); on the bunny
nothing drops.

Runs come from the curated ~/Desktop/{BUNNY,MUG}/<planner>/run_*_expC_<stage>_*
trees, trial_00, which are the runs the ladder tables of the thesis report.

Usage:
    python3 burusa_table_ladder.py --out-bunny b.tex --out-mug m.tex
"""
import argparse
import glob
import json
import os
import re

import numpy as np

from burusa_table import (CHECKPOINTS, DEPLOYABLE, PLANNERS, RAYS, build,
                          console)

DESKTOP = os.path.expanduser("~/Desktop")
PLANNER_DIR = {"RH-NBV": "RH", "GradientNBV": "GradientNBV",
               "PSO": "PSO", "Random": "Random"}
STAGES = ["none", "panels1", "panels2", "panels3", "panels4", "panels5",
          "panels6", "panels8"]
OBJECTS = {"BUNNY": "Stanford bunny", "MUG": "coffee mug"}
RUN_RE = re.compile(r"run_(\d{8}_\d{6})_expC_(\w+?)_"
                    r"(K10_H3_box|GradientNBV|PSO|Random)$")


def load(path):
    f = glob.glob(os.path.join(path, "trial_00", "metrics_*.json"))
    if not f:
        return None
    with open(f[0]) as fh:
        return json.load(fh)


def usable(m, planner):
    """A run measures the planner only if the arm executed at least half of the
    commanded viewpoints; below that it measures the reachability of the scene.
    This is the criterion behind the dashes in the ladder tables of the thesis.
    move_success_rate is absent in the earliest runs, which predate the counter;
    those are kept. PSO fails the criterion nearly everywhere by construction
    and is reported over its executed views with the dagger footnote, so it is
    only required to have moved at all."""
    msr = m.get("move_success_rate")
    if msr is None:
        return True, ""
    floor = 0 if planner == "PSO" else 50
    if msr <= floor:
        return False, f"only {int(round(msr / 5))}/20 motions executed"
    return True, ""


def runs_for(obj, planner, stage):
    """Newest usable run for this cell, with why anything was rejected."""
    pat = os.path.join(DESKTOP, obj, PLANNER_DIR[planner], "run_*")
    found, rejected = [], []
    for d in sorted(glob.glob(pat), reverse=True):  # newest first
        mt = RUN_RE.search(os.path.basename(d))
        if not mt or mt.group(2) != stage:
            continue
        m = load(d)
        if m is None:
            rejected.append((os.path.basename(d), "no trial_00 metrics"))
            continue
        ok, why = usable(m, planner)
        (found if ok else rejected).append((os.path.basename(d), m if ok else why))
    return (found[0][1] if found else None), rejected


SERIES = ("coverages", "f1_scores", "occluded_recall_series",
          "ray_tracing_calls", "distances")


def collect(obj, stages):
    """{planner: {metric: array over stages}} for a balanced stage pool."""
    out = {}
    for p in PLANNERS:
        acc = {k: [] for k in SERIES}
        for s in stages:
            m, _ = runs_for(obj, p, s)
            for k in acc:
                a = m[k]
                acc[k].append([a[c] if c < len(a) else a[-1] for c in CHECKPOINTS])
        out[p] = {k: np.array(v, float) for k, v in acc.items()}
    return out


def audit(obj):
    """Which stages are complete for all four planners, and what is missing."""
    ok_stages, missing = [], []
    for s in STAGES:
        gaps = []
        for p in PLANNERS:
            m, rejected = runs_for(obj, p, s)
            if m is None:
                why = "; ".join(f"{d}: {w}" for d, w in rejected) or "no run"
                gaps.append(f"{p} ({why})")
        (ok_stages if not gaps else missing).append(s if not gaps else (s, gaps))
    return ok_stages, missing


COMBINED = [("coverages", r"ROI coverage (\%) $\uparrow$", 1, 1.0),
            ("f1_scores", r"$F_1$ score (\%) $\uparrow$", 1, 100.0),
            ("occluded_recall_series", r"Occluded recall (\%) $\uparrow$", 1,
             100.0),
            ("ray_tracing_calls", r"Ray-tracing calls (\#) $\downarrow$", 0,
             1.0),
            ("distances", r"Trajectory distance (m) $\downarrow$", 2, 1.0)]
LOWER_IS_BETTER = ("ray_tracing_calls", "distances")


def build_combined(blocks, label, caption, cps=CHECKPOINTS):
    """One table, one row block per object: Target | Planner | metric groups.

    blocks: [(display name, {planner: {metric: array}}), ...]
    """
    ncp = len(cps)
    # collect() sampled the series at CHECKPOINTS; cps may be a subset of it
    idx = [CHECKPOINTS.index(c) for c in cps]
    L = [r"\begin{table}[H]", r"\centering",
         r"\caption{" + caption + "}", r"\label{" + label + "}",
         r"\resizebox{\textwidth}{!}{%",
         r"\begin{tabular}{ll|" + "|".join(["c" * ncp] * len(COMBINED)) + "}",
         r"\toprule",
         " & & " + " & ".join(
             r"\multicolumn{" + str(ncp) + "}{c"
             + ("|" if i < len(COMBINED) - 1 else "") + "}{" + t + "}"
             for i, (_, t, _, _) in enumerate(COMBINED)) + r" \\",
         r"\textbf{Target} & \textbf{Planner} & "
         + " & ".join(" & ".join(f"${c}$" for c in cps)
                      for _ in COMBINED) + r" \\"]

    for bi, (name, data) in enumerate(blocks):
        means = {p: {k: data[p][k].mean(axis=0) * sc
                     for k, _, _, sc in COMBINED} for p in PLANNERS}
        best = {}
        for k, _, _, _ in COMBINED:
            if k == "ray_tracing_calls":  # restates K x H, not a measurement
                continue
            for j, c in enumerate(cps):
                if c == 0:
                    continue
                pick = (min if k in LOWER_IS_BETTER else max)(
                    DEPLOYABLE, key=lambda p: means[p][k][idx[j]])
                best[(k, j)] = pick

        L.append(r"\midrule")
        L.append(r"\multirow{4}{*}{" + name + "}")
        for p in PLANNERS:
            cells = []
            for k, _, nd, _ in COMBINED:
                if k == "ray_tracing_calls" and RAYS[p] is not True:
                    cells.append(r"\multicolumn{" + str(ncp)
                                 + r"}{c|}{n/a$^{\ddagger}$}")
                    continue
                for j in range(ncp):
                    s = f"{means[p][k][idx[j]]:.{nd}f}"
                    cells.append(r"\textbf{" + s + "}"
                                 if best.get((k, j)) == p else s)
            label_cell = p + (r"$^{\dagger}$" if p == "PSO" else "")
            L.append("& " + label_cell + " & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}%", "}", r"\end{table}"]
    return "\n".join(L)


CAPTION_COMBINED = (
    r"Results for the occlusion-handling behaviour on the two rigid targets, "
    r"in the layout of \citet{{akshay_henten_kootstra_2023}}. Each row is the "
    r"average over the panel stages of Section~\ref{{sec:panels}}: {bunny} "
    r"stages for the bunny and {mug} for the mug. A stage enters an average "
    r"only if all four planners have a run there in which the arm executed at "
    r"least half of the commanded viewpoints, so the four rows of a block "
    r"average over the same scenes; {excl} The two blocks are therefore not "
    r"comparable with each other: they pool different stages, and the bunny is "
    r"the harder shape at every stage of the ladder. {zero} Best value per "
    r"column within a "
    r"block, among the deployable planners, in bold. "
    r"$^{{\dagger}}$\,PSO's commanded poses were largely unreachable for the "
    r"arm ({pso}); its values reflect executed views only and are excluded "
    r"from the bold comparison. "
    r"$^{{\ddagger}}$\,The ray-tracing counter was wired into RH-NBV and "
    r"GradientNBV only; PSO and Random also cast rays, but their zeros are "
    r"missing values. Even where it is recorded the column restates the "
    r"configuration ($K \times H = 30$ per iteration against one gradient "
    r"step) rather than reporting a measurement, so no value in it is marked "
    r"best (Section~\ref{{sec:secondary-cost}}).")


CAPTION = (
    r"Results for the occlusion-handling behaviour on the {obj}, in the layout "
    r"of \citet{{akshay_henten_kootstra_2023}}. The average performance across "
    r"the {n} occlusion stages of Section~\ref{{sec:panels}} "
    r"({stages}) is shown; {pool} View $0$ is the common predefined start pose, "
    r"which is reached before any measurement is taken, so every planner "
    r"starts from zero here. Best value per column among the deployable "
    r"planners in bold. "
    r"$^{{\dagger}}$\,PSO's commanded poses were largely unreachable for the "
    r"arm ({pso}); its values reflect executed views only and are excluded "
    r"from the bold comparison. "
    r"$^{{\ddagger}}$\,The ray-tracing counter was wired into RH-NBV and "
    r"GradientNBV only; PSO and Random also cast rays, but their zeros are "
    r"missing values. Even where it is recorded the column restates the "
    r"configuration ($K \times H = 30$ per iteration against one gradient "
    r"step) rather than reporting a measurement, so no value in it is marked "
    r"best (Section~\ref{{sec:secondary-cost}}).")

POOL_FULL = (r"the ladder is complete for every planner, so all four rows "
             r"average over the same eight scenes.")
POOL_PART = (r"the average is restricted to the stages where all four planners "
             r"have a run that executed, so that the four rows average over "
             r"the same scenes. {excl}")


def pso_range(obj, stages):
    rates = []
    for s in stages:
        m, _ = runs_for(obj, "PSO", s)
        r = m.get("move_success_rate")
        if r is not None:
            rates.append(int(round(r / 5)))  # of 20 views
    return f"motion success ${min(rates)}/20$--${max(rates)}/20$" if rates \
        else "motion success not recorded"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-bunny", default=None)
    ap.add_argument("--out-mug", default=None)
    ap.add_argument("--out-combined", default=None,
                    help="one table, mug and bunny as row blocks, with the "
                         "occluded-recall group")
    ap.add_argument("--no-zero", action="store_true",
                    help="drop the view-0 column, which is zero by protocol")
    args = ap.parse_args()

    if args.out_combined:
        cps = [c for c in CHECKPOINTS if c or not args.no_zero]
        blocks, pools, pso = [], {}, {}
        for obj in ("MUG", "BUNNY"):
            stages, missing = audit(obj)
            pools[obj], pso[obj] = stages, pso_range(obj, stages)
            blocks.append((OBJECTS[obj].split()[-1].capitalize(),
                           collect(obj, stages)))
            print(f"{obj}: {len(stages)} stages — {', '.join(stages)}")
            for s, gaps in missing:
                print(f"  !! {s} excluded — {'; '.join(gaps)}")
        excl = ("The mug therefore loses "
                + ", ".join(f"\\texttt{{{s}}}" for s, _ in audit("MUG")[1])
                + r", the same cells that "
                r"Table~\ref{tab:planner_comparison_mug} leaves blank.")
        zero = (r"The count starts at the common predefined start pose, "
                r"which is reached before any measurement is taken; that "
                r"viewpoint is zero for every planner on every metric and is "
                r"left out of the table."
                if args.no_zero else
                r"View $0$ is the common predefined start pose, which is "
                r"reached before any measurement is taken, so every planner "
                r"starts from zero there.")
        cap = CAPTION_COMBINED.format(
            bunny=len(pools["BUNNY"]), mug=len(pools["MUG"]), excl=excl,
            zero=zero,
            pso=(f"{pso['MUG']} on the mug and "
                 f"{pso['BUNNY'].replace('motion success ', '')} on the "
                 "bunny"))
        tex = build_combined(blocks, "tab:mug-bunny-burusa", cap, cps)
        with open(args.out_combined, "w") as f:
            f.write(tex + "\n")
        print(f"wrote {args.out_combined}")
        raise SystemExit

    for obj, out in (("BUNNY", args.out_bunny), ("MUG", args.out_mug)):
        stages, missing = audit(obj)
        print(f"\n########## {obj}: pooling {len(stages)} stages: "
              f"{', '.join(stages)}")
        for s, gaps in missing:
            print(f"  !! {s} excluded — {'; '.join(gaps)}")

        excl = ""
        if missing:
            names = ", ".join(f"\\texttt{{{s}}}" for s, _ in missing)
            excl = (f"The stages {names} are left out because at least one "
                    r"planner has no run there in which the arm executed at "
                    r"least half of the commanded viewpoints; these are the "
                    r"same cells that Table~\ref{tab:planner_comparison_mug} "
                    r"leaves blank.")
        cap = CAPTION.format(
            obj=OBJECTS[obj], n=len(stages),
            stages=", ".join(f"\\texttt{{{s}}}" for s in stages),
            pool=(POOL_FULL if not missing else POOL_PART.format(excl=excl)),
            pso=pso_range(obj, stages))

        data = collect(obj, stages)
        tex, means = build(data, stages, f"tab:{obj.lower()}-burusa", cap)
        console(means, f"{OBJECTS[obj]} ({len(stages)} stages)", len(stages))
        if out:
            with open(out, "w") as f:
                f.write(tex + "\n")
            print(f"\nwrote {out}")
        else:
            print("\n" + tex)
