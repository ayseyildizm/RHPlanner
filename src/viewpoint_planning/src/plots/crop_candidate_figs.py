"""Crop the RH-NBV candidate-sequence run plots down to the region where the
planning actually happens, so they stay legible at thesis figure size.
Source PNGs are left untouched; cropped copies go to the thesis figures/ dir.
"""
from PIL import Image, ImageDraw, ImageFont
import matplotlib, os

SRC = ("/home/ayse/Desktop/PLANT/RH/ALL/"
       "run_20260712_052809_expC_panels_tree_all_y000_K10_H3_box/trial_00/")
OUT = "/home/ayse/Downloads/thesis_updated/figures/"
FONT = os.path.join(os.path.dirname(matplotlib.__file__),
                    "mpl-data/fonts/ttf/DejaVuSans-Bold.ttf")

# ---- single iteration -----------------------------------------------------
im = Image.open(SRC + "candidates_iter2_panels_tree_all_y000.png").convert("RGB")
W, H = im.size
single = im.crop((int(0.29*W), int(0.115*H), int(0.965*W), int(0.45*H)))
single.save(OUT + "rh_candidates_iter2_zoom.png")
print("single", single.size)

# ---- four iterations ------------------------------------------------------
im = Image.open(SRC + "candidates_grid_panels_tree_all_y000.png").convert("RGB")
W, H = im.size
pw = W / 4
crops = [im.crop((int(i*pw + 0.36*pw), int(0.15*H),
                  int(i*pw + 0.97*pw), int(0.56*H))) for i in range(4)]

cw, ch = crops[0].size
pad, band, gap = 8, 90, 26
out = Image.new("RGB", (4*cw + 3*gap + 2*pad, ch + band + 2*pad), "white")
d = ImageDraw.Draw(out)
font = ImageFont.truetype(FONT, 62)
for i, c in enumerate(crops):
    x = pad + i*(cw + gap)
    out.paste(c, (x, pad + band))
    d.rectangle((x, pad+band, x+cw-1, pad+band+ch-1), outline=(150, 150, 150), width=3)
    label = "Iteration %d" % i
    tw = d.textbbox((0, 0), label, font=font)[2]
    d.text((x + (cw - tw)//2, pad + band//4), label, font=font, fill=(0, 0, 0))
out.save(OUT + "rh_candidates_iters_zoom.png")
print("grid", out.size)
