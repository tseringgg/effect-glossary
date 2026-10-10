#!/usr/bin/env python3
"""After Step B: 40 placed gap-card abilities. Seed 20261015, declared before any computation. Run once; no redraw.

    python src/sample_gap_placed.py   # -> build/gap_placed_sample_20261015.json

Population: ledger rows of method gap_ability whose state is "placed" (an unflagged leaf), one ability per card (the card's first in rules order).
Two strata, each a seeded shuffle of the sorted card ids; a card is in the first stratum it qualifies for:
  popular   20 cards in the top 3,000 by edhrec_rank
  gap kind  20 cards (not in the first pool) whose unread part includes an unknown trigger mode or an unrecognized condition
An ability with no text is skipped and the next in seed order is taken (skips are listed). Bar: more than 2 wrong of 40 means Step B is reverted.
"""
import collections
import gzip
import io
import json
import os
import random

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
DATA = os.path.join(HERE, "data")
SEED = 20261015


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def main():
    led, cards, tax = jl("ability_taxonomy_ledger.json"), jl("ability_taxonomy_cards.json")["cards"], jl("ability_taxonomy.json")
    L = tax["leaves"]
    rank = {}
    with gzip.open(os.path.join(DATA, "scryfall-oracle-cards.jsonl.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            if o.get("edhrec_rank") is not None:
                rank[o["oracle_id"]] = o["edhrec_rank"]
    first = {}
    for r in led["rows"]:
        if r[9] == "gap_ability" and r[6] == "placed":
            k = (r[0])
            cur = first.get(k)
            key = (r[1], r[2], r[3], -1 if r[4] is None else r[4])
            if cur is None or key < cur[0]:
                first[k] = (key, r)
    pop = {oid: v[1] for oid, v in first.items()}
    rnd = random.Random(SEED)
    popular = sorted(o for o in pop if rank.get(o, 10 ** 9) <= 3000)
    kinds = lambda o: {x[0] for x in (cards[o].get("g") or [])}   # noqa: E731
    gapkind = sorted(o for o in pop if o not in set(popular) and kinds(o) & {"trigger", "cond"})
    out = {"seed": SEED, "population_abilities": len(pop), "popular_pool": len(popular), "gap_kind_pool": len(gapkind), "skipped": [], "items": []}
    items = []
    for name, pool, want in (("popular", popular, 20), ("gap kind", gapkind, 20)):
        order = pool[:]
        rnd.shuffle(order)
        got = 0
        for oid in order:
            r = pop[oid]
            if not (r[5] or "").strip():
                out["skipped"].append({"card": cards[oid]["n"], "stratum": name, "why": "ability has no text"})
                continue
            items.append((name, oid, r))
            got += 1
            if got == want:
                break
    for k, (name, oid, r) in enumerate(items, 1):
        lf = L[r[8]]
        out["items"].append({"n": k, "oid": oid, "stratum": name, "blind": {"card": cards[oid]["n"], "ability_text": " ".join(r[5].split())[:400]},
                             "reveal": {"leaf_id": r[8], "leaf": lf["name"], "signature": lf["sig"], "leaf_abilities": lf["abilities"], "flags": lf["flags"],
                                        "gap_fragments": cards[oid].get("g") or [], "gap_types": sorted(kinds(oid)) or ["item-level only"],
                                        "card_text": cards[oid]["t"].replace("\n", " / ")[:500], "edhrec_rank": rank.get(oid)}})
    with io.open(os.path.join(BUILD, "gap_placed_sample_20261015.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print({k: v for k, v in out.items() if k != "items"}, len(out["items"]))


if __name__ == "__main__":
    main()
