#!/usr/bin/env python3
"""Layout clean-up of a machine-translated language (translations/<lang>/), applied to the 'Translated Text' column:
  1. DeepL drops the spaces around engine tags ("Usapyon【e】I had them 【b】Base【e】move"): a space is restored between a word and a variable /
     colour tag glued to it;
  2. the dialogue windows of the game do not wrap by themselves (the Japanese texts carry explicit line breaks): a row whose Japanese text has a
     line break but whose translation has none, or has a line wider than the window, is wrapped here, balanced, with the real glyph advances
     (a variable counts as a typical name). Colours are closed and reopened around a break.
usage: layout_text.py [--lang en] [--width 290]"""
import argparse, csv, io, json, math, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
ap = argparse.ArgumentParser(); ap.add_argument('--lang', default='en'); ap.add_argument('--width', type=int, default=300); a = ap.parse_args()
d = os.path.join(ROOT, 'translations', a.lang)
adv = {g['cp']: g['advance'] for g in json.load(open(os.path.join(ROOT, 'data', 'atlas', 'glyphs_sml.json')))['glyphs']}
glyph = lambda c: adv.get(ord(c), 16 if ord(c) > 0x2E80 else 8)
width = lambda s: sum(glyph(c) for c in s)
TAG = re.compile(r'【([^】]*)】'); COLORS = set('brgpBRGPy')
VARW = {'Base': 20, 'Chr': 12, 'Unit': 12, 'Yk': 12, 'Clan': 12, 'Str': 12, 'It': 14, 'Val': 3}
def var_width(t):
    for k, n in VARW.items():
        if t.startswith(k): return width('X' * n)
    return width('X' * 8)                                    # 主人公名 軍師名 交換相手 主人公妖怪名
is_var = lambda t: t[:2] in ('Yk', 'It', 'Ba', 'Cl', 'Ch', 'Un', 'St', 'Va') and re.match(r'^(Yk|It|Base|Clan|Chr|Unit|Str|Val)', t) or t in ('主人公名', '軍師名', '交換相手', '主人公妖怪名')

VARTAG = r'【(?:(?:Yk|It|Base|Clan|Chr|Unit|Str|Val)[^】]*|主人公名|軍師名|交換相手|主人公妖怪名)】'
def fix_colours(t):
    """machine translation loses the words of a coloured ruby span: drop empty spans, stray resets, close what stays open"""
    t, k = re.subn(r'【[brgpBRGPy]】\s*【e】', '', t)
    out, op = [], False
    for part in re.split(r'(【[brgpBRGPye]】)', t):
        if re.fullmatch(r'【[brgpBRGPy]】', part): op = True
        elif part == '【e】':
            if not op: continue
            op = False
        out.append(part)
    t = ''.join(out) + ('【e】' if op else '')
    return re.sub(r'(?<=\S)  +(?=\S)', ' ', t) if k else t

def fix_spaces(t):
    t = re.sub(r'(\w)(【[brgpBRGPy]】' + VARTAG + ')', r'\1 \2', t)          # word【b】【Name】
    t = re.sub('(' + VARTAG + r'【e】)(\w)', r'\1 \2', t)                       # 【Name】【e】word
    return t

def words(par):
    """split a paragraph into (text, width) words; tags stay glued to their word"""
    out, cur, w = [], '', 0
    for part in re.split(r'(【[^】]*】)', par):
        if not part: continue
        if part.startswith('【'):
            tg = part[1:-1]; cur += part
            if is_var(tg): w += var_width(tg)
        else:
            for i, s in enumerate(part.split(' ')):
                if i > 0: out.append((cur, w)); cur, w = '', 0
                cur += s; w += width(s)
    out.append((cur, w)); return [x for x in out if x[0]]

def fill(ws, W, sp):
    lines, cur, cw = [], [], 0
    for t, w in ws:
        add = w + (sp if cur else 0)
        if cur and cw + add > W: lines.append(cur); cur, cw = [t], w
        else: cur.append(t); cw += add
    if cur: lines.append(cur)
    return lines

def wrap_par(par, W):
    sp = glyph(' ')
    ws = words(par)
    if sum(w for _, w in ws) + sp * (len(ws) - 1) <= W: return [par]
    n = len(fill(ws, W, sp)); lo, hi = 40, W
    while lo < hi:                                           # narrowest width keeping n lines
        mid = (lo + hi) // 2
        if len(fill(ws, mid, sp)) <= n: hi = mid
        else: lo = mid + 1
    lines = [' '.join(l) for l in fill(ws, hi, sp)]
    res, open_col = [], None                                 # close / reopen the colour around a break
    for l in lines:
        if open_col: l = '【%s】' % open_col + l
        for m in TAG.finditer(l):
            tg = m.group(1)
            if tg in COLORS: open_col = tg
            elif tg == 'e': open_col = None
        if open_col: l += '【e】'
        res.append(l)
    return res

def process(ja, tr):
    new = fix_spaces(fix_colours(tr))
    tags = TAG.findall(new)
    if '<' in new or any('：' in x or x in ('縮小', '倍角', '全角', '幅小') for x in tags): return new
    ja_nl = '\n' in ja or '\\n' in ja
    pars = re.split(r'(\\n|\n)', new)                                     # paragraphs and their separators
    if len(pars) == 1:
        if not ja_nl: return new
        seps = ['\\n' if '\\n' in ja else '\n']
    else: seps = pars[1::2]
    texts = pars[0::2]
    out = [wrap_par(p, a.width) for p in texts]
    if len(texts) == 1 and len(out[0]) == 1: return new
    res = ''
    for i, lines in enumerate(out):
        sep = seps[min(i, len(seps) - 1)] if i else None
        for j, l in enumerate(lines):
            res += (sep if j == 0 and i else (seps[0] if j else '')) + l if (i or j) else l
    return fix_colours(res)

nsp = nwrap = 0
for t in range(1, 5):
    p = os.path.join(d, f'Sangokushi-script-Type{t}.tsv')
    rows = list(csv.reader(io.StringIO(open(p, encoding='utf-8', newline='').read(), newline=''), delimiter='\t'))
    for r in rows[1:]:
        if len(r) > 6 and r[6].strip():
            n = process(r[5], r[6])
            if n != r[6]:
                if fix_spaces(r[6]) != r[6]: nsp += 1
                if re.sub(r'[ \n]|\\n', '', n) == re.sub(r'[ \n]|\\n', '', fix_spaces(r[6])) and n != fix_spaces(r[6]): nwrap += 1
                r[6] = n
    out = io.StringIO(newline=''); csv.writer(out, delimiter='\t', lineterminator='\r\n').writerows(rows)
    open(p, 'w', encoding='utf-8', newline='').write(out.getvalue())
print(f'{a.lang}: spaces restored in {nsp} rows, {nwrap} rows (re)wrapped at {a.width}px')
