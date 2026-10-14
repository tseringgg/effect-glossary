# Would a cheap phrase supplement place more of the remaining cards? (investigation only)

Nothing is built, placed or changed; nothing is committed. Scripts: `src/probe_phrases.py` (Parts A and B), `src/probe_flag_annotation.py` (Part C). Data: `build/phrase_probe*.json`, `build/flag_annotation_*.json`.
**Measured** = counted from the build or read by me; **estimate** = a judgment call is stated.

**Stop rule, written into the script before any result was seen:** if the top 30 families (ranked by cards covered) would place fewer than about 150 cards, the supplement is not worth building.
**Result: the top 30 families would place about 16 cards (estimate). The stop rule is met by a wide margin. The supplement is not worth building.**

## Part A. The unread phrases of the 1,231 gap cards with no readable ability

**Fragments.** A fragment is the clause text of an Unimplemented node, an unknown trigger mode or an unrecognized condition. 1,229 of the 1,231 cards have at least one (2 have none recorded). Normalization: card name to ~, numbers and number words to N, runs of mana symbols to {M}, counter names to <ctr>.
**Unread clauses per card (distinct, normalized):** one 919 cards (75%), two 217 (18%), three or more 93 (8%), none recorded 2.
**Families (identical normalized phrases):** 1,358 for 1,229 cards: 1330 unread-clause families, 19 unknown trigger modes, 8 unrecognized conditions, 1 empty effect. The top 50 families cover **256 cards** (21% of the 1,231); the tail is one-offs.

**Clean siblings.** A family has a clean sibling when the same phrase (3 or more words) occurs in the description of an ability that parsed cleanly on a card with no gap anywhere. **Of the top 50 families only 4 have one (covering 24 cards); 46 families (233 cards) have no clean parse anywhere.**
None of the four siblings is a whole-ability template (the clause is part of a longer ability), so a sibling's structure could not simply be copied. Reading the siblings by hand: for "draft a card from ~'s spellbook" the "sibling" is an ability that parsed as "spend mana as any color": the clause is simply absent from its structure, so it is not a reading of the clause at all;
"damage that would reduce your life total..." and "heist target opponent's library" are the same kind of false match. Real siblings: "can block an additional creature" (22 abilities, a static extra-blockers mode), "can block any number of creatures" and, loosely, "choose a creature card in your hand" (a pump that ignores the hand-choice).
Short phrases ("you", "phase", "otherwise") match everywhere and were excluded.

**Estimated cards placed per family** (estimate): a card counts only if the clause is its only unread clause, none of its abilities is held for a dropped condition, and a clean sibling's ability sits in an unflagged leaf of 5 or more (or a broad leaf); the sibling's placement stands in for where the new item would land.
Matches to a promotable tentative group are not estimated. Cumulative curves are unions of cards.

| Top families | Cards covered | Estimated cards placed (automatic sibling check) |
|---|---|---|
| 10 | 97 | 10 |
| 25 | 174 | 16 |
| 30 | 193 | 16 |
| 50 | 256 | 22 |
| 100 | 351 | 25 |
| **all 1,358 families** | 1,229 | **34** (a ceiling: 38 families have a sibling at all) |

After my hand check of the siblings only about 9 of the top-30 figure survive (the 6 "choose a creature card in your hand" cards and the 3 "can block an additional creature" cards); the rest rest on false sibling matches (estimate).
**A more generous variant** (it breaks the corrections rule of reusing an existing node shape): if a rule could invent a consistent new node for each family that has at least five cards for which the clause is the only unread one, those cards would form leaves of their own. That is 11 families and **67 cards** (draft from a spellbook 10, mana of any type a land produced 8, endure 7, open an Attraction 6, choose a creature card in your hand 6, and six families of 5). It is also far below 150, and the tail beyond rank 25 has no family with five such cards.

