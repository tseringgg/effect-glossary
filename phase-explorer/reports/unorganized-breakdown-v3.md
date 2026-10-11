# "Not yet organized": breakdown by cause (v3, current build)

Investigation only (`src/analyze_unorganized_breakdown_v3.py`, seed 20261200). Nothing was built, placed or changed; new files only. Every figure is **measured** unless it says **estimate**.

## 1. Recount

- Universe 38,921 = 27,590 grouped (22,541 precise + 3,254 only in broad groups + 1,245 keyword block + 346 no abilities + 204 replacement) + **5,593 not yet organized** + 5,738 not cards. Reconciles: **True**.
- Groups in the pile: gap 3,293, too_unusual 1,201, text_may_be_lost 1,037, no_effect_to_group 27, not_parsed 27, known_parse_mistake 8.
- Headline: **24,336 of 33,183 = 73.3%** (basis: placed by an ability in an unflagged leaf of 5 or more, plus the keyword block, “No abilities” and the replacement groups, out of the 33,183 in-scope cards).
- With broad groups: **27,590 = 83.1%** (basis: the headline plus the 3,254 cards whose abilities sit only in groups broader than they look). The archived view's 74.8% is on a different basis.

## 2. Primary cause (fixed order) and overlap

Gap cards always take cause 1 first, so **cause 4 is never primary**: it is counted as a second cause (and sampled from the cards that have it).

| cause | primary | with a second or third cause | has this cause (any) |
|---|---:|---:|---:|
| 1 parser gap | 3,313 | 1,062 | 3,313 |
| 2 unparsed or parse mistake | 35 | 1 | 35 |
| 3 dropped-condition hold | 1,067 | 46 | 1,612 |
| 4 gap-card ability still unplaced | 0 | 0 | 457 |
| 5 below the 5-member minimum | 1,155 | 4 | 1,336 |
| 6 modal / no signature / no family | 1 | 0 | 6 |
| 7 no effect or vanilla extension | 22 | 0 | 27 |
| 8 other | 0 | 0 | 0 |

Second causes behind each primary cause (cards):

- 1 parser gap: 3 dropped-condition hold 544, 4 gap-card ability still unplaced 457, 5 below the 5-member minimum 138, 7 no effect or vanilla extension 2, 6 modal / no signature / no family 1
- 2 unparsed or parse mistake: 3 dropped-condition hold 1
- 3 dropped-condition hold: 5 below the 5-member minimum 43, 7 no effect or vanilla extension 3
- 5 below the 5-member minimum: 6 modal / no signature / no family 4

Cards by number of causes: 1: 4,480, 2: 1,033, 3: 80

## 3. Evidence per cause

### Parser gap and gap-card abilities still unplaced (causes 1 and 4)

- Cards: 3,313. Gap types: unread 2,556; trigger 285; cond 265; trigger + unread 107; cond + unread 47; item-level only 24; effect 10; cond + trigger 9; effect + unread 8; cond + trigger + unread 2.
- Why gap-card abilities are not placed (cards having at least one): item_gap 2,894, gap_card_continuation_gap 250, gap_card_no_text 164, gap_card_same_line_gap 92.
- Second causes of gap cards: 3 dropped-condition hold 544, 5 below the 5-member minimum 138, 4 gap-card ability still unplaced 457, 7 no effect or vanilla extension 2, 6 modal / no signature / no family 1. Cards with exactly one gap fragment: 2,572.
- **Fragment families** (node type + the first two words): 1,132 families cover 3,289 cards that have a fragment (3,102 distinct exact fragments); 2,720 of those cards have an unread clause.

| top N families | cards with any fragment in them | cards whose every fragment is in them |
|---:|---:|---:|
| 12 | 831 | 559 |
| 24 | 1,140 | 815 |
| 36 | 1,328 | 985 |
| 48 | 1,468 | 1,133 |
| 100 | 1,935 | 1,578 |
| 200 | 2,390 | 2,082 |

