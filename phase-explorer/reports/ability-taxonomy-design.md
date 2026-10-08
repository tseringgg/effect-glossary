# Per-ability taxonomy as the main view: Part 1 result and Part 2 design

Nothing has been built. This reports the archive (Part 1) and proposes the design (Part 2), for approval before Part 3.
Measurements come from `src/design_probe_ability_taxonomy.py` -> `build/ability_taxonomy_design_probe.json`. It reuses probe 2's field
extraction, rarest-field-first backoff (minimum 5) and flag rules unchanged, with the scope and rule differences listed in §9.
No Scryfall tag data is used anywhere.

## Part 1: the archive

`archive/card-level-view-2026-10/` (144 MB, 172 files) holds the four pages (`browse`, `ledger`, `card-explorer`, `review-queue`),
`cardview.js`, `branchmap.js`, `findcard.js`, the linked reports, every `build/` file the pages fetch (including the 64 chunks),
`corrections/`, `data/overlay/`, the 51 old generator scripts from `src/` unmodified, and today's project docs. Its `README.md` has the run
order and the old view's final numbers: **26,085 of 34,864 placed (74.8%), 8,779 not yet organized, 657 leaves** (universe 38,921,
4,057 not cards).

**Hashes.** `MANIFEST.sha256` lists live-before, live-after and archived hash per file. I then re-checked independently:
**168 of 168 non-page files are byte-identical to the live files** (before, after and archived all equal). The four HTML pages
are the one deliberate difference: each has one banner `<div>` inserted after `<body>`, so the brief's "banner on archived pages"
and "byte-identical" cannot both hold for them. For those four I recorded the live hash and the archived hash, and removing the
exact banner string from the archived page reproduces the live hash:

| page | live sha256 (unchanged) | archived (with banner) |
|---|---|---|
| browse.html | `946e7a92fba1…` | `31a52f615eed…` |
| ledger.html | `c85eb7bb982e…` | `c2804fa1e2fd…` |
| card-explorer.html | `d9cdffb54a96…` | `79aebc206291…` |
| review-queue.html | `ade5f72dbe86…` | `4df1c6bf0782…` |

Banner text: "Archived card-level view. Numbers here do not match the current view." The whole live tree (232 files) was also hashed
before and after: nothing changed except one new file (`src/archive_card_level_view.py`). Nothing was committed.

**What was and was not checked.** No browser is available in this environment. I served the archive over HTTP, confirmed all four
pages return with the banner, and that all 33 distinct `../build/...` and `../corrections/...` files they fetch resolve (0 failures).
That does not show the pages render or that clicks work. The `build/` copies are ignored by git under the existing rule, so they stay local.

---

## Part 2: design

### 1. Inventory of the 38,921-card universe by how the new view handles each card

Exclusive state per card (priority order shown), measured with the rules in §9. "Placed" means at least one clean ability sits in an
unflagged leaf of 5 or more abilities.

| new-view state | cards | notes |
|---|---:|---|
| not a card (token, art card, emblem, plane, ...) | 4,057 | unchanged |
| keyword block (keyword-only cards) | 1,262 | unchanged; no ability items, so no overlap |
| "No abilities" | 351 | unchanged |
| replacement and cost groups (old signature layer) | 209 | kept as its own block, §2 |
| **placed by ability signature** | **22,371** | on average 1.35 leaves per card |
| in a broad group only (all its abilities sit in flagged leaves) | 2,604 | organized but kept out of the headline, §6 |
| **Not yet organized** | **8,067** | by reason, §5 |
| total | 38,921 | reconciles |

Not yet organized by reason: gap 5,709, too unusual 1,207, part of its text may not have been read 1,086, no effect to group 28, not
parsed 29, known parse mistake 8.

**Coverage** (in scope = 34,864):

- headline (placed + keyword + no abilities + replacement groups) = **24,193 = 69.4%**
- including broad-group-only cards = 26,797 = 76.9%
- the archived view: 26,085 = 74.8%
- the headline is lower because gap-card abilities are held out (1,519 gap cards would have a passing placed ability if included;
  not counted until the step-6 check), because 1,086 cards have only flagged-by-detector abilities, and because 2,604 cards are
  in broad groups only.

