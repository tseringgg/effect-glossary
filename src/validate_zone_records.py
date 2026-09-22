"""Narrow validation of the structured zone records, on known-tricky effects.

The checkpoint before any full-corpus rerun. Mill vs surveil is the case that
motivated adding direction + choice: both are library + graveyard under a flat
scheme, and only the choice flag separates them.

Effect text is pulled from the real corpus (data/full/effects.json) by pattern,
not hand-typed, so the cases are what the classifier will actually meet.

The last section audits the choice field across the WHOLE corpus: it must be a
plain bool everywhere, with no third value surviving anywhere in the pipeline.
"""
import json
import os
import re
import sys

import classify_zones as cz

HERE = os.path.dirname(os.path.abspath(__file__))
EFFECTS = os.path.join(HERE, os.pardir, "data", "full", "effects.json")
CARDS = os.path.join(HERE, os.pardir, "data", "full", "cards.jsonl")

# (zone, direction, choice) expectations. Each is "must be present exactly".
EXPECT = {
    "mill": [("library", cz.SOURCE, cz.NO_CHOICE), ("graveyard", cz.DESTINATION, cz.NO_CHOICE)],
    "surveil": [("library", cz.SOURCE, cz.NO_CHOICE), ("library", cz.DESTINATION, cz.NO_CHOICE),
                ("graveyard", cz.DESTINATION, cz.CHOICE)],
}


def load():
    with open(EFFECTS, encoding="utf-8") as fh:
        effects = json.load(fh)["effects"]
    with open(CARDS, encoding="utf-8") as fh:
        names = {c["card_id"]: c["name"] for c in map(json.loads, fh)}
    return effects, names


def pick(effects, pattern, n=3, exclude=None):
    rx = re.compile(pattern, re.I)
    hits = [e for e in effects if rx.search(e["raw_text"])
            and not (exclude and re.search(exclude, e["raw_text"], re.I))]
    return sorted(hits, key=lambda e: -e["occurrence_count"])[:n]


def show(effect, names, expect=None):
    zones, evidence, _ = cz.classify(effect["raw_text"], "")
    card = names.get(effect["card_ids"][0], "?")
    print("  [%s] %s" % (card, effect["raw_text"][:150].replace("\n", " ")))
    for r in zones:
        tag = "%s:%s" % (r["zone"], r["direction"])
        print("      %-24s %-10s  <- %s" % (tag, cz.CHOICE_LABEL[r["choice"]],
                                            ", ".join(l for _, l in evidence[tag])))
    ok = True
    if expect is not None:
        got = {(r["zone"], r["direction"], r["choice"]) for r in zones}
        for want in expect:
            if want not in got:
                print("      MISSING: %s %s %s" % (want[0], want[1], cz.CHOICE_LABEL[want[2]]))
                ok = False
    print("")
    return ok


def main():
    effects, names = load()
    failures = 0

    print("=" * 78)
    print("MILL  -- expect library:source and graveyard:destination, NO choice anywhere")
    print("=" * 78)
    for e in pick(effects, r"\bmills?\b", 3, exclude=r"dredge"):
        ok = show(e, names, EXPECT["mill"])
        zones, _, _ = cz.classify(e["raw_text"], "")
        if any(r["choice"] for r in zones):
            print("      UNEXPECTED CHOICE on a mill effect")
            ok = False
        failures += not ok

    print("=" * 78)
    print("SURVEIL  -- expect library:source / library:destination with no choice,")
    print("           graveyard:destination WITH choice")
    print("=" * 78)
    for e in pick(effects, r"\bsurveils?\b", 3):
        failures += not show(e, names, EXPECT["surveil"])

    print("=" * 78)
    print("CHOICE DETECTION  -- both wordings ('you may ...' and 'X or Y') set the")
    print("                    same flag. There is no second kind of choice.")
    print("=" * 78)
    for pattern in [r"madness \{", r"\bexplores\b", r"learn\. \("]:
        for e in pick(effects, pattern, 1):
            zones, _, _ = cz.classify(e["raw_text"], "")
            ok = any(r["choice"] for r in zones)
            failures += not ok
            if not ok:
                print("      NO CHOICE RECORD")
            show(e, names)

    print("=" * 78)
    print("BULLETED MODAL  -- extraction splits modes into separate effects;")
    print("                   modality is NOT recoverable per effect (known limit)")
    print("=" * 78)
    with open(CARDS, encoding="utf-8") as fh:
        card = next((c for c in map(json.loads, fh) if c["name"] == "Abzan Charm"), None)
    if card:
        from extract_effects import extract_effects
        for chunk in extract_effects(card["oracle_text"]):
            zones, _, _ = cz.classify(chunk, "")
            print("  |%s" % chunk)
            print("      %s" % (", ".join(cz.describe(r) for r in zones) or "(no zones)"))
        print("")

    print("=" * 78)
    print("REGRESSION  -- effects whose labels should not have moved")
    print("=" * 78)
    for pattern in [r"^Destroy all creatures\.$", r"^Draw a card\.$", r"^Counter target spell\.$",
                    r"^Flying$", r"^Flashback \{", r"enter as a copy of any creature on the battlefield\.$",
                    r"^\{T\}: Add \{G\}\.$"]:
        for e in pick(effects, pattern, 1):
            show(e, names)

    print("=" * 78)
    print("NEW DIRECTION RULES  -- zone pairs that used to collapse into one flat tag")
    print("=" * 78)
    for pattern in [r"^Return target creature to its owner's hand\.$",
                    r"^Search your library for a .{0,40}card, (?:reveal|put) it",
                    r"from your graveyard to your hand\.$",
                    r"^Each player discards a card\.$"]:
        for e in pick(effects, pattern, 1):
            show(e, names)

    print("=" * 78)
    print("CLEAN-COLLAPSE AUDIT  -- the whole corpus, not a sample")
    print("=" * 78)
    seen_values, seen_types = set(), set()
    for e in effects:
        for r in cz.classify(e["raw_text"], "")[0]:
            seen_values.add(r["choice"])
            seen_types.add(type(r["choice"]).__name__)
    print("  effects classified          %d" % len(effects))
    print("  distinct choice values      %s" % sorted(seen_values, key=str))
    print("  distinct python types       %s" % sorted(seen_types))
    leftovers = [n for n in dir(cz) if n.upper() == n and ("CERTAIN" in n or "OPTIONAL" in n
                                                           or "CONDITIONAL" in n or "RANK" in n)]
    print("  leftover three-way names    %s" % (leftovers or "none"))
    if seen_values - {True, False} or seen_types - {"bool"} or leftovers:
        print("  COLLAPSE IS NOT CLEAN")
        failures += 1
    else:
        print("  clean: choice is a plain bool everywhere, no third value survives")
    print("")

    print("VALIDATION FAILURES: %d" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
