# Condition annotations and the gap-test sample: Part 1 design and Part 2 sample (nothing built)

> Built on 2026-10-12: see `annotation-build.md`. Where the numbers differ, the build report is the current one (extractor fixes, the saga rule left out: gap-test stratum 160 new cards, 92.8%, not 92.9%).

Scripts (new, read-only): `src/probe_annotation.py`, `src/probe_annotation_extract.py`, `src/probe_annotation_verbs.py`, `src/probe_gaptest.py`. Data: `build/annotation_*.json`, `build/gaptest_*.json`. No existing file changed; nothing is committed.
Measured = counted from the data. Estimate = said so. "Read" = my hand read, written before the generator's answer was shown where it says so.

## Part 1a. Population (measured)
A candidate is an ability the detector holds for a dropped condition, with text. Route = where it would land if the condition were ignored (same machinery as the 2026-10 Part C probe: `assign_rf_ref`, leaf of 5 or more, else a promoted tentative group).
Held abilities exist only on cards in the pile: 1,673 held abilities, 4 with no text, **1,669 with text on 1,609 cards**.

| Route | Abilities | Cards (best route per card) |
|---|---|---|
| Unflagged leaf | 929 + 30 | 935 |
| Broad leaf | 299 + 18 | 302 |
| Tentative group | 102 + 9 | 104 |
| No leaf (not annotated) | 263 + 19 | |
| **With a route** | **1,387** | **1,341** (1,285 unorganized, 56 already tentative; none placed) |

Per sub-shape (abilities; route: unflagged / broad / tentative group / none): sequential-chain 650 (370/134/41/105), trigger-intervening 335 (177/86/32/40), result-dependent 287 (171/41/16/59), embedded-replacement 129 (53/28/6/42), negative 59 (28/12/10/9), static-level 54 (49/1/0/4), compound 52 (29/13/3/7), replacement-level 52 (42/1/1/8), filter-targeting 36 (30/1/2/3), branch-structural 10 (9/0/0/1), activation-restriction-missing 5 (1/0/0/4).

**Reading of "a leaf in a flagged generic group is not annotated" (needs your yes):** I took it to mean the broad leaves, so the broad route is **not annotated** (317 abilities, 302 cards). That gives the "about 1,000 cards" you expected; with the broad route it would be 1,341. Say if you meant something narrower.

| Step | Abilities | Cards (new from the pile / already tentative) |
|---|---|---|
| With a route | 1,387 | 1,341 (1,285 / 56) |
| minus the broad route | 1,070 | 1,040 (1,002 / 38) |
| minus no extractable clause (14) | 1,056 | 1,034 (996 / 38) |
| minus the cost/lead-in verb rule (below) | **1,018** | **998 (960 / 38)** |

## Part 1b. Condition-text extraction (measured counts; 20 read)
The item text in the data is cut at about 160 characters, so a first pass produced fragments ("if it's the first end st"). The extractor now takes the full ability from the oracle line the item starts (found for 1,376 of 1,387). Two more first-pass bugs were fixed after reading examples: an intervening "if X, Y" took Y with it; and "this way" outranked "if" when choosing the sentence.
Clause rule: a leading "If/Unless/As long as X," gives X; an inline "A if X" gives "if X" to the end of the sentence; an intervening "..., if X, Y" gives "if X" up to the comma; "if you do / when you do / if you don't" gets the sentence before it (37 abilities); otherwise the whole sentence; if no condition word exists in the text, nothing.
All 1,387 with a route: **clean clause 1,367, whole sentence 3, none 17.** Final population: clean 1,016, whole sentence 2. By sub-shape the 17 "none" are sequential-chain 10, trigger-intervening 4, embedded-replacement 2, result-dependent 1: **the text has no condition word at all** (5 of 5 read: "Target player sacrifices two attacking creatures", "Any number of target creatures you control phase out"...). Those are not annotated (a card cannot show a condition that is not in its text).
Read (seed 20261030, declared before the draw; 12 clean, 3 whole-sentence, 5 none; 2nd version of the extractor): **12 of 12 clean clauses quote a real condition correctly; 4 of them leave out a second branch** ("Otherwise...", "If you didn't..." in another sentence: Leeches, revealed card, top-card trick); 2 of 3 whole sentences are usable, 1 chose the wrong sentence (an "instead of putting it into your graveyard" clause rather than "Then if the exiled card doesn't have suspend"); the 5 "none" really contain no condition. The last tweak (preceding sentence for "if you do") came after this read and was not re-read.
Extractor limit, logged: it shows the first condition. 222 of the 1,018 have an inversion word in a different sentence than the clause shown.

