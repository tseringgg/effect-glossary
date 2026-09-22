# Known limitations of the phase.rs card-data snapshot

Permanent record so these are not rediscovered later. All numbers are measured
against the **2026-04-20** snapshot (`data/card-data.json`, 83,388,014 bytes,
34,645 face entries) and are reproduced by `src/build_index.py` and
`src/build_collisions.py` on every build. §4's spot-check findings are tracked
as an ongoing log in [`corrections/corrections.json`](corrections/corrections.json).

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
does not catch: a trigger `mode` arriving as `{"Unknown": "<raw text>"}` instead
of a bare string — meaning the parser did not model that trigger at all — or a
condition coming back `Unrecognized`.

(Static `mode` and replacement `event` also arrive as externally-tagged dicts,
e.g. `{"ReduceCost": {...}}`, but those are legitimate data-carrying variants,
not gaps. An earlier build of this tool counted every dict-valued mode/event as
a soft gap and over-reported 2,244 affected entries — fixed once a flagged
"clean" card, Blasphemous Act, turned out to have a perfectly correct
`ReduceCost` static ability as its only "gap".)

**1,288 entries carry at least one real soft gap (885 trigger modes + 503
conditions), and 887 of those are labelled `clean`** — 3.6% of the clean set.
Example: *\_\_\_\_\_ Balls of Fire* has one `Unimplemented` effect (so it is
`partial`) *and* a second trigger whose whole mode is
`{"Unknown": "Whenever you put a sticker…"}`.

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

### Confirmed by a targeted spot-check, 2026-09-22

§3's implication was tested directly: 32 cards from this project's own
known-hard-case set (mill, surveil, board wipes, removal, clone/token-doubler,
mana dorks, plus Mulldrifter/Rhystic Study/Phyrexian Arena) were checked against
independently-fetched Scryfall oracle text, matched by oracle id. All 32 are
*present* (none collision-dropped), but **field-level comparison found 2 classes
of defect that every one of phase.rs's own signals — `clean` label,
`parse_warnings`, gap nodes — missed on every affected card**:

- **Spark Double**'s entire copy effect is absent. Oracle text has three
  clauses (may copy a creature/planeswalker you control; conditional extra
  counter; isn't legendary); the parse keeps only a bare, unconditional +1/+1
  counter with no copy effect at all. `clean`, 0 `parse_warnings`.
- **7 cards** whose oracle text is "As an additional cost to cast this spell,
  pay X life" (Bond of Agony, Fire Covenant, Fix What's Broken, Hatred,
  Necrologia, Toxic Deluge, Vicious Rivalry) parse their cost to `PayLife
  {Fixed, value: 0}` — free regardless of X — while their effects still
  correctly reference the chosen X. All `clean`, 0 `parse_warnings`. Confirmed
  exhaustive across the full 34,645-entry corpus (no other card matches the
  pattern).

Two more cards in the same spot-check (Mirror Image, Parallel Lives) showed
differences worth a second look but are *not* silent — Mirror Image carries a
`parse_warnings` entry and Parallel Lives is already labelled `partial` with an
`Unimplemented` node, so phase.rs's own signals already surface them; they were
left out of the corrections overlay below for that reason.

### How this tool responds: `corrections/`

These 8 findings are recorded in
[`corrections/corrections.json`](corrections/corrections.json), a hand-maintained
overlay applied on top of the raw snapshot at our own build time — the upstream
file is never edited, their engine is never run. Every entry carries the real
oracle text and the exact byte-for-byte broken JSON fragment as evidence; see
[`corrections/SCHEMA.md`](corrections/SCHEMA.md) for the format.

All 8 entries are currently `kind:"flag"` (documented, not structurally patched)
rather than `kind:"patch"` (a real value substitution). A patch was considered
and rejected for both defect classes: the obvious fix for the X-life costs would
use a `Variable` node inside a cost's `amount` field, and a full corpus scan
found **zero precedent** for that shape in any cost slot anywhere in the 34,645
entries. Patching in an unvalidated guess — one we cannot check against their
engine, which is explicitly out of scope for this tool — risks trading one
silent wrongness for a different, equally unvalidated one. Flags stay flags
until either upstream fixes the parse or a patch's shape has real precedent to
build from.

This is logged as an **ongoing process**, not a one-time pass: add an entry to
`corrections.json` whenever a card's parse looks wrong during real use, following
the same evidence discipline as every entry above.

The page surfaces corrections as a separate, overlapping filter
(`⚠ has correction`) from both the quality axis and the unmodelled-node axis,
with a permanent header note and a dedicated box in each affected card's detail
view — never folded into or implied by phase.rs's own signals, since the entire
point is that those signals missed all 8.

---

## 5. The snapshot is stale and pinned

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
python src/build_index.py       # quality split, soft gaps, facets, corrections applied -> build/
python src/build_collisions.py  # collision diff vs MTGJSON         -> NAME_COLLISIONS.md
python src/serve.py             # browse at /reports/card-explorer.html
```

`build_index.py` loads `corrections/corrections.json` automatically; no separate
step is needed to apply it.
