#!/usr/bin/env python3
"""
make_f1sweep_table.py — LaTeX table of final F1/recall against the matching
threshold, from the f1_sweep_dump.npz files written by test_tree_f1dump_node.py.

Answers the 2026-08-04 question directly: as the matching tolerance shrinks,
do RH-NBV and GradientNBV separate, or do both collapse together? Scoring is
byte-for-byte f1_threshold_sweep.py's rule (Chebyshev NN both ways), so the
numbers here and there agree.

Usage:
    python3 make_f1sweep_table.py <run_dir> [<run_dir> ...]     # explicit
    python3 make_f1sweep_table.py                               # auto-discover
    python3 make_f1sweep_table.py --out tab_f1_threshold.tex
"""
import argparse
import glob
import os

import numpy as np
from scipy.spatial import KDTree

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
THRESHOLDS_MM = [2, 3, 4, 6, 8, 10, 12]


def score(voxels, roi_mesh, half):
    if len(voxels) == 0 or len(roi_mesh) == 0:
        return 0.0, 0.0, 0.0
    d_tp, _ = KDTree(roi_mesh).query(voxels, k=1, p=np.inf)
    d_rc, _ = KDTree(voxels).query(roi_mesh, k=1, p=np.inf)
    precision = float(np.mean(d_tp <= half))
    recall = float(np.mean(d_rc <= half))
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall > 0 else 0.0)
    return f1, recall, precision


def load(run_dir):
    hits = glob.glob(os.path.join(run_dir, "trial_*", "f1_sweep_dump.npz"))
    if not hits:
        return None
    d = np.load(hits[0])
    n = int(d["n_iters"])
    snaps = [d[f"v{i:02d}"] for i in range(n)]
    mesh, target = d["mesh"], d["target"]
    roi_half = float(d["roi_half"])
    roi_mesh = mesh[np.all(np.abs(mesh - target) <= roi_half, axis=1)]
    return {
        "snaps": snaps,
        "roi_mesh": roi_mesh,
        "roi_half": roi_half,
        "thr_run": float(d["f1_thresh"]),
        "voxel": float(d["voxel_size"]),
        "dir": run_dir,
    }


def planner_of(run_dir):
    b = os.path.basename(run_dir.rstrip("/"))
    if "Gradient" in b:
        return "GradientNBV"
    if "K10_H3" in b or "rh" in b.lower():
        return "RH-NBV"
    if "Random" in b:
        return "Random"
    if "PSO" in b:
        return "PSO"
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--out", default=None, help="write the LaTeX here as well")
    args = ap.parse_args()

    dirs = args.dirs or sorted(
        {os.path.dirname(os.path.dirname(p))
         for p in glob.glob(os.path.join(RESULTS, "*", "trial_*", "f1_sweep_dump.npz"))})
    if not dirs:
        raise SystemExit("no f1_sweep_dump.npz found under results/")

    runs = {}
    for rd in dirs:
        data = load(rd)
        if data is None:
            print(f"[atla] dump yok: {rd}")
            continue
        runs[planner_of(rd)] = data

    order = [p for p in ("RH-NBV", "GradientNBV", "PSO", "Random") if p in runs]
    if not order:
        raise SystemExit("taninan planlayici yok")

    # --- console summary -----------------------------------------------------
    for p in order:
        r = runs[p]
        print(f"\n### {p}  {os.path.basename(r['dir'])}")
        print(f"    {len(r['snaps'])} iterasyon · son adim {len(r['snaps'][-1]):,} voxel · "
              f"ROI ici GT {len(r['roi_mesh']):,} · kosu esigi {r['thr_run']*1000:.0f} mm · "
              f"voxel {r['voxel']*1000:.0f} mm")

    rows = {}
    for p in order:
        r = runs[p]
        final = r["snaps"][-1]
        rows[p] = {t: score(final, r["roi_mesh"], t / 1000.0) for t in THRESHOLDS_MM}

    head = "  ".join(f"{p:>12s}" for p in order)
    print(f"\n  {'esik':>6s}  {head}" + ("        fark" if len(order) > 1 else ""))
    for t in THRESHOLDS_MM:
        vals = [rows[p][t][0] for p in order]
        body = "  ".join(f"{v:12.4f}" for v in vals)
        extra = f"   {max(vals)-min(vals):+.4f}" if len(order) > 1 else ""
        print(f"  {t:4d}mm  {body}{extra}")

    # --- LaTeX ---------------------------------------------------------------
    ncol = len(order)
    lines = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(
        r"\caption{Final $F_1$ and recall at the fruit level (\texttt{panels\_tree\_fruit\_y000}, "
        r"$20$ viewpoints, one run per planner) recomputed at a range of matching thresholds. "
        r"The reconstructed voxels and the ground-truth mesh are those of the runs themselves; "
        r"only the tolerance used to declare a match is varied, so no simulation is repeated. "
        r"The threshold the runs reported with is marked $^{\star}$; "
        r"$\rho$ denotes the voxel edge (\SI{3}{\milli\metre}).}")
    lines.append(r"\label{tab:f1-threshold-sweep}")
    lines.append(r"\begin{tabular}{l|" + "c" * ncol + r"|" + "c" * ncol + r"}")
    lines.append(r"\toprule")
    lines.append(r" & \multicolumn{%d}{c|}{$F_1$ $\uparrow$} & \multicolumn{%d}{c}{Recall $\uparrow$} \\"
                 % (ncol, ncol))
    hdr = " & ".join(p.replace("NBV", "NBV") for p in order)
    lines.append(r"Threshold & " + hdr + " & " + hdr + r" \\")
    lines.append(r"\midrule")
    for t in THRESHOLDS_MM:
        star = ""
        for p in order:
            if abs(t / 1000.0 - runs[p]["thr_run"]) < 1e-9:
                star = r"$^{\star}$"
                break
        mult = t / (runs[order[0]]["voxel"] * 1000.0)
        label = r"\SI{%d}{\milli\metre} ($%.3g\rho$)%s" % (t, mult, star)
        f1s = [rows[p][t][0] for p in order]
        rcs = [rows[p][t][1] for p in order]
        best_f1, best_rc = max(f1s), max(rcs)
        cells = [(r"\textbf{%.3f}" % v) if (v == best_f1 and ncol > 1) else ("%.3f" % v)
                 for v in f1s]
        cells += [(r"\textbf{%.3f}" % v) if (v == best_rc and ncol > 1) else ("%.3f" % v)
                  for v in rcs]
        lines.append(label + " & " + " & ".join(cells) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    tex = "\n".join(lines)

    print("\n" + "=" * 70 + "\n")
    print(tex)
    if args.out:
        out = args.out if os.path.isabs(args.out) else os.path.join(HERE, args.out)
        with open(out, "w") as fh:
            fh.write(tex + "\n")
        print(f"\n[yazildi] {out}")


if __name__ == "__main__":
    main()
