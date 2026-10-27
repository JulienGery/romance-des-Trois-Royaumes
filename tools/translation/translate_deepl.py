#!/usr/bin/env python3
"""Machine-translate the game's Japanese texts with DeepL into another language (default English), producing
translations/<lang>/Sangokushi-script-Type[1-4].tsv in the same layout as SangoKuro's TSVs, ready for `patch_rom.py --lang <lang>`.

    DEEPL_API_KEY=...  python3 tools/translation/translate_deepl.py --lang en [--glossary glossary_en.tsv] [--limit N] [--dry-run] [--mock]

 * source = column 6 "Original Text" (Japanese) of the French TSVs (default); `--source fr` translates the French column instead (output in translations/<lang>-from-fr/).
 * game tags are protected: ruby 【base：reading】 keeps only the base, every other 【tag】 (colours, variables, sizes) becomes a numbered XML
   placeholder <x1/> that DeepL keeps in place; the result is checked tag for tag and, when DeepL lost or moved one, the text is retranslated
   segment by segment (tags re-inserted verbatim) so that the output is always tag-safe.
 * explicit line breaks after sentence punctuation stay hard breaks (<br/>), other breaks are joined: the engine re-wraps text itself.
 * unique texts only (about 20 600 / 608 000 characters); translations are cached in translations/<lang>/.cache.json so the run can be
   stopped (quota, network) and resumed. The API key comes from the environment, never from a file. `--mock` needs no key (tests the plumbing).
DeepL free plan: 500 000 characters per month (the whole game needs about 650 000: two months, or a Pro plan)."""
import argparse, csv, hashlib, io, json, os, re, sys, time, urllib.error, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); SK = os.path.join(ROOT, 'translations', 'fr')
TAG = re.compile(r'【([^】]*)】')
SENT_END = '。！？!?…」』）).:;»'
LANGS = {'en': 'EN-US', 'de': 'DE', 'es': 'ES', 'it': 'IT', 'pt': 'PT-BR', 'ru': 'RU', 'zh': 'ZH'}

def protect(jp):
    """Japanese text of a TSV cell -> (xml string for DeepL, list of tags in order). Newlines are literal `\\n` or real."""
    tags = []
    def tag(m):
        body = m.group(1)
        if '：' in body: return body.split('：', 1)[0]                  # ruby: keep the base text only
        tags.append(m.group(0)); return f'\ue000{len(tags)}\ue001'
    s = TAG.sub(tag, jp.replace('\\n', '\n'))
    out = []
    parts = s.split('\n')
    for i, part in enumerate(parts):
        out.append(part)
        if i + 1 < len(parts): out.append('\ue002' if part.rstrip().endswith(tuple(SENT_END)) or not part.strip() else '')
    x = ''.join(out).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')      # the text itself must be well-formed XML
    x = re.sub('\ue000(\\d+)\ue001', r'<x\1/>', x).replace('\ue002', '<br/>')
    return x, tags

_ATLAS = None
def tidy(s):
    """typography the engine's wrapper expects: no space around a line break, no double space, and letters the atlas lacks (macrons: ū ā Ō...) folded to ASCII"""
    global _ATLAS
    if _ATLAS is None:
        try: _ATLAS = {g['ch'] for g in json.load(open(os.path.join(ROOT, 'data', 'atlas', 'glyphs_sml.json')))['glyphs']}
        except OSError: _ATLAS = set()
    import unicodedata
    s = ''.join(c if ord(c) < 128 or c in _ATLAS or '\u3000' <= c else (unicodedata.normalize('NFKD', c)[0] if ord(unicodedata.normalize('NFKD', c)[0]) < 128 else c) for c in s)
    s = re.sub(r' *\n *', '\n', s)
    return re.sub(r'(?<=\S)  +(?=\S)', ' ', s).strip(' ')

