# Yo-kai Watch Sangokushi — Plan d'implémentation : police française à chasse variable, accents, bulles

Complète `RAPPORT_police_variable.md` (analyse du code). Ce document couvre : (1) ce qui est **déjà prêt** (ROM + outils), (2) le **savoir technique** vérifié sur les données, (3) le **plan par phases** avec critères de validation.

Légende : **[Vérifié]** testé sur les fichiers / en émulation · **[Déduit]** raisonnement à partir du code · **[À vérifier]** reste à confirmer par un test.

---

## 1. Ce qui est préparé

### 1.1 Arborescence

```
yokai_watch_claude/
├─ 3dsrecomp/                 recompilateur (binaire déjà compilé : target/release/3dsrecomp), sangokushi.cci
├─ 3dstool, ctrtool           conteneurs 3DS
├─ LINKDATA-explorer/         moteur Python de l'archive LINKDATA (lecture, export, rebuild)
├─ SangoKuro/                 pipeline de traduction (TSV <-> scripts) — texte déjà traduit en français
├─ polices/                   ft_nrm.xf, ft_sml.xf (YW2 FR) + Level5FontAtlas (outil dotnet → atlas + métriques)
├─ rom_work/                  ◄ NOUVEAU : ROM extraite
│   ├─ contents/              .app extraits du .cci (00 = jeu, 01 = mise à jour/manuel)
│   ├─ header/exheader/logo/plain/exefs/romfs .bin   composants du CXI (3dstool -xtf cxi)
│   ├─ romfs_dir/             romfs d'origine (Data/LINKDATA_A.BIN, BGM/, MOVIE/)
│   ├─ romfs_dir_fr/          romfs patché (clone APFS)
│   ├─ entry0/                entrée 0 décodée : entry0.g1t + tex0..5 (RGBA) + a0..a5.png (alpha = glyphes)
│   └─ game_fr.cxi            ◄ ROM patchée (décryptée, bootable)
├─ fr_patch/                  ◄ NOUVEAU : outils de patch
│   ├─ g1t_tools.py           encodeur A4 + reconstructeur de conteneur G1T (auto-test intégré)
│   ├─ bake_french_atlas.py   atlas Level5FontAtlas → page A4 en cellules fixes + tables C
│   ├─ charset_from_translations.py   caractères réellement utilisés par la traduction
│   ├─ make_entry0.py         entrée 0 d'origine + 2 pages françaises (textures 6 et 7)
│   ├─ patch_linkdata.py      remplace UNE entrée de LINKDATA_A.BIN sans reconstruire l'archive
│   ├─ build_all.sh           chaîne complète → rom_work/game_fr.cxi
│   └─ build/                 page_sml/nrm.alpha|png, glyphs_*.json, font_sml.h, font_nrm.h, entry0_fr.g1t, LINKDATA_A.BIN
└─ rapport/                   RAPPORT_police_variable.md, PLAN_police_et_bulles.md, annexe CSV
```

### 1.2 Commandes

```bash
# Reconstruire la ROM patchée (≈ 20 s)
fr_patch/build_all.sh

# Lancer en émulation sans fenêtre (test de non-régression)
zakuro rom_work/game_fr.cxi --headless 1500 --interpreter --mute --rasterizer software --data /tmp/zdata

# Avec le code recompilé + overrides (phase 1)
3dsrecomp/target/release/3dsrecomp build 3dsrecomp/sangokushi.cci --overrides overrides/
zakuro rom_work/game_fr.cxi            # trouve ~/.local/share/3dsrecomp/000400000018B000.so
```

### 1.3 Vérifications déjà faites

| Test | Résultat |
|---|---|
| Extraction `.cci` → CXI → romfs → `LINKDATA_A.BIN` (482 509 312 o, 19 165 entrées) | OK |
| Entrée 0 = G1T `GT1G 0600`, **6 textures, toutes A4** : 1024², 1024×512, 1024×512, 256², 128², 128² | **[Vérifié]** — correspond exactement aux 6 descripteurs de police du binaire |
| Ré-encodage A4 de chacune des 6 textures (décodage → encodage) | **identique à l'octet** |
| Reconstruction du conteneur G1T à partir de ses 6 entrées | **identique à l'octet** |
| Recompression d'une entrée (`compress_entry_payload`) | même format de flux (blocs zlib de 32 Ko, en-tête identique) ; taille différente (niveau zlib) mais lisible par le jeu |
| `patch_linkdata.py` sur l'entrée 0 (nouvelle taille 1 163 420 o, ajoutée en fin d'archive) | relecture de l'entrée = contenu injecté |
| Reconstruction romfs (3dstool, **sans** `--romfs` modèle) + CXI | 857 Mo, `Crypto Key: None`, même Title ID `000400000018B000` |
| Démarrage Zakuro `--headless 1500` : ROM d'origine reconstruite **vs** ROM patchée | statistiques identiques (1208 draws, 2089 transferts, 2784 remplissages) → **aucune régression** |

