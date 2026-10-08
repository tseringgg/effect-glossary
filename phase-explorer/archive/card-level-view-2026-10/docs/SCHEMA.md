# phase.rs `card-data.json` — real schema

Derived empirically from the 2026-04-20 snapshot (34,645 entries) and cross-checked
against upstream `CardFace` (`crates/engine/src/types/card.rs`) and
`CardExportEntry` (`crates/engine/src/database/card_db.rs`).

## Top level

A single JSON **object**, not an array:

```
{ "<lowercased face name>": <CardExportEntry>, ... }
```

The key is the lowercased *face* name, not a card id. Multi-face cards are
**flattened into one entry per face**, each stored under its own face name.
`layout` marks the face's parent layout.

Layout distribution: `null` 33,012 · transform 802 · adventure 305 · split 209 ·
modal_dfc 192 · prepare 83 · flip 42.

## Per-entry fields

Always present (34,645/34,645):

| field | type | notes |
|---|---|---|
| `name` | string | display-cased |
| `mana_cost` | object | `{type:"Cost", shards:[ManaColor], generic:int}`, or `{type:"NoCost"}` |
| `card_type` | object | `{supertypes:[], core_types:[], subtypes:[]}` |
| `power`, `toughness` | object\|null | a **quantity node**, e.g. `{type:"Fixed",value:2}` — not a string |
| `loyalty`, `defense` | string\|null | |
| `oracle_text` | string\|null | null for vanilla cards (360 of them) |
| `non_ability_text`, `flavor_name` | string\|null | |
| `keywords` | array | externally-tagged enum, see below |
| `abilities` | array | spell + activated abilities (23,136 items) |
| `triggers` | array | triggered abilities (17,137 items) |
| `static_abilities` | array | continuous/static effects (6,383 items) |
| `replacements` | array | replacement effects (2,361 items) |
| `color_override` | [ManaColor]\|null | |
| `scryfall_oracle_id` | string\|null | 33,834 distinct across 34,645 keys |
| `legalities` | object | format → status; `{}` for some entries |
| `printings` | [string] | set codes |

Conditionally present (serde `skip_serializing_if`):

`rulings` 19,357 · `brawl_commander` 3,874 · `layout` 1,633 · `parse_warnings` 544 ·
`additional_cost` 524 · `modal` 499 · `casting_restrictions` 69 ·
`casting_options` 57 · `strive_cost` 20 · `solve_condition` 15

Declared upstream but absent in this snapshot: `cleave_variant`, `color_identity`,
`is_commander`, `is_oathbreaker`, `deck_copy_limit`, `attraction_lights`,
`metadata`, `rarities`, `face_index`, `bracket_signals`.

## The four ability buckets

### `abilities[]` — AbilityDefinition
Core keys on every item: `kind`, `effect`, `cost`, `sub_ability`, `duration`,
`description`, `target_prompt`, `sorcery_speed`, `condition`,
`optional_targeting`, `optional`, `forward_result`.

Optional: `activation_restrictions` 1,089 · `multi_target` 498 ·
`activation_zone` 444 · `player_scope` 333 · `distribute` 76 · `repeat_for` 58 ·
`modal` 36 · `mode_abilities` 36 · `else_ability` 29 · `cost_reduction` 22.

`kind`: `Activated` 12,183 · `Spell` 10,933 · `BeginGame` 20.

### `triggers[]` — TriggerDefinition
Core keys: `mode`, `execute`, `valid_card`, `origin`, `destination`,
`trigger_zones`, `phase`, `optional`, `damage_kind`, `secondary`, `valid_target`,
`valid_source`, `description`, `constraint`, `condition`, `batched`.

Optional: `counter_filter` 726 · `unless_pay` 85 · `expend_threshold` 13 ·
`attack_target_filter` 10 · `player_actions` 3 · `origin_zones` 2.

`execute` is a **nested AbilityDefinition** (same shape as `abilities[]` items).

`mode` is usually a bare string but can be `{"Unknown": "<raw text>"}`.
Top modes: ChangesZone 6,915 · Phase 2,340 · Attacks 1,405 · SpellCast 1,352 ·
DamageDone 879 · CounterAdded 751 · YouAttack 213 · LeavesBattlefield 205.

### `static_abilities[]` — StaticDefinition
Keys: `mode`, `affected`, `modifications`, `condition`, `affected_zone`,
`effect_zone`, `active_zones`, `characteristic_defining`, `description`.

51 modes: Continuous 4,049 · ReduceCost 466 · CantBlock 176 · CantUntap 163 ·
CantAttack 141 · CantBeBlockedBy 133 · CantBeBlocked 126 · CantBeCountered 114.

### `replacements[]` — ReplacementDefinition
Keys: `event`, `execute`, `mode`, `valid_card`, `description`, `condition`.

12 events: Moved 1,855 · DamageDone 341 · ChangeZone 39 · Destroy 33 · Draw 26 ·
GainLife 19 · AddCounter 18 · CreateToken 12 · ProduceMana 7 · GameLoss 5 ·
BeginTurn 4 · LoseLife 2.

## Node vocabularies (internally tagged via `type`)

Counts are node occurrences across all four buckets, resolved **by slot** — the
same tag name means different things in different slots (`Fixed` is a quantity,
`Cost` is both a mana-cost and a cost node), so filtering must be slot-aware.

