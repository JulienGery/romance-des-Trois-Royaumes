#!/usr/bin/env python3
"""Met à jour dans code.bin la largeur des plaques de noms (Yo-kai + officier).

Le jeu aligne chaque plaque à droite d'après un tableau de données de 16 octets par plaque (pointeur en 0x14BA48, tableau en 0x628140 dans la ROM d'origine) :
  +8 u16 = largeur de la pilule (px), +10 u16 = hauteur ; indexé par ligne du script 57/0 (entrée LINKDATA = 12205 + ligne).
Vérifié sur les 232 plaques japonaises : largeur du tableau == largeur visible de la pilule.
On y écrit la largeur visible des PNG français de translations/<langue>/textures/ pour qu'ils restent alignés.

  patch_plate_table.py CODE_IN CODE_OUT TEXTURES_DIR
"""
import os, struct, sys
import numpy as np
from PIL import Image

BASE, PTR, N = 12205, 0x14BA48 - 0x100000, 0x2A8


def main():
    src, dst, tex = sys.argv[1:4]
    d = bytearray(open(src, 'rb').read())
    tab = struct.unpack_from('<I', d, PTR)[0] - 0x100000
    n = 0
    for L in range(N):
        f = os.path.join(tex, f'{BASE + L}_0.png')
        if not os.path.exists(f): continue
        a = np.asarray(Image.open(f).convert('RGBA'))
        if a.shape[0] != 32: continue
        ys, xs = np.where(a[:, :, 3] > 150)
        w = int(xs.max()) + 1
        off = tab + L * 16 + 8
        old = struct.unpack_from('<H', d, off)[0]
        assert 0 < old <= 128, (L, old)                       # on ne touche qu'à de vraies entrées de plaque
        if old != w: struct.pack_into('<H', d, off, w); n += 1
    open(dst, 'wb').write(d)
    print(f'{n} largeurs de plaques mises à jour (tableau en 0x{tab + 0x100000:X})')


if __name__ == '__main__':
    main()
