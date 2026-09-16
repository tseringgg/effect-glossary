# Effect-level search vs whole-card baseline

Corpus: 30 hand-picked cards. Glossary: 34 unique effects from 22 extractions, 31 authored, 3 unauthored.

Embedders: TF-IDF, e5-small-v2, bge-base-en-v1.5. RRF with k=60 over 1-based ranks, ties sharing a rank.

`EL` = effect-level pipeline: authored plain_text effects embedded individually, fused with RRF at the effect level, then aggregated to cards by MAX. `BL` = whole-card baseline: name/type/cost/oracle text concatenated, no splitting, no rewording.

## Cards excluded for missing plain_text coverage

- **Divination** -- every extracted effect is unauthored, so it is absent from every effect-level result. It still appears in the baseline.
- **Ponder** -- every extracted effect is unauthored, so it is absent from every effect-level result. It still appears in the baseline.

Unauthored glossary entries:

- `eff_d165f247e4` 'Look at the top three cards of your library, then put them back in any order. You may shuffle.' -- cards: ponder
- `eff_84c96ff95b` 'Draw a card.' -- cards: ponder
- `eff_7918637ea5` 'Draw two cards.' -- cards: divination

## Primary queries (as specified)

### Query: "a mana dork"

| Card | Cluster role | EL fused | EL tfidf | EL e5 | EL bge | BL fused | BL tfidf | BL e5 | BL bge |
|---|---|---|---|---|---|---|---|---|---|
| Mana Reflection | mana_dork / distractor | 1 | 1 | 6 | 1 | 4 | 1 | 10 | 2 |
| Birds of Paradise **<-** | mana_dork / target | 2 | 7 | 3 | 2 | 2 | 5 | 1 | 3 |
| Chromatic Lantern | mana_dork / distractor | 2 | 7 | 3 | 2 | 3 | 2 | 5 | 4 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 4 | 6 | 1 | 8 | 7 | 4 | 9 | 7 |
| Noble Hierarch | mana_dork / target | 5 | 10 | 2 | 7 | 12 | 6 | 21 | 6 |
| Elvish Mystic **<-** | mana_dork / target | 6 | 2 | 11 | 4 | 5 | 6 | 2 | 9 |
| Fyndhorn Elves | mana_dork / target | 6 | 2 | 11 | 4 | 10 | 6 | 7 | 12 |
| Llanowar Elves **<-** | mana_dork / target | 6 | 2 | 11 | 4 | 17 | 6 | 15 | 19 |
| Avacyn's Pilgrim | mana_dork / target | 9 | 5 | 8 | 9 | 20 | 6 | 24 | 16 |
| Gilded Lotus | mana_dork / distractor | 10 | 9 | 5 | 10 | 1 | 3 | 4 | 1 |
| Cackling Counterpart | clone / target | 11 | 12 | 7 | 15 | 9 | 6 | 3 | 14 |
| Phantasmal Image | clone / target | 12 | 12 | 10 | 13 | 23 | 6 | 18 | 27 |
| Blasphemous Act | board_wipe / target | 13 | 11 | 14 | 11 | 29 | 6 | 28 | 30 |
| Spark Double | clone / target | 14 | 12 | 9 | 17 | 14 | 6 | 13 | 15 |
| Giant Growth | board_wipe / control | 15 | 12 | 16 | 12 | 11 | 6 | 12 | 13 |
| Lightning Bolt | clone / control | 16 | 12 | 15 | 14 | 29 | 6 | 30 | 28 |
| Clever Impersonator | clone / target | 17 | 12 | 20 | 16 | 8 | 6 | 6 | 8 |
| Mirror Image | clone / target | 18 | 12 | 17 | 18 | 16 | 6 | 14 | 20 |
| Clone | clone / target | 19 | 12 | 21 | 20 | 27 | 6 | 25 | 29 |
| Counterspell | board_wipe / control | 20 | 12 | 23 | 19 | 19 | 6 | 17 | 21 |
| Toxic Deluge | board_wipe / target | 21 | 12 | 18 | 21 | 15 | 6 | 11 | 18 |
| Doom Blade | board_wipe / distractor | 22 | 12 | 22 | 24 | 21 | 6 | 23 | 17 |
| Fumigate | board_wipe / target | 23 | 12 | 19 | 28 | 24 | 6 | 19 | 26 |
| Doubling Season | clone / distractor | 24 | 12 | 24 | 22 | 27 | 6 | 29 | 25 |
| Parallel Lives | clone / distractor | 25 | 12 | 28 | 22 | 18 | 6 | 27 | 10 |
| Damnation | board_wipe / target | 26 | 12 | 25 | 25 | 22 | 6 | 20 | 22 |
| Wrath of God | board_wipe / target | 26 | 12 | 25 | 25 | 25 | 6 | 22 | 24 |
| Day of Judgment | board_wipe / target | 28 | 12 | 27 | 27 | 26 | 6 | 26 | 23 |
| Divination | clone / control (EXCLUDED) | -- | -- | -- | -- | 6 | 6 | 8 | 5 |
| Ponder | board_wipe / control (EXCLUDED) | -- | -- | -- | -- | 13 | 6 | 16 | 11 |

