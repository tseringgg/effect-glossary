# phase.rs Card Data Explorer

Dev-only tool for inspecting phase.rs's **static parsed** MTG card data. Read-only
consumer of their snapshot — it does not run their rules engine or game logic, and
does not touch their repo.

## Run

```
python src/build_index.py         # -> build/index.json, facets.json, meta.json, chunks/
python src/build_collisions.py    # -> NAME_COLLISIONS.md, build/collisions.json
python src/cluster_structural.py  # -> build/clusters.json, reports/clustering-structural.md
python src/branch_leaves.py       # -> build/branches.json, reports/branches.md
python src/sub_branches.py        # -> build/sub_branches.json (analysis only, not read by the pages)
python src/audit_leaf_types.py    # -> build/type_audit.json, reports/leaf-type-audit.md
python src/leaf_phrases.py        # -> build/leaf_phrases.json, reports/leaf-phrases.md
python src/match_spans.py         # -> build/match_spans.json, build/effect_anchors.json
python src/build_images.py        # -> build/card_images.json  (downloads ~25 MB from Scryfall)
python src/build_ledger.py        # -> build/ledger.json, reports/coverage-ledger.md
python src/recover_dropped.py     # -> data/overlay/recovered-cards.json (needs oracle-gen, see below)
python src/add_new_release_cards.py  # -> data/overlay/new-release-cards.json: cards released after the snapshot
                                    #    (needs oracle-gen and data/AtomicCards-20261003.json.gz; gate-checked, oracle-id keyed)
python src/build_placements.py    # -> build/placements.json
python src/build_keyword_layer.py # -> build/keyword_layer.json: keyword-only cards, placed by rule (kw:<signature>)
python src/build_ledger.py        # again: adds each card's placement
python src/build_also_fits.py     # -> build/also_fits.json: per-ability "also fits" suggestions (display only; reads the probe's scorer)
python src/build_keyword_layer.py   # (also takes recovered keyword-only cards)
python src/build_partial_ability_layer.py  # -> build/partial_ability_layer.json (gap cards placed by one ability)
python src/build_signature_layer.py  # -> build/signature_layer.json (replacement-effect groups; newer vanilla cards)
python src/build_ability_layer.py  # -> build/ability_layer.json (cards placed by one ability), build/ability_ledger.json; then rerun build_ledger.py
python src/build_unorganized.py   # -> build/unorganized*.json, build/lookup.json: "Not yet organized" groups + Find a card (display only)
python src/serve.py               # opens http://localhost:8765/reports/browse.html
```

The ledger runs twice because placement reads the ledger's statuses and the
ledger then records placement; placement never feeds back into a status.

`cluster_structural.py` is optional — the audit page works without it and simply
shows no cluster column. Requires `hdbscan`, `numpy`, `scipy`. `audit_leaf_types.py`
supplies the `mixed types` marks and is optional, as is
`leaf_phrases.py` — without it a leaf row falls back to its raw structural label.
`sub_branches.py` is no longer read by either page; it is kept for its report.
`match_spans.py` is optional too — without it the oracle text renders unhighlighted —
as is `build_images.py`, without which the card-image view is hidden entirely.

The page must be served over HTTP; it fetches JSON, which `file://` forbids.

## Inputs (gitignored, re-fetch as needed)

| file | size | purpose |
|---|---|---|
| `data/card-data.json` | 83 MB | the snapshot under inspection |
| `data/AtomicCards.json.gz` | 52 MB | MTGJSON reference, only for collision detection |
| `data/scryfall-oracle-cards.jsonl.gz` | 25 MB | Scryfall reference: image join, out-of-scope ids |
| `data/scryfall-default-cards.jsonl.gz` | — | Scryfall `default_cards` bulk export: first-printing dates for the ledger and NAME_COLLISIONS.md (URL from `https://api.scryfall.com/bulk-data/default-cards`) |

```
curl -o data/card-data.json     https://data.phase-rs.dev/card-data.json
curl -o data/AtomicCards.json.gz https://mtgjson.com/api/v5/AtomicCards.json.gz
# the Scryfall export is fetched by the script itself:
python src/build_images.py --refresh
```

## Coverage ledger (reports/ledger.html)

