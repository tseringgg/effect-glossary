#!/usr/bin/env python3
"""Fresh auto-name check for the per-ability taxonomy (round 2). Seed 20261009, declared before computing.

    python src/sample_names_ability_taxonomy.py   # -> build/ability_taxonomy_names_check.json

Draws 20 leaves of 10 or more abilities whose name is auto-generated (flagged leaves included) with
random.Random("20261009-names"), 8 member abilities each (random.Random("20261009-members-<leaf>")).
The judge reads the members first and writes what the group should be called; only then is "reveal" read.
Run once; not redrawn. (Round 1's samples are in build/ability_taxonomy_handcheck_round1.json and were drawn from
the build before the extra flags and name fixes; src/sample_ability_taxonomy.py would now draw from the current build.)
"""
import io
import json
import os
import random

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
SEED = 20261009


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def main():
    T, G, C = jl("ability_taxonomy.json"), jl("ability_taxonomy_ledger.json"), jl("ability_taxonomy_cards.json")["cards"]
    leaves = T["leaves"]
    by_leaf = {}
    for r in G["rows"]:
        if r[6] in ("placed", "placed_broad") and r[8]:
            by_leaf.setdefault(r[8], []).append(r)
    pool = sorted(k for k, l in leaves.items() if l["abilities"] >= 10 and l["auto_named"])
    pick = random.Random("%d-names" % SEED).sample(pool, 20)
    out = {"v": 1, "seed": SEED, "pool": len(pool), "names": []}
    for lid in pick:
        mem = sorted(by_leaf[lid], key=lambda r: (r[0], r[2], r[3], -1 if r[4] is None else r[4]))
        random.Random("%d-members-%s" % (SEED, lid)).shuffle(mem)
        rows = []
        for r in mem[:8]:
            t = (r[5] or "").strip() or "(no ability text) card: " + C[r[0]]["t"][:200].replace("\n", " / ")
            rows.append([C[r[0]]["n"], t[:220]])
        out["names"].append({"leaf": lid, "members": rows,
                             "reveal": {"name": leaves[lid]["name"], "sig": leaves[lid]["sig"], "flags": leaves[lid]["flags"]}})
    with io.open(os.path.join(BUILD, "ability_taxonomy_names_check.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print("pool", len(pool), "drawn", len(out["names"]))


if __name__ == "__main__":
    main()
