#!/usr/bin/env python3
"""Ground-truth meshes as voxels, at the grid resolution the planners use.

Why this exists
---------------
The reconstruction figures scatter 3 mm occupancy voxels on the left and raw
COLLADA vertices on the right, which are not the same unit -- the fruit mesh
carries ~1 mm vertex spacing, the mug mesh ~5.5 mm. Quantising the *vertices*
is not the fix either: a mesh states its surface with triangles, and a large
triangle spanned by three far-apart vertices still covers every voxel in
between. Vertex quantisation undercounts the whole plant by 4x and the mug by
5x, which then makes "reconstruction reached X% of the ground truth" wrong.

So the ceiling here is computed by sampling the triangle faces densely and
voxelising the samples. Transforms are copied from
viewpoint_planning.get_mesh_coordinates so the point set matches what the runs
were scored against.
"""
import xml.etree.ElementTree as ET

import numpy as np

MESHES = "/home/ayse/Desktop/RecedingHorizon/src/simulation_environment/meshes"
NS = {"ns": "http://www.collada.org/2005/11/COLLADASchema"}

TOMATO_NODES = {
    "fruit":   {"Fruit1", "Fruit2", "Fruit3", "Fruit4"},
    "blossom": {"Blossom1", "Blossom2", "Blossom3"},
    "all":     {"Branch1", "Leaf1", "Leaf2",
                "Blossom1", "Blossom2", "Blossom3",
                "Fruit1", "Fruit2", "Fruit3", "Fruit4"},
}


def _triangles(geometry):
    """Vertex-index triangles of one <geometry>, fanning any n-gons."""
    out = []
    for prim in (geometry.findall(".//ns:triangles", NS)
                 + geometry.findall(".//ns:polylist", NS)):
        inputs = prim.findall("ns:input", NS)
        stride = max(int(i.get("offset", 0)) for i in inputs) + 1
        voff = [int(i.get("offset", 0)) for i in inputs
                if i.get("semantic") == "VERTEX"]
        if not voff:
            continue
        idx = np.array(list(map(int, prim.find("ns:p", NS).text.split())))
        idx = idx.reshape(-1, stride)[:, voff[0]]
        if prim.tag.endswith("polylist"):
            counts = np.array(list(map(int, prim.find("ns:vcount", NS).text.split())))
            if not np.all(counts == 3):
                k = 0
                for c in counts:
                    face = idx[k:k + c]
                    k += c
                    for j in range(1, c - 1):
                        out.append(np.array([[face[0], face[j], face[j + 1]]]))
                continue
        out.append(idx.reshape(-1, 3))
    return np.vstack(out) if out else np.zeros((0, 3), int)


def load_gt(target="fruit", yaw_deg=0.0):
    """Return (vertices, triangles) in world frame for one experiment target."""
    target = target.lower()

    if target == "mug":
        root = ET.parse(f"{MESHES}/coffee_mug.dae").getroot()
        arr = root.find(".//ns:float_array[@id='coffee_mug-mesh-positions-array']", NS)
        V = np.array(list(map(float, arr.text.split()))).reshape(-1, 3)
        T = _triangles(root)
        return V + np.array([0.5, -0.30, 0.85]), T

    if target == "bunny":
        root = ET.parse(f"{MESHES}/bunny.dae").getroot()
        arr = root.find(".//ns:float_array[@id='bun_zipper-mesh-positions-array']", NS)
        V = np.array(list(map(float, arr.text.split()))).reshape(-1, 3)
        T = _triangles(root)
        V = np.column_stack([-V[:, 0], V[:, 2], V[:, 1] - 0.05])
        return V * 1.2 + np.array([0.5, -0.30, 0.85]), T

    if target not in TOMATO_NODES:
        raise ValueError(f"bilinmeyen hedef: {target}")

    root = ET.parse(f"{MESHES}/tomato6.dae").getroot()
    wanted = set()
    for node in root.findall(".//ns:visual_scene//ns:node", NS):
        if node.get("name", "") in TOMATO_NODES[target]:
            for inst in node.findall(".//ns:instance_geometry", NS):
                wanted.add(inst.get("url", "").lstrip("#").replace("-mesh", ""))
    Vs, Ts, off = [], [], 0
    for geom in root.findall(".//ns:geometry", NS):
        gid = (geom.get("id") or "").replace("-mesh", "")
        if gid not in wanted:
            continue
        arr = geom.find(f".//ns:float_array[@id='{gid}-mesh-positions-array']", NS)
        V = np.array(list(map(float, arr.text.split()))).reshape(-1, 3)
        Vs.append(V)
        Ts.append(_triangles(geom) + off)
        off += len(V)
    if not Vs:
        raise RuntimeError(f"tomato6.dae içinde {target} geometrisi yok")
    V, T = np.vstack(Vs), np.vstack(Ts)

    # COLLADA Y-up -> Gazebo Z-up, then the plant's yaw about its own origin.
    V = np.column_stack([V[:, 0], -V[:, 2], V[:, 1]])
    if yaw_deg:
        c, s = np.cos(np.radians(yaw_deg)), np.sin(np.radians(yaw_deg))
        V = V @ np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])
    return V * 0.4 + np.array([0.5, -0.50, 0.9]), T


def surface_points(V, T, voxel_size=0.003, per_voxel=12.0, seed=0):
    """Uniform samples over the triangles, ~per_voxel samples per voxel edge.

    The voxel count converges as the density rises (mug: 4,219 at 3/voxel,
    4,399 at 8, 4,421 at 12, 4,422 at 16), so 12 is where the number stops
    moving without wasting samples. It still shifts by a few percent with the
    grid origin, which the grid picks from the target position -- treat the
    result as "about N", not an exact count.
    """
    rng = np.random.default_rng(seed)
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    n = np.maximum((area / (voxel_size / per_voxel) ** 2).astype(int), 4)
    chunks = []
    for i in range(len(T)):
        k = int(n[i])
        u, v = rng.random(k), rng.random(k)
        flip = u + v > 1
        u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
        chunks.append(a[i] + np.outer(u, b[i] - a[i]) + np.outer(v, c[i] - a[i]))
    return np.vstack(chunks)


def voxel_centres(points, voxel_size=0.003):
    cells = np.unique(np.floor(points / voxel_size).astype(np.int64), axis=0)
    return (cells + 0.5) * voxel_size


def gt_voxels(target="fruit", yaw_deg=0.0, voxel_size=0.003, mode="surface",
              per_voxel=12.0):
    """Voxel centres of the ground truth. mode: 'surface' (correct) or 'vertex'."""
    V, T = load_gt(target, yaw_deg)
    pts = (V if mode == "vertex" or len(T) == 0
           else surface_points(V, T, voxel_size, per_voxel))
    return voxel_centres(pts, voxel_size), len(V), len(T)


if __name__ == "__main__":
    for tgt in ("fruit", "blossom", "all", "mug", "bunny"):
        surf, nv, nt = gt_voxels(tgt)
        vert, _, _ = gt_voxels(tgt, mode="vertex")
        print(f"{tgt:8} {nv:>7,} vertex {nt:>7,} üçgen | "
              f"vertex-voksel {len(vert):>7,} | yüzey-voksel {len(surf):>7,}")