def restore(xml, tags, src=None):
    """DeepL output -> game text. Placeholders are re-sequenced in SOURCE order (a swapped open/close colour pair would invert the colours),
    and tags that began or ended the source text are put back at the very start / end (DeepL tends to move them into the sentence)."""
    s = xml.replace('<br/>', '\n').replace('<br />', '\n')
    n = len(tags); lead = trail = 0
    if src is not None:
        lead = len(re.match(r'(?:<x\d+/>)*', src).group(0)) // 0 if False else len(re.findall(r'<x\d+/>', re.match(r'(?:<x\d+/>)*', src).group(0)))
        trail = len(re.findall(r'<x\d+/>', re.search(r'(?:<x\d+/>)*$', src).group(0)))
        if lead + trail > n: trail = n - lead
    ph = re.compile(r'<x\d+\s*/>')
    inner_tags = tags[lead:n - trail]; it = iter(inner_tags)
    seen = [0]
    def sub(m):
        seen[0] += 1
        # the placeholders of the leading/trailing groups are dropped; the others receive the interior tags in source order
        i = int(re.search(r'\d+', m.group(0)).group(0))
        if i <= lead or i > n - trail: return ''
        return next(it, '')
    body = ph.sub(sub, s)
    s = ''.join(tags[:lead]) + body + ''.join(tags[n - trail:] if trail else [])
    return tidy(s.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&'))

def tags_ok(xml, n): return sorted(re.findall(r'<x(\d+)\s*/>', xml)) == sorted(str(i) for i in range(1, n + 1))

def deepl(texts, key, target, glossary, plain=False, source='JA'):
    host = 'api-free.deepl.com' if key.endswith(':fx') else 'api.deepl.com'
    body = {'text': texts, 'source_lang': source, 'target_lang': target, 'split_sentences': 'nonewlines', 'preserve_formatting': True}
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

def make_glossary(path, key, target, source='JA'):
    """tab separated `japanese<TAB>translation` lines -> a DeepL glossary id (cached by content hash)"""
    ents = [l.rstrip('\n') for l in open(path, encoding='utf-8') if '\t' in l and not l.startswith('#')]
    host = 'api-free.deepl.com' if key.endswith(':fx') else 'api.deepl.com'
    data = {'name': 'sangokushi-' + hashlib.sha1(('\n'.join(ents) + source).encode()).hexdigest()[:8], 'source_lang': source, 'target_lang': target.split('-')[0], 'entries': '\n'.join(ents), 'entries_format': 'tsv'}
    hdr = {'Authorization': f'DeepL-Auth-Key {key}', 'Content-Type': 'application/json'}
    for g in json.load(urllib.request.urlopen(urllib.request.Request(f'https://{host}/v2/glossaries', headers=hdr), timeout=60)).get('glossaries', []):
        if g['name'] == data['name']: return g['glossary_id']                      # same content: reuse (the free plan allows a single glossary)
        urllib.request.urlopen(urllib.request.Request(f"https://{host}/v2/glossaries/{g['glossary_id']}", headers=hdr, method='DELETE'), timeout=60)   # outdated glossary of ours
    req = urllib.request.Request(f'https://{host}/v2/glossaries', json.dumps(data).encode(), hdr)
    return json.load(urllib.request.urlopen(req, timeout=60))['glossary_id']

def translatable(text):
    """does the cell hold real text? (Japanese kana/kanji for --source ja, Latin letters for --source fr; skips '―', numbers, code rows)"""
    return bool(re.search(r'[A-Za-zÀ-ÿŒœ]{2}' if SOURCE_FR else r'[\u3040-\u30ff\u4e00-\u9fff]', TAG.sub('', text)))

SOURCE_FR = False

def main():
    global SOURCE_FR
    ap = argparse.ArgumentParser(); ap.add_argument('--lang', default='en'); ap.add_argument('--glossary'); ap.add_argument('--limit', type=int)
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--mock', action='store_true'); ap.add_argument('--batch', type=int, default=40); ap.add_argument('--source', choices=('ja', 'fr'), default='ja', help='ja = Japanese original (default, best quality) ; fr = the French translation (cheaper to proofread, pivot errors)')
    ap.add_argument('--write-only', action='store_true', help='do not call DeepL: write the TSVs from the cache (rows not translated yet keep the French text)')
    ap.add_argument('--usage', action='store_true', help='print the DeepL character usage of the account and exit')
    a = ap.parse_args(); SOURCE_FR = a.source == 'fr'; target = LANGS.get(a.lang, a.lang.upper()); src_code = 'FR' if a.source == 'fr' else 'JA'; col = 6 if a.source == 'fr' else 5
    if a.usage:
        k = os.environ['DEEPL_API_KEY']; h = 'api-free.deepl.com' if k.endswith(':fx') else 'api.deepl.com'
        print(json.load(urllib.request.urlopen(urllib.request.Request(f'https://{h}/v2/usage', headers={'Authorization': f'DeepL-Auth-Key {k}'}), timeout=60))); return
    out_dir = os.path.join(ROOT, 'translations', a.lang + ('-from-fr' if a.source == 'fr' else '')); os.makedirs(out_dir, exist_ok=True)
    cache_path = os.path.join(out_dir, '.cache.json'); cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    key = os.environ.get('DEEPL_API_KEY', '')
    if not a.mock and not a.dry_run and not a.write_only and not key: sys.exit('set DEEPL_API_KEY (or use --mock / --dry-run)')
    tables = {t: list(csv.reader(io.StringIO(open(os.path.join(SK, f'Sangokushi-script-Type{t}.tsv'), encoding='utf-8', newline='').read(), newline=''), delimiter='\t')) for t in range(1, 5)}
    todo = {}                                                   # protected xml -> tags
    for rows in tables.values():
        for r in rows[1:]:
            if len(r) > 6 and r[6].strip() and translatable(r[col]):
                x, tags = protect(r[col])
                if x.strip() and x not in cache: todo[x] = tags
    chars = sum(len(x) for x in todo)
    print(f'{len(todo)} texts to translate ({chars} characters), {len(cache)} already cached')
    if a.dry_run: return
    glossary = make_glossary(a.glossary, key, target, src_code) if a.glossary and not a.mock and not a.write_only else None
    items = [] if a.write_only else (list(todo.items())[:a.limit] if a.limit else list(todo.items()))
    done = 0
    for i in range(0, len(items), a.batch):
        chunk = items[i:i + a.batch]
        res = mock([x for x, _ in chunk]) if a.mock else deepl([x for x, _ in chunk], key, target, glossary, source=src_code)
        bad = []
        for (x, tags), t in zip(chunk, res):
            if tags_ok(t, len(tags)): cache[x] = t
            else: bad.append((x, tags))
        for x, tags in bad:                                     # fallback: translate the pieces between tags, re-insert the tags verbatim
            pieces = re.split(r'(<x\d+/>)', x); seg = [p for p in pieces if p and not re.fullmatch(r'<x\d+/>', p)]
            tr = iter(mock(seg, True) if a.mock else deepl(seg, key, target, glossary, plain=True, source=src_code))
            cache[x] = ''.join(p if (not p or re.fullmatch(r'<x\d+/>', p)) else next(tr) for p in pieces)
        done += len(chunk); json.dump(cache, open(cache_path, 'w'), ensure_ascii=False)
        print(f'  {done}/{len(items)} texts ({len(bad)} needed the tag-safe fallback)', flush=True)
    # write the TSVs
    missing = 0
    for t, rows in tables.items():
        for r in rows[1:]:
            if len(r) > 6 and r[6].strip():
                if translatable(r[col]):
                    x, tags = protect(r[col])
                    if x in cache:
                        r[6] = restore(cache[x], tags, x)
                        pre = re.match(r'<[0-9a-fA-F]{16}>', r[col])             # Type 3 rows start with a 16-digit hex block the generator reads back
                        if pre: r[6] = pre.group(0) + re.sub(r'^<[^>]*>', '', r[6]).lstrip()
                    elif x.strip(): missing += 1                # not translated yet (interrupted run): keep the French text
        out = io.StringIO(newline=''); csv.writer(out, delimiter='\t', lineterminator='\r\n').writerows(rows)
        open(os.path.join(out_dir, f'Sangokushi-script-Type{t}.tsv'), 'w', encoding='utf-8', newline='').write(out.getvalue())
    print(f'written {os.path.relpath(out_dir, ROOT)}/ ({missing} rows still use the French text: rerun to finish)')

if __name__ == '__main__':
    main()
