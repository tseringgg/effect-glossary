# The "Loosely grouped" browse layer: build and checks

Built from `src/build_loose_groups.py` (field logic in `src/probe_loose_groups_v2.py`); outputs `build/loose_groups.json`, `build/loose_unread.json`; page changes in `reports/browse.html`; hand checks by `src/check_loose_groups.py`
(reads and results in `build/loose_groups_check_*.json`). Supersedes the numbers in `loose-groups-probe.md`. Limits are logged in KNOWN_LIMITATIONS.md §14. Nothing is committed.

## What was built

* Under "Not yet organized": a section **Loosely grouped by effect** (family, then group; every page and group says "Loosely grouped by effect. Not checked for accuracy.") and a list **Cards we couldn't read yet**.
* A card is listed under every group one of its abilities fits. Each row shows the ability's text and why it is not a real placement ("its shape is rare...", "the parser may have dropped a condition from it", "part of the ability was
  not read", ...). Groups are sorted most popular first.
* Find a card: a pile card resolves to its loose groups (same label, "still counted as not yet organized"); a card with no family resolves to the couldn't-read-yet list. The card page shows the same.
* The hide-no-picture switch also drops hidden cards from the layer's counts (4,293 -> 4,286 with the switch on).
* Not changed: the tree, leaves, leaf formation, the 5-member minimum, thresholds, placement rules, the parser, the headline.

## The groups (measured)

| | |
|---|---|
| Groups | 220: 195 plain groups, 23 "Less common effects, by kind" buckets (one per family), 2 labeled catch-alls over 100 cards |
| Size bands (cards) | under 10: 10 (all small family buckets) · 10-50: 199 · 51-100: 9 · over 100: 2 |
| Cards with a loose group | 4,293 of 5,593 |
| In a group of 100 or fewer | 4,120 · of 50 or fewer: 3,661 · only in the two groups over 100: 173 |
| Groups per card | average 1.14, maximum 4 |
| Cards with no usable ability ("couldn't read yet") | 1,300: 1,231 an unread part · 27 not parsed · 24 no effect to group · 9 text may be lost · 8 known parse mistake · 1 too unusual; 80 are in the top 3,000 |

Largest 15: Continuous effect on things, less common kinds 128 (catch-all) · Destroy, less common kinds 106 (catch-all) · Draw cards from a spell or activated ability 93 · Give things a gained effect, other kinds of target 75 ·
Sacrifice, less common kinds 70 · Static restriction, less common effects 66 · Attach to a creature 64 · Deal damage to a creature, from a spell or activated ability 56 · Game / player, less common effects 55 ·
Continuous effect on this permanent: adds power 54 · Counter a card 52 · Draw cards, on another kind of trigger 48 · Search a library, put it in hand 47 · Put counters, through a replacement effect, less common kinds 47 ·
A card with several modes 46.

Cards reached in one or two clicks: a pile card with a loose group is one click from the section (tree), two from its group; 4,120 sit in a group of 100 or fewer, so scanning the group is practical; 173 are in a catch-all of 106-128
cards whose sub-headings (by object type, or by what the effect does) split it into kinds. The 1,300 others are one click (the list), sorted by popularity. Measured: the counts. Estimate: the click paths follow from the tree.

## Catch-alls and buckets (what they hold)

* **Continuous effect on things, less common kinds (128):** sub-headings by what it does (adds a creature type 9, gives hexproof 8, adds a card type 8, gives double strike 7, ...), "Other kinds" 35.
* **Destroy, less common kinds (106):** sub-headings by object type (permanent 9, artifact or creature 8, enchantment 8, nonland permanent 7, ...), "Other kinds" 31.
* **23 family buckets** (66 static restrictions, 55 game and player effects, 35 other static rules, 35 counters, 31 library, 19 choices, 19 zone change, ...): sub-headings are the effect types with counts, most popular first;
  sub-headings under 3 cards fold into "Other kinds". Sub-headings are headings, not groups; no card has a new membership because of them.

## Hand checks (bars as written; none changed after the results)

