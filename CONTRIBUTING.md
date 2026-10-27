# Contribuer

Le cas d'usage principal : **modifier les textes du jeu et reconstruire le patch**. Le moteur ARM n'a normalement pas besoin d'être touché (voir la fin).

## 1. Corriger un texte (sans rien installer)

1. Cherchez la phrase dans `translations/fr/Sangokushi-script-Type[1-4].tsv` : barre de recherche de GitHub, ou en local `python3 tools/translation/search.py "bout de phrase"` (ajoutez `--ja` pour chercher le japonais, `--lang en` pour l'anglais).
2. Modifiez **uniquement la colonne 7, « Translated Text »** (un tableur ouvre ces fichiers : séparateur tabulation, UTF-8). Ne touchez ni aux autres colonnes ni à l'ordre des lignes. Règles d'écriture (balises `【…】`, sauts de ligne) : [`translations/README.md`](translations/README.md).
3. Ouvrez une pull request. L'interface web de GitHub suffit (icône crayon sur le fichier). La CI lance le lint et signale les balises cassées ou les caractères absents de la police.

## 2. Reconstruire le patch chez vous

Il faut **votre propre dump déchiffré** de la version japonaise (SHA-256 attendu dans le README). Une seule fois :

1. Installer Python 3, `xdelta3` et la chaîne ARM (macOS : `brew install xdelta` et `brew install --cask gcc-arm-embedded` ; Linux : `gcc-arm-none-eabi`, `xdelta3`). La chaîne ARM sert seulement à compiler le moteur de texte, inchangé quand on édite des textes.
2. Copier dans `externals/` les binaires [`3dstool`](https://github.com/dnasdw/3dstool) et [`ctrtool`](https://github.com/3DSGuy/Project_CTR).
3. `tools/setup.sh` : vérifie tout et clone `LINKDATA-explorer`.

Ensuite, à chaque modification (≈ 30 s) :

```bash
tools/build.sh ORIGINAL.cci fr      # ou: en
```

Résultat : `work/release/fr/YokaiWatchSangokushi-FR.xdelta` (+ `SHA256.txt`), à appliquer sur le dump comme dans le README. Pour juste tester dans un émulateur, sans xdelta : `python3 tools/patch_rom.py ORIGINAL.cci test.cxi`.

Vérification rapide sans ROM : `tools/check.sh fr`.

## 3. Ajouter une langue

Voir « Autres langues » dans [`docs/TECHNIQUE.md`](docs/TECHNIQUE.md) (traduction automatique DeepL depuis le japonais, noms officiels, puis relecture).

## Règles

- **Ne commitez jamais** de ROM, d'exécutable, de dump ni de fichier extrait du jeu (`externals/` et `work/` sont ignorés).
- Une pull request = un sujet. Messages de commit en français, descriptifs.
- Les TSV `en/` sont du brouillon machine : les relectures sont bienvenues, mais ne les régénérez pas en masse sans en discuter.
- Le build est déterministe : une PR qui ne change que du texte change le SHA-256 du patch, mais jamais le comportement du moteur.

## Le moteur ARM (rarement nécessaire)

Police variable, retours à la ligne, bulles : `src/overrides/` (C) et `src/arm/`, compilés pour l'ARM11 par `tools/build_arm_native.py` et placés dans du code mort de l'exécutable. C'est délicat (une erreur peut planter le jeu bien plus tard). Si un texte ne s'affiche pas correctement malgré une bonne traduction, ouvrez une issue avec une capture ; sinon, la documentation pensée pour être donnée à un assistant IA est dans [`docs/dev/`](docs/dev/README.md) (commencer par `HANDOVER.md`), et [`docs/TECHNIQUE.md`](docs/TECHNIQUE.md) donne le reste.

## Licence

Aucune licence n'a encore été choisie pour le code propre au projet ; `tools/fontatlas/` reste sous GPL-3.0 et `tools/sangokuro/` sous MIT. En contribuant, vous acceptez que votre contribution soit publiée sous la licence que choisira le mainteneur.
