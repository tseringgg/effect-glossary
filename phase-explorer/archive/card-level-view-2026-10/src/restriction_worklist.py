#!/usr/bin/env python3
"""Worklist for "round B": the restriction phrasings the parser kept only as
ParsedCondition::Unrecognized (unrecognized-restriction-fix overlay).

    python src/restriction_worklist.py   # -> reports/restriction-condition-worklist.md

Families are assigned by the first matching text rule, then ranked by card
count -- the same prioritisation as every gap-closing round. Each Unrecognized
`text` is the real restriction sentence, so a parser fix is a new phrase parser
in crates/engine/src/parser/oracle_condition.rs plus (where needed) a new
`ParsedCondition` variant; the round-1 fix deliberately parses nothing.
"""
import collections
import io
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OV = os.path.join(HERE, "data", "overlay", "unrecognized-restriction-fix.json")
OUT = os.path.join(HERE, "reports", "restriction-condition-worklist.md")

# An "Activate only A and only if B" sentence reaches the generic `activate only `
# branch whole, so the timing half (as a sorcery / during X / once each turn) is
# swallowed into the Unrecognized text instead of becoming its own restriction.
TIMING_PREFIX = re.compile(
    r"^(?:as a sorcery|during |once each turn|only once|once |before |at |if )", re.I)

FAMILIES = [
    ("city's blessing", lambda t, n: "city's blessing" in t),
    ("counters on a permanent", lambda t, n: "counter" in t),
    ('"this turn" / "this combat" events', lambda t, n: bool(re.search(r"this turn|this combat|this step", t))),
    ("life totals", lambda t, n: bool(re.search(r"\blife\b", t))),
    ("land counts", lambda t, n: bool(re.search(r"\blands?\b", t))),
    ("graveyard / hand / exile counts",
     lambda t, n: bool(re.search(r"graveyard|in hand|their hand|your hand|in exile|exile", t))),
    ("source state / self-name",
     lambda t, n: bool(re.search(r"\bthis (?:creature|artifact|permanent|land|card)\b|\bit's\b|isn't|"
                                 r"\bis attacking\b", t)) or n.split(",")[0] in t),
]


def family(text, name):
    for label, rule in FAMILIES:
        if rule(text, name.lower()):
            return label
    return "singletons / other"


def effective_cards():
    """Round 1's overlay with later overlays' faces substituted in (same order the build
    applies them), so the worklist shows what is STILL unrecognized."""
    cards = json.load(io.open(OV, encoding="utf-8"))["cards"]
    later = os.path.join(HERE, "data", "overlay", "activation-timing-split-fix.json")
    if os.path.exists(later):
        for oid, faces in json.load(io.open(later, encoding="utf-8"))["cards"].items():
            cards[oid] = faces
    return cards


def rows():
    out = []
    for oid, faces in effective_cards().items():
        for f in faces:
            for a in f["abilities"]:
                for r in a.get("activation_restrictions") or []:
                    c = (r.get("data") or {}).get("condition") if r["type"] == "RequiresCondition" else None
                    if isinstance(c, dict) and c.get("type") == "Unrecognized":
                        out.append(("activation", oid, f["name"], c["text"]))
            for r in f.get("casting_restrictions") or []:
                c = (r.get("data") or {}).get("condition") if r["type"] == "RequiresCondition" else None
                if isinstance(c, dict) and c.get("type") == "Unrecognized":
                    out.append(("casting restriction", oid, f["name"], c["text"]))
            for o in f.get("casting_options") or []:
                c = o.get("condition")
                if isinstance(c, dict) and c.get("type") == "Unrecognized":
                    out.append(("casting option", oid, f["name"], c["text"]))
    return out


