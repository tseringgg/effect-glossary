# Loose groups for the unorganized pile: probe

Investigation only. Nothing was built, placed or changed. New files: `src/probe_loose_groups.py`, `build/loose_groups_probe.json`, `build/loose_groups_probe_reads.json`, this report. Pile: 5,593 cards ("Not yet organized"), taxonomy build as of this session. Everything below marked **measured** is a count from the build; **hand-read** is my reading; **estimate** is a guess.

## Part 1. The split (loose key per ability)

Coarse to fine: **L1** tree family; **L2** family + effect type; **L3** L2 + the fields below. A value of a chosen field seen fewer than 8 times within an effect type folds into "other". Fields are read from the parse only; no text matching.

| Family | Fields added at L3 | Why |
|---|---|---|
| Zone change | from, to, mass, controller | the zone pair is what a person looks for ("graveyard to battlefield") |
| Counters | counter kind, object, mass | "+1/+1 on a creature" vs "lore counter on this" |
| Pump / grant | sign, what is granted, object, mass | bigger vs smaller; which keyword |
| Static: continuous | what is granted, object | |
| Library | to, who | mill vs search vs put on top |
| Tokens | object, keyword | |
| Damage, Destroy, Tap / untap | object, mass | |
| Sacrifice | who, object | |
| Card draw, Life, Discard / hand | who | |
| Mana | object | |
| everything else | object | |

## Part 2. Assignment

Pile abilities usable in a tree family: 4,979 on 4,293 cards (**measured**). Sources: abilities of the pile cards the build kept as unplaced (1,416), abilities held for an unread part (1,524), abilities held for a dropped condition (1,442), gap-card abilities that failed a same-line / continuation test (597). Every assignment carries its reason (shape too rare; parser may have dropped a condition; part of the ability not read; card has an unread clause; no rules text of its own). 1,202 cards have every usable ability with an unread part, so a quarter of the loose groups' members would be on weaker ground than the real leaves.

## Part 3. Browsability (measured)

| Level | Groups | <10 cards | 10-50 | 51-100 | >100 |
|---|---|---|---|---|---|
| L1 family | 28 | 1 | 4 | 10 | 13 |
| L2 effect type | 139 | 87 | 28 | 12 | 12 |
| L3 chosen fields | 515 | 381 | 121 | 10 | 3 |
| L3, groups <10 folded into "Other <effect type>" | 252 | 98 | 136 | 12 | 6 |

Largest 15 at L3: Card draw > Draw cards 223; Counters > put counters on this permanent, other kinds 117; ...+1/+1 counters 108; Damage > creature 91; Zone change > to exile 87; Tokens > creature 86; Zone change > return to hand 67; Library > search to hand 65; Attach > creature 64; Destroy > creature 58; Damage > any target 56; Static continuous > this permanent, add power 54; Counter spell > a spell 52; Destroy > artifact 50; Sacrifice > creature 47.

Reach: 4,293 cards get at least one loose group; 3,970 sit in a group of 100 or fewer; 323 only in groups over 100; 3,419 in a group of 50 or fewer. Average 1.14 groups per card, maximum 4. At L2 alone only 1,727 cards reach a group of 100 or fewer, so the fields at L3 are what make it browsable. With small groups folded into "Other": 3,530 cards in a visible group of 100 or fewer.

## Part 4. Coherence hand-check (seed 20261016, set before computing)

**Draw limits, plainly:** the over-100 stratum has only 3 groups in the whole split, so 10 could not be drawn. The draw was 10 from 10-30, 10 from 31-100, 3 from over 100 = **23 groups**, not 30. No redraw, no hand-filling. 23 groups cannot show a rate.

I read 8 member abilities per group from the text, wrote my read and verdict to `build/loose_groups_probe_reads.json`, then revealed the keys.

Result: **0 incoherent, 14 coherent, 9 loose.** Bar (more than 25% incoherent means too coarse) is not tripped, but 0 of 23 only says the rate is probably not high. The nine "loose" groups were: sacrifice (two groups), copy a spell/ability, creature tokens, exile, cast from a zone, draw a card (223 cards, mixed triggers), +1/+1 counters on "this permanent" (one member exiles and returns), and "other counters on this permanent".

