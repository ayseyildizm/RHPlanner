#!/usr/bin/env python3
"""analyze_lamprobe.py — read a lambda probe and report the flip weight.

Each candidate sequence has a discounted gain G and a discounted motion cost C,
and the planner picks the candidate maximising G - lambda*C. Raising lambda can
only change the winner when a rival has both lower gain and lower cost; the
crossing point for that rival is

    lambda* = (G_win - G_rival) / (C_win - C_rival)

and the smallest positive crossing over all rivals is the weight at which this
iteration's decision would first change. The largest of those over the run is
the weight at which the planner's whole trajectory would change.

    python3 analyze_lamprobe.py [results/_lamprobe/lamprobe_*.json]
"""
import glob
import json
import statistics as st
import sys


def flip_lambda(cands, lam):
    """Weights nearest to lam that change the winner of this iteration.

    Returns (up, down): the smallest weight above lam and the largest weight
    below it at which some rival overtakes the winner. Raising lambda promotes
    rivals that are cheaper to reach, lowering it promotes rivals that are more
    expensive but higher-gain, so both directions have to be reported: the
    thesis argument rests on lambda=0 and lambda=2 selecting the same
    viewpoints, which is a claim about the downward direction.
    """
    if len(cands) < 2:
        return None, None
    scored = [(c["gain"] - lam * c["cost"], c) for c in cands]
    _, win = max(scored, key=lambda t: t[0])
    up, down = [], []
    for c in cands:
        if c is win:
            continue
        dc = win["cost"] - c["cost"]
        if dc == 0:          # parallel scores: no crossing at any weight
            continue
        x = (win["gain"] - c["gain"]) / dc
        if dc > 0:           # rival is cheaper -> it wins once lambda exceeds x
            if x > lam:
                up.append(x)
        else:                # rival costs more -> it wins once lambda drops below x
            if 0 <= x < lam:  # a negative crossing would need a weight that
                down.append(x)  # rewards motion: not a runnable setting
    return (min(up) if up else None), (max(down) if down else None)


def main(path):
    d = json.load(open(path))
    lam = d["lambda_used"]
    print(f"probe: {path}")
    print(f"target={d['target']} occlusion={d['occlusion']} lambda={lam}\n")

    ups, downs, unflippable = [], [], 0
    for i, cands in enumerate(d["iterations"], start=1):
        if not cands:
            continue
        g = [c["gain"] for c in cands]
        c_ = [c["cost"] for c in cands]
        up, down = flip_lambda(cands, lam)
        if up is None and down is None:
            unflippable += 1
        if up is not None:
            ups.append(up)
        if down is not None:
            downs.append(down)
        print("iter %2d  K=%2d  gain %8.2f..%-8.2f (spread %7.2f)  "
              "cost %6.3f..%-6.3f (spread %6.3f)  flips at %s / %s"
              % (i, len(cands), min(g), max(g), max(g) - min(g),
                 min(c_), max(c_), max(c_) - min(c_),
                 "%.2f" % up if up else "  none",
                 "%.2f" % down if down else "none"))

    print("\n(flips at UP / DOWN = nearest weight above / below lambda=%g at "
          "which this iteration's winner changes)" % lam)
    print()
    if ups:
        print("raising lambda:  first flip at %.2f (min over iterations), "
              "median %.2f, max %.2f" % (min(ups), st.median(ups), max(ups)))
        print("  -> lambda >= %.2f changes every iteration recorded" % max(ups))
    else:
        print("raising lambda: no iteration flips at any weight — the "
              "highest-gain candidate is also the cheapest to reach.")
    if downs:
        print("lowering lambda: first flip at %.2f (max over iterations), "
              "median %.2f, min %.2f" % (max(downs), st.median(downs),
                                         min(downs)))
    else:
        print("lowering lambda: no iteration flips at any weight down to 0 — "
              "consistent with the lambda=0 run tracking the lambda=%g run."
              % lam)
    if unflippable:
        print("%d iteration(s) cannot be flipped in either direction." %
              unflippable)
    if ups:
        print("\nsuggested sweep: lambda = %.0f and %.0f"
              % (st.median(ups), max(ups) * 2))


if __name__ == "__main__":
    args = sys.argv[1:] or sorted(glob.glob(
        "results/_lamprobe/lamprobe_*.json"))[-1:]
    if not args:
        sys.exit("no probe file found")
    main(args[0])
