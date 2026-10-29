# Textures (images avec texte dessiné)

Tout est dans `LINKDATA_A.BIN` (13 128 entrées G1T, 15 361 textures, ~4 070 uniques — **plus** ~10 900 textures G1T embarquées dans des entrées `binary`, voir « Pack HD » plus bas). Formats rencontrés : ETC1A4 (0x48), RGBA4444 (0x3D),
RGB565 (0x3B), RGBA8 (0x09), A4 (0x44), ETC1 (0x47) — tous réencodés par `g1t_encode.py` (RGBA4444/565/8/A4 sans perte, ETC1 avec perte légère).

## Préparer (une fois)

```sh
python3 -m venv work/venv && work/venv/bin/pip install pillow numpy
work/venv/bin/python tools/assets/extract_textures.py      # ~10 s -> work/assets/png/<entrée>_<tex>.png + manifest.json
work/venv/bin/python tools/assets/make_gallery.py --no-sheets   # -> work/assets/index.html (galerie par famille)
```

Ouvrir `work/assets/index.html` : recherche par identifiant (`1234_0`), textures **uniques** seulement (les doublons exacts sont omis ;
un PNG retouché s'applique à l'identifiant donné — pour un doublon, voir `same_as` dans `manifest.json`).

## Familles à traduire (repérées sur les planches-contact)

| Famille (`--copy`) | Entrées | Taille | Contenu |
|---|---|---|---|
| `techniques` | 203–663 (+ quelques-unes en 16xxx/18xxx) | 256×64 | noms de techniques de Yo-kai (blanc, contour noir, fond violet, furigana) — **393** |
| `plaques` | 12205–12500, 16xxx, 18xxx | 128×32, 64×32 | plaques nom Yo-kai + officier (kanji + furigana) — **321** |
| `bannieres` | 2970–3044 | 512×128 | bannières de tutoriel / annonces — **75** |
| `effets` | 2688–2703 | 128×32 | « Subit moitié de dégâts ! », « 1 fois ! »… — **16** |
| `ui` | 1–76 | variable | atlas d'interface : titres, boutons, mentions légales (`30_0`), logos, panneaux — **44** (le texte est mélangé à des icônes : retoucher au cas par cas) |

Les autres textures (cartes 77–200, icônes 686–2600, portraits 2704–2890, illustrations 3086–3194, décors 17711+, sprites 128×128) n'ont pas de texte repéré
(planches parcourues par échantillonnage : **les entrées 205–660 ont été vues en partie seulement**, ouvrir la galerie pour confirmer).

## Génération automatique (FR) — état au 2026-10-28

| Famille | Script | Fait |
|---|---|---|
| techniques 256×64 | `gen_technique_banners.py --all --out translations/fr/textures` (nom officiel du glossaire `skills_fr.tsv`, sinon traduction du jeu ; entrée = 203 + ligne) | 383 |
| plaques 128×32 / 64×32 | `gen_name_plates.py --out translations/fr/textures` (entrée = 12205 + ligne du script 57/0) | 229 |
| effets 128×32 | `gen_effect_banners.py --out translations/fr/textures` (textes écrits à la main) | 15 |
| bannières 512×128, atlas `ui` | **non faits** : texte posé sur des illustrations / sprites, à repeindre à la main | 0 |

Les PNG générés sont dans `translations/fr/textures/` (pris par le build). Non vérifié en jeu : police différente de l'original, furigana supprimés, plaques 64 px très petites.

### Placement des plaques de noms (vérifié)
Le jeu aligne les plaques d'après un **tableau de données** de 16 octets par plaque (pointeur en `0x14BA48`, tableau en `0x628140`) : `+8` u16 = largeur de la pilule, `+10` u16 = hauteur
(identique à la largeur visible des 232 plaques japonaises). `patch_plate_table.py`, appelé par `tools/build_all.sh`, y écrit la largeur visible des PNG français,
donc les plaques restent alignées quelle que soit la longueur du nom. Le 4ᵉ champ du enregistrement est non décodé : ne pas changer la taille des textures (64/128 px).

### Libellés d'interface (atlas)
`translations/<langue>/ui_labels.json` + `gen_ui_labels.py` (repérage : `find_labels.py`) réécrivent les libellés dessinés dans les atlas `26_0` (écran titre), `21_0` (menu de combat), `8_3` (actions de la carte).
Styles : `title` (lavande, contour sombre net), `map` (blanc, contour noir, ombre, liseré blanc), sinon couleurs échantillonnées ; `size`/`thin` = taille et finesse imposées pour un groupe ; `align` ; `text_dx` = début du texte à droite d'une icône.
Leçons : les rectangles de sprites sont fixes (le texte reste dedans), le jeu agrandit les sprites (contours francs, pas de double anneau sur du petit texte), mêmes tailles de police pour un groupe de boutons.

## Retoucher

