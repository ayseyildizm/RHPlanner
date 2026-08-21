#!/usr/bin/env python3
"""
analyze_bunny_results.py — 4-planner panel-ladder table.

Aggregates over ALL trials of the chosen run (mean +- std, n reported).
Use --agg trial0 to reproduce the old trial_00-only numbers.

Usage:
    python3 analyze_bunny_results.py
    python3 analyze_bunny_results.py --target mug
    python3 analyze_bunny_results.py --occ panels8 --agg trial0
"""
import argparse
import glob
import json
import os
import re
from collections import defaultdict

import numpy as np

RH_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_ROOTS = {
    "bunny": [
        (os.path.join(RH_DIR, "results"), "new"),
        (os.path.expanduser("~/Desktop/BUNNY/GradientNBV"), "prev"),
        (os.path.expanduser("~/Desktop/BUNNY/RH"), "prev"),
        (os.path.expanduser("~/Desktop/BUNNY/PSO"), "prev"),
        (os.path.expanduser("~/Desktop/BUNNY/Random"), "prev"),
        (os.path.expanduser("~/Downloads/BUNNY/RH"), "prev"),
        (os.path.expanduser("~/Downloads/BUNNY/GradientNBV"), "prev"),
    ],
    "mug": [
        (os.path.expanduser("~/Desktop/MUG/GradientNBV"), "prev"),
        (os.path.expanduser("~/Desktop/MUG/RH"), "prev"),
        (os.path.expanduser("~/Desktop/MUG/PSO"), "prev"),
        (os.path.expanduser("~/Desktop/MUG/Random"), "prev"),
    ],
}
RUN_RE = re.compile(
    r"run_(\d{8}_\d{6})_expC_(none|panels\d+)_(GradientNBV|K10_H3_box|PSO|Random)$")
PLANNER_NAME = {"GradientNBV": "GradientNBV", "K10_H3_box": "RH-NBV",
                "PSO": "PSO", "Random": "Random"}
PLANNER_ORDER = ["GradientNBV", "RH-NBV", "PSO", "Random"]
OCC_ORDER = ["none", "panels1", "panels2", "panels3", "panels4", "panels5",
             "panels6", "panels8"]


PROGRESS_LOG = os.path.join(RH_DIR, "results", "_explogs", "ladder4_progress.log")
LOG_PLANNER = {"rh": "K10_H3_box", "gradient": "GradientNBV",
               "pso": "PSO", "random": "Random"}
BATCH_RE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\] === LADDER4 START .*target: (\w+)\)")
START_RE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\] START (none|panels\d+) (\w+) ")


def resolve_targets():
    """Map results/ run dirs to the target they ran against.

    Run dir names carry no target, so bunny and mug ladder runs are
    indistinguishable by name. ladder4_progress.log records the target per
    batch but timestamps only carry a clock time, so dates are reconstructed
    by rollover and anchored to whichever start date best fits the run dirs.
    """
    import datetime as dt

    if not os.path.exists(PROGRESS_LOG):
        return {}
    entries, target = [], None
    with open(PROGRESS_LOG) as f:
        for line in f:
            mb = BATCH_RE.match(line)
            if mb:
                target = mb.group(4)
                continue
            ms = START_RE.match(line)
            if ms and target:
                h, m, s = (int(x) for x in ms.groups()[:3])
                planner = LOG_PLANNER.get(ms.group(5))
                if planner:
                    entries.append([h * 3600 + m * 60 + s, ms.group(4), planner, target])
    if not entries:
        return {}

    dirs = []
    for d in glob.glob(os.path.join(RH_DIR, "results", "run_*")):
        mo = RUN_RE.search(os.path.basename(d))
        if mo:
            ts, occ, planner = mo.groups()
            dirs.append((dt.datetime.strptime(ts, "%Y%m%d_%H%M%S"), occ, planner,
                         os.path.basename(d)))
    if not dirs:
        return {}

    offsets, day, prev = [], 0, None
    for secs, _, _, _ in entries:
        if prev is not None and secs < prev:
            day += 1
        prev = secs
        offsets.append(day)

    votes = defaultdict(int)
    for (secs, occ, planner, _), off in zip(entries, offsets):
        for rt, rocc, rplanner, _ in dirs:
            if rocc != occ or rplanner != planner:
                continue
            anchor = rt - dt.timedelta(days=off, seconds=secs)
            if 0 <= anchor.hour * 3600 + anchor.minute * 60 + anchor.second <= 3600:
                votes[anchor.date()] += 1
    if not votes:
        return {}
    best = max(votes, key=lambda d: (votes[d], d))

    base_day = dt.datetime.combine(best, dt.time())
    stamps = [(base_day + dt.timedelta(days=off, seconds=secs), occ, planner, tgt)
              for (secs, occ, planner, tgt), off in zip(entries, offsets)]

    resolved = {}
    for rt, rocc, rplanner, base in dirs:
        cands = [(rt - w).total_seconds() for w, o, p, _ in stamps
                 if o == rocc and p == rplanner and 0 <= (rt - w).total_seconds() <= 3600]
        if not cands:
            continue
        gap = min(cands)
        for w, o, p, tgt in stamps:
            if o == rocc and p == rplanner and abs((rt - w).total_seconds() - gap) < 1:
                resolved[base] = tgt
                break
    return resolved


