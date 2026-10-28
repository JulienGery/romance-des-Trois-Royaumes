# Textures (images avec texte dessiné)

Tout est dans `LINKDATA_A.BIN` (13 128 entrées G1T, 15 361 textures, ~4 070 uniques). Formats rencontrés : ETC1A4 (0x48), RGBA4444 (0x3D),
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
