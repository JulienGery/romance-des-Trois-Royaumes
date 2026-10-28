#!/usr/bin/env python3
"""Génère un pack de textures haute résolution pour Azahar (sans toucher à l'archive du jeu).

  build_hires_pack.py [--config tools/assets/hires_config.json] [--out work/hires_pack] [--range A:B] [--ids 17779_0,...] [--dry-run]
  build_hires_pack.py --from-dump ~/Library/Application\\ Support/Azahar/dump/textures/000400000018B000
Le 2e mode agrandit les PNG dumpés par Azahar sous le même nom (textures fabriquées à l'exécution, dont le hash est imprévisible :
décors de la carte, par exemple). Les PNG sont stockés retournés verticalement, comme les dumps (`flip_png_files: true`).

Pour chaque texture de LINKDATA_A.BIN (G1T des entrées `texture`, G1T embarqués dans les entrées `binary`, `.bflim` des SARC) : hash CityHash64 des octets encodés du niveau 0 (= `use_new_hash` d'Azahar),
agrandissement par Upscayl (binaire du .app), réduction éventuelle à l'échelle voulue, puis
<out>/<TitleID>/tex1_<L>x<H>_<HASH>_<format>.png + pack.json. Copier <TitleID>/ dans `load/textures/` d'Azahar.
La config donne le modèle et l'échelle par défaut, plus des règles (dernier match gagnant) par plage d'entrées ou identifiants.
"""
import argparse, json, os, shutil, struct, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'externals', 'LINKDATA-explorer'))
from linkdata_engine import LinkDataArchive, parse_sarc  # noqa: E402
from g1t_to_png import G1tFile, G1tTextureEntry, PLATFORM_N3DS  # noqa: E402
import cityhash  # noqa: E402
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

TITLE_ID = '000400000018B000'
UPSCAYL = '/Applications/Upscayl.app/Contents/Resources'
# format G1T (3DS) -> (format PICA d'Azahar, octets par pixel du niveau 0 ; ETC1 = 0.5)
FMT = {0x09: (0, 4), 0x45: (1, 3), 0x3C: (2, 2), 0x3B: (3, 2), 0x3D: (4, 2), 0x44: (11, 0.5), 0x47: (12, 0.5), 0x48: (13, 1)}

# format BFLIM -> (format PICA d'Azahar, octets par pixel, format G1T pour réutiliser le décodeur) ; None = non décodé
BFLIM = {0x5: (3, 2, 0x3B), 0x6: (1, 3, 0x45), 0x7: (2, 2, 0x3C), 0x8: (4, 2, 0x3D), 0x9: (0, 4, 0x09),
         0xA: (12, .5, 0x47), 0xB: (13, 1, 0x48)}


def pow2(n):
    x = 8
    while x < n:
        x *= 2
    return x


def bflim_textures(arc, idx):
    """Textures .bflim des SARC de l'entrée idx : [(nom, hash, dims GPU, format PICA, format G1T, octets niveau 0)].
    Les images BFLIM sont stockées transposées : dimensions GPU = (p2(hauteur), p2(largeur)) (vérifié sur 132 hash du dump)."""
    try:
        d = arc.read_entry_decompressed(idx)
    except Exception:
        return []
    if d[:4] != b'SARC':
        return []
    out = []
    for f in parse_sarc(d)['files']:
        b = d[f['offset']:f['offset'] + f['size']]
        if not f['name'].endswith('.bflim') or b[-40:-36] != b'FLIM' or b.rfind(b'imag') < 0:
            continue
        i = b.rfind(b'imag')
        w, h, _, fmt, _ = struct.unpack('<HHHBB', b[i + 8:i + 16])
        if fmt not in BFLIM:
            continue
        pf, bpp, g1t = BFLIM[fmt]
        gw, gh = pow2(h), pow2(w)
        raw = b[:int(gw * gh * bpp)]
        out.append((f['name'], cityhash.CityHash64(raw), (gw, gh), pf, g1t, raw))
    return out


def lo_hi(rng):
    lo, hi = map(int, rng.split(':'))
    return lo, hi


