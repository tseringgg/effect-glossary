<!--
DRAFT ONLY. Not submitted anywhere. If you want this filed against
github.com/phase-rs/phase, open it as an issue yourself (or ask this tool to
draft the `gh issue create` command) -- outward-facing actions like filing on
a third-party repo aren't done without you explicitly asking for it.

Source data: the 2026-04-20 card-data.json snapshot. Re-verify both findings
against the current snapshot before submitting, in case either has already
been fixed.
-->

# Two silent parse defects found via oracle-text spot-check (2026-04-20 snapshot)

Both were found by comparing phase.rs's parsed structure against Scryfall's
oracle text for cards outside any automated coverage sweep -- neither is
flagged by `parse_warnings`, and both cards are labeled with no gap nodes
(`Unimplemented`/`GenericEffect` absent).

## 1. Spark Double: entire copy effect missing

**Card:** Spark Double, oracle id `8dcb35e5-ae44-455f-86e3-4a77d496ff34`

**Oracle text:**
> You may have this creature enter as a copy of a creature or planeswalker you
> control, except it enters with an additional +1/+1 counter on it if it's a
> creature, it enters with an additional loyalty counter on it if it's a
> planeswalker, and it isn't legendary.

**Parsed `replacements` (the only ability-bearing field on the card):**

```json
[
 {
  "event": "Moved",
  "execute": {
   "kind": "Spell",
   "effect": {
    "type": "PutCounter",
    "counter_type": "P1P1",
    "count": { "type": "Fixed", "value": 1 },
    "target": { "type": "SelfRef" }
   },
   "cost": null, "sub_ability": null, "duration": null, "description": null,
   "target_prompt": null, "sorcery_speed": false, "condition": null,
   "optional_targeting": false, "optional": false, "forward_result": false
  },
  "mode": { "type": "Mandatory" },
  "valid_card": { "type": "SelfRef" },
  "description": "You may have this creature enter as a copy of a creature or planeswalker you control, except it enters with an additional +1/+1 counter on it if it's a creature, it enters with an additional loyalty counter on it if it's a planeswalker, and it isn't legendary.",
  "condition": null
 }
]
```

**What's missing:** the actual copy effect (`BecomeCopy`, or whatever the
current internal name is) is entirely absent -- only a bare, unconditional
+1/+1 counter survives. Also lost: the type-conditional branching (+1/+1 *iff*
creature, loyalty counter *iff* planeswalker), the "isn't legendary" override,
and the optionality ("may") -- `mode` is `Mandatory`, not `Optional`.

**Comparison:** Clone, Phantasmal Image, and Clever Impersonator all correctly
parse the near-identical lead-in ("may have this creature enter as a copy of
X") to a `BecomeCopy` effect (verified in the same snapshot), so this looks
like an isolated regression on this specific card/oracle-text variant rather
than missing support for the mechanic in general.

**Severity:** the card is a well-known Commander/cube staple whose entire
function is the copy effect; the parsed structure represents essentially none
of what the card does.

## 2. "Pay X life" additional costs parse to `Fixed 0`

Exhaustively confirmed across the full 34,645-entry snapshot -- affects exactly
these 7 cards, all with the same defect:

| card | oracle id |
|---|---|
| Bond of Agony | `8e7bd5ae-005a-47d8-90bc-69f48cd8793d` |
| Fire Covenant | `025939a0-424a-41bf-8fc9-2ef9ea5485f7` |
| Fix What's Broken | `7f8f46c0-889a-4c9a-9bfa-2b43db608d55` |
| Hatred | `40601061-1b25-4db8-8b99-33324ce945cf` |
| Necrologia | `925f11c3-fd32-4aa7-a130-6554b81ad3eb` |
| Toxic Deluge | `afaef788-34d1-460b-b884-9d7ae6ddeb18` |
| Vicious Rivalry | `90898c76-21f9-4597-88fe-dc9179911cde` |

Example -- **Toxic Deluge**:

**Oracle text:**
> As an additional cost to cast this spell, pay X life.
> All creatures get -X/-X until end of turn.

**Parsed `additional_cost`:**

```json
{ "type": "Required", "data": { "type": "PayLife", "amount": { "type": "Fixed", "value": 0 } } }
```

**Parsed effect (for reference -- this half is correct):**

```json
{ "type": "PumpAll", "power": { "type": "Variable", "value": "-X" },
  "toughness": { "type": "Variable", "value": "-X" }, "target": { "...":"Typed[Creature]" } }
```

The effect correctly binds to a `Variable "-X"`. The cost does not -- it's
`Fixed 0`, so the spell is parsed as costing zero life regardless of what X the
caster announces, while the board-wipe strength still scales with that same X.
The two halves of the same card disagree about whether X is bound to anything.

**Reproduction:** search the snapshot for any `additional_cost.data.type ==
"PayLife"` node where `amount.type == "Fixed"` and `amount.value == 0`, cross-
referenced against oracle text containing "pay X life". All 7 hits are listed
above; nothing else in the corpus matches.

**Possible root cause (speculative, not verified against the parser source):**
if `PayLife`'s `amount` field doesn't currently accept a `Variable` node at
all, X-life costs may need routing through whatever machinery resolves `{X}`
in a mana cost, rather than through the plain cost-amount path.

---

Both cards/classes are `clean`-labeled with zero `parse_warnings` in the
snapshot used, so neither would surface via existing coverage dashboards without
this kind of manual, oracle-text-level spot-check.
