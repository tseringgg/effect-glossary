# Search fixes: Part 1 (investigation) and Part 2 (proposal). Nothing is built.

Written for: the project owner, to approve or change the rules before Part 3. Everything here was measured by `src/probe_search_defects.py` (new, read-only; output `build/search_defects_probe.json`) or read by me (`reports/search-fixes-reads.json`). No existing file, correction, id or figure was touched.

## A correction to the clutter probe first

The clutter probe said hand-defined groups had "0 cards" and "open an empty page". **That was wrong in what it implied.** I counted *placed members* (cards a person added by hand). The search index counts a hand group by its **rule matches** (suggestions), the row shows that number, and the page has two parts: "Members: placed here by hand" and "Rule matches: suggestions, not members", where the second list is full (blink 192, cantrip 710, mana rocks 370). So no search result opens an empty page. The real defect is that the row says "192 cards" for a group with 0 placed members and 192 suggestions, and that such a group can rank first. The clutter probe also ran the index file alone; the page adds 321 type pages and 42 ability-type pages at run time, so its counts (creature 1,027, artifact 152) were slightly low. This round uses the index the page actually builds (2,461 entries).

## Part 1: what causes each defect

### 1. Groups with no cards
- The index has **no entry with size 0**, in any layer (leaf 1,222, community tag 306, tentative 177, keyword filter 172, keyword block 106, loose 48, hand 41, merged page 13, replacement 13, type page 321, ability-type page 42).
- **Hand groups: 41 in the index, 36 with no placed member, 5 with some** (the biggest, "Wins, loses or draws the game", has 6). All 41 have rule matches.
- **What ranks them first.** A hand alias is an exact-alias match (tier 1, ordered by the alias file), and the owner put the hand group first: **20 of 286 aliases** point first at a memberless hand group (blink, flicker, cantrip, mana rock, rock, balance, cataclysm, …). That is why blink, flicker, cantrip and mana rock return a hand group first. A fifth case, "exil", is different: "Exiles a permanent and returns it …" is a tier-2 name-prefix match and ranks first by size score (192 rule matches).
- A memberless hand group appears in **16 of the 100 searches**, first in 5 (blink, cantrip, mana rock, flicker, exil).

### 2. Weak matches ("zombie" → Sacrifice a creature, "flash" → Flashback)
Match kinds in the ranking: exact name (0), exact alias (1), name starts with (2), every word in the name (3), most words (3.5), tag-slug words or partial alias (4), drafted alias (4.5), description (5), family (6), plus "did you mean". Causes found:
- **Description hits come from a quoted card line.** 1,449 of 1,964 group descriptions begin "Example: “…”", auto-written from the line of the group's most popular member (`auto_described: 1951`). "zombie" matched "Sacrifice a creature" because its example line is "…you may sacrifice a Zombie…". The match is on one card's text, which the search is meant never to search. Whole-word matching is already enforced; the problem is the source of the text.
- **Prefix matches on a complete word.** Tier 2 lets the last typed word be the start of a longer word, tier 3 lets any word be. "flash" → Flashback (tier 2) and "gains flashback" (tier 3). "equip" → Equipment, "ramp" → Rampage, "land" → Landwalk, Landfall.
- **A stripped inflection creates a prefix.** "cycling" is also tried as "cycl", which is the start of "Cyclops" (a type page). That is why Cycling returns Cyclops second.
- Not defects: typo correction ("destory") and the intended partials ("sacrific", "tok", "exil" are not words, so prefix is the only way they work). "tok" is in the English word list, so a "real word" test alone would misjudge it; the rule below only reorders, so it is safe.

How many of the 100 searches (97 return something) contain a result that matches only through a weak kind (description, name-prefix, "most words", slug words, partial alias; fuzzy excluded because it is the typo feature): **56 of 100 have at least one, 34 have one in the top 5.** In the 50 probe searches: 29 and 15. Broken down (searches containing the kind): description 38 (36 of them an example line), name-prefix 15, partial alias 11, slug words 5, "most words" 4. In the top 5, example-line descriptions occur in 14 searches (dragon, saga, proliferate, elf, goblin, surveil, ward ×2, zombie, bounce, copy spell, draft from spellbook, hexproof indestructible, search for plains); prefix on a complete word in 5 (flash, equip, cycling, ramp, untap lands).
Partial aliases ("pump" → "Pay mana, no other cost") and slug words ("tutor" → community tags "Searches for a card …") are weak by kind but mostly sensible; I propose no change to them.

