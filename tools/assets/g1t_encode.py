"""Encodeurs de textures G1T Nintendo 3DS (inverse de externals/LINKDATA-explorer/g1t_to_png.py).

Formats : 0x09 RGBA8, 0x3B RGB565, 0x3C RGBA5551, 0x3D RGBA4444, 0x44 A4, 0x47 ETC1, 0x48 ETC1A4.
Disposition CTR : tuiles 8x8 en ordre de Morton, image retournée verticalement.
ETC1 : encodeur simple vectorisé (numpy) ; essaie les 2 orientations × (différentiel | individuel) × 8 tables
et garde la plus faible erreur quadratique. Largeur/hauteur multiples de 8.
"""
import struct
import numpy as np

MODS = np.array([[2, 8, -2, -8], [5, 17, -5, -17], [9, 29, -9, -29], [13, 42, -13, -42],
                 [18, 60, -18, -60], [24, 80, -24, -80], [33, 106, -33, -106], [47, 183, -47, -183]], dtype=np.int32)
Z_ORDER = [0, 4, 1, 5, 8, 12, 9, 13, 2, 6, 3, 7, 10, 14, 11, 15]


def _swizzle_xy(w, h):
    """Pour chaque pixel du flux (pt), la position (x, y) dans l'image (haut = 0)."""
    n = w * h
    pt = np.arange(n)
    tx = (pt // 64) % max(1, w // 8)
    ty = (pt // 64) // max(1, w // 8)
    ix = (pt & 1) | ((pt >> 1) & 2) | ((pt >> 2) & 4)
    iy = ((pt >> 1) & 1) | ((pt >> 2) & 2) | ((pt >> 3) & 4)
    return tx * 8 + ix, h - 1 - (ty * 8 + iy)


def _to_stream(img, w, h):
    """img (h, w, C) -> (w*h, C) dans l'ordre du flux."""
    x, y = _swizzle_xy(w, h)
    return img[y, x]


def _block_bits(img, w, h):
    """img (h, w, C) -> (nb, 16, C) : pixels de chaque bloc 4x4 indexés par le bit i = x*4+y."""
    s = _to_stream(img, w, h).reshape(-1, 16, img.shape[2])
    out = np.empty_like(s)
    out[:, Z_ORDER] = s
    return out


def _q(v, bits):
    m = (1 << bits) - 1
    return np.clip(np.rint(v * m / 255.0), 0, m).astype(np.int32)


def _expand(v, bits):
    return (v << (8 - bits)) | (v >> (2 * bits - 8))


def _best_table(px, base):
    """px (nb, 8, 3) ; base (nb, 3) -> (err (nb,), table (nb,), sel (nb, 8))."""
    cand = np.clip(base[:, None, None, :] + MODS[None, :, :, None], 0, 255)       # nb, 8 tables, 4 sel, 3
    d = ((px[:, None, None, :, :] - cand[:, :, :, None, :]) ** 2).sum(-1)         # nb, 8, 4, 8px
    sel = d.argmin(2)                                                               # nb, 8 tables, 8px
    e = d.min(2).sum(-1)                                                            # nb, 8 tables
    t = e.argmin(1)
    ar = np.arange(len(t))
    return e[ar, t], t, sel[ar, t]


def _encode_etc1_blocks(rgb):
    """rgb (nb, 16, 3) int32 indexé par bit -> (nb,) uint64."""
    nb = rgb.shape[0]
    idx = np.arange(16)
    best = None
    for flip in (0, 1):
        sub1 = ((idx & 2) != 0) if flip else ((idx & 8) != 0)
        s0, s1 = np.where(~sub1)[0], np.where(sub1)[0]
        p0, p1 = rgb[:, s0], rgb[:, s1]
        m0, m1 = p0.mean(1), p1.mean(1)
        for diff in (0, 1):
            if diff:
                q0 = _q(m0, 5)
                q1 = np.clip(_q(m1, 5), q0 - 4, q0 + 3)
                c0, c1 = _expand(q0, 5), _expand(q1, 5)
            else:
                q0, q1 = _q(m0, 4), _q(m1, 4)
                c0, c1 = q0 * 17, q1 * 17
            e0, t0, sl0 = _best_table(p0, c0)
            e1, t1, sl1 = _best_table(p1, c1)
            err = e0 + e1
            if best is None:
                best = dict(err=err.copy(), flip=np.full(nb, flip), diff=np.full(nb, diff), q0=q0.copy(), q1=q1.copy(),
                            t0=t0.copy(), t1=t1.copy(), sel=np.zeros((nb, 16), np.int32))
                best['sel'][:, s0] = sl0; best['sel'][:, s1] = sl1
                continue
            better = err < best['err']
            if not better.any():
                continue
            for k, v in (('err', err), ('q0', q0), ('q1', q1), ('t0', t0), ('t1', t1)):
                best[k][better] = v[better]
            best['flip'][better] = flip; best['diff'][better] = diff
            sel = np.zeros((nb, 16), np.int32); sel[:, s0] = sl0; sel[:, s1] = sl1
            best['sel'][better] = sel[better]
    b = best
    sel = b['sel'].astype(np.uint64)
    shifts = np.arange(16, dtype=np.uint64)
    lsb = ((sel & 1) << shifts).sum(1)
    msb = (((sel >> 1) & 1) << shifts).sum(1)
    q0, q1 = b['q0'].astype(np.int64), b['q1'].astype(np.int64)
    rgbbytes = np.where(b['diff'][:, None] == 1,
                        (q0 << 3) | ((q1 - q0) & 7),
                        (q0 << 4) | q1)                                              # nb, 3 (r, g, b)
    flags = (b['t0'].astype(np.int64) << 5) | (b['t1'].astype(np.int64) << 2) | (b['diff'].astype(np.int64) << 1) | b['flip']
    return ((rgbbytes[:, 0].astype(np.uint64) << 56) | (rgbbytes[:, 1].astype(np.uint64) << 48) | (rgbbytes[:, 2].astype(np.uint64) << 40)
            | (flags.astype(np.uint64) << 32) | (msb << 16) | lsb)


def encode_level(rgba: np.ndarray, fmt: int) -> bytes:
    """rgba (h, w, 4) uint8 -> charge utile d'un niveau de mipmap."""
    h, w, _ = rgba.shape
    assert w % 8 == 0 and h % 8 == 0, (w, h)
    if fmt == 0x44:
        a = _to_stream(rgba[:, :, 3:4], w, h)[:, 0].astype(np.int32)
        v = np.minimum((a + 8) // 17, 15).astype(np.uint8)
        return (v[0::2] | (v[1::2] << 4)).astype(np.uint8).tobytes()
    if fmt in (0x47, 0x48):
        rgb = _block_bits(rgba[:, :, :3].astype(np.int32), w, h)
        out = bytearray()
        CH = 16384
        alpha = None
        if fmt == 0x48:
            ab = _block_bits(rgba[:, :, 3:4].astype(np.int32), w, h)[:, :, 0]
            an = np.minimum((ab + 8) // 17, 15).astype(np.uint64)
            alpha = (an << (np.arange(16, dtype=np.uint64) * 4)).sum(1)
        blocks = np.empty((rgb.shape[0], 2 if alpha is not None else 1), dtype='<u8')
        for s in range(0, rgb.shape[0], CH):
            c = _encode_etc1_blocks(rgb[s:s + CH])
            if alpha is not None:
                blocks[s:s + CH, 0] = alpha[s:s + CH]; blocks[s:s + CH, 1] = c
            else:
                blocks[s:s + CH, 0] = c
        return blocks.tobytes()
    s = _to_stream(rgba, w, h).astype(np.int64)
    r, g, b, a = s[:, 0], s[:, 1], s[:, 2], s[:, 3]
    if fmt == 0x09:
        return np.stack([a, b, g, r], 1).astype(np.uint8).tobytes()
    if fmt == 0x3D:
        v = ((r + 8) // 17 << 12) | ((g + 8) // 17 << 8) | ((b + 8) // 17 << 4) | ((a + 8) // 17)
        return v.astype('<u2').tobytes()
    if fmt == 0x3B:
        v = (_q(r, 5) << 11) | (_q(g, 6) << 5) | _q(b, 5)
        return v.astype('<u2').tobytes()
    if fmt == 0x3C:
        v = (_q(r, 5) << 11) | (_q(g, 5) << 6) | (_q(b, 5) << 1) | (a >= 128)
        return v.astype('<u2').tobytes()
    raise ValueError(f'format G1T non géré : {fmt:#04x}')
