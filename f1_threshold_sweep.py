#!/usr/bin/env python3
"""
f1_threshold_sweep.py — recompute plant-level F1 at other matching thresholds
from the dumps written by test_tree_f1dump_node.py. No simulation is re-run.

Question (2026-08-04): at the plant attention levels all four planners score
F1 within 0.05 of one another and the random walk matches RH-NBV. Is that a
real equivalence, or does the 2*rho matching tolerance saturate the score?

The scoring here is byte-for-byte the pipeline's rule (planner_eval_mixin.py
lines 139-152): Chebyshev (p=inf) nearest-neighbour both ways, precision over
reconstructed voxels, recall over ROI-cropped ground-truth mesh points.

Usage:
    python3 f1_threshold_sweep.py                # auto-discovers the dumps
    python3 f1_threshold_sweep.py <run_dir> ...  # explicit dirs
"""
import glob
import os
import sys

import numpy as np
from scipy.spatial import KDTree

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
THRESHOLDS_MM = [2, 3, 4, 6, 8, 10, 12]      # 2 mm = Burusa's value


def score(voxels, roi_mesh, half):
    """Exactly planner_eval_mixin.calculate_F1's TP/FP/FN convention."""
    if len(voxels) == 0 or len(roi_mesh) == 0:
        return 0.0, 0.0, 0.0, 0, 0, 0
    d_tp, _ = KDTree(roi_mesh).query(voxels, k=1, p=np.inf)
    nr_correct = int(np.sum(d_tp <= half))
    d_rec, _ = KDTree(voxels).query(roi_mesh, k=1, p=np.inf)
    nr_recalled = int(np.sum(d_rec <= half))
    precision = nr_correct / len(voxels)
    recall = nr_recalled / len(roi_mesh)
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall > 0 else 0.0)
    return f1, recall, precision, nr_correct, len(voxels) - nr_correct, len(roi_mesh) - nr_recalled


def load(path):
    d = np.load(path)
    n = int(d["n_iters"])
    snaps = [d[f"v{i:02d}"] for i in range(n)]
    mesh, target, roi_half = d["mesh"], d["target"], float(d["roi_half"])
    roi_mesh = mesh[np.all(np.abs(mesh - target) <= roi_half, axis=1)]
    return snaps, roi_mesh, roi_half, float(d["f1_thresh"]), float(d["voxel_size"])


def label_of(run_dir):
    b = os.path.basename(run_dir.rstrip("/"))
    lvl = "fruit" if "fruit" in b else "all" if "_all_" in b else "?"
    pl = ("GradientNBV" if "Gradient" in b else
          "RH-NBV" if "K10_H3" in b or "rh" in b.lower() else
          "Random" if "Random" in b else "PSO" if "PSO" in b else "?")
    return lvl, pl


def main(dirs):
    if not dirs:
        dirs = sorted({os.path.dirname(os.path.dirname(p))
                       for p in glob.glob(os.path.join(RESULTS, "*", "trial_*", "f1_sweep_dump.npz"))})
    if not dirs:
        sys.exit("no f1_sweep_dump.npz found under results/ — are the runs finished?")

    rows = {}
    for rd in dirs:
        hits = glob.glob(os.path.join(rd, "trial_*", "f1_sweep_dump.npz"))
        if not hits:
            continue
        snaps, roi_mesh, roi_half, thr_run, vox = load(hits[0])
        lvl, pl = label_of(rd)
        final = snaps[-1] if snaps else np.zeros((0, 3))
        print(f"\n### {lvl:6s} {pl:8s}  {os.path.basename(rd)}")
        print(f"    {len(snaps)} iterasyon · son adımda {len(final):,} hedef voxel · "
              f"ROI içi GT {len(roi_mesh):,} nokta · koşu eşiği {thr_run*1000:.0f} mm · voxel {vox*1000:.0f} mm")
        print(f"    {'eşik':>6s} {'F1':>7s} {'recall':>8s} {'prec':>8s} {'TP':>7s} {'FP':>7s} {'FN':>7s}")
        per_thr = {}
        for t in THRESHOLDS_MM:
            f1, rec, prec, tp, fp, fn = score(final, roi_mesh, t / 1000.0)
            mark = "  <- koşu eşiği" if abs(t / 1000.0 - thr_run) < 1e-9 else ""
            print(f"    {t:4d}mm {f1:7.4f} {rec:8.4f} {prec:8.4f} {tp:7d} {fp:7d} {fn:7d}{mark}")
            per_thr[t] = f1
        rows[(lvl, pl)] = per_thr

    levels = sorted({k[0] for k in rows})
    for lvl in levels:
        pls = [p for (l, p) in rows if l == lvl]
        if len(pls) < 2:
            continue
        print(f"\n=== {lvl}: eşik düştükçe planlayıcılar ayrışıyor mu? ===")
        head = "  ".join(f"{p:>9s}" for p in pls)
        print(f"    {'eşik':>6s}  {head}     fark")
        for t in THRESHOLDS_MM:
            vals = [rows[(lvl, p)][t] for p in pls]
            body = "  ".join(f"{v:9.4f}" for v in vals)
            print(f"    {t:4d}mm  {body}   {max(vals)-min(vals):+.4f}")


if __name__ == "__main__":
    main(sys.argv[1:])
