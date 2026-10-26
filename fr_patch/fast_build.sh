#!/bin/sh
# Incremental build of the recompiled library: recompiles ONLY overrides/*.c (a few seconds) and relinks the
# objects of the last full `3dsrecomp build`. A full build (2+ min) is needed only when the SET of overridden
# addresses changes (new/removed RECOMP_OVERRIDE(0x...)); this script detects that and tells you.
set -e
ID=000400000018B000
C="$HOME/Library/Caches/3dsrecomp/$ID"
OV="$(cd "$(dirname "$0")/../overrides" && pwd)"
cd "$C"
want=$(grep -ho 'RECOMP_OVERRIDE(0x[0-9A-Fa-f]*)' "$OV"/*.c | sed 's/.*(0x\(.*\))/\1/' | tr a-f A-F | sort -u)
have=$(grep -o 'override_0x[0-9A-F]*' entries.c | sed 's/override_0x//' | sort -u)
if [ "$want" != "$have" ]; then
  echo "overridden address set changed -> full build needed:"
  echo "  (cd 3dsrecomp && ./target/release/3dsrecomp build sangokushi.cci --overrides ../overrides)"
  exit 2
fi
for f in "$OV"/*.c; do
  b=$(basename "$f")
  cp "$f" "hand/$b"
  cc -O2 -ffp-contract=off -fno-math-errno -w -fPIC -fvisibility=hidden -I "$C" -c "hand/$b" -o "hand/${b%.c}.o" &
done
wait
cc -shared -o "$C/$ID.dylib" *.o hand/*.o 2>&1 | grep -v "reducing alignment" || true
cp "$C/$ID.dylib" "$HOME/Library/Application Support/3dsrecomp/$ID.dylib"
echo "fast build OK"
