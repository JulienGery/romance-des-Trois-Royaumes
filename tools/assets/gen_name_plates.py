#!/usr/bin/env python3
"""Génère les plaques de noms (128x32 / 64x32 : Yo-kai + officier) en français.

Libellé = traduction du jeu (script 57, entrée 0, colonne « Translated Text »), déjà en noms officiels des Yo-kai.
Lien plaque <-> ligne : entrée LINKDATA = 12205 + numéro de ligne.
Les plaques de 32/64 px de large sont élargies à 128 px (le tableau de dimensions du jeu est patché au build : patch_plate_table.py).

  gen_name_plates.py --out DOSSIER [--preview apercu.png] [--lines 0,75]
"""
import argparse, csv, os, re
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FONT = '/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf'      # étroite : tient dans la largeur de la plaque japonaise
BASE = 12205
PILL = (31, 31, 31, 204)         # fond de la plaque d'origine
Y0, Y1 = 5, 19                   # lignes de la pilule d'origine


def render(text, W, H=32, S=8, maxw=None):
    maxw = min(W, maxw or W)
    size = 13 * S
    while True:
        f = ImageFont.truetype(FONT, size); b = f.getbbox(text, stroke_width=S)
        if b[2] - b[0] <= (maxw - 15) * S or size <= 6 * S: break
        size -= S // 2
    tw = (b[2] - b[0]) / S
    pw = min(maxw, int(tw + 15))
    render.last_size = size / S
    out = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0)); d = ImageDraw.Draw(out)
    d.rounded_rectangle([0, Y0 * S, pw * S - 1, (Y1 + 1) * S - 1], radius=4 * S, fill=PILL)
    cy = (Y0 + Y1 + 1) / 2 * S
    d.text((7 * S - b[0], cy - (b[1] + b[3]) / 2), text, font=f, fill=(255, 255, 255, 255), stroke_width=S * 3 // 4, stroke_fill=(0, 0, 0, 255))
    return out.resize((W, H), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True); ap.add_argument('--lines'); ap.add_argument('--preview')
    ap.add_argument('--png', default=os.path.join(ROOT, 'work', 'assets', 'png'))
    a = ap.parse_args()
    rs = list(csv.reader(open(os.path.join(ROOT, 'translations', 'fr', 'Sangokushi-script-Type2.tsv'), encoding='utf-8', newline=''), delimiter='\t'))
    fr = {int(r[4]): (r[5], r[6] or r[5]) for r in rs[1:] if r[1] == '57' and r[3] == '0'}
    lines = [int(x) for x in a.lines.split(',')] if a.lines else sorted(fr)
    os.makedirs(a.out, exist_ok=True); done = []
    for i in lines:
        ref = os.path.join(a.png, f'{BASE + i}_0.png')
        if not os.path.exists(ref): continue
        im = Image.open(ref)
        if im.size[1] != 32 or im.size[0] not in (32, 64, 128): continue
        text = re.sub(r'【([^：】]*)：[^】]*】', r'\1', fr[i][1])
        import numpy as np
        ys, xs = np.where(np.asarray(im.convert('RGBA'))[:, :, 3] > 150); ow = int(xs.max()) + 1                       # (largeur japonaise, plus utilisée : le tableau du jeu est patché, voir patch_plate_table.py)
        render(text, 128).save(                                           # les plaques étroites (64/32 px) passent à 128 px : tableau du jeu patché (patch_plate_table.py)
            os.path.join(a.out, f'{BASE + i}_0.png')); done.append((BASE + i, text))
    print(len(done), 'plaques ->', a.out)
    if a.preview:
        sel = done[::max(1, len(done) // 24)][:24]
        s = Image.new('RGB', (900, len(sel) * 36 + 4), (70, 70, 80)); d = ImageDraw.Draw(s)
        for k, (e, t) in enumerate(sel):
            for j, p in enumerate((os.path.join(a.png, f'{e}_0.png'), os.path.join(a.out, f'{e}_0.png'))):
                im = Image.open(p).convert('RGBA'); bg = Image.new('RGBA', im.size, (70, 70, 80, 255)); bg.alpha_composite(im)
                s.paste(bg.convert('RGB').resize((im.width * 2, im.height * 2), Image.NEAREST).crop((0, 0, im.width * 2, 64)).resize((im.width * 2, 32)) if False else bg.convert('RGB'), (4 + j * 140, k * 36 + 2))
            d.text((290, k * 36 + 12), f'{e}  {t}', fill=(255, 230, 120))
        s.save(a.preview)


if __name__ == '__main__':
    main()
