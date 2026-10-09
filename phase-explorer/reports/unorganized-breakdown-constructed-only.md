# "Not yet organized": breakdown by cause

Investigation only (`src/analyze_unorganized_breakdown.py`, seed 20261100). Nothing was built, placed or changed; new files only: `build/unorganized_breakdown.json` and this report. Every figure is **measured** from the current build unless it says **estimate**.

**This version leaves out the 1,149 pile cards that are not meant for constructed play** (gap 1058, text_may_be_lost 45, too_unusual 43, not_parsed 2, no_effect_to_group 1); every count below is of the remaining 5,760 cards. The headline figures in section 1 still describe the whole pool.

## 1. Recount

- Universe 38,921 = 26,589 placed in a group (21,637 precise-grouped + 3,131 only in broad groups + 1,261 keyword block + 351 no abilities + 209 replacement) + **6,909 not yet organized** + 4,274 not cards. Reconciles: **True**.
- Groups in the pile today: gap 4,618, too_unusual 1,196, text_may_be_lost 1,033, no_effect_to_group 27, not_parsed 27, known_parse_mistake 8.
- Headline: **23,458 of 34,647 = 67.7%** (basis: placed by an ability in an unflagged leaf of 5 or more, plus the keyword block, “No abilities” and the replacement groups, out of the 34,647 in-scope cards).
- With broad groups: **26,589 = 76.7%** (basis: the headline plus the 3,131 cards whose abilities sit only in groups broader than they look). The archived view's 74.8% is on a different basis.

## 2. Primary cause (fixed order) and overlap

A card gets the first cause in the list that applies. **Cause 4 can never be primary** under this order: every gap-card ability belongs to a card that cause 1 already took. It appears only as a second cause, which is exactly what keeps a fix from over-promising. Cause 7 is empty by construction: cards that sit only in broad groups are 3,131 cards outside the pile.

| cause | primary | with a second cause | has this cause (any) |
|---|---:|---:|---:|
| 1 parser gap | 4,638 | 2,108 | 4,638 |
| 2 unparsed or parse mistake | 35 | 1 | 35 |
| 3 dropped-condition hold | 1,064 | 47 | 1,726 |
| 4 gap-card hold | 0 | 0 | 1,445 |
| 5 below the 5-member minimum | 1,149 | 4 | 1,377 |
| 6 modal / no signature / no family | 1 | 0 | 8 |
| 7 broad group only | 0 | 0 | 0 |
| 8 no effect or vanilla extension | 22 | 0 | 27 |
| 9 other | 0 | 0 | 0 |

Second causes behind each primary cause (cards):

- 1 parser gap: 4 gap-card hold 1,445, 3 dropped-condition hold 661, 5 below the 5-member minimum 184, 6 modal / no signature / no family 3, 8 no effect or vanilla extension 2
- 2 unparsed or parse mistake: 3 dropped-condition hold 1
- 3 dropped-condition hold: 5 below the 5-member minimum 44, 8 no effect or vanilla extension 3
- 5 below the 5-member minimum: 6 modal / no signature / no family 4

Cards by number of causes: 1 causes: 4,749, 2 causes: 1,981, 3 causes: 171, 4 causes: 8

## 3. Evidence per cause

### Parser gap (cause 1)

- Cards: 4,638. Gap types (what the parser could not read): unread 3,419; trigger 509; cond 432; trigger + unread 129; cond + unread 54; item-level only 52; effect 18; cond + trigger 12; effect + unread 10; cond + trigger + unread 3.
- Cards with at least one clean ability that passes the same-line and continuation tests: **1,581**. Of those, **1,252** have a held-out ability that would match an unflagged specific leaf (1,436 abilities), and 193 more only match broad leaves.
- Cards failing each test: item_gap 4,089, gap_card_continuation_gap 251, gap_card_no_text 245, gap_card_same_line_gap 74.
- Distinct gap fragments: 4,030; 3,805 cards have exactly one, 781 have two or more.