`<-` marks the cards this query is supposed to find.

Top 5 effect-level matches, with the effect that carried each card (MAX rule):

1. **Mana Reflection** via `eff_086b340da2` -- 'Whenever you tap a permanent for mana, it produces double the mana instead.'
2. **Birds of Paradise** via `eff_b711c42e82` -- 'Tap this permanent to produce one mana of whatever color you need.'
2. **Chromatic Lantern** via `eff_b711c42e82` -- 'Tap this permanent to produce one mana of whatever color you need.'
4. **Nykthos, Shrine to Nyx** via `eff_84a90976db` -- 'Pay two generic mana and tap this permanent to produce a large burst of mana in a single color, as much as your devotion to that color.'
5. **Noble Hierarch** via `eff_6ba24fb6df` -- 'Tap this permanent to produce one green, white, or blue mana.'

### Query: "a board wipe"

No lexical signal (every document tied, so the model contributes nothing to fusion): effect-level none; baseline tfidf.

| Card | Cluster role | EL fused | EL tfidf | EL e5 | EL bge | BL fused | BL tfidf | BL e5 | BL bge |
|---|---|---|---|---|---|---|---|---|---|
| Blasphemous Act | board_wipe / target | 1 | 1 | 1 | 3 | 14 | 1 | 15 | 14 |
| Cackling Counterpart | clone / target | 2 | 2 | 4 | 9 | 2 | 1 | 1 | 4 |
| Toxic Deluge | board_wipe / target | 3 | 2 | 2 | 13 | 1 | 1 | 2 | 1 |
| Noble Hierarch | mana_dork / target | 4 | 2 | 9 | 8 | 23 | 1 | 27 | 15 |
| Chromatic Lantern | mana_dork / distractor | 5 | 2 | 6 | 11 | 13 | 1 | 19 | 9 |
| Birds of Paradise | mana_dork / target | 5 | 2 | 6 | 11 | 21 | 1 | 25 | 16 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 7 | 2 | 11 | 2 | 18 | 1 | 11 | 27 |
| Giant Growth | board_wipe / control | 8 | 2 | 5 | 15 | 12 | 1 | 7 | 18 |
| Avacyn's Pilgrim | mana_dork / target | 9 | 2 | 14 | 1 | 24 | 1 | 16 | 26 |
| Doom Blade | board_wipe / distractor | 10 | 2 | 12 | 10 | 6 | 1 | 6 | 8 |
| Lightning Bolt | clone / control | 11 | 2 | 3 | 20 | 28 | 1 | 30 | 24 |
| Fumigate | board_wipe / target | 12 | 2 | 10 | 21 | 4 | 1 | 5 | 2 |
| Gilded Lotus | mana_dork / distractor | 13 | 2 | 8 | 24 | 25 | 1 | 26 | 21 |
| Fyndhorn Elves | mana_dork / target | 14 | 2 | 22 | 5 | 27 | 1 | 23 | 28 |
| Llanowar Elves | mana_dork / target | 14 | 2 | 22 | 5 | 29 | 1 | 28 | 30 |
| Elvish Mystic | mana_dork / target | 14 | 2 | 22 | 5 | 30 | 1 | 29 | 29 |
| Clever Impersonator | clone / target | 17 | 2 | 27 | 4 | 15 | 1 | 24 | 11 |
| Mirror Image | clone / target | 18 | 2 | 19 | 14 | 11 | 1 | 14 | 10 |
| Damnation **<-** | board_wipe / target | 19 | 2 | 15 | 17 | 5 | 1 | 4 | 6 |
| Wrath of God **<-** | board_wipe / target | 19 | 2 | 15 | 17 | 8 | 1 | 13 | 5 |
| Spark Double | clone / target | 21 | 2 | 13 | 23 | 22 | 1 | 21 | 20 |
| Counterspell | board_wipe / control | 22 | 2 | 18 | 19 | 3 | 1 | 3 | 3 |
| Clone | clone / target | 23 | 2 | 25 | 16 | 16 | 1 | 12 | 23 |
| Phantasmal Image | clone / target | 24 | 2 | 17 | 25 | 20 | 1 | 20 | 19 |
| Day of Judgment **<-** | board_wipe / target | 25 | 2 | 20 | 22 | 7 | 1 | 9 | 7 |
| Mana Reflection | mana_dork / distractor | 26 | 2 | 26 | 26 | 17 | 1 | 18 | 17 |
| Doubling Season | clone / distractor | 26 | 2 | 21 | 27 | 26 | 1 | 22 | 25 |
| Parallel Lives | clone / distractor | 28 | 2 | 28 | 28 | 19 | 1 | 17 | 22 |
| Divination | clone / control (EXCLUDED) | -- | -- | -- | -- | 9 | 1 | 8 | 12 |
| Ponder | board_wipe / control (EXCLUDED) | -- | -- | -- | -- | 10 | 1 | 10 | 13 |

