# Signature taxonomy: would per-ability exact signatures with backoff organize cards better?

Investigation only. Nothing was built, placed or changed. All 215 files that existed under `phase-explorer/` before
the probe (a superset of the 107 frozen files) were hashed before and after and are byte-identical. New files only:
`src/probe_signature_taxonomy.py`, `src/analyze_signature_probe.py`, `build/signature_probe.json`,
`build/signature_probe_leaves.json` (every ability's fields, signatures and leaf under every variant),
`build/signature_probe_analysis.json`, `build/signature_probe_handcheck.json` (the drawn sample),
`build/signature_probe_handcheck_verdicts.json` (my verdicts) and this report. Both scripts give identical bytes on
a rerun. No Scryfall tag data was read.

```
python src/probe_signature_taxonomy.py   # fields, signatures, backoff  -> build/signature_probe*.json
python src/analyze_signature_probe.py    # named cases, comparison, hand-check sample
```

## Answer first

**Don't build this taxonomy as specified.** The hand check fails the bar set in advance: **7 of 30 sampled leaves
are incoherent (23%, above 15%)**. All 7 incoherent leaves are level-1 leaves: the "everything else with this effect
type" remainder that backoff ends in (for example "PutCounter: other counter types", 242 abilities: net, film, age,
study and supply counters). The 20 sampled leaves at levels 2 to 5 had no incoherent ones (13 coherent, 7 loose).
Twenty leaves is too few for an error rate.

Against the three parts of the hypothesis (primary variant C5: order C, minimum 5, literal backoff; definitions below):

- **(a) Places most of what sits in noise or "Not yet organized": yes, mechanically.** 9,071 of the 9,546
  abilities unplaced today reach a leaf of 5 or more, and 7,122 of those are specific leaves (level 3 or finer,
  not generic). If each card's best new leaf counted as a placement, "Not yet organized" would fall from 8,779
  cards to 3,633 (any leaf) or 4,449 (specific leaves only). That is an upper bound: none of the new placements
  was hand-checked as a placement.
