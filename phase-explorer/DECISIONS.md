# Decision log

Newest first. Each entry records what was decided, the numbers it was decided
on, and what it does *not* establish.

> This file was started on `main` on 2026-09-24. An earlier decision log exists
> on the `archive/zone-choice-leaf-map` branch and was never merged here; it is
> not duplicated into this file.

---

## 2026-09-27 — Highlights narrowed to the effect that was actually matched

The highlight used to cover each ability's whole `description`. That is
phase.rs's granularity — they record text only at the top of an ability, never
per sub-effect — but it is wider than what was matched. The clustering reads the
top-level effect only (`node.effect`; sub-ability chains are not walked), so on
*Angrath's Fury* the match is `Destroy target creature.`, while the old
highlight also covered the damage, the tutor and the shuffle chained after it.

`src/effect_span.py` now cuts each located description down, in three steps:
the cost / trigger condition prefix (found by Oracle punctuation at quote and
paren depth 0, with the card's own name masked since names can hold commas);
trailing `Activate only…` restriction sentences; and chained sub-effects, cut at
the first clause that reads as a different effect in the chain.

**How "reads as an effect" is decided is learned, not hand-written.** A
vocabulary of effect words was exactly what was rejected for the leaf phrases,
so none is used here either. Instead, 33,320 unambiguous clauses (single-link
chains) teach each effect type its marker words by smoothed log-odds — with card
names excluded and a 3% support floor, both added after the first pass learned
`searing` and `bolt` for DealDamage from "Searing Spear deals…". The result is in
`build/effect_anchors.json`, readable. It only locates boundaries; the marked text
is always the card's own.

### Measured, not eyeballed

| | whole ability | narrowed |
|---|---|---|
| multi-effect abilities marking another effect's words | 8,677 | **1,998** |
| highlighted characters | 4.03 M | 2.46 M (61%) |
| narrowed spans still holding their own effect's words | — | **99.5%** |

Iterating against the misses found three real bugs, each fixed and re-measured:
commas inside card names ("Whenever *Ambergris, Agent of Tyranny* attacks,")
truncating the condition; leading durations ("Until end of turn,") being taken as
the whole effect; and "If you do" lead-ins attaching to the wrong side. A
positional fallback (one sentence per chain link → align by reading order)
covers sub-effects that are unmodelled and so have no learned words.

Also a tooling hazard worth recording: a regex `\b` written through a
shell-quoted Python string reached the file as a literal backspace byte,
silently disabling the "If you do" rule — no error, just a rule that never
matched. It had bitten once before in this work, in code since deleted. Regex-bearing code is now edited directly rather than through shell-quoted
Python strings.

### What this does NOT establish

- **It is still their attribution, narrowed.** Not a capture group; we have no
  access to their parser's spans.
- **1,998 multi-effect highlights still carry another effect's words** — mostly
  single clauses that genuinely mix two effects, or sub-effects the corpus has
  too few examples of. Where a boundary is not confident the text stays wider.
- **The leaf phrases are unchanged.** They are built from the same whole-ability
  descriptions and would benefit from the same narrowing (41 leaves are currently
  topped by a trigger-condition phrase), but it changes 141 of 591 top phrases,
  leaves one leaf with none, and makes some more faithful but less readable
  (`TargetOnly` leaves read `Choose target spell`). A separate decision.

Artifacts: `src/effect_span.py` · `src/match_spans.py` ·
`build/effect_anchors.json` · `reports/cardview.js`

---

## 2026-09-27 — Card images: the first thing here that leaves the machine

A **card images** view toggle on the browse page, backed by
`src/build_images.py`. This is worth a decision entry mainly because of what it
changes about the project, not because the grid is hard.

### It breaks the offline property, deliberately and narrowly

Every page here has been a read-only consumer of one local snapshot: after the
build, nothing talked to anything. Images cannot work that way — 33,618 card
images are gigabytes, so they are loaded from Scryfall's CDN as you scroll.

The containment: the view is **opt-in** (a toggle, text stays the default), it is
**hidden entirely** unless `build_images.py` has been run, and it is the only
feature that does this. The view's own note says so on screen rather than leaving
it to be discovered in devtools. Everything else — tree, filters, phrases,
highlighting, parsed structure — still works with no network at all.

### The join, and the number the scoping could not settle

`oracle_cards` bulk (~25 MB, gitignored, fetched once) rather than per-card API
calls, which is what Scryfall asks programs to do.

**33,618 of 33,834 oracle ids matched — 99.4%.** The scoping flagged Alchemy
`A-` cards as an unknown risk; the bulk join answered it exactly: **all 216
misses are Alchemy cards and nothing else.** They are digital-only and absent
from that export. They keep their slot in the grid as a tile that says why,
rather than being skipped into a gap that looks like a bug.

### Two small things worth keeping

- **URLs are stored as a template plus parts**, not 33,618 full strings — 3.1 MB
  instead of ~9 MB, and the page can pick a size.
- **The template is verified during the build**, by rebuilding Scryfall's own
  `image_uris` from it and comparing. All 33,618 matched. If their URL shape ever
  changes the run exits rather than writing a file of 404s — the failure would
  otherwise show up as silently blank tiles much later.

Their manifest had already moved from a plain-JSON `download_uri` to a gzipped
JSONL `jsonl_download_uri` since the format this was first written against, which
is precisely the kind of drift that check exists for. Reading it as streamed JSONL
also means the export is never held in memory.

### What this does NOT establish

- **It is not a local cache.** Browsing images needs network every time; nothing
  is stored. A card whose image fails to load shows a blank tile, not an error.
- **99.4% is a join rate, not a correctness claim.** It says an oracle id was
  found in their export, not that the printing shown is the one you would expect
  — `oracle_cards` picks one printing per oracle id, and which one is their call.
- **The audit page has no image view.** It is the parse-audit tool and stays
  text-only.

Artifacts: `src/build_images.py` · `build/card_images.json` ·
`reports/cardview.js` · [`reports/browse.html`](reports/browse.html)

---

## 2026-09-27 — Showing what the parser consumed, and letting a phrase be overridden

Two features, plus a reproducibility bug found while building them.

### Highlighting the matched clause

Every parsed node carries a `description`: phase.rs's own record of which clause
it matched that node from. `src/match_spans.py` locates that clause back inside
the card's oracle text and stores the character range, so both pages can mark it.

**This is their attribution, not a capture group.** We do not have their regexes.
The scoping request was to "show which part the regex matched" — what is
actually available is the text they say a node came from, which is close but not
the same claim, and the pages say so.

Measured over the whole corpus, 47,971 nodes:

| | |
|---|---|
| located in the card's text | **90.6%** |
| no `description` at all | 6.3% |
| description is not card text (`Chapter 1`, `CR 702.104a: …`) | 3.1% |

The only normalisation is `~`, their self-reference token, against oracle text
that spells it "This creature". No case folding beyond one retry, no whitespace
repair, no fuzzy matching — a clause that cannot be found is counted and left
unhighlighted rather than approximated onto nearby words.

**The unhighlighted text turned out to be the interesting half.** Reminder text
and keyword definitions stay plain, so the parser can be watched walking past
`Deathtouch (Any amount of damage this deals to a creature is enough to destroy
it.)` and matching only `When this creature enters, destroy target artifact,
enchantment, or land.`

### Overriding a leaf's phrase

`/api/phrase` on `serve.py` writes `corrections/leaf_phrases.json`;
`leaf_phrases.py` reads it back, so an edit survives a rebuild and appears in the
report as *(edited by hand)*. This is the review queue's existing shape — dev-only,
127.0.0.1, a file rather than browser storage precisely so the build can see it.

Overrides are **free text**, by request. That breaks the "verbatim, never our
wording" property the phrases were built on, which is a fair trade when it is the
editor's deliberate choice — but it is not hidden: the phrase carries an `edited`
chip, the tree row is rule-marked, and the derived phrase stays on screen
underneath it, so what was replaced is always visible and one click from being
restored.

Saving updates only the affected rows rather than re-rendering the tree, which
would collapse every open sector for a one-line edit.

### The bug: the build was not reproducible

Two runs of `leaf_phrases.py` over identical input produced different files.
Cause: `dominant_effect()` fed a `Counter` from a `set` of effect-name strings,
and set iteration order for strings changes with every process under hash
randomisation. `Counter.most_common()` breaks ties by insertion order, so a leaf
whose top two effects were tied could get a different dominant effect — and
therefore a different phrase — on each rebuild.

Fixed by making every tie-break explicit (`(-count, name)`) rather than relying
on insertion order, in both the dominant-effect choice and the literal-form
choice. Three consecutive runs now produce byte-identical output. Worth recording
because nothing about the output *looked* wrong — the phrases were plausible
either way, and only hashing two builds caught it.

### What this does NOT establish

- **90.6% is not a verdict on the parse.** It measures how often their own
  attribution can be found in their own text, nothing about whether the node is
  correct.
- **An unhighlighted clause is not proof the parser ignored it.** It may have
  been matched by a node whose description is missing (6.3%) or synthetic (3.1%).
  The expanded detail lists both cases per card rather than leaving the gap to be
  read as intent.
- **An override says nothing about the cards.** It is one person's label for a
  leaf, recorded as such.

Artifacts: `src/match_spans.py` · `build/match_spans.json` ·
`corrections/leaf_phrases.json` · `src/serve.py` · `src/leaf_phrases.py` ·
`reports/cardview.js` · [`reports/browse.html`](reports/browse.html) ·
[`reports/card-explorer.html`](reports/card-explorer.html)

---

## 2026-09-26 — The card-type layer is gone; the filter already does it

The tree was sector → branch → **type sub-branch** → leaf. The middle level is
removed: a branch now opens straight to its leaves.

The reasoning is that the layer duplicated a control that already exists. The
card list carries a **card-type filter** that works on any scope — a sector, a
branch, an effect group, a single leaf — and it is computed live from the cards
on screen. A fixed type level in the tree does the same cut in one place only,
at one fixed depth, and costs a level of nesting on every branch to do it. That
includes the Ramp → Mana dork / Mana rock split, which is a real distinction in
the game and still not worth a tree level: filtering Ramp to `Creature` gives
the dorks, `Artifact` gives the rocks.

### What changed with it

- **Effect groups moved up a level.** They used to be computed inside each type
  sub-branch; now they sit on the branch and cover all of it. Spot removal's
  Destroy group went from 270 cards (the Creature slice) to **831** (the whole
  branch), which is the number the branch's own sibling actually holds.
- **Leaves are listed directly under their branch.** Spot removal shows its 113
  leaves rather than hiding them behind six type folders.
- **A leaf's pick key carries the branch it was clicked from**, purely so the
  breadcrumb reads `Removal › Spot removal › leaf 299`. The card set is
  unchanged — leaves are many-to-many with branches, and the readout still says
  when a leaf sits under more than one.
- The same layer was removed from the audit page, so the two do not disagree
  about what the tree is.

### What this does NOT change

- **The type-mixing finding stands, and is still on screen.** The 74
  heterogeneous leaves keep their `mixed types` chip and their shares; leaf 44
  is still 513 cards at Creature 44% / Land 30% / Artifact 28%. What is gone is
  a layer that *organised* that mixing without fixing it — the previous entry on
  sub-branches said as much at the time.
- **`src/sub_branches.py` and `reports/sub-branches.md` are kept.** The analysis
  (89 typed sub-branches, 0 type-heterogeneous under the same test) is a real
  result and stays recorded. Nothing reads `build/sub_branches.json` any more,
  and the README says so rather than leaving it looking live.
- **The standalone `Mana dork` and `Mana rock` branches are untouched.** They
  come from the curated glossary vocabulary in `branch_leaves.py`, not from the
  type split, and they remain their own branches.

Artifacts: [`reports/browse.html`](reports/browse.html) ·
[`reports/card-explorer.html`](reports/card-explorer.html)

---

## 2026-09-26 — The phrase must come from the clause the parser matched

A leaf row now reads:

```
leaf 453 · 117 cards
Destroy target creature
```

The phrase is verbatim card text. Getting it right took two corrections, both
of which are the point of this entry.

**First correction: no descriptions.** The first version wrote a plain-English
*description* of the structural facts, generated from the enum names
("destroys target creature"). That was our prose dressed as the card's. It was
rejected, and the glosser plus its ~230 lines of vocabulary tables were
deleted rather than left switched off.

**Second correction: not the whole card.** The replacement scanned each card's
full oracle text for the most common shared wording — literal, but wrong in a
way that is worth recording. The most common phrase on a card is frequently
unrelated boilerplate. A leaf clustered on `eff:PutCounterAll` reported *"You
may cast this card face down as a 2/2 creature for"*, because every card in it
happened to be a megamorph Dragon. Literally true, and nothing to do with why
those cards are in that leaf.

The fix is not a heuristic. Each parsed node carries a `description` — phase.rs's
own record of which clause it matched that node from. `leaf_phrases.py` now
imports `cluster_structural.effect_features()` (the same function that formed
the leaves) to find the nodes whose effect type IS the leaf's dominant effect,
and reads only those descriptions. The phrase can only come from the clause the
parser matched. That leaf now reads *"When this creature is turned face up, put
a +1/+1 counter on"*.

| | whole oracle text | matched clause only |
|---|---|---|
| leaf 11 (`PutCounterAll`) | "You may cast this card face down as a 2/2 creature for" | "When this creature is turned face up, put a +1/+1 counter on" |
| leaves with a shared phrase | 591 | 579 |
| top phrase in ≥50% of the leaf | 481 | 432 |

Both numbers going **down** is the correct direction: the smaller corpus is the
relevant one, and 932 cards match their leaf's effect in a node carrying no
description at all, so they now contribute nothing rather than contributing
irrelevant text.

### The scoring, and what was tried against it

The winner maximises `share × phrase_length`. Two alternatives were tested on
the same leaves and both are worse:

- **Anchoring to the start of the matched clause** (to favour the effect's own
  verb) helps pump leaves but wrecks triggered abilities, where the clause
  starts with the trigger: leaf 32 goes from "draw a card" (60%) to "When this
  creature" (16%).
- **Cross-leaf dampening** (downweighting phrases common to many leaves) fixes
  the same pump leaves and costs far more elsewhere: leaf 426 drops from
  "Counter target spell" at 99% to "Counter target spell unless its controller
  pays" at 39%.

### What this does NOT establish

- **The phrase is not a definition of the leaf.** 18 leaves report *"until end
  of turn"*, because on a Pump card that genuinely is the most common wording
  inside the matched clause. It is the duration, not the effect — the duration
  is a separate parsed field, and there is no way to exclude it without the
  vocabulary this pass exists to avoid. Left as is, and recorded here.
- **432 of 591 leaves have a top phrase in half their cards or more.** The rest
  are weaker, and the number is in `reports/leaf-phrases.md` rather than being
  implied away by showing the phrase alone.
- **It says nothing about whether the parse is right.** It reports which text
  phase.rs attributed to a node, taking that attribution at face value.

### Row behaviour

The whole leaf row is the click target (previously only the number was), with
hover and selected states, `role="button"`, `tabindex`, and Enter/Space
handling. One phrase, on its own line under the count; no quotes, no percentage
— the count and share stayed, on the selected-leaf readout and in the report,
where there is room to read them.

Artifacts: `src/leaf_phrases.py` · `build/leaf_phrases.json` ·
[`reports/leaf-phrases.md`](reports/leaf-phrases.md) ·
[`reports/browse.html`](reports/browse.html) ·
[`reports/card-explorer.html`](reports/card-explorer.html)

---

## 2026-09-25 — A bare `Non` in the clustering feature space

Found while working on leaf wording, and independent of how it is displayed.
`shape_tag()` folds a scalar payload into its tag (`{"Non": "Artifact"}` →
`Non:Artifact`), but a **nested** one has nowhere to go, so
`{"Non": {"Subtype": "Zombie"}}` collapses to a bare `Non` and the excluded
subtype is lost. Six leaves carry `Typed[Creature,Non]` as a result, and in
leaf 111 *Cruel Revival* (non-Zombie) and *Eyeblight's Ending* (non-Elf) are
genuinely indistinguishable in that feature space. Fixing it means changing
`shape_tag`, which changes the feature space and invalidates every leaf id.
Not taken; recorded.

---

## 2026-09-25 — Two more nav layers: sectors on top, effect groups underneath

Two additions to `reports/browse.html`, both reusing data that already
existed — `build/sectors.json` (`src/build_sectors.py`) for the top, and
branches.json's own leaf lists for the new bottom layer. Neither runs a new
clustering pass or writes a new build file; both are computed client-side at
page load.

**Sectors are now the top level.** The tree was branch → sub-branch → leaf;
it is now sector → branch → sub-branch → leaf. A sector groups branches only
(it contributes no leaf of its own), so a branch's own content is identical
whichever way it's reached. 28 of 64 branches sit in one of the 8 sectors;
the other 36 — including some big, well-known ones (Card draw, Token maker,
Reanimation, Lifegain, the Ramp/Land-ramp/Mana-dork family) — are under
**Unsectored branches**, with `sectors.json`'s own `unsectored_notes`
surfaced there rather than silently dropped: e.g. Reanimation sits closer to
the Removal cluster (0.49–0.60x) than to Graveyard hate (0.77x), so filing it
under either would misstate the map. Clicking a sector loads the union of
its branches' cards, same many-to-many caveat as everywhere else (cards
don't sum across branches within a sector any more than across branches
generally).