### 3. Searches that return nothing
Of the 100, **three return nothing**: recursion, fetch land, rump.
- **recursion**: no alias, no group name or description with the word, not in the dictionary, and no group word within two edits, so no correction.
- **fetch land**: both words are real, no alias, no group names it. (`landcycling` and `ramp` aliases exist but do not answer "fetch land".)
- **rump** is a deliberate near-collision (it must not become "ramp"). Returning nothing is correct.
- **overrun** now returns something: the ability page "Anthems and lords" through that page's alias. Partly right (it is a static anthem; Overrun is a one-shot team pump with trample).
Groups that exist for each (target ids, for the alias proposal in Part 2): recursion → leaf:a14e122ade, leaf:a31121acb5, leaf:a4ba4fe8b8 (graveyard to hand / to the battlefield). fetch land → leaf:ad63abdf62, leaf:aa22211a7e (search a basic land onto the battlefield). overrun → leaf:a88dbba5aa, leaf:a4642ebb65 (all your creatures get +N/+N). I looked for "draft from spellbook" too (a fresh query that returned a noise group): the conjure tags exist (tag:264e8508-… "Conjures spellbook").

### 4. Generic words (index as the page builds it)
| word | results | type page | named or starts with | contains the word | example-line only | other |
|---|---:|---|---:|---:|---:|---:|
| creature | 1,035 | Creature first | 43 | 489 | 479 | 24 |
| artifact | 153 | Artifact first | 3 | 60 | 89 | 1 |
| sacrifice | 82 | (ability page "Sacrifice as a cost" first) | 26 | 13 | 43 | 0 |
| draw cards | 65 | – | 21 | 10 | 29 | 5 |
| damage | 140 | – | 6 | 84 | 44 | 6 |
| token | 167 | – | 0 | 154 | 13 | 0 |
| land | 155 | Land first | 6 | 73 | 74 | 2 |
The page shows 5 and "Show more" up to 30. The top 10 are already sensible for all seven (the type page or the exact merged page first, then name matches by size; see `build/search_defects_probe.json` → `generic`). What is wrong is the *count and the tail*: a third to a half of the list is example-line noise, and the header says "1,035 groups match; showing 30".

### 5. Baseline (before any change)
100 searches = 50 probe + 30 baseline + 20 fresh (duplicates such as wrath and counterspell kept, as separate entries). Reads in `reports/search-fixes-reads.json`.
- **Top-1 sensible: 90 of 100** (5 partly, 4 not, 1 "expected nothing").
- **Top-5 sensible: 93 of 100** (2 partly, 4 not, 1 expected nothing).
- Not sensible (N): recursion, fetch land, "draft from spellbook" (returns "You spend mana as any color"), "tap creatures for mana". Partly (M): overrun, magecraft, and top-1 only for graveyard, exil, graveyrad.
Subsets: baseline 30: top-1 27, top-5 30. Fresh 20: top-1 16, top-5 16 (rump expected nothing; draft from spellbook and tap creatures for mana not sensible). Probe 50: top-1 47, top-5 47 (recursion and fetch land none; overrun partly).
These are my reads (not independent of the builder). They are the numbers Part 3 must not fall below.

## Part 2: proposed rules, effect, risk (all behind `SEARCH_FIXES`, default off until you approve)

