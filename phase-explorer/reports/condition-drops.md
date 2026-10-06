# Silent condition drops -- corpus-wide sizing

Detection and sizing only (KNOWN_LIMITATIONS.md section 4). Detector: `src/detect_condition_drops.py`; classifier: `src/size_condition_drops.py`; raw hits: `build/condition_drops.json`.

## Headline

| measure | value |
|---|---:|
| flagged items | **2,861** (tier A 2,771, tier B 90) |
| distinct cards (oracle ids) | **2,785** |
| ...of which fully `clean` by every existing signal (invisible) | **1,889** |
| ...of which already carry a visible gap/flag elsewhere | 896 |
| cards that are Alchemy `A-` rebalances only | 22 |
| cards from the collision-recovered overlay | 19 |
| cards excluding `A-` | 2,763 (silent 1,873) |

By bucket (items): triggers 1,349, abilities 1,189, static_abilities 188, replacements 135

## Sub-shapes, ranked by cards

| rank | sub-shape | items | cards | silent cards | sole-cause (silent) | sole-shape |
|---:|---|---:|---:|---:|---:|---:|
| 1 | sequential-chain | 1,055 | 1,046 | 611 | 607 | 1,024 |
| 2 | trigger-intervening | 585 | 568 | 436 | 429 | 556 |
| 3 | result-dependent | 435 | 433 | 276 | 269 | 423 |
| 4 | embedded-replacement | 200 | 195 | 108 | 103 | 187 |
| 5 | static-level | 188 | 184 | 169 | 165 | 175 |
| 6 | replacement-level | 135 | 135 | 126 | 126 | 133 |
| 7 | compound | 98 | 98 | 69 | 68 | 93 |
| 8 | negative | 92 | 92 | 64 | 64 | 90 |
| 9 | filter-targeting | 51 | 49 | 39 | 39 | 48 |
| 10 | activation-restriction-missing | 11 | 11 | 0 | 0 | 10 |
| 11 | branch-structural | 11 | 11 | 5 | 5 | 9 |

## Sub-shape detail

### sequential-chain

| variant | items | cards | silent cards | sole-cause |
|---|---:|---:|---:|---:|
| later sentence 'If X, B.' | 644 | 638 | 382 | 380 |
| inline 'A if X.' | 269 | 266 | 148 | 146 |
| if ... instead | 142 | 142 | 81 | 81 |

Examples (silent): Abzan Beastmaster, Accumulate Wisdom, Agency Coroner, Aggression, Ajani's Chosen, Ajani, Nacatl Avenger

### trigger-intervening

| variant | items | cards | silent cards | sole-cause |
|---|---:|---:|---:|---:|
| intervening if | 585 | 568 | 436 | 429 |

Examples (silent): 17-Year Cicadas, Adrenaline Jockey, Aerial Surveyor, Agent of Treachery, Aggressive Detective, Air Nomad Student

### result-dependent

| variant | items | cards | silent cards | sole-cause |
|---|---:|---:|---:|---:|
| this way / if you do | 333 | 331 | 202 | 197 |
| search this way -> shuffle (benign) | 55 | 55 | 44 | 42 |
| if you win/lose | 47 | 47 | 30 | 30 |

Examples (silent): Acolyte Hybrid, Adder-Staff Boggart, Aether Rift, Ajani's Aid, Angrath's Fury, Anowon, the Ruin Thief

### embedded-replacement

| variant | items | cards | silent cards | sole-cause |
|---|---:|---:|---:|---:|
| 'if X would Y, Z instead' inside an ability | 200 | 195 | 108 | 103 |

Examples (silent): Agate Assault, Anger of the Gods, Annihilating Fire, Arcane Heist, Betrayer's Bargain, Bleed Dry

### static-level

| variant | items | cards | silent cards | sole-cause |
|---|---:|---:|---:|---:|
| ReduceCost | 79 | 79 | 77 | 75 |
| Panharmonicon | 35 | 35 | 30 | 29 |
| CastWithFlash | 21 | 21 | 20 | 20 |
| GraveyardCastPermission | 14 | 14 | 14 | 14 |
| Continuous | 15 | 13 | 9 | 9 |
| CantAttack | 8 | 8 | 8 | 6 |
| CantBlock | 4 | 4 | 3 | 1 |
| CantBeCountered | 3 | 3 | 3 | 2 |
| RaiseCost | 3 | 3 | 3 | 3 |
| CantAttackOrBlock | 2 | 2 | 1 | 1 |
| CantUntap | 1 | 1 | 1 | 1 |
| MayChooseNotToUntap | 1 | 1 | 0 | 0 |
| MustBeBlocked | 1 | 1 | 1 | 1 |
| Other | 1 | 1 | 1 | 1 |