Top 10 gap causes by cards (sole cause = the card's only gap fragment, so fixing it clears the gap; the last column is an upper bound on cards that would then be placed, because they already have an ability matching an unflagged leaf):

| kind | fragment | cards | sole-cause cards | ...of which already have a matching ability |
|---|---|---:|---:|---:|
| unread | otherwise | 65 | 53 | 0 |
| unread | starting with you | 39 | 3 | 0 |
| cond | it remains exiled | 37 | 25 | 12 |
| unread | empower jace N | 31 | 22 | 10 |
| trigger | when ~ specializes | 30 | 20 | 0 |
| effect | GenericEffect[?] | 28 | 18 | 8 |
| unread | draft a card from ~'s spellbook | 25 | 18 | 6 |
| cond | ~ is paired with another creature | 25 | 25 | 1 |
| unread | you take the initiative | 23 | 17 | 6 |
| unread | starting intensity N | 20 | 2 | 1 |

### Below the 5-member minimum (cause 5)

- Primary-cause cards: 1,149, with 1,212 blocking abilities (below_minimum_size 582, rare_object 321, rare_verb_parameter 294, rare_effect_type 15).
- Best signature similarity (Jaccard over field=value pairs, same effect type) of each card's closest blocking ability to any leaf: 0.70-0.90 196, 0.30-0.50 207, 0.50-0.70 651, no leaf of that effect type 52, <0.30 25, >=0.90 18.
- Nearest leaves, by cards: Put +1/+1 counters on this permanent (40); Destroy a land (27); Sacrifice a creature (21); Create a token copy of a creature you control (18); Reveal cards until one matches (land) (15); A creature becomes a copy (14); Untap a creature (12); A permanent gains an ability until end of turn (11); Gain control of a creature (10); Exile all cards from a graveyard (10).
- With a minimum of 3 instead of 5 (measured, not built): **793 cards** have a blocking ability that would place, **768** have every blocking ability placing; 814 abilities have a leaf at 3 but not at 5.

### Dropped-condition holds (cause 3)

- Flagged abilities held back in the pile: 1,790. If every sub-shape were fixed and the abilities then matched like any clean ability: 987 would place in an unflagged leaf, 325 only in a broad leaf, 478 still would not place; **726 clean cards would move** (241 gap-card abilities would place but stay held out).

| shape | sub-shape | items | place (unflagged) | broad | still no | on gap cards | clean cards that would move |
|---|---|---:|---:|---:|---:|---:|---:|
| sequential-chain | later sentence 'If X, B.' | 417 | 233 | 82 | 102 | 168 | 166 |
| trigger-intervening | intervening if | 362 | 189 | 88 | 85 | 117 | 152 |
| result-dependent | this way / if you do | 230 | 127 | 37 | 66 | 89 | 99 |
| sequential-chain | inline 'A if X.' | 164 | 75 | 37 | 52 | 91 | 37 |
| embedded-replacement | 'if X would Y, Z instead' inside an ability | 153 | 55 | 29 | 69 | 70 | 45 |
| sequential-chain | if ... instead | 107 | 66 | 20 | 21 | 55 | 36 |
| compound | two conditions joined by or / and | 53 | 28 | 13 | 12 | 18 | 19 |
| replacement-level | enters tapped / with counters if | 45 | 41 | 0 | 4 | 3 | 38 |
| result-dependent | search this way -> shuffle (benign) | 42 | 29 | 3 | 10 | 9 | 28 |
| filter-targeting | restriction on the target ('X target Y if it ...') | 40 | 34 | 1 | 5 | 8 | 26 |
| negative | declined option ('may/pay ... if you don't') | 40 | 20 | 7 | 13 | 11 | 16 |
| result-dependent | if you win/lose | 34 | 18 | 2 | 14 | 12 | 12 |
| negative | negated event/state ('if you didn't ...') | 22 | 9 | 5 | 8 | 7 | 7 |
| static-level | Panharmonicon | 16 | 16 | 0 | 0 | 3 | 13 |
| branch-structural | FlipCoin sub_ability outside the branch | 10 | 9 | 0 | 1 | 5 | 5 |
| static-level | ReduceCost | 9 | 9 | 0 | 0 | 1 | 8 |
| static-level | GraveyardCastPermission | 9 | 5 | 0 | 4 | 1 | 4 |
| activation-restriction-missing | 'Activate only if' with no restriction at all | 8 | 1 | 0 | 7 | 8 | 0 |
| replacement-level | other replacement | 7 | 3 | 1 | 3 | 1 | 3 |
| static-level | Continuous | 6 | 6 | 0 | 0 | 1 | 5 |
| static-level | CastWithFlash | 5 | 5 | 0 | 0 | 2 | 3 |
| static-level | CantAttack | 4 | 4 | 0 | 0 | 0 | 4 |
| replacement-level | damage prevention / modification | 2 | 0 | 0 | 2 | 2 | 0 |
| static-level | CantBlock | 2 | 2 | 0 | 0 | 0 | 2 |
| static-level | CantBeCountered | 1 | 1 | 0 | 0 | 0 | 1 |
| static-level | CantAttackOrBlock | 1 | 1 | 0 | 0 | 0 | 1 |
| static-level | RaiseCost | 1 | 1 | 0 | 0 | 0 | 1 |

(The numbers assume the fix leaves each ability's parse as the detector's structure implies; a real fix changes the parse. Treat as an **estimate** of the ceiling.)

### Other causes

- Unparsed or parse mistake: 35 cards (known_parse_mistake 8, not_parsed 27).
- Modal / no signature / no family: 1 cards (no_signature 1).
- No effect or vanilla extension: 22 cards. Other: 0 cards.

### Ten sample cards per cause (seeded)

**1 parser gap**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Sylvan Paradise | One or more target creatures become green until end of turn. | gap: unread: one or more target creatures become green | no ability of this card clears the tests |
| Storm of Souls | Return all creature cards from your graveyard to the battlefield. Each of them is a 1/1 Spirit with flying in  | gap: unread: each of them is a N/N spirit with flying in addition to its  | no ability of this card clears the tests |
| Sycorax Commander | When this creature enters, each opponent faces a villainous choice — That opponent discards all the cards in t | gap: unread: face a villainous choice — that opponent discards all the ca | no ability of this card clears the tests |
| Fast | Target creature gains haste until end of turn. It can't be blocked this turn except by Vehicles or by creature | gap: unread: it can't be blocked this turn except by vehicles or by creat | no ability of this card clears the tests |
| Jocasta, Automaton Avenger | Whenever your commander deals combat damage to a player, put a +1/+1 counter on Jocasta. | gap: trigger: whenever your commander deals combat damage to a player | held-out ability would sit in: Put it onto the battlefield — what it applies to isn't recorded |
| Static Discharge | Starting intensity 3 | gap: unread: cards you own named ~ intensify by N; unread: starting intensity N | no ability of this card clears the tests |
| Edgar, King of Figaro | Two-Headed Coin — The first time you flip one or more coins each turn, those coins come up heads and you win t | gap: unread: two-headed coin — the first time you flip one or more coins  | held-out ability would sit in: Draw cards — who draws isn't recorded |
| Rootpath Purifier | Lands you control and land cards in your library are basic. | gap: unread: lands you control and land cards in your library are basic | no ability of this card clears the tests |
| Feywild Caretaker | When this creature enters, you take the initiative. | gap: unread: you take the initiative | no ability of this card clears the tests |
| Linvala, Shield of Sea Gate | Sacrifice Linvala: Choose hexproof or indestructible. Creatures you control gain that ability until end of tur | gap: unread: attack or block, and its activated abilities can't be activa; unread: creatures you control gain that ability | no ability of this card clears the tests |

**2 unparsed or parse mistake**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Swarm, Being of Bees |  | not_parsed |  |
| Bond of Agony | Each other player loses X life. | known_parse_mistake / not_in_scope:corrections_flagged |  |
| Skyshroud Condor |  | not_parsed |  |
| Vicious Rivalry | Destroy all artifacts and creatures with mana value X or less. | known_parse_mistake / not_in_scope:corrections_flagged |  |
| Grim Wanderer |  | not_parsed |  |
| Toxic Deluge | All creatures get -X/-X until end of turn. | known_parse_mistake / not_in_scope:corrections_flagged |  |
| Illusory Angel |  | not_parsed |  |
| Volunteer Reserves |  | not_parsed |  |
| Skizzik Surger |  | not_parsed |  |
| Talara's Battalion |  | not_parsed |  |

**3 dropped-condition hold**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Sundering Stroke | Sundering Stroke deals 7 damage divided as you choose among one, two, or three targets. If at least seven red  | dropped-condition detector: if ... instead | would match: Deal damage to any target |
| Odious Witch | Whenever this creature attacks, defending player loses 1 life and you gain 1 life. | dropped-condition detector: intervening if | would match: Transform this permanent |
| Deathgorge Scavenger | Whenever this creature enters or attacks, you may exile target card from a graveyard. If a creature card is ex | dropped-condition detector: this way / if you do | would match: Exile a card from a graveyard |
| Collector's Cage | {1}, {T}: Put a +1/+1 counter on target creature you control. Then if you control three or more creatures with | dropped-condition detector: later sentence 'If X, B.' | would match: Put +1/+1 counters on a creature you control |
| Branded Brawlers | ~ can't attack if defending player controls an untapped land. | dropped-condition detector: CantAttack | would match: This permanent can't attack, sometimes only unless a condition is met |
| Survival Cache | You gain 2 life. Then if you have more life than an opponent, draw a card. | dropped-condition detector: later sentence 'If X, B.' | would match: Gain life, then draw |
| Skullknocker Ogre | Whenever this creature deals damage to an opponent, that player discards a card at random. If the player does, | dropped-condition detector: this way / if you do | would still not place |
| Springjack Knight | Whenever this creature attacks, clash with an opponent. If you win, target creature gains double strike until  | dropped-condition detector: if you win/lose | would still not place |
| Intervention Pact | At the beginning of your next upkeep, pay {1}{W}{W}. If you don't, you lose the game. | dropped-condition detector: negated event/state ('if you didn't ...') | would match: Lose the game |
| Arcane Heist | You may cast target instant or sorcery card from an opponent's graveyard without paying its mana cost. If that | dropped-condition detector: 'if X would Y, Z instead' inside an ability | would only reach a broad leaf |

**5 below the 5-member minimum**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Sky Tether | Enchanted creature has defender and loses flying. | rare_verb_parameter | nearest leaf 0.40: Enchanted creature has an extra ability |
| Increasing Savagery | Put five +1/+1 counters on target creature. If this spell was cast from a graveyard, put ten +1/+1 counters on | below_minimum_size | nearest leaf 0.83: Put +1/+1 counters on it, if you pay a cost and a condition holds — what it applies to isn't recorded |
| Shrine Steward | When this creature enters, you may search your library for an Aura or Shrine card, reveal it, put it into your | below_minimum_size | nearest leaf 0.71: Search your library for an Aura enchantment and put it into your hand |
| Crescendo of War | Attacking creatures get +1/+0 for each strife counter on ~. | below_minimum_size | nearest leaf 0.60: Put +1/+1 counters on this permanent |
| Cloudspire Skycycle | When this Vehicle enters, distribute two +1/+1 counters among one or two other target Vehicles and/or creature | below_minimum_size | nearest leaf 0.71: Put +1/+1 counters on a Vehicle artifact or creature you control |
| Whirlpool Warrior | {R}, Sacrifice this creature: Each player shuffles the cards from their hand into their library, then draws th | rare_verb_parameter | nearest leaf 0.50: Move all you from a graveyard to a library, then shuffle, after choosing a target |
| Fraying Sanity | At the beginning of each end step, enchanted player mills X cards, where X is the number of cards put into the | rare_verb_parameter | nearest leaf 0.43: Mill cards |
| Llanowar Druid | {T}, Sacrifice this creature: Untap all Forests. | below_minimum_size | nearest leaf 0.60: Untap all lands you control |
| Mirrormade | You may have this enchantment enter as a copy of any artifact or enchantment on the battlefield. | rare_object | nearest leaf 0.50: A creature becomes a copy |
| Balduvian Dead | {2}{R}, Exile a creature card from your graveyard: Create a 3/1 black and red Graveborn creature token with ha | below_minimum_size | nearest leaf 0.60: Create creature tokens with haste |

**6 modal / no signature / no family**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Veilstone Amulet | Whenever you cast a spell, creatures you control can't be the targets of spells or abilities your opponents co | too_unusual / no_signature |  |

**8 no effect or vanilla extension**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Soul-Scar Mage | If a source you control would deal noncombat damage to a creature an opponent controls, put that many -1/-1 co | no_effect_to_group / replacement_group |  |
| Neriv, Heart of the Storm | If a creature you control that entered this turn would deal damage, it deals twice that much damage instead. | no_effect_to_group / replacement_group |  |
| Captain's Maneuver | The next X damage that would be dealt to target creature, planeswalker, or player this turn is dealt to anothe | no_effect_to_group / replacement_group |  |
| Treacherous Link | All damage that would be dealt to enchanted creature is dealt to its controller instead. | no_effect_to_group / replacement_group |  |
| Lich's Mirror | If you would lose the game, instead shuffle your hand, your graveyard, and all permanents you own into your li | no_effect_to_group / replacement_group |  |
| Exalted Sunborn | If one or more tokens would be created under your control, twice that many of those tokens are created instead | no_effect_to_group / replacement_group |  |
| Lava Burst | Lava Burst deals X damage to any target. If Lava Burst would deal damage to a creature, that damage can't be p | no_effect_to_group / replacement_group |  |
| Divine Presence | If a source would deal 4 or more damage to a permanent or player, that source deals 3 damage to that permanent | no_effect_to_group / replacement_group |  |
| Donatello, the Brains | If one or more tokens would be created under your control, those tokens plus a Mutagen token are created inste | no_effect_to_group / replacement_group |  |
| Heroic Sacrifice | Choose target creature you control. Until end of turn, all damage that would be dealt to you and creatures you | no_effect_to_group / replacement_group |  |

## 4. Popularity

Field: edhrec_rank (Scryfall oracle_cards export); lower is more popular; 32332 of 34647 in-scope cards have one. Cumulative: a top-1,000 card is also in the top 3,000 and 10,000.

| primary cause | cards | top 1,000 | top 3,000 | top 10,000 | no rank |
|---|---:|---:|---:|---:|---:|
| 1 parser gap | 4,638 | 71 | 337 | 1494 | 434 |
| 2 unparsed or parse mistake | 35 | 2 | 3 | 8 | 0 |
| 3 dropped-condition hold | 1,064 | 16 | 70 | 287 | 27 |
| 4 gap-card hold | 0 | 0 | 0 | 0 | 0 |
| 5 below the 5-member minimum | 1,149 | 34 | 125 | 371 | 35 |
| 6 modal / no signature / no family | 1 | 0 | 0 | 0 | 0 |
| 7 broad group only | 0 | 0 | 0 | 0 | 0 |
| 8 no effect or vanilla extension | 22 | 1 | 4 | 7 | 0 |
| 9 other | 0 | 0 | 0 | 0 | 0 |
| all | 6,909 | 124 | 539 | 2167 | 496 |

## 5. Unique subgrouping, on paper

- Pile cards with at least one ability whose effect type maps to a family of the new tree: **5,435** of 6,909. Cards with no family at all: **1,474** (1 parser gap 1408, 8 no effect or vanilla extension 22, 2 unparsed or parse mistake 35, 3 dropped-condition hold 8, 6 modal / no signature / no family 1).
- Cards per family if a card may appear under several (browse-only): Zone change 778; Counters 659; Pump / grant 630; Static: continuous 619; Library 584; Tokens 408; Damage 359; Card draw 357; Destroy 228; Sacrifice 191; Tap / untap 183; Mana 179.
- Cards per family if each card goes to its most common family: Zone change 648; Counters 575; Pump / grant 572; Library 514; Static: continuous 463; Tokens 328; Damage 315; Card draw 270; Destroy 203; Mana 153; Sacrifice 148; Tap / untap 143.
- Largest single-assignment subgroup: **Zone change**; it spans 6 effect types, its top 3 cover 97% of its abilities (ChangeZone 573, Bounce 163, PutAtLibraryPosition 28, PhaseOut 12, Shuffle 5, PutOnTopOrBottom 4).


## 6. Recommendation

Ranked by cards moved per effort. **Measured** = counted on the current build. **Estimate** = rests on a judgment call. The first three card sets are counted as sets, so their overlap is measured: A and B overlap in 0 cards, A and C in 0, B and C in 0 (they are disjoint by construction: A is gap cards, B is cards whose only block is the minimum, C is clean cards held for a dropped condition), so together they cover **2,771** distinct cards. What is NOT measured is whether a card also needs a second fix: 2,108 of the primary cause-1 cards, 5 of cause 5 and 49 of cause 3 have a second cause, but each set above counts only cards that need nothing else to be placed.

| rank | fix | cards moved (upper bound) | effort | what it leaves behind | judgment calls |
|---:|---|---:|---|---|---|
| 1 | **Lift the gap-card hold** (the 5.0% question): their held-out abilities already match an unflagged leaf | **1,252** measured (about +3.6 points on the headline) | low: a decision plus a fresh sample of about 100 on a new seed | the other 3,386 gap cards, whose abilities fail the tests or match nothing | the error rate: 2 of 40 wrong last time; with a true rate near 5% roughly 63 of these would be wrongly filed (estimate) |
| 2 | **A minimum of 3 for the "too unusual" cards** | **793** measured (every blocking ability places for 768) | low to build; needs a coherence check | the other 356 of that group; the cards with no near leaf | whether groups of 3 or 4 abilities are coherent: unmeasured, so the real number is lower (estimate); this changes a threshold, which this task did not touch |
| 3 | **Browse-only subgroups by family** (display, not placement) | up to 5,435 cards get a home; none count toward the precise headline | low to medium | 1,474 cards with no family (mostly gap cards whose only abilities are the hole) | whether a browse-only home counts as organized: a definition call; the largest subgroup is not a junk drawer on effect type (see section 5) |
| 4 | **Dropped-condition fixes** (detector / parser) | ceiling **726** clean cards for all sub-shapes together; **417** for the three biggest sub-shapes (measured on the detector's own structure) | high: each sub-shape is its own parser change | gap cards (their items stay held out), and the 478 flagged items that would still not place | the real figure is lower: once the condition is kept, items get a more specific signature and many will fall to a rarer leaf (estimate) |
| 5 | **Parser gap causes**, one fragment at a time | the ten biggest causes clear the gap for 203 sole-cause cards; at most 44 of those already have a matching ability, so about that many would be placed (measured upper bound) | high per fix, and the tail is long | 4,030 distinct gap fragments exist; 3,805 cards have exactly one | each fix helps a handful of cards; several of the ten are mechanics the parser does not model at all (e.g. spellbook drafting, the initiative) |
| 6 | Unparsed (29), known parse mistakes (8), replacement-only (23), modal / no signature (1) | 61 | per card | all of them | none; these are the floor of the pile |

What the ranking does not claim: none of the sets is a count of cards that will be **correctly** placed; A carries a known error risk, B and C carry unmeasured ones. The popularity view says the most popular cards are in cause 1 by number (71 of the top 1,000), but cause 5 has the highest share (3.0% of its cards are in the top 1,000 against 1.5% for cause 1).