Notes pratiques **[Vérifié]** :
- `3dstool -cvtf romfs … --romfs romfs.bin` (avec modèle) **gonfle** le romfs (1,34 Go) quand un fichier grandit. Utiliser la création sans modèle (3 s, taille d'origine). Le tutoriel du dépôt SangoKuro recommande le modèle ; ce n'est pas nécessaire pour Zakuro/Luma.
- Effacer les `.DS_Store` avant de reconstruire (déjà dans `build_all.sh`).
- Le premier lancement dans un dossier `--data` neuf formate la sauvegarde et donne des compteurs différents ; comparer deux lancements successifs.

---

## 2. Savoir technique

### 2.1 Structure du jeu

| Élément | Contenu |
|---|---|
| Titre | Yo-kai Watch Sangokushi (CTR-P-AYKJ), Title ID `000400000018B000`, NCCH décrypté |
| ExeFS | `code` ARM (≈ 5,3 Mo, `exefs.elf`, `.text` 0x100000) — c'est ce que décompile `code.c` |
| RomFS | `Data/LINKDATA_A.BIN` (482 Mo), `BGM/` (BCSAR + g1l), `MOVIE/` (moflex) |
| `LINKDATA_A.BIN` | en-tête 16 o (`0x0133781D`, N=19165, multiplicateur 32, 0) + N×16 o `{adresse/32, 0, taille disque, taille décompressée (0 = brut)}`, puis données alignées sur 32. Compression = flux de blocs zlib (`u32 taille totale` + `{u32 n, zlib}`* + `u32 0`). |
| Chargement | `load_entry(id, dest, &taille, flag)` (0x00120CB0) → `load_entry_core` (0x00132508). La table (stride 0x10, taille décompressée en `+0xC`) est **lue depuis l'archive à l'exécution** : modifier la table suffit, aucune table n'est figée dans l'exécutable. **[Vérifié]** |
| Types d'entrées | textures G1T 13 128 · scripts 1 532 · archives (SARC/Z3/…) 365 · modèles G1M 178 · audio 80 · binaires 3 782 |
| Scripts texte (plages) | Type 1 : 13585-14264 · Type 2 : 53-59 (≠54) · Type 3 : 16112-16131 · Type 4 : 15134-15954 et 61-63 |
| Encodage des scripts | **UTF-8**, chaîne terminée par `\0`, `\n` = saut de ligne forcé. Type 1/2/4 : table `{offset, longueur}`. |

### 2.2 L'entrée 0 = l'atlas de police (confirmé)

Les 6 textures de l'entrée 0 sont, dans l'ordre, les 6 descripteurs de `rodata 0x0061BF74` :

| Tex | Taille | Descripteur | Contenu | Remarque |
|---|---|---|---|---|
| 0 | 1024×1024 | 0x61BF74 | japonais **16 px**, cellules 16×16, 2139 glyphes | 1957 cases libres |
| 1 | 1024×512 | 0x61BF8C | japonais **14 px**, 14×14 | contient aussi des ASCII pleine chasse en bas |
| 2 | 1024×512 | 0x61BFA4 | japonais **12 px**, 12×12 | |
| **3** | 256×256 | 0x61BFBC | **ASCII demi-chasse** 14×28, 16 colonnes : seules 6 lignes (0x20–0x7E + ■) sont dessinées ; police étroite et haute (rendue à l'échelle `charH/28`) | utilisé aujourd'hui seulement pour `: / -` (drapeau `+0x1214` = 0) |
| 4, 5 | 128×128 | 0x61BFD4/FEC | ruby (furigana) 8 px, kana | inutile en français |

Format **A4** (4 bits d'alpha, pixel pair = quartet bas), tuilage CTR 8×8 Morton, Y inversé **[Vérifié par aller-retour]**. Le moteur charge les textures via un chargeur G1T **générique** (`FUN_0013F464`, boucle sur le nombre de textures de l'en-tête, 0x40 octets par texture) → **ajouter des textures à l'entrée 0 est possible** **[Déduit]** ; non-régression de démarrage vérifiée, **utilisation effective des textures 6 et 7 : [À vérifier]** (premier test de la phase 1).

Géométrie de rendu (code) :
```
quad = { x0,y0,x1,y1, z, ptr_textures(police+0x11E0), indice_texture, u0,v0,u1,v1, flag, ptr_couleurs }   ← FUN_0052D848(police, quad)
UV : origine en haut à gauche, v = y/hauteurTexture (même convention que les PNG décodés)
```
Indice de texture = champ [6] du quad (3 pour l'ASCII, 0/1/2 pour 16/14/12 px, 4/5 ruby). Les textures 6 et 7 seraient donc adressées par `[6] = 6` / `7`.

### 2.3 Polices YW2 françaises (`polices/`)

`ft_nrm.xf` / `ft_sml.xf` : XPCK → `FNT.bin` (Level-5 `Fnt00/01`) + texture `.xi` ; chaque glyphe a une position dans l'atlas, un canal (R/G/B), des **offsets** et une **avance** propres (police à chasse variable native). L'outil `Level5FontAtlas` (dotnet) en tire `atlas.png` (blanc + alpha) + `atlas.json` (x, y, largeur, hauteur, offsetX, offsetY, advance) + `atlas.fnt` (BMFont).

| Police | Hauteur de ligne | Avance moy. (ASCII) | Hauteur max d'encre | Usage proposé |
|---|---|---|---|---|
| `ft_sml` | **16** | 7,9 px | 14 | **taille de base du jeu (16 px) en 1:1** ; réduction (14 px ×0,875, 12 px ×0,75) pour les autres |
| `ft_nrm` | 18 | 9,3 px | 16 | texte large/titres (≈ 22 px via tag `縮小`/`倍角` inverse) |

Les deux contiennent latin complet, ligatures, guillemets et symboles. Le jeu de caractères réellement nécessaire a été calculé depuis les TSV (`charset_from_translations.py`) : `« » ° À Â Ç È É Ê Î Ï Ô × Ù à â ç è é ê ë î ï ô ö ù û ü ō Œ œ — ― … ※ € ↑ → ⑯ ★ ☆ ♪` ; **165 glyphes** bakés (tout y est, y compris `ō ♪ ★ ☆ ―`). Restent hors police : `⑯` (existe dans la police japonaise) et quelques kanji de tags.

### 2.4 Atlas français préparé (textures 6 et 7)

- **Cellules fixes**, une page 256×256 chacune : `sml` = 16×16 (16×16 cases), `nrm` = 16×18 (16×14 cases). 165 glyphes triés par code UTF-8 empaqueté (même empaquetage que `UTF8_iter`, donc comparable directement à `local_50`).
- Chaque glyphe est copié **à sa position (offsetX, offsetY)** dans sa case → le rendu = dessiner la case entière (aucun recadrage). Les 7 glyphes à `offsetX < 0` (`Y _ Î Ï î ï Ÿ`) sont décalés dans la case et leur **bearing** (`−1`) est dans `fr_*_bearing[]`.
- Tables C générées (`font_sml.h`, `font_nrm.h`) : `fr_sml_codes[]` (triée), `fr_sml_adv[]` (avance px à 16 px), `fr_sml_bearing[]`, `FR_SML_COUNT/CELL_W/CELL_H/COLS/LINE/FALLBACK_INDEX` (repli = `■`).
- Les tables vivent **côté hôte** (tableaux statiques C de l'override) : pas besoin de mémoire invité ni de modifier le `rodata`.

### 2.5 Texte et traduction (état réel)

La traduction française est **déjà faite** dans `SangoKuro/*.tsv` :

| Type | Lignes | Traduites | Plus longue | Max lignes (`\n`) | Max octets |
|---|---|---|---|---|---|
| 1 | 18 360 | 18 359 | 108 car. | 1 | 111 |
| 2 | 13 952 | 13 952 | 324 car. | 5 | 362 |
| 3 | 257 | 257 | 115 | 3 | 115 |
| 4 | 10 698 | 10 095 | 177 | 2 | 184 |

Conséquences **[Vérifié sur les TSV]** :
1. **Aucune ligne > 511 octets** → les tampons de 0x200 octets suffisent aujourd'hui.
2. Beaucoup de répliques longues (jusqu'à 320 caractères) **sans `\n`** : elles comptent sur le retour à la ligne automatique → le calcul de la hauteur des boîtes doit supporter **5+ lignes**.
3. Tags utilisés (hors variables) : `【e】` 1679 (retour couleur), `【g】`, `【r】`, `【b】`, `【y】`, `【G】`, `【縮小】` (petite taille) ; **variables** `【Str1】`, `【Unit1.strName】`, `【Chr1.strChrName】`, `【Base1.strBaseName】`, `【Partenaire d'échange】` — résolues par `FUN_001EB7FC` → **leur longueur finale (nom français) est inconnue à la mesure** ; prévoir un test avec les noms les plus longs.
4. `Sangokushi-GenerateTranslatedFiles.py::process_dialogue_string` **remplace** `'`→`´` (U+00B4), `"`→`″` (U+2033) et `...`→`…` parce que l'ancienne police n'avait pas ces glyphes ASCII. Avec la nouvelle police, **supprimer** ces trois remplacements (ou conserver uniquement `...`→`…`). Sinon l'apostrophe reste `´`, présent dans le japonais mais avec chasse pleine.
5. Espaces avant `! ? : ; »` : la traduction utilise des espaces ordinaires (pas de U+00A0/U+202F dans les TSV). Le retour à la ligne doit donc **interdire la coupure avant** ces signes (et après `«`).
6. Les caractères non latins restent possibles (`※ ★ ☆ ♪ ⑯ ―`) : le moteur doit rester **hybride** (latin → atlas français, le reste → chemin japonais existant `FUN_0052DC54`).

---

## 3. Décisions de conception

| # | Décision | Justification |
|---|---|---|
| D1 | **Ne pas toucher aux textures 0-5** ; textures 6/7 ajoutées. | La ROM reste fonctionnelle sans hook ; retour arrière trivial ; pas de perte de kanji. |
| D2 | **Cellules fixes + tables d'avance** (et non un moteur BMFont à rectangles libres). | Réutilise la géométrie quad existante ; UV = (col,ligne)×cellule ; une table de 165 octets d'avance. |
| D3 | **ft_sml 16 px en 1:1**, mise à l'échelle `charH/16` pour 14/12/22. | La majorité des textes sont à 14 (49 écrans) et 12 (32) ; 16 pour les fenêtres de message. Si la netteté à 14/12 déçoit : cuire des pages dédiées (rastérisation propre) plutôt que d'agrandir/réduire. |
| D4 | Moteur **hybride** : `GlyphLookup(code)` → (page française, index) sinon chemin japonais. | Garde `※ ★ ♪` et tous les kanji restants. |
| D5 | **Une seule fonction d'avance** `GlyphAdvance(code, charW, charH, spacing)` utilisée par mesure, rendu et retour à la ligne. | Évite que boîte et texte divergent (cause n°1 de bugs prévisible). |
| D6 | **Retour à la ligne unique**, fait au prétraitement (`FUN_0052C690`) par insertion de `\n`. | La logique de coupe est dupliquée dans mesure et rendu ; la déplacer élimine le doublon. |
| D7 | Boîtes : **formule générale** `hauteur = marge + n×(charH+interligne)`, ancrée au lieu de cascades `if`. | Supporte 5+ lignes ; un seul code remplace 8 fonctions presque identiques. |

---

## 4. Plan par phases

### Phase 0 — Fait
ROM extraite, atlas FR cuit, entrée 0 patchée (textures 6/7), pipeline reproductible, non-régression de démarrage.

### Phase 1 — Banc d'essai de hook (½ journée)
1. Créer `overrides/` ; premier override **purement diagnostique** : `RECOMP_OVERRIDE(0x001115EC)` → `CALL(RECOMP_ORIGINAL)` puis journaliser (`fprintf`) le nombre de textures du jeu (`police+0x11E0 → +0xC`, 8 attendues) **[À vérifier : 8 textures chargées]**.
2. `3dsrecomp build sangokushi.cci --overrides overrides/` (long la première fois), puis `zakuro rom_work/game_fr.cxi`.
3. Écrire `1` à `0x007DBC3C` (drapeau ASCII proportionnel) → constater que l'ASCII passe par `FUN_0052DA8C` (texture 3) : **preuve que le chemin existe**, et banc visuel de l'ancien atlas.
4. Capture d'écran sous Zakuro (fenêtre, ou `--headless` + dump) pour comparer ; définir 5 écrans de référence (titre, dialogue 1 ligne, dialogue multi-lignes, menu, combat) — scripter l'entrée si Zakuro l'autorise, sinon sauvegarde (`--data`).

**Critère :** log « 8 textures » ; un texte ASCII affiché via le chemin proportionnel.

### Phase 1 — Résultats (exécutée)
- `3dsrecomp build sangokushi.cci --overrides ../overrides` : **≈ 2 min 20** (249 unités), installe `~/Library/Application Support/3dsrecomp/000400000018B000.dylib` ; `zakuro game_fr.cxi` l'utilise automatiquement (« running recompiled code… 188360 entry points », 0,1 % interprété). Les overrides sont dans `overrides/diag_font.c`.
- **[Vérifié] Le jeu charge notre entrée 0 patchée** : `FUN_00112FDC` reçoit un G1T de 1 163 420 o avec `tex_count = 8`.
- **[Vérifié] Le groupe de textures a 8 emplacements** (`police+0x11E0 → [+8] → [+0xC]`, pas 0x40) : slot 3 = 256² (ASCII d'origine), **slots 6 et 7 = 256×256 A4 valides** (0x8000 octets en VRAM, 0x181C7800 / 0x181CF800). Les indices de texture 6 et 7 sont donc utilisables. Le plan B (remplacer la texture 3) n'est pas nécessaire.
- **[Vérifié]** `police+0x1214` = 0 après l'init.
- **Leçon d'override** : un code placé *après* `CALL(original)` est ignoré quand l'original déclenche un `svc` (E/S fichier, p. ex. `0x001115EC`) — l'hôte reprend le code d'origine. Journaliser **avant** l'appel, ou accrocher une fonction sans E/S (comme `0x00112FDC` côté sortie, qui elle revient bien).
- En 9000 images sans entrée manette, aucun texte n'est dessiné (`0x0052D340` jamais appelée : écran titre/logos). Les tests visuels demanderont d'injecter des entrées ou de forcer un appel depuis un override de test.

### Phase 2 — Glyphes français + avance variable (cœur)
Fichier `overrides/frfont.h` (inclut `font_sml.h`/`font_nrm.h` générés) :
- `fr_lookup(code) → index | -1` (recherche binaire dans `fr_sml_codes`).
- `fr_advance(index, charH)` = `round(adv × charH/16)` (+ règle d'espacement unique).
- `fr_emit_glyph(ctx, font, x, y, z, index, charH)` : remplit la structure quad `{x0=x+bearing×s, y0=y, x1=x0+16s, y1=y+16s, z, tex_ptr, [6]=6, u=col*16/256…}` et appelle **`FUN_0052D848`** (qui gère ombre, couleur, listes de quads, plafond 756).

Overrides :
| Adresse | Fonction | Travail |
|---|---|---|
| `0x0052DEBC` | `KTGL_Font_DrawFormattedString` | Réécrire la branche « caractère » : si `fr_lookup(code) ≥ 0` → `fr_emit_glyph` + `fr_advance`; sinon chemin d'origine (`FUN_0052DC54`). Espace (0x20) = `fr_adv(' ')`. Garder tout le reste (ruby, icônes, couleurs, alignement). |
| `0x0052CEA4` | mesure | Même `fr_advance` ; même gestion espace. **Obligatoire** : sinon boîtes ≠ texte. |
| `0x0052DC54` / `0x0052DA8C` | glyphes d'origine | Conservés (chemin hybride). `0x0052DA8C` inutile pour le latin. |
| `0x001115EC` (post) ou `0x00120E0C` (post) | init / reset | Rien d'obligatoire (drapeau `+0x1214` non utilisé par le nouveau chemin). |

**Tests :** (a) chaîne « Éléphant à l'école ! » dessinée via `FUN_0052DC28` depuis un override de test ; (b) comparaison largeur mesurée vs dessinée ; (c) 3 tailles (16/14/12) ; (d) caractères hors police → repli ■.
**Critère :** accents corrects, avance variable, aucun artefact aux jointures (cellules complètes se recouvrent sur de l'alpha nul).

### Phase 2 — Résultats (exécutée)
Fichiers : `overrides/frfont.h` (logique), `overrides/fr_text.c` (overrides), `overrides/diag_font.c` (auto-tests, activés par `FR_SELFTEST=1`), `overrides/font_sml.h` (généré par `bake_french_atlas.py`, copié par `build_all.sh`). Les `.c` incluent `frfont.h` par chemin absolu (le build ne copie que les `.c`).

| Override | Rôle |
|---|---|
| `0x0052D340` | pose `police+0x1214 = 1` à chaque dessin (active le chemin ASCII proportionnel du moteur) puis appelle l'original |
| `0x0052DA8C` | glyphe ASCII : si le code est dans la table française → un quad (texture 6) via `FUN_0052D848`, renvoie l'avance ; sinon original |
| `0x0052DC54` | autres glyphes (accents, `« » … ★ ♪`) : table française d'abord, sinon chemin japonais d'origine |
| `0x0052CEA4` | **mesure** : port C fidèle de la fonction d'origine (préprocess original + boucle C) ; largeurs latines depuis la table française |

**Résultats [Vérifié]**
- **Port de la mesure = original** : 720 cas (15 chaînes dont kana, ruby `【大丈夫：だいじょうぶ】`, tags de couleur/taille, icônes, `\n`, texte long × 4 tailles × 4 largeurs de coupe × 3 espacements × 2 interlignes), en mode « tables d'origine » : **0 divergence** (nombre de glyphes, largeur, hauteur, drapeaux, état de la police).
- **Dessin par le vrai chemin du moteur** : « Éléphant à l'école ; ~ ! « oui » … » → 25 quads (tous les glyphes), tous sur la texture 6, UV corrects ; l'aperçu reconstitué depuis les quads capturés (`fr_patch/preview_quads.py`) montre un texte français correct, à chasse variable, accents compris.
- **Bugs de la police d'origine contournés** : dans la table ASCII d'origine, `;` `|` `}` `~` n'étaient pas trouvés (le code 0x3B est remplacé par un doublon de `,` et l'entrée 95 casse le tri) → ils s'affichaient comme `?`. Notre table n'a pas ce défaut. De plus la mesure d'origine traitait `~` comme pleine chasse alors que le dessin le traitait en ASCII.

**Corrections d'hypothèses [Vérifié sur le code ARM]**
- Signature des fonctions de glyphe : **`s0,s1,s2` = x, y, z (flottants), `r0` = objet police, `r1` = code**. (Le z du quad est un flottant.) L'ABI n'est pas celle déduite de Ghidra (qui avait décalé les arguments).
- `.rodata` **n'est pas modifiable** par un override (`mem_write32` ignoré) ; `.data` l'est. Les tables françaises vivent donc dans les overrides (hôte).
- `CALL` d'une fonction non surchargée : `ctx->r[15] = addr; ctx->thumb = 0; CALL(f_XXXXXXXX);` (`RECOMP_ORIGINAL` n'existe que pour les fonctions surchargées).
- Les tests longs doivent relever `ctx->budget` (sinon le `CALL` sort sur `EXIT_BUDGET` et l'hôte reprend le code d'origine au milieu du test).

**Limites connues (volontaires, traitées en phase 3/4)**
- Pas de retour à la ligne pour le latin (le chemin ASCII du moteur ne coupe jamais) → les textes longs dépassent tant que `WrapFrench` n'est pas en place.
- Avance du latin = `round(adv16 × charW / 16)`, **sans** l'espacement `+0x1228` (volontaire).
- Rendu à l'écran réel (couleurs, ombre, z) non encore vu : le jeu n'atteint aucun écran de texte en mode sans fenêtre faute d'entrées.

### Phase 3 — Retour à la ligne français
`WrapFrench(buf, wrapPx, charW, spacing)` appelée à la fin de **`FUN_0052C690` (0x0052C690)** :
- coupe aux espaces ; coupe sur le dernier espace tenant dans `wrapPx` ;
- **interdit** la coupure avant `! ? : ; » % ) , . …` et après `«` ; traite `-` comme point de coupe ;
- un mot plus long qu'une ligne est coupé au caractère ;
- ne touche pas aux séquences de contrôle (0x10–0x17, ruby, tags) et ne compte pas les `\n` insérés dans le compteur « machine à écrire » (`param_4`).
Puis **neutraliser** la coupe automatique dans `0x0052DEBC` (bloc `LAB_0052E8B0…E9F4`) et `0x0052CEA4` (bloc `LAB_0052D248…D2F8`).

**Tests :** corpus = toutes les répliques des TSV ; assertions : (i) aucune ligne ne dépasse `wrap`, (ii) pas de ligne commençant par `! ? : ;`, (iii) nombre de lignes mesuré = nombre de lignes dessiné. Idéalement implémenter `WrapFrench` aussi en Python pour valider **hors émulateur** sur les 40 000 lignes (génère des statistiques de lignes max par type : dimensionne les boîtes).

### Phase 3 — Résultats (exécutée)
Fichiers : `overrides/frwrap.h` (algorithme, C pur, testable sur l'hôte), `overrides/fr_text.c` (intégration), `fr_patch/wrap_corpus.py` + `fr_patch/wrap_test.c` (test sur tout le corpus).

**Conception**
- Le retour à la ligne se fait **une seule fois**, dans le tampon prétraité de `FUN_0052C690` (override `0x0052C690`) : texte complet prétraité → `fr_wrap_text` → limite « machine à écrire » appliquée **après** la coupe (le texte ne saute donc pas de ligne pendant l'écriture). Mesure et dessin voient le même tampon.
- Règles : coupe aux espaces (l'espace de coupe devient `\n`), après un tiret entre deux lettres, entre deux caractères japonais (kinsoku : pas de début de ligne sur `! ? : ; % ) , . » … ’ 、 。 」 ー`, pas de fin de ligne sur `« ( 「`), mot trop long coupé au caractère ; les espaces avant `! ? : ; »` ne sont jamais des points de coupe (le mot précédent suit le signe). Le compte des codes « machine à écrire » ignore les `\n` insérés et les codes de contrôle, comme l'original.
- Texte avec **ruby** (`0x11`) : comportement d'origine conservé (aucune coupe française, coupe japonaise d'origine active).
- `0x0052CEA4` (mesure, port C) : fait la même coupe quand elle prétraite elle-même (p5 ≠ 0) ; pour du texte déjà coupé, la coupe japonaise d'origine est désactivée. `0x0052DEBC` (dessin) : sa coupe automatique est neutralisée pendant l'appel (`+0x1238` mis à 0x7FFFFFFF puis restauré), **sauf en alignement à droite** (le moteur a besoin de `+0x1238`).

**Résultats [Vérifié]**
- Corpus complet (**42 572 chaînes** traduites, balises converties comme le moteur, variables remplacées par 9 glyphes) × largeurs 120/200/301/400 × tailles 16/14/12 : **0 ligne plus large que la coupe, 0 contenu perdu**. Les 56 lignes commençant par un signe interdit (constant quel que soit la largeur) viennent du texte source (ligne qui commence par `…`/`!` après un `\n` explicite). Distribution à 301 px / 16 px : 31 827 chaînes d'1 ligne, 5 354 de 2, 3 520 de 3, 1 231 de 4, 190 de 5, 258 de 6, 129 de 7, 59 de 8, 4 de 9 → **les boîtes doivent supporter jusqu'à 9 lignes** (8 à 14 px, 7 à 12 px), mais 99,5 % tiennent en ≤ 4.
- Dans l'émulateur, par le vrai chemin `FUN_0052D340` : « Mais qu'est-ce que c'est que cette histoire de mots très longs qui doivent passer à la ligne ?! Voilà. » à 150 px → 6 lignes (pas de 18 px = 16 + interligne 2), `?!` reste collé à « ligne » ; avec limite machine-à-écrire 30 : les 2 premières lignes sont identiques à celles du texte complet, retour = 0 (« pas fini »).
- Non-régression : le port de la mesure reste identique à l'original (720 cas, 0 divergence) ; les auto-tests désactivent la coupe via `fr_wrap_disabled`.

**Limites / à surveiller**
- Alignement à droite + accents : la coupe japonaise d'origine du dessin peut encore se déclencher en bout de ligne pleine (cas rare).
- Les mises en page de fenêtres (phase 4) mesurent avec `+0x1238 = 0x12D` : le texte sera désormais coupé à 301 px ; la hauteur des boîtes dépend du nombre de lignes retourné (`FUN_0052CE38`) — il faut maintenant supprimer les cascades `if (lignes == k)`.
- Aucune vérification visuelle en jeu réel (même limite que la phase 2).

### Phase 4 — Boîtes et bulles
Ordre de risque croissant :
1. **Largeur de wrap** : remplacer `0x12D` (301) dans les mises en page par `largeurBoîte − marges` (constante ajustable).
2. **Fenêtres de message** (8 fonctions) : `0x00533D70`, `0x005586CC`, `0x0055833C`, `0x00265900`, `0x00272E60`, `0x002C7F7C`, `0x00353308`, `0x0054179C`. Approche : un wrapper `ComputeMessageBox` qui appelle l'original puis **réécrit** `+0x24/+0x28/+0x2C/+0x30` (boîte), `+0x254/+0x258` (texte), `+0x26C/+0x270` (taille mesurée) avec la formule générale (D7), sans changer le reste. Valider boîte par boîte en forçant des répliques de 1, 2, 3, 5 lignes.
3. **Machine à écrire / pages** : `0x005412E0`, `0x00541710`, `0x0021B87C` (10 pages × 0x1FF o), `0x001EB7FC` (0x200 o) — vérifier les noms de variables longs (§2.5-3).
4. **Bulles avatar/tutoriel** : `0x00236170`, `0x00237858`, `0x002372A4`, `0x002373E0`, `0x00237C28`, `0x00237D90`, `0x002DE710`, `0x002DFA54`, `0x002DFAD8`, rectangle commun `0x00542430`. Retirer les minima (`w ≥ 0x1C`, `h ≥ 0x0E`) et le seuil `charW×18`, recalculer marges de `FUN_002DE710`, plafonner à l'écran.
5. **Libellés d'écran** (≈ 130 fonctions, CSV) : appliquer `FitWidth` (`0x0052D44C`) aux libellés qui débordent ; le reste se corrige à la main au fil des captures. Les 15 écrans qui l'utilisent déjà en profitent automatiquement.

### Phase 4 — Résultats (exécutée) — détail et suivi ARM dans `JOURNAL_MODIFICATIONS.md`
- **Constat** : les 8 mises en page de fenêtres adaptent déjà la hauteur au nombre de lignes, mais au-delà de ~7 lignes (0,6 % des répliques à 301 px) la boîte sort de l'écran de 240 px (hauteurs jusqu'à 284, `y` jusqu'à −30) et certaines boîtes à hauteur fixe (`0x00265900`, `0x002C7F7C`) laissent déborder le texte (jusqu'à +169 px) ; `0x00353308` types 6/8 : texte 9 px plus large que la boîte (largeur de coupe 301 pour une boîte de 284).
- **Correctif** (`fr_fix_message_box`, wrapper après l'original sur 7 fonctions) : si la boîte ne tient pas, re-mesure à 16 → 14 → 12 px, conserve les marges, recentre, borne à l'écran. Comportement inchangé quand tout tient (les géométries d'origine à 1-4 lignes sont conservées).
- **Mesure sur 108 chaînes (1 à 9 lignes) × 2 modes × types** avec le vrai code du jeu (fausse vtable `bx lr`) : avant → jusqu'à 108/108 cas hors cadre ; après → **0 cas hors écran / hors boîte** (restes : `0x0055833C` 1 px en bas, déjà présent à 1 ligne dans l'original ; `0x00541794` boîte système, 2 textes de 299 caractères).
- **Bulles** : la mesure des bulles n'avait aucune largeur de coupe ; ajout d'une largeur de 252 px aux 6 sites d'appel (identifiés par scan des `bl 0x0052CEA4` dans `FUN_00236170/00237858/002DEA30/002DFAD8`) et même largeur au dessin (`FUN_002DFA54` → `+0x26C`). Test : 128 caractères → 4 lignes, 243 px.
- **Outillage** : `fr_patch/fast_build.sh` (≈ 1 s) au lieu du build complet de 2 min 30 ; 14 overrides « pass-through » réservés pour les prochaines modifications. Tests : `FR_BOXFILE=… zakuro …` (+ `fr_patch/box_report.py`).
- **ARM** : premier patch d'octets (`0x00111714`, drapeau ASCII proportionnel) et pipeline ExeFS (`fr_patch/arm_patches.py`, `build_arm_rom.sh`) vérifiés ; cavités de code candidates listées dans le journal.

### Phase 5 — Intégration traduction
1. `process_dialogue_string` : retirer les remplacements `'`/`"`; ajouter option pour `...`→`…`.
2. Re-générer les scripts (SangoKuro `build`) puis appliquer **le patch d'entrée 0** sur le `LINKDATA_A.BIN-new` produit : `patch_linkdata.py LINKDATA_A.BIN-new out.bin 0 build/entry0_fr.g1t` (compatible, car les deux outils partagent le même format de table).
3. Lint de la traduction : octets/page ≤ 0x1FF, chaînes contenant des caractères hors atlas (liste vide à ce jour hors `■`), tags orphelins.

### Phase 5 — Résultats (exécutée)
Outils : `fr_patch/lint_translation.py`, `fix_translation_tags.py`, `apply_translation.py`, `patch_linkdata.py` (`patch_many`), `build_all.sh` (lint → traduction → atlas → ROM en ≈ 6 s).

1. **Apostrophes / guillemets** : `process_dialogue_string` (générateur modulaire **et** `Sangokushi-Pipeline.py`) ne remplace plus `'`→`´` ni `"`→`″` (ces glyphes existent dans la police française) ; `...`→`…` conservé ; ancien comportement via `SANGO_LEGACY_QUOTES=1`.
2. **Le générateur est maintenant fidèle aux fichiers du jeu** : test de **round trip** (textes japonais d'origine → générateur → comparaison octet par octet avec les 1 308 scripts de `LINKDATA_A.BIN`) : au départ 852 identiques / 456 différents ; après alignement sur le format réel (**entrées Type 2 et 4 alignées sur 4 octets, chaînes Type 3 alignées sur 4 octets sans rembourrage de 16, dernière chaîne non rembourrée**) : **1 308 / 1 308** équivalents (19 fichiers Type 3 ne diffèrent que par des octets résiduels dans le rembourrage entre chaînes). Ces corrections suppriment un risque réel : l'ancien format décalait les données du bytecode Type 4 (offset non aligné).
3. **Lint** (`lint_translation.py`, 43 267 lignes) : couverture des glyphes (atlas français, puis police japonaise du jeu), budget d'octets (≤ 511), balises (équilibre, retour couleur `【e】`, **mots-clés moteur** : préfixes `Yk It Base Clan Chr Unit Str Val` + 4 mots japonais, table du binaire `0x0067D9C0`, comparaison par **préfixe** comme `FUN_001EB224`), identité des variables avec l'original, lignes après coupe française (≤ 9), lignes non traduites, préfixe Type 3, lignes de bytecode Type 4. Résultat : **0 erreur**, 194 avertissements (133 doubles espaces, 60 espaces autour d'un `\n`, 1 ruby `【旗：drapeau】`), 204 infos (> 6 lignes).
4. **Deux vraies erreurs de traduction corrigées** (`fix_translation_tags.py`, colonne traduite uniquement, aller-retour CSV exact en CRLF) : **78 fois `【Partenaire d'échange】` → `【交換相手】`** (mot-clé reconnu par le moteur : traduit, il aurait été affiché tel quel entre crochets) et **2 balises `【Arachnus Yuan Shao】`/`【Crapop Yuan Shu】`** transformées en texte simple. Sauvegarde dans `fr_patch/build/tsv_backup/`.
5. **Application** (`apply_translation.py build`) : génère les scripts depuis les TSV, vérifie que chaque entrée est compressée ou non comme dans l'archive, et patche **1 308 scripts + l'entrée 0** dans `LINKDATA_A.BIN` en une passe (ajout en fin d'archive, table re-pointée, relecture vérifiée) sans extraire les 482 Mo : ROM `rom_work/game_fr.cxi`.
6. **Test en émulation (code recompilé + overrides)** : premier texte réel du jeu (« Sauvegarde dans le journal en cours… », 110 caractères, fenêtre `0x00533D70`) mesuré, coupé et dessiné ; 12 000 images sans erreur.
7. **Bug trouvé grâce à ce premier texte réel** : « branch to unmapped 0x6F63206C » = du texte utilisé comme adresse de retour. Cause : quand le **budget d'instructions** s'épuise pendant un `CALL` imbriqué dans un override, l'hôte reprend la fonction appelée et **la fin de l'override est ignorée** (pile `r13` jamais restaurée…). Les tests précédents l'évitaient en relevant le budget à la main. Correctif : `FR_ENSURE_BUDGET(ctx)` en tête de tous les overrides qui font quelque chose après un `CALL` (mesure, préprocess, rendu, glyphes via `FR_EMIT`, boîtes, bulles). Ne concerne pas un portage ARM natif.
8. **Limite** : la ROM démarre jusqu'à un écran de confirmation de sauvegarde ; les autres écrans (menus, dialogues) n'ont pas été atteints en mode sans fenêtre.

### Phase 6 — Reliquats
- **Textes dessinés en images** (menus/ boutons dans des G1T ou SARC `.bflim`/`.bflyt` avec du japonais pré-rendu) : hors portée de la police ; inventaire par l'explorateur web `linkdata_tool.py web` ; remplacement texture par texture (encodeur A4/ETC1 à étendre).
- Noms de Yo-kai/personnages affichés par les fonctions de « fiches » (largeurs fixes).
- Ruby/furigana : désactivé pour le français (supprimer `【kanji：kana】` restants).

### Phase 7 — QA
Matrice : écrans (≈ 20) × tailles (16/14/12) × longueurs (1/3/5 lignes) × lettres larges (`W M Œ`) × variables longues. Mesures automatisables : compteur de quads/image (plafond 756), échecs de `FUN_0052D340` (retour 0), troncatures 0x200.

---

## 5. Risques et questions ouvertes

| Risque / question | Mitigation |
|---|---|
| Les textures 6/7 ne sont pas créées ou l'indice est refusé | Test phase 1 ; plan B : remplacer le contenu de la **texture 3** (ASCII, 256², déjà inutilisée pour le latin) par la page `sml` et utiliser l'indice 3 |
| Le chemin `FUN_0052D848` impose des champs inconnus du quad | La structure est déjà documentée ([0..10], [12]) ; copier un quad produit par `FUN_0052DC54` en mode traçage |
| Netteté à 14/12 px (mise à l'échelle d'un bitmap 16 px) | Baker des pages dédiées 14 et 12 px depuis `ft_sml` ré-échantillonné ; place suffisante (page 256² = 256 cases) |
| Limite 756 quads / 128 appels par image | Ne concerne pas un dialogue normal (≈ 100 car.) ; surveiller menus denses |
| Variables de tags longues (`【Str1】`…) | Mesure après expansion (déjà le cas si la mesure se fait sur la chaîne expansée) — test dédié |
| `3dsrecomp build` long, première fois | Lancer en arrière-plan dès la phase 1 ; les overrides ne relancent que la compilation concernée |
| Compatibilité matérielle réelle (Luma/console) | Textures A4 standard, aucun changement d'exécutable → compatible ; tester aussi sur émulateur Azahar |

---

## 6. Mises à jour du rapport précédent

- « Atlas ASCII = texture d'indice 3 » **confirmé** (entrée 0, tex 3, 256×256 A4) ; géométrie réelle = cellules 14×28, **16 colonnes, 6 lignes utilisées** (0x20–0x7E + ■), 3 lignes libres en bas.
- « Ensemble de textures créé par `FUN_001115EC` via `load_entry(0,…)` » **confirmé** : entrée 0 de `LINKDATA_A.BIN`.
- Les 6 textures de l'entrée 0 correspondent 1:1 aux 6 descripteurs (tailles identiques).
- Ajout : les chemins `: / -` utilisent déjà la texture ASCII ; tous les autres ASCII sont affichés en pleine chasse depuis les textures japonaises (cases `Ａ–Ｚ ａ–ｚ`).
