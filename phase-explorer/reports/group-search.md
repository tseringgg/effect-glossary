# Group search

Built by `src/build_group_search.py` (flag `GROUP_SEARCH`). Names, aliases and short descriptions of groups; never the text of cards. Nothing is placed and no figure changes.

## Groups in the search: 2098

| layer | groups |
|---|---|
| hand | 41 |
| kw | 106 |
| leaf | 1222 |
| loose | 48 |
| page | 13 |
| rp | 13 |
| tag | 306 |
| tent | 177 |
| yk | 172 |

## Aliases: 71 hand entries (93 typed phrases, 135 groups referenced) and 193 drafted

- hand aliases pointing at a hashed id (leaf, tentative or loose; about 34 of 1,273 leaf ids changed between earlier builds): **88** of 151 references
- drafted aliases pointing at a hashed id: **86** of 193 references (they are rewritten by `--draft`, so a vanished id is a warning, not an error)
- drafted aliases dropped because a hand alias uses the same words: 0; because their group is gone: 0
- partial hand aliases (each carries a note saying what it leaves out): card advantage, combat trick, copy spell, cost reduction, edict, evasion, extra combat, firebreathing, fixing, giant growth, impulse draw, landcycling, mana dork, mana rock, pacifism, planeswalker removal, ramp, siege, stax
- candidate groups (a term with no group to point at): **bite** - One-sided fight (a creature deals damage equal to its power to another). The nearest group, 'Deal damage to a creature an opponent controls', fits only 25%; a candidate group.; **magecraft** - Ability word; 29 cards, no group. Same for heroic, morbid, threshold, ferocious, undergrowth, constellation and other ability words (about 110 Scryfall keywords have no group or name hit).; **soft counter** - A counterspell the other player can pay to avoid. 'Counter a spell (card)' holds it among 203 cards (47% fit); a candidate group.; **tome** - Repeatable card advantage by tapping; no group (the community tag has 150 cards).
- warnings: 5
  - alias 'card advantage' is also a group name (harmless: the exact name ranks first)
  - alias 'sneak' is also a group name (harmless: the exact name ranks first)
  - alias 'clone' is also a group name (harmless: the exact name ranks first)
  - alias 'combat trick' is also a group name (harmless: the exact name ranks first)
  - alias 'spot removal' is also a group name (harmless: the exact name ranks first)

## Merged pages: 13 (replacing 29 groups in the search)

- aliases that pointed at a member and now point at its page: 17
- member descriptions shadowed by the page's own description (not an error): 27 (leaf:a039d3eeec, leaf:a117b4c7f5, leaf:a1abfc84b8, leaf:a237be105b, leaf:a2c1953ec5, leaf:a34ba37fca, leaf:a39b028786, leaf:a3a21c4de3, leaf:a3b9975737, leaf:a41e991480, leaf:a49909b911, leaf:a4de15e309, leaf:a5cdea60ab, leaf:a618b877c2, leaf:a99162a56a, leaf:a9a2ffd15d, leaf:aa3e8ce261, leaf:ab2d4667c5, leaf:ac62240d34, leaf:ad9e5c28f9, leaf:aec50f6132, leaf:aef44d9d4b, leaf:af9b0f603d, tag:0454fcef-0118-4f10-b9d7-c071845bfbd4, tag:0e87cf9c-591e-4f2a-b4fd-675021f120ae, tag:524845ed-ea82-4a60-8b54-8a38ab06a503, tag:e7f7559f-5ddd-4262-90ad-04f2ea2a735b)

## Descriptions: 1964 of 2098 groups (1951 drafted, 13 by hand)

- orphaned hand edits (id no longer a searchable group): none
- orphaned drafts (rewrite them with `--draft`): 0
- hand edits at a hashed id (can orphan): none

## Real-word list: 51066 words

