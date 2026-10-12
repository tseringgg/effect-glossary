# False dropped-condition flags, and the next tentative promotions (design, before building)

Investigation and design only: nothing is built, placed or changed; nothing is committed. Scripts: `src/probe_false_flags.py`, `src/probe_promotions.py`. Data: `build/false_flag_*.json`, `build/promotion_*.json`.
**Measured** = counted from the build or read by me; **estimate** = a judgment call is stated.

## Part A. How many dropped-condition flags are false (read-only; the detector and the holds are untouched)

**Population.** Abilities held by the detector on cards still in "Not yet organized" (not placed, not tentative): **1,606 abilities on 1,545 cards**.
By sub-shape: sequential-chain 633, trigger-intervening 312, result-dependent 278, embedded-replacement 120, negative 58, compound 51, replacement-level 50, static-level 50, filter-targeting 39, branch-structural 10, activation-restriction-missing 5.

**Draw.** Seed 20261023, declared before computing. 100 abilities, one per card, stratified by sub-shape in proportion to size (largest remainder), taken in seed order within each sub-shape; none hand-picked, no redraw.
No ability had to be skipped for missing text and no card repeated. activation-restriction-missing (5 abilities) got a quota of 0 by proportion.

**Judging.** For each ability I read the card's full oracle text, the parsed structure of the flagged item and a list of the card's other items, and wrote a verdict to `build/false_flag_reads.json` **before** the detector's evidence (sub-shape, the "if" clauses, the missing families) was looked at.
Real drop = a condition in the text is not represented in the structure (or is stored as the opposite). False flag = the structure is correct. Unclear = the part that carries the condition is an Unimplemented placeholder, so there is no structure to compare.

| Sub-shape | Population | Drawn | Real drop | Unclear | False flag |
|---|---|---|---|---|---|
| sequential-chain | 633 | 39 | 31 | 7 | 1 |
| trigger-intervening | 312 | 19 | 15 | 4 | 0 |
| result-dependent | 278 | 17 | 16 | 1 | 0 |
| embedded-replacement | 120 | 8 | 6 | 2 | 0 |
| negative | 58 | 4 | 3 | 1 | 0 |
| compound | 51 | 3 | 3 | 0 | 0 |
| replacement-level | 50 | 3 | 3 | 0 | 0 |
| static-level | 50 | 3 | 3 | 0 | 0 |
| filter-targeting | 39 | 3 | 3 | 0 | 0 |
| branch-structural | 10 | 1 | 1 | 0 | 0 |
| activation-restriction-missing | 5 | 0 | 0 | 0 | 0 |

**Overall: 84 real drops, 15 unclear, 1 false flag.** The false-flag rate is **1%** (95% range 0.2% to 5.4%). **100 reads cannot show a rate**, and the per-sub-shape cells (1 to 39 reads) show nothing by themselves.
If every unclear read were counted as a false flag the rate would be 16%: that is the upper bound, and it is not what they are (see below).

* **The one false flag:** Chalice of Death (sequential-chain). The flagged ability's own text is "{T}: Target player loses 5 life." with no condition; the "if" the detector found belongs to the other face of this double-faced card.
* **The 15 unclear reads:** 14 of them carry the detector's unread-node marker (the flagged clause sits inside an Unimplemented node); the last has no structure to compare either. In the whole population 446 of the 1,606 flagged abilities also have an unread node. The flag there is the detector noticing that a condition has no structure: arguably correct, and already visible as an unread part.
* **What the real drops look like (84):** mostly an "if" or "if you do / don't / otherwise" clause stored as an unconditional sub-ability or trigger; several replacement idioms ("if it would die, exile it instead") stored as an unconditional exile; several intervening "if" clauses on a trigger that has no condition; and one clause stored as its opposite (Imprison). 5 of the 84 are the benign "if you search your library this way, shuffle" idiom: a condition is dropped but the effect is harmless.

**Comparison with the earlier 50-item result: that figure does not apply to the detector.** The 44% false in KNOWN_LIMITATIONS section 4 was the false-positive rate of the old quick heuristic (4,889 candidates); the detector was built to clear those: on the same 50 it flagged 27 and cleared 23
(reports/condition-drops.md). My last report wrongly quoted the 44% as the detector's rate and built a lever on it; `remaining-breakdown.md` now carries a correction. The detector's flags are almost all real drops.

**Repeating false-flag reasons: none** (one false flag, so nothing repeats). The only repeating pattern is the 5 benign shuffle drops, which the detector already labels "search this way -> shuffle (benign)" (39 abilities in the population).
A detector change could lift those 39 (a policy choice, not a correction) and the other-face case (the count of that case is not obtainable without changing the detector).

**Estimate of what lifting would release (estimate; marked as such).**

| If the detector lifted... | Abilities | Cards | Would match an unflagged leaf | a broad leaf | a promotable loose group | Could not match (no usable signature) |
|---|---|---|---|---|---|---|
| its false flags at the sampled rate (1%, range 0.2-5.4%) | about 16 (3 to 87) | about 15 (3 to 83) | about 9 | about 3 | about 1 | about 2 |
| the benign shuffle sub-variant (policy; measured counts, not a rate) | 39 | 39 | 28 | 3 | 2 | 6 |
| every flag whose item also has an unread node (not a false-flag fix; for comparison) | 446 | 434 | 155 | 49 | 23 | 206 |

