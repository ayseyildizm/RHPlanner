#!/usr/bin/env python3
"""
make_coffee_mug.py — regenerates src/simulation_environment/meshes/coffee_mug.dae.

The mug is a procedurally generated synthetic target: a capped cylinder plus a
torus handle, written straight to COLLADA. It is not a third-party asset and
was never exported from a modelling package — which is why the file carries no
<contributor>/<authoring_tool>. Keeping the generator in the repo makes that
verifiable: run this and diff against the shipped mesh.

Geometry (all dimensions in metres, Z up, origin at the base centre):

    body    cylinder r=0.035, h=0.100, 40 angular x 15 axial rings   600 verts
    caps    one centre vertex at each end, triangle-fanned              2 verts
    handle  torus centred (0.057, 0, 0.055), R=0.020, r=0.005,
            24 major x 14 minor segments                              336 verts
                                                                 = 938 verts
    triangles: 40*14*2 (side) + 40*2 (caps) + 24*14*2 (handle) = 1872

Vertex normals are averages of the incident faces' UNIT normals (not area
weighted), which is what reproduces the shipped file exactly.

Running --verify regenerates the geometry and diffs it against the shipped
mesh: 938/938 vertices and 938/938 normals match to the file's 1e-6 precision,
and the triangle count is identical. Writing is opt-in (pass an output path) so
the asset every experiment depends on is never overwritten by accident.

Usage:
    python3 make_coffee_mug.py --verify       # default: compare, write nothing
    python3 make_coffee_mug.py out.dae        # regenerate to an explicit path
"""
import os
import sys

import numpy as np

DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "src/simulation_environment/meshes/coffee_mug.dae")

# ---- parameters -----------------------------------------------------------
BODY_R, BODY_H = 0.035, 0.100
N_THETA, N_Z = 40, 15                    # 15 rings => 14 axial steps
HANDLE_C = np.array([0.057, 0.0, 0.055])  # torus centre, in the x-z plane
HANDLE_R, HANDLE_r = 0.020, 0.005
N_MAJOR, N_MINOR = 24, 14
CREATED = "2026-06-14"


def build():
    verts, tris = [], []

    # ---- body: ring by ring, bottom to top --------------------------------
    for zi in range(N_Z):
        z = BODY_H * zi / (N_Z - 1)
        for ti in range(N_THETA):
            a = 2 * np.pi * ti / N_THETA
            verts.append([BODY_R * np.cos(a), BODY_R * np.sin(a), z])
    for zi in range(N_Z - 1):
        for ti in range(N_THETA):
            tn = (ti + 1) % N_THETA
            a = zi * N_THETA + ti
            b = zi * N_THETA + tn
            c = (zi + 1) * N_THETA + ti
            d = (zi + 1) * N_THETA + tn
            tris += [[a, b, c], [b, d, c]]

    # ---- caps: centre vertex + fan ----------------------------------------
    i_bot, i_top = len(verts), len(verts) + 1
    verts.append([0.0, 0.0, 0.0])
    verts.append([0.0, 0.0, BODY_H])
    for ti in range(N_THETA):
        tn = (ti + 1) % N_THETA
        tris.append([i_bot, tn, ti])                                   # -Z
        top = (N_Z - 1) * N_THETA
        tris.append([i_top, top + ti, top + tn])                       # +Z

    # ---- handle: torus in the x-z plane, axis along y ---------------------
    h0 = len(verts)
    for mj in range(N_MAJOR):
        phi = np.pi / 2 - 2 * np.pi * mj / N_MAJOR      # starts at the top
        radial = np.array([np.cos(phi), 0.0, np.sin(phi)])
        centre = HANDLE_C + HANDLE_R * radial
        for mk in range(N_MINOR):
            psi = 2 * np.pi * mk / N_MINOR              # 0 = radially outward
            verts.append(centre
                         + HANDLE_r * np.cos(psi) * radial
                         + HANDLE_r * np.sin(psi) * np.array([0.0, 1.0, 0.0]))
    for mj in range(N_MAJOR):
        mjn = (mj + 1) % N_MAJOR
        for mk in range(N_MINOR):
            mkn = (mk + 1) % N_MINOR
            a = h0 + mj * N_MINOR + mk
            b = h0 + mj * N_MINOR + mkn
            c = h0 + mjn * N_MINOR + mk
            d = h0 + mjn * N_MINOR + mkn
            tris += [[a, b, c], [b, d, c]]

    V = np.round(np.array(verts), 6)
    T = np.array(tris)

    # ---- vertex normals: mean of incident UNIT face normals ---------------
    N = np.zeros_like(V)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    fl = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = np.divide(fn, fl, out=np.zeros_like(fn), where=fl > 0)
    for k in range(3):
        np.add.at(N, T[:, k], fn)
    ln = np.linalg.norm(N, axis=1, keepdims=True)
    N = np.round(np.divide(N, ln, out=np.zeros_like(N), where=ln > 0), 6)
    return V, N, T


