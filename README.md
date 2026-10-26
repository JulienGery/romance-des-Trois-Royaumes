# Romance des Trois Royaumes — traduction française de *Yo-kai Watch Sangokushi* (3DS)

## Installer le patch (sans rien compiler)
1. Télécharger `YokaiWatchSangokushi-FR.xdelta` (≈ 4 Mo) dans la section **Releases**.
2. Avoir **son propre dump déchiffré** de la version japonaise, au format `.cci`, **non chiffré** (lisible par `3dstool`/`ctrtool` sans clés). Le patch ne s'applique qu'à ce dump exact : **SHA-256 attendu** `8776733296fb2f984e86102c834693b952aeae62789b4a584320c4fec359a453`.
3. L'appliquer avec n'importe quel outil xdelta (GUI : *Delta Patcher*, *xdelta UI* ; ligne de commande ci-dessous) :
   ```bash
   xdelta3 -d -s yokai-sangokushi.cci YokaiWatchSangokushi-FR.xdelta yokai-sangokushi-FR.cci
   ```
   Le résultat doit avoir le SHA-256 `4a365b26600df577214bb0a950a573e4459731050f982c7fbcb9efd34d6dbbd6`.
4. Lancer `yokai-sangokushi-FR.cci` dans un émulateur (testé : Azahar avec le CXI équivalent, Zakuro avec ce CCI). Sur console : conversion en CIA et signature patchée nécessaires (non testé).

Le patch ne contient que les différences avec le dump d'origine (aucune ROM complète). Pour le reconstruire soi-même : `fr_patch/make_release.sh ORIGINAL.cci dossier_de_sortie`.

Patch de traduction française pour **Yo-kai Watch Sangokushi** (titre `000400000018B000`, version japonaise). Pour compiler soi-même : une seule commande transforme **votre dump déchiffré** de la ROM japonaise en un CXI français :

```bash
python3 fr_patch/patch_rom.py ORIGINAL.cci FRANCAIS.cxi --verify
```

Ce dépôt **ne contient aucune donnée du jeu** (ni ROM, ni exécutable, ni police) : il faut fournir votre propre dump.

## Ce que fait le patch
- **Textes** : les 1 308 scripts traduits (projet [SangoKuro](https://github.com/JulienGery/SangoKuro), TSV) sont recompilés dans `LINKDATA_A.BIN`.
- **Police française** à chasse variable (accents, `« »`, `œ`…), ajoutée à l'atlas de police du jeu. L'atlas est **fourni pré-construit** dans `fr_patch/atlas/` (aucune police source à extraire). Pour le régénérer (nouveaux caractères dans la traduction) : placer les polices de Yo-kai Watch 2 `polices/ft_sml.xf` et `ft_nrm.xf`, installer `dotnet`, construire `polices/Level5FontAtlas`, puis `UPDATE_ATLAS=1 sh fr_patch/build_all.sh` ; sans ces polices, `check_atlas.py` vérifie que l'atlas fourni couvre tous les caractères de la traduction.
- **Moteur de texte natif ARM** (`overrides/`, `fr_arm/`) : avance variable, retour à la ligne français avec reflow et équilibrage, adaptation des fenêtres, bulles (dialogue et combat), textes centrés et bannières. Le code C est compilé pour l'ARM11 (`arm-none-eabi-gcc`, Thumb/ARM), placé dans du code mort de l'exécutable, et accroché par des branchements (`fr_patch/build_arm_native.py`). Aucune bibliothèque recompilée n'est nécessaire.

Détails techniques, faits vérifiés et limites : [`rapport/JOURNAL_MODIFICATIONS.md`](rapport/JOURNAL_MODIFICATIONS.md) (spécification de chaque modification), [`rapport/HANDOVER.md`](rapport/HANDOVER.md) (état du projet, commandes, pièges).

## Prérequis
- Python 3, `arm-none-eabi-gcc/ld/objcopy/nm` (`dotnet` seulement pour régénérer l'atlas de police).
- [`3dstool`](https://github.com/dnasdw/3dstool) et [`ctrtool`](https://github.com/3DSGuy/Project_CTR) à la racine du dépôt (binaires non fournis).
- À côté de `fr_patch/` : les dépôts [`SangoKuro`](https://github.com/JulienGery/SangoKuro) et [`LINKDATA-explorer`](https://github.com/JulienGery/LINKDATA-explorer). Les modifications apportées à SangoKuro (générateurs + TSV) sont fournies sous forme de patch : `cd SangoKuro && git apply ../patches/SangoKuro-fr.patch`.
- Une ROM **déchiffrée** (`.cci`/`.3ds`/`.cxi`).

## Utilisation et état
Le CXI produit démarre dans Zakuro (`--interpreter`) et dans Azahar ; textes, bulles de combat, bannières et écrans d'introduction ont été vérifiés visuellement dans l'émulateur. **Pas testé sur une vraie console** : le CXI n'est pas signé et l'exheader est modifié (`.bss` agrandi), il faut le convertir en CIA et l'installer avec des patchs de signature.

Outils de développement (nécessitent la décompilation Ghidra du jeu, non fournie) : `fr_patch/dead_code.py`, `cavity_search.py`, `cavity_update.py`, `make_trap_rom.sh` (recherche et vérification du code mort réutilisé comme cavité). Le résultat est versionné dans `fr_patch/cavities.json`.

## Mentions
Projet de fan non officiel. *Yo-kai Watch* est une marque de LEVEL-5. Aucune donnée du jeu n'est incluse, **à une exception près** : l'atlas de police pré-construit (`fr_patch/atlas/`) contient des glyphes dérivés des polices de Yo-kai Watch 2 (LEVEL-5), fournis pour éviter à chacun d'extraire ces polices ; à retirer si le détenteur des droits le demande. `polices/Level5FontAtlas` est dérivé de [Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2) et reste sous **GPL-3.0** (voir `polices/Level5FontAtlas/NOTICE.md` et `LICENSE`). Aucune licence n'a encore été choisie pour le reste du code de ce dépôt.
