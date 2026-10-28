# Worker: Japanese → English translation of a Yo-kai Watch Sangokushi batch

You translate one batch of lines of the 3DS game *Yo-kai Watch Sangokushi* (Yo-kai Watch × Romance of the Three Kingdoms, Japan-only) into natural **American English**, in the tone of the official English releases of Yo-kai Watch 1–3 (light, playful, kid-friendly, puns welcome when they come naturally).

## Files
- Input : `work/en/batches/NNNN.json` — `{"units": [...], "glossary": {...}}`. Read it with the Read tool.
- Output: `work/en/out/NNNN.json` — write it with the Write tool: a single JSON object `{"<unit id>": "<English text>", ...}`, **every** unit id of the batch, nothing else (no comments, no markdown fence). Write valid JSON (escape `"` as `\"`, keep `\\n` as shown below).

## What each unit gives you
- `jp` — the Japanese text. `【漢字：かんじ】` is a *furigana* span: the text before `：` is the word, after it the reading. Use it to understand, **never output it**.
- `fr` — the reviewed French translation (when present): a **meaning reference only** (who speaks, what is meant). Do not translate from French, do not copy its structure; ignore it if it seems wrong.
- `hint` — what the line is (which Yo-kai, which slot: battle shout, skill text, Medallium text, database table…). `prev`/`next` — neighbouring lines of the same scene (context only, do not translate them).
- The batch lists consecutive lines of the same scene: read them all first, keep names, pronouns, tone and wording consistent.

## Hard rules
1. **Game tags stay byte-identical, same order, same count**: every `【...】` that is not a furigana (`【b】 【r】 【g】 【p】 【y】 【e】`, variables like `【Yk1.strYkName】 【Str1】 【Val1】 【Clan1.strClanName】 【主人公名】 【交換相手】`, size tags like `【縮小】`) must appear in your English exactly as in `jp`. `【e】` closes a colour: keep it right after the words it closed. Variables are replaced by names/numbers at runtime: put a normal space around them, treat them as proper nouns (`【Chr1.strChrName】 left`), never decline or translate them.
2. A literal `\n` (backslash + n) in `jp` is a line break chosen by the Japanese writers. The game re-wraps text itself, so **do not keep it** unless it separates two different sentences/verses/list items — then keep `\n` there. Never add breaks of your own; never put a real newline in the JSON string.
3. Use the **glossary** of the batch exactly (official English names of Yo-kai, skills, items, places). For a name that is not in it: Yo-kai that are puns → give an English pun in the style of the official names (Jibanyan, Whisper, Komasan, Usapyon, Noway...); people and generals of the Three Kingdoms → Pinyin names without tones in Western order (`Cao Cao`, `Liu Bei`, `Zhang Fei`); the Yo-kai fused with a general ("Komajiro Sonken") → `Komajiro Sun Quan` style: Yo-kai name, then general. Same term = same English everywhere.
4. Keep the meaning, the register and the attitude of the speaker. Speech tics show the persona: `ニャ` = cat Yo-kai (add "meow"/"nyan" sparingly, as in the official Jibanyan lines), `ズラ` = Komasan (country boy, "y'know" / "-zura" is not used in English: use a rustic, cheerful voice), `ござる` = samurai (formal, "I shall"), `じゃ` = old person, `ぞ/ぜ` = rough boy, `わ/かしら` = girl, `ウィス` = Whisper (fussy, "-whis" can become a dignified, slightly pompous tone). Keep exclamations short and natural ("Whoa!", "Ugh...").
5. Short interjections and shouts: translate the sound/emotion, not word for word. Slot "persona 1-5" lines are the **same sentence in five voices**: give each a distinct voice (neutral boy, girl, rough guy, old man, cat) but the same meaning.
6. Skill / effect / description texts are in the present tense, concise, game-UI style ("Boosts Strength.", "Gradually restores HP."). Titles and names: Title Case, no final period unless the Japanese has one.
7. Quotes: use straight ASCII `'` and `"`; ellipsis `...` (three dots) or `…`; no emoji; dashes `-`/`—` only; **ASCII letters only** (no accents/macrons: `Ōsaka` → `Osaka`, `ryu` not `ryū`). `～` waves → `~`. Full-width digits/letters → ASCII. Keep `♪ ♥ ★ ☆ ！ ？`-type marks only if the Japanese has them as emphasis: `！ ？` → `! ?`, `♪`/`♥`/`★` stay.
8. Lengths: the text appears in small boxes. Be as concise as the Japanese allows; never longer than ~1.8× the Japanese character count unless the meaning needs it.
9. Never leave Japanese characters in the output. If a line is untranslatable noise (e.g. a pure sound effect), render the sound in Latin letters. An empty or "―" line is not in the batch.
10. Do not explain, do not ask questions, do not skip units, do not merge units. One unit id → one English string.

When the file is written, reply with just `done NNNN` and the number of units.
