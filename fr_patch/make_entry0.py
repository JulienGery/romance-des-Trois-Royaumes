#!/usr/bin/env python3
"""Build the patched entry 0 (font atlas G1T): original 6 textures + FR pages appended.
   tex 6 = ft_sml cells 16x16, tex 7 = ft_nrm cells 16x18 (both 256x256 A4)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from g1t_tools import split_g1t, build_g1t, make_a4_entry
src, outp = sys.argv[1], sys.argv[2]
d = open(src, 'rb').read(); g, ents = split_g1t(d)
assert len(ents) == 6
like = ents[3]                       # 256x256 A4 header to clone
for name in ('sml', 'nrm'):
    alpha = open(os.path.join(os.path.dirname(__file__), 'build', f'page_{name}.alpha'), 'rb').read()
    ents.append(make_a4_entry(like, 256, 256, alpha))
out = build_g1t(g, ents)
open(outp, 'wb').write(out); print('entry0 new size', len(out), 'textures', len(ents))
