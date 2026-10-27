#!/bin/sh
# One command to turn the translations into a patch: ORIGINAL dump -> patched .cci + .xdelta + SHA-256, in work/release/<lang>/.
# usage: tools/build.sh ORIGINAL.cci [fr|en|<lang>]        (default fr; the text comes from translations/<lang>/)
set -e
cd "$(dirname "$0")/.."
ROM="${1:?usage: tools/build.sh ORIGINAL.cci [lang]}"; L="${2:-fr}"
sh tools/setup.sh >/dev/null || { sh tools/setup.sh; exit 1; }
sh tools/check.sh "$L" | grep -E "ERROR|syntax|atlas" || true
sh tools/make_release.sh "$ROM" "work/release/$L" "$L"
echo
echo "Patch : work/release/$L/YokaiWatchSangokushi-$(echo "$L" | tr a-z A-Z).xdelta"
echo "A appliquer sur votre dump avec https://kotcrab.github.io/xdelta-wasm/ (voir README)"
