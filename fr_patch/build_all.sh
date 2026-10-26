#!/bin/sh
# Rebuild the patched ROM from scratch. Needs: dotnet, ../3dstool, ../ctrtool, rom_work/romfs_dir (see PLAN).
set -e
cd "$(dirname "$0")"
if [ -f ../polices/ft_sml.xf ] && [ -f ../polices/ft_nrm.xf ]; then
  # regenerate the French atlas from the Yo-kai Watch 2 fonts (needs dotnet); UPDATE_ATLAS=1 also refreshes the prebuilt copy in atlas/
  EXTRA="$(python3 -I charset_from_translations.py)"
  DN=../polices/Level5FontAtlas/bin/Debug/net10.0/Level5FontAtlas.dll
  for f in sml nrm; do dotnet $DN ../polices/ft_$f.xf build/atlas_$f --chars "$EXTRA" | head -1; done
  python3 -I bake_french_atlas.py build/atlas_sml --name sml --cell 16 --cellh 16
  python3 -I bake_french_atlas.py build/atlas_nrm --name nrm --cell 16 --cellh 18
  if [ -n "$UPDATE_ATLAS" ]; then cp build/page_*.alpha build/page_*.png build/glyphs_*.json build/font_*.h atlas/; fi
else
  # no source fonts: use the prebuilt atlas shipped in atlas/
  python3 -I check_atlas.py
  mkdir -p build && cp atlas/page_*.alpha atlas/page_*.png atlas/glyphs_*.json atlas/font_*.h build/
fi
cp build/font_sml.h ../overrides/font_sml.h
python3 -I make_entry0.py ../rom_work/entry0/entry0.g1t build/entry0_fr.g1t
../3dstool -xtfu exefs ../rom_work/exefs.bin --exefs-dir ../rom_work/exefs_dir --header ../rom_work/exefs_header.bin >/dev/null
python3 -I lint_translation.py --strict | head -3
python3 -I apply_translation.py build ../rom_work/romfs_dir/Data/LINKDATA_A.BIN build/LINKDATA_A.BIN
cd ../rom_work
rm -rf romfs_dir_fr && cp -Rc romfs_dir romfs_dir_fr
cp ../fr_patch/build/LINKDATA_A.BIN romfs_dir_fr/Data/LINKDATA_A.BIN
find romfs_dir_fr -name .DS_Store -delete
../3dstool -cvtf romfs romfs_fr.bin --romfs-dir romfs_dir_fr >/dev/null
../3dstool -cvtf cxi game_fr.cxi --header header.bin --exh exheader.bin --logo logo.bin --plain plain.bin --exefs exefs.bin --romfs romfs_fr.bin --not-encrypt >/dev/null
../ctrtool game_fr.cxi 2>&1 | grep -E "Crypto Key|Title id"
echo "OK -> rom_work/game_fr.cxi"