One row per oracle id in the card universe — MTGJSON AtomicCards plus
Scryfall-only ids — with exactly one status (`clustered`, `noise`, `partial`,
`unparsed`, `missing_from_export`, `out_of_scope`, …), a reason code and the
evidence behind it. Exclusivity is computed, not assumed: pairwise
intersections, sum = universe, and reconciliation against the counts earlier
passes produced. The page filters by status, reason and placement, searches by
name or oracle id, ranks gap causes (which `Unimplemented`/`GenericEffect`
fragments cost the most cards), and shows each card's raw evidence and parse.
Out of scope: tokens, art series, emblems and other non-cards, plus planes,
schemes and vanguards (deferred to a separate pass).

**Recovery.** `src/recover_dropped.py` regenerates the 63 collision-dropped
cards with phase-rs `oracle-gen` at v0.1.15 — the snapshot's own release —
one card per run so nothing can collide. It first proves parser parity: the
same binary must reproduce every comparable snapshot entry byte-for-byte, or
nothing is written. Building it on Windows: rustup with
`--default-host x86_64-pc-windows-gnu`, toolchain `nightly-2026-04-19` (the
tag's `rust-toolchain.toml`), then
`cargo +nightly-2026-04-19 build --profile tool --bin oracle-gen --features cli -p engine`.
Without MSVC the bundled `dlltool` needs an assembler: pass
`RUSTFLAGS=-Cdlltool=<wrapper>` where the wrapper calls the bundled
`dlltool.exe -S <path to as.exe>` (any MinGW-w64 binutils `as.exe`). Point
`PHASE_ORACLE_GEN` at the built binary.

**Placement.** `src/build_placements.py` places `noise` cards and recovered
clean parses at the nearest leaf centroid in the clustering's own feature space
(cosine ≥ 0.80), and `vanilla` cards under "No abilities". It is a separate
layer: centroids come from clustered members only, and no leaf, branch, sector,
map or cohesion number changes. Browse shows those cards with a dashed
`nearby` chip and a separate "+N nearby" count, and can hide them.

## Two pages

| page | for | entry point |
|---|---|---|
| `reports/browse.html` | **reading the glossary** — sector → branch → leaf → filtered card list | what `serve.py` opens |
| `reports/card-explorer.html` | **auditing the parse** — quality split, slot-aware facets, corrections overlay | linked from the header |

Both render cards with the same code: `reports/cardview.js` holds the escaper, the
chunk loader, the card row and the parsed-structure detail view, and
`reports/branchmap.js` holds the treemap. Each page passes its own extras through
those modules' `opts` hooks rather than forking a second renderer — the audit page
injects its cluster box, the browse page injects a branch/leaf provenance box.

## Browsing (reports/browse.html)

The tree is the primary navigation, four layers deep at most:

**sector → branch → (effect group →) leaf**

- **Sector** (`build/sectors.json`, from `src/build_sectors.py`) is the top level —
  bigger structural neighbourhoods the leaf-similarity map found among branches,
  tier 1 the tighter ones. A sector groups branches only; it adds no leaf of its
  own, so a branch reads identically whichever way it's reached. 28 of 64 branches
  sit in a sector; the other 36 sit under **Unsectored branches**, together with the
  map's own documented reasons for leaving each one out (e.g. Reanimation sits
  closer to Removal than to Graveyard hate on the map, so filing it under either
  would misstate it) — surfaced, not dropped.
- **Branch**, sorted by card count within its sector, opens straight to its
  leaves. It used to split by card type first (Ramp → Land ramp / Mana dork /
  Mana rock); that layer was removed because the card-type filter on the card
  list does the same cut on demand, across any scope, without a fixed extra
  level in the tree. `src/sub_branches.py` and
  [reports/sub-branches.md](reports/sub-branches.md) remain as the record of
  that analysis — nothing reads them.
- **Effect group** is a second axis nested one level deeper: a branch's own
  **sector siblings** — e.g. Destroy / Bounce / Sacrifice / Exile removal are Spot
  removal's siblings in the Removal sector — intersected live against the branch's
  cards. A sibling qualifies only if (1) it is
  itself a near-full subset of some *other* branch in the sector — what keeps the
  umbrella branch itself (Spot removal, Mass effect) off its own children's sibling
  list — and (2) its rule names an effect, not a target-type or controller-scope
  axis riding the same sector (which is why Creature removal and One-sided sweeper
  are correctly excluded). Cards matching none of a scope's siblings land in an
  **other** bucket, shown alongside the named groups, never folded in or dropped.
