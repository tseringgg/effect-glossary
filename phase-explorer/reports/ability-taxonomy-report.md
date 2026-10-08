# The per-ability taxonomy as the main view: results (round 3)

Built by `src/build_ability_taxonomy.py`; design in [ability-taxonomy-design.md](ability-taxonomy-design.md); the archived card-level view is in
`archive/card-level-view-2026-10/` (all 172 archived files re-hash to their Part 1 values). Nothing is committed. No Scryfall tag data is used in
signatures or placement.

**The headline figure here (67.8%) and the archived 74.8% are measured on different bases and are not comparable.**

| | archived card-level view | this view |
|---|---|---|
| what counts as grouped | a card is in exactly one cluster leaf, placed by closeness, by one ability, by keyword, "No abilities" or a replacement group | a card is grouped when at least one of its clean abilities sits in an **unflagged** group of 5 or more abilities, plus the keyword block, "No abilities" and the replacement groups |
| unit of a group | a card (blended vector of all its abilities) | one ability; a card appears under every group one of its abilities fits |
| groups where the parser lacks a field | counted | **kept out** of the headline (those cards are reported separately as "in a broad group only") |
| abilities flagged by the dropped-condition check | placed anyway | held back |
| gap-card abilities | 456 gap cards placed by one ability | held out entirely |
| result | 26,085 of 34,864 = 74.8% | **23,653 of 34,864 = 67.8%**; **26,774 = 76.8%** counting broad-group-only cards |

Do not subtract one from the other. The 7-point difference comes from what is allowed to count (the last three rows above), not from groups being lost; the second figure (76.8%) is the nearest to the old way of counting.

## 1. This round: sign and recipient go into the signature

**The measurement you asked for, before changing anything.** For each field, how often the parse records it for the members of the leaves flagged for it
(`src/measure_field_presence.py`, `build/ability_taxonomy_field_presence.json`):

| field | present in the parse | decision |
|---|---|---|
| sign of a power/toughness change | **91%** of the 4,474 members of the sign-flagged leaves (4,070; the other 404 depend on a count or a reference). By class: boost 3,467, shrink 496, mixed 107, undecidable 404 | into the signature; a leaf is flagged only for the abilities whose sign is undecidable |
| who is damaged, `DamageEachPlayer` | **98.9%** (180 of 182 have a player filter: "opponent" or "each player") | into the signature; unflagged |
| who is damaged, `DamageAll` ("and each player") | **2.1%** (6 of 287) | stays flagged, for the abilities that lack it |
| who is damaged, `DealDamage` | a target node on 98.9%, but **31%** (88 of 281) have no type filter | stays flagged for those only |
| who loses or gains life | **89%** of all 1,421 lose/gain-life abilities (gain 98%, lose 77%) | already in the signature; the flagged leaf holds only the abilities that lack it: of its 130 members none has a player scope or player field, 83 have a target with no player kind, 47 have no target |
| who pays life (shocklands and similar) | not separately recorded: "pay 2 life" is read as a life-loss effect with no subject | stays flagged (same leaf) |

