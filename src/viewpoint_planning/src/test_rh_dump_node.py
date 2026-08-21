#!/usr/bin/env python3
"""
test_rh_dump_node.py — wrapper that makes an RH run persist its candidate data.

Nothing in the existing pipeline is modified. This wrapper installs the
candidate_dump patch and then executes the requested inner test node via runpy,
which resolves the already-patched modules from sys.modules — the same
mechanism test_rh_tree_node.py uses.

The run produces everything it normally would, plus
    candidates_data_<occ>.npz
in the trial directory, which plots/plot_candidates_thesis.py turns into the
thesis figures without needing another simulation.

Env:
    INNER_NODE   which node to run underneath; default test_rh_tree_node.py
                 (use test_rh_node.py for the bunny/mug scenes)
    ...plus every variable the inner node already understands.

Example (tomato plant, the scene used for the RH search figure):
    TOMATO_TARGET=all TREE_YAW=0 OCC=panels_tree_all_y000 \
        python3 test_rh_dump_node.py
"""
import os
import runpy
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from plots import candidate_dump

candidate_dump.install()

_inner = os.environ.get("INNER_NODE", "test_rh_tree_node.py")
print(f"[dump] running inner node: {_inner}")

runpy.run_path(os.path.join(_HERE, _inner), run_name="__main__")