- **(b) Fixes the wrong-target placements: mostly not.** 2 of the 11 now reach a land-specific leaf (Cleansing;
  Strategy, Schmategy's land mode). Bearer of the Heavens moves to an accurate "destroy all permanents" leaf.
  7 are not fixed: the land fact is missing from the parse (Upheaval, Worldpurge, Global Ruin, Balancing Act,
  Wave of Vitriol) or sits in a later chain step that backoff drops (Death Cloud, Pox Plague). Impending Disaster
  is excluded by its condition-drop flag. The token scheme's other confusions are fixed: −1/−1 counters, "each
  opponent discards", and target-player mill against self-mill each get their own leaf. The graveyard-to-hand
  return (Dogged Detective) is not.
- **(c) Stays coherent without HDBSCAN: not at the coarsest level** (see above), and the result is lopsided.
  55% of abilities sit in 147 leaves of 50 or more (one "draw cards" leaf holds 1,887), while 1,226 leaves hold
  fewer than 10.

---

## 1. Signature fields the parser exposes

Population for every count in this section: the 41,842 abilities defined in §3. "Relevant" means the effect types
where the field carries meaning.

| field | read from | coverage | token blind spot it closes |
|---|---|---|---|
| effect type | `effect.type` (abilities; `execute.effect` for triggers and replacements); static `mode`; replacement `event` | 41,822 of 41,842 | already in tokens |
| **zone to** | `effect.destination`; implied by the type (Bounce = hand, PutAtLibraryPosition = library); for search / dig effects, the first chain step's destination | **5,418 of 5,932** zone-moving abilities (ChangeZone 2,115/2,115, Bounce 1,265/1,265, Mill 461/461, SearchLibrary 708/853, Dig 358/437) | **zone destination: closed** |
| zone from | `effect.origin`, else the target's `InZone` property | 1,611 of 5,932 (ChangeZone 1,087/2,115, Bounce 385/1,265) | **partly**: graveyard/hand/library origins are recorded on typed targets; a self-reference never carries one (below) |
| **counter type** | `counter_type` / `counter_kind`, lower-cased (the parser emits both `oil` and `OIL`, `charge` and `CHARGE`) | **3,089 of 3,137** counter effects | **counter type: closed** |
| **player scope** | `player_scope` (Opponent / All / TriggeringPlayer), a player-kind target (Player, Controller, TriggeringPlayer, DefendingPlayer), or `effect.player` | Discard 491/546, Mill 443/461, LoseLife 488/631, Sacrifice 115/802, **Draw 68/2,638** | **closed for discard, mill, life loss; open for draw** |
| target type | `Typed.type_filters` core types (a subtype-only filter such as `Subtype:Island` is mapped to the core type the corpus gives that subtype, >= 80% share); `Or` = union; a `ParentTarget` with `repeat_for` reads the repeat filter; tokens: their card types; mana: what it produces; statics: `affected` (+ cost-change spell filter) | 33,718 abilities have an object | already in tokens (now finer) |
| controller | `Typed.controller` | 6,358 (You 5,222, Opponent 1,089, TargetPlayer 43) | already in tokens |
| all vs one | an `*All` effect type (1,878), `repeat_for` (113), `multi_target` max > 1 (475), else one / none | as listed | partly: **not recorded for Bounce** or for "destroy X" vs "destroy target X" |
| duration | effect or ability `duration` | 5,333 | new |
| condition presence | ability `condition` (trigger conditions say *when*, not *what*, and are not used) | 1,553 | new |
| **chain** | `sub_ability` steps after the head (step type, destination, counter type, target type; up to 3) | **7,603** abilities have later steps (raw depth: 1 step 6,188, 2 steps 1,607, 3+ 422) | **"anything after the first effect": the field exists**, but it only discriminates where a level that uses it is reached (§7: 4,641 of the 7,595 chained abilities end in a leaf that ignores it) |

Two structural reads were needed to make the fields mean anything. Wrapper effects (`TargetOnly`, `Choose`,
`PayCost`, `CreateDelayedTrigger`; 911 abilities) are unwrapped to the first real step, and a wrapper's target is
carried forward when the step only points back at it. The 246 modal placeholders (a `GenericEffect` with the real
content in `mode_abilities`) get a "Modal" head listing their mode verbs.

**Blind spots with no usable field:**

1. **Who draws.** "Target player draws" is dropped (SCHEMA.md caveat 3). 190 draw abilities name another player
   in their text and 68 carry a player field, so about 120 are indistinguishable from "you draw".
2. **"Return all" vs "return target".** Upheaval and Worldpurge parse exactly like Boomerang
   (`Bounce`, `Typed[Permanent]`). 58 bounce texts say "return all/each"; none is marked.
3. **The origin zone of a self-reference.** 201 abilities return "this" to hand; 92 of them say "from your
   graveyard"; none records an origin. Trigger zones don't help (Dogged Detective's trigger says Battlefield).
4. **Dropped clauses.** Death Cloud has no discard or creature sacrifice; Global Ruin's land filter is `Any`;
   Limited Resources has no "sacrifice the rest"; Spark Double would read as "+1/+1 counter on self" (it is
   corrections-flagged and outside the population).
5. **Misread statics.** Silumgar Assassin ("creatures with power greater than ~'s can't block it") and Spitting
   Dilophosaurus's static ("creatures your opponents control with −1/−1 counters can't block") parse as
   "~ can't block".

## 2. Levels

Each level must strictly refine the one above, so backoff is a path up a tree. I compared three orders. They share
the same finest level (9,585 distinct signatures) and differ only in what an ability falls back to.

| level | A (your example order) | B | **C (primary)** |
|---|---|---|---|
| L1 | effect family | effect family | **effect type** (`DestroyAll` folded into Destroy) |
| L2 | effect type (raw) | effect type + zone from/to, counter type, player scope, grant kinds | **L1 + zone from/to, counter type, player scope, granted-modification kinds** |
| L3 | + target type | + target type | **+ target type** |
| L4 | + controller, all/one, zone from/to | + controller, all/one | **+ controller, all/one** |
| L5 | + counter type, player scope, chain, detail | + detail | **+ detail**: subtypes and properties of the target, keyword and token names, duration, condition, wrapper, chain steps |
| distinct signatures | 30 / 179 / 916 / 1,592 / 9,585 | 30 / 706 / 1,710 / 2,293 / 9,585 | 171 / 706 / 1,710 / 2,293 / 9,585 |

**Why this order.** Zone, counter type and player scope change *what an ability does* (exile vs return to hand,
+1/+1 vs −1/−1, you discard vs an opponent discards), so they bind to the verb. The object changes *what it is done
to*. When an ability's finest cell is too small, backoff should drop the less meaning-bearing fields first. This
is measured, not only argued: the table counts abilities that have a field whose assigned leaf ignores it.

| backoff drops | A5 | B5 | **C5** |
|---|---:|---:|---:|
| counter type (3,090 have one) | 835 | 304 | **303** |
| player scope (3,045) | 767 | 141 | **131** |
| zone to (5,480) | 616 | 84 | **84** |
| zone from (2,040) | 326 | 60 | **60** |
| chain steps (7,603) | 4,649 | 4,649 | **4,641** |

So order A reintroduces the very blind spots this probe is about whenever a cell is small. C over B: a family floor
mixes unrelated types ("Counters" holds poison, rad, keyword and loyalty counters together: 347 abilities in B5).
In C the family is a browse branch above the tree, not a leaf. The price is that an effect type with fewer than 5
abilities gets no leaf at all: 48 abilities in C5, against 0 in B5.

**Backoff rule.** Literal, as asked: an ability sits at the finest level whose signature is held by at least
MIN abilities *in total*. A node can then hold fewer than MIN abilities directly when its other holders went finer;
in a tree that is the node's "other" remainder. The alternative, residual (finest first, a signature needs MIN
abilities *not yet assigned*, every leaf >= MIN), is reported as "C5r". Literal keeps related abilities together:
Wildfire stays in the "each player sacrifices lands" node with Tectonic Break, where residual sends it to a generic
"each player sacrifices" leaf.

