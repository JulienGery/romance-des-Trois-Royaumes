#!/usr/bin/env python3
"""ARM patch table for the executable (ExeFS code.bin == the ELF .text/.rodata/.data image, vaddr 0x100000 = offset 0).
Every entry checks the ORIGINAL bytes before patching, so a wrong ROM/version is refused.
Usage: arm_patches.py <code.bin in> <code.bin out>
Keep this table in sync with rapport/JOURNAL_MODIFICATIONS.md."""
import struct, sys
BASE = 0x100000
PATCHES = [
    # (vaddr, original u32, new u32, description)
    # A1 (font init `str r6,[r4,#0x214]` -> `str r8,...`, ASCII flag permanently 1) is DISABLED: with the flag set during boot the
    # engine measures/draws through tables that are not ready yet (null font accesses, game never reaches its first frame in the
    # interpreter). The native hooks set the flag themselves (fr_init() in the 0x52D340 and measure hooks).
]
def apply(data: bytearray):
    for va, old, new, desc in PATCHES:
        off = va - BASE
        cur = struct.unpack_from('<I', data, off)[0]
        if cur == new: print('already patched', hex(va)); continue
        assert cur == old, f'{va:#x}: expected {old:#010x}, found {cur:#010x}'
        struct.pack_into('<I', data, off, new); print('patched', hex(va), desc[:70])
if __name__ == '__main__':
    d = bytearray(open(sys.argv[1], 'rb').read()); apply(d); open(sys.argv[2], 'wb').write(d)
