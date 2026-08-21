#!/usr/bin/env python3
"""Compact reconstruction-evolution strip for the thesis.

Takes the per-view reconstruction PNGs that a run already wrote into
``trial_XX/reconstruction_per_iter/`` and stitches a selected subset into a
single row, so the 7x3 grid figure does not have to go into the thesis as is.
Nothing is re-rendered: the panels are crops of the produced pictures, and the
numbers under them come from the run's metrics json.

Usage:
  python3 plot_recon_evolution_strip.py                       # fruit y000 trial_01
  python3 plot_recon_evolution_strip.py --trial <dir> --views 1 3 5 9 10 20
"""
import argparse
import glob
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_TRIAL = os.path.expanduser(
    "~/Desktop/PLANT/RH/FRUIT/run_20260711_164843_expC_panels_tree_fruit_y000_K10_H3_box/trial_01"
)
FIGDIR = os.path.expanduser("~/Downloads/LaTeX_thesis_template_draft/figures")
L = {
    "en": dict(view="View", jump="pp", cov="coverage", vox="voxels",
               gt="Ground truth", gtvox="{n:,} voxels at {mm:.0f} mm",
               mesh="({n:,} mesh points)", gtsolo="Ground truth"),
    "tr": dict(view="Görünüm", jump="puan", cov="kapsama", vox="voksel",
               gt="Yer gerçeği", gtvox="{mm:.0f} mm vokselde\n{n:,} voksel",
               mesh="({n:,} mesh noktası)", gtsolo="Yer gerçeği"),
}

SCRATCH = "/tmp/claude-1000/-home-ayse/804d5c72-6411-430d-9079-4a6d8a9d013a/scratchpad"


