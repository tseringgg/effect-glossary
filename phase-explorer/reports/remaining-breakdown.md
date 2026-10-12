# What is left in "Not yet organized" after the tentative layer

Investigation only: nothing is built, placed or changed; nothing is committed. Scripts: `src/probe_remaining.py`, `src/analyze_remaining_levers.py`. Data: `build/remaining_breakdown.json`, `build/remaining_cards.json`,
`build/remaining_reads.json`, `build/remaining_subheadings_*.json`. Seed 20261023 (declared before computing) drew the sample cards and the members read. **Measured** means a count from the build; **estimate** marks a judgment call.

## 1. Recount and reconciliation (measured)
* Pile still in "Not yet organized": **3,726**. Reconciliation: 27,590 placed + 1,867 tentative + 3,726 unorganized + 5,738 not cards = **38,921** (holds).
* Headline figures: precise 24,336 of 33,183 = 73.3%; with broad 27,590 = 83.1%; with tentative 29,457 = 88.8%.
  Bases: placed by an ability in an unflagged leaf of 5 or more, plus the keyword block, "No abilities" and the replacement groups; plus the 3,254 cards in groups broader than they look; plus the 1,867 not-yet-organized cards with an eligible ability in a tentative group. The archived view's 74.8% is on a different basis.
* The pile splits into **1,300 with no loose group** and **2,426 with a loose group that was not promoted**: exactly the expected counts.

## 2. Primary reason per card (fixed order) and the overlap (measured)

| # | Primary reason | Cards | Cards with this reason at all |
|---|---|---|---|
| 1 | no readable ability | 1,300 | 1,300 |
| 2 | dropped-condition hold | 1,342 | 1,342 |
| 3 | gap-test hold | 329 | 379 |
| 4 | only in a catch-all or less-common bucket | 359 | 391 |
| 5 | only in a held group | 396 | 427 |
| 6 | other | 0 | 0 |

Rules, in order: 1 = no usable ability, so no loose group. 2 = no eligible ability and at least one ability held for a possible dropped condition. 3 = no eligible ability and none held for a dropped condition (gap-test failures, no text).
4 = an eligible ability sits in a catch-all group or a "Less common effects" bucket. 5 = an eligible ability sits in a plain loose group that was not promoted. "Eligible" is the tentative layer's own rule. 4 and 5 are "any" tests, so a card in both is counted under 4.

**Cards with more than one reason: 113** (3% of the pile). Combinations: 2+3: 50, 2+4: 19, 2+5: 8, 3+4: 13, 3+5: 16, 4+5: 7.
Pairs: 2+3 50, 2+4 19, 3+5 16, 3+4 13, 2+5 8, 4+5 7.
The 1,300 cards with no readable ability have no other reason, so no fix to any other reason can move them. Reasons overlap so little that the levers below are close to independent; the exceptions are shown in section 6.

## 3. Evidence per reason

