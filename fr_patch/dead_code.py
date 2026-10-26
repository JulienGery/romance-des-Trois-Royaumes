#!/usr/bin/env python3
"""Static reachability over the game's code: which functions can never be reached? (candidates for code space, then confirmed by
cavity_search.py). Roots = every code address stored in .rodata/.data (absolute or REL32) and the entry point. Edges = bl/b/adr/literal/Thumb bl
found inside each function. Output: build/dead_candidates.json = [[start,end]...] (function aligned)."""
import bisect, json, os, re, struct, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = open(os.path.join(ROOT, 'exefs.elf'), 'rb').read()
src = open(os.path.join(ROOT, 'code.c'), errors='replace').read()
starts = sorted(set(int(m.group(1), 16) for m in re.finditer(r'// Fonction : \S+ @ ([0-9a-f]{8})', src)))
starts = [s for s in starts if 0x100000 <= s < 0x60c000]; ends = starts[1:] + [0x60c000]; n = len(starts)
def fidx(a): return bisect.bisect_right(starts, a) - 1 if 0x100000 <= a < 0x60c000 else -1
edges = [set() for _ in range(n)]; roots = {fidx(0x100000)}
text = d[0x1000:0x1000 + 0x50c000]
words = struct.unpack('<%dI' % (len(text) // 4), text)
for i, w in enumerate(words):
    pc = 0x100000 + i * 4; f = fidx(pc); t = None
    if (w >> 25) & 7 == 5:
        off = w & 0xFFFFFF
        if off & 0x800000: off -= 0x1000000
        t = pc + 8 + off * 4
    elif (w & 0x0FFF0000) in (0x028F0000, 0x024F0000):
        rot = ((w >> 8) & 0xF) * 2; imm = w & 0xFF; imm = ((imm >> rot) | (imm << (32 - rot))) & 0xFFFFFFFF if rot else imm
        t = pc + 8 + imm if (w & 0x0FFF0000) == 0x028F0000 else pc + 8 - imm
    elif 0x100000 <= w < 0x60c000: t = w & ~1
    if t is not None and fidx(t) >= 0 and fidx(t) != f: edges[f].add(fidx(t))
    if 0x100000 <= ((pc + w) & 0xFFFFFFFF) < 0x60c000 and w:       # REL32 word inside code (tables of relative function addresses)
        tt = fidx(((pc + w) & 0xFFFFFFFF) & ~1)
        if tt >= 0 and ((pc + w) & ~1) == starts[tt] and tt != f: edges[f].add(tt)
hws = struct.unpack('<%dH' % (len(text) // 2), text)
for i in range(len(hws) - 1):
    h1 = hws[i]
    if (h1 & 0xF800) == 0xF000 and (hws[i + 1] & 0xF800) in (0xF800, 0xE800):
        pc = 0x100000 + i * 2; h2 = hws[i + 1]
        imm = ((h1 & 0x7FF) << 12) | ((h2 & 0x7FF) << 1)
        if imm & 0x400000: imm -= 0x800000
        t = pc + 4 + imm
        if (h2 & 0xF800) == 0xE800: t &= ~3
        if fidx(t) >= 0 and fidx(t) != fidx(pc): edges[fidx(pc)].add(fidx(t))
for o, sz, base in ((0x50d000, 0x68000, 0x60c000), (0x575000, 0x3c000, 0x674000)):
    for i, w in enumerate(struct.unpack('<%dI' % (sz // 4), d[o:o + sz])):
        A = base + i * 4
        if 0x100000 <= w < 0x60c000: roots.add(fidx(w & ~1))
        t = ((A + w) & 0xFFFFFFFF) & ~1
        if w and 0x100000 <= t < 0x60c000 and t == starts[fidx(t)]: roots.add(fidx(t))      # REL32 (static-constructor table)
live = set(); stack = list(roots)
while stack:
    f = stack.pop()
    if f in live: continue
    live.add(f); stack.extend(edges[f] - live)
dead = [i for i in range(n) if i not in live]
# a live function can FALL THROUGH into the next one (C++ `this`-adjusting thunks: `add r0,r0,#4` then the real function follows).
# A predecessor is safe only if its last instruction (before its literal pool) is a terminator: bx/pop pc/ldm pc/unconditional b/ldr pc.
def word(a): return struct.unpack_from('<I', d, 0x1000 + a - 0x100000)[0]
def terminator(w):
    if (w >> 28) != 0xE: return False
    return w == 0xE12FFF1E or (w & 0x0FF00000) in (0x08B00000, 0x08900000, 0x08300000, 0x08100000) and (w & 0x8000) or (w >> 24) == 0xEA or \
           (w & 0x0FF000F0) == 0x01200010 or (w & 0x0F7FF000) == 0x051FF000 or (w & 0x0FFFF000) == 0x059FF000 or (w & 0x0E50F000) == 0x0410F000
def falls_through(i):
    st, en = starts[i], ends[i]; pool = set()
    for a in range(st, en, 4):
        w = word(a)
        if (w & 0x0F7F0000) == 0x051F0000 and (w >> 28) in (0xE, 0x0, 0x1, 0x2, 0x3, 0xA, 0xB, 0xC, 0xD): pool.add(a + 8 + ((w & 0xFFF) if (w >> 23) & 1 else -(w & 0xFFF)))
    a = en - 4
    while a >= st and a in pool: a -= 4
    return not (a >= st and terminator(word(a)))
runs = []; skipped = 0; deadset = set(dead)
for i in dead:
    if i - 1 not in deadset and i > 0 and falls_through(i - 1): skipped += 1; continue
    if runs and runs[-1][1] == starts[i]: runs[-1][1] = ends[i]
    else: runs.append([starts[i], ends[i]])
os.makedirs(os.path.join(ROOT, 'fr_patch', 'build'), exist_ok=True)
json.dump(runs, open(os.path.join(ROOT, 'fr_patch', 'build', 'dead_candidates.json'), 'w'))
print(f'(skipped {skipped} fall-through candidates) {n} functions, {len(roots)} roots, {len(dead)} unreachable, {sum(b - a for a, b in runs)} bytes; largest runs:',
      [(hex(a), b - a) for a, b in sorted(runs, key=lambda r: r[0] - r[1])[:10]])
