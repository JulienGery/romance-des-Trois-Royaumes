#!/usr/bin/env python3
"""Official English names of the Yo-kai: scrapes the Yo-kai Watch wiki (yokaiwatch.fandom.com, text under CC BY-SA) infoboxes
({{yo-kai | name = ... | japanese name = ...}}) into translations/yokai_names_en.tsv (japanese<TAB>english).
usage: yokai_names.py [out.tsv]      (network access to the wiki's public MediaWiki API; a few dozen requests)"""
import json, os, re, sys, time, urllib.parse, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'translations', 'yokai_names_en.tsv')
API = 'https://yokaiwatch.fandom.com/api.php'
def get(params):
    for a in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(API + '?' + urllib.parse.urlencode(params), headers={'User-Agent': 'yokai-sangokushi-translation/1.0'}), timeout=90) as r: return json.load(r)
        except Exception: time.sleep(2 ** a)
    raise SystemExit('wiki unreachable')
names = {}; cont = {}; n = 0
while True:
    d = get({'action': 'query', 'generator': 'embeddedin', 'geititle': 'Template:Yo-kai', 'geilimit': 30, 'prop': 'revisions', 'rvprop': 'content', 'rvslots': 'main', 'format': 'json', **cont})
    for p in d.get('query', {}).get('pages', {}).values():
        t = p['revisions'][0]['slots']['main']['*']; n += 1
        m_en = re.search(r'^\|\s*name\s*=\s*([^\n|]+)', t, re.M); m_jp = re.search(r'^\|\s*japanese name\s*=\s*([^\n|<]+)', t, re.M)
        if m_en and m_jp:
            en = re.sub(r"\{\{[^}]*\}\}|<[^>]+>|\[\[|\]\]|''", '', m_en.group(1)).strip(); jp = m_jp.group(1).strip()
            if en and jp and jp not in names: names[jp] = en
    if 'continue' not in d: break
    cont = d['continue']
    print(f'{n} pages, {len(names)} names', end='\r', flush=True)
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, 'w', encoding='utf-8').write('# Japanese name <TAB> official English name (Yo-kai Watch wiki, CC BY-SA)\n' + ''.join(f'{j}\t{e}\n' for j, e in sorted(names.items())))
print(f'\n{n} pages, {len(names)} names -> {out}')
