# Code de triche 60 FPS — Yo-kai Watch Sangokushi (`000400000018B000`)

Fonctionne sur la version japonaise **et** sur le patch FR/EN (même Title ID, adresses inchangées).

```
[60 FPS]
006AFFDC 00000002
B067DEF0 00000000
00000148 00000001
D3000000 00000000
```

À copier dans `/cheats/000400000018B000.txt` (Luma3DS/Rosalina) ou dans le dossier `cheats/` d'Azahar/Citra, puis activer le code. La ligne `B067DEF0 00000000` est le « load offset » Gateway (format `BXXXXXXX 00000000`, supporté par Azahar et Luma3DS) : elle lit le pointeur stocké en `0x67DEF0`, et la ligne suivante écrit à `pointeur + 0x148`. `D3…` remet l'offset à 0.

## Principe

- `0x6AFF00` est l'objet application. Son champ `+0xDC` est le **mode de cadence** : le jeu l'écrit à `2` (30 fps). Chaque conversion « durée du script → temps » du moteur (≈ 35 endroits : scripts d'événements/cinématiques, fondus, animations de fenêtres…) choisit ses constantes selon ce mode : `1/30 s` par image de script si le mode vaut 2, `1/60 s` sinon. Le contenu du jeu est écrit pour 30 images/s : **en mode « 60 fps » natif, les cinématiques, textes et fondus passent deux fois trop vite** (la voix, elle, ne bouge pas : décalage son/image). C'était le défaut de la première version du code, qui forçait ce mode.
- Le code garde donc le mode à `2` (toutes les constantes d'origine), et ne change que la **cadence de présentation** : `*(0x67DEF0)` est l'objet graphique, dont `+0x148` est l'intervalle d'échange d'écran (en VBlanks), 2 par défaut, mis à `1`. Le moteur mesure déjà le temps réel écoulé par image (pas de temps variable), donc les animations qui en dépendent restent à la bonne vitesse et sont simplement plus fluides.
- Mesuré sous Zakuro (ARM pur, 2000 VBlanks) : intervalle 2 → 4474 images dessinées, intervalle 1 → 9013 (×2).

## Limites connues

- Le test son/image n'est pas possible en headless ; le correctif repose sur l'analyse du code (conversion des durées de script) et sur la remarque « images trop rapides » du joueur.
- Quelques compteurs comptent des *images* et non du temps, et iront donc deux fois plus vite : l'horloge globale (temps de jeu affiché), un compteur de fondu d'interface (`0x113B88`) et les délais anti-doublon des bruitages (`0x108E30`, ils redescendent plus vite, donc sons un peu moins filtrés). Sans effet sur la synchro des cinématiques.
- Sur console, une scène trop lourde pour 60 fps retombe sous 60 (le temps réel mesuré compense).
- Zakuro : l'indicateur de fps est la cadence d'écran, pas la vitesse du jeu.
