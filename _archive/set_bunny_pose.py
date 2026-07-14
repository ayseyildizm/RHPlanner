#!/usr/bin/env python3
"""
set_bunny_pose.py — move the bunny to a new pose EVERYWHERE, atomically:

  1. Gazebo base world  ur5e_world.sdf (src + install copies)
  2. make_panel_world.py BUNNY AABB constant
  3. GT mesh translations in viewpoint_planning.py, test_gradient_node.py,
     test_baseline_node.py (bunny AND mug branches — mug spawns at bunny pose)
  4. fair_comparison_config.get_target_position (target = pose + 0.07 in z)
  5. regenerates all panel stage worlds (make_panel_world --stages-all)
  6. verifies: GT mesh bbox == BUNNY constant == world pose, panels outside ROI

This replaces the old sed-based move_bunny_to.sh, whose partial pattern
matches caused the 2026-07-04 GT-mesh divergence (RH scoring against a mesh
5 cm away from the sim bunny). Here every consumer is updated from ONE value
and the script fails loudly if any file does not contain the expected current
value.

Usage:
    python3 set_bunny_pose.py --z 0.85            # keep x,y, lower the bunny
    python3 set_bunny_pose.py --x 0.5 --y -0.30 --z 0.90
Then RESTART the Gazebo stack. Legacy hand-made worlds (frontal/tunnel/well/
half_box/covered_well) are NOT updated — do not use them after a move.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np

HOME = os.path.expanduser("~")
RH = os.path.join(HOME, "Desktop/RecedingHorizon")
SRC_WORLD = os.path.join(HOME, "ros2_ws/src/ur5e_l515_description/worlds/ur5e_world.sdf")
INSTALL_WORLDS = [
    os.path.join(HOME, "ros2_ws/install/ur5e_l515_description/share/ur5e_l515_description/worlds/ur5e_world.sdf"),
    os.path.join(HOME, "install/ur5e_l515_description/share/ur5e_l515_description/worlds/ur5e_world.sdf"),
]
MAKE_PANELS = os.path.join(RH, "make_panel_world.py")
GT_FILES = [
    os.path.join(RH, "src/viewpoint_planning/src/viewpoint_planners/viewpoint_planning.py"),
    os.path.join(RH, "src/viewpoint_planning/src/test_gradient_node.py"),
    os.path.join(RH, "src/viewpoint_planning/src/test_baseline_node.py"),
]
FC = os.path.join(RH, "src/viewpoint_planning/src/viewpoint_planners/fair_comparison_config.py")

# Bunny mesh AABB offsets relative to the model pose (scale 1.2 bunny.dae):
# pose (0.5,-0.30,1.0) <-> AABB x[0.427,0.614] y[-0.374,-0.229] z[0.980,1.165]
AABB_OFF = {"x": (-0.073, 0.114), "y": (-0.074, 0.071), "z": (-0.020, 0.165)}
TARGET_Z_OFF = 0.07  # target/ROI centre sits 0.07 above the model pose


def read(p):
    with open(p) as f:
        return f.read()


def write(p, s):
    with open(p, "w") as f:
        f.write(s)


def replace_or_die(path, old, new, expect=None):
    s = read(path)
    n = s.count(old)
    if expect is not None and n != expect:
        sys.exit(f"[bunny] ABORT: expected {expect} occurrence(s) of '{old}' in "
                 f"{os.path.basename(path)}, found {n} — file layout changed, fix manually.")
    if n == 0:
        sys.exit(f"[bunny] ABORT: '{old}' not found in {os.path.basename(path)}")
    write(path, s.replace(old, new))
    print(f"[bunny] {os.path.basename(path)}: '{old}' -> '{new}' ({n}x)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--x", type=float, default=None)
    ap.add_argument("--y", type=float, default=None)
    ap.add_argument("--z", type=float, default=None)
    args = ap.parse_args()
    if args.x is None and args.y is None and args.z is None:
        sys.exit("[bunny] give at least one of --x/--y/--z")

    # --- current pose from the base world (single source of current truth) ---
    world = read(SRC_WORLD)
    m = re.search(r'<model name=[\'"]bunny[\'"]>.*?<pose>([-\d.]+) ([-\d.]+) ([-\d.]+) 0 0 0</pose>',
                  world, re.S)
    if not m:
        sys.exit("[bunny] ABORT: bunny pose not found in ur5e_world.sdf")
    cur = [float(v) for v in m.groups()]
    new = [args.x if args.x is not None else cur[0],
           args.y if args.y is not None else cur[1],
           args.z if args.z is not None else cur[2]]
    print(f"[bunny] pose {cur} -> {new}")

    def fmt(v):  # match the files' style: 0.5, 1.0, 0.85 (always keep a dot)
        s = f"{v:g}"
        return s if "." in s else s + ".0"

    cur_pose_str = f"<pose>{m.group(1)} {m.group(2)} {m.group(3)} 0 0 0</pose>"
    new_pose_str = f"<pose>{new[0]:g} {new[1]:.2f} {new[2]:g} 0 0 0</pose>"

    # --- pre-flight: every expected current value must exist BEFORE we touch
    # anything, so a mismatch can never leave files half-migrated. ---
    pre_old_vec = f"np.array([{fmt(cur[0])}, {cur[1]:.2f}, {fmt(cur[2])}])"
    pre_old_t = f"return np.array([{cur[0]:.2f}, {cur[1]:.2f}, {cur[2] + TARGET_Z_OFF:.2f}])"
    problems = []
    for p in GT_FILES:
        if pre_old_vec not in read(p):
            problems.append(f"{os.path.basename(p)}: '{pre_old_vec}' yok")
    if pre_old_t not in read(FC):
        problems.append(f"{os.path.basename(FC)}: '{pre_old_t}' yok")
    if problems:
        sys.exit("[bunny] ABORT (hicbir dosya degistirilmedi):\n  " + "\n  ".join(problems))

    # 1) base world (src + installs)
    replace_or_die(SRC_WORLD, cur_pose_str, new_pose_str)
    for p in INSTALL_WORLDS:
        if os.path.exists(p) and not os.path.samefile(p, SRC_WORLD):
            shutil.copy(SRC_WORLD, p)
            print(f"[bunny] world copied to {p}")

    # 2) BUNNY AABB constant in make_panel_world.py
    aabb = {a: (new[i] + AABB_OFF[a][0], new[i] + AABB_OFF[a][1])
            for i, a in enumerate("xyz")}
    s = read(MAKE_PANELS)
    s2 = re.sub(r'BUNNY = \{"x": \([^}]*\}',
                'BUNNY = {"x": (%.3f, %.3f), "y": (%.3f, %.3f), "z": (%.3f, %.3f)}'
                % (aabb["x"] + aabb["y"] + aabb["z"]), s)
    if s2 == s:
        sys.exit("[bunny] ABORT: BUNNY constant not found in make_panel_world.py")
    write(MAKE_PANELS, s2)
    print(f"[bunny] make_panel_world BUNNY -> {aabb}")

    # 3) GT translations (bunny + mug branches use the model pose vector)
    old_vec = f"np.array([{fmt(cur[0])}, {cur[1]:.2f}, {fmt(cur[2])}])"
    new_vec = f"np.array([{fmt(new[0])}, {new[1]:.2f}, {fmt(new[2])}])"
    for p in GT_FILES:
        replace_or_die(p, old_vec, new_vec)

    # 4) target position (bunny branch of get_target_position)
    old_t = f"return np.array([{cur[0]:.2f}, {cur[1]:.2f}, {cur[2] + TARGET_Z_OFF:.2f}])"
    new_t = f"return np.array([{new[0]:.2f}, {new[1]:.2f}, {new[2] + TARGET_Z_OFF:.2f}])"
    replace_or_die(FC, old_t, new_t, expect=1)

    # 5) regenerate panel stage worlds around the new AABB
    subprocess.run([sys.executable, MAKE_PANELS, "--stages-all"], check=True,
                   cwd=RH, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, MAKE_PANELS, "--stage", "1"], check=True,
                   cwd=RH, stdout=subprocess.DEVNULL)
    print("[bunny] panel stage worlds regenerated")

    # 6) verification: GT mesh bbox == BUNNY AABB; panels outside new ROI
    import xml.etree.ElementTree as ET
    ns = {"ns": "http://www.collada.org/2005/11/COLLADASchema"}
    root = ET.parse(os.path.join(RH, "src/simulation_environment/meshes/bunny.dae")).getroot()
    arr = root.find(".//ns:float_array[@id='bun_zipper-mesh-positions-array']", ns)
    v = np.array(list(map(float, arr.text.split()))).reshape(-1, 3)
    gt = np.column_stack([-v[:, 0], v[:, 2], v[:, 1] - 0.05]) * 1.2 + np.array(new)
    for i, a in enumerate("xyz"):
        lo, hi = gt[:, i].min(), gt[:, i].max()
        if abs(lo - aabb[a][0]) > 2e-3 or abs(hi - aabb[a][1]) > 2e-3:
            sys.exit(f"[bunny] VERIFY FAIL: GT {a}[{lo:.3f},{hi:.3f}] != AABB {aabb[a]}")
    print("[bunny] VERIFY: GT mesh bbox == BUNNY AABB OK")

    tgt = np.array([new[0], new[1], new[2] + TARGET_Z_OFF])
    roi = [(tgt[i] - 0.095, tgt[i] + 0.095) for i in range(3)]
    man = json.load(open(os.path.join(
        RH, "src/simulation_environment/panels_occluders_stage4.json")))
    for p in man["panels"]:
        c, h = p["center"], [x - 0.003 for x in p["half"]]
        if all(c[i] - h[i] < roi[i][1] and c[i] + h[i] > roi[i][0] for i in range(3)):
            sys.exit(f"[bunny] VERIFY FAIL: panel {p['face']} intersects ROI")
    print("[bunny] VERIFY: all stage-4 panels outside ROI OK")
    print("\n[bunny] DONE. RESTART the Gazebo stack. Legacy worlds "
          "(frontal/tunnel/well/...) were NOT moved — don't use them.")


if __name__ == "__main__":
    main()
