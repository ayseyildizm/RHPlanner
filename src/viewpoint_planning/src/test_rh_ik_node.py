#!/usr/bin/env python3
"""
test_rh_ik_node.py — reachability-aware candidate sampling for RH-NBV.

Motivation (measured 2026-07-28, mug/panels3): RH-NBV samples camera poses
from a box that is partly outside what the UR5e can actually execute. The
failures are not noise -- MoveIt reports "Unable to sample any valid states
for goal tree" / "Insufficient states in sampleable goal region", i.e. the
commanded pose has no collision-free IK solution -- and their rate grows with
the planning horizon, because a longer horizon walks the camera further from
the current pose. At H=3 only 13 of 20 commanded motions executed, while H=1
executed 20 of 20.

This wrapper tests each sampled candidate against MoveIt's /compute_ik
(group camera_manipulator, tip camera_color_frame, avoid_collisions=true --
the same solver and scene the executor plans with) BEFORE the utility is
evaluated, and resamples sequences that contain an infeasible pose. The
planner's objective, sampling distribution and parameters are untouched; only
poses the robot cannot reach are removed from consideration.

NOTHING existing is modified: this file monkeypatches
RHPlanner.generate_candidate_sequence and then runpy-executes the stock
test_rh_node.py, exactly like test_rh_tree_node.py does for the tomato scene.

Env (on top of everything test_rh_node.py understands):
    RH_IK_FILTER    1 (default) enables the filter; 0 runs stock behaviour
    RH_IK_ATTEMPTS  max resamples before a sequence is accepted anyway (40)
    RH_IK_TIMEOUT   per-call service timeout in seconds (2.0)

Caveat for the write-up: resampling consumes extra draws from the shared RNG
stream, so a filtered run is not view-for-view comparable to an unfiltered
one with the same seed; compare aggregate behaviour, not individual views.
"""
import atexit
import os
import runpy

import numpy as np
import torch

from utils.torch_utils import look_at_rotation
from viewpoint_planners.rh_planner import RHPlanner

_ENABLED = os.environ.get("RH_IK_FILTER", "1") != "0"
_MAX_ATTEMPTS = int(os.environ.get("RH_IK_ATTEMPTS", "40"))
_CALL_TIMEOUT = float(os.environ.get("RH_IK_TIMEOUT", "2.0"))

_GROUP = "camera_manipulator"     # ur5e_l515_description.srdf
_TIP = "camera_color_frame"       # chain tip of that group
_FRAME = "world"                  # move_group planning frame

_stats = {
    "checks": 0,        # IK service calls actually issued
    "cache_hits": 0,
    "infeasible": 0,    # poses rejected by IK
    "resamples": 0,     # sequences thrown away and drawn again
    "fallbacks": 0,     # sequences accepted despite an infeasible pose
    "errors": 0,        # service unavailable / timed out (counted as feasible)
}


class _IKChecker:
    """Lazy /compute_ik client. Created on first use, after rclpy is up."""

    def __init__(self):
        self._node = None
        self._client = None
        self._cache = {}
        self._dead = False

    def _ensure(self):
        if self._node is not None or self._dead:
            return
        try:
            import rclpy
            from moveit_msgs.srv import GetPositionIK
            if not rclpy.ok():
                return                      # test_rh_node.py has not init'd yet
            self._node = rclpy.create_node("rh_ik_filter")
            self._client = self._node.create_client(GetPositionIK, "/compute_ik")
            if not self._client.wait_for_service(timeout_sec=15.0):
                print("[ik] /compute_ik not available — filter DISABLED", flush=True)
                self._dead = True
                return
            print("[ik] /compute_ik ready", flush=True)
        except Exception as exc:                       # noqa: BLE001
            print(f"[ik] client init failed ({exc}) — filter DISABLED", flush=True)
            self._dead = True

    def feasible(self, pos_xyz, quat_wxyz):
        """True if the arm has a collision-free IK solution for this pose."""
        self._ensure()
        if self._dead or self._client is None:
            return True

        key = tuple(np.round(np.asarray(pos_xyz, dtype=float), 3))
        if key in self._cache:
            _stats["cache_hits"] += 1
            return self._cache[key]

        try:
            import rclpy
            from geometry_msgs.msg import Pose, Point, Quaternion, PoseStamped
            from moveit_msgs.srv import GetPositionIK

            req = GetPositionIK.Request()
            req.ik_request.group_name = _GROUP
            req.ik_request.ik_link_name = _TIP
            req.ik_request.avoid_collisions = True
            req.ik_request.timeout.sec = 0
            req.ik_request.timeout.nanosec = 100_000_000      # 100 ms (KDL is
            # a random-restart solver; a too-short budget causes false rejects)
            ps = PoseStamped()
            ps.header.frame_id = _FRAME
            ps.pose = Pose(
                position=Point(x=float(pos_xyz[0]), y=float(pos_xyz[1]),
                               z=float(pos_xyz[2])),
                orientation=Quaternion(x=float(quat_wxyz[1]), y=float(quat_wxyz[2]),
                                       z=float(quat_wxyz[3]), w=float(quat_wxyz[0])),
            )
            req.ik_request.pose_stamped = ps

            fut = self._client.call_async(req)
            rclpy.spin_until_future_complete(self._node, fut,
                                             timeout_sec=_CALL_TIMEOUT)
            _stats["checks"] += 1
            if not fut.done() or fut.result() is None:
                _stats["errors"] += 1
                return True                      # never block on infrastructure
            ok = fut.result().error_code.val == 1  # SUCCESS
        except Exception:                                   # noqa: BLE001
            _stats["errors"] += 1
            return True

        self._cache[key] = ok
        if not ok:
            _stats["infeasible"] += 1
        return ok


_checker = _IKChecker()


def _install():
    orig = RHPlanner.generate_candidate_sequence

    def _gcs_ik_filtered(self, start_pos):
        seq = orig(self, start_pos)
        for _ in range(_MAX_ATTEMPTS):
            if all(_checker.feasible(
                       seq[k].detach().cpu().numpy(),
                       look_at_rotation(seq[k], self.target_params)
                       .detach().cpu().numpy())
                   for k in range(seq.shape[0])):
                return seq
            _stats["resamples"] += 1
            seq = orig(self, start_pos)
        # Budget exhausted: hand back the last draw so the planner always has
        # a candidate. Counted, and reported at the end of the run.
        _stats["fallbacks"] += 1
        return seq

    RHPlanner.generate_candidate_sequence = _gcs_ik_filtered


def _report():
    print("\n[ik] reachability filter summary: "
          f"{_stats['checks']} IK calls ({_stats['cache_hits']} cache hits), "
          f"{_stats['infeasible']} poses infeasible, "
          f"{_stats['resamples']} sequences resampled, "
          f"{_stats['fallbacks']} accepted without a feasible draw, "
          f"{_stats['errors']} service errors", flush=True)


if _ENABLED:
    _install()
    atexit.register(_report)
    print(f"[ik] RH reachability filter ACTIVE (group={_GROUP}, tip={_TIP}, "
          f"max {_MAX_ATTEMPTS} resamples/sequence)", flush=True)
else:
    print("[ik] RH reachability filter disabled (RH_IK_FILTER=0)", flush=True)

runpy.run_path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_rh_node.py"),
    run_name="__main__")