## Part 1c. Cost and effect sharing a verb (Akuta, Born of Ash)
Rule scanned: the leaf's key verb (first non-generic verb of the leaf name) occurs in the activated cost or the text before the first "If you do / When you do / If you don't / Unless you" sentence, and **not** after it (past-participle references such as "the sacrificed creature's power" do not count as the effect). Akuta is caught.
Measured: 78 of 1,387 abilities match (39 on routes we would annotate). Read 20 of the first (looser, 70-match) version: **8 mis-filed** (the leaf names the optional lead-in or cost: Ultra Magnus puts a creature onto the battlefield but the effect is "convert"; Look at the top card, effect is "each player discards"; Energy paid, effect is counters; Sacrifice it, effect is the reveal chain), **2 loose**, 10 fine. So roughly 40% of the class is mis-filed: an estimate from 20.
**Proposed exclusion rule:** an ability matching the scan is not annotated. It also drops some right ones (the "may X, if you don't Y" abilities whose leaf is X and correct), accepted. Removes 38 abilities and 36 cards from the final population. A second read of 20 names found one more of this kind (Sacrifice another creature, whose effect is damage); the participle refinement now catches it.

## Part 1d. Inversion risk (measured; 16 read)
Of the 1,018: "instead" 184, "otherwise" 41, "unless" 19, "if you don't" 15, "if it doesn't / didn't" 10, "if you didn't / can't" 13 (an ability can have several): **270 contain an inversion word anywhere; 48 have it in the clause shown.** Read 16 of the 48 (seed 20261033, declared before the draw): 12 leaves are right (the counter-unless-pay family, "if it doesn't have suspend", "if you didn't put a card into your hand"), **2 are loose** (a pay-or-lose-the-creature upkeep trigger filed under "put counters"; "lose that much life, or sacrifice permanents" filed under "target player loses life"), 2 not clear. None need holding on this read; the shared-verb rule already removes the worst kind.
**Wording:** every row gets the sentence you chose. For the 270 add one more clause: "The condition may change what the ability does, or make it do something else instead." For the 48 whose shown clause is itself "unless / if you don't / if it doesn't": "The condition may change what the ability does, even to the opposite." Hold none; the rows are tentative and flagged. (A 16-of-48 read cannot show a rate.)

## Part 1e. Display (mock-up)
Tentative groups already get a striped italic badge; annotations get their own badge, **"Condition not read"**: a dotted outline with a small question mark, never striped, never solid, never dashed. It sits in the member row next to the leaf name.

```
Draw  >  Draw cards
  Rhino                                   [Condition not read]
  Whenever Rhino attacks, if you've cast a spell with mana value 4 or greater this turn, draw a card.
  This ability has a condition the tool did not read: "if you've cast a spell with mana value 4 or greater this turn".
  The condition may change what the ability does.
  Placed in: Draw cards (tentative, condition not read)
```
Find a card: the card shows a chip "Condition not read" beside its leaf chip, and the same sentence under the ability.
Phone width (estimate, no browser run yet): at 390 px (about 358 px of text, roughly 50 characters a line) the fixed sentence is 3 lines, the median clause (39 characters) adds 1, the ability text 1-4: **about 5-8 lines a row**; the longest clause (239 characters) adds 5. I will measure in headless Edge at 390 px in Part 4 and report the real figure.

