# Known limitations of the phase.rs card-data snapshot

Permanent record so these are not rediscovered later. All numbers are measured
against the **2026-04-20** snapshot (`data/card-data.json`, 83,388,014 bytes,
34,645 face entries) and are reproduced by `src/build_index.py` and
`src/build_collisions.py` on every build. §3's spot-check findings are tracked
as an ongoing log in [`corrections/corrections.json`](corrections/corrections.json).

This file documents limitations of the **upstream data**, not of this tool.
Improving phase.rs's coverage is deliberately out of scope here.

**Sized, not fixed — see §4**: mid-chain conditional clauses can silently
drop their `condition` field. A verified 50-card spot-check found a 56%
real rate (40% fully invisible) — this is corpus-wide, not contained to the
79-card `Unimplemented:otherwise` count that first surfaced it, and needs its
own dedicated investigation before any fix is attempted.

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
| cards missing from the snapshot as a result (`card_dropped`) | **63** |
| cards that lost one face's key but are present under another face | 12 |
| losing ids first printed after the snapshot (never competed) | 3 |
| contested keys absent from the snapshot entirely | 6 |

An earlier version of this table said **80** oracle ids were missing. That
figure summed losers per key: it double-counted ids that lost more than one
key and included the other two classes above. 63 is the number of cards
actually absent.

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
The other classic casualties are **Ancestral Recall**, **Channel**,
**Braingeyser** and **Careful Study**.

