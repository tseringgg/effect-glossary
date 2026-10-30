# Browse groups: probe report (read-only)

Written for: the project owner, who will review the draft mapping and decide whether to build the browse-group level. Nothing was built, committed or changed; every new file is listed at the end. Dates: 2026-10-29/30.

**Verdict in one paragraph.** The design is workable, but not as a pure rule pass. The read-only rules (merged pages, name twins, aliases, tag slugs, keywords, taxonomy nodes) place all 1,942 fine groups and lose no card, and 27 of 30 browse groups I read were right (0 wrong, 3 loose, under the bar of 6). But the rules give 581 browse groups, not 150 to 300 (546 have at least one card; 305 have 20 or more cards), and 25 of the 40 browse groups a deckbuilder would expect come out split across 2 to 6 browse groups that are one idea (Burn / Deal damage, Counterspell / Counter a spell, Tutor in four places). Those splits are merge decisions only you can make. Plan on about 250 browse groups in the tree (the head) plus a search-only tail, and on roughly 8 to 16 hours of review for a first pass (an estimate, section 5).

---

## 1. Clutter today (measured; nothing changed)

**Search set.** Seed 20261029, fixed in `src/probe_browse_clutter.py` before anything was computed: your 7 examples (dragon, draw cards, board wipe, recursion, land denial, sacrifice, tutor) + 43 drawn from three pools I wrote down first (24 mechanics, 30 slang terms, 13 card types). The real `reports/groupsearch.js` ran against the real `build/group_search/index.json` with the page's defaults (tentative and community-tag groups on). *Near-twin* = same core name (qualifiers, “Family ›” prefix and “less common kinds” removed), or 70% card overlap. Overlap is reported two ways because the brief does not say which: the overlap coefficient |A∩B|/min(|A|,|B|) (a small group inside a big one counts) and the strict Jaccard.

| | all 50 searches | without “creature” (1,027 results) |
|---|---:|---:|
| group results returned | 1,732 | 705 |
| median / mean / max per search | 4.0 / 34.6 / 1,027 | |
| searches with 0 results | 3 (recursion, fetch land, overrun) | |
| searches with 10 or more results | 16 | |
| results that are a near-twin of another result, same core name | 180 (10%) | 65 |
| … core name or overlap coefficient ≥ 70% | 268 (15%) | 122 (17%) |
| … core name or strict Jaccard ≥ 70% | 186 (11%) | 69 |
| distinct ideas after collapsing twins (core or overlap) | 1,561 of 1,732 | 624 of 705 |
| searches that show at least one twin pair | 16 of 47 with results (core name), 21 (with overlap) | |

**What this says.** Collapsing twins removes 171 of 1,732 results (10%), not most of them. The clutter is mainly *breadth*: a generic word returns many different ideas (creature 1,027, artifact 152, sacrifice 81, draw cards 64, enchantment 59; the page shows 30). The twins show up where you would expect (“Surveil” three times, “Flash” twice, “Counter a spell” as a merged page and again as its member, “Destroy an artifact” as leaf and loose group) and in 21 of 47 searches with results. Three other defects the reads found, which the browse level does not fix on its own: (1) **hand-defined groups with 0 cards are returned first** (blink, cantrip, mana rock: the first click lands on an empty page); (2) description matches pull in unrelated groups (“zombie” returns “Sacrifice a creature”); (3) keyword prefixes (“flash” returns Flashback).

**Top 10 read for 10 searches** (drawn with the same generator after the 50: cantrip, flash, surveil, counterspell, artifact, enchantment, blink, zombie, menace, mana rock). My reading of each:

- *cantrip*: 1 result: a hand-defined group with 0 cards placed. Empty page.
- *flash*: 7 results: 'Flash' appears twice (keyword filter and keyword block, same cards); 'Flashback' (a prefix match) and 'Flash + Flying' are noise for someone who wants flash; 2 results are real (cast as though it had flash). About 3 ideas.
- *surveil*: 5 results: 'Surveil' three times (leaf, loose group, community tag) + 'Surveil, then draw'; 'Exile a creature or planeswalker' is a description match with no connection. 2 ideas + 1 irrelevant.
- *counterspell*: 2 results: the merged page 'Counter a spell' and its member 'Counter a spell with targets'. Sensible, and one idea shown twice.
- *artifact*: 152 results; top 10 has two twin pairs (create artifact tokens leaf+tentative, destroy an artifact leaf+loose) and the empty 'Mana rocks' group. Mostly distinct ideas.
- *enchantment*: 59 results; the top 10 are mostly distinct ideas (cost less, destroy, create tokens, cares about, return from graveyard). One twin pair ('Destroy an artifact or enchantment', leaf and tentative). Clutter here is breadth, not twins.
- *blink*: 1 result: a hand-defined group with 0 cards placed. The page opens empty.
- *zombie*: 9 results: 3 are right (create Zombie tokens, with decayed, Zombie lords); the other 6 matched only by description and are unrelated ('Sacrifice a creature', 'Cast a card'). Noise from the description match.
- *menace*: 10 shown of 17: 'Menace' twice (filter and block), 'Menace: other combinations', then seven groups that GRANT menace or mention it (tokens with menace, equipment that gives menace). About 3 ideas; the top 3 are one idea.
- *mana rock*: 2 results: an empty hand-defined group ('Mana rocks', 0 cards) first, then 'Add colorless mana' (528 cards, which includes lands). The first click lands on nothing.

**Groups by layer** (measured). The page offers 1,942 fine groups. 1,470 of them are hashed ids that can change on a rebuild (leaf, tentative, loose); 472 have stable ids.

| layer | fine groups | share a core name with another group | share |
|---|---|---|---|
| leaf | 1,245 | 200 | 16% |
| tent | 177 | 46 | 26% |
| loose | 48 | 14 | 29% |
| tag | 312 | 2 | 1% |
| kw | 106 | 0 | 0% |
| rp | 13 | 0 | 0% |
| hand | 41 | 0 | 0% |
| **all** | 1,942 | 262 | 13% |

110 core-name families hold those 262 groups; 46 of the families span more than one layer (a leaf and its tentative or loose twin). Not groups for this probe: 172 keyword-filter pages (`yk:`, shown in search as group rows), 13 merged pages (display only), the type pages and the 42 ability-type pages (filters). The 25 offered=0 groups (loose “less common effects” buckets, retired hand groups) are outside the mapping; 121 cards are only in those (see 2.4).

Largest families: “search your library for a card and put it into your hand” ×7; “return permanents to its owners hand” ×5; “lose life” ×5; “exile cards” ×5; “create creature tokens” ×5; “search your library for a card and put it onto the battlefield” ×4; “draw cards” ×4; “discard cards” ×4.

---

## 2. The draft mapping (measured, then read)

`src/probe_browse_draft.py` → `build/browse_groups_draft.json`. Deterministic; no hand assignment. Rules in the order you gave, with one addition I had to make (marked): 1 merged pages → 2 name-twin families → 3 aliases (alias group lists that overlap ≥ 50% are one concept) → 4 tag slug roots → 5 keyword blocks (a two-keyword block is in both keywords: the structural second mapping) → **6 the existing taxonomy node (family › node) as the “broad bucket” refinement**: the 15 topics alone are far too coarse to be browse groups, so a leaf goes to its node, and a tentative or loose group goes to the node of the leaf whose name shares most words with it → 7 hand-defined groups no rule reaches become their own browse group. Card overlap never assigns; it only records a lead (`overlap_hint`) when 70% of a group's cards sit in another browse group. Two small rules I added after the first run showed the problem: concepts with the same display name merge (the name-twin rule applied to concepts), and a named artifact token (Treasure, Food, Clue ...) is its own browse group because the Tokens node held 125 fine groups.

### 2.1 Numbers