def embedded_texture(arc, idx, off, k):
    d = arc.read_entry_decompressed(idx)
    g = G1tFile(d[off:off + struct.unpack('<I', d[off + 8:off + 12])[0]])
    return g.decode_texture(g.textures[k])


def decode_raw(g1t_fmt, gw, gh, raw):
    g = object.__new__(G1tFile)
    g.platform = PLATFORM_N3DS
    dim = (gw.bit_length() - 1) | ((gh.bit_length() - 1) << 4)
    return g.decode_texture(G1tTextureEntry(0, 0, 0, g1t_fmt, dim, 0, 0, 0, 0, 0, 0, b'', raw, []))


def rule_matches(rule, entry, tex):
    if 'ids' in rule and f'{entry}_{tex}' in rule['ids']:
        return True
    for span in rule.get('entries', []):
        lo, _, hi = str(span).partition('-')
        if int(lo) <= entry <= int(hi or lo):
            return True
    return False


def settings(cfg, entry, tex):
    s = dict(model=cfg['model'], scale=cfg['scale'])
    for r in cfg.get('rules', []):
        if rule_matches(r, entry, tex):
            s.update({k: r[k] for k in ('model', 'scale') if k in r})
    return s


def upscale_batch(model, items, work, dest, flip_src=False):
    """items : [(nom final, PNG source, échelle, (largeur, hauteur) d'origine)] ; écrit dans dest, retourné verticalement."""
    inp, outp = os.path.join(work, model, 'in'), os.path.join(work, model, 'out')
    shutil.rmtree(os.path.join(work, model), ignore_errors=True)
    os.makedirs(inp); os.makedirs(outp)
    for n, (name, src, scale, size) in enumerate(items):
        shutil.copy(src, os.path.join(inp, f'{n}.png'))
    subprocess.run([f'{UPSCAYL}/bin/upscayl-bin', '-i', inp, '-o', outp, '-m', f'{UPSCAYL}/models',
                    '-n', model, '-s', '4', '-f', 'png'], check=True, stderr=subprocess.DEVNULL)
    for n, (name, src, scale, size) in enumerate(items):
        im = cv2.imread(os.path.join(outp, f'{n}.png'), cv2.IMREAD_UNCHANGED)
        if scale < 4:
            im = cv2.resize(im, (size[0] * scale, size[1] * scale), interpolation=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(dest, name), im if flip_src else cv2.flip(im, 0))
    shutil.rmtree(os.path.join(work, model), ignore_errors=True)
    print(f'{model}: {len(items)} écrites')


def write_pack_json(dest):
    json.dump(dict(author='yokai-watch-claude', version='1.0.0', description='Textures HD (Upscayl)',
                   options=dict(skip_mipmap=True, flip_png_files=True, use_new_hash=True)),
              open(os.path.join(dest, 'pack.json'), 'w'), indent=4)