`<-` marks the cards this query is supposed to find.

Top 5 effect-level matches, with the effect that carried each card (MAX rule):

1. **Blasphemous Act** via `eff_974a6041c8` -- 'This spell costs one less generic mana to cast for each creature on the battlefield, so it gets cheaper as the board fills up.'
2. **Cackling Counterpart** via `eff_04f790315a` -- 'This card has flashback, so you may cast it once from your graveyard for its flashback cost and then it is exiled.'
3. **Toxic Deluge** via `eff_afb5679e1b` -- 'Give every creature on the battlefield the same amount of -X/-X until end of turn, which destroys any whose toughness drops to zero.'
4. **Noble Hierarch** via `eff_6ba24fb6df` -- 'Tap this permanent to produce one green, white, or blue mana.'
5. **Birds of Paradise** via `eff_b711c42e82` -- 'Tap this permanent to produce one mana of whatever color you need.'

### Query: "a clone effect"

No lexical signal (every document tied, so the model contributes nothing to fusion): effect-level tfidf; baseline none.

| Card | Cluster role | EL fused | EL tfidf | EL e5 | EL bge | BL fused | BL tfidf | BL e5 | BL bge |
|---|---|---|---|---|---|---|---|---|---|
| Phantasmal Image | clone / target | 1 | 1 | 1 | 4 | 4 | 4 | 4 | 7 |
| Mirror Image | clone / target | 2 | 1 | 3 | 2 | 2 | 4 | 2 | 2 |
| Cackling Counterpart | clone / target | 3 | 1 | 5 | 1 | 7 | 4 | 8 | 5 |
| Clone **<-** | clone / target | 4 | 1 | 9 | 3 | 1 | 1 | 1 | 1 |
| Spark Double | clone / target | 5 | 1 | 4 | 17 | 8 | 4 | 6 | 9 |
| Clever Impersonator | clone / target | 6 | 1 | 11 | 9 | 4 | 4 | 7 | 4 |
| Toxic Deluge | board_wipe / target | 7 | 1 | 2 | 20 | 17 | 4 | 15 | 21 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 8 | 1 | 16 | 8 | 28 | 4 | 29 | 24 |
| Doubling Season | clone / distractor | 9 | 1 | 15 | 6 | 6 | 2 | 9 | 6 |
| Noble Hierarch | mana_dork / target | 10 | 1 | 7 | 12 | 23 | 4 | 21 | 25 |
| Blasphemous Act | board_wipe / target | 11 | 1 | 8 | 18 | 25 | 4 | 17 | 30 |
| Mana Reflection | mana_dork / distractor | 12 | 1 | 21 | 5 | 10 | 4 | 14 | 8 |
| Parallel Lives | clone / distractor | 13 | 1 | 22 | 6 | 3 | 3 | 3 | 3 |
| Birds of Paradise | mana_dork / target | 14 | 1 | 17 | 10 | 21 | 4 | 26 | 19 |
| Chromatic Lantern | mana_dork / distractor | 14 | 1 | 10 | 10 | 24 | 4 | 24 | 22 |
| Fumigate | board_wipe / target | 16 | 1 | 6 | 27 | 9 | 4 | 5 | 12 |
| Damnation | board_wipe / target | 17 | 1 | 12 | 23 | 13 | 4 | 11 | 15 |
| Wrath of God | board_wipe / target | 17 | 1 | 12 | 23 | 14 | 4 | 10 | 20 |
| Gilded Lotus | mana_dork / distractor | 19 | 1 | 14 | 22 | 30 | 4 | 30 | 27 |
| Giant Growth | board_wipe / control | 20 | 1 | 18 | 19 | 11 | 4 | 12 | 10 |
| Avacyn's Pilgrim | mana_dork / target | 21 | 1 | 24 | 13 | 20 | 4 | 22 | 17 |
| Elvish Mystic | mana_dork / target | 22 | 1 | 26 | 14 | 18 | 4 | 23 | 14 |
| Fyndhorn Elves | mana_dork / target | 22 | 1 | 26 | 14 | 19 | 4 | 25 | 13 |
| Llanowar Elves | mana_dork / target | 22 | 1 | 26 | 14 | 27 | 4 | 27 | 23 |
| Doom Blade | board_wipe / distractor | 25 | 1 | 19 | 25 | 15 | 4 | 16 | 18 |
| Lightning Bolt | clone / control | 26 | 1 | 20 | 26 | 29 | 4 | 28 | 28 |
| Counterspell | board_wipe / control | 27 | 1 | 25 | 21 | 12 | 4 | 13 | 11 |
| Day of Judgment | board_wipe / target | 28 | 1 | 23 | 28 | 26 | 4 | 20 | 29 |
| Divination | clone / control (EXCLUDED) | -- | -- | -- | -- | 15 | 4 | 18 | 16 |
| Ponder | board_wipe / control (EXCLUDED) | -- | -- | -- | -- | 21 | 4 | 19 | 26 |