Largest families: unread "for each" (119); trigger "whenever a" (105); unread "choose a" (96); unread "the next" (92); trigger "whenever you" (87); unread "otherwise" (65); unread "put a" (62); unread "n n" (61); unread "conjure a" (53); unread "starting with" (41); cond "~ is" (40); unread "this ability" (34); trigger "whenever an" (32); unread "when you" (32); unread "at the" (31); trigger "when ~" (29); cond "you control" (28); cond "an opponent" (26); trigger "whenever one" (26); unread "as this" (26).

Top 10 exact gap causes:

| kind | fragment | cards | sole-cause cards |
|---|---|---:|---:|
| unread | otherwise | 65 | 53 |
| unread | {tk}{tk} — N/N | 44 | 0 |
| unread | starting with you | 35 | 3 |
| cond | ~ is paired with another creature | 24 | 24 |
| cond | it remains exiled | 23 | 13 |
| unread | {tk}{tk}{tk} — N/N | 22 | 0 |
| trigger | when ~ specializes | 19 | 17 |
| unread | empower jace N | 18 | 10 |
| effect | GenericEffect[?] | 18 | 10 |
| unread | open an attraction | 17 | 9 |

### Below the 5-member minimum (cause 5)

- Primary-cause cards 1,155, 1,220 blocking abilities. Best similarity of a card's closest blocking ability to any leaf: 0.70-0.90 194, 0.30-0.50 209, 0.50-0.70 654, no leaf of that effect type 52, <0.30 25, >=0.90 21.
- Nearest leaves: Put +1/+1 counters on this permanent (40); Destroy a land (27); Sacrifice a creature (21); Create a token copy of a creature you control (18); Reveal cards until one matches (land) (15); A creature becomes a copy (14); Untap a creature (12); A permanent gains an ability until end of turn (11); Gain control of a creature (10); Exile all cards from a graveyard (10).
- At a minimum of 3 (measured, not built): **792 cards** have a blocking ability that would place; **767** have every blocking ability placing; 814 abilities have a leaf at 3 and not at 5.

### Dropped-condition holds (cause 3)

- Flagged abilities in the pile: 1,673. If every sub-shape were fixed and they then matched like any clean ability: 963 would place in an unflagged leaf, 317 only in a broad leaf, 393 still would not. **729 pile cards on clean cards would move**; 208 gap cards would gain a placeable ability (they would still need the gap-card tests to pass). **Estimate**: the real figure is lower, because a kept condition makes the signature more specific.

