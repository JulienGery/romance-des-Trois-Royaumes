# Outils

Tous les scripts se lancent depuis n'importe quel dossier ; ils retrouvent la racine du dépôt eux-mêmes.

## Build

| Script | Rôle |
|---|---|
| `build.sh` | **commande principale** : dump + langue → `.xdelta` dans `work/release/<langue>/` |
| `translation/search.py` | retrouver une phrase dans les TSV |
| `setup.sh` | vérifie les outils nécessaires, clone `LINKDATA-explorer` dans `externals/` |
| `patch_rom.py` | **point d'entrée** : dump déchiffré → CXI/CCI traduit (`--lang`, `--verify`, `--cci`) |
| `build_all.sh` | atlas, traduction compilée dans `LINKDATA_A.BIN`, romfs |
| `build_arm_rom.sh`, `arm_patches.py`, `build_arm_native.py` | patchs ARM + moteur de texte natif compilé pour l'ARM11 |
| `apply_translation.py`, `patch_linkdata.py` | TSV → scripts → `LINKDATA_A.BIN` |
| `bake_french_atlas.py`, `make_entry0.py`, `g1t_tools.py`, `charset_from_translations.py`, `check_atlas.py` | police française et textures |
| `make_cci.py`, `make_release.sh`, `publish_release.sh` | CCI, patchs xdelta, publication GitHub |
| `fast_build.sh` | itération rapide sur les overrides avec le recompilateur `3dsrecomp` (développeur du moteur) |
| `check.sh` | vérifications sans ROM (utilisé par la CI) |

## Sous-dossiers

- `translation/` : `lint_translation.py`, `fix_translation_tags.py`, `scan_translation_issues.py`, DeepL (`translate_deepl.py`, `build_language.sh`), noms officiels (`yokai_names.py`, `apply_names.py`), `apply_manual.py`, `layout_text.py`.
- `dev/` : analyse du code mort et des cavités (`dead_code.py`, `cavity_*.py`, `make_trap_rom.sh`; nécessitent la décompilation Ghidra, non fournie), corpus de test de la coupe de lignes.
- `sangokuro/` : générateur de scripts du projet [SangoKuro](https://github.com/JulienGery/SangoKuro) (MIT, légèrement modifié).
- `fontatlas/` : outil .NET dérivé de Kuriimu2 (GPL-3.0) pour extraire les polices de Yo-kai Watch 2.
- `build/` *(ignoré)* : sorties intermédiaires.
