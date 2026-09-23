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
python src/serve.py               # opens http://localhost:8765/reports/card-explorer.html
```

`cluster_structural.py` is optional — the page works without it and simply shows
no cluster column. Requires `hdbscan`, `numpy`, `scipy`.

The page must be served over HTTP; it fetches JSON, which `file://` forbids.

## Inputs (gitignored, re-fetch as needed)

| file | size | purpose |
|---|---|---|
| `data/card-data.json` | 83 MB | the snapshot under inspection |
| `data/AtomicCards.json.gz` | 52 MB | MTGJSON reference, only for collision detection |

```
curl -o data/card-data.json     https://data.phase-rs.dev/card-data.json
curl -o data/AtomicCards.json.gz https://mtgjson.com/api/v5/AtomicCards.json.gz
```

## What the page gives you

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
- [PROVENANCE.md](PROVENANCE.md) — snapshot identity
- [corrections/corrections.json](corrections/corrections.json) — hand-maintained
  correction log, [corrections/SCHEMA.md](corrections/SCHEMA.md) for its format