### The top 50 families
| # | Kind | Phrase (normalized) | Cards | Sole-cause | Sole and no dropped-condition flag | Clean sibling | Est. placed |
|---|---|---|---|---|---|---|---|
| 1 | unread | starting with you | 29 | 2 | 2 | none | 0 |
| 2 | unread | {tk}{tk} - N/N | 24 | 0 | 0 | none | 0 |
| 3 | unread | put a sticker on a nonland permanent you own | 14 | 0 | 0 | none | 0 |
| 4 | unread | draft a card from ~'s spellbook | 11 | 10 | 10 | part of a longer ability (2) | 10 |
| 5 | unread | {tk}{tk}{tk} - N/N | 11 | 0 | 0 | none | 0 |
| 6 | unread | get {tk} | 9 | 1 | 1 | none | 0 |
| 7 | unread | add one mana of any type that land produced | 8 | 8 | 8 | none | 0 |
| 8 | unread | open an attraction | 8 | 6 | 6 | none | 0 |
| 9 | unread | {tk}{tk}{tk}{tk} - N/N | 8 | 0 | 0 | none | 0 |
| 10 | unread | {tk}{tk}{tk}{tk}{tk} - N/N | 8 | 0 | 0 | none | 0 |
| 11 | unread | choose a creature card in your hand | 7 | 6 | 6 | part of a longer ability (1) | 6 |
| 12 | unread | draft this card face up | 7 | 0 | 0 | none | 0 |
| 13 | unread | it endures N | 7 | 7 | 7 | none | 0 |
| 14 | unread | pay any amount of mana | 7 | 3 | 3 | none | 0 |
| 15 | unread | otherwise | 6 | 2 | 0 | none | 0 |
| 16 | unread | remove this card from your deck before playing if you're not playing f | 6 | 0 | 0 | none | 0 |
| 17 | unread | the next N damage that would be dealt to this creature this turn is de | 6 | 5 | 5 | none | 0 |
| 18 | unread | the next time a source of your choice would deal damage to you this tu | 6 | 5 | 5 | none | 0 |
| 19 | unread | become that type | 5 | 5 | 5 | none | 0 |
| 20 | unread | for each player, choose friend or foe | 5 | 5 | 5 | none | 0 |
| 21 | unread | get {tk}{tk} | 5 | 0 | 0 | none | 0 |
| 22 | unread | put a name sticker on it | 5 | 4 | 4 | none | 0 |
| 23 | unread | roll N dN and choose one result | 5 | 5 | 5 | none | 0 |
| 24 | unread | the next time you would draw a card | 5 | 5 | 5 | none | 0 |
| 25 | unread | those votes are revealed | 5 | 0 | 0 | none | 0 |
| 26 | effect | GenericEffect[?] | 4 | 0 | 0 | none | 0 |
| 27 | unread | change the text of target spell or permanent by replacing all instance | 4 | 3 | 3 | none | 0 |
| 28 | unread | conjure a duplicate of it into your hand | 4 | 1 | 0 | none | 0 |
| 29 | unread | empower jace N | 4 | 4 | 4 | none | 0 |
| 30 | unread | phase | 4 | 3 | 3 | none | 0 |
| 31 | unread | recruit | 4 | 4 | 4 | none | 0 |
| 32 | unread | starting intensity N | 4 | 0 | 0 | none | 0 |
| 33 | unread | target player takes an extra turn after this one | 4 | 2 | 2 | none | 0 |
| 34 | unread | the next time a source of your choice would deal damage to any target  | 4 | 4 | 3 | none | 0 |
| 35 | unread | you | 4 | 4 | 4 | none | 0 |
| 36 | unread | you take the initiative | 4 | 4 | 4 | none | 0 |
| 37 | unread | can block an additional creature | 3 | 3 | 3 | part of a longer ability (22) | 3 |
| 38 | unread | change the text of target permanent by replacing all instances of one  | 3 | 3 | 3 | none | 0 |
| 39 | unread | choose a card in your hand | 3 | 1 | 1 | none | 0 |
| 40 | unread | choose the same mode more than once | 3 | 0 | 0 | none | 0 |
| 41 | unread | choose {M} worth of modes | 3 | 0 | 0 | none | 0 |
| 42 | unread | damage that would reduce your life total to less than N reduces it to  | 3 | 3 | 3 | part of a longer ability (2) | 3 |
| 43 | unread | double target creature's power | 3 | 3 | 3 | none | 0 |
| 44 | unread | double ~'s power | 3 | 3 | 3 | none | 0 |
| 45 | unread | exchange life totals with target opponent | 3 | 3 | 2 | none | 0 |
| 46 | unread | give that permanent or player another counter of that kind | 3 | 3 | 3 | none | 0 |
| 47 | unread | if an effect would create one or more tokens under your control, it cr | 3 | 2 | 0 | none | 0 |
| 48 | unread | in turn order | 3 | 0 | 0 | none | 0 |
| 49 | unread | players play with their hands revealed | 3 | 2 | 2 | none | 0 |
| 50 | unread | put it on their choice of the top or bottom of their library | 3 | 3 | 3 | none | 0 |

