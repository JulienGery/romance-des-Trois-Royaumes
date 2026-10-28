#!/usr/bin/env python3
"""Réécrit en français les libellés d'interface dessinés dans les atlas (translations/<langue>/ui_labels.json).

  gen_ui_labels.py [--lang fr] [--out translations/fr/textures] [--preview apercu.png]

Part du PNG d'origine (work/assets/png/<id>.png), efface le texte japonais (plain : alpha = 0 ; tile : inpainting OpenCV du texte blanc + contour),
dessine le français (même zone, couleurs de remplissage/contour échantillonnées sur l'original) et écrit l'atlas complet <id>.png (mêmes dimensions).
Les rectangles d'atlas sont codés en dur dans le jeu : le texte reste dans la zone d'origine.
"""
import argparse, json, os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FONT = ('/System/Library/Fonts/SFCompactRounded.ttf', 'Black')          # lourde et arrondie, proche du style Level-5 des libellés
S = 4
WEIGHT = {'title': 'Heavy'}                                        # graisse par style (le titre est plus fin : petits caractères)


def sample(rgb, mask, fallback=None):
    if not mask.any() and fallback is not None: mask = fallback
    px = rgb[mask]
    lum = px.sum(1)
    order = np.argsort(lum)
    n = max(1, len(px) // 4)
    return tuple(int(v) for v in np.median(px[order[-n:]], 0)), tuple(int(v) for v in np.median(px[order[:n]], 0))


def layers_for(style, fill, outline, h, thin=1.0):
    """(couches de contour [(épaisseur px, couleur, dx, dy)] de l'extérieur vers l'intérieur, couleur de remplissage, épaisseur d'embonpoint, ombre dy)"""
    sw = (2 if h >= 15 else 1) * thin
    if style == 'map':                       # libellés de la carte : blanc, contour noir épais, ombre noire, liseré blanc
        k, w2 = (0, 0, 0), (255, 255, 255)
        return [(sw + 1 * thin, w2, 0, 0), (sw + 1 * thin, w2, 0, 2 * thin), (sw, k, 0, 2 * thin), (sw, k, 0, 0)], (255, 255, 255), 0.0, 2 * thin
    if style == 'title':                     # boutons de l'écran titre : lavande très claire, anneau gris, fin contour sombre, ombre bas-droite
        d = (50, 50, 50)                      # un seul contour sombre net + ombre d'un pixel (un anneau gris en plus bouchait les lettres à cette taille)
        return [(1.0, d, 1, 1), (1.0, d, 0, 0)], (250, 249, 254), 0.0, 1
    return [(sw, outline, 0, 0)], fill, 0.0, 0


def fit(text, w, h, style, fill, outline, thin):
    lays, fcol, fat, sh = layers_for(style, fill, outline, h, thin)
    pad = max(t for t, *_ in lays)
    hmax = round(h * 0.80) + 2 * pad
    size = int(h * S * 1.3)
    while size > 6 * S:
        f = ImageFont.truetype(FONT[0], size); f.set_variation_by_name(WEIGHT.get(style, FONT[1]))
        b = f.getbbox(text, stroke_width=int(pad * S))
        if b[2] - b[0] + S <= w * S and b[3] - b[1] + sh * S <= min(h, hmax) * S: break
        size -= S // 2
    return lays, fcol, fat, sh, f, b, size / S


def render_text(text, w, h, fill, outline, align, style=None, size=None, thin=None):
    """Texte dans un rectangle w x h (supersampling S) ; hauteur limitée à 80 % de celle des kana d'origine ; contours amincis si le texte devient petit."""
    if size:                                                                # taille imposée (libellés d'un même groupe) : épaisseur de contour fixe
        lays, fcol, fat, sh = layers_for(style, fill, outline, h, thin or 0.6)
        f = ImageFont.truetype(FONT[0], int(size * S)); f.set_variation_by_name(WEIGHT.get(style, FONT[1]))
        b = f.getbbox(text, stroke_width=int(max(t for t, *_ in lays) * S))
        if b[2] - b[0] > w * S * 1.12: print(f'  attention : « {text} » dépasse ({(b[2] - b[0]) / S:.0f} > {w} px)')
    else:
        for thin in (1.0, 0.6, 0.4):
            lays, fcol, fat, sh, f, b, px = fit(text, w, h, style, fill, outline, thin)
            if px >= 12: break
    wc = max(w * S, b[2] - b[0])                                              # canvas plus large si le texte dépasse : écrasé horizontalement ensuite
    lay = Image.new('RGBA', (wc, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    x = 0 if align == 'left' else (wc - (b[2] - b[0])) // 2
    pos = (x - b[0], (h * S - (b[3] - b[1]) - sh * S) // 2 - b[1])
    for t, col, dx, dy in lays:
        d.text((pos[0] + dx * S, pos[1] + dy * S), text, font=f, fill=col + (255,), stroke_width=max(1, int(t * S)), stroke_fill=col + (255,))
    d.text(pos, text, font=f, fill=fcol + (255,), stroke_width=int(fat * S), stroke_fill=fcol + (255,))
    out = np.asarray(lay.resize((w, h), Image.LANCZOS)).copy()      # (écrase aussi horizontalement si besoin)
    out[:, :, 3] = np.clip((out[:, :, 3].astype(float) - 60) * 255 / 135, 0, 255).astype(np.uint8)     # contours nets (le jeu agrandit les sprites)
    return Image.fromarray(out, 'RGBA')


def process(img, items):
    a = np.asarray(img.convert('RGBA')).copy()
    for it in items:
        x, y, w, h = it['box']
        rgb, al = a[:, :, :3].copy(), a[:, :, 3]
        reg = np.zeros(al.shape, bool)
        if it['kind'] == 'plain':
            reg[y:y + h, x:x + w] = al[y:y + h, x:x + w] > 8
            if it.get('text_dx'): reg[:, :x + it['text_dx']] = False            # icône à gauche : le texte commence à x + text_dx
            ys, xs = np.where(reg)
            fill, outline = sample(rgb, reg & (al > 200), reg)
            tx, ty, tw, th = xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
            a[cv2.dilate(reg.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = 0
            if it.get('text_x') is not None: tx = x + it['text_x']; tw = x + w - tx - 1                 # colonne de départ commune (alignement entre boutons)
            elif it.get('text_dx'): tw = x + w - tx - 1
            if it.get('vcenter'): th = max(int(th), 16); ty = y + (h - th) // 2                           # même centre vertical que l'icône
            align = it.get('align', 'left' if it.get('text_dx') else 'center')
        else:                                                           # tile : texte blanc + contour sombre sur un aplat
            white = (rgb.min(2) >= 205) & (al > 200)
            reg[y:y + h, x:x + w] = white[y:y + h, x:x + w]
            ys, xs = np.where(reg)
            tx, ty, tw, th = xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
            ring = cv2.dilate(reg.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
            ring &= ~reg
            fill, _ = (255, 255, 255), None
            _, outline = sample(rgb, ring & (al > 200), ring)
            mask = (cv2.dilate(reg.astype(np.uint8), np.ones((7, 7), np.uint8)) * 255).astype(np.uint8)
            a[:, :, :3] = cv2.inpaint(np.ascontiguousarray(rgb), mask, 4, cv2.INPAINT_TELEA)
            align = 'center'
        lay = render_text(it['text'], int(tw) + (6 if it['kind'] == 'tile' else 0), int(th), fill, outline, align, it.get('style'), it.get('size'), it.get('thin'))
        base = Image.fromarray(a, 'RGBA'); base.alpha_composite(lay, (int(tx) - (3 if it['kind'] == 'tile' else 0), int(ty))); a = np.asarray(base).copy()
    return Image.fromarray(a, 'RGBA')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--lang', default='fr'); ap.add_argument('--out'); ap.add_argument('--preview')
    ap.add_argument('--png', default=os.path.join(ROOT, 'work', 'assets', 'png'))
    a = ap.parse_args()
    spec = json.load(open(os.path.join(ROOT, 'translations', a.lang, 'ui_labels.json'), encoding='utf-8'))
    out = a.out or os.path.join(ROOT, 'translations', a.lang, 'textures')
    os.makedirs(out, exist_ok=True)
    for tid, items in spec.items():
        if tid.startswith('_'): continue
        new = process(Image.open(os.path.join(a.png, tid + '.png')), items)
        new.save(os.path.join(out, tid + '.png'))
        if a.preview:
            for k, it in enumerate(items):
                x, y, w, h = it['box']; pad = 6
                pair = Image.new('RGB', (2 * (w + 2 * pad) * 3, (h + 2 * pad) * 3), (70, 70, 80))
                for j, im in enumerate((Image.open(os.path.join(a.png, tid + '.png')), new)):
                    c = im.convert('RGBA').crop((x - pad, y - pad, x + w + pad, y + h + pad)); bg = Image.new('RGBA', c.size, (70, 70, 80, 255)); bg.alpha_composite(c)
                    pair.paste(bg.convert('RGB').resize((c.width * 3, c.height * 3), Image.NEAREST), (j * c.width * 3, 0))
                pair.save(f'{a.preview}_{tid}_{k}.png')
        print(tid, len(items), 'libellés')


if __name__ == '__main__':
    main()