| # | rule | effect (simulated on the 100 searches) | risk |
|---|---|---|---|
| R1 | **Hand groups: say what the count is, and demote only at weak tiers.** A hand group's row says "N rule matches, M placed by hand" (not "N cards"). A memberless hand group is never hidden; at tiers below exact name/alias it ranks after groups that have members. | Labels change on blink, flicker, cantrip, mana rock and every other hand-group row. Order changes in 1 of 100 searches (exil: the blink group, now first, drops below the groups that have members). | Low. I do **not** propose hiding them: for blink, cantrip, flicker and mana rock the memberless group *is* the right answer and its suggestion list is full. Hiding would leave "no group" for the three words you named. |
| R2 | **Descriptions that are an auto-written example line are not matched in the main list.** They stay reachable in one collapsed row under the results ("N more groups matched only in an example card line ▸"), next to the existing "matched only by family" row. Written descriptions and drafted-from-tag/note descriptions still match as today. | 36 of 100 searches lose entries from the main list; 13 change their top 5 (dragon, saga, proliferate, elf, goblin, surveil, ward ×2, zombie, copy spell, draft from spellbook, hexproof indestructible, search for plains). Removed counts: creature −479, artifact −89, sacrifice −43, draw cards −29, damage −44, token −13, land −74. In all 13 the remaining top 5 is the same or cleaner; "saga" loses "Put lore counters on this permanent" from the top 5 (the Saga type page stays first, the group is in the row). "draft from spellbook" goes from one wrong result to none and says so. | Medium-low: a user whose only route is a card line ("dragon" → Add mana, of one specific color) finds it behind one click instead of at result 5. Nothing becomes unreachable. |
| R3 | **A longer word that merely starts with the typed word ranks after whole-word matches** (Flash before Flashback, Ramp before Rampage, Land before Landfall). An inflection (-s, -ed, -ing, -er) is not "longer". Applies only when the typed word is a real word or a word of a group name; it only *reorders*, so a partial with no whole-word match ("sacrific", "tok") is untouched. The stripped "-ing" form ("cycl") no longer prefix-matches when the full word is itself a group-name word. | Order changes in 2 of 100 searches' top 5 (flash, untap lands) and Cyclops leaves "cycling". 10 of the 100 runs (8 distinct words; “draw cards” and “discard” only match inflections such as “drawing”, which stay) have such a result; 5 more (sacrific, regener, indestruct, exil, counterspel) are partials/typos and are explicitly unchanged. | Low. "equip" would show Equip, then Equipped creature …, then Equipment: Equipment moves down but stays in the list. |
| R4 | **Generic words: a count that means something, and two blocks.** After R2, results are shown in two headed blocks, "Named …" (exact and starts-with, whole word) and "Contains the word", each 10 then "Show 10 more", total cap unchanged at 30 per block. Type pages and exact names stay first (already true). The header says “556 groups match; showing 20” instead of “1,035 groups match; showing 30”, and the example-line row carries the rest. | Affects any search with more than 10 results (37 of 100). After R2: creature 556, artifact 64, sacrifice 39, draw cards 36, damage 96, token 154, land 81. Top 10 unchanged for all seven. | Low-medium: a layout change on the results panel (narrow screen included); the keyboard order must follow the blocks. Optional: if you would rather not add blocks, R4 shrinks to the honest count text only. |
| R5 | **No-result searches say so plainly, and the alias proposals are listed for you** (below). I write nothing to `corrections/`. | recursion, fetch land: "No group is named “recursion”. Try a card name, or a common term such as “board wipe”." (today's text, kept) with "Didn't find it?" ; they stay empty until you accept aliases. rump: unchanged, correct. | None. |

Bars after R1–R4: no search marked sensible changes to wrong (checked against the reads for the 13 changed top-5s), top-5 sensible stays at 93, and recursion / fetch land say "no group" (until you accept aliases) while overrun keeps its page.

### Alias proposals (entries only; for your review; not written)
| alias | target ids | fit | what it leaves out |
|---|---|---|---|
| recursion | leaf:a14e122ade (graveyard → hand), leaf:a31121acb5 (your graveyard → battlefield), leaf:a4ba4fe8b8 (a graveyard → battlefield) | partial | repeatable recursion engines as a kind, flashback/dredge/escape (keyword pages hold those); the existing `reanimate` alias already points at the two battlefield groups |
| fetch land | leaf:ad63abdf62, leaf:aa22211a7e (search a basic land / a land onto the battlefield) | partial | the "sacrifice this land" cost that makes a fetch land (spells like Rampant Growth are in the same groups), nonbasic fetches |
| overrun | leaf:a88dbba5aa, leaf:a4642ebb65 (all creatures you control get +N/+N, then grant an ability / until end of turn) | partial | the trample requirement, and the "only once, this turn" meaning of a one-shot overrun |
| draft from spellbook | tag:264e8508-85aa-4c0c-82c0-31de4f3f283d (Conjures spellbook) | good | cards that conjure other kinds of card (separate "Conjures …" tags) |
| mana dork (phrase "tap creatures for mana") | the existing `mana dork` alias | – | not proposed; the phrase is a query-form issue, not a missing alias |

## What I need from you before Part 3
1. R1: label plus weak-tier demotion only (my recommendation), or hide memberless hand groups except by exact name/alias (your wording), accepting that hand groups then never appear for partials like "exil"?
2. R2: collapsed row (recommended) or remove example-line matching outright?
3. R3: reorder only (recommended), as described?
4. R4: two blocks with the honest count, or the count text only?
5. The five alias entries: accept, edit, or drop (you edit `corrections/group_aliases.json`; I will not).

## Alias proposals: id stability (added with Part 3; nothing written to corrections/)
Four entries, not five: the fifth line in the earlier table ("tap creatures for mana") was a "not proposed" note. `leaf:` ids are hashes that can change on a rebuild (the alias file records about 34 of 1,273 did once; the build reports a vanished id as an ERROR). `tag:` ids are Scryfall tag UUIDs and do not change.
| alias | target id | id kind |
|---|---|---|
| recursion | leaf:a14e122ade, leaf:a31121acb5, leaf:a4ba4fe8b8 | hashed ×3 |
| fetch land | leaf:ad63abdf62, leaf:aa22211a7e | hashed ×2 |
| overrun | leaf:a88dbba5aa, leaf:a4642ebb65 | hashed ×2 |
| draft from spellbook | tag:264e8508-85aa-4c0c-82c0-31de4f3f283d | stable |
Correction to Part 1: in tester mode a hand group's row already read "N possible cards" (not "N cards"); SEARCH_FIXES adds ", M placed by hand".
