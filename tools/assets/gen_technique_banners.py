#!/usr/bin/env python3
"""Génère les bandeaux de noms de techniques (256x64) en français.

Libellé = nom officiel du glossaire (translations/skills_fr.tsv, colonne 5) s'il existe, sinon le français du jeu (colonne 3).
Lien bandeau <-> compétence : entrée LINKDATA = 203 + numéro de ligne dans la table des compétences (script 57, entrée 6).

  gen_technique_banners.py --out DOSSIER [--lines 0,2,3 | --all] [--source officiel|jeu] [--preview apercu.png]

--out reçoit <entrée>_0.png (même nom que work/assets/png) : à copier dans translations/<langue>/textures/.
--preview : planche avant/après avec la source du libellé (O = officiel, J = traduction du jeu).
"""
import argparse, csv, os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FONT = '/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf'
BASE = 203
SHADOW = (170, 85, 170)          # ombre violette des bandeaux d'origine


def render(text, W=256, H=64, S=4):
    k = H / 64                                       # tout est dimensionné pour 64 px de haut puis mis à l'échelle (bandeaux 128x32 : k = 0.5)
    out = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    size = int(44 * k * S)
    while True:
        f = ImageFont.truetype(FONT, size); b = f.getbbox(text, stroke_width=int(4 * k * S))
        if b[2] - b[0] <= (W - 14 * k) * S or size <= 12 * k * S: break
        size -= max(1, S // 2)
    x = (W * S - (b[2] - b[0])) // 2 - b[0]; y = (H * S - (b[3] - b[1])) // 2 - b[1] + int(2 * k * S)

    def layer(dx, dy, fill, stroke, sw):
        l = Image.new('RGBA', out.size, (0, 0, 0, 0)); ImageDraw.Draw(l).text((x + dx, y + dy), text, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke); return l
    o = int(2 * k * S)
    out = Image.alpha_composite(out, layer(o, o, SHADOW + (255,), SHADOW + (255,), int(4 * k * S)))
    out = Image.alpha_composite(out, layer(0, 0, (255, 255, 255, 255), (0, 0, 0, 255), int(3 * k * S)))
    out = out.transform(out.size, Image.AFFINE, (1, 0.12, -0.12 * H * S / 2, 0, 1, 0), Image.BICUBIC)   # inclinaison « italique »
    return out.resize((W, H), Image.LANCZOS)


def load_skills():
    sk = {}
    ln = {}
    rs = list(csv.reader(open(os.path.join(ROOT, 'translations', 'fr', 'Sangokushi-script-Type2.tsv'), encoding='utf-8', newline=''), delimiter='\t'))
    for r in rs[1:]:
        if r[1] == '57' and r[3] == '6': ln[int(r[4])] = r[5]
    import re
    gl = {}
    for l in open(os.path.join(ROOT, 'translations', 'skills_fr.tsv'), encoding='utf-8'):
        if l.startswith('#'): continue
        c = l.rstrip('\n').split('\t'); gl[c[1]] = c
    for i, raw in ln.items():
        jp = re.sub(r'【([^：】]*)：[^】]*】', r'\1', raw); c = gl.get(jp)
        if c: sk[i] = (jp, c[2], c[4] if c[5] == 'wiki FR+EN' else '', c[3])
    return sk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True); ap.add_argument('--lines'); ap.add_argument('--all', action='store_true')
    ap.add_argument('--source', default='officiel', choices=['officiel', 'jeu']); ap.add_argument('--preview')
    ap.add_argument('--png', default=os.path.join(ROOT, 'work', 'assets', 'png'))
    a = ap.parse_args()
    sk = load_skills()
    lines = sorted(sk) if a.all else [int(x) for x in a.lines.split(',')]
    os.makedirs(a.out, exist_ok=True); done = []
    for i in lines:
        jp, game, off, en = sk[i]
        ref = os.path.join(a.png, f'{BASE + i}_0.png')
        if not os.path.exists(ref) or Image.open(ref).size != (256, 64): continue
        text, tag = (off, 'O') if (off and a.source == 'officiel') else (game, 'J')
        render(text).save(os.path.join(a.out, f'{BASE + i}_0.png')); done.append((BASE + i, jp, text, tag))
    print(len(done), 'bandeaux ->', a.out)
    if a.preview:
        sheet = Image.new('RGB', (1100, len(done) * 70 + 6), (70, 70, 80))
        d = ImageDraw.Draw(sheet)
        for k, (e, jp, text, tag) in enumerate(done):
            for j, p in enumerate((os.path.join(a.png, f'{e}_0.png'), os.path.join(a.out, f'{e}_0.png'))):
                im = Image.open(p).convert('RGBA'); bg = Image.new('RGBA', im.size, (70, 70, 80, 255)); bg.alpha_composite(im)
                sheet.paste(bg.convert('RGB'), (6 + j * 300, k * 70 + 4))
            d.text((620, k * 70 + 14), f'{e}  [{tag}] {"officiel" if tag == "O" else "traduction du jeu"}', fill=(255, 230, 120))
            d.text((620, k * 70 + 34), text, fill=(255, 255, 255))
        sheet.save(a.preview)
    return done


if __name__ == '__main__':
    main()
