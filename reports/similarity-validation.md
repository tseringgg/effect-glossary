# Word-overlap similarity — validation

Two deterministic modes over the deduped effect glossary (`data/full/effects.json`, reused as-is). No model, no curated MTG-term list.

- **raw** — plain Jaccard over token sets: `|A ∩ B| / |A ∪ B|`, every shared token worth 1.
- **weighted** — cosine between IDF-weighted token vectors, `idf = log(total_effects / effects_containing_token)`.

Tokenizing drops parenthetical reminder text, then a small ordinary-English stopword list (72 words: of/the/a/to/and/this/that/…). Nothing MTG-specific is stopworded — `target` and `creature` are discounted by their own IDF, which is the thing being tested.

**Card-name masking is on by default** (both modes): for effects belonging to exactly one card, words from that card's own name are excluded before scoring — see §1 below for why, and why it stops at singletons.

Every score below is exact: each probe is compared against all 42,445 effects with no candidate pruning.

## Corpus and IDF

| | tokens |
|---|---|
| **lowest IDF** — commonest, discounted with no help from anyone | `creature` 0.68 `you` 0.88 `target` 1.26 `control` 1.48 `your` 1.52 `turn` 1.60 `card` 1.61 `whenever` 1.70 `end` 1.92 `when` 1.97 `put` 1.99 `enters` 2.03 `until` 2.03 `damage` 2.13 |
| **named MTG terms, for scale** | `surveil` 5.53 `mill` 4.95 `mills` 5.06 `regenerated` 5.69 `lifelink` 4.68 `scry` 4.65 `destroy` 3.35 `exile` 2.73 `counter` 2.45 `damage` 2.13 `creature` 0.68 `target` 1.26 `you` 0.88 `card` 1.61 |

42,445 effects, 6,084 distinct tokens, 433,811 postings, median 10 tokens per effect (**with card-name masking already applied** — see §1 below). 186 effects tokenize to nothing (pure reminder text, nothing but stopwords, or — a handful — nothing left after their own name is masked out) and score 0 against everything under both modes.

## Named pairs

| pair | raw | weighted | shared tokens (token idf) |
|---|--:|--:|---|
| mill vs surveil | 0.000 | 0.000 | _none_ |
| mill vs mill (different number) | 0.667 | 0.721 | `mills` 5.1 `player` 2.3 `cards` 2.2 `target` 1.3 |
| mill vs mill (player vs opponent) | 0.429 | 0.522 | `mills` 5.1 `cards` 2.2 `target` 1.3 |
| surveil vs surveil (different number) | 0.333 | 0.787 | `surveil` 5.5 |
| wipe vs wipe: Day of Judgment / Wrath of God | 0.600 | 0.615 | `destroy` 3.3 `all` 3.1 `creatures` 2.4 |
| wipe vs wipe: Day of Judgment / Toxic Deluge | 0.250 | 0.437 | `all` 3.1 `creatures` 2.4 |
| wipe vs wipe: Day of Judgment / Blasphemous Act | 0.000 | 0.000 | _none_ |
| wipe vs unrelated: Day of Judgment / Giant Growth | 0.000 | 0.000 | _none_ |
| wipe vs unrelated: Day of Judgment / Llanowar Elves | 0.000 | 0.000 | _none_ |
| wipe vs single removal: Day of Judgment / Murder | 0.200 | 0.599 | `destroy` 3.3 |
| removal pair: Murder / Doom Blade | 0.750 | 0.501 | `destroy` 3.3 `target` 1.3 `creature` 0.7 |
| removal pair: Murder / Terror | 0.429 | 0.307 | `destroy` 3.3 `target` 1.3 `creature` 0.7 |
| removal pair: Swords to Plowshares / Path to Exile | 0.176 | 0.232 | `controller` 4.1 `target` 1.3 `creature` 0.7 |
| removal cross-mode: Murder / Swords to Plowshares | 0.222 | 0.072 | `target` 1.3 `creature` 0.7 |
| removal vs unrelated: Murder / Giant Growth | 0.250 | 0.080 | `target` 1.3 `creature` 0.7 |
| removal vs unrelated: Murder / Lightning Bolt | 0.111 | 0.034 | `target` 1.3 |

## Where the modes disagree

Found automatically: raw-mode top-8 neighbours whose weighted score is under half the raw score, or that clear raw 0.35 but miss weighted 0.50.

| probe | raw neighbour | raw | weighted | carried by low-IDF tokens |
|---|---|--:|--:|---|
| Board wipe (damage) | This creature deals π damage to each non-Clown creature. …<br><sub>Omniclown Colossus // Pie-roclasm</sub> | 0.600 | 0.111 | `creature` 0.7 |
| Counterspell | Counter target nonblue spell.<br><sub>Frazzle</sub> | 0.750 | 0.381 | `target` 1.3 |
| Board wipe (damage) | Spontaneous Combustion deals 3 damage to each creature.<br><sub>Spontaneous Combustion</sub> | 0.600 | 0.264 | `creature` 0.7 |
| Board wipe (damage) | Incendiary Sabotage deals 3 damage to each creature.<br><sub>Incendiary Sabotage</sub> | 0.600 | 0.264 | `creature` 0.7 |
| Board wipe (damage) | Slagstorm deals 3 damage to each creature.<br><sub>Slagstorm</sub> | 0.600 | 0.264 | `creature` 0.7 |
| Board wipe (damage) | Avengers Disassembled deals 3 damage to each creature.<br><sub>Avengers Disassembled</sub> | 0.600 | 0.264 | `creature` 0.7 |
| Removal (destroy) | Destroy target non-Spirit creature.<br><sub>Rend Flesh</sub> | 0.750 | 0.422 | `target` 1.3 `creature` 0.7 |
| Board wipe (damage) | −X: Chandra deals X damage to each creature.<br><sub>Chandra, Flamecaller</sub> | 0.600 | 0.281 | `creature` 0.7 |
| Board wipe (damage) | Desert Sandstorm deals 1 damage to each creature.<br><sub>Desert Sandstorm</sub> | 0.600 | 0.290 | `creature` 0.7 |
| Removal (destroy) | Destroy target creature or Spacecraft.<br><sub>Embrace Oblivion</sub> | 0.750 | 0.466 | `target` 1.3 `creature` 0.7 |
| Board wipe (destroy all) | Destroy all small creatures.<br><sub>Scaled Destruction</sub> | 0.750 | 0.474 | _—_ |
| Removal (exile) | Exile target creature. Each player gains 3 life.<br><sub>Fall to Earth</sub> | 0.500 | 0.491 | `target` 1.3 `creature` 0.7 |

