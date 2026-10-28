#!/usr/bin/env python3
"""Official English glossary (Japanese -> English) for the English translation, from the Yo-kai Watch wiki (yokaiwatch.fandom.com, text CC BY-SA).

Merges, by kind:
  yokai   translations/yokai_names_en.tsv         (tools/translation/yokai_names.py)
  skill   translations/skills_official.tsv        (tools/translation/skill_names.py)
  item / place / shop / quest / char / term / food   scraped here from the wiki categories below ({{item}}, {{location}}, {{Translation|EN|JP|romaji}} ...)
  manual  translations/glossary_en.tsv            (hand-written, always wins)
Output: translations/glossary_en_full.tsv   (japanese<TAB>english<TAB>kind), cache of the wiki pages in work/wiki/glossary_cache.json.
usage: en_glossary.py [--refresh]"""
import json, os, re, sys, time, urllib.parse, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, 'work', 'wiki', 'glossary_cache.json')
API = 'https://yokaiwatch.fandom.com/api.php'
UA = {'User-Agent': 'yokai-sangokushi-translation/1.0'}
CATS = {                                                   # category -> kind
    'Items': 'item', 'Food': 'food', 'Equipment': 'item', 'Key items': 'item', 'Fusion Items': 'item', 'Fusible Items': 'item', 'Gemstones': 'item',
    'Coins': 'item', 'Books': 'item', 'Drinks': 'food', 'Bread': 'food', 'Candy': 'food', 'Fruits': 'food', 'Items introduced in Yo-kai Sangokushi': 'item',
    'Locations': 'place', 'Locations in Yo-kai Watch': 'place', 'Locations in Yo-kai Watch 2': 'place', 'Locations in Yo-kai Watch 3': 'place',
    'Springdale Locations': 'place', 'Cities': 'place', 'Districts of Springdale': 'place', 'Shops': 'shop', 'Food Places': 'shop', 'Buildings': 'place',
    'Terminology': 'term', 'Game mechanics': 'term', 'Combat mechanics': 'term', 'Mechanics Introduced in Yo-kai Watch': 'term', 'Mechanics Introduced in Yo-kai Watch 2': 'term',
    'Mechanics Introduced in Yo-kai Watch 3': 'term', 'Attributes': 'term', 'Attack Type': 'term', 'Defense Type': 'term', 'Inspirit Type': 'term', 'Factions': 'term',
    'Characters': 'char', 'Humans': 'char', 'Seven Jewel Generals': 'char', 'Kingdom of Shu': 'char', 'Kingdom of Wei': 'char', 'Kingdom of Wu': 'char', 'Other Kingdoms': 'char',
    'Quests': 'quest', 'Yo-kai Watch Quests': 'quest', 'Yo-kai Watch 2 Quests': 'quest', 'Yo-kai Watch Requests': 'quest', 'Yo-kai Watch 2 Requests': 'quest',
}
def api(**p):
    p['format'] = 'json'
    for a in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(API + '?' + urllib.parse.urlencode(p), headers=UA), timeout=90) as r: return json.load(r)
        except Exception: time.sleep(2 ** a)
    raise SystemExit('wiki unreachable')

def clean(s):
    s = re.sub(r"\{\{[^}]*\}\}|<[^>]+>|\[\[(?:[^|\]]*\|)?([^\]]*)\]\]|'''?", lambda m: m.group(1) or '', s)
    return s.strip(' \t‎')
def pairs_of(text):
    out = []
    for m in re.finditer(r'\{\{\s*[Tt]ranslation\s*\|\s*(?:\'\'\')?([^|{}]+?)(?:\'\'\')?\s*\|\s*([^|{}]+?)\s*(?:\||\}\})', text):
        out.append((m.group(2), m.group(1)))
    en = re.search(r'^\|\s*(?:item name|location name|quest title|name)\s*=\s*([^\n|]+)', text, re.M)
    jp = re.search(r'^\|\s*(?:japanese name|location name jp|jp name|japanese)\s*=\s*([^\n|<]+)', text, re.M)
    if en and jp: out.append((jp.group(1), en.group(1)))
    return [(clean(j), clean(e)) for j, e in out if clean(j) and clean(e) and re.search(r'[぀-ヿ一-鿿]', j)]

def scrape():
    cache = {} if '--refresh' in sys.argv or not os.path.exists(CACHE) else json.load(open(CACHE, encoding='utf-8'))
    for cat, kind in CATS.items():
        if cat in cache: continue
        got = []; cont = {}
        while True:
            d = api(action='query', generator='categorymembers', gcmtitle='Category:' + cat, gcmlimit=40, gcmtype='page', prop='revisions', rvprop='content', rvslots='main', **cont)
            for p in d.get('query', {}).get('pages', {}).values():
                t = p.get('revisions', [{}])[0].get('slots', {}).get('main', {}).get('*', '')
                got += pairs_of(t[:6000])
            if 'continue' not in d: break
            cont = d['continue']
        cache[cat] = got
        print(f'{cat}: {len(got)} pairs', flush=True)
        json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
    return cache

def tsv(path, jp_col, en_col, kind=None, skip=0):
    for l in open(path, encoding='utf-8'):
        if l.startswith('#') or not l.strip(): continue
        c = l.rstrip('\r\n').split('\t')
        if len(c) > max(jp_col, en_col) and c[jp_col] and c[en_col]: yield c[jp_col].strip(), c[en_col].strip(), (kind or (c[3] if len(c) > 3 else 'skill'))

if __name__ == '__main__':
    cache = scrape(); g = {}
    T = os.path.join(ROOT, 'translations')
    for jp, en, k in tsv(os.path.join(T, 'yokai_names_en.tsv'), 0, 1, 'yokai'): g[jp] = (en, k)
    for cat, kind in CATS.items():
        for jp, en in cache.get(cat, []): g.setdefault(jp, (en, kind))
    for jp, en, k in tsv(os.path.join(T, 'skills_official.tsv'), 0, 1): g[jp] = (en, 'skill:' + k)
    for jp, en, k in tsv(os.path.join(T, 'glossary_en.tsv'), 0, 1, 'manual'): g[jp] = (en, k)
    for jp in list(g):                                                 # ruby / HTML markup in some names -> plain base text
        if '<' in jp:
            plain = re.sub(r'<rt>.*?</rt>|<[^>]+>', '', jp)
            g.setdefault(plain, g[jp]); del g[jp]
    out = os.path.join(T, 'glossary_en_full.tsv')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# japanese<TAB>english<TAB>kind ; yokai/skill/item/place/shop/quest/char/term/food from the Yo-kai Watch wiki (CC BY-SA), manual = hand-written\n')
        for jp, (en, k) in sorted(g.items()): f.write(f'{jp}\t{en}\t{k}\n')
    print(len(g), 'entries ->', out)
