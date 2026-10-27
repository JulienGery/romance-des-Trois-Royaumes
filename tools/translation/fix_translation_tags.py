#!/usr/bin/env python3
"""Deterministic fixes of tag errors found by lint_translation.py, applied ONLY to the 'Translated Text' column (col 7) of the TSVs
(CSV round trip is byte-exact with CRLF, verified):
  1. a translated engine keyword (e.g. 【Partenaire d'échange】 for 【交換相手】) is restored to the original keyword
     (learned from the data: one-to-one, >= 3 occurrences);
  2. a non-keyword, non-ruby tag such as 【Arachnus Yuan Shao】 loses its brackets (it would print literally).
Engine keywords: a tag STARTING WITH Yk|It|Base|Clan|Chr|Unit|Str|Val, or 主人公名 軍師名 交換相手 主人公妖怪名 (FUN_001EB224).
Dry run by default; --apply writes the TSVs (backups in build/tsv_backup/)."""
import csv, io, os, re, shutil, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from langcfg import TSV_DIR as SK
VAR_RE = re.compile(r'^(Yk|It|Base|Clan|Chr|Unit|Str|Val)'); VAR_JP = {'主人公名', '軍師名', '交換相手', '主人公妖怪名'}
COLORS = set('brgpBRGPye'); SIZE = {'縮小', '倍角', '全角', '幅小'}
TAG = re.compile(r'【([^】]*)】')
is_var = lambda x: x in VAR_JP or bool(VAR_RE.match(x))
known = lambda x: is_var(x) or x in COLORS or x in SIZE or '：' in x
apply = '--apply' in sys.argv
def load(t):
    p = os.path.join(SK, f'Sangokushi-script-Type{t}.tsv'); raw = open(p, encoding='utf-8', newline='').read()
    return p, raw, list(csv.reader(io.StringIO(raw, newline=''), delimiter='\t'))
renames = collections.defaultdict(collections.Counter)
data = {t: load(t) for t in range(1, 5)}
for t, (p, raw, rows) in data.items():
    for r in rows[1:]:
        if len(r) > 6 and r[6].strip():
            o = [x for x in TAG.findall(r[5]) if is_var(x)]; n = [x for x in TAG.findall(r[6]) if not known(x)]
            if len(o) == 1 and len(n) == 1: renames[n[0]][o[0]] += 1
good = {k: next(iter(v)) for k, v in renames.items() if len(v) == 1 and sum(v.values()) >= 3}
total = collections.Counter()
for t, (p, raw, rows) in data.items():
    changed = False
    for r in rows[1:]:
        if len(r) > 6 and r[6].strip():
            def fix(m):
                x = m.group(1)
                if known(x): return m.group(0)
                if x in good: total['restored keyword'] += 1; return '【%s】' % good[x]
                total['brackets removed'] += 1; return x
            new = TAG.sub(fix, r[6])
            if new != r[6]: r[6] = new; changed = True
    if changed and apply:
        os.makedirs(os.path.join(ROOT, 'tools', 'build', 'tsv_backup'), exist_ok=True); shutil.copy(p, os.path.join(ROOT, 'tools', 'build', 'tsv_backup', os.path.basename(p)))
        out = io.StringIO(newline=''); csv.writer(out, delimiter='\t', lineterminator='\r\n').writerows(rows)
        open(p, 'w', encoding='utf-8', newline='').write(out.getvalue())
print('keyword renames learned:', good); print(dict(total), '(applied)' if apply else '(dry run, use --apply)')
