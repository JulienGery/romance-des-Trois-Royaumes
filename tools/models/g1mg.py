#!/usr/bin/env python3
"""Lecture / réécriture de la géométrie `GM1G` (plate-forme 3DS, v44) des modèles `_M1G` de LINKDATA_A.BIN.

Sections (u32 type, u32 taille, u32 nombre) : 10001 constantes, 10002 matériaux, 10003 ombreurs,
10004 tampons de sommets, 10005 attributs, 10006 palettes d'os, 10007 tampons d'index,
10008 sous-maillages, 10009 maillages (LOD). Sommet type : pos f32×3 (0x00), indices d'os 4×u8 (0x0C),
poids 4×u8 (0x10), normale f32×3 (0x14), couleur u8×4 (0x20), UV f32×2 (0x24) ; pas 0x2C.
Sous-maillage (56 o) : mots [10..13] = début sommets, nb sommets, début index, nb index ; [9] = primitive (3 liste, 4 bande).
"""
import struct

SEC_VERT, SEC_ATTR, SEC_IDX, SEC_SUB = 0x10004, 0x10005, 0x10007, 0x10008


class Section:
    def __init__(self, typ, count, body):
        self.typ, self.count, self.body = typ, count, body   # body = octets après l'en-tête de 12 octets


def split_models(entry):
    """Entrée « binary » d'un yo-kai : u32 n, n décalages, fichiers (_M1G…, GT1G) → [(décalage, taille, magie)]."""
    n = struct.unpack_from('<I', entry, 0)[0]
    if not 0 < n < 64: return None
    offs = list(struct.unpack_from('<%dI' % n, entry, 4))
    if offs != sorted(offs) or offs[-1] >= len(entry): return None
    ends = offs[1:] + [len(entry)]
    return [(o, e - o, entry[o:o + 4]) for o, e in zip(offs, ends)]


def find_gm1g(m1g):
    """Position (début, taille) du chunk GM1G dans un `_M1G`."""
    if m1g[:4] != b'_M1G': return None
    hdr, n = struct.unpack_from('<II', m1g, 12)[0], struct.unpack_from('<I', m1g, 20)[0]
    o = hdr
    for _ in range(n):
        c, v, s = struct.unpack_from('<4s4sI', m1g, o)
        if c == b'GM1G': return o, s
        o += s
    return None


def parse_gm1g(g):
    assert g[:4] == b'GM1G' and g[12:16] == b'3DS\0', g[:16]
    head = g[:44]
    cnt = struct.unpack_from('<I', g, 44)[0]
    secs, o = [], 48
    for _ in range(cnt):
        t, s, c = struct.unpack_from('<III', g, o)
        secs.append(Section(t & 0xFFFFFFFF, c, g[o + 12:o + s]))
        secs[-1].raw_size = s
        o += s
    return head, secs, g[o:]


def build_gm1g(head, secs, tail=b''):
    out = bytearray(head) + struct.pack('<I', len(secs))
    for s in secs:
        out += struct.pack('<III', s.typ, 12 + len(s.body), s.count) + s.body
    out += tail
    out[8:12] = struct.pack('<I', len(out))
    return bytes(out)


def get(secs, typ):
    return [s for s in secs if s.typ == typ]


# ---------------------------------------------------------------- niveau « maillage »
import numpy as np

T_F32x2, T_F32x3, T_BYTES4_A, T_BYTES4_B = 1, 2, 5, 0xD


def parse_attrs(sec):
    """Un jeu d'attributs par tampon : [[(flux, décalage, type, sémantique), …], …]. Sémantiques : 0 pos, 1 poids, 2 os, 3 normale, 5 UV, 10 couleur."""
    b, o, sets = sec.body, 0, []
    for _ in range(sec.count):
        n = struct.unpack_from('<I', b, o + 8)[0]
        sets.append([struct.unpack_from('<4H', b, o + 12 + 8 * i) for i in range(n)])
        o += 12 + 8 * n
    assert o == len(b), (o, len(b))
    return sets


def parse_vbufs(sec):
    """[(stride, count, data)] de la section 10004. Les données de chaque tampon suivent un en-tête de 16 o."""
    b, o, out = sec.body, 0, []
    for _ in range(sec.count):
        _, stride, cnt, _ = struct.unpack_from('<4I', b, o)
        out.append((stride, cnt, b[o + 16:o + 16 + stride * cnt]))
        o += 16 + stride * cnt
    assert o == len(b), (o, len(b))
    return out


def build_vbufs(bufs):
    return b''.join(struct.pack('<4I', 0, s, c, 0) + d for s, c, d in bufs)


def parse_ibufs(sec):
    """[ndarray u16] — un tableau d'index par tampon (type 0x10 = u16)."""
    b, o, out = sec.body, 0, []
    for _ in range(sec.count):
        n, typ, _ = struct.unpack_from('<3I', b, o)
        assert typ == 0x10
        out.append(np.frombuffer(b, '<u2', n, o + 12).copy())
        o += 12 + 2 * n
    assert o == len(b), (o, len(b))
    return out


def build_ibufs(arrs):
    return b''.join(struct.pack('<3I', len(a), 0x10, 0) + np.asarray(a, '<u2').tobytes() for a in arrs)


def parse_subs(sec):
    return [list(struct.unpack_from('<14I', sec.body, i * 56)) for i in range(sec.count)]


def strip_to_tris(idx):
    """Bande de triangles (avec dégénérés) → liste (n,3), orientation conservée."""
    idx = np.asarray(idx, np.int64)
    n = len(idx) - 2
    if n <= 0: return np.zeros((0, 3), np.int64)
    a, b, c = idx[:-2], idx[1:-1], idx[2:]
    odd = (np.arange(n) & 1).astype(bool)
    t = np.stack([a, np.where(odd, c, b), np.where(odd, b, c)], 1)
    ok = (t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])
    return t[ok]


def tris_to_strip(tris):
    """Liste de triangles → une bande unique. Un triangle prolonge la bande quand il partage la dernière arête dans le bon sens
    (parité comprise) ; sinon jonction par triangles dégénérés (la parité de la position de départ est respectée)."""
    out = []
    for a, b, c in np.asarray(tris).tolist():
        if len(out) >= 3:
            p, q = out[-2], out[-1]
            want = (p, q) if (len(out) - 2) % 2 == 0 else (q, p)      # arête attendue, dans l'ordre d'enroulement du triangle suivant
            for t in ((a, b, c), (b, c, a), (c, a, b)):
                if (t[0], t[1]) == want:
                    out.append(t[2]); break
            else:
                t = None
            if t is not None: continue
        if out:
            out += [out[-1], a]
            if len(out) & 1: out.append(a)       # le triangle suivant doit commencer sur un index pair
        out += [a, b, c]
    return np.asarray(out, np.int64)