## Part B. Drafts for the top 20 families (design only; nothing is built)

For each family I read the oracle text of five touched cards (the five with the lowest oracle ids) before deciding whether a rule could exist. "Meaning" marks a clause that changes the meaning of the rest of the ability, as Spark Double's does.

| # | Phrase | Cards (sole) | Rule pattern and the structure it would emit | Leaf or group it would match | Five cards read | Meaning-changing? |
|---|---|---|---|---|---|---|
| 1 | starting with you | 29 (2) | "starting with you, each player ..." (council votes, join forces); no node for turn-order scope or votes | none | the clause is part of a vote or pay-in mechanic in all five | **yes**: it sets who acts, in what order, and that votes decide the rest |
| 2 | {TK}{TK} - N/N | 24 (0) | a ticket-level header with a power and toughness; no node exists | none | all five are Unfinity ticket cards where the level lines carry the real abilities | **yes**: it defines level thresholds for the rest |
| 3 | put a sticker on a nonland permanent you own | 14 (0) | sticker mechanic; no node | none | five Unfinity cards, each with other unread clauses | yes (sets what later clauses refer to) |
| 4 | draft a card from ~'s spellbook | 11 (10) | "draft a card from this card's spellbook" (Alchemy): nearest existing shapes are Seek and Conjure, which are not the same action (choose one of three) | would form its own leaf of 10 if given a new effect type; no existing leaf | five Alchemy cards, a plain trigger or activation each time | no |
| 5 | {TK}{TK}{TK} - N/N | 11 (0) | as 2 | none | as 2 | yes |
| 6 | get {TK} | 9 (1) | gain tickets; no node | none | five Unfinity cards, each also with a sticker clause | no |
| 7 | add one mana of any type that land produced | 8 (8) | "whenever a player taps a land for mana, that player adds one mana of any type that land produced" (Mana Flare): a trigger mode exists (taps for mana); the effect "same type as produced" has no precedent | none; a new leaf of 8 if invented | five Mana Flare effects, identical text | no |
| 8 | open an attraction | 8 (6) | an Unfinity action; no node | would form a leaf of 6 if invented | five cards, identical clause in parentheses | no |
| 9 | {TK}{TK}{TK}{TK} - N/N | 8 (0) | as 2 | none | as 2 | yes |
| 10 | {TK}{TK}{TK}{TK}{TK} - N/N | 8 (0) | as 2 | none | as 2 | yes |
| 11 | choose a creature card in your hand | 7 (6) | "choose a creature card in your hand. It perpetually gains/gets ..." (Alchemy): reuse a Pump or GenericEffect with a hand-card target; the existing "sibling" ignores the hand choice | a broad leaf ("A target gets +N/+N, what it applies to isn't recorded") | five cards, each followed by a perpetual keyword or +2/+2 | **yes**: it names the target of the next sentence |
| 12 | draft this card face up | 7 (0) | a draft-time instruction; no game effect | none | five cards, a draft rule in each | no (nothing to place) |
| 13 | it endures N | 7 (7) | "it endures N" (put N counters on it or create an N/N Spirit token): a choice between two existing effects, no single node | would form a leaf of 7 if invented | five cards, reminder text spells the choice | yes (a choice) |
| 14 | pay any amount of mana | 7 (3) | "each player may pay any amount of mana ... X is the total paid" (join forces): needs a variable total across players | none | all five set X for the next sentence | **yes**: it defines X for the rest |
| 15 | otherwise | 6 (2) | a bare "otherwise": an else branch; the detector's field list shows else_ability exists, but it needs the condition it negates | none (it needs the unread condition too) | five cards, the clause negates the previous sentence | **yes**: it inverts the preceding sentence |
| 16 | remove this card from your deck before playing if you're not playing for ante | 6 (0) | a deck instruction for ante cards; no effect | none | five Ante cards with other unread clauses (ante) | no |
| 17 | the next N damage that would be dealt to this creature this turn is dealt to target creature | 6 (5) | a damage-redirection shield; Prevent damage nodes exist but redirection does not | would match "Prevent damage" only loosely | five en-Kor cards, identical clause | **yes**: it is a replacement effect ("instead") |
| 18 | the next time a source of your choice would deal damage to you this turn, prevent that damage | 6 (5) | a one-shot prevention shield; reuse of the existing prevent-damage node with amount "all" changes "next time" to "every time" | "Prevent damage, less common kinds" (tentative) | five cards | **yes**: "next time" is lost if mapped to "all" |
| 19 | become that type | 5 (5) | "choose a creature type. Target creature becomes that type": needs the chosen type from the previous clause | none | five cards, one clause pair | **yes**: it refers to a choice in the previous sentence |
| 20 | for each player, choose friend or foe | 5 (5) | friend-or-foe partition; no node | none | five friend-or-foe cards; the clause splits every later sentence | **yes**: it defines two groups for the rest |