Where the read and the key differed: my read was never wider than the key, but three keys were narrower than the text suggested (G12 copy: spell vs ability vs exiled card are mixed; G19 cast: "any target" says nothing about casting from a graveyard; G21 holds a card that exiles and returns a permanent). **Fields to add if this is built:** copy (what is copied: spell / ability / card), cast (from which zone), sacrifice (the sacrificed thing's type as a field of its own, not "object"). **Fields that earn nothing:** mass and controller where nearly every member shares one value.

**The three old junk drawers (measured, then read):** Zone change splits into 69 groups, all of 100 or fewer cards (to exile 87, return to hand 67, graveyard to battlefield 42...). Pump / grant splits into 109 groups, largest 43. Counters splits into 44 groups; the two largest, "this permanent, other kinds" 117 and "+1/+1 on this permanent" 108, remain over 100. Verdict: **Zone change and Pump / grant are now findable; Counters is findable except those two.**

## Part 5. Name test (20 of the 23 sampled groups, seed 20261017)

Names are built from field values with fixed wording; not polished. Whole set of 515: 114 hard template defects (after excluding the family prefix; examples: "Cant attack affecting other (other kinds)", "Add mana of fixed"), 6 claims hits ("change" stem), 0 over 110 characters. Of the 20 checked against their members: **2 would mislead** (G12 "Copy a spell affecting the same object" while 3 of 8 copy abilities or an exiled card; G19 "Cast a card affecting any target" while members cast from graveyards or reduce cost). Another 5 are opaque rather than wrong ("...affecting other (other kinds)"). 2 of 20 is not a rate. The drafted names would need real template work before tester use; "other kinds" and "affecting" read badly.

## Part 6. The 1,300 cards with no family at all (measured)

| Reason | Cards |
|---|---|
| Gap card (parser left a part unread, nothing usable) | 1,231 |
| Not parsed | 27 |
| No effect | 24 |
| Parse mistake | 8 |
| Text may be lost | 9 |
| Too unusual | 1 |

None lack rules text. 1,147 have a popularity rank; **80 are in the top 3,000** and 324 in the top 10,000. Most popular: Toxic Deluge (parse mistake), Reflecting Pool, Doubling Season, Bloom Tender, Academy Manufactor, Anointed Procession, Spark Double (parse mistake), Dauthi Voidwalker, Parallel Lives, Opposition Agent.

**Proposal:** a section "Cards we couldn't read yet", sorted by popularity, each row showing the card and the plain reason ("the reader missed part of this card's text"), unranked cards at the end. It is a list, not a classification, and carries no rule claims.

## Part 7. Design (not built)

- **Place in tree:** under "Not yet organized", a sub-section "Loosely grouped (unchecked)" with the family > effect type > detail levels; groups under 10 folded into "Other <effect type>"; a card shows under every group it fits. Next to it: "Cards we couldn't read yet".
- **Wording on each group and card page:** "Loosely grouped by the parts the reader understood. Not checked, and not counted as organized." Each card line shows the reason it isn't a real placement (rare shape / may have a dropped condition / part not read).
- **Find a card:** a card in the pile resolves to its loose groups with the same "unchecked" label and links; "couldn't read yet" cards say so.
- **Headline:** loose membership never feeds the headline, leaf formation or the 5-member rule. Reconciliation stays placed + unorganized + not cards = universe; each pile card still counts once as unorganized, however many loose groups hold it. The page keeps the loose view in separate data (`loose.json`), not in the cards/ledger files. No tag data in placement.

## Part 8. Recommendation

**Worth building, in the rolled-up form, as a clearly separate section.** **Measured:** with the L3 split, 3,970 of 4,293 cards with a usable ability (3,530 in the rolled form) are in a group of 100 or fewer, versus today's one flat list of 5,593; 23 sampled groups had 0 incoherent. **Estimate (not measured):** a tester could reach about 60-70% of the pile in two clicks (family, then group) and could find about 3,500 cards by browsing; the 1,300 unreadable cards stay reachable only through the "couldn't read yet" list. The rest (about 300 over-100 only) need the added fields. **Add:** copy target, cast-from zone, sacrificed type. **Drop:** mass and controller fields where they don't split. **Before showing testers:** name template work, and a larger coherence check. 23 groups and 20 names are not enough to promise a rate.

Frozen files and the archive were not touched; `git status` shows only the new untracked files; nothing committed.