### 3.1 No readable ability (1,300)
By pile group: gap 1,231, not parsed 27, no effect to group 24, text may be lost 9, known parse mistake 8, too unusual 1. Of the gap cards: unread clause only 1,197; with an unknown trigger mode 20; with an unrecognized condition 8; with an unread effect 4; no fragment recorded 2.
1,341 distinct fragments in 610 families; **51 families cover 50%, 201 cover 80%, 400 cover 90%** of the 1,229 gap cards that have a fragment: a long tail. Top 10 fragments (sole-cause = the card's only fragment):

| Kind | Fragment (digits as N) | Cards | Sole-cause cards |
|---|---|---|---|
| unread | starting with you | 29 | 2 |
| unread | {tk}{tk} — N/N | 24 | 0 |
| unread | put a sticker on a nonland permanent you own | 14 | 0 |
| unread | draft a card from ~'s spellbook | 11 | 10 |
| unread | {tk}{tk}{tk} — N/N | 11 | 0 |
| unread | get {tk} | 9 | 1 |
| unread | add one mana of any type that land produced | 8 | 8 |
| unread | the next N damage that would be dealt to this creature this turn is de | 8 | 7 |
| unread | {tk}{tk}{tk}{tk}{tk} — N/N | 8 | 0 |
| unread | {tk}{tk}{tk}{tk} — N/N | 8 | 0 |

Top fragment families (leading words), cards: unread the next 62, unread for each 54, unread choose a 44, unread put a 34, unread n n 34, unread starting with 33, unread conjure a 29, unread this creature 19, unread vote for 19, unread as this 16. None is a single fixable construct ("{TK}{TK} - N/N" is a one-off card-art notation).

### 3.2 Dropped-condition holds (1,342 primary; 1,545 cards have at least one flagged ability, 1,606 abilities)
If a sub-shape were fixed (the flag lifted and the signature unchanged: **estimate**, a judgment call, because a corrected parse would add the condition to the signature, which could change the leaf):

| Sub-shape | Cards | Abilities | to an unflagged leaf | to a broad leaf | to a promoted group | Cards gaining a precise placement | Cards gaining broad or tentative only |
|---|---|---|---|---|---|---|---|
| activation-restriction-missing | 5 | 5 | 1 | 0 | 0 | 1 | 0 |
| branch-structural | 10 | 10 | 9 | 0 | 0 | 9 | 0 |
| compound | 51 | 51 | 29 | 12 | 3 | 29 | 15 |
| embedded-replacement | 116 | 120 | 51 | 28 | 6 | 50 | 33 |
| filter-targeting | 37 | 39 | 33 | 1 | 2 | 31 | 3 |
| negative | 58 | 58 | 28 | 12 | 10 | 28 | 22 |
| replacement-level | 50 | 50 | 41 | 0 | 1 | 41 | 1 |
| result-dependent | 276 | 278 | 167 | 40 | 16 | 167 | 54 |
| sequential-chain | 616 | 633 | 363 | 131 | 36 | 354 | 163 |
| static-level | 48 | 50 | 45 | 1 | 0 | 43 | 1 |
| trigger-intervening | 297 | 312 | 170 | 76 | 29 | 164 | 98 |

Shapes overlap (a card can carry flags of several shapes). Fixing every shape would return **1,294 cards**: 911 gain a precise placement, 286 a broad-leaf placement only, 97 a tentative placement only; 1,294 of the 1,342 primary-reason-2 cards would gain something. The 4 abilities in "activation-restriction-missing" and 34 in "embedded-replacement" are among the 217 flagged abilities that have no usable signature and so cannot be matched at all.
**Correction (2026-10-12):** the 44% I first quoted here was the false-positive rate of the old quick heuristic (4,889 candidates), not of the detector. The detector cleared those false positives (it flagged 27 of the 50 and cleared 23). A fresh 100-item read of the detector's own flags found 1 false flag (see `false-flags-and-promotions.md`), so this lever is a parser/representation fix, not a flag-lifting exercise.

### 3.3 Gap-test holds (329 primary)
Blockers: continuation gap 153, same-line gap 64, no ability text 112 (some cards have two blockers). Releasing the gap-test hold in the tentative layer returned **240 cards** when measured last round (they were already in promoted groups); the 112 no-text cards cannot be placed from text that is not there.

### 3.4 Catch-all groups and "Less common effects" buckets (391 cards, 359 primary)
110 sub-headings in the 2 catch-alls and 23 buckets. 33 have at least 5 eligible cards and are not "Other kinds": I read 8 members of each, text first (reads written before the names were shown): 28 coherent, 5 loose. The other 77 (including every "Other kinds") cannot meet the 5-eligible-card rule and were not read; their remaining cards number 205, of which 7 are also in a promotable sub-heading.
**30 sub-headings could be promoted as tentative groups under the existing rule, moving 177 cards** (2 of the 30 read as loose); 3 fail on the name ("Choose a target", "Other rule changes", "Move cards between zones, uncommon cases": mixed members, or a name that does not say what happens). "Give a player counters" would move 0 (its cards are already tentative).

| # | Family | Sub-heading | Cards | Eligible | Remaining that would move | Read | Name states effect | Promotable |
|---|---|---|---|---|---|---|---|---|
| 1 | Static: continuous | adds a card type | 8 | 8 | 7 | coherent | yes | **yes** |
| 2 | Static: continuous | adds a creature type | 9 | 9 | 9 | loose | yes | **yes** |
| 3 | Static: continuous | adds power by a count | 7 | 6 | 2 | coherent | yes | **yes** |
| 4 | Static: continuous | gives deathtouch | 8 | 8 | 7 | coherent | yes | **yes** |
| 5 | Static: continuous | gives double strike | 7 | 7 | 5 | coherent | yes | **yes** |
| 6 | Static: continuous | gives first strike | 8 | 5 | 5 | coherent | yes | **yes** |
| 7 | Static: continuous | gives flying | 5 | 5 | 5 | loose | yes | **yes** |
| 8 | Static: continuous | gives hexproof | 8 | 8 | 7 | coherent | yes | **yes** |
| 9 | Static: continuous | gives menace | 8 | 8 | 8 | coherent | yes | **yes** |
| 10 | Destroy | permanent | 9 | 5 | 4 | coherent | yes | **yes** |
| 11 | Attach | Attach, uncommon cases | 9 | 9 | 9 | coherent | yes | **yes** |
| 12 | Card draw | Connive | 8 | 8 | 8 | coherent | yes | **yes** |
| 13 | Card draw | Draw cards, uncommon cases | 6 | 5 | 5 | coherent | yes | **yes** |
| 14 | Choice / wrapper | Choose a target | 6 | 6 | 6 | loose | no | no |
| 15 | Combat | Goad a creature | 8 | 8 | 7 | coherent | yes | **yes** |
| 16 | Counters | Double counters | 7 | 6 | 6 | coherent | yes | **yes** |
| 17 | Counters | Give a player counters | 8 | 6 | 0 | coherent | yes | **yes** |
| 18 | Counters | Move counters | 8 | 7 | 4 | coherent | yes | **yes** |
| 19 | Game / player | Take an extra turn | 6 | 5 | 5 | coherent | yes | **yes** |
| 20 | Library | Reveal cards until a match | 8 | 6 | 6 | coherent | yes | **yes** |
| 21 | Life | Gain life | 6 | 6 | 6 | coherent | yes | **yes** |
| 22 | Life | Set a life total | 9 | 8 | 7 | coherent | yes | **yes** |
| 23 | Pump / grant | Double power and toughness | 6 | 5 | 5 | coherent | yes | **yes** |
| 24 | Static: cost change | Spells cost more | 9 | 7 | 6 | coherent | yes | **yes** |
| 25 | Static: other rule | Cast from hand without paying | 5 | 5 | 5 | coherent | yes | **yes** |
| 26 | Static: other rule | Has shroud | 5 | 5 | 5 | coherent | yes | **yes** |
| 27 | Static: other rule | Other rule changes | 7 | 6 | 6 | loose | no | no |
| 28 | Static: restriction | Can attack despite defender | 9 | 9 | 9 | coherent | yes | **yes** |
| 29 | Static: restriction | Can't enter the battlefield from a zone | 5 | 5 | 5 | coherent | yes | **yes** |
| 30 | Static: restriction | Doesn't untap | 9 | 7 | 7 | coherent | yes | **yes** |
| 31 | Static: restriction | Spells can't be cast | 9 | 9 | 9 | coherent | yes | **yes** |
| 32 | Tokens | Investigate | 8 | 5 | 5 | coherent | yes | **yes** |
| 33 | Zone change | Move cards between zones, uncommon cases | 8 | 8 | 6 | loose | no | no |

### 3.5 Held groups (427 cards, 396 primary)
50 plain groups are held. Cards moved = remaining cards with an eligible ability in the group; groups overlap, so do not add. D / G / T = abilities held for a dropped condition / a gap-test failure / with no text.

| Group | Why held | Cards | Eligible | Remaining eligible | Abilities held | My read | Lever that would release it |
|---|---|---|---|---|---|---|---|
| Give things a gained effect, other kinds of target | the name does not state the effect | 75 | 50 | 49 | D 15 / G 2 / T 8 | loose | a field, or a parser/text fix |
| A card with several modes | mixed or unreadable members | 46 | 41 | 41 | D 0 / G 0 / T 5 | incoherent | a field, or a parser/text fix |
| Continuous effect on this permanent | the name does not state the effect | 39 | 39 | 38 | D 0 / G 0 / T 0 | loose | rename |
| Deal damage, less common kinds | loose and a backoff residual | 46 | 33 | 31 | D 8 / G 4 / T 1 | loose | policy: allow loose residuals |
| Put counters, through a replacement effect, less common kinds | the name does not state the effect | 47 | 35 | 26 | D 8 / G 4 / T 0 | loose | a field, or a parser/text fix |
| Tap, less common kinds | loose and a backoff residual | 35 | 22 | 20 | D 5 / G 8 / T 0 | loose | policy: allow loose residuals |
| Make things bigger, other kinds of target | loose and a backoff residual | 23 | 20 | 20 | D 1 / G 1 / T 1 | loose | policy: allow loose residuals |
| Move cards to exile, less common kinds | loose and a backoff residual | 25 | 18 | 17 | D 3 / G 1 / T 3 | loose | policy: allow loose residuals |
| Give things a gained effect, less common kinds | the name does not state the effect | 14 | 13 | 13 | D 1 / G 0 / T 0 | loose | a field, or a parser/text fix |
| Attach to a creature | the name does not state the effect | 64 | 12 | 12 | D 0 / G 1 / T 55 | loose | a field, or a parser/text fix |
| Return things to their owners' hands, less common kinds | loose and a backoff residual | 17 | 12 | 12 | D 4 / G 0 / T 1 | loose | policy: allow loose residuals |
| Give a creature a different rule | the name does not state the effect | 18 | 12 | 11 | D 3 / G 4 / T 0 | coherent | rename |
| Give things haste, other kinds of target | loose and a backoff residual | 15 | 12 | 10 | D 2 / G 1 / T 0 | loose | policy: allow loose residuals |
| Give things a set power, other kinds of target | the name does not state the effect | 13 | 12 | 10 | D 1 / G 0 / T 0 | loose | a field, or a parser/text fix |
| Give things a gained ability, other kinds of target | loose and a backoff residual | 11 | 9 | 9 | D 1 / G 0 / T 1 | loose | policy: allow loose residuals |
| Create tokens, less common kinds | loose and a backoff residual | 10 | 9 | 8 | D 0 / G 1 / T 0 | loose | policy: allow loose residuals |
| Move cards to the graveyard, less common kinds | loose and a backoff residual | 11 | 10 | 8 | D 1 / G 0 / T 0 | loose | policy: allow loose residuals |
| Give things a gained ability | the name does not state the effect | 12 | 7 | 7 | D 2 / G 0 / T 3 | loose | a field, or a parser/text fix |
| Make things bigger or smaller by a counted amount, other kinds of target | loose and a backoff residual | 11 | 7 | 7 | D 3 / G 1 / T 0 | loose | policy: allow loose residuals |
| Cast a card (the zone is not recorded) | the name does not state the effect | 22 | 6 | 6 | D 12 / G 1 / T 3 | loose | a field, or a parser/text fix |
| Give things a different rule, other kinds of target | the name does not state the effect | 10 | 5 | 5 | D 3 / G 0 / T 2 | loose | rename |
| Look at the top cards of a library, cards go to the battlefield | fewer than 5 eligible cards | 16 | 4 | 4 | D 11 / G 1 / T 0 | coherent | policy: minimum 3 |
| Mill cards, by you | fewer than 5 eligible cards | 31 | 4 | 4 | D 23 / G 3 / T 1 | coherent | policy: minimum 3 |
| Draw cards | fewer than 5 eligible cards | 28 | 4 | 4 | D 22 / G 1 / T 1 | coherent | policy: minimum 3 |
| Surveil | fewer than 5 eligible cards | 12 | 4 | 4 | D 6 / G 3 / T 0 | coherent | policy: minimum 3 |
| Make a creature smaller, all of them | fewer than 5 eligible cards | 11 | 4 | 4 | D 7 / G 0 / T 0 | coherent | policy: minimum 3 |
| Give things double strike, other kinds of target | fewer than 5 eligible cards | 11 | 4 | 4 | D 5 / G 1 / T 1 | coherent | policy: minimum 3 |
| Destroy a land | fewer than 5 eligible cards | 13 | 3 | 3 | D 8 / G 2 / T 0 | coherent | policy: minimum 3 |
| Reveal the top cards of a library, less common kinds | loose and a backoff residual | 12 | 3 | 3 | D 9 / G 0 / T 0 | loose | policy, and then too few eligible |
| Put +1/+1 counters on this permanent | fewer than 5 eligible cards | 17 | 3 | 3 | D 12 / G 2 / T 0 | coherent | policy: minimum 3 |
| Give things first strike, other kinds of target | loose and a backoff residual | 11 | 3 | 3 | D 6 / G 0 / T 2 | loose | policy, and then too few eligible |
| Move cards from hand to the battlefield | fewer than 5 eligible cards | 10 | 3 | 3 | D 7 / G 0 / T 0 | coherent | policy: minimum 3 |
| Scry | fewer than 5 eligible cards | 14 | 4 | 3 | D 6 / G 4 / T 0 | coherent | policy: minimum 3 |
| Put +1/+1 counters on this permanent, at the beginning of a phase | fewer than 5 eligible cards | 16 | 3 | 3 | D 11 / G 2 / T 0 | coherent | policy: minimum 3 |
| Return a nonland permanent to its owner's hand | fewer than 5 eligible cards | 12 | 3 | 3 | D 8 / G 0 / T 1 | coherent | policy: minimum 3 |
| Cast cards from a graveyard, less common kinds | fewer than 5 eligible cards | 12 | 3 | 3 | D 9 / G 0 / T 0 | coherent | policy: minimum 3 |
| Make any target bigger | fewer than 5 eligible cards | 10 | 3 | 3 | D 6 / G 1 / T 0 | loose | policy: minimum 3 |
| Cast a card (the zone is not recorded), without paying its cost | fewer than 5 eligible cards | 22 | 2 | 2 | D 20 / G 0 / T 0 | loose | needs flags or tests released first |
| Give things indestructible | fewer than 5 eligible cards | 10 | 3 | 2 | D 4 / G 2 / T 1 | coherent | policy: minimum 3 |
| Add mana | fewer than 5 eligible cards | 14 | 3 | 2 | D 8 / G 3 / T 0 | coherent | policy: minimum 3 |
| Destroy an artifact | fewer than 5 eligible cards | 13 | 2 | 2 | D 9 / G 0 / T 2 | coherent | needs flags or tests released first |
| Look at the top cards of a library, cards go to hand | fewer than 5 eligible cards | 27 | 2 | 2 | D 25 / G 0 / T 0 | coherent | needs flags or tests released first |
| Draw cards, when a card moves between zones | fewer than 5 eligible cards | 24 | 2 | 1 | D 22 / G 0 / T 0 | loose | needs flags or tests released first |
| Put +1/+1 counters on this permanent, when a card moves between zones | fewer than 5 eligible cards | 12 | 2 | 1 | D 8 / G 2 / T 0 | coherent | needs flags or tests released first |
| Deal damage to the thing chosen before | fewer than 5 eligible cards | 11 | 2 | 1 | D 9 / G 0 / T 0 | loose | needs flags or tests released first |
| Create creature tokens, at the beginning of a phase | fewer than 5 eligible cards | 13 | 1 | 1 | D 11 / G 1 / T 0 | coherent | needs flags or tests released first |
| Search a library for a card, put it in hand | fewer than 5 eligible cards | 18 | 2 | 1 | D 16 / G 0 / T 0 | coherent | needs flags or tests released first |
| Put +1/+1 counters on this permanent, through a replacement effect | fewer than 5 eligible cards | 39 | 0 | 0 | D 34 / G 5 / T 0 | coherent | needs flags or tests released first |
| Triggers an extra time | mixed or unreadable members | 16 | 0 | 0 | D 16 / G 0 / T 0 | incoherent | parser |
| Put lore counters on this permanent | fewer than 5 eligible cards | 17 | 0 | 0 | D 0 / G 17 / T 0 | coherent | needs flags or tests released first |

Totals by lever (cards, de-duplicated): rename only 54; allow loose backoff residuals 142; lower the eligible minimum to 3 52; a field or a parser/text fix 164.
"A card with several modes" is a wrapper group: every member shows only the trigger clause, so there is nothing to release; its cards depend on their mode abilities. "Attach to a creature" is held because 51 of 64 members have no ability text (the Equip line comes from a keyword), which is a text-source fix, not a rename.

### 3.6 Ten sample cards per reason (name, ability text, blocking reason)

**1 no readable ability**

| Card | Ability text | Blocking reason |
|---|---|---|
| Tivit, Seller of Secrets | Flying, ward {3} / Council's dilemma — Whenever Tivit enters or deals combat damage to a player, starting with you, each player votes for evidence or  | Parsed, but with a gap; not understood: unread: for each bribery vote, create a treasure token; unread: for each evidence vote, investigate |
| Swarm, Being of Bees | Flash / Flying / Mayhem {B} (You may cast this card from your graveyard for {B} if you discarded it this turn. Timing rules still apply.) | Not parsed yet |
| Will, Scion of Peace | Vigilance / {T}: Spells you cast this turn that are white and/or blue cost {X} less to cast, where X is the amount of life you gained this turn. Activ | Parsed, but with a gap; not understood: unread: spells you cast this turn that are white and/or blue cost {x} less to cast, where x is the amount of l |
| Speedbrood Stalker | Flying, Lifelink / When this creature enters, choose target opponent. Secretly choose a creature or planeswalker that player controls. That player sac | Parsed, but with a gap; not understood: unread: secretly choose a creature or planeswalker that player controls |
| Pandora's Box | {3}, {T}: Choose a random summon card from all players' decks. For each player, flip a coin. If the flip ends up heads, put a token creature into play | Parsed, but with a gap; not understood: unread: choose a random summon card from all players' decks. for each player, flip a coin. if the flip ends up |
| Veiling Oddity | Suspend 4—{1}{U} (Rather than cast this card from your hand, you may pay {1}{U} and exile it with four time counters on it. At the beginning of your u | Parsed, but with a gap; not understood: trigger: when the last time counter is removed from this card while it's exiled, creatures can't be blocked th |
| Fathom Trawl | Reveal cards from the top of your library until you reveal three nonland cards. Put the nonland cards revealed this way into your hand, then put the r | Parsed, but with a gap; not understood: unread: reveal cards from the top of your library until you reveal three nonland cards |
| Mentor of Evos Isle | Flying / When this creature enters, choose a creature card in your hand. It perpetually gains flying. | Parsed, but with a gap; not understood: unread: choose a creature card in your hand |
| Transguild Courier | Transguild Courier is all colors. | Parsed, but with a gap; not understood: unread: ~ is all colors |
| Snowblind | Enchant creature / Enchanted creature gets -X/-Y. If that creature is attacking, X is the number of snow lands defending player controls. Otherwise, X | Parsed, but with a gap; not understood: unread: enchanted creature gets -x/-y. if that creature is attacking, x is the number of snow lands defending  |

**2 dropped-condition hold**

| Card | Ability text | Blocking reason |
|---|---|---|
| Fistful of Force | Target creature gets +2/+2 until end of turn. Clash with an opponent. If you win, that creature gets an additional +2/+2 and gains trample until end o | held for a possible dropped condition (result-dependent) |
| Cosmic Intervention | If a permanent you control would be put into a graveyard from the battlefield this turn, exile it instead. Return it to the battlefield under its owne | held for a possible dropped condition (embedded-replacement) |
| Spiritual Sanctuary | At the beginning of each player's upkeep, if that player controls a Plains, they gain 1 life. | held for a possible dropped condition (trigger-intervening) |
| Traumatic Revelation | Target opponent reveals their hand. You may choose a creature or battle card from it. If you do, that player discards that card. If you don't, incubat | held for a possible dropped condition (result-dependent) |
| Visions of Beyond | Draw a card. If a graveyard has twenty or more cards in it, draw three cards instead. | held for a possible dropped condition (sequential-chain) |
| Rogue Skycaptain | At the beginning of your upkeep, put a wage counter on this creature. You may pay {2} for each wage counter on it. If you don't, remove all wage count | held for a possible dropped condition (negative) |
| Doom Foretold | At the beginning of each player's upkeep, that player sacrifices a nonland, nontoken permanent of their choice. If that player can't, they discard a c | held for a possible dropped condition (result-dependent) |
| Prismatic Ending | Converge — Exile target nonland permanent if its mana value is less than or equal to the number of colors of mana spent to cast this spell. | held for a possible dropped condition (filter-targeting) |
| Fblthp, the Lost | When Fblthp enters, draw a card. If it entered from your library or was cast from your library, draw two cards instead. | held for a possible dropped condition (sequential-chain) |
| Auratouched Mage | When this creature enters, search your library for an Aura card that could enchant it. If this creature is still on the battlefield, put that Aura car | held for a possible dropped condition (sequential-chain) |

**3 gap-test hold**

| Card | Ability text | Blocking reason |
|---|---|---|
| Mammoth Harness | Enchanted creature loses flying. | gap-card test failed: gap_card_continuation_gap |
| Knight Rampager | When this creature dies, it deals 4 damage to target opponent chosen at random. | gap-card test failed: gap_card_continuation_gap |
| Combine Guildmage | {1}{U}, {T}: Move a +1/+1 counter from target creature you control onto another target creature you control. | gap-card test failed: gap_card_continuation_gap |
| Argivian Welcome | Destroy up to one target creature with power 4 or greater. | gap-card test failed: gap_card_continuation_gap |
| Choreographed Sparks | (none) | no ability text |
| Highway Reaver | (none) | no ability text |
| Blade of Shared Souls | (none) | no ability text |
| Champion's Helm | (none) | no ability text |
| Taste for Mayhem | Enchanted creature gets +2/+0. | gap-card test failed: gap_card_same_line_gap |
| Circle of Solace | As this enchantment enters, choose a creature type. | gap-card test failed: gap_card_continuation_gap |

**4 only in a catch-all or less-common bucket**

| Card | Ability text | Blocking reason |
|---|---|---|
| Baffling Defenses | Target creature's base power perpetually becomes 0. | in the catch-all / bucket 'Less common effects, by kind' |
| Paradox Zone | At the beginning of your end step, double the number of growth counters on this enchantment. Then create a 0/0 green and blue Fractal creature token.  | in the catch-all / bucket 'Less common effects, by kind' |
| North Wind Avatar | When this creature enters, if you cast it, you may put a card you own from outside the game into your hand. | in the catch-all / bucket 'Less common effects, by kind' |
| Hand to Hand | During combat, players can't cast instant spells or activate abilities that aren't mana abilities. | in the catch-all / bucket 'Less common effects, by kind' |
| Mana Vapors | Lands target player controls don't untap during their next untap step. | in the catch-all / bucket 'Less common effects, by kind' |
| Glorious End | At the beginning of your next end step, you lose the game. | in the catch-all / bucket 'Less common effects, by kind' |
| Cataclysmic Gearhulk | When this creature enters, each player chooses an artifact, a creature, an enchantment, and a planeswalker from among the nonland permanents they cont | in the catch-all / bucket 'Less common effects, by kind' |
| Bedevil | Destroy target artifact, creature, or planeswalker. | in the catch-all / bucket 'Destroy, less common kinds' |
| Surveillance Monitor | When this creature enters, you may collect evidence 4. | in the catch-all / bucket 'Less common effects, by kind' |
| Redirect | You may choose new targets for target spell. | in the catch-all / bucket 'Less common effects, by kind' |

**5 only in a held group**

| Card | Ability text | Blocking reason |
|---|---|---|
| By Elspeth's Command | At the beginning of combat on your turn | in the held group 'A card with several modes': mixed or unreadable members |
| Bloodrage Alpha | When this creature enters the battlefield | in the held group 'A card with several modes': mixed or unreadable members |
| Titanium Man | Whenever Titanium Man attacks | in the held group 'A card with several modes': mixed or unreadable members |
| Dralnu's Pet | If this creature was kicked, it enters with flying and with X +1/+1 counters on it, where X is the discarded card's mana value. | in the held group 'Put counters, through a replacement effect, less common kinds': the name does not state the effect |
| Windcrag Siege | As this enchantment enters | in the held group 'A card with several modes': mixed or unreadable members |
| Search for Dagger | Whenever your commander enters or attacks, look at the top six cards of your library. You may reveal a legendary creature card from among them and put | in the held group 'Look at the top cards of a library, cards go to hand': fewer than 5 eligible cards |
| Tactical Advantage | Target blocking or blocked creature you control gets +2/+2 until end of turn. | in the held group 'Make things bigger, other kinds of target': loose and a backoff residual |
| Lurking Jackals | When an opponent has 10 or less life, if this permanent is an enchantment, it becomes a 3/2 Jackal creature. | in the held group 'Give things a set power, other kinds of target': the name does not state the effect |
| Etched Host Doombringer | When this creature enters | in the held group 'A card with several modes': mixed or unreadable members |
| Wall of Stolen Identity | You may have ~ enter as a copy of any creature on the battlefield, except it's a ~ in addition to its other types and has defender. When you do, tap t | in the held group 'Continuous effect on this permanent': the name does not state the effect |

## 4. Popularity (measured; rank from the Scryfall oracle data)

| Primary reason | Cards | Top 1,000 | Top 3,000 | Top 10,000 | No rank |
|---|---|---|---|---|---|
| 1 no readable ability | 1300 | 16 | 80 | 324 | 153 |
| 2 dropped-condition hold | 1342 | 25 | 106 | 393 | 56 |
| 3 gap-test hold | 329 | 9 | 24 | 91 | 58 |
| 4 only in a catch-all or less-common bucket | 359 | 11 | 37 | 128 | 13 |
| 5 only in a held group | 396 | 1 | 21 | 102 | 38 |
| all remaining | 3726 | 62 | 268 | 1038 | 318 |

The dropped-condition holds hold the most popular cards in absolute terms (106 in the top 3,000), then no readable ability (80). Relative to size, the catch-all and bucket cards are the most popular (about 10% in the top 3,000, against 5-8% elsewhere).

## 5. Typing errors (the Second Sunrise kind)
* No Bounce-typed ability records a destination (all 1,241 have an empty one), so a return to the battlefield or the command zone is typed as a return to hand. A text audit (investigation only) finds **8** such abilities: 7 on placed cards (precise or broad) and 1 tentative: Parallax Tide, Parallax Wave, Gerrard's Hourglass Pendant, Moira, Urborg Haunt, Leadership Vacuum, Squirming Emergence, Faith's Reward (placed) and Second Sunrise (tentative). I read all 8: every one is a return to the battlefield or the command zone, none to hand.
* Bounce-typed abilities with a graveyard source: 380 (112 precise, 255 broad-only, 13 tentative). I read 10 drawn at random (seed 20261028): all 10 are genuine returns to hand. So the graveyard-source members are right; the mistyped ones are the 8 above, which the parse fields cannot tell apart from a real bounce (only the text can).
* Other types (heuristic: the ability text lacks every verb stem of its type, or a ChangeZone destination is not named in the text): 43 abilities in 7 of the 22 effect types checked lack their stem (19 are the keyword action "support N" typed as put-counters, the rest are Class level-up lines, airbend and "top of their library" wordings), and 25 ChangeZone abilities do not name their destination (13 "airbend" lines, 10 "owners' libraries" lines, 2 Class lines). All benign. **No other systematic typing problem found**; the check only catches gross mismatches, so this is an estimate of coverage, not a proof.
* Scale: 8 abilities of about 1,240 Bounce abilities; 7 placed cards of about 27,590 (0.03%) look mistyped. It is a correctness issue, not a reach lever.

## 6. Levers, ranked by cards moved per effort
Cards are remaining cards (of 3,726). The four rule or naming changes (ranks 1-4) overlap by a few cards: together they move **422**, not 425. Adding the dropped-condition lever gives **1,707** (the two overlap by 9). Do not add the other levers' numbers.

| Rank | Lever | Cards moved | Effort | Basis | Leaves behind |
|---|---|---|---|---|---|
| 1 | Promote the 30 qualifying catch-all sub-headings as tentative groups (existing rule, new names) | 177 | low: names plus a hand check | measured sizes; 2 loose reads are a judgment | the 77 sub-headings that cannot qualify (205 cards) |
| 2 | Allow loose-and-residual groups (drop that hold) | 142 | low: one flag, but it undoes a deliberate quality choice | measured; the choice is a judgment | looser tentative groups |
| 3 | Rename the 3 groups whose name says nothing | 54 | low | measured; the wording is a judgment | the mixed groups |
| 4 | Lower the eligible-card minimum from 5 to 3 | 52 | low, but it weakens a rule that mirrors the main tree's | measured | |
| 5 | Dropped-condition holds: lift false flags, fix real drops, by sub-shape (sequential-chain 616 cards, trigger-intervening 297, result-dependent 276 first) | up to 1,294 (911 precise, 286 broad, 97 tentative) | high: parser work (the detector's flags are almost all real: 84 of 100 read as real drops, 1 false) | **estimate**: assumes the signature is unchanged | about 2,000 cards, including the real drops |
| 6 | Field or parser/text fixes for the mixed held groups | 164 | medium to high | measured sizes; whether a field can split them is a judgment | |
| 7 | Release gap-test failures | 240 | low, but held on purpose | measured last round | continuation and same-line gaps stay unplaced |
| 8 | Close the top gap-fragment families (610 families, a long tail) | at most about 340 for the top 10 families (overlapping); a read fragment is not yet a placement | high | **estimate** | the long tail |
| 9 | Fix the 8 mistyped bounces | 0 reach (7 placed cards become correct) | medium | measured | |

With tentative would be 90.0% after ranks 1-4 (measured sizes, 29,879 of 33,183), and the precise figure would be 76.1% if every dropped-condition fix landed as estimated (**estimate**).
What would stay behind after ranks 1-4 and 7: the 1,300 unreadable cards, most of the dropped-condition holds, and the mixed groups: about 3,064 cards.

## Hash check
The 519-file hash list taken before this round was re-checked at the end of the round: see the final message.
