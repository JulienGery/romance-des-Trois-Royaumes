#!/usr/bin/env python3
"""Finds the machine-translation defects that break the game's text (not covered by lint_translation.py). usage: scan_translation_issues.py [--lang en]
Writes tools/build/issues_<lang>.csv (category, type, file, entry, line, JA, translation) and prints the counts."""
import argparse, collections, csv, os, re
csv.field_size_limit(10**9)
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
ap = argparse.ArgumentParser(); ap.add_argument('--lang', default='en'); a = ap.parse_args()
TAG = re.compile(r'【([^】]*)】'); V = r'【(?:Yk|It|Base|Clan|Chr|Unit|Str|Val)[^】]*】|【(?:主人公名|軍師名|交換相手|主人公妖怪名)】'
PART = re.compile(r'(?:【[brgpBRGPy]】)?(?:' + V + r')(?:【e】)?(?:を|に|と|が|は|へ|の|で|も|から|より|さん|たち)')
FMT = re.compile(r'%[-0-9.]*[sdxXfc]|<[0-9a-f]{8,}>')
rows_out = []; cnt = collections.Counter()
def add(c, t, r): cnt[c] += 1; rows_out.append([c, t, r[0][:8], r[3], r[4], r[5], r[6]])
for t in range(1, 5):
    for r in list(csv.reader(open(os.path.join(ROOT, 'translations', a.lang, f'Sangokushi-script-Type{t}.tsv'), newline='', encoding='utf-8'), delimiter='\t'))[1:]:
        ja, tr = r[5], r[6]
        if not tr.strip(): continue
        if PART.search(ja): add('variable + particle in JA: word order/subject invented by the translation', t, r)
        if re.search(r'【[brgpBRGPy]】\s*【e】', tr): add('empty colour span (ruby text lost)', t, r)
        d = 0; bad = False
        for m in re.finditer(r'【([brgpBRGPye])】', tr):
            d += -1 if m.group(1) == 'e' else 1; bad |= d < 0
        if bad or d: add('unbalanced colour tags', t, r)
        jv = re.findall(V, ja)
        if jv and collections.Counter(jv) != collections.Counter(re.findall(V, tr)): add('variable missing/extra/duplicated', t, r)
        if collections.Counter(FMT.findall(ja)) != collections.Counter(FMT.findall(tr)): add('format specifier or <hex> token mismatch', t, r)
        if jv and len(re.sub(r'【[^】]*】', '', tr).split()) <= 2 and len(re.sub(r'【[^】]*】', '', ja)) > 6: add('content dropped (very short with a variable)', t, r)
        if re.search(r'[぀-ヿ一-鿿]', TAG.sub('', tr)): add('Japanese characters left', t, r)
        if re.search(r'\*[^*\s][^*]*\*', tr): add('markdown asterisks', t, r)
        if re.search(r'[A-Za-z]【(?:[brgpBRGPy])】|【e】[A-Za-z]', tr): add('letters glued to a colour tag', t, r)
os.makedirs(os.path.join(ROOT, 'tools', 'build'), exist_ok=True)
with open(os.path.join(ROOT, 'tools', 'build', f'issues_{a.lang}.csv'), 'w', encoding='utf-8', newline='') as f:
    w = csv.writer(f); w.writerow(['category', 'type', 'file', 'entry', 'line', 'original', 'translation']); w.writerows(rows_out)
for c, n in cnt.most_common(): print(f'{n:6d}  {c}')