**Reading:** only family 11 has a usable existing shape, and it ignores the point of the clause; two more (17, 18) could be approximated by the prevent-damage node but would change the meaning ("next time" becomes "always"). Eleven of the 20 are Unfinity ticket, sticker or attraction mechanics, draft-time instructions or Join-forces voting, for which no node exists anywhere in the corpus.
The rest would need a node with no precedent, which the corrections schema forbids ("a patch is only used when the corrected value reuses a node shape with existing precedent in the same slot").

### The supplement design, if anyone still wants it (not recommended)
* **Overlay keyed by oracle_id**, one entry per card and clause: `{oracle_id, bucket, index, node_path, rule_id, replaces: Unimplemented, emits: <node copied from a cited precedent>, precedent: [oracle ids and paths], evidence: oracle text, upstream snippet and its hash, added}`, in a new file next to `data/overlay/`.
* **Replace Unimplemented nodes only**; the build asserts that the node at `node_path` is an Unimplemented node with the recorded hash and never touches a clean ability.
* **Retirement check on each entry:** if upstream's parse of that card no longer has an Unimplemented at that path (they fixed it), the entry is reported as retired and ignored; a build fails on an entry whose evidence no longer matches.
* **Method recorded in data only** (`phrase_supplement`); placements from it are tentative, flagged, and counted in the tentative figure only.
* Not built: the stop rule says it would place about 16 cards (67 on the generous variant) for 20-plus rules.

## Part C. Dropped-condition holds: would the effect land in the right leaf if the condition were ignored? (measurement only)

**Draw.** Seed 20261027, declared before computing. Population 1,606 abilities on 1,545 cards (the cards left in the pile before the 2026-10 promotions, so the numbers match earlier rounds; 226 of those cards have since become tentative). 100 drawn, one per card, stratified by sub-shape, none hand-picked, no redraw, none skipped.
I read each card's oracle text and the ability text and wrote the effect and leaf I expected, and whether the dropped condition could change or invert the effect, to `build/flag_annotation_reads.json` before the leaf the build would assign was shown.
"Condition yes" = it gates or replaces the head effect or is an "if you don't / unless / instead / otherwise" clause; "rider" = it gates only an extra clause; "no" = harmless.