- **Leaf** is one clickable row: the leaf number and card count, and under it on
  its own line, `Destroy target creature` — verbatim card text, not a description.
  It comes from `src/leaf_phrases.py`, which reads only the `description` of the
  parsed nodes whose effect **is** that leaf's dominant effect, found with
  `cluster_structural.effect_features()` — the same function that formed the leaf.
  So the phrase can only come from the clause the parser actually matched, not from
  unrelated boilerplate elsewhere on the card. The share is on the selected-leaf
  readout and in [reports/leaf-phrases.md](reports/leaf-phrases.md); the raw
  structural label is the row's tooltip. Clicking any node above a leaf lists every
  card under it, so the filters below work across a whole sector, branch, type or
  effect group, not just inside one leaf.

Every layer past sector→branch is a lookup or a live set intersection over data
`branch_leaves.py` and `build_sectors.py` already computed — no new rule, no new
clustering, no new build file for either sectors or effect groups.

**Filters — colour, card type, mana value.** All three read off fields the index
rows already carry (`col`, `mv`, `cty`), derived in `build_index.py` from the
snapshot's own `mana_cost`, `color_override` and `card_type`. No second pipeline,
and no new input.

- **Colour** — `W U B R G` plus colourless, as *any of* or *exactly these*. Sourced
  from `color_override` where the snapshot carries one, else from the mana cost's
  shards. The override is authoritative: 3,202 entries have one and 541 of those
  disagree with their cost (back faces with a colour indicator but no cost; devoid
  cards with coloured pips that are colourless). Reading the cost alone mis-colours
  every one of them.
- **Card type** — the `core_types` present in the current list, with counts.
- **Mana value** — a min/max **range**, with one click on a histogram bar for an
  exact value. Range is the natural control here: the distribution is a long right
  tail and "3 or less" is a question players actually ask. `X` counts 0 and a
  `Two<Colour>` hybrid pip counts 2. **A face with no mana cost is its own state
  (`—`), never mana value 0** — 2,368 entries (back faces, tokens, most lands)
  cannot be cast at all, and folding them into the 0 bucket would pad it with cards
  that have no mana value. A range therefore excludes them, and the control says so.

Option counts are computed over the current list, not the corpus, so each control
shows what it would actually yield here.

### What the parser matched, inside the card's own text

**highlight what the parser matched** (header toggle) marks, in the oracle text,
exactly the effect each ability was matched on — not the whole ability. On
*Angrath's Fury* only `Destroy target creature.` is marked; the damage, tutor and
shuffle that follow on the same line are sub-effects the clustering never read.

Two steps in `src/match_spans.py`:

1. **Locate.** Every ability carries a `description` — phase.rs's record of which
   text it came from — found verbatim in the card's oracle text. 90.6% are
   located; 6.3% have no description and 3.1% name something that isn't card text
   (a Saga's `Chapter 1`). Those are counted, never approximated.
2. **Narrow** (`src/effect_span.py`). A description is the whole ability, but the
   clustering reads only the top-level effect (`node.effect`; sub-ability chains
   are not walked). So the cost (`{2}, {T}, Sacrifice this artifact:`), the trigger
   condition (`Whenever you cast an instant, sorcery, or artifact spell,`),
   trailing `Activate only…` restrictions, and every chained sub-effect are cut
   off. Sub-effects are cut at the first clause that reads as a *different* effect
   in the chain — which words mark which effect is **learned from the corpus**
   (33,320 unambiguous single-effect clauses, card names excluded), written to
   `build/effect_anchors.json` so it can be checked, and never displayed.

Measured against the old whole-ability highlight: multi-effect abilities whose
highlight contained another effect's words fell from 8,677 to 1,998, highlighted
text fell to 61%, and 99.5% of narrowed spans still contain their own effect's
words — the cut almost never removes what was matched. Where a boundary can't be
found confidently the text is left wider rather than guessed narrower.

Expanding a card lists each ability's full description, so what was trimmed is
always visible next to what was marked.

### Card images

**card images** (view toggle above the card list) swaps the text table for a grid
of card images. This is **the only part of these pages that reaches outside the
machine** — images come from Scryfall's CDN, lazily, as you scroll. Everything
else still works with no network at all, and the view is hidden unless
`build_images.py` has been run.

`src/build_images.py` downloads Scryfall's `oracle_cards` bulk export (~25 MB,
gitignored, fetched once) and joins it on `scryfall_oracle_id`. Bulk rather than
per-card API calls is what Scryfall asks programs to do. The output stores a URL
*template* plus each card's Scryfall id, not 33,618 full strings, and the build
**verifies that template against Scryfall's own `image_uris`** — if their URL shape
changes, the run fails instead of writing a file of 404s.

