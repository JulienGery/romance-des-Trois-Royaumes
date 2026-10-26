#!/usr/bin/env python3
"""G1T (GT1G, Nintendo 3DS) helpers: A4 encode + rebuild with an extra texture.

Stdlib only. Reuses the decoder of LINKDATA-explorer/g1t_to_png.py.
Format facts (verified on LINKDATA_A.BIN entry 0):
  header : 'GT1G' '0600' u32 file_size u32 data_offset u32 tex_count u32 unk1 u32 unk2
  then   : tex_count * u32 (unk region), then at data_offset: tex_count * u32 offsets
  entry  : 8 byte header (mip_unk, fmt, dim, zero, swiz, unk3, unk4, ext_hdr) + raw data
  A4 (fmt 0x44): 2 px/byte, LOW nibble = first pixel, CTR 8x8 Morton tiles, Y flipped.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'LINKDATA-explorer'))
from g1t_to_png import G1tFile  # noqa: E402


def a4_encode(alpha: bytes, w: int, h: int) -> bytes:
    """alpha: w*h bytes (0..255), row 0 = top. Returns CTR-swizzled A4 payload."""
    assert len(alpha) == w * h and w % 8 == 0 and h % 8 == 0
    tiles_x = w // 8
    n = w * h
    out = bytearray(n // 2)
    for pt in range(n):
        tile = pt // 64
        tx, ty = tile % tiles_x, tile // tiles_x
        ix = (pt & 1) | ((pt >> 1) & 2) | ((pt >> 2) & 4)
        iy = ((pt >> 1) & 1) | ((pt >> 2) & 2) | ((pt >> 3) & 4)
        x = tx * 8 + ix
        y = h - 1 - (ty * 8 + iy)
        v = (alpha[y * w + x] + 8) // 17          # 0..255 -> 0..15
        v = 15 if v > 15 else v
        out[pt >> 1] |= v << (4 if pt & 1 else 0)
    return bytes(out)


def split_g1t(data: bytes):
    """Return (header_fields, [raw entry bytes incl. 8-byte header])."""
    g = G1tFile(data)
    ents = []
    for i, off in enumerate(g.offsets):
        start = g.data_offset + off
        end = g.data_offset + (g.offsets[i + 1] if i + 1 < len(g.offsets) else len(data) - g.data_offset)
        ents.append(data[start:end])
    return g, ents


def build_g1t(g: G1tFile, entries) -> bytes:
    n = len(entries)
    unk = list(g.unk_region) + [0] * (n - len(g.unk_region))
    data_offset = 28 + 4 * n
    offs, cur = [], 4 * n
    for e in entries:
        offs.append(cur)
        cur += len(e)
    size = data_offset + cur
    hdr = b'GT1G' + g.version.encode('latin1')
    hdr += struct.pack('<IIIII', size, data_offset, n, g.unk1, g.unk2)
    hdr += struct.pack('<%dI' % n, *unk[:n])
    hdr += struct.pack('<%dI' % n, *offs)
    return hdr + b''.join(entries)


def make_a4_entry(like_entry: bytes, w: int, h: int, alpha: bytes) -> bytes:
    """New texture entry cloned from an existing A4 entry header (dim byte replaced)."""
    import math
    hdr = bytearray(like_entry[:8])
    assert hdr[1] == 0x44 and hdr[7] == 0
    hdr[2] = (int(math.log2(h)) << 4) | int(math.log2(w))
    return bytes(hdr) + a4_encode(alpha, w, h)


if __name__ == '__main__':
    # self-test: decode -> re-encode every A4 texture, and rebuild the container byte-identical
    src = sys.argv[1]
    d = open(src, 'rb').read()
    g, ents = split_g1t(d)
    ok = True
    for i, t in enumerate(g.textures):
        w, h, px = g.decode_texture(t)
        alpha = bytes(px[3::4])
        same = a4_encode(alpha, w, h) == t.raw_data
        print('tex', i, w, h, 'A4 roundtrip', same)
        ok &= same
    rebuilt = build_g1t(g, ents)
    print('container rebuild identical:', rebuilt == d, len(rebuilt), len(d))
    sys.exit(0 if ok and rebuilt == d else 1)