def from_dump(a, cfg):
    import re
    dest, work = os.path.join(a.out, TITLE_ID), os.path.join(a.out, '_work')
    os.makedirs(dest, exist_ok=True)
    items = []
    for f in sorted(os.listdir(a.from_dump)):
        m = re.match(r'tex1_(\d+)x(\d+)_([0-9A-F]+)_(\d+)_mip0\.png$', f)
        if not m or min(int(m[1]), int(m[2])) < cfg.get('min_size', 32) or os.path.exists(os.path.join(dest, f.replace('_mip0', ''))):
            continue
        items.append((f.replace('_mip0', ''), os.path.join(a.from_dump, f), cfg.get('dump_scale', cfg['scale']), (int(m[1]), int(m[2]))))
    print(f'{len(items)} textures dumpées à agrandir')
    if items and not a.dry_run:
        upscale_batch(cfg['model'], items, work, dest, flip_src=True)
    write_pack_json(dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default=os.path.join(ROOT, 'tools/assets/hires_config.json'))
    ap.add_argument('--linkdata', default=os.path.join(ROOT, 'work/rom/romfs_dir/Data/LINKDATA_A.BIN'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'work/hires_pack'))
    ap.add_argument('--range', default=None)
    ap.add_argument('--ids', default=None)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--from-dump', default=None)
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    if a.from_dump:
        return from_dump(a, cfg)
    arc = LinkDataArchive(a.linkdata)
    idxs = [e.index for e in arc.entries if e.file_type == 'texture']
    if a.range:
        lo, hi = map(int, a.range.split(':')); idxs = [i for i in idxs if lo <= i < hi]
    ids = set(a.ids.split(',')) if a.ids else None
    dest = os.path.join(a.out, TITLE_ID)
    work = os.path.join(a.out, '_work')
    os.makedirs(dest, exist_ok=True)

    jobs, seen, skipped = {}, set(), 0       # modèle -> [(nom final, décodeur () -> (l, h, rgba), échelle, taille d'origine)]
    min_size = cfg.get('min_size', 32)

    def add(s, name, h, loader, size):
        nonlocal skipped
        if s['scale'] <= 1 or min(size) < min_size or h in seen or os.path.exists(os.path.join(dest, name)):
            skipped += 1; return
        seen.add(h)
        jobs.setdefault(s['model'], []).append((name, loader, s['scale'], size))

    for idx in idxs:
        g = G1tFile(arc.read_entry_decompressed(idx))
        for t in g.textures:
            if ids and f'{idx}_{t.index}' not in ids:
                continue
            if t.format not in FMT:
                skipped += 1; continue
            pf, bpp = FMT[t.format]
            h = cityhash.CityHash64(bytes(t.raw_data[:int(t.width * t.height * bpp)]))
            add(settings(cfg, idx, t.index), f'tex1_{t.width}x{t.height}_{h:016X}_{pf}.png', h,
                lambda i=idx, k=t.index: (lambda g: g.decode_texture(g.textures[k]))(G1tFile(arc.read_entry_decompressed(i))),
                (t.width, t.height))
    if not ids:                                # G1T embarqués dans les entrées « binary » (modèles, décors, yo-kai) : magie GT1G
        for e in arc.entries:
            if e.file_type in ('texture', 'script', 'audio', 'empty', 'animation') or (a.range and not lo_hi(a.range)[0] <= e.index < lo_hi(a.range)[1]):
                continue
            d = arc.read_entry_decompressed(e.index)
            off = d.find(b'GT1G')
            while off >= 0:
                try:
                    g = G1tFile(d[off:off + struct.unpack('<I', d[off + 8:off + 12])[0]])
                except Exception:
                    g = None
                for t in (g.textures if g else []):
                    if t.format not in FMT:
                        continue
                    pf, bpp = FMT[t.format]
                    h = cityhash.CityHash64(bytes(t.raw_data[:int(t.width * t.height * bpp)]))
                    add(settings(cfg, e.index, t.index), f'tex1_{t.width}x{t.height}_{h:016X}_{pf}.png', h,
                        lambda i=e.index, o=off, k=t.index: embedded_texture(arc, i, o, k), (t.width, t.height))
                off = d.find(b'GT1G', off + 4)
    if not ids:                                # textures .bflim des SARC (décors, interface)
        lo, hi = map(int, a.range.split(':')) if a.range else (0, 1 << 30)
        for e in arc.entries:
            if e.file_type in ('texture', 'script', 'audio', 'empty', 'animation') or not lo <= e.index < hi:
                continue
            for name, h, (gw, gh), pf, g1t, raw in bflim_textures(arc, e.index):
                add(settings(cfg, e.index, 0), f'tex1_{gw}x{gh}_{h:016X}_{pf}.png', h,
                    lambda f=g1t, gw=gw, gh=gh, raw=raw: decode_raw(f, gw, gh, raw), (gw, gh))
    total = sum(len(v) for v in jobs.values())
    print(f'{total} textures à agrandir ({skipped} ignorées : échelle 1, trop petites, format inconnu ou déjà faites)')
    if a.dry_run or not total:
        return
    os.makedirs(work, exist_ok=True)
    for model, items in jobs.items():
        batch = []
        for name, loader, scale, size in items:
            w, h, rgba = loader()
            src = os.path.join(work, f'{len(batch)}_src.png')
            Image.frombytes('RGBA', (w, h), bytes(rgba)).save(src)
            batch.append((name, src, scale, size))
        upscale_batch(model, batch, work, dest)
    write_pack_json(dest)


if __name__ == '__main__':
    main()
