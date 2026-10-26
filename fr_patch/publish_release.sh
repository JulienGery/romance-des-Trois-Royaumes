#!/bin/sh
# Reconstruit les patchs FR et EN, puis publie la release GitHub avec les .xdelta (nécessite gh : brew install gh ; gh auth login).
# usage: fr_patch/publish_release.sh vX.Y [ORIGINAL.cci]      (dump par défaut : 3dsrecomp/sangokushi.cci)
set -e
TAG="${1:?tag (ex. v1.1)}"; ROM="${2:-3dsrecomp/sangokushi.cci}"
cd "$(dirname "$0")/.."
fr_patch/make_release.sh "$ROM" release/fr fr
fr_patch/make_release.sh "$ROM" release/en en
NOTES=$(mktemp)
{ echo "Patchs xdelta à appliquer sur votre propre dump (voir le README)."; echo; echo '```'
  echo "FR: $(grep patched release/fr/SHA256.txt | sed 's/.*: //')"; echo "EN: $(grep patched release/en/SHA256.txt | sed 's/.*: //')"
  echo "dump attendu: $(grep original release/fr/SHA256.txt | sed 's/.*: //')"; echo '```'; } > "$NOTES"
git tag "$TAG" 2>/dev/null || true
git push origin "$TAG"      # le workflow crée la release ; on la complète ensuite
for i in 1 2 3 4 5 6; do gh release view "$TAG" >/dev/null 2>&1 && break || sleep 5; done
gh release view "$TAG" >/dev/null 2>&1 || gh release create "$TAG" --title "$TAG" --notes-file "$NOTES"
gh release edit "$TAG" --notes-file "$NOTES"
gh release upload "$TAG" release/fr/YokaiWatchSangokushi-FR.xdelta release/en/YokaiWatchSangokushi-EN.xdelta --clobber
rm -f "$NOTES"; echo "release $TAG publiée"