The first row scales the whole population (1,606 abilities: 937 would match an unflagged leaf, 301 a broad leaf, 103 a promotable group, 217 have no usable signature) by the sampled rate; it is an estimate resting on one false flag in 100.
The matching assumes the signature is unchanged. **Conclusion: lifting false flags would move almost nothing; the dropped-condition hold is almost entirely real drops, so it is a representation or parser problem.**

## Part B. Promotion of the renamed groups and the qualifying sub-headings (names and counts before building)

### Candidates
* **3 groups that need only a rename** (held last round for "the name does not state the effect"): 54 remaining cards.
* **30 catch-all sub-headings that qualified** under the existing rule (at least 5 eligible cards, name states the effect, not incoherent, at most half text-less): 177 remaining cards. The 3 that failed the rule on the name are not candidates.
* The two sets do not overlap: **231 cards would leave "Not yet organized"** (measured sizes). A card already tentative is not counted again: its membership in a new group is added, its place in the count is not.

### The re-read of the 2 sub-headings that read as loose (seed 20261024, set first; 8 members each, read before the names)
* "adds a creature type": loose again, and half the members add a **land** type (Forest, Swamp, Mountain/Forest/Plains) and some also set base power and toughness. As named ("adds a creature type") it would mislead, so **it stays in only under the corrected wording "adds a creature or land type"**; if that wording were refused it would be held.
* "gives flying" (5 members, all of them): coherent enough, flying plus other changes. **Stays in.**
* Nothing read as incoherent, so no sub-heading is held.

### How sub-headings become tentative groups, and how a card is counted once
A sub-heading is today a heading inside a catch-all or a "Less common effects" bucket; the catch-all and the buckets themselves are not promoted and stay as they are in the loose layer. A promoted sub-heading becomes **a tentative group of its own**
(id from its parent group and heading), holding every card that has an eligible ability under that heading (same eligibility as before: not held for a dropped condition, has text, not a gap-test failure). It is named from fixed wording: a catch-all heading under
"Continuous effect on other kinds of target: ..." (the Destroy one reads "Destroy a permanent"); a bucket heading keeps its own effect wording ("Connive", "Goad a creature", ...), with ", uncommon cases" added where the name would repeat an existing group's.
The cards stay members of the catch-all or bucket in the loose layer. A card is counted once however many tentative groups hold it (the tentative card count is a set); the pile count falls only by the cards that were not tentative before.
Same method (`loose_tentative`), badge, wording and `TENTATIVE_LAYER` switch as the existing layer; the new groups sit in the same "Tentative groups" row of their family.

### The names (33): the 3 renames and the 30 sub-heading groups
Renames use the existing fixed wording per field value, with one new wording each: "a combat effect like can't block or can't be blocked" for the static-mode grant (the group before was "a different rule"), "gets or has something as long as something is true" for a continuous effect with nothing recorded.

| Kind | Family | Was | New name | Eligible cards |
|---|---|---|---|---|
| renamed group | Pump / grant | Give things a different rule, other kinds of target | Give things a combat effect like can't block or can't be blocked, other kinds of target | 5 |
| renamed group | Static: continuous | Continuous effect on this permanent | This permanent gets or has something as long as something is true | 39 |
| renamed group | Pump / grant | Give a creature a different rule | Give a creature an effect like can't attack, can't block or can't be blocked | 12 |
| sub-heading | Static: continuous | adds a card type | Continuous effect on other kinds of target: adds a card type | 8 |
| sub-heading | Static: continuous | adds a creature type | Continuous effect on other kinds of target: adds a creature or land type | 9 |
| sub-heading | Static: continuous | adds power by a count | Continuous effect on other kinds of target: adds power by a count | 6 |
| sub-heading | Static: continuous | gives deathtouch | Continuous effect on other kinds of target: gives deathtouch | 8 |
| sub-heading | Static: continuous | gives double strike | Continuous effect on other kinds of target: gives double strike | 7 |
| sub-heading | Static: continuous | gives first strike | Continuous effect on other kinds of target: gives first strike | 5 |
| sub-heading | Static: continuous | gives flying | Continuous effect on other kinds of target: gives flying | 5 |
| sub-heading | Static: continuous | gives hexproof | Continuous effect on other kinds of target: gives hexproof | 8 |
| sub-heading | Static: continuous | gives menace | Continuous effect on other kinds of target: gives menace | 8 |
| sub-heading | Destroy | permanent | Destroy a permanent | 5 |
| sub-heading | Attach | Attach, uncommon cases | Attach, uncommon cases | 9 |
| sub-heading | Card draw | Connive | Connive | 8 |
| sub-heading | Card draw | Draw cards, uncommon cases | Draw cards, uncommon cases | 5 |
| sub-heading | Combat | Goad a creature | Goad a creature | 8 |
| sub-heading | Counters | Double counters | Double counters | 6 |
| sub-heading | Counters | Give a player counters | Give a player counters | 6 |
| sub-heading | Counters | Move counters | Move counters | 7 |
| sub-heading | Game / player | Take an extra turn | Take an extra turn | 5 |
| sub-heading | Library | Reveal cards until a match | Reveal cards until a match, uncommon cases | 6 |
| sub-heading | Life | Gain life | Gain life | 6 |
| sub-heading | Life | Set a life total | Set a life total | 8 |
| sub-heading | Pump / grant | Double power and toughness | Double power and toughness | 5 |
| sub-heading | Static: cost change | Spells cost more | Spells cost more | 7 |
| sub-heading | Static: other rule | Cast from hand without paying | Cast from hand without paying | 5 |
| sub-heading | Static: other rule | Has shroud | Has shroud | 5 |
| sub-heading | Static: restriction | Can attack despite defender | Can attack as though it didn't have defender | 9 |
| sub-heading | Static: restriction | Can't enter the battlefield from a zone | Can't enter the battlefield from a zone | 5 |
| sub-heading | Static: restriction | Doesn't untap | Doesn't untap | 7 |
| sub-heading | Static: restriction | Spells can't be cast | Spells can't be cast | 9 |
| sub-heading | Tokens | Investigate | Investigate | 5 |

