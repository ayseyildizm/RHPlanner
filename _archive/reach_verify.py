#!/usr/bin/env python3
"""
reach_verify.py — Phase-2 confirmation of the reach_map_ik.py finalists with
REAL motion planning (plan + execute), plus a collision-checked IK pre-pass.

Why: reach_map_ik.py measures pure kinematics (avoid_collisions=false). A
pose can be IK-solvable yet unplannable (pedestal/self-collision, cluttered
C-space near the base — exactly how the earlier x=0.3 move failed live).
Per pose this logs BOTH signals:
    ik_col    collision-checked IK (against the CURRENT planning scene —
              run this with OCC=none so panel obstacles don't pollute it)
    motion    move_arm_to_pose succeeded (1 retry per pose; re-home + bail
              the radius after MAX_CONSEC_FAIL consecutive motion fails)
Motion is only attempted where ik_col passes (hopeless poses waste ~10 s each).

PREREQ: stack up with OCC=none, NO experiment in flight (this MOVES the arm).
Run:    REACH=reach_verify.py ./run_reach_test.sh
Output: reach_verify_results.csv + ranked summary.
"""
import csv
import math
import time

import numpy as np

import ros2_node  # singleton node + spin thread; must be first
ros2_node.init("reach_verify")

from abb_control.arm_control_client import ArmControlClient
from moveit_msgs.srv import GetPositionIK
from geometry_msgs.msg import PoseStamped
from utils.py_utils import numpy_to_pose, look_at_rotation

# Finalists from reach_ik_results.csv (2026-07-05 dense sweep, top arcs with
# start pose valid) + the current position as baseline. Memory: a bare x=0.30
# move failed live in June — that is exactly what this run must settle.
CANDIDATES = {
    "current_x050_y-030_z085": np.array([0.50, -0.30, 0.85]),
    "ik1_x030_y-015_z065":     np.array([0.30, -0.15, 0.65]),
    "ik2_x030_y-010_z075":     np.array([0.30, -0.10, 0.75]),
    "ik3_x035_y-010_z075":     np.array([0.35, -0.10, 0.75]),
    "ik4_x030_y-010_z095":     np.array([0.30, -0.10, 0.95]),
    "ik5_x040_y-010_z075":     np.array([0.40, -0.10, 0.75]),
}

RADII = [0.40, 0.50, 0.60]
Z_OFF = 0.05
N_AZ = 12
AZIMUTHS = [0.0, 180.0, 90.0, 270.0, 30.0, 330.0, 60.0, 300.0,
            150.0, 210.0, 120.0, 240.0]
MAX_CONSEC_FAIL = 4
GROUP = "camera_manipulator"

HOME = np.array([0.5, -0.05, 1.0, 0.0, 0.0,
                 -0.7071067811865475, 0.7071067811865476])


def cam_on_circle(c, radius, az_deg):
    az = math.radians(az_deg)
    return np.array([c[0] + radius * math.sin(az),
                     c[1] + radius * math.cos(az),
                     c[2] + Z_OFF])


def pose_vec(cam, target):
    return np.concatenate((cam, look_at_rotation(cam, target)))


class IKCheck:
    def __init__(self):
        self.node = ros2_node.get_node()
        self.cli = self.node.create_client(GetPositionIK, "/compute_ik")
        if not self.cli.wait_for_service(timeout_sec=10.0):
            raise RuntimeError("/compute_ik not available")

    def ok(self, view, timeout=0.15):
        req = GetPositionIK.Request()
        req.ik_request.group_name = GROUP
        req.ik_request.avoid_collisions = True
        ps = PoseStamped()
        ps.header.frame_id = "world"
        ps.pose = numpy_to_pose(view)
        req.ik_request.pose_stamped = ps
        req.ik_request.timeout.nanosec = int(timeout * 1e9)
        fut = self.cli.call_async(req)
        t0 = time.time()
        while not fut.done() and time.time() - t0 < timeout + 2.0:
            time.sleep(0.01)  # background executor spins the node
        r = fut.result() if fut.done() else None
        return r is not None and r.error_code.val == 1


def main():
    arm = ArmControlClient()
    ik = IKCheck()

    f = open("reach_verify_results.csv", "w", newline="")
    w = csv.writer(f)
    w.writerow(["candidate", "cx", "cy", "cz", "radius", "az_deg",
                "ik_col", "motion", "attempts"])

    per_combo = {}
    for name, C in CANDIDATES.items():
        for radius in RADII:
            print(f"\n=== {name}  r={radius:.2f} ===", flush=True)
            arm.move_arm_to_pose(numpy_to_pose(HOME)); time.sleep(0.5)
            reached, consec, bailed = [], 0, False
            for az in AZIMUTHS:
                cam = cam_on_circle(C, radius, az)
                view = pose_vec(cam, C)
                col = ik.ok(view)
                ok, attempts = False, 0
                if col and not bailed:
                    for attempts in (1, 2):
                        ok = bool(arm.move_arm_to_pose(numpy_to_pose(view)))
                        if ok:
                            break
                w.writerow([name, f"{C[0]:.2f}", f"{C[1]:.2f}", f"{C[2]:.2f}",
                            f"{radius:.2f}", f"{az:.0f}",
                            int(col), int(ok), attempts]); f.flush()
                print(f"    az={az:5.0f} ikcol={'Y' if col else 'n'} -> "
                      f"{'REACH' if ok else ('skip' if bailed or not col else 'FAIL')}",
                      flush=True)
                if ok:
                    reached.append(az); consec = 0
                elif col and not bailed:
                    consec += 1
                    if consec >= MAX_CONSEC_FAIL:
                        print(f"    {MAX_CONSEC_FAIL} consecutive motion fails "
                              "-> re-home, IK-log rest, no more motion",
                              flush=True)
                        arm.move_arm_to_pose(numpy_to_pose(HOME))
                        time.sleep(0.5)
                        bailed = True
                time.sleep(0.2)
            per_combo[(name, radius)] = reached
    f.close()

    print("\n" + "=" * 74)
    print("  MOTION-VERIFIED reachable azimuths per (candidate, standoff)")
    print("=" * 74)
    totals = {}
    for (name, radius), azs in per_combo.items():
        totals[name] = totals.get(name, 0) + len(azs)
        arc = ",".join(f"{a:.0f}" for a in sorted(azs)) if azs else "NONE"
        print(f"  {name:<26} r={radius:.2f}: {len(azs):2d}/{N_AZ}  [{arc}]")
    print("-" * 74)
    for name, t in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<26} TOTAL {t}/36")
    print("  csv -> reach_verify_results.csv")


if __name__ == "__main__":
    main()
