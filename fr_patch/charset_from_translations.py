#!/usr/bin/env python3
"""Print the non-ASCII characters used by the French translations (tag contents 【…】 excluded)."""
import csv, glob, os, re, sys
d = os.path.join(os.path.dirname(__file__), '..', 'SangoKuro')
used = set()
for p in glob.glob(os.path.join(d, 'Sangokushi-script-Type*.tsv')):
    for r in list(csv.reader(open(p, encoding='utf-8'), delimiter='\t'))[1:]:
        if len(r) > 6 and r[6].strip():
            used |= set(re.sub(r'【[^】]*】', '', r[6]))
print(''.join(sorted(c for c in used if ord(c) > 127 and not ('　' <= c <= '鿿' or '＀' <= c <= '￯'))))
