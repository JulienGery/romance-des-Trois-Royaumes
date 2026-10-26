# HANDOVER — à lire en premier après un contexte vidé

Projet : **traduire Yo-kai Watch Sangokushi (3DS) en français**. La traduction du texte existe déjà (TSV). Le travail consiste à faire afficher ce texte correctement : police française à chasse variable, accents, retour à la ligne, fenêtres/bulles. Tout se fait en **overrides C** exécutés par l'émulateur Zakuro + code recompilé (`3dsrecomp`) ; plus tard, **portage en patchs ARM** dans l'exécutable.

Langue de travail avec l'utilisateur : **français**. Il préfère : peu de bavardage, des résultats vérifiés, **ne pas relancer le build complet (2 min 30) à chaque fois** (utiliser `fast_build.sh`, 1 s). Il lance le jeu lui-même et envoie des captures.

Docs : `PLAN_police_et_bulles.md` (phases 1-5 faites, résultats détaillés), `JOURNAL_MODIFICATIONS.md` (tout ce qui change vs le jeu d'origine, pour le portage ARM), `RAPPORT_police_variable.md` (analyse du code Ghidra), `PLAN_correctifs_texte.md` (**travail en cours**), annexe CSV des 130 fonctions qui dessinent du texte.

---

## 1. État au moment du handover (2026-10-26)

- Phases 1-5 **faites** : police française en jeu (ft_sml, 165 glyphes), avance variable, retour à la ligne français, boîtes/bulles adaptées, traduction intégrée (1 308 scripts + entrée 0 de `LINKDATA_A.BIN`), lint, corrections de balises. Phase 6 (textes dessinés en images, noms, ruby) **volontairement différée**.
- L'utilisateur a lancé le jeu : « globalement très très bien ». **Deux défauts restants** (captures dans la conversation, analysés dans `PLAN_correctifs_texte.md`) :
  1. une fenêtre de dialogue du bas de l'écran haut (Whisper « Tout est fin prêt ! … ») : la 3ᵉ ligne sort de l'écran (boîte dimensionnée pour 2 lignes, texte dessiné sur 3) ;
  2. dans une bulle (« Que le meilleur gagne entre mon / intuition / de génie… ») : retour à la ligne **non équilibré** (saut de ligne explicite du traducteur + coupe automatique → ligne orpheline).
- **2026-10-26 (session suivante)** : les deux défauts sont **codés, non encore validés en jeu** :
  1. *Reflow + équilibrage* (`frwrap.h` `fr_wrap_text2`, drapeaux `FRW_REFLOW/REFLOW_ALL/BALANCE`) : testé hors jeu sur tout le corpus (`fr_patch/wrap_test2.c`, `build/wrap_test2 build/wrapcorpus.bin`) : 0 contenu perdu, jamais plus de lignes, mesure = dessin, orphelines 2 164 → 26. Auto-test zakuro : 720 cas de mesure inchangés.
  2. *Text fit* des boîtes fixes (Whisper) : dans l'override `0x005412E0` + `fr_fit_guest` (appelé par le préprocess `0x52C690`). Hors jeu, la phrase de la capture passe de 3 lignes à 2 lignes à 16 px (étape 2). Non testé en jeu (pas de moyen de rejouer la scène en headless). `FR_NOFIT=1` désactive le text fit. Le journal `FR_TRACE_FILE` écrit `FIT step=… size=… lsp=… inner=… lines=…` à chaque déclenchement (étape ≥ 2).
  Reste à faire : l'utilisateur rejoue les deux scènes (bulle de Jibanyan, Whisper) ; vérifier d'autres boîtes fixes via `WIDGETDRAW`/`FIT` dans le journal. Note : `FR_SELFTEST=1` finit toujours par une erreur fatale `0xD8E007F7` (artefact du test, antérieur à ces changements).

- **2026-10-26 (suite)** : validés en jeu par l'utilisateur : reflow/équilibrage, text fit Whisper, bulle de combat (O11 : cadre élargi, fonction `FUN_005514F4`/`FUN_00222FE8`), écrans d'intro/tutoriel/horloge/pseudo (O12 : réduction/reflow des textes centrés + 4 traductions raccourcies, voir journal). Dernier correctif livré, à valider : bannière du menu « Reprendre… » (texte d'une ligne rétréci à ≥ 11 px, traduction raccourcie) et avertissement « œuvre de fiction » en 3 lignes. Outil de diagnostic : journal `STACK` (pile d'appel par texte) + `DRAWFMT xyz`. **Agrandir la bannière (image du jeu)** : non fait, fonction de dessin non localisée.
Nouveau dans le dépôt : `fr_patch/wrap_test2.c` (propriétés du reflow sur le corpus). Un nouvel override d'adresse (ex. `0x222FE8`, `0x2DEA30`) impose un build complet de 3 min 30.

- **2026-10-26 (fin)** : **portage ARM réalisé** (`fr_patch/patch_rom.py`, voir `JOURNAL_MODIFICATIONS.md` §4) : une commande transforme la ROM japonaise déchiffrée en CXI français sans bibliothèque recompilée ; démarre en `zakuro --interpreter` avec les mêmes statistiques que la version overrides. À valider par l'utilisateur : lancer `zakuro FRANCAIS.cxi --interpreter` (ARM pur) et rejouer les scènes habituelles (texte, bulles, bannières), puis une longue partie (risque : cavité de code mort exécutée plus tard) ; matériel réel non testé. Les correctifs de texte peuvent désormais se faire dans `overrides/fr_text.c` et sont repris tels quels par le build ARM (`fr_patch/build_arm_rom.sh`) ; une nouvelle fonction accrochée = un nouveau `RECOMP_OVERRIDE(0x…)`, pris en compte automatiquement (sauf s'il est dans `PASS`).

