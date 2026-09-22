# phase.rs Card Data Explorer

Dev-only tool for inspecting phase.rs's **static parsed** MTG card data. Read-only
consumer of their snapshot — it does not run their rules engine or game logic, and
does not touch their repo.

## Run

```
python src/build_index.py       # -> build/index.json, facets.json, meta.json, chunks/
python src/build_collisions.py  # -> NAME_COLLISIONS.md, build/collisions.json
python src/serve.py             # opens http://localhost:8765/reports/card-explorer.html
```

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
  `clean` / `partial` / `unparsed` / `vanilla`, plus a separate overlapping
  `+ unmodelled node` axis for gaps the clean/partial split misses.
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

## Files

- [SCHEMA.md](SCHEMA.md) — the upstream schema, empirically derived + cross-checked
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) — the three caveats, with numbers
- [NAME_COLLISIONS.md](NAME_COLLISIONS.md) — generated: every dropped card
- [PROVENANCE.md](PROVENANCE.md) — snapshot identity
