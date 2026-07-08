#!/usr/bin/env python3
"""
make_panel_world.py — generate ur5e_world_panels.sdf with IDENTICAL-thickness
occlusion panels around the bunny, plus a JSON manifest of panel AABBs that the
planners use to exclude panel voxels from F1 scoring.

Modes
-----
0) STAGED WALLS (recommended):  --stage N   (N = 1..6)
   Walls with identical height (--wall-height, default 0.184), bottom-
   anchored 1 cm below the bunny so the head/ears stay visible over the top;
   widths span each face edge-to-edge and walls TOUCH at the corners:
       --stage 1   side wall only (--side, default right/+X)
       --stage 2   TUNNEL: both side walls (front/back/top open)
       --stage 3   U-shape: tunnel + front
       --stage 4   4 walls (front, back, both sides), top open
       --stage 5   stage-4 walls + bottom lid flush under the walls (top open)
       --stage 6   stage 5 + top lid resting ON the wall tops (sealed; the
                   bunny's ears clip through it — accepted, the real target
                   is a coffee mug that fits fully under the wall tops)
       python3 make_panel_world.py --stage 2

1) SEALED BOX:  --box N   (N = 1..6)
   Builds the first N faces of a tight closed box around the bunny, 1 cm off
   the mesh AABB (bunny X=[0.427,0.614] Y=[-0.374,-0.229] Z=[0.98,1.165], see
   ur5e_world_well.sdf). Face order (override with --faces):
       front(+Y, camera side), left(-X), right(+X), back(-Y), top, bottom
   --box 6 = fully closed box. Faces meet exactly at the edges (no gaps).

       python3 make_panel_world.py --box 1     # stage 1: frontal panel
       python3 make_panel_world.py --box 3     # front + left + right
       python3 make_panel_world.py --box 6     # fully closed box

2) RING:  --az "0,60,300"
   N identical WxH panels on a ring of --radius around the bunny, one per
   azimuth (0=front/+Y, 90=+X, 180=behind, 270=-X — reach_map convention).

Run the scenario with OCC=panels (or any label starting with "panels", e.g.
OCC=panels3 so the results dir is named per stage):
    OCC=panels3 ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py
    OCC=panels3 PLANNER=gradient ./run_ros2_gz.sh
The world is written to src + install worlds dirs (no colcon rebuild), but the
Gazebo stack must be RESTARTED after regenerating. The manifest is written to
src/simulation_environment/panels_occluders.json.
"""
import argparse
import json
import math
import os
import shutil
import sys

HOME = os.path.expanduser("~")
SRC_WORLDS = os.path.join(HOME, "ros2_ws/src/ur5e_l515_description/worlds")
INSTALL_WORLDS = [
    os.path.join(HOME, "ros2_ws/install/ur5e_l515_description/share/ur5e_l515_description/worlds"),
    os.path.join(HOME, "install/ur5e_l515_description/share/ur5e_l515_description/worlds"),
]
BASE_WORLD = os.path.join(SRC_WORLDS, "ur5e_world.sdf")
OUT_NAME = "ur5e_world_panels.sdf"
MANIFEST = os.path.join(HOME, "Desktop/RecedingHorizon/src/simulation_environment/panels_occluders.json")