Two verb-bound fields, `sign` (boost / shrink / mixed / zero / unknown) and `recip` (opponents / each player), joined the signature and are never dropped by the backoff.
(A first build used "+" and "−" as the class symbols; "−" collided with the code's placeholder for "no value" and merged shrinks with abilities that have no sign. The comparison below caught it; the classes are now words.)

**What it did** (comparison with the build before this round, `build/ability_taxonomy_round3_compare.json`):

| | before | after |
|---|---:|---:|
| old leaves that split | | **42** (34 Pump and grant, 7 continuous statics, 1 damage), into **61** new leaves |
| leaves in total / of 5 or more abilities | 1,759 / 1,254 | 1,802 / 1,273 |
| new nodes that fell under 5 members | | 18 nodes; 30 abilities that had been placed are stranded in them (47 abilities in all went from placed to unplaced: 30 below the minimum, 14 rare verb parameter, 3 rare object) |
| abilities in the headline | 26,038 | **30,248** (+4,210: 4,190 moved out of a flagged group, 20 from unplaced) |
| flagged leaves / abilities in them | 300 / 10,247 | **165 / 6,010** |
| cards in the headline | 20,997 (60.2%) | **23,653 (67.8%)** |
| cards in a broad group only | 5,795 | 3,121 |
| headline + broad | 26,792 (76.8%) | **26,774 (76.8%)** (30 cards fell to not-yet-organized when their group split under 5; 12 came in) |

**Does the +N/+N versus −N/−N leaf separate cleanly?** Yes. Of the old 527-ability "A creature gets ±N/±N until end of turn" leaf, 265 are now in a "+N/+N" leaf, 196 in a "−N/−N" leaf, 15 in a "+N/−N or −N/+N" leaf and 61 in the
flagged unknown-sign leaf. Reading the sign out of each member's text: **boost leaves 3,337 of 3,338 agree (100%), shrink leaves 473 of 478 (99.0%), mixed leaves 94 of 94**. The flagged unknown-sign leaves are a genuine mix: of their 382
members with a readable sign, 325 are boosts, 54 are shrinks and 3 are mixed, which is why they stay flagged.

**Two name fixes**, as asked: the lure is now "All creatures able to block this creature must do so (like Lure)", and a duration is added to a name only for effects that carry their own (pump, grants, gain control, animate, prevent
damage, regenerate), so "Gain life until end of turn" is now "Gain life". `ledger.html` and `card-explorer.html` now carry a dev-only banner saying they show the archived view, and `browse.html` links to them only with `?dev=1`.

## 2. The view, in numbers

Universe 38,921 cards; 4,057 are not cards; **34,864 in scope**.

| state | cards |
|---|---:|
| placed by ability signature (headline) | 21,831 |
| keyword block (headline) | 1,262 |
| "No abilities" (headline) | 351 |
| replacement groups, old layer unchanged (headline) | 209 |
| **headline total** | **23,653 = 67.8% of 34,864** |
| in a broad group only (not headline) | 3,121 |
| **headline + broad = 26,774 = 76.8%** | |
| **Not yet organized** | **8,090** |
| not a card | 4,057 |

Not yet organized, by group: Parsed but with a gap 5,709; Parsed but too unusual to group 1,230; Parsed but part of its text may not have been read 1,086; No effect to group 28; Not parsed yet 29; Known parse mistake 8.
Reconciliation: 21,831 + 1,262 + 351 + 209 + 3,121 + 8,090 + 4,057 = 38,921, and the other seven checks in `build/ability_taxonomy.json` pass (every placed card has a placed ability; no unorganized card has one; broad-only cards have
only broad abilities; leaf members equal card-leaf links; one state per ability; group sizes sum to the unorganized count; the ability rows cover all 50,672 old-ledger rows). Two consecutive builds are byte-identical.

**Groups.** 28 families, 289 effect-and-verb nodes, 1,802 leaves of which 1,273 have 5 or more abilities. Sizes: 1 to 4: 529, 5 to 9: 542, 10 to 19: 353, 20 to 49: 247, 50 to 99: 77, 100 to 499: 45, 500 or more: 9. At the display
threshold of 10 the tree shows 731 leaves (626 unflagged, 105 flagged); the leaves of 5 to 9 sit in their parent. **Leaves flagged generic: 165.**

| what is not recorded | flagged leaves | abilities |
|---|---:|---:|
| who draws | 15 | 2,411 |
| what the effect applies to (object unresolved) | 66 | 1,518 |
| "all" vs "target" on return-to-hand | 50 | 1,195 |
| sign of the power/toughness change (undecidable counts) | 21 | 383 |
| where a self-return comes from | 7 | 344 |
| whether players are hit by an "all" damage effect | 10 | 266 |
| who loses or gains life | 3 | 126 |
| who is damaged (no recipient kept) | 2 | 83 |

(A leaf can carry more than one reason, so these overlap.)

**Abilities, over all 50,672 ability rows:** placed (headline) 30,248; placed in a flagged leaf 6,010; held out (gap cards: would place 1,720, would place in a broad group 312) 2,032; unplaced 12,983. Unplaced and held out, by reason:
item holds a gap node 5,976; flagged by the dropped-condition check 2,847; below minimum size 1,128; rare object 726; rare verb parameter 777; gap-card tests (no text 418, continuation 339, same line 105); replacement group 367; modal
placeholder 246 (placed through its modes); no signature 19; rare effect type 27; card not in scope 7; no family 1.

**Leaves per card:** a placed card is in 1.35 groups on average, at most 7 (18 cards are in five or more).

## 3. Hand checks, round 3: seed 20261010, set before computing, nothing redrawn

Each member or ability was read and judged from its text before its name or signature was shown. **None of these counts is a measured error rate.** The rules and bars are the earlier ones.

| check | n | result | bar | outcome |
|---|---:|---|---|---|
| leaf coherence | 30 leaves (10 finest, 10 middle, 10 coarsest; each with at least 8 members) | 23 coherent, 7 loose, **0 incoherent** | stop above 15% incoherent | passed |
| placed abilities | 40 | **40 right, 0 wrong** | stop above 5% wrong | passed |
| auto-names | 20 | **3 would mislead a tester**; 3 more are vague or garbled and not counted | none set | reported |
| leaves whose members could split by sign or recipient | 10 | **all 10 consistent** | | reported |

Skipped for having fewer than 8 members: 6 finest, 3 middle, 1 coarsest (listed in the draw file). Round 1's modal-mode check (39 of 40 right), its gap-card check (5.0% strict wrong) and round 2's "too unusual" check (the old view was right
for 13 of 20) are not re-run here. The round-3 draws came from the build just before one more edit (two flag-note wordings), which changes no leaf and no name.

- **Leaves.** The 7 loose: "destroy all creatures" where 3 of 8 destroy a filtered set; "exile all <something>" with different objects; shield counters where one card gives a perpetual one; "exile a card going to a graveyard" (instead-of
  replacements, exile on discard, an exile cost); blink versus exile-until-leaves; "grant an ability" mixing grants and tokens that have one; plain "draw a card" including a doubling replacement. None is incoherent.
- **Sign and recipient.** The three flagged unknown-sign leaves were each internally consistent in the sample (two all boosts, one all shrinks), so for them the flag is cautious; across all unknown leaves 14% of readable members are
  shrinks. "Deal damage to each player" (18 abilities) holds only abilities that hit each player; the old mix with "each opponent" is gone because the parse does record it.
- **A different split I did not expect, and did not flag.** Two leaves record the *triggering* player as the subject while the text says "you": "That player draws cards" (35 abilities: 32 read as "you draw", 9 name another player) and "That
  player gains life" (8 abilities: all 8 read as "you"). The field is present and wrong, not absent, so no flag applies, and their names are misleading for most members. Other "That player ..." leaves (discards, loses life, mills) match their text.
- **Names.** Misleading: "Creatures have an extra ability" for "Commander creatures you own have ..." (the commander restriction is in the signature but not the name); "Exile a card from your hand" for an alternative cost ("rather than pay
  this spell's mana cost"); "Return cards from a graveyard onto the battlefield" for "each player returns ..." (the symmetry is not in the name). Vague or garbled, not counted: "Exile cards (then change zone)" for blink, "Counter something" for
  countering an activated ability, "A permanent cant be blocked except by". Round 2's two misleading names are fixed.

## 4. Where this view is worse than the archived one

- **5,097 cards that were grouped in the old view are not in the headline now** (7,516 before this round): 2,912 are in broad groups only (still findable), 988 held back by the dropped-condition check, 737 too unusual, 457 gap cards, 3 no
  effect. The reverse: **2,665** cards that were unplaced before are placed now, and 209 more are in broad groups.
- **Old leaves that were coherent and now fragment.** 333 old leaves of 10 or more cards were coherent by the exact-token proxy used in the probes. For 11 the cause is flagging, not fragmentation (every card is in a flagged group). **78
  really fragment** (fewer than 30% of card pairs share a new group even counting broad ones): mostly the `TargetOnly` wrapper leaves (the old view grouped "choose a target" cards that this view splits by what they do), `ChangeZone` with a
  union target, and union-object Sacrifice leaves. The median coherent old leaf keeps 64% of its card pairs together counting broad groups (over all old leaves, headline groups only, 47%).
- **The names are weaker than the old leaf phrases in places.** They are generated, not quoted from card text. Known defects, not fixed so the name check stays valid: some object words are unfinished ("All triggeringsources get +N/+N",
  "A target gets +N/+N", "everything it names an opponent controls"); `(variant)` and `(other variants)` suffixes appear where two groups had the same name.

## 5. What was exercised in a browser, and what was not

`src/test_browse_browser.py` runs `reports/browse.html` (and the two dev pages) in headless Edge through its DevTools protocol, with real clicks and keystrokes. **21 checks, 0 failed.**

- **Exercised in a browser:** the page boots and shows both coverage figures with their bases and the snapshot line; clicking a family, a node and a leaf opens a card list in which each card shows the text of the ability that put it there;
  an "Also in" link opens another group; clicking a card name expands its rules text and abilities; an "Other: ..." roll-up lists small groups; a broad leaf shows its plain-language note; a "Not yet organized" group lists cards and "Show more"
  adds 150; typing a name into Find a card (real key events) shows the plain-language answer and its group link opens that group; the keyword and replacement blocks open to cards; a deep link opens a leaf directly; **a boost leaf and a
  shrink leaf open as separate, correctly named groups**; **the dev links are hidden by default and shown with `?dev=1`**; **`ledger.html` and `card-explorer.html` show the dev-only banner**. The archived pages also render with their
  banner and data.
- **Covered by logic tests only** (`src/test_abilityfind.py`, the same `abilityfind.js` the page loads, run in a JavaScript engine over the real data): every one of the 38,921 entries is found by its own name and every answer is non-empty;
  ordering (real cards before non-cards); the named lookups.
- **Not exercised anywhere:** small-screen layout, light/dark theme switching, scroll performance with the largest lists, and any browser other than Edge.

## 6. Still open

- **Parser work that would move cards into the headline:** who draws; "return all" vs "return target"; the source zone of a self-return; whether players are hit by "damage to all"; unresolved objects; who pays or loses life; and the
  triggering-player subject recorded where the text says "you". Dropped clauses (Death Cloud, Global Ruin, Spark Double) and static misreads are separate parse defects.
- **Gap-card abilities stay held out.** The bar was under 5%; the sample came to exactly 5.0% strict, so it is not met. Revisiting needs a fresh sample of about 100 on a new seed (KNOWN_LIMITATIONS §12).
- **Not built:** a new coverage-ledger page; fixes for the unfinished name words listed above; a flag or fix for the "that player" leaves.
- **Judgment calls this rests on:** my verdicts (single reader); the flag rules, which decide what is headline; "right" meaning the ability does what its group says, not everything it does; reading the 5.0% gap-card result strictly; the
  family map, wrapper and modal handling.