Examples (silent): Ajani's Response, Ancient Greenwarden, Animist's Might, Annie Joins Up, Armor of Thorns, Assassin's Ink

### replacement-level

| variant | items | cards | silent cards | sole-cause |
|---|---:|---:|---:|---:|
| enters tapped / with counters if | 100 | 100 | 94 | 94 |
| damage prevention / modification | 24 | 24 | 23 | 23 |
| other replacement | 11 | 11 | 9 | 9 |

Examples (silent): Acolyte's Reward, Ancient Amphitheater, Apocalypse Hydra, Ardenvale Paladin, Ascendant Packleader, Auntie's Hovel

### compound

| variant | items | cards | silent cards | sole-cause |
|---|---:|---:|---:|---:|
| two conditions joined by or / and | 98 | 98 | 69 | 68 |

Examples (silent): Alpharael, Stonechosen, Archfiend's Vessel, Armored Kincaller, Axavar, Fate Thief, Banishing Slash, Barrin's Unmaking

### negative

| variant | items | cards | silent cards | sole-cause |
|---|---:|---:|---:|---:|
| declined option ('may/pay ... if you don't') | 56 | 56 | 37 | 37 |
| negated event/state ('if you didn't ...') | 36 | 36 | 27 | 27 |

Examples (silent): Adventure Awaits, Ainok Wayfarer, Airlift Chaplain, Baral and Kari Zev, Blanchwood Prowler, Blossom Prancer

### filter-targeting

| variant | items | cards | silent cards | sole-cause |
|---|---:|---:|---:|---:|
| restriction on the target ('X target Y if it ...') | 51 | 49 | 39 | 39 |

Examples (silent): Agadeem Occultist, Ancient Animus, Burnout, Corrupted Resolve, Deathbringer Liege, Desperate Plea

### activation-restriction-missing

| variant | items | cards | silent cards | sole-cause |
|---|---:|---:|---:|---:|
| 'Activate only if' with no restriction at all | 11 | 11 | 0 | 0 |

Examples (silent): 

### branch-structural

| variant | items | cards | silent cards | sole-cause |
|---|---:|---:|---:|---:|
| FlipCoin sub_ability outside the branch | 11 | 11 | 5 | 5 |

Examples (silent): Goblin Archaeologist, Invert Polarity, Krark, the Thumbless, Mijae Djinn, Sorcerer's Strongbox

## Validation against the original 50-card spot-check

The 50 sampled items (`cond_sample.json`): detector flags **27** and clears **23**; section 4 recorded 28 real / 22 false positive. Of the 27 flagged, **19 silent** (card shows `clean`) and **8 with a visible gap elsewhere** (section 4: 20 / 8).

Stricter silent (also no soft-gap/unmodelled node, no correction): 1,823 cards.

## Round 1 -- nested-wrapper: a VISIBILITY fix, not a resolution

`parse_restriction_condition` returns `None` for any restriction text outside its closed vocabulary and the engine evaluates `None` as permissive-true; the `RequiresCondition` wrapper was built regardless, so the condition text was discarded. The fix (overlay `data/overlay/unrecognized-restriction-fix.json`, new `ParsedCondition::Unrecognized { text }`, evaluated `true` exactly like the `None` it replaces) keeps the real text. **Zero cards are newly parsed**; nothing about gameplay evaluation changes.

| nested-wrapper, same detector | before | after |
|---|---:|---:|
| flagged items | 57 | 0 |
| cards | 57 | 0 |
| silent cards (`clean` label) | 46 | 0 |
| sole-cause silent cards | 46 | 0 |
| whole corpus, flagged items | 2918 | 2861 |
| whole corpus, flagged cards | 2839 | 2785 |

The overlay carries **133 cards / 134 condition nodes** (100 activation, 6 casting restriction, 28 casting option -- the last two are call sites of the same function found during implementation; the sizing's 79 covered only the activation ones the detector could see). The gate compared 34,503 entries against the snapshot with the two earlier parser-fix overlays applied: 34,311 byte-identical, 192 rerun-flagged, of which 59 were metadata-restoration artifacts identical after regeneration and 133 cards carry the change. Every shipped difference is `null/absent -> {type: Unrecognized, text}` at exactly those nodes.

Residuals, stated plainly: (1) the 77 cards here are the 79 of the sizing round minus Gate to the Afterlife and Isolated Watchtower, whose first unsatisfied clause is a separate body clause ("if you search your library this way", "if a basic land card is revealed this way") and are now classified by it -- they were never only a wrapper problem. (2) After the fix, 74 of the 77 stop flagging at all; 3 keep a separate, real drop that the null wrapper had been hiding from the classifier: Izzet Generatorium and Ojer Taq (embedded replacement) and Sarevok's Tome ("...instead"). (3) To make that visible the detector now lets a restriction sentence back only its own `only if` clause (family RESTR) instead of masking every other clause of the ability; on identical data that unmasks 2 items elsewhere (2,936 -> 2,938), and the 50-card baseline is unchanged (28 flagged / 22 cleared, 20 silent / 8 visible).

Worklist for round B (real phrase parsers): `reports/restriction-condition-worklist.md`.

## Round B1 -- timing clause split out of compound activation restrictions

Round 1 left every unparsed "Activate only ..." sentence as one `Unrecognized` string. For compound sentences ("as a sorcery and only if ...", "during your upkeep and only if ...", "once each turn and only if ...") the leading clause is a phrase the parser already knows. The generic `activate only ` branch now splits on ` and only ` / `, and only ` / `, only `, emits `AsSorcery`, `DuringYourTurn`, `DuringYourUpkeep`, `DuringCombat`, `OnlyOnceEachTurn`, `OnlyOnce` for exact matches, and keeps every other piece verbatim as `Unrecognized` (the remainder is deliberately NOT run through the condition parser; see below). A sentence with no recognised timing piece is left exactly as it was.

| of the 40 timing-prefix blobs found after round 1 | cards |
|---|---:|
| timing extracted, nothing left over (fully resolved) | 2 |
| timing extracted, `Unrecognized` remainder kept | 20 |
| unchanged: timing phrase with no equivalent variant yet | 18 |
| **total** | 40 |

(Grizzled Wolverine is in the second row and also keeps a leftover "during the declare blockers step" piece, which is why the worklist counts 19 timing-phrase texts still unrecognized.)

**This one changes gameplay.** The engine enforces those timing variants; the `Unrecognized` remainder is still permissive. Engine tests parse the real Oracle text and run it through the activation gate: Cabal Inquisitor is refused in Upkeep, Beginning of Combat, Declare Blockers and End steps and during the opponent's main phase and allowed in its owner's main phase; an upkeep-only ability is refused outside the upkeep; `OnlyOnceEachTurn` blocks a second activation; "once and only during your turn" enforces both halves (4,479 engine tests pass).

Gate: 34,497 entries compared against the snapshot with the three earlier parser-fix overlays applied. 34,279 byte-identical in generator key order, 16 after restoring the April metadata, 180 earlier-overlay faces identical under a canonical (sorted-key) comparison, and exactly 22 different -- the declared set of 22 cards, computed beforehand by an independent re-implementation of the split rule. Every difference is an `activation_restrictions` list that was one `Unrecognized` blob and is now a lossless split (each piece's text occurs in the old blob), plus `sorcery_speed: false -> true` on the 6 `AsSorcery` abilities. The comparison itself was audited: two comparators agree, the compared bytes are hashed on both sides, and a planted one-field mutation is detected. (That audit also corrected round 1's account: the "59 metadata-restoration artifacts" were earlier-overlay faces whose bytes differ only in key order, not in content.)

Detector: flagged items 2,861 / cards 2,785 before and after, as expected -- an extracted timing restriction is not a condition drop, and the remainder is still represented.

Two findings that shaped the scope. (1) Live-checking showed that sending remainders through the existing condition parser gives two cards a wrong, now-enforced meaning (Urza's Fun House's three-land clause and Goblin Ski Patrol's "snow Mountain" each become one made-up subtype that nothing can satisfy, so the abilities would become unusable); remainders therefore stay `Unrecognized`. (2) Seven remainders do parse correctly with the existing parser (Cabal Inquisitor's seven graveyard cards, Chronatog Totem, Gutterbones, Kuldotha Phoenix, Coffin Puppets, ...) and are a cheap later win once the misparses are fixed.

## Reach limits (what this detector cannot see)

- Only conditions written as `if` in an item's own `description` (49,017 items). `as long as`, `unless`, `only during` and similar are not examined.
- Items with no `description` are read through modal `mode_descriptions` when aligned; otherwise skipped (about 3,000 abilities, mostly keyword-generated).
- Card-level fields (`casting_restrictions`, `casting_options`, `additional_cost`) are not searched, and a whole oracle line missing from every item is invisible here: 272 entries (222 `clean`) have more `if` clauses in the oracle text than in all item descriptions (mostly Cast-only-if / alternative-cost / Saga / Raid lines). Unaudited, not counted above.
- Tier A needs a clause family with zero evidence; tier B (89 items) is a family with fewer condition nodes than clauses. Two different conditions where only one is dropped and the surviving node is of the same family can still be missed.
- Sub-shape is assigned by text pattern on the first unsatisfied clause; boundaries (compound vs sequential, filter-targeting) are heuristic.