* **Coherence, seed 20261017** (set before computing). Draw: every group over 100 cards (2 exist, not 10), 10 groups of 31-100 cards, 10 of the 23 buckets (the two catch-alls were already drawn) = **22 groups, not 30**.
  Reads written to `build/loose_groups_check_reads.json` before any name or key was looked at. **0 incoherent, 11 coherent, 11 loose.** Bar (more than 25% incoherent means stop) not tripped. One finding: group 10 (Attach) had 6 of 8
  member rows with no ability text; 227 of 4,905 member rows are like this (gap-card abilities with no rules line), shown as "(no separate rules line)". 22 groups cannot show a rate.
* **Names, seed 20261018** (set before computing): 40 names (15 of 10-30 cards, 15 of 31-100, 10 buckets or catch-alls), read from 6 members each, my own name written first. **0 misleading.** Three names (drawn as "Spells cost less, card",
  with "cards go to hand" repeated, and "cards go to the graveyard" repeated) had wording warts the automatic scan had not flagged; the wording rules were fixed and the three re-read before the verdict was written. 40 names cannot show a rate.
  The bar (more than 10% misleading) not tripped.
* **Name scan** over all 220 names: 0 hard defects, 0 claims hits, 0 over 110 characters (was 114 of 515 before the rework). The build also stops if two names are equal (an earlier draft had several such pairs that the scan did not see).
* **Independent of the generator:** the seeds, the member text (from the parse's own rules lines), the counts, the hashes, the reconciliation and the browser pass. **Not independent:** the reads and verdicts (same model wrote the wording and judged it).

## Verification (measured)

* Archive and every frozen file: hash list taken before Part 1 (484 files) and re-checked after: identical except `reports/browse.html`, `src/test_browse_browser.py`, `README.md` and `KNOWN_LIMITATIONS.md`, the files this work was meant to change. `git diff -- archive` empty.
* Reconciliation: placed 22,541 + broad only 3,254 + keyword 1,245 + no abilities 346 + replacement 204 + unorganized 5,593 = 33,183; + 5,738 not cards = **38,921**. 4,293 + 1,300 = 5,593 (each pile card counted once).
* Headline unchanged: **24,336 of 33,183 = 73.3%** (basis: placed by an ability in an unflagged leaf of 5 or more, plus the keyword block, "No abilities" and the replacement groups); **27,590 = 83.1%** with the broad groups.
  The archived card-level view's 74.8% is on a different basis.
* Two consecutive builds of `loose_groups.json` and `loose_unread.json`: byte-identical (sha1 equal).
* Headless Edge (`src/test_browse_browser.py`): **89 checks, 0 failed** (55 existing + 34 new). Covered: the section in the tree and its "not checked" label, open family, open group, each card showing its text and its reason,
  buckets and a catch-all with headings, the couldn't-read list (reason on every row, sorted by popularity), headline unchanged, Find a card (below), the card pages, the hide-switch counts. Not covered: layout on small screens,
  theme switching, scrolling performance.
* Find a card, by name in the page's search box: 5 loose-group cards (Loreseeker's Stone, Awakening, Herald of Ilharg, Thoughtbound Primoc, Finale of Promise) each resolve to their groups with the label; 5 no-family cards (Monomania,
  Wandering Eye, Bold Plagiarist, Wall of Diffusion, Djinn Illuminatus) each resolve to the couldn't-read-yet list; 5 placed cards (Dormant Sliver, Loyal Retainers, Silent Gravestone, Presence of Gond, Tamiyo Meets the Story Circle) show
  no loose-group text; 3 left-out cards (White Rhystic Study, Glorious Enforcer // Glorious Enforcer, Taught by Bruce Tarl) are answered as not cards in this tool.
* `test_abilityfind.py`: all pass. `check_tester_note.py`: one FAIL, the stale "suggestion links" bullet in TESTER_NOTE.md (known; decision pending, unrelated to this work).

## Not done / open

* Copy (spell vs ability) and Cast (source zone) cannot be split until the parser records them (parser-gap worklist).
* TESTER_NOTE.md is not updated for the new section.
* Names are generated and will read as slightly formulaic ("ones you control", "less common kinds"); they are labeled as not checked.
