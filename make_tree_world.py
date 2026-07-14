#!/usr/bin/env python3
"""
make_tree_world.py — pre-build the tree (tomato) experiment worlds.

Writes, for every (stage, yaw) combination:
  1. ur5e_world_panels_tree_<stage>_y<yaw>.sdf      (src + install worlds dirs)
  2. panels_occluders_stage_tree_<stage>_y<yaw>.json (empty panel list)

Why the "panels" prefix: the launch file loads ur5e_world_panels<suffix>.sdf
directly for any OCC=panels<suffix> label, and the eval side
(fair_comparison_config.load_panel_occluders) looks up the matching
panels_occluders_stage<suffix>.json. Riding that hook means ZERO changes to
the launch file or any bunny/mug file — the manifests are empty, so no voxels
are masked and MoveIt gets no phantom panel obstacles.

The injected tomato model is byte-compatible with the TARGET=tomato patch in
move_group_gz_ur5e.launch.py (same mesh, scale, pose, colors), with two
differences: the model pose carries the stage yaw, and the model is baked
into a world file instead of patched at launch time.

Usage:
    python3 make_tree_world.py            # default: 3 stages x yaws 0/90/180/270
    python3 make_tree_world.py --stages fruit --yaws 0,45,90
"""
import argparse
import json
import os
import re
import sys

HOME = os.path.expanduser("~")
RH = os.path.join(HOME, "Desktop/RecedingHorizon")
MESHES = os.path.join(RH, "src/simulation_environment/meshes")
SIM_ENV = os.path.join(RH, "src/simulation_environment")
SRC_WORLDS = os.path.join(HOME, "ros2_ws/src/ur5e_l515_description/worlds")
INSTALL_WORLDS = os.path.join(
    HOME, "ros2_ws/install/ur5e_l515_description/share/ur5e_l515_description/worlds")

TOMATO_DAE = os.path.join(MESHES, "tomato6.dae")
POSE_XYZ = "0.5 -0.50 0.9"   # must match tomato_gt.TRANSLATION
SCALE = "0.4 0.4 0.4"        # must match tomato_gt.SCALE

# Colors per stage — identical to the TARGET=tomato branch of
# move_group_gz_ur5e.launch.py. Red = segmenter-visible target class.
_BROWN, _GREEN = (0.18, 0.08, 0.02), (0.05, 0.28, 0.05)
_RED, _YELLOW, _ORANGE = (0.80, 0.10, 0.10), (0.70, 0.60, 0.05), (0.75, 0.35, 0.00)
STAGE_COLORS = {
    # stage: (branch, leaf, blossom, fruit)
    "fruit":   (_BROWN, _GREEN, _YELLOW, _RED),
    "blossom": (_BROWN, _GREEN, _RED, _ORANGE),
    "all":     (_RED, _RED, _RED, _RED),
}
SUBMESHES = [
    ("branch1", "Branch1", 0), ("leaf1", "Leaf1", 1), ("leaf2", "Leaf2", 1),
    ("blossom1", "Blossom1", 2), ("blossom2", "Blossom2", 2),
    ("blossom3", "Blossom3", 2),
    ("fruit1", "Fruit1", 3), ("fruit2", "Fruit2", 3),
    ("fruit3", "Fruit3", 3), ("fruit4", "Fruit4", 3),
]


def _vis(name, submesh, rgb):
    r, g, b = rgb
    return (
        f'        <visual name="{name}">\n'
        f'          <geometry><mesh>\n'
        f'            <uri>file://{TOMATO_DAE}</uri>\n'
        f'            <submesh><name>{submesh}</name></submesh>\n'
        f'            <scale>{SCALE}</scale>\n'
        f'          </mesh></geometry>\n'
        f'          <material>\n'
        f'            <ambient>{r} {g} {b} 1</ambient>\n'
        f'            <diffuse>{r} {g} {b} 1</diffuse>\n'
        f'            <emissive>{r*0.3:.2f} {g*0.3:.2f} {b*0.3:.2f} 1</emissive>\n'
        f'          </material>\n'
        f'        </visual>\n'
    )


def tomato_model(stage, yaw_deg):
    colors = STAGE_COLORS[stage]
    yaw_rad = yaw_deg * 3.141592653589793 / 180.0
    visuals = "".join(_vis(n, sm, colors[ci]) for n, sm, ci in SUBMESHES)
    return (
        '    <model name="tomato">\n'
        '      <static>true</static>\n'
        f'      <pose>{POSE_XYZ} 0 0 {yaw_rad:.9f}</pose>\n'
        '      <link name="link">\n'
        '        <collision name="collision">\n'
        '          <geometry>\n'
        '            <box><size>0.30 0.30 0.58</size></box>\n'
        '          </geometry>\n'
        '        </collision>\n'
        + visuals +
        '      </link>\n'
        '    </model>'
    )


def build(stage, yaw_deg):
    label = f"tree_{stage}_y{yaw_deg:03d}"
    base_path = os.path.join(SRC_WORLDS, "ur5e_world.sdf")
    with open(base_path) as f:
        base = f.read()
    if '<model name="bunny">' not in base:
        sys.exit(f"ABORT: no bunny model found in {base_path}")
    world = re.sub(r'<model name="bunny">.*?</model>',
                   tomato_model(stage, yaw_deg), base, count=1, flags=re.DOTALL)

    world_name = f"ur5e_world_panels_{label}.sdf"
    written = []
    for d in (SRC_WORLDS, INSTALL_WORLDS):
        if not os.path.isdir(d):
            print(f"  WARN: {d} missing, skipped")
            continue
        path = os.path.join(d, world_name)
        with open(path, "w") as f:
            f.write(world)
        written.append(path)

    manifest = os.path.join(SIM_ENV, f"panels_occluders_stage_{label}.json")
    with open(manifest, "w") as f:
        json.dump({"scenario": f"panels_{label}",
                   "panels": []}, f, indent=2)
    written.append(manifest)
    return label, written


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="all,blossom,fruit")
    ap.add_argument("--yaws", default="0,90,180,270")
    args = ap.parse_args()

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    yaws = [int(y) for y in args.yaws.split(",")]
    bad = [s for s in stages if s not in STAGE_COLORS]
    if bad:
        sys.exit(f"unknown stage(s) {bad}; valid: {sorted(STAGE_COLORS)}")

    for stage in stages:
        for yaw in yaws:
            label, written = build(stage, yaw)
            print(f"[{label}]  OCC=panels_{label}")
            for p in written:
                print(f"    {p}")
    print("\nDone. Launch with e.g.:")
    print("  OCC=panels_tree_fruit_y090 ros2 launch ur5e_l515_description "
          "move_group_gz_ur5e.launch.py")
