#!/usr/bin/env python3
"""
plot_candidates_thesis.py — thesis-quality figures of the RH-NBV search,
drawn from a candidates_data_<occ>.npz written by plots/candidate_dump.py.

The stock candidate plots frame the whole scene, so the plant fills the axes
and the planning itself collapses into a small tangle in one corner. These
figures instead frame the camera workspace: the axes are fitted to the
candidate sequences, and the plant is kept only as a faint silhouette for
context.

Produces
    rh_candidates_iter<N>.png   one planning iteration in detail
    rh_candidates_iters.png     the same run across several iterations

Usage
    python3 plot_candidates_thesis.py <candidates_data_*.npz> \
        [--out DIR] [--iter N] [--iters 0 1 2 3] [--elev 22] [--azim -60]
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers 3d projection)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plots.candidate_dump import load  # noqa: E402

# Kept consistent with the other RH figures in the thesis.
C_SELECTED = "#1a7f37"
C_EXECUTED = "#c0392b"
C_REJECTED = "#9e9e9e"
C_PLANT = "#c8c8c8"
C_TARGET = "#1f4e9c"


def _limits(iters, idxs, pad=0.08):
    """Axis limits that frame the candidate sequences, with a margin."""
    pts = []
    for i in idxs:
        pts.append(np.asarray(iters[i]["sequences"]).reshape(-1, 3))
        pts.append(np.asarray(iters[i]["start_pos"]).reshape(1, 3))
    pts = np.vstack(pts)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    span = np.maximum(hi - lo, 1e-3).max()          # one cube, so angles stay true
    mid = (lo + hi) / 2.0
    half = span * (0.5 + pad)
    return mid - half, mid + half


def _draw(ax, it, mesh, lo, hi, target=None, label_axes=True):
    seqs = np.asarray(it["sequences"])
    start = np.asarray(it["start_pos"]).ravel()
    best = int(it["best_idx"])
    K = seqs.shape[0]

    # plant, only what falls inside the frame, as background context
    if mesh is not None and len(mesh):
        m = np.asarray(mesh)
        inside = np.all((m >= lo) & (m <= hi), axis=1)
        if inside.any():
            sub = m[inside]
            if len(sub) > 4000:
                sub = sub[np.random.default_rng(0).choice(len(sub), 4000, False)]
            ax.scatter(sub[:, 0], sub[:, 1], sub[:, 2], s=0.7,
                       c=C_PLANT, alpha=0.55, linewidths=0, depthshade=False)

    # rejected candidate sequences
    for k in range(K):
        if k == best:
            continue
        path = np.vstack([start, seqs[k]])
        ax.plot(path[:, 0], path[:, 1], path[:, 2], color=C_REJECTED,
                lw=0.9, ls="--", alpha=0.75, zorder=2)
        ax.scatter(seqs[k][:, 0], seqs[k][:, 1], seqs[k][:, 2], s=9,
                   c=C_REJECTED, alpha=0.8, linewidths=0, depthshade=False,
                   zorder=2)

    # The selected sequence, split so the figure says which part is real:
    # the first edge is executed, everything after it is thrown away.
    if len(seqs[best]) > 1:
        planned = seqs[best]
        ax.plot(planned[:, 0], planned[:, 1], planned[:, 2], color=C_SELECTED,
                lw=2.0, zorder=4)
        ax.scatter(planned[1:, 0], planned[1:, 1], planned[1:, 2], s=30,
                   c=C_SELECTED, edgecolors="white", linewidths=0.6,
                   depthshade=False, zorder=5)
    # drawn after the planned tail so the committed edge stays on top
    executed = np.vstack([start, seqs[best][0]])
    ax.plot(executed[:, 0], executed[:, 1], executed[:, 2], color=C_EXECUTED,
            lw=3.4, solid_capstyle="round", zorder=6)

    # where the planner started, and the one viewpoint it commits to
    ax.scatter(*start, s=90, marker="s", c="white", edgecolors="black",
               linewidths=1.5, depthshade=False, zorder=7)
    ax.scatter(*seqs[best][0], s=260, marker="*", c=C_EXECUTED,
               edgecolors="white", linewidths=0.8, depthshade=False, zorder=8)

    if target is not None:
        t = np.asarray(target).ravel()
        if np.all((t >= lo) & (t <= hi)):
            ax.scatter(*t, s=70, marker="X", c=C_TARGET, depthshade=False,
                       zorder=6)

    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect((1, 1, 1))
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_tick_params(labelsize=7)
    if label_axes:
        ax.set_xlabel("X (m)", fontsize=8, labelpad=1)
        ax.set_ylabel("Y (m)", fontsize=8, labelpad=1)
        ax.set_zlabel("Z (m)", fontsize=8, labelpad=1)
    ax.grid(True, alpha=0.25)
    return K


def _legend_handles(K):
    import matplotlib.lines as mlines
    return [
        mlines.Line2D([], [], color="none", marker="s", markerfacecolor="white",
                      markeredgecolor="black", markersize=8,
                      label="current viewpoint"),
        mlines.Line2D([], [], color=C_REJECTED, ls="--", marker="o",
                      markersize=4, label=f"rejected ({K - 1} sequences)"),
        mlines.Line2D([], [], color=C_EXECUTED, lw=3.0,
                      label="executed step"),
        mlines.Line2D([], [], color=C_SELECTED, lw=2.0, marker="o",
                      markersize=5, label="planned, discarded"),
        mlines.Line2D([], [], color="none", marker="*",
                      markerfacecolor=C_EXECUTED, markeredgecolor="white",
                      markersize=14, label="next viewpoint"),
    ]


def plot_single(iters, extra, it_idx, out_path, elev=22, azim=-60):
    lo, hi = _limits(iters, [it_idx])
    fig = plt.figure(figsize=(5.4, 4.8))
    ax = fig.add_subplot(111, projection="3d")
    ax.view_init(elev=elev, azim=azim)
    K = _draw(ax, iters[it_idx], extra.get("mesh"), lo, hi, extra.get("target"))
    H = np.asarray(iters[it_idx]["sequences"]).shape[1]
    ax.set_title(f"Planning iteration {it_idx}   ($K={K}$, $H={H}$)",
                 fontsize=9.5, pad=0)
    fig.legend(handles=_legend_handles(K), loc="lower center", ncol=3,
               fontsize=8, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out_path)


def plot_row(iters, extra, idxs, out_path, elev=22, azim=-60):
    # one shared frame, so the viewpoint drift between iterations is readable
    lo, hi = _limits(iters, idxs)
    fig = plt.figure(figsize=(2.9 * len(idxs), 3.3))
    K = None
    for j, i in enumerate(idxs):
        ax = fig.add_subplot(1, len(idxs), j + 1, projection="3d")
        ax.view_init(elev=elev, azim=azim)
        K = _draw(ax, iters[i], extra.get("mesh"), lo, hi, extra.get("target"),
                  label_axes=(j == 0))
        ax.set_title(f"Iteration {i}", fontsize=9.5, pad=0)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.97, bottom=0.14,
                        wspace=0.02)
    fig.legend(handles=_legend_handles(K), loc="lower center", ncol=5,
               fontsize=8, frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("--out", default=None, help="output directory")
    ap.add_argument("--iter", type=int, default=2)
    ap.add_argument("--iters", type=int, nargs="+", default=[0, 1, 2, 3])
    ap.add_argument("--elev", type=float, default=22)
    ap.add_argument("--azim", type=float, default=-60)
    a = ap.parse_args()

    iters, extra = load(a.npz)
    out = a.out or os.path.dirname(os.path.abspath(a.npz))
    os.makedirs(out, exist_ok=True)
    print(f"{len(iters)} iterations in {a.npz}")

    it_idx = min(a.iter, len(iters) - 1)
    idxs = [i for i in a.iters if i < len(iters)] or [0]

    plot_single(iters, extra, it_idx,
                os.path.join(out, f"rh_candidates_iter{it_idx}.png"),
                a.elev, a.azim)
    plot_row(iters, extra, idxs,
             os.path.join(out, "rh_candidates_iters.png"), a.elev, a.azim)


if __name__ == "__main__":
    main()
