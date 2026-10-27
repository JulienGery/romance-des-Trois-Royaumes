# Code de triche 60 FPS — Yo-kai Watch Sangokushi (`000400000018B000`)

Fonctionne sur la version japonaise **et** sur le patch FR/EN (même Title ID, la zone mémoire concernée n'est pas déplacée par le patch).

## Code

```
[60 FPS]
006AFFDC 00000001
006AFFE0 00000002
```

À copier dans `/cheats/000400000018B000.txt` (carte SD, menu Rosalina de Luma3DS → Cheats), ou dans le dossier `cheats/` d'Azahar/Citra. Activer le code une fois dans la partie.

## Pourquoi ça marche (analyse du code.c / de l'ELF)

- `0x6AFF00` est l'objet application (`DAT_00104af8`, passé à `main_loop` 0x105278). Son champ `+0xDC` (`param_1[0x37]`) est le **mode de cadence** : le jeu l'écrit à `2` une fois, à l'initialisation d'une scène (`mov r0,#2 ; str r0,[r1,#220]` en `0x21D764`). Toute autre valeur = 60 fps natif.
- Si le mode vaut 2, `main_loop` règle l'intervalle d'échange du GPU à 2 VBlanks (`FUN_0010831c(gfx,2)`, 30 fps) ; sinon il le remet à 1 (60 fps).
- Le moteur est à pas de temps variable, et gère les deux cadences nativement : `FUN_001085c8` prend 1/30 s (mode 2) ou 1/60 s comme durée nominale d'image, `main_loop` passe `dt × 60` aux mises à jour (2,0 en 30 fps, 1,0 en 60 fps), et le compteur d'images (`0x113B88`) avance de 2 ou 1. La vitesse du jeu reste donc la même, seule la fluidité change.
- Le code écrit `0` à chaque image dans `0x6AFFDC` : même si le jeu remet `2`, le mode redescend à 60 fps à l'image suivante, et `main_loop` rétablit l'intervalle de 1 VBlank tout seul.

## Pourquoi `1` et pas `0` (bug corrigé)

Ce champ n'est pas qu'un drapeau : c'est aussi le **nombre de « ticks » 60 Hz par image** (2 en 30 fps, 1 en 60 fps). Le moteur s'en sert comme pas : le compteur d'images global l'additionne à chaque tour (`0x10A69C`, `0x106D10`), et les délais anti-doublon des effets sonores (30 emplacements, `FUN_00108e30`) sont décrémentés de cette valeur. Avec `0`, ces délais ne redescendaient jamais, donc les bruitages déjà joués (surtout ceux de l'interface) ne se redéclenchaient plus. Avec `1` ils redescendent normalement.

## Vérification (Zakuro, `--headless 2000`, ARM pur, jeu FR)

En remplaçant les instructions de `main_loop`/`FUN_001085c8` par l'équivalent du cheat (mode lu = 0, ancien mode = 2), le nombre d'images 3D dessinées pour 2000 VBlanks émulés passe de **4474 à 9013** (×2,01). Contrôles : intervalle forcé à 4 → 2207 ; à 1 → 9013 ; supprimer l'attente de VBlank (`FUN_00123094`) → 18069. L'écran restant à 60 Hz, le nombre d'images dessinées par VBlank est la cadence réelle du jeu (pas l'affichage de l'émulateur). Au démarrage, le jeu tourne déjà à l'intervalle 2 (30 fps) : le code agit donc dès le début, sans attendre la scène en `0x21D764` (jamais atteinte en headless). `006AFFE0` (`param_1[0x38]`, mode appliqué) à 2 force `main_loop` à réappliquer l'intervalle 1.

## Limites

- Test fait par équivalent en code (le moteur de triche lui-même n'a pas été lancé) et en headless uniquement ; pas d'essai sur console.
- Sur console, une scène trop lourde pour tenir 60 fps retombera vers ~30 fps (le pas de temps variable compense la vitesse).
- Du code de jeu qui compterait des images sans passer par `dt` pourrait aller plus vite ; non observé dans le code analysé.
- Zakuro : l'indicateur de fps de l'émulateur est la cadence de présentation de l'écran, pas la vitesse du jeu.

## Variante permanente (patch de code, sans moteur de triche)

Remplacer l'instruction en `0x21D764` : `E3A00002` (`mov r0,#2`) → `E3A00001` (`mov r0,#1`). Équivaut à une entrée de `PATCHES` dans `fr_patch/arm_patches.py` (non ajoutée : cela changerait le SHA-256 du patch distribué).
