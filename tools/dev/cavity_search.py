#!/usr/bin/env python3
"""Confirm which statically-dead functions (build/dead_candidates.json) are really free: fill a subset with an undefined-instruction trap, boot the
original game in the interpreter and compare with an untouched boot (same number of draws/transfers/fills and threads, no trap executed, no
fatal error). Delta debugging removes the functions that change the behaviour (they are read as data or executed). Writes build/cavities.json."""
import bisect, json, os, re, struct, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); RW = os.path.join(ROOT, 'work', 'rom'); HERE = os.path.join(ROOT, 'tools')
FRAMES = int(os.environ.get('FRAMES', '1500'))
def sh(c): return subprocess.run(c, shell=True, cwd=RW, capture_output=True, text=True).stdout
src = open(os.path.join(ROOT, 'externals', 'code.c'), errors='replace').read()
starts = sorted(set(int(m.group(1), 16) for m in re.finditer(r'// Fonction : \S+ @ ([0-9a-f]{8})', src)))
starts = [s for s in starts if 0x100000 <= s < 0x60c000]; ends = starts[1:] + [0x60c000]; endof = dict(zip(starts, ends))
runs = json.load(open(os.path.join(HERE, 'build', 'dead_candidates.json')))
cand = [s for s in starts for a, b in runs if a <= s < b]
sh('rm -rf exefs_p && ../../externals/3dstool -xtfu exefs exefs.bin --exefs-dir exefs_p --header exefs_header_p.bin')
orig = open(os.path.join(RW, 'exefs_p/code.bin'), 'rb').read()
def boot(fill):
    code = bytearray(orig)
    for s in fill:
        for va in range(s, endof[s], 4): struct.pack_into('<I', code, va - 0x100000, 0xE7F000F0)
    open(os.path.join(RW, 'exefs_p/code.bin'), 'wb').write(code)
    sh('../../externals/3dstool -ctf exefs exefs_p.bin --exefs-dir exefs_p --header exefs_header_p.bin --compress')
    sh('../../externals/3dstool -ctf cxi game_p.cxi --header header.bin --exh exheader.bin --logo logo.bin --plain plain.bin --exefs exefs_p.bin --romfs romfs_fr.bin --not-encrypt')
    sh('rm -rf /private/tmp/claude-501/zP; mkdir -p /private/tmp/claude-501/zP')
    out = sh(f'zakuro game_p.cxi --interpreter --headless {FRAMES} --mute --rasterizer software --data /private/tmp/claude-501/zP 2>&1 | grep -v "^v[0-9]* = "')
    m = re.search(r'(\d+) threads .*?(\d+) draws \| (\d+) transfers \| (\d+) fills', out)
    sig = m.groups() if m else None
    traps = len(re.findall(r'undefined instruction 0xE7F000F0', out)); fatal = 'fatal errors' in out
    return sig, traps, fatal, out
base, _, _, _ = boot([])
print('baseline', base, flush=True)
def good(fill):
    sig, traps, fatal, out = boot(fill)
    ok = sig == base and not traps and not fatal
    print(f'  test {len(fill)} functions: {"ok" if ok else "BAD"} {sig} traps={traps}', flush=True)
    return ok
def find_bad(items):
    """delta debugging: returns the set of items that must be excluded"""
    if not items or good(items): return set()
    if len(items) == 1: return set(items)
    h = len(items) // 2
    return find_bad(items[:h]) | find_bad(items[h:])
keep = list(cand); bad = set()
while True:
    b = find_bad([s for s in keep if s not in bad])
    if not b: break
    bad |= b
    print('excluded', [hex(x) for x in sorted(b)], flush=True)
    keep = [s for s in keep if s not in bad]
    # neighbours of a culprit often belong to the same routine: exclude them too, then re-verify the whole set
    for s in list(bad):
        i = starts.index(s)
        for j in (i - 1, i + 1):
            if 0 <= j < len(starts) and starts[j] in keep: keep.remove(starts[j])
res = []
for s in sorted(keep):
    if res and res[-1][1] == s: res[-1][1] = endof[s]
    else: res.append([s, endof[s]])
json.dump(res, open(os.path.join(HERE, 'build', 'cavities.json'), 'w'))
print('cavities:', [(hex(a), b - a) for a, b in sorted(res, key=lambda r: r[0] - r[1])[:12]], 'total', sum(b - a for a, b in res))
