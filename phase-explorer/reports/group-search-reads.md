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

