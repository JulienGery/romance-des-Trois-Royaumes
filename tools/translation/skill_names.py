#!/usr/bin/env python3
"""Noms officiels des capacités (attaque, technique, âmultime, envoûtement, talent) : japonais -> anglais -> français.

Sources (API MediaWiki publique, texte sous CC BY-SA, ~quelques centaines de requêtes) :
  - yokaiwatch.fandom.com (EN) : pages des Yo-kai, {{abilities|Rôle|{{Translation|EN|JP|romaji}}…}}
  - yokaiwatch.fandom.com/fr (FR) : pages des Yo-kai, {{Attaques|NomDeLattaque=…|NomDeLaTechnique=…|NomDeLamultime=…|NomDeLenvoûtement=…}} + « Talent : … »
Les deux wikis sont appariés par Yo-kai (nom japonais) puis par rôle ; l'anglais sert de pivot (JP -> EN -> FR, vote majoritaire).
Sortie : translations/skills_official.tsv (japonais, anglais, français, rôle, nb de Yo-kai concordants). Cache des pages dans work/wiki/.
usage: skill_names.py [--refresh]"""
import collections, json, os, re, sys, time, urllib.parse, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, 'work', 'wiki'); os.makedirs(CACHE, exist_ok=True)
UA = {'User-Agent': 'yokai-sangokushi-translation/1.0'}


def api(base, params):
    for a in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(base + '?' + urllib.parse.urlencode(params), headers=UA), timeout=90) as r: return json.load(r)
        except Exception: time.sleep(2 ** a)
    raise SystemExit('wiki unreachable: ' + base)


