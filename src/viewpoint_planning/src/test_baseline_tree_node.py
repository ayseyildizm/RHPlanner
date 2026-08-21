#!/usr/bin/env python3
"""
test_baseline_tree_node.py — tree/tomato wrapper for the PSO and Random
baselines (PLANNER=pso|random).

test_baseline_node.py and the bunny/mug pipeline are NOT modified. Like
test_gradient_tree_node.py, its main block sits under the __main__ guard, so
this wrapper imports the module (inert) and mirrors that short main flow with
the tomato-specific pieces swapped in:

  * GT comes from tomato_gt.get_mesh_coordinates (yaw-aware, single source of
    truth shared with the RH/gradient wrappers; test_baseline_node's own
    tomato branch has no TREE_YAW support)
  * fair_comparison_config.GRID_SIZE / VOXEL_SIZE mutated in place when the
    env vars are set (both planners default voxel_size to the fc array
    object, so the in-place mutation reaches them without a partial)
  * commanded viewpoints get the same spherical reach clamp as RH
    (execution-layer, planners untouched): positions beyond BASELINE_REACH_R
    of the arm base are pulled radially onto the shell and the look-at
    quaternion is recomputed toward the planner's current look target.
    Without it the blossom/all camera boxes contain UR5e-unreachable corners
    (see test_rh_tree_node.py) and runs fail the 80% move-success gate.

Env: PLANNER=pso|random, TOMATO_TARGET, TREE_YAW, GRID_SIZE, VOXEL_SIZE,
     BASELINE_REACH_R (default 1.0; 0 disables) — rest as test_baseline_node.
"""
import datetime
import json
import os

import numpy as np
import torch

os.environ["TARGET"] = "tomato"  # before any fair_comparison_config import

import viewpoint_planners.fair_comparison_config as fc
from viewpoint_planners import tomato_gt
from utils.torch_utils import look_at_rotation

import test_baseline_node as tb  # __main__ guard keeps the import inert

# NOTE: the D455 color-to-depth insertion correction lives in
# test_baseline_node.insertion_pose (driver-level, shared by bunny/mug/tree).
print("[tree] D455 color-to-depth correction ACTIVE for PSO/Random "
      "(matches GradientNBV/RH insertion)")

if os.environ.get("GRID_SIZE"):
    fc.GRID_SIZE[:] = [float(v) for v in os.environ["GRID_SIZE"].split(",")]
    print(f"[tree] GRID_SIZE -> {fc.GRID_SIZE.tolist()}")

if os.environ.get("VOXEL_SIZE"):
    fc.VOXEL_SIZE[:] = [float(os.environ["VOXEL_SIZE"])]
    print(f"[tree] VOXEL_SIZE -> {float(fc.VOXEL_SIZE[0])}")

# Spherical reach clamp, same radius/base as the RH wrapper. Applied to the
# pose returned by next_view (execution layer): the planner's internal state
# is untouched except that RandomPlanner.viewpoint is updated to the pose the
# arm actually visits, so its neighbour sampling stays anchored to reality.
_ARM_BASE = np.array([0.0, 0.0, 0.525])
_REACH_R = float(os.environ.get("BASELINE_REACH_R", "1.0"))
if _REACH_R > 0:
    _orig_next_view = tb.next_view

    def _next_view_reach_clamped(planner):
        vp, util = _orig_next_view(planner)
        vec = vp[:3] - _ARM_BASE
        d = float(np.linalg.norm(vec))
        if d > _REACH_R:
            vp = np.array(vp, dtype=float, copy=True)
            vp[:3] = _ARM_BASE + vec / d * _REACH_R
            # keep sensor min-depth standoff; if the push moves the pose back
            # outside the shell, reach wins (as in the RH wrapper)
            tgt = getattr(planner, "target_position", None)
            if tgt is None or not isinstance(tgt, np.ndarray):
                tgt = planner.target_params.detach().cpu().numpy()
            vp[:3] = fc.push_out_of_standoff(vp[:3], tgt)
            vec2 = vp[:3] - _ARM_BASE
            d2 = float(np.linalg.norm(vec2))
            if d2 > _REACH_R:
                vp[:3] = _ARM_BASE + vec2 / d2 * _REACH_R
            quat = look_at_rotation(
                torch.tensor(vp[:3], dtype=torch.float32, device=planner.device),
                torch.tensor(tgt, dtype=torch.float32, device=planner.device))
            vp[3:] = quat.detach().cpu().numpy()
            if hasattr(planner, "viewpoint"):
                planner.viewpoint = vp
            _next_view_reach_clamped.count += 1
        return vp, util

    _next_view_reach_clamped.count = 0
    tb.next_view = _next_view_reach_clamped
    print(f"[tree] baseline reach clamp ACTIVE: r<={_REACH_R} m about base "
          f"{_ARM_BASE.tolist()}")


