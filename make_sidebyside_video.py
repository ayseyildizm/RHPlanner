#!/usr/bin/env python3
"""
make_sidebyside_video.py — "ne görülüyor vs. ne ölçülüyor" karşılaştırma videosu.

Sol panel : run'in ekran kaydindaki RViz gorunumu (ham derinlik bulutu; her
            piksel entegre edildigi icin tum bitki gorunur).
Sag panel : ayni run'in reconstruction_per_iter/ kareleri (skorlanan sey:
            ROI icindeki semantik meyve voxelleri).

Senkron   : videonun toplam suresi run'in toplam suresine (metrics["times"][-1])
            dogrusal esleniyor; her video karesi icin o ana denk gelen iterasyon
            karesi gosteriliyor. Ekran kaydi tekduze hizlandirilmis varsayilir.

Kullanim:
    python3 make_sidebyside_video.py \
        --video    ~/Downloads/reconstruction_timelapse_30s.mp4 \
        --run      results/run_20260819_081203_expC_panels_tree_fruit_y000_K10_H3_box \
        --out      ~/Downloads/recon_sidebyside_30s.mp4
"""
import argparse
import glob
import json
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
BG       = (250, 250, 250)
INK      = (25, 25, 25)
MUTED    = (110, 110, 110)
RULE     = (205, 205, 205)

PANEL_H  = 660          # her iki panelin ortak yuksekligi
PAD      = 26
HEAD_H   = 96
CAP_H    = 62
FOOT_H   = 74

# Ekran kaydindaki RViz gorunumunun kirpma kutusu (1280x576 kayit icin).
RVIZ_CROP = (445, 0, 1280, 576)          # x0, y0, x1, y1
# Per-iter figurun SOL alt grafigi (3600x1833 figur icin); GT sag tarafta kaliyor.
RECON_CROP = (60, 150, 1760, 1833)


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def load_fonts():
    return {
        "title":  _font("DejaVuSans-Bold.ttf", 30),
        "sub":    _font("DejaVuSans.ttf", 19),
        "cap":    _font("DejaVuSans-Bold.ttf", 22),
        "capsub": _font("DejaVuSans.ttf", 17),
        "foot":   _font("DejaVuSans.ttf", 20),
        "footb":  _font("DejaVuSans-Bold.ttf", 20),
        "note":   _font("DejaVuSans-Oblique.ttf", 18),
    }


def fit_to_height(img, height):
    h, w = img.shape[:2]
    scale = height / float(h)
    return cv2.resize(img, (int(round(w * scale)), height), interpolation=cv2.INTER_AREA)


def load_recon_frames(run_dir, height):
    """Iterasyon indeksinden (1..N) kirpilmis+olceklenmis kareye sozluk."""
    pattern = os.path.join(run_dir, "trial_00", "reconstruction_per_iter", "*view*.png")
    frames = {}
    for path in sorted(glob.glob(pattern)):
        idx = int(os.path.basename(path).split("view")[-1].split(".")[0])
        img = cv2.imread(path)
        if img is None:
            continue
        x0, y0, x1, y1 = RECON_CROP
        img = img[y0:min(y1, img.shape[0]), x0:min(x1, img.shape[1])]
        frames[idx] = fit_to_height(img, height)
    if not frames:
        raise SystemExit(f"[HATA] iterasyon karesi bulunamadi: {pattern}")
    return frames


def load_metrics(run_dir):
    hits = glob.glob(os.path.join(run_dir, "trial_00", "metrics_*.json"))
    if not hits:
        raise SystemExit(f"[HATA] metrics_*.json bulunamadi: {run_dir}")
    with open(hits[0]) as fh:
        return json.load(fh)


