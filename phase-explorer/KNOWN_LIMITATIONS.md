# Known limitations of the phase.rs card-data snapshot

Permanent record so these are not rediscovered later. All numbers are measured
against the **2026-04-20** snapshot (`data/card-data.json`, 83,388,014 bytes,
34,645 face entries) and are reproduced by `src/build_index.py` and
`src/build_collisions.py` on every build.

This file documents limitations of the **upstream data**, not of this tool.
Improving phase.rs's coverage is deliberately out of scope here.

---

## 1. Face-name keying silently drops cards

`card-data.json` is a JSON object keyed by **lowercased face name**. Object keys
are unique, so when two different cards share a face name, one survives the
export and the other is **absent with no marker of any kind** — no warning, no
duplicate list, nothing. You cannot detect the loss from the snapshot alone.

Measured against MTGJSON AtomicCards (v5.3.0+20260921):

| | count |
|---|---|
| face-name keys contested by 2+ oracle ids in MTGJSON | **50** |
| contested keys present in the snapshot holding one id while others were dropped | **44** |
| distinct oracle ids silently missing as a result | **80** |
| contested keys absent from the snapshot entirely | 6 |

The full list, naming the winner and every dropped card, is regenerated into
[`NAME_COLLISIONS.md`](NAME_COLLISIONS.md).

### The confirmed example

`lightning bolt` resolves to the **Strixhaven "prepare" face**, not the card
everyone means:

- **DROPPED** `4457ed35-7c10-48c8-9776-456485fdf070` — classic Lightning Bolt,
  Instant, layout `normal`, **46 printings** (2ED, 3ED, 4ED, A25, ATH, …)
- **WON** `5963eef1-1022-42b1-8a0c-fc9850bfc2a3` — face of
  *Emeritus of Conflict // Lightning Bolt*, layout `prepare`, 2 printings
  (PSOS, SOS), `legalities: {}`

A 46-printing staple lost its slot to a 2-printing face of a different card.
Other notable casualties include **Ancestral Recall**, **Brainstorm**,
**Demonic Tutor**, **Channel**, **Braingeyser**, and **Careful Study**.

### How this tool responds

Internal identity is keyed by `scryfall_oracle_id`, never by face name. Two
wrinkles the data forces:

- multi-face cards share one oracle id across faces (34,645 keys vs 33,834
  distinct ids; 811 ids cover 2 faces each), so ids map to a *group* and
  per-face ids are suffixed `/0`, `/1`;
- some entries carry no oracle id, and fall back to `noid:<export key>`.

**What this tool cannot do:** show you a dropped card. It is not in the
snapshot. Re-keying prevents *further* collisions inside our own index; it
cannot resurrect what the export already discarded. Recovering those 80 cards
means regenerating card-data from MTGJSON with a non-colliding key, which is
upstream work.

---

## 2. Parse coverage is ~71%, not complete

Of 34,645 entries:

| category | count | share of all | share of texted |
|---|---|---|---|
| `clean` — no Unimplemented/GenericEffect node | **24,685** | 71.3% | 72.0% |
| `partial` — real structure **plus** ≥1 such node | **8,256** | 23.8% | 24.1% |
| `unparsed` — has oracle text, **zero** structured abilities | **1,344** | 3.9% | 3.9% |
| `vanilla` — no oracle text at all | **360** | 1.0% | — |

`vanilla` is a fourth category added here: those 360 entries have no oracle text,
so they are neither `unparsed` (which means "text but no structure") nor
meaningfully `clean`. Forcing them into either would misstate coverage.

`Unimplemented` nodes keep the raw fragment they gave up on, as
`{name, description}`. Most common `name` values: `unknown` 844,
`static_structure` 407, `choose` 254, `the` 220, `put` 173, `effect_structure`
147, `replacement_structure` 125.

### `clean` does not mean "fully modelled"

There is a second, weaker class of gap that the Unimplemented/GenericEffect test
does not catch: an enum slot the parser left **unmodelled** rather than an effect
it failed to build.

- a trigger or static `mode` arriving as `{"Unknown": "<raw text>"}` instead of a
  bare string — 885 trigger modes, 1,021 static modes
- a condition coming back `Unrecognized` — 503 occurrences

**2,244 entries carry at least one, and 1,696 of those are labelled `clean`** —
6.9% of the clean set. Example: *\_\_\_\_\_ Balls of Fire* has one
`Unimplemented` effect (so it is `partial`) *and* a second trigger whose whole
mode is `{"Unknown": "Whenever you put a sticker…"}`.

The explorer keeps `clean`/`partial`/`unparsed` meaning exactly what is defined
above, and exposes unmodelled nodes as a **separate overlapping filter**
(`+ unmodelled node`) plus a per-row count, rather than silently folding them in.

---

## 3. `parse_warnings` is not a trust signal

Only **544 of 34,645** entries carry any `parse_warnings` at all — far fewer than
the 8,256 entries that demonstrably contain gap nodes. The field is populated by
an upstream warning accumulator that misses real issues, so **absence of a
warning says nothing about correctness**.

### The confirmed example

*Deep Analysis* — oracle text "Target player draws two cards." — parses to:

```json
{"kind":"Spell","effect":{"type":"Draw","count":{"type":"Fixed","value":2}}, ...}
```

The **target player is gone entirely**. There is no `target` field, no `player`
field, and **no `parse_warnings` entry**. Nothing in the record indicates a
clause was dropped. This entry is classified `clean` by every available signal.

### How this tool responds

Every expanded card shows either its `parse_warnings` or, when absent, an
explicit dashed note stating that the absence is not a verification. The page
header carries the same caveat permanently. Parse quality is computed from **gap
nodes only** and never from `parse_warnings`, so the warning field is never
allowed to act as a proxy for correctness.

**Implication for any downstream use:** field-level fidelity must be spot-checked
per effect type. Do not assume a `clean` label means the structure faithfully
represents the oracle text — it means only that the parser did not announce a
failure.

---

## 4. The snapshot is stale and pinned

Last-Modified **2026-04-20**, fetched **2026-09-21** — 154 days old, and the page
displays that age at all times. Cards printed after April 2026 are absent, which
is expected and is *not* a collision (the collision detection in §1 is
deliberately date-independent: it only considers names MTGJSON itself covers with
multiple oracle ids).

Refresh with `curl -o data/card-data.json https://data.phase-rs.dev/card-data.json`,
or regenerate via `phase-gen -i AtomicCards.json.gz -o card-data.json`. Re-run
both build scripts afterwards; every number in this file is derived, not
hand-maintained.

---

## Reproducing these numbers

```
python src/build_index.py       # quality split, soft gaps, facets  -> build/
python src/build_collisions.py  # collision diff vs MTGJSON         -> NAME_COLLISIONS.md
python src/serve.py             # browse at /reports/card-explorer.html
```
