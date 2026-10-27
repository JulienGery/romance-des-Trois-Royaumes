# Contribuer

Merci de votre aide ! Ce projet traduit *Yo-kai Watch Sangokushi* (3DS) en français (et un brouillon anglais). Voici comment participer selon ce que vous savez faire.

## Sans jouer ni compiler : corriger un texte

1. Trouvez la phrase dans `translations/fr/Sangokushi-script-Type[1-4].tsv` (recherche sur le texte français ou japonais).
2. Modifiez **uniquement la colonne 7, « Translated Text »**. Ne changez pas les autres colonnes ni l'ordre des lignes. Format détaillé : [`translations/README.md`](translations/README.md).
3. Ouvrez une pull request en décrivant ce qui change (une capture du jeu aide si c'est un problème d'affichage).

Cela peut se faire entièrement depuis l'interface web de GitHub (icône crayon sur le fichier).

## Vérifier sa modification

```bash
tools/check.sh fr      # ou "en" : atlas, lint des balises et des largeurs de ligne, syntaxe des scripts
```

Aucune ROM n'est nécessaire. Le lint signale les caractères absents de la police du jeu, les balises `【…】` perdues ou modifiées, et les lignes trop larges. La CI lance la même vérification sur chaque pull request.

## Tester dans le jeu

Il faut **votre propre dump déchiffré** de la version japonaise (le dépôt n'en contient aucun).

```bash
tools/setup.sh                                              # vérifie les outils, clone LINKDATA-explorer dans externals/
python3 tools/patch_rom.py ORIGINAL.cci test.cxi --verify   # ≈ 10 s, ajoutez --lang en pour l'anglais
```

Lancez `test.cxi` dans un émulateur (voir le README pour les versions testées).

## Modifier le code

- Moteur de texte : `src/overrides/` (C) et `src/arm/` (runtime). Il est compilé pour l'ARM11 par `tools/build_arm_native.py`.
- Pipeline : `tools/` (voir [`tools/README.md`](tools/README.md)).
- Avant de toucher au moteur, lisez [`docs/TECHNIQUE.md`](docs/TECHNIQUE.md) et [`docs/dev/JOURNAL_MODIFICATIONS.md`](docs/dev/JOURNAL_MODIFICATIONS.md) : le patch place du code dans des zones de code mort de l'exécutable, une erreur peut faire planter le jeu bien plus tard.
- **Contrôle de non-régression** : le build est déterministe. Si votre changement ne doit pas modifier le résultat, le SHA-256 du `.cci` produit doit rester celui du tableau « Quelle version ? » du README.

## Règles du dépôt

- **Ne commitez jamais** de ROM, d'exécutable, de dump ou de fichier extrait du jeu (`externals/` et `work/` sont ignorés).
- Messages de commit en français, à l'impératif ou descriptifs, une idée par commit.
- Une pull request = un sujet (traduction d'un chapitre, un correctif de moteur…).
- Les traductions anglaises de `translations/en/` sont machine-générées : les relectures sont bienvenues, mais ne les régénérez pas en masse (`translate_deepl.py`) sans en discuter dans une issue.

## Licence

Aucune licence n'a encore été choisie pour le code propre au projet ; `tools/fontatlas/` reste sous GPL-3.0 et `tools/sangokuro/` sous MIT (voir leurs fichiers de licence). En proposant une contribution, vous acceptez qu'elle soit publiée sous la licence que choisira le mainteneur.
