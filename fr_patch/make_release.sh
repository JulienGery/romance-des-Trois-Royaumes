#!/bin/sh
# Builds the files of a GitHub release from YOUR original dump: the patched CCI, the xdelta patch users apply to their own dump, the
# SHA-256 of the dump the patch expects, and the notes. Needs xdelta3 (brew install xdelta). usage: make_release.sh ORIGINAL.cci OUTDIR
set -e
ROM="$1"; OUT="$2"; [ -f "$ROM" ] && [ -n "$OUT" ] || { echo "usage: $0 ORIGINAL.cci OUTDIR"; exit 1; }
cd "$(dirname "$0")/.."
mkdir -p "$OUT"
python3 fr_patch/patch_rom.py "$ROM" "$OUT/french.cxi" --cci "$OUT/french.cci" --verify
rm -f "$OUT/french.cxi"
SRC_SHA=$(shasum -a 256 "$ROM" | cut -d' ' -f1)
xdelta3 -e -9 -f -B 1073741824 -s "$ROM" "$OUT/french.cci" "$OUT/YokaiWatchSangokushi-FR.xdelta"
# the patch must rebuild the patched CCI bit for bit
xdelta3 -d -f -s "$ROM" "$OUT/YokaiWatchSangokushi-FR.xdelta" "$OUT/check.cci"
cmp "$OUT/check.cci" "$OUT/french.cci" && rm "$OUT/check.cci" && echo "patch verified"
PATCHED_SHA=$(shasum -a 256 "$OUT/french.cci" | cut -d' ' -f1)
cat > "$OUT/SHA256.txt" <<EOT
original dump the patch expects : $SRC_SHA
patched result                  : $PATCHED_SHA
EOT
rm "$OUT/french.cci"
ls -la "$OUT"