# Target-object AABBs in world coordinates. Panels are built around the
# selected target (--target); the launch file swaps the mesh at runtime
# (TARGET=mug/tomato), so a panels world sized for the mug MUST be run with
# the matching TARGET or the panels won't fit.
#   bunny: bunny.dae scale 1.2 at pose 0.5 -0.30 0.85
#   mug:   coffee_mug.dae scale 1.0 at pose 0.5 -0.30 0.85; local mesh bounds
#          x[-0.035,0.082] y[-0.035,0.035] z[0,0.10] (handle juts out in +X)
TARGETS = {
    "bunny": {"x": (0.427, 0.614), "y": (-0.374, -0.229), "z": (0.830, 1.015)},
    "mug":   {"x": (0.465, 0.582), "y": (-0.335, -0.265), "z": (0.850, 0.950)},
}
BUNNY = TARGETS["bunny"]  # default target AABB; overridden by --target in main()
FACE_ORDER = ["front", "left", "right", "back", "top", "bottom"]
def stage_faces(side: str):
    """Aperture-based stage progression: each stage closes exactly one more
    viewing 'door', so difficulty rises monotonically for BOTH planners.
      S1 side only         -> with side='right' (default) only the barely-
                              arm-reachable +X door closes: gentlest rung,
                              the frontal door stays open for both planners
      S2 TUNNEL            -> identical wall on the OPPOSITE side: both side
                              doors closed, front/back/top still open
      S3 U (tunnel+front)  -> the punishing frontal door closes too
      S4 4 walls           -> back door also closed; top aperture remains
      S5 + bottom lid      -> the SAME 4 walls plus a bottom lid flush under
                              them (z=[0.78,0.80]); the top door stays open
      S6 + top lid         -> S5 plus a top lid resting ON the wall tops
                              (z=[0.984,1.004]): sealed. With the bunny the
                              ears (up to 1.015) clip through the lid —
                              accepted (user, 2026-07-06): the real target
                              object is a coffee mug, shorter than the walls
    ALL stages reuse identical panels (lids = the stage-6-box lids): the
    ONLY variable across the ladder is the panel count (1,2,3,4,5,6).
    S5-S6 are built in stage_panels()."""
    other = "right" if side == "left" else "left"
    return {1: [side],
            2: [side, other],
            3: [side, other, "front"],
            4: [side, other, "front", "back"]}


BOTTOM_STAGE = 5
SEALED_STAGE = 6

PANEL_TEMPLATE = """
    <!-- panel #{idx} ({label}): size {sx:.3f}x{sy:.3f}x{sz:.3f} -->
    <model name="panel_{idx}">
      <static>true</static>
      <pose>{x:.3f} {y:.3f} {z:.3f} 0 0 {yaw:.4f}</pose>
      <link name="link">
        <collision name="collision">
          <geometry><box><size>{sx:.3f} {sy:.3f} {sz:.3f}</size></box></geometry>
        </collision>
        <visual name="visual">
          <geometry><box><size>{sx:.3f} {sy:.3f} {sz:.3f}</size></box></geometry>
          <material><ambient>0.8 0.6 0.2 1</ambient><diffuse>0.8 0.6 0.2 1</diffuse><specular>0.2 0.2 0.2 1</specular></material>
        </visual>
      </link>
    </model>
"""


def box_faces(gap: float, t: float):
    """Panel (label, center, size) for each face of the tight box:
    bunny AABB + gap on every side, panels t thick.

    Every panel is only `gap` larger than the bunny silhouette. The closed box
    still seals without oversizing: front/back panels span exactly x∈[x0,x1]
    and the side walls (which sit at x∈[x0-t,x0] / [x1,x1+t] and span
    y∈[y0-t,y1+t]) fill the corners; only the top/bottom lids must overhang to
    cover the wall tops."""
    x0, x1 = BUNNY["x"][0] - gap, BUNNY["x"][1] + gap
    y0, y1 = BUNNY["y"][0] - gap, BUNNY["y"][1] + gap
    z0, z1 = BUNNY["z"][0] - gap, BUNNY["z"][1] + gap
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
    return {
        "front":  ((cx, y1 + t / 2, cz), (sx, t, sz)),
        "back":   ((cx, y0 - t / 2, cz), (sx, t, sz)),
        "left":   ((x0 - t / 2, cy, cz), (t, sy + 2 * t, sz)),
        "right":  ((x1 + t / 2, cy, cz), (t, sy + 2 * t, sz)),
        "top":    ((cx, cy, z1 + t / 2), (sx + 2 * t, sy + 2 * t, t)),
        "bottom": ((cx, cy, z0 - t / 2), (sx + 2 * t, sy + 2 * t, t)),
    }


