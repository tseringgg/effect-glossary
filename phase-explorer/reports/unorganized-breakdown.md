# "Not yet organized": breakdown by cause

Investigation only (`src/analyze_unorganized_breakdown.py`, seed 20261100). Nothing was built, placed or changed; new files only: `build/unorganized_breakdown.json` and this report. Every figure is **measured** from the current build unless it says **estimate**.

## 1. Recount

- Universe 38,921 = 26,589 placed in a group (21,637 precise-grouped + 3,131 only in broad groups + 1,261 keyword block + 351 no abilities + 209 replacement) + **8,058 not yet organized** + 4,274 not cards. Reconciles: **True**.
- Groups in the pile today: gap 5,676, too_unusual 1,239, text_may_be_lost 1,078, not_parsed 29, no_effect_to_group 28, known_parse_mistake 8.
- Headline: **23,458 of 34,647 = 67.7%** (basis: placed by an ability in an unflagged leaf of 5 or more, plus the keyword block, “No abilities” and the replacement groups, out of the 34,647 in-scope cards).
- With broad groups: **26,589 = 76.7%** (basis: the headline plus the 3,131 cards whose abilities sit only in groups broader than they look). The archived view's 74.8% is on a different basis.

## 2. Primary cause (fixed order) and overlap

A card gets the first cause in the list that applies. **Cause 4 can never be primary** under this order: every gap-card ability belongs to a card that cause 1 already took. It appears only as a second cause, which is exactly what keeps a fix from over-promising. Cause 7 is empty by construction: cards that sit only in broad groups are 3,131 cards outside the pile.

| cause | primary | with a second cause | has this cause (any) |
|---|---:|---:|---:|
| 1 parser gap | 5,700 | 2,603 | 5,700 |
| 2 unparsed or parse mistake | 37 | 1 | 37 |
| 3 dropped-condition hold | 1,108 | 49 | 2,002 |
| 4 gap-card hold | 0 | 0 | 1,711 |
| 5 below the 5-member minimum | 1,189 | 5 | 1,457 |
| 6 modal / no signature / no family | 1 | 0 | 22 |
| 7 broad group only | 0 | 0 | 0 |
| 8 no effect or vanilla extension | 23 | 0 | 28 |
| 9 other | 0 | 0 | 0 |

Second causes behind each primary cause (cards):

- 1 parser gap: 4 gap-card hold 1,711, 3 dropped-condition hold 893, 5 below the 5-member minimum 222, 6 modal / no signature / no family 16, 8 no effect or vanilla extension 2
- 2 unparsed or parse mistake: 3 dropped-condition hold 1
- 3 dropped-condition hold: 5 below the 5-member minimum 46, 8 no effect or vanilla extension 3
- 5 below the 5-member minimum: 6 modal / no signature / no family 5

Cards by number of causes: 1 causes: 5,400, 2 causes: 2,426, 3 causes: 223, 4 causes: 9

## 3. Evidence per cause

### Parser gap (cause 1)

- Cards: 5,700. Gap types (what the parser could not read): unread 4,305; trigger 550; cond 458; trigger + unread 216; cond + unread 69; item-level only 57; effect 19; cond + trigger 13; effect + unread 10; cond + trigger + unread 3.
- Cards with at least one clean ability that passes the same-line and continuation tests: **1,874**. Of those, **1,483** have a held-out ability that would match an unflagged specific leaf (1,708 abilities), and 228 more only match broad leaves.
- Cards failing each test: item_gap 4,995, gap_card_continuation_gap 287, gap_card_no_text 304, gap_card_same_line_gap 101.
- Distinct gap fragments: 5,416; 4,407 cards have exactly one, 1,236 have two or more.

