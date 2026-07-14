#!/usr/bin/env python3
"""
reach_map_ik.py — DENSE bunny-position sweep via MoveIt /compute_ik (fast,
no arm motion; safe to run while an experiment is in flight).

Phase-1 counterpart to reach_map_multi.py: instead of ~12 hand-picked
candidates tested with full plan+execute (slow, single-shot-RRT flaky), this
sweeps a dense x/y/z grid and asks ONLY for kinematic IK feasibility of the
camera pose (avoid_collisions=false, so the answer is world-independent and
is not polluted by whatever OCC world happens to be loaded). Finalists must
then be confirmed with real motion planning (reach_map_multi.py protocol) in
the OCC=none world before moving the bunny — IK-reachable does not guarantee
a collision-free path.

Pose convention matches the planners exactly: camera on a ring of RADII
around the candidate at z_off=+0.05, looking at the candidate center with
look_at_rotation (ref=[1,0,0], quat [w,x,y,z]; numpy_to_pose w=view[3]).

Output: reach_ik_results.csv + ranked summary on stdout.
Run:  source /opt/ros/jazzy/setup.bash && source ~/ros2_ws/install/setup.bash
      python3 reach_map_ik.py
"""
import csv
import itertools
import math
import sys
import time

import numpy as np
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose, PoseStamped
from moveit_msgs.srv import GetPositionIK

GROUP = "camera_manipulator"
FRAME = "world"

# Grid over plausible table positions (bunny/mug center). Robot base_link at
# world (0,0,0.525) on the pedestal; UR5e reach 0.85 m.
XS = np.round(np.arange(0.30, 0.651, 0.05), 3)
YS = np.round(np.arange(-0.45, -0.099, 0.05), 3)
ZS = np.round(np.arange(0.65, 1.001, 0.05), 3)

RADII = [0.40, 0.50, 0.60]          # D455-valid standoffs (min/comfort/ideal)
Z_OFF = 0.05
N_AZ = 12
# Priority order (front/back/sides first) + early bail like reach_map_multi.
AZIMUTHS = [0.0, 180.0, 90.0, 270.0, 30.0, 330.0, 60.0, 300.0,
            150.0, 210.0, 120.0, 240.0]
MAX_CONSEC_FAIL = 6

# Cheap geometric prefilter: camera points farther than this from the
# shoulder (world (0,0,0.69)) can never be reached (0.85 arm + wrist/camera
# offsets, generous margin) — skip the IK call entirely.
SHOULDER = np.array([0.0, 0.0, 0.69])
MAX_DIST = 1.05

# Known-reachable sanity pose (experiment start pose, world frame).
HOME = np.array([0.5, -0.05, 1.0, 0.0, 0.0,
                 -0.7071067811865475, 0.7071067811865476])

IK_TIMEOUT = 0.06   # seconds per query (KDL restarts internally)


def look_at_quat_wxyz(eye, target):
    d = np.asarray(target, float) - np.asarray(eye, float)
    d /= np.linalg.norm(d)
    ref = np.array([1.0, 0.0, 0.0])
    axis = np.cross(ref, d)
    n = np.linalg.norm(axis)
    if n < 1e-9:
        return np.array([1.0, 0.0, 0.0, 0.0])
    axis /= n
    ang = math.acos(np.clip(np.dot(ref, d), -1.0, 1.0))
    return np.concatenate(([math.cos(ang / 2)], axis * math.sin(ang / 2)))


def make_pose(xyz, quat_wxyz):
    p = Pose()
    p.position.x, p.position.y, p.position.z = (float(v) for v in xyz)
    p.orientation.w = float(quat_wxyz[0])
    p.orientation.x = float(quat_wxyz[1])
    p.orientation.y = float(quat_wxyz[2])
    p.orientation.z = float(quat_wxyz[3])
    return p


def cam_on_circle(c, radius, az_deg):
    az = math.radians(az_deg)
    return np.array([c[0] + radius * math.sin(az),
                     c[1] + radius * math.cos(az),
                     c[2] + Z_OFF])


class IKSweep(Node):
    def __init__(self):
        super().__init__("reach_map_ik")
        self.cli = self.create_client(GetPositionIK, "/compute_ik")
        if not self.cli.wait_for_service(timeout_sec=10.0):
            sys.exit("[ik] /compute_ik not available — is the stack up?")

    def solvable(self, pose, timeout=IK_TIMEOUT):
        req = GetPositionIK.Request()
        req.ik_request.group_name = GROUP
        req.ik_request.avoid_collisions = False
        ps = PoseStamped()
        ps.header.frame_id = FRAME
        ps.pose = pose
        req.ik_request.pose_stamped = ps
        req.ik_request.timeout.sec = 0
        req.ik_request.timeout.nanosec = int(timeout * 1e9)
        fut = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=timeout + 2.0)
        r = fut.result()
        return r is not None and r.error_code.val == 1  # SUCCESS