| shape | sub-shape | items | place (unflagged) | broad | still no | on gap cards | clean cards moved | gap cards with a placeable ability |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| sequential-chain | later sentence 'If X, B.' | 396 | 229 | 78 | 89 | 143 | 169 | 54 |
| trigger-intervening | intervening if | 335 | 177 | 86 | 72 | 91 | 151 | 20 |
| result-dependent | this way / if you do | 214 | 125 | 36 | 53 | 73 | 99 | 26 |
| sequential-chain | inline 'A if X.' | 149 | 74 | 36 | 39 | 76 | 38 | 34 |
| embedded-replacement | 'if X would Y, Z instead' inside an ability | 129 | 53 | 28 | 48 | 46 | 46 | 6 |
| sequential-chain | if ... instead | 105 | 67 | 20 | 18 | 53 | 36 | 30 |
| compound | two conditions joined by or / and | 52 | 29 | 13 | 10 | 17 | 19 | 10 |
| replacement-level | enters tapped / with counters if | 43 | 39 | 0 | 4 | 1 | 38 | 1 |
| filter-targeting | restriction on the target ('X target Y if it ...') | 40 | 34 | 1 | 5 | 8 | 26 | 6 |
| result-dependent | search this way -> shuffle (benign) | 39 | 28 | 3 | 8 | 6 | 28 | 0 |
| negative | declined option ('may/pay ... if you don't') | 38 | 20 | 7 | 11 | 9 | 16 | 4 |
| result-dependent | if you win/lose | 34 | 18 | 2 | 14 | 12 | 12 | 6 |
| negative | negated event/state ('if you didn't ...') | 21 | 8 | 5 | 8 | 6 | 6 | 2 |
| static-level | Panharmonicon | 16 | 16 | 0 | 0 | 3 | 13 | 3 |
| branch-structural | FlipCoin sub_ability outside the branch | 10 | 9 | 0 | 1 | 5 | 5 | 4 |
| static-level | ReduceCost | 9 | 9 | 0 | 0 | 1 | 8 | 1 |
| static-level | GraveyardCastPermission | 9 | 5 | 0 | 4 | 1 | 4 | 1 |
| replacement-level | other replacement | 7 | 3 | 1 | 3 | 1 | 3 | 0 |
| static-level | Continuous | 6 | 5 | 1 | 0 | 1 | 5 | 0 |
| static-level | CastWithFlash | 5 | 5 | 0 | 0 | 2 | 3 | 2 |
| activation-restriction-missing | 'Activate only if' with no restriction at all | 5 | 1 | 0 | 4 | 5 | 0 | 1 |
| static-level | CantAttack | 4 | 4 | 0 | 0 | 0 | 4 | 0 |
| replacement-level | damage prevention / modification | 2 | 0 | 0 | 2 | 2 | 0 | 0 |
| static-level | CantBlock | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| static-level | CantBeCountered | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| static-level | CantAttackOrBlock | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| static-level | RaiseCost | 1 | 1 | 0 | 0 | 0 | 1 | 0 |

### Gap-card tests (what they hold back)

- 601 gap-card abilities fail a test. If a test were dropped they would match: gap_card_continuation_gap -> unplaced 40, placed 215, broad 35; gap_card_no_text -> broad 31, placed 157, unplaced 28; gap_card_same_line_gap -> placed 83, broad 7, unplaced 5. 359 pile gap cards have such an ability matching an unflagged leaf. dropping a test is what the Spark Double pattern warns against: these are the cases the tests exist to keep out

### Other causes

- Unparsed or parse mistake: 35 cards (known_parse_mistake 8, not_parsed 27). Modal / no signature: 1. No effect: 22.

### Ten sample cards per cause (seeded)

**1 parser gap**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Aurification | Each creature with a gold counter on it is a Wall in addition to its other creature types and has defender. | gap: unread: each creature with a gold counter on it is a wall in additio |  |
| Rampaging Cyclops | ~ gets -2/-0 as long as two or more creatures are blocking it. | gap: cond: two or more creatures are blocking it |  |
| Animal Attendant |  | gap: unread: that creature enters with an additional +N/+N counter on it |  |
| Verrak, Warped Sengir |  | gap: unread: pay that much life again; trigger: whenever you activate an ability that isn't a mana ability |  |
| Last Light of Durin's Day | Whenever a Mountain you control enters, put a quest counter on this enchantment. If it has six or more quest c | gap: unread: search your hand and/or library for a dragon card |  |
| Solemnity | Players can't get counters. | gap: unread: counters can't be put on artifacts, creatures, enchantments,; unread: players can't get counters |  |
| Cyber Conversion | Turn target creature face down. It's a 2/2 Cyberman artifact creature. | gap: unread: it's a N/N cyberman artifact creature; unread: turn target creature face down |  |
| Cytoshape | Choose a nonlegendary creature on the battlefield. Target creature becomes a copy of that creature until end o | gap: unread: choose a nonlegendary creature on the battlefield |  |
| Lantern Flare | Lantern Flare deals X damage to target creature or planeswalker and you gain X life. [X is the number of creat | gap: unread: [x is the number of creatures you control; unread: ] |  |
| Unglued Pea-Brained Dinosaur | {TK}{TK} — {T}: Add {2}. Spend this mana only to cast creature spells. | gap: unread: add {N}; unread: spend this mana only to cast creature spells |  |

**2 unparsed or parse mistake**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Fix What's Broken | Return each artifact and creature card with mana value X from your graveyard to the battlefield. | known_parse_mistake / not_in_scope:corrections_flagged |  |
| Talara's Battalion |  | not_parsed |  |
| Putrid Raptor |  | not_parsed |  |
| Ruthless Radrat |  | not_parsed |  |
| Toxic Deluge | All creatures get -X/-X until end of turn. | known_parse_mistake / not_in_scope:corrections_flagged |  |
| Raging Goblinoids |  | not_parsed |  |
| Spark Double | You may have this creature enter as a copy of a creature or planeswalker you control, except it enters with an | known_parse_mistake / flagged_condition_drop |  |
| Zombie Cutthroat |  | not_parsed |  |
| Illusory Angel |  | not_parsed |  |
| Oversoul of Dusk |  | not_parsed |  |

**3 dropped-condition hold**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Shantotto, Tactician Magician | Whenever you cast a noncreature spell, Shantotto gets +X/+0 until end of turn, where X is the amount of mana s | dropped condition: later sentence 'If X, B.' | would match: This permanent gets +N/+N until end of turn |
| Tower Winder | When this creature enters, search your library and/or graveyard for a card named Command Tower, reveal it, and | dropped condition: search this way -> shuffle (benign) | would match: Search your library for a card and put it into your hand (then move a chosen card and shuffle) |
| Slumbering Trudge | This creature enters with a number of stun counters on it equal to three minus X. If X is 2 or less, it enters | dropped condition: enters tapped / with counters if | would match: Enters tapped |
| Holy Justiciar | {2}{W}, {T}: Tap target creature. If that creature is a Zombie, exile it. | dropped condition: later sentence 'If X, B.' | would match: Tap a creature |
| Tuktuk Scrapper | Whenever this creature or another Ally you control enters, you may destroy target artifact. If that artifact i | dropped condition: this way / if you do | would match: Destroy an artifact |
| Harmonic Prodigy | If a triggered ability of a Shaman or another Wizard you control triggers, that ability triggers an additional | dropped condition: Panharmonicon | would match: Triggered abilities trigger an extra time |
| Marcus, Mutant Mayor | Whenever a creature you control deals combat damage to a player, draw a card if that creature has a +1/+1 coun | dropped condition: inline 'A if X.' | would only reach a broad leaf |
| Sabertooth Outrider | Whenever this creature attacks, if creatures you control have total power 8 or greater, this creature gains fi | dropped condition: intervening if | would match: A permanent gains first strike until end of turn |
| Feed the Flames | Feed the Flames deals 5 damage to target creature. If that creature would die this turn, exile it instead. | dropped condition: 'if X would Y, Z instead' inside an ability | would match: Deal damage to a creature |
| Celestial Reunion | Search your library for a creature card with mana value X or less, reveal it, put it into your hand, then shuf | dropped condition: Continuous | would match: This permanent is changed: add chosen subtype |

**4 gap-card ability still unplaced**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Unbreakable Formation | Creatures you control gain indestructible until end of turn. | gap_card_continuation_gap |  |
| Break Ties |  | gap_card_no_text |  |
| What Must Be Done |  | gap_card_no_text |  |
| Liliana, Death's Majesty | [+1]: Create a 2/2 black Zombie creature token. Mill two cards. | gap_card_continuation_gap |  |
| Tahngarth, First Mate | ~ can't be blocked by more than one creature. | gap_card_continuation_gap |  |
| Kozilek's Command |  | gap_card_no_text |  |
| Nils, Discipline Enforcer | Each creature with one or more counters on it can't attack you or planeswalkers you control unless its control | gap_card_continuation_gap |  |
| Fishing Pole |  | gap_card_no_text |  |
| Gladewalker Ritualist |  | gap_card_no_text |  |
| Soulfire Grand Master | Instant and sorcery spells you control have lifelink. | gap_card_continuation_gap |  |

**5 below the 5-member minimum**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Waxing Moon | Transform up to one target Werewolf you control. Creatures you control gain trample until end of turn. | rare_object | nearest leaf 0.29: Transform this permanent |
| Rite of Renewal | Return up to two target permanent cards from your graveyard to your hand. Target player shuffles up to four ta | below_minimum_size | nearest leaf 0.71: Return permanents from your graveyard to its owner's hand (several) — “all” vs “target” isn't recorded |
| Urborg Syphon-Mage | {2}{B}, {T}, Discard a card: Each other player loses 2 life. You gain life equal to the life lost this way. | rare_object | nearest leaf 0.67: Lose life, then gain life (permanent; an opponent controls) — who loses or gains it isn't recorded |
| Treasure Keeper | When this creature dies, reveal cards from the top of your library until you reveal a nonland card with mana v | rare_object | nearest leaf 0.33: Reveal cards until one matches (land) |
| Outlaw Stitcher | When this creature enters, create a 2/2 blue and black Zombie Rogue creature token, then put two +1/+1 counter | below_minimum_size | nearest leaf 0.60: Create Fractal tokens, then put +1/+1 counters on it |
| Timebender | When this creature is turned face up — Remove two time counters from target permanent or suspended card. | rare_verb_parameter | nearest leaf 0.75: Remove counters from a permanent |
| Eardrum Rattler | {1}, {T}: Another target creature you control with power 2 or less can't be blocked this turn. | below_minimum_size | nearest leaf 0.71: A creature can't be blocked until end of turn |
| Shields Up! | Target artifact or creature you control gains hexproof and indestructible until end of turn. If it's a creatur | below_minimum_size | nearest leaf 0.62: A permanent gains a keyword until end of turn (you control) |
| Massacre Girl | When Massacre Girl enters, each other creature gets -1/-1 until end of turn. Whenever a creature dies this tur | below_minimum_size | nearest leaf 0.71: All creatures get −N/−N until end of turn (restriction varies) |
| Assemble the Legion | At the beginning of your upkeep, put a muster counter on this enchantment. Then create a 1/1 red and white Sol | rare_verb_parameter | nearest leaf 0.67: Put +1/+1 counters on this permanent, then create a token |

**6 modal / no signature / no family**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Veilstone Amulet | Whenever you cast a spell, creatures you control can't be the targets of spells or abilities your opponents co | too_unusual / no_signature |  |

**7 no effect or vanilla extension**

| card | ability text | reason | would sit in (measured) |
|---|---|---|---|
| Adrix and Nev, Twincasters | If one or more tokens would be created under your control, twice that many of those tokens are created instead | no_effect_to_group / replacement_group |  |
| Mirror Strike | All combat damage that would be dealt to you this turn by target unblocked creature is dealt to its controller | no_effect_to_group / replacement_group |  |
| Divine Presence | If a source would deal 4 or more damage to a permanent or player, that source deals 3 damage to that permanent | no_effect_to_group / replacement_group |  |
| Exquisite Archangel | If you would lose the game, instead exile this creature and your life total becomes equal to your starting lif | no_effect_to_group / replacement_group |  |
| Exalted Sunborn | If one or more tokens would be created under your control, twice that many of those tokens are created instead | no_effect_to_group / replacement_group |  |
| Lich's Mirror | If you would lose the game, instead shuffle your hand, your graveyard, and all permanents you own into your li | no_effect_to_group / replacement_group |  |
| Turn the Tables | All combat damage that would be dealt to you this turn is dealt to target attacking creature instead. | no_effect_to_group / replacement_group |  |
| Pariah | All damage that would be dealt to you is dealt to enchanted creature instead. | no_effect_to_group / replacement_group |  |
| Eye for an Eye | The next time a source of your choice would deal damage to you this turn, instead that source deals that much  | no_effect_to_group / replacement_group |  |
| Reflect Damage | The next time a source of your choice would deal damage this turn, that damage is dealt to that source's contr | no_effect_to_group / replacement_group |  |

## 4. Popularity

Field: edhrec_rank (Scryfall oracle_cards export); lower is more popular. Cumulative: a top-1,000 card is also in the top 3,000 and 10,000.

| primary cause | cards | top 1,000 | top 3,000 | top 10,000 | no rank |
|---|---:|---:|---:|---:|---:|
| 1 parser gap | 3,313 | 45 | 211 | 930 | 370 |
| 2 unparsed or parse mistake | 35 | 2 | 3 | 8 | 0 |
| 3 dropped-condition hold | 1,067 | 16 | 70 | 286 | 27 |
| 4 gap-card ability still unplaced | 0 | 0 | 0 | 0 | 0 |
| 5 below the 5-member minimum | 1,155 | 36 | 126 | 373 | 36 |
| 6 modal / no signature / no family | 1 | 0 | 0 | 0 | 0 |
| 7 no effect or vanilla extension | 22 | 1 | 4 | 7 | 0 |
| 8 other | 0 | 0 | 0 | 0 | 0 |
| all | 5,593 | 100 | 414 | 1604 | 433 |

## 5. Browse-only family subgroups, on paper

- Pile cards with at least one ability whose effect type maps to a family of the tree: **4,293** of 5,593; **1,300 have no family** (1 parser gap 1234, 7 no effect or vanilla extension 22, 2 unparsed or parse mistake 35, 3 dropped-condition hold 8, 6 modal / no signature / no family 1).
- Per family if a card may appear under several: Zone change 598; Pump / grant 536; Counters 455; Library 450; Static: continuous 404; Damage 280; Tokens 257; Card draw 237; Destroy 207; Sacrifice 136; Tap / untap 125; Life 121; Discard / hand 112; Static: restriction 88.
- Per family if each card goes to its most common family: Zone change 505; Pump / grant 501; Counters 433; Library 433; Static: continuous 330; Damage 266; Card draw 236; Tokens 208; Destroy 194; Sacrifice 119; Discard / hand 107; Life 106; Tap / untap 102; Copy 80.

- Zone change effect types: ChangeZone 452, Bounce 135, PutAtLibraryPosition 14, PhaseOut 13, Shuffle 5, PutOnTopOrBottom 1.
- Pump / grant effect types: GenericEffect 330, Pump 209, DoublePT 6, BlightEffect 3, SwitchPT 1.
- Counters effect types: PutCounter 420, RemoveCounter 46, GivePlayerCounter 19, MoveCounters 10, Double 8, GainEnergy 5, MultiplyCounter 3, Proliferate 2, Monstrosity 2.

Twenty cards read from each of the three largest:

**Zone change**

| card | mapped ability | effect type | primary cause |
|---|---|---|---|
| Teferi's Veil | Whenever a creature you control attacks, it phases out at end of combat. | PhaseOut | 5 below the 5-member minimum |
| Guardians of Koilos | When this creature enters, you may return another target historic permanent you control to its owner's hand. | Bounce | 5 below the 5-member minimum |
| Mindleech Ghoul | When this creature exploits a creature, each opponent exiles a card from their hand. | ChangeZone | 5 below the 5-member minimum |
| Surgical Extraction | Choose target card in a graveyard other than a basic land card. Search its owner's graveyard, hand, and library for any number of  | ChangeZone | 5 below the 5-member minimum |
| Foreboding Steamboat | When this Vehicle enters, each player chooses two nontoken, non-Vehicle creatures they control. Exile them until this Vehicle leav | ChangeZone | 5 below the 5-member minimum |
| Warren Pilferers | When this creature enters, return target creature card from your graveyard to your hand. If that card is a Goblin card, this creat | Bounce | 3 dropped-condition hold |
| Grey Host Reinforcements | When this creature enters, exile target player's graveyard. Put a number of +1/+1 counters on this creature equal to the number of | ChangeZone | 1 parser gap |
| Abstruse Appropriation | Exile target nonland permanent. You may cast that card for as long as it remains exiled, and you may spend colorless mana as thoug | ChangeZone | 1 parser gap |
| Mistcaller | Sacrifice this creature: Until end of turn, if a nontoken creature would enter and it wasn't cast, exile it instead. | ChangeZone | 3 dropped-condition hold |
| Tezzeret's Reckoning | Exile three random cards from your library face down and look at them. For as long as they remain exiled, you may play one of thos | ChangeZone | 1 parser gap |
| Talion's Throneguard | When Talion's Throneguard enters, return up to one target spell or nonland permanent to its owner's hand. If Talion's Throneguard  | Bounce | 1 parser gap |
| Web of Inertia | At the beginning of combat on each opponent's turn, that player may exile a card from their graveyard. If the player doesn't, crea | ChangeZone | 1 parser gap |
| Barrin's Unmaking | Return target permanent to its owner's hand if that permanent shares a color with the most common color among all permanents or a  | Bounce | 3 dropped-condition hold |
| Driftgloom Coyote | When this creature enters, exile target creature an opponent controls until this creature leaves the battlefield. If that creature | ChangeZone | 3 dropped-condition hold |
| Wanderwine Farewell | Return one or two target nonland permanents to their owners' hands. Then if you control a Merfolk, create a 1/1 white and blue Mer | Bounce | 3 dropped-condition hold |
| Skeleton Shard | {3}, {T} or {B}, {T}: Return target artifact creature card from your graveyard to your hand. | Bounce | 1 parser gap |
| Meticulous Excavation | {2}{W}: Return target permanent you control to its owner's hand. If it has unearth, instead exile it, then return that card to its | Bounce | 1 parser gap |
| Yorion, Sky Nomad | When Yorion enters, exile any number of other nonland permanents you own and control. Return those cards to the battlefield at the | ChangeZone | 5 below the 5-member minimum |
| Bank Job | At the beginning of your upkeep, exile the bottom creature card of your library. You may cast that card this turn. At the beginnin | ChangeZone | 3 dropped-condition hold |
| Yedora, Grave Gardener | Whenever another nontoken creature you control dies, you may return it to the battlefield face down under its owner's control. It' | ChangeZone | 1 parser gap |

**Pump / grant**

| card | mapped ability | effect type | primary cause |
|---|---|---|---|
| Wizened Githzerai | Whenever Wizened Githzerai becomes blocked by a creature, that creature perpetually gets -2/-0. | Pump | 5 below the 5-member minimum |
| Canopy Dragon | {1}{G}: This creature gains flying and loses trample until end of turn. | GenericEffect | 5 below the 5-member minimum |
| Momentum Rumbler | Whenever this creature attacks, if it has first strike, it gains double strike until end of turn. | GenericEffect | 1 parser gap |
| Quicksmith Rebel | When this creature enters, target artifact you control gains "{T}: This artifact deals 2 damage to any target" for as long as you  | GenericEffect | 5 below the 5-member minimum |
| Quicksmith Spy | When this creature enters, target artifact you control gains "{T}: Draw a card" for as long as you control this creature. | GenericEffect | 5 below the 5-member minimum |
| Sylvan Awakening | Until your next turn, all lands you control become 2/2 Elemental creatures with reach, indestructible, and haste. They're still la | GenericEffect | 5 below the 5-member minimum |
| Cry of the Carnarium | All creatures get -2/-2 until end of turn. Exile all creature cards in all graveyards that were put there from the battlefield thi | Pump | 3 dropped-condition hold |
| Aethershield Artificer | At the beginning of combat on your turn, target artifact creature you control gets +2/+2 and gains indestructible until end of tur | GenericEffect | 5 below the 5-member minimum |
| Dementia Sliver |  | GenericEffect | 1 parser gap |
| Distorting Lens | {T}: Target permanent becomes the color of your choice until end of turn. | GenericEffect | 5 below the 5-member minimum |
| Opal Archangel | When an opponent casts a creature spell, if this permanent is an enchantment, it becomes a 5/5 Angel creature with flying and vigi | GenericEffect | 5 below the 5-member minimum |
| Forerunner of Slaughter | {1}: Target colorless creature gains haste until end of turn. | GenericEffect | 5 below the 5-member minimum |
| Sassy Gremlin Blood | {TK}{TK}{TK}{TK}{TK} — {3}: Target creature gains flying until end of turn. | GenericEffect | 1 parser gap |
| Kjeldoran Guard | {T}: Target creature gets +1/+1 until end of turn. When that creature leaves the battlefield this turn, sacrifice this creature. A | Pump | 1 parser gap |
| Sickle Dancer | Whenever this creature attacks, if your team controls another Warrior, this creature gets +1/+1 until end of turn. | Pump | 3 dropped-condition hold |
| Jaded Sell-Sword | When this creature enters, if mana from a Treasure was spent to cast it, it gains first strike and haste until end of turn. | GenericEffect | 3 dropped-condition hold |
| Agatha's Soul Cauldron |  | GenericEffect | 1 parser gap |
| Soulbright Seeker | {R}: Target creature you control gains trample until end of turn. If this is the third time this ability has resolved this turn, a | GenericEffect | 3 dropped-condition hold |
| Lulu, Wild Hollyphant | Whenever you attack with one or more other creatures with flying, those creatures get +2/+2 until end of turn. | Pump | 5 below the 5-member minimum |
| Savage Swipe | Target creature you control gets +2/+2 until end of turn if its power is 2. Then it fights target creature you don't control. | Pump | 3 dropped-condition hold |

**Counters**

| card | mapped ability | effect type | primary cause |
|---|---|---|---|
| Summon: Fenrir | Saga ETB lore counter | PutCounter | 1 parser gap |
| Life Matrix | {4}, {T}: Put a matrix counter on target creature and that creature gains "Remove a matrix counter from this creature: Regenerate  | PutCounter | 1 parser gap |
| Aquitect's Will | Put a flood counter on target land. That land is an Island in addition to its other types for as long as it has a flood counter on | PutCounter | 1 parser gap |
| Master Biomancer | Each other creature you control enters with a number of additional +1/+1 counters on it equal to this creature's power and as a Mu | PutCounter | 5 below the 5-member minimum |
| Codespell Cleric | When this creature enters, if it was the second spell you cast this turn, put a +1/+1 counter on target creature. | PutCounter | 3 dropped-condition hold |
| Ajani, the Greathearted | [−2]: Put a +1/+1 counter on each creature you control and a loyalty counter on each other planeswalker you control. | PutCounter | 1 parser gap |
| Way of the Mentor | Whenever you gain life, put a loyalty counter on each planeswalker you control. | PutCounter | 1 parser gap |
| Swamp Mosquito | Whenever this creature attacks and isn't blocked, defending player gets a poison counter. | GivePlayerCounter | 5 below the 5-member minimum |
| Musician | {T}: Put a music counter on target creature. If it doesn't have "At the beginning of your upkeep, destroy this creature unless you | PutCounter | 1 parser gap |
| Support Mission | Whenever a creature you control enters, put a quest counter on this enchantment. Put a +1/+1 counter on that creature. If this enc | PutCounter | 1 parser gap |
| Sharp-Eyed Rookie | Whenever a creature you control enters, if its power is greater than this creature's power or its toughness is greater than this c | PutCounter | 3 dropped-condition hold |
| Evolutionary Escalation | At the beginning of your upkeep, put three +1/+1 counters on target creature you control and three +1/+1 counters on target creatu | PutCounter | 1 parser gap |
| Fate Transfer | Move all counters from target creature onto another target creature. | MoveCounters | 5 below the 5-member minimum |
| Decorated Champion | Whenever another Warrior your team controls enters, put a +1/+1 counter on this creature. | PutCounter | 1 parser gap |
| Blue, Loyal Raptor | For each kind of counter on Blue, Loyal Raptor, each other Dinosaur you control enters with a counter of that kind on it. | PutCounter | 5 below the 5-member minimum |
| Nazar, the Velvet Fang | Whenever you gain life, put a feeding counter on Nazar. | PutCounter, RemoveCounter | 5 below the 5-member minimum |
| Boreal Outrider | Whenever you cast a creature spell, if {S} of any of that spell's colors was spent to cast it, that creature enters with an additi | PutCounter | 3 dropped-condition hold |
| Freyalise's Winds | Whenever a permanent becomes tapped, put a wind counter on it. | PutCounter, RemoveCounter | 5 below the 5-member minimum |
| Collector's Cage | {1}, {T}: Put a +1/+1 counter on target creature you control. Then if you control three or more creatures with different powers, y | PutCounter | 3 dropped-condition hold |
| Wall of Resistance | At the beginning of each end step, if this creature was dealt damage this turn, put a +0/+1 counter on it. | PutCounter | 3 dropped-condition hold |

## 6. Fix sets and their overlap (measured)

- Minimum of 3: 792 cards. Dropped-condition fixes: 729 pile cards on clean cards, plus 208 gap cards. Relaxing a gap-card test: 359 gap cards. Pairwise overlaps: min3 and cond 0, min3 and tests 0, cond and tests 24. **Union of the four placement fixes: 2,064 cards (the plain sum is 2,088).** Browse-only family subgroups: 4,293 cards, of which 2,064 are also in one of the placement fixes.

