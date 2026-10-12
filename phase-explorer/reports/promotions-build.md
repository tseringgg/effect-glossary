# The 2026-10 tentative promotions: renamed groups and sub-headings (build and checks)

Built by `src/build_tentative.py` (hand reads in `corrections/tentative_groups.json`, now with a `subheadings` section) -> `build/tentative_placements.json`, `build/tentative_ledger.json`. Wording changes in `src/probe_loose_groups_v2.py`.
Placement check: `src/check_promotions.py`. Design and Part A: `false-flags-and-promotions.md`. Limits: KNOWN_LIMITATIONS.md section 16. Nothing is committed.

## What was built
* **Wording:** "adds a creature or land type"; "Double counters, life or mana"; "Can attack as though it didn't have defender"; the as-long-as group is now **"Continuous effect, only as long as something is true"** (no subject: its members apply to this permanent, a paired creature or an equipped creature).
  Two groups that held a static-mode grant are named "Give a creature an effect like can't attack, can't block or can't be blocked" and "Give things a combat effect like can't block or can't be blocked, other kinds of target".
* **Promotion:** 2 renamed groups and 30 sub-heading groups join the 145 existing ones: **177 tentative groups**. A promoted sub-heading is a tentative group of its own (named from fixed wording; the catch-all or bucket it came from is unchanged and not promoted); a card is counted once.
  Same method (`loose_tentative`), badge, wording and `TENTATIVE_LAYER` switch; the page needed no change.
* **The third renamed group is not promoted:** "Give things a combat effect like can't block or can't be blocked, other kinds of target" reads loose and is a backoff residual, so the existing hold on loose residual groups keeps it out (5 cards). That is why **226** cards are new, not the 231 expected.
* **Switches:** `PROMOTE_RENAMED_GROUPS`, `PROMOTE_SUBHEADINGS` (each turns one of the new promotions off alone) and `HOLD_UNREAD_PART_ABILITIES` (below); the page checkbox and `TENTATIVE_LAYER` are unchanged.

## Numbers (measured)
| | Groups | Tentative cards |
|---|---|---|
| Before this round | 145 | 1,867 |
| + the 2 renamed groups | 147 | 1,916 (+49) |
| + the 30 sub-heading groups | 175 | 2,044 (+177) |
| **Both (the build)** | **177** | **2,093** (+226) |

| Figure | Cards | % of 33,183 | Basis |
|---|---|---|---|
| Precise (unchanged) | 24,336 | 73.3% | placed by an ability in an unflagged leaf of 5 or more, plus the keyword block, "No abilities" and the replacement groups |
| With broad (unchanged) | 27,590 | 83.1% | plus 3,254 cards whose abilities sit only in groups broader than they look |
| **With tentative** | **29,683** | **89.5%** | the broad figure plus 2,093 not-yet-organized cards with an eligible ability in a tentative group |

Pile 5,593 -> **3,500**. Reconciliation: 27,590 placed + 2,093 tentative + 3,500 unorganized + 5,738 not cards = **38,921**. The archived view's 74.8% is on a different basis.

