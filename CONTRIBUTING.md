# Contribuer au projet

Merci de vouloir contribuer à **Yo-kai Watch Sangokushi** !

La plupart des contributions consistent à corriger ou améliorer les textes français, puis à vérifier que le patch se construit correctement. Il n'est généralement pas nécessaire de modifier le moteur du jeu.

## 1. Améliorer la traduction

Vous pouvez proposer une correction sans installer d'outil de développement.

1. Recherchez le texte dans les fichiers `translations/fr/Sangokushi-script-Type[1-4].tsv`.
   - Sur GitHub, utilisez la recherche du dépôt.
   - En local, lancez `python3 tools/translation/search.py "bout de phrase"`.
   - Ajoutez `--ja` pour rechercher le texte japonais ou `--lang en` pour rechercher le texte anglais.
2. Modifiez **uniquement la colonne 7, `Translated Text`**. Les fichiers sont au format TSV (colonnes séparées par des tabulations) et encodés en UTF-8.
3. Ne modifiez pas les autres colonnes et ne changez pas l'ordre des lignes.
4. Respectez les conventions de traduction, notamment les balises `【…】` et les sauts de ligne : consultez [`translations/README.md`](translations/README.md).
5. Soumettez une pull request. Vous pouvez modifier le fichier directement depuis l'interface web de GitHub avec l'icône en forme de crayon.

La CI vérifie notamment les balises et les caractères pris en charge par la police. Ces contrôles sont utiles, mais **ils ne remplacent pas un test en jeu**.

## 2. Tester les changements

Les tests en jeu sont importants : un patch qui se compile correctement peut tout de même présenter des problèmes d'affichage ou de compatibilité.

### Tester avec un émulateur

Pour tester une modification, construisez une ROM de test à partir de **votre dump déchiffré de la version japonaise non patchée** :

```bash
python3 tools/patch_rom.py ORIGINAL.cci test.cxi
```

Ouvrez ensuite `test.cxi` dans votre émulateur et vérifiez les textes concernés ainsi que leur affichage.

**Avant de conclure à un problème du patch, vérifiez que le jeu original non patché fonctionne correctement dans le même émulateur.** Azahar peut présenter des problèmes avec le jeu de base ; un crash ou un comportement anormal ne provient donc pas nécessairement du patch. Si le jeu original présente déjà le même problème, notez-le dans votre signalement et évitez de l'attribuer au patch sans autre vérification.

Lorsque c'est possible, testez le jeu original puis la version patchée dans des conditions comparables. Pour signaler un problème, indiquez l'émulateur utilisé, sa version, la version du jeu et les étapes permettant de reproduire le problème. Ajoutez des captures d'écran si elles sont utiles.

### Vérifier sans lancer le jeu

Pour lancer les vérifications disponibles sans fournir de ROM :

```bash
tools/check.sh fr
```

Cette commande aide à repérer certains problèmes de données, mais elle ne permet pas de confirmer le bon fonctionnement en jeu.

## 3. Construire le patch

Pour reconstruire le patch localement, vous devez disposer de **votre propre dump déchiffré de la version japonaise originale**. La somme SHA-256 attendue est indiquée dans le `README.md` du projet.

### Installation (à faire une seule fois)

1. Installez Python 3, `xdelta3` et la chaîne de compilation ARM.
   - **macOS** :
     ```bash
     brew install xdelta
     brew install --cask gcc-arm-embedded
     ```
   - **Linux** : installez les paquets `gcc-arm-none-eabi` et `xdelta3` avec le gestionnaire de paquets de votre distribution.
2. Placez les binaires `3dstool` et `ctrtool` dans `externals/` :
   - [`3dstool`](https://github.com/dnasdw/3dstool)
   - [`ctrtool`](https://github.com/3DSGuy/Project_CTR)
3. Lancez le script de configuration :
   ```bash
   tools/setup.sh
   ```
   Il vérifie les dépendances et récupère `LINKDATA-explorer`.

La chaîne ARM est nécessaire pour compiler le moteur de texte. Pour une modification portant uniquement sur les traductions, le moteur n'a normalement pas besoin d'être modifié.

### Reconstruire après une modification

Lancez :

```bash
tools/build.sh ORIGINAL.cci fr
```

Remplacez `fr` par `en` pour construire la version anglaise.

Le patch et son fichier de somme de contrôle sont générés dans `work/release/fr/`, notamment :

- `YokaiWatchSangokushi-FR.xdelta`
- `SHA256.txt`

Appliquez le patch au dump original selon les instructions du `README.md`. Pour tester en émulateur sans générer de fichier xdelta, utilisez plutôt la commande `tools/patch_rom.py` présentée plus haut.

## 4. Ajouter une langue

Pour ajouter une langue, consultez la section « Autres langues » de [`docs/TECHNIQUE.md`](docs/TECHNIQUE.md). Le processus décrit s'appuie sur une traduction automatique DeepL depuis le japonais, l'utilisation des noms officiels, puis une relecture.

## 5. Proposer une pull request

Avant de soumettre vos changements :

- Vérifiez que la modification répond à un objectif clair.
- Lancez `tools/check.sh fr` lorsque c'est pertinent.
- Si vous modifiez le rendu en jeu, testez le résultat dans un émulateur et vérifiez le comportement du jeu original non patché.
- Décrivez clairement ce qui a changé et les vérifications effectuées.
- Regroupez les changements portant sur un même sujet dans une seule pull request.

Les messages de commit doivent être descriptifs et rédigés en français.

### Fichiers anglais

Les fichiers TSV de `translations/en/` sont des brouillons générés automatiquement. Les corrections et relectures sont bienvenues, mais évitez de les régénérer en masse sans en discuter au préalable.

## 6. Modifier le moteur ARM

La plupart des contributions n'ont pas besoin de toucher au moteur.

Le code lié à la police variable, aux retours à la ligne et aux bulles de dialogue se trouve notamment dans `src/overrides/` (C) et `src/arm/`. Il est compilé pour l'ARM11 par `tools/build_arm_native.py`, puis placé dans une zone de code inutilisée de l'exécutable.

Ces modifications sont plus délicates : une erreur peut provoquer un crash bien après le changement concerné. Si un texte s'affiche mal malgré une traduction correcte, privilégiez d'abord une issue accompagnée d'une capture et d'informations sur les conditions du test.

Pour approfondir le fonctionnement du projet, consultez [`docs/TECHNIQUE.md`](docs/TECHNIQUE.md). La documentation destinée à aider un assistant IA à travailler sur le code se trouve dans [`docs/dev/`](docs/dev/README.md) ; commencez par `HANDOVER.md`.

## 7. Fichiers à ne pas publier

**Ne commitez jamais** de ROM, de dump, d'exécutable ou de fichier extrait du jeu. Les répertoires `externals/` et `work/` sont ignorés par Git ; vérifiez tout de même le contenu de votre commit avant de soumettre une pull request.

Le processus de compilation est déterministe : une modification limitée aux textes change le SHA-256 du patch généré, mais ne change pas le comportement du moteur.

## Licence

Aucune licence n'a encore été choisie pour le code propre au projet. `tools/fontatlas/` reste sous GPL-3.0 et `tools/sangokuro/` sous MIT. En contribuant, vous acceptez que votre contribution soit publiée sous la licence qui sera choisie par le mainteneur.