if __name__ == "__main__":
    import ros2_node
    ros2_node.init(f"{tb.PLANNER}_test")

    arm = tb.ArmControlClient()
    perceiver = tb.Perceiver()
    sampler = tb.ViewpointSampler()
    sdf = tb.SDFSpawner()

    occ = tb.detect_occlusion_type()
    tb.spawn_occlusion(sdf, occ)

    # Camera warm-up gate: for the first minutes after a stack (re)start the
    # gz bridge delivers no frames even though `ros2 topic echo --once`
    # succeeds. The fast Random runs (~10 s/view) finished entirely inside
    # that dead window twice (2026-07-18), recording 20 views of zero data.
    # Block until the perceiver actually returns a frame pair.
    import time as _time
    _t0 = _time.time()
    while _time.time() - _t0 < 300:
        _d, _, _s = perceiver.run()
        if _d is not None and _s is not None:
            print(f"[tree] camera stream up after {_time.time() - _t0:.0f}s")
            break
        _time.sleep(2)
    else:
        print("[tree] WARNING: no camera data after 300s — proceeding anyway")

    mesh_coords, mesh_tree = tomato_gt.get_mesh_coordinates()
    run_dir = tb.make_run_dir(occ)

    with open(os.path.join(run_dir, "config.json"), "w") as f:
        json.dump({"experiment": tb.EXPERIMENT, "planner": tb.METHOD_NAME,
                   "num_iters": tb.NUM_ITERS, "num_trials": tb.NUM_TRIALS,
                   "base_seed": tb.BASE_SEED,
                   "grid_size": [float(v) for v in fc.GRID_SIZE],
                   "voxel_size": float(fc.VOXEL_SIZE[0]),
                   "occlusion": occ,
                   "reach_clamp_r": _REACH_R,
                   "tomato_target": os.environ.get("TOMATO_TARGET", "blossom"),
                   "tree_yaw": float(os.environ.get("TREE_YAW", "0")),
                   "roi_half": os.environ.get("ROI_HALF"),
                   "timestamp": datetime.datetime.now().isoformat()}, f, indent=2)

    print(f"\nRun directory: {run_dir}")
    print(f"{tb.METHOD_NAME} tree baseline | {tb.NUM_ITERS} viewpoints | "
          f"Occlusion: {occ} | TOMATO_TARGET="
          f"{os.environ.get('TOMATO_TARGET', 'blossom')} "
          f"TREE_YAW={os.environ.get('TREE_YAW', '0')}\n")

    all_results = [tb.run_single_trial(t, occ, run_dir, mesh_coords, mesh_tree,
                                       arm, perceiver, sampler)
                   for t in range(tb.NUM_TRIALS)]
    if _REACH_R > 0:
        print(f"[tree] reach clamp fired on {tb.next_view.count} viewpoints")
    print(f"\n{tb.METHOD_NAME} tree baseline complete.")
    ros2_node.shutdown()