def fetch(base, template, name):
    path = os.path.join(CACHE, name + '.json')
    if os.path.exists(path) and '--refresh' not in sys.argv: return json.load(open(path, encoding='utf-8'))
    pages, cont = {}, {}
    while True:
        d = api(base, {'action': 'query', 'generator': 'embeddedin', 'geititle': template, 'geilimit': 30, 'prop': 'revisions', 'rvprop': 'content', 'rvslots': 'main', 'format': 'json', **cont})
        for p in d.get('query', {}).get('pages', {}).values():
            if 'revisions' in p: pages[p['title']] = p['revisions'][0]['slots']['main']['*']
        print(f'  {name}: {len(pages)} pages', end='\r', flush=True)
        if 'continue' not in d: break
        cont = d['continue']
    print()
    json.dump(pages, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
    return pages


EN_ROLE = {'attack': 'attaque', 'technique': 'technique', 'soultimate': 'âmultime', 'inspirit': 'envoûtement', 'skill': 'talent'}
FR_PARAM = {'NomDeLattaque': 'attaque', 'NomDeLaTechnique': 'technique', 'NomDeLamultime': 'âmultime', 'NomDeLenvoûtement': 'envoûtement'}
clean = lambda s: re.sub(r"<[^>]+>|\[\[|\]\]|'''?", '', s).strip()


def parse_en(pages):
    out = {}
    for title, t in pages.items():
        m = re.search(r'^\|\s*japanese name\s*=\s*([^\n|<{]+)', t, re.M)
        if not m: continue
        roles = {}
        for a in re.finditer(r'\{\{abilities\|(?:top=yes\|)?(Attack|Technique|Inspirit|Soultimate|Skill)\|\{\{[Tt]ranslation\|([^|}]+)\|([^|}]+)', t):
            roles.setdefault(EN_ROLE[a[1].lower()], (clean(a[2]), a[3].strip()))     # première occurrence = premier jeu
        for k, v in roles.items(): out.setdefault(m[1].strip(), {}).setdefault(k, v)      # plusieurs pages peuvent porter le même nom japonais
    return out


def parse_fr(pages):
    out = {}
    for title, t in pages.items():
        m = re.search(r'nom_original\s*=\s*\{\{Nomjap\|([^|}]+)', t)
        if not m: continue
        roles = {}
        for k, role in FR_PARAM.items():                                        # première occurrence = premier jeu
            v = re.search(r'\|\s*' + k + r'\s*=\s*([^|}\n]+)', t)
            if v and clean(v[1]): roles[role] = clean(v[1])
        tl = re.search(r'Talent\s*:\s*([^<\n]+)', t)
        if tl: roles['talent'] = clean(tl[1])
        for k, v in roles.items(): out.setdefault(m[1].strip(), {}).setdefault(k, v)
    return out


def main():
    en_pages = fetch('https://yokaiwatch.fandom.com/api.php', 'Template:Yo-kai', 'en_yokai')
    en = parse_en(en_pages)
    fr = parse_fr(fetch('https://yokaiwatch.fandom.com/fr/api.php', 'Template:Infobox Yo-kai déf', 'fr_yokai'))
    print(len(en), 'Yo-kai EN,', len(fr), 'Yo-kai FR,', len(set(en) & set(fr)), 'communs')
    votes = collections.defaultdict(collections.Counter)      # (jp, en, role) -> Counter(fr)
    for jp, roles in en.items():
        for role, (e, j) in roles.items():
            f = fr.get(jp, {}).get(role)
            if f: votes[(j, e, role)][f] += 1
    rows = []
    for (j, e, role), c in sorted(votes.items()):
        f, n = c.most_common(1)[0]
        rows.append((j, e, f, role, n, '; '.join(f'{k}×{v}' for k, v in c.most_common()) if len(c) > 1 else ''))
    out = os.path.join(ROOT, 'translations', 'skills_official.tsv')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write('# Capacités officielles : japonais<TAB>anglais<TAB>français<TAB>rôle<TAB>Yo-kai concordants<TAB>variantes FR (wiki Yo-kai Watch EN + FR, CC BY-SA) ; généré par tools/translation/skill_names.py\n')
        for r in rows: fh.write('\t'.join(map(str, r)) + '\n')
    print(len(rows), 'capacités ->', out)
    build_glossary(en_pages, rows)


def build_glossary(en_pages, rows):
    """translations/skills_fr.tsv : compétences du jeu (script 57, entrée 6) avec FR actuel + officiel (direct, ou via l'anglais)."""
    import csv
    jp2en = {}
    for t in en_pages.values():
        for m in re.finditer(r"\{\{[Tt]ranslation\|'*([^|']+?)'*\|([^|}]+)\|", t): jp2en.setdefault(m[2].strip(), m[1].strip())
    direct = {r[0]: r for r in sorted(rows, key=lambda r: -r[4])}
    en2fr = collections.defaultdict(collections.Counter)
    for j, e, f, role, n, _ in rows: en2fr[e][f] += n
    strip = lambda x: re.sub(r'【([^：】]*)：[^】]*】', r'\1', x)
    rs = list(csv.reader(open(os.path.join(ROOT, 'translations', 'fr', 'Sangokushi-script-Type2.tsv'), encoding='utf-8', newline=''), delimiter='\t'))
    seen, lines, st = set(), [], collections.Counter()
    for r in rs[1:]:
        if r[1] != '57' or r[3] != '6': continue
        jp = strip(r[5])
        if jp in seen: continue
        seen.add(jp); en = jp2en.get(jp, ''); fr = src = ''
        if jp in direct: en, fr, src = direct[jp][1], direct[jp][2], 'wiki FR+EN'
        elif en in en2fr: fr, src = en2fr[en].most_common(1)[0][0], 'via EN'
        elif en: src = 'EN seul'
        st[src or 'inconnu'] += 1
        lines.append((r[4], jp, r[6], en, fr, src, 'identique' if fr and fr.lower() == r[6].lower() else ''))
    with open(os.path.join(ROOT, 'translations', 'skills_fr.tsv'), 'w', encoding='utf-8') as fh:
        fh.write('# Compétences du jeu (script 57, entrée 6) : ligne<TAB>japonais<TAB>français actuel<TAB>anglais officiel<TAB>français officiel<TAB>source<TAB>note ; généré par tools/translation/skill_names.py (wikis Yo-kai Watch EN+FR, CC BY-SA)\n')
        for l in lines: fh.write('\t'.join(l) + '\n')
    print(len(lines), 'compétences distinctes :', dict(st))


if __name__ == '__main__':
    main()
