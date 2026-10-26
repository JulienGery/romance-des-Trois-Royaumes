"""Language selection for the pipeline: FR_LANG=fr (default, the TSVs of SangoKuro) or another code (en, ...) whose TSVs live in
translations/<lang>/ (same layout as SangoKuro/Sangokushi-script-Type[1-4].tsv, translated text in column 7 "Translated Text")."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = os.environ.get('FR_LANG', 'fr').lower()
GEN_DIR = os.path.join(ROOT, 'SangoKuro')                       # generator scripts + the French TSVs
TSV_DIR = GEN_DIR if LANG == 'fr' else os.path.join(ROOT, 'translations', LANG)
if not os.path.isdir(TSV_DIR):
    raise SystemExit(f'no translation for language {LANG!r}: {TSV_DIR} is missing (see fr_patch/translate_deepl.py)')