def voxelized_gt_panel(occlusion, voxel_size, out_png, elev=20, azim=-60,
                       single=False, lang="en", target="auto", mode="surface"):
    """Draw the ground truth as voxels at the reconstruction's own resolution.

    The stock right-hand panel scatters raw COLLADA vertices while the left-hand
    panel shows 3 mm occupancy voxels, so the two sides are not in the same unit
    (the fruit mesh has ~1 mm vertex spacing, the mug mesh ~5.5 mm). gt_voxelize
    samples the triangle faces and voxelises those, which is the honest ceiling:
    quantising vertices alone undercounts the whole plant 4x and the mug 5x.

    Axis limits, view angle and marker size follow plots/plot_reconstruction.py,
    and the layout matches the produced frames so the same crop lands correctly.
    ``single=True`` writes one standalone axes instead.

    Returns (n_gt_voxels, n_mesh_points).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    import numpy as np
    import gt_voxelize as gv

    if target == "auto":
        # config.json does not record the object -- the occlusion string is just
        # "panels3" for both bunny and mug -- so a non-tree run must be named or
        # we would silently draw a tomato as some other object's ground truth.
        if "tree" not in occlusion:
            raise SystemExit(f"occlusion={occlusion!r} bir bitki koşusu değil; "
                             "nesneyi --target ile ver (mug | bunny).")
        target = ("fruit" if "fruit" in occlusion else
                  "all" if "_all_" in occlusion else "blossom")
    yaw = float(occlusion.rsplit("_y", 1)[1][:3]) if "_y" in occlusion else 0.0

    mesh, _ = gv.load_gt(target, yaw)
    centres, n_mesh, _ = gv.gt_voxels(target, yaw, voxel_size, mode=mode)

    fig = plt.figure(figsize=(7, 6) if single else (14, 6))
    if not single:
        fig.suptitle("Ground truth (voxelised)", fontsize=13, fontweight="bold", y=1.01)
    mid = mesh.mean(axis=0)
    span = max((mesh.max(axis=0) - mesh.min(axis=0)).max() / 2, 0.10)
    title = (f"Ground truth — {voxel_size*1000:.0f} mm voxels\n"
             f"({len(centres):,} voxels · {n_mesh:,} mesh points)" if lang == "en" else
             f"Yer gerçeği — {voxel_size*1000:.0f} mm voksel\n"
             f"({len(centres):,} voksel · {n_mesh:,} mesh noktası)")
    for pos in ((111,) if single else (121, 122)):
        ax = fig.add_subplot(pos, projection="3d")
        ax.view_init(elev=elev, azim=azim)
        ax.scatter(centres[:, 0], centres[:, 1], centres[:, 2],
                   c="red", s=1, alpha=0.6, rasterized=True)
        ax.set_title(title if single else "Voxelised Ground Truth",
                     fontsize=11, fontweight="bold")
        ax.set_xlabel("X (m)", fontsize=9)
        ax.set_ylabel("Y (m)", fontsize=9)
        ax.set_zlabel("Z (m)", fontsize=9)
        ax.set_xlim(mid[0] - span, mid[0] + span)
        ax.set_ylim(mid[1] - span, mid[1] + span)
        ax.set_zlim(mid[2] - span, mid[2] + span)
        ax.set_box_aspect([1, 1, 1])
    plt.tight_layout()
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return len(centres), n_mesh


def content_box(img, thresh=248):
    """Bounding box of everything that is not white, incl. the light axis panes."""
    a = np.asarray(img.convert("L"))
    rows = np.where(a.min(axis=1) < thresh)[0]
    cols = np.where(a.min(axis=0) < thresh)[0]
    return cols[0], rows[0], cols[-1] + 1, rows[-1] + 1


def panel_boxes(path, pad=12):
    """Crop boxes for the left (reconstruction) and right (ground truth) plot.

    The per-view PNG is a two-panel figure with a suptitle; we drop the text
    band at the top and keep one common box for every view so the 3D axes stay
    registered from cell to cell.
    """
    img = Image.open(path).convert("RGB")
    w, h = img.size
    top = int(h * 0.20)                      # below suptitle + per-axes titles
    left = img.crop((0, top, w // 2, h))
    x0, y0, x1, y1 = content_box(left)
    box_l = (max(x0 - pad, 0), top + max(y0 - pad, 0),
             min(x1 + pad, w // 2), top + min(y1 + pad, h - top))
    box_r = (box_l[0] + w // 2, box_l[1], box_l[2] + w // 2, box_l[3])
    return box_l, box_r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trial", default=DEFAULT_TRIAL)
    ap.add_argument("--views", type=int, nargs="+", default=[1, 3, 5, 9, 10, 20])
    ap.add_argument("--out", default="fruit_y000_recon_strip")
    ap.add_argument("--figdir", default=FIGDIR)
    ap.add_argument("--no-gt", action="store_true", help="drop the ground-truth cell")
    ap.add_argument("--gt-voxel", action="store_true",
                    help="GT hücresini ham mesh yerine 3 mm voksellenmiş haliyle çiz")
    ap.add_argument("--voxel-size", type=float, default=0.003)
    ap.add_argument("--lang", choices=("en", "tr"), default="en",
                    help="etiket dili (tez İngilizce olduğu için varsayılan en)")
    ap.add_argument("--gt-mode", choices=("surface", "vertex"), default="surface",
                    help="GT vokselleri: üçgen yüzeyinden (doğru) ya da sadece vertex'lerden")
    ap.add_argument("--target", default="auto",
                    choices=("auto", "fruit", "blossom", "all", "mug", "bunny"),
                    help="GT nesnesi; bitki dışı koşularda zorunlu")
    ap.add_argument("--gt-only", action="store_true",
                    help="şerit yerine sadece vokselleştirilmiş GT panelini yaz")
    ap.add_argument("--tight", action="store_true",
                    help="eksen etiketlerini kırp; şerit küçültüldüğünde okunmayan yazıyı atar")
    ap.add_argument("--cut", type=float, nargs=3, default=[0.10, 0.14, 0.22],
                    metavar=("SOL", "SAG", "ALT"), help="--tight ile kırpma oranları")
    ap.add_argument("--highlight", type=int, default=None,
                    help="bu görünümün hücresini çerçeveye al (okluzyonun açıldığı adım)")
    args = ap.parse_args()

    trial = os.path.expanduser(args.trial)
    mfile = glob.glob(os.path.join(trial, "metrics_*.json"))[0]
    m = json.load(open(mfile))
    cov, f1, rec = m["coverages"], m["f1_scores"], m["recalls"]
    tp, fp = m["tp_series"], m["fp_series"]

    if args.gt_only:
        os.makedirs(args.figdir, exist_ok=True)
        out = os.path.join(args.figdir, f"{args.out}.png")
        n_vox, n_mesh = voxelized_gt_panel(m["occlusion"], args.voxel_size, out,
                                           single=True, lang=args.lang,
                                           target=args.target, mode=args.gt_mode)
        voxelized_gt_panel(m["occlusion"], args.voxel_size,
                           out.replace(".png", ".pdf"), single=True, lang=args.lang,
                           target=args.target, mode=args.gt_mode)
        print(f"yazıldı: {out} (+.pdf)")
        print(f"{n_mesh:,} mesh noktası -> {n_vox:,} voksel "
              f"@ {args.voxel_size*1000:.0f} mm")
        return

    frames = sorted(glob.glob(os.path.join(trial, "reconstruction_per_iter", "*_view*.png")))
    by_view = {int(os.path.basename(f).rsplit("view", 1)[1][:2]): f for f in frames}
    views = [v for v in args.views if v in by_view]
    missing = [v for v in args.views if v not in by_view]
    if missing:
        print("uyarı: bu görünümlerin karesi yok:", missing)

    lab = L[args.lang]
    box_l, box_r = panel_boxes(by_view[views[-1]])
    if args.tight:
        # 3B eksenin kendisini bırak, tik/eksen yazılarını kırp
        w_, h_ = box_l[2] - box_l[0], box_l[3] - box_l[1]
        cut = (int(args.cut[0] * w_), 0, int(args.cut[1] * w_), int(args.cut[2] * h_))
        box_l = (box_l[0] + cut[0], box_l[1] + cut[1], box_l[2] - cut[2], box_l[3] - cut[3])
        box_r = (box_r[0] + cut[0], box_r[1] + cut[1], box_r[2] - cut[2], box_r[3] - cut[3])
    ncell = len(views) + (0 if args.no_gt else 1)

    cw, ch = box_l[2] - box_l[0], box_l[3] - box_l[1]
    fig_w = 2.05 * ncell
    fig, axes = plt.subplots(1, ncell, figsize=(fig_w, fig_w / ncell * ch / cw + 0.85))

    for ax in axes:
        for s_ in ax.spines.values():
            s_.set_visible(False)

    for ax, v in zip(axes, views):
        ax.imshow(Image.open(by_view[v]).crop(box_l))
        seen = tp[v] + fp[v]
        jump = cov[v] - cov[v - 1]
        ax.set_title(f"{lab['view']} {v}", fontsize=10, fontweight="bold", pad=4)
        if v == args.highlight:
            for s_ in ax.spines.values():
                s_.set_visible(True); s_.set_color("#c0392b"); s_.set_linewidth(1.6)
            ax.set_title(f"{lab['view']} {v}  (+{jump:.0f} {lab['jump']})", fontsize=10,
                         fontweight="bold", color="#c0392b", pad=4)
        ax.set_xlabel(f"{lab['cov']} {cov[v]:.0f}%\nrecall {rec[v]:.2f} · F1 {f1[v]:.2f}\n"
                      f"{seen:,} {lab['vox']}",
                      fontsize=8.5, labelpad=3)

    if not args.no_gt:
        ax = axes[-1]
        if args.gt_voxel:
            os.makedirs(SCRATCH, exist_ok=True)
            tmp = os.path.join(SCRATCH, "gt_voxel_panel.png")
            n_vox, n_mesh = voxelized_gt_panel(m["occlusion"], args.voxel_size, tmp,
                                               lang=args.lang, target=args.target,
                                               mode=args.gt_mode)
            _, gbox = panel_boxes(tmp)
            if args.tight:
                gw, gh = gbox[2] - gbox[0], gbox[3] - gbox[1]
                gbox = (gbox[0] + int(args.cut[0] * gw), gbox[1],
                        gbox[2] - int(args.cut[1] * gw), gbox[3] - int(args.cut[2] * gh))
            ax.imshow(Image.open(tmp).convert("RGB").crop(gbox).resize((cw, ch), Image.LANCZOS))
            ax.set_title(lab["gt"], fontsize=10, fontweight="bold", pad=4)
            seen_last = tp[views[-1]] + fp[views[-1]]
            ax.set_xlabel(lab["gtvox"].format(n=n_vox, mm=args.voxel_size * 1000)
                          + "\n" + lab["mesh"].format(n=n_mesh),
                          fontsize=8.5, labelpad=3)
            print(f"GT: {n_mesh:,} mesh noktası -> {n_vox:,} voksel; "
                  f"son görünüm {seen_last:,} = tavanın %{100*seen_last/n_vox:.0f}'i")
        else:
            ax.imshow(Image.open(by_view[views[-1]]).crop(box_r))
            ax.set_title(lab["gt"], fontsize=10, fontweight="bold", pad=4)
            ax.set_xlabel("mesh points" if args.lang == "en" else "mesh noktaları",
                          fontsize=8.5, labelpad=3)

    for ax in axes:
        ax.set_xticks([]); ax.set_yticks([])

    fig.tight_layout(w_pad=0.4)
    os.makedirs(args.figdir, exist_ok=True)
    for ext in ("pdf", "png"):
        p = os.path.join(args.figdir, f"{args.out}.{ext}")
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print("yazıldı:", p)


if __name__ == "__main__":
    main()
