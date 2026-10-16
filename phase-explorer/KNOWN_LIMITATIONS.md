# Known limitations of the phase.rs card-data snapshot

Permanent record so these are not rediscovered later. All numbers are measured
against the **2026-04-20** snapshot (`data/card-data.json`, 83,388,014 bytes,
34,645 face entries) and are reproduced by `src/build_index.py` and
`src/build_collisions.py` on every build. §3's spot-check findings are tracked
as an ongoing log in [`corrections/corrections.json`](corrections/corrections.json).

This file documents limitations of the **upstream data**, not of this tool.
Improving phase.rs's coverage is deliberately out of scope here.

**Since 2026-10 the main view is per-ability and the card-level view is archived: see §12.** §§1-11 describe the data and the archived view.

**Sized, one sub-shape made visible — see §4**: conditional clauses can
silently drop their condition. A per-item detector sizes this at **2,785 cards**
(1,889 still `clean`) across 11 remaining sub-shapes; round 1 (the
`RequiresCondition` null-wrapper) is a *visibility* fix, not a resolution — its
conditions are now kept as `Unrecognized` text but not yet parsed. Full numbers:
`reports/condition-drops.md`.

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

## 4. Conditional clauses can silently drop their `condition`

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

### Sizing, superseding the estimate above

The 4,889-hit heuristic and its 40-56% extrapolation are superseded by a validated per-item
detector (`src/detect_condition_drops.py`; it reproduces the 50-card spot-check exactly: 28
real / 22 false positive, 20 silent / 8 visible). Corpus-wide it found **2,936 items on 2,857
cards, 1,952 of them still `clean`**, in 12 sub-shapes. Ranked list, per-shape card and
sole-cause counts, and the detector's reach limits are in `reports/condition-drops.md`.
The fixes are being done one sub-shape at a time, in that report's recommended order.

### Round 1 -- nested-wrapper: made VISIBLE, not resolved (2026-10-03)

**What it was.** `ActivationRestriction::RequiresCondition { condition }` was built for every
"Activate only if ..." sentence, but its condition came from `parse_restriction_condition`,
which returns `None` for any phrasing outside a closed, hand-written vocabulary (the
`ParsedCondition` enum). The engine evaluates `None` as permissive-true. So the wrapper
correctly said "this is conditional" and the condition text was thrown away. This was **not**
a wiring bug: 79 cards were about 75 unrelated unrecognized phrasings. The same discard
happened at the casting-restriction (`Cast this spell only if`) and casting-option
(`You may pay ... if`) call sites, which the sizing could not see: the real population is
**133 cards / 134 condition nodes** (100 activation, 6 casting restriction, 28 casting option).

**What changed.** New `ParsedCondition::Unrecognized { text }` (same precedent as
`StaticCondition::Unrecognized` / `ReplacementCondition::Unrecognized`), evaluated `true`
exactly like the `None` it replaces, plus a storing-form helper
`parse_restriction_condition_or_unrecognized` used at the 10 storing call sites (the
`Option`-returning function is untouched because three casting-option callers use its `None`
as control flow). Gameplay evaluation is unchanged. **No card is newly parsed.** Delivered as
`data/overlay/unrecognized-restriction-fix.json`; `card-data.json` is untouched.

**Gate.** Full byte-for-byte run over all 34,645 entries against the snapshot with the two
earlier parser-fix overlays applied: 34,311 identical, 192 rerun-flagged, 59 of those being the
earlier overlays' own faces (saved with sorted keys, so their bytes differ from the generator's
only in key order; identical after regeneration), 133 cards carry the change.
Every shipped difference is `null/absent -> {type: Unrecognized, text}` at exactly those nodes;
anything else aborts. 4,472 engine unit tests pass, including new ones for the helper, the
permissive evaluation and the oracle-level parse.

