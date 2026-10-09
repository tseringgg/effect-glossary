#!/usr/bin/env python3
"""Part 2: a fresh sample on lifting the gap-card hold. Seed 20261013, declared before any computation. Run once; no redraw.

    python src/sample_gap_hold.py   # -> build/gap_hold_sample_20261013.json   (blind part first; the reveal is a separate key)

Population: abilities of gap cards that pass the same-line and continuation tests and match an UNFLAGGED specific leaf (state held_out,
reason gap_card_placed), on the corrected base. The corrected base takes out the not-for-constructed cards (build/card_flags.json), and,
because the hand check in Part 1a found 170 flagged cards that are legal in at least one format, only those flagged cards that are
legal in NO format. Both counts are reported (with and without that legality exception); the draw uses the exception.
Rule: one ability per card (the card's first held-out ability in rules order); cards in a seeded shuffle of the sorted card ids; the first 100
whose ability has text are taken. An ability with no text is skipped and the next one in seed order is used; skips are listed.
"""
import collections
import gzip
import io
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import investigate_not_for_constructed as INV  # noqa: E402

HERE = INV.HERE
BUILD = INV.BUILD
DATA = INV.DATA
SEED = 20261013


def main():
    flags = INV.jl("card_flags.json")["cards"]
    legal_any = set()
    rank = {}
    with gzip.open(os.path.join(DATA, "scryfall-oracle-cards.jsonl.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            if any(v != "not_legal" for v in o["legalities"].values()):
                legal_any.add(o["oracle_id"])
            if o.get("edhrec_rank") is not None:
                rank[o["oracle_id"]] = o["edhrec_rank"]
    S0 = INV.run_build()
    inset = set(S0["cards"])
    X_rule = {o for o in flags if o in inset}
    X = {o for o in X_rule if o not in legal_any}
    out = {"seed": SEED, "excluded_by_the_rule": len(X_rule), "excluded_with_the_legality_exception": len(X), "flagged_but_legal_somewhere": len(X_rule) - len(X)}

    def population(S):
        by = collections.defaultdict(list)
        for a in S["A"]:
            if a["kind"] == "gap" and a["state"] == "held_out" and a["reason"] == "gap_card_placed":
                by[a["oid"]].append(a)
        pick = {}
        for oid, aa in by.items():
            aa.sort(key=lambda a: (a["face"], a["b"], a["i"], -1 if a["mode"] is None else a["mode"]))
            pick[oid] = aa[0]
        return pick
    S_rule = INV.run_build(excluded=X_rule)
    pop_rule = population(S_rule)
    S = INV.run_build(excluded=X)
    pop = population(S)
    out["population_cards"] = {"current_build_(nothing_excluded)": len(population(S0)), "rule_as_built": len(pop_rule), "with_the_legality_exception": len(pop)}
    out["headline_on_the_corrected_base"] = {"in_scope": S["tax"]["totals"]["in_scope"], "headline": S["tax"]["totals"]["headline"], "with_broad": S["tax"]["totals"]["with_broad"],
                                              "pile": S["tax"]["totals"]["not_yet_organized"]}

    U = INV.jl("ability_taxonomy_unorganized.json")["groups"]
    frag = {}
    for g in U:
        for c in g["list"]:
            frag[c["c"]] = c.get("g") or []
    cards, L = S["cards"], S["tax"]["leaves"]
    rnd = random.Random(SEED)
    order = sorted(pop)
    rnd.shuffle(order)
    taken, skipped = [], []
    for oid in order:
        a = pop[oid]
        if not (a["text"] or "").strip():
            skipped.append({"card": cards[oid]["n"], "why": "ability has no text"})
            continue
        taken.append(oid)
        if len(taken) == 100:
            break
    items = []
    for k, oid in enumerate(taken, 1):
        a = pop[oid]
        lf = L[a["leaf"]]
        fr = frag.get(oid, [])
        items.append({"n": k, "oid": oid,
                      "blind": {"card": cards[oid]["n"], "ability_text": " ".join(a["text"].split())[:400]},
                      "reveal": {"leaf_id": a["leaf"], "leaf": lf["name"], "signature": lf["sig"], "leaf_abilities": lf["abilities"], "leaf_cards": lf["cards"],
                                 "gap_fragments": fr, "gap_types": sorted({x[0] for x in fr}) or ["item-level only"], "card_text": cards[oid]["t"].replace("\n", " / ")[:500],
                                 "edhrec_rank": rank.get(oid)}})
    out["skipped"] = skipped
    out["items"] = items
    with io.open(os.path.join(BUILD, "gap_hold_sample_20261013.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print({k: v for k, v in out.items() if k not in ("items",)})


if __name__ == "__main__":
    main()