def staged_walls(n: int, h: float, gap: float, t: float, side: str = "right"):
    """Wall panels for --stage N, all with the same height h, bottom-anchored
    at bunny_bottom - gap so the head/ears peek over the top edge.

    Widths span each bunny face edge-to-edge and the walls MEET at the
    corners with no gaps (same construction as the sealed box, just shorter):
    front/back span exactly x∈[x0,x1]; left/right sit at x∈[x0-t,x0] /
    [x1,x1+t] and span y∈[y0-t,y1+t], filling the corners."""
    x0, x1 = BUNNY["x"][0] - gap, BUNNY["x"][1] + gap
    y0, y1 = BUNNY["y"][0] - gap, BUNNY["y"][1] + gap
    z0 = BUNNY["z"][0] - gap
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    zc = z0 + h / 2
    geo = {
        "front": ((cx, y1 + t / 2, zc), (x1 - x0, t, h)),
        "back":  ((cx, y0 - t / 2, zc), (x1 - x0, t, h)),
        "left":  ((x0 - t / 2, cy, zc), (t, (y1 - y0) + 2 * t, h)),
        "right": ((x1 + t / 2, cy, zc), (t, (y1 - y0) + 2 * t, h)),
    }
    return [(f, *geo[f]) for f in stage_faces(side)[n]]


def stage_panels(n: int, h: float, gap: float, t: float, side: str = "right"):
    """(label, center, size) list for stage n. Stages 1-4 are the short
    bottom-anchored walls; stage BOTTOM_STAGE (5) adds a bottom lid flush
    under the same walls (top open); stage SEALED_STAGE (6) additionally
    rests a top lid ON the wall tops (bunny ears clip through it — accepted,
    the real target is a coffee mug that fits under the wall tops)."""
    if n in (BOTTOM_STAGE, SEALED_STAGE):
        walls = staged_walls(4, h, gap, t, side)
        geo = box_faces(gap, t)
        panels = walls + [("bottom", *geo["bottom"])]
        if n == SEALED_STAGE:
            (cx, cy, _), size = geo["top"]
            z_top = BUNNY["z"][0] - gap + h + t / 2  # resting on the wall tops
            panels.append(("top", (cx, cy, z_top), size))
        return panels
    return staged_walls(n, h, gap, t, side)


def lshape_panels(gap, t, side="right"):
    """L-shape occluder: two FULL-HEIGHT walls meeting at a corner (an 'L' in
    top view). The FRONT panel (+Y, between the camera/robot and the target)
    plus one SIDE wall (default right/+X). Same edge-to-edge construction as
    the sealed box, so the two walls meet cleanly at the +Y/side corner; the
    opposite side and the back stay open. Sized around the --target AABB."""
    geo = box_faces(gap, t)
    return [("front", *geo["front"]), (side, *geo[side])]


