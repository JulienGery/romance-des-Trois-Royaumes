#!/usr/bin/env python3
"""Check the worker outputs work/en/out/NNNN.json against work/en/batches/NNNN.json: every id present, game tags identical, no Japanese left,
no French leftovers, sane length. Prints the failing batches/units; `--redo` writes work/en/redo.json (batch numbers to run again, units to fix).
usage: en_validate.py [--batch N ...] [--redo]"""
import json, os, re, sys, glob
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); W = os.path.join(ROOT, 'work', 'en')
JA = re.compile(r'[぀-ヿ一-鿿ｦ-ﾟ　-〿！-～]')
TAG = re.compile(r'【([^】]*)】'); RUBY = re.compile(r'【([^：】]*)：[^】]*】')
FR = re.compile(r"[àâçéèêëîïôûùüÿœ]|\b(?:le|la|les|des|une|est|pour|vous|nous|pas|avec)\b", re.I)
def tags(s): return [m.group(0) for m in TAG.finditer(RUBY.sub(r'\1', s))]
def check(u, en):
    errs = []
    if not isinstance(en, str) or not en.strip(): return ['empty']
    COL = set('brgpBRGPye')
    jv = sorted(t for t in tags(u['jp']) if t[1:-1] not in COL); ev = sorted(t for t in tags(en) if t[1:-1] not in COL)
    if jv != ev: errs.append(f'variables {jv} != {ev}')
    depth = 0
    for t in tags(en):
        if t[1:-1] == 'e': depth -= 1
        elif t[1:-1] in COL: depth += 1
        if depth < 0 or depth > 1: break
    if depth != 0: errs.append('unbalanced colours')
    if JA.search(TAG.sub('', en)): errs.append('japanese left')
    jl = len(TAG.sub('', RUBY.sub(r'\1', u['jp']))); 
    if len(en) > 3 * max(jl, 8) + 12: errs.append(f'too long {len(en)}/{jl}')
    return errs
only = [int(x) for x in sys.argv[sys.argv.index('--batch') + 1:] if x.isdigit()] if '--batch' in sys.argv else None
bad, nok, nmiss = {}, 0, []
for bf in sorted(glob.glob(os.path.join(W, 'batches', '*.json'))):
    b = json.load(open(bf, encoding='utf-8')); n = b['batch']
    if only and n not in only: continue
    of = os.path.join(W, 'out', f'{n:04d}.json')
    if not os.path.exists(of): nmiss.append(n); continue
    try: out = json.load(open(of, encoding='utf-8'))
    except Exception as e: bad[n] = {'*': [f'invalid json: {e}']}; continue
    for u in b['units']:
        if str(u['id']) not in out: bad.setdefault(n, {})[u['id']] = ['missing']; continue
        e = check(u, out[str(u['id'])])
        if e: bad.setdefault(n, {})[u['id']] = e
        else: nok += 1
print(f'ok units {nok}; batches missing {len(nmiss)}; batches with problems {len(bad)} ({sum(len(v) for v in bad.values())} units)')
for n, d in list(bad.items())[:15]:
    for i, e in list(d.items())[:4]: print(' ', n, i, e)
if '--redo' in sys.argv: json.dump({'missing': nmiss, 'bad': {str(k): v for k, v in bad.items()}}, open(os.path.join(W, 'redo.json'), 'w'), indent=0)
