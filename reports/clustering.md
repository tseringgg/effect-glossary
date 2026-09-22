# Raw-overlap HDBSCAN clustering -- first pass

`hdbscan.HDBSCAN` (the standard scikit-learn-compatible reference implementation; see the note at the top of `cluster_effects.py` for why sklearn's own newer port was dropped) over 1 - raw Jaccard distance (`similarity.py`'s `raw` mode: stopword-stripped tokens, card-name masking on, no IDF weighting). Parameters left at sensible defaults (`min_cluster_size=5`, `min_samples=min_cluster_size`) -- first honest pass, not tuned yet.

## Cluster summary

- 42,445 effects total
- 238 excluded before clustering (0 tokens, or 0 shared tokens with anything): not fed to HDBSCAN, reported as noise directly
- 42,207 effects handed to HDBSCAN
- **678 clusters found**
- **32,666 effects labeled noise by HDBSCAN itself** (77.4% of the input; 77.0% of the whole corpus)
- **77.5% of the whole corpus is noise/unclustered** (excluded + HDBSCAN noise combined: 32,904 of 42,445)
- KNN graph: K=25, 10 connected components before bridging (1 giant + 9 small islands), 88 rows needed bridging/degree padding via 15 anchor effects
- HDBSCAN fit: 9s (min_cluster_size=5, min_samples=5, metric=precomputed)

Size distribution (top 15 largest, then a histogram of the rest):

| cluster rank | size | % of corpus |
|--:|--:|--:|
| 1 | 263 | 0.62% |
| 2 | 127 | 0.30% |
| 3 | 122 | 0.29% |
| 4 | 112 | 0.26% |
| 5 | 102 | 0.24% |
| 6 | 99 | 0.23% |
| 7 | 97 | 0.23% |
| 8 | 95 | 0.22% |
| 9 | 70 | 0.16% |
| 10 | 69 | 0.16% |
| 11 | 67 | 0.16% |
| 12 | 66 | 0.16% |
| 13 | 65 | 0.15% |
| 14 | 65 | 0.15% |
| 15 | 51 | 0.12% |

No cluster holds more than 2% of the corpus -- no single-cluster collapse.

| bucket | # clusters |
|---|--:|
| 5 | 70 |
| 6 | 91 |
| 7 | 83 |
| 8 | 54 |
| 9 | 40 |
| 10-24 | 264 |
| 100+ | 5 |
| 25-49 | 61 |
| 50-99 | 10 |

## Validation: known cases

