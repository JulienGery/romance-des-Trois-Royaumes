#!/usr/bin/env python3
"""Compile the translation TSVs into script files (tools/sangokuro generator, from SangoKuro) and patch them, plus LINKDATA entry 0, into
LINKDATA_A.BIN without extracting/rebuilding the whole archive.
  apply_translation.py check             : round-trip test: generate from ORIGINAL texts and compare with the entries of the game
  apply_translation.py build SRC DST     : SRC = original LINKDATA_A.BIN, DST = patched archive (scripts + entry0_fr.g1t)
"""
import importlib.util, os, re, shutil, sys, csv, io, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); SK = os.path.join(HERE, 'sangokuro')   # SK = generator script (from SangoKuro, MIT)
sys.path.insert(0, HERE); from langcfg import TSV_DIR; sys.path.insert(0, os.path.join(HERE, '..', 'externals', 'LINKDATA-explorer'))
from linkdata_engine import LinkDataArchive
from patch_linkdata import patch_many

def load_gen():
    sp = importlib.util.spec_from_file_location('sgen', os.path.join(SK, 'Sangokushi-GenerateTranslatedFiles.py'))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m

def generate(tsv_dir, out_dir):
    """run the generator with cwd = tsv_dir (it reads Sangokushi-script-Type*.tsv from the cwd)"""
    m = load_gen(); cwd = os.getcwd(); os.makedirs(out_dir, exist_ok=True)
    try:
        os.chdir(tsv_dir)
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            for f in (m.type1recompile, m.type2recompile, m.type3recompile, m.type4recompile): f(out_dir)
    finally: os.chdir(cwd)
    return {int(n.split('-')[0]): (n, open(os.path.join(out_dir, n), 'rb').read()) for n in os.listdir(out_dir) if n.endswith('.script')}

def type3_same(ref, gen):
    """Type 3: compare header, offsets and every string up to its NUL (the original padding bytes after the NUL are leftovers)"""
    import struct
    if ref[:8] != gen[:8]: return False
    n = struct.unpack('<I', ref[4:8])[0]
    if ref[8:8 + 4 * n] != gen[8:8 + 4 * n]: return False
    offs = list(struct.unpack('<%dI' % n, ref[8:8 + 4 * n])) + [len(ref)]
    return all(ref[offs[i]:offs[i + 1]].split(b'\0')[0] == gen[offs[i]:offs[i + 1]].split(b'\0')[0] for i in range(n))

def original_tsvs(dst):
    """copy of the TSVs with the translation column emptied -> generator falls back to the original text"""
    os.makedirs(dst, exist_ok=True)
    for t in range(1, 5):
        raw = open(os.path.join(TSV_DIR, f'Sangokushi-script-Type{t}.tsv'), encoding='utf-8', newline='').read()
        rows = list(csv.reader(io.StringIO(raw, newline=''), delimiter='\t'))
        for r in rows[1:]:
            if len(r) > 6: r[6] = ''
        out = io.StringIO(newline=''); csv.writer(out, delimiter='\t', lineterminator='\r\n').writerows(rows)
        open(os.path.join(dst, f'Sangokushi-script-Type{t}.tsv'), 'w', encoding='utf-8', newline='').write(out.getvalue())

if __name__ == '__main__':
    mode = sys.argv[1]; tmp = os.path.join(HERE, 'build', 'translated')
    arch_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '..', 'work', 'rom', 'romfs_dir', 'Data', 'LINKDATA_A.BIN')
    if mode == 'check':
        shutil.rmtree(tmp + '_orig', ignore_errors=True); original_tsvs(tmp + '_orig_tsv')
        gen = generate(tmp + '_orig_tsv', tmp + '_orig'); a = LinkDataArchive(arch_path)
        ok = bad = pad_only = t3_same = 0; bad_list = []
        for idx, (name, data) in sorted(gen.items()):
            ref = a.read_entry_decompressed(idx)
            if ref == data: ok += 1
            elif len(ref) == len(data) and 16112 <= idx <= 16131 and type3_same(ref, data): t3_same += 1
            elif ref[:len(data)] == data and not any(ref[len(data):]) and len(ref) - len(data) < 32: pad_only += 1
            else: bad += 1; bad_list.append((idx, name, len(ref), len(data)))
        print(f'round trip (original text -> generator): {ok} identical, {pad_only} identical except trailing zero padding, {t3_same} Type3 identical except garbage in the inter-string padding, {bad} different, of {len(gen)}')
        for b in bad_list[:8]: print('  differs', b)
    elif mode == 'build':
        dst = sys.argv[3]; shutil.rmtree(tmp, ignore_errors=True)
        gen = generate(TSV_DIR, tmp); a = LinkDataArchive(arch_path); items = {}
        for idx, (name, data) in gen.items():
            marker = name.split('-')[1]; e = a.entries[idx]
            assert (marker == 'X') == e.is_compressed, f'{name}: marker does not match the archive entry'
            items[idx] = (data, e.is_compressed)
        e0 = os.path.join(HERE, 'build', 'entry0_fr.g1t')
        if os.path.exists(e0): items[0] = (open(e0, 'rb').read(), True)
        n = patch_many(arch_path, dst, items)
        print(f'{n} entries patched ({len(gen)} scripts' + (' + entry 0 font atlas' if 0 in items else '') + f') -> {dst} ({os.path.getsize(dst)/1e6:.1f} MB)')
