#!/usr/bin/env python3
"""Check that the prebuilt French atlas (fr_patch/atlas) has a glyph for every non-ASCII character used by the translations."""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
need = set(subprocess.check_output([sys.executable, '-I', os.path.join(HERE, 'charset_from_translations.py')]).decode().strip())
have = set(chr(g['cp']) for f in ('sml', 'nrm') for g in json.load(open(os.path.join(HERE, 'atlas', f'glyphs_{f}.json')))['glyphs'])
missing = sorted(c for c in need - have if not '\ue000' <= c <= '\uf8ff')      # private-use codes are engine icons, not glyphs
if missing:
    sys.exit('prebuilt atlas lacks glyphs for: ' + ''.join(missing) + '\nProvide polices/ft_sml.xf and polices/ft_nrm.xf (Yo-kai Watch 2 fonts) to regenerate it.')
print('prebuilt atlas covers the translation charset')
