# corrections.json schema

Hand-maintained overlay of known-wrong phase.rs parses. Applied on top of
`data/card-data.json` at our own build time (`src/build_index.py`) — never
edits their file, never forks their engine. This file is the audit trail:
every entry must be evidence-based, same discipline as
[KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md) and
[NAME_COLLISIONS.md](../NAME_COLLISIONS.md).

This is an ongoing log. Add an entry whenever a card's parse looks wrong
during real use, not only during a dedicated audit pass — see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Entry shape

```json
{
  "oracle_id": "8dcb35e5-ae44-455f-86e3-4a77d496ff34",
  "name": "Spark Double",
  "added": "2026-09-22",
  "kind": "flag",
  "severity": "silent-major",
  "field": "replacements",
  "issue": "One paragraph: what's wrong, in plain terms.",
  "evidence": {
    "oracle_text": "the real Oracle text, verbatim",
    "upstream_snippet": { "...": "the exact broken JSON fragment, taken from data/card-data.json" }
  },
  "patch": null,
  "note": "Why no patch was applied, or what a real fix would require."
}
```

| field | meaning |
|---|---|
| `oracle_id` | Scryfall oracle id. Matches on identity, never on face name — see [KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md) §1. |
| `kind` | `"flag"` — documented, not patched. `"patch"` — a real value substitution, applied at build time. |
| `severity` | `"silent-major"` (core function lost, 0 parse_warnings), `"silent-cost"` (cost/quantity wrong, 0 parse_warnings), `"flagged-minor"` (phase.rs's own signals already caught something, we're adding detail). |
| `field` | which bucket/field the defect lives in — for quick scanning, not machine-read. |
| `evidence.upstream_snippet` | the literal broken fragment, copy-pasted from the real snapshot. No paraphrasing — if this doesn't match `data/card-data.json` byte for byte at that path, the entry is wrong. |
| `patch` | `null` for `kind:"flag"`. For `kind:"patch"`, a list of `{"path": "dotted.path", "value": <replacement>}` applied to a deep copy of the raw entry before it's indexed. |
| `note` | for flags: why we didn't patch (usually: the correct value would use a node shape with no precedent elsewhere in the corpus in that slot, so we can't validate it without running their engine, which is out of scope). For patches: what precedent justified the value used. |

## Why `kind:"flag"` is the default, not `kind:"patch"`

A patch asserts a specific replacement JSON structure. We do not run phase.rs's
engine (explicit scope guard from the start of this project), so we have no way
to validate that an invented structure is actually well-formed for their
consumer — patching a wrong parse with a *differently* wrong, unvalidated one is
worse than clearly flagging it. A `patch` is only used when the corrected value
reuses a node shape **with existing precedent elsewhere in the same slot in this
same corpus** — i.e. we're not inventing new vocabulary, only correcting which
already-attested value applies to this card. Every `patch` entry's `note` must
cite that precedent.

Checked and rejected as unsafe to patch on this pass:
- `Variable` inside a cost `amount` (needed for the 7 "pay X life" cards) —
  **zero** precedent anywhere in the 34,645-entry corpus for `Variable` inside
  any cost slot.
- The type-conditional branching Spark Double needs (extra +1/+1 counter *if*
  creature, extra loyalty counter *if* planeswalker, in the same replacement) —
  `BecomeCopy` does co-occur with counter effects on 7 other cards, but none
  branch by copied-permanent-type in a way we could safely generalize from.

## How this is applied

`src/build_index.py` loads `corrections.json`, matches entries to raw records by
`scryfall_oracle_id`, and:
- for `kind:"patch"`, applies the value substitutions to a deep copy before
  indexing (the corrected value is what ships in `build/chunks/*.json`);
- for `kind:"flag"`, leaves the raw structure untouched but attaches the
  correction record for display.

Either way, every affected row gets a `corr` count in `build/index.json` and the
full record(s) in its chunk under `_corrections`, and the page surfaces it as a
separate, overlapping filter axis — this never overwrites or is implied by
phase.rs's own `clean`/`partial`/`unparsed` label, since the whole point is that
those labels missed it.
