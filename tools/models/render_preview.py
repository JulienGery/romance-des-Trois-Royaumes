#!/usr/bin/env python3
"""Aperçu logiciel avant/après d'un modèle (projection orthographique, éclairage par normales de sommets) → PNG.

  render_preview.py ENTREE [--level 1] [--model N] [--out fichier.png] [--src LINKDATA_A.BIN]
"""
import argparse, os, sys
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path[:0] = [HERE, os.path.join(ROOT, 'externals', 'LINKDATA-explorer')]
from improve_models import *  # noqa


def tri_soup(m1g):
    r = find_gm1g(m1g); head, secs, tail = parse_gm1g(m1g[r[0]:r[0] + r[1]])
    vbs, ibs = parse_vbufs(get(secs, SEC_VERT)[0]), parse_ibufs(get(secs, SEC_IDX)[0])
    subs, sets = parse_subs(get(secs, SEC_SUB)[0]), parse_attrs(get(secs, SEC_ATTR)[0])
    P, N = [], []
    for s in subs:
        t = strip_to_tris(ibs[s[7]][s[12]:s[12] + s[13]])
        b = Buf(vbs[s[7]][0], vbs[s[7]][2], sets[s[7]])
        P.append(b.f32(SEM_POS, 3)[t]); N.append(b.f32(SEM_NRM, 3)[t])
    return np.concatenate(P), np.concatenate(N)


def render(P, N, box, size=700, edges=False):
    (x0, x1), (y0, y1) = box
    sc = size / max(x1 - x0, y1 - y0) * 0.95
    img = Image.new('RGB', (size, size), (235, 235, 240)); dr = ImageDraw.Draw(img)
    order = np.argsort(-P[:, :, 2].mean(1))
    L = np.array([0.3, 0.5, 0.8]); L /= np.linalg.norm(L)
    for i in order:
        n = N[i].mean(0); n /= np.linalg.norm(n) + 1e-9
        k = 0.25 + 0.75 * abs(float(n @ L)); c = int(40 + 200 * k)
        pts = [((p[0] - x0) * sc + 10, size - ((p[1] - y0) * sc + 10)) for p in P[i]]
        dr.polygon(pts, fill=(c, c, int(c * 0.95)), outline=(60, 60, 70) if edges else None)
    return img


if __name__ == '__main__':
    from linkdata_engine import LinkDataArchive
    ap = argparse.ArgumentParser(); ap.add_argument('entry', type=int); ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--model', type=int); ap.add_argument('--crease', type=float, default=CREASE_DEG); ap.add_argument('--out', default='preview.png'); ap.add_argument('--edges', action='store_true'); ap.add_argument('--crop', help='x0,y0,x1,y1 dans le repère du modèle')
    ap.add_argument('--src', default=os.path.join(ROOT, 'work/rom/romfs_dir/Data/LINKDATA_A.BIN'))
    a = ap.parse_args()
    d = LinkDataArchive(a.src).read_entry_decompressed(a.entry)
    files = [f for f in split_models(d) if f[2] == b'_M1G']
    if a.model is None:      # le plus gros
        a.model = max(range(len(files)), key=lambda i: files[i][1])
    o, sz, _ = files[a.model]; blob = d[o:o + sz]
    new = process_m1g(blob[:struct.unpack_from('<I', blob, 8)[0]], levels=a.level, crease=a.crease)
    P0, N0 = tri_soup(blob); P1, N1 = tri_soup(new)
    lo, hi = P0.reshape(-1, 3).min(0), P0.reshape(-1, 3).max(0)
    # zoom : tête / partie haute si le modèle est très large (pose en T)
    box = ((lo[0], hi[0]), (lo[1], hi[1]))
    if a.crop: x0, y0, x1, y1 = map(float, a.crop.split(',')); box = ((x0, x1), (y0, y1))
    A = render(P0, N0, box, edges=a.edges); B = render(P1, N1, box, edges=a.edges)
    out = Image.new('RGB', (A.width * 2 + 10, A.height), (255, 255, 255)); out.paste(A, (0, 0)); out.paste(B, (A.width + 10, 0)); out.save(a.out)
    print(f'{len(P0)} -> {len(P1)} triangles ; {a.out}')