Top 10 gap causes by cards (sole cause = the card's only gap fragment, so fixing it clears the gap; the last column is an upper bound on cards that would then be placed, because they already have an ability matching an unflagged leaf):

| kind | fragment | cards | sole-cause cards | ...of which already have a matching ability |
|---|---|---:|---:|---:|
| unread | otherwise | 81 | 57 | 0 |
| unread | {tk}{tk} — N/N | 44 | 0 | 0 |
| unread | starting with you | 40 | 3 | 0 |
| cond | it remains exiled | 37 | 25 | 12 |
| unread | empower jace N | 31 | 22 | 10 |
| trigger | when ~ specializes | 30 | 20 | 0 |
| effect | GenericEffect[?] | 29 | 19 | 8 |
| unread | draft a card from ~'s spellbook | 25 | 18 | 6 |
| cond | ~ is paired with another creature | 25 | 25 | 1 |
| unread | you take the initiative | 23 | 17 | 6 |

### Below the 5-member minimum (cause 5)

- Primary-cause cards: 1,189, with 1,258 blocking abilities (below_minimum_size 596, rare_object 340, rare_verb_parameter 307, rare_effect_type 15).
- Best signature similarity (Jaccard over field=value pairs, same effect type) of each card's closest blocking ability to any leaf: 0.70-0.90 201, 0.30-0.50 213, 0.50-0.70 676, no leaf of that effect type 53, <0.30 27, >=0.90 19.
- Nearest leaves, by cards: Put +1/+1 counters on this permanent (41); Destroy a land (29); Sacrifice a creature (21); Create a token copy of a creature you control (19); Reveal cards until one matches (land) (17); A creature becomes a copy (14); A creature you control becomes a copy (ability duration: permanently) (12); Untap a creature (12); Gain control of a creature (11); A permanent gains an ability until end of turn (11).
- With a minimum of 3 instead of 5 (measured, not built): **818 cards** have a blocking ability that would place, **792** have every blocking ability placing; 843 abilities have a leaf at 3 but not at 5.

### Dropped-condition holds (cause 3)

- Flagged abilities held back in the pile: 2,088. If every sub-shape were fixed and the abilities then matched like any clean ability: 1,072 would place in an unflagged leaf, 350 only in a broad leaf, 666 still would not place; **761 clean cards would move** (289 gap-card abilities would place but stay held out).

| shape | sub-shape | items | place (unflagged) | broad | still no | on gap cards | clean cards that would move |
|---|---|---:|---:|---:|---:|---:|---:|
| sequential-chain | later sentence 'If X, B.' | 529 | 265 | 96 | 168 | 260 | 181 |
| trigger-intervening | intervening if | 399 | 204 | 92 | 103 | 146 | 159 |
| result-dependent | this way / if you do | 269 | 127 | 39 | 103 | 126 | 99 |
| sequential-chain | inline 'A if X.' | 194 | 81 | 38 | 75 | 118 | 39 |
| embedded-replacement | 'if X would Y, Z instead' inside an ability | 170 | 55 | 30 | 85 | 87 | 45 |
| sequential-chain | if ... instead | 114 | 73 | 20 | 21 | 59 | 39 |
| compound | two conditions joined by or / and | 67 | 31 | 14 | 22 | 29 | 20 |
| negative | declined option ('may/pay ... if you don't') | 50 | 23 | 7 | 20 | 19 | 18 |
| replacement-level | enters tapped / with counters if | 49 | 44 | 0 | 5 | 6 | 39 |
| filter-targeting | restriction on the target ('X target Y if it ...') | 43 | 35 | 1 | 7 | 10 | 27 |
| result-dependent | search this way -> shuffle (benign) | 43 | 30 | 3 | 10 | 10 | 28 |
| result-dependent | if you win/lose | 40 | 18 | 2 | 20 | 18 | 12 |
| negative | negated event/state ('if you didn't ...') | 24 | 10 | 5 | 9 | 9 | 7 |
| static-level | Panharmonicon | 17 | 17 | 0 | 0 | 4 | 13 |
| static-level | Continuous | 13 | 11 | 1 | 1 | 4 | 7 |
| activation-restriction-missing | 'Activate only if' with no restriction at all | 11 | 3 | 1 | 7 | 11 | 0 |
| static-level | ReduceCost | 10 | 10 | 0 | 0 | 2 | 8 |
| branch-structural | FlipCoin sub_ability outside the branch | 10 | 9 | 0 | 1 | 5 | 5 |
| static-level | GraveyardCastPermission | 9 | 5 | 0 | 4 | 1 | 4 |
| replacement-level | other replacement | 8 | 4 | 1 | 3 | 1 | 4 |
| static-level | CastWithFlash | 5 | 5 | 0 | 0 | 2 | 3 |
| static-level | CantAttack | 4 | 4 | 0 | 0 | 0 | 4 |
| static-level | CantBlock | 3 | 3 | 0 | 0 | 1 | 2 |
| static-level | CantAttackOrBlock | 2 | 2 | 0 | 0 | 1 | 1 |
| replacement-level | damage prevention / modification | 2 | 0 | 0 | 2 | 2 | 0 |
| static-level | MayChooseNotToUntap | 1 | 1 | 0 | 0 | 1 | 0 |
| static-level | CantBeCountered | 1 | 1 | 0 | 0 | 0 | 1 |
| static-level | RaiseCost | 1 | 1 | 0 | 0 | 0 | 1 |

(The numbers assume the fix leaves each ability's parse as the detector's structure implies; a real fix changes the parse. Treat as an **estimate** of the ceiling.)

### Other causes

- Unparsed or parse mistake: 37 cards (known_parse_mistake 8, not_parsed 29).
- Modal / no signature / no family: 1 cards (no_signature 1).
- No effect or vanilla extension: 23 cards. Other: 0 cards.

### Ten sample cards per cause (seeded)

**1 parser gap**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Excava, the Risen Past | Whenever Excava attacks, return up to one target artifact, creature, or non-Aura enchantment card with mana va | gap: unread: it's a N/N spirit creature with flying in addition to its ot | no ability of this card clears the tests |
| Mercurial Spelldancer | Whenever this creature deals combat damage to a player, you may remove two oil counters from it. If you do, wh | gap: unread: when you next cast an instant or sorcery spell this turn, co | held-out ability would sit in: This permanent can't be blocked |
| Shadow of the Goblin | Whenever you play a land or cast a spell from anywhere other than your hand, this enchantment deals 1 damage t | gap: trigger: whenever you play a land or cast a spell from anywhere other | held-out ability would sit in: Discard cards, then draw |
| Sphinx's Herald | {2}{U}, {T}, Sacrifice a white creature, a blue creature, and a black creature: Search your library for a card | gap: unread: a black creature; unread: a blue creature | no ability of this card clears the tests |
| Kaya, Geist Hunter |  | gap: unread: twice that many of those tokens are created instead | held-out ability would sit in: A permanent gains deathtouch until end of turn |
| Shield of Kaldra | Equipment named Sword of Kaldra, Shield of Kaldra, and Helm of Kaldra have indestructible. | gap: unread: helm of kaldra have indestructible; unread: ment named sword of kaldra | held-out ability would sit in: Equipped creature has a keyword |
| Gunk Slug | When Gunk Slug enters, create three Gunk token cards and shuffle them into target opponent's library. | gap: unread: create three gunk token cards | no ability of this card clears the tests |
| Dubious Challenge | Look at the top ten cards of your library, exile up to two creature cards from among them, then shuffle. Targe | gap: unread: choose one of the exiled cards and put it onto the battlefie | no ability of this card clears the tests |
| Sarpadian Empires, Vol. VII | As this artifact enters, choose white Citizen, blue Camarid, black Thrull, red Goblin, or green Saproling. | gap: unread: as this artifact enters, choose white citizen, blue camarid, | held-out ability would sit in: Create creature tokens |
| Imperiosaur | Spend only mana produced by basic lands to cast this spell. | gap: unread: spend only mana produced by basic lands to cast this spell | no ability of this card clears the tests |

**2 unparsed or parse mistake**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Street Wraith |  | not_parsed |  |
| Banned Eldraine Card |  | not_parsed |  |
| Putrid Raptor |  | not_parsed |  |
| Zombie Cutthroat |  | not_parsed |  |
| Swarm, Being of Bees |  | not_parsed |  |
| Fix What's Broken | Return each artifact and creature card with mana value X from your graveyard to the battlefield. | known_parse_mistake / not_in_scope:corrections_flagged |  |
| Elite Inquisitor |  | not_parsed |  |
| Ruthless Radrat |  | not_parsed |  |
| Fleshwrither |  | not_parsed |  |
| Volunteer Reserves |  | not_parsed |  |

**3 dropped-condition hold**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Illuminate | Illuminate deals X damage to target creature. If this spell was kicked with its {2}{R} kicker, it deals X dama | dropped-condition detector: later sentence 'If X, B.' | would match: Deal damage to a creature |
| Akuta, Born of Ash | At the beginning of your upkeep, if you have more cards in hand than each opponent, you may sacrifice a Swamp. | dropped-condition detector: intervening if | would match: Sacrifice a land |
| Inventive Wingsmith | At the beginning of your end step, if you haven't cast a spell from your hand this turn and this creature does | dropped-condition detector: two conditions joined by or / and | would still not place |
| Ziatora's Envoy | Whenever this creature deals combat damage to a player, look at the top card of your library. You may play a l | dropped-condition detector: declined option ('may/pay ... if you don't') | would only reach a broad leaf |
| Land Aid '04 | Search your library for a basic land card, put that card onto the battlefield tapped, then shuffle. If you san | dropped-condition detector: later sentence 'If X, B.' | would match: Search your library for a basic land and put it onto the battlefield (follow-up varies) |
| Civilized Scholar | {T}: Draw a card, then discard a card. If a creature card is discarded this way, untap this creature, then tra | dropped-condition detector: this way / if you do | would only reach a broad leaf |
| Two-Headed Giant | Whenever this creature attacks, flip two coins. If both coins come up heads, this creature gains double strike | dropped-condition detector: later sentence 'If X, B.' | would still not place |
| Frodo, Adventurous Hobbit | Whenever Frodo attacks, if you gained 3 or more life this turn, the Ring tempts you. Then if Frodo is your Rin | dropped-condition detector: intervening if | would match: The Ring tempts you |
| Feast of Worms | Destroy target land. If that land was legendary, its controller sacrifices another land of their choice. | dropped-condition detector: later sentence 'If X, B.' | would match: Destroy a land |
| Krovikan Vampire | At the beginning of each end step, if a creature dealt damage by this creature this turn died, put that card o | dropped-condition detector: intervening if | would only reach a broad leaf |

**5 below the 5-member minimum**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Break Under Pressure | Target opponent sacrifices a creature or planeswalker with the greatest mana value among creatures and planesw | below_minimum_size | nearest leaf 0.60: Sacrifice a creature, then gain life |
| Dollhouse of Horrors | {1}, {T}, Exile a creature card from your graveyard: Create a token that's a copy of the exiled card, except i | rare_object | nearest leaf 0.40: Create a token copy of a creature |
| Sky Tether | Enchanted creature has defender and loses flying. | rare_verb_parameter | nearest leaf 0.40: Enchanted creature has an extra ability |
| Launch Mishap | Counter target creature or planeswalker spell. Create a 1/1 colorless Thopter artifact creature token with fly | below_minimum_size | nearest leaf 0.67: Counter a spell, then create a token |
| Decoy Gambit | For each opponent, choose up to one target creature that player controls, then return that creature to its own | below_minimum_size | nearest leaf 0.60: Return it to its owner's hand — “all” vs “target” isn't recorded; what it applies to isn't recorded |
| Snarl Song | Converge — Create two 0/0 green and blue Fractal creature tokens. Put X +1/+1 counters on each of them and you | below_minimum_size | nearest leaf 0.60: Create Fractal tokens, then put +1/+1 counters on itself |
| Waker of the Wilds | {X}{G}{G}: Put X +1/+1 counters on target land you control. That land becomes a 0/0 Elemental creature with ha | below_minimum_size | nearest leaf 0.67: Put +1/+1 counters on permanents (you control) |
| Lich-Knights' Conquest | Sacrifice any number of artifacts, enchantments, and/or tokens. Return that many creature cards from your grav | rare_object | nearest leaf 0.17: Sacrifice creatures |
| Gilder Bairn | {2}{G/U}, {Q}: Double the number of each kind of counter on target permanent. | rare_object | no leaf of that effect type |
| Loxodon Mender | {W}, {T}: Regenerate target artifact. | rare_object | nearest leaf 0.50: Regenerate this permanent |

**6 modal / no signature / no family**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Veilstone Amulet | Whenever you cast a spell, creatures you control can't be the targets of spells or abilities your opponents co | too_unusual / no_signature |  |

**8 no effect or vanilla extension**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Heroic Sacrifice | Choose target creature you control. Until end of turn, all damage that would be dealt to you and creatures you | no_effect_to_group / replacement_group |  |
| Goblin Bowling Team | If this creature would deal damage to a permanent or player, it deals that much damage plus the result of a si | no_effect_to_group / replacement_group |  |
| Soul-Scar Mage | If a source you control would deal noncombat damage to a creature an opponent controls, put that many -1/-1 co | no_effect_to_group / replacement_group |  |
| Harm's Way | The next 2 damage that a source of your choice would deal to you and/or permanents you control this turn is de | no_effect_to_group / replacement_group |  |
| Ghosts of the Innocent | If a source would deal damage to a permanent or player, it deals half that damage, rounded down, to that perma | no_effect_to_group / replacement_group |  |
| Captain's Maneuver | The next X damage that would be dealt to target creature, planeswalker, or player this turn is dealt to anothe | no_effect_to_group / replacement_group |  |
| Szadek, Lord of Secrets | If Szadek would deal combat damage to a player, instead put that many +1/+1 counters on Szadek and that player | no_effect_to_group / replacement_group |  |
| Pariah | All damage that would be dealt to you is dealt to enchanted creature instead. | no_effect_to_group / replacement_group |  |
| Exquisite Archangel | If you would lose the game, instead exile this creature and your life total becomes equal to your starting lif | no_effect_to_group / replacement_group |  |
| Treacherous Link | All damage that would be dealt to enchanted creature is dealt to its controller instead. | no_effect_to_group / replacement_group |  |

## 4. Popularity

Field: edhrec_rank (Scryfall oracle_cards export); lower is more popular; 32332 of 34647 in-scope cards have one. Cumulative: a top-1,000 card is also in the top 3,000 and 10,000.

| primary cause | cards | top 1,000 | top 3,000 | top 10,000 | no rank |
|---|---:|---:|---:|---:|---:|
| 1 parser gap | 5,700 | 71 | 337 | 1498 | 1,334 |
| 2 unparsed or parse mistake | 37 | 2 | 3 | 8 | 2 |
| 3 dropped-condition hold | 1,108 | 16 | 70 | 287 | 65 |
| 4 gap-card hold | 0 | 0 | 0 | 0 | 0 |
| 5 below the 5-member minimum | 1,189 | 34 | 125 | 371 | 72 |
| 6 modal / no signature / no family | 1 | 0 | 0 | 0 | 0 |
| 7 broad group only | 0 | 0 | 0 | 0 | 0 |
| 8 no effect or vanilla extension | 23 | 1 | 4 | 7 | 1 |
| 9 other | 0 | 0 | 0 | 0 | 0 |
| all | 8,058 | 124 | 539 | 2171 | 1,474 |

## 5. Unique subgrouping, on paper

- Pile cards with at least one ability whose effect type maps to a family of the new tree: **6,054** of 8,058. Cards with no family at all: **2,004** (1 parser gap 1935, 8 no effect or vanilla extension 23, 2 unparsed or parse mistake 37, 3 dropped-condition hold 8, 6 modal / no signature / no family 1).
- Cards per family if a card may appear under several (browse-only): Zone change 842; Counters 732; Static: continuous 720; Pump / grant 671; Library 630; Tokens 472; Card draw 409; Damage 389; Destroy 251; Sacrifice 220; Mana 215; Tap / untap 211.
- Cards per family if each card goes to its most common family: Zone change 699; Counters 633; Pump / grant 606; Library 556; Static: continuous 548; Tokens 383; Damage 339; Card draw 310; Destroy 222; Mana 185; Sacrifice 165; Tap / untap 160.
- Largest single-assignment subgroup: **Zone change**; it spans 6 effect types, its top 3 cover 97% of its abilities (ChangeZone 624, Bounce 172, PutAtLibraryPosition 31, PhaseOut 13, Shuffle 6, PutOnTopOrBottom 4).


## 6. Recommendation

Ranked by cards moved per effort. **Measured** = counted on the current build. **Estimate** = rests on a judgment call. The first three card sets are counted as sets, so their overlap is measured: A and B overlap in 0 cards, A and C in 0, B and C in 0 (they are disjoint by construction: A is gap cards, B is cards whose only block is the minimum, C is clean cards held for a dropped condition), so together they cover **3,062** distinct cards. What is NOT measured is whether a card also needs a second fix: 2,603 of the primary cause-1 cards, 5 of cause 5 and 49 of cause 3 have a second cause, but each set above counts only cards that need nothing else to be placed.

| rank | fix | cards moved (upper bound) | effort | what it leaves behind | judgment calls |
|---:|---|---:|---|---|---|
| 1 | **Lift the gap-card hold** (the 5.0% question): their held-out abilities already match an unflagged leaf | **1,483** measured (about +4.3 points on the headline) | low: a decision plus a fresh sample of about 100 on a new seed | the other 4,217 gap cards, whose abilities fail the tests or match nothing | the error rate: 2 of 40 wrong last time; with a true rate near 5% roughly 74 of these would be wrongly filed (estimate) |
| 2 | **A minimum of 3 for the "too unusual" cards** | **818** measured (every blocking ability places for 792) | low to build; needs a coherence check | the other 371 of that group; the cards with no near leaf | whether groups of 3 or 4 abilities are coherent: unmeasured, so the real number is lower (estimate); this changes a threshold, which this task did not touch |
| 3 | **Browse-only subgroups by family** (display, not placement) | up to 6,054 cards get a home; none count toward the precise headline | low to medium | 2,004 cards with no family (mostly gap cards whose only abilities are the hole) | whether a browse-only home counts as organized: a definition call; the largest subgroup is not a junk drawer on effect type (see section 5) |
| 4 | **Dropped-condition fixes** (detector / parser) | ceiling **761** clean cards for all sub-shapes together; **439** for the three biggest sub-shapes (measured on the detector's own structure) | high: each sub-shape is its own parser change | gap cards (their items stay held out), and the 666 flagged items that would still not place | the real figure is lower: once the condition is kept, items get a more specific signature and many will fall to a rarer leaf (estimate) |
| 5 | **Parser gap causes**, one fragment at a time | the ten biggest causes clear the gap for 206 sole-cause cards; at most 43 of those already have a matching ability, so about that many would be placed (measured upper bound) | high per fix, and the tail is long | 5,416 distinct gap fragments exist; 4,407 cards have exactly one | each fix helps a handful of cards; several of the ten are mechanics the parser does not model at all (e.g. spellbook drafting, the initiative) |
| 6 | Unparsed (29), known parse mistakes (8), replacement-only (23), modal / no signature (1) | 61 | per card | all of them | none; these are the floor of the pile |

What the ranking does not claim: none of the sets is a count of cards that will be **correctly** placed; A carries a known error risk, B and C carry unmeasured ones. The popularity view says the most popular cards are in cause 1 by number (71 of the top 1,000), but cause 5 has the highest share (2.9% of its cards are in the top 1,000 against 1.2% for cause 1).

