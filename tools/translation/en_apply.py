#!/usr/bin/env python3
"""Merge the worker outputs (work/en/out/*.json) and the fixed texts (work/en/fixed.json) into translations/en/Sangokushi-script-Type[1-4].tsv (column 7).
Rows without a new translation keep their current text (DeepL draft) and are counted. Type 3 headers `<16 hex>` are re-attached. Texts are tidied for the engine:
ASCII quotes, no space around explicit breaks, no double spaces. usage: en_apply.py [--dry]"""
import glob, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); W = os.path.join(ROOT, 'work', 'en')
new = {}
units = {}
for l in open(os.path.join(W, 'units.jsonl'), encoding='utf-8'):
    u = json.loads(l); units[u['id']] = u['jp']
for f in glob.glob(os.path.join(W, 'out', '*.json')):
    try: out = json.load(open(f, encoding='utf-8'))
    except Exception: continue
    for i, en in out.items():
        if int(i) in units and isinstance(en, str) and en.strip(): new[units[int(i)]] = en
fixed = json.load(open(os.path.join(W, 'fixed.json'), encoding='utf-8'))
HEADER = re.compile(r'^(<[0-9a-f]{16}>)')
def tidy(s):
    s = s.replace('’', "'").replace('“', '"').replace('”', '"').replace('…', '...').replace('\n', '\\n')
    s = re.sub(r' *\\n *', r'\\n', s)
    return re.sub(r'(?<=\S)  +(?=\S)', ' ', s).strip(' ')
hit = miss = 0
for t in range(1, 5):
    p = os.path.join(ROOT, 'translations', 'en', f'Sangokushi-script-Type{t}.tsv')
    rows = [l.split('\t') for l in open(p, 'rb').read().decode('utf-8').split('\r\n')]
    for c in rows[1:]:
        if len(c) < 7 or c[0] == 'END': continue
        jp = c[5]; m = HEADER.match(jp); body = HEADER.sub('', jp)
        en = fixed.get(jp) or new.get(body)
        if en is None: miss += 1; continue
        if m and not HEADER.match(en): en = m.group(1) + en
        c[6] = tidy(en) if not m else m.group(1) + tidy(HEADER.sub('', en)); hit += 1
    if '--dry' not in sys.argv: open(p, 'wb').write('\r\n'.join('\t'.join(c) for c in rows).encode('utf-8'))
print(f'rows updated {hit}, rows left as they were {miss}')
