#!/usr/bin/env python3
"""One-shot French patcher for Yo-kai Watch Sangokushi (3DS, title 000400000018B000).

    patch_rom.py ORIGINAL.cci|.3ds|.cxi  FRENCH.cxi  [--cci FRENCH.cci] [--verify] [--skip-extract]

Input must be a DECRYPTED dump of the Japanese game (what 3dstool/ctrtool can read without keys).
Output is a CXI that needs no emulator support: French text data (scripts, font atlas) + native ARM patches in the executable
(French font engine, line breaking, windows, bubbles; see docs/dev/JOURNAL_MODIFICATIONS.md). It runs in Zakuro/Citra-style emulators
and, once converted to a CIA (makerom) and installed with signature patches, on a modded console.

Other languages: `--lang en` uses translations/en/ (made by tools/translation/translate_deepl.py).
Stages: extract -> French font atlas -> translated scripts into LINKDATA_A.BIN -> ARM code (cavities + hooks + bss) -> repack.
Needs: 3dstool, ctrtool, python3, arm-none-eabi-gcc/ld/objcopy/nm (dotnet + externals/fonts/ft_*.xf only to regenerate the font atlas; a prebuilt one is in data/atlas)."""
import argparse, hashlib, os, re, shutil, struct, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); RW = os.path.join(ROOT, 'work', 'rom')
TITLE = '000400000018b000'

def run(cmd, **k):
    print('+', cmd if isinstance(cmd, str) else ' '.join(cmd), flush=True)
    return subprocess.run(cmd, shell=isinstance(cmd, str), check=True, **k)

def need(tool):
    if not shutil.which(tool) and not os.path.exists(os.path.join(ROOT, 'externals', tool)): sys.exit(f'missing tool: {tool}')

def extract(rom):
    os.makedirs(RW, exist_ok=True)
    cxi = os.path.join(RW, 'original.cxi')
    if rom.lower().endswith(('.cci', '.3ds')):
        run([os.path.join(ROOT, 'externals', '3dstool'), '-xvt01f', 'cci', cxi, os.path.join(RW, '1.cfa'), rom, '--header', os.path.join(RW, 'ncsd_header.bin')], stdout=subprocess.DEVNULL)
    else:
        shutil.copyfile(rom, cxi)
    run([os.path.join(ROOT, 'externals', '3dstool'), '-xvtf', 'cxi', cxi, '--header', os.path.join(RW, 'header.bin'), '--exh', os.path.join(RW, 'exheader.bin'),
         '--logo', os.path.join(RW, 'logo.bin'), '--plain', os.path.join(RW, 'plain.bin'), '--exefs', os.path.join(RW, 'exefs.bin'),
         '--romfs', os.path.join(RW, 'romfs.bin')], stdout=subprocess.DEVNULL)
    shutil.copyfile(os.path.join(RW, 'exefs.bin'), os.path.join(RW, 'exefs_orig.bin'))     # exefs d'origine, base de build_all.sh
    hdr = open(os.path.join(RW, 'header.bin'), 'rb').read(0x200)
    if hdr[0x100:0x104] != b'NCCH': sys.exit('not an NCCH: is the dump decrypted?')
    tid = struct.pack('<Q', struct.unpack_from('<Q', hdr, 0x118)[0])[::-1].hex()
    if tid != TITLE: sys.exit(f'unexpected title id {tid} (expected {TITLE})')
    shutil.rmtree(os.path.join(RW, 'romfs_dir'), ignore_errors=True)
    run([os.path.join(ROOT, 'externals', '3dstool'), '-xvtf', 'romfs', os.path.join(RW, 'romfs.bin'), '--romfs-dir', os.path.join(RW, 'romfs_dir')], stdout=subprocess.DEVNULL)
    # font atlas entry (entry 0 of LINKDATA_A.BIN) as the base of the French atlas
    sys.path.insert(0, os.path.join(ROOT, 'externals', 'LINKDATA-explorer'))
    from linkdata_engine import LinkDataArchive
    a = LinkDataArchive(os.path.join(RW, 'romfs_dir', 'Data', 'LINKDATA_A.BIN'))
    os.makedirs(os.path.join(RW, 'entry0'), exist_ok=True)
    open(os.path.join(RW, 'entry0', 'entry0.g1t'), 'wb').write(a.read_entry_decompressed(0))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('rom'); ap.add_argument('out')
    ap.add_argument('--lang', default='fr', help='fr (default, translations/fr) or another language whose TSVs are in translations/<lang>/ (see translate_deepl.py)')
    ap.add_argument('--cci', help='also write a patched CCI (same container as the input dump) to this path; needs a CCI/3DS input')
    ap.add_argument('--verify', action='store_true', help='boot the result in zakuro --interpreter (pure ARM, no recompiled library)')
    ap.add_argument('--skip-extract', action='store_true', help='reuse work/rom/ from a previous run')
    a = ap.parse_args(); os.environ['FR_LANG'] = a.lang
    for t in ('3dstool', 'ctrtool', 'arm-none-eabi-gcc', 'arm-none-eabi-ld', 'arm-none-eabi-objcopy', 'arm-none-eabi-nm'): need(t)
    if os.path.exists(os.path.join(ROOT, 'externals', 'fonts', 'ft_sml.xf')): need('dotnet')          # only to regenerate the atlas; a prebuilt one is in data/atlas
    if not a.skip_extract: extract(os.path.abspath(a.rom))
    run(['sh', os.path.join(HERE, 'build_all.sh')], stdout=subprocess.DEVNULL)          # atlas + translated LINKDATA + romfs_fr.bin
    run(['sh', os.path.join(HERE, 'build_arm_rom.sh')])                                # native ARM code + exheader + game_arm.cxi
    shutil.copyfile(os.path.join(RW, 'game_arm.cxi'), a.out)
    if a.cci:
        run([sys.executable, os.path.join(HERE, 'make_cci.py'), os.path.join(RW, 'ncsd_header.bin'), os.path.join(RW, 'game_arm.cxi'), os.path.join(RW, '1.cfa'), a.cci])
    h = hashlib.sha256(open(a.out, 'rb').read()).hexdigest()
    print(f'\nwritten {a.out} ({os.path.getsize(a.out) // 2**20} MiB, sha256 {h[:16]}...)')
    if a.verify:
        shutil.rmtree(os.path.join(RW, 'verify_data'), ignore_errors=True)          # fresh save data: comparable numbers
        r = subprocess.run(['zakuro', a.out, '--interpreter', '--headless', '1500', '--mute', '--rasterizer', 'software', '--data', os.path.join(RW, 'verify_data')],
                           capture_output=True, text=True)
        m = re.search(r'(\d+) threads .*?(\d+) draws', r.stdout + r.stderr)
        print('verify:', 'FATAL ' + re.findall(r'fatal errors: .*', r.stdout + r.stderr)[0] if 'fatal errors' in r.stdout + r.stderr else f'boot OK ({m.group(1)} threads, {m.group(2)} draws)' if m else 'no report')

if __name__ == '__main__':
    main()
