#!/usr/bin/env python3
import argparse
import copy
import glob
import math
import os
import shutil
import tempfile

import numpy as np
import open3d as o3d
from open3d.visualization import rendering
from PIL import Image, ImageChops

REPO = os.path.dirname(os.path.abspath(__file__))
MESH = os.path.join(REPO, "src/simulation_environment/meshes/tomato6.dae")
TEXTURES = os.path.join(
    REPO, "src/greenhouse_gazebo/meshes/tomato/materials/textures")


def stage_mesh(workdir):
    """Copy the mesh and its textures into workdir under the names the .dae asks for."""
    shutil.copy(MESH, workdir)
    for png in glob.glob(os.path.join(TEXTURES, "AG15*.png")):
        tif = os.path.splitext(os.path.basename(png))[0] + ".tif"
        shutil.copy(png, os.path.join(workdir, tif))
    return os.path.join(workdir, os.path.basename(MESH))


def render(model, yaw, renderer, centre, extent):
    renderer.scene.clear_geometry()
    renderer.scene.set_background([1, 1, 1, 1])
    rot = o3d.geometry.get_rotation_matrix_from_axis_angle(
        [0, math.radians(yaw), 0])
    for i, item in enumerate(model.meshes):
        mesh = copy.deepcopy(item.mesh)
        mesh.rotate(rot, center=centre)
        mesh.compute_vertex_normals()
        renderer.scene.add_geometry(
            f"m{i}", mesh, model.materials[item.material_idx])
    renderer.scene.scene.enable_sun_light(True)
    renderer.scene.scene.set_sun_light([-0.4, -0.5, -0.75], [1, 1, 1], 320000)
    renderer.scene.scene.set_indirect_light_intensity(110000)
    dist = max(extent[0], extent[2]) * 2.6
    eye = centre + np.array([0.0, 0.06 * extent[1], dist])
    renderer.scene.camera.look_at(centre, eye, [0, 1, 0])
    return renderer.render_to_image()


def common_crop(paths, pad=30):
    """One crop box for every panel, so the four stay at a common scale."""
    boxes = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        bg = Image.new("RGB", im.size, im.getpixel((2, 2)))
        mask = ImageChops.difference(im, bg).convert("L")
        boxes.append(mask.point(lambda v: 255 if v > 12 else 0).getbbox())
    w, h = Image.open(paths[0]).size
    return (max(0, min(b[0] for b in boxes) - pad),
            max(0, min(b[1] for b in boxes) - pad),
            min(w, max(b[2] for b in boxes) + pad),
            min(h, max(b[3] for b in boxes) + pad))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.expanduser(
        "~/Desktop/LaTeX_thesis_template1__1_(1)/figures"))
    ap.add_argument("--size", type=int, default=1600)
    ap.add_argument("--yaws", default="0,90,180,270")
    args = ap.parse_args()
    yaws = [int(y) for y in args.yaws.split(",")]

    work = tempfile.mkdtemp(prefix="plantrender_")
    try:
        model = o3d.io.read_triangle_model(stage_mesh(work))
        if not model.meshes:
            raise SystemExit("mesh could not be read")
        pts = np.vstack([np.asarray(m.mesh.vertices) for m in model.meshes])
        centre, extent = pts.mean(axis=0), pts.max(axis=0) - pts.min(axis=0)
        print(f"{len(model.meshes)} submeshes, extent {extent.round(3)}")

        raw = []
        renderer = rendering.OffscreenRenderer(args.size, args.size)
        for yaw in yaws:
            path = os.path.join(work, f"raw_y{yaw:03d}.png")
            o3d.io.write_image(path, render(model, yaw, renderer, centre, extent))
            raw.append(path)

        box = common_crop(raw)
        os.makedirs(args.out, exist_ok=True)
        for yaw, path in zip(yaws, raw):
            dst = os.path.join(args.out, f"plant_orient_y{yaw:03d}.png")
            Image.open(path).convert("RGB").crop(box).save(dst)
            print("wrote", dst)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
