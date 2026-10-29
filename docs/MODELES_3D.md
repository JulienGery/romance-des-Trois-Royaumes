# Modèles 3D : format et amélioration de la qualité

Outils : `tools/models/` (`g1mg.py` lecteur/écrivain, `improve_models.py` traitements, `render_preview.py` aperçu avant/après). Python + numpy (`work/venv`).

## Ce que contient le jeu
- **1 510 modèles `_M1G`** (yo-kai, personnages, accessoires) dans les entrées `binary` 16000–18800 de `LINKDATA_A.BIN` : table `u32 n, n décalages` (alignés sur 16) puis fichiers `_M1G`, `GT1G`, animations…
  693 entrées contiennent de la géométrie. (Les 178 entrées de type « model », magie `ME1G`, sont d'un autre format, non traité.)
- `_M1G` = chunks `FM1G`, `SM1G` (squelette), `MM1G` (matériaux), **`GM1G`** (géométrie, plate-forme `3DS`, v44), `RTXE`.

## Géométrie `GM1G` (décodée et vérifiée sur les 1 510 modèles)
Après l'en-tête de 48 o : sections `{u32 type, u32 taille, u32 nombre}` + corps.
| Type | Contenu |
|---|---|
| 0x10004 | tampons de sommets : par tampon `{0, stride, nb, 0}` + `nb×stride` octets |
| 0x10005 | un jeu d'attributs par tampon : `{1, 0, n}` + `n×(flux, décalage, type, sémantique)` u16 |
| 0x10007 | tampons d'index : `{nb, 0x10 (u16), 0}` + indices — **bandes de triangles** (avec triangles dégénérés) |
| 0x10008 | sous-maillages, 56 o : mots `[7]` n° de tampon (sommets **et** index), `[10..13]` début sommets, nb sommets, début index, nb index (index **absolus** dans le tampon) |
| 0x10006 / 0x10009 | palettes d'os / maillages (LOD), non modifiés |

Sommet (stride 44 si skinné, 36 sinon) : position f32×3 · poids d'os u8×4 (0x0C) · indices d'os u8×4 (0x10) · normale f32×3 · couleur u8×4 · UV f32×2.

## Idées étudiées
| Idée | État |
|---|---|
| Textures des modèles en HD | déjà faite (pack HD, `docs/PACK_HD.md`) |
| **Lissage des normales** aux coutures d'UV (arêtes vives conservées) | **implémenté** (`--level 0` = uniquement ceci, taille inchangée) |
| **Subdivision courbe** (PN-triangles, 1 triangle → 4, ou 16) : silhouettes plus rondes, moins de facettes | **implémenté** |
| Réglages Azahar (résolution interne ×5 déjà utilisée) | rien à changer côté fichiers |
| Reconstruction des animations / os supplémentaires, remplacement par modèles du jeu 2 | non fait (hors de portée sans l'outillage de rig) |
| Modèles `ME1G` (178 entrées : décors, objets) | format non décodé |

### Détails de la subdivision
- **Netteté automatique** : une arête dont l'angle dièdre dépasse 40° (`--crease` ; un décagone = 36° est arrondi, un octogone = 45° reste net) reste droite, et ses sommets n'arrondissent pas leurs voisines → chapeau, pointes, rebords restent vifs ; dômes et ventres (petits angles) sont arrondis.
- Les sommets d'origine **ne bougent pas** ; les milieux d'arêtes sont posés sur l'arête cubique définie par les normales lissées (`m = (Pi+Pj)/2 + ((d·Nj)Nj − (d·Ni)Ni)/8`). Faces planes inchangées ; arêtes vives (normales écartées de > 45°) restent droites.
- La position du milieu dépend uniquement des sommets *soudés* (même position) → pas de fissure entre coutures d'UV ni entre sous-maillages.
- UV, normale, couleur interpolés ; poids d'os : fusion 50/50 des deux sommets, 4 meilleurs os, somme 255. Les palettes d'os ne changent pas (même sous-maillage).
- Garde-fous : aucun tampon > 65 535 sommets (sinon il reste intact) ; sommets/index réécrits de façon cohérente (début/nombre de chaque sous-maillage, tailles des chunks, table de décalages de l'entrée). Un modèle qui échoue est laissé tel quel.
- Coût : niveau 1 → ×4 triangles ; archive ≈ 482 → 672 Mo (niveau 1), 972 Mo avec `YOKAI_MODELS=3` (les anciens emplacements restent dans le fichier, `patch_many` ajoute à la fin).

## Utilisation
```bash
YOKAI_MODELS=3 tools/build_all.sh                       # build complet (N = niveaux max, avec budget de sommets ; 0 = normales seulement)
YOKAI_MODELS=1 YOKAI_MODELS_ENTRIES=16300 tools/build_all.sh   # essai sur une seule entrée
work/venv/bin/python tools/models/render_preview.py 16300 --out /tmp/p.png --crop=-40,0,40,80 --edges   # aperçu avant/après
work/venv/bin/python tools/models/improve_models.py --dst /tmp/LINKDATA_models.BIN                      # archive seule
```

## À valider en jeu (non testé)
Le décodage et la cohérence des fichiers sont vérifiés hors-jeu sur les 1 510 modèles (bornes, couverture des sommets/index, orientation des triangles, relecture après écriture), mais **rien n'a encore été lancé dans Azahar**.
Points à regarder : chargement (mémoire du jeu si une entrée grossit beaucoup), culling (sens des faces), déformation des os aux articulations, performances sur la Thor (les vertex shaders PICA sont émulés : ×4 sommets coûte).
Si un modèle pose problème : `YOKAI_MODELS_ENTRIES` pour isoler, ou `YOKAI_MODELS=0` (normales seulement).
