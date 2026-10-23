# Group search: the fixed query sets and my reads

Both sets were fixed before the reads (`group-search-baseline-queries.json`, `group-search-fresh-queries.json`). A read is "sensible" when a group in the top 5 (or at rank 1) is what a Magic player means by the query, judged from the group's name and its most popular members. **These are my reads, written by the same model that wrote the search: they are not independent of the generator, and 30 and 20 queries cannot show a rate.** M = a marginal call, counted as sensible.

## Baseline set (30)

| query | rank 1 | top 5 | rank 1 |
|---|---|---|---|
| wrath | Destroy all creatures (restriction varies) | yes | yes |
| counterspell | Counter a spell (card) | yes | yes |
| tutor | Search your library for a card and put it into your hand (then move a  | yes | yes |
| fog | Fog: prevent all combat damage | yes | yes |
| stax | (no group) | no | no |
| looting | Repeatable: loot | yes | yes |
| flying | Flying | yes | yes |
| deathtouch | Deathtouch | yes | yes |
| cycling | Cycling | yes | yes |
| landwalk | Landwalk | yes | yes |
| ward | Ward | yes | yes |
| first strike | First strike | yes | yes |
| draw cards | Draw cards — who draws isn't recorded | yes | yes |
| extra turn | Extra turn | yes | yes |
| search library | Search your library for a basic land and put it onto the battlefield ( | yes | M |
| copy spell | Copies spell | yes | yes |
| discard | Discard | yes | yes |
| untap lands | Untap a land | yes | M |
| sacrific | Sacrifice this permanent | yes | M |
| regener | Regenerate this permanent | yes | yes |
| tok | Create creature tokens | yes | yes |
| graveyard | Return a creature card from your graveyard to its owner's hand — “all” | yes | yes |
| indestruct | Indestructible | yes | yes |
| exil | Exile it — what it applies to isn't recorded | yes | no |
| destory | Destroy a creature (restriction varies) [did you mean destroy] | yes | yes |
| sacrifise | Sacrifice this permanent [did you mean sacrifice] | yes | M |
| lifegian | Gain life [did you mean lifegain] | yes | yes |
| tokns | Create creature tokens [did you mean tokens] | yes | yes |
| graveyrad | Return a creature card from your graveyard to its owner's hand — “all” | yes | yes |
| deathtoch | Deathtouch [did you mean deathtouch] | yes | yes |

**29 of 30 sensible in the top 5; 28 of 30 at rank 1 (24 if the M calls are dropped).**

## Fresh set (20; seed 20262901 for the 12 drawn terms; wraith and rump pass by not being corrected and by finding no wipe/ramp group, as set beforehand)

| query | rank 1 | top 5 | rank 1 |
|---|---|---|---|
| draft from spellbook | You spend mana as any color | no | no |
| extra blockers | This permanent extra blockers | yes | yes |
| +1/+1 counters | Put +1/+1 counters on this permanent | yes | no |
| hexproof indestructible | A permanent gains hexproof, indestructible until end of turn | no | no |
| search for plains | Search your library for a Plains card | yes | yes |
| discover | Discover | yes | yes |
| magecraft | (no group) | no | no |
| monarch | Become the monarch | yes | yes |
| sacrifice a creature to pump | (no group) | no | no |
| tap creatures for mana | (no group) | no | no |
| give double strike | Gives double strike | yes | yes |
| stun counter | Tap a creature, then put stun counters on it | yes | yes |
| wrath | Destroy all creatures (restriction varies) | yes | yes |
| wraith | (no group) | yes | yes |
| ramp | Search your library for a basic land and put it onto the battlefield ( | yes | yes |
| rump | (no group) | yes | yes |
| reanimtae | Return a creature card from your graveyard onto the battlefield [did y | yes | yes |
| counterspel | Counter a spell (card) | yes | yes |
| lifelnik | Lifelink [did you mean lifelink] | yes | yes |
| mana dorc | Creature that makes mana again and again [did you mean mana dork] | yes | yes |

**15 of 20 sensible in the top 5; 14 of 20 at rank 1 (14 if the M calls are dropped).**


# 2026-10-20: the alias round (hand aliases with spellings, drafted aliases, "most words", three new hand groups)

Re-run of the 50 fixed searches above: no search that was sensible before is now wrong. Four top-5 lists changed: "stax" (none, now five effect groups, partial alias), "sacrifice a creature to pump" (none, now "Sacrifice a creature": a fresh-set miss became a hit), "give double strike" (same top 3, two keyword groups added below) and "tap creatures for mana" (none before; now "Mana rocks: artifacts that tap for mana" first, which is **not** what was meant: a wrong result where there was none). Baseline set 29 of 30 (top 5) and 28 at rank 1, unchanged; first fresh set 15 to **16** of 20 (top 5) and 14 to **15** at rank 1; 50 searches together 44 to **45** (top 5) and 42 to **43** (rank 1).

Fresh set 2, seed 20263101 (`group-search-fresh2-queries.json`; 12 cards drawn, the term written from the card text after the index was built and before any of these queries was run; 4 near-collisions that must not be corrected into the new aliases; 4 typos of new aliases). My reads, not independent of the generator; 20 queries cannot show a rate.

| query | rank 1 | top 5 | rank 1 |
|---|---|---|---|
| riot | Riot | yes | yes |
| flicker | Exiles a permanent and returns it to the battlefield (blink, flicker) | yes | yes |
| give first strike | Gives first strike | yes | yes |
| lifegain and draw | (no group) | no | no |
| edict | Removal: sacrifice | yes | yes |
| gainland | (no group) | no | no |
| create drake tokens | Create Drake tokens with flying | yes | yes |
| ooze tokens | Create Ooze tokens | yes | yes |
| regeneration | (no group) | no | no |
| wheel | Each player discards, then draw | yes | yes |
| opponent sacrifices a creature | Each opponent sacrifices a creature | yes | yes |
| exile removal | Exile a creature | yes | yes |
| blind | (no group) | yes | yes |
| stack | Ends the turn or takes a spell off the stack | yes | yes |
| cantor | Conjure a card (to the graveyard) | yes | yes |
| rack | (no group) | yes | yes |
| blnik | Exiles a permanent and returns it to the battlefield (blink, flicker)  | yes | yes |
| cantrpi | Cantrips: draws a card as it resolves or enters [did you mean cantrip] | yes | yes |
| mana rokc | Mana rocks: artifacts that tap for mana [did you mean mana rock] | yes | yes |
| thoughtsiez | An opponent reveals their hand, then target player discards [did you m | yes | yes |

**17 of 20 sensible in the top 5 (85%) and 17 of 20 at rank 1 (85%).** Counting the four near-collisions as misses (they pass by not being corrected and returning only groups that contain the typed word, as set beforehand) it is 13 of 20 (65%). Misses: "lifegain and draw" (a hand alias and a name word in one phrase: every word must match one kind), "gainland" (no group), "regeneration" (no stem rule joins -ion to -e: "regenerate" groups are not found).

