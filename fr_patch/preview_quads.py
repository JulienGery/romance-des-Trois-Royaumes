#!/usr/bin/env python3
"""Rasterize "[selftest] QUAD x0 y0 x1 y1 uv u0 v0 u1 v1" lines on the baked page (nearest, alpha-over-black), x4 upscale."""
import re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from bake_french_atlas import write_gray_png
page = open(os.path.join(os.path.dirname(__file__), 'build', 'page_sml.alpha'), 'rb').read()
W, H, S = 200, 130, 4
cv = bytearray(W * H)
for l in open(sys.argv[1]):
    m = re.search(r'QUAD ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+) uv ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+)', l)
    if not m: continue
    x0, y0, x1, y1, u0, v0, u1, v1 = map(float, m.groups())
    for y in range(int(y0), int(y1)):
        for x in range(int(x0), int(x1)):
            if 0 <= x < W and 0 <= y < H:
                u = u0 + (x - x0 + .5) / (x1 - x0) * (u1 - u0); v = v0 + (y - y0 + .5) / (y1 - y0) * (v1 - v0)
                a = page[int(v * 256) * 256 + int(u * 256)]
                i = y * W + x; cv[i] = max(cv[i], a)
big = bytearray()
for y in range(H):
    row = bytes(sum(([cv[y * W + x]] * S for x in range(W)), []))
    big += row * S
write_gray_png(sys.argv[2], W * S, H * S, bytes(big))