def main():
    rs = rows()
    fams = collections.defaultdict(list)
    for r in rs:
        fams[family(r[3], r[2])].append(r)
    ranked = sorted(fams.items(), key=lambda kv: (-len({r[1] for r in kv[1]}), kv[0]))
    cards = {r[1] for r in rs}
    prefixed = []
    distinct = len({re.sub(r"\d+|\b(?:two|three|four|five|six|seven|eight|nine|ten)\b", "N", r[3]) for r in rs})
    w = []
    w.append("# Restriction-condition worklist (round B)\n")
    w.append(f"{len(rs)} restriction/option conditions on **{len(cards)} cards** are kept as "
             f"`ParsedCondition::Unrecognized` (round 1, a visibility fix). "
             f"{distinct} distinct phrasings once numbers are normalised. Fixing one means a real phrase parser "
             f"(and usually a new `ParsedCondition` variant); the engine currently evaluates all of them as `true`.\n")
    w.append("| rank | family | cards | activation | casting restriction | casting option |")
    w.append("|---:|---|---:|---:|---:|---:|")
    for i, (label, v) in enumerate(ranked, 1):
        c = collections.Counter(r[0] for r in v)
        w.append(f"| {i} | {label} | {len({r[1] for r in v})} | {c['activation']} | "
                 f"{c['casting restriction']} | {c['casting option']} |")
    w.append("")
    split_meta = None
    sp = os.path.join(HERE, "data", "overlay", "activation-timing-split-fix.json")
    if os.path.exists(sp):
        split_meta = json.load(io.open(sp, encoding="utf-8"))["meta"]
    stuck = [r for r in rs if r[0] == "activation" and re.match(r"(?:during|before) ", r[3])]
    suffix = [r for r in rs if r[0] == "activation" and re.search(r" and only as a sorcery$", r[3])]
    w.append("**Timing clauses swallowed into the text.**")
    if split_meta:
        w.append(f"Round B1 split the timing clause out of {split_meta['fixed']} cards' compound "
                 f"\"Activate only <timing> and only if <condition>\" sentences (AsSorcery, DuringYourTurn, "
                 f"DuringYourUpkeep, DuringCombat, OnlyOnceEachTurn, OnlyOnce are now emitted -- and enforced by "
                 f"the engine); their `if` remainders stay `Unrecognized` and appear below. "
                 f"Still swallowed, by design of that round:")
    w.append(f"- **{len(stuck)} activation texts** (18 whole blobs plus Grizzled Wolverine's leftover piece) are a timing phrase that has NO equivalent "
             f"`ActivationRestriction` yet: during the declare blockers / declare attackers / end-of-combat step, "
             f"during an opponent's turn / upkeep, during any upkeep step, before blockers are declared, before "
             f"the end of combat / combat damage step, during combat after blockers are declared, and "
             f"`before attackers are declared`. Each needs a new variant (reuse the `CastingRestriction` names: "
             f"`DeclareBlockersStep`, `DeclareAttackersStep`, `DuringOpponentsTurn`, `DuringOpponentsUpkeep`, "
             f"`DuringAnyUpkeep`, `BeforeBlockersDeclared`, ...) plus engine evaluation. Do NOT reuse "
             f"`BeforeAttackersDeclared` for Norritt / Arcum's Whistle / Nettling Imp: it requires the active "
             f"player to hold priority, but those are opponent-turn abilities; `BeforeCombatDamage` means "
             f"\"during combat before damage\", not Angus Mackenzie's \"before the combat damage step\".")
    w.append(f"- **{len(suffix)} activation texts** have the mirror form \"<condition> and only as a sorcery\" "
             f"(Balustrade Wurm, Resurrected Cultist, Speaker of the Heavens, Temple of Civilization / Cyclical "
             f"Time / Power / the Dead, Uchbenbak): they reach the `activate only if ` branch, where "
             f"`strip_once_per_turn_suffix` strips \"and only once (each turn)\" but not \"and only as a "
             f"sorcery\", so `AsSorcery` is swallowed the same way. Not touched in B1; the same split applies.")
    w.append("- Parseable remainders were deliberately NOT parsed in B1: the existing condition parser would "
             "give some of them a wrong, then-enforced meaning (\"you control a snow Mountain\" becomes the "
             "subtype `snow mountain`; Urza's Fun House's three-land clause becomes one made-up subtype). "
             "Fix those parses before enabling them.\n")
    for label, v in ranked:
        w.append(f"## {label} ({len({r[1] for r in v})} cards)\n")
        for side, oid, name, text in sorted(v, key=lambda r: (r[3], r[2])):
            w.append(f"- {name} [{side}]: {text}")
        w.append("")
    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(w))
    print("\n".join(w[:16]))


if __name__ == "__main__":
    main()