def views_to(cov, tau):
    for i, c in enumerate(cov):
        if c >= tau:
            return i
    return None


def gate(m):
    ms = m.get("move_successes")
    if ms and sum(ms) / len(ms) < 0.8:
        return False, f"moves {sum(ms)}/{len(ms)}"
    cov = m.get("coverages", [])
    if len(cov) > 1 and cov[1] == 0:
        return False, "no camera data at view 1"
    return True, ""


def no_eval(m):
    """True when calculate_F1 bailed out before scoring: tp=fp=fn=0 at the last
    view. Such trials report F1=0 and chamfer/hausdorff=None."""
    try:
        return (m["tp_series"][-1] == 0 and m["fp_series"][-1] == 0
                and m["fn_series"][-1] == 0)
    except (KeyError, IndexError):
        return False


def archive_names(target):
    names = set()
    for root, prov in TARGET_ROOTS[target]:
        if prov == "prev":
            names.update(os.path.basename(d)
                         for d in glob.glob(os.path.join(root, "run_*")))
    return names


def collect(roots, target):
    runs = defaultdict(list)
    seen = set()
    resolved = resolve_targets()
    foreign = set()
    for other in TARGET_ROOTS:
        if other != target:
            foreign |= archive_names(other)
    foreign -= archive_names(target)
    for root, prov in roots:
        for d in sorted(glob.glob(os.path.join(root, "run_*"))):
            base = os.path.basename(d)
            mo = RUN_RE.search(base)
            if not mo or base in seen:
                continue
            tag = prov
            if prov == "new":
                ran_on = resolved.get(base)
                if ran_on is None and base in foreign:
                    ran_on = "other"
                if ran_on is not None and ran_on != target:
                    continue
                tag = "new" if ran_on == target else "new?"
            ts, occ, planner = mo.groups()
            trials = []
            for mf in sorted(glob.glob(os.path.join(d, "trial_*", "metrics_*.json"))):
                try:
                    with open(mf) as f:
                        trials.append(json.load(f))
                except (json.JSONDecodeError, OSError) as e:
                    print(f"  !! unreadable metrics in {base}: {e}")
            if not trials:
                continue
            seen.add(base)
            runs[(occ, PLANNER_NAME[planner])].append((ts, tag, trials))
    for k in runs:
        runs[k].sort(key=lambda r: (r[1] != "new?", r[0]), reverse=True)
    return runs


def trial_row(m):
    cov = m["coverages"]
    ms = m.get("move_successes")
    return {
        "cov": m.get("final_coverage", cov[-1]),
        "f1": m.get("final_f1", m["f1_scores"][-1]),
        "recall": m["recalls"][-1],
        "precision": m["precisions"][-1],
        "auc": m.get("coverage_auc", float(np.trapz(cov, dx=1) / (len(cov) - 1))),
        "v80": views_to(cov, 80.0),
        "v90": views_to(cov, 90.0),
        "traj": m.get("final_distance", m["distances"][-1]),
        "moves": 100.0 * sum(ms) / len(ms) if ms else None,
    }


