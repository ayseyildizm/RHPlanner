#!/usr/bin/env python
"""
hsv_preload.py — gerçek D455 koşusu için HSV eşiklerini DIŞARIDAN ver.

perceiver.py DEĞİŞMEZ. Bu launcher Perceiver.color_segmentation'ı çalışma
anında sarar, sonra asıl node script'ini normal şekilde çalıştırır.

Kullanım (doğrudan):
    python hsv_preload.py src/viewpoint_planning/src/test_rh_node.py --ros-args ...

Kullanım (normal yol — run_ros2_real.sh HSV_TUNED=1 görünce buraya yönlenir):
    HSV_TUNED=1 HSV_S_MIN=80 HSV_V_MIN=60 HSV_WRAP=1 \
        PLANNER=gradient OCC=none NUM_TRIALS=1 ./run_ros2_real.sh

Ortam değişkenleri (hepsi opsiyonel; verilmeyen simülasyondaki değerde kalır):
    HSV_H1_LO / HSV_H1_HI   birinci kırmızı bandı        (varsayılan 0 / 10)
    HSV_S_MIN / HSV_V_MIN   doygunluk / parlaklık alt sınırı (varsayılan 50 / 50)
    HSV_WRAP                1 ise hue çemberinin öbür ucundaki ikinci bant açılır
    HSV_H2_LO / HSV_H2_HI   ikinci (sarmal) bant         (varsayılan 170 / 179)

Hiçbiri verilmezse maske simülasyondakiyle bit-bit aynıdır.
"""

import os
import sys
import runpy

import cv2
import numpy as np

REPO = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(REPO, "src", "viewpoint_planning", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


def _env_int(name, default):
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(float(raw))


def _build_segmenter():
    h1_lo = _env_int("HSV_H1_LO", 0)
    h1_hi = _env_int("HSV_H1_HI", 10)
    s_min = _env_int("HSV_S_MIN", 50)
    v_min = _env_int("HSV_V_MIN", 50)
    wrap = os.environ.get("HSV_WRAP", "0") not in ("0", "", "false", "False")
    h2_lo = _env_int("HSV_H2_LO", 170)
    h2_hi = _env_int("HSV_H2_HI", 179)

    lower1 = np.array([h1_lo, s_min, v_min])
    upper1 = np.array([h1_hi, 255, 255])
    lower2 = np.array([h2_lo, s_min, v_min])
    upper2 = np.array([h2_hi, 255, 255])

    def color_segmentation(self, color_image):
        # capturer BGR->RGB çevirdiği için dönüşüm perceiver.py ile aynı kalmalı
        hsv_image = cv2.cvtColor(color_image, cv2.COLOR_RGB2HSV)
        mask = cv2.inRange(hsv_image, lower1, upper1)
        if wrap:
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv_image, lower2, upper2))
        return mask

    desc = f"H {h1_lo}-{h1_hi}, S>={s_min}, V>={v_min}"
    if wrap:
        desc += f" + wrap H {h2_lo}-{h2_hi}"
    return color_segmentation, desc


def main():
    if len(sys.argv) < 2:
        print("kullanim: python hsv_preload.py <node_script.py> [args...]")
        return 2

    from perception.perceiver import Perceiver

    segmenter, desc = _build_segmenter()
    Perceiver.color_segmentation = segmenter
    print(f"[hsv_preload] color_segmentation sarildi: {desc}", flush=True)

    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    runpy.run_path(script, run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