**Judgment calls:** the family map, unwrapping wrappers, the subtype-to-type mapping, the level order, and what counts
as generic (§4).

## 3. Population

**41,842 abilities on 28,839 cards** (rows of `build/ability_ledger.json`):

- **38,689 on clean cards.** By card status: clustered 28,653, noise 6,503, placed_by_ability 1,779,
  unclustered 1,511, no_extractable_effect 213, and recovered cards whose face is clean.
- **3,153 clean abilities on gap cards** (partial 2,435, unmodelled 693, and recovered partial faces).

Excluded:

- 5,976 abilities whose own item holds a gap node (5,808 on gap cards, 168 on clean cards)
- 2,846 abilities flagged by the condition-drop detector
- 8 rows on corrections-flagged cards

**Usable signatures: 41,822. Not usable: 20** (triggers whose `execute` has no effect node, mostly "suspect").
Keyword-only cards have no ability items, so they add nothing. Cards that have keywords and abilities are included
through their abilities; I read "keyword-free cards" as not a further exclusion.

The gap-card abilities pass only the item-gap and condition-drop exclusions you named. §10's same-line and
continuation tests were **not** applied, so for gap cards this population is looser than the current partial layer.

## 5. Named cases

All results are C5 unless stated. "Land-specific" means the leaf's own signature names Land or a basic land type.

### Mass land denial (68 core cards, roles D / DP / DB)

| outcome | C5 | A5 | C3 | C5r |
|---|---:|---:|---:|---:|
| land ability lands in a land-specific leaf | **34** | 32 | 36 | 28 |
| land in the full signature, but the leaf backs off past it | 5 | 7 | 3 | 11 |
| no land in any signature (parse) | 17 | 17 | 17 | 17 |
| not in the population (gap item or flagged) | 12 | 12 | 12 | 12 |

- **The six destroy-all-lands cards share one leaf under every variant:** `Destroy · obj=Land · quant=all`
  (L5, 8 abilities). They are Armageddon, Bust, Catastrophe, Fall of the Thran (chapter I), Myojin of Infinite
  Rage and Ravages of War, plus Decree of Annihilation's cycling trigger and Strategy, Schmategy's "destroy all
  lands" mode. Nothing else is in it.
- **Other land-specific leaves the core cards reach:**
  - "Destroy all \<basic type\> / nonbasic lands": Acid Rain, Boil, Boiling Seas, Flashfires, Tsunami, Stench of
    Evil, From the Ashes, Ruination; L4, 8.
  - "Each player sacrifices lands": Tectonic Break and Thoughts of Ruin at L5; Wildfire, Destructive Force and
    Devastating Dreams in the same L4 node.
  - "Return lands to hand": Sunder, Omen of Fire; L4, 6.
  - "Exile lands": Realm Razer.
  - "Destroy target land": Break the Ice, Rumbling Crescendo; L5, 46.
