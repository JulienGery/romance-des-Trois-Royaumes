#!/usr/bin/env python3
"""Replace one entry of LINKDATA_A.BIN (chunked-zlib or raw) without rebuilding the archive.

Table layout (verified): 16-byte header, then N*16-byte records {addr/32, 0, disk_size, decomp_size}
(decomp_size == 0 => stored raw). The new payload is written in the old slot if it fits,
otherwise appended at the end of the file (32-byte aligned) and the record is re-pointed.
"""
import argparse, os, shutil, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'externals', 'LINKDATA-explorer'))
from linkdata_engine import LinkDataArchive, compress_entry_payload  # noqa: E402


def patch(src, dst, index, payload, compress=True):
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    a = LinkDataArchive(dst)
    e = a.entries[index]
    blob = compress_entry_payload(payload) if compress else payload + b'\0' * ((32 - len(payload) % 32) % 32)
    disk_size, decomp = (len(blob), len(payload)) if compress else (len(payload), 0)
    nxt = min((x.offset for x in a.entries if x.offset > e.offset and not x.is_empty), default=a.file_size)
    slot = nxt - e.offset
    with open(dst, 'r+b') as f:
        if len(blob) <= slot:
            off = e.offset; where = 'in place'
        else:
            f.seek(0, 2); end = f.tell(); pad = (-end) % 32
            f.write(b'\0' * pad); off = end + pad; where = 'appended'
        f.seek(off); f.write(blob)
        f.seek(16 + index * 16); f.write(struct.pack('<IIII', off // 32, 0, disk_size, decomp))
    b = LinkDataArchive(dst)
    assert b.read_entry_decompressed(index) == payload, 'verification failed'
    return where, off, disk_size


def patch_many(src, dst, items):
    """items: {index: (payload_bytes, compress_bool)}. One copy of the archive, all payloads appended (32-aligned), table re-pointed."""
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    a = LinkDataArchive(dst)
    with open(dst, 'r+b') as f:
        f.seek(0, 2); end = f.tell()
        for index in sorted(items):
            payload, comp = items[index]
            blob = compress_entry_payload(payload) if comp else payload + b'\0' * ((32 - len(payload) % 32) % 32)
            disk_size, decomp = (len(blob), len(payload)) if comp else (len(payload), 0)
            pad = (-end) % 32
            f.seek(end); f.write(b'\0' * pad); off = end + pad; f.write(blob); end = off + len(blob)
            f.seek(16 + index * 16); f.write(struct.pack('<IIII', off // 32, 0, disk_size, decomp))
    b = LinkDataArchive(dst)
    for index, (payload, comp) in items.items():
        assert b.read_entry_decompressed(index) == payload, f'verification failed for entry {index}'
    return len(items)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('index', type=int); ap.add_argument('payload')
    ap.add_argument('--raw', action='store_true'); a = ap.parse_args()
    print(patch(a.src, a.dst, a.index, open(a.payload, 'rb').read(), not a.raw))
