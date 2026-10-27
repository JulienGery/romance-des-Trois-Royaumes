#!/usr/bin/env python3
"""Hand-written translations that replace the machine ones: translations/manual_<lang>.json maps the Japanese text of a row to its translation
(every row with exactly that Japanese text is replaced). Used for the sentences the machine translation cannot handle (an engine variable
followed by a Japanese particle: the subject/object order is invented). usage: apply_manual.py [--lang en]"""
import argparse, csv, io, json, os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
ap = argparse.ArgumentParser(); ap.add_argument('--lang', default='en'); a = ap.parse_args()
m = json.load(open(os.path.join(ROOT, 'translations', f'manual_{a.lang.split("-")[0]}.json'), encoding='utf-8')); n = 0
for t in range(1, 5):
    p = os.path.join(ROOT, 'translations', a.lang, f'Sangokushi-script-Type{t}.tsv')
    rows = list(csv.reader(io.StringIO(open(p, encoding='utf-8', newline='').read(), newline=''), delimiter='\t'))
    for r in rows[1:]:
        if len(r) > 6 and r[5] in m and r[6] != m[r[5]]: r[6] = m[r[5]]; n += 1
    out = io.StringIO(newline=''); csv.writer(out, delimiter='\t', lineterminator='\r\n').writerows(rows)
    open(p, 'w', encoding='utf-8', newline='').write(out.getvalue())
print(f'{n} rows replaced by the manual translations')