def aggregate(trials):
    rows = [trial_row(m) for m in trials]
    agg = {"n": len(rows)}
    for k in ("cov", "f1", "recall", "precision", "auc", "traj"):
        vals = [r[k] for r in rows if r[k] is not None]
        agg[k] = (float(np.mean(vals)), float(np.std(vals))) if vals else (float("nan"), 0.0)
    for k in ("v80", "v90"):
        vals = [r[k] for r in rows if r[k] is not None]
        agg[k] = float(np.mean(vals)) if len(vals) == len(rows) and vals else None
        agg[k + "_partial"] = 0 < len(vals) < len(rows)
    mv = [r["moves"] for r in rows if r["moves"] is not None]
    agg["moves"] = float(np.mean(mv)) if mv else None
    return agg


def fmt(a, note=""):
    def pm(key, w, d):
        mu, sd = a[key]
        s = f"{mu:.{d}f}" if a["n"] == 1 else f"{mu:.{d}f}±{sd:.{d}f}"
        return f"{s:>{w}}"

    def vt(key):
        v = a[key]
        if v is None:
            return "-*" if a[key + "_partial"] else "-"
        return f"{v:.0f}"

    mv = "n/a" if a["moves"] is None else f"{a['moves']:.0f}%"
    return (f"{pm('cov', 11, 1)} {pm('f1', 11, 3)} {pm('recall', 11, 3)} "
            f"{pm('auc', 11, 1)} {vt('v80'):>4} {vt('v90'):>4} "
            f"{pm('traj', 9, 2)} {mv:>5} {a['n']:>2}  {note}")


def select(runs, occ, planner, agg="mean"):
    """Pick the run for one table cell. Returns (ts, prov, trials, tags, gate_ok)
    or None. Verified runs outrank unverified ones even when they fail the gate;
    within a run only gate-passing trials are kept unless none pass."""
    cands = runs.get((occ, planner), [])
    if not cands:
        return None

    verified = [c for c in cands if c[1] != "new?"]
    if verified:
        cands = verified

    chosen, note, gate_ok = None, "", True
    for ts, prov, trials in cands:
        keep = [m for m in trials if gate(m)[0]]
        if keep:
            dropped = len(trials) - len(keep)
            chosen = (ts, prov, keep)
            note = f"{dropped} trial gate-failed" if dropped else ""
            break
    if chosen is None:
        ts, prov, trials = cands[0]
        chosen = (ts, prov, trials)
        note = f"GATE-FAILED ({gate(trials[0])[1]})"
        gate_ok = False
    ts, prov, trials = chosen

    if agg == "trial0":
        trials = trials[:1]

    tags = [t for t in [note] if t]
    n_bail = sum(no_eval(m) for m in trials)
    if n_bail:
        tags.append(f"NO-EVAL {n_bail}/{len(trials)} (tp=fp=fn=0)")
    if prov == "new?":
        tags.append("TARGET UNVERIFIED")
    tags.append(f"run {ts[:4]}-{ts[4:6]}-{ts[6:8]}")
    return ts, prov, trials, tags, gate_ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=sorted(TARGET_ROOTS), default="bunny")
    ap.add_argument("--occ", help="restrict to one scenario")
    ap.add_argument("--agg", choices=("mean", "trial0"), default="mean",
                    help="mean over all trials (default) or trial_00 only")
    args = ap.parse_args()

    runs = collect(TARGET_ROOTS[args.target], args.target)
    occs = [args.occ] if args.occ else OCC_ORDER

    label = "trial_00 only" if args.agg == "trial0" else "mean±std over trials"
    print(f"target={args.target}  aggregation={label}\n")
    hdr = (f"{'scenario':<9} {'planner':<12}{'cov%':>11} {'F1':>11} {'rec':>11} "
           f"{'AUC':>11} {'v80':>4} {'v90':>4} {'traj':>9} {'mv%':>5} {'n':>2}")
    print(hdr)
    print("-" * len(hdr))
    missing = []
    for occ in occs:
        for planner in PLANNER_ORDER:
            picked = select(runs, occ, planner, args.agg)
            if picked is None:
                missing.append((occ, planner))
                continue
            _, _, trials, tags, _ = picked
            print(f"{occ:<9} {planner:<12}{fmt(aggregate(trials), ' | '.join(tags))}")
        print()

    print("v80/v90: '-' never reached; '-*' reached in some trials only")
    print("NO-EVAL: calculate_F1 returned early (no target-class voxels); "
          "F1=0 is not a measured score and chamfer/hausdorff are null")

    if missing:
        print("\nMISSING (no run):")
        for occ, planner in missing:
            print(f"  {occ:<9} {planner}")


if __name__ == "__main__":
    main()
