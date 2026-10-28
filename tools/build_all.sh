#!/bin/sh
# Rebuild the patched ROM from scratch. Needs: dotnet, ../3dstool, ../ctrtool, work/rom/romfs_dir (see PLAN).
set -e
cd "$(dirname "$0")"
if [ -f ../externals/fonts/ft_sml.xf ] && [ -f ../externals/fonts/ft_nrm.xf ]; then
  # regenerate the French atlas from the Yo-kai Watch 2 fonts (needs dotnet); UPDATE_ATLAS=1 also refreshes the prebuilt copy in atlas/
  EXTRA="$(python3 -I charset_from_translations.py)"
  DN=fontatlas/bin/Debug/net10.0/Level5FontAtlas.dll
  for f in sml nrm; do dotnet $DN ../externals/fonts/ft_$f.xf build/atlas_$f --chars "$EXTRA" | head -1; done
  python3 -I bake_french_atlas.py build/atlas_sml --name sml --cell 16 --cellh 16
  python3 -I bake_french_atlas.py build/atlas_nrm --name nrm --cell 16 --cellh 18
  if [ -n "$UPDATE_ATLAS" ]; then cp build/page_*.alpha build/page_*.png build/glyphs_*.json build/font_*.h ../data/atlas/; fi
else
  # no source fonts: use the prebuilt atlas shipped in atlas/
  python3 -I check_atlas.py
  mkdir -p build && cp ../data/atlas/page_*.alpha ../data/atlas/page_*.png ../data/atlas/glyphs_*.json ../data/atlas/font_*.h build/
fi
cp build/font_sml.h ../src/overrides/font_sml.h
python3 -I make_entry0.py ../work/rom/entry0/entry0.g1t build/entry0_fr.g1t
PYT=python3; [ -x ../work/venv/bin/python ] && PYT=../work/venv/bin/python   # venv (Pillow, numpy) : seulement requis pour les textures retouchées
[ -f ../work/rom/exefs_orig.bin ] || cp ../work/rom/exefs.bin ../work/rom/exefs_orig.bin       # exefs d'origine (jamais modifié)
cp ../work/rom/exefs_orig.bin ../work/rom/exefs.bin
../externals/3dstool -xtfu exefs ../work/rom/exefs.bin --exefs-dir ../work/rom/exefs_dir --header ../work/rom/exefs_header.bin >/dev/null
TEX="../translations/${FR_LANG:-fr}/textures"
if [ -z "$YOKAI_NO_ASSETS" ] && ls "$TEX"/12*_0.png >/dev/null 2>&1; then      # largeurs des plaques de noms (tableau de données du jeu) : voir tools/assets/patch_plate_table.py
  $PYT -I assets/patch_plate_table.py ../work/rom/exefs_dir/code.bin ../work/rom/exefs_dir/code.bin "$TEX"
  ../externals/3dstool -ctf exefs ../work/rom/exefs.bin --exefs-dir ../work/rom/exefs_dir --header ../work/rom/exefs_header.bin --compress >/dev/null
fi
python3 -I translation/lint_translation.py --strict | head -3
$PYT -I apply_translation.py build ../work/rom/romfs_dir/Data/LINKDATA_A.BIN build/LINKDATA_A.BIN
cd ../work/rom
rm -rf romfs_dir_fr && cp -Rc romfs_dir romfs_dir_fr
cp ../../tools/build/LINKDATA_A.BIN romfs_dir_fr/Data/LINKDATA_A.BIN
find romfs_dir_fr -name .DS_Store -delete
../../externals/3dstool -cvtf romfs romfs_fr.bin --romfs-dir romfs_dir_fr >/dev/null
../../externals/3dstool -cvtf cxi game_fr.cxi --header header.bin --exh exheader.bin --logo logo.bin --plain plain.bin --exefs exefs.bin --romfs romfs_fr.bin --not-encrypt >/dev/null
../../externals/ctrtool game_fr.cxi 2>&1 | grep -E "Crypto Key|Title id"
echo "OK -> work/rom/game_fr.cxi"