* Existing defect and claims checks over the 33 new names: **0 hard defects, 0 claims hits, 0 over 110 characters (longest 102); no duplicate and no clash with an existing group name.** (Getting there: three wording changes were needed after the first run flagged "condition", "despite" and an "attack" claim; one name that clashed with an existing group gained ", uncommon cases".)
* Hand check of 20 of the 33 names against their members (seed 20261025, set before drawing; members read and my own name written before the names were shown): **18 fine, 1 fine but imprecise, 1 misleading in part.** 20 names cannot show a rate.

| # | What I would call it (from the members) | New name | Verdict |
|---|---|---|---|
| 1 | has shroud | Has shroud | fine |
| 2 | double power (until end of turn) | Double power and toughness | fine |
| 3 | spells can't be cast | Spells can't be cast | fine |
| 4 | has double strike, usually conditional | Continuous effect on other kinds of target: gives double strike | fine |
| 5 | has deathtouch, usually conditional | Continuous effect on other kinds of target: gives deathtouch | fine |
| 6 | reveal cards from the top until a match | Reveal cards until a match, uncommon cases | fine |
| 7 | a life total or power becomes a set value | Set a life total | fine |
| 8 | players get rad counters | Give a player counters | fine |
| 9 | connive | Connive | fine |
| 10 | can't attack / can't block / can't be blocked this turn | Give a creature an effect like can't attack, can't block or can't be blocked | fine |
| 11 | attach Equipment or Auras | Attach, uncommon cases | fine |
| 12 | has menace, usually conditional | Continuous effect on other kinds of target: gives menace | fine |
| 13 | permanents become other land or creature types, sometimes with base power/toughness | Continuous effect on other kinds of target: adds a creature or land type | fine |
| 14 | take an extra turn | Take an extra turn | fine |
| 15 | this permanent or a paired creature gets or has something as long as a condition holds | This permanent gets or has something as long as something is true | fine, imprecise ('this permanent' is loose: some members apply to a paired or equipped creature) |
| 16 | has hexproof, usually conditional | Continuous effect on other kinds of target: gives hexproof | fine |
| 17 | permanents don't untap | Doesn't untap | fine |
| 18 | destroy a permanent (target or all of a kind) | Destroy a permanent | fine |
| 19 | double counters, life or mana | Double counters | misleads in part (2 of 6 members double life or mana, not counters) |
| 20 | each opponent or player draws a card | Draw cards, uncommon cases | fine |

The one name that misleads in part: "Double counters" (2 of 6 members double life or mana). It is the wording for that effect type and would be reworded before building (for example "Double counters, life or mana"); the imprecise one is "This permanent gets or has something as long as something is true" ("this permanent" is loose for members that apply to a paired or equipped creature).

### Counting (measured sizes; nothing here changes the precise or with-broad figures)
* Cards promoted: **231** (54 + 177). Tentative cards 1,867 -> **2,098**. Pile 3,726 -> **3,495**.
* Third figure: **29,688 of 33,183 = 89.5%** (basis: the broad figure, 27,590, plus 2,098 not-yet-organized cards with an eligible ability in a tentative group). Precise 24,336 = 73.3% and with-broad 27,590 = 83.1% unchanged.
* Reconciliation: 27,590 placed + 2,098 tentative + 3,495 unorganized + 5,738 not cards = 38,921.
* The unread-part flag (a build switch that turns off, alone, the placements that rest only on abilities with an unread part; default unchanged, on) will be reported with its figure after the build.

### Checks for the build (not run yet)
Two strata checked separately on seed 20261026 (20 placements from the renamed groups, 20 from the sub-headings; bar: more than 5 wrong overall turns the new promotions off, more than 3 of 20 in one stratum holds that stratum), archive and frozen-file hashes, two identical builds, reconciliation, and the headless Edge pass.
