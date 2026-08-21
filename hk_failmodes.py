#!/usr/bin/env python3
"""hk_failmodes.py — classify why commanded arm motions failed in a run.

Two mechanisms were identified on 2026-07-28 and they mean different things
for the thesis:

  A  goal infeasible  -- OMPL cannot sample a valid goal state ("Unable to
     sample any valid states for goal tree" / "Insufficient states in
     sampleable goal region"): the commanded pose has no collision-free IK
     solution. Deterministic property of the pose, i.e. planner behaviour.
  B  execution abort  -- the trajectory was planned and started, then the
     controller aborted it on a joint tracking-tolerance violation. A
     simulation-load artefact, not a planning error.
  C  other planning failure -- planning failed without the goal-sampling
     signature (e.g. no collision-free path from the start state).

Usage:
    python3 hk_failmodes.py <planner.log> <stack.log>
    python3 hk_failmodes.py --tag lam0          # uses the snapshot pair
"""
import math
import re
import sys
import os

LOGS = os.path.expanduser("~/Desktop/RecedingHorizon/results/_explogs")
BASE = (0.0, 0.0, 0.525)

POSE = re.compile(
    r"Requesting move to pose:.*?x=([-\d.e]+), y=([-\d.e]+), z=([-\d.e]+)")
STAMP = re.compile(r"\[(?:INFO|ERROR|WARN)\] \[(\d+\.\d+)\]")
GOAL_INFEASIBLE = ("Unable to sample any valid states for goal tree",
                   "Insufficient states in sampleable goal region")
EXEC_ABORT = ("State tolerances failed", "Aborted due to state tolerance")


def parse_planner(path):
    """[(t, (x,y,z), ok)] in command order."""
    out, pending, tstamp = [], None, None
    for line in open(path, errors="ignore"):
        m = POSE.search(line)
        if m:
            ts = STAMP.search(line)
            tstamp = float(ts.group(1)) if ts else None
            pending = tuple(float(v) for v in m.groups())
            continue
        if pending is None:
            continue
        if "Arm arrived at pose" in line:
            out.append((tstamp, pending, True))
            pending = None
        elif "Arm motion failed" in line:
            ts = STAMP.search(line)
            out.append((float(ts.group(1)) if ts else tstamp, pending, False))
            pending = None
    return out


def classify(stack_path, t0, t1):
    """Which failure signature appears in the stack log within (t0, t1]."""
    hit = "C other planning failure"
    for line in open(stack_path, errors="ignore"):
        ts = STAMP.search(line)
        if not ts:
            continue
        t = float(ts.group(1))
        if not (t0 < t <= t1):
            continue
        if any(s in line for s in GOAL_INFEASIBLE):
            return "A goal infeasible"
        if any(s in line for s in EXEC_ABORT):
            hit = "B execution abort"
    return hit


def main():
    if sys.argv[1:2] == ["--tag"]:
        tag = sys.argv[2]
        planner = os.path.join(LOGS, f"hk2_live_{tag}.log")
        stack = os.path.join(LOGS, f"hk2_stack_{tag}.log")
    else:
        planner, stack = sys.argv[1], sys.argv[2]

    moves = parse_planner(planner)
    ok = sum(1 for _, _, s in moves if s)
    print(f"{os.path.basename(planner)}: {ok}/{len(moves)} motions executed")

    counts, prev_t = {}, 0.0
    for t, pos, success in moves:
        r = math.dist(pos, BASE)
        if success:
            prev_t = t or prev_t
            continue
        mode = classify(stack, prev_t, t) if t else "C other planning failure"
        counts[mode] = counts.get(mode, 0) + 1
        print(f"  FAIL pos=({pos[0]:+.3f},{pos[1]:+.3f},{pos[2]:.3f}) "
              f"r_base={r:.3f}  -> {mode}")
        prev_t = t or prev_t

    okr = [math.dist(p, BASE) for _, p, s in moves if s]
    badr = [math.dist(p, BASE) for _, p, s in moves if not s]
    if okr and badr:
        print(f"  r_base executed: {min(okr):.2f}-{max(okr):.2f} | "
              f"refused: {min(badr):.2f}-{max(badr):.2f}")
    for mode, n in sorted(counts.items()):
        print(f"  {mode}: {n}")


if __name__ == "__main__":
    main()
