#!/usr/bin/env python3
"""Police FR/EN en haute résolution pour Azahar : redessine les pages d'atlas (A4 256x256) à partir d'une police vectorielle
au lieu d'agrandir le bitmap.

  build_hires_font.py [--font /System/Library/Fonts/Helvetica.ttc] [--scale 4] [--atlas data/atlas] [--out work/hires_pack]

Chaque glyphe est dessiné dans la boîte d'encre exacte du glyphe d'origine (ox, oy, ink_w, ink_h de glyphs_<nom>.json) : même mise en page
et mêmes avances que le jeu, seule la netteté change. Le fichier est nommé d'après le hash CityHash64 des octets A4 de la page
(= `use_new_hash` d'Azahar) et remplace donc l'agrandissement Upscayl de la même texture. Les glyphes absents de la police gardent
le bitmap d'origine, agrandi.
"""
import argparse, json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from g1t_tools import a4_encode  # noqa: E402
import cityhash  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageFont  # noqa: E402

TITLE_ID = '000400000018B000'
BIG = 256                                   # corps de rendu avant réduction dans la boîte d'encre


def load_font(path, size):
    for i in range(16):
        try:
            f = ImageFont.truetype(path, size, index=i)
        except OSError:
            break
        if f.getname()[1] == 'Regular':
            return f
    return ImageFont.truetype(path, size)


def glyph_bitmap(font, notdef, ch):
    """(bitmap, haut de l'encre par rapport à la ligne de base) ; None si le glyphe est absent de la police."""
    m = font.getmask(ch)
    if m.size == notdef.size and bytes(m) == bytes(notdef) or not m.getbbox():
        return None
    l, t, r, b = font.getbbox(ch, anchor='ls')
    return Image.frombytes('L', m.size, bytes(m)).crop(Image.frombytes('L', m.size, bytes(m)).getbbox()), t


def render_page(name, atlas, font_path, scale):
    """Échelle uniforme (hauteur de capitale = celle du 'H' d'origine), ligne de base et centre de chaque glyphe pris sur l'original :
    les traits gardent leur épaisseur naturelle au lieu d'être étirés dans la boîte d'encre."""
    meta = json.load(open(os.path.join(atlas, f'glyphs_{name}.json')))
    alpha = open(os.path.join(atlas, f'page_{name}.alpha'), 'rb').read()
    P, C, CH, cols = meta['page'], meta['cell_w'], meta['cell_h'], meta['cols']
    font = load_font(font_path, BIG)
    notdef = font.getmask('\uFFFF')
    orig = Image.frombytes('L', (P, P), alpha)
    H = next(g for g in meta['glyphs'] if g['ch'] == 'H')
    k = H['ink_h'] / -font.getbbox('H', anchor='ls')[1] * scale          # pixels de page finale par pixel de rendu
    base = H['oy'] + H['ink_h']                                          # ligne de base dans la cellule d'origine
    out = Image.new('L', (P * scale, P * scale), 0)
    kept = 0
    for g in meta['glyphs']:
        w, h, ox, oy = g['ink_w'], g['ink_h'], g['ox'], g['oy']
        if not (w and h):
            continue
        cx, cy = (g['index'] % cols) * C, (g['index'] // cols) * CH
        x0, y0 = cx + ox - g['bearing_x'], cy + oy
        r = glyph_bitmap(font, notdef, g['ch'])
        if r is None:                       # absent de la police : bitmap d'origine agrandi
            bm, px, py = orig.crop((x0, y0, x0 + w, y0 + h)).resize((w * scale, h * scale), Image.LANCZOS), x0 * scale, y0 * scale
            kept += 1
        else:
            bm0, top = r
            bw = min(round(bm0.width * k), (w + 1) * scale)
            avail = (min(y0 + h + 1, cy + CH) - (cy + base)) * scale      # place sous la ligne de base dans la cellule
            up = bm0.crop((0, 0, bm0.width, min(bm0.height, max(1, -top))))  # partie au-dessus de la ligne de base
            low = bm0.crop((0, up.height, bm0.width, bm0.height)) if bm0.height > up.height else None
            hu = max(1, round(up.height * k))
            bm = up.resize((max(1, bw), hu), Image.LANCZOS)
            if low is not None:                                              # descendantes (p, q, y, g, j) : compressées sous la ligne de base, jamais décalées
                hl = max(1, min(round(low.height * k), avail))
                lo = low.resize((max(1, bw), hl), Image.LANCZOS)
                full = Image.new('L', (max(1, bw), hu + hl)); full.paste(bm, (0, 0)); full.paste(lo, (0, hu)); bm = full
            px = round((x0 + w / 2) * scale - bm.width / 2)
            py = round((cy + base) * scale + top * k)
            py = max(py, max(y0 - 1, cy) * scale)
            px = min(max(px, cx * scale), (cx + C) * scale - bm.width)
        tile = Image.new('L', (C * scale, CH * scale), 0)                # rognage à la cellule : pas de débordement sur la voisine
        tile.paste(bm, (px - cx * scale, py - cy * scale))
        out.paste(tile, (cx * scale, cy * scale))
    return alpha, out, kept, len(meta['glyphs'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--font', default='/System/Library/Fonts/Helvetica.ttc')
    ap.add_argument('--scale', type=int, default=4)
    ap.add_argument('--atlas', default=os.path.join(ROOT, 'data/atlas'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'work/hires_pack'))
    a = ap.parse_args()
    dest = os.path.join(a.out, TITLE_ID)
    os.makedirs(dest, exist_ok=True)
    for name in ('sml', 'nrm'):
        alpha, page, kept, n = render_page(name, a.atlas, a.font, a.scale)
        h = cityhash.CityHash64(a4_encode(alpha, 256, 256))
        fn = f'tex1_256x256_{h:016X}_11.png'
        existed = os.path.exists(os.path.join(dest, fn))
        rgba = np.zeros(page.size[::-1] + (4,), np.uint8)
        rgba[..., 3] = np.asarray(page)     # A4 : RGB noir, alpha = couverture (comme le décodage d'Azahar)
        Image.fromarray(rgba).transpose(Image.FLIP_TOP_BOTTOM).save(os.path.join(dest, fn))   # flip_png_files
        print(f'{name}: {n} glyphes ({kept} gardés du bitmap) -> {fn} {page.size[0]}x{page.size[1]}'
              + (' (remplace un fichier existant)' if existed else ''))


if __name__ == '__main__':
    main()
