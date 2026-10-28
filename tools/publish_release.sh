#!/bin/sh
# Reconstruit les patchs FR et EN, puis publie la release GitHub avec les .xdelta (nécessite gh : brew install gh ; gh auth login).
# usage: tools/publish_release.sh vX.Y [ORIGINAL.cci]      (dump par défaut : externals/3dsrecomp/sangokushi.cci)
set -e
TAG="${1:?tag (ex. v1.1)}"; ROM="${2:-externals/3dsrecomp/sangokushi.cci}"
cd "$(dirname "$0")/.."
tools/make_release.sh "$ROM" work/release/fr fr
tools/make_release.sh "$ROM" work/release/en en
tools/make_release.sh "$ROM" work/release/fr-assets fr assets          # FR + textures retouchées (le patch FR sans assets est conservé)
NOTES=$(mktemp)
{ echo "Patchs xdelta à appliquer sur votre propre dump (voir le README)."; echo; echo '```'
  echo "FR: $(grep patched work/release/fr/SHA256.txt | sed 's/.*: //')"; echo "FR assets: $(grep patched work/release/fr-assets/SHA256.txt | sed 's/.*: //')"; echo "EN: $(grep patched work/release/en/SHA256.txt | sed 's/.*: //')"
  echo "dump attendu: $(grep original work/release/fr/SHA256.txt | sed 's/.*: //')"; echo '```'; } > "$NOTES"
git tag "$TAG" 2>/dev/null || true
git push origin "$TAG"      # le workflow crée la release ; on la complète ensuite
for i in 1 2 3 4 5 6; do gh release view "$TAG" >/dev/null 2>&1 && break || sleep 5; done
gh release view "$TAG" >/dev/null 2>&1 || gh release create "$TAG" --title "$TAG" --notes-file "$NOTES"
gh release edit "$TAG" --notes-file "$NOTES"
gh release upload "$TAG" work/release/fr/YokaiWatchSangokushi-FR.xdelta work/release/fr-assets/YokaiWatchSangokushi-FR-assets.xdelta work/release/en/YokaiWatchSangokushi-EN.xdelta --clobber
rm -f "$NOTES"; echo "release $TAG publiée"
