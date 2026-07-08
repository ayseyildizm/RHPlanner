#!/usr/bin/env python3
"""
render_target_objects.py — render each reconstruction target (bunny, coffee
mug, tree/tomato, box) as a two-panel figure (point cloud + shaded 3D model),
matching the style of the Stanford Bunny figure in the thesis.

Outputs: figures/objects/<name>.png  (one two-panel PNG per object)

Run:  ~/miniconda3/envs/rh_nbv_ros2/bin/python render_target_objects.py
"""
import os
import numpy as np
import trimesh
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

MESH_DIR = "src/simulation_environment/meshes"
OUT_DIR = "figures/objects"
W, H = 900, 900           # per-panel render resolution
N_POINTS = 25000          # points sampled for the point-cloud panel
# 3/4 front-top-right viewing direction (eye = center + dir*radius)
VIEW_DIR = np.array([0.9, -1.0, 0.55])
UP = np.array([0.0, 0.0, 1.0])

# (file, nice title, optional extra rotation in degrees about X,Y,Z to make it
#  stand upright / face the camera). Tweak these if an object looks rotated.
OBJECTS = [
    ("bunny.dae",      "Stanford Bunny", (0, 0, 0)),
    ("coffee_mug.dae", "Coffee Mug",     (0, 0, 0)),
    ("tomato6.dae",    "Tree",           (0, 0, 0)),
    ("box.dae",        "Box",            (0, 0, 0)),
]


def load_o3d_mesh(fname):
    """Load a .dae into an open3d TriangleMesh (box is rebuilt as a primitive
    because trimesh's collada reader returns it empty)."""
    path = os.path.join(MESH_DIR, fname)
    if fname == "box.dae":
        tm = trimesh.creation.box(extents=[0.15, 0.15, 0.15])
    else:
        tm = trimesh.load(path, force="mesh")
    mesh = o3d.geometry.TriangleMesh(
        o3d.utility.Vector3dVector(np.asarray(tm.vertices)),
        o3d.utility.Vector3iVector(np.asarray(tm.faces)),
    )
    mesh.compute_vertex_normals()
    return mesh


def apply_rotation(geom, rot_deg):
    if rot_deg == (0, 0, 0):
        return geom
    R = geom.get_rotation_matrix_from_xyz(np.radians(rot_deg))
    geom.rotate(R, center=geom.get_center())
    return geom


def setup_camera(renderer, geom):
    bbox = geom.get_axis_aligned_bounding_box()
    center = bbox.get_center()
    radius = np.linalg.norm(bbox.get_extent()) * 1.1
    eye = center + VIEW_DIR / np.linalg.norm(VIEW_DIR) * radius * 2.0
    renderer.setup_camera(50.0, center, eye, UP)


def render_model(fname, rot_deg):
    mesh = apply_rotation(load_o3d_mesh(fname), rot_deg)
    r = o3d.visualization.rendering.OffscreenRenderer(W, H)
    r.scene.set_background([1, 1, 1, 1])
    r.scene.scene.set_sun_light([-0.4, 0.6, -0.7], [1, 1, 1], 90000)
    r.scene.scene.enable_sun_light(True)
    mat = o3d.visualization.rendering.MaterialRecord()
    mat.shader = "defaultLit"
    mat.base_color = [0.78, 0.78, 0.80, 1.0]
    r.scene.add_geometry("m", mesh, mat)
    setup_camera(r, mesh)
    img = np.asarray(r.render_to_image())
    del r
    return img


def render_pointcloud(fname, rot_deg):
    mesh = apply_rotation(load_o3d_mesh(fname), rot_deg)
    pcd = mesh.sample_points_uniformly(number_of_points=N_POINTS)
    pcd.paint_uniform_color([0.15, 0.15, 0.15])
    r = o3d.visualization.rendering.OffscreenRenderer(W, H)
    r.scene.set_background([1, 1, 1, 1])
    mat = o3d.visualization.rendering.MaterialRecord()
    mat.shader = "defaultUnlit"
    mat.point_size = 2.0
    r.scene.add_geometry("p", pcd, mat)
    setup_camera(r, pcd)
    img = np.asarray(r.render_to_image())
    del r
    return img


def crop_white(img, pad=20):
    """Trim surrounding white so the object fills the panel."""
    mask = np.any(img < 250, axis=2)
    if not mask.any():
        return img
    ys, xs = np.where(mask)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, img.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, img.shape[1])
    return img[y0:y1, x0:x1]


def _draw_pair(axes, pc, md):
    for ax, im, sub in ((axes[0], pc, "Point Cloud Representation"),
                        (axes[1], md, "3D Model")):
        ax.imshow(im)
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xlabel(sub, fontsize=10)


def make_individual():
    for fname, title, rot in OBJECTS:
        print(f"[render] {fname} ...")
        pc = crop_white(render_pointcloud(fname, rot))
        md = crop_white(render_model(fname, rot))
        fig, axes = plt.subplots(1, 2, figsize=(8, 4.2))
        _draw_pair(axes, pc, md)
        out = os.path.join(OUT_DIR, os.path.splitext(fname)[0] + ".png")
        fig.tight_layout()
        fig.savefig(out, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"[render]   -> {out}")


def make_grid():
    """All four objects in a 2x2 grid; each cell = object name + point cloud
    and 3D model panels."""
    print("[render] 2x2 grid ...")
    panels = []
    for fname, title, rot in OBJECTS:
        pc = crop_white(render_pointcloud(fname, rot))
        md = crop_white(render_model(fname, rot))
        panels.append((title, pc, md))

    fig = plt.figure(figsize=(11, 9))
    subfigs = fig.subfigures(2, 2, wspace=0.02, hspace=0.06)
    for sf, (title, pc, md) in zip(subfigs.ravel(), panels):
        sf.suptitle(title, fontsize=13, fontweight="bold")
        axes = sf.subplots(1, 2)
        _draw_pair(axes, pc, md)
    out = os.path.join(OUT_DIR, "targets_grid.png")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[render]   -> {out}")


def main():
    import sys
    os.makedirs(OUT_DIR, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("all", "individual"):
        make_individual()
    if mode in ("all", "grid"):
        make_grid()
    print("\nDone. PNGs in", OUT_DIR)


if __name__ == "__main__":
    main()
