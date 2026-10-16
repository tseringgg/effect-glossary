#!/usr/bin/env python3
"""The sibling-of-leaf rule: TENTATIVE placements for abilities the grouping rule could not place only because they are the PLAIN variant of a group. NEW FILE ONLY: build/sibling_placements.json.

    python src/build_sibling.py        # about a minute (re-runs the taxonomy in memory, as build_tentative.py does)

Why it exists. A leaf is formed by the abilities that share a signature after the rarest-field-first backoff has dropped their extra details. A plain ability (no extra details) has nothing to drop, so it is counted only
with its exact twins, and if fewer than 5 share its exact tuple it is "held" (reason rare_object / rare_verb_parameter / below_minimum_size) even though its signature equals the leaf its detailed relatives formed
(Putrefy: "Destroy target artifact or creature. It can't be regenerated." beside "Destroy an artifact or creature", 10 cards).
Rule. An ability is a sibling of a leaf when (a) its card is not placed (the not-yet-organized pile, tentative, annotation and tag cards), (b) the ability is held for one of those backoff reasons and is not flagged
or gap-held, and (c) the set of its non-empty fields equals the leaf's signature exactly, for exactly one unflagged leaf. The placement is TENTATIVE: method `sibling_tentative`, badge "sibling", its own page switch,
counted in no figure (the six figures are generated elsewhere and do not move), and reversible (a hand removal in the edit panel, or the switch).
Read before it was built (seed 20261080; the 27 abilities, text first): 24 correct, 2 loose, 1 wrong (Summoner's Egg's enters-the-battlefield exile under an alternative-cost group); the bar was no more than 2 wrong.
SIBLING_RULE = False writes nothing and removes the file.
"""
import collections
import contextlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SIBLING_RULE = True
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(BUILD, "sibling_placements.json")
METHOD = "sibling_tentative"
BADGE = "sibling"
LABEL = ("Tentative placement (sibling): this ability has exactly this group's signature, but the group was formed from more detailed variants, so the grouping rule could not place it. Not checked; "
         "not counted in any figure.")
RARE = ("rare_object", "rare_verb_parameter", "rare_effect_type", "below_minimum_size")
CANON = ["sign", "recip", "frm", "to", "ctr", "who", "mods", "obj", "ctrl", "quant", "props", "kw", "dur", "cond", "wrap", "chain", "tok"]


def jl(n):
    with io.open(os.path.join(BUILD, n), encoding="utf-8") as fh:
        return json.load(fh)


def toks(f):
    return frozenset("%s=%s" % (k, f[k]) for k in CANON if f.get(k) not in ("", "-", None))


def main():
    if not SIBLING_RULE:
        for q in (OUT, os.path.join(BUILD, "sibling_ledger.json")):
            if os.path.exists(q):
                os.remove(q)
        print("SIBLING_RULE is off: nothing written")
        return
    argv, sys.argv = sys.argv, sys.argv[:1]               # build_ability_taxonomy.main() parses sys.argv
    import build_ability_taxonomy as B
    B.dump = lambda *a, **k: None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            S = B.main()
    finally:
        sys.argv = argv
    A, tax = S["A"], S["tax"]
    look = {e[0]: e for e in jl("ability_taxonomy_lookup.json")["entries"]}
    tent, ann, tag = jl("tentative_placements.json"), jl("annotation_placements.json"), jl("tag_placements.json")
    cond = {}
    for g in ann["groups"].values():
        for r in g["m"]:
            if cond.get(r[0]) != "c":
                cond[r[0]] = r[6]
    state = {}
    for o, e in look.items():
        if e[3] == "u":
            state[o] = "tentative" if o in tent["by_card"] else "annotation" if cond.get(o) == "c" else "tag" if o in tag["by_card"] else "unorganized"
    by_sig = collections.defaultdict(list)
    for lid, l in sorted(tax["leaves"].items()):
        d = dict(p.split("=", 1) for p in l["sig"].split(" · "))
        by_sig[(d["fam"], d["ftype"], frozenset("%s=%s" % (k, v) for k, v in d.items() if k not in ("fam", "ftype") and v not in ("", "-")))].append(lid)
    groups, by_card, ambiguous, rows = {}, collections.defaultdict(list), 0, []
    for a in sorted(A, key=lambda a: (a["oid"], a["b"], a["i"])):
        o = a["oid"]
        if o not in state or a["state"] != "unplaced" or a["reason"] not in RARE or a["pre"] or not a["f"].get("usable"):
            continue
        f = a["f"]
        lids = [l for l in by_sig.get((f["fam"], f["ftype"], toks(f)), ()) if not tax["leaves"][l]["flags"]]
        if not lids:
            continue
        if len(lids) > 1:
            ambiguous += 1
            continue
        lid = lids[0]
        l = tax["leaves"][lid]
        text = " ".join((a["text"] or "").split())[:240]
        g = groups.setdefault(lid, {"name": l["name"], "leaf_cards": l["cards"], "m": []})
        g["m"].append([o, text, a["reason"]])
        if lid not in by_card[o]:
            by_card[o].append(lid)
        rows.append([o, a["face"], a["b"], a["i"], text, lid, METHOD, a["reason"]])
    for g in groups.values():
        g["m"].sort(key=lambda r: (r[0], r[1]))
    cs = collections.Counter(state[o] for o in by_card)
    doc = {"meta": {"enabled": True, "method": METHOD, "badge": BADGE, "label": LABEL, "abilities": len(rows), "cards": len(by_card), "groups": len(groups), "ambiguous_skipped": ambiguous,
                    "cards_by_state": dict(sorted(cs.items())),
                    "rule": "ability held for a backoff reason (rare_* or below_minimum_size), card not placed, ability field set equal to exactly one unflagged leaf's signature",
                    "read": {"seed": 20261080, "abilities": 27, "correct": 24, "loose": 2, "wrong": 1, "bar": "no more than 2 wrong"}},
           "groups": {k: groups[k] for k in sorted(groups)}, "by_card": {o: sorted(v) for o, v in sorted(by_card.items())}}
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    led = os.path.join(BUILD, "sibling_ledger.json")
    with io.open(led, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"method": METHOD, "columns": ["oracle_id", "face", "bucket", "index", "ability text", "leaf", "method", "held for"], "rows": sorted(rows)}, ensure_ascii=False, separators=(",", ":")))
    print(json.dumps(doc["meta"], ensure_ascii=False))


if __name__ == "__main__":
    main()
