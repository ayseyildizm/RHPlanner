"""
fair_comparison_config.py — single source of truth for every parameter that
MUST be identical between the RH-NBV planner and the GradientNBV baseline.

Both test_rh_node.py (via viewpoint_planning.py) and test_gradient_node.py
import from here, so the two planners can never silently drift apart again.
Any value that affects the reconstruction volume, the evaluation ROI, the
camera workspace, the robot reach, or the per-trial start perturbation lives
HERE and nowhere else.

Rationale for each value is documented inline; all are overridable via env
vars so ablations stay reproducible.
"""
import os
import numpy as np

# ---------------------------------------------------------------------------
# Target node (centre of the ROI on the object surface).
# Camera starts at Y=+0.20 (target_y + 0.60 m standoff) and looks toward -Y.
# ---------------------------------------------------------------------------
def get_target_position() -> np.ndarray:
    tp_env = os.environ.get("TARGET_POS")
    if tp_env:
        return np.array([float(v) for v in tp_env.split(",")])
    target = os.environ.get("TARGET", "bunny").lower()
    if target == "tomato":
        tt = os.environ.get("TOMATO_TARGET", "blossom").lower()
        if tt == "fruit":
            return np.array([0.50, -0.50, 1.16])   # Fruit1-4 centroid
        elif tt == "all":
            return np.array([0.50, -0.50, 1.20])   # full plant centroid
        else:                                        # blossom (default)
            return np.array([0.50, -0.50, 1.30])   # Blossom1-3 centroid
    # Bunny spawn (0.50, -0.30, 1.0). COLLADA node matrix gives world Z∈[0.980,1.165],
    # geometric centre Z=1.073. ROI z=1.073±0.075=[0.998,1.148] covers 97% of bunny height.
    # Camera starts at y=-0.30+0.60=+0.30. Workspace y∈[+0.20,+0.40].
    # Camera-bunny y∈[0.50,0.70m] = D455 ideal range.
    # (A closer position, x030_y-015_z075 at 0.30,-0.15,0.75, was tried based
    # on reach_map_multi.py's sweep — it unlocked a much wider camera orbit
    # arc in the abstract IK test, but the real bunny mesh sitting at that
    # exact spot caused live arm/camera collisions once actually placed
    # there, so reverted back to this original, collision-safe position.)
    return np.array([0.50, -0.30, 0.92])


# ---------------------------------------------------------------------------
# VoxelGrid reconstruction volume.
# The depth axis is Y (camera looks along -Y), so the grid is widest in Y.
# This MUST be identical for both planners — a different grid_size changes the
# physical reconstruction volume, the coverage denominator, and which voxels
# survive the ROI crop, invalidating any RH-vs-GradientNBV comparison.
# ---------------------------------------------------------------------------
GRID_SIZE  = np.array([0.3, 0.6, 0.3])
VOXEL_SIZE = np.array([0.003])


# ---------------------------------------------------------------------------
# Evaluation ROI and F1 matching threshold.
# Mirrors voxel_grid.set_target_roi (+/-25 voxels = +/-75mm at 3mm voxels).
# F1_THRESH default = 4x voxel size (~12mm) to account for the reconstructed
# occupancy shell sitting ~9-13mm off the continuous mesh surface (true for
# BOTH planners in this setup). Identical for both => fair.
# ---------------------------------------------------------------------------
ROI_HALF        = float(os.environ.get("ROI_HALF", 0.095))  # ±31 voxels @ 3mm = 93mm ≈ bunny z_max
F1_THRESH_SCALE = 4.0  # x voxel_size