- **Back off past the land fact:** Death Cloud (lands only in chain step 2), Jokulhaups and Obliterate
  ("artifacts, creatures and lands": a rare union, so they fall to the generic Destroy leaf), Wave of Vitriol,
  Limited Resources.
- **No land in the parse at all:** Balancing Act, Cataclysm, Cataclysmic Gearhulk, Global Ruin, Pox Plague
  ("half their permanents"), Upheaval, Worldpurge, Apocalypse, Worldfire, Soulscour and others. These are the
  "via all permanents" and balance cards, plus parse drops.

### The 11 wrong-target placements

| card | old leaf | new leaf (C5) | land-specific? | left the old leaf's effect? |
|---|---|---|---|---|
| Cleansing | 427 (Destroy ParentTarget) | `Destroy · Land` (L3; repeat filter read) | **yes** | yes (0 old-leaf mates) |
| Strategy, Schmategy | 505 (ability-placed) | mode 3 in the destroy-all-lands leaf; other modes in their own leaves | **yes** | yes |
| Bearer of the Heavens | 615 (delayed trigger) | `Destroy · Permanent · all` (L4, 11) | no, but accurate (DP card) | yes |
| Death Cloud | 240 (each opponent loses) | `LoseLife · who=all players` (L4, 9) | no: land is chain step 2 | partly: 6 old-leaf mates remain |
| Pox Plague | 240 | same leaf as Death Cloud | no: parse says "permanents" | partly |
| Global Ruin | 369 (TargetOnly) | `Sacrifice` (L2, 16), generic | no: parser target is `Any` | yes, into a generic leaf |
| Balancing Act | 157 (Choose) | `Sacrifice` (L2, 16), generic | no | yes, into a generic leaf |
| Wave of Vitriol | 277 (Sacrifice Or) | `Sacrifice · who=all players` (L2, 10) | no: the union is too rare | partly |
| Upheaval | 391 (return target permanent) | `Bounce · Permanent · one` (L5, 33), with Boomerang | no: "all" not parsed | **no** (26 old-leaf mates) |
| Worldpurge | 391 | same as Upheaval | no | **no** |
| Impending Disaster | 475 | not in population (condition-drop flag) | n/a | n/a |

**2 fixed, 1 improved, 7 not fixed, 1 excluded.** Order A does no better: Death Cloud lands in a 32-ability
`LoseLife` leaf mixing every life-loss scope.

### Token-scheme confusions

| case | signature | leaf (C5) | separated? |
|---|---|---|---|
| Memory Sluice (target player mills) | `Mill · to=Graveyard · who=player · obj=player · one` | L5, 96 | **yes**, from self-mill |
| Seedship Broodtender (mill three) | `Mill · to=Graveyard · who=you` | L5, 103 | **yes** |
| Deadly Visit, Raucous Theater, Dogged Detective (surveil) | `Surveil` | L5, 154 | **yes**: surveil never shares a leaf with mill |
| Spitting Dilophosaurus, trigger | `PutCounter · ctr=m1m1 · Creature · one` | L5, 33 (Necropede, Festering Mummy, Grasping Dunes ...) | **yes**, away from +1/+1 |
| Spitting Dilophosaurus, static | `static:CantBlock · obj=self` | L5, 164 ("~ can't block") | **no**: the parse misreads the static (§1, item 5) |
| Bandit's Talent, discard trigger | `Discard · who=scope:Opponent · obj=you · one` | L5, 34 (Unnerve, Burglar Rat, Nicol Bolas ...) | **yes**, away from self-discard |
| Dogged Detective, return from graveyard | `Bounce · to=Hand · obj=self · one` | L5, 184 | **no**: 92 graveyard returns mixed with "return this to its owner's hand" from the battlefield; no origin field |

### Shuri, Mulldrifter, Spark Double, Sakura-Tribe Elder

