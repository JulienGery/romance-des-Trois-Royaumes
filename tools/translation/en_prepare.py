#!/usr/bin/env python3
"""Steps 2 + 3 of the English translation: attach context to every line of the game, drop duplicates, cut the rest into batches for the workers.

Reads   translations/fr/*.tsv (Japanese + reviewed French), translations/glossary_en_full.tsv (tools/translation/en_glossary.py), translations/manual_en.json
Writes  work/en/units.jsonl      one record per UNIQUE Japanese text: id, jp, fr (reviewed French, reference only), n (occurrences), kind, hint, prev/next, fixed (already answered)
        work/en/batches/NNNN.json   units grouped by scene (same file / table), with the glossary entries that occur in them
        work/en/fixed.json       {jp: en} texts that need no worker (empty, symbols, whole-text glossary hits, manual corrections)

Context available in the game data (the scripts carry no speaker field):
  * Type 1 files = one per Yo-kai (680, same order as the table in Type 2 entry 57, lines 0-679): slot 0-5 battle shouts, 6 effect text, 7-11 the five speech personas
  * Type 2 entry 57 = database tables (entry 0 Yo-kai name, 4/6 ability/attack names, 5/7 their descriptions, 47-49 Medallium text ...), other entries: places, quests, UI
  * Type 4 = story scenes (list of lines, title in line 0); Type 3 = bubbles with an 8-byte header (kept verbatim)
usage: en_prepare.py [--batch-chars 3200] [--max-units 60]"""
import argparse, collections, json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser(); ap.add_argument('--batch-chars', type=int, default=3200); ap.add_argument('--max-units', type=int, default=60); a = ap.parse_args()
OUT = os.path.join(ROOT, 'work', 'en'); os.makedirs(os.path.join(OUT, 'batches'), exist_ok=True)
JA = re.compile(r'[぀-ヿ一-鿿ｦ-ﾟ]')
RUBY = re.compile(r'【([^：】]*)：[^】]*】')
plain = lambda s: RUBY.sub(r'\1', s)

def load(path):
    rows = []
    for l in open(path, 'rb').read().decode('utf-8').split('\r\n')[1:]:
        c = l.split('\t')
        if len(c) >= 7 and c[0] != 'END': rows.append(c)
    return rows

glossary = {}
for l in open(os.path.join(ROOT, 'translations', 'glossary_en_full.tsv'), encoding='utf-8'):
    if l[0] != '#':
        c = l.rstrip('\n').split('\t')
        if len(c) >= 3: glossary[c[0]] = (c[1], c[2])
manual = {k.replace('\\n', '\n'): v for k, v in json.load(open(os.path.join(ROOT, 'translations', 'manual_en.json'), encoding='utf-8')).items()}

# ---- 1. all rows, in game order, with their scene ------------------------------------------------------------------------------------------
scenes = collections.OrderedDict()            # (type, file, entry) -> list of (line, jp, fr)
for t in (1, 3, 2, 4):
    for r in load(os.path.join(ROOT, 'translations', 'fr', f'Sangokushi-script-Type{t}.tsv')):
        scenes.setdefault((t, r[0], r[3]), []).append((int(r[4]), r[5], r[6]))
ent57 = {}                                    # entry -> {line: jp}
for (t, f, e), L in scenes.items():
    if t == 2 and f.startswith('00000057'): ent57[int(e)] = {n: jp for n, jp, _ in L}
yokai_files = [f for (t, f, e) in scenes if t == 1]
yokai_of = {f: i for i, f in enumerate(yokai_files)}
def yokai_name(i):
    jp = plain(ent57.get(0, {}).get(i, ''))
    g = glossary.get(jp)
    return f'{jp} (wiki: {g[0]})' if g else jp
ENT57 = {0: 'Yo-kai name', 1: 'Yo-kai name, katakana reading', 4: 'name of the ability the Yo-kai grants when it possesses a Yo-kai (Inspirit)', 5: 'description of that ability, starts "the possessed Yo-kai ..."',
         6: 'name of the Yo-kai\'s attack/technique', 7: 'description of that attack', 47: 'Medallium description of the Yo-kai (third person)', 48: 'Medallium: what the Yo-kai says when recruited (first person)',
         49: 'Medallium: what the Yo-kai says when first met / traded (first person)'}
SLOT = {6: 'battle: effect text of the Yo-kai\'s skill', **{i: 'battle shout of the Yo-kai' for i in range(6)},
        7: 'reaction line, speaker persona 1 (neutral boy)', 8: 'same reaction, persona 2 (girl)', 9: 'same reaction, persona 3 (rough guy)', 10: 'same reaction, persona 4 (old man)', 11: 'same reaction, persona 5 (cat, ends in "nyan")'}