`<-` marks the cards this query is supposed to find.

Top 5 effect-level matches, with the effect that carried each card (MAX rule):

1. **Phantasmal Image** via `eff_676d325a65` -- 'This creature can enter the battlefield as a copy of any creature already in play, except it is also an Illusion and it is sacrificed as soon as it becomes the target of a spell or ability.'
2. **Mirror Image** via `eff_0edb5a1fd9` -- 'This creature can enter the battlefield as a copy of a creature you already control.'
3. **Cackling Counterpart** via `eff_d9e646fb5c` -- 'Create a token that is a copy of a creature you already control.'
4. **Clone** via `eff_ed25a537f6` -- 'This creature can enter the battlefield as a copy of any creature already in play.'
5. **Spark Double** via `eff_5c74bbe0be` -- 'This creature can enter the battlefield as a copy of a creature or planeswalker you already control, arriving with one extra counter on it and never legendary.'

## Diagnostic paraphrase queries

Same corpus and pipelines, the same three intents phrased in ordinary English instead of MTG jargon.

### Query: "a creature that taps for mana"

| Card | Cluster role | EL fused | EL tfidf | EL e5 | EL bge | BL fused | BL tfidf | BL e5 | BL bge |
|---|---|---|---|---|---|---|---|---|---|
| Birds of Paradise **<-** | mana_dork / target | 1 | 9 | 2 | 2 | 2 | 3 | 3 | 1 |
| Chromatic Lantern | mana_dork / distractor | 1 | 9 | 2 | 2 | 3 | 2 | 7 | 8 |
| Mana Reflection | mana_dork / distractor | 3 | 1 | 8 | 1 | 1 | 1 | 1 | 2 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 4 | 7 | 5 | 4 | 11 | 5 | 15 | 16 |
| Elvish Mystic **<-** | mana_dork / target | 5 | 2 | 9 | 5 | 5 | 14 | 2 | 7 |
| Llanowar Elves **<-** | mana_dork / target | 5 | 2 | 9 | 5 | 10 | 12 | 10 | 11 |
| Fyndhorn Elves | mana_dork / target | 5 | 2 | 9 | 5 | 12 | 12 | 11 | 12 |
| Avacyn's Pilgrim | mana_dork / target | 8 | 5 | 6 | 9 | 20 | 16 | 13 | 19 |
| Noble Hierarch | mana_dork / target | 9 | 14 | 1 | 8 | 13 | 10 | 21 | 6 |
| Gilded Lotus | mana_dork / distractor | 10 | 13 | 4 | 11 | 4 | 4 | 12 | 3 |
| Mirror Image | clone / target | 11 | 6 | 17 | 13 | 14 | 7 | 16 | 17 |
| Clone | clone / target | 12 | 8 | 19 | 10 | 16 | 6 | 25 | 14 |
| Phantasmal Image | clone / target | 13 | 18 | 12 | 12 | 9 | 8 | 14 | 9 |
| Blasphemous Act | board_wipe / target | 14 | 12 | 13 | 16 | 25 | 15 | 28 | 30 |
| Spark Double | clone / target | 15 | 17 | 7 | 18 | 7 | 11 | 6 | 10 |
| Giant Growth | board_wipe / control | 16 | 20 | 15 | 15 | 6 | 18 | 5 | 5 |
| Clever Impersonator | clone / target | 17 | 21 | 18 | 14 | 8 | 9 | 18 | 4 |
| Cackling Counterpart | clone / target | 18 | 19 | 14 | 17 | 15 | 20 | 4 | 20 |
| Lightning Bolt | clone / control | 19 | 23 | 16 | 19 | 28 | 21 | 30 | 26 |
| Day of Judgment | board_wipe / target | 20 | 11 | 27 | 26 | 26 | 21 | 24 | 27 |
| Doom Blade | board_wipe / distractor | 21 | 22 | 23 | 20 | 18 | 17 | 17 | 13 |
| Damnation | board_wipe / target | 22 | 15 | 25 | 23 | 23 | 21 | 22 | 23 |
| Wrath of God | board_wipe / target | 22 | 15 | 25 | 23 | 23 | 21 | 23 | 22 |
| Counterspell | board_wipe / control | 24 | 26 | 22 | 21 | 19 | 21 | 9 | 18 |
| Toxic Deluge | board_wipe / target | 25 | 25 | 20 | 22 | 17 | 21 | 8 | 15 |
| Fumigate | board_wipe / target | 26 | 24 | 21 | 28 | 22 | 19 | 20 | 24 |
| Doubling Season | clone / distractor | 27 | 26 | 24 | 25 | 30 | 21 | 29 | 28 |
| Parallel Lives | clone / distractor | 28 | 26 | 28 | 27 | 27 | 21 | 26 | 25 |
| Divination | clone / control (EXCLUDED) | -- | -- | -- | -- | 21 | 21 | 19 | 21 |
| Ponder | board_wipe / control (EXCLUDED) | -- | -- | -- | -- | 29 | 21 | 27 | 29 |

