# Pack de textures haute résolution (Azahar) — guide d'utilisation

Ce guide explique comment **produire** et **installer** un pack de textures HD pour Yo-kai Watch Sangokushi sur l'émulateur [Azahar](https://azahar-emu.org/).
Le pack ne modifie jamais l'archive du jeu (il fonctionne donc avec la ROM japonaise ou avec le patch de traduction) : Azahar remplace chaque texture à l'affichage,
d'après son empreinte (hash). Ce dépôt ne contient **aucune texture du jeu** : le pack se génère depuis **votre propre dump**.

Détails techniques (format des noms, hash, où se trouvent les textures dans `LINKDATA_A.BIN`, pièges) : [`tools/assets/README.md`](../tools/assets/README.md), section « Pack HD ».

## 1. Ce qu'il faut

| Besoin | Pourquoi |
|---|---|
| Votre dump déchiffré de la ROM japonaise (`ORIGINAL.cci`) | source des textures |
| [Upscayl](https://upscayl.org/) installé (macOS : `/Applications/Upscayl.app`) | agrandissement par IA (modèle `digital-art-4x` fourni avec l'application) ; un GPU est nécessaire |
| Python 3 + environnement `work/venv` | `python3 -m venv work/venv && work/venv/bin/pip install pillow numpy opencv-python-headless cityhash` |
| `dotnet` (seulement pour une langue autre que le français) | régénère l'atlas de police de cette langue |
| ~2 Go d'espace disque | le pack complet fait ~1,8 Go |

Le script lit `work/rom/romfs_dir/` (ROM japonaise extraite) : `python3 tools/patch_rom.py ORIGINAL.cci FRANCAIS.cxi` le crée (étape d'extraction) ; voir le README principal et [`TECHNIQUE.md`](TECHNIQUE.md).
Le chemin d'Upscayl est la constante `UPSCAYL` en tête de `tools/assets/build_hires_pack.py` (à adapter hors macOS).

## 2. Produire le pack (une commande)

```sh
tools/assets/make_hires_pack.sh --langs fr
```

Résultat : `work/hires_pack/YokaiWatchSangokushi-HD-Pack.zip` (+ le dossier `work/hires_pack/000400000018B000/`). Compter environ une heure la première fois (Upscayl calcule environ 100 textures par minute) ;
les fois suivantes, seul ce qui a changé est refait.

Ce que fait le script, dans l'ordre :
1. textures du jeu japonais (textures simples, textures embarquées dans les entrées `binary`, textures `.bflim` des archives SARC) ;
2. textures traduites de chaque langue demandée (`work/rom/romfs_dir_<langue>/Data/LINKDATA_A.BIN`, produit par `tools/build_all.sh`) ;
3. polices FR/EN redessinées en vectoriel (1024×1024) ;
4. suppression optionnelle des fichiers périmés, puis archive `.zip` avec `LISEZMOI.txt`.

### Options

| Option | Effet |
|---|---|
| `--langs fr,en` | langues dont on ajoute les textures traduites et la police (défaut : `fr`). Pour l'anglais, construire la ROM avec `FR_LANG=en tools/build_all.sh` puis copier `work/rom/romfs_dir_fr` en `work/rom/romfs_dir_en` |
| `--light` | variante allégée (ignore les grandes textures à transparence) pour AYN Thor et consoles portables |
| `--font POLICE.ttc` | police vectorielle des glyphes (défaut : Helvetica du système). **Pour diffuser le pack, utilisez une police libre** (Liberation Sans, Arimo) |
| `--prune` | supprime du pack les PNG que le jeu et les traductions actuels n'utilisent plus |
| `--from-dump DOSSIER` | ajoute les textures fabriquées à l'exécution (voir § 4) |
| `--clean` | repart de zéro (par défaut le script est incrémental) |
| `--dry-run` | compte ce qui serait fait, sans lancer Upscayl ni créer l'archive |
| `--out DOSSIER` | dossier de sortie (défaut : `work/hires_pack`) |

Réglages d'agrandissement (modèle, échelle par défaut, exceptions par plage d'entrées ou par texture) : `tools/assets/hires_config.json`.
Exemple : `{"entries": ["2704-2890"], "scale": 4}` agrandit les portraits ×4 ; `"scale": 1` ignore une famille. Dernière règle correspondante gagnante.

## 3. Recettes

**Première génération (japonais + français)**
```sh
tools/build_all.sh                                   # produit work/rom/romfs_dir_fr (LINKDATA traduit)
tools/assets/make_hires_pack.sh --langs fr
```

**Après avoir retraduit des textures** (`translations/<langue>/textures/`) — seules les textures modifiées sont réagrandies
```sh
tools/build_all.sh                                   # reconstruit le LINKDATA avec les nouvelles textures
tools/assets/make_hires_pack.sh --langs fr --prune --from-dump "<dossier dump d'Azahar>"
```

**Pour une console portable** : ajouter `--light`. Si les images saccadent encore, mettre une échelle de 1 pour les familles concernées dans `hires_config.json`.

**Tester sans tout régénérer** : `tools/assets/make_hires_pack.sh --dry-run` ; ou ne traiter que quelques textures avec les outils unitaires :
```sh
work/venv/bin/python tools/assets/build_hires_pack.py --ids 17779_0,17780_0      # identifiants <entrée>_<texture>
work/venv/bin/python tools/assets/build_hires_pack.py --range 16040:16300        # plage d'entrées
```

## 4. Textures que le jeu fabrique à l'exécution

Quelques textures n'existent dans aucune archive (leur contenu est calculé pendant le jeu). Pour les couvrir : dans Azahar, activer **« Extraire les textures »** (`dump_textures`), jouer les zones concernées,
puis passer le dossier `dump/textures/000400000018B000` à `--from-dump`. Les images de la **vidéo d'intro** (512×256 RGBA8) sont automatiquement ignorées : les agrandir fait perdre le GPU de certains Mac.

**Une texture dumpée absente du pack ne signifie presque jamais qu'elle est introuvable** : vérifiez d'abord qu'elle n'est pas dans un G1T embarqué ou une archive SARC (voir `tools/assets/README.md`). Pour vérifier :
chercher son hash (le nom du fichier dumpé) parmi ceux calculés par `build_hires_pack.py`.

## 5. Installer le pack dans Azahar

1. Décompresser l'archive et copier le dossier **`000400000018B000`** dans le dossier `load/textures/` d'Azahar :
   macOS `~/Library/Application Support/Azahar/load/textures/`, Windows `%APPDATA%\Azahar\load\textures\`, Android : dossier Azahar (`/sdcard/Documents/` ici), sous-dossier `load/textures/`.
   Le fichier `pack.json` doit se trouver **directement** dans `000400000018B000/` (pas dans un dossier imbriqué).
2. Azahar › Configurer › Graphismes › Utilitaires : cocher **« Utiliser des textures personnalisées »** ; laisser le préchargement désactivé (le chargement asynchrone est conseillé).
3. Lancer le jeu. Le premier lancement peut bloquer plusieurs secondes le temps d'indexer le pack.

Sur Android depuis un Mac : `adb push 000400000018B000 /sdcard/Documents/load/textures/`.

## 6. Problèmes courants

| Symptôme | Cause probable |
|---|---|
| Aucune texture remplacée | « Textures personnalisées » désactivé ; `pack.json` absent ou mal placé ; dossier copié en double |
| Gel ou plantage GPU (`OUT_OF_DEVICE_MEMORY`, `DEVICE_LOST`) pendant l'intro sur Mac | images de la vidéo d'intro présentes dans le pack : régénérer avec la version actuelle du script |
| Fps qui chutent (âmes ultimes, combats chargés) sur console portable | essayer `--light`, ou réduire l'échelle de certaines familles |
| Un élément précis reste flou | relever le nom de fichier dans le dump d'Azahar ; vérifier s'il est dans le pack (nom = `tex1_<L>x<H>_<HASH>_<format>.png`) |
| Les vidéos (`.moflex`) ne sont pas agrandies | impossible par un pack de textures (une image = une texture au hash imprévisible) |

## 7. Les outils

| Fichier | Rôle |
|---|---|
| `tools/assets/make_hires_pack.sh` | pipeline complet (ci-dessus) |
| `tools/assets/build_hires_pack.py` | génère les agrandissements : textures du jeu, traduites ou dumpées (`--linkdata`, `--from-dump`, `--ids`, `--range`, `--light`, `--dry-run`) |
| `tools/assets/build_hires_font.py` | redessine les pages de police (`--font`, `--scale`, `--atlas`, `--bake-lang`) |
| `tools/assets/hires_config.json` | modèle, échelle, exceptions |