| card / ability | signature (finest) | leaf (C5) |
|---|---|---|
| Shuri: "Artifact spells you cast cost {1} less" | `static:ReduceCost · obj=Card/spell:Artifact · ctrl=You` | L5, 5: exactly the five "artifact spells cost {1} less" cards (Foundry Inspector, Etherium Sculptor ...) |
| Shuri: "Target artifact you control becomes a copy of ..." | `BecomeCopy · obj=any target` (the parser drops "artifact you control") | L2 `BecomeCopy`, 27 (Clone-likes, Thespian's Stage ...): generic |
| Mulldrifter: "draw two cards" | `Draw` | L5, **1,887**: every plain draw |
| Sakura-Tribe Elder: sac, search basic land to battlefield tapped | `SearchLibrary · to=Battlefield · obj=Land · one · det=HasSupertype:Basic, chain ChangeZone>Battlefield, Shuffle` | L5, 100 (Evolving Wilds, Natural Connection, Frontier Guide ...) |
| Spark Double | corrections-flagged, outside the population. Its only item would read `PutCounter · ctr=p1p1 · obj=self`: the copy is lost entirely | n/a |

## 6. Coherence hand check

**Rule, fixed before reading.** *Coherent*: all 8 abilities do one thing a tester would accept under one name.
*Loose*: at least 6 of 8 do; the rest are related or misfits. *Incoherent*: fewer than 6 of 8 share one thing.
Bar: more than 15% incoherent means don't recommend building.

**Sample.** C5, seed 20261006. Every leaf drawn holds at least 8 abilities directly, so exactly 8 could be read.

- 10 finest-level (L5) leaves, stratified by size thirds
- 10 coarsest: all 10 L1 leaves that hold 8 or more
- 10 middle (L2 to L4), stratified by size

An earlier draw from all leaves was replaced because 13 of its 30 leaves held only 1 to 7 abilities (literal-backoff
remainders that are trivially "coherent"). By the same rule, that draw had 3 incoherent of 30. The verdicts and
the abilities read are in `build/signature_probe_handcheck_verdicts.json` and `build/signature_probe_handcheck.json`.
The verdicts are my judgment.

| band | coherent | loose | incoherent |
|---|---:|---:|---:|
| finest (L5) | 7 | 3 | 0 |
| middle (L2 to L4) | 6 | 4 | 0 |
| coarsest (L1) | 0 | 3 | **7** |
| **all 30** | **13** | **10** | **7 (23%)** |

**The 7 incoherent leaves (all L1 remainders):**

| leaf | size | what is in it |
|---|---:|---|
| PutCounter (other) | 242 | wreck, vigilance, +0/+1, age, soul, knowledge, study, supply counters |
| static Continuous (other) | 59 | mass type change (Wrath of Oko), Sliver grants, base P/T setters, "every basic land type" |
| ChangeZone (other) | 41 | hand exile (Intellect Devourer), Show and Tell, wheels, library exile, put exiled card into hand |
| RemoveCounter (other) | 38 | loyalty removal (Lonely End), time counters, ice (Dark Depths), slumber, bait, delay |
| GivePlayerCounter (other) | 22 | rad counters (5) mixed with poison counters (3) |
| GainLife (other) | 9 | opponents or each player gain life (5), Gollum *loses* life (a misread), Essence Sliver, Curse of the Forsaken |
| PutAtLibraryPosition (other) | 8 | hand cycling (4), hand disruption (2), graveyard to bottom, top to bottom |

**Loose (10):**

- exile-all-creatures wipes, plus Wall of Nets
- mass "can't block this turn", plus a self-evasion
- level-up P/T bands, plus Snowmelt Stag
- set life total, plus Baffling Defenses (a misread)
- symmetric "each player may search", plus Doomsday
- L1 GenericEffect animations, plus two pumps
- polymorph-down mixed with land animation
- target player discards, plus two wheels
- total wipes mixed with narrow conditional sweeps of permanents
- "you may sacrifice an artifact: payoff", plus a drawback and a modal

**Verdict: 23% incoherent, above the 15% bar. Not recommended for building.** The failure is concentrated at L1:
an effect-type remainder collects whatever could not reach a finer cell, and those abilities have little in common.

## 7. Compared with the old taxonomy (657 leaves)

**Same old leaf, same new leaf?** For pairs of clustered cards in the same old leaf, the share that have an ability
in a common new leaf:

- **34% weighted by pairs** (large old leaves dominate)
- per old leaf: **median 62%** (quartiles 37% to 92%)
- 210 of 657 old leaves keep at least 80% of their pairs together; 60 keep fewer than 20%

**How old leaves split** (C5), counting the new leaves needed to cover 80% of an old leaf's members:

| new leaves needed | old leaves |
|---|---:|
| 1 | 310 |
| 2 | 172 |
| 3 | 70 |
| 4 | 34 |
| 5 | 24 |
| 6 or more | 47 |

Old leaves are per card and new leaves per ability, so a two-ability card counts as "together" if either of its
abilities matches.

**Abilities unplaced today** (state `unplaced` in the ability ledger, inside the population): 9,546 abilities on
6,247 cards. By card status: noise 5,466, partial 2,099, the other abilities of ability-placed cards 1,059,
unmodelled 573, unclustered 292, rest 57.

| C5 | abilities |
|---|---:|
| reach a leaf of 5 or more | **9,071** |
| ... at L5 / L4 / L3 / L2 / L1 | 5,213 / 2,791 / 278 / 582 / 207 |
| ... in a specific leaf (L3 or finer, not generic) | **7,122** |
| ... in a generic leaf (e.g. the 1,887-ability draw leaf) | 1,643 |
| ... at L1 or L2 only | 306 |
| in a leaf of fewer than 5 | 420 |
| no leaf (effect type under 5) | 55 |

902 of the 6,247 cards reach only coarse or generic leaves.

**"Not yet organized", projected** (a card counts if any of its abilities is in a leaf of 5 or more):

| group | cards | any leaf | specific leaf (L3+, not generic) |
|---|---:|---:|---:|
| Parsed, but with a gap | 5,252 | 1,934 | 1,515 |
| Parsed, no close group found | 3,459 | 3,187 | 2,807 |
| No effect to group | 31 | 25 | 8 |
| Not parsed yet | 29 | 0 | 0 |
| Known parse mistake | 8 | 0 | 0 |
| **unorganized after** | **8,779** | **3,633** | **4,449** |

This is an upper bound. On gap cards it places by a clean ability without §10's same-line and continuation tests,
so it carries the "headline lost" risk §10 found on 194 of 456 placements. None of these projected placements was
hand-checked.

**Where the new taxonomy is worse.**

- **Coherent old leaves that fragment.** I used a proxy for "coherent": every member shares one exact
  effect+target token. 552 of the 657 old leaves pass it. **7** of those fragment, meaning fewer than half their
  members share a new leaf with another member:
  - **4 are `TargetOnly` wrapper leaves** (369, 261, 358, 52). Unwrapping splits them by the real effect,
    arguably an improvement.
  - **3 are real losses.** The Equipment-grant leaf 518 ("equipped creature gets +N/+N and has X", 8 cards,
    0 kept together) and the Aura-grant leaf 533 (9) splinter by granted keyword name. Because "equipped by" and
    "enchanted by" sit in the L5 detail, the backoff leaves (`Continuous · AddKeyword · Creature`) mix Equipment,
    Auras and anthems. Leaf 231 (+1/+1 counter on an attacking creature) splits too.
- **Abilities that lose a good match.** 174 abilities that best-matched their own old leaf now end in an L1
  remainder.
- **One giant leaf.** The new scheme makes a single 1,887-ability draw leaf where the old one had 971 cards (leaf
  34). Quantities are out of scope, and the parser drops "target player".

## 4 and 8. Backoff results and leaf explosion

| | **C5** | C3 | A5 | C5r (residual) |
|---|---:|---:|---:|---:|
| leaves | **2,033** | 2,954 | 1,834 | 1,669 |
| leaves by level L1 / L2 / L3 / L4 / L5 | 43 / 164 / 218 / 582 / 1,026 | 40 / 169 / 243 / 762 / 1,740 | 11 / 78 / 213 / 506 / 1,026 | 18 / 121 / 92 / 412 / 1,026 |
| abilities ending at L1 / L2 / L3 / L4 / L5 | 569 / 1,191 / 753 / 8,747 / 30,514 | 360 / 685 / 497 / 7,363 / 32,898 | 49 / 840 / 817 / 9,602 / 30,514 | 657 / 1,452 / 623 / 8,377 / 30,514 |
| below the minimum at every level | 48 | 19 | 0 | 199 |
| generic leaves (L1, or no object and no verb parameter) / their abilities | 200 / 5,652 | 194 / 5,117 | 162 / 5,041 | 137 / 5,845 |
| median leaf size | 7 | 4 | 8 | 9 |
| remainder leaves holding fewer than MIN directly / their abilities | 414 / 872 | 465 / 639 | 294 / 634 | 0 |
| leaves of 1-2 / 3-4 / 5-9 / 10-19 / 20-49 / 50-99 / 100-499 / 500+ | 270 / 144 / 812 / 414 / 246 / 92 / 44 / 11 | 465 / 1,086 / 672 / 372 / 223 / 84 / 42 / 10 | 190 / 104 / 745 / 406 / 248 / 83 / 46 / 12 | 0 / 0 / 842 / 426 / 252 / 94 / 44 / 11 |
| abilities in leaves of 5-9 vs 50+ | 5,231 vs **22,862** | 4,335 vs 21,470 | 4,804 vs 23,636 | 5,417 vs 23,071 |

**Largest C5 leaves:**

| leaf | level | abilities |
|---|---|---:|
| Draw | L5 | 1,887 |
| +1/+1 counter on self | L5 | 898 |
| mana of any one color | L5 | 852 |
| fixed-color mana | L5 | 804 |
| tap self, incl. "enters tapped" | L5 | 751 |
| self pump until end of turn | L5 | 735 |
| Attach to a creature you control | L5 | 713 |
| gain life | L5 | 699 |
| create creature tokens | L4 | 658 |
| colorless mana | L5 | 546 |
| damage to any target | L5 | 512 |

**Browsable?** Not by browsing alone. At C5 there are 2,033 leaves, 3.1 times today's 657, under 171 effect types
grouped into 30 families. More than half of all abilities (55%) sit in 147 leaves of 50 or more, while 1,226
leaves hold fewer than 10, and 414 of those are "other" remainders of 1 to 4. A tester could navigate it with
search and filters on the signature fields. As a tree to click through, it is wide at the bottom and lumpy at the
top. Minimum 3 makes this worse (2,954 leaves, median 4) without fixing the named cases (36 land-specific against
34) and fragments more coherent old leaves (10 against 7).

## 9. Recommendation

**Don't build it.** The pre-set coherence bar is failed (7 of 30 incoherent), and the failure is structural:
level-1 remainders. The probe does show three things worth keeping:

- The parser's fields close three of the four token blind spots (zone destination, counter type, player scope
  except for draw), when the level order keeps them near the verb (order C).
