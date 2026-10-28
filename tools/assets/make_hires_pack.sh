#!/bin/sh
# Produit le pack de textures HD pour Azahar en une commande (prêt à publier : GameBanana, etc.) — rien de ce pack n'est versionné,
# il se reconstruit depuis VOTRE dump. Relancer après chaque changement de traduction des textures (translations/<langue>/textures).
#
# usage: tools/assets/make_hires_pack.sh [--light] [--font POLICE.ttc] [--langs fr,en] [--out DOSSIER] [--dry-run]
#   --light     variante allégée (ignore les grandes textures à transparence) pour AYN Thor et consoles portables
#   --langs     langues dont on ajoute les textures traduites et la police (défaut : fr). Le LINKDATA traduit doit exister :
#               fr -> work/rom/romfs_dir_fr/Data/LINKDATA_A.BIN (tools/build_all.sh) ; autre langue : build_all.sh avec FR_LANG=<langue> écrit aussi dans
#               romfs_dir_fr, donc le copier en work/rom/romfs_dir_<langue> avant de relancer ce script
#   --font      police vectorielle des glyphes (défaut : Helvetica du système ; pour diffuser, une police libre : Liberation Sans, Arimo)
#   --dry-run   ne lance pas Upscayl (compte seulement) et ne crée pas l'archive
# Prérequis : work/venv (pillow numpy opencv-python cityhash), Upscayl dans /Applications, work/rom/romfs_dir (dump japonais extrait), dotnet pour les langues autres que fr.
set -e
cd "$(dirname "$0")/../.."
OUT=work/hires_pack; LANGS=fr; LIGHT=; FONT=; DRY=
while [ $# -gt 0 ]; do case "$1" in
  --light) LIGHT=--light ;; --dry-run) DRY=--dry-run ;;
  --font) FONT="--font $2"; shift ;; --langs) LANGS="$2"; shift ;; --out) OUT="$2"; shift ;;
  *) echo "option inconnue : $1"; exit 1 ;; esac; shift; done
PY=work/venv/bin/python; [ -x $PY ] || PY=python3
TID=000400000018B000
[ -z "$DRY" ] && rm -rf "$OUT/$TID" "$OUT/_work"

echo "== textures du jeu japonais (G1T, G1T embarqués, BFLIM)"
$PY tools/assets/build_hires_pack.py --out "$OUT" $LIGHT $DRY
for L in $(echo "$LANGS" | tr ',' ' '); do
  LD=work/rom/romfs_dir_$L/Data/LINKDATA_A.BIN
  [ -f "$LD" ] || { echo "!! $LD absent : construire la ROM avec FR_LANG=$L (tools/build_all.sh) puis copier work/rom/romfs_dir_fr en work/rom/romfs_dir_$L — langue $L ignorée"; continue; }
  echo "== textures traduites ($L)"
  $PY tools/assets/build_hires_pack.py --out "$OUT" --linkdata "$LD" $LIGHT $DRY
  echo "== police ($L)"
  if [ "$L" = fr ]; then $PY tools/assets/build_hires_font.py --out "$OUT" $FONT; else $PY tools/assets/build_hires_font.py --out "$OUT" --bake-lang "$L" $FONT; fi
done

[ -n "$DRY" ] && { echo "(dry-run : pas d'archive)"; exit 0; }
cat > "$OUT/LISEZMOI.txt" <<TXT
Pack de textures haute résolution — Yo-kai Watch Sangokushi (Azahar)

1. Copiez le dossier $TID dans le dossier « load/textures » d'Azahar
   (macOS : ~/Library/Application Support/Azahar/load/textures/ ; Windows : %APPDATA%/Azahar/load/textures/ ; Android : dossier Azahar/load/textures/).
2. Azahar > Émulation > Configurer > Graphismes > Utilitaires : cocher « Utiliser des textures personnalisées » (laisser le préchargement désactivé).
3. Les textures sont agrandies par IA (Real-ESRGAN, Upscayl) ; les polices française et anglaise sont redessinées en vectoriel.
Le pack remplace les textures par leur empreinte : il fonctionne avec la ROM japonaise et avec les patchs de traduction du projet.
TXT
ZIP="$OUT/YokaiWatchSangokushi-HD-Pack${LIGHT:+-light}.zip"
rm -f "$ZIP"; (cd "$OUT" && zip -qr "$(basename "$ZIP")" "$TID" LISEZMOI.txt)
ls -lh "$ZIP" | awk '{print "archive : "$9" ("$5")"}'