# ---------------------------------------------------------------------------
# Axis-aligned camera workspace: start_pose +/- this half-width.
# This is Burusa's GradientNBV box; RH mirrors it exactly in rh_planner.py.
# ---------------------------------------------------------------------------
# UR5e + D455. Bunny at y=-0.30, standoff 0.60 m → start_y=+0.30. With ±0.10
# bounds in y, camera-bunny stays in [0.50, 0.70 m] = D455 ideal range exactly.
# x_hw=0.35: camera reaches x=[0.15,0.85], up to ~60° side-view angle.
# z_hw=0.22: camera reaches z=[0.85,1.29], top-down views of bunny back/ears.
# Overridable via CAM_HW="x,y,z".
def _cam_halfwidths() -> np.ndarray:
    env = os.environ.get("CAM_HW")
    if env:
        return np.array([float(v) for v in env.split(",")], dtype=np.float32)
    return np.array([0.35, 0.10, 0.22], dtype=np.float32)


CAMERA_BOUNDS_HALFWIDTHS = _cam_halfwidths()

# ---------------------------------------------------------------------------
# Front-only fix. The old box (start ± halfwidths → y ∈ [+0.20, +0.40]) kept
# the camera strictly on the +Y side of the bunny, so every view was frontal
# and occlusion panels could not be planned around. CAM_WRAP_Y extends the -Y
# face of the box toward/past the object so side views enter the search space:
# with the default 0.60 the box reaches y=-0.40, i.e. 0.10 m past the bunny
# centre plane, giving true ±90° side positions at x=0.15/0.85.
# reach_map_multi_results.csv (bunny 0.50,-0.30,1.0): az 0/±30° reachable at
# r=0.40 and az 270° (-X side) at r=0.50-0.60, so parts of the wrapped box are
# NOT reachable — those poses fail move_arm_to_pose and are pruned at runtime
# by the reach-bounds tightening in viewpoint_planning.run_rh().
# CAM_WRAP_Y=0 restores the original frontal-only box.
# ---------------------------------------------------------------------------
CAM_WRAP_Y = float(os.environ.get("CAM_WRAP_Y", 0.60))

# Minimum camera-to-TARGET standoff. The Gazebo D455 depth AND color cameras
# have a 0.40 m near clip (ur5e_l515.urdf.xacro): any surface closer than that
# is clipped out of both images. Applied by ALL planners (RH sampling,
# GradientNBV/PSO clamp, Random selection) — identical for everyone => fair.
#
# 0.45 (was 0.50): the widened orbit arc unlocked by lowering the bunny to
# z=0.85 was measured at r=0.40-0.45 (reach_map_multi); 0.50 locked it out
# entirely. At 0.45 the nearest object surfaces (~0.35 m) lose some pixels to
# the near clip, but those pixels are neutralized in the ray sampler (no
# corruption) — a partial view from the side is worth far more than no side
# view at all.
MIN_STANDOFF = float(os.environ.get("CAM_MIN_STANDOFF", 0.45))


def push_out_of_standoff(position: np.ndarray, target: np.ndarray) -> np.ndarray:
    """If position is closer than MIN_STANDOFF to target, push it radially out
    to MIN_STANDOFF. Returns a copy; positions already outside are unchanged."""
    p = np.array(position, dtype=float, copy=True)
    t = np.asarray(target, dtype=float)[:3]
    vec = p[:3] - t
    dist = float(np.linalg.norm(vec))
    if dist >= MIN_STANDOFF:
        return p
    if dist < 1e-6:
        vec = np.array([0.0, 1.0, 0.0])
        dist = 1.0
    p[:3] = t + vec / dist * MIN_STANDOFF
    return p


def camera_bounds_for_start(start_pose: np.ndarray) -> np.ndarray:
    """Shared camera workspace box, shape (2,3) [lo, hi]:
    start ± CAMERA_BOUNDS_HALFWIDTHS, with the -Y face pushed a further
    CAM_WRAP_Y toward/past the object so side views are searchable.
    Used identically by the RH, GradientNBV, PSO and Random planners."""
    s = np.asarray(start_pose, dtype=np.float32)[:3]
    lo = s - CAMERA_BOUNDS_HALFWIDTHS
    hi = s + CAMERA_BOUNDS_HALFWIDTHS
    lo[1] -= CAM_WRAP_Y
    return np.array([lo, hi], dtype=np.float32)