def to_dae(V, N, T):
    f = lambda A: "\n".join("            " + " ".join(f"{x:.6f}" for x in row)
                            for row in A)
    p = " ".join(f"{i} {i}" for tri in T for i in tri)
    return f"""<?xml version='1.0' encoding='utf-8'?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset>
    <created>{CREATED}</created>
    <modified>{CREATED}</modified>
    <up_axis>Z_UP</up_axis>
  </asset>
  <library_geometries>
    <geometry id="coffee_mug-mesh" name="coffee_mug">
      <mesh>
        <source id="coffee_mug-mesh-positions">
          <float_array id="coffee_mug-mesh-positions-array" count="{V.size}">
{f(V)}
          </float_array>
          <technique_common>
            <accessor source="#coffee_mug-mesh-positions-array" count="{len(V)}" stride="3">
              <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>
        <source id="coffee_mug-mesh-normals">
          <float_array id="coffee_mug-mesh-normals-array" count="{N.size}">
{f(N)}
          </float_array>
          <technique_common>
            <accessor source="#coffee_mug-mesh-normals-array" count="{len(N)}" stride="3">
              <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>
        <vertices id="coffee_mug-mesh-vertices">
          <input semantic="POSITION" source="#coffee_mug-mesh-positions"/>
        </vertices>
        <triangles count="{len(T)}">
          <input semantic="VERTEX" source="#coffee_mug-mesh-vertices" offset="0"/>
          <input semantic="NORMAL" source="#coffee_mug-mesh-normals" offset="1"/>
          <p>{p}</p>
        </triangles>
      </mesh>
    </geometry>
  </library_geometries>
  <library_visual_scenes>
    <visual_scene id="Scene" name="Scene">
      <node id="coffee_mug" name="coffee_mug" type="NODE">
        <instance_geometry url="#coffee_mug-mesh"/>
      </node>
    </visual_scene>
  </library_visual_scenes>
  <scene><instance_visual_scene url="#Scene"/></scene>
</COLLADA>
"""


def verify(V, N, T, path):
    import xml.etree.ElementTree as ET
    ns = {"ns": "http://www.collada.org/2005/11/COLLADASchema"}
    root = ET.parse(path).getroot()
    fas = root.findall(".//ns:float_array", ns)
    Vr = np.array(list(map(float, fas[0].text.split()))).reshape(-1, 3)
    Nr = np.array(list(map(float, fas[1].text.split()))).reshape(-1, 3)
    ntri = int(root.find(".//ns:triangles", ns).get("count"))
    print(f"shipped : {len(Vr)} verts, {ntri} triangles")
    print(f"generated: {len(V)} verts, {len(T)} triangles")
    ok = len(Vr) == len(V) and ntri == len(T)
    if ok:
        dv = np.abs(Vr - V).max()
        dn = np.abs(Nr - N).max()
        print(f"max |dvertex| = {dv:.2e} m   max |dnormal| = {dn:.2e}")
        print(f"vertices differing: {int((np.abs(Vr - V).max(1) > 1e-9).sum())}/{len(V)}   "
              f"normals differing: {int((np.abs(Nr - N).max(1) > 1e-9).sum())}/{len(N)}")
        ok = dv < 1e-9 and dn < 1e-9
    print("EXACT MATCH" if ok else "MISMATCH")
    return ok


if __name__ == "__main__":
    V, N, T = build()
    out = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
    if out is None:
        sys.exit(0 if verify(V, N, T, DEFAULT_OUT) else 1)
    with open(out, "w") as fh:
        fh.write(to_dae(V, N, T))
    print(f"wrote {out}: {len(V)} vertices, {len(T)} triangles")
