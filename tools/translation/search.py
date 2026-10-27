#!/usr/bin/env python3
"""Find a sentence in the translation TSVs: tools/translation/search.py "texte" [--lang fr] [--ja]
Searches the translated column (or the Japanese one with --ja) and prints file, line number and both texts, ready to edit."""
import argparse, csv, glob, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser(); ap.add_argument('text'); ap.add_argument('--lang', default='fr'); ap.add_argument('--ja', action='store_true', help='search the Japanese column'); ap.add_argument('--max', type=int, default=30)
a = ap.parse_args(); col = 5 if a.ja else 6; n = 0; csv.field_size_limit(1 << 24)
for p in sorted(glob.glob(os.path.join(ROOT, 'translations', a.lang, 'Sangokushi-script-Type*.tsv'))):
    with open(p, encoding='utf-8', newline='') as f:
        for i, r in enumerate(csv.reader(f, delimiter='\t'), 1):
            if len(r) > 6 and a.text.lower() in r[col].lower():
                n += 1
                if n <= a.max: print(f'{os.path.relpath(p, ROOT)}:{i}\n  JA: {r[5]}\n  {a.lang.upper()}: {r[6]}')
print(f'{n} match(es)' + (f', {a.max} shown' if n > a.max else ''))
