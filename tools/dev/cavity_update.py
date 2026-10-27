#!/usr/bin/env python3
"""Remove from data/cavities.json every function executed in a trap-ROM session (work/rom/game_trap.cxi) and its two neighbours.
usage: cavity_update.py /tmp/zakuro.log   (then rebuild: tools/build_arm_rom.sh and tools/dev/make_trap_rom.sh)"""
import bisect, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); P = os.path.join(ROOT, 'data', 'cavities.json')
src = open(os.path.join(ROOT, 'externals', 'code.c'), errors='replace').read()
starts = sorted(set(int(m.group(1), 16) for m in re.finditer(r'// Fonction : \S+ @ ([0-9a-f]{8})', src))); ends = starts[1:] + [0x60c000]
log = open(sys.argv[1], errors='replace').read()
hits = sorted(set(int(m, 16) for m in re.findall(r'undefined instruction 0xE7F000F0 at 0x([0-9A-F]{8})', log)))
bad = []
for a in hits:
    i = bisect.bisect_right(starts, a) - 1
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(starts) and (starts[j], ends[j]) not in bad: bad.append((starts[j], ends[j]))
cav = json.load(open(P)); out = []
for a, b in cav:
    pieces = [(a, b)]
    for s, e in bad:
        nxt = []
        for x, y in pieces:
            if e <= x or s >= y: nxt.append((x, y)); continue
            if x < s: nxt.append((x, s))
            if e < y: nxt.append((e, y))
        pieces = nxt
    out += [[x, y] for x, y in pieces if y - x >= 8]
json.dump(out, open(P, 'w'))
print(f'{len(hits)} executed trap addresses in {len(set(starts[bisect.bisect_right(starts, a) - 1] for a in hits))} functions; cavities {sum(b - a for a, b in cav)} -> {sum(b - a for a, b in out)} bytes')