**Effect groups are a new bottom layer** — nested inside a branch's type
sub-branch when it has one (matching the user's own framing: *"within Spot
removal (Creature), group again by whether it's Destroy, Bounce, or
Sacrifice"*), directly under the branch when it doesn't. A group is one of
the branch's own **sector siblings** — e.g. Destroy/Bounce/Sacrifice/Exile
removal are Spot removal's siblings in the Removal sector — intersected live
against whatever cards are already on screen. No new rule, no new leaf: this
surfaces branch membership `branch_leaves.py` already computed, the same way
the type sub-branch layer surfaces `card_type`.

A sibling only qualifies if it clears two checks, both computed once at
boot, not hand-picked:
1. **It must itself be a near-full subset (≥85% of its own leaves) of some
   OTHER branch in the same sector.** This is what keeps "Spot removal"
   itself off the sibling list for its own children — nothing else in the
   sector contains Spot removal, so it fails the test, correctly, and
   doesn't loop back on itself as a spurious "100% overlap" group. The bug
   this test fixes was caught only by an end-to-end run: without it, every
   type sub-branch across the Removal sector picked up a "Spot removal:
   ~100%" group that added nothing.
2. **Its rule must name an effect, not a different axis riding the same
   sector.** `Typed[...]` is a target-type filter — Creature removal is
   "which of Spot removal's targets are creatures," not a removal
   *mechanism* — and `controller scope` is a who-it-affects filter
   (One-sided sweeper). Both fail this check and are correctly excluded,
   which is also why Creature removal's own type sub-branches get an effect
   layer (Destroy/Bounce/Sacrifice, live-intersected against *that* card set)
   while Creature removal the branch does not: it isn't itself a sector
   subset-qualifying sibling, so it never appears as someone else's "effect."

Verified numbers: Spot removal (Creature) — 1,202 cards — splits into Bounce
347 / Sacrifice 284 / Destroy 270 / Exile 218 / **other 83** (sums to 1,202;
`other` is real — mostly the Fight-effect leaves Spot removal's own rule
names but no branch was ever curated for). Creature removal (Creature) — 272
cards — splits into Bounce 106 / Sacrifice 80 / Destroy 71 / **other 15**
(Exile removal has zero overlap here — not an omission, its own leaves never
bind to a creature-typed target in this parse). Mass effect, which has no
type split, gets the layer directly on the branch: Board wipe 332 / Mass
+1/+1 counters 91 / other 438. Every count cross-checked against an
independent Python pass over the same build files.

### What this does NOT establish

- **It does not establish that every branch has an effect breakdown.** Most
  don't — the sector-subset test is a real filter, not a formality; outside
  Removal and Mass Effects, no sector currently produces a subset relation at
  all, so e.g. Tutor / Impulse / Copy spell (Resource Acquisition) show no
  effect layer, which is correct: nothing there is a subset of anything else
  in that sector.
- **It does not establish that "other" is small or unimportant.** 83 of 1,202
  Spot-removal-Creature cards and 438 of 861 Mass-effect cards land in
  "other" — the layer surfaces what the sector's OWN curated branches already
  cover, nothing more, and says so on the card list itself.
- **It does not change what a sector or branch contains.** Both come
  straight from files already built and already documented in
  `reports/sectors.md` / `reports/branches.md`; this pass only changed how
  they're reached.

Artifacts: [`reports/browse.html`](reports/browse.html) (no new build file;
`build/sectors.json` was already built by `src/build_sectors.py`)

---

## 2026-09-25 — Browsing page: an assembly pass, and what it did not change

`reports/browse.html` makes the tree the way in — branch → sub-branch → leaf →
filtered card list — and demotes the treemap to a collapsed secondary overview.
Nothing about the data changed: every set it shows is a lookup or a set
intersection over `build/clusters.json`, `build/branches.json` and
`build/sub_branches.json`. No leaf was re-clustered, no branch re-assigned, and
the review queue was not touched.

Card rendering moved into `reports/cardview.js` and the treemap into
`reports/branchmap.js`, both now shared with `card-explorer.html`, which lost its
inline copies (−11 KB). Each page injects its own extras through the modules'
`opts` hooks. One side effect of the extraction: clicking an **auto-named**
region in the treemap now opens that branch in the tree. It never did before —
the region's `data-b` carried the ` · auto` suffix and the tree's `data-branch`
did not, so the lookup silently missed on all 23 of them.

### The three filters, and the two judgement calls in them

Colour, card type and mana value, all read off `col` / `mv` / `cty` added to the
existing index rows by `build_index.py` — from the snapshot's own `mana_cost`,
`color_override` and `card_type`. No new input file, no second pass.

- **Colour comes from `color_override` first, the mana cost second.** 3,202
  entries carry an override and **541 of those disagree with their cost**: back
  faces with a colour indicator but no cost (70 red, 69 green, …), and devoid
  cards with coloured pips that are colourless (35 blue, 32 black, …). Deriving
  colour from the cost alone mis-colours every one of them.
- **A face with no mana cost is its own state (`—`), not mana value 0.** 2,368
  entries have no cost at all — 1,248 lands, 509 with no core type, 265
  creatures, mostly back faces and tokens. Folding them into the 0 bucket would
  take it from 19 cards to 2,387 and fill it with cards that cannot be cast. A
  mana-value **range** therefore excludes them, and the control says so rather
  than silently dropping them.

Range was chosen over an exact value because the distribution is a long right
tail (0–16, plus *Gleemax* at 1,000,000) and "3 or less" is the question a player
actually asks; one click on a histogram bar still gives an exact value.

### What this does NOT establish

- **It does not establish that the corpus is browsable.** The tree sits on a
  clean-parse-only clustering pass: **11,087 of 34,645 entries have no leaf** and
  appear nowhere in it. The page states this above the tree; it is not fixed.
- **It does not fix the type mixing.** The 74 heterogeneous leaves are now
  *marked* `mixed types` with their shares, which is the previous entry's finding
  made visible — not resolved. Leaf 44 is still 513 cards at Creature 44% / Land
  30% / Artifact 28%.
- **It does not resolve anything in the review queue.** The 79 open items are
  unchanged; their leaves are marked `in review` and left browsable.
- **The filters are not verified against Scryfall.** They are faithful to the
  snapshot's fields, and the snapshot's parses are unverified — the same caveat
  as everywhere else in this project.

Verified end-to-end by driving the real page in headless Chrome: branch → sub-
branch → leaf → filters → card detail → pagination, with every filter count
cross-checked against an independent Python pass over the same build files
(Ramp 1,269 cards; + green 179; + green and Land 1, *Dryad Arbor*; Burn mana
value 1–2 485, exactly 3 296, + red 209, mono-red only 180; Land ramp ∩ leaf 555
= 257).

Artifacts: [`reports/browse.html`](reports/browse.html) ·
`reports/cardview.js` · `reports/branchmap.js` · `src/build_index.py`

---

## 2026-09-24 — Type sub-branches: the mixing is hidden, not fixed

Sub-branches make the browsing experience look clean, but the underlying
leaf-level mixing — **74 leaves / 2,784 cards** from the type audit — is
unchanged: it is hidden from the user, not fixed. **Ramp** is the one branch
where this pass happened to be complete (100% of its exposure was tier A);
**Burn** and **Tutor** are still mostly tier-B exposure and were not addressed
by this pass.

### The numbers behind it

| | leaf-level exposure | tier A (addressed) | tier B (untouched) |
|---|---|---|---|
| Ramp | 49% | 49% | 0% |
| Tutor | 51% | 12% | 38% |
| Burn | 46% | 11% | 35% |

The sub-branch layer verifies clean — 89 typed sub-branches, **0** still
type-heterogeneous under the identical 50% test. That is a real result about
the *containers*, and only about the containers.

### What this does NOT establish

- **It does not establish that the leaves were fixed.** Nothing was
  re-clustered. Leaf 44 is still 513 cards at Creature 44% / Land 30% /
  Artifact 28%, and `reports/leaf-type-audit.md` still reports all 74 leaves.
- **It does not establish that Burn and Tutor are resolved.** Their queue
  entries for leaves 567 and 374 were recorded as `split` to make the queue
  reflect reality, since their parents were split via other tier-A leaves — but
  no tier-B work was done, and their tier-B exposure (35% / 38%) stands.
- **"Exposure dropped to 0%" is only true of the sub-branch layer.** Saying it
  of the branch would be measuring one layer and naming another.

Removing the mixing at its source means re-clustering with card type in the
feature set, which invalidates every leaf id, branch assignment, both leaf maps
and the sector geometry. That decision has not been taken.

Artifacts: [`reports/sub-branches.md`](reports/sub-branches.md) ·
[`reports/leaf-type-audit.md`](reports/leaf-type-audit.md) ·
`src/sub_branches.py` · `src/audit_leaf_types.py`