- **2026-10-26 (fin 2)** : patch **français** publié sous forme de patch xdelta (`fr_patch/make_release.sh`, SHA-256 résultat `4a365b26…`) ; **anglais** (brouillon DeepL depuis le japonais + noms officiels du wiki, `fr_patch/build_language.sh`, SHA-256 `a5e8f654…`). Voir `docs/TECHNIQUE.md` (autres langues, noms officiels). Traduction EN depuis le français : 75 % faite (`translations/en-from-fr/.cache.json`, non versionné), reprise possible quand le quota DeepL se réinitialise (`translate_deepl.py --lang en --source fr`). Restent : textures non traduites, essai sur console réelle.

## 2. Carte du dépôt (`/Users/juliengery/Documents/yokai_watch_claude/`)

| Chemin | Rôle |
|---|---|
| `code.c` | décompilation Ghidra complète (16 253 fonctions, noms `FUN_xxxxxxxx`, **ABI parfois fausse**, voir §5) |
| `exefs.elf` | exécutable ARM (`.text 0x100000`, `.rodata 0x60C000`, `.data 0x674000`, `.bss 0x6B0000`) |
| `3dsrecomp/` | recompilateur (binaire `target/release/3dsrecomp`), `sangokushi.cci` (ROM d'origine), `docs/overrides.md` |
| `overrides/` | **le code que nous écrivons** : `frfont.h` (logique, mesure, quads), `frwrap.h` (coupe de lignes, C pur), `fr_text.c` (tous les overrides), `diag_font.c` (auto-tests), `font_sml.h` (tables de glyphes générées) |
| `fr_patch/` | outils : `build_all.sh`, `fast_build.sh`, `bake_french_atlas.py`, `g1t_tools.py`, `make_entry0.py`, `patch_linkdata.py`, `apply_translation.py`, `lint_translation.py`, `fix_translation_tags.py`, `arm_patches.py`, `build_arm_rom.sh`, `box_corpus.py`/`box_report.py`, `wrap_corpus.py`/`wrap_test.c`, `preview_quads.py` ; sorties dans `fr_patch/build/` |
| `rom_work/` | ROM extraite (`romfs_dir`, `exefs.bin`, `entry0/`…) et **`game_fr.cxi` = la ROM à lancer** |
| `SangoKuro/` | pipeline de traduction (TSV `Sangokushi-script-Type[1-4].tsv`, générateurs) — dépôt git de l'utilisateur ; nous y avons modifié les 2 générateurs et le TSV Type2 |
| `LINKDATA-explorer/` | moteur Python de `LINKDATA_A.BIN` (lecture/extraction, G1T→PNG) |
| `polices/` | `ft_nrm.xf`, `ft_sml.xf` (YW2 FR) + outil dotnet `Level5FontAtlas` |
| `3dstool`, `ctrtool` | conteneurs 3DS |
| `rapport/` | la documentation |

## 3. Commandes essentielles (toujours en chemins absolus ; le cwd du shell dérive)

```bash
# lancer le jeu (fenêtre) ; bruit "v123 = …" sur stderr = dump de shader, sans importance
zakuro /Users/juliengery/Documents/yokai_watch_claude/rom_work/game_fr.cxi 2> /tmp/zakuro.log

# itérer sur les overrides (1 s) — à utiliser par défaut
/Users/juliengery/Documents/yokai_watch_claude/fr_patch/fast_build.sh
# build complet (2 min 30) : seulement si l'ENSEMBLE des RECOMP_OVERRIDE(0x…) change
cd /Users/juliengery/Documents/yokai_watch_claude/3dsrecomp && ./target/release/3dsrecomp build sangokushi.cci --overrides ../overrides

# reconstruire la ROM (lint + scripts + atlas + romfs + cxi, ≈ 6 s)
/Users/juliengery/Documents/yokai_watch_claude/fr_patch/build_all.sh

# tests sans fenêtre
zakuro .../rom_work/game_fr.cxi --headless 3000 --mute --rasterizer software --data /private/tmp/claude-501/zdataN
FR_SELFTEST=1 …                       # mesure (720 cas vs original), dessin, coupe, bulle
FR_BOXFILE=…/fr_patch/build/boxcorpus.bin [FR_BOXORIG=1] …   # géométrie des 8 mises en page de fenêtres
FR_TRACE=1 …                           # traces [fr] sur stderr
FR_TRACE_FILE=/tmp/fr.log …            # journal d'événements texte (voir PLAN_correctifs_texte.md)
```
Les `.c` des overrides incluent `frfont.h`/`frwrap.h` **par chemin absolu** (le build ne copie que les `.c`). Le scanner d'overrides exige `RECOMP_OVERRIDE(0x…)` avec adresse littérale (pas de macro).

## 4. Faits vérifiés à ne pas ré-établir

**Données**
- `LINKDATA_A.BIN` : en-tête 16 o + N×16 o `{adresse/32, 0, taille disque, taille décompressée (0 = brut)}` ; compression = blocs zlib de 32 Ko. Entrée **0 = atlas de police** (G1T, A4, 6 textures ↔ 6 descripteurs de police en `.rodata 0x61BF74`). Nous y avons ajouté les textures **6 (ft_sml, cellules 16×16)** et **7 (ft_nrm, 16×18)** ; le jeu les charge (8 emplacements vérifiés).
- Textes : UTF-8, `\n` forcé, balises `【…】` : variables moteur reconnues **par préfixe** `Yk It Base Clan Chr Unit Str Val` ou mots `主人公名 軍師名 交換相手 主人公妖怪名` ; couleurs `b r g p B R G y`, retour `e` ; taille `縮小 倍角 全角 幅小` ; ruby `【base：lecture】`.
- ExeFS `code.bin` = image du jeu (vaddr 0x100000 = offset 0) ; compressé dans la ROM (`3dstool … -u` / `--compress`).

**Moteur de texte (objet police global `0x007DAA28`)**
`+0x11E0` textures · `+0x1214` drapeau ASCII proportionnel (mis à 1 par `fr_init`/patch A1) · `+0x1218` alignement (0 gauche, 1 droite, 2 centré bloc x+y) · `+0x1220/+0x1224` taille · `+0x1228` espacement · `+0x122C` interligne · `+0x1238` largeur de coupe · `+0x1250` alpha.
Pipeline : `DrawText 0x52DC28 → FUN_0052D340 → préprocess FUN_0052C690 → KTGL_Font_DrawFormattedString 0x52DEBC → glyphes 0x52DA8C (ASCII) / 0x52DC54 (autres) → FUN_0052D848 (quad)`. Mesure : `0x52CEA4` (7 args : r0-r3 + pile p5=prétraiter, p6, p7) ; `CountLines 0x52CE38`.
**ABI des fonctions de glyphe : `s0,s1,s2` = x,y,z (flottants), `r0` = police, `r1` = code** (Ghidra se trompe).
Widgets de fenêtre : `+0x24 x, +0x28 y, +0x2C w, +0x30 h` (boîte) ; `+0x254/+0x258` position du texte (relative à la boîte) ; `+0x260/+0x264` taille ; `+0x268` interligne (**float**, vaut 10.0 pour les fenêtres de dialogue, 7 pour les bulles) ; `+0x26C/+0x270` taille mesurée (**+0x26C sert de largeur de coupe au dessin**) ; `+0x274` alignement ; `+0x278` multi-lignes ; `+0x27C` compteur machine à écrire ; `+0x54` texte. Rendu générique : `FUN_005412E0` (chaque image). Mises en page de fenêtres (méthode virtuelle) : `0x533D70 0x5586CC 0x55833C 0x265900 0x272E60 0x2C7F7C 0x353308` ; boîte système `0x541794` (entrée réelle de la fonction `0x54179C`). Bulles : `0x236170 0x237858 0x2DFAD8 0x2DEA30` (mesure), `0x2DFA54` (init), `0x2373E0/0x2372A4` (placement), `0x2DE710` (marges par style).
Écrans de 240 px de haut (haut 400 px, bas 320 px).

**Overrides (hôte)**
- `.rodata` **non inscriptible** par un override, `.data` oui. Tables françaises = statiques C de l'hôte.
- `CALL(RECOMP_ORIGINAL(0xADDR))` seulement pour une fonction surchargée ; sinon `ctx->r[15]=ADDR; ctx->thumb=0; CALL(f_ADDR);`.
- Code après `CALL` : **exécuté seulement si pas d'appel système ni d'épuisement du budget** → `FR_ENSURE_BUDGET(ctx)` en tête de tout override qui agit après un `CALL` (leçon : crash « branch to unmapped 0x6F63206C »). Tests longs : relever `ctx->budget`.
- Appeler un override depuis un autre : `override_0x0052CEA4(ctx)` (fonction C ordinaire).
- 14 overrides « pass-through » réservés (dont `0x5412E0`, `0x52CE38`, `0x2373E0`, `0x2372A4`, `0x541794`, `0x2DE710`, `0x236170`, `0x237858`, `0x542430`, `0x541710`, `0x21B87C`, `0x52D44C`, `0x52CAF8`, `0x120E0C`) : on peut y écrire du code avec `fast_build.sh`.

## 5. Comportements actuels des overrides (résumé)

- **Glyphes** `0x52DA8C/0x52DC54` : table française d'abord (texture 6), sinon chemin japonais d'origine. Avance = `round(adv16 × charW / 16)`, sans espacement `+0x1228`.
- **Mesure** `0x52CEA4` : port C fidèle (720 cas identiques à l'original) ; coupe française faite dans le préprocess ; coupe japonaise désactivée pour le texte déjà coupé ; sites de bulles (`LR` ∈ `0x23634C 0x23652C 0x23795C 0x2DEB78 0x2DFBBC 0x2DFCB4` +4) mesurés à 252 px.
- **Préprocess** `0x52C690` : reflow + équilibrage (voir journal O5) ; text fit si widget à boîte fixe (O10) ; coupe **toute** la chaîne puis applique la limite machine-à-écrire (le texte ne « saute » pas) ; ruby → comportement d'origine.
- **Rendu** `0x52DEBC` : neutralise la coupe japonaise de rendu (sauf alignement droite).
- **Fenêtres** : l'original s'exécute, puis `fr_fix_message_box` corrige seulement si la boîte sort de l'écran / le texte sort de la boîte (re-mesure 16→14→12 px).
- **Bulles** : largeur 252 (mesure + `+0x26C` via `0x2DFA54`).

## 6. Journal de diagnostic (env `FR_TRACE_FILE=/chemin`)

Lignes écrites : `LAYOUT fn=… box=(x,y,w,h) text@(tx,ty) meas=(w,h) cw lsp '…'` (chaque mise en page de fenêtre), `LAYOUT-FIX …`, `COUNTLINES n=… wrap=…`, `WIDGETDRAW wd=… box … meas … align multi chars '…'` (à chaque changement de texte/page), `DRAWFMT align wrap sw prewrapped …`, `MEASURE(p5=0, inside draw) n w h`. Exemple vu en test : écran de sauvegarde = `fn=00533D70 mode=1 box=(0,50,320,140) meas=(260,94) lsp=10`.

## 7. Prochaines étapes (ordre conseillé)

1. Demander à l'utilisateur de rejouer les deux scènes (`FR_TRACE_FILE=/tmp/fr.log zakuro …`) et de confirmer / envoyer captures + journal ; ajuster le text fit (marge 6, ordre des étapes) selon le résultat.
2. (fait, à valider) `PLAN_correctifs_texte.md` : reflow + équilibrage, text fit.
3. Ensuite seulement : phase 6 (textes en images, noms de fiches, ruby), puis portage ARM (voir `JOURNAL_MODIFICATIONS.md` §4).

## 8. Pièges rencontrés

- `sed -i` BSD (macOS) : syntaxe différente ; préférer Python pour les remplacements.
- Les TSV sont en CRLF ; l'aller-retour `csv` avec `lineterminator='\r\n'` est exact (ne jamais faire de remplacement texte brut sur tout le fichier : il toucherait la colonne japonaise d'origine).
- `3dstool -ctf romfs … --romfs romfs.bin` (modèle) gonfle le romfs ; créer **sans** modèle.
- Un build `3dsrecomp` qui échoue silencieusement laisse l'ancienne bibliothèque installée : lire la fin de sa sortie.
- Les sorties de commandes très longues (dump de shaders) : toujours filtrer avec `grep`/`tail`.
