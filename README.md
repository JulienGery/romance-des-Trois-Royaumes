# Romance des Trois Royaumes — patch français et anglais

*Yo-kai Watch Sangokushi* est un jeu de stratégie au tour par tour sur Nintendo 3DS, développé par LEVEL-5 et jamais sorti officiellement hors du Japon. Ce projet traduit son texte en français et propose aussi une version anglaise provisoire.

**Important : avant d'appliquer le patch, testez impérativement le jeu japonais d'origine, sans modification, dans votre émulateur.** Certains émulateurs — ou certaines versions — ont déjà des problèmes avec le jeu non patché. Un test préalable permet de distinguer un problème d'émulation d'un problème introduit par le patch.

![Tutoriel en français](docs/images/01-tutoriel.jpg)

## Sommaire

- [Versions disponibles](#versions-disponibles)
- [Avant de commencer : tester le jeu d'origine](#avant-de-commencer--tester-le-jeu-dorigine)
- [Installation du patch](#installation-du-patch)
- [Ce que le patch traduit](#ce-que-le-patch-traduit)
- [Limites et précautions](#limites-et-précautions)
- [Code 60 FPS](#code-60-fps)
- [Contribuer au projet](#contribuer-au-projet)
- [Documentation technique](#documentation-technique)
- [Mentions](#mentions)

## Versions disponibles

| Version | Fichier | SHA-256 du jeu patché |
|---|---|---|
| **Français** — traduction relue | `YokaiWatchSangokushi-FR.xdelta` | `4a365b26600df577214bb0a950a573e4459731050f982c7fbcb9efd34d6dbbd6` |
| **English** — traduction DeepL à relire | `YokaiWatchSangokushi-EN.xdelta` | `ee6535fcef3c060553a562c944869c7ced1ea4a6868a314dd4ad240f2238269b` |

Téléchargez le fichier `.xdelta` souhaité dans la section [Releases](https://github.com/JulienGery/romance-des-Trois-Royaumes/releases).

La version anglaise est un **brouillon** traduit automatiquement du japonais avec DeepL. Les noms anglais officiels des Yo-kai sont utilisés lorsqu'ils existent dans le *Yo-kai Watch Wiki* ; les Yo-kai propres à *Sangokushi* peuvent conserver une traduction automatique. Les mêmes avertissements techniques que pour la version française s'appliquent. Les corrections sont les bienvenues.

## Avant de commencer : tester le jeu d'origine

### Cette étape est essentielle

Avant d'appliquer le patch, lancez votre **ROM japonaise non patchée** dans l'émulateur et vérifiez que le jeu fonctionne jusqu'à la **carte du monde**. Si le jeu d'origine ne démarre pas, plante ou affiche un écran noir, n'appliquez pas encore le patch : essayez un autre émulateur ou une autre version.

C'est particulièrement important avec **Azahar**, qui présente des problèmes avec le jeu de base selon la version et la plateforme. Un problème déjà présent sur la ROM d'origine ne peut pas être attribué au patch.

Problèmes constatés avec le jeu **non patché** :

- **Azahar sur macOS** : certaines versions récentes ne lancent pas le jeu. La version **Azahar 2125.1 universal macOS** a fonctionné lors des tests.
- **AYN Thor** : l'écran inférieur peut rester entièrement noir — même si le tactile répond — et l'émulateur peut planter.

Le patch a été testé avec **Zakuro** (fichier `.cci`), **Citra** et **Azahar 2125.1 universal macOS** (avec l'équivalent `.cxi`). Ces résultats ne garantissent pas le fonctionnement sur toutes les versions, tous les appareils ou toutes les configurations.

**Avant de signaler un plantage**, vérifiez donc d'abord que la ROM d'origine atteint la carte du monde dans le même émulateur. Si elle ne le fait pas, le problème vient probablement de l'émulateur ou de sa configuration, et non du patch.

## Installation du patch

L'application du patch se fait dans le navigateur : aucun logiciel supplémentaire n'est nécessaire.

### Prérequis

Il vous faut :

- Votre **propre dump déchiffré** de la version japonaise du jeu, au format `.cci`, correspondant au titre `000400000018B000`.
- Le patch `YokaiWatchSangokushi-FR.xdelta` ou `YokaiWatchSangokushi-EN.xdelta`, disponible dans les [Releases](https://github.com/JulienGery/romance-des-Trois-Royaumes/releases).

Le dump source attendu doit avoir ce SHA-256 :

`8776733296fb2f984e86102c834693b952aeae62789b4a584320c4fec359a453`

### Étapes

1. **Testez d'abord la ROM japonaise d'origine**, sans patch, comme expliqué dans la section précédente. Vérifiez que vous pouvez atteindre la carte du monde.
2. Ouvrez [xdelta-wasm](https://kotcrab.github.io/xdelta-wasm/). Le traitement se fait dans votre navigateur : les fichiers restent sur votre machine.
3. Dans **Source file**, sélectionnez votre dump japonais `.cci`.
4. Dans **Patch file**, sélectionnez le patch `.xdelta` français ou anglais.
5. Lancez l'application du patch, puis téléchargez le fichier obtenu. Il fait environ **860 Mo** ; l'opération peut demander un peu de temps et de mémoire vive.
6. Facultatif : vérifiez le SHA-256 du résultat avec les valeurs du tableau [Versions disponibles](#versions-disponibles).
7. Lancez le fichier `.cci` obtenu dans votre émulateur.

Si l'outil refuse le patch, vérifiez le SHA-256 du dump source : il doit correspondre exactement à celui indiqué plus haut, et le dump doit être déchiffré.

### Console réelle

Le patch sur console réelle n'a pas été testé. Le fichier n'est pas signé et l'exheader est modifié ; une conversion en CIA et des patchs de signature seraient nécessaires.

## Ce que le patch traduit

- **1 308 scripts** : histoire, dialogues, tutoriels, objectifs et messages système.
- **Une police adaptée au français** : accents, `« »`, `œ` et apostrophes, avec une largeur de caractères variable pour éviter les espacements irréguliers.
- **Un moteur de texte adapté** : retours à la ligne automatiques et ajustements des lignes, fenêtres et bulles à la longueur du texte français.

Les captures ci-dessous proviennent du jeu patché.

![Cinématique](docs/images/02-cinematique.jpg)
![Dialogue avec USApyon](docs/images/04-dialogue.jpg)
![Carte et annonces](docs/images/05-carte.jpg)
![Objectifs de combat](docs/images/06-combat.jpg)
![Passer une scène](docs/images/03-confirmation.jpg)

## Limites et précautions

### Les textures restent en japonais

Le patch traduit le **texte du jeu**, mais pas les textes intégrés aux images : titres de lieux, enseignes, boutons comme « SKIP » ou `はい / いいえ`, en-têtes comme `残り時間` ou `目的`, et noms affichés au-dessus des personnages. Leur traduction nécessiterait de modifier les textures. Les contributions graphiques sont les bienvenues.

### Des plantages restent possibles

Le patch modifie le code de l'exécutable : le moteur de texte en ARM natif est placé dans une zone de code considérée comme inutilisée. Aucun plantage n'a été rencontré pendant les tests réalisés, mais toutes les situations du jeu n'ont pas nécessairement été couvertes.

- **Sauvegardez régulièrement** et conservez plusieurs sauvegardes.
- Si le jeu plante, ouvrez une [issue GitHub](https://github.com/JulienGery/romance-des-Trois-Royaumes/issues) en indiquant :
  - l'endroit du jeu et l'action effectuée juste avant le plantage ;
  - l'émulateur, sa version et l'appareil utilisé ;
  - si la **ROM japonaise non patchée** fonctionne dans ce même émulateur jusqu'à la carte du monde ;
  - si possible, le log et une capture d'écran.

Le test de la ROM d'origine est la première information à fournir : il aide à déterminer si le problème est lié à l'émulateur ou au patch.

## Code 60 FPS

Le jeu tourne normalement à 30 FPS. Le code suivant vise à le faire passer à 60 FPS, sur la version japonaise comme sur les versions française et anglaise (même Title ID) :

```text
[60 FPS]
006AFFDC 00000002
B0000000 0067DEF0
00000148 00000001
D3000000 00000000
```

Placez ce code dans `cheats/000400000018B000.txt` (Azahar/Citra ou Luma3DS/Rosalina), puis activez-le en jeu. Le jeu garde son timing d'origine et ne change que la fréquence d'affichage (images dessinées en double sous Zakuro). Il n'a pas été testé sur console réelle.

Pour plus de détails, consultez [`cheats/README.md`](cheats/README.md).

## Contribuer au projet

Toute aide est bienvenue, même sans compétences en programmation. Le guide détaillé se trouve dans [`CONTRIBUTING.md`](CONTRIBUTING.md).

- **Signaler une erreur ou un plantage** : ouvrez une [issue](https://github.com/JulienGery/romance-des-Trois-Royaumes/issues/new/choose), avec une capture si possible. Pour un plantage, précisez surtout le résultat du test de la ROM non patchée.
- **Corriger la traduction** : les textes sont dans [`translations/`](translations/README.md), au format TSV. La version française est relue ; la version anglaise est encore à corriger. Modifiez la colonne `Translated Text`, puis ouvrez une pull request.
- **Reconstruire le patch** : lancez `tools/build.sh VOTRE_DUMP.cci fr` (environ 30 secondes). Consultez [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **Modifier le moteur de texte ARM** : voir [`docs/TECHNIQUE.md`](docs/TECHNIQUE.md).
- **Travailler sur les textures** : les textes intégrés aux images ne sont pas traduits pour le moment.

## Documentation technique

Pour compiler le patch, comprendre le moteur ARM et la police, créer une autre langue ou utiliser le pipeline de traduction (`tools/translation/build_language.sh`), consultez [`docs/TECHNIQUE.md`](docs/TECHNIQUE.md).

Pour les spécifications et l'état du projet :
- [`docs/dev/HANDOVER.md`](docs/dev/HANDOVER.md)
- [`docs/dev/JOURNAL_MODIFICATIONS.md`](docs/dev/JOURNAL_MODIFICATIONS.md)

## Organisation du dépôt

| Dossier | Contenu |
|---|---|
| `translations/` | Textes TSV, noms officiels et glossaire |
| `src/overrides/`, `src/arm/` | Moteur de texte en C et runtime ARM |
| `tools/` | Pipeline de build, traduction, analyse et vérifications |
| `data/` | Atlas de police préconstruit et cavités de code réutilisées |
| `docs/` | Documentation technique et documents de développement |
| `cheats/` | Code 60 FPS |
| `externals/`, `work/` | Outils tiers et dossiers de travail locaux non versionnés ; voir `tools/setup.sh` |

## Mentions

Projet de fan non officiel et sans but lucratif. *Yo-kai Watch* est une marque de LEVEL-5. Les noms anglais officiels des Yo-kai proviennent du [Yo-kai Watch Wiki](https://yokaiwatch.fandom.com) (CC BY-SA).

Ce dépôt ne contient aucune ROM ni aucun exécutable du jeu. Il contient toutefois l'atlas de police préconstruit (`data/atlas/`), dont les glyphes sont dérivés des polices de *Yo-kai Watch 2*, ainsi que les fichiers `translations/*/*.tsv`, qui conservent le texte japonais d'origine en regard de chaque traduction. Ces éléments devront être retirés si le détenteur des droits le demande.

`tools/fontatlas` est dérivé de [Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2) et reste sous **GPL-3.0**. Aucune licence n'a encore été choisie pour le reste du code.
