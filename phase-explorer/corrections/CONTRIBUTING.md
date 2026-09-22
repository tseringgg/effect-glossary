# Adding a correction

This is an ongoing log, not a one-time audit deliverable. Add an entry whenever
a card's parse looks wrong during real use — while building a deck, checking a
ruling, anything — not only during a dedicated sweep.

## Before adding an entry

1. **Get the real oracle text independently.** Scryfall's API
   (`api.scryfall.com/cards/named?exact=<name>` or
   `/cards/collection` for a batch) is the reference used so far. Don't rely on
   memory or on phase.rs's own `oracle_text` field as your source of truth —
   that field can itself be stale or wrong, though it usually just mirrors
   Scryfall correctly.
2. **Get the exact broken fragment from `data/card-data.json`**, byte for byte.
   Don't paraphrase or reconstruct it from memory — copy the real JSON. If
   `data/card-data.json` isn't present locally, re-fetch per the README.
3. **Match by `scryfall_oracle_id`**, printed on the card's entry in
   `data/card-data.json`, never by name (see
   [KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md) §1 for why).
4. **Decide `flag` vs `patch`.** Default to `flag`. Only use `patch` if the
   corrected value reuses a node shape that already appears, with the same
   meaning, somewhere else in `data/card-data.json` in the *same slot* (same
   key name feeding the same axis in `src/build_index.py`'s `SLOTS`/`GAP_TAGS`
   scan). If you're inventing a shape that has no precedent, it's a `flag`
   until someone can validate it against phase.rs's actual engine — we
   explicitly don't run that engine here.

## Adding the entry

Append to `corrections/corrections.json` following the shape in
[SCHEMA.md](SCHEMA.md). Then:

```
python src/build_index.py
```

This re-derives `build/index.json` and `build/chunks/*.json` with the
correction applied/attached, and updates `meta.json`'s
`corrections_loaded`/`corrections_applied_by_kind` counts. Nothing needs
touching in `reports/card-explorer.html` — it reads the correction count and
record straight from the rebuilt index/chunks.

If the defect is one instance of a broader pattern (like the 7 "pay X life"
cards), search the full corpus for the pattern before writing individual
entries, and note in each entry whether the search was exhaustive — see
`corrections/CLASS-x-life-cost.md` for the template.

## Removing a correction

If phase.rs fixes the underlying parse upstream (confirmed by re-fetching
`data/card-data.json` and checking the card's structure changed), delete its
entry from `corrections.json` and rebuild. Don't leave stale entries around —
a correction that no longer corrects anything is worse than no record, since it
would misreport `corrections_loaded` and clutter the `⚠ has correction` filter.
