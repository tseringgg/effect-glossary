#!/usr/bin/env python3
"""Seeded hand-check samples for the per-ability taxonomy (Part 4). Rules fixed before any draw was read.

    python src/sample_ability_taxonomy.py   # -> build/ability_taxonomy_handcheck.json

Seed 20261008 (new; probes used 20261006 and 20261007). Every draw uses random.Random("<seed>-<name>"), so the draws
are independent and reproducible. Nothing is redrawn after reading.

  leaves     30 leaves: 10 finest (level 5), 10 middle (levels 3-4), 10 coarsest (level 2). Within a band the leaves
             (sorted by id) are shuffled; a leaf with fewer than 8 placed member abilities is skipped (and listed) and
             the next is taken. Flagged (broad) leaves are eligible and marked. 8 member abilities per leaf, shuffled.
  placed     40 abilities with state "placed" (clean cards, unflagged leaf of 5 or more), any kind.
  modes      40 placed abilities that are inline modal modes (rule 3), drawn separately.
  gap        40 gap-card abilities that pass the same-line / continuation / no-text tests and would be placed
             (reason gap_card_placed).
  names      20 leaves of 10 or more (the display threshold), auto-named.
  unusual    20 cards placed in the archived card-level view and "too unusual" now.
Each sample stores the ability text first and the leaf name / signature separately, so a judge can read the text
before the leaf.
"""
import collections
import io
import json
import os
import random

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
SEED = 20261008


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def R(name):
    return random.Random("%d-%s" % (SEED, name))


def main():
    T = jl("ability_taxonomy.json")
    G = jl("ability_taxonomy_ledger.json")
    C = jl("ability_taxonomy_cards.json")["cards"]
    old = {e[0]: e for e in jl("lookup.json")["entries"]}
    lp = jl("leaf_phrases.json")
    rows = G["rows"]
    leaves = T["leaves"]

    def text(r):
        t = (r[5] or "").strip()
        return t if t else "(no ability text) card: " + C.get(r[0], {}).get("t", "")[:200].replace("\n", " / ")

    def name(r):
        return C.get(r[0], {}).get("n", r[0])
    by_leaf = collections.defaultdict(list)
    for r in rows:
        if r[6] in ("placed", "placed_broad") and r[8]:
            by_leaf[r[8]].append(r)
    out = {"v": 1, "seed": SEED, "rules": __doc__}
    # leaves
    bands = {"finest": lambda l: l["level"] == 5, "middle": lambda l: l["level"] in (3, 4), "coarsest": lambda l: l["level"] == 2}
    lv, skipped = [], {}
    for band, pred in bands.items():
        ids = sorted(k for k, l in leaves.items() if pred(l))
        R("leaves-" + band).shuffle(ids)
        taken, sk = [], []
        for lid in ids:
            if len(taken) == 10:
                break
            mem = sorted(by_leaf.get(lid, []), key=lambda r: (r[0], r[2], r[3], -1 if r[4] is None else r[4]))
            if len(mem) < 8:
                sk.append([lid, len(mem)])
                continue
            R("members-" + lid).shuffle(mem)
            taken.append({"band": band, "leaf": lid, "members": [[name(r), text(r)[:260]] for r in mem[:8]],
                          "reveal": {"name": leaves[lid]["name"], "sig": leaves[lid]["sig"], "abilities": leaves[lid]["abilities"],
                                     "flags": leaves[lid]["flags"], "level": leaves[lid]["level"]}})
        skipped[band] = sk
        lv.extend(taken)
    out["leaves"] = lv
    out["leaves_skipped_under_8"] = skipped

    def draw(pool, n, nm):
        pool = sorted(pool, key=lambda r: (r[0], r[1], r[2], r[3], -1 if r[4] is None else r[4]))
        pick = R(nm).sample(pool, min(n, len(pool)))
        res = []
        for r in pick:
            res.append({"card": name(r), "oid": r[0], "text": text(r)[:300],
                        "card_text": C.get(r[0], {}).get("t", "")[:400],
                        "reveal": {"leaf": r[8], "name": leaves.get(r[8], {}).get("name"), "sig": leaves.get(r[8], {}).get("sig"),
                                   "state": r[6], "reason": r[7]}})
        return res, len(pool)
    out["placed"], out["placed_pool"] = draw([r for r in rows if r[6] == "placed"], 40, "placed")
    out["modes"], out["modes_pool"] = draw([r for r in rows if r[6] == "placed" and r[4] is not None], 40, "modes")
    out["gap"], out["gap_pool"] = draw([r for r in rows if r[6] == "held_out" and r[7] == "gap_card_placed"], 40, "gap")
    # names
    vis = sorted(k for k, l in leaves.items() if l["abilities"] >= 10 and l["auto_named"])
    pick = R("names").sample(vis, 20)
    out["names"] = []
    for lid in pick:
        mem = sorted(by_leaf.get(lid, []), key=lambda r: (r[0], r[2], r[3]))
        R("name-members-" + lid).shuffle(mem)
        out["names"].append({"leaf": lid, "members": [[name(r), text(r)[:200]] for r in mem[:8]],
                             "reveal": {"name": leaves[lid]["name"], "sig": leaves[lid]["sig"], "flags": leaves[lid]["flags"]}})
    # too unusual, placed before
    cards = G["cards"]
    pool = sorted(o for o, c in cards.items() if c["view"] == "unorganized" and c["reason"] == "too_unusual"
                  and old.get(o, [None] * 4)[3] in ("c", "p", "a"))
    pick = R("unusual").sample(pool, 20)
    out["unusual_pool"] = len(pool)
    out["unusual"] = []
    for o in pick:
        e = old[o]
        leaf = e[4] if e[3] == "c" else e[4][0]
        ph = (lp.get("leaves", {}).get(str(leaf)) or {}).get("phrases") or []
        mates = [old[x][1] for x in sorted(old) if old[x][3] == "c" and old[x][4] == leaf][:6]
        out["unusual"].append({"card": cards[o]["name"], "oid": o, "card_text": C[o]["t"][:500],
                               "old": {"how": {"c": "clustered", "p": "nearby", "a": "one ability"}[e[3]], "leaf": leaf,
                                       "phrase": ph[0]["phrase"] if ph else None, "leaf_mates": mates},
                               "now_reasons": sorted({r[7] for r in rows if r[0] == o})})
    with io.open(os.path.join(BUILD, "ability_taxonomy_handcheck.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print({k: (len(v) if isinstance(v, list) else v) for k, v in out.items() if k != "rules"})


if __name__ == "__main__":
    main()
