# Known limitations of the phase.rs card-data snapshot

Permanent record so these are not rediscovered later. All numbers are measured
against the **2026-04-20** snapshot (`data/card-data.json`, 83,388,014 bytes,
34,645 face entries) and are reproduced by `src/build_index.py` and
`src/build_collisions.py` on every build. §3's spot-check findings are tracked
as an ongoing log in [`corrections/corrections.json`](corrections/corrections.json).

This file documents limitations of the **upstream data**, not of this tool.
Improving phase.rs's coverage is deliberately out of scope here.

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

## Reproducing these numbers

```
python src/build_index.py       # quality split, soft gaps, facets, corrections applied -> build/
python src/build_collisions.py  # collision diff vs MTGJSON         -> NAME_COLLISIONS.md
python src/serve.py             # browse at /reports/card-explorer.html
```

`build_index.py` loads `corrections/corrections.json` automatically; no separate
step is needed to apply it.
