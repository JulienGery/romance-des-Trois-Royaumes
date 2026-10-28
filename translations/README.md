# Traductions

Un dossier par langue : `fr/` (français, relu), `en/` (anglais, brouillon DeepL à relire). Chaque dossier contient quatre fichiers, un par type de script du jeu :

`Sangokushi-script-Type1.tsv` … `Type4.tsv`

## Format

TSV (séparateur : tabulation, UTF-8, fins de ligne d'origine à conserver), une ligne par phrase du jeu :

| # | Colonne | À modifier ? |
|---|---|---|
| 1 | Filename | non |
| 2 | Index | non |
| 3 | Type | non |
| 4 | Entry# | non |
| 5 | Line# | non |
| 6 | Original Text (japonais) | non |
| **7** | **Translated Text** | **oui** |
| 8 | Remarks | libre |

Si la colonne 7 est vide, le jeu garde le texte japonais.

## Règles d'écriture

- Les balises `【…】` (couleurs, noms de variables comme `【Yk1.strYkName】`) doivent rester **identiques** à l'original : copiez-les telles quelles.
- `\n` dans la colonne 7 est un saut de ligne explicite. Le moteur coupe et équilibre les lignes tout seul : n'en ajoutez que pour des vers/listes.
- Utilisez les vrais caractères français (`é`, `«  »`, `œ`, `…`) : l'atlas de police les contient. Un caractère absent est signalé par `tools/check.sh`.
- Une phrase trop longue déborde de sa fenêtre : préférez une formulation plus courte (le lint signale les cas détectables).

## Fichiers annexes

- `yokai_names_en.tsv` : noms anglais officiels des Yo-kai (Yo-kai Watch Wiki, CC BY-SA), généré par `tools/translation/yokai_names.py`.
- `skills_fr.tsv` : les 472 compétences du jeu (japonais, FR actuel, EN/FR officiels des wikis Yo-kai Watch, colonne `source`), et `skills_official.tsv` : 1 517 capacités officielles japonais/anglais/français ; générés par `tools/translation/skill_names.py` (API publique des wikis, CC BY-SA).
- `glossary_en.tsv` : glossaire envoyé à DeepL.
- `manual_en.json` : corrections anglaises faites à la main, appliquées par-dessus DeepL (`tools/translation/apply_manual.py`).

## Ajouter une langue

Voir « Autres langues » dans [`../docs/TECHNIQUE.md`](../docs/TECHNIQUE.md) : `tools/translation/translate_deepl.py --lang xx` crée `translations/xx/`, puis `tools/translation/build_language.sh`.
