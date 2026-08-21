"""Regenerate the four-planner ladder tables from the run logs.

Replaces the hand-transcribed tab:planner_comparison_mug (and the bunny
equivalent). Every number is read from each run's metrics JSON, only completed
runs are reported, and the stagnation column is gone -- that one now lives in
Figure stagnation_ladder (plot_stagnation.py).

A run counts as completed when it logged 20 iterations and the arm actually
moved (executed path > 0). A stage with no completed run gets a dash.

Writes tab_planner_comparison_{mug,bunny}.tex next to the thesis sources.
"""

import glob
import json
import os
import re

RESULTS = {
    "mug": os.path.expanduser("~/Desktop/MUG"),
    "bunny": os.path.expanduser("~/Desktop/BUNNY"),
}
THESIS = os.path.expanduser("~/Downloads/LaTeX_thesis_template_draft")

BUDGET = 20  # viewpoints per run

STAGES = ["none", "panels1", "panels2", "panels3",
          "panels4", "panels5", "panels6", "panels8"]
STAGE_LABEL = {s: s for s in STAGES}
STAGE_LABEL["panels8"] = r"panels8 (L-shape)"

PLANNERS = [
    ("RH", r"RH-NBV ($K=10$, $H=3$)"),
    ("GradientNBV", "GradientNBV"),
    ("PSO", "PSO"),
    ("Random", "Random"),
]

# The ray-call counter was never wired into these two, so their logged 0 is an
# absent counter, not an absence of computation.
NO_RAY_COUNTER = {"PSO", "Random"}

# lower is better -> not bolded; these three are "higher is better"
BOLD_COLS = ("cov", "f1", "coveff")


def completed_runs(root):
    """{planner: {stage: metrics or None}}, keeping only completed runs."""
    table, dropped = {}, []
    for planner, _ in PLANNERS:
        per_stage = dict.fromkeys(STAGES)
        for run in sorted(glob.glob(os.path.join(root, planner, "run_*"))):
            name = os.path.basename(run)
            stage = re.search(r"expC_(\w+?)_(?:K10|GradientNBV|PSO|Random)", name)
            metrics = glob.glob(os.path.join(run, "trial_00", "metrics_*.json"))
            if stage is None or stage.group(1) not in per_stage or not metrics:
                continue
            d = json.load(open(metrics[0]))
            if d["num_iters"] != BUDGET or d["distances"][-1] == 0:
                dropped.append((planner, stage.group(1), name,
                                f"iters={d['num_iters']}, path={d['distances'][-1]:.2f} m"))
                continue
            if per_stage[stage.group(1)] is not None:
                dropped.append((planner, stage.group(1), name, "duplicate, kept the other"))
                continue
            per_stage[stage.group(1)] = d
        table[planner] = per_stage
    return table, dropped


def rows(table, stage):
    """Per-planner cell values for one stage, plus the per-column best."""
    out = {}
    for planner, _ in PLANNERS:
        d = table[planner][stage]
        out[planner] = None if d is None else {
            "cov": d["final_coverage"],
            "f1": d["final_f1"] * 100.0,
            "ray": None if planner in NO_RAY_COUNTER else d["total_ray_calls"],
            "time": d["total_time"],
            "coveff": d["coverage_efficiency"],
        }
    best = {}
    for col in BOLD_COLS:
        vals = [v[col] for v in out.values() if v is not None]
        # a stage where every planner scored zero has no winner, and neither
        # does a tie -- bold only a strict, non-zero best
        top = max(vals) if vals else 0
        best[col] = top if top > 0 and vals.count(top) == 1 else None
    return out, best


def fmt(value, best, digits=2):
    if value is None:
        return "---"
    text = f"{value:.{digits}f}"
    return rf"\textbf{{{text}}}" if best is not None and value == best else text


def table_tex(obj, table):
    label = "mug" if obj == "mug" else "bunny"
    name = "coffee mug" if obj == "mug" else "Stanford bunny"
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        rf"\caption{{Four-planner comparison on the {name} across the staged panels, which are",
        r"defined in Section~\ref{sec:panels} and listed in",
        rf"Table~\ref{{tab:panel-stages}}; Figure~\ref{{fig:{label}-panels}} shows the",
        r"corresponding scenes. \texttt{none} is unoccluded, each later stage adds",
        r"one panel to those of the previous stage, and \texttt{panels8} is the asymmetric",
        r"L-shaped occluder of Section~\ref{sec:lshape}. Cov.\ Eff.\ is final coverage per",
        r"metre of executed path (\si{\percent\per\metre}). Every row is a completed run:",
        r"twenty commanded viewpoints with a non-zero executed path. A dash marks a stage",
        r"with no such run. \emph{n/a} in the ray-call column marks a planner for which the",
        r"counter was never instrumented, not one that performs no computation; the",
        r"ray-call and time columns are read in Section~\ref{sec:secondary-metrics}, which",
        r"explains why neither of them supports a comparison between planners. Stagnation",
        r"counts are given in Figure~\ref{fig:stagnation-ladder}.}",
        rf"\label{{tab:planner_comparison_{label}}}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{llccccc}",
        r"\toprule",
        r"\textbf{Stage} & \textbf{Planner} & \textbf{Coverage (\%)} & \textbf{F1 (\%)} & "
        r"\textbf{Ray Calls} & \textbf{Time (s)} & \textbf{Cov. Eff.} \\",
        r"\midrule",
    ]
    for si, stage in enumerate(STAGES):
        if si:
            lines.append(r"\midrule")
        cells, best = rows(table, stage)
        lines.append(rf"\multirow{{4}}{{*}}{{{STAGE_LABEL[stage]}}}")
        for planner, label_tex in PLANNERS:
            v = cells[planner]
            if v is None:
                lines.append(rf"  & {label_tex} & --- & --- & --- & --- & --- \\")
                continue
            ray = "n/a" if v["ray"] is None else f"{v['ray']}"
            lines.append(
                rf"  & {label_tex} & {fmt(v['cov'], best['cov'])} & {fmt(v['f1'], best['f1'])}"
                rf" & {ray} & {v['time']:.1f} & {fmt(v['coveff'], best['coveff'], 1)} \\")
    lines += [r"\bottomrule", r"\end{tabular}%", r"}", r"\end{table}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    for obj, root in RESULTS.items():
        table, dropped = completed_runs(root)
        out = os.path.join(THESIS, f"tab_planner_comparison_{obj}.tex")
        with open(out, "w") as f:
            f.write(table_tex(obj, table))
        print(f"{obj}: wrote {out}")
        for planner, stage, name, why in dropped:
            print(f"   dropped {planner:12s} {stage:8s} {name}  ({why})")
        for planner, _ in PLANNERS:
            missing = [s for s in STAGES if table[planner][s] is None]
            if missing:
                print(f"   no completed run: {planner:12s} {', '.join(missing)}")