def main():
    rclpy.init()
    node = IKSweep()

    home_pose = make_pose(HOME[:3], HOME[3:7])
    if not node.solvable(home_pose, timeout=0.5):
        sys.exit("[ik] SANITY FAIL: HOME pose not IK-solvable — frame/group "
                 "convention wrong, aborting instead of producing garbage.")
    print("[ik] sanity OK: HOME solvable in frame 'world', group "
          f"'{GROUP}'. Grid {len(XS)}x{len(YS)}x{len(ZS)} = "
          f"{len(XS)*len(YS)*len(ZS)} candidates, "
          f"{len(RADII)} radii x {N_AZ} az.")

    f = open("reach_ik_results.csv", "w", newline="")
    w = csv.writer(f)
    w.writerow(["cx", "cy", "cz", "radius", "az_deg", "reachable"])

    t0 = time.time()
    n_query = n_pref = 0
    results = {}  # (cx,cy,cz) -> {radius: set(reachable az)}
    cands = list(itertools.product(XS, YS, ZS))
    for i, (cx, cy, cz) in enumerate(cands):
        c = np.array([cx, cy, cz])
        per_r = {}
        for radius in RADII:
            reached, consec = set(), 0
            for az in AZIMUTHS:
                cam = cam_on_circle(c, radius, az)
                if np.linalg.norm(cam - SHOULDER) > MAX_DIST:
                    ok = False           # geometrically impossible
                    n_pref += 1
                else:
                    ok = node.solvable(make_pose(cam, look_at_quat_wxyz(cam, c)))
                    n_query += 1
                w.writerow([cx, cy, cz, radius, f"{az:.0f}", int(ok)])
                if ok:
                    reached.add(az); consec = 0
                else:
                    consec += 1
                    if consec >= MAX_CONSEC_FAIL:
                        break
            per_r[radius] = reached
        results[(cx, cy, cz)] = per_r
        if (i + 1) % 32 == 0:
            el = time.time() - t0
            print(f"[ik] {i+1}/{len(cands)} candidates  "
                  f"({n_query} IK calls, {n_pref} prefiltered, {el:.0f}s, "
                  f"ETA {el/(i+1)*(len(cands)-i-1):.0f}s)", flush=True)
    f.close()

    def arc_len(azs):
        """Longest contiguous run (deg, wrap-aware) of 30-deg-spaced azimuths."""
        if not azs:
            return 0
        s = sorted(azs)
        if len(s) == N_AZ:
            return 360
        runs, run = [], 1
        for a, b in zip(s, s[1:]):
            run = run + 1 if b - a == 30 else runs.append(run) or 1
        runs.append(run)
        if s[0] == 0 and s[-1] == 330 and len(runs) > 1:  # wraparound
            runs[0] += runs.pop()
        return max(runs) * 30

    rows = []
    for c, per_r in results.items():
        total = sum(len(v) for v in per_r.values())
        arcs = {r: arc_len(per_r[r]) for r in RADII}
        start_ok = 0.0 in per_r[0.40]          # frontal start pose must work
        score = total + sum(arcs.values()) / 90.0
        rows.append((score, total, arcs, start_ok, c, per_r))
    rows.sort(key=lambda t: (-t[3], -t[0]))    # start-pose-valid first, then score

    print("\n" + "=" * 78)
    print("  TOP 15 (start-valid ranked first; score = total reach + arc bonus)")
    print("  current position: (0.50, -0.30, 0.85)")
    print("=" * 78)
    for score, total, arcs, start_ok, c, per_r in rows[:15]:
        azs = ",".join(f"{int(a)}" for a in sorted(per_r[0.40]))
        print(f"  ({c[0]:.2f},{c[1]:.2f},{c[2]:.2f}) total={total:2d}/36 "
              f"arc040={arcs[0.40]:3d} arc050={arcs[0.50]:3d} arc060={arcs[0.60]:3d}"
              f" start={'Y' if start_ok else 'N'}  r040az=[{azs}]")
    cur = results.get((0.50, -0.30, 0.85))
    if cur:
        print(f"\n  current (0.50,-0.30,0.85): "
              f"total={sum(len(v) for v in cur.values())}/36  "
              + "  ".join(f"r{r:.2f}:{len(cur[r])}" for r in RADII))
    print(f"\n  csv -> reach_ik_results.csv   ({n_query} IK calls, "
          f"{n_pref} prefiltered, {time.time()-t0:.0f}s)")
    rclpy.shutdown()


if __name__ == "__main__":
    main()
