#!/usr/bin/env python3
"""
candidate_dump.py — persist rh_planner.candidate_history to disk.

The stock pipeline renders the candidate sequences straight to PNG and then
throws the numbers away, so a figure can never be re-drawn without re-running
the whole simulation. This module adds a dump without touching any of the
finished experiment files: install() wraps the plotting entry point in
plots.plot_candidate_sequences, so every run that already produces
candidates_*.png also writes candidates_data_<occ>.npz next to it.

Use via test_rh_dump_node.py, or by hand before runpy executes a test node:

    from plots import candidate_dump
    candidate_dump.install()

The npz holds, per planning iteration i:
    start_{i}    (3,)      viewpoint the iteration planned from
    seq_{i}      (K,H,3)   the K sampled candidate sequences
    scores_{i}   (K,)      objective value J of each sequence
    best_{i}     ()        index of the selected sequence
plus the ground-truth mesh, and — when the live planner can be reached —
the target position and the shell geometry needed to draw it.
"""
import functools
import os
import weakref

import numpy as np

_planner_ref = None       # weakref to the live RHPlanner, set on first rh_view
_installed = False


def _as_numpy(x):
    """torch tensor / list / array -> plain numpy, on the CPU."""
    if x is None:
        return None
    if hasattr(x, "detach"):
        x = x.detach().cpu().numpy()
    return np.asarray(x)


def _planner_geometry():
    """Shell radii, target and step size of the live planner, if available."""
    out = {}
    planner = _planner_ref() if _planner_ref is not None else None
    if planner is None:
        return out
    for name, attr in [("target", "target_params"), ("r_min", "r_min"),
                       ("r_max", "r_max"), ("step_size", "step_size"),
                       ("horizon", "horizon"), ("num_candidates", "num_candidates")]:
        val = getattr(planner, attr, None)
        if val is not None:
            out[name] = _as_numpy(val)
    return out


def dump(candidate_history, mesh_coordinates, out_dir, occlusion_type="none"):
    """Write one npz for a finished run. Returns the path, or None on failure."""
    if not candidate_history:
        return None
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"candidates_data_{occlusion_type}.npz")

    payload = {"n_iter": np.array(len(candidate_history))}
    for i, it in enumerate(candidate_history):
        payload[f"start_{i}"] = _as_numpy(it["start_pos"])
        payload[f"seq_{i}"] = _as_numpy(it["sequences"])
        payload[f"scores_{i}"] = _as_numpy(it["scores"])
        payload[f"best_{i}"] = np.array(it["best_idx"])

    mesh = _as_numpy(mesh_coordinates)
    if mesh is not None:
        payload["mesh"] = mesh
    payload.update(_planner_geometry())

    np.savez_compressed(path, **payload)
    print(f"  [dump] candidate data -> {path} "
          f"({len(candidate_history)} iterations)")
    return path


def load(path):
    """Read a dump back into the shape the plotting script wants."""
    z = np.load(path, allow_pickle=False)
    n = int(z["n_iter"])
    iters = [{"start_pos": z[f"start_{i}"],
              "sequences": z[f"seq_{i}"],
              "scores": z[f"scores_{i}"],
              "best_idx": int(z[f"best_{i}"])} for i in range(n)]
    extra = {k: z[k] for k in z.files
             if not k.startswith(("start_", "seq_", "scores_", "best_"))
             and k != "n_iter"}
    return iters, extra


def install():
    """Patch the plot entry point so runs dump their candidate data."""
    global _installed, _planner_ref
    if _installed:
        return
    _installed = True

    # Keep a handle on the live planner so the shell geometry can be recorded.
    try:
        from viewpoint_planners.rh_planner import RHPlanner

        _orig_rh_view = RHPlanner.rh_view

        @functools.wraps(_orig_rh_view)
        def _rh_view(self, *args, **kwargs):
            global _planner_ref
            if _planner_ref is None or _planner_ref() is not self:
                _planner_ref = weakref.ref(self)
            return _orig_rh_view(self, *args, **kwargs)

        RHPlanner.rh_view = _rh_view
    except Exception as e:                       # planner import is optional
        print(f"  [dump] planner geometry unavailable: {e}")

    # The test nodes do `from plots.plot_candidate_sequences import ...` at
    # runpy time, so patching the module attribute here is picked up there.
    import plots.plot_candidate_sequences as pcs

    _orig_plot = pcs.plot_candidate_sequences

    @functools.wraps(_orig_plot)
    def _plot_and_dump(candidate_history, mesh_coordinates,
                       occlusion_type="none", iteration_to_plot=None,
                       save_path=None, title=None):
        if save_path:
            try:
                dump(candidate_history, mesh_coordinates,
                     os.path.dirname(os.path.abspath(save_path)),
                     occlusion_type)
            except Exception as e:
                print(f"  [dump] failed: {e}")
        return _orig_plot(candidate_history, mesh_coordinates,
                          occlusion_type=occlusion_type,
                          iteration_to_plot=iteration_to_plot,
                          save_path=save_path, title=title)

    pcs.plot_candidate_sequences = _plot_and_dump
    print("[dump] candidate_history dumping ACTIVE")