`<-` marks the cards this query is supposed to find.

### Query: "destroy all creatures"

| Card | Cluster role | EL fused | EL tfidf | EL e5 | EL bge | BL fused | BL tfidf | BL e5 | BL bge |
|---|---|---|---|---|---|---|---|---|---|
| Day of Judgment **<-** | board_wipe / target | 1 | 1 | 1 | 3 | 1 | 1 | 1 | 1 |
| Damnation **<-** | board_wipe / target | 2 | 3 | 4 | 1 | 3 | 2 | 5 | 3 |
| Wrath of God **<-** | board_wipe / target | 2 | 3 | 4 | 1 | 4 | 3 | 4 | 4 |
| Doom Blade | board_wipe / distractor | 4 | 5 | 2 | 5 | 5 | 5 | 2 | 5 |
| Fumigate | board_wipe / target | 5 | 6 | 3 | 4 | 2 | 4 | 3 | 2 |
| Toxic Deluge | board_wipe / target | 6 | 7 | 6 | 6 | 6 | 6 | 6 | 6 |
| Blasphemous Act | board_wipe / target | 7 | 7 | 7 | 7 | 8 | 7 | 12 | 9 |
| Birds of Paradise | mana_dork / target | 8 | 2 | 11 | 9 | 7 | 7 | 10 | 7 |
| Lightning Bolt | clone / control | 9 | 7 | 8 | 8 | 16 | 7 | 24 | 11 |
| Giant Growth | board_wipe / control | 10 | 7 | 9 | 12 | 11 | 7 | 7 | 17 |
| Chromatic Lantern | mana_dork / distractor | 11 | 7 | 10 | 11 | 15 | 7 | 23 | 10 |
| Clone | clone / target | 12 | 7 | 12 | 16 | 12 | 7 | 11 | 14 |
| Phantasmal Image | clone / target | 13 | 7 | 13 | 17 | 13 | 7 | 13 | 13 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 14 | 7 | 20 | 10 | 26 | 7 | 27 | 22 |
| Gilded Lotus | mana_dork / distractor | 15 | 7 | 17 | 18 | 25 | 7 | 28 | 21 |
| Noble Hierarch | mana_dork / target | 16 | 7 | 14 | 22 | 10 | 7 | 14 | 8 |
| Cackling Counterpart | clone / target | 17 | 7 | 15 | 23 | 8 | 7 | 9 | 12 |
| Clever Impersonator | clone / target | 18 | 7 | 18 | 21 | 19 | 7 | 22 | 15 |
| Llanowar Elves | mana_dork / target | 19 | 7 | 25 | 13 | 17 | 7 | 16 | 18 |
| Fyndhorn Elves | mana_dork / target | 19 | 7 | 25 | 13 | 20 | 7 | 21 | 16 |
| Elvish Mystic | mana_dork / target | 19 | 7 | 25 | 13 | 21 | 7 | 15 | 25 |
| Mirror Image | clone / target | 22 | 7 | 19 | 24 | 22 | 7 | 20 | 23 |
| Spark Double | clone / target | 23 | 7 | 16 | 26 | 23 | 7 | 19 | 27 |
| Avacyn's Pilgrim | mana_dork / target | 24 | 7 | 22 | 19 | 18 | 7 | 17 | 19 |
| Counterspell | board_wipe / control | 25 | 7 | 21 | 20 | 14 | 7 | 8 | 20 |
| Mana Reflection | mana_dork / distractor | 26 | 7 | 23 | 25 | 30 | 7 | 29 | 28 |
| Doubling Season | clone / distractor | 27 | 7 | 24 | 27 | 29 | 7 | 30 | 26 |
| Parallel Lives | clone / distractor | 28 | 7 | 28 | 28 | 27 | 7 | 25 | 24 |
| Ponder | board_wipe / control (EXCLUDED) | -- | -- | -- | -- | 24 | 7 | 18 | 30 |
| Divination | clone / control (EXCLUDED) | -- | -- | -- | -- | 28 | 7 | 26 | 29 |

