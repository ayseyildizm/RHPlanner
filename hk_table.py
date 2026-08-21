#!/usr/bin/env python3
"""hk_table.py — H/K ablation summary (mug, panels3, RH-NBV).

Collects every H/K ablation trial on disk (frozen 07-07 baseline + the
abtest_* run dirs), applies the same validity gate used elsewhere in this
project (>=80% arm-move success and coverage[1] > 0), and prints a
per-configuration table with mean+-std over the valid trials.

New file; nothing else is touched.  Usage:
    python3 hk_table.py [--all-trials]
"""
import glob
import json
import os
import statistics as st
import sys

RESULTS = os.path.expanduser("~/Desktop/RecedingHorizon/results")
BASELINE_07 = os.path.expanduser(
    "~/Desktop/MUG/RH/run_20260707_180342_expC_panels3_K10_H3_box")

SHOW_ALL = "--all-trials" in sys.argv


def trials(run_dir):
    for t in sorted(glob.glob(os.path.join(run_dir, "trial_*"))):
        js = glob.glob(os.path.join(t, "metrics_*.json"))
        if js:
            yield os.path.basename(t), json.load(open(js[0]))


def row(d):
    cov = d["coverages"]
    occ = d.get("occluded_recall_series") or [0]
    # The frozen 07-07 baseline predates the move-tracking fields; its move
    # success (20/20) is only in the run log, so the gate can only check data.
    rate = d.get("move_success_rate")
    total = d.get("total_moves", d["num_iters"])
    # coverage[1] == 0 was introduced to catch runs whose camera bridge never
    # delivered frames (the whole curve stays flat). It also fires when the
    # first commanded motion simply failed: the camera never left its start
    # pose, so view 1 sees nothing while the rest of the run is fine. Only the
    # former is a dead run, so check the first motion before condemning it.
    succ = d.get("move_successes")
    first_move_failed = bool(succ) and not succ[0]
    dead = len(cov) > 1 and cov[1] == 0 and not first_move_failed
    if first_move_failed and len(cov) > 2:
        dead = max(cov[1:3]) == 0        # still nothing by view 2 -> dead
    valid = (not dead) and (rate is None or rate >= 80.0)
    if rate is None:
        moves = "n/a"
    else:
        moves = f"{int(round(rate * total / 100))}/{total}"
    return {
        "H": d["params"]["horizon"],
        "K": d["params"]["num_candidates"],
        "lam": d["params"]["lambda_cost"],
        "cov": d["final_coverage"],
        "f1": d["final_f1"],
        "auc": d["coverage_auc"],
        "occrec": occ[-1],
        "dist": d["final_distance"],
        "moves": moves,
        "moverate": rate,
        "firstf1": d["views_to_f1_threshold"],
        "time": d["total_time"],
        "valid": valid,
    }


def collect():
    runs = [("baseline-0707", BASELINE_07)]
    for p in sorted(glob.glob(os.path.join(RESULTS, "abtest_H*K*_run_*panels3*"))):
        tag = os.path.basename(p).split("_run_")[0].replace("abtest_", "")
        runs.append((tag, p))
    for p in sorted(glob.glob(os.path.join(RESULTS, "abtest_ikfilter_run_*panels3*"))):
        runs.append(("ikfilter", p))
    for p in sorted(glob.glob(os.path.join(RESULTS, "abtest_lam*_run_*panels3*"))):
        tag = os.path.basename(p).split("_run_")[0].replace("abtest_", "")
        runs.append((tag, p))
    out = []
    for tag, path in runs:
        if not os.path.isdir(path):
            continue
        for tname, d in trials(path):
            r = row(d)
            r["tag"], r["run"], r["trial"] = tag, os.path.basename(path), tname
            out.append(r)
    return out


def fmt(vals, prec):
    if not vals:
        return "--"
    if len(vals) == 1:
        return f"{vals[0]:.{prec}f}"
    return f"{st.mean(vals):.{prec}f}+-{st.stdev(vals):.{prec}f}"


def main():
    rows = collect()
    if not rows:
        print("no runs found")
        return

    print("\n== per-trial ==")
    hdr = ("tag", "trial", "H", "K", "lam", "cov%", "F1", "AUC", "OccRec",
           "dist", "moves", "1stF1", "time_s", "valid")
    print(f"{hdr[0]:<14}{hdr[1]:<9}{hdr[2]:<3}{hdr[3]:<4}{hdr[4]:<5}"
          f"{hdr[5]:>7}{hdr[6]:>7}{hdr[7]:>7}{hdr[8]:>8}{hdr[9]:>7}"
          f"{hdr[10]:>8}{hdr[11]:>7}{hdr[12]:>9}  {hdr[13]}")
    for r in rows:
        print(f"{r['tag']:<14}{r['trial']:<9}{r['H']:<3}{r['K']:<4}{r['lam']:<5}"
              f"{r['cov']:>7.2f}{r['f1']:>7.3f}{r['auc']:>7.1f}{r['occrec']:>8.3f}"
              f"{r['dist']:>7.2f}{r['moves']:>8}{str(r['firstf1']):>7}"
              f"{r['time']:>9.0f}  {'OK' if r['valid'] else 'INVALID'}")

    print("\n== per-configuration (valid trials only, mean+-std) ==")
    keys = {}
    for r in rows:
        if not (r["valid"] or SHOW_ALL):
            continue
        keys.setdefault((r["H"], r["K"], r["lam"]), []).append(r)
    print(f"{'H':<3}{'K':<4}{'lam':<5}{'n':<3}{'cov%':>14}{'F1':>14}{'AUC':>14}"
          f"{'OccRec':>14}{'dist_m':>14}")
    for (h, k, lam), rs in sorted(keys.items()):
        print(f"{h:<3}{k:<4}{lam:<5}{len(rs):<3}"
              f"{fmt([x['cov'] for x in rs], 2):>14}"
              f"{fmt([x['f1'] for x in rs], 3):>14}"
              f"{fmt([x['auc'] for x in rs], 1):>14}"
              f"{fmt([x['occrec'] for x in rs], 3):>14}"
              f"{fmt([x['dist'] for x in rs], 2):>14}")

    bad = [r for r in rows if not r["valid"]]
    if bad:
        print("\nexcluded by the gate (>=80% moves, coverage[1]>0):")
        for r in bad:
            print(f"  {r['tag']}/{r['trial']}: moves {r['moves']} "
                  f"({r["moverate"] if r["moverate"] is not None else -1:.0f}%)  -> {r['run']}")


if __name__ == "__main__":
    main()