**Result.** The detector's nested-wrapper count goes 77 -> 0 (65 -> 0 silent). 74 of the 77
cards stop flagging; 3 keep a separate real drop the wrapper had hidden (Izzet Generatorium,
Ojer Taq, Sarevok's Tome). The 133 cards now carry a soft-gap `Unrecognized` node in the
explorer (the build now also reads it from `casting_restrictions` / `casting_options`);
quality labels did not move; in the coverage ledger 102 cards moved to `unmodelled_node` (82 from
clustered leaves, 18 from noise, 2 from no-extractable-effect), and re-clustering then shuffled
202 unrelated cards between clustered and noise (156 out, 46 in) -- cluster ripple, not parse changes.

**Residual -- round B worklist.** The text is kept, not understood: all 134 conditions are
still evaluated `true`. `reports/restriction-condition-worklist.md` lists every phrasing
(116-120 distinct once numbers are normalised), grouped and ranked by card count (as of B1:
singletons 39, "this turn" events 36, graveyard/hand/exile counts 20, source-state/self-name 15,
counters 10, land counts 6, city's blessing 3, life totals 3). Found on the way: in 40
activation texts a leading timing clause was swallowed into the unrecognized text, so
`AsSorcery` / `DuringYourUpkeep` / `OnlyOnceEachTurn` were not emitted either -- round B1 below.

### Round B1 -- timing clause split out of compound activation restrictions (2026-10-03)

**What it was.** "Activate only as a sorcery and only if <X>" (and "during your upkeep / during
your turn / during combat / once / once each turn ... and only if <X>") reached the generic
`activate only ` branch of `strip_activated_constraints`, which handed the whole sentence to
the condition parser. The timing half is a phrase the parser already emits elsewhere, so round
1's `Unrecognized` blob was hiding recognizable information as well as the unrecognized part.

**What changed.** That branch now splits on ` and only ` / `, and only ` / `, only ` and emits
`AsSorcery`, `DuringYourTurn`, `DuringYourUpkeep`, `DuringCombat`, `OnlyOnceEachTurn`,
`OnlyOnce` for exact phrase matches; every other piece stays verbatim as `Unrecognized`, and a
sentence with no recognised timing piece is left exactly as it was. Overlay:
`data/overlay/activation-timing-split-fix.json`. **This changes gameplay**: the engine enforces
those variants (the `Unrecognized` remainder is still permissive), and the parser also sets
`sorcery_speed` on `AsSorcery` abilities. Engine tests parse the real Oracle text and run it
through the activation gate: Cabal Inquisitor is refused in the upkeep, beginning-of-combat,
declare-blockers and end steps and on the opponent's turn, and allowed in its owner's main phase;
an upkeep-only ability is refused outside the upkeep; `OnlyOnceEachTurn` blocks a second
activation; "once and only during your turn" enforces both halves. 4,479 engine tests pass.

**Result, honestly.** Of the 40 swallowed-timing texts, **22 cards** were split: 2 fully
resolved (The Food Court, Ashling, the Extinguisher Avatar -- nothing left over) and 20 now
carry the real timing plus a residual `Unrecognized` remainder (Grizzled Wolverine also keeps a
"declare blockers step" piece). The other **18 are unchanged by design**: their timing phrase has
no equivalent `ActivationRestriction` (declare blockers / declare attackers / end-of-combat step,
an opponent's turn or upkeep, any upkeep step, before blockers are declared, ...), so they need
new variants -- reuse `CastingRestriction`'s names (`DeclareBlockersStep`, `DuringOpponentsUpkeep`,
`DuringAnyUpkeep`, ...) in a future round. `BeforeAttackersDeclared` must NOT be reused for
Norritt / Arcum's Whistle / Nettling Imp (it requires the active player to hold priority; those
are opponent-turn abilities), and `BeforeCombatDamage` does not mean "before the combat damage
step". The mirror form "<condition> and only as a sorcery" (8 cards: Balustrade Wurm, Resurrected
Cultist, Speaker of the Heavens, four Temples, Uchbenbak) reaches a different branch and still
swallows `AsSorcery`; same fix, not done here.

**Why remainders are not parsed.** The first version also ran remainders through the existing
condition parser. Live-checking showed that gives two cards a wrong, now-enforced meaning
(Urza's Fun House's three-land clause and Goblin Ski Patrol's "snow Mountain" each become one
made-up subtype nothing can satisfy, making the abilities unusable), so remainders stay
`Unrecognized`. Seven would have parsed correctly (e.g. Cabal Inquisitor's seven graveyard cards);
they are a cheap win once that misparse is fixed.

**Gate.** 34,497 entries compared against the snapshot with the three earlier overlays applied:
34,279 byte-identical, 16 after April-metadata restoration, 180 earlier-overlay faces identical
under a canonical comparison, exactly 22 different -- equal to the target set declared beforehand
by an independent re-implementation of the rule. Every difference is a lossless split of a
single `Unrecognized` blob (plus `sorcery_speed` false -> true on the 6 `AsSorcery` abilities).
The comparison was audited too: ordered and canonical comparators agree, the compared bytes are
hashed on both sides, and a planted mutation is confirmed detected. The detector's totals did not
move (2,861 items / 2,785 cards): an extracted timing restriction is not a condition drop.

### How this tool responds

Round 1's overlay is applied at our own build time (`PARSER_FIX_OVERLAYS` in `build_index.py`).
Nothing else in this section has a fix, corrections.json entry or overlay yet; the remaining
sub-shapes are logged as sized-but-unresolved.

---

## 5. The snapshot is stale and pinned -- and a post-snapshot layer sits on top

Last-Modified **2026-04-20**, fetched **2026-09-21**; the pages display that age at all
times. `card-data.json` itself is never refreshed. Cards released since are a separate
layer (below), so a "snapshot" count on a page means the April file and a "universe" count
includes the layer.

### Post-snapshot layer (2026-10-03)

**1,383 cards** (1,430 faces) released after the snapshot are in
`data/overlay/new-release-cards.json`: the 1,367 that were `released_after_snapshot`, 15
more MTGJSON added after 2026-09-21, and Mr. Monopoly, On the Go (formerly
`absent_unexplained`). Universe 38,906 -> **38,921**; `missing_from_export` 1,431 -> **63**
(the collision-recovered cards, which keep that status by precedent).

- **Generator.** The pinned phase-rs `oracle-gen` v0.1.15 plus the four local parser-fix
  overlays, one oracle id per run (no face-name collision can drop a card). Nothing newer
  was used: upstream is now v0.101.0, 7,018 commits ahead; its hosted
  `card-data.json` is still the April file (the current build is at a content-hashed URL),
  and it re-parses **93.5%** of the existing cards (32,186 of 34,421 comparable faces)
  differently, so no newer generator can pass a control-set gate and mixing parser versions
  would put two node vocabularies in one corpus. Its collision handling is better but not
  fixed: it still keys by lowercased face name and keeps some losers under hidden
  `name [oracle_id]` keys.
- **Gate (nothing written unless it passes).** The pinned binary over the full 2026-09-21
  AtomicCards: 34,502 existing entries compared against the snapshot with the four overlays
  applied, 34,284 byte-identical + 202 earlier-overlay faces identical under a canonical
  comparison + 16 after April-metadata restoration, **0 different**; comparators agree and a
  planted mutation is detected (same audit as round B1).
- **Two MTGJSON files on purpose.** `data/AtomicCards.json.gz` (2026-09-21) stays the
  universe and the gate's control set. `data/AtomicCards-20261003.json.gz` is read only
  to generate the new cards. Swapping the newer one in as the universe would have removed 216
  snapshot cards (Alchemy "A-" rebalances MTGJSON dropped) and changed the Oracle text of 56
  existing ones.
- **Collisions in the new data, found and avoided.** 3 new cards share a lowercased face name
  with an existing snapshot card (`joven and chandler`, `artist alley`, `boltwave`) and 15 share
  one with each other (`omit variables`, `peer review`, `seed suture`, `soul tether`,
  `vicious verse`: three Strixhaven-style `prepare` spells each); 18 cards would have been
  silently dropped or overwritten under face-name keying. Isolated, oracle-id-keyed generation
  returned every face of every card (1,383 / 1,383, 0 failed).
- **What happened to them.** Faces: 1,159 clean, 263 partial, 1 unparsed, 7 vanilla. Cards:
  **1,030 clean-with-features -> new status `unclustered`** (815 placed by proximity at cosine
  >= 0.80, **215 below the floor -> review queue**), 258 partial, 57 unmodelled node, 30 no
  extractable effect, 7 vanilla, 1 unparsed. The 568 not placed carry their stage as the reason
  (`post_snapshot_partial`, ...). 82% of faces parse clean against about 85% for the April
  corpus: the gap is mostly April-era limits on new mechanics (`empower` 35 cards, `teamwork`
  16, `recruit` 9, `create` 22, ...), which the hosted newer file does parse (96 partial faces
  vs 263). Not fixed here; revisiting this means re-baselining the whole corpus (re-cluster,
  new leaf ids).
- **What did not move.** `clusters.json`, `branches.json`, `sub_branches.json`,
  `sectors.json`, `index.json`, all 64 chunks, the leaf maps and every file under
  `corrections/` are byte-identical before and after (76 files hashed). Existing proximity
  placements (472 noise + 20 recovered) and the existing review-queue items are identical; the
  leaf centroids and the self-similarity of clustered members are identical. New cards are
  never inputs to a centroid. They land in 260 leaves, at most 51 in one.
- **Not covered.** The new cards are not in `build/index.json`, so the parse-audit explorer
  (`card-explorer.html`) does not list them; the ledger (`ledger.html`, with parsed structure)
  and the browse tree (a green `new` chip; counted separately as "+N nearby") do.
  Pre-existing parse gaps and condition drops are inherited unchanged.

Do not refresh `card-data.json` in place: upstream's current parse differs for nearly every
card, which would invalidate the leaf ids. To re-baseline deliberately, regenerate everything
and re-run the clustering as a new round.

---

## 6. Keyword-only cards are placed by rule, not by clustering (2026-10-04)

`cluster_structural.card_features()` reads only the four ability buckets. A card whose whole
text is parsed into `keywords` ("Flying"; "Flying, vigilance"; "Protection from red") therefore
emits no feature: it cannot be clustered or placed by proximity. **1,257 cards** (1,264 faces,
25 of them from the post-snapshot layer, 7 multi-face) were `no_extractable_effect` /
`no_feature_to_compare` for that reason although their text is fully modelled. `card_features()`
was not changed and nothing was re-clustered; they are a separate, additive layer
(`src/build_keyword_layer.py` -> `build/keyword_layer.json`), placement method **`keyword_rule`**
(exact membership, a rule rather than a guess), shown with its own solid badge in browse, never
the dashed "nearby" one.

- **Status.** New ledger status `keyword_only` (1,257 cards). The pipeline stage is still
  `no_extractable_effect` and stays in each row's `evidence.pipeline_status`; the other **240**
  keep that status: 71 have keywords *and* ability items that yield no feature (prevention
  shields, replacements), 161 have ability items and no keywords, 8 are `additional_cost` only.
  Twelve statuses, 66 pairwise intersections, all zero.
- **Grouping.** Leaf id `kw:<signature>` (the card's sorted keyword names joined by `+`), in a
  namespace that cannot collide with the integer leaf ids. A signature held by >= 5 cards is a
  leaf (49 leaves, 711 cards; Landwalk additionally splits by land type, `kw:Landwalk|Swamp`
  -> "Swampwalk"). Otherwise the card goes to "`<Keyword>`: other combinations" under its
  *rarest* keyword by corpus card count (56 leaves, 454 cards). Otherwise to one leaf labelled
  **"Rare keyword combinations (catch-all)"** (92 cards, sorted by rarest keyword). 106 leaves
  in 67 branches (one per keyword + the catch-all); the largest leaf is Flying with 103, the
  smallest 5, the median 8; the largest branch is Flying with 225 cards. 449 distinct
  signatures exist; 307 of them have a single card. Each card is in exactly one leaf; a
  multi-keyword leaf is listed under each of its keywords' branches (many-to-many at the branch
  level, like every existing branch).
- **Payloads.** Shown on every card (Protection from what, Ward/Morph/Echo costs, Crew/Bushido
  numbers) but not used to split leaves, except Landwalk. After the 5-card minimum only
  "Protection from red" would have reached a leaf of its own, so Protection stays one leaf
  family with the colour or quality visible on the card.
- **Names.** Keyword names come from the engine's own `Keyword` variants split on case; checked
  against the Comprehensive Rules 702 headings, the only observed irregular is Battle cry (CR
  702.91); landwalk leaves use the real names (Swampwalk, ...).
- **Card types: no split.** 98% are creatures. The audit rule (>= 2 permanent types at >= 20%)
  literally flags **14 of the 106 leaves**, but every flagged Artifact is also a Creature (an
  artifact creature is counted under both types), so no split is applied. 21 cards are not
  creatures: 14 are Vehicles in one clean Crew leaf, and **7 strays** sit in other leaves
  (Ardent Plea, Braid of Fire, Catalyst Stone, Darksteel Relic, Into the Time Vortex, Memory
  Crystal, Throes of Chaos).
- **Left alone.** The **12,046** cards that have keywords *and* ability items (8,244 clustered,
  1,469 noise, 1,321 partial, 472 unmodelled, 469 unclustered, 71 `no_extractable_effect`) keep
  their ability-based placement; their keywords are still ignored by clustering.
- **Coverage.** Placed 23,435 -> **24,692** of 34,864 in scope (**67.2% -> 70.8%**); unplaced
  15,486 -> 14,229. Only the 1,257 rows' status and placement changed; the other 37,664 rows are
  identical in status, reason and placement.
- **Verified.** 107 files hashed before and after (`clusters.json`, `branches.json`,
  `sub_branches.json`, `sectors.json`, the three leaf maps, `index.json`, `placements.json`, all 64
  chunks, `type_audit.json`, everything under `corrections/` and `data/overlay/`,
  `card-data.json`): byte-identical. Existing proximity (1,303) and vanilla (344) placements and
  the 4,214-item review queue are unchanged; no keyword card is also clustered or
  proximity/vanilla-placed; two consecutive ledger runs give identical bytes.
- **Not covered.** The parse-audit explorer (`card-explorer.html`) lists index rows only, so it
  does not list keyword-only cards under this layer; browse and the ledger do.

### Leaf counts: 657, not 591

The current clustering has **657 leaves** (`clusters.json`, `branches.json`). "591" was the
count when the first passes were written. Hard-coded copies in generator prose were corrected to
read from the data (`audit_leaf_types.py`: "80 of the 657 leaves", not "74 of the 591";
`branch_leaves.py`; `README.md`: 486 of 657 leaves have a top phrase carried by at least half the
leaf). Left as they are because they are true: the three leaf maps
(`build/leafmap*.json`, `reports/leafmap*-validation.md`) really were built over 591 leaves and are
frozen, so they cover 591 of the 657 leaves; `DECISIONS.md` lines are dated records of what was
measured then; and "cluster 591" / "leaf 591" in `clustering-structural.md` and
`leaf-phrases.md` is a leaf *id*.

---

## 7. "Not yet organized" and "Find a card" are a display layer (2026-10-05)

Of 34,864 in-scope cards, 24,692 are organized (a leaf, nearby, a keyword leaf, or "No
abilities") and **10,172 are not**. The browse page now lists them in plain-language groups and
answers "where is this card?" for every one of the 38,921 catalogue entries. It is a display
layer: `src/build_unorganized.py` reads the ledger and the placement and keyword layers and
writes three new files (`build/unorganized.json`, `build/unorganized_cards.json`,
`build/lookup.json`); no status, placement, threshold, branch rule or frozen file changes, and
all 107 hashed files are byte-identical. Tester-facing wording lives only in that generator,
`reports/findcard.js` and the page.

| group | cards | what puts a card there |
|---|---:|---|
| Parsed, but with a gap | 5,708 | status partial or unmodelled node (4,600 + 1,071), plus 37 recovered partials |
| Parsed, no close group found | 4,175 | below the similarity floor: 3,958 noise, 215 newer, 2 recovered; best group and score shown as a *suggestion* |
| No effect to group | 245 | `no_extractable_effect` (240) plus 5 recovered |
| Not parsed yet | 29 | status unparsed |
| Known parse mistake | 8 | `corrections_flagged` (hand-confirmed defects) |
| No rules text: newer cards | 7 | newer vanilla cards the "No abilities" rule (snapshot only) does not cover |

- **Recovered cards are not a group.** The 44 unplaced recovered cards are parsed; they sit in
  the group for their stage with a plain "recovered card" tag. "Awaiting recovery" would have
  told a tester the card was missing.
- **Group 3 is not only shields.** About 167 are prevent-damage shields, 66 are
  keyword-plus-replacement cards, 7 are additional-cost-only. The explanation covers all three.
- **Group 1 gap text is the parser's normalized fragment** (lowercase, numbers as N, `~` for the
  card name), with its internal "line failed ... parser:" prefix removed. 32 cards (the
  Traps) carry no ledger fragment; their gap is an unrecognized casting-option condition,
  read from the card itself. One card, Evolving Adaptive, has no recorded gap and says so.
- **Group 2 strength words** are display labels only: close >= 0.70 (953 cards), loose
  0.50-0.70 (709), weak < 0.50 (2,513, shown muted). No placement threshold is involved.
- **Find a card.** Matches any face name, ignoring case, accents and punctuation. Real
  cards are listed before catalogue entries that are not cards (art cards, tokens, emblems,
  memorabilia, planes, schemes, Vanguard), each with its reason; duplicate names list every
  match (235 names are shared by more than one entry, 101 of them by a real card and a
  non-card). Load: `unorganized.json` is 2 KB at boot; the card lists (1.8 MB raw, ~0.5 MB
  compressed) load when a group is first opened and the lookup (3.2 MB raw, ~1.4 MB compressed)
  on first use of the Find box, on top of the ~33 MB the page already loads.
- **"Review queue" wording is dev-only.** The curation queue (leaf-level "in review" chips,
  the open-items box, the header link, the unique-effect blurb) now shows only with `?dev=1`
  on `browse.html` and `card-explorer.html`. The generated `review-queue.html` page itself is
  unchanged.
- **Verified** with `src/test_findcard.py`, which runs the same `findcard.js` the page loads in
  a JavaScript engine (dukpy) against the real data: reconciliation, every one of the 38,921
  entries found by every one of its 39,826 face names, 17 named lookups across all twelve
  states, ordering, and accent folding. That is not a render check: no browser was available, so
  the page's layout, styling and click paths have only been syntax-checked.

---

## 8. "Also fits" suggestions, and ability-level clustering as an open decision (2026-10-08)

**What shipped.** Cards in "Parsed, no close group found" with a blended score of 0.50 or more
(1,662 cards) can show per-ability "also fits" links: an individual ability that matches an
existing leaf at **0.90 or more**, by the clustering's own tokens, IDF weights and centroids
(`src/ability_probe.py`; generator `src/build_also_fits.py` -> `build/also_fits.json`, loaded
with the group's card list). Each link is labelled "Also fits (suggestion, not a placement)" and
has the ability's text beside it. The card stays in its group; no leaf gains a member; nothing
is placed, no centroid, score, status or frozen file changes (107 hashed files byte-identical;
ledger rebuilt to identical bytes). Evidence for the design: `reports/ability-placement-probe.md`.

**What it shows: 991 cards, 1,473 links** (444 cards have two or more). Rules, as approved:
skip flagged cards (162) and modal spells (152; modes are separate ability items); show
*specific* matches only (>= 3 tokens and a leaf of <= 300 cards): 798 generic matches (a bare
eff:Draw / eff:Token / eff:Mana, or a leaf of 500+ cards) and 196 in-between ones are not shown;
230 abilities have no text to put beside the link (keyword-generated equip / cycling, and Saga
chapters whose text is only "Chapter N") and are not shown.

**Hand check (two seeded samples).** Final output, 30 cards / 44 links: 41 correct, 3 wrong or
doubtful (a -1/-1 counter ability matched to the +1/+1-counter leaf; an opponent-discards
ability matched to the self-discard leaf; a graveyard-to-hand return matched to a
battlefield-bounce leaf). An earlier sample, before the Saga-chapter filter, had 6-7 bad links in
49: a Saga chapter that returns a card from a graveyard matched to the exile leaf, Helvault's
return-exiled-cards trigger matched to an exile leaf, a flicker-leaf match for a plain exile,
"exile a card from a graveyard" matched to "shuffle graveyard into library". About **7-13% of
links are wrong or doubtful**, and the cause is consistent: tokens are blind to zones and
destinations, to counter type, to player scope, and to everything after a chain's first effect. Several
correct matches carry a leaf whose derived phrase or branch label does not describe its members
(e.g. "Tapper" on "enters tapped", "Bounce removal" on graveyard returns); that is the leaf
label, not the match. This is why these are suggestions.

**Open design decision (logged, not built): ability-level clustering.** Placed cards stay one-leaf.
The probe shows leaves were built from blended card vectors, so a multi-ability card clustered
into a combined leaf is a worse fit per ability than per card (best single ability >= 0.90 against
its own leaf on 59% of multi-ability faces, against 72% blended), and 718 of the 737
two-ability cards in the 0.70-0.80 band match two *different* leaves almost perfectly. So
the question is whether a card should be allowed several leaves, which would change
leaf membership, counts, centroids and every cohesion number, and needs the token blind spots above
fixed first. Not decided; nothing in this layer prejudges it. Placement rules for the "also fits"
links, if ever promoted to placements, would need at least: zone / destination and counter type in
the tokens, chain steps beyond the first effect, mode handling, and a rule for generic leaves.

---

## 9. Ability-level placement (2026-10-09)

**What it does.** Placement used to score a card as a whole, so a two-effect card with one perfect
ability scored about 1/sqrt(2) = 0.71 against it and missed the 0.80 floor: the good ability was
blocked by its sibling (Shuri, Wakandan Inventor: a cost-reduction static scoring 0.9998 against
leaf 465, a copy ability at 0.45, blended 0.61). Now each ability is judged alone
(`src/ability_rules.py`, `src/build_ability_layer.py` -> `build/ability_layer.json`), and a card with
one ability that clears the rule is placed in that ability's leaf, like any other placed card:
it is listed with the leaf's members, counted in the placed total, and shows the matching ability's
text. Method `ability` (placement data only); the ledger keeps `placed_by_ability` as an internal
status (13 statuses, 78 pairwise checks), as `keyword_only` is for the keyword layer; the stage the
card stopped at stays in `evidence.pipeline_status`. Its remaining abilities are shown as plain card
detail, with any "also fits" suggestion for them (section 8) unchanged.

**The rule (per ability).** Scored against the clustering's own tokens, IDF and centroids, and
all of: >= 0.90; a *specific* leaf (>= 3 tokens, <= 300 cards); has rules text; the card and item
are not flagged by the condition-drop detector; the card is not modal; and three token-blind-spot
checks: (type) the effect is not ChangeZone / ChangeZoneAll / Bounce / Discard / Counter / PutCounter(All)
/ RemoveCounter / MoveCounters / MultiplyCounter / GivePlayerCounter, and the item carries no
player_scope; (wording) every zone / player-scope / counter-type term in the ability's text appears in
>= 20% of the leaf's members; (structure) the effect node's own scalar fields and its sub-ability
chain length match at least 15% of the leaf's members with the same tokens (>= 2 of them). One leaf
per card: the best-scoring promoted ability's; a promoted ability in a second leaf is recorded as
`second_leaf`.

**Scope (first version).** Cards in "Parsed, no close group found" with a blended score of 0.50 or
more (1,662 of 4,175). Not in scope, not changed: partial / unmodelled cards, proximity-placed
cards, clustered cards.

**Result.** 716 cards placed (720 abilities). Placed coverage 24,692 -> 25,408 of 34,864 in scope
(70.8% -> 72.9%; 63.4% -> 65.3% of the 38,921 universe). "Parsed, no close group found" 4,175 -> 3,459.
No leaf centroid, cohesion figure or clustered count changes (107 hashed files byte-identical). A leaf
or branch now lists its ability-placed cards with its clustered ones.

**Hand check.** 40 promoted placements (seeded sample): 0 wrong, 2 loose (a heterogeneous leaf
"Instant and sorcery spells you control have ..." holding a creature-type pump; an enters-tapped
replacement whose +1/+1 counters the leaf does not describe). 12 abilities the blind-spot checks
held back: about 6 would have been correct (e.g. "Return target creature to its owner's hand",
"Counter target spell"), about 4 wrong. So the exclusion is conservative: it costs correct matches
as well as catching bad ones. The three known misses (Spitting Dilophosaurus, Bandit's Talent,
Dogged Detective) and Helvault are all held back. Leaf *labels* are sometimes poor (a "sacrifice a
creature" label on a leaf of "can't attack unless" statics); the placement is judged on members.

**Ability ledger** (`build/ability_ledger.json`, display-free): one row per ability item of every
in-scope card: state (placed with route and leaf, or unplaced with a reason), best leaf and score,
and for placed-by-card abilities whether the card's own leaf is the ability's best leaf. 50,672
rows over 33,215 cards. 33,333 abilities (65.8%) sit under a placed card (30,278 clustered, 2,335
proximity, 720 ability) against 72.9% of cards. Of clustered cards' abilities that have a best leaf, 65.2% best-match
their own card's leaf and 34.8% another one. Unplaced by reason: not_scored 13,960 (outside the first
version's scope), generic_leaf 806, token_blind_spot 568, below_0.90 565, modal 411, flagged 396,
no_text 230, in_between 200, second_leaf 194, no_tokens 9. Keyword-only and no-text cards have no
ability items, so they have no rows.

**Still not solved.** The tokens remain blind to zone, counter type, player scope and chain steps
after the first effect (section 8); this rule works around that, it does not fix it. Statics' dict
modes are compared by mode name only.

---

## 10. Shrinking "Not yet organized": gap cards, "No effect to group", and a measurement (2026-10-10)

**Ability placement for partial / unmodelled cards** (`src/build_partial_ability_layer.py` ->
`build/partial_ability_layer.json`). The section 9 rule, on the 5,708 gap cards, plus three conditions that
only matter when the parse has a hole: `item_gap` (the ability's own item holds an Unimplemented /
GenericEffect[?] / Unrecognized / unknown-trigger-mode node), `same_line_gap` (a gap fragment sits in the same
rules-text line as the ability, so the ability is a partial reading of it: the Spark Double pattern) and
`continuation_gap` (the face has an unread clause that starts with a continuation word: it, that, the, this,
~, then, instead, otherwise, unless, choose, ...). **456 cards placed** (334 partial, 120 unmodelled, 2
recovered; 458 abilities). The card keeps its status (the gap stays in the gap-cause ranking); only its
placement method becomes `ability`, and its unread parts are shown as plain card detail. A looser version
without the continuation test would have placed 537; it was not built. Corrections-flagged cards (Spark Double,
Toxic Deluge) are out of scope by status.

*Hand check.* 40 placements, 30 ordinary + 10 "headline-lost" (the unread / gap items hold at least as much
text as the placed ability; 194 of the 456 meet that definition). Ordinary: 0 wrong. Headline-lost: 0 wrong,
2 doubtful (Old Man of the Sea sits under "may choose not to untap" although its point is the steal effect;
Ashling's Prerogative's enters-tapped line carries a condition the leaf does not). The ability is true of the
card in every case; what a headline-lost placement can mislead about is what the card is *for*. Ten cards are
too few to call that rate stable.

**Replacement effects and costs** (`src/build_signature_layer.py` -> `build/signature_layer.json`, method
`signature_rule`). 209 of the 245 cards of "No effect to group" are grouped by an exact replacement signature
(event + scope / amount / modification / redirect), keywords never split a group, a signature needs >= 5 cards,
else a family group needs >= 5, else the card stays out; there is no catch-all. 13 groups in 5 branches. Left in
"No effect to group": 8 cards with other items, 11 damage replacements the parser recorded with no parameters at
all (unrelated cards), 6 too-rare signatures, 6 whose text redirects damage although the signature does not say
so. Coined names are flagged `coined: true` in the data; the real terms and their basis are recorded
(Comprehensive Rules 118.8 additional costs, 614.9 redirection effects, 615.7 "prevent the next N damage ...
work like shields"; "prevention shield" itself is informal; "Fog" is community slang).

*What went wrong first.* The parser records that all combat damage is prevented but drops who the damage is dealt
by or to when the card limits it, so the first "Fog" group held mostly one-creature shields (first hand check of
30: 5 wrong, over the 5% stop rule). Fixed by two text gates (Fog = the prevent clause is exactly "prevent all
combat damage that would be dealt this turn"; a prevent-shaped signature whose text redirects damage is left out)
and a rename of the remainder to "Prevent combat damage, limited to some creatures or players". Later draws of
30: 1 wrong (a naming mismatch), 1 wrong (a redirect the first gate missed), then 0 wrong. The signature layer
therefore depends on card text for these groups; the structure alone is not enough.

**Newer vanilla cards.** The 7 post-snapshot cards with no rules text join the existing "No abilities" branch
(method `vanilla_rule`); the existing rule is not changed. "No rules text: newer cards" is now empty and no
longer listed.

**Knight of the Kitchen Sink (5 recovered cards).** They are keyword-only (First strike + Protection from ...)
but the keyword layer skipped recovered cards. Route used: `build_keyword_layer.py` now also takes recovered
cards whose whole text is keywords, added after the corpus keyword frequency is taken so no other card's leaf
can move. Output diff against the previous file: 5 new face rows; leaf `kw:FirstStrike+Protection` 7 -> 12;
branch counts Protection 76 -> 81, First strike 56 -> 61 (the Protection branch's leaf order follows size);
meta cards 1,257 -> 1,262, faces 1,264 -> 1,269, leaf-kind `sig` 711 -> 716, type-audit flagged leaves 14 ->
15 (a derived count: the leaf's type mix changed). No other row changed; each face is in one leaf.

**Result.** Placed 25,408 -> 26,085 of 34,864 in scope (74.8%; 67.0% of the 38,921 universe). "Not yet
organized" 9,456 -> 8,779: gap 5,708 -> 5,252; no close group 3,459; no effect to group 245 -> 31; not parsed 29;
known parse mistake 8; newer vanilla 7 -> 0.

## 11. Measurement only: cards whose abilities match no leaf at 0.90 (2026-10-10)

No layer was built. Population: review-queue cards (clean parse, unplaced) none of whose abilities scores >= 0.90
against any leaf: **1,782** (1,604 single-ability; 1,551 have exactly three tokens). Clustered among themselves
(HDBSCAN, the clustering's own tokens and weights, `min_samples=1`, leaf selection), by minimum group size:

| min size | cards in groups of >= 5 | groups of >= 5 | groups with an effect token in the shared core | cards in such groups |
|---|---:|---:|---:|---:|
| 5 | 815 | 93 | 26 | 236 |
| 4 | 761 | 93 | - | 249 |
| 3 | 534 | 78 | - | 212 |
| 2 | 254 | 40 | - | 166 |

At size 5, 67 of the 93 groups are held together only by a target-shape token and 21 have no shared token at all,
so they are not coherent (an 11-card "nonland permanent you control" group mixes exile, return and destroy). At
size 3, 28 of 215 groups have no specific shared token. Coherent examples: 30 Sliver "All Sliver creatures ..."
statics, 22 explore cards, 7 "counter target spell with ..." cards, 6 "entering doesn't cause abilities to
trigger". About 13% of the population sits in coherent groups, so a general layer is not worth building; a narrow
one limited to groups sharing an effect token might be. Measurement files: `build/nomatch_cluster_probe.json`,
`src/probe_nomatch_cluster.py`.

---

## 12. The per-ability view is the main view; the card-level view is archived (2026-10)

**What changed.** `reports/browse.html` now shows the per-ability taxonomy (`src/build_ability_taxonomy.py` -> `build/ability_taxonomy*.json`): a card appears under every group one of its abilities fits. The card-level view
(657 clustered leaves) is archived, unmodified, in `archive/card-level-view-2026-10/` with its generators, run order and final numbers (26,085 of 34,864 placed = 74.8%, 8,779 not yet organized). **§§1-11 above describe the data
and that archived view; their numbers do not apply to the main view.** `reports/ledger.html` and `reports/card-explorer.html` are dev-only pages (they carry a banner) and still show the archived view. Full results:
[`reports/ability-taxonomy-report.md`](reports/ability-taxonomy-report.md); design: [`reports/ability-taxonomy-design.md`](reports/ability-taxonomy-design.md).

**The two coverage figures are on different bases and must not be subtracted.** Main view: **23,653 of 34,864 = 67.8%** (an unflagged group of 5 or more abilities, plus the keyword block, "No abilities" and the replacement
groups); 26,774 = 76.8% counting 3,121 cards that sit only in groups broader than they look. Not yet organized: 8,090. Archived view: 74.8%.

**Rules of the main view.** Signatures from the parse; rarest-field-first backoff at minimum 5; no level-1 groups; equipped / enchanted in the target; an ability with an object but no verb detail never falls to a bare effect type;
leaves built from clean abilities on clean cards only; abilities flagged by the dropped-condition detector held back; inline modal spells read as one ability per mode; replacement and cost rules stay in the old signature layer as a
block; three catch-all effect types mapped into real families and any effect type with no family left unplaced; **the sign class of a power/toughness change and the damage recipient are part of the signature** (round 3).

**Groups that are broader than they look (flagged, kept out of the headline).** A group is flagged when a field that splits its members is not recorded for its abilities: who draws; "return all" vs "return target"; where a
self-return comes from; what an effect applies to; whether players are hit by an "all" damage effect; who is damaged when no recipient was kept; who loses or gains life; the sign of a power/toughness change when it depends on a
count. 165 leaves, 6,010 abilities. Measured before the sign and recipient moved into the signature: the sign is recorded for 91% of the abilities in the sign-flagged leaves; a `DamageEachPlayer` recipient for 98.9%; "players hit" on
a `DamageAll` for 2.1%; who loses or gains life for 89% of such abilities. The boost / shrink / mixed leaves agree with the sign read from their members' text in 100% / 99.0% / 100% of cases.

**A field can be present and wrong.** "That player draws cards" (35 abilities) and "That player gains life" (8) record the triggering player as the subject, but the text says "you" for 32 and 8 of them. No flag applies
(the field is not absent), so these two groups' names mislead. Parser work, not a rule.

**Gap-card abilities are held out, by decision (2026-10).** A hand check of 40 gap-card abilities that pass the same-line and continuation tests came to 5.0% wrong (2 of 40: Kasmina's tutor-and-cast filed as "search into your hand", and
Xantcha's "attacks each combat" filed as "can't attack"). The bar was *under* 5%, so they stay out (2,032 abilities, 1,720 of which would place in an unflagged group). **Revisiting needs a fresh sample of about 100 on a new seed**, drawn
with the rule fixed in advance; 40 cannot separate 2.5% from 7.5%.

**Hand checks, seeds 20261008 (round 1), 20261009 (round 2 names) and 20261010 (round 3), nothing redrawn** (none of these is a measured error rate). Round 3: 30 leaves, 0 incoherent; 40 placed abilities, 0 wrong; 20 auto-names, 3 would
mislead a tester; 10 sign / recipient leaves, all consistent. Round 1: 30 leaves, 2 incoherent (both then flagged); 40 modal modes, 1 wrong. 13 of 20 "too unusual" cards that the old view grouped were grouped correctly by it.

**Known defects not fixed.** Names are generated and some are unfinished ("All triggeringsources get +N/+N", "A target gets +N/+N", "A permanent cant be blocked except by"); three of the round-3 names mislead (the commander restriction,
an alternative cost, and "each player" are missing from them); `(variant)` suffixes appear where two groups had one name. Dropped clauses (Death Cloud, Global Ruin, Spark Double) and static misreads are parse defects and remain.

**What was checked in a browser.** `src/test_browse_browser.py` drives headless Edge with real clicks and typed text (21 checks: boot, tree, leaf, "Also in", card detail, roll-up, broad note, Not yet organized with "Show more", Find a
card, keyword and replacement blocks, deep link, boost versus shrink leaves, dev-only links, dev-only banners). Small-screen layout, theme switching and scroll performance with the largest lists were not exercised.
`src/test_abilityfind.py` covers the Find-a-card logic for all 38,921 entries in a JavaScript engine.

**A name that cannot be checked against text (2026-10 naming round).** "A permanent can't be blocked except by certain creatures" (24 abilities, the `CantBeBlockedExceptBy` grant) is unverifiable against member text: none of its 24 members has ability text in the parse, so the name rests on the signature alone. It is left as is, and the automated claims check skips leaves where over half the members have no text.

## 13. Cards not meant for constructed play are out of scope; gap-card abilities are placed (2026-10)

**Step A: a real `out_of_scope` status.** `src/build_card_flags.py` (local Scryfall files, no network) writes `build/card_flags.json`: a card is flagged only if **every printing** is silver-border, acorn-stamped, tagged
`playtest`, in a "funny"-type set, or memorabilia, **and the card is legal in no format**. The legality exception exists because 170 Unfinity non-acorn cards sit in a "funny" set but are legal in Commander and the eternal formats
(found in the hand check: Bounce Chamber). Each flagged card stores a reason code (`silver_border`, `acorn_stamp`, `playtest_card`, `joke_or_test_set`, `memorabilia`) and its evidence (sets, borders, stamps, promo tags). The
taxonomy build applies the status in memory (like the "A-" Alchemy copies); the frozen `ledger.json` is unchanged. 1,464 cards in the card set are excluded (744 playtest, 458 silver-border, 128 acorn, 76 joke/test set, 58
memorabilia); their lookup entries are "Not a card in this tool: ...", and the page lists them under "Left out: not meant for constructed play". **The headline moved only because the denominator moved:** 23,458 of 34,647 = 67.7%
(26,589 = 76.7% with broad groups) became **23,066 of 33,183 = 69.5%** (26,127 = 78.7%); the numerator fell by 392 because excluded cards had been counted as grouped. Leaf formation changed a little as a result (a population change,
not a re-cluster): 19 leaves fell below 5 members (none with a hand-edited name; no orphaned corrections), 12 dropped under the display threshold of 10, 116 abilities of kept cards changed leaf.

**Known limits of the flag rule (logged, not fixed).** Cards that are not meant for constructed play but are not caught: (a) a joke card that has one ordinary-looking printing, e.g. **Blacker Lotus** (Unglued + a Secret Lair
reprint); (b) digital-only joke cards such as **Aswan Jaguar** (Astral Cards, legal nowhere, first printed 1997); (c) any joke card Scryfall does not tag. "Legal in no format" is not usable as a rule on its own: it also covers cards of
sets that have not released yet (167 cards such as the Star Trek and Mystery Booster Commander cards), digital-only Alchemy cards (123) and promo cards released before their main set. A year-old "legal nowhere" rule would add only
Blacker Lotus, Sticker sheet, Call from the Grave and Aswan Jaguar; it was declined.

**Name collisions (checked against the source data).** 8 flagged cards share a name or a face name with an unflagged card of the set (Red Herring, Joven and Chandler, Pick Your Poison, Unquenchable Fury, Fast // Furious, Bind //
Liberate, Start // Fire against Start // Finish). In every case the unflagged entry is the real card, and everything is keyed by oracle id. One real defect surfaced: the real "Fast // Furious" is stored under its first face
name "Fast", so a search for the full name found only the flagged playtest twin. Find a card now also looks up each side of "A // B" by its exact name, and a left-out entry always sorts after real cards.

**Step B: gap-card abilities are placed.** A gap card's ability that passes the same-line and continuation tests, is not flagged by the dropped-condition detector, and matches a specific leaf is placed like any other ability, method
`gap_ability` (ledger column 10, data only). Gap-card abilities never count toward a group's formation or its 5-member minimum: every leaf has the same members and size as in Step A (checked); a leaf's heading says how many of its
abilities came from cards with an unread part, and the unread part stays on the card as plain detail. 1,716 abilities (1,453 in unflagged leaves, 263 in broad leaves) on 1,463 cards. **Headline after Step B: 24,336 of 33,183 = 73.3%**
(basis: placed by an ability in an unflagged leaf of 5 or more, plus the keyword block, "No abilities" and the replacement groups); 27,590 = 83.1% with broad groups; Not yet organized 7,056 -> 5,593. This supersedes the
"gap-card abilities are held out" decision of section 12 (`GAP_ABILITY_PLACEMENT` in `src/build_ability_taxonomy.py` turns it back off).

*Evidence.* Seed 20261013, 100 abilities (one per card, text read first, reads written before the reveal): **1 wrong** (Cactus Preserve: an "animate" ability filed under "gains a keyword") and 1 loose (The Fantasticar, filed under
"Sacrifice this permanent"); the unread clause changed no assignment; 0 wrong among the 10 abilities of top-3,000 cards. Seed 20261015, after the build, 40 placed gap-card abilities (20 from top-3,000 cards, 20 from unknown-trigger-mode
or unrecognized-condition cards): **0 wrong**. Bars were 5 of 100 and 2 of 40. These samples are rough: 100 abilities cannot tell 4% from 6%, and 40 cannot show a rate.

## 14. The "Loosely grouped" browse layer for the Not-yet-organized pile (2026-10)

**What it is.** `src/build_loose_groups.py` writes `build/loose_groups.json` and `build/loose_unread.json`. The page lists them under "Not yet organized, browsed loosely": a section "Loosely grouped by effect" (family, then group)
and a list "Cards we couldn't read yet". Every group says "Loosely grouped by effect. Not checked for accuracy." It is a finding aid. **Nothing in it is a placement**: it is not read by the taxonomy build, does not touch leaves,
leaf formation, the 5-member minimum, the thresholds, the parser or the headline, and each of the 5,593 pile cards is still counted once as "Not yet organized" (placed 22,541 + broad only 3,254 + keyword 1,245 + no abilities 346 +
replacement groups 204 + unorganized 5,593 = 33,183 in scope; + 5,738 not cards = 38,921). Headline unchanged: 24,336 of 33,183 = 73.3% (basis: placed by an ability in an unflagged leaf of 5 or more, plus the keyword block,
"No abilities" and the replacement groups); 27,590 = 83.1% with the broad groups.

**How the groups are made (fields already in the parse; no text matching, no tag data).** Each usable ability of a pile card (including abilities held back for a dropped condition, abilities with an unread part, and gap-card
abilities that failed the tests; each says so) gets a key of a few fields per family (`FIELDS` in `src/probe_loose_groups_v2.py`). A key with fewer than 10 cards drops its last field, and so on; a group of more than 50 cards is split
once more by `when` (the block it came from and the trigger mode) or the object type; effect types still under 10 cards go into one bucket per family, "Less common effects, by kind", whose sub-headings are the effect types
(sub-headings under 3 cards fold into "Other kinds"). The two groups still over 100 cards are plainly labeled catch-alls with sub-headings (Destroy by object type, Continuous effect by what it does). Sub-headings are headings,
not groups. 4,293 of the 5,593 cards get a group; the other 1,300 (1,231 with an unread part, 27 not parsed, 24 no effect to group, 9 text may be lost, 8 known parse mistakes, 1 too unusual) go to the "couldn't read yet" list,
sorted by popularity with the reason on each row (80 of them are in the top 3,000).

**Limits (logged, not fixed).**
* *Copy:* the parse does not say whether a spell or an ability is copied (one effect type covers both). The group names say "Copy a spell or ability (which one is not recorded)". *Cast:* the parse has no source zone for
  "cast from ...". The names say "(the zone is not recorded)". Both are on the parser-gap worklist; neither can be split by field until the parser records them.
* A member row shows the whole rules line of the ability, so in a card with several abilities a group can look wider than its key (a card whose counter clause is one of several lines appears under the counter group).
  227 of 4,905 member rows have no ability text of their own ("it has no rules text of its own": gap-card items) and show "(no separate rules line)".
* A group can contain a card for an ability that is the weaker half of a gap card or a held-back condition; each member row says why it is not a real placement. Names are generated from the key fields with fixed wording; they are
  not edited by hand.
* The name defect check (the existing scan and claims check) found 0 hard defects and 0 claims hits in 220 names; it did not catch two kinds of fault that the hand check did (a stray trailing word, a repeated phrase), both fixed
  since. The scan also would not have caught two different groups with one name, so the build now refuses to write if any two names are equal.
* *Hand checks* (seeds 20261017 and 20261018; reads written before names and keys were looked at): 22 groups, not the 30 asked for (the over-100 stratum has 2 groups, not 10, and 23 buckets remained for the third stratum),
  0 incoherent (11 coherent, 11 loose); 40 names, 0 misleading (3 had wording warts that were fixed before the verdict was written). 22 groups and 40 names cannot show a rate. The checks are not independent of the generator:
  the same model wrote the wording and the reads. What is independent of it is the fixed seed, the member text (taken from the parse's own rules lines), and the machine counts (reconciliation, hashes, identical builds).

## 15. Tentative placements: loose groups promoted, beside the main groups, never counted as organized (2026-10)

**What it is.** `src/build_tentative.py` promotes some loose groups (section 14) to **tentative placements** (method `loose_tentative` in `build/tentative_ledger.json`; `min3_tentative` is reserved and not built). The page shows them in a
"Tentative groups" row at the end of each family and on the group pages with a **tentative** badge and the wording "Tentative placement: grouped by effect type, not fully checked."; Find a card and the card page name them. A header checkbox
("show tentative placements", on by default) hides every tentative placement, the third figure, and puts the cards back into the pile count. **Nothing in the taxonomy build, the leaves, leaf formation, the 5-member minimum, the thresholds,
the placement rules, the parser, the headline's definition or the loose layer reads the tentative layer.** The build still lists every tentative card as "Not yet organized"; `tentative` is a derived field in new files, and the page subtracts it.

**Three figures, always with their bases.** Precise 24,336 of 33,183 = 73.3% (placed by an ability in an unflagged leaf of 5 or more, plus the keyword block, "No abilities" and the replacement groups). With broad 27,590 = 83.1% (plus 3,254 cards
whose abilities sit only in groups broader than they look). **With tentative 29,457 = 88.8%** (the broad figure plus 1,867 not-yet-organized cards with an eligible ability in a tentative group). The archived view's 74.8% is on a different
basis. Reconciliation: 27,590 placed + 1,867 tentative + 3,726 still unorganized + 5,738 not cards = 38,921; each card is counted once.

**Rules.** Candidates: the 195 plain loose groups (not the two catch-alls, not the "Less common effects, by kind" buckets). An ability is eligible only if it is not held for a dropped condition, has ability text, and is not a gap-test failure.
A group is promoted if my blind read of up to 8 eligible members (seed 20261021) is coherent or loose, its name states the effect, it has at least 5 eligible cards, at most half its cards are text-less, and it is not both loose and a backoff
residual. The reads are `corrections/tentative_groups.json`; the build applies the rules. A card appears under every tentative group one of its eligible abilities fits. Abilities with an unread part stay in, and every such row says "part of the ability was not read".

**What each hold removed (cards).** Scope as first measured: 168 groups, 2,256 cards. Hold the 10 groups that are both loose and backoff residuals: 158 groups, 2,107 cards (-149). Hold the gap-test failures as well: 145 groups, **1,867 cards (-240 more;
-247 if applied alone)**. Attach was held under the text-less rule before these numbers (51 of its 64 cards have no ability text; it has 13 eligible cards). Of the 1,867, 791 rest on at least one rare-shape ability of a clean card and 1,076 rest only
on abilities with an unread part.

**Limits (logged, not fixed).**
* A tentative placement is a text-and-field reading of one ability, not a checked placement. Abilities with an unread part can mean more than their read part says; they are marked as such and could be held in a later version (counting only rare-shape abilities would give 791 cards).
* Copy (spell versus ability) and Cast (source zone) are still not recorded by the parser; their groups keep the honest names, and the Cast group is not promoted (its members also hold can't-cast restrictions).
* Some effect types are mis-typed by the parser: "Second Sunrise" (returns cards from the graveyard to the battlefield) is filed under "Return things to their owners' hands". It was the one wrong placement in the 40-placement check.
* The ledger file is new data only (`build/tentative_ledger.json`); `ability_ledger.json` and every existing status are unchanged.
* The group names are the loose names; "Deal damage in another form to a creature, all of them" was reworded to "Deal damage to each creature" (and its fallback to "Deal damage to many things at once").

**Checks (rough: small samples).** Names: 20 promoted names hand-checked against the members (seed 20261022): 0 misleading; the defect and claims checks found 0 in 168 names. Placements, seed 20261020, 40 drawn (20 rare-shape abilities, 20 unread-part abilities;
text read first, my read written before the group was shown): **1 wrong, 5 loose, 34 right**; by stratum: rare-shape 1 wrong of 20, unread-part 0 wrong of 20. Bars: more than 5 wrong overall, or more than 3 of 20 in one stratum, would have turned the layer off or held the stratum:
neither was tripped. **40 cannot show a rate** and the reads are not independent of the generator (the same model wrote the group wording and judged it). Independent of it: the seeds, the member text, the counts, the hashes, the reconciliation, the browser run.

## 16. Tentative promotions, second round: renamed groups and sub-headings; what the dropped-condition flags really are (2026-10)

**Figures (this supersedes the numbers in section 15; the rules there still hold).** Precise 24,336 of 33,183 = 73.3% and with broad 27,590 = 83.1% are unchanged. **With tentative: 29,683 = 89.5%** (the broad figure plus 2,093 not-yet-organized cards with an eligible ability in a tentative group).
Pile 5,593 -> **3,500** still not yet organized. Reconciliation: 27,590 placed + 2,093 tentative + 3,500 unorganized + 5,738 not cards = 38,921. Each tentative card is still a "Not yet organized" card in the build; the page subtracts it.

**What was promoted.** 177 tentative groups (145 plain, 2 renamed, 30 sub-heading groups); 226 cards are new (49 from the renamed groups, 177 from the sub-headings; 231 were expected).
* *Renamed groups.* Three groups had been held only because their name did not say what they hold. Two are promoted under new names ("Give a creature an effect like can't attack, can't block or can't be blocked"; "Continuous effect, only as long as something is true", which claims no subject because its
  members apply to this permanent, a paired creature or an equipped creature). The third ("Give things a combat effect like can't block or can't be blocked, other kinds of target") reads loose and is a backoff residual, so the existing hold on loose residual groups keeps it out (5 cards): that is why 226, not 231.
* *Sub-headings.* A promoted sub-heading of a catch-all or a "Less common effects" bucket becomes a tentative group of its own, named from fixed wording ("Continuous effect on other kinds of target: gives deathtouch", "Destroy a permanent", "Connive", ...). The catch-alls and the buckets themselves are not promoted and are unchanged in the loose layer. A card is counted once however many tentative groups hold it.
  The rule is the same as for plain groups (hand read not incoherent, the name states the effect, at least 5 eligible cards, at most half text-less); the reads are in `corrections/tentative_groups.json` (`subheadings`). Two sub-headings that read loose were re-read on a fresh seed (20261024): "gives flying" stays; "adds a creature type" stays only as "adds a creature or land type" (half its members add a land type).
* New wording: "adds a creature or land type", "Double counters, life or mana", "Can attack as though it didn't have defender".

**The unread-part switch.** `HOLD_UNREAD_PART_ABILITIES` in `src/build_tentative.py` (default False: unchanged) turns off, alone, the placements that rest on an ability with an unread part. With it on: **805 tentative cards, with tentative 28,395 = 85.6%, pile 4,788**.
Of the 2,093 tentative cards, 1,159 rest only on abilities with an unread part and 934 have at least one rare-shape ability. `PROMOTE_RENAMED_GROUPS` and `PROMOTE_SUBHEADINGS` turn the two new promotions off separately.

**Dropped-condition flags are almost all real (measured; corrects an earlier claim).** The 44% false rate in section 4 was the old quick heuristic's, not the detector's: the detector cleared those false positives (reports/condition-drops.md). A fresh read of 100 of the detector's 1,606 held abilities on cards still in the pile
(seed 20261023, one per card, stratified by sub-shape, my verdict written before the detector's evidence was shown) found **84 real drops, 15 unclear (almost all because an Unimplemented node holds the clause) and 1 false flag** (a condition that belongs to the other face of a double-faced card): a false-flag rate of 1% (95% range 0.2-5.4%; 100 reads cannot show a rate).
Lifting false flags would therefore move almost nothing; the 1,342 dropped-condition cards are a representation or parser problem. The detector's benign sub-variant "search this way -> shuffle" (39 abilities) is a separate policy choice, not lifted: see `reports/false-flags-and-promotions.md` and `build/benign_shuffle_flags.json`.

**Limits (logged, not fixed).**
* "Continuous effect, only as long as something is true" holds some members that are not "as long as" clauses (Wall of Stolen Identity, an enters-as-a-copy clause, sits in it), and "Set a life total" holds a member that sets a creature's base power (Baffling Defenses). Both were the one wrong placement in their stratum.
* The wording of the as-long-as group changed after the 40-placement check (from "applies" to "only", for a vocabulary check); the meaning is the same.
* The 20-name hand check and the claims check were run on the proposed names; one wording was then changed, as above.

**Checks (rough: small samples).** 40 placements, seed 20261026 (20 from the renamed groups, 20 from the sub-heading groups; ability text read and my read written before the group was shown): **35 right, 3 loose, 2 wrong** (renamed groups 1 of 20, sub-headings 1 of 20). Bars: more than 5 wrong overall, or more than 3 of 20 in a stratum, would have
turned the new promotions off or held the stratum: neither tripped. **40 cannot show a rate** and the reads are not independent of the generator. Independent of it: the seeds, the member text, the counts, the hashes, the reconciliation and the browser run.

## 17. Condition annotations: abilities held for an unread condition, shown in the group they would belong in (2026-10)

**What it is.** `src/build_annotation.py` -> `build/annotation_placements.json`, `build/annotation_ledger.json`. An ability the dropped-condition detector holds is shown, beside the tentative groups, in the leaf (or tentative group) it would belong in if the condition were ignored, with the unread text quoted on the row and a dotted "Condition not read" badge: "This ability has a condition the tool did not read: '...'. The condition may change what the ability does." (with ", or make it do something else instead" where an instead / otherwise / unless / if-you-don't branch exists, and ", even to the opposite" where the shown condition is itself an unless / if-you-don't). Method in the data: `condition_unread`. Flags in the build: `ANNOTATION_LAYER`, `HOLD_CONDITION_ANNOTATION` (the condition stratum off alone), `HOLD_GAP_STRATUM` (the gap-test stratum off alone). Page switch: "Show condition annotations".
**Figures (four, on one basis of 33,183; none replaces another).** Precise 24,336 = 73.3% and with broad 27,590 = 83.1% and with tentative 29,683 = 89.5% are unchanged. **With condition annotations: 30,643 = 92.3%** (the tentative figure plus 960 pile cards). The gap-test stratum is a **separate line, never blended: 30,803 = 92.8%** (plus 160 more cards). Pile 3,500 -> 2,540 (2,380 with the gap-test stratum). Reconciliation: 27,590 + 2,093 + 960 + 2,540 + 5,738 = 38,921 (the 160 are counted separately, 2,540 - 160 = 2,380).
**Rules.** Candidates: held abilities with text whose leaf (condition ignored) is unflagged, or whose promoted tentative group exists. Not annotated: the broad route (317 abilities, 302 cards: they stay in their loose groups; annotating them would be its own flag and its own sample), abilities with no leaf (282), with no condition word in their text (14: the detector's flag belongs to another ability or face of the card: a flip or transform side, or a neighbouring ability), and the shared-verb exclusion (38 abilities: the leaf's key verb occurs only in the cost or the "you may X" lead-in before an "If you do / When you do / If you don't / Unless you" sentence, as in Akuta, Born of Ash). A card is counted once: 38 of the 998 condition-annotated cards were already tentative and gain the badge row, no extra count.
**Gap-test stratum.** Cards held by the gap test only (continuation and same-line failures; no-text cards excluded), one ability per card, leaf unflagged or a promoted tentative group, badge "Card part not read": "This ability was read, but another part of this card was not: '...'". Method `card_part_unread`. 169 cards, 160 of them new; 11 more were left out because the ability is a rule the tool describes rather than a line of the card (a saga's lore counter).
**Limits (logged, not fixed).**
* The extractor shows the first condition and its branch. A sibling condition ("If it's the second time...", "If it's the third time...") on a later sentence is not shown; of the 1017 abilities, 270 have an inversion word somewhere in the ability, and in 33 of those it is not in the text shown on the row (a later sentence).
* The shared-verb rule keeps abilities whose verb also occurs in the effect, and some of those are still mis-filed (Part 1 read: 18 of 20 retained correct, 1 loose, 1 wrong); it also removes some correct placements (15 of 20 removed were rightly removed, 5 were collateral).
* A row can show the card's own name where the oracle text says "this creature" (20 rows; the tool's own rendering), and the leaf names an ability by its head effect, not by its condition: "Destroy a land" under a card that also deals damage to the land's controller.
* Counts of the condition stratum depend on `build/remaining_cards.json` (for the gap-test stratum) and `build/condition_drops.json`; rerun `src/probe_remaining.py` after a change to the tentative layer.
**Checks (rough: small samples).** Placement check, seed 20261029 (set before computing; ability text, unread text read and my read written before the group was shown): condition stratum 40 (20 sequential-chain, 20 other sub-shapes): **34 right, 4 loose, 2 wrong** (sequential-chain 17/3/0; other sub-shapes 17/1/2). Bars (more than 5 wrong overall, more than 3 of 20 in a stratum): not tripped. Gap-test stratum, 20 placements all from the same-line failure (oversampled on purpose): 18 right, 2 loose, 0 wrong. Of the 40 condition placements, **13 would be misread by a tester who saw only the ability and its group**: the unread condition gates or changes the effect (a kicker, a "surge", "if you attacked", "if it was enchanted or equipped"). The two wrong: Thunderscape Battlemage (the group is the card's other trigger, destroy an enchantment) and Brood Birthing (the group names the grant on the tokens, not creating them). 40 and 20 cannot show a rate; the reads are not independent of the generator.
The gap-test sample (Part 2, seed 20261028; 33 right, 5 loose, 1 wrong, 1 no leaf of 40) read three times the synthesized saga lore-counter ability, which the build now leaves out.

## 18. The community-tag layer: the 1,300 cards with no readable ability, grouped by Scryfall community tag (2026-10)

**What it is.** `src/build_tag_layer.py` -> `build/tag_placements.json`, `build/tag_ledger.json`; page section "Grouped by community tag" beside "Cards we couldn't read yet", with a tag filter on that list. Method in the data: `community_tag`. Flag: `TAG_LAYER`; page switch "Show community-tag groups". Every card says "Grouped by community tag. Not checked against the card's parsed text.", the tag, and the date of the tag snapshot (2026-10-14; the page turns the line red when the snapshot is more than 60 days old). This is the one place in the project where tag data is used in placement, by decision, because these cards have no readable structure; tags never enter the main tree, the tentative layer or the annotation layer, and the layer is never counted in the first five figures.
**Source and what it is not.** The tags are Scryfall's community Tagger tags (`data/oracle-tags-20261014.json`, 4,577 tags, fetched by `src/fetch_tags_probe.py`; the old snapshot of 2026-07-16 in the card_function_search project was not touched). They are the same vocabulary that project's otag glossary is built from, so nothing here validates a tag; they are independent of our parser. The layer says "community tag", never "verified".
**Filter.** Existing rules (type oracle, a floor of 20 taggings, the card_function_search denylist) leave 1,131 tags; `corrections/tag_denylist.json` denies 108 more that describe design, errata, names or templating, not effects (errata 20, name or flavor trivia 50, templating or rules jargon 21, set design or vague 17): 1,023 functional tags. Groups of 5 to 100 of the 1,300 cards: 350 -> **312**; cards reached 1,255 -> **1,205** (the deny list costs 50 cards; none gains). A first pass missed the prefix `type-addition-` (errata); it surfaced as one wrong placement in the check and was added afterwards (the check was not redrawn).
**Figures (the sixth, on its own line; none replaces another).** Precise 73.3%, with broad 83.1%, with tentative 89.5%, with condition annotations 92.3% and the gap-test stratum 92.8% are unchanged. **With the community-tag layer: 31,848 = 96.0%** (the 92.3% figure plus 1,205 cards), described as "browsable by community tag", not organized. Pile 2,540 -> **1,335** (1,175 with the gap-test stratum on). Reconciliation: 27,590 + 2,093 + 960 + 1,205 + 1,335 + 5,738 = 38,921. The 160 gap-test cards are separate and none is in the 1,300.
**Cards without a group.** 95 of the 1,300 are not in any group: 43 carry no functional tag; 52 carry only tags that are too rare (under 5 of these cards) or too broad (over 100: `evasion`, `single-target-instant-sorcery`, `repeatable-crime`; 21 cards carry only those three). Broad tags are filters in "Cards we couldn't read yet", not groups; these cards stay in that list and in the pile with the text "No community-tag group yet".
**Names.** Fixed rules (`src/tag_layer_names.py`: "Cares about ...", "Removal: ...", "Works against ...") name 154 groups (name_source `rule`); 158 are written by hand in `corrections/tag_names.json` (`model_written`); a `user_edits` section overrides both (`user_edit`; empty now). Checks: 0 structural defects, 0 duplicate names, 0 claims hits, longest name 82 characters; the vocabulary flags (35 plain-English words such as "alternative", "strategy") are allow-listed in the same file. Hand check of 30 names: 22 fine, 6 loose or awkward, 2 misleading (both reworded). A re-read of 12 reworded names (seed 20261041, set before the draw): **0 misleading, 1 loose** ("Cares about haste (often in a list of keywords)"); bar 10%: not tripped. The three loose names left untouched at first ("Removal: permanent", "Prevents damage to a player", "Protects creature") were reworded ("Takes permanents away from players, often at random or for everyone"; "Halves or redirects damage to players and creatures"; "Protects creatures, or works around their protection"): the tags mix cards that do different things, so the names now say what the members do.
**Limits (logged, not fixed).**
* A tag group is only as coherent as the volunteers' tagging: a few groups mix cards (the `scry-like` group is clash cards; `peek-hand` is mostly cards that exile a named card from hand, graveyard and library), and some tags are awkward by nature ("Out of color token", "Gains +1/+1 counters").
* The deny list is hand-written from the groups of 5 or more among the 1,300 and a word scan; a design or templating tag that is smaller, or that the scan missed, can still form a group (`out-of-color-token` is a judgment call and is kept).
* The other 1,240 not-yet-organized cards are not in the layer (no 40-card read of those causes exists). The snapshot is a file; a new tag update needs `src/fetch_tags_probe.py` and a rebuild.
**Checks (rough: small samples).** Placement check, seed 20261039 (set before computing): 40 placements, one per card, **20 from the 73 cards in the top 3,000 (oversampled: 27% of that pool) and 20 from the other 1,134**; card text read and my fair description written before the group was shown: **26 right, 13 loose, 1 wrong**; top 3,000: 12 / 7 / 1; the rest: 14 / 6 / 0. Bar (more than 5 wrong of 40 turns the layer off): not tripped. The wrong one: Silent Arbiter under "Type addition from none", an errata tag (now denied). **40 cannot show a rate, the oversampling means it is not a rate over the layer, and the reads are mine, not independent of the generator.**

## 19. Placing cards by hand: the edit panel, suggestions and the work queue (2026-10)

**What it is.** A right-hand edit panel on the card page of `reports/browse.html`, a "To place" work queue and a corrections file, so that cards the tool had nowhere to put can be placed by a person now, before the parser work. New files only: `src/manual_common.py` (validation, the write path, the resolver), `src/build_manual_layer.py` -> `build/manual_index.json`, `build/manual_layer.json`, `build/manual_ids_seen.json`, `reports/manual-placements.md`; `src/build_manual_suggestions.py` -> `build/manual_suggestions.json`; `reports/manualedit.js` (page logic); `POST /api/manual` in `src/serve.py`. The one file ever written is `corrections/manual_placements.json`. No generated file is edited by the tool; no leaf, leaf formation, threshold, parser, detector, phase.rs or any of the six figures (73.3 / 83.1 / 89.5 / 92.3 / 92.8 / 96.0) changes. Flag `MANUAL_PLACEMENTS` (in `src/build_manual_layer.py`; off writes nothing and removes this layer's own files, and the build is byte-for-byte the one without it) and the page checkbox "Show hand edits".

**Counting (agreed before building; a hand edit never moves a card between the existing figures).**
* *Placed by hand* (its own line and badge, never added to another figure): a pile card ("Not yet organized" and in none of the tentative, annotation or tag layers) with a valid hand add; it leaves the pile and counts once. As built, no card was placed by hand (the tests use a temporary file); real use has since started, and `reports/manual-placements.md` holds the current counts.
* *Confirmed by hand*: a tentative, annotation or tag card with a valid hand add. It stays in its own figure and is reported as a sub-count (of which tentative / annotation / tag). *Edits on precisely placed cards* take edits that count nowhere. *Marked "nothing fits"* is its own count and never a placement. A removal is recorded and shown (struck through) and changes no generated count.
* Reconciliation: 27,590 placed + tentative + annotation + tag + by hand + unorganized + 5,738 not cards = 38,921, each card in one bucket (today 27,590 + 2,093 + 960 + 1,205 + 0 + 1,335 + 5,738). The 160 gap-test cards are inside unorganized, as in section 17. Unsaved edits (an endpoint that is missing) are shown with a red NOT SAVED badge and are counted nowhere.

**Groups offered: 1,901.** leaf 1,245 · tentative 177 · loose 48 (the plain loose groups that are not tentative; a promoted loose group is offered once, as its tentative group) · community tag 312 · keyword block 106 · replacement block 13. Not offered: the 2 loose catch-alls and 23 "less common effects" buckets (a hand-filled Miscellaneous), and the 404 annotation groups (views of a leaf or tentative group). Ids: `leaf:` + the leaf id (sha1 of the signature), `tent:` / `loose:` + the loose group id (sha1 of the group key; sub-heading ids are sha1 of parent and label), `tag:` + the Scryfall tag UUID, `kw:` + the keyword signature (`kw:Affinity+Flying`), `rp:` + the replacement rule name (`rp:cost:additional`). Keyword and replacement ids are rule-derived names, not hashes. Stability: of the 1,273 leaf ids in the Oct 8 build, 1,239 (97.3%) are in the Oct 9 build, across the gap-card and out-of-scope changes; the 34 that vanished are what an orphan looks like. `build/manual_ids_seen.json` records every id offered so far, and every build reports "ids seen before and missing now" and "renamed since first seen"; it was started with this build, so it has no churn to report yet. An edit stores the group's name when it was made, so a rename is reported as a rename and an id that disappeared as an orphan. An orphaned edit is listed on the console, in `build/manual_layer.json`, in `reports/manual-placements.md` and on the page, and is never remapped or dropped.

**Suggestions (labelled "Suggestion, not a placement"; nothing is placed until Add is pressed).** Three sources merged by group id, top 5 per card: *signature* (each usable ability, held ones included, against the leaves of the same family and effect type; (2 + shared fields) / (2 + fields in either), capped at 0.50 when nothing beyond family and effect type matches), *community tags* (the card's functional Scryfall tags against the placed cards of each leaf: F1 of "share of the tag's placed cards in the leaf" and "share of the leaf that has the tag", at least 3 cards and F1 of at least 0.10; a tag group that exists for one of the card's tags scores 0.50) and the card's own *loose / tentative groups* (0.35). Merged score = highest source score + 0.10 per further agreeing source (cap 1.0). The number is agreement between card and group, not a probability.
*Checks (rough: small samples; the reads are mine, written from the card text before the suggestions were looked at, and are not independent of the design).* First sample, seed 20261050, 30 pile cards: a sensible group in the top 5 for 27 (90%; 21 at rank 1, 26 in the top 3); the two fixes above (the 0.50 cap, the F1 floor) were chosen after seeing its failures, so it is not evidence for them. Hard stratum, seed 20261051, 10 of the 95 cards with no readable ability: 3 of 10 (5 had no tag and got no suggestion). **Fresh sample after the fixes, seed 20261060, 30 pile cards: 24 of 30 (80%; 21 of 30 = 70% if three marginal calls are dropped), 20 at rank 1, 23 in the top 3.** Misses: Relic Robber, March Toward Perfection, Cogwork Spy, Goblin Brawler, The Horus Heresy, Dueling Grounds (by cause: held group 10 of 12, gap-test stratum 6 of 6, no readable ability 2 of 4). 30 cannot show a rate, and the 80% is for pile cards drawn at random, which are mostly cards whose abilities do match a leaf and are held for another reason: the 47 pile cards with no suggestion at all (all within the 95 that cannot be read) rely on the search box.
**Limits.** The signature score does not know direction (a card that removes a keyword scores against the leaves that grant one: Mystic Decree, Humility); parser-typed boilerplate such as "Put lore counters on this permanent" (sagas) scores 1.00 and says nothing; a hand placement into a leaf that the tool held back for an unread condition places the card there without that condition (the panel shows the unplaced reason, and the page labels the placement as by hand and unchecked); a card in several groups takes several adds; the search lists groups by name and size only (17 leaf names are shared: the path is shown to tell them apart).

**The endpoint** (`POST /api/manual`, `GET /api/manual/ping`; `src/test_manual_endpoint.py`, 43 checks): the body is capped at 8 KB; unknown fields, a malformed id, an unknown card (404), an entry that is not a card, an unknown group or layer, a group that is not offered, a bad action, a note over 500 characters (control characters are stripped), a remove of a group the card does not hold, an add of a group it already holds precisely (409), a remove of a hand add (use undo) and a nothing-fits on a hand-placed card are refused with a reason; `Content-Type: application/json` plus `X-Manual-Edit: 1` are required (a cross-site POST cannot send them) and the Host must be local. Writes are serialized (a lock and a lock file), the file is re-read first and refused if it is corrupt (never overwritten), written to a temp file in the same folder, flushed, fsynced and renamed, with the last good file kept as `.bak`. 60 concurrent distinct edits all landed; 20 concurrent writes to one key left one entry; a failed rename left the original byte-identical. If the server has no endpoint (a plain static server), the page applies the edit provisionally and shows NOT SAVED (red badge, banner with Retry and Download); unsaved edits survive a reload in this browser's local storage, are not counted, and are not lost silently.

**Checks of the page** (`src/test_manual_browser.py`, headless Edge over the DevTools protocol, a temporary corrections file; clicks are DOM `click()` calls and the search box is typed with real key events; no touch or pointing device, no other browser): see the list in the README. `src/test_manual_logic.py` runs `reports/manualedit.js` against the Python resolver on the real data. `src/test_abilityfind.py` covers the new Find a card wording (18 hand-placement cases); `reports/findcard.js` (the archived view's) is untouched and hash-identical.

## 20. The keyword facet: a filter, not a placement (2026-10)

`src/build_keyword_facet.py` -> `build/keyword_facet.json` (flag `KEYWORD_FACET`; off writes nothing and removes the file). Page: a "Keyword" filter on the Cards tab and a "By keyword" list in the tree, both labelled "a filter, not a placement". It lists the in-scope cards that carry a parsed keyword (the `keywords` field of the parser's record, faces merged to the oracle id, recovered cards included) wherever they are placed, and each row shows the card's placement beside the keyword. It writes one file, reads no placement, adds no status, group, bucket or id, and changes none of the six figures (checked: the generated layers are byte-identical around a build).
**Counts (all 33,183 in-scope cards, not only keyword-only ones).** 172 distinct keywords; 167 have 5 or more cards, 155 have 10 or more; 12,906 cards carry at least one (1,245 of them are the keyword-only cards in the keyword block; 1,959 are not precisely placed). Flying 3,255, Enchant 1,246, Trample 1,032, Vigilance 752, Haste 674. **Mutate is in the parser's list**: 34 cards (22 placed, 8 broad-only, 3 pile, 1 tentative), and Scryfall also lists 34.
**The parser's list is narrower than Scryfall's.** Scryfall's `keywords` for the same cards holds 836 names, 665 of them with no parser keyword: it also includes keyword actions and ability words (Mill 593 cards, Scry 431, Transform 426, Treasure 363, Regenerate 271, Landfall 193, Fight 149, Investigate 138 ...). Counts differ even for shared names (Cycling 302 here, 404 on Scryfall). The page and the file say so. **Limits.** It is exactly the parser's keyword field, with that field's gaps; a card is listed once per keyword, not once per face; the facet is not used to place anything (a keyword rule in a hand-defined group only suggests).

## 21. Hand-defined groups: rules that only suggest (2026-10)

`corrections/hand_groups.json` (hand-edited; no endpoint writes it; format in `src/hand_groups.py`), `src/build_hand_groups.py` -> `build/hand_group_hits.json`, `reports/hand-groups.md` (flag `HAND_GROUPS`). A group has a slug (id `hand:<slug>`, chosen once, never derived from the name, rules, members or the build, never reused), a name, a note and rules of three types: `text` (literal phrases, folded for case and curly apostrophes, matched inside one sentence, with a `not` list that voids a match when the same sentence holds a `not` phrase), `keyword` (reads the facet) and `tag` (a Scryfall community-tag slug). No regular expressions, so no rule can hang a build. A rule match is a SUGGESTION: it never places a card and never moves a count. A member is a person's Add click (group id `hand:<slug>` in `corrections/manual_placements.json`), counted on the existing "placed by hand" line. **Tombstones:** `retired: true` removes the group from the search and from suggestions but keeps its id resolving, so no placement into it is orphaned; deleting the entry orphans them (reported on every build). Page: a "Hand-defined groups" list, a group page (members placed by hand first, then the rule matches with the card's own sentence as the reason), a dashed "hand group" badge, the group in the panel's search (layer "hand-defined group") and as a suggestion (source "hand-group rule", scored by the rule's confidence; 40 cards have it in their top 5: 13 pile, 14 tentative, 9 annotation, 4 tag).
**The seeded group, `hand:wins-or-loses-the-game` ("Wins, loses or draws the game, or stops it").** Read first, then defined (2026-10-15): all 107 text matches (the four phrase families "you win the game", "loses the game", "can't win", "can't lose" on all in-scope cards, after taking out the 15 cards whose only match is the poison reminder line "A player with ten or more poison counters loses the game.") and the 10 cards that carry a win/lose community tag but no text match. **False hits.** The 15 poison reminders (12% of the 122 raw matches; 3 of the 30 listed on 2026-10-14) are the false hits, and the rule's `not` entry removes exactly those: a test checks that none of the 15 is matched and that none of the matches' sentences holds "poison counters". Of the 107 read, none was a clear false hit. About 9 cards react to a player losing rather than cause it (Blood Tyrant, Elbrus, Sengir, Curse of Vengeance, Miss Highwater, Share the Spoils, Ramses and a few more; they are on topic and kept), and 2 were weak (Hot Pursuit, Rampant Frogantua: "if two or more players have lost the game", "for each player who has lost the game"); the rule does not match "lost the game", so those two are out. Of the 10 tag-only cards, 2 are on topic and were missed by the narrower patterns (Celestial Convergence: "the player with the highest life total wins the game"; Divine Intervention: "the game is a draw"), so the rule has the phrases "win the game", "wins the game" and "the game is a draw"; the other 8 are tag noise (a coin "win the flip", 20 damage, a saga that draws seven cards), so the seed group has **no tag rule**. Result: 107 cards (56 placed, 9 broad-only, 13 pile, 15 tentative, 10 annotation, 4 tag; the 42 that are not precisely placed are what the panel can offer). Not done: no recall estimate, and the cards the phrases do not reach (a "loses the game" spelled another way) were not searched for.
**Limits.** The sentence cut is regular but not a parser (a bracketed reminder or a modal bullet is one sentence); a `not` entry removes a whole sentence's match, so a sentence holding a real win and a `not` phrase is lost (none of the 107); two groups can suggest the same card; the keyword rule inherits the facet's gaps; a retired group's placements stay and are shown; with `HAND_GROUPS` off the hand-defined groups leave the index, so a placement into one is reported as an orphan until the flag is on again.

## 22. The sibling-of-leaf rule: tentative placements for the plain variant of a group (2026-10)

`src/build_sibling.py` -> `build/sibling_placements.json`, `build/sibling_ledger.json` (method `sibling_tentative`; flag `SIBLING_RULE`; page switch "Show sibling placements"; badge "sibling"). **Why.** A leaf is formed from abilities after the rarest-field-first backoff has dropped their extra details; a *plain* ability has nothing to drop, so it is counted only with its exact twins and is held (`rare_object`, `rare_verb_parameter`, `below_minimum_size`) even though its signature equals the leaf its detailed relatives formed. Putrefy ("Destroy target artifact or creature. It can't be regenerated.") is the example: clean parse, no gap nodes, no dropped-condition flag, suggestion score 1.00 against "Destroy an artifact or creature" (10 cards), held because only 2 clean abilities share its exact tuple. The rider was not the cause. Across cards not precisely placed, 17 are held only by an unread "can't be regenerated" rider and 6 of those would land in a leaf; this rule does not address them.
**Rule.** An ability of a card that is not precisely placed (pile, tentative, annotation, tag), held for one of those backoff reasons, not flagged and not gap-held, whose non-empty fields equal exactly one unflagged leaf's signature, is placed in that leaf tentatively. **27 abilities on 27 cards in 20 leaves** (21 tentative cards, 6 pile cards; none ambiguous). **Read before it was built** (seed 20261080, set before computing; the population is exactly the 27, so the seed fixed the reading order; ability text only, my read written first, then the leaf shown): **24 correct, 2 loose, 1 wrong**. Wrong: Summoner's Egg's enters-the-battlefield "exile a card from your hand face down" under "Alternative cost: exile a card from your hand rather than pay the mana cost". Loose: Merfolk Spy (reveals a card at random from the hand, under "That player reveals their hand") and Broadside Bombardiers (the group names the sacrifice cost; the ability has no text of its own). The bar was no more than 2 wrong; read strictly (loose counted as wrong) it would have been 3, so treat the rule as tentative accordingly.
**Counting.** Tentative, flagged, reversible, and counted in **no** figure: the six figures do not move and no card changes bucket (the 6 pile cards stay in the pile count, the 21 tentative cards stay tentative); the page's sibling line gives its own count. In the edit panel a sibling placement is a source ("sibling") with a Remove button: a removal is recorded and shown, and changes no generated count; the switch hides all of it. **Limits.** 27 abilities are a small population and one reader read them; the rule trusts signature equality, which cannot see that two abilities with one signature mean different things (the Summoner's Egg case); it is for cards not precisely placed only (an unplaced ability of a placed card is not touched); it closes a symmetry gap in the backoff for placement only and does not change a leaf, leaf formation or a threshold.
**Checks.** `src/test_keyword_facet.py` (15), `src/test_hand_groups.py` (37: the evaluator, validation, retirement, the flag, the seeded group, the endpoint rules for `hand:` ids), `src/test_sibling.py` (18, with an independent re-derivation of the rule), `src/test_features_browser.py` (32, headless Edge over the DevTools protocol, a temporary corrections file: the facet pages and filter, the hand-group page, suggestion, Add and search, the sibling line, rows, removal and switch, the six figures unchanged, 390 px). Clicks are DOM `click()` calls and the search box is typed with real key events; no touch, no other browser.

## 23. Batch actions: place from suggestions, confirm or reject soft placements, undo a batch (2026-10)

**What it is.** A "Batch view" in the "To place" queue and a "Batch review" panel on the pages of tentative, tag, sibling and annotation groups, so cards can be placed, confirmed or rejected many at a time. New: `src/manual_batch.py` (the batch logic), `POST /api/manual/batch` in `src/serve.py`, the pure page logic in `reports/manualedit.js`, `build/manual_fallback.json` (the low-confidence fallback list), and a `batch` field in `build/manual_index.json` (flag `BATCH_ACTIONS` in `src/build_manual_layer.py`; page checkbox "Show batch actions"). The only file written is `corrections/manual_placements.json`, plus a copy of it from before each batch write in `corrections/backups/` (the newest 20 are kept). No generated file is edited; nothing changes a leaf, leaf formation, a threshold, the parser, the detector, phase.rs or any of the six figures. **Nothing is placed without a click.** With `BATCH_ACTIONS` off every other output is byte-identical to the build before batch actions existed (checked by hash: the manual index, layer, ids, report and suggestions, and every other file), the fallback file is removed, the endpoint answers 404 and the page shows no batch control.

**What your own first session showed (2026-10-15, 11 cards, 33 revisions; a rough signal, not a rate).** All 33 operations were adds. Every group added was in that card's top 5 at the time of the read (rank 1 x11, 2 x7, 3 x5, 4 x5, 5 x5), none came from the search box, and there was no "nothing fits", removal, undo or note. The first add was the top suggestion for 11 of 11 cards; on average 3 suggestions per card were accepted (up to 5), and four of the 11 top suggestions accepted scored under 0.70 (0.165, 0.405, 0.50, 0.60). So a batch row lets more than one suggestion be ticked per card, and a 0.90 default is stricter than that behaviour.

**The threshold, and why 0.90.** Pile cards: 1,335, of which 1,272 have a suggestion (63 have none). Top score at or above 1.00: 316; 0.95: 352; 0.90: 511; 0.80: 680; 0.70: 851. *Read 1 (seed 20261090, set before drawing; 10 pile cards from each of the bands 0.90-1.00, 0.80-0.90 and 0.70-0.80; the card text read and my read written first, then the top suggestion shown):* at or above 0.90, 10 read: 9 sensible, 0 loose, 1 wrong (a Saga whose top suggestion was the saga boilerplate "Put lore counters on this permanent"); at or above 0.80, 20 read: 15 / 4 / 1; at or above 0.70, 30 read: 21 / 7 / 2. The boilerplate is the top suggestion of 11 pile cards, so the batch view skips it (a checkbox). *Read 2 (after the build, on a dry run of the batch on a temporary copy, which placed 526 suggestions; seeds set before the dry run: A 20261101, B 20261102, C 20261103; reads written from the text before any suggestion was revealed):* **A, 20 placements scoring 0.90-0.95 (the marginal end of the pre-ticked tier): 20 sensible, 0 loose, 0 wrong. B, 20 placements scoring 0.80-0.90 (just below): 15 sensible, 4 loose, 1 wrong. C, 20 pre-ticked pile cards drawn from all rows at 0.90 and above: 17 sensible, 3 loose, 0 wrong.** The bar (more than 3 wrong of 20 at the threshold raises it) was not tripped, so the starting threshold is **0.90, with saga boilerplate skipped; the slider goes down to 0.70**. At 0.90 the batch view pre-ticks 371 of the 1,175 queue cards (about 498 over all 1,261 pile cards with a suggestion); rows from 0.70 up to the threshold are shown **unticked** in a "review band". **These samples cannot show a rate** (20 per set; 37 sensible of the 40 at or above 0.90, 3 loose, none wrong), the reads are mine and not independent of the design of the suggestions (the same model wrote the scoring and judged it), and "sensible" means "states something the card does": the loose ones were generic groups ("A permanent gains an ability", "Cast a card") or a near group (creature versus permanent colour change). What is independent of the generator: the seeds, the counts, the hashes, the reconciliation, the byte-identical builds, the endpoint tests, the browser run and the independent re-implementations in the tests.

**Batch place (queue).** 100 cards per page, most popular first, each row showing the card, its top suggestion (name, layer, size, source, reason, score) and a checkbox; "+N more" shows the card's other suggestions, unticked. One button, "Accept ticked (N)", places the ticked suggestions of the current page; disabled above 100 ticked. Cards that already have any hand entry are never rows: they are listed apart, unticked, labelled "ticking overrides", and the server refuses a batch that includes one without `override: true`. **Batch confirm / reject.** On a tentative, tag, sibling or annotation group page: "Confirm ticked" (an add, into the group the card already holds as a soft placement: counted as "confirmed by hand", staying in its own figure) and "Reject ticked" (a `remove`, recorded and shown struck through, changing no generated count), with a preview of each card and its evidence (tentative: why it is not a real placement; tag: the tag; sibling: exactly the group's signature; annotation: the unread condition, with rows whose condition may reverse or change the ability **unticked**). Reject has no immediate single click: it is Reject ticked only, so one card is still a batch with a batch id.
**Cards with no suggestion (63).** 57 of them have no readable ability and 6 are catch-all-only; 23 carry a parser keyword (21 with a keyword block named after it), 18 have functional tags. The batch view lists them in the same view under "No suggestion: possible homes (low confidence)", never ticked: the keyword block named after a keyword the card carries (exact), a weak community-tag leaf (F1 of at least 0.02), then name-word overlap (at least 2 words and half of the group's name words); 59 have at least one. **A read of 12 of them (seed 20261091) found about a third useful** (4 sensible, 1 loose, 6 wrong, 1 none), so "Nothing fits" is one click away on every row and stays the honest default. A ticked fallback is its own batch (kind `fallback`, source `fallback:<how found>`, no score).

**Counting.** A card counts once as "placed by hand" (pile cards) or "confirmed by hand" (tentative, annotation, tag) however it was placed. The batch sub-counts sit inside those lines: a card counts as batch only when every valid add on it carries a batch id (a card also placed singly counts as single). Reconciliation is unchanged, with the hand figure taken from the pile: 27,590 + 2,093 + 960 + 1,205 + hand + (1,335 - hand) + 5,738 = 38,921. A reject and a "nothing fits" are never a placement. The six figures do not move.
**Records.** Each entry gains `batch: {id, kind: place|fallback|confirm|reject, threshold, score, source}`; the file gains `batches[id] = {date, kind, threshold, count, note, undone, replaced, seq}`; `version` stays 1. An entry without `batch` is read as a single placement; the resolver and the build ignore unknown fields. **Undo** removes only the entries that still carry the batch id and restores the entries the batch had replaced (an override, or a "nothing fits" mark ended by a placement); an entry edited singly since is left alone and reported. A batch can be undone from the bar ("Undo this batch") or by id from the batch list.
**Server.** `POST /api/manual/batch`: body at most 64 KB; 1 to 100 items; every card and group must exist and be offered; a note at most 500 characters; a threshold from 0.70 to 1.00 for place and fallback; `X-Manual-Edit` and a local Host required. A place item must be one of the card's top-5 suggestions with the suggestion file's own score; a fallback item must be in the card's fallback list; confirm and reject must hold the group as a tentative, annotation, tag or sibling placement. **All or nothing:** every row is checked first inside the lock (the file is re-read, and a corrupt file is refused and never overwritten); one bad row refuses the whole batch with the failing rows listed and the file byte-identical; the write is one temp file and one rename, after a copy of the old file is kept. The same batch id with the same items is a no-op (a retry after a lost answer). 57 endpoint checks, on temporary copies: a good batch of each kind, every refusal (unknown card or group, a bad threshold, over the cap, an oversized note and body, a foreign Host, a missing header, a wrong score, a group that is not a suggestion, a duplicate, a card with a hand entry and no override), concurrent batches (10 distinct landed; 8 copies of one applied once), a failed rename, a corrupt file, undo, the flag off.
**Page.** The page shows a failed batch (an endpoint that is missing, a network failure) as "NOT SAVED: batch of N ... nothing was placed" with Retry (the same id, safe to repeat) and Discard, kept in the browser across a reload; a refused batch lists the rows and stays ticked for fixing. Find a card says a batch-placed card was "placed in a batch, score 0.93 from sig + tag, threshold 0.90" (or confirmed / rejected in a batch).
**Limits.** The server cannot know that a suggestion is *right*, only that it is one of the card's top 5 with the stated score; a batch of sensible-looking but loose rows is still a batch of unchecked placements (undoable). One click is at most 100 placements, on the current page. Ticks are kept per page in memory (a reload keeps what was saved, not the ticks). The default-ticked tier is a score cut, so two near-duplicate leaves can both be ticked for one card (as the 11 real cards did on purpose). The review of an annotation group places the card in the leaf its unread-condition ability would belong in, which an unread condition can make wrong (the unticked rows mark the known cases). `corrections/backups/` is created by the first real batch.
**Checks.** `src/test_batch_endpoint.py` (57), `src/test_batch_logic.py` (27: the batch rows in a JavaScript engine against an independent Python implementation at 3 thresholds x skip on/off x with and without edits; batch counts JS = Python; the flag-off format), `src/test_batch_browser.py` (61, headless Edge over the DevTools protocol, a temporary corrections file: preview, untick, accept, undo, reload, the cap, an endpoint failure and a refused row, the fallback list, confirm and reject on tag, tentative, annotation and sibling groups, Find a card, the checkbox, the flag off, 390 px), `src/test_batch_find.py` (23 Find a card answers: 5 batch-placed, 5 single, 5 tag, 5 tentative, 3 excluded), `src/test_abilityfind.py` (30 hand and batch wording cases), `src/check_manual_layer.py batchflag` (the flag-off identity). Clicks are DOM `click()` calls and typing uses real key events; no touch, no other browser. Every test and the dry run used temporary copies: the real `corrections/manual_placements.json` and its backup were hashed before and after and are byte-identical.

## Reproducing these numbers

```
python src/build_index.py       # quality split, soft gaps, facets, corrections applied -> build/
python src/build_collisions.py  # collision diff vs MTGJSON         -> NAME_COLLISIONS.md
python src/serve.py             # browse at /reports/card-explorer.html
```

`build_index.py` loads `corrections/corrections.json` automatically; no separate
step is needed to apply it.
