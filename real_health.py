#!/usr/bin/env python
"""
real_health.py — gerçek robot koşusunda ALGI SAĞLIK KONTROLÜ.

Ana dosyalar DEĞİŞMEZ (bkz. hsv_preload.py ile aynı yaklaşım). Bu launcher
çalışma anında iki yeri sarar:

  * Perceiver.run              -> kaç kırmızı piksel, derinlik ne kadar geçerli
  * VoxelGrid.insert_depth_and_semantics -> haritaya ne düştü

ve her görüşten sonra TEK satır basar:

  [health] view 3 | red_px=1842 (0.5%) | depth_ok=71% | occ_vox=5120 |
           roi_occ=430 | roi_class0=118 | cov=34.2%

Satırın okunuşu — coverage yükselirken F1/precision/recall 0 kalıyorsa:

  red_px = 0                 HSV maskesi hiç ateşlenmiyor. Hedef gerçekten
                             kırmızı mı, ışık nasıl? run_hsv_test.sh ile ayarla,
                             sonra HSV_* değişkenleriyle koş (hsv_preload.py).
  red_px > 0, roi_class0 = 0 Maske çalışıyor ama hedef sınıf voxel'i ROI'ye
                             düşmüyor: nesne konumu ölçüsü (TARGET_POS /
                             OBJECT_CENTER), TF ya da el-göz offset'i şüpheli.
  roi_occ = 0 ama cov artıyor  ROI hacmi taranıyor fakat hiçbir YÜZEY
                             görülmüyor — nesne derinlik menzili/FOV dışında ya
                             da ROI kutusu boş havada.
  hepsi > 0                  Algı sağlıklı. F1/precision/recall'ın 0 olması
                             GT mesh'ten kaynaklanıyor (gerçek nesnenin
                             kayıtlı mesh'i yok), planlayıcıdan değil.

Kullanım (doğrudan):
    python real_health.py src/viewpoint_planning/src/test_rh_node.py --ros-args ...

Kullanım (normal yol — run_ros2_real.sh varsayılan olarak açar):
    PLANNER=gradient OCC=none NUM_TRIALS=1 ./run_ros2_real.sh
    HEALTH=0 ... ./run_ros2_real.sh          # kapatmak için

hsv_preload.py ile zincirlenebilir (sarmalayıcılar soldan sağa uygulanır):
    python hsv_preload.py real_health.py test_rh_node.py ...

Ortam değişkenleri:
    HEALTH_ABORT_VIEWS   N>0 ise: ilk N görüşün hepsinde roi_class0 == 0
                         kalırsa koşuyu durdurur (varsayılan 0 = kapalı).
                         20 görüşü kör harcamamak için 3 iyi bir değer.
"""

import os
import sys
import runpy

import numpy as np

