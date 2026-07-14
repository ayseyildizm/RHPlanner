#!/usr/bin/env python3
"""
hsv_test.py — D455 canlı görüntüsünde kırmızı HSV segmentasyon ayarı.

Perceiver.color_segmentation'ın (perceiver.py:50) BİREBİR aynı renk yolunu izler:
capturer BGR→RGB çevirir, perceiver RGB2HSV kullanır — burada da öyle.

Trackbar'lar:
  H1 lo/hi : alt kırmızı bandı (perceiver'daki mevcut aralık: 0–10)
  H2 on    : üst kırmızı bandını (H2 lo–hi, sarmal 170–179) maskeye EKLE
  S min/V min : doygunluk/parlaklık tabanı (mevcut: 50/50)

Ekran: sol = canlı görüntü (tuned maske yeşil konturla), sağ = maske.
Üstte piksel sayıları: PERCEIVER (mevcut kod ne görüyor) vs TUNED (senin ayarın).

Tuşlar: q/ESC çık (çıkışta seçili değerleri kod parçası olarak basar), p = anlık bas.

Kullanım: ./run_hsv_test.sh   (kamera node'unu gerekirse kendisi başlatır)
Topic override: HSV_TOPIC=/baska/topic ./run_hsv_test.sh
"""
import os
import numpy as np
import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

TOPIC = os.environ.get("HSV_TOPIC", "/camera/color/image_rect_color")
WIN = "hsv_tune  (q: kaydet+cik | p: degerleri bas)"

# Perceiver'daki mevcut değerler (perceiver.py:59-60)
PERC_LO = np.array([0, 50, 50])
PERC_HI = np.array([10, 255, 255])


class HsvTuner(Node):
    def __init__(self):
        super().__init__("hsv_tuner")
        self._bridge = CvBridge()
        self.rgb = None
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                         history=HistoryPolicy.KEEP_LAST, depth=2)
        self.create_subscription(Image, TOPIC, self._cb, qos)

    def _cb(self, msg):
        bgr = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        self.rgb = bgr[:, :, ::-1].copy()  # capturer ile aynı: BGR→RGB


def make_masks(rgb, h1lo, h1hi, h2on, h2lo, h2hi, smin, vmin):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)  # perceiver ile aynı dönüşüm
    perc = cv2.inRange(hsv, PERC_LO, PERC_HI)
    tuned = cv2.inRange(hsv, np.array([h1lo, smin, vmin]),
                        np.array([h1hi, 255, 255]))
    if h2on:
        band2 = cv2.inRange(hsv, np.array([h2lo, smin, vmin]),
                            np.array([h2hi, 255, 255]))
        tuned = cv2.bitwise_or(tuned, band2)
    return perc, tuned


def snippet(h1lo, h1hi, h2on, h2lo, h2hi, smin, vmin):
    lines = [
        "# --- hsv_test.py ile secilen degerler ---",
        f"lower1, upper1 = np.array([{h1lo}, {smin}, {vmin}]), np.array([{h1hi}, 255, 255])",
    ]
    if h2on:
        lines += [
            f"lower2, upper2 = np.array([{h2lo}, {smin}, {vmin}]), np.array([{h2hi}, 255, 255])",
            "mask = cv2.inRange(hsv_image, lower1, upper1) | cv2.inRange(hsv_image, lower2, upper2)",
        ]
    else:
        lines += ["mask = cv2.inRange(hsv_image, lower1, upper1)"]
    return "\n".join(lines)


def main():
    rclpy.init()
    node = HsvTuner()
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    nop = lambda _v: None
    cv2.createTrackbar("H1 lo", WIN, 0, 179, nop)
    cv2.createTrackbar("H1 hi", WIN, 10, 179, nop)
    cv2.createTrackbar("H2 on", WIN, 1, 1, nop)
    cv2.createTrackbar("H2 lo", WIN, 170, 179, nop)
    cv2.createTrackbar("H2 hi", WIN, 179, 179, nop)
    cv2.createTrackbar("S min", WIN, 50, 255, nop)
    cv2.createTrackbar("V min", WIN, 50, 255, nop)

    print(f"[hsv_test] {TOPIC} bekleniyor...")
    vals = (0, 10, 1, 170, 179, 50, 50)
    try:
        while True:
            rclpy.spin_once(node, timeout_sec=0.05)
            if node.rgb is None:
                if (cv2.waitKey(50) & 0xFF) in (27, ord("q")):
                    break
                continue
            vals = (cv2.getTrackbarPos("H1 lo", WIN), cv2.getTrackbarPos("H1 hi", WIN),
                    cv2.getTrackbarPos("H2 on", WIN), cv2.getTrackbarPos("H2 lo", WIN),
                    cv2.getTrackbarPos("H2 hi", WIN), cv2.getTrackbarPos("S min", WIN),
                    cv2.getTrackbarPos("V min", WIN))
            rgb = node.rgb
            perc, tuned = make_masks(rgb, *vals)

            disp = rgb[:, :, ::-1].copy()  # imshow BGR ister
            contours, _ = cv2.findContours(tuned, cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(disp, contours, -1, (0, 255, 0), 2)
            mask_bgr = cv2.cvtColor(tuned, cv2.COLOR_GRAY2BGR)
            both = np.hstack([disp, mask_bgr])
            txt = (f"PERCEIVER(0-10,S50,V50): {int((perc > 0).sum())} px   "
                   f"TUNED: {int((tuned > 0).sum())} px")
            cv2.putText(both, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0, 255, 255), 2)
            cv2.imshow(WIN, both)

            k = cv2.waitKey(30) & 0xFF
            if k in (27, ord("q")):
                break
            if k == ord("p"):
                print(snippet(*vals))
    finally:
        print("\n" + snippet(*vals))
        cv2.destroyAllWindows()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