**Demonic Tutor**, **Brainstorm** and classic **Swords to Plowshares** are *not*
missing — an earlier version of this section said Brainstorm and Demonic Tutor
were. Those classics won their keys. What lost was the Strixhaven twin's
prepare face: *Emeritus of Woe // Demonic Tutor*, *Harmonized Trio //
Brainstorm* and *Emeritus of Truce // Swords to Plowshares* are in the snapshot
under their front faces, minus the back face (`face_lost_card_present` in
NAME_COLLISIONS.md; recorded per card in the coverage ledger's evidence).

### How this tool responds

Internal identity is keyed by `scryfall_oracle_id`, never by face name. Two
wrinkles the data forces:

- multi-face cards share one oracle id across faces (34,645 keys vs 33,834
  distinct ids; 811 ids cover 2 faces each), so ids map to a *group* and
  per-face ids are suffixed `/0`, `/1`;
- some entries carry no oracle id, and fall back to `noid:<export key>`.

Re-keying prevents *further* collisions inside our own index; it cannot
resurrect what the export already discarded. The 63 dropped cards are
regenerated separately by `src/recover_dropped.py`: phase-rs `oracle-gen` at
v0.1.15 (the snapshot's own release), run once per card on a one-card
AtomicCards input, into `data/overlay/recovered-cards.json`. `card-data.json`
is untouched. A hard gate precedes it: the same binary must reproduce every
comparable snapshot entry byte-for-byte (34,497 of 34,497). The overlay's
`legalities`/`printings`/`rulings`/keyword metadata come from the newer
AtomicCards, not April's. The 12 lost faces of present cards are *not*
recovered — adding a face would change an existing card's parse.

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

## 4. Mid-chain conditional clauses can silently drop their `condition` (size unknown)

Found 2026-10-02 while investigating `Unimplemented:otherwise` (phase.rs's
engine; this is a parser-side limitation, not a classification error of ours —
confirmed before logging it here). **Not yet sized. This section will be
updated once it is.**

### The mechanism

phase.rs has a real, working mechanism (CR 608.2c) for `"...Otherwise,
[effect]."`: it parses the else-text, then walks the ability chain backward
for the most recent def with a non-null `condition` and attaches the else-text
as that def's `else_ability`. When no such def is found, it falls back to an
`Unimplemented{name:"otherwise"}` node whose `description` is just the bare
word `"Otherwise"` — the else-effect's own text is parsed (the fallback still
emits it as a sibling node) but the conditional relationship to its trigger is
lost.

The fallback fires because **the clause immediately before "Otherwise" has
already lost its own `condition` by the time the backward walk runs** — not
because the else-attachment code is broken. That upstream clause's effect is
present and correct; only the `if`-condition gating it is gone.

### Confirmed examples

| card | oracle text (relevant clause) | parsed `condition` |
|---|---|---|
| Candles of Leng | "...**if it has the same name as a card in your graveyard**, put it into your graveyard. Otherwise, draw a card." | `null` on the `ChangeZone` effect |
| Bogardan Phoenix | "...exile it **if it had a death counter on it**. Otherwise, return it to the battlefield..." | `null` on the `ChangeZone` (Exile) effect |
| Pulling Teeth | "**If you win**, target player discards two cards. Otherwise, that player discards a card." | `null` on the `Discard{count:2}` effect |
| Jon Irenicus, the Exile | "...draw a card **if your library has more cards in it than target opponent's library**. Otherwise, each opponent mills five cards." | `null` on the `Draw` effect |

All four: the gated effect is structurally present and correct; the `if`-clause
that should gate it is simply absent from `condition`, with no
`parse_warnings` entry — same silent-defect shape as Spark Double and Deep
Analysis (§3), not a new kind of problem, just not yet known how large.

### Why this might be much bigger than 79 cards

`Unimplemented:otherwise` (79 cards, 56 sole-cause) is only the *visible* slice
— the only reason these specific cards show a gap node at all is that the
"Otherwise" else-handler is the one piece of code that actually notices a
missing condition and complains. A card with the identical mid-chain
`"[effect] if [condition]"` shape but **no** trailing "Otherwise" would have
nothing downstream to notice the drop, and would be labelled `clean`, 0
`parse_warnings` — invisible by every signal phase.rs or this tool currently
has, exactly like Deep Analysis.

### Sizing status: spot-checked 2026-10-03, real rate is 40-56%, not contained

A quick heuristic (description contains "if", `condition` is null, effect
itself gap-free) returned **4,889 candidate hits** — not trusted as a count on
its own. 50 were pulled at random and individually verified against full
parsed structure and oracle text, same discipline as §3's Spark Double / Deep
Analysis entries:

| verdict | n/50 | meaning |
|---|---:|---|
| Real, genuinely silent (card shows fully `clean`) | **20 (40%)** | invisible by every existing signal |
| Real, but card already carries a visible `Unimplemented` elsewhere | 8 (16%) | condition also dropped, not contributing to an *invisible* population |
| False positive | 22 (44%) | see reasons below |

**Combined real rate: 28/50 = 56%. This is not a contained sub-case — do not
scope a narrow fix off the `Unimplemented:otherwise` count alone.**

False-positive reasons found (useful if the heuristic is revisited):
"if able"/"if it's blocking" idioms that aren't conditions at all; "if you do"
correctly captured via `IfYouDo` on a *nested* sub-ability (my heuristic only
checked the outer, correctly-unconditional wrapper); conditions correctly
living in `activation_restrictions[].data.condition`, `AdditionalCostPaid`, a
direct `QuantityCheck`, or replacement-specific fields instead of a bucket
item's own `condition`; `FlipCoin.win_effect`/`lose_effect` used correctly; and
one heuristic bug of my own (checked `effect` on trigger-bucket items, which
nest under `execute` instead, silently missing cards that already had a
visible gap node).

Real examples found span genuinely different sub-shapes, suggesting multiple
distinct root causes, not one:
- **Sequential chained conditionals** — Ray of Enfeeblement ("-4/-1... if
  white, -4/-4 **instead**" parses as two unconditional Pumps, both applying
  cumulatively), Gimli's Fury, Ritual of Hope.
- **Result-dependent ("...this way" / "...does")** — Play with Fire ("if a
  player is dealt damage *this way*"), Grist (deathtouch "if a black card was
  milled *this way*"), Skullknocker Ogre (mandatory-antecedent "if the player
  *does*", no "may" anywhere in the sentence).
- **Compound/OR conditions** — Orator of Ojutai ("if you revealed a Dragon
  **or** controlled a Dragon").
- **Negative "if you don't"** (no handling found at all) — Rashmi.
- **Dropped condition nested inside an already-present wrapper** — Groundling
  Pouncer (`RequiresCondition` node exists; its own `data.condition` is null).
- **Static-ability-level, not effect-chain** — Of One Mind's `ReduceCost`
  mode.
- **Targeting restriction dropped from the filter, not a condition field** —
  TL;DR.
- **Branch/structural** — Sorcerer's Strongbox (draw happens unconditionally
  outside the coin-flip's `win_effect`, contrast Skyclaw Thrash where the same
  mechanism is used correctly).

### Recommendation: separate future effort, not a narrow fix

Not a contained sub-case. A rough, order-of-magnitude-only projection (40-56%
of 4,889) suggests hundreds to low-thousands of cards corpus-wide — but the
heuristic's own reach is known incomplete (the trigger/`execute` bug alone
shows it misses cases), so treat that as a floor, not a measurement. A proper
investigation needs: (1) a real per-item detector (check the actual
effect-bearing field per bucket type, positively exclude known-good patterns
like `IfYouDo`/`AdditionalCostPaid`/`QuantityCheck`/restriction wrappers
instead of a blind null-check), (2) separate characterization of each
sub-shape above, since they likely live in different parser modules. This
does not move the `clean`/`partial` split (these cards already show `clean`)
— it is a correctness-fidelity investigation in the spirit of §3, not a
coverage one, and deserves its own dedicated pass.

### How this tool responds

Nothing yet — no fix, no corrections.json entries, no overlay. Logged as a
sized-but-unresolved finding, for a future, separate effort.

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