`<-` marks the cards this query is supposed to find.

### Query: "copy a creature"

| Card | Cluster role | EL fused | EL tfidf | EL e5 | EL bge | BL fused | BL tfidf | BL e5 | BL bge |
|---|---|---|---|---|---|---|---|---|---|
| Cackling Counterpart | clone / target | 1 | 3 | 1 | 1 | 6 | 6 | 5 | 6 |
| Mirror Image | clone / target | 2 | 1 | 3 | 2 | 2 | 2 | 2 | 2 |
| Clone **<-** | clone / target | 3 | 2 | 4 | 3 | 1 | 1 | 1 | 1 |
| Phantasmal Image | clone / target | 4 | 5 | 2 | 4 | 4 | 3 | 4 | 4 |
| Spark Double | clone / target | 5 | 4 | 5 | 6 | 5 | 4 | 6 | 5 |
| Clever Impersonator | clone / target | 6 | 6 | 6 | 5 | 3 | 5 | 3 | 3 |
| Doom Blade | board_wipe / distractor | 7 | 13 | 7 | 7 | 17 | 13 | 18 | 16 |
| Damnation | board_wipe / target | 8 | 9 | 15 | 8 | 13 | 17 | 12 | 12 |
| Wrath of God | board_wipe / target | 8 | 9 | 15 | 8 | 16 | 17 | 16 | 13 |
| Giant Growth | board_wipe / control | 10 | 12 | 13 | 10 | 15 | 15 | 14 | 14 |
| Birds of Paradise | mana_dork / target | 11 | 16 | 9 | 15 | 11 | 14 | 13 | 10 |
| Noble Hierarch | mana_dork / target | 12 | 8 | 10 | 19 | 12 | 7 | 17 | 17 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 13 | 18 | 17 | 11 | 26 | 17 | 22 | 28 |
| Toxic Deluge | board_wipe / target | 14 | 17 | 8 | 17 | 18 | 17 | 11 | 21 |
| Lightning Bolt | clone / control | 15 | 14 | 12 | 24 | 30 | 17 | 30 | 30 |
| Blasphemous Act | board_wipe / target | 16 | 11 | 14 | 21 | 21 | 11 | 23 | 29 |
| Chromatic Lantern | mana_dork / distractor | 17 | 18 | 19 | 16 | 19 | 17 | 20 | 18 |
| Fumigate | board_wipe / target | 18 | 15 | 11 | 28 | 10 | 16 | 10 | 11 |
| Day of Judgment | board_wipe / target | 19 | 7 | 20 | 27 | 22 | 17 | 19 | 26 |
| Fyndhorn Elves | mana_dork / target | 20 | 18 | 22 | 12 | 7 | 8 | 8 | 7 |
| Elvish Mystic | mana_dork / target | 20 | 18 | 22 | 12 | 8 | 10 | 7 | 8 |
| Llanowar Elves | mana_dork / target | 20 | 18 | 22 | 12 | 9 | 8 | 9 | 9 |
| Mana Reflection | mana_dork / distractor | 23 | 18 | 25 | 18 | 27 | 17 | 27 | 23 |
| Avacyn's Pilgrim | mana_dork / target | 24 | 18 | 21 | 20 | 14 | 12 | 15 | 15 |
| Gilded Lotus | mana_dork / distractor | 25 | 18 | 18 | 26 | 29 | 17 | 28 | 27 |
| Parallel Lives | clone / distractor | 26 | 18 | 28 | 22 | 23 | 17 | 26 | 20 |
| Doubling Season | clone / distractor | 26 | 18 | 26 | 22 | 28 | 17 | 29 | 24 |
| Counterspell | board_wipe / control | 28 | 18 | 27 | 25 | 20 | 17 | 25 | 19 |
| Ponder | board_wipe / control (EXCLUDED) | -- | -- | -- | -- | 24 | 17 | 21 | 25 |
| Divination | clone / control (EXCLUDED) | -- | -- | -- | -- | 25 | 17 | 24 | 22 |

`<-` marks the cards this query is supposed to find.

## Summary: ranks of the cards each query should find

| Query | Target cards | Effect-level ranks | Baseline ranks |
|---|---|---|---|
| a mana dork | Llanowar Elves, Elvish Mystic, Birds of Paradise | 6, 6, 2 | 17, 5, 2 |
| a board wipe | Wrath of God, Damnation, Day of Judgment | 19, 19, 25 | 8, 5, 7 |
| a clone effect | Clone | 4 | 1 |
| a creature that taps for mana | Llanowar Elves, Elvish Mystic, Birds of Paradise | 5, 5, 1 | 10, 5, 2 |
| destroy all creatures | Wrath of God, Damnation, Day of Judgment | 2, 2, 1 | 4, 3, 1 |
| copy a creature | Clone | 3 | 1 |