```sh
work/venv/bin/python tools/assets/make_gallery.py --copy techniques /chemin/edition   # copie une famille
```

Éditer les PNG **sans changer leurs dimensions** (le jeu référence des coordonnées dans les atlas ; garder le canal alpha), puis les placer dans
`translations/<langue>/textures/<entrée>_<tex>.png` (mêmes noms). Au prochain `tools/build.sh` / `tools/patch_rom.py`, `apply_translation.py` les
ré-encode dans le format d'origine (mipmaps régénérées) et les injecte dans `LINKDATA_A.BIN`.

Vérifier l'encodage seul : `work/venv/bin/python tools/assets/apply_textures.py DOSSIER_PNG --check` (écart décodé/PNG, sans écrire).
Injection manuelle : `apply_textures.py DOSSIER_PNG --dst sortie.BIN`.

## Limites connues
- L'entrée 0 (atlas de police) reste gérée par `make_entry0.py`.
- Le texte des noms est le même que dans les scripts : pour les plaques/techniques, le bon libellé FR se retrouve dans `translations/fr/*.tsv`
  (`tools/translation/search.py`). Le rendu doit rentrer dans 256×64 / 128×32 : prévoir des libellés courts ou un texte plus petit.
- Non testé en jeu (encodeur vérifié par aller-retour décodage ↔ encodage, injection vérifiée dans l'archive).

## Pack de textures haute résolution (Azahar)

Agrandit les textures **sans toucher à l'archive du jeu** (compatible console réelle) : Azahar remplace à l'affichage toute texture dont le hash correspond
à un PNG de `load/textures/<TitleID>/`. Il faut activer « Textures personnalisées » dans Azahar.

**En une commande** (pack prêt à publier, ex. GameBanana — rien n'est versionné, il se reconstruit depuis son propre dump ; à relancer quand les textures traduites changent) :

```sh
tools/assets/make_hires_pack.sh --langs fr            # -> work/hires_pack/YokaiWatchSangokushi-HD-Pack.zip (+ LISEZMOI.txt d'installation)
tools/assets/make_hires_pack.sh --langs fr,en --light  # variante allégée (AYN Thor) ; --font pour une police libre ; --dry-run pour compter sans lancer Upscayl
```

Par défaut le script est **incrémental** : une texture déjà agrandie (PNG de même hash) n'est pas refaite ; après une retraduction, seules les textures modifiées (nouveau hash) passent dans Upscayl. `--prune` supprime ensuite les PNG périmés (anciennes versions des textures retraduites ; ajouter `--from-dump <dump d'Azahar>` pour conserver les textures fabriquées à l'exécution), `--clean` repart de zéro.

Étapes détaillées (le script les enchaîne) :

```sh
work/venv/bin/python tools/assets/build_hires_pack.py                       # LINKDATA japonais -> work/hires_pack/000400000018B000/
work/venv/bin/python tools/assets/build_hires_pack.py --linkdata work/rom/romfs_dir_fr/Data/LINKDATA_A.BIN   # + textures traduites FR
work/venv/bin/python tools/assets/build_hires_font.py [--atlas data/atlas | --bake-lang en] [--font ...]   # polices redessinées (voir plus bas)
work/venv/bin/python tools/assets/build_hires_pack.py --from-dump <dossier dump d'Azahar>  # textures vraiment fabriquées à l'exécution
```

Le dossier produit se copie tel quel dans `load/textures/` d'Azahar (macOS : `~/Library/Application Support/Azahar/`; Android : le dossier d'Azahar). `hires_config.json` : modèle Upscayl
(`digital-art-4x`, binaire du .app), échelle par défaut (2) et règles par plage d'entrées (`17711-17900`) ou identifiant (`17779_0`) — dernier match gagnant, échelle 1 = ignorer ; `min_size` = plus petit côté traité.
Les agrandissements viennent d'Upscayl (GPU, ~100 textures/min) puis, si l'échelle < 4, d'une réduction `INTER_AREA`.

### Règles d'Azahar à respecter (toutes vérifiées sur des dumps)
- Nom : `tex1_<L>x<H>_<HASH16 MAJ>_<format PICA>.png`, L×H = taille **d'origine** de la texture GPU (le PNG peut être plus grand).
- `pack.json` obligatoire à la racine du dossier du jeu (`skip_mipmap`, `flip_png_files: true`, `use_new_hash: true`), sinon hash « ancien » (pixels décodés) et rien ne correspond. Piège : un dossier copié en double (`<TitleID>/<TitleID>/`).
- Nouveau hash = **CityHash64 des octets encodés du niveau 0** (`largeur × hauteur × octets/pixel`), python `cityhash`. Les PNG sont stockés **retournés verticalement** (`flip_png_files`), comme les dumps.
- Formats G1T → PICA : `0x09→0` RGBA8, `0x45→1` RGB8, `0x3C→2` RGB5A1, `0x3B→3` RGB565, `0x3D→4` RGBA4, `0x44→11` A4, `0x47→12` ETC1, `0x48→13` ETC1A4.

### Où sont les textures (à lire avant de dire « introuvable »)
Une texture dumpée absente du pack **n'est presque jamais** « fabriquée à l'exécution » : elle est dans `LINKDATA_A.BIN` mais pas dans une entrée de type `texture`. Trois endroits :
1. **Entrées `texture`** (13 128 G1T) : lecture directe (`G1tFile`).
2. **G1T embarqués dans des entrées `binary`** : ~1 000 entrées (16040–16269, 16394–16659, 18539–18736…) commencent par un compteur (u32) puis contiennent un ou plusieurs fichiers de magie `GT1G`
   — modèles et textures des yo-kai, atlas de décors de ville (ex. l'atlas 1024×1024 ETC1 de la ville, entrée 16164, herbe comprise). ~10 900 textures, 2 846 hash uniques.
   Le décalage de début n'est **pas** aligné sur 32 : un scan par fenêtres de 32 octets les rate. Méthode : chercher `GT1G`, lire la taille en `+8`, parser avec `G1tFile`.
3. **`.bflim` dans des archives SARC** (entrées `archive`/`binary` de magie `SARC`, ex. 17820–17928, 17901, 17986) : décors de la carte. Format CTR BFLIM : données d'abord, pied `FLIM` de 40 octets avec section `imag`
   (`u16 largeur, u16 hauteur, u16 alignement, u8 format, u8 flags`). Formats BFLIM → PICA : 5→3, 6→1, 7→2, 8→4, 9→0, 0xA→12, 0xB→13 (L8, LA4… non décodés). **Les dimensions GPU sont transposées** :
   `(pow2(hauteur), pow2(largeur))` (vérifié sur 132 hash).
Restent vraiment hors de portée : les textures fabriquées à l'exécution (par ex. **les images de la vidéo d'intro**), dont le hash dépend du contenu.

### Pièges rencontrés
- **Ne jamais mettre les images de vidéo dans le pack.** Les vidéos `.moflex` (OP, ED, LOGO — 22 433 images) sont décodées par le jeu et envoyées image par image dans une texture 512×256 RGBA8 :
  chaque image a son hash. Des images agrandies en 1024×512 (issues d'un dump) ont fait perdre le GPU à MoltenVK (`OUT_OF_DEVICE_MEMORY` → `DEVICE_LOST`) pendant l'intro sur Mac (M5) ; retirées, plus de souci.
  Agrandir les vidéos par un pack n'est pas faisable (hash non reproductible via ffmpeg : écart moyen 2,8/255 sur la meilleure image, ~20 Go de PNG) ; réencoder le `.moflex` n'a pas d'encodeur public.
- **`min_size`** : mettre 8 (et non 32) — 10 231 textures G1T font 16×16 (tuiles de terrain, herbe…).
- **Performances de la Thor (AYN)** : ~8 000 PNG, 1,8 Go. Des chutes de fps occasionnelles (âmes ultimes, certains combats) sont apparues avec les textures embarquées ; les grandes textures ETC1A4 (alpha, ≥ 256×256, 299 fichiers)
  agrandies en RGBA brut sont la piste (**non confirmée**) : les retirer du dossier de la console. Les atlas de ville agrandis (2048×2048) sont aussi lourds.
- Upscayl calcule sur le GPU (`-g -1` pour le CPU est 10 à 50 fois plus lent).

### Polices FR/EN en haute résolution (`build_hires_font.py`)
La police du jeu n'existe qu'en bitmap 18 px (`ft_nrm.xf`, `ft_sml.xf`) : un agrandissement par IA est flou. Le script **redessine** chaque glyphe à partir d'une police vectorielle (Helvetica du système par défaut ;
`--font` pour une police libre type Liberation Sans/Arimo avant diffusion) dans la boîte d'encre d'origine (`ox, oy, ink_w, ink_h` de `glyphs_<nom>.json`) : mêmes avances, même mise en page. Page de 256×256 A4 → 1024×1024 (échelle 4).
Nommage : hash CityHash64 de `a4_encode(page)` (vérifié : identique aux fichiers agrandis par Upscayl pour le FR). Échelle uniforme calée sur la hauteur de capitale du `H` d'origine, ligne de base et centre pris sur l'original ;
les descendantes (p, q, y, g, j) sont **compressées sous la ligne de base**, jamais décalées (sinon elles ne s'alignent plus). Glyphes absents de la police (♪ ★ ⑯…) : bitmap d'origine agrandi.
L'atlas anglais a un autre jeu de caractères, donc d'autres hash : `FR_LANG=en` + `charset_from_translations.py`, `dotnet … ft_*.xf --chars`, `bake_french_atlas.py`, puis `--atlas <dossier>` (hash EN non vérifiés sur une ROM anglaise).
