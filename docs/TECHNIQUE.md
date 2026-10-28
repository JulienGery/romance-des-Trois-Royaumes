# Documentation technique

Compiler soi-même le patch de traduction (le README principal ne couvre que l'installation via le patch xdelta).

Pour reconstruire le patch xdelta distribué en release : `tools/make_release.sh ORIGINAL.cci dossier_de_sortie`.

Patch de traduction française pour **Yo-kai Watch Sangokushi** (titre `000400000018B000`, version japonaise). Pour compiler soi-même : une seule commande transforme **votre dump déchiffré** de la ROM japonaise en un CXI français :

```bash
python3 tools/patch_rom.py ORIGINAL.cci FRANCAIS.cxi --verify
```

Ce dépôt **ne contient ni ROM, ni exécutable, ni police du jeu** : il faut fournir votre propre dump (voir « Mentions » pour les deux seuls éléments dérivés du jeu).

## Ce que fait le patch
- **Textes** : les 1 308 scripts traduits (TSV de `translations/fr/`, format du projet [SangoKuro](https://github.com/JulienGery/SangoKuro)) sont recompilés dans `LINKDATA_A.BIN`.
- **Police française** à chasse variable (accents, `« »`, `œ`…), ajoutée à l'atlas de police du jeu. L'atlas est **fourni pré-construit** dans `data/atlas/` (aucune police source à extraire). Pour le régénérer (nouveaux caractères dans la traduction) : placer les polices de Yo-kai Watch 2 `polices/ft_sml.xf` et `ft_nrm.xf`, installer `dotnet`, construire `tools/fontatlas`, puis `UPDATE_ATLAS=1 sh tools/build_all.sh` ; sans ces polices, `check_atlas.py` vérifie que l'atlas fourni couvre tous les caractères de la traduction.
- **Moteur de texte natif ARM** (`src/overrides/`, `src/arm/`) : avance variable, retour à la ligne français avec reflow et équilibrage, adaptation des fenêtres, bulles (dialogue et combat), textes centrés et bannières. Le code C est compilé pour l'ARM11 (`arm-none-eabi-gcc`, Thumb/ARM), placé dans du code mort de l'exécutable, et accroché par des branchements (`tools/build_arm_native.py`). Aucune bibliothèque recompilée n'est nécessaire.

Détails techniques, faits vérifiés et limites : [`dev/JOURNAL_MODIFICATIONS.md`](dev/JOURNAL_MODIFICATIONS.md) (spécification de chaque modification), [`dev/HANDOVER.md`](dev/HANDOVER.md) (état du projet, commandes, pièges).

## Prérequis
- Python 3, `arm-none-eabi-gcc/ld/objcopy/nm` (`dotnet` seulement pour régénérer l'atlas de police), `xdelta3` pour fabriquer un patch de release.
- [`3dstool`](https://github.com/dnasdw/3dstool) et [`ctrtool`](https://github.com/3DSGuy/Project_CTR) dans `externals/` (binaires non fournis).
- [`LINKDATA-explorer`](https://github.com/JulienGery/LINKDATA-explorer) dans `externals/`.
- Une ROM **déchiffrée** (`.cci`/`.3ds`/`.cxi`).

`tools/setup.sh` vérifie tout cela, clone `LINKDATA-explorer` au bon endroit et dit ce qui manque. Le générateur de scripts du projet SangoKuro (MIT) est inclus dans `tools/sangokuro/`.

## Utilisation et état
Le CXI produit démarre dans Zakuro (`--interpreter`) et dans Azahar ; textes, bulles de combat, bannières et écrans d'introduction ont été vérifiés visuellement dans l'émulateur. **Pas testé sur une vraie console** : le CXI n'est pas signé et l'exheader est modifié (`.bss` agrandi), il faut le convertir en CIA et l'installer avec des patchs de signature.

Outils de développement (nécessitent la décompilation Ghidra du jeu, non fournie) : `tools/dev/dead_code.py`, `cavity_search.py`, `cavity_update.py`, `make_trap_rom.sh` (recherche et vérification du code mort réutilisé comme cavité). Le résultat est versionné dans `data/cavities.json`.

## Autres langues (anglais via DeepL)
Le pipeline accepte d'autres langues : `FR_LANG` / `--lang` choisit le dossier de TSV (`translations/<langue>/`, même format que SangoKuro ; le français est dans `translations/fr/`). `tools/translation/translate_deepl.py` produit ces TSV avec DeepL **à partir du japonais** (pas du français) :
```bash
DEEPL_API_KEY=... python3 tools/translation/translate_deepl.py --lang en --glossary translations/glossary_en.example.tsv   # --dry-run pour compter, --mock pour tester sans clé
python3 tools/patch_rom.py ORIGINAL.cci ANGLAIS.cxi --lang en --cci ANGLAIS.cci
tools/make_release.sh ORIGINAL.cci sortie en            # patch xdelta YokaiWatchSangokushi-EN.xdelta
```
**Pipeline automatique** : `DEEPL_API_KEY=... tools/translation/build_language.sh en ORIGINAL.cci sortie [ja|fr]` enchaîne noms officiels des Yo-kai, traduction DeepL (reprenable, s'arrête proprement quand le quota est épuisé), application des noms, contrôle de qualité et patch xdelta.

**Noms officiels des Yo-kai** : `tools/translation/yokai_names.py` récupère les noms anglais officiels sur le [Yo-kai Watch Wiki](https://yokaiwatch.fandom.com) (texte sous licence CC BY-SA ; 2 781 paires japonais/anglais dans `translations/yokai_names_en.tsv`). `tools/translation/apply_names.py` les applique : les lignes de la table des noms du jeu (celle qu'utilisent les variables `【Yk…】`) reçoivent le nom officiel, et dans les phrases le rendu automatique d'un nom est remplacé quand le japonais de la phrase le contient. Les Yo-kai propres à *Sangokushi* n'ont pas de nom officiel : ils restent traduits par DeepL.

Les balises du jeu (couleurs, noms de variables) sont protégées et contrôlées une à une ; en cas de perte, le texte est retraduit morceau par morceau. Environ 20 500 textes uniques (≈ 390 000 caractères) : le forfait gratuit de DeepL (500 000 caractères par mois) suffit. La clé d'API reste dans l'environnement, jamais dans le dépôt. Les traductions sont mises en cache (`translations/<langue>/.cache.json`), l'exécution est reprenable. Une relecture humaine reste nécessaire.

## Pack de textures haute résolution (optionnel, Azahar)

`tools/assets/build_hires_pack.py` et `build_hires_font.py` génèrent un pack de textures agrandies (Upscayl, polices FR/EN redessinées en vectoriel) à copier dans `load/textures/` d'Azahar : l'archive du jeu n'est pas modifiée. Méthode, pièges et limites : `tools/assets/README.md` (« Pack HD »).

## Mentions
Projet de fan non officiel. *Yo-kai Watch* est une marque de LEVEL-5. Aucune donnée du jeu n'est incluse, **à deux exceptions près** : (1) l'atlas de police pré-construit (`data/atlas/`) contient des glyphes dérivés des polices de Yo-kai Watch 2 (LEVEL-5), fournis pour éviter à chacun d'extraire ces polices ; (2) les TSV de `translations/` contiennent, en colonne « Original Text », le texte japonais du jeu, nécessaire pour retrouver chaque phrase ; à retirer si le détenteur des droits le demande. `tools/fontatlas` est dérivé de [Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2) et reste sous **GPL-3.0** (voir `tools/fontatlas/NOTICE.md` et `LICENSE`). Aucune licence n'a encore été choisie pour le reste du code de ce dépôt.
