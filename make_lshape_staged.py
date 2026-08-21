#!/usr/bin/env python3
"""make_lshape_staged.py — L-shape occluder with EXACTLY the ladder-stage
wall geometry (staged_walls: height 0.184, bottom-anchored, edge-to-edge
widths, gap 0.03, thickness 0.02), instead of the full-height box_faces
walls the stock --lshape mode builds. Panels: FRONT (+Y) + LEFT (-X) wall
(Ayşe 2026-07-19: "L tavsanin onune ve [right'in] tam karsisina").

Writes ur5e_world_panels8.sdf + the stage-8 manifest — same OCC=panels8
hooks as make_panel_world.py --lshape. NEW file; make_panel_world.py is
imported read-only, not edited.

    python3 make_lshape_staged.py
"""
import make_panel_world as mpw

TARGET = "bunny"
H, GAP, T = 0.184, 0.03, 0.02   # identical to the panels1..6 ladder walls

mpw.BUNNY = mpw.TARGETS[TARGET]
geo = {f: (c, s) for f, c, s in mpw.staged_walls(4, H, GAP, T)}
panels = []
for label in ("front", "left"):
    c, s = geo[label]
    panels.append((label, c, s, 0.0, (s[0] / 2, s[1] / 2, s[2] / 2)))
mpw.emit(panels, f"lshape-{TARGET}", "ur5e_world_panels8.sdf",
         mpw.stage_manifest_path(8))
print(f"\n[lshape-staged] wall height {H} m, gap {GAP}, thickness {T} m — "
      "identical to the panels1..6 stage walls.")
print("[lshape-staged] Launch with OCC=panels8 TARGET=bunny (restart the stack).")
