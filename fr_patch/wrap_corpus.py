#!/usr/bin/env python3
"""Dump the translated corpus as engine-like pre-processed buffers (one record per line, NUL separated)."""
import csv, glob, os, re, sys
d = os.path.join(os.path.dirname(__file__), '..', 'SangoKuro')
col = {'b': 0, 'r': 1, 'g': 2, 'p': 3, 'B': 4, 'R': 5, 'G': 6, 'y': 7}
def conv(m):
    t = m.group(1)
    if t == 'e': return b'\x13'
    if t in col: return b'\x12' + bytes([col[t]])
    if t == '縮小': return b'\x16'
    if t == '倍角': return b'\x15'
    return b'Xxxxxxxxx'                       # variable (player/unit name...) expanded to ~9 glyphs
out = open(sys.argv[1], 'wb'); n = 0
for p in sorted(glob.glob(os.path.join(d, 'Sangokushi-script-Type*.tsv'))):
    for r in list(csv.reader(open(p, encoding='utf-8'), delimiter='\t'))[1:]:
        if len(r) > 6 and r[6].strip():
            t = r[6].replace('\\n', '\n').replace("'", "'")
            b = re.sub(r'【([^】：]*)】', lambda m: '\0%s\0' % m.group(1), t)
            parts = b.split('\0'); res = b''
            for i, x in enumerate(parts):
                res += x.encode('utf-8') if i % 2 == 0 else conv(re.match(r'(.*)', x))
            if b'\x00' in res or b'\x11' in res: continue
            out.write(res + b'\0'); n += 1
print(n, 'records')
