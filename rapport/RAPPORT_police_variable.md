# Yo-kai Watch Sangokushi — Rapport d'analyse : police à chasse variable, accents et bulles de texte

Sources analysées : `code.c` (décompilation Ghidra, 16 253 fonctions) et `exefs.elf` (ARM32, tout en mode ARM, `.text` 0x100000, `.rodata` 0x60C000, `.data` 0x674000, `.bss` 0x6B0000).
Toutes les adresses sont des adresses virtuelles 3DS. Toutes les fonctions citées sont en **mode ARM** (adresse paire dans les `RECOMP_OVERRIDE`).
Annexe complète des 130 fonctions appelantes : `annexe_appelants_texte.csv`.

> Légende de fiabilité : **[Confirmé]** = lu dans le C et/ou vérifié dans l'ELF. **[Déduit]** = inférence raisonnable. **[À vérifier]** = ne peut pas se prouver avec le seul exécutable (nécessite le romfs ou l'émulateur).

---

## 1. Résumé

1. Le rendu de texte tient dans **un seul module compact, 0x0052C690 → 0x0052EAB8**, autour d'un objet « police » global à **0x007DAA28** (≈ 0x1254 octets). Il est appelé depuis 130 fonctions d'écran. C'est un très bon point d'ancrage pour des hooks.
2. Le texte est du **UTF-8, mais chaque caractère est empaqueté en un entier big-endian** (`é` = 0xC3A9, `あ` = 0xE38182) par `UTF8_iter` (0x0052D79C). Les 4 octets (≥ 0xF0) ne sont pas gérés. Les codes de contrôle sont 0x10–0x17 + `\n`.
3. **Aujourd'hui l'ASCII est affiché en pleine chasse** : `A` devient `Ａ` (U+FF21) et se dessine dans l'atlas japonais, avec une avance fixe `charW + espacement`. C'est la cause directe de votre problème de rendu.
4. **Bonne nouvelle : le moteur contient déjà un chemin ASCII proportionnel**, inutilisé : un drapeau `police+0x1214` (0x007DBC3C), mis à 0 à l'init et jamais mis à 1. S'il vaut 1, l'ASCII passe par `FUN_0052DA8C` avec une **table de largeurs par glyphe** (146 entrées, `.data` 0x0067D3F2). Il reste à ajouter les **lettres accentuées** (absentes de tous les atlas) et à corriger le **retour à la ligne** (conçu pour le japonais).
5. Les « bulles » sont de deux familles : (a) **fenêtres de message** (8 fonctions de mise en page, boîtes de 320/400 px, largeur de texte codée en dur à 301 px, hauteur/position choisies par *tables if/else selon le nombre de lignes*) ; (b) **bulles de dialogue d'avatar/tutoriel** (`FUN_002DE710`, `FUN_002373E0`, `FUN_002372A4`…) dont les marges et positions sont aussi codées en dur.
6. Pièges à anticiper : tampons de **512 octets** pour chaque page de message, **1024 octets** pour la mise en forme, **756 quads** par couche et par image, comptage « caractères affichés » (machine à écrire) qui suppose 1 glyphe = 1 caractère.

---

## 2. Architecture du pipeline de texte

```
écran (130 fonctions "draw")                 mise en page (8 fonctions + bulles)
   │ ResetTextState 00120E0C                      │ Measure 0052CEA4 / CountLines 0052CE38
   │ SetColorPreset 0052DBF4, Alpha 0052DA38      │ → calcule w/h, choisit hauteur/pos de la boîte
   ▼ DrawText 0052DC28 (x,y entiers)              ▼
   FUN_0052D340 (x,y float, nbCharMax, texte, z)
      ├─ FUN_0052C690  prétraitement : texte → tampon interne (1024 o)   [ruby 【base：ruby】, tags, icônes, compteur machine à écrire]
      │       ├─ FUN_0052D4F0  analyse des tags 【b】【r】… 【倍角】…
      │       ├─ FUN_0052D988  écrit un code (entier packé) en UTF-8
      │       └─ UTF8_iter 0052D79C
      ├─ KTGL_Font_DrawFormattedString 0052DEBC   boucle de rendu (avance, retours à la ligne, alignement)
      │       ├─ FUN_0052DA8C  glyphe ASCII demi-chasse proportionnel   (atlas #3)
      │       ├─ FUN_0052DC54  glyphe "normal" (16/14/12 px, ruby 8 px) (atlas 0,1,2,4,5…)
      │       │       └─ binary_search 0052C9F4  (code → index de glyphe)
      │       └─ FUN_0052D848 → FUN_0052CBC0 / FUN_0052CCDC  (crée le quad, ajoute à la liste de la couche)
      └─ post-traitement des quads créés (FUN_00131A68, profondeur/priorité)
```

