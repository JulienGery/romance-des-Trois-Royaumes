#!/usr/bin/env python3
"""Machine-translate the game's Japanese texts with DeepL into another language (default English), producing
translations/<lang>/Sangokushi-script-Type[1-4].tsv in the same layout as SangoKuro's TSVs, ready for `patch_rom.py --lang <lang>`.

    DEEPL_API_KEY=...  python3 fr_patch/translate_deepl.py --lang en [--glossary glossary_en.tsv] [--limit N] [--dry-run] [--mock]

 * source = column 6 "Original Text" (Japanese) of the French TSVs; the French translation is NOT used as a pivot.
 * game tags are protected: ruby 【base：reading】 keeps only the base, every other 【tag】 (colours, variables, sizes) becomes a numbered XML
   placeholder <x1/> that DeepL keeps in place; the result is checked tag for tag and, when DeepL lost or moved one, the text is retranslated
   segment by segment (tags re-inserted verbatim) so that the output is always tag-safe.
 * explicit line breaks after sentence punctuation stay hard breaks (<br/>), other breaks are joined: the engine re-wraps text itself.
 * unique texts only (about 20 600 / 608 000 characters); translations are cached in translations/<lang>/.cache.json so the run can be
   stopped (quota, network) and resumed. The API key comes from the environment, never from a file. `--mock` needs no key (tests the plumbing).
DeepL free plan: 500 000 characters per month (the whole game needs about 650 000: two months, or a Pro plan)."""
import argparse, csv, hashlib, io, json, os, re, sys, time, urllib.error, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); SK = os.path.join(ROOT, 'SangoKuro')
TAG = re.compile(r'【([^】]*)】')
SENT_END = '。！？!?…」』）)'
LANGS = {'en': 'EN-US', 'de': 'DE', 'es': 'ES', 'it': 'IT', 'pt': 'PT-BR', 'ru': 'RU', 'zh': 'ZH'}

def protect(jp):
    """Japanese text of a TSV cell -> (xml string for DeepL, list of tags in order). Newlines are literal `\\n` or real."""
    tags = []
    def tag(m):
        body = m.group(1)
        if '：' in body: return body.split('：', 1)[0]                  # ruby: keep the base text only
        tags.append(m.group(0)); return f'<x{len(tags)}/>'
    s = TAG.sub(tag, jp.replace('\\n', '\n'))
    out = []
    parts = s.split('\n')
    for i, part in enumerate(parts):
        out.append(part)
        if i + 1 < len(parts): out.append('<br/>' if part.rstrip().endswith(tuple(SENT_END)) or not part.strip() else '')
    return ''.join(out).replace('&', '&amp;'), tags

def restore(xml, tags):
    s = xml.replace('&amp;', '&').replace('<br/>', '\n').replace('<br />', '\n')
    for i, t in enumerate(tags, 1): s = re.sub(rf'<x{i}\s*/>', lambda _: t, s)
    return s

def tags_ok(xml, n): return sorted(re.findall(r'<x(\d+)\s*/>', xml)) == sorted(str(i) for i in range(1, n + 1))

def deepl(texts, key, target, glossary, plain=False):
    host = 'api-free.deepl.com' if key.endswith(':fx') else 'api.deepl.com'
    body = {'text': texts, 'source_lang': 'JA', 'target_lang': target, 'split_sentences': 'nonewlines', 'preserve_formatting': True}
    if not plain: body.update({'tag_handling': 'xml', 'ignore_tags': ['x'], 'non_splitting_tags': ['br']})
    if glossary: body['glossary_id'] = glossary
    req = urllib.request.Request(f'https://{host}/v2/translate', json.dumps(body).encode(), {'Authorization': f'DeepL-Auth-Key {key}', 'Content-Type': 'application/json'})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r: return [t['text'] for t in json.load(r)['translations']]
        except urllib.error.HTTPError as e:
            if e.code == 456: raise SystemExit('DeepL quota exceeded: the cache is saved, rerun after the quota resets')
            if e.code in (429, 500, 502, 503, 504): time.sleep(2 ** attempt * 2); continue
            raise SystemExit(f'DeepL error {e.code}: {e.read().decode(errors="replace")[:300]}')
        except urllib.error.URLError: time.sleep(2 ** attempt * 2)
    raise SystemExit('DeepL unreachable')