def placeholder(width, height, fonts, text):
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, width - 1, height - 1], outline=RULE, width=2)
    box = draw.textbbox((0, 0), text, font=fonts["capsub"])
    draw.text(((width - box[2]) / 2, (height - box[3]) / 2), text,
              font=fonts["capsub"], fill=MUTED)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def compose(left_bgr, right_bgr, fonts, iter_idx, n_iters, coverage, f1, voxels):
    lw, rw = left_bgr.shape[1], right_bgr.shape[1]
    width  = PAD * 3 + lw + rw
    height = HEAD_H + CAP_H + PANEL_H + FOOT_H + PAD

    canvas = Image.new("RGB", (width, height), BG)
    draw   = ImageDraw.Draw(canvas)

    draw.text((PAD, 20), "RH-NBV — ne görülüyor, ne ölçülüyor?",
              font=fonts["title"], fill=INK)
    draw.text((PAD, 58),
              "Aynı koşu, iki farklı görünüm: solda kameranın entegre ettiği her şey, "
              "sağda amaç fonksiyonunun ve metriklerin üzerinde tanımlı olduğu küme.",
              font=fonts["sub"], fill=MUTED)
    draw.line([(PAD, HEAD_H - 8), (width - PAD, HEAD_H - 8)], fill=RULE, width=2)

    lx, rx = PAD, PAD * 2 + lw
    cap_y  = HEAD_H + 2
    draw.text((lx, cap_y), "Robotun gördüğü — ham derinlik bulutu",
              font=fonts["cap"], fill=INK)
    draw.text((lx, cap_y + 28),
              "Her derinlik pikseli occupancy'ye yazılır: yapraklar, dallar, hepsi.",
              font=fonts["capsub"], fill=MUTED)
    draw.text((rx, cap_y), "Skorlanan — semantik meyve vokselleri",
              font=fonts["cap"], fill=INK)
    draw.text((rx, cap_y + 28),
              "ROI ile kırpılmış, kırmızı-HSV semantik etiketli vokseller.",
              font=fonts["capsub"], fill=MUTED)

    panel_y = HEAD_H + CAP_H
    canvas_bgr = cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR)
    canvas_bgr[panel_y:panel_y + PANEL_H, lx:lx + lw] = left_bgr
    canvas_bgr[panel_y:panel_y + PANEL_H, rx:rx + rw] = right_bgr

    canvas = Image.fromarray(cv2.cvtColor(canvas_bgr, cv2.COLOR_BGR2RGB))
    draw   = ImageDraw.Draw(canvas)
    for x, w_ in ((lx, lw), (rx, rw)):
        draw.rectangle([x - 1, panel_y - 1, x + w_, panel_y + PANEL_H], outline=RULE, width=2)

    foot_y = panel_y + PANEL_H + 16
    draw.line([(PAD, foot_y - 6), (width - PAD, foot_y - 6)], fill=RULE, width=2)
    if iter_idx == 0:
        left_txt = "İterasyon —/%d" % n_iters
        stats    = "ilk ölçüm henüz alınmadı"
    else:
        left_txt = "İterasyon %d/%d" % (iter_idx, n_iters)
        stats    = "ROI kapsama %.2f%%   ·   F1 %.2f" % (coverage, f1)
    draw.text((PAD, foot_y + 6), left_txt, font=fonts["footb"], fill=INK)
    draw.text((PAD + 190, foot_y + 6), stats, font=fonts["foot"], fill=INK)
    draw.text((PAD, foot_y + 34),
              "Kapsama paydası ROI küpünün tamamıdır (70³ voksel, ±10,5 cm); "
              "F1'in yer gerçekliği yalnızca Fruit1–4 alt meshleridir.",
              font=fonts["note"], fill=MUTED)

    return cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR)


def target_voxel_counts(run_dir, n_iters):
    """Kare basliklarindaki 'N target voxels' sayisini OCR'siz alamayiz; bunun
    yerine metrics'te yoksa None dondurup alt bantta '—' gosteriyoruz."""
    return {k: None for k in range(n_iters + 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=0.0, help="0 = kaynak videonun fps'i")
    args = ap.parse_args()

    run_dir = os.path.expanduser(args.run)
    metrics = load_metrics(run_dir)
    times   = metrics["times"]
    covs    = metrics["coverages"]
    f1s     = metrics["f1_scores"]
    n_iters = metrics["num_iters"]
    total_t = float(times[-1])

    cap = cv2.VideoCapture(os.path.expanduser(args.video))
    if not cap.isOpened():
        raise SystemExit("[HATA] video acilamadi")
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    src_fps  = cap.get(cv2.CAP_PROP_FPS) or 30.0
    fps      = args.fps or src_fps

    fonts   = load_fonts()
    recon   = load_recon_frames(run_dir, PANEL_H)
    counts  = target_voxel_counts(run_dir, n_iters)
    blank_w = next(iter(recon.values())).shape[1]
    blank   = placeholder(blank_w, PANEL_H, fonts, "ilk ölçüm bekleniyor")

    writer = None
    x0, y0, x1, y1 = RVIZ_CROP
    written = 0
    for i in range(n_frames):
        ok, frame = cap.read()
        if not ok:
            break
        left = fit_to_height(frame[y0:y1, x0:x1], PANEL_H)

        t_run = (i / max(n_frames - 1, 1)) * total_t
        k = int(np.searchsorted(times, t_run, side="right") - 1)
        k = max(0, min(k, n_iters))

        right = recon.get(k, blank) if k >= 1 else blank
        out_frame = compose(left, right, fonts, k, n_iters,
                            covs[k] if k < len(covs) else covs[-1],
                            f1s[k] if k < len(f1s) else f1s[-1],
                            counts.get(k))

        if writer is None:
            h, w = out_frame.shape[:2]
            writer = cv2.VideoWriter(os.path.expanduser(args.out),
                                     cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            if not writer.isOpened():
                raise SystemExit("[HATA] VideoWriter acilamadi")
            print("[bilgi] cikti boyutu %dx%d @ %.1f fps" % (w, h, fps))
        writer.write(out_frame)
        written += 1

    cap.release()
    if writer:
        writer.release()
    print("[tamam] %d kare yazildi -> %s" % (written, os.path.expanduser(args.out)))


if __name__ == "__main__":
    main()