**Overlaps.**

- 8,193 of the placed cards also have keywords. They are placed by their abilities, and the keywords show as plain card detail.
- 4,816 clean cards have an ability in a flagged leaf; 2,604 of them have nothing else.
- Cards in several leaves: 22,371 placed cards have 30,100 or so card-leaf memberships (mean 1.345, max 6).
- One two-faced card (Fast // Furious) has a clean face and a gap face. The card-level rule below sends it to gap.

**Old state against new view** (old counts from `lookup.json`):

| old state | cards | placed now | broad only | block | not organized now |
|---|---:|---:|---:|---:|---|
| clustered | 21,788 | 17,814 | 2,303 | | 988 text may be lost, 680 too unusual, 3 no effect |
| nearby (proximity) | 1,303 | 1,173 | 100 | | 29 too unusual, 1 gap |
| placed by one ability | 1,172 | 694 | 19 | | 456 gap, 3 too unusual |
| replacement-effect groups | 209 | | | 209 | |
| keyword block | 1,262 | | | | (keyword block unchanged) |
| "No abilities" | 351 | | | | ("No abilities" unchanged) |
| not organized | 8,779 | 2,690 | 182 | | 5,907 |

**Cards placed before that are not specifically placed now: 4,582**: 2,422 now in a broad group only, 988 held back by the
condition-drop detector, 712 too unusual, 457 gap cards, 3 no effect. **Cards unplaced before and placed now: 2,690** (plus 182 in broad groups).

### 2. Prevention and replacement cards: keep the old signature layer, as a block

The old layer holds 209 cards in 13 groups: 8 counter replacements, 20 damage changes, 10 doublings, 5 mana replacements, 47 prevent-all,
32 limited prevent-combat, 14 fog, 20 prevent-to-creatures, 14 prevent-to-players, 15 next-N shields, 7 redirects, 10 other prevention, 7 additional costs.

Probe-2 signatures would place 176 of the 209 (84%) from the replacement items themselves. They are placed coarsely: the signature
reads only string fields and drops the dict-valued ones that carry the shield kind and redirect. Fog, next-N shields, redirects and
limited shields therefore collapse into 128 abilities with a bare `DamageDone` signature plus a few sub-leaves by combat scope or damage target.
In the probe, the damage-replacement items fall into only a handful of leaves, and 128 of them share the one bare leaf, so the old layer's hand-checked distinctions are lost there.

**Proposal: keep the signature layer unchanged and show it as one top-level family, "Replacement effects and costs"**, with its 13 groups
and 209 cards. Replacement items that have no effect node (the `repl:*` signatures) are then *not* placed as ability leaves
(ledger reason `replacement_group`). Replacement items that do have an effect node (for example "enters tapped", which parses as a Tap effect) stay in
ability leaves. 2,180 cards have replacement items; 1,649 of them are placed by ability.

Why not absorb it: absorbing means adding replacement-only fields (shield kind, redirect, modification) and the two text gates to
the signature code, which is a rule change that needs its own hand check. Keeping it costs nothing: it is already hand-checked, and the 209 cards do not otherwise overlap with ability leaves.

### 3. The tree: families, effect-and-verb nodes, leaves

**Three levels.** *Family* (29 from the effect-type map, for example Destroy, Card draw, Counters, Static: restriction, plus the replacement block = 30) -> *effect-and-verb node*
(effect type plus its verb parameters: zone from/to, counter type, player scope, granted modification) -> *leaf* (the node plus the object and, where
needed, controller, all-or-one and detail). A node with no verb parameters is just the effect type, so Destroy is one node holding all its leaves.
Example, Destroy (1,326 abilities): leaves of 10 or more are creature · one 174, artifact · one 143, creature · all 98, artifact or enchantment ·
one 96, land · one 79, enchantment · one 72, and so on; 25 smaller leaves (160 abilities) sit under "Other Destroy".

**Rolling up.** A leaf under the display threshold does not appear as its own row. Its abilities are listed under its node, in a single
entry "Other <node>" that shows each ability's signature as a chip. A node that has no visible leaf is still shown, with only that entry.

**Several leaves per card.** A card is listed under every visible leaf, or roll-up entry, one of its abilities fits. In each list the row
shows the text of the ability that put it there; abilities that matched the same leaf are folded into "+1 more". On the card's detail view
a line "Also in:" lists its other leaves (up to 6) as links; its remaining abilities show as plain card detail, as now.

**Sizes** (clean-built leaves; flagged leaves excluded from these rows):

| threshold | visible leaves | abilities in them | rolled up | effect-and-verb nodes (with a visible leaf / all) | cards with a visible leaf | cards only via a roll-up | visible leaves per card: mean / max | entries per card: mean / max |
|---:|---:|---:|---:|---:|---:|---:|---|---|
| 5 | 1,119 | 30,868 | 0 | 275 / 275 | 22,372 | 0 | 1.345 / 6 | 1.345 / 6 |
| **10** | **627** | 27,613 | 3,255 | 207 / 275 | 20,353 | 2,019 | 1.20 / 5 | 1.344 / 6 |
| 20 | 329 | 23,646 | 7,222 | 140 / 275 | 17,918 | 4,454 | 1.03 / 5 | 1.343 / 6 |

Families: 29 plus the replacement block. One of the 29 is the fallback family "Other" (Tribute, ChooseFromZone, a pending-counter effect: 14 abilities, one leaf of 11). That is a miscellaneous bucket in all but name, so **the build will map those three effect types into real families, and any effect type with no family stays unplaced**. At threshold 10 the tree has about **30 + 275 + 627 = 930 rows** of which 81 more flagged leaves
show in a separate section (§6). Every placed card stays reachable at every threshold, because a roll-up entry is an entry. 13 cards appear
in five or more entries.

**Node-size distribution** (all 1,746 nodes): fewer than 5 abilities 500, 5 to 9 538, 10 to 19 335, 20 to 49 248, 50 to 99 74, 100 to 499 41, 500 or more 10.

### 4. What a placed ability shows

About 93% of placed abilities have their own rules text. The rest are handled so each card row still shows something real:

- **modal modes** (902): shown from the card's own mode list; 895 of 902 align with it, and the other 7 fall to the generic rule below
- **keyword-generated** (542, mostly equip): shown as the keyword line, "Equip {2}"
- **others** (705: spells with no description, basic-land mana abilities, some statics): shown as "(no separate rules line)" plus the leaf name

**Inline modal placeholders.** 246 abilities on 239 cards hold their modes inside one item. Probe 2 placed the placeholder itself, in a bare "Modal" leaf that says nothing
about the modes (206 cards are placed only that way). Reading each mode as its own ability gives 601 mode abilities; 490 land in
unflagged leaves of 5 or more, 74 in flagged leaves, 27 elsewhere, and 227 of the 239 cards get a placeable mode. **Proposal: read the modes
as abilities; the placeholder is not placed** (ledger reason `modal`).

### 5. "Not yet organized" groups

Wording follows the current groups (plain language, "the tool, not the card"). "Review queue" does not appear in tester-facing text; `?dev=1`
keeps dev-only views (signature strings, per-ability ledger reasons, orphaned corrections).

| group | cards | what puts a card there | tester-facing explanation (draft) |
|---|---:|---|---|
| Parsed, but with a gap | 5,709 | partial or unmodelled status; v1 holds gap-card abilities out | "The parser read most of this card but could not understand part of its text (shown next to the card). We don't group a card on a partial reading, because it could put it in the wrong place." (unchanged) |
| Parsed, but too unusual to group | 1,207 | every usable ability has a shape that fewer than five abilities share | "The parser read this card fully, but its abilities are rare: fewer than five other abilities have the same shape, so there is no group of five to put it in yet." (replaces "no close group found"; there is no similarity score any more) |
| Parsed, but part of its text may not have been read | 1,086 | all of its abilities were held back by the check for dropped conditions | "A check found that the parser may have left out a condition (an “if”, “unless” or “as long as”) from this card's abilities. We don't group an ability that may be incomplete." |
| No effect to group | 28 | replacement or cost rules not covered by the groups in the replacement block | unchanged |
| Not parsed yet | 29 | unchanged | unchanged |
| Known parse mistake | 8 | unchanged | unchanged |

No "Miscellaneous" group exists. The old "No rules text: newer cards" group is empty and is not listed.

### 6. Ledger reporting and reconciliation

- **Existing `status` values are kept verbatim**, including the 13 current ones. They are parse-quality facts, plus the two older placement-derived ones
  (`placed_by_ability`, `keyword_only`) that stay as they are until nothing reads them. `ledger.json` and `build_ledger.py` are not touched.
- **New derived fields**, on a new file `build/ability_taxonomy_ledger.json`, shown here before anything is built:
  - per card: `view` (one of `not_a_card`, `keyword_block`, `no_abilities`, `replacement_group`, `placed`, `broad_only`, `unorganized`),
    `view_reason` (for `unorganized`), `leaves` (ids) and `leaf_count`, plus `parse_status` copied from the ledger.
  - per ability (one row per ability item, 50,672 today): `state` (`placed`, `placed_broad`, `unplaced`, `held_out`), `reason`, `leaf`, `signature`.
- **Reconciliation.** Each card has exactly one `view`, so the card sums reconcile as now: 4,057 + 1,262 + 351 + 209 + 22,371 + 2,604 +
  8,067 = 38,921. A second line reconciles the many-to-many part: sum over leaves of members = sum over placed cards of `leaf_count`.
  A card is counted once in the universe and once per leaf in the leaf totals; the page says which it is showing.
- **Abilities per reason** (all 50,672 rows):

| reason | abilities |
|---|---:|
| placed (headline) | 30,868 |
| gap-card ability, held out in v1 (1,759 of them would place) | 2,291 |
| gap-card item gap or failed same-line / continuation / no-text tests | 6,670 |
| flagged by the condition-drop detector | 2,847 |
| in a flagged generic leaf (`flagged_generic`) | 5,095 |
| below minimum size (node under 5) | 1,012 |
| rare object for its effect (`rare_object`) | 682 |
| rare verb parameter | 657 |
| replacement group (no effect node) | 346 |
| item holds a gap node | 168 |
| rare effect type / no signature / card not in scope | 22 / 7 / 7 |

### 7. Flagged generic leaves

They are shown, not hidden, in the leaf's node, with a "broad group" badge and a plain note, and are listed in a separate section "Groups
broader than they look" with the same wording. They hold 4,802 abilities in 81 leaves of 10 or more (156 flagged leaves in all). Their cards are
counted in the "broad group only" line, not in the headline.

| flag | note shown to the tester |
|---|---|
| who draws | "Who draws isn't recorded, so this group is broader than it looks: it mixes “you draw” with “target player draws” and “each opponent draws”." |
| return all or target | "“Return all” and “return target” are recorded the same way, so this group mixes mass return with single-target return." |
| self-return source | "Where the card returns from isn't recorded, so “return this from your graveyard” and “return this from the battlefield” are mixed." |
| unresolved object | "The parser doesn't say what this applies to (it recorded “that thing” or “any target”), so the group is broader than it looks." |

The largest: Draw 1,868 (who draws), Draw plus discard 244, return-self-to-hand 180, return a creature 121. Mulldrifter is a broad-group-only card.

### 8. Naming

**Rules.**

1. A name is built mechanically from the signature, using only rules vocabulary (destroy, exile, sacrifice, scry, surveil, return to hand, ...)
   plus the object, controller and all-or-one words already in the signature. Each is `auto_named: true`.
2. Where an established term exists for the whole signature (Surveil, Investigate, Monstrosity, Time travel), the name is that term; 41 of the 708 leaves
   of 10 or more are bare effect types of this kind.
3. `coined: true` marks any name containing a label we invented, and any community term (for example "Fog", "anthem") carries a `basis` line, as the current signature layer does.
4. The member buckets (replacement versus trigger versus ability) may be read **for naming only**, so that "Tap this permanent"
   is not shown for the 734 "enters tapped" replacements that share one leaf.
5. Names are never used to place anything.

**Corrections file** `corrections/ability_taxonomy_names.json`, keyed by signature string (as decided):
`{"v": 1, "leaves": {"<signature>": {"name": "...", "coined": false, "basis": "...", "note": "..."}}, "nodes": {"<family>|<effect>|<verb parameters>": {...}}, "families": {...}}`.
A rebuild applies any key that still exists and *reports* orphaned keys rather than dropping them.

**Workload at threshold 10.** 627 unflagged and 81 flagged leaves (708), 275 nodes (207 with a visible leaf, 68 shown only as a roll-up entry), 30 families:
about 1,013 names. Of the 708 leaves, 421 have an effect type that is a rules verb, 123 are statics, 164 other effect types (grants and the like).
Illustrative auto-names: `Destroy · Land · all` -> "Destroy all lands"; `PutCounter · m1m1 · Creature · one` -> "Put a −1/−1 counter on a creature";
`Discard · each opponent` -> "Each opponent discards"; `static · AddPower,AddToughness · Creature[enchanted]` -> "Enchanted creature gets +N/+N".

### 9. Rule differences from probe 2 (all of them)

1. **Leaves are built from clean abilities on clean cards only.** Gap-card abilities that pass the partial layer's tests (2,291) are assigned
   against those counts and add nothing to any count. Probe 2 built from both.
2. **Replacement items with no effect node are not placed as ability leaves** (they stay in the replacement block, §2).
3. **Inline modal placeholders are replaced by their modes** (§4), subject to your approval.
4. **A card's kind is decided per card, not per face**: a card with any gap face is a gap card (one card, Fast // Furious, differs).
5. Everything else is identical to probe 2: fields, rarest-field-first backoff, the bare-fallback guard, flag rules, minimum 5, headline = unflagged leaf of 5 or more.

### 10. Named lookups, as the design would answer them

| lookup | would say |
|---|---|
| Armageddon, Ravages of War | placed: "Destroy all lands" (16 abilities, both cards) |
| Death Cloud | placed: "Each player loses life" (24); its land sacrifice is not in the signature |
| Global Ruin | not yet organized: too unusual |
| Shuri | placed: "Artifact spells cost {1} less" (5; shown under its node, below the display threshold) |
| Mulldrifter | in a broad group only: draw ("who draws isn't recorded") |
| Spark Double | not yet organized: known parse mistake |
| Lightning Bolt | placed: "Deal damage to any target" (526). The data's only entry is the Strixhaven prepare-layout face (KNOWN_LIMITATIONS §1) |
| Storm Crow | keyword block (Flying); a separate token entry of the same name is listed after the card |
| Yargle, Grizzly Bears | "No abilities" |
| Jeska, Thrice Reborn | not yet organized: parsed, but with a gap |
| Treasure (a token), Akoum (a plane) | not a card, with the reason shown |

---

## Decisions I need from you before Part 3

1. **Cards in flagged leaves only (2,604).** I propose a separate "in a broad group only" state, shown in the tree with the note and excluded from the headline, rather than counting them as Not yet organized. If you would rather count them, the headline stays 69.4% and "Not yet organized" becomes 10,671.
2. **Abilities flagged by the condition-drop detector (2,847 abilities; 1,086 cards have nothing else).** I kept the existing rule (held back), which costs the most against the old view. The alternative is to place them with a "may be incomplete" marker and keep them out of the headline.
3. **Replacement groups**: keep the old layer as a block (proposed) or absorb it.
4. **Inline modal**: read the modes as abilities (proposed).
5. **Seed** for Part 4's hand checks: **20261008**, set now. It is new (probes used 20261006 and 20261007) and is fixed before anything is computed.

The headline will not equal the archived 74.8%, and I will not relabel anything to make it. The gap is explained by gap-card abilities held out (about 1,519 cards, pending the step-6 check), condition-flagged cards (1,086), and the separate broad-group state (2,604).