### 2.1 Structure de l'objet police (base 0x007DAA28) [Confirmé sauf mention]

| Offset | Rôle |
|---|---|
| +0x0004… / +0x0BD4 | tableau de pointeurs de quads couche A + compteur (max **0x2F4 = 756**) |
| +0x0BD8… / +0x0FD8 | idem couche B (ombres/contours) |
| +0x0FDC[0x80], +0x11DC | pile des paramètres z/priorité par appel (128 appels max par image) |
| +0x11E0 | ensemble de textures de police (créé à l'init, voir §3.3) |
| +0x11E4 | 4 couleurs de sommets (dégradé) ; alpha = octet +3 de chaque (cf. `FUN_0052DA38`) |
| +0x11F4 / +0x120C | drapeau « couleur preset » / identifiant du preset (table 0x007EB3A8) |
| +0x11F8, +0x1208 | couleurs d'ombre / drapeau |
| **+0x1214** | **drapeau « ASCII proportionnel »** (toujours 0 aujourd'hui) |
| +0x1218 | alignement : 0 gauche, 1 droite (par rapport à `+0x1238`), 2 centré (x **et** y) |
| +0x1220 / +0x1224 | largeur / hauteur de caractère (valeurs utilisées : **12, 14, 16**, 22 par tag, 8 ruby) |
| +0x1228 | espacement entre caractères (défaut **−1**) |
| +0x122C | interligne (défaut 2 ; 8 dans la plupart des fenêtres de message) |
| +0x1230 / +0x1234 | espacement et mode du ruby (furigana) |
| **+0x1238** | **largeur de retour à la ligne** (défaut 0x7FFFFFFF ; **0x12D = 301** dans les fenêtres de message) |
| +0x1240/+0x1244 | plage de décalages d'ombre (table 0x0061BF34, `FUN_0052CAA4`) |
| +0x1248 | pool de quads alternatif (sinon allocation globale) |
| +0x1250 | alpha global |

### 2.2 Descripteurs de police (rodata 0x0061BF74, 6 × 0x18 octets) [Confirmé]

```
+0x00 u32 table des codes (triée, entiers packés)     +0x08 u16 largeur atlas    +0x0A u16 hauteur atlas
+0x04 u32 table des largeurs (octets) ou 0            +0x0C u16 largeur cellule  +0x0E u16 hauteur cellule
+0x10 u16 colonnes  +0x12 u16 lignes  +0x14 u16 dernier index (inclusif)  +0x16 u16 capacité par page
```

| Adresse | Police | Table codes | Largeurs | Atlas | Cellule | Glyphes | Cases libres* |
|---|---|---|---|---|---|---|---|
| 0x61BF74 | 16 px | 0x615350 | – | 1024×1024 | 16×16 | 2139 | **1957** |
| 0x61BF8C | 14 px | 0x6174BC | – | 1024×512 | 14×14 | 2139 | 489 |
| 0x61BFA4 | 12 px | 0x619628 | – | 1024×512 | 12×12 | 2139 | 1431 |
| **0x61BFBC** | **ASCII demi-chasse** | 0x61BCEC | **0x67D3F2** | 256×256 | 14×28 | 146 (+ espace) | – |
| 0x61BFD4 / 0x61BFEC | ruby 8 px (2 variantes) | 0x61B794 / 0x61BA40 | 0x67D29C / 0x67D347 | 128×128 | 8×8 | 172 (kana) | – |

\* capacité de page − glyphes. Les trois grandes polices ont les **mêmes 2139 codes** (tri croissant vérifié) : kana, ~1 900 kanji, symboles, et **Ａ–Ｚ ａ–ｚ pleine chasse (index 2058-2138)**. **Aucune lettre latine accentuée** dans aucune table.

La table ASCII (0x61BCEC) contient 0x20–0x7E, puis les octets bruts 0xA1–0xD2 (demi-chasse kana). Ses largeurs (en 1/14ᵉ de cellule) : `i`/`l`/`I`/`|` = 6, `f`/`r`/`t` = 8, `J` = 10, majorité = 12, `m n o w M O Q W` = 14. Ce sont déjà des métriques proportionnelles utilisables.

### 2.3 Codes de contrôle [Confirmé]

| Code | Effet (rendu `0052DEBC`) |
|---|---|
| 0x0A | saut de ligne : `y += charH + interligne` |
| 0x10 + octet | icône (bouton…) d'indice octet−0x40 ; générée par `FUN_0052C690` pour U+E000–U+E07F |
| 0x11 | marqueur de ruby (furigana) : `【base：ruby】` |
| 0x12 + octet / 0x13 | preset de couleur / retour à la couleur normale |
| 0x14 / 0x15 / 0x16 | taille restaurée / **22×22** / **12×12** |
| tags 【…】 | `b r g p B R G y e` (couleurs), `倍角` (double), `全角`, `縮小`, `幅小` (taille) — `FUN_0052D4F0` |

Attention aux collisions : le rendu teste `(code & 0xFF) − 0x10 < 0x10` et `(code & 0xFF) − 0x20 < 0x5F` sur l'**octet bas**. Les octets bas des séquences UTF-8 2 octets (0x80–0xBF) ne rentrent dans aucun de ces tests : **les accents UTF-8 normaux ne collisionnent pas**.

---

## 3. Fonctions à modifier — par objectif

### 3.1 Objectif A — Police à chasse variable (ASCII + latin)

#### A1. Activer le chemin proportionnel existant (changement minimal)
| Cible | Modification |
|---|---|
| **`FUN_001115EC`** (init de l'objet police, appelé depuis l'init du moteur à ~0x00105xxx) | Hook post-appel : écrire `1` à `0x007DBC3C` (`police+0x1214`). Effet immédiat : tout l'ASCII passe par `FUN_0052DA8C` avec la table de largeurs. |
| Table de largeurs `.data 0x0067D3F2` | Modifiable (RW). Ajuster les métriques de l'ASCII sans toucher au code. |

Conséquence **[Déduit]** : avec le drapeau, l'avance ASCII = `(charW/2 × largeur[i]) / cellW`, **sans** l'espacement `+0x1228` (il n'est pas ajouté dans `FUN_0052DA8C`). À re-régler si l'on veut un crénage cohérent.

#### A2. Ajouter les lettres accentuées (la vraie fonctionnalité manquante)
Il faut des **glyphes** (texture) et des **entrées de tables** (codes + largeurs). Caractères français nécessaires : `à â ä ç é è ê ë î ï ô ö ù û ü ÿ œ æ À Â Ç É È Ê Î Ô Ù Û Œ « » ’ …` (≈ 45).

| Fonction | Adresse | Pourquoi / quoi changer |
|---|---|---|
| `FUN_0052DA8C` | 0x0052DA8C | Dessine un glyphe ASCII. Elle lit le descripteur `DAT_0052DBF0` (= 0x61BFBC). Réécrire pour : descripteur étendu en RAM, largeur lue dans une table étendue, **UV** calculées avec la géométrie réelle du nouvel atlas. |
| `binary_search` | 0x0052C9F4 | Résolution code → index. À garder, mais avec une table étendue : les nouveaux codes (`0xC380…0xC3BF`, `0xC592`/`0xC593`, `0xC2AB`/`0xC2BB`, `0xE28099`…) sont tous numériquement **supérieurs à 0xD2** (dernier code actuel), donc on peut les **ajouter en fin de table** sans re-trier ; il faut seulement mettre à jour le champ « dernier index » (`+0x14`). Le repli (`param_4` = `？`) sert de glyphe « manquant ». |
| `FUN_0052DC54` | 0x0052DC54 | Chemin des polices 16/14/12 : choisit la police selon `charW`/`charH` et un seuil de code (`< 0x236`), cherche l'index, calcule UV, renvoie l'avance `charW + 0x1228`. À remplacer/hooker pour router **tout le latin** (y compris accentué) vers l'atlas proportionnel et renvoyer une avance **par glyphe**. |
| `KTGL_Font_DrawFormattedString` | 0x0052DEBC | Dispatche l'ASCII : condition `(c & 0xFF) − 0x20 < 0x5F` et `+0x1214 != 0`. **Étendre** : tout code latin (ASCII + `0xC380–0xC5BF` + `«»’…`) → `FUN_0052DA8C`. Sans cela, `é` tombe dans `FUN_0052DC54` et affiche `？`. |
| `FUN_0052CEA4` | 0x0052CEA4 | **Mesure** (largeur/hauteur/nb de glyphes). Contient une *copie indépendante* de la logique d'avance et de retour à la ligne. **Doit être modifiée en parallèle** de `0052DEBC`, sinon la boîte calculée ≠ le texte dessiné. Chemin ASCII à `+0x1214` déjà présent (binary_search inline sur `DAT_0052D330`). |
| `FUN_0052C690` | 0x0052C690 | Prétraitement : `else if (c != 0xD) { … cVar3++ … }` — il **compte les caractères** pour la machine à écrire (`param_4` = nb max). C'est un 1 glyphe = 1 compte. OK pour le latin, mais attention aux séquences 2 octets (un seul code → un seul compte, correct). |
| `UTF8_iter` | 0x0052D79C | Ne gère pas les séquences 4 octets (renvoie 1 octet). Suffisant pour le français. À corriger seulement si vous voulez des emojis. |
| `FUN_0052D988` | 0x0052D988 | Encodeur du code packé → octets. OK pour 2 octets. |
| `FUN_0052CE10` | 0x0052CE10 | Taille en octets d'un code (utilisé par l'expansion de tags, voir §3.4). OK. |

**Atlas / textures [À vérifier]** : l'ensemble de textures est créé par `FUN_001115EC` → `load_entry(0,0,&taille,1)` → `FUN_00112FDC` et rangé dans `police+0x11E0` (`param_1[0x478]`). L'atlas ASCII est la **texture d'indice 3** (`uStack_48 = 3` dans `FUN_0052DA8C`). Il faut identifier la ressource correspondante dans le romfs/archive (format de texture 3DS, tuilage) pour y ajouter les glyphes accentués. Deux stratégies :
- **Statique** : modifier l'atlas dans le romfs (ajouter des cellules, agrandir si besoin) + fournir des tables étendues par override. C'est la voie la plus simple et la plus fiable.
- **Dynamique** : générer un atlas additionnel en mémoire au démarrage (après `FUN_001115EC`) et l'ajouter comme texture d'indice supplémentaire (l'indice de texture est le champ `[6]` de la structure de quad ; la table de textures est `*(police+0x11E0)+0xC`).

Les trois grandes polices ont de la place libre (voir §2.2), ce qui permet aussi d'**ajouter les glyphes latins dans les atlas 16/14/12 px**. C'est moins utile car ces atlas sont à cellules carrées (chasse fixe).

#### A3. Avance, espacement et crénage
- `FUN_0052DC54` retourne `charW + 0x1228` ; `FUN_0052DA8C` retourne l'avance proportionnelle **sans** espacement. Décider d'une règle unique (recommandé : `avance = largeur_glyphe_scalée + espacement`).
- Le fixe `charW/2` pour l'espace (`0x20`) apparaît à **4 endroits** : `0052DEBC` (chemin principal, ruby, et deux boucles de ruby), `0052CEA4`. À centraliser dans une fonction `GlyphAdvance(code, charW)`.

#### A4. Polices secondaires (ruby 8 px et petites tailles)
`FUN_0052DC54` utilise les descripteurs 0x61BFD4/0x61BFEC pour `charW < 9`. Le français n'utilise pas de ruby ; vous pouvez le laisser tel quel. Si des étiquettes 8 px contiennent du texte latin, il faut aussi étendre ces deux tables.

---

### 3.2 Objectif B — Retour à la ligne adapté au français

**Constat [Confirmé]** : l'algorithme actuel coupe à *n'importe quel caractère* quand `largeur > wrap`, sauf avant une liste de signes de ponctuation (`' , . ? ! \n`, espace, et la liste JP de kinsoku `」` etc. via les constantes `DAT_0052D334/0052D338/0052D33C`). Il est écrit **deux fois** :
- mesure : `FUN_0052CEA4`, bloc `LAB_0052D248`…`0052D2F8`
- rendu : `KTGL_Font_DrawFormattedString`, bloc `LAB_0052E8B0`…`0052E9F4`

Le test est « conservateur » : il anticipe `cur + 2×avance + espacement > wrap` en supposant que le caractère suivant a la même largeur. Avec une police proportionnelle, c'est faux.

**Plan recommandé** (le plus robuste) : *ne plus coder le retour à la ligne dans ces deux boucles* ; le faire **une seule fois, dans le prétraitement** :

| Cible | Modification |
|---|---|
| **`FUN_0052C690`** (0x0052C690) | Après la construction du tampon interne, passer une fonction `WrapFrench(buffer, wrap, charW, spacing)` qui insère des `\n` aux espaces (jamais avant `: ; ? ! » %` ni après `«`, espaces insécables à gérer) en utilisant `GlyphAdvance`. Les deux consommateurs (`0052CEA4` avec `param_5 != 0` et `0052D340`) appellent déjà `FUN_0052C690`, donc mesure et rendu restent cohérents. |
| `KTGL_Font_DrawFormattedString` bloc `LAB_0052E8B0…E9F4` | Désactiver le retour à la ligne automatique (ne plus jamais déclencher). Le bloc ruby (`LAB_0052E524`) doit rester. |
| `FUN_0052CEA4` bloc `LAB_0052D248…D2F8` | Idem. |

Alternative moins invasive : conserver la coupure par caractère mais ajouter un test « mot en cours » (recule jusqu'au dernier espace). Moins propre car cela doit être fait dans les deux boucles.

Effet de bord à valider : le **nombre de lignes** retourné par `FUN_0052CE38` (CountLines, appelée par 8 mises en page) change, ce qui est voulu (§3.3).

`FUN_0052CAF8` (0x0052CAF8, `GetLine(n)`) extrait la n-ième ligne d'un texte avec `\n` explicites uniquement (utilisée par 6 écrans : `FUN_002B8C30`, `FUN_002BC0A0`, `FUN_0035E758`, `FUN_0035FB50`, `FUN_005412E0`, `FUN_00556AD4`) → ces écrans fonctionnent *ligne par ligne* et **ne bénéficient pas** de l'insertion automatique : il faut soit appeler `WrapFrench` avant, soit les traiter au cas par cas.

---

### 3.3 Objectif C — Redimensionner et repositionner les bulles / fenêtres de message

Les fenêtres de message sont des objets UI avec un jeu de champs commun (ce que lit le rendu générique `FUN_005412E0`) [Confirmé] :

| Champ widget | Rôle |
|---|---|
| +0x24 / +0x28 / +0x2C / +0x30 | x, y, largeur, hauteur de la boîte (écran haut 400×240, bas 320×240) |
| +0x254 / +0x258 | x, y du texte dans la boîte |
| +0x260 / +0x264 | largeur/hauteur de caractère (16×16 partout ici) |
| +0x268 | interligne (float) |
| +0x26C / +0x270 | largeur/hauteur mesurées du texte |
| +0x274 | alignement ; +0x27C compteur de caractères affichés ; +0x280/+0x288 minuteur/intervalle machine à écrire |

#### C1. Les 8 fonctions de mise en page de fenêtres de message
Toutes suivent le patron : fixer la taille de caractère → fixer `police+0x1238 = 0x12D` → `Measure` + `CountLines` → **choisir (y, hauteur, y_texte) par `if (lignes == 1) … else if (== 2) … else (n−k)×interligne`** → centrer horizontalement avec `0xA0 − largeur/2`.

| Fonction | Adresse | Particularité |
|---|---|---|
| `FUN_00533D70` | 0x00533D70 | Fenêtre principale ; 1/2/3/4/n lignes → hauteur 0x60/0x74/0x80/0x8C… |
| `FUN_005586CC` | 0x005586CC | Variante (y de départ différents) |
| `FUN_0055833C` | 0x0055833C | Variante bas d'écran (y=0xAB, hauteur 0x46) |
| `FUN_00265900` | 0x00265900 | Hauteur fixe 0x80 |
| `FUN_00272E60` | 0x00272E60 | 3 niveaux |
| `FUN_002C7F7C` | 0x002C7F7C | Boîte à position fixe (x=9, y=0x6A, h=0x7C) |
| `FUN_00353308` | 0x00353308 | Selon un type (`+0x2A4`) : 0, 6/8, autre ; largeurs 0x11C/0x134/400 |
| `FUN_0054179C` | 0x0054179C | Boîte de dialogue à **largeur calculée** (`mesure + 0x60`, min 320), hauteur `mesure + 0x13` (min 0x80). C'est le meilleur modèle à généraliser. |

**À faire** :
1. Remplacer le **301 px codé en dur** (`0x12D`) par une valeur dérivée de la largeur utile de la boîte (c'est aussi ce qui limite la largeur du texte français).
2. Remplacer les cascades `if (lignes == k)` par une formule générale : `hauteur = marge_haut + n × (charH + interligne) + marge_bas` ; `y = centre_vertical − hauteur/2` (ou bord ancré), plafonnée à la hauteur de l'écran (240). La version « n lignes » de ces fonctions le fait déjà (`(n−4) × (charH+interligne) + base`), il suffit de **l'étendre au-delà de 4 lignes et de supprimer les cas fixes**.
3. Introduire un hook commun : `ComputeMessageBox(widgetPtr, texte, &x,&y,&w,&h,&textX,&textY)` appelé par ces 8 fonctions (via `RECOMP_OVERRIDE` sur chacune ou un wrapper qui appelle l'original puis ajuste les champs +0x24…+0x258).
4. **Taille de caractère** : toutes ces fonctions fixent 16×16. Pour du français, vous aurez sans doute besoin de 14 ou 12 px (voir polices disponibles §2.2 : l'ASCII proportionnel s'adapte à n'importe quelle `charW`).

#### C2. Machine à écrire / pagination
| Fonction | Adresse | Rôle |
|---|---|---|
| `FUN_00541710` | 0x00541710 | Mise à jour : `+0x27C += floor(temps/intervalle)` (nombre de caractères révélés) |
| `FUN_005412E0` | 0x005412E0 | **Rendu générique du widget texte** (vtable slot, utilisé par ~16 classes). Appelle `FUN_0052D340(..., nbCharMax=+0x27C, texte=+0x54, ...)`. Quand le tampon retourne « tout affiché », il marque la page comme terminée. **Point d'entrée idéal pour recalculer** boîte + texte à chaque changement de page. |
| `FUN_0021B87C` | 0x0021B87C | Ajoute une **page** de message : max **10 pages**, chaque page ≤ **0x1FF octets** (`strlen < 0x200`). |
| `FUN_001EB7FC` | 0x001EB7FC | Expansion des tags/variables (`DAT_001EB9E8`) vers un tampon de **0x200 octets**, avec troncature **silencieuse**. |
| `FUN_0017F3A8` | 0x0017F3A8 | `strncpy` borné à 0x200, utilisé par plusieurs écrans. |

→ Le français est en général plus court en *octets* que le japonais UTF-8 (3 o/char), mais les textes longs avec beaucoup d'accents (2 o) et de balises peuvent dépasser. Surveiller ces limites 0x200 ; prévoir le découpage automatique en pages si nécessaire.

#### C3. Bulles de dialogue (avatars, tutoriels, quêtes)
| Fonction | Adresse | Rôle | À modifier |
|---|---|---|---|
| `FUN_00236170` | 0x00236170 | Affiche une bulle (2 variantes selon `*(short*)(…+0x83E2)`), mesure avec `Measure` et plafonne w ≥ 0x1C, h ≥ 0x0E/0x23 | Retirer les minima, utiliser la largeur mesurée |
| `FUN_00237858` | 0x00237858 | Idem, bulle simple | idem |
| `FUN_002372A4` | 0x002372A4 | **Placement** de la bulle à partir d'une table (`DAT_002373C4`, pas 0x10) | positions codées en dur par index |
| `FUN_002373E0` | 0x002373E0 | **Positionnement/clamp à l'écran** (très long, flottants, comparaison avec `DAT_00237810/818`…) | adapter les marges et l'ancrage si la bulle grandit |
| `FUN_00237C28`, `FUN_00237D90` | 0x00237C28 / 0x00237D90 | appelées par `FUN_002373E0` pour obtenir les ancres haut/bas **[Déduit, non lu en détail]** | à examiner |
| `FUN_002DE710` | 0x002DE710 | **Marges (+0x254/+0x258) par style de bulle (0–7)**, dépend de `Measure` (2 lignes ?) | tables de marges à recalculer |
| `FUN_002DFA54` | 0x002DFA54 | Initialisation d'un widget bulle (taille par défaut 0x140×0x10, char 14×14) | taille initiale |
| `FUN_002DFAD8` | 0x002DFAD8 | Définit le texte de la bulle (expansion tags ×2, `Measure`, choix de style 7/0x11 si largeur > `charW×18`) | seuil `×0x12` à revoir |
| `FUN_002DE6BC` | 0x002DE6BC | Appelle `Measure` et renvoie le drapeau « ruby présent » (3ᵉ sortie) | – |
| `FUN_00542430` | 0x00542430 | **Setter de rectangle** de widget (x,y,w,h = +0x24…+0x30) | **meilleur hook générique** : intercepter ici pour appliquer l'auto-dimensionnement |
| `FUN_005429B8` | 0x005429B8 | Démarre l'animation d'ouverture | – |

#### C4. Fonctions de rendu des autres boîtes
Les écrans qui dessinent directement avec `DrawText` à des coordonnées fixes (130 fonctions, voir CSV) doivent être revus au cas par cas : menus, noms d'objets, fiche de personnage, combats. Pour la plupart, la bonne stratégie est :
1. Garder l'appel `DrawText`.
2. Laisser `FUN_0052D44C` (`FitWidth`) réduire la taille de caractère quand le texte dépasse la largeur disponible (déjà utilisé par 15 écrans : `FUN_001AF2DC`, `FUN_001FF1AC`, `FUN_00228EB8`, `FUN_00242704`, `FUN_0025D6E0`, `FUN_0025DB48`, `FUN_00280CE0`, `FUN_002873D0`, `FUN_002B842C`, `FUN_002BC998`, `FUN_002E633C`, `FUN_00321DD8`, `FUN_00346AC0`, `FUN_0036B36C`, `FUN_00544294`). Cette fonction est **la bonne approche pour étiquettes courtes** une fois la mesure proportionnelle en place — **elle fonctionne via `FUN_0052CEA4`, donc elle bénéficie automatiquement de la police proportionnelle**.
3. Pour les autres écrans à largeur fixe, ajouter un appel `FitWidth` dans l'override de l'écran.

Détail de `FUN_0052D44C` : réduit `charW` tant que `largeur > max`, puis recalcule l'espacement `+0x1228 = spacing × oldW / newW`. Utile pour les noms de Yo-kai/compétences/objets français plus longs.

---

### 3.4 Objectif D — Adaptations annexes nécessaires

| Sujet | Fonctions / zones | Détail |
|---|---|---|
| **Compteur de quads (limite 756)** | `FUN_0052D848` (`0x2F3 < +0xBD4`), `FUN_0052CBC0`, `FUN_0052CCDC` | Un glyphe = 1 quad (+1 pour l'ombre). Les gros textes français peuvent saturer. Le rendu s'arrête (retour 0). Augmenter la capacité = agrandir le tableau (`+0x0004…`), donc l'objet. |
| **Pile d'appels (128)** | `FUN_0052D340` (`*(+0x11DC) < 0x80`) | 128 `DrawText` par image au plus ; sinon le texte n'est pas dessiné. |
| **Tampon de prétraitement** | `FUN_0052CEA4` (`abStack_460[1024]`), `FUN_0052D340` (`auStack_448[1024]`), `FUN_005412E0` (`auStack_420[1024]`) | OK pour <1 KiB. L'insertion de `\n` par `WrapFrench` ajoute des octets : garantir la taille. |
| **Tampons 512 octets** | `FUN_002BC0A0` (3×512), `FUN_0035E758` (3×512) | `GetLine` écrit sans limite explicite : vérifier avec du texte long. |
| **Couleur / ombre** | `FUN_0052DBF4`, `FUN_0052CA74`, `FUN_0052CAA4`, `FUN_0052DA38` | Aucune modification, mais leur appel précède toujours `DrawText`. |
| **Reset d'état** | `FUN_00120E0C` (0x00120E0C) | Réinitialise `charW/H=16`, `espacement=−1`, `interligne=2`, `wrap=∞`, alignement 0. **Ne touche pas `+0x1214`** : bon endroit pour le garder à 1. |
| **Ruby (furigana)** | `FUN_0052C690`, `FUN_0052D4F0`, branches `case 0x11` | Inutile en français, mais ne doit pas s'activer à tort : surveiller que `【` (0xE38090) n'apparaisse pas dans vos chaînes. |
| **Majuscules/minuscules** | – | Aucune conversion de casse dans le moteur ; aucun problème. |
| **Tri des codes** | tables | `binary_search` suppose une table **triée par entier packé** (ordre numérique des octets UTF-8). Dans l'atlas ASCII, tout code ≥ 0xC2AB dépasse le dernier code actuel (0xD2) : on ajoute en fin de table, dans l'ordre croissant (`«`=0xC2AB, `»`=0xC2BB, `À…ÿ`=0xC380–0xC3BF, `Œ œ`=0xC592/0xC593, `’`=0xE28099…). |

---

## 4. Stratégie de hook recommandée

Vu le mécanisme `RECOMP_OVERRIDE(addr)` de `3dsrecomp` (`docs/overrides.md`), qui remplace une fonction entière par du C hôte (accès `ctx->r[]`, `mem_read*/mem_write*`, appel de l'original via `RECOMP_ORIGINAL`), l'ordre de travail le plus sûr :

| Étape | Override / hook | But | Risque |
|---|---|---|---|
| 1 | `RECOMP_OVERRIDE(0x001115EC)` → `CALL(ORIGINAL)`, puis `mem_write32(0x007DBC3C, 1)` | Activer l'ASCII proportionnel | faible |
| 2 | Patch des données `.data 0x0067D3F2` (largeurs) + atlas | Ajuster les métriques | faible |
| 3 | `RECOMP_OVERRIDE(0x0052DA8C)` | Glyphe latin étendu + tables en RAM | moyen |
| 4 | `RECOMP_OVERRIDE(0x0052DEBC)` branche ASCII (ou wrapper) | Router le latin accentué vers (3) | moyen |
| 5 | `RECOMP_OVERRIDE(0x0052CEA4)` | Même avance/mesure que (3)(4) | moyen |
| 6 | `RECOMP_OVERRIDE(0x0052C690)` (+ `WrapFrench`) | Retour à la ligne français unique | moyen |
| 7 | Désactiver la coupe auto dans (4) et (5) | Pas de double coupe | moyen |
| 8 | Hooks sur `FUN_00542430`, les 8 mises en page (§3.3 C1) et `FUN_002373E0`/`002DE710` | Boîtes auto-dimensionnées | élevé (beaucoup de cas) |
| 9 | `FitWidth` dans les écrans restants (CSV) | Éviter les débordements | variable |

Les étapes 3–5 forment un ensemble cohérent : **implémentez d'abord une fonction hôte unique `GlyphAdvance(code, charW)` et `LookupGlyph(code)`, puis faites-la utiliser par les trois fonctions**. C'est la clé pour que mesure, rendu et boîte ne divergent jamais.

---

## 5. Points à vérifier avec l'émulateur / le romfs (non déterminables ici)

1. **Format et emplacement exact de l'atlas ASCII** (texture d'indice 3 de la ressource chargée par `FUN_001115EC`). Géométrie réelle : les champs (cellule 14×28, 16 colonnes, 9 lignes, capacité 162) ne se recoupent pas exactement avec 146 glyphes sur 256×256 ; confirmer sur la texture avant d'écrire les UV.
2. **Écriture de `+0x1214`** : aucune écriture n'apparaît dans le C ni dans l'init (`param_1[0x485] = 0`). Un watchpoint sur `0x007DBC3C` confirmerait qu'aucun chemin ARM ne le met à 1.
3. **Largeur de référence de la fonction de division `FUN_002FEDD8`** (utilisée pour l'avance proportionnelle) : confirmer s'il s'agit d'une division par arrondi ou à virgule fixe (`FUN_001644D0` est `__aeabi_uidivmod`).
4. **Comportement exact de l'anticipation de retour à la ligne** (`wrap < cur + 2×avance + espacement`) sur quelques chaînes réelles, pour valider qu'il n'y a pas d'autre appel qui force des `\n`.
5. **Source des chaînes** : ce rapport ne couvre pas le chargement des tables de messages (romfs) ; leur encodage (UTF-8) a été déduit du code de rendu uniquement.

---

## 6. Récapitulatif des fonctions (liste de travail)

**Noyau (obligatoire)**
`0x0052DEBC` KTGL_Font_DrawFormattedString · `0x0052CEA4` Measure · `0x0052C690` Prétraitement · `0x0052DC54` Glyphe normal · `0x0052DA8C` Glyphe ASCII · `0x0052C9F4` binary_search · `0x001115EC` Init police · `0x00120E0C` Reset

**Utilitaires à connaître (probablement intactes)**
`0x0052D340` DrawTextRaw · `0x0052DC28` DrawText · `0x0052C678` DrawText (variante z) · `0x0052CE38` CountLines · `0x0052D44C` FitWidth · `0x0052CAF8` GetLine · `0x0052D79C` UTF8_iter · `0x0052D988` encodeur · `0x0052CE10` taille en octets · `0x0052D4F0` tags · `0x0052D848/0052CBC0/0052CCDC` création de quads · `0x0052DBF4/0052CA74/0052CAA4/0052DA38` couleur/ombre/alpha

**Fenêtres de message**
`0x00533D70` · `0x005586CC` · `0x0055833C` · `0x00265900` · `0x00272E60` · `0x002C7F7C` · `0x00353308` · `0x0054179C` · `0x005412E0` (rendu) · `0x00541710` (machine à écrire) · `0x00542430` (setter de rectangle) · `0x0021B87C` · `0x001EB7FC` · `0x0017F3A8`

**Bulles**
`0x00236170` · `0x00237858` · `0x002372A4` · `0x002373E0` · `0x00237C28` · `0x00237D90` · `0x002DE710` · `0x002DFA54` · `0x002DFAD8` · `0x002DE6BC` · `0x005429B8`

**Appelants (130, voir CSV)**
Dont 15 utilisent `FitWidth`, 6 utilisent `GetLine`, 8 utilisent `Measure` pour dimensionner.
