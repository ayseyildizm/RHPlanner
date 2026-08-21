#!/usr/bin/env python3
"""Figures for the 'secondary metrics' section.

Form follows the job:
  fig1  two distributions compared        -> range bars, not a scatter
  fig2  cost against benefit per planner  -> 4 aggregated points, direct labels
  fig3  agreement between two metrics     -> scatter, single colour (the
                                             relationship is the message,
                                             planner identity is not)
Separate from plots.py, own filenames.
"""
import glob, json, os, re, statistics as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RH     = os.path.dirname(os.path.abspath(__file__))
OUT    = os.path.join(RH, "figures_secondary")
THESIS = os.path.expanduser("~/Downloads/LaTeX_thesis_template_draft/figures")
ROOTS = {
    "bunny": [os.path.join(RH, "results"),
              *[os.path.expanduser(f"~/Desktop/BUNNY/{p}") for p in ("GradientNBV","RH","PSO","Random")],
              *[os.path.expanduser(f"~/Downloads/BUNNY/{p}") for p in ("RH","GradientNBV")]],
    "mug":   [os.path.expanduser(f"~/Desktop/MUG/{p}") for p in ("GradientNBV","RH","PSO","Random")],
}
RUN_RE = re.compile(r"run_(\d{8}_\d{6})_expC_(none|panels\d+)_(GradientNBV|K10_H3_box|PSO|Random)$")
NAME   = {"GradientNBV":"GradientNBV","K10_H3_box":"RH-NBV","PSO":"PSO","Random":"Random"}
ORDER  = ["RH-NBV", "GradientNBV", "PSO", "Random"]
COLOR  = {"RH-NBV":"#009E73","GradientNBV":"#D55E00","PSO":"#0072B2","Random":"#CC79A7"}
MARKER = {"RH-NBV":"o","GradientNBV":"s","PSO":"^","Random":"D"}
INK, MUTED = "#1a1a1a", "#6b6b6b"

def load():
    rows = []
    for obj, roots in ROOTS.items():
        for root in roots:
            for run in glob.glob(os.path.join(root, "run_*")):
                m = RUN_RE.match(os.path.basename(run))
                if not m: continue
                for mf in glob.glob(os.path.join(run, "trial_*", "metrics_*.json")):
                    try: j = json.load(open(mf))
                    except Exception: continue
                    rows.append(dict(planner=NAME[m.group(3)], obj=obj, stage=m.group(2),
                        f1=j.get("final_f1"), cov=j.get("final_coverage"),
                        dist=j.get("final_distance"), cham=j.get("chamfer_distance"),
                        prec=(j.get("precisions") or [None])[-1],
                        rec=(j.get("recalls") or [None])[-1]))
    return rows

def clean(ax):
    ax.grid(True, axis="both", linewidth=0.4, alpha=0.3); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9)
    for s in ("left", "bottom"): ax.spines[s].set_color(MUTED)

def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name + ".pdf")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    if os.path.isdir(THESIS):
        import shutil; shutil.copy(p, THESIS)
    print("wrote", p)

def q(v, p): 
    v = sorted(v); k = (len(v)-1)*p; f = int(k)
    return v[f] if f+1 >= len(v) else v[f] + (k-f)*(v[f+1]-v[f])

# ------------------------------------------------------------- helpers
def med_by_planner(rows, key, pred=None):
    out = {}
    for pl in ORDER:
        v = [x[key] for x in rows if x["planner"] == pl and x[key] is not None
             and (pred is None or pred(x))]
        if v: out[pl] = st.median(v)
    return out