**33,618 of 33,834 oracle ids (99.4%) have an image.** Every one of the 216 misses
is an Alchemy `A-` card: those are digital-only and absent from the oracle export.
They keep their place in the grid as a tile saying so, rather than being skipped.
(Scryfall's larger `default_cards` export carries them if they are ever wanted.)
Clicking any card opens the same parsed-structure view the text rows use.

### Editing a leaf's phrase

The phrase a leaf is labelled by is derived, and sometimes the derived one is the
wrong one to lead with. Select a leaf and hit **edit**: the page POSTs to
`/api/phrase` on `src/serve.py`, which writes `corrections/leaf_phrases.json`.
`leaf_phrases.py` reads that back, so an override survives a rebuild and shows up
in the report marked *(edited by hand)*. Clearing the box drops the override.

An override is free text — your wording, not the cards' — so it carries an
`edited` chip, the tree row is rule-marked, and the derived phrase stays visible
underneath it. Same shape as the review queue: dev-only, bound to 127.0.0.1, and a
file rather than browser storage so the build can read the decision back.

The **branch map** is a secondary overview behind a toggle, collapsed by default. It
renders no cards; clicking a region opens that branch in the tree.

### What browsing cannot reach, stated on the page

The branch layer sits on a clean-parse-only clustering pass, so **11,087 of the
34,645 entries have no leaf and appear nowhere in the tree** — the page says this
above the tree and points at the audit explorer for those. The states that are not
branches stay visible rather than being tidied away: leaves with an open review-queue
item are marked `in review` and still browsable, auto-named branches carry the
`auto-named` badge, the 74 type-heterogeneous leaves are marked
`mixed types` with their shares, `Unique effect` is presented as a terminal finding
rather than a backlog, and the unruled vocabulary and zero-leaf branches are listed
under the tree. The shared phrases carry the same discipline: 486 of 657 leaves
have a phrase carried by at least half the leaf and the rest are weaker, with the
share printed rather than implied away. 18 leaves report `until end of turn`, which
is the duration rather than the effect — on a Pump card that genuinely is the most
common wording inside the matched clause, and removing it would need exactly the
hand-written vocabulary this pass exists to avoid. Most branches get no effect-group layer at all — outside the Removal
and Mass Effects sectors, nothing currently passes the subset test that layer
requires — and where it does appear, its `other` bucket can be large (83 of 1,202
cards for Spot removal → Creature, 438 of 861 for Mass effect): it surfaces exactly
what the sector's own curated branches cover, nothing more.

## What the audit page gives you

- **Search** across card name + oracle text.
- **Parse quality** as a top-level filter with live per-result-set percentages:
  `clean` / `partial` / `unparsed` / `vanilla`, plus two separate overlapping
  axes for what that split misses: `+ unmodelled node` (parser gaps the
  clean/partial test doesn't catch) and `⚠ has correction` (our own
  hand-verified findings — see below).
- **Slot-aware facets** — effect, trigger mode, static mode, replacement event,
  keyword, target/filter, quantity, cost, condition. Each axis matches only nodes
  found in that slot, so `quantity:Fixed` (18,978 cards) and `cost:Fixed`
  (193 cards) stay distinct. Option lists are derived from the data at build time,
  never hardcoded, so they track phase.rs's parser as it improves.
- **Full parsed structure** per card — all four ability buckets plus modal /
  additional-cost / casting-option fields, with gap nodes highlighted.
- **Pagination** over 34,645 entries, 50 per page.
- **Permanent header** showing snapshot age and the `parse_warnings` caveat.

## Design notes

- Identity is keyed by `scryfall_oracle_id`, never face name. See
  [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) §1.
- `build/index.json` (18 MB) holds only search text and interned facet ids. The
  37 MB of parsed structure is sharded into 64 chunks and fetched on expand, so
  the page loads once and stays responsive.
- Parse quality is computed from gap nodes only, never from `parse_warnings` —
  that field is not a trust signal. See KNOWN_LIMITATIONS.md §3.

## Structural clustering

`src/cluster_structural.py` clusters **cards** on (effect type + target/filter
shape) — structural fields already in the parse, not word overlap or embeddings.
HDBSCAN over a cosine KNN graph of IDF-weighted feature tokens; density-based, so
a card can come back unclustered rather than be forced somewhere.

Runs over **clean parses only** (partial/unparsed/unmodelled/corrected entries
excluded — a half-parsed card would cluster on what survived the parse). Uses
top-level effects only; `sub_ability` chains are not walked, that being full-tree
similarity rather than this pass.

Results and validation live in
[reports/clustering-structural.md](reports/clustering-structural.md). In the
explorer, each row carries its cluster (or `noise` / `n/a`), clicking it filters
to that cluster, and expanding a card lists the other members.

## Branch assignment (glossary tree)

`src/branch_leaves.py` groups the clustering's leaves under named **branches**
by structural rule only — a closed list of named predicates over each leaf's
dominant effect types and target/filter shapes, in the same style as the parent
experiment's zone classifier. **No membership voting:** Scryfall's oracle tags
supply *vocabulary*, never assignment. Leaves are read as given, never
re-clustered.

Branch names are all sourced, none invented — from the curated
`glossary.yaml` `function:` entries, the Scryfall otag list, and the slang
glossary's function terms. Where a curated term has no clean structural signal
(Mana dork needs a *type line*, not an effect) there is deliberately **no rule**
and the term is recorded as a gap instead.

Assignment is many-to-many, and unbranched leaves stay visible as a first-class
entry rather than being dropped. Results in
[reports/branches.md](reports/branches.md); in the explorer, the **glossary
tree** control opens a plain nested accordion (branch → leaf → cards) that hands
off to the existing cluster filter and row detail view.

### Branch map

The **branch map** control above it is a squarified treemap of the 37 populated
branches plus Unbranched, as the top-level visual entry point. Branches only —
no leaves nested inside. Regions are sized by **card count**, not leaf count:
card count reflects how much of the corpus a branch covers, whereas leaf count
only reflects how finely that branch happened to split during clustering.
Clicking a region opens that branch in the glossary tree; the treemap renders no
cards of its own.

Colour carries the branch's **vocabulary source** (3 slots), not its identity —
38 regions is far past the 8-slot cap for categorical hues, so identity is
carried by the label. The slots come from the validated default palette and were
checked with the data-viz validator at `pairs=all` (any two regions can end up
adjacent): worst CVD ΔE 9.2, worst normal-vision ΔE 24.0, both clear. A fourth
slot was rejected because it hard-fails the normal-vision floor (yellow↔orange
ΔE 13.7) — which is why the two `slang` variants share one slot. Label ink is
picked per fill by contrast rather than fixed to white (white on the aqua slot
is only 2.82:1). Unbranched is deliberately not a fourth hue: it is a *state*,
so it gets neutral grey plus a 45° hatch, readable in greyscale and for any
colour vision.

Regions do not sum to the corpus — assignment is many-to-many, so a card in 3
branches contributes 3 times. The page says so above the map.

## Corrections overlay

`corrections/corrections.json` is a hand-maintained, evidence-based log of
phase.rs parses found wrong by direct comparison against Scryfall oracle text —
never a fork of their engine, never an edit to their file. `build_index.py`
loads it automatically and applies it at build time, keyed by `oracle_id`.
Every entry is `kind:"flag"` (documented, structure left untouched) unless a
correct replacement value has real precedent elsewhere in the corpus in the
same slot, in which case it's `kind:"patch"`. See
[corrections/SCHEMA.md](corrections/SCHEMA.md) for why patches are the
exception, not the default.

This is an ongoing log, not a one-time pass — add to it whenever a card's parse
looks wrong during real use.

## Files

- [SCHEMA.md](SCHEMA.md) — the upstream schema, empirically derived + cross-checked
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) — measured caveats, including the
  corrections overlay (§4)
- [NAME_COLLISIONS.md](NAME_COLLISIONS.md) — generated: every dropped card
- [reports/coverage-ledger.md](reports/coverage-ledger.md) — generated: every card
  in the universe, one status each, plus placement coverage
- [data/overlay/recovered-cards.json](data/overlay/recovered-cards.json) — the 63
  collision-dropped cards, regenerated (tracked; the snapshot is not modified)
- [PROVENANCE.md](PROVENANCE.md) — snapshot identity
- [corrections/corrections.json](corrections/corrections.json) — hand-maintained
  correction log, [corrections/SCHEMA.md](corrections/SCHEMA.md) for its format
