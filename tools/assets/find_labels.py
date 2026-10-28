#!/usr/bin/env python3
"""Détecte les sprites (composantes connexes de l'alpha, après dilatation) d'un atlas et dessine un repérage numéroté.

  find_labels.py ENTREE_TEX [--region x0,y0,x1,y1] [--dilate N] [--zoom Z] [--out repere.png]
Sortie : boîtes (x, y, w, h) imprimées + repere.png (région agrandie, boîtes numérotées).
"""
import argparse, os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def boxes(img, region, dilate):
    a = np.asarray(img.convert('RGBA'))[:, :, 3] > 40
    x0, y0, x1, y1 = region
    m = np.zeros_like(a); m[y0:y1, x0:x1] = a[y0:y1, x0:x1]
    lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=dilate))
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        ys, xs = sl
        sub = m[sl] & (lab[sl] == i)
        if sub.sum() < 6: continue
        yy, xx = np.where(sub)
        out.append((xs.start + int(xx.min()), ys.start + int(yy.min()), int(xx.max() - xx.min() + 1), int(yy.max() - yy.min() + 1)))
    return sorted(out, key=lambda b: (b[1] // 20, b[0]))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('id'); ap.add_argument('--region'); ap.add_argument('--dilate', type=int, default=3)
    ap.add_argument('--zoom', type=int, default=2); ap.add_argument('--out', default='repere.png')
    ap.add_argument('--png', default=os.path.join(ROOT, 'work', 'assets', 'png'))
    a = ap.parse_args()
    im = Image.open(os.path.join(a.png, a.id + '.png')).convert('RGBA')
    reg = tuple(map(int, a.region.split(','))) if a.region else (0, 0, im.width, im.height)
    bs = boxes(im, reg, a.dilate)
    z = a.zoom
    crop = im.crop(reg); bg = Image.new('RGBA', crop.size, (70, 70, 80, 255)); bg.alpha_composite(crop)
    big = bg.convert('RGB').resize((crop.width * z, crop.height * z), Image.NEAREST); d = ImageDraw.Draw(big)
    for k, (x, y, w, h) in enumerate(bs):
        d.rectangle([(x - reg[0]) * z, (y - reg[1]) * z, (x - reg[0] + w) * z, (y - reg[1] + h) * z], outline=(255, 60, 60))
        d.text(((x - reg[0]) * z + 1, (y - reg[1]) * z - 10), str(k), fill=(255, 255, 0))
    big.save(a.out)
    for k, b in enumerate(bs): print(k, b)


if __name__ == '__main__':
    main()
