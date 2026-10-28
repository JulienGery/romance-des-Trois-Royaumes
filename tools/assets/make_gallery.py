#!/usr/bin/env python3
"""Planches-contact (PNG) + galerie HTML des textures extraites par extract_textures.py.

  make_gallery.py [--out work/assets] [--lo 0] [--hi 99999] [--per-sheet 80] [--no-sheets]
  make_gallery.py --copy FAMILLE DOSSIER     copie les PNG d'une famille (à retoucher puis placer dans translations/<lang>/textures/)

Écrit <out>/sheets/sheet_NNN.png (cellules étiquetées « entrée_tex ») et <out>/index.html
(recherche par identifiant, filtre de taille, chargement paresseux). Les doublons exacts sont omis.
"""
import argparse, json, os
from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CW, CH, COLS = 168, 132, 10

# Familles de textures contenant du texte japonais dessiné (repérées à la main sur les planches-contact).
FAMILIES = {
    'ui':       ('Atlas d\'interface (menus, boutons, bulles, titres, mentions légales…)', lambda r: 1 <= r['entry'] <= 76),
    'techniques': ('Bandeaux de noms de techniques 256×64', lambda r: (r['w'], r['h']) == (256, 64)),
    'effets':   ('Bandeaux d\'effets 128×32 (« Subit moitié de dégâts ! »…)', lambda r: 2688 <= r['entry'] <= 2703 and (r['w'], r['h']) == (128, 32)),
    'bannieres': ('Bannières 512×128 (tutoriels, annonces)', lambda r: (r['w'], r['h']) == (512, 128)),
    'plaques':  ('Plaques de noms Yo-kai/officier 128×32, 64×32 (+ lecture furigana)', lambda r: r['fmt'] == 72 and r['h'] == 32 and r['w'] in (64, 128) and r['entry'] >= 12205),
}


def family_of(r):
    for k, (_, f) in FAMILIES.items():
        if f(r): return k
    return None


def checker(w, h):
    im = Image.new('RGB', (w, h), (70, 70, 80))
    d = ImageDraw.Draw(im)
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            if (x // 8 + y // 8) & 1: d.rectangle([x, y, x + 7, y + 7], fill=(96, 96, 108))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'work/assets'))
    ap.add_argument('--lo', type=int, default=0); ap.add_argument('--hi', type=int, default=10**9)
    ap.add_argument('--per-sheet', type=int, default=80)
    ap.add_argument('--no-sheets', action='store_true')
    ap.add_argument('--copy', nargs=2, metavar=('FAMILLE', 'DOSSIER'))
    a = ap.parse_args()
    rows = [r for r in json.load(open(a.out + '/manifest.json'))
            if 'sha1' in r and 'same_as' not in r and a.lo <= r['entry'] < a.hi]
    rows.sort(key=lambda r: (r['entry'], r['tex']))
    if a.copy:
        import shutil
        os.makedirs(a.copy[1], exist_ok=True)
        sel = [r for r in rows if family_of(r) == a.copy[0]]
        for r in sel: shutil.copy(f"{a.out}/png/{r['entry']}_{r['tex']}.png", a.copy[1])
        print(len(sel), 'PNG copiés'); return
    if not a.no_sheets:
        os.makedirs(a.out + '/sheets', exist_ok=True)
        for n in range(0, len(rows), a.per_sheet):
            chunk = rows[n:n + a.per_sheet]
            nr = (len(chunk) + COLS - 1) // COLS
            sheet = Image.new('RGB', (COLS * CW, nr * CH), (30, 30, 34))
            d = ImageDraw.Draw(sheet)
            for i, r in enumerate(chunk):
                x, y = (i % COLS) * CW, (i // COLS) * CH
                im = Image.open(f"{a.out}/png/{r['entry']}_{r['tex']}.png").convert('RGBA')
                s = min((CW - 6) / im.width, (CH - 20) / im.height, 3.0)
                im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.NEAREST if s >= 1 else Image.LANCZOS)
                bg = checker(im.width, im.height); bg.paste(im, mask=im)
                sheet.paste(bg, (x + 3, y + 3))
                d.text((x + 3, y + CH - 15), f"{r['entry']}_{r['tex']} {r['w']}x{r['h']}", fill=(255, 230, 120))
            sheet.save(f"{a.out}/sheets/sheet_{a.lo:05d}_{n // a.per_sheet:03d}.png")
    def fig(r):
        return (f'<figure data-id="{r["entry"]}_{r["tex"]}" data-w="{r["w"]}"><img loading="lazy" src="png/{r["entry"]}_{r["tex"]}.png">'
                f'<figcaption>{r["entry"]}_{r["tex"]}<br>{r["w"]}×{r["h"]} f{r["fmt"]}</figcaption></figure>')
    cells = ''
    for k, (title, _) in list(FAMILIES.items()) + [(None, ('Autres textures (icônes, cartes, portraits, décors : pas de texte repéré)', None))]:
        sel = [r for r in rows if family_of(r) == k]
        cells += f'<h2>{title} — {len(sel)}</h2>' + ''.join(fig(r) for r in sel)
    open(a.out + '/index.html', 'w').write(f'''<!doctype html><meta charset=utf-8><title>Textures LINKDATA</title>
<style>body{{background:#2a2a30;color:#ddd;font:12px sans-serif;margin:8px}}figure{{display:inline-block;margin:4px;text-align:center;max-width:260px;
background:repeating-conic-gradient(#46464f 0 25%,#60606c 0 50%) 0/16px 16px}}img{{max-width:256px;image-rendering:pixelated}}
figcaption{{background:#222;color:#fd6}}h2{{color:#fff;font-size:15px;margin:18px 0 4px}}input{{margin-right:8px}}</style>
<input id=q placeholder="id (ex. 1234 ou 1234_0)" oninput=f()><input id=mw type=number placeholder="largeur min" oninput=f()>{len(rows)} textures uniques
<div id=g>{cells}</div><script>function f(){{const q=document.getElementById('q').value,m=+document.getElementById('mw').value||0;
document.querySelectorAll('figure').forEach(e=>e.style.display=(e.dataset.id.startsWith(q)&&+e.dataset.w>=m)?'':'none')}}</script>''')
    print(len(rows), 'textures dans la galerie')


if __name__ == '__main__':
    main()