**`effect` — 128 variants, 61,016 nodes.** ChangeZone 5,028 · Draw 3,854 ·
PutCounter 3,473 · Token 3,413 · Mana 2,661 · DealDamage 2,469 · Pump 2,090 ·
GainLife 1,742 · Bounce 1,598 · Destroy 1,535 · Tap 1,482 · Sacrifice 1,291 ·
Shuffle 1,243 · Discard 1,170 · LoseLife 1,151 · SearchLibrary 1,044 · plus
`Unimplemented` 5,890 and `GenericEffect` 4,421 (see Caveats).

**target / filter slots** (`target`, `valid_card`, `valid_target`,
`valid_source`, `affected`) — 23 variants, 62,816 nodes. SelfRef 22,403 ·
Typed 22,157 · ParentTarget 5,624 · Controller 4,126 · Any 3,101 · Or 2,137 ·
Player 1,607 · TrackedSet 400 · AttachedTo 354 · TriggeringPlayer 352.

`Typed` is the workhorse filter:
`{type:"Typed", type_filters:[...], controller:null|"Opponent"|..., properties:[...]}`
where each property is itself a tagged node (`{type:"Another"}`,
`{type:"InZone",zone:"Stack"}`, `{type:"HasSupertype",...}`).

**quantity slots** (`amount`, `count`, `qty`, `power`, `toughness`, `value`) —
59 variants, 46,546 nodes. Fixed 35,139 · Ref 4,015 · ObjectCount 1,703 ·
Variable 1,141 · Quantity 552 · Cost 545 · EventContextSourcePower 311 ·
CountersOnSelf 281 · ZoneCardCount 257 · HandSize 240 · Devotion 33.

**cost slots** — 21 variants, 21,216 nodes. Cost 7,880 · Composite 4,480 ·
Mana 3,745 · Tap 2,913 · Loyalty 938 · Sacrifice 442 · TapCreatures 113 ·
RemoveCounter 104 · Discard 82 · Energy 55 · PayLife 47.

**condition slots** (`condition`, `constraint`, `solve_condition`) — 126
variants, 7,815 nodes. OnlyDuringYourTurn 1,832 · IfYouDo 1,110 ·
QuantityComparison 664 · AtNextPhase 406 · QuantityCheck 298 · WhenYouDo 236 ·
OncePerTurn 203 · HasCounters 181 · plus `Unrecognized` 499.

## Composition patterns

**Sequential effects** chain through `sub_ability` — a full nested
AbilityDefinition. *Swords to Plowshares* = `ChangeZone`(exile, Typed Creature)
with `sub_ability` → `GainLife` amount `{type:"Ref",qty:{type:"TargetPower"}}`,
player `"targeted_controller"`. Sentence-to-sentence dependency is preserved.

**Delayed triggers** recurse: effect `CreateDelayedTrigger` (570) carries a
`condition` (e.g. `{type:"AtNextPhase",phase:"End"}`) plus a nested `effect`
that is itself an AbilityDefinition. Trees can nest several levels deep.

**Modal spells** are flat, not nested: one `abilities[]` entry per mode, plus a
top-level `modal` object
`{min_choices, max_choices, mode_count, mode_descriptions[], allow_repeat_modes}`.
*Cryptic Command* → 4 abilities (Counter / Bounce / TapAll / Draw) +
`modal{min:2,max:2,mode_count:4}`. Mode ordering aligns with
`mode_descriptions`. (36 abilities instead use inline `modal`/`mode_abilities`.)

**Keywords carry their costs**, externally tagged — `keywords[]` items are
either a bare string or a single-key object:

```json
{"Flashback": {"type":"NonMana","data":{"type":"Composite","costs":[
  {"type":"Mana","cost":{"type":"Cost","shards":["Blue"],"generic":1}},
  {"type":"PayLife","amount":{"type":"Fixed","value":3}}]}}}
{"Madness": {"type":"Cost","shards":[],"generic":0}}
```

172 distinct keywords. Flying 3,230 · Enchant 1,265 · Trample 1,011 ·
Vigilance 715 · Haste 676 · Flash 596 · Equip 594 · Kicker 219 · Flashback 207 ·
Madness 61.

## Caveats

1. **Parse coverage is ~71%, not 100%.** Of 34,285 entries with oracle text:
   24,316 (70.9%) are cleanly structured; 8,256 (24.1%) contain at least one
   `Unimplemented` or `GenericEffect` node; 1,344 (3.9%) have oracle text but
   **zero** structured abilities. `Unimplemented` nodes carry `{name, description}`
   holding the raw text fragment the parser punted on — top `name` values are
   `unknown` 844, `static_structure` 407, `choose` 254, `the` 220.
   So this is a partial, actively-in-progress parse, and any filter UI needs to
   surface parse quality as a first-class axis or the gaps will read as absences.

2. **Face-name keying loses cards to collisions.** Keys are lowercased face
   names, so a newer face with a reused name overwrites the older card. The only
   entry under `lightning bolt` is the Strixhaven "prepare"-layout face
   (`printings:["SOS"]`, `legalities:{}`, oracle_id `5963eef1…`) — the classic
   Lightning Bolt is **not in the file**. Do not assume name → card is complete
   or that a familiar name gives the familiar card.

3. **Individual parses can silently drop clauses.** *Deep Analysis* ("Target
   player draws two cards") yields `Draw{count:2}` with no target/player field —
   the "target player" is lost, not flagged in `parse_warnings`. Field-level
   fidelity needs spot-checking per effect type before relying on it.

4. **Snapshot is 5 months old** (2026-04-20) and 34,645 entries. Regenerate via
   `phase-gen -i AtomicCards.json.gz -o card-data.json` if currency matters.

5. Text is clean UTF-8 (em dashes, bullets); `oracle_text` uses `\n` between
   ability lines and `•` for modal bullets.