def bars(ax, vals, title, fmt, ylabel):
    xs = [p for p in ORDER if p in vals]
    ys = [vals[p] for p in xs]
    b = ax.bar(range(len(xs)), ys, width=.62,
               color=[COLOR[p] for p in xs], zorder=3)
    for rect, y in zip(b, ys):
        ax.text(rect.get_x() + rect.get_width()/2, y, fmt.format(y),
                ha="center", va="bottom", fontsize=9, color=INK, zorder=4)
    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels([x.replace("GradientNBV", "Gradient") for x in xs],
                       fontsize=9, color=INK)
    ax.set_ylabel(ylabel, color=INK, fontsize=9)
    ax.set_title(title, fontsize=10, color=INK, loc="left", pad=6)
    ax.set_ylim(0, max(ys) * 1.22)
    clean(ax); ax.grid(axis="x", visible=False)

# ---------------------------------------------------------------- figure 1
def fig_precision_recall(rows):
    r = [x for x in rows if x["prec"] is not None and x["rec"] is not None
         and not (x["prec"] == 0 and x["rec"] == 0)]
    xs = [p for p in ORDER if any(x["planner"] == p for x in r)]
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    w = .36
    for k, (key, lab, col) in enumerate((("prec", "Precision", "#7a7a7a"),
                                         ("rec", "Recall", "#0072B2"))):
        med, lo, hi = [], [], []
        for pl in xs:
            v = [x[key] for x in r if x["planner"] == pl]
            m = st.median(v); med.append(m)
            lo.append(m - q(v, .05)); hi.append(q(v, .95) - m)
        pos = [i + (k - .5) * w for i in range(len(xs))]
        ax.bar(pos, med, width=w, color=col, label=lab, zorder=3)
        ax.errorbar(pos, med, yerr=[lo, hi], fmt="none", ecolor=INK,
                    elinewidth=1.1, capsize=4, capthick=1.1, zorder=4)
        for x_, m_, h_ in zip(pos, med, hi):
            ax.text(x_, m_ + h_ + .03, f"{m_:.2f}", ha="center", va="bottom",
                    fontsize=9, color=INK, zorder=5)
    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels([x.replace("GradientNBV", "Gradient") for x in xs],
                       fontsize=9, color=INK)
    ax.set_ylim(0, 1.22); ax.set_yticks([0, .25, .5, .75, 1.0])
    ax.set_ylabel("Value at the final viewpoint", color=INK, fontsize=9)
    ax.legend(frameon=False, fontsize=9, ncol=2, loc="upper center",
              bbox_to_anchor=(.5, 1.12))
    clean(ax); ax.grid(axis="x", visible=False)
    save(fig, "sec_precision_recall"); print("  fig1 n =", len(r))

# ---------------------------------------------------------------- figure 2
def fig_cost_benefit(rows):
    r = [x for x in rows if x["dist"] and x["cov"] is not None and x["dist"] > 0]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.4, 3.3))
    bars(a1, med_by_planner(r, "cov"), "Coverage reached", "{:.0f}",
         "Median final ROI coverage (%)")
    bars(a2, med_by_planner(r, "dist"), "Distance travelled for it", "{:.2f}",
         "Median executed path (m)")
    fig.tight_layout()
    save(fig, "sec_cost_coverage"); print("  fig2 n =", len(r))

# ---------------------------------------------------------------- figure 3
def fig_f1_chamfer(rows):
    r = [x for x in rows if x["f1"] and x["cham"]]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.4, 3.3))
    bars(a1, med_by_planner(r, "f1"), "With a threshold", "{:.2f}",
         "Median final $F_1$")
    bars(a2, med_by_planner(r, "cham"), "Without one", "{:.3f}",
         "Median Chamfer distance (m)")
    a2.invert_yaxis(); a2.set_ylim(max(med_by_planner(r, "cham").values())*1.35, 0)
    fig.tight_layout()
    save(fig, "sec_f1_chamfer"); print("  fig3 n =", len(r))

def main():
    rows = load(); print(f"{len(rows)} runs loaded")
    plt.rcParams["text.usetex"] = False
    fig_precision_recall(rows); fig_cost_benefit(rows); fig_f1_chamfer(rows)

if __name__ == "__main__":
    main()