## Part 1f. Counting (the fourth figure)
| Figure | Cards | % of 33,183 | Basis |
|---|---|---|---|
| Precise | 24,336 | 73.3% | unchanged |
| With broad | 27,590 | 83.1% | unchanged |
| With tentative | 29,683 | 89.5% | unchanged (+2,093) |
| **With tentative plus annotation** | **30,643** | **92.3%** | the tentative figure plus 960 pile cards that have an annotated ability and no tentative placement |

Annotated cards in all 998: **960 leave the pile; 38 were already tentative** (they gain the badge row, no extra count). Pile 3,500 -> **2,540**. Reconciliation: 27,590 + 2,093 + 960 + 2,540 + 5,738 = **38,921**. No existing status is renamed; "tentatively placed" keeps its meaning; the new status reads "placed with a condition not read".
If the gap-test stratum passes and is added (below): about 180 more cards (estimate), 30,823 = 92.9%, pile about 2,360.

## Part 1g. Names and wording
No new groups are made (annotations reuse leaf and tentative-group names that already passed the checks). New wording: the badge **"Condition not read"**, the fixed sentence, the two inversion clauses, the checkbox **"Show condition annotations"**, and the status "placed with a condition not read".
The existing defect scan over these strings: no hard defect (no double space, code words, dangling ends); the sentence with the opposite clause is 127 characters (the 110 limit is for names, not sentences). The vocabulary check flags the interface words *condition, tool, annotations, opposite, placed, what, did* as "not in any card text"; they are interface words, not names, so I would add them to the allow list for interface strings only.
20-name hand check (seed 20261032, declared before the draw; leaf name read against the ability, condition ignored): **16 fit, 2 loose** (an opponent-reveals-hand leaf for a reveal-then-exile ability; "Flip a coin" for a coin-flip with different branches), **1 awkward but accurate** ("Deal damage to a creature, then deal damage to it"), **1 mis-filed** (Sacrifice another creature, whose effect is damage; the participle refinement now excludes it).

## Part 2. Gap-test sample (measurement only)
**Seed 20261028, declared in `src/probe_gaptest.py` before any computation.** The 329 in your brief are cards (continuation 153, same-line 64, no text 112): 218 cards remain without the no-text ones (continuation 153, same-line 65; a card with both counts once, as continuation). **The third stratum in the brief, "item gap", has no cards in this population**: every such card also carries a no-text or continuation failure, so it is empty. I drew in proportion: 28 continuation, 12 same-line, one ability per card, no redraw. Ability text and the card's unread parts were shown, my read ("what leaf I expect", "could the unread part change the leaf") written to `build/gaptest_reads.json` before the leaf was shown, then revealed.
**Result: 33 right, 5 loose, 1 wrong, 1 with no leaf (of 40).** Continuation: 23 right, 4 loose, 1 no leaf; same-line: 10 right, 1 loose, 1 wrong. The wrong one: "Target creature gains all creature types" filed under "A creature gains a keyword". Loose: three abilities whose own text carries a restriction the leaf drops (spend-only-on-instants, noncreature-only, chosen colors), one "enters with counters" under "put counters", one that also mills.
**Could the unread part change the leaf? 0 of 40**: in every case the unread clause was a different ability of the card (a chapter, a second trigger, a leveler tier), not part of the ability read.
**Bar (more than 2 wrong of 40 means do not add them): 1 wrong, so it passes.** 40 cannot show a rate (1 of 40 wrong has a 95% range of about 0.4-13%), and the reads are not independent of the generator.
Cards a gap-test stratum would add (estimate, using each card's best route): 180 (123 continuation, 57 same-line); 28 on a broad leaf and 10 with no leaf are left out, matching the broad rule above.

## Decisions I need before Part 3
1. The broad route not annotated (998 cards), or annotated (up to 1,341)?
2. The shared-verb exclusion as proposed (removes 38 abilities, 36 cards)?
3. The two inversion clauses, and the badge name "Condition not read"?
4. The gap-test stratum: add behind its own flag (it passed 1 of 40 wrong), or leave out?
