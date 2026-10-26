#!/usr/bin/env python3
"""Lint the French translation TSVs (SangoKuro/Sangokushi-script-Type[1-4].tsv).
Checks: glyph coverage (French atlas, else the game's Japanese 16px font), byte budget per string (page buffers are 0x200),
tag integrity (orphans, colour reset, variable tags kept vs the original), line count after French wrapping,
untranslated rows, Type 3 prefix, Type 4 bytecode rows, double spaces. Writes build/lint_report.csv.
usage: lint_translation.py [--strict]   (exit 1 when an ERROR is found)"""
import csv, json, os, re, struct, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); SK = os.path.join(HERE, '..', 'SangoKuro')
sys.path.insert(0, HERE)
atlas = {g['ch'] for g in json.load(open(os.path.join(HERE, 'build', 'glyphs_sml.json')))['glyphs']}
adv = {g['ch']: g['advance'] for g in json.load(open(os.path.join(HERE, 'build', 'glyphs_sml.json')))['glyphs']}
# the game's own Japanese 16px code table (ELF .rodata 0x615350, 2139 UTF-8-packed codes)
elf = open(os.path.join(HERE, '..', 'exefs.elf'), 'rb').read()
jp = set()
for c in struct.unpack('<2139I', elf[0x50d000 + 0x615350 - 0x60c000:][:2139 * 4]):
    try: jp.add(c.to_bytes(4, 'big').lstrip(b'\0').decode('utf8'))
    except Exception: pass
COLORS = set('brgpBRGPye') | {'G', 'R', 'B'}
SIZE_TAGS = {'縮小', '倍角', '全角', '幅小'}
TAG = re.compile(r'【([^】]*)】')
# authoritative keyword table of the engine (FUN_001EB224, table at 0x0067D9C0): a tag is a variable when it STARTS WITH one of the 8 prefixes
# (the engine does a prefix compare: 'Item1.strItName' matches 'It'), or equals one of 4 Japanese keywords
VAR_RE = re.compile(r'^(Yk|It|Base|Clan|Chr|Unit|Str|Val)')
VAR_JP = {'主人公名', '軍師名', '交換相手', '主人公妖怪名'}
def known_var(x): return x in VAR_JP or bool(VAR_RE.match(x))
issues = []
def add(sev, typ, fn, line, msg): issues.append((sev, typ, fn, line, msg))

def wrap_lines(text, wrap=301, cw=16):
    """greedy estimate (same rules as frwrap.h in spirit) -> number of lines"""
    n = 0
    for para in text.split('\n'):
        words, cur, k = para.split(' '), 0, 1
        for w in words:
            ww = sum(adv.get(c, cw) for c in w) * cw // 16 + 4
            if cur and cur + ww > wrap: k += 1; cur = ww
            else: cur += ww
        n += k
    return n

stats = collections.Counter(); chars_missing = collections.Counter(); vars_seen = collections.Counter()
for t in range(1, 5):
    rows = list(csv.reader(open(os.path.join(SK, f'Sangokushi-script-Type{t}.tsv'), encoding='utf-8'), delimiter='\t'))[1:]
    for r in rows:
        if not r or r[0] == 'END' or len(r) < 6: continue
        fn, entry, line = r[0], r[3], r[4]; orig = r[5]; tr = r[6] if len(r) > 6 else ''
        stats['rows'] += 1
        if t == 4 and entry == '1':
            if tr and tr != orig: add('ERROR', t, fn, line, 'bytecode row (entry 1) modified')
            continue
        if t == 3:
            if not re.match(r'^<[0-9a-fA-F]{16}>', (tr or orig)): add('ERROR', t, fn, line, 'Type3 text lost its <hex16> prefix')
        if not tr.strip():
            if orig.strip() and orig != 'NULL' and re.search(r'[぀-ヿ一-鿿]', orig): add('WARN', t, fn, line, 'untranslated (Japanese original kept)'); stats['untranslated'] += 1
            continue
        stats['translated'] += 1
        body = tr[18:] if t == 3 else tr
        txt = body.replace('\\n', '\n')
        # bytes
        b = len(txt.replace("...", "…").encode('utf-8')) + 1
        if b > 0x1FF: add('ERROR', t, fn, line, f'{b} bytes > 511 (page buffer 0x200)')
        elif b > 400: add('WARN', t, fn, line, f'{b} bytes (close to the 511 limit)')
        # tags
        tags = TAG.findall(txt)
        if txt.count('【') != txt.count('】'): add('ERROR', t, fn, line, 'unbalanced 【 】')
        opens = sum(1 for x in tags if x in COLORS and x != 'e'); resets = sum(1 for x in tags if x == 'e')
        if opens and not resets: add('WARN', t, fn, line, 'colour tag without 【e】 reset')
        for x in tags:
            if '：' in x: add('WARN', t, fn, line, f'ruby tag kept in French text: 【{x}】'); continue
            if x in COLORS or x in SIZE_TAGS: continue
            if known_var(x): vars_seen[x] += 1
            else: add('ERROR', t, fn, line, f'unknown tag 【{x}】 (not an engine keyword: it would print literally with its brackets)')
        otags = [x for x in TAG.findall(orig.replace('\\n', '\n')) if known_var(x)]
        ntags = [x for x in tags if known_var(x)]
        if collections.Counter(otags) != collections.Counter(ntags): add('ERROR', t, fn, line, f'engine variable tags differ: original {otags} vs translation {ntags}')
        plain = TAG.sub('', txt)
        # glyphs
        for c in set(plain):
            if c == '\n' or ord(c) < 0x20 or 0xE000 <= ord(c) <= 0xE07F: continue   # PUA E000-E07F = button icons (FUN_0052C690)
            if c in atlas: continue
            if c in jp: stats['jp_font_glyph'] += 1; continue
            chars_missing[c] += 1
            add('ERROR', t, fn, line, f'no glyph for {c!r} (U+{ord(c):04X}) in French atlas nor Japanese font')
        if '  ' in plain: add('WARN', t, fn, line, 'double space')
        if re.search(r' \n|\n ', plain): add('WARN', t, fn, line, 'space around a line break')
        n = wrap_lines(plain)
        stats[f'lines>={min(n,9)}'] += 1
        if n > 9: add('ERROR', t, fn, line, f'{n} lines at 301px/16px (window supports ~9)')
        elif n > 6: add('INFO', t, fn, line, f'{n} lines at 301px/16px')

os.makedirs(os.path.join(HERE, 'build'), exist_ok=True)
with open(os.path.join(HERE, 'build', 'lint_report.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['severity', 'type', 'file', 'line', 'message']); w.writerows(issues)
sev = collections.Counter(i[0] for i in issues)
print('rows', stats['rows'], 'translated', stats['translated'], 'untranslated(JP kept)', stats['untranslated'])
print('issues:', dict(sev), '  (build/lint_report.csv)')
print('variable tags seen:', dict(vars_seen.most_common(12)))
if chars_missing: print('characters without glyph:', dict(chars_missing.most_common(20)))
by = collections.Counter((i[0], re.sub(r'[\d\[\]\'(),{}:.<>=]+', '#', i[4])[:50]) for i in issues)
for (s, m), n in by.most_common(14): print(f'  {n:6d} {s:5s} {m}')
sys.exit(1 if ('--strict' in sys.argv and sev['ERROR']) else 0)
