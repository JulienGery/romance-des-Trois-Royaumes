#!/usr/bin/env python3
"""Remplace des textures de LINKDATA_A.BIN par des PNG retouchés (mêmes dimensions que l'original).

  apply_textures.py DOSSIER_PNG [--src LINKDATA_A.BIN] [--dst out.BIN] [--check]

DOSSIER_PNG contient des fichiers <entrée>_<tex>.png (noms identiques à ceux de extract_textures.py).
Chaque texture est ré-encodée dans son format d'origine (mipmaps régénérées), puis l'entrée G1T est
reconstruite et réinjectée via tools/patch_linkdata.patch_many. --check : encode/décode et affiche l'écart, sans écrire.
"""
import argparse, os, re, struct, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path[:0] = [HERE, os.path.join(ROOT, 'tools'), os.path.join(ROOT, 'externals', 'LINKDATA-explorer')]
from linkdata_engine import LinkDataArchive  # noqa: E402
from g1t_to_png import G1tFile  # noqa: E402
from g1t_tools import split_g1t, build_g1t  # noqa: E402
from g1t_encode import encode_level  # noqa: E402


def replace_textures(g1t_bytes, new):
    """new: {tex_index: PIL RGBA image}. Retourne le G1T reconstruit."""
    g, ents = split_g1t(g1t_bytes)
    for ti, img in new.items():
        t = g.textures[ti]
        hdr = 8 + t.ext_hdr_size
        head = bytearray(ents[ti][:hdr])
        if img.size != (t.width, t.height):
            if not os.environ.get('YOKAI_ALLOW_RESIZE'):
                raise SystemExit(f'texture {ti}: {img.size} au lieu de {(t.width, t.height)} (les dimensions doivent rester identiques ; YOKAI_ALLOW_RESIZE=1 pour un essai)')
            w, h = img.size
            assert w & (w - 1) == 0 and h & (h - 1) == 0 and not (t.mip_unk >> 4) > 1, 'redimensionnement : puissances de 2, sans mipmaps'
            head[2] = (h.bit_length() - 1) << 4 | (w.bit_length() - 1)
        payload = encode_level(np.asarray(img.convert('RGBA')), t.format)
        for m in range(1, t.mip_unk >> 4):
            payload += encode_level(np.asarray(img.convert('RGBA').resize((max(8, t.width >> m), max(8, t.height >> m)), Image.BOX)), t.format)
        if img.size == (t.width, t.height): assert len(payload) == len(ents[ti]) - hdr, (ti, len(payload), len(ents[ti]) - hdr)
        ents[ti] = bytes(head) + payload
    return build_g1t(g, ents)


def texture_items(arc, pngdir):
    """{entrée: (G1T reconstruit, compressé)} pour tous les <entrée>_<tex>.png de pngdir (utilisé par apply_translation.py)."""
    groups = {}
    for f in sorted(os.listdir(pngdir)):
        m = re.fullmatch(r'(\d+)_(\d+)\.png', f)
        if m:
            if int(m[1]) == 0: raise SystemExit('l\'entrée 0 (atlas de police) est gérée par make_entry0.py, pas par les textures')
            groups.setdefault(int(m[1]), {})[int(m[2])] = Image.open(os.path.join(pngdir, f)).convert('RGBA')
    return {e: (replace_textures(arc.read_entry_decompressed(e), t), arc.entries[e].is_compressed) for e, t in groups.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pngdir')
    ap.add_argument('--src', default=os.path.join(ROOT, 'work/rom/romfs_dir/Data/LINKDATA_A.BIN'))
    ap.add_argument('--dst'); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    arc = LinkDataArchive(a.src)
    items = texture_items(arc, a.pngdir)
    if a.check:
        for entry, (new, _) in sorted(items.items()):
            g2 = G1tFile(new)
            for ti in range(len(g2.textures)):
                f = os.path.join(a.pngdir, f'{entry}_{ti}.png')
                if not os.path.exists(f): continue
                ref = np.asarray(Image.open(f).convert('RGBA')).astype(int)
                _, _, px = g2.decode_texture(g2.textures[ti]); dec = np.frombuffer(px, np.uint8).reshape(ref.shape).astype(int)
                m = ref[:, :, 3] > 0
                print(f'{entry}_{ti}: écart moyen RGB (pixels visibles) {np.abs(ref-dec)[m][:, :3].mean() if m.any() else 0:.2f}, alpha {np.abs(ref-dec)[:, :, 3].mean():.2f}')
        return
    from patch_linkdata import patch_many
    patch_many(a.src, a.dst, items)
    print(len(items), 'entrées remplacées ->', a.dst)


if __name__ == '__main__':
    main()
