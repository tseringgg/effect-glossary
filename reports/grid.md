# Controlled grid: effect-level vs whole-card

Two confounds from the first run are held down here: query-side jargon (this experiment has no slang layer, the real pipeline does) and card-name leakage (the baseline can win by string-matching a card's own name).

## Query variants

| Cluster | Variant | Query text | Source |
|---|---|---|---|
| mana_dork | jargon | a mana dork | real glossary: terms 'ramp' + 'mana dork' |
| mana_dork | expanded | a mana dork (ramp: increases available mana, usually by putting extra lands into play or adding mana; mana dork: a creature that taps to produce mana, accelerating you ahead) |  |
| mana_dork | glossed | increases available mana, usually by putting extra lands into play or adding mana; a creature that taps to produce mana, accelerating you ahead |  |
| board_wipe | jargon | a board wipe | real glossary: term 'wrath' (alias 'board wipe') |
| board_wipe | expanded | a board wipe (wrath: destroys all creatures at once; a board wipe or mass removal reset) |  |
| board_wipe | glossed | destroys all creatures at once; a board wipe or mass removal reset |  |
| clone | jargon | a clone effect | APPROXIMATED -- the real glossary has no clone term and its LLM fallback raises NotImplementedError, so this gloss was written to match the register of the real entries |
| clone | expanded | a clone effect (clone: enters the battlefield as a copy of a creature already in play) |  |
| clone | glossed | enters the battlefield as a copy of a creature already in play |  |

`expanded` is exactly what the real slang layer emits. It expands rather than replaces, so the jargon stays and the term label is prepended to the gloss. That puts the literal token "wrath" into the board-wipe query and the token "clone" into the clone query, which string-match the cards Wrath of God and Clone. The real translation therefore reintroduces name leakage. `glossed` drops the jargon and the term label, and is the only variant that removes the confound.

## Is effect-level actually name-independent?

- Card names found in the indexed text: **none**
- Distinctive name tokens found: **none**
- Rebuilding the effect-level index with every card name replaced by nonsense and re-running all 9 queries: ranks identical in **9 of 9** cases.

Confirmed rather than assumed: effect-level ranks cannot move when card names change, so `effect-level` columns are identical across the two baseline variants and are printed once per query.

## Cluster: mana_dork

### jargon query &mdash; 'a mana dork'

| Card | Role | effect-level fused | tfidf | e5 | bge | baseline +name fused | tfidf | e5 | bge | baseline -name fused | tfidf | e5 | bge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Mana Reflection | mana_dork / distractor | 1 | 1 | 6 | 1 | 4 | 1 | 10 | 2 | 4 | 2 | 13 | 2 |
| Chromatic Lantern | mana_dork / distractor | 2 | 7 | 3 | 2 | 3 | 2 | 5 | 4 | 1 | 1 | 2 | 4 |
| Birds of Paradise | mana_dork / target **TARGET** | 2 | 7 | 3 | 2 | 2 | 5 | 1 | 3 | 3 | 4 | 1 | 3 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 4 | 6 | 1 | 8 | 7 | 4 | 9 | 7 | 8 | 5 | 9 | 6 |
| Noble Hierarch | mana_dork / target **TARGET** | 5 | 10 | 2 | 7 | 12 | 6 | 21 | 6 | 19 | 6 | 23 | 14 |
| Elvish Mystic | mana_dork / target **TARGET** | 6 | 2 | 11 | 4 | 5 | 6 | 2 | 9 | 5 | 6 | 4 | 9 |
| Fyndhorn Elves | mana_dork / target **TARGET** | 6 | 2 | 11 | 4 | 10 | 6 | 7 | 12 | 5 | 6 | 4 | 9 |
| Llanowar Elves | mana_dork / target **TARGET** | 6 | 2 | 11 | 4 | 17 | 6 | 15 | 19 | 5 | 6 | 4 | 9 |
| Avacyn's Pilgrim | mana_dork / target **TARGET** | 9 | 5 | 8 | 9 | 20 | 6 | 24 | 16 | 9 | 6 | 8 | 7 |
| Gilded Lotus | mana_dork / distractor | 10 | 9 | 5 | 10 | 1 | 3 | 4 | 1 | 2 | 3 | 3 | 1 |
| Cackling Counterpart | clone / target | 11 | 12 | 7 | 15 | 9 | 6 | 3 | 14 | 15 | 6 | 10 | 23 |
| Phantasmal Image | clone / target | 12 | 12 | 10 | 13 | 23 | 6 | 18 | 27 | 27 | 6 | 22 | 28 |
| Blasphemous Act | board_wipe / target | 13 | 11 | 14 | 11 | 29 | 6 | 28 | 30 | 30 | 6 | 27 | 30 |
| Spark Double | clone / target | 14 | 12 | 9 | 17 | 14 | 6 | 13 | 15 | 20 | 6 | 20 | 17 |
| Giant Growth | board_wipe / control | 15 | 12 | 16 | 12 | 11 | 6 | 12 | 13 | 11 | 6 | 18 | 8 |
| Lightning Bolt | clone / control | 16 | 12 | 15 | 14 | 29 | 6 | 30 | 28 | 29 | 6 | 30 | 26 |
| Clever Impersonator | clone / target | 17 | 12 | 20 | 16 | 8 | 6 | 6 | 8 | 12 | 6 | 12 | 16 |
| Mirror Image | clone / target | 18 | 12 | 17 | 18 | 16 | 6 | 14 | 20 | 14 | 6 | 11 | 21 |
| Clone | clone / target | 19 | 12 | 21 | 20 | 27 | 6 | 25 | 29 | 23 | 6 | 19 | 24 |
| Counterspell | board_wipe / control | 20 | 12 | 23 | 19 | 19 | 6 | 17 | 21 | 21 | 6 | 14 | 25 |
| Toxic Deluge | board_wipe / target | 21 | 12 | 18 | 21 | 15 | 6 | 11 | 18 | 18 | 6 | 15 | 20 |
| Doom Blade | board_wipe / distractor | 22 | 12 | 22 | 24 | 21 | 6 | 23 | 17 | 17 | 6 | 7 | 29 |
| Fumigate | board_wipe / target | 23 | 12 | 19 | 28 | 24 | 6 | 19 | 26 | 13 | 6 | 16 | 13 |
| Doubling Season | clone / distractor | 24 | 12 | 24 | 22 | 27 | 6 | 29 | 25 | 25 | 6 | 29 | 18 |
| Parallel Lives | clone / distractor | 25 | 12 | 28 | 22 | 18 | 6 | 27 | 10 | 22 | 6 | 28 | 15 |
| Damnation | board_wipe / target | 26 | 12 | 25 | 25 | 22 | 6 | 20 | 22 | 24 | 6 | 26 | 19 |
| Wrath of God | board_wipe / target | 26 | 12 | 25 | 25 | 25 | 6 | 22 | 24 | 26 | 6 | 25 | 22 |
| Day of Judgment | board_wipe / target | 28 | 12 | 27 | 27 | 26 | 6 | 26 | 23 | 28 | 6 | 24 | 27 |
| Divination | clone / control (excluded) | -- | -- | -- | -- | 6 | 6 | 8 | 5 | 10 | 6 | 17 | 5 |
| Ponder | board_wipe / control (excluded) | -- | -- | -- | -- | 13 | 6 | 16 | 11 | 16 | 6 | 21 | 12 |

### expanded query &mdash; 'a mana dork (ramp: increases available mana, usually by putting extra lands into play or adding mana; mana dork: a creature that taps to produce mana, accelerating you ahead)'

| Card | Role | effect-level fused | tfidf | e5 | bge | baseline +name fused | tfidf | e5 | bge | baseline -name fused | tfidf | e5 | bge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Chromatic Lantern | mana_dork / distractor | 1 | 1 | 2 | 2 | 3 | 1 | 10 | 4 | 1 | 1 | 4 | 1 |
| Birds of Paradise | mana_dork / target **TARGET** | 1 | 1 | 6 | 2 | 2 | 3 | 6 | 5 | 3 | 4 | 1 | 4 |
| Mana Reflection | mana_dork / distractor | 3 | 9 | 5 | 1 | 1 | 2 | 3 | 2 | 2 | 2 | 2 | 2 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 4 | 8 | 1 | 4 | 7 | 5 | 16 | 7 | 9 | 5 | 11 | 10 |
| Noble Hierarch | mana_dork / target **TARGET** | 5 | 11 | 4 | 5 | 9 | 10 | 19 | 1 | 11 | 10 | 20 | 5 |
| Gilded Lotus | mana_dork / distractor | 6 | 3 | 10 | 11 | 6 | 4 | 23 | 3 | 4 | 3 | 16 | 3 |
| Blasphemous Act | board_wipe / target | 7 | 16 | 8 | 6 | 25 | 15 | 26 | 28 | 26 | 16 | 29 | 26 |
| Elvish Mystic | mana_dork / target **TARGET** | 8 | 4 | 20 | 7 | 8 | 14 | 5 | 9 | 5 | 11 | 6 | 7 |
| Fyndhorn Elves | mana_dork / target **TARGET** | 8 | 4 | 20 | 7 | 12 | 12 | 15 | 8 | 5 | 11 | 6 | 7 |
| Llanowar Elves | mana_dork / target **TARGET** | 8 | 4 | 20 | 7 | 15 | 12 | 20 | 11 | 5 | 11 | 6 | 7 |
| Avacyn's Pilgrim | mana_dork / target **TARGET** | 11 | 7 | 14 | 14 | 26 | 16 | 29 | 25 | 16 | 15 | 15 | 17 |
| Cackling Counterpart | clone / target | 12 | 21 | 3 | 13 | 11 | 20 | 2 | 14 | 18 | 20 | 13 | 21 |
| Spark Double | clone / target | 13 | 13 | 7 | 17 | 5 | 11 | 4 | 10 | 10 | 14 | 5 | 12 |
| Phantasmal Image | clone / target | 14 | 15 | 12 | 12 | 14 | 8 | 13 | 19 | 13 | 9 | 14 | 18 |
| Mirror Image | clone / target | 15 | 17 | 9 | 16 | 13 | 7 | 9 | 22 | 12 | 6 | 9 | 22 |
| Giant Growth | board_wipe / control | 16 | 22 | 11 | 10 | 4 | 18 | 1 | 6 | 8 | 18 | 3 | 6 |
| Clone | clone / target | 17 | 10 | 17 | 19 | 19 | 6 | 21 | 23 | 17 | 7 | 22 | 23 |
| Clever Impersonator | clone / target | 18 | 12 | 19 | 15 | 10 | 9 | 11 | 13 | 14 | 8 | 18 | 19 |
| Toxic Deluge | board_wipe / target | 19 | 14 | 13 | 22 | 17 | 21 | 7 | 18 | 15 | 21 | 10 | 16 |
| Lightning Bolt | clone / control | 20 | 24 | 16 | 18 | 30 | 21 | 30 | 30 | 30 | 21 | 30 | 29 |
| Doubling Season | clone / distractor | 21 | 26 | 15 | 20 | 21 | 21 | 18 | 16 | 20 | 21 | 24 | 11 |
| Damnation | board_wipe / target | 22 | 19 | 26 | 24 | 28 | 21 | 25 | 27 | 27 | 21 | 28 | 25 |
| Wrath of God | board_wipe / target | 22 | 19 | 26 | 24 | 27 | 21 | 24 | 26 | 29 | 21 | 27 | 28 |
| Day of Judgment | board_wipe / target | 24 | 18 | 28 | 27 | 29 | 21 | 27 | 29 | 28 | 21 | 25 | 30 |
| Parallel Lives | clone / distractor | 25 | 26 | 24 | 21 | 18 | 21 | 14 | 12 | 19 | 21 | 19 | 15 |
| Fumigate | board_wipe / target | 26 | 25 | 18 | 28 | 22 | 19 | 17 | 24 | 21 | 19 | 17 | 20 |
| Doom Blade | board_wipe / distractor | 27 | 23 | 23 | 26 | 24 | 17 | 28 | 20 | 25 | 17 | 21 | 27 |
| Counterspell | board_wipe / control | 28 | 26 | 25 | 23 | 20 | 21 | 12 | 21 | 22 | 21 | 12 | 24 |
| Divination | clone / control (excluded) | -- | -- | -- | -- | 16 | 21 | 8 | 15 | 23 | 21 | 23 | 13 |
| Ponder | board_wipe / control (excluded) | -- | -- | -- | -- | 23 | 21 | 22 | 17 | 24 | 21 | 26 | 14 |

### glossed query &mdash; 'increases available mana, usually by putting extra lands into play or adding mana; a creature that taps to produce mana, accelerating you ahead'

| Card | Role | effect-level fused | tfidf | e5 | bge | baseline +name fused | tfidf | e5 | bge | baseline -name fused | tfidf | e5 | bge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Nykthos, Shrine to Nyx | mana_dork / distractor | 1 | 8 | 2 | 3 | 5 | 5 | 10 | 9 | 4 | 5 | 4 | 8 |
| Mana Reflection | mana_dork / distractor | 2 | 11 | 5 | 1 | 1 | 2 | 2 | 1 | 1 | 2 | 1 | 1 |
| Chromatic Lantern | mana_dork / distractor | 3 | 1 | 3 | 2 | 2 | 1 | 5 | 3 | 2 | 1 | 5 | 2 |
| Birds of Paradise | mana_dork / target **TARGET** | 3 | 1 | 7 | 6 | 3 | 3 | 9 | 6 | 3 | 4 | 2 | 3 |
| Blasphemous Act | board_wipe / target | 5 | 16 | 6 | 4 | 26 | 15 | 26 | 29 | 24 | 16 | 26 | 25 |
| Noble Hierarch | mana_dork / target **TARGET** | 6 | 10 | 4 | 5 | 8 | 10 | 16 | 5 | 7 | 10 | 11 | 4 |
| Gilded Lotus | mana_dork / distractor | 7 | 3 | 11 | 15 | 6 | 4 | 21 | 4 | 5 | 3 | 12 | 6 |
| Elvish Mystic | mana_dork / target **TARGET** | 8 | 4 | 20 | 7 | 13 | 14 | 12 | 13 | 8 | 11 | 13 | 10 |
| Fyndhorn Elves | mana_dork / target **TARGET** | 8 | 4 | 20 | 7 | 15 | 12 | 20 | 10 | 8 | 11 | 13 | 10 |
| Llanowar Elves | mana_dork / target **TARGET** | 8 | 4 | 20 | 7 | 16 | 12 | 19 | 12 | 8 | 11 | 13 | 10 |
| Cackling Counterpart | clone / target | 11 | 21 | 1 | 17 | 11 | 20 | 6 | 11 | 16 | 20 | 10 | 14 |
| Avacyn's Pilgrim | mana_dork / target **TARGET** | 12 | 7 | 18 | 12 | 24 | 16 | 29 | 21 | 20 | 15 | 22 | 17 |
| Spark Double | clone / target | 13 | 13 | 8 | 18 | 7 | 11 | 3 | 14 | 11 | 14 | 7 | 15 |
| Clone | clone / target | 14 | 9 | 15 | 14 | 20 | 6 | 22 | 24 | 19 | 7 | 21 | 24 |
| Mirror Image | clone / target | 15 | 17 | 10 | 13 | 18 | 7 | 15 | 25 | 15 | 6 | 16 | 22 |
| Clever Impersonator | clone / target | 16 | 12 | 17 | 10 | 17 | 9 | 18 | 18 | 18 | 8 | 20 | 19 |
| Toxic Deluge | board_wipe / target | 17 | 14 | 9 | 20 | 12 | 21 | 4 | 16 | 14 | 21 | 6 | 13 |
| Phantasmal Image | clone / target | 18 | 15 | 13 | 16 | 14 | 8 | 13 | 20 | 17 | 9 | 18 | 18 |
| Giant Growth | board_wipe / control | 19 | 22 | 12 | 11 | 4 | 18 | 1 | 2 | 6 | 18 | 3 | 5 |
| Lightning Bolt | clone / control | 20 | 24 | 16 | 19 | 30 | 21 | 30 | 28 | 29 | 21 | 30 | 29 |
| Doubling Season | clone / distractor | 21 | 26 | 14 | 21 | 10 | 21 | 8 | 8 | 12 | 21 | 9 | 7 |
| Damnation | board_wipe / target | 22 | 19 | 24 | 24 | 28 | 21 | 24 | 27 | 27 | 21 | 28 | 26 |
| Wrath of God | board_wipe / target | 22 | 19 | 24 | 24 | 27 | 21 | 23 | 26 | 28 | 21 | 27 | 28 |
| Day of Judgment | board_wipe / target | 24 | 18 | 28 | 27 | 29 | 21 | 27 | 30 | 29 | 21 | 29 | 30 |
| Parallel Lives | clone / distractor | 25 | 26 | 23 | 22 | 9 | 21 | 7 | 7 | 13 | 21 | 8 | 9 |
| Fumigate | board_wipe / target | 26 | 25 | 19 | 28 | 22 | 19 | 17 | 23 | 21 | 19 | 19 | 20 |
| Doom Blade | board_wipe / distractor | 27 | 23 | 27 | 26 | 25 | 17 | 28 | 22 | 26 | 17 | 24 | 27 |
| Counterspell | board_wipe / control | 28 | 26 | 26 | 23 | 19 | 21 | 11 | 17 | 23 | 21 | 17 | 23 |
| Divination | clone / control (excluded) | -- | -- | -- | -- | 21 | 21 | 14 | 15 | 22 | 21 | 23 | 16 |
| Ponder | board_wipe / control (excluded) | -- | -- | -- | -- | 23 | 21 | 25 | 19 | 25 | 21 | 25 | 21 |

## Cluster: board_wipe

### jargon query &mdash; 'a board wipe'

| Card | Role | effect-level fused | tfidf | e5 | bge | baseline +name fused | tfidf | e5 | bge | baseline -name fused | tfidf | e5 | bge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Blasphemous Act | board_wipe / target **TARGET** | 1 | 1 | 1 | 3 | 14 | 1 | 15 | 14 | 19 | 1 | 23 | 15 |
| Cackling Counterpart | clone / target | 2 | 2 | 4 | 9 | 2 | 1 | 1 | 4 | 2 | 1 | 3 | 3 |
| Toxic Deluge | board_wipe / target **TARGET** | 3 | 2 | 2 | 13 | 1 | 1 | 2 | 1 | 6 | 1 | 5 | 10 |
| Noble Hierarch | mana_dork / target | 4 | 2 | 9 | 8 | 23 | 1 | 27 | 15 | 20 | 1 | 24 | 17 |
| Chromatic Lantern | mana_dork / distractor | 5 | 2 | 6 | 11 | 13 | 1 | 19 | 9 | 5 | 1 | 10 | 4 |
| Birds of Paradise | mana_dork / target | 5 | 2 | 6 | 11 | 21 | 1 | 25 | 16 | 13 | 1 | 9 | 18 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 7 | 2 | 11 | 2 | 18 | 1 | 11 | 27 | 27 | 1 | 26 | 22 |
| Giant Growth | board_wipe / control | 8 | 2 | 5 | 15 | 12 | 1 | 7 | 18 | 8 | 1 | 4 | 13 |
| Avacyn's Pilgrim | mana_dork / target | 9 | 2 | 14 | 1 | 24 | 1 | 16 | 26 | 12 | 1 | 6 | 21 |
| Doom Blade | board_wipe / distractor | 10 | 2 | 12 | 10 | 6 | 1 | 6 | 8 | 1 | 1 | 1 | 1 |
| Lightning Bolt | clone / control | 11 | 2 | 3 | 20 | 28 | 1 | 30 | 24 | 21 | 1 | 14 | 29 |
| Fumigate | board_wipe / target **TARGET** | 12 | 2 | 10 | 21 | 4 | 1 | 5 | 2 | 4 | 1 | 8 | 2 |
| Gilded Lotus | mana_dork / distractor | 13 | 2 | 8 | 24 | 25 | 1 | 26 | 21 | 17 | 1 | 18 | 14 |
| Elvish Mystic | mana_dork / target | 14 | 2 | 22 | 5 | 30 | 1 | 29 | 29 | 22 | 1 | 19 | 26 |
| Fyndhorn Elves | mana_dork / target | 14 | 2 | 22 | 5 | 27 | 1 | 23 | 28 | 22 | 1 | 19 | 26 |
| Llanowar Elves | mana_dork / target | 14 | 2 | 22 | 5 | 29 | 1 | 28 | 30 | 22 | 1 | 19 | 26 |
| Clever Impersonator | clone / target | 17 | 2 | 27 | 4 | 15 | 1 | 24 | 11 | 14 | 1 | 29 | 5 |
| Mirror Image | clone / target | 18 | 2 | 19 | 14 | 11 | 1 | 14 | 10 | 15 | 1 | 15 | 16 |
| Damnation | board_wipe / target **TARGET** | 19 | 2 | 15 | 17 | 5 | 1 | 4 | 6 | 11 | 1 | 17 | 7 |
| Wrath of God | board_wipe / target **TARGET** | 19 | 2 | 15 | 17 | 8 | 1 | 13 | 5 | 18 | 1 | 22 | 12 |
| Spark Double | clone / target | 21 | 2 | 13 | 23 | 22 | 1 | 21 | 20 | 16 | 1 | 13 | 19 |
| Counterspell | board_wipe / control | 22 | 2 | 18 | 19 | 3 | 1 | 3 | 3 | 3 | 1 | 2 | 6 |
| Clone | clone / target | 23 | 2 | 25 | 16 | 16 | 1 | 12 | 23 | 26 | 1 | 27 | 20 |
| Phantasmal Image | clone / target | 24 | 2 | 17 | 25 | 20 | 1 | 20 | 19 | 29 | 1 | 30 | 23 |
| Day of Judgment | board_wipe / target **TARGET** | 25 | 2 | 20 | 22 | 7 | 1 | 9 | 7 | 7 | 1 | 7 | 8 |
| Mana Reflection | mana_dork / distractor | 26 | 2 | 26 | 26 | 17 | 1 | 18 | 17 | 28 | 1 | 25 | 24 |
| Doubling Season | clone / distractor | 26 | 2 | 21 | 27 | 26 | 1 | 22 | 25 | 30 | 1 | 28 | 25 |
| Parallel Lives | clone / distractor | 28 | 2 | 28 | 28 | 19 | 1 | 17 | 22 | 25 | 1 | 16 | 30 |
| Divination | clone / control (excluded) | -- | -- | -- | -- | 9 | 1 | 8 | 12 | 9 | 1 | 12 | 9 |
| Ponder | board_wipe / control (excluded) | -- | -- | -- | -- | 10 | 1 | 10 | 13 | 10 | 1 | 11 | 11 |

### expanded query &mdash; 'a board wipe (wrath: destroys all creatures at once; a board wipe or mass removal reset)'

| Card | Role | effect-level fused | tfidf | e5 | bge | baseline +name fused | tfidf | e5 | bge | baseline -name fused | tfidf | e5 | bge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Toxic Deluge | board_wipe / target **TARGET** | 1 | 3 | 1 | 5 | 7 | 5 | 10 | 6 | 11 | 5 | 11 | 12 |
| Damnation | board_wipe / target **TARGET** | 2 | 4 | 5 | 1 | 2 | 3 | 2 | 2 | 4 | 3 | 6 | 4 |
| Wrath of God | board_wipe / target **TARGET** | 2 | 4 | 5 | 1 | 1 | 1 | 1 | 1 | 5 | 2 | 7 | 5 |
| Day of Judgment | board_wipe / target **TARGET** | 4 | 4 | 4 | 3 | 3 | 2 | 4 | 4 | 1 | 1 | 2 | 2 |
| Fumigate | board_wipe / target **TARGET** | 5 | 4 | 3 | 4 | 4 | 4 | 3 | 3 | 2 | 4 | 3 | 1 |
| Blasphemous Act | board_wipe / target **TARGET** | 6 | 1 | 2 | 7 | 8 | 6 | 7 | 10 | 7 | 6 | 9 | 8 |
| Noble Hierarch | mana_dork / target | 7 | 4 | 11 | 6 | 11 | 6 | 15 | 8 | 9 | 6 | 12 | 6 |
| Giant Growth | board_wipe / control | 8 | 4 | 7 | 11 | 10 | 6 | 9 | 11 | 10 | 6 | 8 | 10 |
| Lightning Bolt | clone / control | 9 | 4 | 8 | 9 | 15 | 6 | 20 | 13 | 17 | 6 | 16 | 17 |
| Doom Blade | board_wipe / distractor | 10 | 4 | 10 | 8 | 5 | 6 | 6 | 5 | 3 | 6 | 1 | 3 |
| Cackling Counterpart | clone / target | 11 | 4 | 9 | 10 | 6 | 6 | 5 | 7 | 6 | 6 | 4 | 7 |
| Chromatic Lantern | mana_dork / distractor | 12 | 4 | 12 | 14 | 19 | 6 | 24 | 12 | 13 | 6 | 20 | 9 |
| Phantasmal Image | clone / target | 13 | 4 | 14 | 17 | 15 | 6 | 13 | 20 | 15 | 6 | 13 | 19 |
| Mirror Image | clone / target | 14 | 4 | 18 | 15 | 12 | 6 | 11 | 19 | 19 | 6 | 17 | 18 |
| Clone | clone / target | 15 | 4 | 22 | 12 | 17 | 6 | 12 | 22 | 20 | 6 | 21 | 16 |
| Spark Double | clone / target | 16 | 4 | 13 | 21 | 13 | 6 | 14 | 17 | 14 | 6 | 10 | 20 |
| Mana Reflection | mana_dork / distractor | 17 | 4 | 21 | 16 | 21 | 6 | 21 | 18 | 26 | 6 | 27 | 21 |
| Clever Impersonator | clone / target | 18 | 4 | 24 | 13 | 23 | 6 | 23 | 21 | 18 | 6 | 23 | 11 |
| Birds of Paradise | mana_dork / target | 19 | 2 | 16 | 20 | 20 | 6 | 22 | 14 | 12 | 6 | 14 | 14 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 20 | 4 | 15 | 18 | 22 | 6 | 17 | 25 | 27 | 6 | 22 | 28 |
| Doubling Season | clone / distractor | 21 | 4 | 17 | 27 | 14 | 6 | 16 | 15 | 16 | 6 | 18 | 15 |
| Counterspell | board_wipe / control | 22 | 4 | 19 | 25 | 9 | 6 | 8 | 9 | 8 | 6 | 5 | 13 |
| Gilded Lotus | mana_dork / distractor | 23 | 4 | 20 | 26 | 29 | 6 | 30 | 27 | 28 | 6 | 29 | 26 |
| Avacyn's Pilgrim | mana_dork / target | 24 | 4 | 25 | 19 | 27 | 6 | 28 | 26 | 22 | 6 | 19 | 25 |
| Elvish Mystic | mana_dork / target | 25 | 4 | 26 | 22 | 28 | 6 | 26 | 29 | 23 | 6 | 24 | 22 |
| Fyndhorn Elves | mana_dork / target | 25 | 4 | 26 | 22 | 26 | 6 | 27 | 24 | 23 | 6 | 24 | 22 |
| Llanowar Elves | mana_dork / target | 25 | 4 | 26 | 22 | 30 | 6 | 29 | 28 | 23 | 6 | 24 | 22 |
| Parallel Lives | clone / distractor | 28 | 4 | 23 | 28 | 18 | 6 | 18 | 16 | 21 | 6 | 15 | 27 |
| Ponder | board_wipe / control (excluded) | -- | -- | -- | -- | 25 | 6 | 19 | 30 | 29 | 6 | 28 | 30 |
| Divination | clone / control (excluded) | -- | -- | -- | -- | 24 | 6 | 25 | 23 | 30 | 6 | 30 | 29 |

### glossed query &mdash; 'destroys all creatures at once; a board wipe or mass removal reset'

| Card | Role | effect-level fused | tfidf | e5 | bge | baseline +name fused | tfidf | e5 | bge | baseline -name fused | tfidf | e5 | bge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Day of Judgment | board_wipe / target **TARGET** | 1 | 4 | 1 | 3 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 |
| Toxic Deluge | board_wipe / target **TARGET** | 2 | 2 | 2 | 5 | 7 | 5 | 9 | 7 | 12 | 5 | 10 | 16 |
| Damnation | board_wipe / target **TARGET** | 3 | 4 | 4 | 1 | 3 | 2 | 3 | 4 | 4 | 3 | 4 | 4 |
| Wrath of God | board_wipe / target **TARGET** | 3 | 4 | 4 | 1 | 4 | 3 | 4 | 3 | 5 | 2 | 5 | 5 |
| Fumigate | board_wipe / target **TARGET** | 5 | 4 | 3 | 4 | 2 | 4 | 2 | 1 | 2 | 4 | 3 | 2 |
| Blasphemous Act | board_wipe / target **TARGET** | 6 | 3 | 6 | 6 | 10 | 6 | 7 | 14 | 11 | 6 | 9 | 13 |
| Doom Blade | board_wipe / distractor | 7 | 4 | 7 | 7 | 5 | 6 | 5 | 5 | 3 | 6 | 2 | 3 |
| Lightning Bolt | clone / control | 8 | 4 | 9 | 8 | 20 | 6 | 23 | 13 | 14 | 6 | 18 | 12 |
| Noble Hierarch | mana_dork / target | 9 | 4 | 11 | 9 | 11 | 6 | 12 | 11 | 10 | 6 | 11 | 10 |
| Giant Growth | board_wipe / control | 10 | 4 | 8 | 16 | 8 | 6 | 8 | 10 | 7 | 6 | 8 | 9 |
| Chromatic Lantern | mana_dork / distractor | 11 | 4 | 14 | 11 | 12 | 6 | 22 | 9 | 15 | 6 | 25 | 7 |
| Cackling Counterpart | clone / target | 12 | 4 | 10 | 22 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 13 | 4 | 17 | 10 | 23 | 6 | 17 | 27 | 30 | 6 | 26 | 30 |
| Gilded Lotus | mana_dork / distractor | 14 | 4 | 18 | 20 | 26 | 6 | 30 | 23 | 23 | 6 | 29 | 17 |
| Avacyn's Pilgrim | mana_dork / target | 15 | 4 | 23 | 12 | 28 | 6 | 25 | 28 | 21 | 6 | 19 | 23 |
| Phantasmal Image | clone / target | 16 | 4 | 13 | 25 | 18 | 6 | 14 | 21 | 19 | 6 | 16 | 21 |
| Spark Double | clone / target | 17 | 4 | 12 | 27 | 19 | 6 | 15 | 20 | 20 | 6 | 17 | 24 |
| Clone | clone / target | 18 | 4 | 20 | 19 | 14 | 6 | 11 | 22 | 16 | 6 | 14 | 18 |
| Birds of Paradise | mana_dork / target | 19 | 1 | 15 | 18 | 15 | 6 | 21 | 12 | 9 | 6 | 12 | 8 |
| Clever Impersonator | clone / target | 20 | 4 | 22 | 17 | 21 | 6 | 19 | 19 | 13 | 6 | 15 | 14 |
| Elvish Mystic | mana_dork / target | 21 | 4 | 26 | 13 | 29 | 6 | 24 | 30 | 25 | 6 | 22 | 27 |
| Fyndhorn Elves | mana_dork / target | 21 | 4 | 26 | 13 | 25 | 6 | 26 | 25 | 25 | 6 | 22 | 27 |
| Llanowar Elves | mana_dork / target | 21 | 4 | 26 | 13 | 30 | 6 | 28 | 29 | 25 | 6 | 22 | 27 |
| Counterspell | board_wipe / control | 24 | 4 | 16 | 26 | 8 | 6 | 10 | 8 | 8 | 6 | 7 | 11 |
| Mirror Image | clone / target | 25 | 4 | 19 | 23 | 13 | 6 | 13 | 18 | 17 | 6 | 13 | 20 |
| Doubling Season | clone / distractor | 26 | 4 | 21 | 24 | 17 | 6 | 16 | 17 | 18 | 6 | 21 | 15 |
| Mana Reflection | mana_dork / distractor | 27 | 4 | 24 | 21 | 22 | 6 | 27 | 16 | 24 | 6 | 28 | 19 |
| Parallel Lives | clone / distractor | 28 | 4 | 25 | 28 | 16 | 6 | 18 | 15 | 22 | 6 | 20 | 22 |
| Ponder | board_wipe / control (excluded) | -- | -- | -- | -- | 24 | 6 | 20 | 26 | 28 | 6 | 27 | 26 |
| Divination | clone / control (excluded) | -- | -- | -- | -- | 27 | 6 | 29 | 24 | 29 | 6 | 30 | 25 |

## Cluster: clone

### jargon query &mdash; 'a clone effect'

| Card | Role | effect-level fused | tfidf | e5 | bge | baseline +name fused | tfidf | e5 | bge | baseline -name fused | tfidf | e5 | bge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Phantasmal Image | clone / target **TARGET** | 1 | 1 | 1 | 4 | 4 | 4 | 4 | 7 | 2 | 3 | 4 | 2 |
| Mirror Image | clone / target **TARGET** | 2 | 1 | 3 | 2 | 2 | 4 | 2 | 2 | 3 | 3 | 7 | 1 |
| Cackling Counterpart | clone / target **TARGET** | 3 | 1 | 5 | 1 | 7 | 4 | 8 | 5 | 6 | 3 | 9 | 5 |
| Clone | clone / target **TARGET** | 4 | 1 | 9 | 3 | 1 | 1 | 1 | 1 | 9 | 3 | 10 | 8 |
| Spark Double | clone / target **TARGET** | 5 | 1 | 4 | 17 | 8 | 4 | 6 | 9 | 7 | 3 | 5 | 10 |
| Clever Impersonator | clone / target **TARGET** | 6 | 1 | 11 | 9 | 4 | 4 | 7 | 4 | 10 | 3 | 15 | 6 |
| Toxic Deluge | board_wipe / target | 7 | 1 | 2 | 20 | 17 | 4 | 15 | 21 | 21 | 3 | 21 | 21 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 8 | 1 | 16 | 8 | 28 | 4 | 29 | 24 | 29 | 3 | 30 | 24 |
| Doubling Season | clone / distractor | 9 | 1 | 15 | 6 | 6 | 2 | 9 | 6 | 4 | 1 | 6 | 4 |
| Noble Hierarch | mana_dork / target | 10 | 1 | 7 | 12 | 23 | 4 | 21 | 25 | 27 | 3 | 28 | 25 |
| Blasphemous Act | board_wipe / target | 11 | 1 | 8 | 18 | 25 | 4 | 17 | 30 | 26 | 3 | 23 | 29 |
| Mana Reflection | mana_dork / distractor | 12 | 1 | 21 | 5 | 10 | 4 | 14 | 8 | 14 | 3 | 22 | 7 |
| Parallel Lives | clone / distractor | 13 | 1 | 22 | 6 | 3 | 3 | 3 | 3 | 1 | 2 | 3 | 3 |
| Birds of Paradise | mana_dork / target | 14 | 1 | 17 | 10 | 21 | 4 | 26 | 19 | 20 | 3 | 20 | 20 |
| Chromatic Lantern | mana_dork / distractor | 14 | 1 | 10 | 10 | 24 | 4 | 24 | 22 | 23 | 3 | 25 | 22 |
| Fumigate | board_wipe / target | 16 | 1 | 6 | 27 | 9 | 4 | 5 | 12 | 11 | 3 | 8 | 17 |
| Damnation | board_wipe / target | 17 | 1 | 12 | 23 | 13 | 4 | 11 | 15 | 18 | 3 | 12 | 19 |
| Wrath of God | board_wipe / target | 17 | 1 | 12 | 23 | 14 | 4 | 10 | 20 | 19 | 3 | 13 | 23 |
| Gilded Lotus | mana_dork / distractor | 19 | 1 | 14 | 22 | 30 | 4 | 30 | 27 | 25 | 3 | 24 | 26 |
| Giant Growth | board_wipe / control | 20 | 1 | 18 | 19 | 11 | 4 | 12 | 10 | 13 | 3 | 11 | 15 |
| Avacyn's Pilgrim | mana_dork / target | 21 | 1 | 24 | 13 | 20 | 4 | 22 | 17 | 12 | 3 | 14 | 11 |
| Elvish Mystic | mana_dork / target | 22 | 1 | 26 | 14 | 18 | 4 | 23 | 14 | 15 | 3 | 16 | 12 |
| Fyndhorn Elves | mana_dork / target | 22 | 1 | 26 | 14 | 19 | 4 | 25 | 13 | 15 | 3 | 16 | 12 |
| Llanowar Elves | mana_dork / target | 22 | 1 | 26 | 14 | 27 | 4 | 27 | 23 | 15 | 3 | 16 | 12 |
| Doom Blade | board_wipe / distractor | 25 | 1 | 19 | 25 | 15 | 4 | 16 | 18 | 8 | 3 | 2 | 16 |
| Lightning Bolt | clone / control | 26 | 1 | 20 | 26 | 29 | 4 | 28 | 28 | 30 | 3 | 27 | 28 |
| Counterspell | board_wipe / control | 27 | 1 | 25 | 21 | 12 | 4 | 13 | 11 | 5 | 3 | 1 | 9 |
| Day of Judgment | board_wipe / target | 28 | 1 | 23 | 28 | 26 | 4 | 20 | 29 | 24 | 3 | 19 | 30 |
| Divination | clone / control (excluded) | -- | -- | -- | -- | 15 | 4 | 18 | 16 | 22 | 3 | 29 | 18 |
| Ponder | board_wipe / control (excluded) | -- | -- | -- | -- | 21 | 4 | 19 | 26 | 28 | 3 | 26 | 27 |

### expanded query &mdash; 'a clone effect (clone: enters the battlefield as a copy of a creature already in play)'

| Card | Role | effect-level fused | tfidf | e5 | bge | baseline +name fused | tfidf | e5 | bge | baseline -name fused | tfidf | e5 | bge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Clone | clone / target **TARGET** | 1 | 1 | 3 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 |
| Mirror Image | clone / target **TARGET** | 2 | 2 | 1 | 2 | 5 | 3 | 4 | 6 | 3 | 2 | 4 | 5 |
| Phantasmal Image | clone / target **TARGET** | 3 | 3 | 2 | 3 | 2 | 4 | 3 | 2 | 2 | 4 | 2 | 1 |
| Clever Impersonator | clone / target **TARGET** | 4 | 4 | 5 | 4 | 3 | 5 | 2 | 3 | 5 | 5 | 3 | 4 |
| Spark Double | clone / target **TARGET** | 5 | 5 | 4 | 5 | 4 | 2 | 5 | 4 | 4 | 3 | 5 | 3 |
| Cackling Counterpart | clone / target **TARGET** | 6 | 6 | 6 | 6 | 6 | 9 | 6 | 5 | 6 | 9 | 9 | 6 |
| Blasphemous Act | board_wipe / target | 7 | 10 | 10 | 7 | 11 | 8 | 9 | 24 | 14 | 8 | 16 | 17 |
| Damnation | board_wipe / target | 8 | 8 | 11 | 10 | 20 | 19 | 13 | 22 | 22 | 19 | 19 | 22 |
| Wrath of God | board_wipe / target | 8 | 8 | 11 | 10 | 18 | 19 | 12 | 17 | 24 | 19 | 20 | 25 |
| Toxic Deluge | board_wipe / target | 10 | 12 | 8 | 13 | 17 | 19 | 14 | 14 | 20 | 19 | 18 | 19 |
| Noble Hierarch | mana_dork / target | 11 | 13 | 9 | 9 | 12 | 10 | 16 | 15 | 15 | 10 | 17 | 14 |
| Fumigate | board_wipe / target | 12 | 11 | 7 | 25 | 15 | 18 | 8 | 20 | 19 | 18 | 14 | 18 |
| Giant Growth | board_wipe / control | 13 | 14 | 14 | 16 | 8 | 17 | 7 | 10 | 11 | 17 | 7 | 11 |
| Day of Judgment | board_wipe / target | 14 | 7 | 15 | 26 | 25 | 19 | 22 | 26 | 25 | 19 | 21 | 29 |
| Lightning Bolt | clone / control | 15 | 16 | 16 | 17 | 29 | 19 | 29 | 28 | 29 | 19 | 26 | 30 |
| Mana Reflection | mana_dork / distractor | 16 | 18 | 23 | 8 | 21 | 19 | 28 | 9 | 21 | 19 | 27 | 13 |
| Doubling Season | clone / distractor | 17 | 18 | 20 | 12 | 9 | 6 | 23 | 8 | 10 | 6 | 23 | 7 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 18 | 18 | 19 | 14 | 27 | 19 | 26 | 25 | 27 | 19 | 28 | 24 |
| Chromatic Lantern | mana_dork / distractor | 19 | 18 | 18 | 15 | 24 | 19 | 24 | 19 | 23 | 19 | 24 | 20 |
| Birds of Paradise | mana_dork / target | 20 | 17 | 13 | 18 | 22 | 16 | 20 | 21 | 16 | 16 | 15 | 15 |
| Doom Blade | board_wipe / distractor | 21 | 15 | 17 | 27 | 10 | 15 | 10 | 11 | 12 | 15 | 6 | 16 |
| Counterspell | board_wipe / control | 22 | 18 | 22 | 19 | 13 | 19 | 11 | 12 | 17 | 19 | 8 | 21 |
| Parallel Lives | clone / distractor | 23 | 18 | 24 | 23 | 7 | 7 | 15 | 7 | 13 | 7 | 22 | 12 |
| Elvish Mystic | mana_dork / target | 24 | 18 | 26 | 20 | 14 | 13 | 17 | 13 | 7 | 11 | 11 | 8 |
| Fyndhorn Elves | mana_dork / target | 24 | 18 | 26 | 20 | 16 | 11 | 19 | 16 | 7 | 11 | 11 | 8 |
| Llanowar Elves | mana_dork / target | 24 | 18 | 26 | 20 | 19 | 11 | 21 | 18 | 7 | 11 | 11 | 8 |
| Gilded Lotus | mana_dork / distractor | 27 | 18 | 21 | 28 | 30 | 19 | 30 | 30 | 28 | 19 | 25 | 28 |
| Avacyn's Pilgrim | mana_dork / target | 28 | 18 | 25 | 24 | 23 | 14 | 18 | 29 | 18 | 14 | 10 | 26 |
| Divination | clone / control (excluded) | -- | -- | -- | -- | 26 | 19 | 25 | 23 | 26 | 19 | 29 | 23 |
| Ponder | board_wipe / control (excluded) | -- | -- | -- | -- | 28 | 19 | 27 | 27 | 30 | 19 | 30 | 27 |

### glossed query &mdash; 'enters the battlefield as a copy of a creature already in play'

| Card | Role | effect-level fused | tfidf | e5 | bge | baseline +name fused | tfidf | e5 | bge | baseline -name fused | tfidf | e5 | bge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Clone | clone / target **TARGET** | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| Mirror Image | clone / target **TARGET** | 2 | 2 | 3 | 2 | 5 | 3 | 4 | 5 | 4 | 2 | 4 | 5 |
| Phantasmal Image | clone / target **TARGET** | 3 | 3 | 2 | 4 | 2 | 4 | 3 | 2 | 2 | 4 | 3 | 2 |
| Clever Impersonator | clone / target **TARGET** | 4 | 4 | 5 | 3 | 3 | 5 | 2 | 3 | 3 | 5 | 2 | 3 |
| Spark Double | clone / target **TARGET** | 5 | 5 | 4 | 5 | 4 | 2 | 5 | 4 | 5 | 3 | 5 | 4 |
| Cackling Counterpart | clone / target **TARGET** | 6 | 6 | 6 | 6 | 6 | 7 | 6 | 6 | 6 | 7 | 12 | 6 |
| Blasphemous Act | board_wipe / target | 7 | 10 | 10 | 7 | 14 | 6 | 14 | 20 | 12 | 6 | 16 | 13 |
| Toxic Deluge | board_wipe / target | 8 | 12 | 7 | 12 | 17 | 17 | 18 | 15 | 17 | 17 | 17 | 17 |
| Damnation | board_wipe / target | 9 | 8 | 11 | 9 | 21 | 17 | 20 | 21 | 20 | 17 | 21 | 22 |
| Wrath of God | board_wipe / target | 9 | 8 | 11 | 9 | 20 | 17 | 19 | 19 | 22 | 17 | 22 | 25 |
| Noble Hierarch | mana_dork / target | 11 | 13 | 9 | 8 | 13 | 8 | 17 | 14 | 13 | 8 | 15 | 15 |
| Day of Judgment | board_wipe / target | 12 | 7 | 13 | 17 | 25 | 17 | 21 | 28 | 23 | 17 | 19 | 29 |
| Fumigate | board_wipe / target | 13 | 11 | 8 | 20 | 18 | 16 | 16 | 22 | 18 | 16 | 18 | 18 |
| Giant Growth | board_wipe / control | 14 | 14 | 15 | 16 | 7 | 15 | 7 | 7 | 10 | 15 | 7 | 7 |
| Lightning Bolt | clone / control | 15 | 16 | 14 | 15 | 29 | 17 | 30 | 27 | 30 | 17 | 27 | 28 |
| Nykthos, Shrine to Nyx | mana_dork / distractor | 16 | 18 | 18 | 14 | 26 | 17 | 23 | 26 | 29 | 17 | 26 | 26 |
| Birds of Paradise | mana_dork / target | 17 | 17 | 16 | 18 | 16 | 14 | 15 | 18 | 14 | 14 | 14 | 12 |
| Doom Blade | board_wipe / distractor | 18 | 15 | 17 | 22 | 8 | 13 | 8 | 9 | 11 | 13 | 6 | 11 |
| Mana Reflection | mana_dork / distractor | 19 | 18 | 28 | 11 | 23 | 17 | 29 | 17 | 24 | 17 | 30 | 19 |
| Doubling Season | clone / distractor | 20 | 18 | 22 | 13 | 28 | 17 | 28 | 24 | 26 | 17 | 29 | 23 |
| Chromatic Lantern | mana_dork / distractor | 21 | 18 | 19 | 19 | 24 | 17 | 24 | 23 | 21 | 17 | 23 | 21 |
| Counterspell | board_wipe / control | 22 | 18 | 21 | 21 | 12 | 17 | 13 | 8 | 16 | 17 | 13 | 14 |
| Avacyn's Pilgrim | mana_dork / target | 23 | 18 | 23 | 24 | 15 | 12 | 10 | 25 | 15 | 12 | 11 | 20 |
| Gilded Lotus | mana_dork / distractor | 24 | 18 | 20 | 28 | 29 | 17 | 27 | 30 | 25 | 17 | 20 | 30 |
| Parallel Lives | clone / distractor | 25 | 18 | 27 | 23 | 22 | 17 | 26 | 16 | 27 | 17 | 28 | 24 |
| Elvish Mystic | mana_dork / target | 26 | 18 | 24 | 25 | 9 | 11 | 9 | 10 | 7 | 9 | 8 | 8 |
| Fyndhorn Elves | mana_dork / target | 26 | 18 | 24 | 25 | 11 | 9 | 12 | 12 | 7 | 9 | 8 | 8 |
| Llanowar Elves | mana_dork / target | 26 | 18 | 24 | 25 | 10 | 9 | 11 | 11 | 7 | 9 | 8 | 8 |
| Divination | clone / control (excluded) | -- | -- | -- | -- | 19 | 17 | 25 | 13 | 19 | 17 | 24 | 16 |
| Ponder | board_wipe / control (excluded) | -- | -- | -- | -- | 27 | 17 | 22 | 29 | 28 | 17 | 25 | 27 |

## Verdict

Fairest cell: `glossed` query (jargon removed) against `baseline -name` (name leakage removed). Mean rank of the cards each cluster should find, lower is better. A gap under 1.0 places on a 17-card corpus is called a tie.

| Cluster | Effect-level | Baseline -name | Gap | Verdict |
|---|---|---|---|---|
| mana_dork | 7.50 | 9.00 | +1.50 | **WIN** |
| board_wipe | 3.33 | 5.83 | +2.50 | **WIN** |
| clone | 3.50 | 3.50 | +0.00 | **TIE** |

### Per-card spread in the fairest cell

The mean can be carried by one card, which is the whole reason for widening the sample. Ranks are out of 30. Delta is baseline minus effect-level, so positive means effect-level placed the card higher.

**mana_dork** &mdash; cluster mean 7.50 vs 9.00 (WIN). Per card: 2 win / 4 tie / 0 loss. Mean delta +1.50, **median delta +0.0**, largest single card +8 (89% of all movement).

| Card | Effect-level | Baseline -name | Delta | Card verdict | vs cluster |
|---|---|---|---|---|---|
| Llanowar Elves | 8 | 8 | +0 | tie |  |
| Elvish Mystic | 8 | 8 | +0 | tie |  |
| Birds of Paradise | 3 | 3 | +0 | tie |  |
| Fyndhorn Elves | 8 | 8 | +0 | tie |  |
| Avacyn's Pilgrim | 12 | 20 | +8 | win |  |
| Noble Hierarch | 6 | 7 | +1 | win |  |

No card contradicts the cluster mean.

**board_wipe** &mdash; cluster mean 3.33 vs 5.83 (WIN). Per card: 4 win / 1 tie / 1 loss. Mean delta +2.50, **median delta +1.5**, largest single card +10 (48% of all movement).

| Card | Effect-level | Baseline -name | Delta | Card verdict | vs cluster |
|---|---|---|---|---|---|
| Wrath of God | 3 | 5 | +2 | win |  |
| Damnation | 3 | 4 | +1 | win |  |
| Day of Judgment | 1 | 1 | +0 | tie |  |
| Fumigate | 5 | 2 | -3 | loss | **CONTRADICTS** |
| Toxic Deluge | 2 | 12 | +10 | win |  |
| Blasphemous Act | 6 | 11 | +5 | win |  |

Contradicting the cluster mean: **Fumigate**.

**clone** &mdash; cluster mean 3.50 vs 3.50 (TIE). Per card: 1 win / 3 tie / 2 loss. Mean delta +0.00, **median delta +0.0**, largest single card +2 (50% of all movement).

| Card | Effect-level | Baseline -name | Delta | Card verdict | vs cluster |
|---|---|---|---|---|---|
| Clone | 1 | 1 | +0 | tie |  |
| Phantasmal Image | 3 | 2 | -1 | loss |  |
| Clever Impersonator | 4 | 3 | -1 | loss |  |
| Spark Double | 5 | 5 | +0 | tie |  |
| Mirror Image | 2 | 4 | +2 | win |  |
| Cackling Counterpart | 6 | 6 | +0 | tie |  |

No card contradicts the cluster mean.

### Do the three embedders agree with the fused verdict?

Mean rank of the cluster's target cards under each model alone, before fusion, in the fairest cell. A fused win that only one model supports is a weaker result than one all three produce.

| Cluster | Model | Effect-level | Baseline -name | Favours |
|---|---|---|---|---|
| mana_dork | tfidf | 5.00 | 10.33 | effect-level |
| mana_dork | e5 | 14.83 | 12.33 | baseline |
| mana_dork | bge | 7.33 | 9.00 | effect-level |
| mana_dork | **all three** | | | **2 of 3 favour effect-level, one favours the baseline** |
| board_wipe | tfidf | 3.50 | 3.50 | neither |
| board_wipe | e5 | 3.33 | 5.33 | effect-level |
| board_wipe | bge | 3.33 | 6.83 | effect-level |
| board_wipe | **all three** | | | **2 of 3 favour effect-level** |
| clone | tfidf | 3.50 | 3.67 | effect-level |
| clone | e5 | 3.50 | 4.50 | effect-level |
| clone | bge | 3.50 | 3.50 | neither |
| clone | **all three** | | | **2 of 3 favour effect-level** |

### Does the prior verdict hold? 17 cards vs 30

Mean target rank in the fairest cell. Ranks are out of 17 in the prior run and out of 30 here, so the absolute numbers are not comparable across columns; the verdict and the sign of the gap are.

| Cluster | 17-card EL | 17-card BL | 17-card verdict | 30-card EL | 30-card BL | 30-card verdict | Holds? |
|---|---|---|---|---|---|---|---|
| mana_dork | 4.00 | 6.00 | WIN | 7.50 | 9.00 | WIN | yes |
| board_wipe | 1.00 | 2.00 | WIN | 3.33 | 5.83 | WIN | yes |
| clone | 1.00 | 1.00 | TIE | 3.50 | 3.50 | TIE | yes |

### The requested 2x2

{raw jargon, translated} x {baseline with name, baseline without name}, with effect-level under both query variants. `translated` here is `expanded`, the real slang layer's actual output. Mean target rank, lower is better.

| Cluster | Query | Effect-level | Baseline +name | Baseline -name | Name leakage |
|---|---|---|---|---|---|
| mana_dork | jargon | 5.67 | 11.00 | 7.67 | -3.33 |
| mana_dork | expanded | 6.83 | 12.00 | 7.50 | -4.50 |
| board_wipe | jargon | 13.17 | 6.50 | 10.83 | +4.33 |
| board_wipe | expanded | 3.33 | 4.17 | 5.00 | +0.83 |
| clone | jargon | 3.50 | 4.33 | 6.17 | +1.83 |
| clone | expanded | 3.50 | 3.50 | 3.50 | +0.00 |

Name leakage is how many places the baseline loses when its own card name is removed from the document. A positive number is signal the baseline was taking from the name rather than from the card's text.

### Every cell of the grid, mean target rank

| Cluster | Query variant | Effect-level | Baseline +name | Baseline -name |
|---|---|---|---|---|
| mana_dork | jargon | 5.67 | 11.00 | 7.67 |
| mana_dork | expanded | 6.83 | 12.00 | 7.50 |
| mana_dork | glossed | 7.50 | 13.17 | 9.00 |
| board_wipe | jargon | 13.17 | 6.50 | 10.83 |
| board_wipe | expanded | 3.33 | 4.17 | 5.00 |
| board_wipe | glossed | 3.33 | 4.50 | 5.83 |
| clone | jargon | 3.50 | 4.33 | 6.17 |
| clone | expanded | 3.50 | 3.50 | 3.50 |
| clone | glossed | 3.50 | 3.50 | 3.50 |

Equal means in a row do not imply equal rankings. In the clone cluster under the translated queries all three pipelines average the same rank while ordering the cards differently, which is exactly why the per-card tables above are the primary evidence and these means are only a summary.