REPO = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(REPO, "src", "viewpoint_planning", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


class _BlindRun(RuntimeError):
    """İlk N görüşte hedef sınıfı hiç görülmedi."""


# Perceiver.run ile insert_depth_and_semantics arasında taşınan son kare bilgisi
_last_frame = {"red_px": None, "px_total": None, "depth_ok": None}
_state = {"view": 0, "blind_views": 0}


def _as_numpy(x):
    if x is None:
        return None
    if hasattr(x, "detach"):
        x = x.detach().cpu()
    return np.asarray(x)


def _patch_perceiver():
    from perception.perceiver import Perceiver

    _orig_run = Perceiver.run

    def run(self):
        depth_image, points, semantics = _orig_run(self)

        red_px = px_total = depth_ok = None
        sem = _as_numpy(semantics)
        if sem is not None and sem.ndim == 3 and sem.shape[-1] == 2:
            # semantics[..., 1] == 0 -> hedef sınıf (assign_semantics: label 0),
            # arka plan -1 ile işaretlenir.
            labels = sem[..., 1]
            red_px = int((labels == 0).sum())
            px_total = int(labels.size)

        depth = _as_numpy(depth_image)
        if depth is not None and depth.size > 0:
            valid = np.isfinite(depth) & (depth > 0.0)
            depth_ok = float(valid.mean())

        _last_frame.update(red_px=red_px, px_total=px_total, depth_ok=depth_ok)
        return depth_image, points, semantics

    Perceiver.run = run


def _patch_voxel_grid():
    from scene_representation.voxel_grid import VoxelGrid

    _orig_insert = VoxelGrid.insert_depth_and_semantics

    def insert_depth_and_semantics(self, depth_image, semantics, transforms):
        coverage = _orig_insert(self, depth_image, semantics, transforms)
        try:
            _report(self, coverage)
        except _BlindRun:
            raise
        except Exception as exc:  # sağlık çıktısı asla koşuyu düşürmesin
            print(f"[health] (özet basılamadı: {exc})", flush=True)
        return coverage

    VoxelGrid.insert_depth_and_semantics = insert_depth_and_semantics


def _report(grid, coverage):
    _state["view"] += 1
    view = _state["view"]

    occ_mask = grid.voxel_grid[..., 1] > 0.5
    occ_vox = int(occ_mask.sum().item())

    roi_occ = roi_class0 = None
    bounds = getattr(grid, "target_bounds", None)
    if bounds is not None:
        b = [int(v) for v in _as_numpy(bounds).reshape(-1)]
        roi = grid.voxel_grid[b[0]:b[3], b[1]:b[4], b[2]:b[5], :]
        roi_occupied = roi[..., 1] > 0.5
        roi_occ = int(roi_occupied.sum().item())
        roi_class0 = int((roi_occupied & (roi[..., 3] == 0)).sum().item())

    red_px = _last_frame["red_px"]
    px_total = _last_frame["px_total"]
    depth_ok = _last_frame["depth_ok"]

    if red_px is None:
        red_txt = "red_px=?"
    elif px_total:
        red_txt = f"red_px={red_px} ({red_px / px_total * 100:.2f}%)"
    else:
        red_txt = f"red_px={red_px}"

    parts = [
        f"view {view}",
        red_txt,
        "depth_ok=?" if depth_ok is None else f"depth_ok={depth_ok * 100:.0f}%",
        f"occ_vox={occ_vox}",
        "roi_occ=?" if roi_occ is None else f"roi_occ={roi_occ}",
        "roi_class0=?" if roi_class0 is None else f"roi_class0={roi_class0}",
        "cov=?" if coverage is None else f"cov={float(coverage):.1f}%",
    ]
    print("[health] " + " | ".join(parts), flush=True)

    # Teşhis ipucu — sadece bir şeyler ters gittiğinde, her görüşte değil.
    if red_px == 0:
        print("[health]   -> HSV maskesi hic ateslenmedi: hedef kirmizi mi? "
              "run_hsv_test.sh ile ayarla, HSV_* ile kos.", flush=True)
    elif roi_class0 == 0 and roi_occ == 0 and occ_vox == 0:
        print("[health]   -> hicbir dolu voxel yok: nesne derinlik menzili/FOV "
              "disinda ya da ROI kutusu bos havada.", flush=True)
    elif roi_class0 == 0:
        print("[health]   -> hedef sinif voxel'i ROI'ye dusmuyor: TARGET_POS / "
              "OBJECT_CENTER olcusu, TF ve el-goz offset'i supheli.", flush=True)

    limit = int(float(os.environ.get("HEALTH_ABORT_VIEWS", "0") or 0))
    if limit > 0:
        if roi_class0:
            _state["blind_views"] = 0
        else:
            _state["blind_views"] += 1
            if _state["blind_views"] >= limit:
                raise _BlindRun(
                    f"ilk {limit} goruste ROI'de hic hedef sinifi voxel'i "
                    "olusmadi — kosu durduruldu (HEALTH_ABORT_VIEWS)."
                )


def main():
    if len(sys.argv) < 2:
        print("kullanim: python real_health.py <node_script.py> [args...]")
        return 2

    _patch_perceiver()
    _patch_voxel_grid()
    abort = os.environ.get("HEALTH_ABORT_VIEWS", "0")
    print(f"[health] algi saglik kontrolu AKTIF "
          f"(HEALTH_ABORT_VIEWS={abort})", flush=True)

    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    try:
        runpy.run_path(script, run_name="__main__")
    except _BlindRun as exc:
        print(f"\n[health] DURDURULDU: {exc}", flush=True)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
