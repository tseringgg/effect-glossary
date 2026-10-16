# Tester note

Kept in the repo so the wording and the numbers stay in step with the build. `python src/check_tester_note.py` compares the claims below with
`build/ability_taxonomy*.json` and `reports/browse.html` and lists any that no longer hold. Update this file and rerun the check whenever a build
changes the headline, the scope, or what the page offers.

---

## What this is

A browsing tool for finding Magic cards by what they do. You explore groups of cards that share an effect (removal, ramp, card draw and so on) instead of searching for a name you already know.

It's built on an open-source rules parser that is still in progress. Most cards are read accurately, but some aren't, and the tool shows you where.

## What to expect

- Oracle text is on every card. If a group or detail looks off, the card's own text is the source of truth.
- Groups are made from individual abilities. A card with two effects can appear under two groups. Cards the tool shows under a group are placed by the ability shown next to them.
- Some cards are placed by one ability while another part of their text isn't understood yet. The card page shows the part that wasn't read.
- Some groups are marked as broader than their name says. The parser doesn't record every detail (who draws, for example), so those groups can hold more than the name suggests.
- Group names can be imprecise. The cards inside a group are right more often than its label is. If a name confuses you, tell me.
- About 73% of constructed-legal cards are in a group, and about 83% counting the broad ones. The rest are in "Not yet organized," and each one says why. They're still findable.
- Some cards in "Not yet organized" are also shown under "Tentative groups" in each family (about 2,100 cards; about 90% of the card set counting them). They are grouped by effect type but not fully checked, so treat them as hints. A switch at the top hides them.
- Some cards in "Not yet organized" have an ability the tool held back because it did not read part of it, usually a condition such as "if you control a Swamp". Under "Condition annotations" in each family, that ability is shown in the group it would belong in if the condition were ignored, with the condition quoted on the card and a dotted "Condition not read" badge. The condition may change what the ability does, even to the opposite, so treat the placement as a hint (about 960 more cards; about 92% of the card set counting them). A further 160 cards, whose ability was read but another part of the card was not, are on their own line with a "Card part not read" badge (about 93% with them, kept separate). A switch at the top, "Show condition annotations", hides all of it.
- Cards the tool could not read at all (about 1,200 of the 1,300 in "Cards we couldn't read yet") are also shown in a section called "Grouped by community tag": groups made from Scryfall's community tags, with the tag, the date of the tag snapshot and the line "Not checked against the card's parsed text." The tags are volunteers' labels, so treat them as hints for browsing, not as a check of anything (about 96% of the card set counting them, on its own line, never added to the other figures). The same list has a tag filter. A switch at the top, "Show community-tag groups", hides it.
- A few cards have been placed in a group by hand, with a solid blue "by hand" badge. That is a person's judgment, not a checked placement: it is counted on its own line ("placed by hand"), never added to the other figures, and a switch at the top, "Show hand edits", hides all of it.
- A "Keyword" filter on the Cards tab and a "By keyword" list show which cards carry a keyword wherever they are placed. It is a filter, not a placement, and it changes no group and no figure. The parser's keyword list (172 names) is narrower than Scryfall's (836 names, which also include actions and ability words such as Scry and Landfall).
- A few groups are defined by hand (a dashed "hand group" badge, for example "Wins, loses or draws the game"). Their rules only suggest cards in the edit panel; a card is in one only if someone placed it there.
- Some tentative cards carry a "sibling" badge: the ability has exactly a group's signature but the grouping rule left it out because it is the plain variant. These are not checked, are counted in no figure, and a switch at the top, "Show sibling placements", hides them.
- In "To place" there is a "Batch view": cards with their suggestions and a checkbox each. Nothing is placed until you press Accept; one click is at most 100 placements, all or nothing, with its own id, and "Undo this batch" takes it all back. Suggestions are not checked, so a batch can contain loose ones. The tentative, tag, sibling and annotation group pages have a "Batch review" to confirm or reject ticked cards. A batch-placed card says so in Find a card, and the "placed by hand" line shows how many were placed in a batch. A switch at the top, "Show batch actions", hides all of it.
- Silver-border, playtest, acorn and similar cards are left out, since they aren't meant for constructed play. Find a card tells you when a card is one of these.
- Cards released since April are included but parsed by an older version of the parser, so a few newer mechanics may show a gap.

## What I'd like to know

- Could you find the kind of card you were looking for without knowing its name?
- Did any group contain cards that clearly didn't belong?
- Was there a card you expected to find and couldn't?
- Did a group name or explanation mislead you?