- **Browse groups: 581** (546 with cards, 35 empty hand-defined, listed in the review sheet). With ≥ 5 cards: 542; ≥ 10: 425; ≥ 20: 305; ≥ 50: 162; ≥ 100: 96.
- **Size, in fine groups per browse group:** median 1, mean 3.4, max 115. 1-1: 325; 2-2: 102; 3-5: 89; 6-10: 31; 11-20: 16; 21-40: 12; 41-: 6
- **Size, in cards (non-empty):** 1-4: 4; 5-9: 117; 10-19: 120; 20-49: 143; 50-99: 66; 100-299: 65; 300-999: 26; 1000-: 5
- **Singletons (one fine group): 325** (56% of all browse groups). By what their one fine group came from (basis / layer): bucket node / leaf 116, own idea / tag 108, keyword / kw 37, own idea / hand 33, alias / leaf 9, alias / hand 7, family fallback / tent 5, alias / tag 3. They are mostly legitimate ideas (Egg, Coin flip, Initiative, Megamorph), not merge failures.
- **Confidence of the 1,942 fine-group mappings:** high 249, medium 1,572, low 121.
  By basis: bucket node 999; bucket node + name twin 171; alias 153; tag slug 151; own idea 144; keyword 106; name words 88; family fallback 75; alias + merged page 17; name words + name twin 16; bucket node + token name 10; merged page 10; own idea + merged page 2.
  By layer (high/medium/low): hand 6/35/0; kw 106/0/0; leaf 85/1142/18; loose 3/27/18; rp 1/12/0; tag 37/247/28; tent 11/109/57.
  Confidence is the rule's, not a verdict: **medium** includes the 999 leaves placed by taxonomy node, whose names I only spot-read. The overlap hint is not in the confidence.
- **Fine groups in two browse groups: 18** (keyword 13, alias 5). The brief allows at most two and the rules make a second mapping only for a keyword pair (Flying + Haste) or when an alias names a second concept (Destroy an artifact or enchantment: Artifact removal and Disenchant).

### 2.2 The 40 biggest browse groups (by cards)

| # | id | name | cards | fine groups | topics |
|---|---|---|---|---|---|
| 1 | bg:b001 | Create tokens | 2,102 | 115 | Tokens; Buffs and equipment |
| 2 | bg:b002 | Put +1/+1 counters | 2,016 | 49 | Counters; Damage and life |
| 3 | bg:b003 | Deal damage (Damage) | 1,148 | 39 | Damage and life; Library |
| 4 | bg:b004 | Draw cards (Card draw) | 1,100 | 16 | Card draw; Damage and life |
| 5 | bg:b005 | Tap | 1,056 | 26 | Tap and untap |
| 6 | bg:b006 | Gains a keyword (Pump and grant abilities) | 917 | 44 | Buffs and equipment; Combat and evasion |
| 7 | bg:b007 | Add mana | 896 | 16 | Mana; Damage and life |
| 8 | bg:b008 | Fixing | 840 | 2 | Mana |
| 9 | bg:b009 | Has a keyword (Continuous effects (static)) | 828 | 54 | Buffs and equipment; Combat and evasion |
| 10 | bg:b010 | Lifegain | 812 | 5 | Damage and life |
| 11 | bg:b011 | Exile | 704 | 48 | Removal; Tokens |
| 12 | bg:b012 | Gets +N/+N (Pump and grant abilities) | 703 | 31 | Buffs and equipment; Damage and life |
| 13 | bg:b013 | Burn | 655 | 5 | Damage and life |
| 14 | bg:b014 | Firebreathing | 613 | 1 | Buffs and equipment |
| 15 | bg:b015 | Equipment | 586 | 2 | Buffs and equipment |
| 16 | bg:b016 | Sacrifice | 544 | 21 | Sacrifice; Damage and life |
| 17 | bg:b017 | Destroy | 540 | 43 | Removal; Damage and life |
| 18 | bg:b018 | Gets +N/+N (Continuous effects (static)) | 531 | 24 | Buffs and equipment |
| 19 | bg:b019 | Mana rock | 528 | 2 | Mana; Tap and untap |
| 20 | bg:b020 | Other: Pump and grant abilities | 526 | 28 | Buffs and equipment; Combat and evasion |
| 21 | bg:b021 | Return to its owner's hand | 441 | 37 | Removal; Graveyard |
| 22 | bg:b022 | Gets +N/+N and has a keyword | 416 | 25 | Buffs and equipment; Combat and evasion |
| 23 | bg:b023 | Spot removal | 398 | 8 | Removal |
| 24 | bg:b024 | Spells cost less | 386 | 10 | Spells and casting |
| 25 | bg:b025 | Untap | 386 | 22 | Tap and untap |
| 26 | bg:b026 | Gains a keyword, gets +N/+N | 358 | 26 | Buffs and equipment; Combat and evasion |
| 27 | bg:b027 | Other: Continuous effects (static) | 346 | 23 | Buffs and equipment; Combat and evasion |
| 28 | bg:b028 | Shrink | 325 | 6 | Buffs and equipment |
| 29 | bg:b029 | Discard cards (Discard and hands) | 315 | 5 | Hand and discard; Card draw |
| 30 | bg:b030 | Combat trick | 307 | 3 | Buffs and equipment; Combat and evasion |
| 31 | bg:b031 | Counterspell | 304 | 4 | Spells and casting |
| 32 | bg:b032 | Gets ±N/±N (Pump and grant abilities) | 284 | 18 | Buffs and equipment; Damage and life |
| 33 | bg:b033 | Artifact removal | 283 | 5 | Removal |
| 34 | bg:b034 | Return from a graveyard onto the battlefield | 277 | 14 | Graveyard; Damage and life |
| 35 | bg:b035 | Return from a graveyard to its owner's hand | 269 | 16 | Graveyard; Removal |
| 36 | bg:b036 | Mill | 260 | 5 | Library; Graveyard |
| 37 | bg:b037 | Tapper | 253 | 4 | Tap and untap |
| 38 | bg:b038 | Scry | 252 | 3 | Library; Card draw |
| 39 | bg:b039 | Look at the top cards and put into hand | 249 | 11 | Library |
| 40 | bg:b040 | Search your library and put it into your hand | 244 | 13 | Library |

