#!/usr/bin/env python3
"""
test_rh_tree_node.py — tree/tomato wrapper around test_rh_node.py.

test_rh_node.py and the bunny/mug pipeline are NOT modified. This wrapper
monkeypatches the tomato-specific pieces into the already-imported modules,
then executes the stock test_rh_node.py via runpy (which resolves the patched
modules from sys.modules):

  * ViewpointPlanning.get_mesh_coordinates -> tomato_gt.get_mesh_coordinates
    (yaw-aware GT, single source of truth shared with the gradient wrapper)
  * fair_comparison_config.GRID_SIZE mutated in place when GRID_SIZE env is
    set (the whole plant is taller than the default bunny grid)
  * RHPlanner called with voxel_size override when VOXEL_SIZE env is set

Env (on top of everything test_rh_node.py understands):
    TOMATO_TARGET  blossom|fruit|all — GT submeshes; must match the world's
                   red-painted parts (make_tree_world.py stage)
    TREE_YAW       degrees; must match the prebuilt world's plant yaw
    GRID_SIZE      "x,y,z" reconstruction volume override (optional)
    VOXEL_SIZE     voxel edge in m (optional)
    RH_REACH_R     spherical reach clamp radius in m about the arm base
                   (default 1.0; 0 disables)
"""
import functools
import os
import runpy

import numpy as np
import torch

os.environ["TARGET"] = "tomato"  # before any fair_comparison_config import

import viewpoint_planners.fair_comparison_config as fc
import viewpoint_planners.viewpoint_planning as vpmod
from viewpoint_planners import tomato_gt
from viewpoint_planners.rh_planner import RHPlanner

vpmod.ViewpointPlanning.get_mesh_coordinates = (
    lambda self: tomato_gt.get_mesh_coordinates())

if os.environ.get("GRID_SIZE"):
    # In-place: every `from fair_comparison_config import GRID_SIZE` alias
    # points at this same array object.
    fc.GRID_SIZE[:] = [float(v) for v in os.environ["GRID_SIZE"].split(",")]
    print(f"[tree] GRID_SIZE -> {fc.GRID_SIZE.tolist()}")

if os.environ.get("VOXEL_SIZE"):
    _vs = float(os.environ["VOXEL_SIZE"])
    fc.VOXEL_SIZE[:] = [_vs]
    vpmod.RHPlanner = functools.partial(RHPlanner,
                                        voxel_size=np.array([_vs]))
    print(f"[tree] VOXEL_SIZE -> {_vs}")

# Spherical reach clamp (RH only). base_link sits at world (0,0,0.525); the
# UR5e cannot execute look-at poses beyond ~1.0 m radial distance from it
# (reach_map_multi_results.csv: 0/59 IK successes in r=[1.0,1.2); every
# "Arm motion failed" pose in the blossom/all runs was at r>=1.10 m, every
# successful fruit_y000 pose <=0.99 m). Candidates beyond RH_REACH_R are
# pulled radially back onto the shell so the entropy term cannot keep
# selecting permanently-unreachable corner poses.
_ARM_BASE = torch.tensor([0.0, 0.0, 0.525], dtype=torch.float32)
_REACH_R = float(os.environ.get("RH_REACH_R", "1.0"))
if _REACH_R > 0:
    _orig_gcs = RHPlanner.generate_candidate_sequence

    def _gcs_reach_clamped(self, start_pos):
        seq = _orig_gcs(self, start_pos)
        base = _ARM_BASE.to(seq.device)
        for k in range(seq.shape[0]):
            vec = seq[k] - base
            d = torch.norm(vec)
            if d > _REACH_R:
                seq[k] = base + vec / d * _REACH_R
                # keep D455 min-depth standoff; if the push moves the pose
                # back outside the shell, reach wins (unreachable is worse
                # than a few near-clip pixels, which the ray sampler drops)
                seq[k] = self._push_to_min_standoff(seq[k])
                vec2 = seq[k] - base
                d2 = torch.norm(vec2)
                if d2 > _REACH_R:
                    seq[k] = base + vec2 / d2 * _REACH_R
                _gcs_reach_clamped.count += 1
        return seq

    _gcs_reach_clamped.count = 0
    RHPlanner.generate_candidate_sequence = _gcs_reach_clamped
    print(f"[tree] RH reach clamp ACTIVE: r<={_REACH_R} m about base "
          f"{_ARM_BASE.tolist()}")

print(f"[tree] RH wrapper: TOMATO_TARGET={os.environ.get('TOMATO_TARGET', 'blossom')} "
      f"TREE_YAW={os.environ.get('TREE_YAW', '0')}")

runpy.run_path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_rh_node.py"),
    run_name="__main__")