## Failure modes, measured

### 1. Card names hijack the weighted vector (fixed by default masking)

Restricted to effects with exactly one card (singletons): masking never touches a shared effect, however many cards use it. **7,427 singleton effects (17.5% of the corpus) now have their own-name tokens excluded** before anything is scored. That drops 4,219 tokens out of the vocabulary entirely (10,303 → 6,084) — mostly hapax proper nouns, but also words like a repeated legendary's own name echoed across several printings of itself, that existed only as name-echo in the first place.

What that's fixing, measured on the **unmasked baseline**: 7,593 effects (17.9% of the corpus) use a word from their own card name in their rules text; for 3,655 of them — 8.6% of the whole corpus — those name tokens carried **more than half** the weighted vector's mass, median 49% among affected effects. Raw overlap was unaffected either way: a name token is worth exactly 1 there, same as every other word.

**Why singleton-only, not "any card that uses this effect":** Un-set joke cards are deliberately named after game terms. `Counter target spell.` is shared by 52 cards; one of them is literally named **Spell Counter**. Masking by "any sharing card's name" would strip `counter` from all 52, including every ordinary counterspell. Singleton-only sidesteps this entirely: a word that common is never used by only one card, so it is never a masking candidate to begin with.

Worked example — `Blasphemous Act deals 13 damage to each creature.`, unmasked baseline:

| token | df | idf | share of weighted vector |
|---|--:|--:|--:|
| `blasphemous` | 1 | 10.66 | 39.9% |
| `act` | 2 | 9.96 | 34.9% |
| `13` | 17 | 7.82 | 21.5% |
| `deals` | 4,088 | 2.34 | 1.9% |
| `damage` | 5,072 | 2.12 | 1.6% |
| `creature` | 21,541 | 0.68 | 0.2% |

Masked (the default): ``act`, `blasphemous`` excluded as this card's own name; ``13`, `deals`, `damage`, `creature`` remain.

| | top weighted neighbour, unmasked | score | top weighted neighbour, masked | score |
|---|---|--:|---|--:|
| `Blasphemous Act...` | This land enters tapped unless a player has 13 or less l | 0.322 | Shivan Meteor deals 13 damage to target creature. | 0.989 |

Masking removes the name-echo, but `13` is still a bare numeral shared with every other effect that happens to deal or reference 13 of something (see §3 below) — masking card names and disambiguating numerals are two different fixes for two different tokens in the same sentence.

**The trade-off, measured:** masking assumes a card's own name is flavor, not content. That holds almost everywhere — 191 of the 7,427 masked singletons are left with 1–2 tokens, and the overwhelming majority of those are correctly generic (`enters` `tapped`; `commander` `your`). It fails when the card is *named after* the exact restriction its own ability applies: **Rend Spirit**'s `Destroy target Spirit.` masks away `spirit` — the creature-type restriction that IS the card's whole point, not flavor — leaving just `destroy` `target`, which then scores 0.982 weighted against plain `Destroy target creature.` because there is nothing left to tell them apart. This specific pattern (a `Destroy`/`Exile target <own-name-word>.` singleton reduced to ≤ 2 tokens) occurs exactly once in the whole corpus. Worth knowing about; not worth reverting the default over.

### 2. The weighted mode forgets what the spell hits

`creature` has the lowest IDF in the entire corpus (0.68), so under the weighted mode it barely constrains anything. Of the top 20 weighted neighbours of `Destroy target creature.`, **7 name no creature at all**; raw overlap lets 0 through.

