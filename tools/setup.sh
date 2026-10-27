#!/bin/sh
# Prepares a checkout for building: checks the required tools and fetches LINKDATA-explorer into externals/.
set -e
cd "$(dirname "$0")/.."
mkdir -p externals work
ok=1
need() { if command -v "$1" >/dev/null 2>&1 || [ -x "externals/$1" ]; then echo "ok       $1"; else echo "MISSING  $1  ($2)"; ok=0; fi; }
need python3 "https://www.python.org"
for t in arm-none-eabi-gcc arm-none-eabi-ld arm-none-eabi-objcopy arm-none-eabi-nm; do need $t "brew install --cask gcc-arm-embedded, ou le paquet gcc-arm-none-eabi"; done
need 3dstool "https://github.com/dnasdw/3dstool : copier le binaire dans externals/"
need ctrtool "https://github.com/3DSGuy/Project_CTR : copier le binaire dans externals/"
command -v xdelta3 >/dev/null 2>&1 && echo "ok       xdelta3" || echo "optional xdelta3 (seulement pour fabriquer un patch de release)"
if [ ! -d externals/LINKDATA-explorer ]; then
  echo "clone    LINKDATA-explorer"
  git clone --depth 1 https://github.com/JulienGery/LINKDATA-explorer.git externals/LINKDATA-explorer
else echo "ok       externals/LINKDATA-explorer"; fi
[ "$ok" = 1 ] && echo "Pret : python3 tools/patch_rom.py ORIGINAL.cci sortie.cxi --verify" || { echo "Des outils manquent (voir ci-dessus)."; exit 1; }
