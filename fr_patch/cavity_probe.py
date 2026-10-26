#!/usr/bin/env python3
"""Fill candidate dead-code ranges with an undefined-instruction trap, build a CXI and run it: the emulator's abort log tells which
'dead' function is actually executed. usage: cavity_probe.py start-end [start-end ...] (hex)"""
import os, re, struct, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); RW = os.path.join(ROOT, 'rom_work')
def sh(c, **k): return subprocess.run(c, shell=True, cwd=RW, capture_output=True, text=True, **k)
sh('rm -rf exefs_p && ../3dstool -xtfu exefs exefs.bin --exefs-dir exefs_p --header exefs_header_p.bin')
code = bytearray(open(os.path.join(RW, 'exefs_p/code.bin'), 'rb').read())
for r in sys.argv[1:]:
    a, b = [int(x, 16) for x in r.split('-')]
    for va in range(a, b, 4): struct.pack_into('<I', code, va - 0x100000, 0xE7F000F0)
open(os.path.join(RW, 'exefs_p/code.bin'), 'wb').write(code)
sh('../3dstool -ctf exefs exefs_p.bin --exefs-dir exefs_p --header exefs_header_p.bin --compress')
sh('../3dstool -ctf cxi game_p.cxi --header header.bin --exh exheader.bin --logo logo.bin --plain plain.bin --exefs exefs_p.bin --romfs romfs_fr.bin --not-encrypt')
sh('rm -rf /private/tmp/claude-501/zP; mkdir -p /private/tmp/claude-501/zP')
out = sh('zakuro game_p.cxi --interpreter --headless 400 --mute --rasterizer software --data /private/tmp/claude-501/zP 2>&1 | grep -v "^v[0-9]* = "').stdout
for l in out.split('\n'):
    if re.search(r'abort|fatal|undefined|Completed|CPU state|pc=|lr=|r1[0-4]|  r[0-9]', l): print(l[:200])
