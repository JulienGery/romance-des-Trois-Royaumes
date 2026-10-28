# Journal des modifications du jeu — pour le portage en code ARM

Ce journal liste **tout ce qui change par rapport au jeu d'origine**, avec ce qu'il faut savoir pour le refaire en ARM (et ne plus dépendre de l'émulation recompilée). À mettre à jour à chaque changement : une ligne dans la table du §2, et le détail au §3.

Convention : « override » = fonction C hôte dans `overrides/*.c` (spécification exécutable) ; « patch ARM » = octets modifiés dans `code.bin` (`tools/arm_patches.py`) ; « données » = fichiers du romfs.

---

## 1. Vue d'ensemble

| Couche | Fichier(s) | État |
|---|---|---|
| Données (romfs) | `LINKDATA_A.BIN` entrée 0 : +2 textures (6, 7) — `tools/build_all.sh` | **fait**, chargé et vérifié dans le jeu |
| Patchs ARM (octets) | `tools/arm_patches.py`, `tools/build_arm_rom.sh` → `work/rom/game_arm.cxi` | 1 patch (voir §2), pipeline ExeFS compress/décompress **vérifié** (démarre, mêmes statistiques que l'original) |
| Overrides (spécification) | `overrides/frfont.h`, `frwrap.h`, `fr_text.c`, `diag_font.c`, `font_sml.h` | phases 2, 3, 4 — **ce sont eux qu'il faudra porter** |
| Tests | `diag_font.c` (`FR_SELFTEST=1`, `FR_BOXFILE=…`), `tools/dev/wrap_test.c`, `box_report.py`, `preview_quads.py` | réutilisables tels quels contre une ROM ARM (voir §5) |

Outils d'itération : `tools/fast_build.sh` recompile **seulement** `overrides/*.c` et relie (≈ 1 s). Un build complet (`3dsrecomp build …`, ≈ 2 min 30) n'est nécessaire que si l'**ensemble** des adresses `RECOMP_OVERRIDE(0x…)` change. Pour cette raison `fr_text.c` contient des overrides « pass-through » réservés (voir §2) : on peut y écrire du code sans reconstruire.

---

## 2. Table des modifications

### 2.1 Données

| # | Quoi | Détail |
|---|---|---|
| D1 | `LINKDATA_A.BIN` entrée 0 (G1T, 6 textures A4) | +texture 6 (256×256 A4, `ft_sml`, cellules 16×16, 165 glyphes triés par code UTF-8 empaqueté) et +texture 7 (`ft_nrm`, cellules 16×18). Textures 0-5 **inchangées**. Nouvelle taille 1 163 420 o (`tex_count = 8`), l'entrée est ajoutée en fin d'archive et la table est re-pointée. Chargement vérifié : `FUN_00112FDC` voit `tex_count = 8`, groupe de textures à 8 emplacements (6, 7 = 0x8000 o). |
| D2 | Tables de glyphes (hôte) | `overrides/font_sml.h` : `fr_sml_codes[165]` (u32 triés), `fr_sml_adv[]` (avance px à 16 px), `fr_sml_bearing[]` (int8, −1 pour `Y _ Î Ï î ï Ÿ`), `fr_sml_inkw[]` (0 = pas d'encre, p. ex. espace). Générées par `bake_french_atlas.py` à partir de `ft_sml.xf`. **À reloger dans la ROM en ARM** (voir §4). |

### 2.2 Patchs ARM (octets)

| # | Adresse | Avant → après | Effet |
|---|---|---|---|
| A1 | `0x00111714` (dans `FUN_001115EC`, init de l'objet police) | `E5846214` (`str r6,[r4,#0x214]`) → `E5848214` (`str r8,[r4,#0x214]`) | `police+0x1214 = 1` définitivement (r8 vaut 1 depuis `mov r8,#1` en `0x111690`, préservé par les appels). Active le chemin ASCII proportionnel du moteur. **Remplace `fr_init()`** des overrides. |

### 2.3 Overrides (fonctions à porter)

ABI à retenir **[vérifié sur le désassemblage]** : fonctions de glyphe `FUN_0052DA8C` / `FUN_0052DC54` : `s0,s1,s2` = x, y, z (flottants), `r0` = objet police (`0x007DAA28`), `r1` = code (u32 UTF-8 empaqueté) ; retour `r0` = avance en px, `-1` si la liste de quads est pleine.

| # | Adresse | Nom Ghidra | Type | Résumé du comportement ajouté |
|---|---|---|---|---|
| O1 | `0x0052DA8C` | glyphe ASCII | remplace | si `code` ∈ table française → un quad (texture 6) via `FUN_0052D848`, retourne `round(adv×charW/16)` ; espace/encre vide : pas de quad ; sinon appelle l'original |
| O2 | `0x0052DC54` | glyphe « autre » | remplace | idem pour les accents / `« » … ★ ♪ ※ ―` ; sinon original (chemin japonais) |
| O3 | `0x0052D340` | dessin de texte (interne) | wrapper | `fr_init` (remplacé par A1) puis original |
| O4 | `0x0052CEA4` | **mesure** de texte | remplace (port C) | port fidèle (720 cas identiques à l'original) : préprocess original, puis boucle C ; largeur latine = `fr_adv` ; coupe japonaise d'origine désactivée si le texte a été coupé par O5 ; site d'appel « bulle » → largeur de coupe 252 (O9) |
| O5 | `0x0052C690` | préprocess (tags, ruby, icônes) | wrapper | appelle l'original avec `maxc = -1`, **coupe les lignes** (`fr_wrap_text`), puis applique la limite « machine à écrire » ; texte avec ruby : comportement d'origine |
| O6 | `0x0052DEBC` | rendu `KTGL_Font_DrawFormattedString` | wrapper | pendant l'appel, `police+0x1238 = 0x7FFFFFFF` si le texte vient d'être coupé par O5 et que l'alignement ≠ 1 ; restauré après |
| O7 | `0x00533D70`, `0x005586CC`, `0x0055833C`, `0x00265900`, `0x00272E60`, `0x002C7F7C`, `0x00353308` | mises en page des fenêtres de message | wrapper (post) | l'original s'exécute ; `fr_fix_message_box` re-mesure à 16 → 14 → 12 px (largeur ≤ 301 / ≤ largeur de boîte − 16), conserve les marges, recentre verticalement, borne à l'écran 240 px. `FUN_0014C094` rappelée pour `5586CC/265900/272E60` (rects tactiles) |
| O8 | `0x002DFA54` | init du widget bulle | wrapper (post) | `widget+0x26C = 252` (largeur de coupe au dessin, identique à la mesure) |
| O9 | sites d'appel de mesure (`LR` ∈ `0x23634C, 0x23652C, 0x23795C, 0x2DEB78, 0x2DFBBC, 0x2DFCB4` + 4) | bulles | dans O4 | `police+0x1238 = 252` pendant la mesure quand la largeur de coupe est « infinie » |
| O10 | `0x005412E0` | dessin du widget de texte (chaque image) | wrapper | **text fit** (voir §3 O10) : fixe la capacité de texte des boîtes fixes et restaure la police après le dessin |
| O11 | `0x00222FE8` (+ mémo largeur dans O4) | cadre des bulles de combat (appelé par `FUN_005514F4`) | wrapper (pré) | **élargit le cadre** (plafond 160 px du jeu) au texte, centre conservé (voir §3 O11) |
| R | `0x002373E0 0x002372A4 0x00541794 0x002DE710 0x00236170 0x00237858 0x00542430 0x00541710 0x0021B87C 0x0052D44C 0x0052CE38 0x0052CAF8 0x00120E0C` | divers | **pass-through réservés** | aucun changement de comportement ; réservés pour pouvoir itérer sans reconstruire |

---

### 2.4 Scripts / traduction (données)
| # | Quoi | Détail |
|---|---|---|
| D3 | 1 308 entrées de script de `LINKDATA_A.BIN` (Types 1-4) | remplacées par les scripts compilés depuis les TSV français (`apply_translation.py build`). Format identique à l'original (vérifié sur le texte japonais : 1 308/1 308). Entrées ajoutées en fin d'archive. |
| D4 | `SangoKuro/Sangokushi-GenerateTranslatedFiles.py` et `Sangokushi-Pipeline.py` | ne remplacent plus `'` et `"` ; alignement 4 octets des entrées Type 2/4 et des chaînes Type 3 (comme les fichiers d'origine). |
| D5 | `SangoKuro/Sangokushi-script-Type2.tsv` | 80 cellules traduites corrigées (78 × `【交換相手】` restauré, 2 balises sans crochets) — sauvegarde dans `tools/build/tsv_backup/`. |

**Contrainte moteur à retenir pour le portage** : le tag `【…】` d'un texte est reconnu par préfixe (`Yk It Base Clan Chr Unit Str Val`) ou par l'un des 4 mots `主人公名 軍師名 交換相手 主人公妖怪名` ; tout autre contenu entre crochets (sans `：`) est imprimé tel quel.

**Leçon spécifique aux overrides (pas au portage ARM)** : tout override qui agit après un `CALL` doit d'abord faire `FR_ENSURE_BUDGET(ctx)` (voir le plan, phase 5 §7).

## 3. Détail par modification (spécification pour l'ARM)

### O1 / O2 — glyphes
```
idx = lookup(code)             ; recherche binaire dans fr_sml_codes[165] (u32 triés)
adv = (fr_sml_adv[idx]*charW + 8) / 16      ; charW = police+0x1220 (entier signé)
si fr_sml_inkw[idx] != 0 : émettre un quad
retour r0 = adv  (ou -1 si FUN_0052D848 a échoué)
```
Quad (13 mots, sur la pile, passé à `FUN_0052D848(police, quad)`) :
`[0]=x0 [1]=y0 [2]=x1 [3]=y1 [4]=z(bits de s2) [5]=*(police+0x11E0) [6]=6 (texture) [7..10]=u0,v0,u1,v1 [11]=0 [12]=0`
avec `sx=charW/16, sy=charH/16`, `x0 = x + bearing*sx`, `x1 = x0 + 16*sx`, `y1 = y + 16*sy`, `col = idx%16, row = idx/16`, `u0 = col*16/256`, `v0 = row*16/256`, `u1 = u0+16/256`, `v1 = v0+16/256`. (Pour `ft_nrm`, texture 7, cellules 16×18 : même schéma, paramètres du `.h`.)
**Pour l'ARM** : ~120 instructions + VFP (VMUL/VADD/VDIV ou constantes précalculées), `FUN_0052D848` est appelée telle quelle.

### O4 — mesure `FUN_0052CEA4(font, texte, &largeur, &hauteur, prétraiter, &drapeau6, &drapeau7)`
Arguments : `r0..r3`, puis pile `[sp]=prétraiter, [sp+4]=drapeau6, [sp+8]=drapeau7`.
Algorithme (identique à l'original sauf deux points) : parcours des codes ; `\n` → ligne suivante (`+= interligne(+0x122C) + charH`) ; codes de contrôle `0x10` (icône : `+= charW`, ou `charW*2` pour les icônes `0x4E/0x4F`, *affectation et non addition* comme l'original), `0x11` (ruby), `0x12` (+1 octet), `0x14` (restaure la taille), `0x15` (22×22, `*drapeau6 = 1`), `0x16` (12×12) ; autres caractères : si `0x20 ≤ code ≤ 0x7E` ou code dans la table française → `+= fr_adv` (**sans** l'espacement `+0x1228`, **sans** coupe japonaise) ; sinon branche pleine chasse d'origine (`charW + espacement`, coupe japonaise sauf si le texte est déjà coupé). Retour : nombre de glyphes. Le port C complet est `fr_measure_core` (`frfont.h`).
Différences avec l'original : (1) avance latine ; (2) la coupe japonaise (kinsoku) est ignorée quand `fr_prewrapped`.

### O5 — coupe française `FUN_0052C690(font, tampon, texte, maxc)` → `r0` = 1 si tout le texte tient dans `maxc` codes
1. Appeler l'original avec `maxc = -1`.
2. Si `police+0x1238 ≥ 0x7FFFFFFF`, ou si le tampon contient `0x11` (ruby) : refaire l'appel d'origine avec le vrai `maxc` (comportement d'origine, `fr_prewrapped = 0`).
3. Sinon `fr_wrap_text(tampon, wrap, charW, espacement, maxc)` (voir `frwrap.h`, ≈ 150 lignes de C pur, déjà compilable en ARM telle quelle) puis `fr_prewrapped = 1`.
`fr_wrap_text` : tokens `{code, début, fin, avance}` (contrôles : `0x10`+1 octet = icône, `0x12`+1 octet = couleur, `0x13/0x17` rien, `0x14/15/16` taille) ; points de coupe : après un espace (l'espace devient `\n`), après `-` entre deux lettres, entre deux caractères japonais ; interdits : espace avant `! ? : ; % ) ] } , . » … ’ 、 。 」 』 ー`, après `« ( [ { 「 『 （`; mot trop long coupé au caractère. Le compteur machine-à-écrire ignore les `\n` insérés et les contrôles.
**Reflow + équilibrage (2026-10-26, `frwrap.h` `fr_wrap_text2`)** — appliqués dès qu'une largeur de coupe existe :
- *Reflow* : un `\n` explicite est **dur** si le dernier caractère visible avant (balises couleur ignorées) ∈ `. ! ? : ; ) " - » … ” 。 ！ ？`, ou si le suivant ∈ `- " * « — • “` ou chiffre suivi de `.`/`)`, ou si `\n\n`, icône, début/fin de texte, CJK ; sinon il devient une **espace** (supprimé si une espace est déjà adjacente). Conserve le nombre de codes comptés (machine à écrire).
- *Équilibrage* par paragraphe dur : glouton à `W` → `n` lignes ; dichotomie du plus petit `W'` ∈ [plus large jeton, `W`] tel que le glouton donne encore ≤ `n` lignes ; recoupe à `W'`. Propriété vérifiée sur le corpus (42 572 textes) : la coupe à la largeur mesurée `mw` redonne exactement le même résultat que la coupe à `W` (mesure = dessin), aucun contenu perdu, jamais plus de lignes que l'ancien glouton, lignes orphelines (< 25 % de `W`) : 2 164 → 26 (`W`=252), 2 314 → 41 (301).
Limites en mémoire : tampon 1024 o (appelants), tokens ≤ 1024.

### O10 — text fit `FUN_005412E0(widget)` (boîtes fixes)
Pour les widgets dont la boîte n'est dimensionnée par aucune fonction de mise en page (ex. dialogue de Whisper `(2,166,396,72)`) :
1. Avant l'original : `capacité = widget+0x30 − widget+0x258 − 6` ; actif si le widget n'est pas « géré » (jamais passé par O7/O8), `0 < h ≤ 240` et `capacité ≥ 24`. Sauvegarder `police+0x1220/0x1224/0x122C`.
2. Dans O5 (préprocess), si actif : essayer dans l'ordre jusqu'à `n×taille + (n−1)×interligne ≤ capacité` (ou 1 ligne) : (1) coupe normale ; (2) reflow total (tous les `\n` → espaces) ; (3) interligne min(interligne, 2) ; (4) 14 px puis 12 px avec interligne réduit, reflow normal puis total. Écrire taille/interligne dans la police. Un 2ᵉ préprocess du même dessin repart des valeurs d'avant (déterministe).
3. Après l'original : restaurer taille et interligne si modifiés, désactiver.
Cas de référence : « Tout est fin prêt ! / En route pour l'École élémentaire de Granval ! » → étape 2, 2 lignes à 16 px.

### O11 — bulles de combat : `FUN_005514F4(widget, &pos)` + cadre `FUN_00222FE8`
Identifiée avec le journal `STACK` (pile d'appel du texte « Je perdrai pas… » : `55137C → 5517F4 → 2231A8 → 224994`). `FUN_005514F4` mesure le texte (taille 12, `FUN_0052CEA4`, p5 = 1), fixe la largeur du cadre = `clamp(max(largeur_texte + 0x20, largeur_texture), 0xA0)` — **le plafond 160 px est un immédiat du code ARM** — puis dessine le cadre 3 tranches par `FUN_00222FE8(x0, y0, x1, y1, …)` (VFP : `s0 = x0`, `s2 = x1` ; c'est un thunk vers `FUN_00223054`) et centre le texte sur le centre du cadre. Un texte français de 194 px déborde donc d'un cadre de 160.
Correctif (deux points d'accroche) :
1. dans la mesure `FUN_0052CEA4` : si `LR` ∈ ]`0x5514F4`, `0x551870`[ → mémoriser la largeur `tw` du texte ;
2. dans `FUN_00222FE8` : si `LR` ∈ [`0x5514F4`, `0x551870`[ et `tw > 0` : `voulu = min(340, tw + 32)` ; si `voulu > x1 − x0` : `d = (voulu − (x1 − x0))/2`, borné pour rester dans [0, 400] ; `s0 −= d`, `s2 += d` (centre conservé → texte toujours centré) ; puis appeler l'original.
En ARM : patcher le plafond `0xA0` (ou le `cmp`) de `FUN_005514F4` à ~`0x154` plutôt que de réécrire les coordonnées. Journal : `COMBATBUBBLE textw=… frame x a..b -> c..d`. `FR_NOCB=1` désactive. `0x002DEA30` et `0x002DFAD8` restent pass-through (première tentative sur `2DEA30` : cette fonction ne dessine pas les bulles de combat).
Diagnostic réutilisable : le journal `STACK '<texte>' lr=… <adresses>` (une ligne par texte distinct) donne la pile d'appel de n'importe quel texte.

### O12 — textes centrés sans largeur de coupe (écrans d'intro, tutoriel, horloge, pseudo)
Ces textes sont dessinés **ligne par ligne** par `FUN_002B8C30` (`CountLines` puis `GetLine` + `FUN_0052D340(x, y, …)` par ligne, positions dans une table à nombre de lignes limité : 5 max pour le panneau de Whisper) avec une largeur de coupe infinie et l'alignement 2 : on ne peut donc **pas** ajouter de lignes. Deux mécanismes :
1. *Texte multi-lignes dessiné d'un bloc* (centré, coupe infinie, `FUN_0052D340` donne le centre `(x,y)` en `s0/s1`) : dans le préprocess, si une ligne dépasse `W = min(284, 2·min(x, 400−x) − 12)` → reflow + équilibrage à `W` (`CENTERFIT`), taille 14/12 si la hauteur dépasse `2·min(y, 240−y) − 8`. Taille/interligne restaurés après `FUN_0052D340`.
2. *Texte dessiné ligne par ligne par `FUN_002B8C30`* : `CountLines` (appelé depuis `0x2B8C30…0x2B9200`) mémorise la largeur de la plus large ligne (dernière mesure) et le nombre de lignes ; chaque `FUN_0052D340` suivant réduit uniformément la taille à `cw·W/larg_max` (`W = min(380, 2·min(x, 400−x) − 12)`, taille ≥ 11) (`PANELFIT`).
2b. *Texte d'une seule ligne* (bannière, étiquette ; `LABELFIT`) : réduit la taille (≥ 11 px) pour tenir dans `W` au lieu d'ajouter une ligne ; au-delà, reflow comme en 1.
3. *Données* : 4 textes trop longs raccourcis dans `Sangokushi-script-Type2.tsv` (lignes 741, 749, 751, 752, 748, 722 : pseudo, horloge, deux écrans du tutoriel, avertissement « œuvre de fiction » remis en 3 lignes, bannière « Reprendre là où… ») pour tenir dans 252 px (panneau de 262 px) / 377 px (écran noir).

### O6 — rendu
Sauvegarder `police+0x1238`, le mettre à `0x7FFFFFFF` si (`fr_prewrapped` et `police+0x1218 ≠ 1` et valeur ≠ ∞), appeler l'original, restaurer, `fr_prewrapped = 0`.

### O7 — fenêtres de message : `fr_fix_message_box(widget, texte, hauteur_fixe)`
Champs du widget (box-relatifs sauf x, y) : `+0x24 x, +0x28 y, +0x2C w, +0x30 h, +0x254/+0x258 texte x/y, +0x260/+0x264 taille, +0x268 interligne (float), +0x26C/+0x270 taille mesurée, +0x274 alignement`.
```
tient = y>=0 && y+h <= 241 && ty+mh <= h && tx>=0 && tx+mw <= w
si tient : rien
sinon pour s dans (16,14,12) :
    interligne' = round(interligne*s/16) ; wrap = min(301, w-16)
    (mw', mh') = mesure(texte)  avec charW=charH=s
    h' = ty + mh' + marge_basse        (marge_basse = h - ty - mh d'origine, bornée à [6,40] ; ≤12 et h' ≥ h pour les boîtes à hauteur fixe 265900/2C7F7C)
    y' = y + h/2 - h'/2, puis borné à [0, 240-h']
    tx' = tx + (mw-mw')/2 (≥ 0)
    arrêt dès que tout tient
écrire +0x260,+0x264 (taille), +0x268 (float), +0x26C,+0x270, +0x28, +0x30, +0x254
```
Résultat mesuré sur 108 chaînes de 1 à 9 lignes × 2 modes × (1 à 9 types) : **0 boîte hors écran / 0 texte hors boîte**, sauf `0x0055833C` (1 px de dépassement en bas, déjà présent dans l'original à 1 ligne) et `0x00541794` (boîte de dialogue système, 2 chaînes absurdes de 299 caractères).

### O8 / O9 — bulles
Les bulles (`FUN_00236170`, `FUN_00237858`, `FUN_002DFAD8`, `FUN_002DEA30`) mesurent sans largeur de coupe (textes japonais à `\n` explicites). O9 fixe 252 px aux 6 sites d'appel de la mesure ; O8 impose la même largeur au dessin. Test : chaîne de 128 caractères → 4 lignes, largeur 243 px (hors sites de bulle : 758 px, inchangé).
**Non vérifié** : placement final de la bulle à l'écran (`FUN_002373E0` borne déjà à l'écran dans l'original).

---

## 4. Portage ARM — **réalisé** (2026-10-26) : `tools/patch_rom.py`

Commande unique : `python3 tools/patch_rom.py ORIGINAL.cci FRANCAIS.cxi [--verify]` (ROM japonaise **déchiffrée** → CXI français). Enchaîne : extraction (3dstool) → atlas de police (dotnet) → scripts traduits dans `LINKDATA_A.BIN` (`build_all.sh`) → code ARM natif (`build_arm_rom.sh` → `arm_patches.py` + `build_arm_native.py`) → CXI. Plus aucune bibliothèque recompilée n'est nécessaire.

**Principe** : les **mêmes sources C** (`overrides/fr_text.c`, `frfont.h`, `frwrap.h`) sont compilées pour l'ARM11 (`arm-none-eabi-gcc -Os -marm -mcpu=arm1176jzf-s -mfpu=vfp -mfloat-abi=hard`) avec `fr_arm/overrides.h` à la place de l'en-tête du recompilateur : `Context` {r0-r15, s0-s31} reconstruit à l'entrée, `mem_read/mem_write` = accès mémoire directs, `CALL(original)` = `fr_call_guest` (rt.S).
1. **Accroche** (17 fonctions, `PASS` = les 14 pass-through ne sont pas accrochés) : le 1er mot de la fonction devient `b stub_XXXX` ; le stub charge `r12 = override_XXXX` puis `b fr_enter`. `fr_enter` (rt.S) : sauve `r4-r6,lr` (32 o sous le sp d'entrée), passe sur une **pile C privée** (`fr_cstack`, 8 Kio par niveau d'imbrication), construit le `Context` (r0-r3, s0-s15, sp/lr d'entrée), appelle l'override, renvoie `r0-r3`. Les arguments sur pile (mesure : p5-p7) sont lus à `ctx->r[13]` = sp d'entrée ; les appels au jeu tournent sur `min(r[13], floor_sp)` pour ne jamais écraser la zone sauvée.
2. **Trampolines de l'original** (`fr_tramp_XXXX`, générés en asm) : instruction déplacée (un `push`, ou `ldr rN,[pc,#]` + `push` pour `0x2DFA54`, avec copie du littéral) + `b original+4`. L'assertion du script refuse toute autre instruction d'entrée.
3. **Place pour le code** : le `.text` est plein ; `dead_code.py` (accessibilité statique : branches ARM/Thumb, `adr`, littéraux, mots ABS/REL32 de `.rodata/.data` dont la table des constructeurs statiques) propose 118 fonctions inaccessibles (47 Ko), `cavity_search.py` les **confirme** (remplies d'un piège `0xE7F000F0`, démarrage du jeu dans `zakuro --interpreter` : mêmes nombres de threads/draws/transfers/fills qu'un démarrage intact, aucun piège exécuté ; dichotomie pour retirer les fautives) → **90 fonctions, 38 062 o** dans `data/cavities.json`. `build_arm_native.py` répartit les sections (`-ffunction-sections`, premier ajustement décroissant) dans ces fragments via un script de liens généré ; ≈ 15 Ko de code.
4. **État** : `.bss` agrandi de `0x20000` dans l'exheader (`0x16E978 → 0x18F000` ; état statique + 8 piles C) ; `3dstool` recalcule le hash d'exheader.
5. `libgcc` non utilisé : `__aeabi_idiv/uidiv`, `memcpy/memset…` dans `fr_arm/rt.c`.
6. **A1 supprimé** (`arm_patches.py` vide) : forcer `font+0x1214 = 1` dès l'init casse le démarrage (accès à une police nulle) ; les hooks `0x52D340` et mesure appellent `fr_init()`.

7. **Marge de place** (2026-10-26, après essais sur `game_trap.cxi`) : deux sessions de jeu ont révélé 7 fonctions « mortes » réellement utilisées (retirées par `cavity_update.py`) ; **2026-10-28** : cavité `0x44B6D4-0x44B878` retirée de `data/cavities.json` — `0x44B710` est un point d'entrée de thread (passé en `r1` à la création du thread, `prefetch abort … 0x0085F000 from 0x0044B715` après ~1000 images) ; toujours tester le build ARM sur **≥ 6000 images** (`--headless 6000`) ; la règle « le prédécesseur doit se terminer par un terminateur » (raccords C++ `this`-ajustant qui se prolongent dans la fonction suivante) est dans `dead_code.py`. Pour garder de la marge : (a) glyphes (`fr_glyph`) et fenêtres (`fr_box_wrap`) factorisés, (b) le corps de la mesure d'origine `0x52CEA8-0x52D340` sert de cavité (jamais appelée), (c) tout le code est compilé en **Thumb** (`-mthumb -mfloat-abi=softfp -fno-jump-tables`, −25 %) sauf les fonctions qui utilisent le FPU (`FR_ARM` : glyphes, cadre `0x222FE8`, boîtes, texte centré, `fr_panel_shrink`) et `rt.c`/`rt.S` en ARM ; l'éditeur de liens reçoit `--use-blx` (sinon il insère des veneers) et les cavités sont limitées à une fenêtre de 4 Mio (portée du `bl` Thumb). Résultat : 10 564 octets de code pour 13 Ko de cavités vérifiées. Outils : `cavity_update.py LOG` (retire les fonctions touchées), `make_trap_rom.sh` (ROM piège).
8. Chaque fil d'exécution a ses propres piles C privées (`fr_acquire`/`fr_release`, clé = TLS) : 8 fils × 4 niveaux × 6 Kio.

**Vérifié** : le CXI démarre en émulation ARM pure (`zakuro --interpreter`) ; à 6000 images : 14 474 draws / 8 857 transfers / 11 808 fills contre 14 456 / 8 851 / 11 800 pour la version « overrides recompilés » (écart de minutage). **Non vérifié** : rendu visuel du français en émulation ARM pure, parties longues (une fonction « morte » rarement exécutée écrasée serait fatale), **matériel réel**, concurrence (état global et profondeur d'imbrication non protégés ; les fils d'exécution du jeu dessinent le texte sur un seul fil).
**Console réelle** : le CXI n'est pas signé et l'exheader est modifié (`bss`) ; il faut le convertir en CIA (`makerom`) et l'installer avec des patchs de signature (CFW), ou l'exécuter par un chargeur qui ne les vérifie pas.

## 5. Vérifier une version ARM contre la spécification (overrides)
- `FR_BOXFILE=… FR_BOXORIG=…` produit les géométries de fenêtres : comparer `box_0.txt` (overrides) avec la sortie obtenue sur la ROM ARM (même harnais appelant les mêmes adresses).
- `wrap_test` (C hôte) : le même `frwrap.h` compilé pour ARM doit donner des résultats identiques sur `build/corpus.bin` (42 572 chaînes).
- Mesure : comparer, pour les 720 combinaisons de `diag_font.c`, `(n, w, h, f6, f7)` entre l'original et le port.
- Dessin : capture des quads (`tools/dev/preview_quads.py`).

## 6. Points ouverts
- Textures 6/7 : **dessin réel à l'écran jamais observé** (aucune entrée manette en mode sans fenêtre) ; vérifier visuellement couleur/ombre/z dans une scène de dialogue réelle.
- Texture 7 (`ft_nrm`) baked mais **non utilisée** ; prévue pour les gros titres (22 px).
- Alignement à droite + accents : la coupe japonaise du rendu peut encore s'activer en bout de ligne pleine.
- Boîte de dialogue système `FUN_00541794` : non adaptée (textes courts supposés).
- Variables de tags (noms de joueur/unités) : mesurées après expansion ? Test dédié à faire avec les noms les plus longs.
- Couverture de la cavité ARM : à mesurer.


## 5. Correctifs d'affichage du 2026-10-27 (v1.3)

Tous dans `src/overrides/fr_text.c` / `frwrap.h` (repris tels quels par le build ARM) :
| Id | Problème | Correctif |
|---|---|---|
| P1 | Fenêtres « multi-lignes » (boîte d'assaut, « Sauvegarde terminée ») : le widget `0x5412E0` dessine chaque ligne séparément via `GetLine` (`0x52CAF8`), qui coupe seulement aux `\n` du texte brut → un paragraphe que nous coupons chevauche la ligne suivante | hook `0x52CAF8` : renvoie la ligne *i* du texte coupé par notre moteur (`fr_getline_core`, forme brute `【r】..【e】`, couleur fermée/rouverte à chaque ligne). `0x52CAF8` retiré de `PASS` (build_arm_native.py) |
| P2 | Médallium (descriptions, talents, aptitudes) : texte dessiné à gauche, sans largeur de coupe → déborde du panneau | `fr_edge_rule` / `fr_edge_guest` : table position (x,y) → bord droit/bas du panneau, puis `fr_pick_step` (coupe, fusion des phrases, interligne 2, 11 px, 10 px) |
| P3 | Médallium page 3, biographie (coupe 339 déjà active mais 5 lignes trop hautes) | `fr_bio_avail` : même « text fit » que les boîtes fixes avec la hauteur restante du panneau |
| P4 | Phrases d'accroche (y 101) trop longues, plaque du nom (y 73) | `fr_center_guest` : une ligne réduite à ≥ 12 px (330 px), sinon deux lignes de 11 px remontées par une dernière ligne contenant un espace ; plaque : 90 px |
| P5 | ⑯ (bouton HOME) : notre atlas contenait un « 16 » cerclé | U+246F retiré des tables (`fr_lookup`, `frw_lookup`) → police d'origine du jeu |
| P6 | Place dans les cavités ARM | choix de mise en page factorisé (`fr_pick_step`), calculs flottants sortis des fonctions (`fr_ctr_xi/yi`, `fr_ftoi`, `fr_itof`) : 12 140 → 11 420 o ; l'empaqueteur laisse 8 o de marge ; les overrides « pass-through » ne sont plus compilés |
| P7 | Journal `FR_TRACE_FILE` | une ligne identique à l'une des 64 dernières n'est plus écrite |
