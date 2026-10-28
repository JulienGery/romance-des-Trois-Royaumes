#!/usr/bin/env python3
"""Extrait les textures G1T de LINKDATA_A.BIN en PNG (RGBA) + manifest.json.

  extract_textures.py [--linkdata LINKDATA_A.BIN] [--out work/assets] [--jobs N] [--range A:B]

Sortie : <out>/png/<entrée>_<tex>.png et <out>/manifest.json
(entrée, tex, format G1T, largeur, hauteur, sha1 des pixels, octets bruts).
Les textures de même sha1 sont dédoublonnées dans l'index (champ "same_as").
"""
import argparse, hashlib, json, os, sys
from multiprocessing import Pool

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'externals', 'LINKDATA-explorer'))
from linkdata_engine import LinkDataArchive  # noqa: E402
from g1t_to_png import G1tFile  # noqa: E402
from PIL import Image  # noqa: E402

_A = None


def _work(args):
    global _A
    path, out, idx = args
    if _A is None:
        _A = LinkDataArchive(path)
    rows = []
    try:
        data = _A.read_entry_decompressed(idx)
        g = G1tFile(data)
    except Exception as ex:
        return [dict(entry=idx, error=str(ex)[:80])]
    for t in g.textures:
        r = dict(entry=idx, tex=t.index, fmt=t.format, w=t.width, h=t.height, raw=len(t.raw_data))
        try:
            w, h, rgba = g.decode_texture(t)
            Image.frombytes('RGBA', (w, h), bytes(rgba)).save(f'{out}/png/{idx}_{t.index}.png')
            r['sha1'] = hashlib.sha1(bytes(rgba)).hexdigest()[:12]
        except Exception as ex:
            r['error'] = str(ex)[:80]
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--linkdata', default=os.path.join(ROOT, 'work/rom/romfs_dir/Data/LINKDATA_A.BIN'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'work/assets'))
    ap.add_argument('--jobs', type=int, default=os.cpu_count())
    ap.add_argument('--range', default=None)
    a = ap.parse_args()
    os.makedirs(a.out + '/png', exist_ok=True)
    arc = LinkDataArchive(a.linkdata)
    idxs = [e.index for e in arc.entries if e.file_type == 'texture']
    if a.range:
        lo, hi = map(int, a.range.split(':')); idxs = [i for i in idxs if lo <= i < hi]
    with Pool(a.jobs) as p:
        res = p.map(_work, [(a.linkdata, a.out, i) for i in idxs], chunksize=8)
    rows = [r for rs in res for r in rs]
    seen = {}
    for r in rows:
        s = r.get('sha1')
        if s:
            if s in seen: r['same_as'] = seen[s]
            else: seen[s] = f"{r['entry']}_{r['tex']}"
    json.dump(rows, open(a.out + '/manifest.json', 'w'))
    print(len(idxs), 'entrées,', len(rows), 'textures,', len(seen), 'uniques,', sum('error' in r for r in rows), 'erreurs')


if __name__ == '__main__':
    main()
