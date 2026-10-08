#!/usr/bin/env python3
"""Round-3 hand-check samples for the per-ability taxonomy. Seed 20261010, declared before any computation. Run once.

    python src/sample_round3_ability_taxonomy.py   # -> build/ability_taxonomy_handcheck_round3.json

  leaves     30: 10 finest (level 5), 10 middle (3-4), 10 coarsest (2); shuffled by id; a leaf with fewer than 8 placed
             members is skipped (listed) and the next taken. Flagged leaves are eligible.
  placed     40 abilities in state "placed" (an unflagged leaf of 5 or more).
  names      20 auto-named leaves of 10 or more abilities.
  split      10 leaves whose signature carries a sign or a recipient, or that hold damage to a player: the leaves where
             members could split by sign or recipient. 8 members each. Reported separately.
Members are sorted then shuffled with random.Random("<seed>-<name>[-<leaf>]"); the judge reads member text first, "reveal" after.
"""
import io
import json
import os
import random

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
SEED = 20261010


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def R(name):
    return random.Random("%d-%s" % (SEED, name))


def main():
    T, G, C = jl("ability_taxonomy.json"), jl("ability_taxonomy_ledger.json"), jl("ability_taxonomy_cards.json")["cards"]
    leaves = T["leaves"]
    rows = G["rows"]
    by_leaf = {}
    for r in rows:
        if r[6] in ("placed", "placed_broad") and r[8]:
            by_leaf.setdefault(r[8], []).append(r)
    name = lambda r: C.get(r[0], {}).get("n", r[0])   # noqa: E731

    def text(r):
        t = (r[5] or "").strip()
        return t if t else "(no ability text) card: " + C.get(r[0], {}).get("t", "")[:200].replace("\n", " / ")

    def members(lid, k=8, tag="members"):
        mem = sorted(by_leaf.get(lid, []), key=lambda r: (r[0], r[2], r[3], -1 if r[4] is None else r[4]))
        R("%s-%s" % (tag, lid)).shuffle(mem)
        return [[name(r), text(r)[:240]] for r in mem[:k]]
    reveal = lambda lid: {"name": leaves[lid]["name"], "sig": leaves[lid]["sig"], "flags": leaves[lid]["flags"],    # noqa: E731
                          "level": leaves[lid]["level"], "abilities": leaves[lid]["abilities"]}
    out = {"v": 1, "seed": SEED}
    bands = {"finest": lambda l: l["level"] == 5, "middle": lambda l: l["level"] in (3, 4), "coarsest": lambda l: l["level"] == 2}
    lv, skipped = [], {}
    for band, pred in bands.items():
        ids = sorted(k for k, l in leaves.items() if pred(l))
        R("leaves-" + band).shuffle(ids)
        taken, sk = [], []
        for lid in ids:
            if len(taken) == 10:
                break
            if len(by_leaf.get(lid, [])) < 8:
                sk.append([lid, len(by_leaf.get(lid, []))])
                continue
            taken.append({"band": band, "leaf": lid, "members": members(lid), "reveal": reveal(lid)})
        skipped[band] = sk
        lv.extend(taken)
    out["leaves"], out["leaves_skipped_under_8"] = lv, skipped
    pool = sorted((r for r in rows if r[6] == "placed"), key=lambda r: (r[0], r[1], r[2], r[3], -1 if r[4] is None else r[4]))
    out["placed_pool"] = len(pool)
    out["placed"] = [{"card": name(r), "oid": r[0], "text": text(r)[:300], "card_text": C.get(r[0], {}).get("t", "")[:400],
                      "reveal": {"leaf": r[8], "name": leaves[r[8]]["name"], "sig": leaves[r[8]]["sig"]}}
                     for r in R("placed").sample(pool, 40)]
    npool = sorted(k for k, l in leaves.items() if l["abilities"] >= 10 and l["auto_named"])
    out["names_pool"] = len(npool)
    out["names"] = [{"leaf": lid, "members": members(lid, 8, "name-members"), "reveal": reveal(lid)} for lid in R("names").sample(npool, 20)]
    spool = sorted(k for k, l in leaves.items() if len(by_leaf.get(k, [])) >= 8 and (
        "sign=" in l["sig"] or "recip=" in l["sig"] or "ftype=DamageEachPlayer" in l["sig"] or "ftype=Damage " in l["sig"] + " " or
        ("ftype=DealDamage" in l["sig"] and any(("obj=" + o) in l["sig"] for o in ("player", "triggering player", "object", "you")))))
    out["split_pool"] = len(spool)
    out["split"] = [{"leaf": lid, "members": members(lid, 8, "split-members"), "reveal": reveal(lid)} for lid in R("split").sample(spool, 10)]
    with io.open(os.path.join(BUILD, "ability_taxonomy_handcheck_round3.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print({k: (len(v) if isinstance(v, list) else v) for k, v in out.items()}, {b: len(s) for b, s in skipped.items()})


if __name__ == "__main__":
    main()