## The unread-part switch (default unchanged: on)
`HOLD_UNREAD_PART_ABILITIES = True` turns off, alone, placements that rest on an ability with an unread part: **805 tentative cards, with tentative 28,395 = 85.6%, pile 4,788** (before this round's promotions the same switch gave 683 cards).
1,159 of the 2,093 tentative cards rest only on unread-part abilities (the stratum the switch removes; it was 1,076 before); 934 have at least one rare-shape ability.

## Placement check (seed 20261026, set before computing)
40 placements, 20 from the renamed groups and 20 from the sub-heading groups (pools: 53 and 204 ledger rows); ability text read and my read written before the group was shown. **Right 35, loose 3, wrong 2.**
Renamed groups: 18 right, 1 loose, 1 wrong. Sub-headings: 17 right, 2 loose, 1 wrong.
Bars: more than 5 wrong overall (no: 2) and more than 3 of 20 in a stratum (no: 1 and 1): not tripped; nothing turned off or held.
The two wrong: Wall of Stolen Identity (an enters-as-a-copy clause) sits in the as-long-as group; Baffling Defenses (sets a creature's base power) sits under "Set a life total".
**40 placements cannot show a rate.** The reads are not independent of the generator: the same model wrote the wording and judged it. Independent of it: the seed, the ability text, the counts, the hashes, the reconciliation and the browser run.

## Verification
* Hashes: the list of 541 files taken before this round, re-checked after: identical except the files meant to change (`src/build_tentative.py`, `src/probe_loose_groups_v2.py`, `corrections/tentative_groups.json`, `src/test_browse_browser.py`, `TESTER_NOTE.md`, `README.md`, `KNOWN_LIMITATIONS.md`, and the rebuilt `build/loose_groups.json`, `build/tentative_placements.json`, `build/tentative_ledger.json`) plus new files. `git diff -- archive` empty; no frozen file or taxonomy output changed.
* Two consecutive builds of all four outputs: byte-identical.
* Name checks over all 177 names: 0 hard defects, 0 claims hits, 0 over 110 characters, all unique (one wording was changed for the vocabulary check; see KNOWN_LIMITATIONS 16).
* Headless Edge (`src/test_browse_browser.py`): **137 checks, 0 failed** (124 before + 13 new). Covered: the switch on and off (badges, rows, third figure, the pile back to 5,593), tentative rows and badges, sub-heading and renamed groups opening with the label and reasons, the as-long-as group claiming no subject, the unread-part flag in the data, the count of cards only the new promotions reach, Find a card for tentative and loose-only cards and the card pages. Not covered: small screens, theme switching, scrolling performance.
* Find a card (by name, in the page's box): 5 existing tentative (Nightkin Ambusher, Qiqirn Merchant, Sphinx of Clear Skies, Augusta Order Returned, Unleash the Inferno), 5 newly promoted (Maeve Insidious Singer, Fencer's Magemark, Goblin Blast-Runner, Pathbreaker Wurm, Lush Growth), 5 loose-only (Pull from Eternity, Chandra's Firemaw, Ends, Safana Calimport Cutthroat, Tajic Legion's Valor), 5 placed (Dormant Sliver, Loyal Retainers, Silent Gravestone, Presence of Gond, Tamiyo Meets the Story Circle), 3 excluded (White Rhystic Study, Glorious Enforcer // Glorious Enforcer, Taught by Bruce Tarl): all as expected.
* `test_abilityfind.py` passes. `check_tester_note.py`: one FAIL, the stale "suggestion links" bullet (known, awaiting your decision). The tester note's tentative line now says about 2,100 cards and about 90%.

## A separate small decision: the 39 benign-shuffle flags (not lifted)
The detector holds 39 abilities (39 cards) for the idiom "if you search your library this way, shuffle": a condition is dropped, but the effect is harmless (the shuffle happens anyway). I read 5 of them in the false-flag draw: all 5 are real drops of that harmless kind.
If the flag were lifted (an estimate: the signature is assumed unchanged), **28 would match an unflagged leaf, 3 a broad leaf, 2 a tentative group, and 6 have no usable signature and would stay.** That is 28 cards (+0.08 points) on the precise figure, 33 cards out of the pile in all.
Most of the 28 are the "search your library and/or graveyard for a named card" planeswalker-helper creatures, whose leaf is "Search your library for a card and put it into your hand"; the others are spells whose head effect (destroy, damage, counters, base power and toughness) is what the leaf names, with the search clause riding along.
The risk is small: the clause is idle for placement, and a placed card still says nothing about the dropped shuffle. Recommendation: lift it, as a policy choice, in a later round. Not lifted now.

The 28 that would match an unflagged leaf:

| Card | Ability | Would land in (leaf) |
|---|---|---|
| Angrath's Fury | Destroy target creature. Angrath's Fury deals 3 damage to target player or planeswalker. You may search your library and | Destroy a creature (restriction varies) |
| Ashiok's Forerunner | When this creature enters, you may search your library and/or graveyard for a card named Ashiok, Sculptor of Fears, reve | Search your library for a card and put it into your hand (then move a  |
| Basri's Aegis | Put a +1/+1 counter on each of up to two target creatures. You may search your library and/or graveyard for a card named | Put +1/+1 counters on several creatures |
| Chandra's Firemaw | When this creature enters, you may search your library and/or graveyard for a card named Chandra, Flame's Catalyst, reve | Search your library for a card and put it into your hand (then move a  |
| Chandra's Flame Wave | Chandra's Flame Wave deals 2 damage to target player and each creature that player controls. Search your library and/or  | Deal damage to target player |
| Delivery Moogle | When this creature enters, search your library and/or graveyard for an artifact card with mana value 2 or less, reveal i | Search your library for an artifact and put it into your hand |
| Domri's Nodorog | When this creature enters, you may search your library and/or graveyard for a card named Domri, City Smasher, reveal it, | Search your library for a card and put it into your hand (then move a  |
| Dovin's Dismissal | Put up to one target tapped creature on top of its owner's library. You may search your library and/or graveyard for a c | Put a creature on top or bottom of a library |
| Elspeth's Devotee | When this creature enters, you may search your library and/or graveyard for a card named Elspeth, Undaunted Hero, reveal | Search your library for a card and put it into your hand (then move a  |
| Ethereal Elk | When this creature enters, you may search your library and/or graveyard for a card named Vivien, Nature's Avenger, revea | Search your library for a card and put it into your hand (then move a  |
| Fang-Druid Summoner | When this creature enters, you may search your library and/or graveyard for a creature card with no abilities, reveal it | Search your library for a creature and put it into your hand |
| Garruk's Warsteed | When this creature enters, you may search your library and/or graveyard for a card named Garruk, Savage Herald, reveal i | Search your library for a card and put it into your hand (then move a  |
| Gideon's Battle Cry | Put a +1/+1 counter on each creature you control. You may search your library and/or graveyard for a card named Gideon,  | Put +1/+1 counters on all creatures you control (restriction varies) |
| Goldmane Griffin | When this creature enters, you may search your library and/or graveyard for a card named Ajani, Inspiring Leader, reveal | Search your library for a card and put it into your hand (then move a  |
| Liberating Combustion | Liberating Combustion deals 6 damage to target creature. You may search your library and/or graveyard for a card named C | Deal damage to a creature |
| Liliana's Influence | Put a -1/-1 counter on each creature you don't control. You may search your library and/or graveyard for a card named Li | Put −1/−1 counters on all creatures (restriction and controller vary) |
| Liliana's Scorn | Destroy target creature. You may search your library and/or graveyard for a card named Liliana, Death Mage, reveal it, a | Destroy a creature (restriction varies) |
| Niambi, Faithful Healer | When Niambi enters, you may search your library and/or graveyard for a card named Teferi, Timebender, reveal it, and put | Search your library for a card and put it into your hand (then move a  |
| Oko's Hospitality | Creatures you control have base power and toughness 3/3 until end of turn. You may search your library and/or graveyard  | A permanent has set base power and toughness until end of turn |
| Rowan's Stalwarts | When this creature enters, you may search your library and/or graveyard for a card named Rowan, Fearless Sparkmage, reve | Search your library for a card and put it into your hand (then move a  |
| Sanctum of All | At the beginning of your upkeep, you may search your library and/or graveyard for a Shrine card and put it onto the batt | Search your library for a card and put it onto the battlefield (then m |
| Sorin's Guide | When this creature enters, you may search your library and/or graveyard for a card named Sorin, Vampire Lord, reveal it, | Search your library for a card and put it into your hand (then move a  |
| Tale of Momo | Search your library and/or graveyard for an Ally creature card, reveal it, and put it into your hand. If you search your | Search your library for a creature and put it into your hand |
| Teferi's Wavecaster | When this creature enters, you may search your library and/or graveyard for a card named Teferi, Timeless Voyager, revea | Search your library for a card and put it into your hand (then move a  |
| Tezzeret's Betrayal | Destroy target creature. You may search your library and/or graveyard for a card named Tezzeret, Master of Metal, reveal | Destroy a creature (restriction varies) |
| Tower Winder | When this creature enters, search your library and/or graveyard for a card named Command Tower, reveal it, and put it in | Search your library for a card and put it into your hand (then move a  |
| Vraska's Stoneglare | Destroy target creature. You gain life equal to its toughness. You may search your library and/or graveyard for a card n | Destroy a creature (restriction varies) |
| Yanling's Harbinger | When this creature enters, you may search your library and/or graveyard for a card named Mu Yanling, Celestial Wind, rev | Search your library for a card and put it into your hand (then move a  |

The other 11:

| Card | Outcome | Would land in |
|---|---|---|
| Jace's Ruse | broad leaf | Return several creatures to its owner's hand — “all” vs “tar |
| Ral's Dispersal | broad leaf | Return a creature to its owner's hand (restriction varies) — |
| Vraska's Scorn | broad leaf | Lose life (permanent; an opponent controls) — who loses or g |
| Agency Outfitter | no usable signature |  |
| Arachnus Spinner | no usable signature |  |
| Boonweaver Giant | no usable signature |  |
| Dark Supplicant | no usable signature |  |
| Mishra, Artificer Prodigy | no usable signature |  |
| Travel Through Caradhras | no usable signature |  |
| Finale of Devastation | promoted loose group | Search a library, put it onto the battlefield |
| The Five Doctors | promoted loose group | Search a library, put it onto the battlefield |
