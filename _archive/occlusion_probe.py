#!/usr/bin/env python3
"""
occlusion_probe.py — one-shot check that occluder walls actually BLOCK the
camera (regression test for the render near-clip bug, 2026-07-05).

Moves the arm to a frontal pose 0.45 m from the target (front wall then sits
~0.33 m from the lens — inside the old 0.40 render clip) and captures one
RGB+depth frame:
    PASS  center depth ~= wall distance (~0.28-0.38 m) and ~0 red pixels
    FAIL  center depth ~= bunny distance (>=0.42 m) or red pixels visible
          (camera is seeing THROUGH the wall again)

PREREQ: stack up with OCC=panels2..5 (any world with a FRONT wall), no
experiment in flight.  Run:  REACH=occlusion_probe.py ./run_reach_test.sh
"""
import math
import time

import numpy as np

import ros2_node
ros2_node.init("occlusion_probe")

from abb_control.arm_control_client import ArmControlClient
from perception.realsense_ros_capturer import RealsenseROSCapturer
from utils.py_utils import numpy_to_pose, look_at_rotation

TARGET = np.array([0.50, -0.30, 0.92])
RADIUS = 0.50          # frontal az=0 at the experiments' MIN_STANDOFF — the
                       # exact pose class every planner run uses (proven
                       # plannable); wall then ~0.37 m from lens, still inside
                       # the old 0.40 render clip, so the regression test holds
Z_OFF = 0.05
WALL_Y = -0.169        # stage front panel outer face (center -0.189 + t/2)

HOME = np.array([0.5, -0.05, 1.0, 0.0, 0.0,
                 -0.7071067811865475, 0.7071067811865476])


def main():
    arm = ArmControlClient()
    cap = RealsenseROSCapturer()

    cam = TARGET + np.array([0.0, RADIUS, Z_OFF])
    view = np.concatenate((cam, look_at_rotation(cam, TARGET)))
    print(f"[probe] moving to frontal pose {cam.round(3).tolist()} "
          f"(wall should be {cam[1] - WALL_Y:.2f} m away, bunny {RADIUS:.2f} m)")
    ok = False
    for attempt in range(4):
        arm.move_arm_to_pose(numpy_to_pose(HOME)); time.sleep(0.5)
        if arm.move_arm_to_pose(numpy_to_pose(view)):
            ok = True
            break
        print(f"[probe] attempt {attempt + 1} failed, retrying")
    if not ok:
        raise SystemExit("[probe] ABORT: could not reach the probe pose")
    time.sleep(2.0)  # let a fresh frame arrive

    color, depth = None, None
    for _ in range(50):
        _, cout, dout = cap.get_frames(wait_for_new=True, timeout=3.0)
        color, depth = cout.get("color_image"), dout.get("depth_image")
        if color is not None and depth is not None:
            break
        time.sleep(0.2)
    if color is None or depth is None:
        raise SystemExit("[probe] ABORT: no camera frames")

    h, w = depth.shape[:2]
    roi = depth[h // 2 - 50:h // 2 + 50, w // 2 - 50:w // 2 + 50].astype(float)
    if np.nanmax(roi) > 50:      # mm -> m
        roi = roi / 1000.0
    valid = roi[np.isfinite(roi) & (roi > 0)]
    med = float(np.median(valid)) if valid.size else float("nan")

    import cv2
    hsv = cv2.cvtColor(color, cv2.COLOR_RGB2HSV)  # color_image is RGB
    red = cv2.inRange(hsv, (0, 50, 50), (10, 255, 255))
    n_red = int(np.count_nonzero(red))

    wall_d = cam[1] - WALL_Y
    print(f"[probe] center 100x100 depth median = {med:.3f} m "
          f"(valid px {valid.size}/{roi.size})")
    print(f"[probe] red bunny pixels in frame  = {n_red}")
    if math.isnan(med):
        verdict = "INCONCLUSIVE (no valid depth in center; wall inside software z_near?)"
    elif abs(med - wall_d) < 0.06 and n_red < 200:
        verdict = "PASS — wall blocks the camera"
    elif med > RADIUS - 0.06 or n_red >= 200:
        verdict = "FAIL — camera sees THROUGH the wall (near-clip bug back?)"
    else:
        verdict = f"UNCLEAR — depth {med:.3f} vs wall {wall_d:.2f}/bunny {RADIUS:.2f}"
    print(f"[probe] {verdict}")
    arm.move_arm_to_pose(numpy_to_pose(HOME))


if __name__ == "__main__":
    main()