| Sub-shape | Drawn | Right | Loose | Wrong | No leaf | Condition yes | Rider | No |
|---|---|---|---|---|---|---|---|---|
| sequential-chain | 39 | 24 | 7 | 0 | 8 | 19 | 19 | 1 |
| trigger-intervening | 19 | 14 | 1 | 1 | 3 | 16 | 2 | 1 |
| result-dependent | 17 | 12 | 1 | 0 | 4 | 6 | 8 | 3 |
| embedded-replacement | 8 | 4 | 1 | 0 | 3 | 8 | 0 | 0 |
| negative | 4 | 2 | 2 | 0 | 0 | 4 | 0 | 0 |
| compound | 3 | 3 | 0 | 0 | 0 | 3 | 0 | 0 |
| filter-targeting | 3 | 3 | 0 | 0 | 0 | 3 | 0 | 0 |
| replacement-level | 3 | 2 | 0 | 0 | 1 | 2 | 0 | 1 |
| static-level | 3 | 3 | 0 | 0 | 0 | 1 | 2 | 0 |
| branch-structural | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |

**Overall: right 68, loose 12, wrong 1, no leaf 19; condition-inverting or -changing: 63 of 100 (53 of the 81 that would get a leaf), rider only 31, harmless 6.**
The one wrong: Akuta, Born of Ash ("return this card from your graveyard to the battlefield") would be filed under "Sacrifice a land", the cost. The bar for considering a tentative placement (no more than 5 wrong) is met: 1 of 100 (95% range 0.2% to 5.4%). **100 cannot show a rate.**
19 of the 100 have no leaf at all (no usable signature, or no leaf of 5): replacement effects ("if you would draw ...", "twice as many tokens"), vote or clash mechanics, and a few others. That matches the earlier whole-population measure: if the flags were ignored, 1,294 of the 1,545 cards would find a leaf (911 precise leaf, 286 broad, 97 tentative group).

**What display would be honest** (design only, not built): the ability's leaf (or tentative group) **together with the condition text from the oracle text**, flagged as tentative, for example: *"Tentative placement: Counter a spell. This ability has a condition the tool did not read: 'if it has the same mana value as the discarded card'. The condition may change what the ability does."*
For the 53 of 81 whose condition changes or inverts the effect, the condition text matters more than the leaf: "draw a card ... instead seek two Vampire cards" and "sacrifice an artifact, if you don't tap this and take 2 damage" would be misleading under a plain leaf. The tentative wording must say the effect depends on the condition; the card must never be counted in the precise or broad figure.

## Part D. Recommendation

| Rank | Lever | Cards moved | Effort | Basis | Leaves behind |
|---|---|---|---|---|---|
| 1 | **Dropped-condition annotation:** leaf plus the condition text, tentative and flagged | up to 1,294 cards (911 would find an unflagged leaf, 286 a broad leaf, 97 a tentative group; the figure is measured on the whole population, the quality from 100 reads) | moderate: a display and a data file; no parser change; condition text comes from the detector's clauses | measured counts, estimate that the leaf is right for about 99% (1 wrong of 100, range 0.2-5.4%) and that 65% of leafed ones have a condition that changes the effect | the 19% with no leaf; the 1,300 unreadable cards; the conditions themselves stay unread |
| 2 | Phrase supplement | about 16 (top 30 families), at most 34 for all families, 67 on the generous variant | moderate to high per family (new node shapes with no precedent) | estimate; stop rule met | nearly everything; 1,358 families |
| 3 | Rust patch (phase.rs parser) | up to 919 cards have a single distinct unread clause (813 of them with no dropped-condition flag); how many would then place is not measured | very high: roughly 1,000 distinct phrases, most of them mechanics new to the parser | upper bound measured, yield **unknown** (a judgment call: by the dropped-condition sample, perhaps 80% would find a leaf) | the multi-clause cards (310) and the long tail |

Overlap, so nothing is added: the annotation population (1,545 cards with a flagged ability) and the unreadable population (1,231) share 169 cards; the supplement and a Rust patch both act on the unreadable 1,231, so they overlap almost completely.
**Recommend the annotation, not the supplement.** The supplement's own stop rule is met many times over and its families are mostly new mechanics. The annotation moves roughly 40 times as many cards as the supplement's best case, needs no new node shapes, and is honest if it shows the condition. A Rust patch is the only way to read the unread phrases at all and belongs with whoever owns the parser.