| group | effect | cluster | cluster size |
|---|---|--:|--:|
| Mill | Target player mills five cards. | 430 | 12 |
| Mill | Target player mills two cards. | 430 | 12 |
| Mill | Target opponent mills seven cards. | noise (-1) | — |
| Surveil | Surveil 1. (Look at the top card of your library. You may put it into  | 213 | 11 |
| Surveil | Surveil 2. (Look at the top two cards of your library, then put any nu | noise (-1) | — |
| Board wipes | Destroy all creatures. | 194 | 38 |
| Board wipes | Destroy all creatures. They can't be regenerated. | 194 | 38 |
| Board wipes | All creatures get -X/-X until end of turn. | 611 | 7 |
| Board wipes | Blasphemous Act deals 13 damage to each creature. | noise (-1) | — |
| Single-target removal | Destroy target creature. | 544 | 65 |
| Single-target removal | Destroy target nonblack creature. | 544 | 65 |
| Single-target removal | Exile target creature. Its controller gains life equal to its power. | noise (-1) | — |

### Full membership for the probe clusters

**Mill** -- "Target player mills five cards." is in cluster 430 (12 members):

- Target player mills eight cards.
- {U}, {T}: Target player mills two cards.
- Target player draws X cards.
- Target player mills three cards.
- Target player draws four cards.
- Target player draws three cards.
- Target player mills five cards.
- {1}, {T}: Target player mills three cards.
- Target player mills four cards. (Then exile this card. You may cast the creature later from exile.)
- Target player mills ten cards.
- Target player mills two cards.
- Target player mills four cards.

**Surveil** -- "Surveil 1. (Look at the top card of your library. You may pu" is in cluster 213 (11 members):

- Surveil 1. (Look at the top card of your library. You may put that card into your graveyard.)
- Surveil 1. (Look at the top card of your library. You may put it into your graveyard.)
- {T}: Surveil 1. (Look at the top card of your library. You may put it into your graveyard.)
- {2}{U}{R}, {T}: Surveil 1. (Look at the top card of your library. You may put it into your graveyar…
- {2}{W}{B}, {T}: Surveil 1. (Look at the top card of your library. You may put it into your graveyar…
- {2}, {T}: Surveil 1. (Look at the top card of your library. You may put it into your graveyard.)
- {2}, {T}: Surveil 1. (Look at the top card of your library. You may put that card into your graveya…
- {2}{B}{G}, {T}: Surveil 1. (Look at the top card of your library. You may put it into your graveyar…
- {2}{G}{U}, {T}: Surveil 1. (Look at the top card of your library. You may put it into your graveyar…
- {T}: Surveil 1.
- −1: Surveil 1. (Look at the top card of your library. You may put that card into your graveyard.)

**Board wipes** -- "Destroy all creatures." is in cluster 194 (38 members):

- Destroy all creatures.
- Destroy all creatures and lands.
- Destroy all nonland permanents.
- Destroy all artifacts.
- Destroy all enchantments.
- Destroy all tapped creatures.
- Destroy all untapped creatures.
- Exile all nonland permanents.
- I — Destroy all lands.
- Destroy all creatures. They can't be regenerated.
- Destroy all nonwhite creatures.
- Destroy all nontoken creatures.
- All Sliver creatures have shadow. (They can block or be blocked by only creatures with shadow.)
- Destroy all artifacts, creatures, and lands. They can't be regenerated.
- Destroy all Dragon creatures.
- Destroy all non-Dragon creatures.
- Destroy all small creatures.
- Destroy all medium creatures.
- Destroy all large creatures.
- Tap all nonwhite creatures.
- Destroy all legendary creatures.
- Destroy all nonlegendary creatures.
- When this creature enters, destroy all tapped creatures.
- Bolas — Destroy all creatures.
- All creatures lose flying.
- Destroy all nonartifact creatures.
- I — Destroy all creatures.
- All creatures lose flying until end of turn.
- Destroy all non-Giant creatures. (Then exile this card. You may cast the creature later from exile.)
- Destroy all black creatures.
- Destroy all artifacts, creatures, and enchantments.
- Destroy all artifacts and enchantments.
- Destroy all green creatures.
- Destroy all creatures with flying.
- Destroy all green creatures. They can't be regenerated.
- Tap all creatures.
- Destroy all white creatures.
- Destroy all nonland creatures.

**Board wipes** -- "All creatures get -X/-X until end of turn." is in cluster 611 (7 members):

- All creatures get -2/-0 until end of turn.
- All creatures get -2/-2 until end of turn.
- All creatures get -1/-1 until end of turn.
- All creatures get -X/-X until end of turn.
- All creatures get +2/-2 until end of turn.
- All creatures get -4/-4 until end of turn.
- All creatures get -1/-0 until end of turn.

**Single-target removal** -- "Destroy target creature." is in cluster 544 (65 members):

- Destroy target land.
- When this creature enters, you may destroy target artifact or enchantment.
- When this creature enters, destroy target artifact or enchantment an opponent controls.
- Destroy target creature or planeswalker.
- Destroy target artifact.
- When this creature enters, if it was kicked, destroy target creature with flying.
- Destroy target attacking creature.
- Destroy target creature.
- When this creature enters, you may destroy target creature with flying.
- Destroy target enchantment.
- Destroy target artifact or enchantment.
- Destroy target creature or land.
- When this creature enters, destroy target artifact.
- Destroy target nonblack creature.
- Destroy target land or nonblack creature.
- When Killmonger enters, you may sacrifice another creature. When you do, destroy target nonland per…
- Destroy target tapped creature.
- When this creature enters, destroy target artifact, enchantment, or land.
- When this creature enters, you may destroy target artifact.
- When this creature enters, you may destroy target Equipment.
- Destroy target creature and target land.
- When this creature enters, you may sacrifice another creature. When you do, destroy target creature…
- Destroy target artifact and target enchantment.
- When this creature enters, you may destroy target enchantment.
- Destroy target creature with flying.
- Destroy target artifact or planeswalker.
- When this creature enters, you may destroy target nonblack creature.
- Destroy target artifact, enchantment, or land.
- When this creature enters, destroy target enchantment.
- When this creature enters, tap target creature an opponent controls.
- Destroy target artifact creature.
- Destroy target artifact. (Then exile this card. You may cast the creature later from exile.)
- When this creature enters, if it was kicked, destroy target artifact or enchantment.
- When Storm enters, destroy up to one target artifact, enchantment, or creature with flying.
- Destroy target artifact, enchantment, or creature with flying.
- When this artifact enters, destroy target creature.
- Destroy target land creature or nonbasic land.
- Destroy target attacking creature with flying.
- When this creature enters, destroy target creature an opponent controls.
- When this creature enters, destroy target artifact an opponent controls.
- … and 25 more

## Sample clusters (varying sizes, not cherry-picked for validation)

### Cluster 118 -- 263 effects (size rank 1 of 678)

- Kicker {B} (You may pay an additional {B} as you cast this spell.)
- Equip {3}
- Equip {2}
- Kicker {B} and/or {R} (You may pay an additional {B} and/or {R} as you cast this spell.)
- Madness {B} (If you discard this card, discard it into exile. When you do, cast it for its madness …
- Equip {2} ({2}: Attach to target creature you control. Equip only as a sorcery.)
- Equip {1}
- Kicker {1}{U} and/or {B} (You may pay an additional {1}{U} and/or {B} as you cast this spell.)
- Kicker {2}{G} (You may pay an additional {2}{G} as you cast this spell.)
- Cycling {U} ({U}, Discard this card: Draw a card.)
- Cycling {2} ({2}, Discard this card: Draw a card.)
- Kicker {W} (You may pay an additional {W} as you cast this spell.)
- Flashback {1}{U} (You may cast this card from your graveyard for its flashback cost. Then exile it.)
- Kicker {2}{U} (You may pay an additional {2}{U} as you cast this spell.)
- Kicker {R} (You may pay an additional {R} as you cast this spell.)
- Kicker {2} (You may pay an additional {2} as you cast this spell.)
- Equip {2}{W}{W}
- Overload {3}{U}{U}{R}{R} (You may cast this spell for its overload cost. If you do, change "target"…
- Equip {3} ({3}: Attach to target creature you control. Equip only as a sorcery.)
- Flashback {2}{W} (You may cast this card from your graveyard for its flashback cost. Then exile it.)
- Kicker {4} (You may pay an additional {4} as you cast this spell.)
- Kicker {1}{U} (You may pay an additional {1}{U} as you cast this spell.)
- Disturb {1}{W}{U} (You may cast this card from your graveyard transformed for its disturb cost.)
- Morph {1}{U} (You may cast this card face down as a 2/2 creature for {3}. Turn it face up any time …
- Cycling {B} ({B}, Discard this card: Draw a card.)
- Madness {1}{B} (If you discard this card, discard it into exile. When you do, cast it for its madne…
- Equip {1} ({1}: Attach to target creature you control. Equip only as a sorcery.)
- Kicker {2}{W} (You may pay an additional {2}{W} as you cast this spell.)
- Kicker {1}{G} (You may pay an additional {1}{G} as you cast this spell.)
- Kicker {B}{B} (You may pay an additional {B}{B} as you cast this spell.)
- Morph {5}{U}{U} (You may cast this card face down as a 2/2 creature for {3}. Turn it face up any ti…
- Cycling {W} ({W}, Discard this card: Draw a card.)
- Sneak {2}{W}{B} (You may cast this spell for {2}{W}{B} if you also return an unblocked attacker you…
- Morph {2}{U} (You may cast this card face down as a 2/2 creature for {3}. Turn it face up any time …
- Kicker {3}{U} (You may pay an additional {3}{U} as you cast this spell.)
- Morph {1}{U}{U} (You may cast this card face down as a 2/2 creature for {3}. Turn it face up any ti…
- Flashback {2}{R}{R} (You may cast this card from your graveyard for its flashback cost. Then exile …
- Morph {U} (You may cast this card face down as a 2/2 creature for {3}. Turn it face up any time for…
- Cycling {1} ({1}, Discard this card: Draw a card.)
- Equip {3}{G}{G}
- Unearth {5}{B}{R} ({5}{B}{R}: Return this card from your graveyard to the battlefield. It gains has…
- Flashback {3}{G}{U} (You may cast this card from your graveyard for its flashback cost. Then exile …
- Kicker {2}{U}{U}
- Kicker {G} (You may pay an additional {G} as you cast this spell.)
- Kicker {3} (You may pay an additional {3} as you cast this spell.)
- Kicker {2}{W}{W} (You may pay an additional {2}{W}{W} as you cast this spell.)
- Flashback {3}{B} (You may cast this card from your graveyard for its flashback cost. Then exile it.)
- Morph {2}{R} (You may cast this card face down as a 2/2 creature for {3}. Turn it face up any time …
- Kicker {1}{W} (You may pay an additional {1}{W} as you cast this spell.)
- Cycling {W}{B}{G} ({W}{B}{G}, Discard this card: Draw a card.)
- … and 213 more

### Cluster 278 -- 15 effects (size rank 170 of 678)

- At the beginning of each upkeep, if you don't control a Pest creature token, create a 1/1 black and…
- Magecraft — Whenever you cast or copy an instant or sorcery spell, create a 1/1 black and green Pes…
- When this creature dies, create two 1/1 black and green Pest creature tokens with "Whenever this to…
- Create a 1/1 black and green Pest creature token with "When this token dies, you gain 1 life."
- {T}, Discard a card: Create a 1/1 black and green Pest creature token with "When this token dies, y…
- At the beginning of each upkeep, create a 1/1 black and green Pest creature token with "When this t…
- Create X 1/1 black and green Pest creature tokens with "When this token dies, you gain 1 life," whe…
- When this creature enters, create a 1/1 black and green Pest creature token with "When this token d…
- When Moseo enters, create a 1/1 black and green Pest creature token with "Whenever this token attac…
- Whenever a nontoken creature you control dies, create a 1/1 black and green Pest creature token wit…
- Create a 1/1 black and green Pest creature token with "Whenever this token attacks, you gain 1 life…
- When this creature dies, create two 1/1 black and green Worm creature tokens.
- When this creature enters, create a 1/1 black and green Pest creature token with "Whenever this tok…
- For each opponent, you create a 1/1 black and green Pest creature token with "When this token dies,…
- Create two 1/1 black and green Pest creature tokens with "When this token dies, you gain 1 life."

### Cluster 523 -- 10 effects (size rank 339 of 678)

- Blazing Volley deals 1 damage to each creature your opponents control.
- When this creature enters, it deals 1 damage to each creature your opponents control.
- Easy Pickings deals 1 damage to each creature your opponents control. (Then exile this card. You ma…
- Iroh's Demonstration deals 1 damage to each creature your opponents control.
- Smash to Dust deals 1 damage to each creature your opponents control.
- +2: Sarkhan deals 1 damage to each opponent and each creature your opponents control.
- Destroy target creature with flying. Sagittars' Volley deals 1 damage to each creature with flying …
- When this creature enters, it deals 1 damage to each opponent and 1 damage to each creature your op…
- Scouring Sands deals 1 damage to each creature your opponents control. Scry 1. (Look at the top car…
- Boiling Earth deals 1 damage to each creature your opponents control.

### Cluster 497 -- 7 effects (size rank 509 of 678)

- When Ojer Pakpatiq dies, return it to the battlefield tapped and transformed under its owner's cont…
- When Ojer Taq dies, return it to the battlefield tapped and transformed under its owner's control.
- When Edgar dies, return it to the battlefield transformed under its owner's control.
- When enchanted creature dies, return it to the battlefield tapped under its owner's control.
- When Ojer Axonil dies, return it to the battlefield tapped and transformed under its owner's contro…
- When Ojer Kaslem dies, return it to the battlefield tapped and transformed under its owner's contro…
- When Aclazotz dies, return it to the battlefield tapped and transformed under its owner's control.

### Cluster 650 -- 5 effects (size rank 678 of 678)

- {1}, Sacrifice another creature or artifact: This creature gains indestructible until end of turn. …
- {1}, Sacrifice another creature: This creature gains indestructible until end of turn. Tap it. (Dam…
- Sacrifice another creature: This creature gains indestructible until end of turn. Tap it.
- Sacrifice another creature: Yahenni gains indestructible until end of turn.
- {1}, Sacrifice a creature: Kels gains indestructible until end of turn.

## Automatic check: largest cluster's internal diversity

Cluster 118 (263 effects, the largest) breaks down by leading word (lead-ins like "When this creature enters," stripped first) into **18 distinct leading words**: `kicker`×61, `flashback`×50, `morph`×44, `cycling`×36, `equip`×32, `unearth`×9, `madness`×8, `sneak`×7, `ninjutsu`×5, `overload`×3, `disturb`×1, `transmute`×1.

**Flagged:** that many distinct lead words for one cluster suggests it is several genuinely different effects/keywords chained together by shared short, generic tokens (costs, reminder-adjacent words) rather than one coherent family -- see the full membership above under "Sample clusters" and judge for yourself.