| weighted score | neighbour |
|--:|---|
| 0.982 | Destroy target Spirit. |
| 0.796 | Destroy target token. |
| 0.791 | Destroy target artifact. |
| 0.791 | Destroy target artifact. (Then exile this card. You may cast the creatur |
| 0.761 | Destroy target land. |
| 0.740 | Destroy target permanent. |

### 3. Bare numerals collide (both modes)

Bare numerals are a single token whatever they count. `Surveil 1.` and `+1: Surveil 2.` share `surveil` and `1` — but the `1` in the second is a loyalty cost, not a surveil count. Raw scores the pair 0.667, weighted 0.900; both are counting a coincidence. `1` appears in 2,667 effects (idf 2.77).

### 4. Sensitivity: dropping reminder text

| pair | reminders dropped (what this tool does) | reminders kept |
|---|--:|--:|
| plain mill vs surveil | raw 0.000 / wtd 0.000 | raw 0.000 / wtd 0.000 |
| mill spelling out its reminder vs surveil | raw 0.077 / wtd 0.120 | raw 0.273 / wtd 0.252 |

Reminder text restates a keyword in the vocabulary every other keyword over the same zones also uses — `top` `1` `library` `graveyard` `card` `you`. Keeping it more than triples that pair, raw 0.077 to 0.273, on boilerplate neither effect chose to say. Dropping it is what keeps the mill/surveil answer honest, and it is the one tokenizer choice here that moves a headline number.

## Top-8 neighbours per probe, both modes

### Mill

> Target player mills five cards.

Tokens after stopword removal, heaviest IDF first: `mills` 5.06 `five` 4.74 `player` 2.32 `cards` 2.19 `target` 1.26

| # | raw overlap (Jaccard) | score | shared | IDF-weighted (cosine) | score | shared (token idf) |
|--:|---|--:|---|---|--:|---|
| 1 | Each player mills five cards.<br><sub>Chill of Foreboding</sub> | 0.800 | `mills` `five` `player` `cards` | Each player mills five cards.<br><sub>Chill of Foreboding</sub> | 0.987 | `mills` 5.1 `five` 4.7 `player` 2.3 `cards` 2.2 |
| 2 | Target player mills eight cards.<br><sub>Breaking // Entering</sub> | 0.667 | `mills` `player` `cards` `target` | When this creature enters, target player mills five cards.<br><sub>Geralf's Mindcrusher</sub> | 0.936 | `mills` 5.1 `five` 4.7 `player` 2.3 `cards` 2.2 `target` 1.3 |
| 3 | Target player mills three cards.<br><sub>Brain Freeze, Dream Twist, Paranoid Delusions</sub> | 0.667 | `mills` `player` `cards` `target` | When this creature dies, target player mills five cards.<br><sub>Mindeye Drake, Rotcrown Ghoul</sub> | 0.882 | `mills` 5.1 `five` 4.7 `player` 2.3 `cards` 2.2 `target` 1.3 |
| 4 | Target player mills four cards. (Then exile this card. You …<br><sub>Cruel Somnophage // Can't Wake Up, Merfolk Secretkeeper // Venture Deeper</sub> | 0.667 | `mills` `player` `cards` `target` | Target player mills two cards.<br><sub>Thought Scour</sub> | 0.721 | `mills` 5.1 `player` 2.3 `cards` 2.2 `target` 1.3 |
| 5 | Target player mills ten cards.<br><sub>Glimpse the Unthinkable</sub> | 0.667 | `mills` `player` `cards` `target` | Target player mills a card.<br><sub>Ray of Erasure</sub> | 0.710 | `mills` 5.1 `player` 2.3 `target` 1.3 |
| 6 | Target player mills two cards.<br><sub>Thought Scour</sub> | 0.667 | `mills` `player` `cards` `target` | Each player mills X cards.<br><sub>Fascination</sub> | 0.692 | `mills` 5.1 `player` 2.3 `cards` 2.2 |
| 7 | Target player mills four cards.<br><sub>Dampen Thought, Memory Sluice, Sweet Oblivion +1</sub> | 0.667 | `mills` `player` `cards` `target` | Target player mills three cards.<br><sub>Brain Freeze, Dream Twist, Paranoid Delusions</sub> | 0.689 | `mills` 5.1 `player` 2.3 `cards` 2.2 `target` 1.3 |
| 8 | When this creature dies, target player mills five cards.<br><sub>Mindeye Drake, Rotcrown Ghoul</sub> | 0.625 | `mills` `five` `player` `cards` `target` | Target player mills two cards. Draw two cards.<br><sub>Pilfered Plans</sub> | 0.669 | `mills` 5.1 `player` 2.3 `cards` 2.2 `target` 1.3 |

### Surveil

> Surveil 1. (Look at the top card of your library. You may put it into your graveyard.)

Tokens after stopword removal, heaviest IDF first: `surveil` 5.53 `1` 2.77

| # | raw overlap (Jaccard) | score | shared | IDF-weighted (cosine) | score | shared (token idf) |
|--:|---|--:|---|---|--:|---|
| 1 | Surveil 1. (Look at the top card of your library. You may p…<br><sub>Etherwrought Page, Unexplained Disappearance</sub> | 1.000 | `surveil` `1` | Surveil 1. (Look at the top card of your library. You may p…<br><sub>Etherwrought Page, Unexplained Disappearance</sub> | 1.000 | `surveil` 5.5 `1` 2.8 |
| 2 | −1: Surveil 1. (Look at the top card of your library. You m…<br><sub>Jace</sub> | 1.000 | `surveil` `1` | −1: Surveil 1. (Look at the top card of your library. You m…<br><sub>Jace</sub> | 1.000 | `surveil` 5.5 `1` 2.8 |
| 3 | +1: Surveil 2.<br><sub>Dakkon, Shadow Slayer, Ral Zarek, Guest Lecturer</sub> | 0.667 | `surveil` `1` | {T}: Surveil 1. (Look at the top card of your library. You …<br><sub>Rune-Sealed Wall, Sinister Starfish, The Grim Captain's Locker</sub> | 0.932 | `surveil` 5.5 `1` 2.8 |
| 4 | {T}: Surveil 1. (Look at the top card of your library. You …<br><sub>Rune-Sealed Wall, Sinister Starfish, The Grim Captain's Locker</sub> | 0.667 | `surveil` `1` | {T}: Surveil 1.<br><sub>Microscope</sub> | 0.932 | `surveil` 5.5 `1` 2.8 |
| 5 | {T}: Surveil 1.<br><sub>Microscope</sub> | 0.667 | `surveil` `1` | When Gallifrey Council Chamber enters, surveil 1. (Look at …<br><sub>Gallifrey Council Chamber</sub> | 0.909 | `surveil` 5.5 `1` 2.8 |
| 6 | I — Surveil 1. (Look at the top card of your library. You m…<br><sub>Summon: G.F. Cerberus</sub> | 0.667 | `surveil` `1` | When Lazav enters, surveil 1. (Look at the top card of your…<br><sub>Lazav, the Multifarious</sub> | 0.909 | `surveil` 5.5 `1` 2.8 |
| 7 | {4}, {T}: Surveil 1. (Look at the top card of your library.…<br><sub>Ominous Asylum, Savage Mansion, Sinister Hideout +2</sub> | 0.500 | `surveil` `1` | When this creature enters, surveil 1. (Look at the top card…<br><sub>Cybernetic Specialist, Faerie Dreamthief, Foraging Wickermaw +6</sub> | 0.905 | `surveil` 5.5 `1` 2.8 |
| 8 | When Gallifrey Council Chamber enters, surveil 1. (Look at …<br><sub>Gallifrey Council Chamber</sub> | 0.500 | `surveil` `1` | When this creature enters, surveil 1.<br><sub>Semester Foreseer // Peer Review</sub> | 0.905 | `surveil` 5.5 `1` 2.8 |

### Board wipe (destroy all)

> Destroy all creatures.

Tokens after stopword removal, heaviest IDF first: `destroy` 3.35 `all` 3.08 `creatures` 2.40

| # | raw overlap (Jaccard) | score | shared | IDF-weighted (cosine) | score | shared (token idf) |
|--:|---|--:|---|---|--:|---|
| 1 | Destroy all creatures and lands.<br><sub>Devastation</sub> | 0.750 | `destroy` `all` `creatures` | Destroy all creatures with flying.<br><sub>Whirlwind</sub> | 0.843 | `destroy` 3.3 `all` 3.1 `creatures` 2.4 |
| 2 | Destroy all tapped creatures.<br><sub>Guan Yu's 1,000-Li March, Split Up</sub> | 0.750 | `destroy` `all` `creatures` | Destroy all tapped creatures.<br><sub>Guan Yu's 1,000-Li March, Split Up</sub> | 0.829 | `destroy` 3.3 `all` 3.1 `creatures` 2.4 |
| 3 | Destroy all untapped creatures.<br><sub>Split Up</sub> | 0.750 | `destroy` `all` `creatures` | Whenever this creature attacks, destroy all other creatures.<br><sub>Novablast Wurm</sub> | 0.816 | `destroy` 3.3 `all` 3.1 `creatures` 2.4 |
| 4 | Destroy all nonwhite creatures.<br><sub>Mass Calcify</sub> | 0.750 | `destroy` `all` `creatures` | Destroy all white creatures.<br><sub>Virtue's Ruin</sub> | 0.810 | `destroy` 3.3 `all` 3.1 `creatures` 2.4 |
| 5 | Destroy all nontoken creatures.<br><sub>Hour of Reckoning</sub> | 0.750 | `destroy` `all` `creatures` | Destroy all green creatures.<br><sub>Nature's Ruin</sub> | 0.805 | `destroy` 3.3 `all` 3.1 `creatures` 2.4 |
| 6 | Destroy all Dragon creatures.<br><sub>Crux of Fate</sub> | 0.750 | `destroy` `all` `creatures` | Destroy all nonland creatures.<br><sub>Planar Outburst</sub> | 0.798 | `destroy` 3.3 `all` 3.1 `creatures` 2.4 |
| 7 | Destroy all non-Dragon creatures.<br><sub>Crux of Fate</sub> | 0.750 | `destroy` `all` `creatures` | Destroy all black creatures.<br><sub>Cleanse</sub> | 0.797 | `destroy` 3.3 `all` 3.1 `creatures` 2.4 |
| 8 | Destroy all small creatures.<br><sub>Scaled Destruction</sub> | 0.750 | `destroy` `all` `creatures` | Destroy all creatures and lands.<br><sub>Devastation</sub> | 0.775 | `destroy` 3.3 `all` 3.1 `creatures` 2.4 |

### Board wipe (damage)

> Blasphemous Act deals 13 damage to each creature.

Tokens after stopword removal, heaviest IDF first: `13` 7.82 `deals` 2.34 `damage` 2.13 `creature` 0.68

| # | raw overlap (Jaccard) | score | shared | IDF-weighted (cosine) | score | shared (token idf) |
|--:|---|--:|---|---|--:|---|
| 1 | Shivan Meteor deals 13 damage to target creature.<br><sub>Shivan Meteor</sub> | 0.800 | `13` `deals` `damage` `creature` | Shivan Meteor deals 13 damage to target creature.<br><sub>Shivan Meteor</sub> | 0.989 | `13` 7.8 `deals` 2.3 `damage` 2.1 `creature` 0.7 |
| 2 | −X: Chandra deals X damage to each creature.<br><sub>Chandra, Flamecaller</sub> | 0.600 | `deals` `damage` `creature` | Destroy target land. Into the Maw of Hell deals 13 damage t…<br><sub>Into the Maw of Hell</sub> | 0.878 | `13` 7.8 `deals` 2.3 `damage` 2.1 `creature` 0.7 |
| 3 | Spontaneous Combustion deals 3 damage to each creature.<br><sub>Spontaneous Combustion</sub> | 0.600 | `deals` `damage` `creature` | −7: Sorin deals 13 damage to any target. You gain 13 life.<br><sub>Sorin the Mirthless</sub> | 0.748 | `13` 7.8 `deals` 2.3 `damage` 2.1 |
| 4 | This creature deals π damage to each non-Clown creature. (H…<br><sub>Omniclown Colossus // Pie-roclasm</sub> | 0.600 | `deals` `damage` `creature` | This land enters tapped unless a player has 13 or less life.<br><sub>Abandoned Campground, Bleeding Woods, Etched Cornfield +7</sub> | 0.640 | `13` 7.8 |
| 5 | Desert Sandstorm deals 1 damage to each creature.<br><sub>Desert Sandstorm</sub> | 0.600 | `deals` `damage` `creature` | Each player with exactly 13 life loses the game, then each …<br><sub>Triskaidekaphobia</sub> | 0.571 | `13` 7.8 |
| 6 | Incendiary Sabotage deals 3 damage to each creature.<br><sub>Incendiary Sabotage</sub> | 0.600 | `deals` `damage` `creature` | 13. Loudest<br><sub>Strictly Better // Strictly Better (cont'd)</sub> | 0.571 | `13` 7.8 |
| 7 | Slagstorm deals 3 damage to each creature.<br><sub>Slagstorm</sub> | 0.600 | `deals` `damage` `creature` | Each player with exactly 13 life loses the game, then each …<br><sub>Triskaidekaphobia</sub> | 0.556 | `13` 7.8 |
| 8 | Avengers Disassembled deals 3 damage to each creature.<br><sub>Avengers Disassembled</sub> | 0.600 | `deals` `damage` `creature` | Specialize {2}. Activate only if a player has 13 or less li…<br><sub>Shadowheart, Sharran Cleric</sub> | 0.527 | `13` 7.8 |

### Board wipe (-X/-X)

> All creatures get -X/-X until end of turn.

Tokens after stopword removal, heaviest IDF first: `get` 3.38 `all` 3.08 `x` 2.98 `creatures` 2.40 `until` 2.03 `end` 1.92 `turn` 1.60

| # | raw overlap (Jaccard) | score | shared | IDF-weighted (cosine) | score | shared (token idf) |
|--:|---|--:|---|---|--:|---|
| 1 | All creatures get +X/-X until end of turn.<br><sub>Flowstone Slide</sub> | 1.000 | `get` `all` `x` `creatures` `until` `end` +1 | All creatures get +X/-X until end of turn.<br><sub>Flowstone Slide</sub> | 1.000 | `get` 3.4 `all` 3.1 `x` 3.0 `creatures` 2.4 `until` 2.0 `end` 1.9 +1 |
| 2 | All creatures get -2/-0 until end of turn.<br><sub>Ivory Charm, Marsh Gas</sub> | 0.750 | `get` `all` `creatures` `until` `end` `turn` | All creatures get +1/+1 until end of turn.<br><sub>Magnify</sub> | 0.835 | `get` 3.4 `all` 3.1 `creatures` 2.4 `until` 2.0 `end` 1.9 `turn` 1.6 |
| 3 | All creatures get -2/-2 until end of turn.<br><sub>Biting Rain, Choking Miasma, Hideous Laughter +6</sub> | 0.750 | `get` `all` `creatures` `until` `end` `turn` | All creatures get +2/+0 until end of turn.<br><sub>Final Revels</sub> | 0.705 | `get` 3.4 `all` 3.1 `creatures` 2.4 `until` 2.0 `end` 1.9 `turn` 1.6 |
| 4 | All creatures get -1/-1 until end of turn.<br><sub>Golgari Charm, Mephitic Vapors, Nausea +2</sub> | 0.750 | `get` `all` `creatures` `until` `end` `turn` | All creatures get -1/-1 until end of turn.<br><sub>Golgari Charm, Mephitic Vapors, Nausea +2</sub> | 0.701 | `get` 3.4 `all` 3.1 `creatures` 2.4 `until` 2.0 `end` 1.9 `turn` 1.6 |
| 5 | All creatures get +1/+1 until end of turn.<br><sub>Magnify</sub> | 0.750 | `get` `all` `creatures` `until` `end` `turn` | {B}, Sacrifice Kagemaro: All creatures get -X/-X until end …<br><sub>Kagemaro, First to Suffer</sub> | 0.684 | `get` 3.4 `all` 3.1 `x` 3.0 `creatures` 2.4 `until` 2.0 `end` 1.9 +1 |
| 6 | All creatures get -3/-3 until end of turn.<br><sub>Blight Grenade, Yahenni's Expertise</sub> | 0.750 | `get` `all` `creatures` `until` `end` `turn` | Creatures you control get +1/+1 until end of turn.<br><sub>Black Panther, Vanguard, Break of Day, Charge +13</sub> | 0.674 | `get` 3.4 `creatures` 2.4 `until` 2.0 `end` 1.9 `turn` 1.6 |
| 7 | All creatures get +2/+0 until end of turn.<br><sub>Final Revels</sub> | 0.750 | `get` `all` `creatures` `until` `end` `turn` | Other creatures you control get +1/+1 until end of turn.<br><sub>Voltstorm Angel</sub> | 0.674 | `get` 3.4 `creatures` 2.4 `until` 2.0 `end` 1.9 `turn` 1.6 |
| 8 | All creatures get -0/-2 until end of turn.<br><sub>Final Revels</sub> | 0.750 | `get` `all` `creatures` `until` `end` `turn` | +2: Untap all creatures you control. Those creatures get +1…<br><sub>Gideon, Martial Paragon</sub> | 0.656 | `get` 3.4 `all` 3.1 `creatures` 2.4 `until` 2.0 `end` 1.9 `turn` 1.6 |

### Removal (destroy)

> Destroy target creature.

Tokens after stopword removal, heaviest IDF first: `destroy` 3.35 `target` 1.26 `creature` 0.68

| # | raw overlap (Jaccard) | score | shared | IDF-weighted (cosine) | score | shared (token idf) |
|--:|---|--:|---|---|--:|---|
| 1 | Destroy target Human creature.<br><sub>Human Frailty</sub> | 1.000 | `destroy` `target` `creature` | Destroy target Human creature.<br><sub>Human Frailty</sub> | 1.000 | `destroy` 3.3 `target` 1.3 `creature` 0.7 |
| 2 | Destroy target creature or planeswalker.<br><sub>Annihilating Glare, Assassin's Ink, Bitter Triumph +15</sub> | 0.750 | `destroy` `target` `creature` | Destroy target Spirit.<br><sub>Rend Spirit</sub> | 0.982 | `destroy` 3.3 `target` 1.3 |
| 3 | Destroy target attacking creature.<br><sub>Airbender's Reversal, Bright Reprisal, Eightfold Maze +4</sub> | 0.750 | `destroy` `target` `creature` | Destroy target artifact creature.<br><sub>Hearth Charm, Molten Frame</sub> | 0.810 | `destroy` 3.3 `target` 1.3 `creature` 0.7 |
| 4 | Destroy target creature with defender.<br><sub>Clear a Path, Deface, Smash to Dust</sub> | 0.750 | `destroy` `target` `creature` | Destroy target artifact or creature.<br><sub>Grub's Command</sub> | 0.810 | `destroy` 3.3 `target` 1.3 `creature` 0.7 |
| 5 | Destroy target non-Spirit creature.<br><sub>Rend Flesh</sub> | 0.750 | `destroy` `target` `creature` | Destroy target token.<br><sub>The Ruinous Wrecking Crew</sub> | 0.796 | `destroy` 3.3 `target` 1.3 |
| 6 | Destroy target creature or land.<br><sub>Lava Flow, Wrecking Ball</sub> | 0.750 | `destroy` `target` `creature` | Destroy target artifact.<br><sub>A-Ready to Rumble, Abrade, Ancient Grudge +64</sub> | 0.791 | `destroy` 3.3 `target` 1.3 |
| 7 | Destroy target creature or Spacecraft.<br><sub>Embrace Oblivion</sub> | 0.750 | `destroy` `target` `creature` | Destroy target artifact. (Then exile this card. You may cas…<br><sub>Embereth Shieldbreaker // Battle Display</sub> | 0.791 | `destroy` 3.3 `target` 1.3 |
| 8 | Destroy target creature, then proliferate. (Choose any numb…<br><sub>Spread the Sickness</sub> | 0.750 | `destroy` `target` `creature` | Destroy target creature or land.<br><sub>Lava Flow, Wrecking Ball</sub> | 0.780 | `destroy` 3.3 `target` 1.3 `creature` 0.7 |

### Removal (exile)

> Exile target creature. Its controller gains life equal to its power.

Tokens after stopword removal, heaviest IDF first: `controller` 4.09 `equal` 3.15 `power` 3.12 `gains` 2.92 `exile` 2.73 `life` 2.60 `target` 1.26 `creature` 0.68

| # | raw overlap (Jaccard) | score | shared | IDF-weighted (cosine) | score | shared (token idf) |
|--:|---|--:|---|---|--:|---|
| 1 | −2: Exile target creature. Its controller gains life equal …<br><sub>Ajani Unyielding</sub> | 0.889 | `controller` `equal` `power` `gains` `exile` `life` +2 | −2: Exile target creature. Its controller gains life equal …<br><sub>Ajani Unyielding</sub> | 0.934 | `controller` 4.1 `equal` 3.1 `power` 3.1 `gains` 2.9 `exile` 2.7 `life` 2.6 +2 |
| 2 | When this creature enters, exile up to one other target cre…<br><sub>Solitude</sub> | 0.667 | `controller` `equal` `power` `gains` `exile` `life` +2 | When this creature enters, exile up to one other target cre…<br><sub>Solitude</sub> | 0.801 | `controller` 4.1 `equal` 3.1 `power` 3.1 `gains` 2.9 `exile` 2.7 `life` 2.6 +2 |
| 3 | Exile target creature with power 2 or less. Its controller …<br><sub>Last Breath</sub> | 0.636 | `controller` `power` `gains` `exile` `life` `target` +1 | Whenever Captain Marvel enters or attacks, exile up to one …<br><sub>Captain Marvel, Shooting Star</sub> | 0.766 | `controller` 4.1 `equal` 3.1 `power` 3.1 `gains` 2.9 `exile` 2.7 `life` 2.6 +2 |
| 4 | Whenever Captain Marvel enters or attacks, exile up to one …<br><sub>Captain Marvel, Shooting Star</sub> | 0.615 | `controller` `equal` `power` `gains` `exile` `life` +2 | Exile target creature with power 2 or less. Its controller …<br><sub>Last Breath</sub> | 0.702 | `controller` 4.1 `power` 3.1 `gains` 2.9 `exile` 2.7 `life` 2.6 `target` 1.3 +1 |
| 5 | −3: Exile target creature. Its controller gains 2 life.<br><sub>Ajani, Inspiring Leader</sub> | 0.600 | `controller` `gains` `exile` `life` `target` `creature` | −3: Exile target creature. Its controller gains 2 life.<br><sub>Ajani, Inspiring Leader</sub> | 0.675 | `controller` 4.1 `gains` 2.9 `exile` 2.7 `life` 2.6 `target` 1.3 `creature` 0.7 |
| 6 | Exile target colorless creature. You gain life equal to its…<br><sub>Infernal Reckoning</sub> | 0.545 | `equal` `power` `exile` `life` `target` `creature` | When this creature enters, for each opponent, exile up to o…<br><sub>Luminate Primordial</sub> | 0.621 | `equal` 3.1 `power` 3.1 `gains` 2.9 `exile` 2.7 `life` 2.6 `target` 1.3 +1 |
| 7 | Exile target creature with power greater than or equal to y…<br><sub>Blazing Hope</sub> | 0.545 | `equal` `power` `exile` `life` `target` `creature` | {2}{W}, {T}, Discard a card: Exile target attacking creatur…<br><sub>Avenger en-Dal</sub> | 0.586 | `controller` 4.1 `equal` 3.1 `gains` 2.9 `exile` 2.7 `life` 2.6 `target` 1.3 +1 |
| 8 | Exile target creature. Each player gains 3 life.<br><sub>Fall to Earth</sub> | 0.500 | `gains` `exile` `life` `target` `creature` | Counter target artifact or enchantment spell. Its controlle…<br><sub>Illumination</sub> | 0.577 | `controller` 4.1 `equal` 3.1 `gains` 2.9 `life` 2.6 `target` 1.3 |

### Counterspell

> Counter target spell.

Tokens after stopword removal, heaviest IDF first: `spell` 2.50 `counter` 2.45 `target` 1.26

| # | raw overlap (Jaccard) | score | shared | IDF-weighted (cosine) | score | shared (token idf) |
|--:|---|--:|---|---|--:|---|
| 1 | Counter target creature spell.<br><sub>Bone to Ash, Essence Scatter, Exclude +8</sub> | 0.750 | `spell` `counter` `target` | Counter target creature spell.<br><sub>Bone to Ash, Essence Scatter, Exclude +8</sub> | 0.984 | `spell` 2.5 `counter` 2.5 `target` 1.3 |
| 2 | Counter target artifact spell.<br><sub>Artifact Blast, Halt Order, Steel Sabotage</sub> | 0.750 | `spell` `counter` `target` | Counter target artifact spell.<br><sub>Artifact Blast, Halt Order, Steel Sabotage</sub> | 0.816 | `spell` 2.5 `counter` 2.5 `target` 1.3 |
| 3 | Counter target noncreature spell.<br><sub>Bind to Secrecy, Dovin's Veto, Fierce Guardianship +8</sub> | 0.750 | `spell` `counter` `target` | When this creature enters, counter target spell.<br><sub>Mystic Snake</sub> | 0.788 | `spell` 2.5 `counter` 2.5 `target` 1.3 |
| 4 | Counter target sorcery spell.<br><sub>Dimir Charm, Envelop, Extinguish +2</sub> | 0.750 | `spell` `counter` `target` | When this creature enters, you may counter target spell.<br><sub>Frilled Mystic</sub> | 0.775 | `spell` 2.5 `counter` 2.5 `target` 1.3 |
| 5 | Counter target instant spell.<br><sub>Bant Charm, Dispel, Flash Counter</sub> | 0.750 | `spell` `counter` `target` | Counter target creature or enchantment spell.<br><sub>Get Out</sub> | 0.743 | `spell` 2.5 `counter` 2.5 `target` 1.3 |
| 6 | Counter target blue spell.<br><sub>Gainsay, Red Elemental Blast</sub> | 0.750 | `spell` `counter` `target` | Counter target sorcery spell.<br><sub>Dimir Charm, Envelop, Extinguish +2</sub> | 0.736 | `spell` 2.5 `counter` 2.5 `target` 1.3 |
| 7 | Counter target noncreature spell. (Then exile this card. Yo…<br><sub>Sapphire Dragon // Psionic Pulse</sub> | 0.750 | `spell` `counter` `target` | Counter target spell cast from a graveyard.<br><sub>Laquatus's Disdain</sub> | 0.731 | `spell` 2.5 `counter` 2.5 `target` 1.3 |
| 8 | Counter target nonblue spell.<br><sub>Frazzle</sub> | 0.750 | `spell` `counter` `target` | Counter target creature or sorcery spell.<br><sub>Mystic Denial</sub> | 0.729 | `spell` 2.5 `counter` 2.5 `target` 1.3 |

### Unrelated: pump

> Target creature gets +3/+3 until end of turn.

Tokens after stopword removal, heaviest IDF first: `+3/+3` 5.49 `gets` 2.56 `until` 2.03 `end` 1.92 `turn` 1.60 `target` 1.26 `creature` 0.68

| # | raw overlap (Jaccard) | score | shared | IDF-weighted (cosine) | score | shared (token idf) |
|--:|---|--:|---|---|--:|---|
| 1 | {3}: Target creature gets +3/+3 until end of turn.<br><sub>Sidar Kondo</sub> | 0.875 | `+3/+3` `gets` `until` `end` `turn` `target` +1 | Target creature you control gets +3/+3 until end of turn.<br><sub>Brigid's Command</sub> | 0.971 | `+3/+3` 5.5 `gets` 2.6 `until` 2.0 `end` 1.9 `turn` 1.6 `target` 1.3 +1 |
| 2 | Untap target creature. It gets +3/+3 until end of turn.<br><sub>Gerrard's Command</sub> | 0.875 | `+3/+3` `gets` `until` `end` `turn` `target` +1 | {T}: This creature gets +3/+3 until end of turn.<br><sub>Boa Constrictor</sub> | 0.929 | `+3/+3` 5.5 `gets` 2.6 `until` 2.0 `end` 1.9 `turn` 1.6 `creature` 0.7 |
| 3 | Target creature gets +3/+3 until end of turn. Another targe…<br><sub>Rites of Reaping</sub> | 0.875 | `+3/+3` `gets` `until` `end` `turn` `target` +1 | When this creature enters, target creature gets +3/+3 until…<br><sub>Briarhorn</sub> | 0.927 | `+3/+3` 5.5 `gets` 2.6 `until` 2.0 `end` 1.9 `turn` 1.6 `target` 1.3 +1 |
| 4 | Target creature gets +3/+3 until end of turn and must be bl…<br><sub>Compelled Duel</sub> | 0.778 | `+3/+3` `gets` `until` `end` `turn` `target` +1 | Whenever another creature you control enters, that creature…<br><sub>Primal Forcemage</sub> | 0.894 | `+3/+3` 5.5 `gets` 2.6 `until` 2.0 `end` 1.9 `turn` 1.6 `creature` 0.7 |
| 5 | Target creature gets +3/+3 and gains trample until end of t…<br><sub>Awaken the Bear, Blitzball Shot, Crash the Ramparts +2</sub> | 0.778 | `+3/+3` `gets` `until` `end` `turn` `target` +1 | Whenever another creature you control enters, this creature…<br><sub>Bronzebeak Moa</sub> | 0.894 | `+3/+3` 5.5 `gets` 2.6 `until` 2.0 `end` 1.9 `turn` 1.6 `creature` 0.7 |
| 6 | Target creature gets +3/+3 and gains flying until end of tu…<br><sub>Silverquill Command, Unconventional Tactics</sub> | 0.778 | `+3/+3` `gets` `until` `end` `turn` `target` +1 | {3}: Target creature gets +3/+3 until end of turn.<br><sub>Sidar Kondo</sub> | 0.886 | `+3/+3` 5.5 `gets` 2.6 `until` 2.0 `end` 1.9 `turn` 1.6 `target` 1.3 +1 |
| 7 | Target creature you control gets +3/+3 until end of turn.<br><sub>Brigid's Command</sub> | 0.778 | `+3/+3` `gets` `until` `end` `turn` `target` +1 | Untap target creature. It gets +3/+3 until end of turn.<br><sub>Gerrard's Command</sub> | 0.878 | `+3/+3` 5.5 `gets` 2.6 `until` 2.0 `end` 1.9 `turn` 1.6 `target` 1.3 +1 |
| 8 | Target creature gets +3/+3 and gains flying until end of tu…<br><sub>Angelic Blessing</sub> | 0.778 | `+3/+3` `gets` `until` `end` `turn` `target` +1 | Whenever this creature attacks, it gets +3/+3 until end of …<br><sub>Hungry Spriggan</sub> | 0.873 | `+3/+3` 5.5 `gets` 2.6 `until` 2.0 `end` 1.9 `turn` 1.6 `creature` 0.7 |

### Unrelated: mana

> {T}: Add {G}.

Tokens after stopword removal, heaviest IDF first: `add` 3.60 `{g}` 3.42 `{t}` 2.40

| # | raw overlap (Jaccard) | score | shared | IDF-weighted (cosine) | score | shared (token idf) |
|--:|---|--:|---|---|--:|---|
| 1 | {T}: Add {G}{G}{G}.<br><sub>A-Canopy Tactician, Canopy Tactician, Elvish Aberration +2</sub> | 1.000 | `add` `{g}` `{t}` | {T}: Add {G}{G}{G}.<br><sub>A-Canopy Tactician, Canopy Tactician, Elvish Aberration +2</sub> | 1.000 | `add` 3.6 `{g}` 3.4 `{t}` 2.4 |
| 2 | {T}: Add {G}{G}.<br><sub>Fyndhorn Elder, Glade of the Pump Spells, Greenweaver Druid +3</sub> | 1.000 | `add` `{g}` `{t}` | {T}: Add {G}{G}.<br><sub>Fyndhorn Elder, Glade of the Pump Spells, Greenweaver Druid +3</sub> | 1.000 | `add` 3.6 `{g}` 3.4 `{t}` 2.4 |
| 3 | {T}: Add {C}{G}.<br><sub>Jungle Basin, Nantuko Elder</sub> | 0.750 | `add` `{g}` `{t}` | {T}: Add {G} for each creature you control.<br><sub>Circle of Dreams Druid, Gaea's Cradle, Growing Rites of Itlimoc // Itlimoc, Cradle of the Sun</sub> | 0.948 | `add` 3.6 `{g}` 3.4 `{t}` 2.4 |
| 4 | {T}: Add {R} or {G}.<br><sub>Atarka Monument, Bleeding Woods, Bristling Backwoods +32</sub> | 0.750 | `add` `{g}` `{t}` | Add {G}{G}{G}.<br><sub>Galadriel, Light of Valinor</sub> | 0.900 | `add` 3.6 `{g}` 3.4 |
| 5 | {T}: Add {G}{W}.<br><sub>Selesnya Sanctuary</sub> | 0.750 | `add` `{g}` `{t}` | {1}, {T}: Add {G}.<br><sub>An-Havva Township</sub> | 0.888 | `add` 3.6 `{g}` 3.4 `{t}` 2.4 |
| 6 | {T}: Add {G} or {U}.<br><sub>Balamb Garden, SeeD Academy // Balamb Garden, Airborne, Botanical Sanctum, Dreamroot Cascade +27</sub> | 0.750 | `add` `{g}` `{t}` | Creatures you control have "{T}: Add {G}."<br><sub>Citanul Hierophants</sub> | 0.881 | `add` 3.6 `{g}` 3.4 `{t}` 2.4 |
| 7 | {T}: Add {B} or {G}.<br><sub>Blooming Marsh, Darkmoss Bridge, Deathcap Cultivator +26</sub> | 0.750 | `add` `{g}` `{t}` | Each creature you control with a counter on it has "{T}: Ad…<br><sub>Rishkar, Peema Renegade</sub> | 0.873 | `add` 3.6 `{g}` 3.4 `{t}` 2.4 |
| 8 | {T}: Add {G}{U}.<br><sub>Arixmethes, Slumbering Isle, Gyre Engineer, Simic Growth Chamber</sub> | 0.750 | `add` `{g}` `{t}` | {T}: Add {R} or {G}.<br><sub>Atarka Monument, Bleeding Woods, Bristling Backwoods +32</sub> | 0.854 | `add` 3.6 `{g}` 3.4 `{t}` 2.4 |

