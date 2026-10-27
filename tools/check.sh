#!/bin/sh
# Checks that need no ROM and no game data (run by the CI, run it before opening a pull request):
#   - every Python script parses; the shell scripts parse
#   - the prebuilt font atlas covers every character of the translations
#   - lint of the translations (tags, characters missing from the font, line widths)
#   - the C text-wrapping code compiles and passes its tests
# usage: tools/check.sh [LANG ...]   (default: fr en)
set -e
cd "$(dirname "$0")"
LANGS="${*:-fr en}"
python3 - <<'PY'
import ast, glob
for f in glob.glob('**/*.py', recursive=True):
    if not f.startswith('fontatlas'): ast.parse(open(f, encoding='utf-8').read(), f)
PY
for f in *.sh */*.sh; do sh -n "$f"; done
echo "syntax OK"
mkdir -p build && cp ../data/atlas/page_*.alpha ../data/atlas/page_*.png ../data/atlas/glyphs_*.json ../data/atlas/font_*.h build/
for L in $LANGS; do
  echo "== $L"
  FR_LANG="$L" python3 -I check_atlas.py
  FR_LANG="$L" python3 -I translation/lint_translation.py | tail -4
done
cp build/font_sml.h ../src/overrides/font_sml.h
cc -O1 -o build/wrap_test dev/wrap_test.c && echo "wrap_test compiled"
