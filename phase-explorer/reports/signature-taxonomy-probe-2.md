# Signature taxonomy, probe 2: no fallback bucket, rarest-field-first backoff

Investigation only. Nothing was built, placed or changed. All 223 files that existed under `phase-explorer/` before this probe
(probe 1's outputs included, and a superset of the 107 frozen files) were hashed before and after and are byte-identical. New
files only: `src/probe2_signature_taxonomy.py`, `src/analyze2_signature_probe.py`, `src/sample2_signature_probe.py`,
`build/signature_probe2.json`, `build/signature_probe2_leaves.json` (every ability's fields and leaf under every variant),
`build/signature_probe2_analysis.json`, `build/signature_probe2_handcheck.json` (the two seeded draws),
`build/signature_probe2_handcheck_verdicts.json` (my verdicts) and this report. The three scripts reproduce all outputs
byte-for-byte on a rerun. No Scryfall tag data was read.

```
python src/probe2_signature_taxonomy.py    # fields, backoff, leaves, flags        -> build/signature_probe2*.json
python src/analyze2_signature_probe.py     # named cases, comparison, browsability
python src/sample2_signature_probe.py      # the seeded hand-check draws (run once, rule fixed in advance)
```

## Answer first

**Both pre-set bars are passed, so by the bars building is not ruled out. It is a conditional yes, for a narrow first build.**

- **Coherence: 0 of 30 sampled leaves incoherent** (26 coherent, 4 loose). Probe 1 had 7 of 30. Bar: more than 15% incoherent
  means don't build. Not triggered.
- **Placement: 0 of 40 newly placed abilities wrong.** Bar: more than 5% wrong means don't build. Not triggered.
- **Neither sample measures an error rate.** 0 of 30 is consistent with a true incoherence rate of up to about 10%, and 0 of 40
  with a wrong-placement rate of up to about 7.5%. So the 5% stop rule is not shown to be satisfied, only not violated.
- **The sample is easier than it looks.** 8 of the 10 coarsest-band leaves are bare effect types with no parameters
  (investigate, time travel, roll a die), which are coherent by construction.
- **The headline gain is smaller than probe 1 suggested.** If every ability's best leaf counted as a placement,
  "Not yet organized" would fall from 8,779 to **5,183 cards (specific leaves only)**, 4,909 including bare effect-type
  leaves, and 4,547 if the flagged-generic leaves also counted. Probe 1's figure was 4,449, with generic leaves counted and no gap-card tests.
- **The wrong-target and named cases are not better than probe 1.** The reason is the parser, not the taxonomy (§4).
- **Two things I did that deviate from a literal reading of the brief** are listed under "Judgment calls" in §1.

---

## 1. Sampling seed and the changed rules

**Seed: 20261007**, fixed before any result was computed. No draw was repeated: I ran the sampler once, then re-ran it only
to also record the skipped-leaf lists, and verified both draws were identical afterwards. Both samples are drawn from
variant **RF5** (rarest-field-first, minimum 5), which I fixed as the primary variant in advance.

| change | what was done |
|---|---|
| **No level-1 leaves** | An ability is placed only if a signature of at least MIN abilities exists at level 2 or finer. Otherwise it stays unplaced, with a reason: `rare_object` (effect type + object too rare), `rare_verb_parameter` (effect type + zone/counter/scope too rare), `rare_effect_type`, `no_signature`. |
| **Bare-fallback guard** (my addition) | An ability that has an object but no verb parameter may not fall to the bare effect type; its floor is effect type + object. Without this, "Destroy · one target" would be probe 1's "everything else" bucket in disguise. An ability whose *complete* signature is bare (Surveil, plain Draw) keeps it, because that is its finest signature. |
| **Equipped / enchanted** | Folded into the target: `obj = Creature[equipped]` or `Creature[enchanted]`, removed from the detail bag. |
| **Rarest field first (RF)** | Droppable: object, controller, all/one, subtype/property bag, keyword, duration, condition, wrapper, chain, token name. Never dropped: zone from/to, counter type, player scope, granted-modification kinds. The rarest value (among abilities of the same effect type) goes first; ties drop detail first. The deciding count is the number of abilities in the population that agree on every retained field (the literal reading, as in probe 1). |
| **Fixed order (FO)** | Probe 1's order C (L2 verb fields, L3 + object, L4 + controller / all-one, L5 + all detail), computed under the same new rules, for comparison. |
| **Gap cards** | Clean abilities on partial / unmodelled cards must also pass the partial layer's same-line and continuation tests (and its no-text rule). |
| **Generic leaves** | A leaf is flagged when a field it needs is missing from the parse (below). Flagged leaves are kept out of the headline placement counts. |

**Judgment calls.**

1. **The bare-fallback guard.** It follows the brief's intent (no "everything else" bucket) but is not in its literal wording. In
   the hand-check sample no leaf was a disguised bucket, so it did not matter there.
2. **The flag rules.** I flagged a leaf when:
   - it is a Draw leaf with no player recorded;
   - it is any return-to-hand leaf ("return all" is not recorded);
   - it is a self-return with no source zone;
   - it is a grant with no parsed modification;
   - its object is unresolved ("parent", "tracked set", or "any target" outside damage).

   These are structural rules. I did not use text to flag.

**Population.** 40,980 abilities on 28,299 cards: 38,689 on clean cards and **2,291** clean abilities on gap cards. The partial
layer's tests excluded **862** of the 3,153 clean gap-card abilities: 339 continuation, 418 no rules text, 105 same-line.
Probe 1's exclusions still apply (items with a gap node, condition-drop flags, corrections-flagged cards). 40,961 abilities
have a usable signature and 19 do not.

**Flagged generic leaves (RF5).** 157 leaves, 5,419 abilities assigned to them, 5,365 of those in leaves of 5 or more. The
reasons overlap:

| missing from the parse | abilities |
|---|---:|
| who draws (17 leaves; Mulldrifter's leaf is 1,976 abilities) | 2,518 |
| return-to-hand: "all" vs "target" not recorded | 1,239 |
| object unresolved by the parser | 1,614 |
| source zone of a self-return | 365 |

Of the 2,518 members of the "who draws" leaves, only 154 (6%) have text naming another player. That is a description of the
result and not an input to any flag. The flag is conservative: most of those leaves are ordinary "you draw" abilities.

**Leaves and placement by variant** (population 40,980; "levels" are the level whose signature matched in FO, and the level of
the retained fields in RF, so level counts are not comparable across the two).

| | FO3 | FO5 | RF3 | **RF5** |
|---|---:|---:|---:|---:|
| leaves (all nodes) | 2,821 | 1,908 | 2,727 | **1,828** |
| leaves at L2 / L3 / L4 / L5 | 128 / 239 / 752 / 1,702 | 111 / 211 / 575 / 1,011 | 130 / 182 / 812 / 1,603 | **113 / 161 / 599 / 955** |
| abilities ending at L2 / L3 / L4 / L5 | 482 / 494 / 7,211 / 32,136 | 789 / 740 / 8,497 / 29,825 | 5,206 / 5,543 / 14,626 / 14,723 | **5,344 / 5,811 / 15,087 / 13,277** |
| abilities assigned to a leaf | 40,323 | 39,851 | 40,098 | **39,519** |
| unplaced, by reason | rare_object 274, rare_verb_parameter 355, rare_effect_type 9, no_signature 19 (657) | 525 / 566 / 19 / 19 (1,129) | 403 / 447 / 13 / 19 (882) | **712 / 701 / 29 / 19 (1,461)** |
| nodes with fewer than MIN direct members / abilities in them | 407 / 550 | 356 / 754 | 650 / 874 | **531 / 1,081** |
| leaves flagged generic | 307 | 203 | 253 | **157** |
| **headline placed** (unflagged, node of 5 or more) | 31,130 | 33,683 | 31,464 | **33,073** (80.7%) |
| placed but flagged generic (kept out of the headline) | 5,119 | 5,414 | 5,187 | **5,365** |
| median node size | 4 | 8 | 4 | **7** |

Size distribution of RF5 nodes (direct members): 1 to 2: 365, 3 to 4: 166, 5 to 9: 552, 10 to 19: 353, 20 to 49: 250, 50 to 99: 83,
100 to 499: 48, 500 and over: 11. Largest: Draw 1,976 (flagged), +1/+1 counter on self 930, mana of any color 864, fixed-color
mana 814, self pump until end of turn 757, "enters tapped" replacements 746, gain life 738, Attach 633, damage to any target 552.
Minimum 3 gives 2,727 to 2,821 nodes with a median of 4, which is worse for browsing without helping any named case, as in probe 1.

---

## 2. Coherence hand check (30 leaves)

**Draw.** RF5, seed 20261007. Frame: leaves with 8 or more abilities directly (898 of 1,828). Strata by level of retained
fields: finest = level 5, mid = levels 3 and 4, coarsest = level 2. Within a stratum, leaves were shuffled with a seeded RNG
and taken in order; a leaf with fewer than 8 members was skipped and the next taken. Skipped: **10 in finest, 7 in mid, 6 in
coarsest** (listed in `signature_probe2_handcheck.json`; all held 1 to 7 members). 8 abilities were read per leaf, with their
signatures. The rule was fixed before reading: *coherent* = all 8 do one thing a tester would accept under one name; *loose*
= at least 6 of 8 do; *incoherent* = fewer than 6 of 8 share one thing. The verdicts are mine, with notes in
`signature_probe2_handcheck_verdicts.json`.

| band | coherent | loose | incoherent |
|---|---:|---:|---:|
| finest (L5) | 10 | 0 | 0 |
| mid (L3, L4) | 9 | 1 | 0 |
| coarsest (L2) | 7 | 3 | 0 |
| **all 30** | **26** | **4** | **0 (0%)** |

**Incoherent leaves: none.** Bar: more than 15% incoherent means don't build. **Not triggered.**

**The 4 loose leaves:**

| leaf | size | why loose |
|---|---:|---|
| `Bounce · to=Hand · Non:Land+Permanent · one` (flagged) | 51 | 5 of 8 are "return target nonland permanent"; Hurkyl's Final Meditation and Displacement Wave return all of them. This is the known "all vs target" gap. |
| `RevealTop · to=Graveyard` | 11 | 6 of 8 make an opponent reveal and put cards in the graveyard; Impromptu Raid and Enduring Renewal reveal your own top card. |
| `BecomeMonarch` | 46 | 6 of 8 "you become the monarch"; Garland and M'Baku give it to an opponent. |
| `Choose` | 224 | "as this enters, choose X" where X varies (colour, creature type, card name, opponent). The parse has `choice_type`, which I did not use. |

**What this draw does and does not show.**

- The probe 1 failure mode, a fallback bucket with unrelated members, did not appear. That is partly because no bucket now exists
  and partly because the sample frame holds only leaves of 8 or more abilities directly.
- 8 of the 10 coarsest leaves are bare effect types with no parameters. They are coherent by construction, so the coarsest
  band is a weak test. Only 18 of the 63 level-2 leaves with 8 or more members carry a verb parameter and no object (for
  example `GainLife · you` 738, `LoseLife · each opponent` 90, `Conjure · to=Hand` 25); 2 of the 10 sampled were of this kind
  (`GainLife · triggering player`, coherent; `RevealTop · to=Graveyard`, loose).
- Leaves holding fewer than 8 abilities directly (930 of 1,828) were not in the frame.
- A leaf can be coherent and still badly named. The 746-ability `Tap · self` leaf is 734 "enters tapped" replacements. It
  would need a human name, and I saw it only in a named case, not in the sample.

## 3. Placement hand check (40 abilities)

**Draw.** Seed 20261007, RF5. Frame: abilities placed in an **unflagged** leaf of 5 or more whose card is noise today, or whose
ability the ledger lists as unplaced: **7,349 abilities**. Forty were drawn with a seeded sample over the (card, bucket,
index) order. Flagged leaves are not in the frame, because they are kept out of the headline.

**Criterion.** *Right* = the ability does what its leaf's signature says. It does not require the signature to capture
everything the ability does.

**Result: 40 right, 0 wrong.** By level: L2 5, L3 4, L4 19, L5 12, all right. By today's status: 21 unplaced noise cards, 5
noise cards that are proximity-placed today, 4 unplaced abilities of ability-placed cards, 3 unclustered, 3 partial, 3
unmodelled, 1 missing-from-export (6 gap-card abilities, too few to say anything about gap cards alone). Stop rule: more than 5%
wrong means don't build. **Not triggered**, but 0 of 40 does not by itself show the rate is under 5%.

Right but lossy (5 of 40, the leaf says less than the ability does):

- Sheoldred's Edict, token mode: the token restriction is not in the leaf.
- Tidal Bore: "tap or untap" sits in the Tap leaf.
- Arachne: "look at an opponent's hand, then choose" sits in the bare Choose leaf.
- Solitary Defiance: the "then discard" is dropped.
- Mystical Teachings: the instant / flash filter is dropped.

One more caution: 12 of the 40 were modal-spell modes or keyword-generated abilities (no ability text of their own), judged from the card text.
The one with no text anywhere in the data (Methods of the Mighty) was checked against the Atomic text.

---

## 4. Named cases against probe 1

Probe 1 reference is its C5 result. "Fixed" means a case moved from wrong to right in probe 2; "unchanged" means same outcome.

**Destroy-all-lands (Armageddon, Bust, Catastrophe, Fall of the Thran, Myojin of Infinite Rage, Ravages of War).** Unchanged under
FO5: one shared 8-member leaf `Destroy · Land · all`, with Decree of Annihilation and Strategy, Schmategy's land mode. Under RF5
it is an 18-member land-specific leaf that also holds the basic-type and nonbasic destroy-all cards (Acid Rain, Boil,
Flashfires, Tsunami, Ruination, Stench of Evil, From the Ashes, Boiling Seas, Ajani Vengeant, Desolation Angel). Land-specific
placements of the 68 core cards: **FO5 34 (same as probe 1), RF5 32.**

**The 11 wrong-target placements.**

| card | probe 1 | probe 2 (RF5) | verdict |
|---|---|---|---|
| Cleansing | land leaf (6) | `Destroy · Land` (2); FO5 6 | unchanged, right |
| Strategy, Schmategy | land mode in land leaf | same, in the 18-member leaf | unchanged, right |
| Bearer of the Heavens | `Destroy · Permanent · all` | same (7; FO5 10) | unchanged, accurate |
| Death Cloud | `LoseLife · all players` (9) | same, coarser: 26 (chain dropped) | unchanged, not fixed; slightly worse |
| Pox Plague | same as Death Cloud | same (26) | unchanged, not fixed; slightly worse |
| Wave of Vitriol | generic `Sacrifice · all players` (10) | `Sacrifice · all players · one` (15) | unchanged, not fixed |
| Global Ruin | generic `Sacrifice` (16) | **unplaced** (rare_object) | not fixed; no longer in a wrong leaf |
| Balancing Act | generic `Sacrifice` (16) | **unplaced** (rare_object) | not fixed; no longer in a wrong leaf |
| Upheaval, Worldpurge | `Bounce · Permanent` with Boomerang | same leaf, now **flagged** and out of the headline | unchanged, not fixed; now visible as untrustworthy |
| Impending Disaster | excluded | excluded | unchanged |

Net: **none of the 11 is newly fixed.** 2 reach a land-specific leaf (as in probe 1), 1 an accurate leaf, 2 become unplaced
instead of wrong, 2 are flagged, 2 are coarser.

**Other cases.**

| case | probe 2 | verdict |
|---|---|---|
| Mill vs surveil | separate leaves (113 / 170) | unchanged, right |
| Spitting Dilophosaurus, −1/−1 trigger | `PutCounter · m1m1 · Creature` (47) | unchanged, right |
| Spitting Dilophosaurus, static | `static:CantBlock · self` (161) | unchanged, wrong: the parse misreads the static |
| Bandit's Talent, opponent discards | `Discard · each opponent` (50) | unchanged, right |
| Bandit's Talent, 2 life loss | **unplaced** (probe 1: generic `LoseLife` of 6) | no longer generic |
| Bandit's Talent, extra draw | Draw leaf, now flagged | unchanged placement, now excluded |
| Dogged Detective, surveil | `Surveil` (170) | unchanged, right |
| Dogged Detective, return from graveyard | `Bounce · self` (186), now **flagged**: source zone and "all/target" not in the parse | unchanged wrong leaf, now out of the headline |
| Shuri, cost reduction | `ReduceCost · Card/spell:Artifact · You` (5) | unchanged, right |
| Shuri, copy | **unplaced** (probe 1: generic `BecomeCopy` of 27) | no longer generic |
| Mulldrifter | the Draw leaf (1,976), now **flagged**, out of the headline | unchanged placement, as asked |
| Spark Double | still outside the population (corrections-flagged) | unchanged |
| Sakura-Tribe Elder | `SearchLibrary · Land · Basic …` (100) | unchanged, right |

Hypothesis (b) from probe 1, "fixes the wrong-target placements", stays **mostly false for parser reasons**: 7 of the 11 lack
the land fact or the "all" fact in the parse.

## 5. Comparison with probe 1 and the old taxonomy

| | probe 1 (C5) | probe 2 FO5 | probe 2 **RF5** |
|---|---:|---:|---:|
| population (abilities) | 41,842 | 40,980 | 40,980 |
| level-1 leaves / abilities | 43 / 569 | 0 | 0 |
| abilities placed, headline (unflagged, node of 5 or more) | not defined | 33,683 | **33,073** |
| placed in flagged-generic leaves | not defined | 5,414 | 5,365 |
| unplaced today, now in a leaf of 5 or more | 9,071 | 7,735 | **7,410** |
| ... in an unflagged non-bare leaf | 7,122 (L3+, not low-info) | 6,055 | **5,756** |
| ... in an unflagged bare leaf / a flagged leaf | 1,643 / – | 691 / 989 | 687 / 967 |
| "Not yet organized" after, **specific leaves only** | 4,449 | 5,020 | **5,183** |
| ... any unflagged leaf | – | 4,750 | 4,909 |
| ... any leaf incl. flagged | 3,633 | 4,400 | 4,547 |
| total leaves | 2,033 | 1,908 | **1,828** |
| leaves of 5 to 9 (abilities) | 812 (5,231) | 780 (5,016) | **552 (3,642)** |
| leaves of 50 or more (abilities) | 147 (22,862) | 143 (21,806) | **142 (22,539)** |

By group, RF5 specific-only: gap cards 989 of 5,252, no close group 2,599 of 3,459, "No effect to group" 8 of 31, not parsed and
known mistakes 0.

- The "specific leaves only" figure is **higher (worse) than probe 1's 4,449** even though the leaf counts are about the same.
  Probe 1 counted generic and fallback leaves as placements and had no gap-card tests; this probe does not.
- This is an upper bound. A card counts as organized if any one ability is in a leaf; the partial layer's hand check found
  194 of 456 gap-card placements "headline lost" (2 of 10 doubtful).
- **Old leaves.** For clustered cards in the same old leaf, **40% of pairs** share a new leaf (RF5; weighted by pairs, as
  34% in probe 1). Per old leaf the median is **76%** (probe 1: 62%). 311 of 657 old leaves keep 80% or more of their pairs
  (probe 1: 210) and 75 keep under 20% (probe 1: 60). That is not a clean improvement: this probe counts only nodes of 5 or more.
  New leaves needed to cover 80% of an old leaf: 1 for 386, 2 for 123, 3 for 56, 4 for 25, 5 for 14, 6 or more for 53.
- **Equipment and Aura grants** no longer mix: `Creature[equipped]` and `Creature[enchanted]` have their own leaves (191 and 238
  for the +N/+N static alone). They still **splinter by granted keyword** where a keyword leaf reaches 5 (the old Equipment leaf
  518's 8 cards sit in 7 new leaves). The probe 1 loss is half fixed.

## 6. Browsability

Proposed display: **30 families, then an effect-type + verb-parameter node, then leaves**; a leaf under the threshold is rolled up
into its node, where it appears as one "other" entry. Flagged leaves are not shown in the tree (157 leaves, 5,365 abilities;
they would appear in a "known parser limits" section). RF5, unflagged leaves, by threshold on direct members:

| threshold | visible leaves | abilities in visible leaves | abilities rolled up | parent nodes | cards with a visible leaf | leaves per card: mean / median / p95 / max |
|---:|---:|---:|---:|---:|---:|---|
| 5 | 1,169 | 33,073 | 0 | 287 | 24,205 | 1.33 / 1 / 3 / **6** |
| **10** | **664** | 29,733 | 3,340 | 220 | 22,109 | 1.31 / 1 / 2 / 5 |
| 20 | 346 | 25,478 | 7,595 | 146 | 19,467 | 1.27 / 1 / 2 / 5 |
| 50 | 123 | 18,772 | 14,301 | 67 | 14,980 | 1.21 / 1 / 2 / 4 |

A card appears under every leaf one of its abilities fits. The average is 1.3 leaves; at threshold 5, 12 cards appear in five or
more and the maximum is 6 (Huatli, Poet of Unity; Fate Reforged; Oko, Lorwyn Liege). **Threshold 10 looks navigable:** 30 families,
about 220 nodes and 664 leaves, with 90% of the headline abilities (29,733 of 33,073) directly visible. Threshold 5 gives
1,169 leaves, which needs search; I would not show it as a flat list.

## 7. Recommendation, by the bars

**Both bars pass, so I recommend a narrow first build, with the caveats below.** Why: 0 of 30 leaves incoherent against a
15% bar, 0 of 40 placements wrong against a 5% bar, and a projected 8,779 to about 5,183 cards "Not yet organized" (3,596 fewer). That is
more than any earlier layer placed (716 and 456). The bars are the only thing I applied, and the samples are too small to
call a rate.

**Scope for a first build**

- **Variant:** RF with minimum 5, literal counts, no level-1 leaves, unflagged leaves only, shown with a display threshold of 10.
- **Population:** clean abilities on clean cards. Clean abilities on gap cards pass the partial layer's tests (1,814 headline
  abilities from them), but the placement sample held only 6 gap-card abilities and the "headline lost" risk from §10 applies, so
  they should be a second step with their own hand check.
- **Not in scope:** flagged leaves (5,365 abilities, 13%) stay out until the parser records the missing field.

**Parser work that would still be needed** (no field exists today)

- who draws ("target player draws"): 2,518 abilities in flagged leaves, 154 of which really name another player
- "all" on return-to-hand
- the source zone of a self-return and graveyard triggers
- unresolved objects ("any target", "parent", "tracked set") on Sacrifice, CastFromZone, ChangeZone and Dig (1,614 abilities)
- dropped clauses (Death Cloud, Global Ruin, Limited Resources, Spark Double's copy)
- static `affected` misreads (Spitting Dilophosaurus, Silumgar Assassin)
- upstream case normalization of `counter_type`

`choice_type` on Choose is already in the parse and would split the loose 224-ability Choose leaf. That is signature work, not parser work.

**Migration from the old 657 leaves**

- **Run it in parallel as an ability-level view first.** New leaves are per ability, so a card is in 1.3 leaves on average. That
  makes the open decision in KNOWN_LIMITATIONS §8 (allow several leaves per card) a prerequisite, not a follow-up.
- **Everything keyed to old leaf ids would have to be rebuilt** to replace the old leaves: branch rules and sub-branches,
  leaf phrases and curated names, the three leaf maps, the also-fits, ability and partial-ability layers, the ledgers, the type
  audit and the browse data. Those are the frozen files, so this stays a separate decision.
- **A crosswalk**: 386 of 657 old leaves map to a single new leaf for 80% of their cards; the other 271 split.
- **Names**: about 1,170 leaves at threshold 5 (664 at threshold 10) would need human-readable names. The "enters tapped" and
  "Choose" leaves show that signature strings are not names.

**Where conclusions rest on judgment**

- all 30 coherence verdicts and all 40 placement verdicts, which are mine, single-reader and unblinded
- the "right" criterion (does what the leaf says, not everything the ability does)
- the bare-fallback guard
- the flag rules, which decide what counts as headline
- the strata definitions, since the coarsest band is mostly bare effect types
- the family map, wrapper unwrapping, the subtype-to-type mapping and "specific" = unflagged and non-bare, all carried from probe 1
