# The tentative layer: build and checks

Built by `src/build_tentative.py` (hand reads in `corrections/tentative_groups.json`) -> `build/tentative_placements.json`, `build/tentative_ledger.json`; page changes in `reports/browse.html`; placement check by `src/check_tentative.py`.
Design: `tentative-design.md`. Limits: KNOWN_LIMITATIONS.md §15. Nothing is committed.

## What was built
* **Tentative groups** row at the end of each family in "What abilities do" (tentative badge, own colours, distinct from the dashed "nearby" pill and the solid "broad" pill); group pages say "Tentative placement: grouped by effect type, not fully checked. Not counted in the precise or the broad figure."
  Each row shows the ability and why it is not a real placement; unread-part rows say "part of the ability was not read".
* Header: a third figure with its basis; "Not yet organized" and "tentatively placed" shown separately. The Not-yet-organized lists leave the tentative cards out and say how many moved.
* Find a card and the card page name a card's tentative groups (and still its loose groups). The Cards tab can filter "tentatively placed". Promoted loose groups carry the badge in the loose section.
* One switch: `TENTATIVE_LAYER` in the build (empty layer) and the header checkbox "show tentative placements" (on by default, remembered): off removes every badge, row, count and the third figure and puts the cards back in the pile count. The main tree is untouched either way.
* Ledger: `build/tentative_ledger.json`, method `loose_tentative`, one row per placed ability (1,972 rows: 825 rest on a rare-shape ability, 1,147 on an unread part). `ability_ledger.json` and all statuses unchanged. `min3_tentative` reserved, not built.
* "Deal damage in another form to a creature, all of them" now reads "Deal damage to each creature".

## Holds and the result (measured)
| Step | Groups | Cards | Removed |
|---|---|---|---|
| Scope A as measured | 168 | 2,256 | |
| + hold the 10 groups both loose and backoff residual | 158 | 2,107 | -149 |
| + hold the gap-test failures | **145** | **1,867** | -240 (-247 alone; 308 placements in scope A) |
| Attach (text-less rule) | held before these numbers | | 13 eligible cards kept out |

1,867 tentative cards: 791 rest on a rare-shape ability of a clean card, 1,076 only on abilities with an unread part. Groups have 5 to 50 cards (median 11).

| Figure | Cards | % of 33,183 | Basis |
|---|---|---|---|
| Precise (unchanged) | 24,336 | 73.3% | placed by an ability in an unflagged leaf of 5 or more, plus the keyword block, "No abilities" and the replacement groups |
| With broad (unchanged) | 27,590 | 83.1% | plus 3,254 cards whose abilities sit only in groups broader than they look |
| **With tentative** | **29,457** | **88.8%** | plus 1,867 not-yet-organized cards with an eligible ability in a tentative group |

Pile: 5,593 -> **3,726** still not yet organized; 1,867 leave it (all already had a loose group). Reconciliation: 27,590 placed + 1,867 tentative + 3,726 + 5,738 not cards = **38,921**. The archived view's 74.8% is on a different basis.

## Placement check (seed 20261020, set before computing)
40 placements: 20 resting on rare-shape abilities, 20 on unread-part abilities; the ability text read and my read of it written to `build/tentative_check_reads.json` before the group was shown. **Right 34, loose 5, wrong 1.**
By stratum: rare-shape 17 right, 2 loose, 1 wrong; unread-part 17 right, 3 loose, 0 wrong. Bars: more than 5 wrong overall (no: 1) and more than 3 of 20 in a stratum (no: 1 and 0) were not tripped, so the layer stays on and no stratum is held.
The wrong one: Second Sunrise (returns cards from graveyards to the battlefield) is filed under "Return things to their owners' hands" (the parser types it as a bounce). The loose ones fit but the group is not the ability's main effect (e.g. "sacrifice" as a cost).
**40 placements cannot show a rate.** The reads are not independent of the generator: the same model wrote the group wording and judged it. Independent of it: the seed, the ability text, the counts, the hashes, the reconciliation and the browser run.
Earlier checks the layer rests on: 195 candidate groups read blind (158 coherent, 35 loose, 2 incoherent), 20 promoted names hand-checked (0 misleading), the defect and claims checks over 168 names (0 and 0); the minimum-of-3 probe (0 of 30 incoherent) is not part of this build.

## Verification
* Hashes: the list of 509 files taken before this round, re-checked after: identical except the files meant to change (`reports/browse.html`, `src/test_browse_browser.py`, `README.md`, `KNOWN_LIMITATIONS.md`, `TESTER_NOTE.md`, `src/build_loose_groups.py`, `src/probe_loose_groups_v2.py`, and `build/loose_groups.json`, whose only change is the renamed damage groups). `git diff -- archive` empty. No frozen file or taxonomy output changed.
* Two consecutive builds of all four new/rebuilt outputs: byte-identical.
* Headless Edge: **124 checks, 0 failed** (89 before + 35 new). Covered: the switch (default on, off removes badges/rows/third figure and restores the pile to 5,593, on again), tree rows and badges, open family/group, text and reason on every row, unread-part wording, the header's three figures and the reconciliation from the page's data, the lists moving out the tentative cards, tentative-group links from Find a card and the card page, the Cards tab filter.
  Not covered: small screens, theme switching, scrolling performance.
* Find a card (by name in the page's box): 5 tentative (Loreseeker's Stone, The Red Terror, Legion's End, Soul Diviner, Touch of Moonglove), 5 loose-only (Cutthroat Maneuver, Riveteers Charm, Undersimplify, Black Sun's Twilight, Centaur of Attention), 5 placed (Dormant Sliver, Loyal Retainers, Silent Gravestone, Presence of Gond, Tamiyo Meets the Story Circle), 3 excluded (White Rhystic Study, Glorious Enforcer // Glorious Enforcer, Taught by Bruce Tarl): all as expected.
* `test_abilityfind.py` passes. `check_tester_note.py`: one FAIL, the stale "suggestion links" bullet (known, awaiting your decision; unrelated). TESTER_NOTE.md has one new line on tentative placements.

## Open
* Unread-part placements (1,076 cards rest only on them) are the weakest basis; an option is to hold them in a later version (791 cards would remain, 85.5% with tentative: 28,381 of 33,183).
* Copy and Cast remain unsplit (parser worklist); the Cast group is not promoted.
