#!/usr/bin/env python3
"""
tomato_gt.py — single source of truth for the tomato/tree experiments.

Both evaluation drivers (test_rh_node.py via viewpoint_planning.py, and
test_gradient_node.py) must score against the SAME ground-truth point set;
keeping the extraction here guarantees that by construction. Bunny/mug GT
lives untouched in the drivers themselves.

Env vars:
    TOMATO_TARGET  blossom (default) | fruit | all — which submeshes are GT.
                   Must match the red-colored (segmenter-visible) parts the
                   launch file painted.
    TREE_YAW       plant yaw in degrees about its model origin (default 0).
                   Must match the yaw the launch file spawned the plant with,
                   or every reconstruction scores as a false positive.
"""
import os
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial import KDTree

MESH_PATH = ("/home/ayse/Desktop/RecedingHorizon/src/simulation_environment/"
             "meshes/tomato6.dae")
_NS = {"ns": "http://www.collada.org/2005/11/COLLADASchema"}

# Gazebo spawn transform — must match the <model name="tomato"> block that
# move_group_gz_ur5e.launch.py injects into the world.
SCALE = 0.4
TRANSLATION = np.array([0.5, -0.50, 0.9])

TARGET_NODES = {
    "fruit":   {"Fruit1", "Fruit2", "Fruit3", "Fruit4"},
    "blossom": {"Blossom1", "Blossom2", "Blossom3"},
    "all":     {"Branch1", "Leaf1", "Leaf2",
                "Blossom1", "Blossom2", "Blossom3",
                "Fruit1", "Fruit2", "Fruit3", "Fruit4"},
}


def get_tree_yaw_rad():
    return float(os.environ.get("TREE_YAW", "0")) * np.pi / 180.0


def get_mesh_coordinates():
    """World-frame GT points for the active TOMATO_TARGET at the active
    TREE_YAW. Returns (coords, KDTree) — identical for every caller."""
    tt = os.environ.get("TOMATO_TARGET", "blossom").lower()
    target_nodes = TARGET_NODES.get(tt, TARGET_NODES["blossom"])

    root = ET.parse(MESH_PATH).getroot()
    arr_ids = set()
    for node in root.findall(".//ns:visual_scene//ns:node", _NS):
        if node.get("name", "") in target_nodes:
            for inst in node.findall(".//ns:instance_geometry", _NS):
                url = inst.get("url", "").lstrip("#")
                arr_ids.add(url.replace("-mesh", "") + "-mesh-positions-array")
    all_verts = []
    for fa in root.findall(".//ns:float_array", _NS):
        if fa.get("id", "") in arr_ids:
            all_verts.append(
                np.array(list(map(float, fa.text.split()))).reshape(-1, 3))
    if not all_verts:
        raise RuntimeError(f"Tomato {tt} arrays not found in tomato6.dae")
    vertices = np.vstack(all_verts)

    # COLLADA Y-up → Gazebo Z-up: world=(dae_x, -dae_z, dae_y)
    converted = np.column_stack(
        [vertices[:, 0], -vertices[:, 2], vertices[:, 1]])

    # Gazebo yaws the model about its pose origin, which equals TRANSLATION,
    # so rotate in the model frame before translating.
    yaw = get_tree_yaw_rad()
    if yaw:
        c, s = np.cos(yaw), np.sin(yaw)
        converted = converted @ np.array(
            [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])

    coords = converted * SCALE + TRANSLATION
    return coords, KDTree(coords)


if __name__ == "__main__":
    for tt in ("all", "blossom", "fruit"):
        os.environ["TOMATO_TARGET"] = tt
        c, _ = get_mesh_coordinates()
        print(f"{tt:8s} n={len(c):7d}  min={c.min(0).round(3)}  "
              f"max={c.max(0).round(3)}  centroid={c.mean(0).round(3)}")
