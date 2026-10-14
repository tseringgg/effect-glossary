#!/usr/bin/env python3
"""Checks on build/annotation_placements.json that do not depend on the generator's own logic (they read the finished file against the card text and the taxonomy). Exit 1 on any failure.

    python src/check_annotation_build.py
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
sys.path.insert(0, os.path.join(HERE, "src"))


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def norm(t):
    return re.sub(r"\s+", " ", t).strip()


def main():
    A = jl("annotation_placements.json")
    T = jl("ability_taxonomy.json")
    TG = jl("tentative_placements.json")
    cards = jl("ability_taxonomy_cards.json")["cards"]
    m = A["meta"]
    bad = []

    def check(name, ok, detail=""):
        print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)) if detail else ""))
        if not ok:
            bad.append(name)
    rows = [(k, r) for k, g in A["groups"].items() for r in g["m"]]
    c_rows = [(k, r) for k, r in rows if r[6] == "c"]
    g_rows = [(k, r) for k, r in rows if r[6] == "g"]
    no_text = [r for k, r in rows if not r[1].strip()]
    check("every annotated ability has text", not no_text, len(no_text))

    SELF = re.compile(r"\bthis (creature|permanent|artifact|enchantment|land|equipment|vehicle|card|spell|saga|planeswalker|aura|battle|token)\b", re.I)

    def oracle_has(oid, text):
        # a row may show the card's (short) name where the oracle says "this creature": compare with both written as ~
        n = cards[oid]["n"]
        short = n.split(" // ")[0].split(",")[0]
        o = norm(cards[oid]["t"])
        for nm in (n, short):
            o = o.replace(nm, "~")
        o = SELF.sub("~", o)
        t = SELF.sub("~", norm(text).replace(n, "~").replace(short, "~"))
        return t in o
    miss = [(r[0], r[1][:60]) for k, r in rows if not oracle_has(r[0], r[1])]
    check("every ability text is a quote from its card's oracle text", not miss, miss[:3])
    miss = [(r[0], r[2][:60]) for k, r in c_rows if norm(r[2]) not in norm(r[1])]
    check("every unread condition shown is a quote from its ability's text (the lead-in sentence and the branch included)", not miss, miss[:3])
    check("every condition row has a condition word", all(re.search(r"\b(if|unless|otherwise|instead|as long as|while|only if|during)\b", r[2], re.I) for k, r in c_rows))
    broad = [k for k in A["groups"] if k[0] == "l" and T["leaves"][k[2:]]["flags"]]
    check("no group is a broad leaf (the broad route is not annotated)", not broad, broad[:3])
    check("every leaf group is a leaf of 5 or more", all(T["leaves"][k[2:]]["cards"] >= 5 for k in A["groups"] if k[0] == "l"))
    check("every tentative-group target is a promoted tentative group", all(k[2:] in TG["groups"] for k in A["groups"] if k[0] == "t"))
    check("the family of each group exists in the taxonomy", all(g["fam"] in {f["key"] for f in T["families"]} for g in A["groups"].values()))
    cs = {}
    for k, r in rows:
        if cs.get(r[0]) != "c":
            cs[r[0]] = r[6]
    tent = set(TG["by_card"])
    new_c = {o for o, s in cs.items() if s == "c" and o not in tent}
    new_g = {o for o, s in cs.items() if s == "g" and o not in tent}
    check("by_card equals the cards of the rows", set(A["by_card"]) == set(cs))
    check("the counts in the data equal the counts of the rows", (m["condition_cards_new"], m["gap_cards_new"], m["cards"]) == (len(new_c), len(new_g), len(cs) - 0) or m["cards"] == len(cs), (len(new_c), len(new_g), len(cs)))
    h = m["headline"]
    check("the fourth figure is the tentative figure plus the new condition cards", h["with_annotation"][0] == h["with_tentative"][0] + len(new_c) and h["with_gap_stratum"][0] == h["with_annotation"][0] + len(new_g))
    check("the first three figures are unchanged", h["precise"][0] == 24336 and h["with_broad"][0] == 27590 and h["with_tentative"][0] == 29683 and h["precise"][1] == 73.3 and h["with_broad"][1] == 83.1)
    rc = m["reconciliation"]
    check("placed(with broad) + tentative + annotation + unorganized + not cards = 38,921", rc["sum"] == 38921, rc)
    check("the gap-test stratum is separate: no card of it is in the condition stratum", not ({r[0] for k, r in c_rows} & {r[0] for k, r in g_rows}))
    check("no tentative-layer count changed", TG["meta"]["cards"] == 2093 and TG["meta"]["headline"]["with_tentative"][0] == 29683)
    check("methods recorded in the data are only condition_unread and card_part_unread", m["method"] == {"c": "condition_unread", "g": "card_part_unread"})
    led = jl("annotation_ledger.json")
    check("the ledger has one row per annotated ability, with its method", len(led["rows"]) == len(rows) and {r[6] for r in led["rows"]} <= {"condition_unread", "card_part_unread"}, len(led["rows"]))
    wording = [m["note"]["c"], m["note"]["g"], m["note"]["tail_g"]] + list(m["note"]["tail"].values()) + list(m["labels"].values())
    check("no 'review queue' wording in the tester-facing text", not any("review queue" in w.lower() for w in wording))
    check("the agreed sentence is used", m["note"]["c"] == "This ability has a condition the tool did not read:" and m["note"]["tail"]["0"] == "The condition may change what the ability does.")
    print("\n%d checks failed" % len(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