def rotated_half_extents(w, t, h, yaw):
    """Axis-aligned half extents of a WxTxH box rotated by yaw about Z."""
    c, s = abs(math.cos(yaw)), abs(math.sin(yaw))
    return (c * w / 2 + s * t / 2, s * w / 2 + c * t / 2, h / 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--stages-all", action="store_true",
                      help="build ALL stages as separate worlds "
                           "(ur5e_world_panels1..6.sdf) + per-stage manifests; "
                           "run once, then just switch OCC=panels1/2/.../6")
    mode.add_argument("--stage", type=int, metavar="N",
                      help="staged walls: 1=side wall, 2=+other side (tunnel), "
                           "3=+front (U), 4=+back (top open), "
                           "5=stage-4 walls + bottom lid (top open), "
                           "6=stage 5 + top lid on the wall tops (sealed); "
                           "side wall chosen by --side")
    mode.add_argument("--box", type=int, metavar="N",
                      help="sealed box: first N faces (1..6) of a closed box")
    mode.add_argument("--az",
                      help="ring mode: comma-separated azimuths in degrees")
    mode.add_argument("--lshape", action="store_true",
                      help="L-shape: front panel + one side wall meeting at a "
                           "corner (full height, sized to --target). Writes "
                           "ur5e_world_panels8.sdf + stage-8 manifest; run with "
                           "OCC=panels8 and the matching TARGET")
    ap.add_argument("--target", choices=list(TARGETS), default="bunny",
                    help="object the panels are sized around. mug is much "
                         "smaller than bunny, so mug panels won't fit a bunny "
                         "(and vice-versa) — run OCC=panels<N> with the TARGET "
                         "that matches how the world was built")
    ap.add_argument("--side", choices=("left", "right"), default="right",
                    help="which side wall the stages start from. right (+X) = "
                         "easier (arm can barely reach +X viewpoints anyway); "
                         "left (-X) = harder (blocks the reachable side)")
    ap.add_argument("--wall-height", type=float, default=0.184,
                    help="stage-mode wall height in metres. Default 0.184 with "
                         "gap 0.03 → bottom z=0.95, top edge z=1.134 (bunny "
                         "ears visible above); widths span each face so walls "
                         "touch at the corners")
    ap.add_argument("--faces", default=",".join(FACE_ORDER),
                    help=f"box-mode face order (default {','.join(FACE_ORDER)})")
    ap.add_argument("--gap", type=float, default=0.03,
                    help="clearance between bunny AABB and panels (m). Default "
                         "0.03 keeps every wall OUTSIDE the ±0.095 evaluation "
                         "ROI cube (bunny faces sit 2.1-2.4 cm inside the ROI "
                         "edge), so panel voxels never pollute ROI coverage. "
                         "0.01 = the old 'hugging' layout (panels inside ROI).")
    ap.add_argument("--front-scale", type=float, default=1.0,
                    help="box-mode difficulty knob: scale the FRONT panel only "
                         "(width centred, height bottom-anchored so the bunny's "
                         "head/ears peek over the top). <1 makes the scenario "
                         "easier; note the closed box is then no longer fully "
                         "sealed at the front rim")
    ap.add_argument("--size", default="0.22x0.22",
                    help="ring-mode panel WxH in metres (same for ALL panels)")
    ap.add_argument("--thick", type=float, default=0.02, help="panel thickness (m)")
    ap.add_argument("--radius", type=float, default=0.13,
                    help="ring-mode radius from bunny centre to panel centre (m)")
    ap.add_argument("--center", default="0.52,-0.30",
                    help="ring-mode centre x,y (bunny mesh centre)")
    ap.add_argument("--z", type=float, default=1.07,
                    help="ring-mode panel centre height (m)")
    ap.add_argument("--out", default=OUT_NAME, help="output world file name")
    args = ap.parse_args()

    global BUNNY
    BUNNY = TARGETS[args.target]  # size all panels around the chosen target

    t = args.thick
    panels = []  # (label, center(3), size(3), yaw, aabb_half(3))

    if args.stages_all:
        build_all_stages(args.wall_height, args.gap, t, args.side)
        return
    if args.lshape:
        out_name = args.out if args.out != OUT_NAME else "ur5e_world_panels8.sdf"
        manifest = stage_manifest_path(8)
        for label, center, size in lshape_panels(args.gap, t, args.side):
            panels.append((label, center, size, 0.0,
                           (size[0] / 2, size[1] / 2, size[2] / 2)))
        emit(panels, f"lshape-{args.target}", out_name, manifest)
        print(f"\n[panels] L-shape ({args.target}): {len(panels)} panel(s), "
              f"thickness {t:.3f} m -> {out_name}")
        print(f"[panels] Launch with OCC=panels8 TARGET={args.target} "
              "(restart the Gazebo stack).")
        return
    if args.stage is not None:
        valid = sorted(stage_faces(args.side)) + [BOTTOM_STAGE, SEALED_STAGE]
        if args.stage not in valid:
            sys.exit(f"[panels] --stage must be one of {valid}")
        for label, center, size in stage_panels(args.stage, args.wall_height,
                                                args.gap, t, args.side):
            panels.append((label, center, size, 0.0,
                           (size[0] / 2, size[1] / 2, size[2] / 2)))
        scenario = f"stage{args.stage}"
    elif args.box is not None:
        faces = [f.strip() for f in args.faces.split(",")]
        unknown = set(faces) - set(FACE_ORDER)
        if unknown or not 1 <= args.box <= len(faces):
            sys.exit(f"[panels] --box must be 1..{len(faces)}; faces must be from {FACE_ORDER}")
        geo = box_faces(args.gap, t)
        if args.front_scale != 1.0:
            (cx, fy, _), (sx, st, sz) = geo["front"]
            new_sz = sz * args.front_scale
            z_bottom = BUNNY["z"][0] - args.gap  # keep bottom edge, expose the top
            geo["front"] = ((cx, fy, z_bottom + new_sz / 2),
                            (sx * args.front_scale, st, new_sz))
        for label in faces[: args.box]:
            center, size = geo[label]
            panels.append((label, center, size, 0.0,
                           (size[0] / 2, size[1] / 2, size[2] / 2)))
        scenario = f"box{args.box}" + (
            f"-fs{args.front_scale:g}" if args.front_scale != 1.0 else "")
    else:
        w, h = (float(v) for v in args.size.lower().split("x"))
        cx, cy = (float(v) for v in args.center.split(","))
        azimuths = [float(v) for v in args.az.split(",") if v.strip() != ""]
        if not azimuths:
            sys.exit("[panels] --az produced no azimuths")
        for az in azimuths:
            az_rad = math.radians(az)
            x = cx + args.radius * math.sin(az_rad)
            y = cy + args.radius * math.cos(az_rad)
            # yaw=-az aligns the box's thin (local Y) axis with the radial
            # direction, so the panel face points at the bunny.
            panels.append((f"az{az:.0f}", (x, y, args.z), (w, t, h), -az_rad,
                           rotated_half_extents(w, t, h, az_rad)))
        scenario = "ring" + "-".join(f"{a:.0f}" for a in azimuths)

    emit(panels, scenario, args.out, MANIFEST)
    print(f"\n[panels] scenario '{scenario}': {len(panels)} panel(s), thickness {t:.3f} m.")
    print("[panels] Restart the Gazebo stack with OCC=panels<stage> to load the new world.")


