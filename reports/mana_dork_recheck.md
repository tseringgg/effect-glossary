# Mana dork, re-measured after the slang gloss cap

Only this cluster's query changed. The board-wipe query matched one term before and after the cap, and the clone query matches nothing, so neither moves. Ranks are out of 30, lower is better.

## Cluster means

| Query family | Phase | Effect-level | Baseline +name | Baseline -name |
|---|---|---|---|---|
| expanded | before (2 glosses) | 6.83 | 12.00 | 7.50 |
| expanded | after (1 gloss) | 6.17 | 11.17 | 7.33 |
| glossed | before (2 glosses) | 7.50 | 13.17 | 9.00 |
| glossed | after (1 gloss) | 6.17 | 12.00 | 6.50 |

- **expanded**, effect-level: 6.83 -> 6.17 (+0.67)
- **glossed**, effect-level: 7.50 -> 6.17 (+1.33)

## Verdict in the fair cell (glossed query vs baseline -name)

| Phase | Effect-level | Baseline -name | Gap | Mean verdict | Per card | Median delta |
|---|---|---|---|---|---|---|
| before (2 glosses) | 7.50 | 9.00 | +1.50 | **WIN** | 2W / 4T / 0L | +0.0 |
| after (1 gloss) | 6.17 | 6.50 | +0.33 | **TIE** | 4W / 1T / 1L | +2.0 |

The mean and the spread disagree after the fix, so read both. Effect-level improves on every one of the six cards. The baseline's larger mean gain comes almost entirely from a single card, so the mean closes to a tie while the median card still favours effect-level by two places.

## expanded query

- before (2 glosses): `a mana dork (ramp: increases available mana, usually by putting extra lands into play or adding mana; mana dork: a creature that taps to produce mana, accelerating you ahead)`
- after (1 gloss): `a mana dork (mana dork: a creature that taps to produce mana, accelerating you ahead)`

### expanded &mdash; effect-level

| Card | before fused | tfidf | e5 | bge | after fused | tfidf | e5 | bge | fused delta |
|---|---|---|---|---|---|---|---|---|---|
| Llanowar Elves | 8 | 4 | 20 | 7 | 8 | 4 | 16 | 5 | +0 |
| Elvish Mystic | 8 | 4 | 20 | 7 | 8 | 4 | 16 | 5 | +0 |
| Birds of Paradise | 1 | 1 | 6 | 2 | 1 | 1 | 2 | 2 | +0 |
| Fyndhorn Elves | 8 | 4 | 20 | 7 | 8 | 4 | 16 | 5 | +0 |
| Avacyn's Pilgrim | 11 | 7 | 14 | 14 | 7 | 7 | 10 | 9 | +4 |
| Noble Hierarch | 5 | 11 | 4 | 5 | 5 | 9 | 5 | 8 | +0 |

### expanded &mdash; baseline +name

| Card | before fused | tfidf | e5 | bge | after fused | tfidf | e5 | bge | fused delta |
|---|---|---|---|---|---|---|---|---|---|
| Llanowar Elves | 15 | 12 | 20 | 11 | 17 | 12 | 24 | 13 | -2 |
| Elvish Mystic | 8 | 14 | 5 | 9 | 3 | 14 | 4 | 5 | +5 |
| Birds of Paradise | 2 | 3 | 6 | 5 | 2 | 3 | 5 | 3 | +0 |
| Fyndhorn Elves | 12 | 12 | 15 | 8 | 12 | 12 | 15 | 9 | +0 |
| Avacyn's Pilgrim | 26 | 16 | 29 | 25 | 23 | 16 | 28 | 16 | +3 |
| Noble Hierarch | 9 | 10 | 19 | 1 | 10 | 10 | 22 | 2 | -1 |

### expanded &mdash; baseline -name

| Card | before fused | tfidf | e5 | bge | after fused | tfidf | e5 | bge | fused delta |
|---|---|---|---|---|---|---|---|---|---|
| Llanowar Elves | 5 | 11 | 6 | 7 | 7 | 11 | 10 | 7 | -2 |
| Elvish Mystic | 5 | 11 | 6 | 7 | 7 | 11 | 10 | 7 | -2 |
| Birds of Paradise | 3 | 4 | 1 | 4 | 2 | 4 | 1 | 2 | +1 |
| Fyndhorn Elves | 5 | 11 | 6 | 7 | 7 | 11 | 10 | 7 | -2 |
| Avacyn's Pilgrim | 16 | 15 | 15 | 17 | 10 | 15 | 9 | 10 | +6 |
| Noble Hierarch | 11 | 10 | 20 | 5 | 11 | 10 | 22 | 5 | +0 |

## glossed query

- before (2 glosses): `increases available mana, usually by putting extra lands into play or adding mana; a creature that taps to produce mana, accelerating you ahead`
- after (1 gloss): `a creature that taps to produce mana, accelerating you ahead`

### glossed &mdash; effect-level

| Card | before fused | tfidf | e5 | bge | after fused | tfidf | e5 | bge | fused delta |
|---|---|---|---|---|---|---|---|---|---|
| Llanowar Elves | 8 | 4 | 20 | 7 | 7 | 4 | 14 | 5 | +1 |
| Elvish Mystic | 8 | 4 | 20 | 7 | 7 | 4 | 14 | 5 | +1 |
| Birds of Paradise | 3 | 1 | 7 | 6 | 1 | 1 | 5 | 3 | +2 |
| Fyndhorn Elves | 8 | 4 | 20 | 7 | 7 | 4 | 14 | 5 | +1 |
| Avacyn's Pilgrim | 12 | 7 | 18 | 12 | 11 | 7 | 11 | 10 | +1 |
| Noble Hierarch | 6 | 10 | 4 | 5 | 4 | 9 | 1 | 8 | +2 |

### glossed &mdash; baseline +name

| Card | before fused | tfidf | e5 | bge | after fused | tfidf | e5 | bge | fused delta |
|---|---|---|---|---|---|---|---|---|---|
| Llanowar Elves | 16 | 12 | 19 | 12 | 22 | 12 | 22 | 18 | -6 |
| Elvish Mystic | 13 | 14 | 12 | 13 | 11 | 14 | 5 | 13 | +2 |
| Birds of Paradise | 3 | 3 | 9 | 6 | 2 | 3 | 6 | 4 | +1 |
| Fyndhorn Elves | 15 | 12 | 20 | 10 | 17 | 12 | 16 | 17 | -2 |
| Avacyn's Pilgrim | 24 | 16 | 29 | 21 | 16 | 16 | 18 | 10 | +8 |
| Noble Hierarch | 8 | 10 | 16 | 5 | 4 | 10 | 14 | 3 | +4 |

### glossed &mdash; baseline -name

| Card | before fused | tfidf | e5 | bge | after fused | tfidf | e5 | bge | fused delta |
|---|---|---|---|---|---|---|---|---|---|
| Llanowar Elves | 8 | 11 | 13 | 10 | 9 | 11 | 13 | 8 | -1 |
| Elvish Mystic | 8 | 11 | 13 | 10 | 9 | 11 | 13 | 8 | -1 |
| Birds of Paradise | 3 | 4 | 2 | 3 | 1 | 1 | 1 | 2 | +2 |
| Fyndhorn Elves | 8 | 11 | 13 | 10 | 9 | 11 | 13 | 8 | -1 |
| Avacyn's Pilgrim | 20 | 15 | 22 | 17 | 5 | 15 | 8 | 4 | +15 |
| Noble Hierarch | 7 | 10 | 11 | 4 | 6 | 10 | 12 | 6 | +1 |

