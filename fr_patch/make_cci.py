#!/usr/bin/env python3
"""Assemble a CCI (NCSD) from the original NCSD header, a patched partition 0 (CXI) and the original partition 1 (CFA): rewrites the partition table (the declared image size, 1 GiB, is kept), keeps everything else (3dstool pads the last partition to 1 GiB, which makes a useless 1.9 GB file).
usage: make_cci.py ncsd_header.bin game.cxi update.cfa out.cci"""
import struct, sys
hdr = bytearray(open(sys.argv[1], 'rb').read()); cxi = open(sys.argv[2], 'rb'); cfa = open(sys.argv[3], 'rb'); out = open(sys.argv[4], 'wb')
import os
n0 = os.path.getsize(sys.argv[2]); n1 = os.path.getsize(sys.argv[3]); U = 0x200
assert n0 % U == 0 and n1 % U == 0 and hdr[0x100:0x104] == b'NCSD'
off0 = struct.unpack_from('<I', hdr, 0x120)[0]
off1 = off0 + n0 // U
struct.pack_into('<II', hdr, 0x120, off0, n0 // U)
struct.pack_into('<II', hdr, 0x128, off1, n1 // U)
out.write(hdr)
for f in (cxi, cfa):
    while True:
        b = f.read(1 << 24)
        if not b: break
        out.write(b)
out.close()
print(f'{sys.argv[4]}: partition 0 at {off0 * U:#x} size {n0:#x}, partition 1 at {off1 * U:#x} size {n1:#x}')
