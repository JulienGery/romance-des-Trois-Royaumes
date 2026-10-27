"""Language selection for the pipeline: FR_LANG=fr (default) or another code (en, ...) whose TSVs live in
translations/<lang>/ (same layout as the SangoKuro TSVs, Sangokushi-script-Type[1-4].tsv, translated text in column 7 "Translated Text")."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = os.environ.get('FR_LANG', 'fr').lower()
TSV_DIR = os.path.join(ROOT, 'translations', LANG)
if not os.path.isdir(TSV_DIR):
    raise SystemExit(f'no translation for language {LANG!r}: {TSV_DIR} is missing (see tools/translation/translate_deepl.py)')