def emit(panels, scenario, out_name, manifest_path):
    """Write one world SDF (src + install copies) and its occluder manifest."""
    with open(BASE_WORLD) as f:
        base = f.read()
    if "</world>" not in base:
        sys.exit(f"[panels] no </world> tag in {BASE_WORLD}")

    blocks, manifest_panels = [], []
    for i, (label, c, s, yaw, half) in enumerate(panels, start=1):
        blocks.append(PANEL_TEMPLATE.format(
            idx=i, label=label, x=c[0], y=c[1], z=c[2], yaw=yaw,
            sx=s[0], sy=s[1], sz=s[2]))
        # +3 mm (one voxel) pad so the reconstructed panel shell is also
        # excluded from F1; small enough not to eat bunny-surface voxels
        # across the --gap clearance.
        manifest_panels.append({
            "name": f"panel_{i}", "face": label,
            "center": [round(v, 4) for v in c],
            "half": [round(v + 0.003, 4) for v in half],
        })
        print(f"[panels] panel_{i} ({label}): centre=({c[0]:.3f}, {c[1]:.3f}, {c[2]:.3f})"
              f"  size={s[0]:.3f}x{s[1]:.3f}x{s[2]:.3f}")

    world = base.replace("  </world>", "".join(blocks) + "\n  </world>")

    out_src = os.path.join(SRC_WORLDS, out_name)
    with open(out_src, "w") as f:
        f.write(world)
    print(f"[panels] wrote {out_src}")
    for d in INSTALL_WORLDS:
        if os.path.isdir(d):
            shutil.copy(out_src, os.path.join(d, out_name))

    with open(manifest_path, "w") as f:
        json.dump({"scenario": scenario, "panels": manifest_panels}, f, indent=2)
    print(f"[panels] manifest -> {manifest_path}")


def stage_manifest_path(n):
    root, ext = os.path.splitext(MANIFEST)
    return f"{root}_stage{n}{ext}"


def build_all_stages(wall_height, gap, t, side="right"):
    """Pre-build one world + manifest per stage so OCC=panels<N> selects the
    scenario directly at launch time — no regeneration between experiments."""
    for n in sorted(stage_faces(side)) + [BOTTOM_STAGE, SEALED_STAGE]:
        panels = [(label, center, size, 0.0,
                   (size[0] / 2, size[1] / 2, size[2] / 2))
                  for label, center, size in stage_panels(n, wall_height, gap, t, side)]
        print(f"\n--- stage {n} ---")
        emit(panels, f"stage{n}", f"ur5e_world_panels{n}.sdf", stage_manifest_path(n))
    print(f"\n[panels] All stages built. Launch with OCC=panels1 ... panels{SEALED_STAGE} —")
    print("[panels] the launch file and the F1-occluder loader pick the right")
    print("[panels] world/manifest from the OCC label automatically.")


if __name__ == "__main__":
    main()
