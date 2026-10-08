# Correction class: "pay X life" additional cost parses to Fixed 0

Affects 8 entries in `corrections.json`: Bond of Agony, Fire Covenant, Fix
What's Broken, Hatred, Necrologia, Toxic Deluge, Vicious Rivalry.

Confirmed **exhaustive** across the full 34,645-entry snapshot — every card
whose `additional_cost` is a `PayLife` node with `amount.value == 0` while the
oracle text says "pay X life" is one of these 7. No others exist in this
snapshot.

## The defect

Each card's oracle text reads "As an additional cost to cast this spell, pay
X life." Every one parses to:

```json
"additional_cost": {
  "type": "Required",
  "data": { "type": "PayLife", "amount": { "type": "Fixed", "value": 0 } }
}
```

`Fixed 0` means the cost is free regardless of what X the caster announces,
while the spell's own effect (e.g. Toxic Deluge's `PumpAll{power:Variable "-X"}`)
still correctly references the chosen X. The cost and the effect disagree about
whether X is bound to anything. All 7 are labeled `clean` with 0
`parse_warnings` — nothing in the record signals the mismatch.

## Why this stays `kind:"flag"`, not `kind:"patch"`

The obvious fix is `amount: {"type":"Variable","value":"X"}`, mirroring how the
same cards' own effects encode `-X` elsewhere. But a full corpus scan (34,645
entries, every `abilities`/`triggers`/`static_abilities`/`replacements` bucket
plus every `additional_cost`) found **zero instances of a `Variable` node
inside any cost's `amount` field**, anywhere. `Variable` is only ever attested
in effect-side quantity slots (`amount`, `count`, `power`, `toughness`), never
in a cost slot.

That absence could mean either: (a) the engine's `PayLife` cost node genuinely
doesn't support a variable amount and X-life costs need a different
representation entirely (e.g. resolved through the X-value-choice machinery
that handles `{X}` in mana costs), or (b) it does support it and this is simply
the first case in the corpus that would exercise it. We can't tell which
without running their engine, which is out of scope for this tool. Patching in
a guess risks asserting a shape their engine may not build for, in a spot where
being wrong would be worse than being silent -- so all 7 stay flagged with full
evidence, not patched.
