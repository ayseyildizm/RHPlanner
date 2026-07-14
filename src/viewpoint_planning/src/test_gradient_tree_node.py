#!/usr/bin/env python3
"""
test_gradient_tree_node.py — tree/tomato wrapper for the GradientNBV baseline.

test_gradient_node.py and the bunny/mug pipeline are NOT modified. Its main
block is inline under the __main__ guard (so runpy monkeypatching cannot
reach the module-local GT function); instead this wrapper imports the module
(inert under the guard) and mirrors that short main flow, with the
tomato-specific pieces swapped in:

  * GT comes from tomato_gt.get_mesh_coordinates (yaw-aware, single source of
    truth shared with the RH wrapper)
  * fair_comparison_config.GRID_SIZE mutated in place when GRID_SIZE env set
  * GradientNBVPlanner called with voxel_size override when VOXEL_SIZE env set

Env: TOMATO_TARGET, TREE_YAW, GRID_SIZE, VOXEL_SIZE — see test_rh_tree_node.py.
"""
import datetime
import functools
import json
import os

import numpy as np

os.environ["TARGET"] = "tomato"  # before any fair_comparison_config import

import viewpoint_planners.fair_comparison_config as fc
from viewpoint_planners import tomato_gt
from viewpoint_planners.gradient_nbv_planner import GradientNBVPlanner

import test_gradient_node as tg  # __main__ guard keeps the import inert

if os.environ.get("GRID_SIZE"):
    fc.GRID_SIZE[:] = [float(v) for v in os.environ["GRID_SIZE"].split(",")]
    print(f"[tree] GRID_SIZE -> {fc.GRID_SIZE.tolist()}")

if os.environ.get("VOXEL_SIZE"):
    _vs = float(os.environ["VOXEL_SIZE"])
    fc.VOXEL_SIZE[:] = [_vs]
    # run_single_trial resolves the name in tg's module globals at call time.
    tg.GradientNBVPlanner = functools.partial(GradientNBVPlanner,
                                              voxel_size=np.array([_vs]))
    print(f"[tree] VOXEL_SIZE -> {_vs}")


if __name__ == "__main__":
    import ros2_node
    ros2_node.init("gradient_test")

    arm = tg.ArmControlClient()
    perceiver = tg.Perceiver()
    sampler = tg.ViewpointSampler()
    sdf = tg.SDFSpawner()

    occ = tg.detect_occlusion_type()
    tg.spawn_occlusion(sdf, occ)

    mesh_coords, mesh_tree = tomato_gt.get_mesh_coordinates()
    run_dir = tg.make_run_dir(occ)

    with open(os.path.join(run_dir, "config.json"), "w") as f:
        json.dump({"experiment": tg.EXPERIMENT, "planner": "GradientNBV",
                   "num_iters": tg.NUM_ITERS, "num_trials": tg.NUM_TRIALS,
                   "base_seed": tg.BASE_SEED,
                   "grid_size": [float(v) for v in fc.GRID_SIZE],
                   "voxel_size": float(fc.VOXEL_SIZE[0]),
                   "occlusion": occ,
                   "tomato_target": os.environ.get("TOMATO_TARGET", "blossom"),
                   "tree_yaw": float(os.environ.get("TREE_YAW", "0")),
                   "roi_half": os.environ.get("ROI_HALF"),
                   "timestamp": datetime.datetime.now().isoformat()}, f, indent=2)

    print(f"\nRun directory: {run_dir}")
    print(f"GradientNBV tree baseline | {tg.NUM_ITERS} viewpoints | "
          f"Occlusion: {occ} | TOMATO_TARGET="
          f"{os.environ.get('TOMATO_TARGET', 'blossom')} "
          f"TREE_YAW={os.environ.get('TREE_YAW', '0')}\n")

    all_results = [tg.run_single_trial(t, occ, run_dir, mesh_coords, mesh_tree,
                                       arm, perceiver, sampler)
                   for t in range(tg.NUM_TRIALS)]
    tg.summarize(all_results, occ, run_dir)
    print("\nGradientNBV tree baseline complete.")
    ros2_node.shutdown()