Nine browse groups have 30 or more fine groups (Create tokens 115, Has a keyword (Continuous effects (static)) 54, Put +1/+1 counters 49, Exile 48, Gains a keyword (Pump and grant abilities) 44, Destroy 43, Deal damage (Damage) 39, Return to its owner's hand 37, Gets +N/+N (Pump and grant abilities) 31). Those are the “one idea, many variants” case the design wants (Create tokens with 115 variants, Put +1/+1 counters 49, Destroy 43), except that “Exile” (48) mixes removal with blink and “Has a keyword” (54) and “Gains a keyword” (44) are parser-shaped, not choices a deckbuilder makes. 

### 2.3 Fine groups that do not map cleanly

230 fine groups carry at least one flag (the full list is in the table below and in the draft file's `fine_to_bg` with its notes). By reason (a group can have more than one): **75 parked in an `Other: <family>` group** (no rule reached them; these are the loose and tentative groups with “less common kinds”-style names, 7 parking browse groups: `Other: Pump and grant abilities` 28, `Other: Continuous effects (static)` 23, …); **46 low** (the name shares no word with its browse group); **84 with an overlap hint** (70% of its cards sit in a different browse group, and the mapping is not high); **38 empty hand-defined groups** (no placed cards). Only the first is a mapping failure. The “low” ones are flags to read (most are fine: “Creatures you control have haste” under “Has a keyword” is right, “Enters tapped” under “Tap” is not); the hint and the empty cases are leads.

Parked or low (121):

| layer | fine group | cards | now in | why |
|---|---|---|---|---|
| leaf | Creatures you control have vigilance | 11 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Creatures you control have flying | 11 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Creatures you control have hexproof | 6 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Creatures you control have deathtouch | 17 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Creatures you control have haste | 40 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Objects you control have hexproof | 13 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Enters tapped | 726 | Tap | low: its name shares no word with the browse group's name |
| leaf | Permanents you control have flying | 8 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Creatures you control have lifelink | 8 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Other creatures you control have haste | 7 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Creatures with counters on it you control have trample | 12 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Creatures you control have trample | 21 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Creatures you control have indestructible | 8 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Creatures you control have first strike | 10 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Creatures you control have menace | 18 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Other creatures you control have trample | 9 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Creatures you control have double strike | 8 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| leaf | Permanents you control have hexproof (another) | 5 | Has a keyword (Continuous effects (stati | low: its name shares no word with the browse group's name |
| loose | Card draw › Draw cards, when a card moves between zones | 24 | Other: Card draw | no rule reached it: parked in the family's 'Other' browse group |
| loose | Pump / grant › Give things a gained ability | 12 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group; overlap hint: 83% of its cards are in 'Gains an ability' |
| loose | Pump / grant › Give things a combat effect like can't block or can't b | 10 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Pump / grant › Give things haste, other kinds of target | 15 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Pump / grant › Give things first strike, other kinds of target | 11 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Choice / wrapper › A card with several modes | 46 | Other: Choices | no rule reached it: parked in the family's 'Other' browse group |
| loose | Pump / grant › Make things bigger or smaller by a counted amount, othe | 11 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Pump / grant › Make a creature smaller, all of them | 11 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group; overlap hint: 100% of its cards are in 'Gets ±N/±N (Pump and grant abilities)' |
| loose | Pump / grant › Make things bigger, other kinds of target | 23 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Cast / play › Cast a card (the zone is not recorded), without paying i | 22 | Other: Cast or play from elsewhere | no rule reached it: parked in the family's 'Other' browse group; overlap hint: 73% of its cards are in 'Cast' |
| loose | Pump / grant › Give things indestructible | 10 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Pump / grant › Give things a gained effect, less common kinds | 14 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Pump / grant › Give things double strike, other kinds of target | 11 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Pump / grant › Give things a set power, other kinds of target | 13 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Pump / grant › Give things a gained effect, other kinds of target | 75 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Pump / grant › Make any target bigger | 10 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Pump / grant › Give things a gained ability, other kinds of target | 11 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| loose | Counters › Put counters, through a replacement effect, less common kin | 47 | Other: Counters | no rule reached it: parked in the family's 'Other' browse group |
| tag | Returns an artifact card from the graveyard to the battlefield | 5 | Reanimate | low: its name shares no word with the browse group's name |
| tag | Stops many creatures from blocking | 6 | Prevent | low: its name shares no word with the browse group's name |
| tag | Puts a permanent into its owner's library | 10 | Removal | low: its name shares no word with the browse group's name; overlap hint: 80% of its cards are in 'Spot removal' |
| tag | Takes control of many permanents | 6 | Theft | low: its name shares no word with the browse group's name |
| tag | Works against drawing cards | 6 | Impulse draw | low: its name shares no word with the browse group's name |
| tag | A replacement effect that applies later | 19 | Delayed | low: its name shares no word with the browse group's name |
| tag | Lets you cast cards from the graveyard | 6 | Gives a keyword to your creatures | low: its name shares no word with the browse group's name; overlap hint: 100% of its cards are in 'Reanimate' |
| tag | Uses permanent cards in the graveyard (bring them back, cast them or a | 6 | Reanimate | low: its name shares no word with the browse group's name; overlap hint: 83% of its cards are in 'Gives a keyword to your creatures' |
| tag | Exiles cards until it finds one to cast (cascade, discover) | 16 | Consult | low: its name shares no word with the browse group's name; overlap hint: 81% of its cards are in 'Free cast another' |
| tag | Works only against one kind of opponent | 8 | Single | low: its name shares no word with the browse group's name |
| tag | Stops players from casting spells | 6 | Prevent | low: its name shares no word with the browse group's name; overlap hint: 83% of its cards are in 'Affects every player or the whole battlefield equal |
| tag | Makes a creature unblockable | 6 | Gives a keyword to your creatures | low: its name shares no word with the browse group's name |
| tag | Becomes a creature | 6 | Animate | low: its name shares no word with the browse group's name |
| tag | Casts a permanent spell from a graveyard | 8 | Reanimate | low: its name shares no word with the browse group's name; overlap hint: 88% of its cards are in 'Gives a keyword to your creatures' |
| tag | Works only against a specific color | 10 | Single | low: its name shares no word with the browse group's name; overlap hint: 80% of its cards are in 'Hate: works against a kind of card' |
| tag | Takes control of cast | 10 | Theft | low: its name shares no word with the browse group's name; overlap hint: 70% of its cards are in 'Gives a keyword to your creatures' |
| tag | Lets you cast cards from exile | 22 | Gives a keyword to your creatures | low: its name shares no word with the browse group's name; overlap hint: 73% of its cards are in 'Free cast another' |
| tag | Searches for basic lands | 7 | Tutor | low: its name shares no word with the browse group's name |
| tag | Ends the turn or takes a spell off the stack | 6 | Remove | low: its name shares no word with the browse group's name |
| tag | Takes control of artifact | 8 | Theft | low: its name shares no word with the browse group's name |
| tag | Returns a card from any graveyard | 7 | Reanimate | low: its name shares no word with the browse group's name |
| tag | Cares about you drawing cards | 11 | Impulse draw | low: its name shares no word with the browse group's name |
| tag | Looks through cards and puts the one it finds onto the battlefield | 9 | Consult | low: its name shares no word with the browse group's name |
| tag | Adds counters like proliferate | 8 | Pseudo | low: its name shares no word with the browse group's name |
| tag | Searches for a land and puts it onto the battlefield | 8 | Tutor | low: its name shares no word with the browse group's name |
| tag | Searches for a card and puts it onto the battlefield | 8 | Tutor | low: its name shares no word with the browse group's name |
| tag | Takes permanents away from players, often at random or for everyone | 9 | Removal | low: its name shares no word with the browse group's name |
| tag | Searches for a card | 5 | Tutor | low: its name shares no word with the browse group's name |
| tent | Static: restriction › Can't be blocked by certain creatures, less comm | 11 | Other: Restrictions (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Make things smaller, other kinds of target | 11 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on enchanted creature: adds pow | 26 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Counters › Put counters, from a spell or activated ability, less commo | 35 | Other: Counters | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Make a creature bigger | 43 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on a creature: adds power | 15 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on things: gives trample, other | 14 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Make things bigger and smaller, other kinds of target | 10 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Zone change › Move the thing chosen before to exile | 22 | Other: Moving cards between zones | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Give things no abilities, other kinds of target | 11 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: other rule › Cast spells with an added ability, less common ki | 12 | Other: Rules changes (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on things: grants an ability, o | 39 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Library › Seek a card, cards go to hand | 12 | Other: Library: search, reveal, mill | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Make this permanent bigger | 30 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Give things a gained effect, power and toughness up, ot | 33 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Give things flying, other kinds of target | 11 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Card draw › Draw cards, from a spell or activated ability | 93 | Other: Card draw | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Make a creature bigger, all of them | 33 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Zone change › Move cards to the battlefield | 26 | Other: Moving cards between zones | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Make a creature smaller | 27 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Give things a creature type, other kinds of target | 18 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect, only as long as something is t | 39 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on things: gives indestructible | 13 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on things: gives haste, other k | 17 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Sacrifice › Sacrifice the thing chosen before | 22 | Other: Sacrifice | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on things: gives lifelink, othe | 11 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Card draw › Draw cards, on another kind of trigger | 48 | Other: Card draw | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Give things a card type, other kinds of target | 15 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on this permanent: adds power | 54 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Give a creature an effect like can't attack, can't bloc | 18 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Destroy › Destroy the thing chosen before | 14 | Other: Destroy | no rule reached it: parked in the family's 'Other' browse group |
| tent | Counters › Put counters, when a card moves between zones, less common  | 16 | Other: Counters | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on this permanent: gives flying | 18 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Give things trample, other kinds of target | 16 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Zone change › Move cards from the graveyard to the battlefield, ones y | 42 | Other: Moving cards between zones | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on things: gives vigilance, oth | 11 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Card draw › Draw cards, at the beginning of a phase | 32 | Other: Card draw | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on things: grants a trigger, ot | 13 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on this permanent: gives first  | 10 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Zone change › Move cards from hand to the battlefield, ones you contro | 12 | Other: Moving cards between zones | no rule reached it: parked in the family's 'Other' browse group |
| tent | Pump / grant › Give things flying | 22 | Other: Pump and grant abilities | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on equipped creature: adds powe | 22 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group; overlap hint: 100% of its cards are in 'Attach' |
| tent | Static: restriction › Can't be blocked, this permanent | 11 | Other: Restrictions (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Attach › Attach, uncommon cases | 9 | Other: Attach and equip | no rule reached it: parked in the family's 'Other' browse group |
| tent | Library › Reveal cards until a match, uncommon cases | 6 | Other: Library: search, reveal, mill | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on other kinds of target: gives | 8 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on other kinds of target: gives | 5 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on other kinds of target: gives | 8 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: restriction › Can't enter the battlefield from a zone | 5 | Other: Restrictions (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on other kinds of target: adds  | 9 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Life › Set a life total | 8 | Other: Life gain and loss | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on other kinds of target: adds  | 8 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on other kinds of target: gives | 5 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on other kinds of target: gives | 7 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Card draw › Draw cards, uncommon cases | 5 | Other: Card draw | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on other kinds of target: gives | 8 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |
| tent | Static: continuous › Continuous effect on other kinds of target: adds  | 6 | Other: Continuous effects (static) | no rule reached it: parked in the family's 'Other' browse group |

Overlap-hint and empty cases are listed per group in `build/browse_groups_draft.json` (`overlap_hint`) and inside each section of the review sheet.

### 2.4 Does every card keep a browse group?

Yes, by construction and by check: 32,629 cards have at least one offered fine group today; 32,629 keep at least one browse group; **0 lose all**. 121 cards are only in the 25 non-offered groups (the “less common effects” buckets): they have no fine group today either, so the browse level does not change them. Browse groups per card: median 1, mean 1.37 (fine groups per card: 1.40). Weaker: 998 cards would have only low-confidence browse groups and 797 only a parked `Other:` group, so they are covered on paper and badly placed.

*This check is mechanical and independent of my reading, but it is nearly trivial: the mapping is total, so no card can lose a group. Hand placements (760) were included as members.*

### 2.5 Group-level read: 30 browse groups

Seed 20261030, fixed in `src/probe_browse_checks.py` before the draft was computed. Drawn from the 256 browse groups with two or more fine groups and at least 5 cards (a one-member browse group tests no merge). I read the member names and 5 sample cards of each (`build/browse_groups_reads_sheet.json`).

**Result: right 27, loose 3, wrong 0.** Not right: 3 (the bar is more than 6, so the rule passes this check).

| # | id | browse group | fine groups | mark | note |
|---|---|---|---|---|---|
| 1 | bg:b120 | Reveal cards from the top of a library | 6 | right | Reveal the top cards: six variants of one idea. |
| 2 | bg:b160 | Protects your permanents | 6 | right | Six 'Protects ...' tags; one idea (give protection). |
| 3 | bg:b088 | Search your library | 11 | loose | Land-type searches (Plains, Island ...) and 'search for a creature' are tutors, but 'Put a card in a library' (a zone-change group) is not a search. |
| 4 | bg:b313 | Remove −1/−1 counters | 2 | right |  |
| 5 | bg:b112 | Clone | 3 | right | Clone, copies creature, becomes a copy. |
| 6 | bg:b010 | Lifegain | 5 | right | Gain life, in five groups. |
| 7 | bg:b233 | Changes color | 4 | right |  |
| 8 | bg:b275 | Theft | 3 | right | Theft tags: takes control of ... The name is jargon; the members fit. |
| 9 | bg:b148 | Remove counters | 2 | right |  |
| 10 | bg:b175 | Haste | 4 | right | Haste and its keyword combinations. |
| 11 | bg:b301 | Put time counters | 2 | right |  |
| 12 | bg:b070 | Jump | 2 | right | Gain flying until end of turn; the name 'Jump' is slang a plain reviewer must rename. |
| 13 | bg:b190 | Time walk | 3 | right | Extra turn; the name 'Time walk' should be 'Extra turn'. |
| 14 | bg:b072 | Graveyard hate | 3 | right |  |
| 15 | bg:b033 | Artifact removal | 5 | right | Artifact removal; the 'artifact or enchantment' groups are its second mapping. |
| 16 | bg:b089 | Get energy | 2 | right |  |
| 17 | bg:b076 | Land denial | 6 | loose | Core (destroy a land, destroy all lands, land denial tag) is right. 'Puts more lands onto the battlefield' is ramp, and 'Changes land types' is not denial: the tag-slug root 'land' joined the word 'land' in the alias. |
| 18 | bg:b402 | Double power and toughness | 2 | right |  |
| 19 | bg:b038 | Scry | 3 | right |  |
| 20 | bg:b196 | Reveal cards until one matches | 3 | right |  |
| 21 | bg:b039 | Look at the top cards and put into hand | 11 | right | Eleven 'look at the top cards, put X into hand' variants. |
| 22 | bg:b043 | Put lore counters | 2 | right | Sagas. |
| 23 | bg:b023 | Spot removal | 8 | right | Spot removal, eight groups. |
| 24 | bg:b007 | Add mana | 16 | right | Add mana, sixteen variants. |
| 25 | bg:b075 | Damage prevention | 7 | right | Seven damage-prevention groups. |
| 26 | bg:b349 | That player gets poison counters | 2 | right |  |
| 27 | bg:b208 | Defender | 3 | right |  |
| 28 | bg:b092 | Cast | 4 | loose | 'Cast a card' and 'Cast cards from a graveyard' are close but not one choice; the loose group joined by name words. |
| 29 | bg:b238 | Can't be blocked (Restrictions (static)) | 2 | right |  |
| 30 | bg:b419 | Look at the top cards and put into a graveyard | 2 | right |  |

**Caveats, plainly.** (1) I wrote the rules and I did the reading: not independent. (2) The sample is multi-member groups only; it contains none of the nine oversize groups or the `Other:` parking groups. A supplementary look at those: `Other:` ×7 are junk drawers by design (wrong as browse groups); “Tap” holds “Enters tapped” (wrong); “Exile” mixes removal and blink; “Tutor” holds the basic-land searches that “Ramp” also holds; “Mana rock” holds “Add colorless mana”, which includes lands; “Firebreathing” is one 613-card group named after a niche slang. Counting those as not right, the honest figure is “the multi-member middle is sound; the very large and the parked groups need hand work”. (3) Names: about 15 of the 30 have jargon or slang names (Jump, Cda, Time walk, Theft) that the alias-derived naming chose; naming is a review task, not a mapping failure.

### 2.6 The 50 most popular groups, and the 40 browse groups a deckbuilder would expect

**Top 50 fine groups by card count** (all 50 map; high 22, medium 27, low 1). My quick read: 44 sensible, 5 loose (the “Firebreathing” name for the +N/+N pump; “Add colorless mana” under Mana rock includes lands; two aura pumps under “Gets +N/+N (Continuous effects)”; team pump split between Anthem and “Gets +N/+N (Pump)”), 1 wrong (“Enters tapped” under “Tap”).

| # | layer | fine group | cards | browse group | its size | basis | conf. |
|---|---|---|---|---|---|---|---|
| 1 | leaf | Put +1/+1 counters on this permanent | 946 | Put +1/+1 counters | 49 | merged page | high |
| 2 | leaf | Draw cards — who draws isn't recorded | 860 | Draw cards (Card draw) | 16 | merged page | high |
| 3 | leaf | Add one mana of any color | 831 | Fixing | 2 | alias | medium |
| 4 | leaf | Gain life | 746 | Lifegain | 5 | alias + merged page | high |
| 5 | leaf | Enters tapped | 726 | Tap | 26 | bucket node | low |
| 6 | leaf | Add mana of a fixed color | 662 | Add mana | 16 | bucket node | medium |
| 7 | leaf | This permanent gets +N/+N until end of turn | 613 | Firebreathing | 1 | alias | medium |
| 8 | leaf | Deal damage to any target | 594 | Burn | 5 | alias | high |
| 9 | leaf | Attach to a creature you control | 558 | Equipment | 2 | alias | high |
| 10 | leaf | Add colorless mana | 528 | Mana rock | 2 | alias | medium |
| 11 | leaf | Deal damage to a creature | 300 | Deal damage (Damage) | 39 | merged page | high |
| 12 | leaf | A creature gets +N/+N until end of turn | 274 | Combat trick | 3 | alias + merged page | high |
| 13 | leaf | Create creature tokens | 257 | Create tokens | 115 | merged page | high |
| 14 | leaf | Counter a spell (card) | 239 | Counterspell | 4 | alias + merged page | high |
| 15 | leaf | Put +1/+1 counters on a creature | 227 | Put +1/+1 counters | 49 | bucket node + name twin | medium |
| 16 | leaf | Make a choice as it enters | 219 | Make a choice as it enters | 1 | bucket node | medium |
| 17 | leaf | Scry | 218 | Scry | 3 | bucket node + name twin | medium |
| 18 | leaf | All creatures you control get +N/+N until end of t | 218 | Gets +N/+N (Pump and grant a | 31 | bucket node | medium |
| 19 | leaf | Put lore counters on this permanent | 216 | Put lore counters | 2 | bucket node + name twin | medium |
| 20 | leaf | A creature gets −N/−N until end of turn | 213 | Shrink | 6 | alias + merged page | high |
| 21 | leaf | Mill cards | 207 | Mill | 5 | alias | high |
| 22 | leaf | Create Treasure tokens | 198 | Treasure tokens | 2 | bucket node + token name | medium |
| 23 | leaf | Creatures you control get +N/+N | 195 | Anthem | 3 | alias | high |
| 24 | leaf | Equipped creature gets +N/+N | 194 | Equipment | 2 | alias | high |
| 25 | leaf | Tap a creature | 191 | Tapper | 4 | alias | high |
| 26 | leaf | Sacrifice this permanent | 189 | Sacrifice | 21 | bucket node + name twin | medium |
| 27 | leaf | Destroy a creature (restriction varies) | 189 | Spot removal | 8 | alias + merged page | high |
| 28 | leaf | Enchanted creature gets +N/+N | 177 | Gets +N/+N (Continuous effec | 24 | bucket node | medium |
| 29 | leaf | Surveil | 175 | Surveil | 4 | bucket node + name twin | medium |
| 30 | leaf | Draw cards, then you discard — who draws isn't rec | 165 | Loot | 2 | alias | high |
| 31 | leaf | Destroy an artifact | 161 | Artifact removal | 5 | alias | high |
| 32 | leaf | Regenerate this permanent | 157 | Regenerate | 4 | bucket node | medium |
| 33 | leaf | This permanent can't block, sometimes only unless  | 156 | Can't block, sometimes only  | 2 | bucket node | medium |
| 34 | leaf | Put +1/+1 counters on a creature you control | 155 | Put +1/+1 counters | 49 | bucket node | medium |
| 35 | leaf | This permanent has set power and toughness | 149 | Cda | 3 | alias + merged page | high |
| 36 | leaf | Spells cost less | 146 | Spells cost less | 10 | bucket node + name twin | medium |
| 37 | leaf | Deal damage to each opponent | 136 | Deal damage to each opponent | 2 | bucket node | medium |
| 38 | leaf | This permanent gets +N/+N, while a condition holds | 129 | Gets +N/+N (Continuous effec | 24 | bucket node | medium |
| 39 | leaf | Discard cards, then draw | 128 | Discard cards (Discard and h | 5 | bucket node | medium |
| 40 | leaf | Put +1/+1 counters on all creatures you control (r | 126 | Put +1/+1 counters | 49 | bucket node | medium |
| 41 | leaf | Transform this permanent | 125 | Transform | 3 | bucket node | medium |
| 42 | leaf | This permanent can't be blocked by some creatures | 122 | Evasion | 2 | alias | medium |
| 43 | leaf | Sacrifice a creature | 118 | Edict | 3 | alias | medium |
| 44 | leaf | Return a creature card from your graveyard onto th | 117 | Reanimate | 7 | alias | high |
| 45 | leaf | Each opponent loses life, then gain life | 114 | Drain | 2 | alias | high |
| 46 | leaf | Target player mills cards | 113 | Target player mills cards | 2 | bucket node | medium |
| 47 | leaf | Return a creature to its owner's hand (restriction | 111 | Bounce | 6 | alias | high |
| 48 | leaf | Get energy | 109 | Get energy | 2 | bucket node | medium |
| 49 | leaf | Discard cards | 106 | Discard cards (Discard and h | 5 | bucket node + name twin | medium |
| 50 | kw | Flying | 104 | Flying | 12 | keyword | high |

**The 40 expected browse groups** (list written in `src/probe_browse_checks.py` before the draft). **14 exist as one clear browse group, 25 are split across 2 to 6 browse groups that are one idea, 1 is effectively missing** (Blink: only an empty hand-defined group). Two of the “exist” ones need a better name or a fix: Extra turn is named “Time walk”; Mana rock contains lands.

| expected | status | what exists (my read) |
|---|---|---|
| Draw cards | split | Draw cards 1,100; Other: Card draw; Impulse draw; Card advantage (reasonable sub-ideas) |
| Removal | split | no browse group named Removal: Spot removal, Destroy, Exile, Artifact removal, Disenchant, Edict, Burn ... (the word is only an alias) |
| Ramp | split | Ramp (5 members), Add mana, Mana rock, Mana dork and 'Search your library and put it onto the battlefield' are separate |
| Counterspell | split | Counterspell (304) and 'Counter a spell' (206, 14 members) are the same idea |
| Board wipe | exists | Board wipe (171) |
| Sacrifice outlet | exists | Sacrifice outlet (25) next to Sacrifice (544) |
| Tutor | split | Tutor, two 'Search your library and put ... into hand' groups and 'Search your library' (4 browse groups) |
| Recursion / reanimation | split | Reanimate; 'Return from a graveyard onto the battlefield'; '... to its owner's hand'; Regrowth |
| Blink / flicker | missing | only the hand-defined group, 0 cards; 'Exile' (48 variants) holds exile-then-return mixed with removal |
| Mill | split | Mill (5), Target player mills, Each player/opponent mills ... |
| Lifegain | split | Lifegain (812) and 'Gain life' (Life gain and loss, 131) |
| Mana dork | exists | Mana dork, 10 cards (a tag); most mana creatures are only in Add mana |
| Land denial | exists | Land denial (142) |
| Anthem | exists | Anthem (208) plus pump groups that overlap in meaning |
| Tokens | exists | Create tokens (2,102 cards, 115 variants) with Treasure, Food, Blood, Clue ... split out |
| Stax | split | Stax (98), Doesn't untap, Spells cost more |
| Burn | split | Burn (655) and 'Deal damage' (1,148, 39 variants) |
| Bounce | split | Bounce (179) and 'Return to its owner's hand' (441) |
| Discard / hand disruption | split | Discard cards, Hand disruption, Thoughtseize, Each opponent discards |
| Cost reduction | split | Spells cost less (386) and Cost reduction (16) |
| Extra turn | exists | named 'Time walk', with no alias 'extra turn' on it |
| Clone / copy a permanent | split | Clone, Becomes a copy, Create a token copy |
| Gain control (steal) | split | Gain control, Steal, Threaten, Changes control |
| Graveyard hate | split | Graveyard hate (146) and 'Exile from a graveyard' (169) |
| Wheel | exists | Wheel, 22 cards |
| Mana rock | exists | Mana rock (528), but it holds 'Add colorless mana', which includes lands |
| Mana fixing | exists | Fixing (840) |
| Tapper | exists | Tapper (253) |
| Fog / damage prevention | split | Fog, Damage prevention, Prevent damage |
| Proliferate | exists | Proliferate (62) |
| +1/+1 counters | exists | Put +1/+1 counters (2,016) with Double / Move / Remove as separate browse groups |
| Equipment | split | Equipment (586) and Attach (94) |
| Evasion | split | Evasion, Flying, Unblockable, Can't be blocked ... |
| Protection / hexproof | split | Hexproof, Protection, Protects your permanents (keywords and effects) |
| Combat trick / pump | split | Combat trick (307), Firebreathing (613), Gets +N/+N ... |
| Drain | split | Drain (120) and 'Each opponent loses life' (98) |
| Copy a spell | split | Copy a spell (122) and Copy spell (88) |
| Artifact / enchantment removal | split | Artifact removal (283) and Disenchant (206) |
| Pillowfort | split | Pillowfort (21), Fog, 'Can't attack, sometimes only ...' (134) |
| Treasure / Food / Clue tokens | exists | Treasure, Food, Blood, Clue tokens, each its own browse group (by the token rule) |

The split pattern is the same every time: a hand alias or tag carries the deckbuilder's word (Burn, Counterspell, Lifegain, Copy spell, Tutor), while the taxonomy node carries the parser's (Deal damage, Counter a spell, Gain life, Copy a spell, Search your library). Name-twin and alias rules do not join them because the names differ. About 25 pairs or clusters; each is one line in the mapping file once you decide.

---

## 3. Popular cards

Top 500 cards by `edhrec_rank` (the rank in `manual_index.json`; seed for the read 20261031). All 500 have at least one fine group and therefore a browse group; they average 1.55 fine groups and 1.50 browse groups each.

**Automatic check (my text patterns, not the site's data).** For each card I matched its oracle text against 40 expected-concept patterns (concepts and text patterns written before the run; the browse-group name patterns were tightened once after the first run showed false matches, such as “counter” matching “+1/+1 counters”) and asked whether the card has a browse group whose name or aliases fit the concept. 424 of the 500 cards trigger at least one pattern (601 card/concept pairs). **175 of those cards (35% of the 500) miss an expected browse group** (223 pairs). By what would fix it: hand placement 163, mapping change 60. The patterns are generous in some places and strict in others, so read this as a lead, not a score.
Misses by concept: draw 41, manarock 23, protection 20, tokens 19, fixing 14, evasion 12, lifegain 12, tutor 11, sacoutlet 10, manadork 7, anthem 7, p1p1 6, treasure 5, costred 5. The biggest: draw (41, mostly cards that draw as a side effect: Mind Stone, Skullclamp, The One Ring), mana rock (23, signets and talismans whose mana is colored), protection (20), tokens (19, e.g. cards that give an opponent a token), fixing (14; dual lands in my 40-card read).

**Hand read: 40 cards, seed 20261031**, against the card text. **16 of 40 miss an expected browse group (40%)**: mapping change 7, hand placement 8, missing browse group 1. (Plus some wrong inclusions: Demolition Field and Karplusan Forest, both lands, sit in “Mana rock”; “Enters tapped” cards sit in “Tap”.) The fix is a mapping change when the card's ability is in a group that maps to the wrong or a sibling browse group, a hand placement when no group holds the ability at all, and a new browse group only for Doubling Season (no doubler group exists).

| # | card | expected, missing | fix | note | its browse groups |
|---|---|---|---|---|---|
| 1 | Ghostly Prison | Pillowfort | mapping change | its group 'Can't attack, sometimes only unless a condition' is a pillowfort group but is not mapped to the Pillowfort browse group | Can't attack, sometimes only unless a condition is met |
| 2 | Talisman of Indulgence | - | ok |  | Add mana | Mana rock |
| 3 | Demolition Field | Land denial | hand placement | the 'destroy target nonbasic land' ability is in no group; it is also wrongly under Mana rock (it is a land) | Mana rock |
| 4 | Badlands | Fixing | mapping change | dual land: 'Add mana of a fixed color' is mapped to Add mana, not Fixing (a judgment call: is a dual land fixing?) | Add mana |
| 5 | Thran Dynamo | - | ok |  | Mana rock |
| 6 | Bloodstained Mire | - | ok | Ramp (fetch land) | Ramp |
| 7 | Force of Negation | Counterspell | hand placement | its counter ability is in no counterspell group | Exile from hand |
| 8 | Nature's Lore | Ramp | mapping change | 'Search your library for a Forest land ...' sits in 'Search your library and put it onto the battlefield', a sibling of Ramp, not in Ramp | Search your library and put it onto the battlefield |
| 9 | Sakura-Tribe Elder | - | ok |  | Ramp |
| 10 | Sunpetal Grove | - | ok | also under 'Tap' for 'enters tapped', which a deckbuilder would not choose as Tap | Tap | Fixing |
| 11 | Boros Signet | Mana rock | hand placement | colored-mana rocks are not in the Mana rock browse group (only 'Add colorless mana' is) | Add mana |
| 12 | Eternal Witness | - | ok | Recursion (named 'Return from a graveyard to its owner's hand') | Return from a graveyard to its owner's hand |
| 13 | Reclamation Sage | - | ok |  | Artifact removal | Disenchant |
| 14 | Cinder Glade | Fixing | mapping change | dual land (same judgment as Badlands) | Tap | Add mana |
| 15 | Generous Gift | - | ok |  | Spot removal |
| 16 | Supreme Verdict | - | ok |  | Board wipe | Can't be countered |
| 17 | Guttersnipe | - | ok |  | Deal damage to each opponent |
| 18 | Craterhoof Behemoth | - | ok | present as 'Gains a keyword, gets +/-X/+/-X'; no 'Overrun / team pump' browse group exists by that name | Gains a keyword, gets ±X/±X (Pump and grant abilities) |
| 19 | Cursed Mirror | - | ok |  | Add mana | Clone |
| 20 | Spire of Industry | - | ok |  | Fixing | Mana rock |
| 21 | Seething Song | - | ok | no 'Ritual' group; it is in Add mana | Add mana |
| 22 | Blasphemous Act | Board wipe | hand placement | the damage-to-each-creature ability is in no group | Spells cost less |
| 23 | Abrade | - | ok |  | Deal damage (Damage) | Artifact removal |
| 24 | Enlightened Tutor | Tutor | mapping change | it is in 'Search your library', a sibling of the 'Tutor' browse group (same idea, two browse groups) | Search your library |
| 25 | Fabled Passage | - | ok |  | Ramp |
| 26 | Witch Enchanter | Artifact removal | mapping change | 'Destroy an artifact or enchantment an opponent controls' maps to Destroy; the same ability without 'an opponent controls' maps to Artifact removal | Add mana | Destroy |
| 27 | Frantic Search | - | ok |  | Draw cards (Card draw) |
| 28 | Kami of Whispered Hopes | Mana dork | hand placement | also a +1/+1 counter doubler; neither is in a group | Fixing |
| 29 | Burnished Hart | - | ok |  | Ramp |
| 30 | Impact Tremors | - | ok |  | Deal damage to each opponent |
| 31 | Temple of Malice | - | ok |  | Tap | Fixing | Scry |
| 32 | Utopia Sprawl | - | ok |  | Add mana | Make a choice as it enters |
| 33 | Doubling Season | Doublers (tokens / counters) | missing browse group | only 'Synergy: cares about a particular thing'; no doubler group exists | Synergy: cares about a particular thing |
| 34 | Warren Soultrader | Sacrifice outlet | hand placement | 'Sacrifice another creature' as a cost is in no group | Treasure tokens |
| 35 | Jungle Shrine | - | ok |  | Tap | Fixing |
| 36 | Victimize | Reanimation | hand placement | only 'Edict'; the return-to-battlefield ability is in no group | Edict |
| 37 | Godless Shrine | Fixing | mapping change | dual land (same judgment as Badlands) | Add mana |
| 38 | Rampant Growth | - | ok |  | Ramp |
| 39 | Karplusan Forest | - | ok | in Mana rock although it is a land | Add mana | Mana rock |
| 40 | Opt | Draw cards | hand placement | the 'draw a card' half is in no group | Scry |

The 40-card read is the real measure: 16 of 40 (40%) is a lot for the 500 most popular cards. Split by cause: 8 cards need a hand placement (an ability sits in no group at all, so the browse level cannot help; these are today's coverage gaps seen through popular cards); 7 are mapping decisions in the browse level (sibling groups: Tutor, Ramp, Artifact removal, Pillowfort, and three dual lands as Fixing); 1 needs a new browse group (doublers).

---

## 4. The file, the validation, and what happens to the features (proposal only, nothing built)

### 4.1 `corrections/browse_groups.json`

```json
{
  "_about": "Browse groups: the curated level over the fine groups. Hand-edited. ids are never reused or derived; to stop using a group set retired.",
  "v": 1,
  "next_id": 312,
  "groups": {
    "bg:b023": {
      "name": "Spot removal",
      "description": "Destroys or exiles one target creature or permanent.",
      "aliases": ["removal", "kill spell"],
      "topic": ["removal"],
      "members": [
        {"id": "leaf:a205bd3cf5", "name": "Destroy a creature (restriction varies)", "sig": "fam=Destroy · ftype=Destroy · obj=Creature", "role": "primary"},
        {"id": "tag:3fb7e4fd-5304-4120-b7c4-8a89f70ad3f0", "name": "Spot removal", "role": "primary"}
      ],
      "basis": "alias; merged page destroy-a-creature",
      "created": "2026-10-30",
      "retired": false
    }
  }
}
```

- **Ids.** `bg:` plus a short opaque slug (`b023`), taken from `next_id`, never derived from the name or the members, never reused. The draft's ids (`bg:b001` …) are provisional in size order; they freeze when you first import the file. (Readable slugs like `bg:board-wipe` are easier to read in a URL; the brief says never derive them, so I used opaque ones. Your call.) Renaming changes only `name`.
- **Topic** is the bucket id (`removal`, `draw` …) from `build/buckets/map.json`, one or two. It is a starting point for browsing, not a constraint.
- **Members** are fine-group ids with the last-seen `name` (and the leaf `sig`), so a vanished hashed id can be found again. `role` is `primary` (exactly one) or `second` (at most one).
- **Build-time validation** (an error stops the build, like the alias file): every member id exists among the offered fine groups, or resolves by the re-key rule below; a fine group is in at most two non-retired browse groups, as `primary` in exactly one; **no orphans**: every offered fine group with at least one card is a member of some non-retired browse group (a new group appearing after a rebuild is listed as an orphan, so it cannot silently vanish from the site); names are unique after case and space folding; ids are unique and an entry is never deleted (retire it); topic ids are among the 15; a browse group with no cards is allowed only when marked `empty_ok`; at most 12 aliases and no alias that is another browse group's name (warning).
- **Hashed ids that change on rebuild.** Measured now: 1,470 of the 1,942 fine groups have hashed ids (leaf, tentative, loose); the other 472 (tag, keyword, replacement, hand) never change. Of the hashed ones, 1,436 have a unique (layer, name) and **all 1,245 leaves have a unique signature**; all 225 tentative and loose groups have a unique name. The alias file records that about 34 of 1,273 leaf ids changed in one rebuild. So the build resolves a missing member by (1) the same layer and exact name if unique, (2) the leaf signature if unique, (3) otherwise an **error** that prints the candidates ranked by card overlap. It never repoints silently; a small `--rekey` tool (not built) would rewrite the file after you accept the printed pairs. That is the same approach as the alias file's “a rename is reported at build”.

### 4.2 Review sheet

`build/browse_groups_review.md`: one section per browse group, sorted by topic then size, with name, description, aliases, topic, members (name, layer, size, basis/confidence), 5 sample cards (the most popular in the group), and a line of boxes to mark. Nothing is in `corrections/`.

### 4.3 How the site would read it, and what happens to each feature

| feature | fate | how |
|---|---|---|
| Group search (`groupsearch.js`) | stays, re-pointed | Indexes browse groups (name, aliases, description) and, below the name tier, the **variants' names** (“treasure”, “plains”, “zombie” still find their browse group, shown as “matched variant: Create Treasure tokens”). Fine groups stop being rows. This is needed: otherwise hiding variants removes every narrow search. The empty-page problem goes away if empty browse groups are not indexed. |
| `group_aliases.json` and `group_descriptions.json` | fold in | Each alias id resolves to its browse group at build; later the aliases move into the browse group's own list. The fine-group descriptions stay as tooltips on the variants. |
| Left tree (“By family”) | replaced | Topic (15) → browse groups. The 28-family taxonomy tree stays reachable as a developer view only. |
| “Might also fit” (suggestions) | stays at the fine level, shown at the browse level | The suggestion engine, batch actions and hand placement still work on fine groups (placement is the precise act). A browse-group page lists suggestions for any variant, each naming the variant it would go into. Open decision: the edit panel's “place in …” picker must choose a variant. |
| “Narrow by group” chips | stays, one level up | The 15 topics stay as the first row. The second row becomes browse-group chips (counts as today, twin folding no longer needed). Variants are a third, optional row inside a browse group, **off by default**. |
| Merged pages (`mergepage.js`, 13 pages) | folds in, retired | Each page is already one browse group (rule 1). Its section-per-member display becomes the variant list. `merged_groups.json` is superseded once every page is a browse group (it is read once for the import and kept, not deleted, per its own rule). |
| Twin folding in narrowing and the “+N similar groups” block | retired for browse groups | Redundant once twins share a browse group. The block can stay in the edit panel for fine groups. |
| Tentative, loose and community-tag layers and their badges | stay as variants | A variant keeps its “not checked” badge. A browse group shows how many of its cards come from checked variants only. The switches at the top still hide unchecked variants. |
| Type pages, ability-type pages, keyword facet, colour/type/MV filters, card pin, topic buckets | unchanged | Filters and pages, not groups; not in the mapping. |
| The six figures | unchanged | The browse level is a display layer over placements; no placement, leaf or count changes. |

---

## 5. Recommendation

**Is the design workable?** Yes. Every fine group maps, no card loses a group, the multi-member browse groups read as sound (27/30), and the browse level fits the data: the hierarchy exists already (topic → taxonomy node → leaf) and the hand aliases are a seed list of the right concepts. Nothing in the draft says it cannot work. What it does *not* show is that a rule pass can make the curated set by itself.

**How many browse groups.** The rules produce 581 (546 non-empty). Merging the ~25 split concepts above (roughly 40 to 60 browse groups fold into others) gives about 480 to 520. 150 to 300 is reachable only as the **tree**, not as the whole set: 305 browse groups have 20 or more cards now, about 250 after the merges. My recommendation: **about 250 in the tree and main search (cards ≥ 20 or an alias/hand-picked concept), and the 200-odd smaller ones (Egg, Coin flip, rare keywords) kept as search-only “more” entries under their topic**, not folded into catch-alls: a catch-all is exactly the “Other:” parking the read marked wrong. If you want a hard 300 cap, the cost is losing niche ideas from the tree.

**Review effort (estimate).** Counts are measured; the minutes are my assumptions. 290 single-member browse groups at 15–30 s, 191 of 2–5 members at 45–90 s, 65 of 6+ members at 2.5–4 min, ~40 concept merges at 2–3 min, ~100 renames and ~150 descriptions at 30–45 s each → **about 8 to 16 hours for a first pass**, plus a few hours of follow-up hand placements for the popular-card misses. A shorter first pass over only the 305 browse groups with 20+ cards (the tree) is roughly a third of that.

**Where you will need to make judgment calls** (I did not, and the file records each as a choice):

- Which split concepts are one idea (Burn vs Deal damage to any target; Counterspell vs Counter a spell with restrictions; Lifegain vs Gain life; Tutor vs Search your library; Reanimate vs Return from a graveyard onto the battlefield). Some are the same, some are real choices (reanimate vs regrowth; burn vs fight).
- Whether a very large group is one browse group or several: Create tokens (115 variants), Exile (removal vs blink), Destroy, Deal damage, “Has a keyword” / “Gains a keyword” (parser-shaped, not a deckbuilder's choice).
- Whether dual lands are “Fixing”, and whether “Mana rock” means any artifact that makes mana or only colorless ones (the alias currently puts lands in it).
- Whether keywords are browse groups (106 keyword blocks make about 50) when a keyword filter already exists; and whether a keyword pair is in two browse groups.
- Whether the 116 community-tag singletons (Egg, Coin flip, Utility land, Attack trigger) are browse groups, tail entries, or variants of something.
- Names and descriptions: about 15 of 30 names I read were slang or parser phrases. Plain names are the review's main work.
- What to do with hand-defined groups that have no placements (35 empty browse groups): hide until placed, or place first.
- Opaque or readable ids; and whether the placement picker in the edit panel chooses a variant or a browse group.

**What is measured, what is estimated, what is independent.**

| what | kind | independent? |
|---|---|---|
| Search counts, twins, ideas, layer counts, shared core names | measured by script | yes (the real search code and data); the 70% overlap definition is mine |
| Draft sizes, confidence, bases, two-group count, unclean list, card coverage | measured by script | yes for the numbers; the rules and the confidence labels are my design |
| 30 browse groups read, 10 top-10 reads, 50 popular groups, 40 expected groups, 40 popular cards read | my judgment | **no**: I wrote the rules and did the reading. The sample seeds were fixed first, so the choice of what to read is not tuned, but the marks are mine |
| Top-500 automatic miss count | measured | partly: text patterns are mine and written before the run; browse-group matching is by name and alias regexes, so it is generous in places |
| Number of browse groups after merging, tree size, review hours | estimate | no |
| Hashed-id re-key figures (1,470 hashed, 1,436 unique names, 1,245 unique signatures) | measured | yes |

**What would make the next round better.** Join concepts across the alias and node sides with one extra rule (a node of ≤ 25 fine groups whose headline group is in an alias absorbs the node), which I expect to remove 15 to 20 of the 25 splits; give every alias concept a plain canonical name; stop the tag-slug root `land` from joining the “land” alias. I did not do these here because the brief asks for a probe of the rules as specified.

---

## Files this probe wrote (all new; nothing else changed)

- src/browse_probe_data.py, src/probe_browse_clutter.py, src/probe_browse_draft.py, src/probe_browse_checks.py, src/probe_browse_report.py (the probe, read-only on every input)
- build/browse_groups_clutter.json, build/browse_groups_draft.json, build/browse_groups_probe_results.json, build/browse_groups_reads_sheet.json, build/browse_groups_cards_sheet.json
- build/browse_groups_review.md (the review sheet)
- reports/browse-groups-probe.md (this file), reports/browse-groups-reads.json (my readings)

Appendix: the 50 searches.

| search | results | twins (core name) | twins (core or overlap coeff.) | twins (core or Jaccard) | distinct ideas |
|---|---|---|---|---|---|
| dragon | 10 | 0 | 0 | 0 | 10 |
| draw cards | 64 | 2 | 4 | 2 | 62 |
| board wipe | 3 | 0 | 0 | 0 | 3 |
| recursion | 0 | 0 | 0 | 0 | 0 |
| land denial | 3 | 0 | 0 | 0 | 3 |
| sacrifice | 81 | 8 | 10 | 8 | 76 |
| tutor | 9 | 2 | 7 | 4 | 5 |
| equipment | 15 | 0 | 3 | 0 | 13 |
| counterspell | 2 | 0 | 0 | 0 | 2 |
| extra turn | 3 | 2 | 2 | 2 | 2 |
| saga | 2 | 0 | 0 | 0 | 2 |
| flashback | 2 | 0 | 0 | 0 | 2 |
| proliferate | 5 | 0 | 0 | 0 | 5 |
| discard | 34 | 4 | 4 | 4 | 31 |
| cost reduction | 2 | 0 | 0 | 0 | 2 |
| removal | 24 | 0 | 6 | 0 | 19 |
| elf | 7 | 0 | 0 | 0 | 7 |
| wrath | 3 | 0 | 0 | 0 | 3 |
| flash | 7 | 2 | 3 | 2 | 5 |
| fetch land | 0 | 0 | 0 | 0 | 0 |
| kicker | 1 | 0 | 0 | 0 | 1 |
| aura | 12 | 0 | 0 | 0 | 12 |
| equip | 28 | 4 | 26 | 6 | 4 |
| vigilance | 23 | 2 | 3 | 2 | 21 |
| goblin | 9 | 0 | 0 | 0 | 9 |
| pump | 4 | 0 | 0 | 0 | 4 |
| surveil | 5 | 3 | 3 | 3 | 3 |
| blink | 1 | 0 | 0 | 0 | 1 |
| menace | 17 | 2 | 3 | 2 | 15 |
| overrun | 0 | 0 | 0 | 0 | 0 |
| storm | 1 | 0 | 0 | 0 | 1 |
| cantrip | 1 | 0 | 0 | 0 | 1 |
| hexproof | 25 | 2 | 3 | 2 | 23 |
| landfall | 1 | 0 | 0 | 0 | 1 |
| enchantment | 59 | 7 | 7 | 7 | 55 |
| ward | 7 | 2 | 3 | 2 | 5 |
| looting | 2 | 0 | 0 | 0 | 2 |
| convoke | 2 | 0 | 2 | 0 | 1 |
| zombie | 9 | 0 | 0 | 0 | 9 |
| mana rock | 2 | 0 | 0 | 0 | 2 |
| anthem | 3 | 0 | 0 | 0 | 3 |
| flicker | 1 | 0 | 0 | 0 | 1 |
| indestructible | 26 | 0 | 2 | 0 | 25 |
| clone | 3 | 0 | 2 | 0 | 2 |
| lifelink | 27 | 2 | 4 | 2 | 24 |
| bounce | 4 | 0 | 0 | 0 | 4 |
| artifact | 152 | 21 | 25 | 21 | 139 |
| creature | 1027 | 115 | 146 | 117 | 937 |
| wheel | 1 | 0 | 0 | 0 | 1 |
| fog | 3 | 0 | 0 | 0 | 3 |
