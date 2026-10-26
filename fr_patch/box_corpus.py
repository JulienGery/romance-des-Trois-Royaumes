#!/usr/bin/env python3
"""Sample of translated dialogue strings covering 1..9 wrapped lines at 301 px / 16 px, NUL separated (raw engine text:
real newlines, colour tags kept, variable tags replaced by 9 glyphs)."""
import csv, glob, os, re, sys, random
random.seed(7)
sys.path.insert(0, os.path.dirname(__file__))
d = os.path.join(os.path.dirname(__file__), '..', 'SangoKuro')
adv = {}
import json
g = json.load(open(os.path.join(os.path.dirname(__file__), 'build', 'glyphs_sml.json')))['glyphs']
for x in g: adv[x['ch']] = x['advance']
def width(s): return sum(adv.get(c, 16) for c in s)
def nlines(t, wrap=301):
    n = 0
    for para in t.split('\n'):
        words, cur, k = para.split(' '), 0, 1
        for w in words:
            ww = width(w) + 4
            if cur and cur + ww > wrap: k += 1; cur = ww
            else: cur += ww
        n += k
    return n
buckets = {}
for p in sorted(glob.glob(os.path.join(d, 'Sangokushi-script-Type*.tsv'))):
    for r in list(csv.reader(open(p, encoding='utf-8'), delimiter='\t'))[1:]:
        if len(r) > 6 and r[6].strip():
            t = re.sub(r'【(?!e】|[rgbyRGBp]】|縮小】)[^】]*】', 'Xxxxxxxxx', r[6].replace('\\n', '\n'))
            buckets.setdefault(min(nlines(t), 9), []).append(t)
out = open(sys.argv[1], 'wb'); tot = 0
for k in sorted(buckets):
    pick = random.sample(buckets[k], min(len(buckets[k]), 12))
    for t in pick: out.write(t.encode('utf-8') + b'\0'); tot += 1
    print(k, len(buckets[k]), 'sampled', len(pick))
print(tot)
