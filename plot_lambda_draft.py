#!/usr/bin/env python3
"""plot_lambda_draft.py — write the lambda figure into the current draft.

plot_lambda.py already draws the figure the way results.tex describes it:
the three runs of the 2026-07-28 batch, coverage on the left and the
cumulative executed path on the right. What it does not do is land in the
right place any more. It inherits REPO and THESIS from plots.py, and both
still point at the previous locations: ~/Desktop/RecedingHorizon for the run
folders and the old Desktop template for the figures. The runs now live in
this copy of the repo, and results.tex reads this figure from Imgs/, not
from figures/.

So this file changes nothing in plot_lambda.py or plots.py. It repoints the
three paths and calls the existing main().

    python3 plot_lambda_draft.py
"""
import os

REPO = os.path.dirname(os.path.abspath(__file__))
DRAFT = os.path.expanduser("~/Downloads/LaTeX_thesis_template_draft/Imgs")

import plots
import plot_lambda

# load() reads plots.REPO at call time, so setting it here is enough for both
# modules. OUT and THESIS were bound into plot_lambda at import, so they have
# to be set on that module.
plots.REPO = REPO
plot_lambda.OUT = os.path.join(REPO, "figures")
plot_lambda.THESIS = DRAFT

if __name__ == "__main__":
    plot_lambda.main()
    print("copied to", DRAFT)