def mock(texts, plain=False):      # no network: upper-case the text between tags (tags and structure must survive)
    return [re.sub(r'(?<=>)([^<]+)|^([^<]+)', lambda m: (m.group(1) or m.group(2)).upper(), t) if not plain else t.upper() for t in texts]

def make_glossary(path, key, target):
    """tab separated `japanese<TAB>translation` lines -> a DeepL glossary id (cached by content hash)"""
    ents = [l.rstrip('\n') for l in open(path, encoding='utf-8') if '\t' in l and not l.startswith('#')]
    host = 'api-free.deepl.com' if key.endswith(':fx') else 'api.deepl.com'
    data = {'name': 'sangokushi-' + hashlib.sha1('\n'.join(ents).encode()).hexdigest()[:8], 'source_lang': 'JA', 'target_lang': target.split('-')[0], 'entries': '\n'.join(ents), 'entries_format': 'tsv'}
    req = urllib.request.Request(f'https://{host}/v2/glossaries', json.dumps(data).encode(), {'Authorization': f'DeepL-Auth-Key {key}', 'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=60))['glossary_id']

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--lang', default='en'); ap.add_argument('--glossary'); ap.add_argument('--limit', type=int)
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--mock', action='store_true'); ap.add_argument('--batch', type=int, default=40)
    a = ap.parse_args(); target = LANGS.get(a.lang, a.lang.upper())
    out_dir = os.path.join(ROOT, 'translations', a.lang); os.makedirs(out_dir, exist_ok=True)
    cache_path = os.path.join(out_dir, '.cache.json'); cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    key = os.environ.get('DEEPL_API_KEY', '')
    if not a.mock and not a.dry_run and not key: sys.exit('set DEEPL_API_KEY (or use --mock / --dry-run)')
    tables = {t: list(csv.reader(io.StringIO(open(os.path.join(SK, f'Sangokushi-script-Type{t}.tsv'), encoding='utf-8', newline='').read(), newline=''), delimiter='\t')) for t in range(1, 5)}
    todo = {}                                                   # protected xml -> tags
    for rows in tables.values():
        for r in rows[1:]:
            if len(r) > 6 and r[6].strip() and re.search(r'[぀-ヿ一-鿿]', r[5]):
                x, tags = protect(r[5])
                if x.strip() and x not in cache: todo[x] = tags
    chars = sum(len(x) for x in todo)
    print(f'{len(todo)} texts to translate ({chars} characters), {len(cache)} already cached')
    if a.dry_run: return
    glossary = make_glossary(a.glossary, key, target) if a.glossary and not a.mock else None
    items = list(todo.items())[:a.limit] if a.limit else list(todo.items())
    done = 0
    for i in range(0, len(items), a.batch):
        chunk = items[i:i + a.batch]
        res = mock([x for x, _ in chunk]) if a.mock else deepl([x for x, _ in chunk], key, target, glossary)
        bad = []
        for (x, tags), t in zip(chunk, res):
            if tags_ok(t, len(tags)): cache[x] = t
            else: bad.append((x, tags))
        for x, tags in bad:                                     # fallback: translate the pieces between tags, re-insert the tags verbatim
            pieces = re.split(r'(<x\d+/>)', x); seg = [p for p in pieces if p and not re.fullmatch(r'<x\d+/>', p)]
            tr = iter(mock(seg, True) if a.mock else deepl(seg, key, target, glossary, plain=True))
            cache[x] = ''.join(p if (not p or re.fullmatch(r'<x\d+/>', p)) else next(tr) for p in pieces)
        done += len(chunk); json.dump(cache, open(cache_path, 'w'), ensure_ascii=False)
        print(f'  {done}/{len(items)} texts ({len(bad)} needed the tag-safe fallback)', flush=True)
    # write the TSVs
    missing = 0
    for t, rows in tables.items():
        for r in rows[1:]:
            if len(r) > 6 and r[6].strip():
                if re.search(r'[぀-ヿ一-鿿]', r[5]):
                    x, tags = protect(r[5])
                    if x in cache: r[6] = restore(cache[x], tags)
                    elif x.strip(): missing += 1                # not translated yet (interrupted run): keep the French text
        out = io.StringIO(newline=''); csv.writer(out, delimiter='\t', lineterminator='\r\n').writerows(rows)
        open(os.path.join(out_dir, f'Sangokushi-script-Type{t}.tsv'), 'w', encoding='utf-8', newline='').write(out.getvalue())
    print(f'written translations/{a.lang}/ ({missing} rows still use the French text: rerun to finish)')

if __name__ == '__main__':
    main()