# ---------------------------------------------------------------------------
# RH's robot reach clamp. RH keeps its own internal reach-clamp mechanism
# (needed on the real arm), but for the fair simulation comparison its bounds
# are set EQUAL to the shared camera_bounds box, so RH's clamp can never make
# its usable workspace smaller than GradientNBV's. Both planners then search
# the identical physical region; only their search STRATEGY differs.
#
# Because camera_bounds depend on the (jittered) start pose, the reach box is
# computed per start pose via reach_bounds_for_start(). The old fixed box
# [[0.30,-0.15,0.97],[0.65,0.05,1.25]] left RH only 55-82% of GradientNBV's
# volume — an unfair handicap — and is replaced by this start-aligned box.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# OCC=panels* scenarios: make_panel_world.py writes the generated panels'
# AABBs here so calculate_F1 can exclude panel voxels — the panel layout is
# data, not code, and both planners must exclude the exact same regions.
# ---------------------------------------------------------------------------
PANELS_MANIFEST = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "simulation_environment", "panels_occluders.json"))


def load_panel_occluders():
    """Occluder AABBs for the active OCC=panels* scenario.

    OCC=panels<N> loads the per-stage manifest panels_occluders_stage<N>.json
    (written by make_panel_world.py --stages-all), matching the world the
    launch file loads for the same label. Bare OCC=panels — or a missing
    stage manifest — falls back to the single panels_occluders.json.
    Returns [(center ndarray(3), half_extents ndarray(3)), ...] or None."""
    import json
    candidates = []
    occ = os.environ.get("OCC", "").lower()
    suffix = occ[len("panels"):] if occ.startswith("panels") else ""
    if suffix:
        root, ext = os.path.splitext(PANELS_MANIFEST)
        candidates.append(f"{root}_stage{suffix}{ext}")
    candidates.append(PANELS_MANIFEST)
    path = next((p for p in candidates if os.path.exists(p)), None)
    if path is None:
        print(f"[panels] WARNING: no manifest found (looked for {candidates}) "
              "— run make_panel_world.py; panel voxels will NOT be excluded from F1")
        return None
    with open(path) as f:
        data = json.load(f)
    out = [(np.array(p["center"], dtype=float), np.array(p["half"], dtype=float))
           for p in data.get("panels", [])]
    print(f"[panels] loaded {len(out)} occluder AABB(s) "
          f"(scenario: {data.get('scenario', '?')}) from {os.path.basename(path)}")
    return out or None


def reach_bounds_for_start(start_pose: np.ndarray) -> np.ndarray:
    """Reach box = the shared camera workspace box (camera_bounds_for_start),
    so RH's clamp can never make its usable workspace smaller than
    GradientNBV's. Returns shape (2,3): [lo, hi]."""
    return camera_bounds_for_start(start_pose)


# ---------------------------------------------------------------------------
# Per-trial start-pose perturbation (Burusa's +/-3cm ROI/start uncertainty).
# Trial 0 is deterministic (seed None); trial t>0 uses BASE_SEED + t.
# Both planners MUST use this same logic so trial t starts both from the same
# perturbed pose (paired comparison + matched variance).
# ---------------------------------------------------------------------------
START_JITTER = 0.03
BASE_SEED    = int(os.environ.get("BASE_SEED", 42))


def seed_for_trial(trial_idx: int):
    """Deterministic trial 0; reproducible jitter seed for later trials."""
    return None if trial_idx == 0 else (BASE_SEED + trial_idx)


def jitter_start_pose(start_pose: np.ndarray, trial_idx: int) -> np.ndarray:
    """Apply the same reproducible +/-START_JITTER perturbation both planners
    use. Operates on the position (first 3 entries) only; orientation is
    recomputed by look_at toward the target downstream. Returns a copy."""
    pose = np.array(start_pose, dtype=float).copy()
    seed = seed_for_trial(trial_idx)
    if seed is not None:
        rng = np.random.default_rng(seed)
        pose[:3] = pose[:3] + rng.uniform(-START_JITTER, START_JITTER, size=3)
    return pose
