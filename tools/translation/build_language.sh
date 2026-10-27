#!/bin/sh
# Whole pipeline for another language, from the Japanese texts to a release patch:
#   official Yo-kai names (wiki) -> DeepL translation (resumable, needs DEEPL_API_KEY) -> official names applied -> lint -> patch + xdelta
# usage: DEEPL_API_KEY=... tools/translation/build_language.sh LANG ORIGINAL.cci OUTDIR [ja|fr]      (source ja by default; fr = from the French translation)
# Stops with a clear message when the DeepL quota runs out: rerun the same command later, the cache keeps what was translated.
set -e
L="${1:?lang (en)}"; ROM="${2:?original dump}"; OUT="${3:?output dir}"; SRC="${4:-ja}"
cd "$(dirname "$0")/../.."
DIR="$L"; [ "$SRC" = "fr" ] && DIR="$L-from-fr"
[ -f translations/yokai_names_en.tsv ] || python3 tools/translation/yokai_names.py
GLOSS=""; [ -f "translations/glossary_$L.tsv" ] && [ "$SRC" = "ja" ] && GLOSS="--glossary translations/glossary_$L.tsv"
python3 tools/translation/translate_deepl.py --lang "$L" --source "$SRC" $GLOSS
python3 tools/translation/translate_deepl.py --lang "$L" --source "$SRC" --write-only
[ "$L" = "en" ] && python3 tools/translation/apply_names.py --lang "$DIR"
[ -f "translations/manual_$L.json" ] && python3 tools/translation/apply_manual.py --lang "$DIR"
python3 tools/translation/layout_text.py --lang "$DIR"      # spaces around tags + explicit line breaks (the dialogue windows do not wrap by themselves)
(cd tools && FR_LANG="$DIR" python3 -I translation/lint_translation.py | grep -E "issues|characters without")
tools/make_release.sh "$ROM" "$OUT" "$DIR"