- Exact signatures make some tight, nameable leaves the clustering never found: destroy-all-lands, "artifact spells
  cost {1} less", "each opponent discards", −1/−1 counters.
- At levels 2 to 5, the 20 sampled leaves had no incoherent ones. That is 20 leaves, not an error rate.

**If it is pursued, the next step is another probe, not a build:**

1. **No L1 leaves.** An ability that can't reach L2 stays unplaced (569 abilities in C5).
2. **Move the attachment relation** (equipped by, enchanted by) into the object at L3, and keep keyword names in
   L5. This targets the Equipment and Aura fragmentation.
3. **Field-wise backoff.** Drop the rarest field first instead of a fixed order, so a chain step that carries the
   meaning (Death Cloud's lands) or a rare union (Jokulhaups) is not thrown away with everything else.
4. **Re-run a fresh 30-leaf hand check under the same 15% bar.**

Use **minimum 5, order C, literal backoff**. Scope it to **clean cards first**. Bring in clean abilities on gap
cards only with §10's same-line and continuation tests applied, which this probe did not do.

**Parser work that would still be needed** (no field exists today):

- who draws ("target player draws")
- "all" on Bounce
- origin zone for self-referencing returns, and correct trigger zones for graveyard triggers
- dropped clauses (Death Cloud, Global Ruin, Limited Resources, Spark Double's copy)
- static `affected` misreads (Silumgar Assassin, Spitting Dilophosaurus)
- upstream case normalization of `counter_type`

**Where conclusions rest on judgment:**

- the family map
- wrapper unwrapping
- the subtype-to-type mapping
- the level order (backed by the blind-spot measurement in §2)
- the definitions of "generic" and "land-specific" (the leaf signature names Land)
- the coherent-old-leaf proxy
- all 30 hand-check verdicts

**Migration from the 657 leaves would involve:**

- **The open ability-level placement decision** (KNOWN_LIMITATIONS §8). New leaves are per ability, so a card
  could sit in several leaves; counts, centroids and every cohesion figure would change.
- **Rebuilding everything keyed to old leaf ids:** branch rules and sub-branches, leaf phrases and curated names,
  the three leaf maps, the also-fits, ability and partial-ability layers (all scored against the old centroids),
  the ledgers, the type audit and the browse data. That means the frozen files.
- **A crosswalk.** 310 old leaves map at least 80% to one new leaf; the other 347 split and would need a mapping.
- **New, coined names for about 2,000 signature leaves.** Branch rules defined by dominant effect type could be
  re-expressed on the L1 and L2 signature fields.