def hint_for(t, f, e, line, L):
    if t == 1:
        i = yokai_of[f]; s = SLOT.get(line, 'unused slot')
        return f'Yo-kai #{i} {yokai_name(i)} - {s}'
    if t == 2 and f.startswith('00000057'):
        e = int(e)
        if e in ENT57 and len(ent57[e]) == 680: return f'Yo-kai #{line} {yokai_name(line)} - {ENT57[e]}'
        return f'database table #{e} line {line}'
    if t == 4: return f'story/blog scene {f[:8]}'
    if t == 3: return 'dialogue bubble'
    return f'table {f[:8]} #{e}'

# ---- 2. units (unique texts) ---------------------------------------------------------------------------------------------------------------
HEADER = re.compile(r'^(<[0-9a-f]{16}>)')
fixed, units, order = {}, collections.OrderedDict(), []
def classify(jp):
    s = plain(jp).strip()
    if s in ('', 'NULL', '―', '-', '－'): return jp
    if re.fullmatch(r'\d+;[0-9a-f]*', s): return jp
    if not JA.search(RUBY.sub('', s)) and not re.search(r'[A-Za-z]{2}', re.sub(r'【[^】]*】', '', s)): return jp
    if jp in manual: return manual[jp]
    g = glossary.get(s.replace('\\n', ''))
    if g and len(s) > 2 and not g[1].startswith('char') : return g[0]
    return None

for key, L in scenes.items():
    t, f, e = key
    jps = [x[1] for x in L]
    for idx, (line, jp, fr) in enumerate(L):
        body = HEADER.sub('', jp)
        r = classify(body)
        if r is not None: fixed[jp] = r if not HEADER.match(jp) else HEADER.match(jp).group(1) + r; continue
        if body in units:
            units[body]['n'] += 1; continue
        pv = [plain(x).replace('\\n', ' ')[:70] for x in [HEADER.sub('', y) for y in jps[max(0, idx - 2):idx]] if x not in ('NULL', '―')]
        nx = [plain(x).replace('\\n', ' ')[:70] for x in [HEADER.sub('', y) for y in jps[idx + 1:idx + 2]] if x not in ('NULL', '―')]
        u = {'id': len(units), 'jp': body, 'fr': HEADER.sub('', fr) if fr != jp else '', 'n': 1, 'hint': hint_for(t, f, e, line, L), 'prev': pv, 'next': nx, 'scene': f'{t}/{f}/{e}'}
        units[body] = u
with open(os.path.join(OUT, 'units.jsonl'), 'w', encoding='utf-8') as f:
    for u in units.values(): f.write(json.dumps(u, ensure_ascii=False) + '\n')
json.dump(fixed, open(os.path.join(OUT, 'fixed.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

# ---- 3. batches: consecutive units of the same scene, 3200 chars at most --------------------------------------------------------------------
terms = sorted((k for k in glossary if len(k) >= 3 or (len(k) == 2 and re.search(r'[一-鿿゠-ヿ]', k))), key=len, reverse=True)
CORE = [k for k in ('妖怪', '妖怪ウォッチ', 'ジバニャン', 'コマさん', 'ウィスパー', 'メダル', '妖怪メダル') if k in glossary]
batches, cur, chars = [], [], 0
def flush():
    global cur, chars
    if not cur: return
    text = '\n'.join(plain(u['jp']) for u in cur)
    gl = {k: glossary[k][0] for k in terms if k in text}
    for k in CORE: gl.setdefault(k, glossary[k][0])
    batches.append({'batch': len(batches), 'scene': cur[0]['scene'], 'units': cur, 'glossary': gl}); cur, chars = [], 0
for u in units.values():
    n = len(plain(u['jp']))
    if cur and (chars + n > a.batch_chars or len(cur) >= a.max_units or (u['scene'] != cur[-1]['scene'] and chars > a.batch_chars * 0.6)): flush()
    cur.append(u); chars += n
flush()
for b in batches: json.dump(b, open(os.path.join(OUT, 'batches', f"{b['batch']:04d}.json"), 'w', encoding='utf-8'), ensure_ascii=False)
total = sum(len(r) for r in scenes.values())
print(f'{total} lines -> {len(fixed)} fixed texts, {len(units)} unique units to translate ({sum(len(plain(u["jp"])) for u in units.values())} chars) in {len(batches)} batches -> {OUT}')
