# Restriction-condition worklist (round B)

133 restriction/option conditions on **131 cards** are kept as `ParsedCondition::Unrecognized` (round 1, a visibility fix). 116 distinct phrasings once numbers are normalised. Fixing one means a real phrase parser (and usually a new `ParsedCondition` variant); the engine currently evaluates all of them as `true`.

| rank | family | cards | activation | casting restriction | casting option |
|---:|---|---:|---:|---:|---:|
| 1 | singletons / other | 39 | 28 | 1 | 11 |
| 2 | "this turn" / "this combat" events | 36 | 21 | 3 | 12 |
| 3 | graveyard / hand / exile counts | 20 | 20 | 0 | 0 |
| 4 | source state / self-name | 15 | 9 | 2 | 4 |
| 5 | counters on a permanent | 10 | 9 | 0 | 1 |
| 6 | land counts | 6 | 6 | 0 | 0 |
| 7 | city's blessing | 3 | 3 | 0 | 0 |
| 8 | life totals | 3 | 3 | 0 | 0 |

**Timing clauses swallowed into the text.**
Round B1 split the timing clause out of 22 cards' compound "Activate only <timing> and only if <condition>" sentences (AsSorcery, DuringYourTurn, DuringYourUpkeep, DuringCombat, OnlyOnceEachTurn, OnlyOnce are now emitted -- and enforced by the engine); their `if` remainders stay `Unrecognized` and appear below. Still swallowed, by design of that round:
- **19 activation texts** (18 whole blobs plus Grizzled Wolverine's leftover piece) are a timing phrase that has NO equivalent `ActivationRestriction` yet: during the declare blockers / declare attackers / end-of-combat step, during an opponent's turn / upkeep, during any upkeep step, before blockers are declared, before the end of combat / combat damage step, during combat after blockers are declared, and `before attackers are declared`. Each needs a new variant (reuse the `CastingRestriction` names: `DeclareBlockersStep`, `DeclareAttackersStep`, `DuringOpponentsTurn`, `DuringOpponentsUpkeep`, `DuringAnyUpkeep`, `BeforeBlockersDeclared`, ...) plus engine evaluation. Do NOT reuse `BeforeAttackersDeclared` for Norritt / Arcum's Whistle / Nettling Imp: it requires the active player to hold priority, but those are opponent-turn abilities; `BeforeCombatDamage` means "during combat before damage", not Angus Mackenzie's "before the combat damage step".
- **8 activation texts** have the mirror form "<condition> and only as a sorcery" (Balustrade Wurm, Resurrected Cultist, Speaker of the Heavens, Temple of Civilization / Cyclical Time / Power / the Dead, Uchbenbak): they reach the `activate only if ` branch, where `strip_once_per_turn_suffix` strips "and only once (each turn)" but not "and only as a sorcery", so `AsSorcery` is swallowed the same way. Not touched in B1; the same split applies.
- Parseable remainders were deliberately NOT parsed in B1: the existing condition parser would give some of them a wrong, then-enforced meaning ("you control a snow Mountain" becomes the subtype `snow mountain`; Urza's Fun House's three-land clause becomes one made-up subtype). Fix those parses before enabling them.

## singletons / other (39 cards)

- Groundling Pouncer [activation]: an opponent controls a creature with flying
- Submerge [casting option]: an opponent controls a forest and you control an island
- Sivvi's Ruse [casting option]: an opponent controls a mountain and you control a plains
- Massacre [casting option]: an opponent controls a plains and you control a swamp
- Refreshing Rain [casting option]: an opponent controls a swamp and you control a forest
- Mogg Salvage [casting option]: an opponent controls an island and you control a mountain
- Arcum's Whistle [activation]: before attackers are declared
- Norritt [activation]: before attackers are declared
- Acidic Dagger [activation]: before blockers are declared
- Angus Mackenzie [activation]: before the combat damage step
- Dwarven Sea Clan [activation]: before the end of combat step
- Lavinia, Foil to Conspiracy [activation]: during an opponent's turn
- Maddening Imp [activation]: during an opponent's turn and only before combat
- Nettling Imp [activation]: during an opponent's turn, before attackers are declared
- Trade Caravan [activation]: during an opponent's upkeep
- Dwarven Armory [activation]: during any upkeep step
- Tolaria [activation]: during any upkeep step
- Trap Runner [activation]: during combat after blockers are declared
- Nemesis Phoenix [activation]: during the declare attackers step and only if you're attacking two or more opponents
- Balduvian Warlord [activation]: during the declare blockers step
- General Jarkeld [activation]: during the declare blockers step
- Grizzled Wolverine [activation]: during the declare blockers step
- Lesser Werewolf [activation]: during the declare blockers step
- Desert [activation]: during the end of combat step
- Nature's Chosen [activation]: enchanted creature is white and untapped
- Arrow Volley Trap [casting option]: four or more creatures are attacking
- Syr Cadian, Knight Owl [activation]: from sunrise to sunset
- Syr Cadian, Knight Owl [activation]: from sunset to sunrise
- Flash Photography [casting option]: it targets a permanent you control
- Puca's Eye [activation]: there are five colors among permanents you control
- Blasphemous Edict [casting option]: there are thirteen or more creatures on the battlefield
- Checks and Balances [casting restriction]: there are three or more players in the game
- Lethargy Trap [casting option]: three or more creatures are attacking
- Silver Scrutiny [casting option]: x is 3 or less
- Molten Exhale [casting option]: you behold a dragon as an additional cost to cast it
- Goblin Ski Patrol [activation]: you control a snow mountain
- Coffin Puppets [activation]: you control a swamp
- Urza's Fun House [activation]: you control an urza's mine, an urza's power-plant, and an urza's tower
- Kuldotha Phoenix [activation]: you control three or more artifacts
- Sarevok's Tome [activation]: you've completed a dungeon

## "this turn" / "this combat" events (36 cards)

- Lilypad Village [activation]: a bird, frog, otter, or rat entered the battlefield under your control this turn
- Essence Anchor [activation]: a card left your graveyard this turn
- Cult Conscript [activation]: a non-skeleton creature died under your control this turn
- Cobra Trap [casting option]: a noncreature permanent under your control was destroyed this turn by a spell or ability an opponent controlled
- Ricochet Trap [casting option]: an opponent cast a blue spell this turn
- Lure of Prey [casting restriction]: an opponent cast a creature spell this turn
- Refraction Trap [casting option]: an opponent cast a red instant or sorcery spell this turn
- Mindbreak Trap [casting option]: an opponent cast three or more spells this turn
- Runeflare Trap [casting option]: an opponent drew three or more cards this turn
- Permafrost Trap [casting option]: an opponent had a green creature enter the battlefield under their control this turn
- Baloth Cage Trap [casting option]: an opponent had an artifact enter the battlefield under their control this turn
- Ravenous Trap [casting option]: an opponent had three or more cards put into their graveyard from anywhere this turn
- Whiplash Trap [casting option]: an opponent had two or more creatures enter the battlefield under their control this turn
- Lavaball Trap [casting option]: an opponent had two or more lands enter the battlefield under their control this turn
- Gutterbones [activation]: an opponent lost life this turn
- Blitzball [activation]: an opponent was dealt combat damage by a legendary creature this turn
- Skarrgan Firebird [activation]: an opponent was dealt damage this turn
- Kongming's Contraptions [activation]: during the declare attackers step and only if you've been attacked this step
- Lagomos, Hand of Hatred [activation]: five or more creatures died this turn
- Temple of Power [activation]: red sources you controlled dealt 4 or more noncombat damage this turn and only as a sorcery
- Master's Manufactory [activation]: this artifact or another artifact entered the battlefield under your control this turn
- Sea Troll [activation]: this creature blocked or was blocked by a blue creature this turn
- Bonecache Overseer [activation]: three or more cards left your graveyard this turn or if you've sacrificed a food this turn
- Diamond City [activation]: two or more creatures entered the battlefield under your control this turn
- Temple of Civilization [activation]: you attacked with three or more creatures this turn and only as a sorcery
- Zhalfirin Decoy [activation]: you had a creature enter the battlefield under your control this turn
- Cleaving Reaper [activation]: you had an angel or berserker enter the battlefield under your control this turn
- Suffocation [casting restriction]: you were dealt damage this turn by a red instant or sorcery spell
- Inferno Trap [casting option]: you've been dealt damage by two or more creatures this turn
- Hall of Oracles [activation]: you've cast an instant or sorcery spell this turn
- Potioner's Trove [activation]: you've cast an instant or sorcery spell this turn
- Sanar, Unfinished Genius [activation]: you've cast an instant or sorcery spell this turn
- Talara's Battalion [casting restriction]: you've cast another green spell this turn
- Patrician's Scorn [casting option]: you've cast another white spell this turn
- Urabrask [activation]: you've cast three or more instant and/or sorcery spells this turn
- Izzet Generatorium [activation]: you've paid or lost four or more {e} this turn

## graveyard / hand / exile counts (20 cards)

- Temple of the Dead [activation]: a player has one or fewer cards in hand and only as a sorcery
- Merfolk Windrobber [activation]: an opponent has eight or more cards in their graveyard
- Sheoldred [activation]: an opponent has eight or more cards in their graveyard
- Deadhead [activation]: an opponent isn't touching their hand
- Diminished Returner [activation]: diminished returner is in your graveyard and its toughness is 2 or greater
- Shellfish Scholar [activation]: seven or more cards are in your graveyard
- Skyblade's Boon [activation]: skyblade's boon is on the battlefield or in your graveyard
- Cavernous Maw [activation]: the number of other caves you control plus the number of cave cards in your graveyard is three or greater
- Tomb Tyrant [activation]: there are at least three zombie creature cards in your graveyard
- Uchbenbak, the Great Mistake [activation]: there are eight or more permanent cards in your graveyard and only as a sorcery
- Balustrade Wurm [activation]: there are four or more card types among cards in your graveyard and only as a sorcery
- Resurrected Cultist [activation]: there are four or more card types among cards in your graveyard and only as a sorcery
- Shadows of the Past [activation]: there are four or more creature cards in your graveyard
- Matzalantli, the Great Door [activation]: there are four or more permanent types among cards in your graveyard
- Cabal Inquisitor [activation]: there are seven or more cards in your graveyard
- Gate to the Afterlife [activation]: there are six or more creature cards in your graveyard
- Dread Wanderer [activation]: you have one or fewer cards in hand
- Jin-Gitaxias [activation]: you have seven or more cards in hand
- Resonating Lute [activation]: you have seven or more cards in your hand
- Dreadlight Monstrosity [activation]: you own a card in exile

## source state / self-name (15 cards)

- Slingbow Trap [casting option]: a black creature with flying is attacking
- Fated Clash [casting option]: a creature is attacking and a creature is blocking
- Confront the Assault [casting restriction]: a creature is attacking you
- Nemesis Trap [casting option]: a white creature is attacking
- Grizzled Wolverine [activation]: at least one creature is blocking this creature
- Pitfall Trap [casting option]: exactly one creature is attacking
- Gerrard Capashen [activation]: gerrard capashen is attacking
- Hakim, Loreweaver [activation]: hakim isn't enchanted
- Ghost Town [activation]: it's not your turn
- Kitsa, Otterball Elite [activation]: kitsa's power is 3 or greater
- Tidal Influence [casting restriction]: no permanents named tidal influence are on the battlefield
- Second Little Pig [activation]: second little pig isn't a spirit
- Chronatog Totem [activation]: this permanent is a creature
- Ashen Ghoul [activation]: three or more creature cards are above this card
- Rocket Launcher [activation]: you've controlled this artifact continuously since the beginning of your most recent turn

## counters on a permanent (10 cards)

- Summoning Trap [casting option]: a creature spell you cast this turn was countered by a spell or ability an opponent controlled
- Churning Reservoir [activation]: an oil counter was removed from a permanent you controlled this turn or a permanent with an oil counter on it was put into a graveyard this turn
- Temple of Cyclical Time [activation]: it has no time counters on it and only as a sorcery
- Ice Cauldron [activation]: there are no charge counters on this artifact
- Jeweled Amulet [activation]: there are no charge counters on this artifact
- Edifice of Authority [activation]: there are three or more brick counters on this artifact
- Luxa River Shrine [activation]: there are three or more brick counters on this artifact
- Oracle's Vault [activation]: there are three or more brick counters on this artifact
- Pyramid of the Pantheon [activation]: there are three or more brick counters on this artifact
- Skarrgan Hellkite [activation]: this creature has a +1/+1 counter on it

## land counts (6 cards)

- Isolated Watchtower [activation]: an opponent controls at least two more lands than you
- Tectonic Edge [activation]: an opponent controls four or more lands
- Weathered Wayfarer [activation]: an opponent controls more lands than you
- Arcum's Sleigh [activation]: defending player controls a snow land
- Kjeldoran Guard [activation]: defending player controls no snow lands
- Monument to Perfection [activation]: there are nine or more lands with different names among the basic, sphere, and locus lands you control

## city's blessing (3 cards)

- Arch of Orazca [activation]: you have the city's blessing
- Orazca Relic [activation]: you have the city's blessing
- Timestream Navigator [activation]: you have the city's blessing

## life totals (3 cards)

- Bilbo, Birthday Celebrant [activation]: you have 111 or more life
- Ayli, Eternal Pilgrim [activation]: you have at least 10 life more than your starting life total
- Speaker of the Heavens [activation]: you have at least 7 life more than your starting life total and only as a sorcery
