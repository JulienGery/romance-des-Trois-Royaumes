> **STATUT 2026-10-26** : B (reflow + équilibrage) et A (text fit, §A.0) sont implémentés ; B validé hors jeu sur le corpus, A et B à valider en jeu par l'utilisateur. Voir HANDOVER §1.

# Plan — deux défauts observés en jeu (captures de l'utilisateur, 2026-10-26)

Résumé : (A) dans une fenêtre de dialogue du bas de l'écran haut, la 3ᵉ ligne **sort de l'écran** ; (B) dans une bulle, le retour à la ligne est **déséquilibré** (« intuition » seul sur une ligne). Contexte complet : `HANDOVER.md`.

---

## A. Le texte sort de la fenêtre (capture 1)

### A.0 RÉSULTAT DU JOURNAL (`/tmp/fr.log` envoyé par l'utilisateur) — **cause trouvée : H3 confirmée**
Pour la scène de la capture, le journal ne contient **aucune ligne `LAYOUT`** (aucune des 7 mises en page n'est appelée) mais :
```
WIDGETDRAW wd=0878E5F4 box=(2,166,396,72) text@(38,16) meas=(320,16) cw=16 ch=16 lsp=10.0 align=0 multi=0 chars=… 'Tout est fin prêt !|En route pour l'École élémentaire de Gr…'
DRAWFMT align=0 wrap=320 sw=1 prewrapped=1 cw=16 lsp=10 'Tout est fin prêt !|En route pour l'École élémentaire de|Gr…'
```
- C'est une **fenêtre de dialogue à boîte FIXE** (classe de widget différente des 7 mises en page) : boîte `(2,166,396,72)`, texte en `(38,16)` aligné à gauche, zone de texte `meas=(320,16)` = valeurs par défaut (320×16) → **largeur de coupe 320, hauteur 72 px = 2 lignes** (16 + interligne 10 + 16 = 42 ; 16 + 42 = 58 ≤ 72).
- Le texte coupé à 320 fait **3 lignes** (ligne 2 = 323 px > 320 : dépasse de 3 px) → la 3ᵉ ligne tombe sous l'écran. Le jeu japonais d'origine tenait en 2 lignes de ≤ 20 caractères (≤ 320 px).
- Pas de désaccord mesure/dessin : **personne ne dimensionne cette boîte**, elle ne s'adapte pas. (Les hypothèses H1, H2, H4, H5 sont écartées pour cette scène.)
- La bannière du bas (`'En route pour l'école primaire de Granval !'`, align 2, 14 px, 267 px) est correcte.

**Conséquence sur la solution** : il faut **adapter le texte à la boîte**, pas la boîte au texte. C'est le « filet de sécurité » A-2, promu **correctif principal** : un *ajustement au dessin* (« text fit ») piloté par la capacité de la boîte du widget.

#### Conception « text fit » (à implémenter)
1. **Capacité** : dans l'override réservé `0x005412E0` (dessin du widget de texte, chaque image), avant d'appeler l'original, calculer `inner_h = box.h − ty − 8` (ici 72 − 16 − 8 = **48 px**) et la largeur de coupe courante (`+0x26C`, ici 320), les poser dans un état global `fr_fit {actif, inner_h}` ; l'effacer après le dessin. Ne rien faire si le widget a été mis en page par l'une des 7 fonctions (leur boîte grandit déjà avec le texte : le texte tient toujours → no-op).
2. **Décision dans le préprocess** (`0x0052C690`, qui connaît le texte, la largeur de coupe et la police) : calculer `hauteur(n lignes) = n×charH + (n−1)×interligne` ; si `> inner_h`, essayer dans cet ordre (le premier qui tient) :
   1. coupe normale (sauts durs conservés, équilibrée) ;
   2. **reflow total** : tous les `\n` explicites deviennent espaces, puis coupe équilibrée (ici : « Tout est fin prêt ! En route pour / l'École élémentaire de Granval ! » = **2 lignes à 16 px**, interligne 10 d'origine inchangée) ;
   3. interligne réduit à 2 (16 px × 3 lignes = 52 > 48 ✗ ; 14 px × 3 + 2×2 = 46 ✓) ;
   4. taille 14 puis 12 px (avec interligne réduit), sauts durs conservés puis reflow total.
   Les changements de taille/interligne sont écrits dans l'objet police (`+0x1220/+0x1224/+0x122C`) : le rendu et l'alignement les lisent après le préprocess, et le widget réinitialise la police (`FUN_00120E0C`) à chaque dessin, donc rien ne fuit.
3. **Déterminisme** : mêmes entrées → même sortie à chaque image, donc pas de scintillement ; la machine à écrire tronque après la coupe (déjà le cas).
4. **Tests** : propriété sur tout le corpus (texte, largeur 320, hauteur 48) → `n×pitch ≤ 48` toujours atteint (sinon la liste des textes impossibles) ; compter combien de textes déclenchent chaque étape (1…4) pour juger du coût visuel ; cas de la capture → 2 lignes à 16 px.
5. **Autres boîtes fixes** : le journal ne montre que ce widget ; généraliser en loggant `WIDGETDRAW` pour les autres écrans (l'utilisateur rejoue menus/combats) et vérifier que `box.h − ty − 8` est une bonne capacité pour chaque classe.

### A.1 Ce que montre la capture (chiffres mesurés)
Scène : Whisper, texte « Tout est fin prêt !\nEn route pour l'École élémentaire de Granval ! » (TSV Type 2, fichier 56, ligne 382). Échelle de la capture : 2,6125 px par pixel 3DS.

- Boîte (bulle bleue pleine largeur 400 px) dont le bord haut est à **y ≈ 168-171** ; deux lignes visibles à y ≈ 192 et 217 (pas de **25-26 px = 16 + interligne 10**) ; la 3ᵉ ligne (« Granval ! ») tombe à y ≈ 243 → **hors de l'écran (240)**.
- Largeur de la ligne 2 complète = **323 px** (calcul avec les avances de la police) > 301 → le texte fait bien **3 lignes** à 301 px.
- Interligne 10 et largeur 400 = **fenêtre `0x0055833C`** (bas d'écran, ancrée en bas). Pour 1-2 lignes elle donne `y=171, h=70` (bas à 241) ; pour 3 lignes `y=145, h=96` (la boîte **grandit vers le haut**).
- **Test hors jeu** (harnais `FR_BOXFILE`, vrai code de `0x0055833C`, même texte) : `y=145, h=96, mesure=(256,68)` = **3 lignes, correct**. En jeu la boîte est celle de **2 lignes** (`y=171, h=70`) et le bloc de texte est centré comme un bloc de 2 lignes (haut du texte ≈ 183 = 203 − 21) alors que le dessin fait 3 lignes.

**Conclusion** : en jeu, la mise en page (et la mesure de centrage) « voit » 2 lignes, le dessin en produit 3. Il y a un **désaccord entre mesure et dessin dans les conditions réelles** que le harnais ne reproduit pas.

### A.2 Hypothèses (historique — H3 confirmée, voir A.0)
| # | Hypothèse | Ce qu'on verrait dans le journal |
|---|---|---|
| H1 | La mise en page mesure avec un état de police différent (largeur de coupe `+0x1238` ≠ 301, ou taille ≠ 16) → 2 lignes | `LAYOUT … meas=(w,h)` avec h = 2 lignes ; `COUNTLINES n=2 wrap=…` |
| H2 | La mise en page est calculée sur un **autre texte** (page précédente / texte non résolu / tronqué) puis le texte change sans nouvelle mise en page (file de pages `FUN_0021B87C`, compteur `+0x27C`) | `LAYOUT '…'` ≠ `WIDGETDRAW '…'` (texte différent) |
| H3 | La fenêtre n'est pas mise en page par l'une des 7 fonctions hookées (autre fonction/classe, ou l'entrée appelée contourne l'override) | `WIDGETDRAW` sans `LAYOUT` correspondant avant |
| H4 | La mise en page est correcte mais un code ultérieur (réinitialisation, `FUN_00542430` setter de rectangle, animation d'ouverture) remet `y/h` aux valeurs de 2 lignes | `LAYOUT … box=(0,145,400,96)` puis `WIDGETDRAW … box=(0,171,400,70)` |
| H5 | La mesure du **dessin** (alignement 2 : `FUN_0052CEA4` avec p5=0 sur le tampon déjà coupé) renvoie 2 lignes parce que le tampon n'est pas encore coupé au même endroit (largeur de coupe du dessin = `+0x26C` = 256/260 ≠ largeur de mesure) | `MEASURE(p5=0, inside draw) n=2` alors que `DRAWFMT prewrapped=1` et le rendu fait 3 lignes |

### A.3 Protocole de diagnostic (instrumentation déjà en place)
1. Faire lancer : `FR_TRACE_FILE=/tmp/fr.log zakuro work/rom/game_fr.cxi 2> /tmp/zakuro.log`, rejouer la scène (Whisper, « Tout est fin prêt ! »), quitter, envoyer `/tmp/fr.log`.
2. Lire dans l'ordre pour ce texte : `LAYOUT` (boîte + mesure vue par la mise en page) → `COUNTLINES` (n) → `WIDGETDRAW` (boîte et mesure au moment du dessin, `chars`, `align`) → `DRAWFMT` (wrap, prewrapped) → `MEASURE(p5=0…)` (n,w,h vus par le dessin).
3. Décision : table des hypothèses ci-dessus. Si le journal est vide pour cette scène → H3 (chercher quelle fonction met en page : `FR_TRACE_FILE` + log d'entrée dans `0x542430` et `0x5412E0`).

### A.4 Correctifs (dans cet ordre)
- **A-1 (cause racine)** selon l'hypothèse :
  - H1/H5 : unifier la largeur de coupe : la mesure de mise en page et le dessin doivent utiliser **la même valeur** (soit forcer `+0x26C = largeur de coupe de la mise en page` dans chaque wrapper de mise en page, soit faire dessiner avec la largeur de mesure). Test : propriété « coupe(texte, W) = coupe(texte, mw(W)) » sur tout le corpus (`wrap_test.c`) + le harnais.
  - H2 : dans le wrapper de mise en page **et** dans `0x005412E0`, détecter le changement de texte (hash comme dans le journal) et rappeler la mise en page (méthode virtuelle slot 7 du widget) quand la page change.
  - H3 : ajouter l'override de la vraie fonction (nouvelle adresse → un build complet, 2 min 30, puis `fast_build.sh`).
  - H4 : localiser l'écrivain de `+0x28/+0x30` (log dans `0x542430`) et le corriger après lui.
- **A-2 (filet de sécurité générique, recommandé de toute façon)** : dans l'override `0x005412E0` (déjà réservé, tourne chaque image), **avant** l'original : mesurer le bloc réellement dessiné (override de mesure avec la largeur de coupe du dessin), calculer la hauteur intérieure disponible `min(h − ty − 6, 240 − (y+ty))` et, si le bloc ne tient pas : (a) réduire l'interligne (10 → 2), (b) réduire la taille 16 → 14 → 12, (c) en dernier recours remonter `ty`. Idempotent (recalculé chaque image depuis le texte). Limite connue : le cadre bleu est dessiné par une autre méthode du widget ; si elle passe avant le texte, le cadre garde l'ancienne taille pendant une image → préférer corriger à la mise en page (A-1) et garder A-2 pour ne **jamais** sortir de l'écran. Pour 3 lignes dans la boîte de 70 px de cette capture, A-2 (a) suffit (3×16 + 2×2 = 52 ≤ 70 − 11 − 6 = 53).
- **A-3 (si H3 ou autres cas)** : version paramétrique unique `ComputeMessageBox(variante, n, mode)` remplaçant les 7 cascades `if (lignes == k)` (les 7 tables sont dans `JOURNAL_MODIFICATIONS.md` / `code.c`), pour que la géométrie ne dépende que du **vrai** nombre de lignes.

### A.5 Tests et critères
- Étendre `diag_font.c` : après chaque mise en page, simuler le dessin (mesure p5=0 avec la largeur de coupe du dessin) et vérifier `bas du texte ≤ bas de la boîte ≤ 240` pour le corpus de 108 chaînes **et** les deux chaînes des captures.
- Critère : **0 texte / 0 boîte hors écran** sur le corpus et sur la scène de la capture (vérifiée par l'utilisateur).

---

## B. Retour à la ligne déséquilibré (capture 2)

### B.1 Ce que montre la capture
Bulle (252 px) : « Que le meilleur gagne entre mon / **intuition** / de génie et vos élucubrations, / Jibanyan ! ». Source : `Que le meilleur gagne entre mon intuition\nde génie et vos élucubrations, Jibanyan !` — le traducteur a laissé un **saut de ligne explicite** copié de la mise en page japonaise. La ligne 1 fait 290 px > 252 → coupée avant « intuition » ; le `\n` explicite force ensuite la suite → ligne orpheline.

### B.2 Chiffres (corpus complet, 42 667 textes traduits)
- 9 025 textes (21 %) contiennent un `\n` explicite ; **4 864** ont un saut **au milieu d'une phrase** (caractère précédent ≠ `. ! ? … : ; » ) "`).
- Dans les contextes à coupe (fenêtres 301 px, bulles 252 px), sur 12 035 textes concernés :

| Méthode | lignes totales @252 | dernières lignes < 25 % de la largeur @252 | lignes @301 | orphelines @301 |
|---|---|---|---|---|
| actuelle (glouton + `\n` durs) | 38 119 | **2 231** | 32 336 | **2 339** |
| reflow (sauts mous = espaces) | 35 766 | 2 196 | 30 461 | 2 455 |
| **reflow + équilibrage** | 35 766 | **41** | 30 461 | **42** |

→ le reflow économise ~6 % de lignes (moins de boîtes hautes), l'équilibrage supprime ~98 % des lignes orphelines.

### B.3 Conception (dans `frwrap.h`, C pur, testé sur le corpus)
1. **Reflow** : un `\n` explicite est **dur** si le caractère précédent ∈ `. ! ? … : ; » ) " ”` ou si la ligne suivante commence par `-`, `—`, `«`, `•`, un chiffre suivi de `.`/`)` (listes/dialogue) ; sinon **mou** (traité comme une espace). Les `\n` consécutifs (`\n\n`) restent durs. S'applique seulement quand une largeur de coupe existe (fenêtres, bulles) — les libellés/menus (pas de coupe) ne changent pas.
2. **Équilibrage** : après le glouton à largeur `W` → `n` lignes, chercher par dichotomie la plus petite largeur `W'` ∈ [mot le plus long, `W`] qui donne encore `n` lignes, puis recouper à `W'`. Par paragraphe dur.
3. **Cohérence mesure/dessin** : le dessin coupe à `+0x26C` (= largeur mesurée `mw`) tandis que la mesure coupe à 301/252. Le résultat doit être **identique** : `coupe(texte, W) == coupe(texte, mw)`. Argument : `W'` minimal est indépendant de la limite initiale tant que `limite ≥ W'` et que le glouton fait `n` lignes ; à **tester par propriété** sur tout le corpus (à ajouter à `wrap_test.c`) avant de livrer.
4. Machine à écrire inchangée (on coupe le texte complet puis on tronque ; `\n`→espace garde le même compte de caractères).
5. Données : ajouter au lint un rapport « sauts mous » (4 864) ; option `reflow_translation.py --apply` si l'utilisateur préfère nettoyer le TSV (équivalent, sans logique à l'exécution, mais non adaptatif à la largeur de boîte).

### B.4 Étapes
1. `frwrap.h` : `frw_hard_break()` + reflow + `balanced` ; paramètres `reflow`, `balance` (activés par défaut quand `wrap < 0x7FFFFFFF`).
2. `wrap_test.c` : propriétés (contenu conservé, aucune ligne > W, pas de début de ligne interdit, **coupe(W) == coupe(mw)**, orphelines ≤ 0,5 %, `n` jamais supérieur au glouton).
3. `fast_build.sh`, auto-tests (`FR_SELFTEST=1` : 720 cas de mesure inchangés ; coupe), puis l'utilisateur relance les deux scènes.
4. Mettre à jour `JOURNAL_MODIFICATIONS.md` (O5 : reflow + équilibrage, avec le pseudo-code pour l'ARM).

### B.5 Critères d'acceptation
Capture 2 : « Que le meilleur gagne entre mon intuition / de génie et vos élucubrations, Jibanyan ! » → 2-3 lignes de longueurs voisines ; corpus : orphelines < 0,5 %, aucune régression des 720 cas de mesure, aucune ligne hors largeur.

---

## Ordre des travaux
1. B (déterministe, testable hors jeu, gain visible immédiat) — environ 1 séance.
2. A-2 (filet de sécurité) puis A.3 (journal de l'utilisateur) → A-1 selon l'hypothèse.
3. Mettre à jour `HANDOVER.md` §1/§5 et `JOURNAL_MODIFICATIONS.md`.
4. Reprendre ensuite la phase 6 (images, noms de fiches, ruby) puis le portage ARM.

## Informations à demander à l'utilisateur si nécessaire
- Le fichier `/tmp/fr.log` après avoir rejoué la scène du magasin (Whisper) et une scène avec bulle.
- S'il voit d'autres fenêtres qui débordent (menus, fiches, combats) : capture + `fr.log`.
