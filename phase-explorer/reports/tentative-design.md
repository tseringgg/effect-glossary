# Tentative placements: minimum-of-3 probe and promotion design

Investigation and design only. Nothing is built, placed or changed; nothing is committed. Files: `src/probe_min3_leaves.py`, `src/probe_tentative.py`, `build/min3_probe*.json`, `build/tentative_probe*.json`. All numbers are **measured** unless marked *estimate*.
Frozen files and the archive were hash-checked before and after (see the end).

## Part 1. Minimum of 3 for the finest signature level

**Method.** The same rarest-field-first backoff (`assign_rf_ref`) with a minimum of 3 over the same clean abilities; the main tree's 5-member leaves are untouched. A pile ability counts as gaining a leaf only if it lands in a leaf
that has exactly 3 or 4 members when formed (a leaf of 5 or more is already a main-tree leaf; a key whose count reaches 3 but whose formed leaf has fewer than 3 members is not a leaf).

| | |
|---|---|
| Usable pile abilities | 4,979 |
| Land in a new leaf of 3 or 4 | 608 |
| ...in a leaf of 5 or more already (held for other reasons) | 3,132 |
| ...no leaf even at 3 / leaf formed with fewer than 3 | 773 / 466 |
| Removed as not eligible: held for a dropped condition / no ability text | 81 / 16 |
| **Eligible abilities in new 3-4 leaves** | **511** (rare shape 398, unread part 94, gap test 19) |
| New leaves of 3 or 4 members (all) / with an eligible pile ability | 714 / 227 (134 of 3 members, 93 of 4) |
| Abilities in those 227 leaves (all members) | 774 |
| **Pile cards that gain a leaf** | **494** |
| ...by cause (v3, primary) | below the 5-member minimum 351; parser gap 131; dropped-condition hold 12 |
| ...by pile group | too unusual 363; gap 131 |
| Already have a loose group (so not new reach) | **494 of 494** (in the couldn't-read list: 0) |

(The v3 breakdown counted 814 abilities / 792 cards "placing at 3": that counted keys whose count reaches 3; this probe counts leaves that actually form with 3 or more members, and drops held abilities.)

**Coherence hand check.** Seed 20261019, set before computing; pool 227 leaves of 3-4 members with an eligible pile ability; 30 drawn (none by hand, no redraw); member texts read first, reads in `build/min3_probe_reads.json`
before the signature was shown. Result: **0 incoherent, 23 coherent, 7 loose.** The bar (more than 15% incoherent: do not recommend) is not tripped. 30 leaves cannot show a rate, and a leaf of 3 abilities is a thin basis for any claim.

**Old view.** Of the 494 gaining cards, 363 are in "Parsed, but too unusual to group". The old card-level view had placed 200 of those 363 (194 clustered, 5 nearby, 1 placed by one ability) and left 163 unorganized. A hand check of 20 of the 200
(same seed, drawn after the 30 leaves; each judged from the ability text against the old cluster's effect type and top phrases): **16 right, 4 wrong** (against the earlier estimate of about 13 of 20). 20 cards cannot show a rate.

**Reading.** The 3-4 leaves are coherent, but every card they reach already has a loose group, and 377 of the 494 are also reached by the promoted loose groups below. They are a tighter alternative for the same cards, not new reach.
Recommendation: do not build `min3_tentative` in this round; keep it as an option (method name reserved).

## Part 2. Promotion of loose groups to tentative placements

### Rule
Candidates are the plain loose groups only (195): not the two catch-alls and not the 23 "Less common effects, by kind" buckets. A member ability is eligible only if it is not held for a dropped condition and has ability text.
A group is promoted if (1) my blind read of up to 8 eligible members is coherent or loose, not incoherent; (2) its key (name) states the effect; (3) it has at least 5 eligible cards (the main tree's minimum, applied to eligible cards);
(4) at most half of its cards are text-less. Reads were written to `build/tentative_probe_reads.json` (seed 20261021 chose the members) before any name was shown.

### Result
* Candidates 195: read **158 coherent, 35 loose, 2 incoherent**. **Promoted: 168 groups. Held back: 27.**
* Held back (a group can fail more than one test): fewer than 5 eligible cards 16; the key does not state the effect 12; mixed or unreadable members 2; most members have no ability text 1.
* Promoted groups by family: Zone change 32, Pump / grant 19, Counters 18, Library 17, Static: continuous 13, Tokens 11, Damage 10, Discard / hand 6, Destroy 5, Tap / untap 5, others 32. Of the 168, 20 are loose; 67 are backoff residuals named "...less common kinds" or "...other kinds of target"
  (10 of them are both loose and residual).
* **Tentative cards: 2,256** (2,439 placements; average 1.08 groups per card, maximum 3). Groups have 5 to 53 eligible cards (median 12).

Why each held-back group failed (details per group in the table below):
* Mixed members: T54 ("A card with several modes": every member shows only a trigger clause, never an effect) and T114 ("Triggers an extra time": every member is held for a dropped condition, none eligible).
* Key does not say what happens: "Give things a different rule" (T35, T144), "Continuous effect on this permanent" (T104), "Give things a gained effect" (T125, T153), "Give things a set power" which also holds animate-an-enchantment (T142),
  "Cast a card" which also holds can't-cast and copy abilities (T27), "gained ability" which also holds token creation for opponents (T28), "Put counters, through a replacement effect" which also holds boons (T171).
* Unrecorded fields: Copy and Cast keep their honest names ("which one is not recorded", "the zone is not recorded"); who draws is not recorded in the parse for the plain Draw groups, so they are named "Draw cards, ..." without a subject.
* Too few eligible cards: 16 groups (a group with 2 or 3 eligible cards, mostly because most members are held for a dropped condition).
* Text-less: T167 "Attach to a creature": 51 of 64 cards have no ability text of their own.

### Groups with many text-less members
Text-less members are only 218 of the 4,280 card-memberships in candidate groups (5%); 76 groups have at least one; only one group has a majority (Attach, 51 of 64). Rule proposed: **text-less members are never promoted; a group where more than half the cards are text-less is not promoted at all**;
a group with fewer keeps its eligible members, and its text-less members stay loose. (Attach is held.)

### The flag
* A new badge, **tentative**: an outlined pill with a diagonal-stripe background and italic text, using its own colours (`--tent`, `--tentbg`, light and dark), distinct from the dashed muted pill (`.b-auto`, "nearby", "auto name") and from the solid coloured pill (`.b-broad`, "broad" and the keyword badge).
* Wording on a tentative group's page: **"Tentative placement: grouped by effect type, not fully checked. Not counted in the precise or the broad figure."** Each card row says why the ability is tentative (the same reason line as the loose list).
* Where it appears in the tree: under "What abilities do", at the end of each family that has promoted groups, a row **"Tentative groups"** (with the badge and a card count) that opens the family's tentative groups, each with the badge. The main nodes and leaves above it are unchanged.
  The loose section stays complete under "Not yet organized, browsed loosely"; its promoted groups carry the badge and a link to the same page.
* A card in both a main group and a tentative group: **cannot happen** by construction (only pile cards, which have no main placement, are promoted). If it ever did, the main group would be shown and the tentative group would appear only as an "Also tentatively" chip.
* Find a card: **"Tentatively grouped (not fully checked, not counted as organized): <group chips>. Tentative placement: grouped by effect type, not fully checked."** A card that is loose only keeps today's wording; a card with no family keeps the couldn't-read-yet link.
* Never "review queue" in tester-facing text.

### Counting (measured; the build does not change any existing figure)
| Figure | Cards | Of | % | Basis |
|---|---|---|---|---|
| **Precise** (unchanged) | 24,336 | 33,183 | 73.3% | placed by an ability in an unflagged leaf of 5 or more, plus the keyword block, "No abilities" and the replacement groups |
| **With broad** (unchanged) | 27,590 | 33,183 | 83.1% | the precise figure plus 3,254 cards whose abilities sit only in groups broader than they look |
| **With tentative** (new) | 29,846 | 33,183 | 89.9% | the broad figure plus 2,256 pile cards with an eligible ability in a promoted loose group |

The archived card-level view's 74.8% is on a different basis. The three figures are always shown together with their bases.
* Pile: 5,593 -> **3,337 still "Not yet organized"**; **2,256 cards leave it** and are shown as tentatively placed (all 2,256 already have a loose group). By pile group: gap 1,424, too unusual 820, part of its text may not have been read 12.
* Reconciliation: placed 27,590 (22,541 placed + 3,254 broad only + 1,245 keyword + 346 no abilities + 204 replacement) + **tentative 2,256** + still unorganized 3,337 + not cards 5,738 = **38,921**. Each card is counted once.
* No existing status is renamed. The ledger statuses and `view` classes stay as they are; the build keeps `unorganized` for these cards. `tentative` is a **derived field**, in new files only (`build/tentative_placements.json`, method `loose_tentative`; `min3_tentative` reserved), and the page subtracts it from the pile count.
* The loose section's own counts (4,293 with a group) are unchanged; it says how many of them are tentative.

### Caution: what the tentative cards rest on
Of the 2,256 tentative cards, **897 rest on a rare-shape ability of a clean card**, and **1,359 rest only on abilities with an unread part (1,227 placements) or gap-test failures (308)**; those are the gap-card abilities the main tree holds back.
Your decisions exclude only dropped-condition and text-less abilities, so these are included in the numbers above; each row will say "part of the ability was not read". *Option B*: count only rare-shape abilities: 897 cards, **85.8%** with tentative (28,487 of 33,183).
*Option R3*: also hold the 10 groups that are both loose and backoff residuals: 2,107 cards, 89.5% (29,697 of 33,183). The Part 3 check of 40 placements (bar: more than 5 wrong turns the layer off) will show whether the unread-part placements hold up.

### Names
* The existing defect and claims checks over the 168 promoted names: **0 hard defects, 0 claims hits, 0 over 110 characters.**
* Hand check of 20 promoted names against the members (seed 20261022, set before drawing; members were read and judged before the names were shown): **0 misleading.** One is incomplete rather than wrong: "Deal damage in another form to a creature, all of them"
  (members hit each opponent and each creature); "in another form" is opaque and should be reworded in Part 3. 20 names cannot show a rate.

### Reversibility
One switch: `TENTATIVE_LAYER = False` in `src/build_tentative.py` writes an empty layer; and a page checkbox **"Show tentative placements"** (default on, remembered per viewer) hides the badge rows, the third headline figure and the tentative count, and puts the 2,256 cards back into the
"Not yet organized" count. Neither touches the main tree, the leaves or the loose layer.

### Candidate table (all 195)
Columns: family, group name, cards, eligible cards, cards with no ability text, mix of the members' abilities (rare shape / unread part / condition / gap test), my read, key states the effect, decision.

| # | Family | Group | Cards | Eligible | No text | Members' abilities | Read | Key ok | Decision |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Static: restriction | Can't be blocked by certain creatures, less common kinds | 11 | 11 | 0 | gap test 6, rare shape 5 | coherent | yes | promote |
| 2 | Tokens | Create creature tokens, from a spell or activated ability | 34 | 26 | 1 | unread part 19, condition 7, rare shape 5, gap test 3 | coherent | yes | promote |
| 3 | Pump / grant | Make things smaller, other kinds of target | 11 | 9 | 0 | rare shape 7, condition 2, gap test 1, unread part 1 | coherent | yes | promote |
| 4 | Counters | Put +1/+1 counters on this permanent, through a replacement effect | 39 | 5 | 0 | condition 34, gap test 5 | coherent | yes | promote |
| 5 | Tokens | Create tokens, less common kinds | 10 | 10 | 0 | unread part 6, rare shape 3, gap test 1 | loose | yes | promote |
| 6 | Destroy | Destroy a land | 13 | 5 | 0 | condition 8, gap test 2, unread part 2, rare shape 1 | coherent | yes | promote |
| 7 | Zone change | Move cards from the graveyard to the battlefield, less common kinds | 12 | 10 | 0 | rare shape 9, condition 2, unread part 1 | coherent | yes | promote |
| 8 | Static: continuous | Continuous effect on enchanted creature: adds power | 26 | 26 | 0 | unread part 17, gap test 5, rare shape 4 | coherent | yes | promote |
| 9 | Library | Reveal the top cards of a library, less common kinds | 12 | 3 | 0 | condition 9, rare shape 2, unread part 1 | loose | yes | hold: fewer than 5 eligible cards |
| 10 | Library | Look at the top cards of a library, cards go to the battlefield | 16 | 5 | 0 | condition 11, rare shape 3, unread part 1, gap test 1 | coherent | yes | promote |
| 11 | Counters | Put power/toughness counters on a creature, less common kinds | 10 | 10 | 0 | rare shape 9, unread part 1 | coherent | yes | promote |
| 12 | Damage | Make creatures fight, less common kinds | 14 | 6 | 3 | rare shape 5, condition 5, gap test 3, unread part 1 | coherent | yes | promote |
| 13 | Card draw | Draw cards, when a card moves between zones | 24 | 2 | 0 | condition 22, unread part 2 | loose | yes | hold: fewer than 5 eligible cards |
| 14 | Counters | Put counters, from a spell or activated ability, less common kinds | 35 | 26 | 3 | rare shape 18, unread part 11, condition 6 | coherent | yes | promote |
| 15 | Damage | Deal damage in another form to a creature, all of them | 19 | 10 | 1 | condition 8, unread part 6, rare shape 3, gap test 2 | coherent | yes | promote |
| 16 | Protection | Prevent damage, less common kinds | 20 | 14 | 1 | rare shape 9, condition 5, unread part 4, gap test 2 | coherent | yes | promote |
| 17 | Library | Mill cards, less common kinds | 27 | 20 | 2 | rare shape 14, unread part 7, condition 5, gap test 2 | coherent | yes | promote |
| 18 | Library | Mill cards, by you | 31 | 7 | 1 | condition 23, gap test 4, unread part 4, rare shape 1 | coherent | yes | promote |
| 19 | Pump / grant | Make a creature bigger | 43 | 16 | 2 | condition 25, unread part 15, gap test 2, rare shape 1 | coherent | yes | promote |
| 20 | Mana | Add mana, of any one color | 23 | 15 | 0 | condition 8, gap test 8, unread part 7 | coherent | yes | promote |
| 21 | Zone change | Move cards from the graveyard to exile, ones you control | 12 | 8 | 1 | unread part 5, rare shape 3, condition 3, gap test 1 | loose | yes | promote |
| 22 | Zone change | Move a creature to exile | 25 | 14 | 2 | unread part 10, condition 9, rare shape 3, gap test 3 | coherent | yes | promote |
| 23 | Zone change | Return this permanent to its owner's hand | 13 | 8 | 0 | unread part 8, condition 5 | coherent | yes | promote |
| 24 | Counters | Put +1/+1 counters on this permanent | 17 | 5 | 0 | condition 12, gap test 2, unread part 2, rare shape 1 | coherent | yes | promote |
| 25 | Control | Gain control of an artifact | 12 | 10 | 0 | rare shape 9, condition 2, unread part 1 | coherent | yes | promote |
| 26 | Mana | Add mana, of one specific color | 27 | 21 | 0 | unread part 18, condition 6, gap test 3, rare shape 1 | coherent | yes | promote |
| 27 | Cast / play | Cast a card (the zone is not recorded) | 22 | 7 | 3 | condition 12, unread part 4, rare shape 3, gap test 3 | loose | no | hold: the key does not state the effect |
| 28 | Pump / grant | Give things a gained ability | 12 | 7 | 3 | unread part 9, condition 2, rare shape 1 | loose | no | hold: the key does not state the effect |
| 29 | Counters | Put time counters, other kinds of target | 10 | 7 | 1 | unread part 5, rare shape 4, condition 2 | coherent | yes | promote |
| 30 | Static: continuous | Continuous effect on a creature: adds power | 15 | 15 | 0 | gap test 8, unread part 6, rare shape 2 | coherent | yes | promote |
| 31 | Counters | Put +1/+1 counters on the thing chosen before, less common kinds | 10 | 7 | 0 | unread part 5, condition 3, rare shape 2 | coherent | yes | promote |
| 32 | Counters | Put +1/+1 counters on this permanent, on another kind of trigger | 26 | 26 | 0 | unread part 27 | coherent | yes | promote |
| 33 | Sacrifice | Sacrifice this permanent | 17 | 11 | 0 | unread part 9, condition 6, gap test 2 | coherent | yes | promote |
| 34 | Zone change | Move cards to exile, less common kinds | 25 | 19 | 3 | rare shape 10, unread part 9, gap test 3, condition 3 | loose | yes | promote |
| 35 | Pump / grant | Give things a different rule, other kinds of target | 10 | 5 | 2 | rare shape 4, condition 3, unread part 2, gap test 1 | loose | no | hold: the key does not state the effect |
| 36 | Damage | Deal damage to any target | 18 | 8 | 0 | condition 10, unread part 9 | coherent | yes | promote |
| 37 | Pump / grant | Give things haste, other kinds of target | 15 | 13 | 0 | rare shape 8, unread part 4, condition 2, gap test 1 | loose | yes | promote |
| 38 | Pump / grant | Give things first strike, other kinds of target | 11 | 3 | 2 | condition 6, unread part 2, gap test 2, rare shape 1 | loose | yes | hold: fewer than 5 eligible cards |
| 39 | Counters | Put +1/+1 counters on a creature, all of them | 11 | 7 | 2 | gap test 5, rare shape 3, unread part 2, condition 2 | coherent | yes | promote |
| 40 | Static: continuous | Continuous effect on things: gives trample, other kinds of target | 14 | 14 | 0 | unread part 8, gap test 5, rare shape 1 | coherent | yes | promote |
| 41 | Pump / grant | Make things bigger and smaller, other kinds of target | 10 | 9 | 0 | rare shape 4, unread part 3, gap test 2, condition 1 | coherent | yes | promote |
| 42 | Library | Exile the top cards of a library | 42 | 30 | 2 | unread part 27, condition 10, gap test 7 | coherent | yes | promote |
| 43 | Damage | Deal damage to a creature, from a spell or activated ability | 56 | 15 | 4 | condition 37, unread part 11, gap test 7, rare shape 1 | coherent | yes | promote |
| 44 | Zone change | Move the thing chosen before to exile | 22 | 12 | 0 | unread part 11, condition 10, gap test 1 | loose | yes | promote |
| 45 | Library | Search a library, less common kinds | 14 | 12 | 0 | rare shape 12, condition 2 | coherent | yes | promote |
| 46 | Game / player | Flip a coin | 17 | 7 | 0 | condition 10, unread part 6, gap test 1 | coherent | yes | promote |
| 47 | Tokens | Create artifact tokens | 38 | 21 | 1 | condition 16, unread part 10, gap test 8, rare shape 4 | coherent | yes | promote |
| 48 | Sacrifice | Sacrifice, less common kinds | 70 | 50 | 3 | rare shape 30, unread part 21, condition 17, gap test 2 | coherent | yes | promote |
| 49 | Counters | Remove counters, less common kinds | 45 | 29 | 3 | rare shape 23, condition 13, unread part 7, gap test 3 | coherent | yes | promote |
| 50 | Pump / grant | Give things no abilities, other kinds of target | 11 | 11 | 0 | rare shape 8, unread part 3 | coherent | yes | promote |
| 51 | Damage | Deal damage to a player | 27 | 6 | 0 | condition 21, unread part 5, gap test 1 | coherent | yes | promote |
| 52 | Card draw | Draw cards | 28 | 5 | 1 | condition 22, unread part 4, gap test 2 | coherent | yes | promote |
| 53 | Tap / untap | Tap a creature | 26 | 15 | 0 | condition 11, unread part 9, rare shape 4, gap test 2 | coherent | yes | promote |
| 54 | Choice / wrapper | A card with several modes | 46 | 41 | 5 | unread part 46 | incoherent | no | hold: mixed or unreadable members; the key does not state the effect |
| 55 | Zone change | Return a creature to its owner's hand | 17 | 7 | 0 | condition 10, unread part 7 | coherent | yes | promote |
| 56 | Zone change | Return things to their owners' hands, ones you control | 17 | 10 | 4 | unread part 8, rare shape 4, condition 3, gap test 2 | coherent | yes | promote |
| 57 | Zone change | Move cards from the graveyard to exile | 23 | 10 | 3 | condition 10, unread part 7, gap test 4, rare shape 2 | coherent | yes | promote |
| 58 | Zone change | Move cards to exile | 42 | 29 | 2 | unread part 14, condition 11, rare shape 10, gap test 7 | coherent | yes | promote |
| 59 | Static: cost change | Spells cost less | 27 | 18 | 0 | gap test 10, condition 9, rare shape 8 | coherent | yes | promote |
| 60 | Damage | Deal damage to each player, all of them | 13 | 10 | 1 | gap test 6, unread part 5, condition 2 | coherent | yes | promote |
| 61 | Copy | Become a copy of a creature | 10 | 6 | 0 | rare shape 5, condition 4, unread part 1 | coherent | yes | promote |
| 62 | Game / player | Roll a die | 12 | 7 | 0 | unread part 6, condition 5, gap test 1 | coherent | yes | promote |
| 63 | Static: other rule | Cast spells with an added ability, less common kinds | 12 | 12 | 0 | rare shape 12 | coherent | yes | promote |
| 64 | Static: continuous | Continuous effect on things: grants an ability, other kinds of target | 39 | 37 | 0 | unread part 35, condition 2, rare shape 1, gap test 1 | coherent | yes | promote |
| 65 | Library | Seek a card, cards go to hand | 12 | 10 | 0 | unread part 5, rare shape 3, gap test 2, condition 2 | coherent | yes | promote |
| 66 | Library | Reveal the top cards of a library | 19 | 7 | 0 | condition 12, unread part 6, rare shape 1 | loose | yes | promote |
| 67 | Zone change | Move cards to the graveyard, less common kinds | 11 | 10 | 0 | rare shape 10, condition 1 | loose | yes | promote |
| 68 | Pump / grant | Make this permanent bigger | 30 | 19 | 1 | unread part 16, condition 10, gap test 4 | coherent | yes | promote |
| 69 | Pump / grant | Make things bigger or smaller by a counted amount, other kinds of target | 11 | 8 | 0 | unread part 4, rare shape 3, condition 3, gap test 1 | loose | yes | promote |
| 70 | Library | Reveal the top cards of a library, cards go to the battlefield | 10 | 5 | 0 | condition 5, unread part 4, rare shape 1 | coherent | yes | promote |
| 71 | Library | Surveil | 12 | 7 | 0 | condition 6, unread part 4, gap test 3 | coherent | yes | promote |
| 72 | Zone change | Move cards from hand to the battlefield | 10 | 3 | 0 | condition 7, rare shape 3 | coherent | yes | hold: fewer than 5 eligible cards |
| 73 | Discard / hand | Reveal a hand | 36 | 17 | 2 | condition 17, unread part 13, rare shape 3, gap test 3 | coherent | yes | promote |
| 74 | Pump / grant | Make a creature smaller, all of them | 11 | 4 | 0 | condition 7, rare shape 3, unread part 1 | coherent | yes | hold: fewer than 5 eligible cards |
| 75 | Tokens | Create creature tokens, less common kinds | 31 | 21 | 2 | unread part 12, condition 8, rare shape 6, gap test 6 | coherent | yes | promote |
| 76 | Zone change | Move cards to exile, ones you control, less common kinds | 16 | 15 | 0 | rare shape 11, unread part 4, condition 1 | coherent | yes | promote |
| 77 | Copy | Copy a spell or ability (which one is not recorded), chosen before | 29 | 14 | 0 | condition 15, unread part 10, rare shape 4 | coherent | yes | promote |
| 78 | Pump / grant | Give things a gained effect, power and toughness up, other kinds of target | 33 | 27 | 2 | rare shape 19, unread part 9, condition 4, gap test 2 | coherent | yes | promote |
| 79 | Pump / grant | Give things flying, other kinds of target | 11 | 11 | 0 | rare shape 8, gap test 3 | coherent | yes | promote |
| 80 | Tap / untap | Tap, less common kinds | 35 | 30 | 0 | rare shape 14, unread part 8, gap test 8, condition 5 | loose | yes | promote |
| 81 | Zone change | Move cards from the graveyard to the battlefield | 36 | 22 | 1 | unread part 20, condition 13, gap test 3 | coherent | yes | promote |
| 82 | Damage | Deal damage to any target, from a spell or activated ability | 38 | 14 | 0 | condition 24, unread part 13, gap test 1 | coherent | yes | promote |
| 83 | Card draw | Draw cards, from a spell or activated ability | 93 | 50 | 20 | gap test 38, unread part 33, condition 23 | coherent | yes | promote |
| 84 | Pump / grant | Make a creature bigger, all of them | 33 | 18 | 5 | unread part 13, condition 10, gap test 9, rare shape 2 | coherent | yes | promote |
| 85 | Library | Search a library | 12 | 9 | 3 | rare shape 10, gap test 2 | coherent | yes | promote |
| 86 | Life | Gain life, by you | 44 | 24 | 2 | condition 18, unread part 17, gap test 11 | coherent | yes | promote |
| 87 | Pump / grant | Make things bigger, other kinds of target | 23 | 21 | 1 | rare shape 18, unread part 3, gap test 2, condition 1 | loose | yes | promote |
| 88 | Zone change | Move cards from the graveyard to exile, less common kinds | 10 | 10 | 0 | rare shape 6, unread part 4 | coherent | yes | promote |
| 89 | Zone change | Move cards from the library to exile | 18 | 14 | 0 | rare shape 9, unread part 7, condition 4 | coherent | yes | promote |
| 90 | Damage | Deal damage, less common kinds | 46 | 37 | 1 | rare shape 26, condition 8, unread part 8, gap test 5 | loose | yes | promote |
| 91 | Life | Lose life, less common kinds | 38 | 24 | 1 | condition 13, unread part 11, rare shape 10, gap test 5 | coherent | yes | promote |
| 92 | Counters | Put power/toughness counters on this permanent | 13 | 10 | 0 | rare shape 6, gap test 4, condition 3 | coherent | yes | promote |
| 93 | Discard / hand | Discard cards | 11 | 5 | 0 | condition 6, rare shape 3, unread part 2 | coherent | yes | promote |
| 94 | Cast / play | Cast a card (the zone is not recorded), without paying its cost | 22 | 2 | 0 | condition 20, rare shape 2 | loose | yes | hold: fewer than 5 eligible cards |
| 95 | Tokens | Create a token that is a copy of the thing chosen before | 15 | 9 | 0 | condition 6, unread part 6, rare shape 3 | coherent | yes | promote |
| 96 | Zone change | Move cards to the battlefield | 26 | 17 | 1 | unread part 14, condition 8, rare shape 2, gap test 2 | coherent | yes | promote |
| 97 | Damage | Deal damage in another form, less common kinds | 13 | 13 | 0 | rare shape 10, unread part 3 | coherent | yes | promote |
| 98 | Counters | Put +1/+1 counters on a creature | 37 | 20 | 3 | unread part 16, condition 14, gap test 4, rare shape 3 | coherent | yes | promote |
| 99 | Control | Gain control of a creature | 28 | 17 | 1 | condition 10, rare shape 9, unread part 8, gap test 1 | coherent | yes | promote |
| 100 | Damage | Deal damage to a creature or planeswalker | 23 | 5 | 0 | condition 18, unread part 5 | coherent | yes | promote |
| 101 | Counters | Give a player counters, poison counters, less common kinds | 11 | 11 | 0 | rare shape 8, unread part 2, gap test 1 | coherent | yes | promote |
| 102 | Pump / grant | Make a creature smaller | 27 | 14 | 4 | condition 9, unread part 7, gap test 6, rare shape 5 | coherent | yes | promote |
| 103 | Pump / grant | Give things a creature type, other kinds of target | 18 | 15 | 1 | rare shape 17, condition 3, gap test 1 | coherent | yes | promote |
| 104 | Static: continuous | Continuous effect on this permanent | 39 | 39 | 0 | unread part 41 | loose | no | hold: the key does not state the effect |
| 105 | Tokens | Create a token that is a copy of a creature | 19 | 18 | 0 | rare shape 12, unread part 5, condition 1, gap test 1 | coherent | yes | promote |
| 106 | Pump / grant | Give things indestructible | 10 | 5 | 1 | condition 4, unread part 3, gap test 3 | coherent | yes | promote |
| 107 | Tap / untap | Untap an artifact, less common kinds | 12 | 11 | 1 | rare shape 9, unread part 3 | coherent | yes | promote |
| 108 | Counters | Put counters, less common kinds | 38 | 31 | 1 | rare shape 15, unread part 15, condition 6, gap test 2 | coherent | yes | promote |
| 109 | Static: continuous | Continuous effect on things: gives indestructible, other kinds of target | 13 | 13 | 0 | unread part 8, rare shape 4, gap test 1 | coherent | yes | promote |
| 110 | Sacrifice | Sacrifice a creature | 24 | 8 | 1 | condition 15, rare shape 6, unread part 2, gap test 1 | loose | yes | promote |
| 111 | Zone change | Move cards to exile, all of them | 18 | 17 | 0 | rare shape 8, unread part 8, condition 1, gap test 1 | loose | yes | promote |
| 112 | Discard / hand | Reveal a hand, by target player | 10 | 8 | 0 | unread part 6, rare shape 2, condition 2 | coherent | yes | promote |
| 113 | Tokens | Create a token that is a copy of an artifact | 12 | 12 | 0 | rare shape 12 | coherent | yes | promote |
| 114 | Static: other rule | Triggers an extra time | 16 | 0 | 0 | condition 16 | incoherent | no | hold: mixed or unreadable members; the key does not state the effect; fewer than 5 eligible cards |
| 115 | Static: continuous | Continuous effect on things: gives haste, other kinds of target | 17 | 17 | 0 | unread part 9, rare shape 7, gap test 1 | coherent | yes | promote |
| 116 | Copy | Copy a spell or ability (which one is not recorded), less common kinds | 20 | 18 | 1 | rare shape 14, unread part 5, gap test 2, condition 1 | coherent | yes | promote |
| 117 | Tokens | Create creature tokens with flying | 22 | 14 | 1 | unread part 8, condition 7, rare shape 6, gap test 2 | coherent | yes | promote |
| 118 | Tap / untap | Untap a creature | 14 | 10 | 0 | rare shape 6, unread part 4, condition 4 | coherent | yes | promote |
| 119 | Sacrifice | Sacrifice the thing chosen before | 22 | 17 | 0 | unread part 10, rare shape 5, condition 5, gap test 2 | loose | yes | promote |
| 120 | Zone change | Move cards to exile, ones an opponent controls | 15 | 12 | 1 | unread part 6, gap test 6, rare shape 3, condition 2 | coherent | yes | promote |
| 121 | Counter spell | Counter a card | 52 | 13 | 4 | condition 37, unread part 11, gap test 3, rare shape 1 | coherent | yes | promote |
| 122 | Counters | Put +1/+1 counters, other kinds of target | 29 | 25 | 1 | rare shape 16, unread part 8, condition 4, gap test 2 | coherent | yes | promote |
| 123 | Static: continuous | Continuous effect on things: gives lifelink, other kinds of target | 11 | 11 | 0 | unread part 7, rare shape 3, gap test 1 | coherent | yes | promote |
| 124 | Library | Scry | 14 | 8 | 0 | condition 6, unread part 4, gap test 4 | coherent | yes | promote |
| 125 | Pump / grant | Give things a gained effect, less common kinds | 14 | 13 | 0 | rare shape 13, condition 1 | loose | no | hold: the key does not state the effect |
| 126 | Library | Reveal cards until a match | 18 | 14 | 0 | rare shape 11, condition 4, unread part 3 | coherent | yes | promote |
| 127 | Zone change | Phase out, less common kinds | 13 | 9 | 2 | rare shape 9, condition 2, unread part 1, gap test 1 | coherent | yes | promote |
| 128 | Counters | Put +1/+1 counters on this permanent, at the beginning of a phase | 16 | 5 | 0 | condition 11, unread part 3, gap test 2 | coherent | yes | promote |
| 129 | Card draw | Draw cards, on another kind of trigger | 48 | 46 | 0 | unread part 46, condition 2 | coherent | yes | promote |
| 130 | Zone change | Put a card in a library, less common kinds | 10 | 7 | 0 | rare shape 5, condition 3, unread part 2 | coherent | yes | promote |
| 131 | Destroy | Destroy a creature, all of them | 12 | 10 | 1 | unread part 8, gap test 3, rare shape 1, condition 1 | coherent | yes | promote |
| 132 | Zone change | Move cards from hand to the library, less common kinds | 11 | 11 | 0 | rare shape 11, unread part 2 | coherent | yes | promote |
| 133 | Control | Gain control of things, less common kinds | 32 | 23 | 0 | rare shape 16, condition 9, unread part 7 | coherent | yes | promote |
| 134 | Pump / grant | Give things a card type, other kinds of target | 15 | 13 | 0 | rare shape 12, condition 2, unread part 1 | coherent | yes | promote |
| 135 | Counter spell | Counter a spell, less common kinds | 24 | 12 | 0 | condition 12, unread part 7, rare shape 5 | coherent | yes | promote |
| 136 | Mana | Add mana | 14 | 6 | 0 | condition 8, unread part 3, gap test 3 | coherent | yes | promote |
| 137 | Static: continuous | Continuous effect on this permanent: adds power | 54 | 53 | 0 | unread part 52, gap test 4, condition 1 | coherent | yes | promote |
| 138 | Library | Search a library, put it in hand | 47 | 37 | 1 | rare shape 19, unread part 16, condition 9, gap test 3 | coherent | yes | promote |
| 139 | Life | Lose life | 25 | 16 | 2 | gap test 8, condition 7, rare shape 6, unread part 4 | coherent | yes | promote |
| 140 | Protection | Regenerate, less common kinds | 20 | 19 | 0 | rare shape 11, unread part 5, gap test 4, condition 1 | coherent | yes | promote |
| 141 | Pump / grant | Give things double strike, other kinds of target | 11 | 5 | 1 | condition 5, rare shape 3, gap test 2, unread part 1 | coherent | yes | promote |
| 142 | Pump / grant | Give things a set power, other kinds of target | 13 | 12 | 0 | unread part 7, rare shape 5, condition 1 | loose | no | hold: the key does not state the effect |
| 143 | Zone change | Move cards from hand to exile, less common kinds | 12 | 11 | 0 | rare shape 7, unread part 3, condition 1, gap test 1 | coherent | yes | promote |
| 144 | Pump / grant | Give a creature a different rule | 18 | 15 | 0 | rare shape 8, gap test 4, unread part 4, condition 3 | coherent | no | hold: the key does not state the effect |
| 145 | Zone change | Return a nonland permanent to its owner's hand | 12 | 3 | 1 | condition 8, unread part 3, gap test 1 | coherent | yes | hold: fewer than 5 eligible cards |
| 146 | Destroy | Destroy a creature | 41 | 12 | 5 | condition 24, unread part 8, gap test 8, rare shape 2 | coherent | yes | promote |
| 147 | Discard / hand | Discard cards, by you | 16 | 9 | 0 | unread part 7, condition 7, gap test 2 | coherent | yes | promote |
| 148 | Destroy | Destroy the thing chosen before | 14 | 8 | 0 | condition 6, unread part 4, rare shape 3, gap test 1 | loose | yes | promote |
| 149 | Zone change | Return things to their owners' hands | 16 | 10 | 1 | unread part 5, condition 5, rare shape 4, gap test 2 | loose | yes | promote |
| 150 | Static: other rule | Cast cards from a graveyard, less common kinds | 12 | 3 | 0 | condition 9, rare shape 3 | coherent | yes | hold: fewer than 5 eligible cards |
| 151 | Tokens | Create creature tokens, on another kind of trigger | 18 | 17 | 0 | unread part 18, condition 1 | coherent | yes | promote |
| 152 | Destroy | Destroy an artifact | 13 | 2 | 2 | condition 9, gap test 2, unread part 2 | coherent | yes | hold: fewer than 5 eligible cards |
| 153 | Pump / grant | Give things a gained effect, other kinds of target | 75 | 52 | 8 | rare shape 42, condition 15, unread part 11, gap test 7 | loose | no | hold: the key does not state the effect |
| 154 | Counters | Put +1/+1 counters on this permanent, when a card moves between zones | 12 | 4 | 0 | condition 8, gap test 2, unread part 2 | coherent | yes | hold: fewer than 5 eligible cards |
| 155 | Destroy | Destroy an artifact or enchantment | 12 | 7 | 0 | unread part 7, condition 5 | coherent | yes | promote |
| 156 | Pump / grant | Make any target bigger | 10 | 4 | 0 | condition 6, unread part 2, rare shape 1, gap test 1 | loose | yes | hold: fewer than 5 eligible cards |
| 157 | Copy | Become a copy, less common kinds | 23 | 23 | 0 | rare shape 24 | coherent | yes | promote |
| 158 | Discard / hand | Discard cards, by target player | 14 | 6 | 1 | condition 7, rare shape 3, unread part 3, gap test 2 | coherent | yes | promote |
| 159 | Counters | Put counters, when a card moves between zones, less common kinds | 16 | 15 | 0 | rare shape 12, unread part 2, condition 1, gap test 1 | coherent | yes | promote |
| 160 | Damage | Deal damage to the thing chosen before | 11 | 2 | 0 | condition 9, rare shape 1, unread part 1 | loose | yes | hold: fewer than 5 eligible cards |
| 161 | Zone change | Move cards to exile, ones you control | 15 | 9 | 1 | unread part 5, condition 5, rare shape 4, gap test 2 | coherent | yes | promote |
| 162 | Tokens | Create creature tokens | 21 | 10 | 2 | condition 9, unread part 6, rare shape 4, gap test 3 | coherent | yes | promote |
| 163 | Discard / hand | Discard cards, less common kinds | 21 | 18 | 0 | unread part 9, rare shape 8, condition 3, gap test 1 | coherent | yes | promote |
| 164 | Static: continuous | Continuous effect on this permanent: gives flying | 18 | 17 | 0 | unread part 16, rare shape 1, condition 1 | coherent | yes | promote |
| 165 | Pump / grant | Give things a gained ability, other kinds of target | 11 | 9 | 1 | unread part 7, rare shape 2, gap test 1, condition 1 | loose | yes | promote |
| 166 | Pump / grant | Give things trample, other kinds of target | 16 | 10 | 1 | rare shape 7, condition 5, unread part 3, gap test 1 | coherent | yes | promote |
| 167 | Attach | Attach to a creature | 64 | 13 | 51 | gap test 56, unread part 11, rare shape 2 | loose | no | hold: the key does not state the effect; most members have no ability text |
| 168 | Zone change | Move cards from the graveyard to the battlefield, ones you control | 42 | 23 | 3 | condition 16, unread part 16, rare shape 5, gap test 5 | coherent | yes | promote |
| 169 | Counters | Put counters, at the beginning of a phase, less common kinds | 34 | 26 | 0 | rare shape 19, condition 8, unread part 4, gap test 3 | coherent | yes | promote |
| 170 | Tokens | Create a token that is a copy of something, less common kinds | 18 | 13 | 0 | rare shape 11, condition 5, unread part 2 | coherent | yes | promote |
| 171 | Counters | Put counters, through a replacement effect, less common kinds | 47 | 39 | 0 | rare shape 35, condition 8, gap test 4 | loose | no | hold: the key does not state the effect |
| 172 | Static: continuous | Continuous effect on things: gives vigilance, other kinds of target | 11 | 11 | 0 | unread part 8, gap test 2, rare shape 1 | coherent | yes | promote |
| 173 | Tokens | Create creature tokens, at the beginning of a phase | 13 | 2 | 0 | condition 11, unread part 1, gap test 1 | coherent | yes | hold: fewer than 5 eligible cards |
| 174 | Card draw | Draw cards, at the beginning of a phase | 32 | 5 | 0 | condition 27, unread part 5 | loose | yes | promote |
| 175 | Static: continuous | Continuous effect on things: grants a trigger, other kinds of target | 13 | 13 | 0 | unread part 9, rare shape 4 | coherent | yes | promote |
| 176 | Static: continuous | Continuous effect on this permanent: gives first strike | 10 | 10 | 0 | unread part 9, gap test 1 | coherent | yes | promote |
| 177 | Zone change | Return things to their owners' hands, less common kinds | 17 | 12 | 1 | rare shape 11, condition 4, unread part 2 | loose | yes | promote |
| 178 | Zone change | Move cards from hand to the battlefield, ones you control | 12 | 6 | 1 | condition 5, unread part 4, rare shape 2, gap test 1 | coherent | yes | promote |
| 179 | Library | Look at the top cards of a library, cards go to exile | 12 | 10 | 0 | unread part 10, condition 2 | coherent | yes | promote |
| 180 | Library | Search a library for a card, put it in hand | 18 | 2 | 0 | condition 16, unread part 2 | coherent | yes | hold: fewer than 5 eligible cards |
| 181 | Library | Reveal the top cards of a library, cards go to hand, less common kinds | 11 | 5 | 0 | condition 6, unread part 4, rare shape 1 | coherent | yes | promote |
| 182 | Library | Look at the top cards of a library, cards go to hand | 27 | 2 | 0 | condition 25, unread part 2 | coherent | yes | hold: fewer than 5 eligible cards |
| 183 | Zone change | Move cards from hand to exile, ones you control, less common kinds | 12 | 12 | 0 | rare shape 6, unread part 3, gap test 3 | coherent | yes | promote |
| 184 | Library | Look at the top cards of a library | 27 | 7 | 0 | condition 20, unread part 6, rare shape 1 | coherent | yes | promote |
| 185 | Zone change | Return the thing chosen before to its owner's hand | 10 | 6 | 0 | unread part 6, condition 4 | loose | yes | promote |
| 186 | Pump / grant | Give things flying | 22 | 14 | 1 | rare shape 9, condition 7, unread part 5, gap test 1 | coherent | yes | promote |
| 187 | Tap / untap | Untap, less common kinds | 39 | 28 | 4 | rare shape 17, gap test 8, condition 7, unread part 7 | coherent | yes | promote |
| 188 | Zone change | Move cards to the library, less common kinds | 14 | 10 | 0 | rare shape 9, condition 4, unread part 1 | coherent | yes | promote |
| 189 | Library | Search a library, put it onto the battlefield | 43 | 30 | 0 | rare shape 15, unread part 13, condition 13, gap test 2 | coherent | yes | promote |
| 190 | Zone change | Return things to their owners' hands, from the graveyard, ones you control | 22 | 14 | 0 | rare shape 8, condition 8, unread part 5, gap test 1 | coherent | yes | promote |
| 191 | Mana | Add mana, less common kinds | 10 | 10 | 0 | rare shape 6, gap test 2, unread part 2 | coherent | yes | promote |
| 192 | Counters | Put lore counters on this permanent | 17 | 17 | 0 | gap test 17 | coherent | yes | promote |
| 193 | Static: continuous | Continuous effect on equipped creature: adds power | 22 | 22 | 0 | gap test 17, unread part 5 | coherent | yes | promote |
| 194 | Static: restriction | Can't be blocked, this permanent | 11 | 11 | 0 | unread part 9, gap test 2 | coherent | yes | promote |
| 195 | Zone change | Return things to their owners' hands, from the graveyard, less common kinds | 11 | 7 | 2 | rare shape 5, condition 2, unread part 2, gap test 2 | coherent | yes | promote |
