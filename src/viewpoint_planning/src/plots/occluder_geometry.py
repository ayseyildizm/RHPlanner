"""
occluder_geometry.py — single source of truth for occluder visualisation.

Bunny at (0.50, -0.30, 1.0).  Camera starts at y=+0.30 (standoff 0.60 m).
Panel sizes (SDF <size> = x y z, half = size/2) — most were unified to
0.22x0.02x0.22; well/covered_well keep a shorter 0.16 height on purpose (a
taller wall there was previously found to make the scenario unsolvable):
  panel_front      : 0.22x0.02x0.22  -> half (0.11, 0.01, 0.11)
  panel_front_low  : 0.22x0.02x0.16  -> half (0.11, 0.01, 0.08)
  panel_side       : 0.02x0.22x0.22  -> half (0.01, 0.11, 0.11)
  panel_side_low   : 0.02x0.22x0.16  -> half (0.01, 0.11, 0.08)
  panel_back       : 0.22x0.02x0.22  -> half (0.11, 0.01, 0.11)
  panel_tunnel     : 0.22x0.02x0.22  -> half (0.11, 0.01, 0.11)

Format: OCCLUDERS[scenario] = list of (center_xyz, half_extent_xyz).
Keep in sync with spawn_*_occlusion() in viewpoint_planning.py.
"""

OCCLUDERS = {
    "none": [],

    # frontal: back face at bunny front face y=-0.229, no penetration.
    "frontal": [
        ([0.50, -0.219, 1.07], (0.110, 0.010, 0.110)),
    ],

    # half_box: two side walls + back wall, front and top open.
    "half_box": [
        ([0.40, -0.30, 1.10], (0.010, 0.110, 0.110)),  # left  (X-)
        ([0.64, -0.30, 1.10], (0.010, 0.110, 0.110)),  # right (X+)
        ([0.50, -0.41, 1.10], (0.110, 0.010, 0.110)),  # back  (Y-)
    ],

    # tunnel: front + back panel pairs, uniform 0.22x0.02x0.22 panels
    # (matches ur5e_world_tunnel.sdf).
    "tunnel": [
        ([0.35, -0.23, 1.07], (0.110, 0.010, 0.110)),  # left front
        ([0.65, -0.23, 1.07], (0.110, 0.010, 0.110)),  # right front
        ([0.35, -0.39, 1.07], (0.110, 0.010, 0.110)),  # left back
        ([0.65, -0.39, 1.07], (0.110, 0.010, 0.110)),  # right back
    ],

    # covered_well: four short walls + top cover.
    "covered_well": [
        ([0.40, -0.30, 1.08],  (0.010, 0.110, 0.080)),  # left  (X-)
        ([0.64, -0.30, 1.08],  (0.010, 0.110, 0.080)),  # right (X+)
        ([0.52, -0.18, 1.08],  (0.110, 0.010, 0.080)),  # front (Y+)
        ([0.52, -0.42, 1.08],  (0.110, 0.010, 0.080)),  # back  (Y-)
        ([0.52, -0.30, 1.185], (0.110, 0.110, 0.010)),  # top
    ],

    # well: four short walls (top open).
    "well": [
        ([0.40, -0.30, 1.08], (0.010, 0.110, 0.080)),  # left  (X-)
        ([0.64, -0.30, 1.08], (0.010, 0.110, 0.080)),  # right (X+)
        ([0.52, -0.18, 1.08], (0.110, 0.010, 0.080)),  # front (Y+)
        ([0.52, -0.42, 1.08], (0.110, 0.010, 0.080)),  # back  (Y-)
    ],
}


def get_occluders(scenario):
    """Return the (center, half_extent) list for a scenario, or [] if unknown."""
    return OCCLUDERS.get(scenario, [])
