#!/usr/bin/env python3
"""Use the official English Yo-kai names (translations/yokai_names_en.tsv, see yokai_names.py) in an English translation.
  1. every row of the game's name table whose Japanese text is exactly a Yo-kai name gets the official name (the table the game uses for the
     【Yk…】 variables, so dialogue that inserts a name at run time is covered);
  2. in other rows, when the Japanese sentence contains a known name and the machine translation rendered it differently (the rendering
     is taken from the name table), that rendering is replaced by the official name.
usage: apply_names.py [--lang en]"""
import argparse, csv, io, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
ap = argparse.ArgumentParser(); ap.add_argument('--lang', default='en'); ap.add_argument('--name-file', default='00000057-X-01040104', help='script file holding the game\'s Yo-kai name table (only its rows are overridden exactly)'); ap.add_argument('--names', default=os.path.join(ROOT, 'translations', 'yokai_names_en.tsv'))
a = ap.parse_args(); d = os.path.join(ROOT, 'translations', a.lang)
norm = lambda s: re.sub(r'[ 　]', '', re.sub(r'【([^】：]*)：[^】]*】', r'\1', s)).strip()
names = {norm(j): e.strip() for j, e in (l.rstrip('\n').split('\t', 1) for l in open(a.names, encoding='utf-8') if '\t' in l and not l.startswith('#')) if len(norm(j)) >= 2}
tables = {t: list(csv.reader(io.StringIO(open(os.path.join(d, f'Sangokushi-script-Type{t}.tsv'), encoding='utf-8', newline='').read(), newline=''), delimiter='\t')) for t in range(1, 5)}
render = {}                                                 # japanese name -> how the machine translation wrote it (name table rows)
for rows in tables.values():
    for r in rows[1:]:
        j = norm(r[5]) if len(r) > 6 else ''
        if j in names and r[0].startswith(a.name_file) and r[6].strip() and not re.search(r'【', r[6]): render.setdefault(j, r[6].strip())
render_ready = None
rx = re.compile('|'.join(re.escape(n) for n in sorted((n for n in names if len(n) >= 4 and n in render), key=len, reverse=True)))
exact = repl = 0
for rows in tables.values():
    for r in rows[1:]:
        if len(r) < 7 or not r[6].strip(): continue
        j = norm(r[5])
        if j in names and r[0].startswith(a.name_file):
            if r[6].strip() != names[j]: r[6] = names[j]; exact += 1
            continue
        for n in set(rx.findall(j)):
            old = render.get(n)
            if old and old != names[n] and len(old) >= 4 and re.search(rf'(?<![\w]){re.escape(old)}(?![\w])', r[6]):
                r[6] = re.sub(rf'(?<![\w]){re.escape(old)}(?![\w])', lambda _: names[n], r[6]); repl += 1
for t, rows in tables.items():
    out = io.StringIO(newline=''); csv.writer(out, delimiter='\t', lineterminator='\r\n').writerows(rows)
    open(os.path.join(d, f'Sangokushi-script-Type{t}.tsv'), 'w', encoding='utf-8', newline='').write(out.getvalue())
print(f'{len(names)} official names: {exact} name rows set, {repl} in-sentence replacements ({len(render)} names present in the game)')
