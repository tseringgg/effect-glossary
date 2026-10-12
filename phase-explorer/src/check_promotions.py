#!/usr/bin/env python3
"""Fresh check of the 2026-10 tentative promotions (the renamed groups and the sub-heading groups), drawn from the built ledger. Nothing here changes the build.

    python src/check_promotions.py draw      # -> build/promotion_check_blind.json (card and ability text only), build/promotion_check_key.json
    python src/check_promotions.py show 1 40
    python src/check_promotions.py reveal    # after build/promotion_check_reads.json holds my read of each ability -> prints the groups; verdicts are then added and `result` writes the result

Seed 20261026, declared before any computation. 40 placements (one ability in one tentative group): 20 from the renamed groups and 20 from the sub-heading groups (pool = every ledger row of those groups).
Order of work: the ability text is read and my read of what it does is written to build/promotion_check_reads.json BEFORE the group of any placement is looked at; then the group's name is shown and
the placement is judged right (the ability belongs in that group), loose (it fits, but the group is wide) or wrong.
Bars: more than 5 wrong overall turns the new promotions off (PROMOTE_RENAMED_GROUPS and PROMOTE_SUBHEADINGS in src/build_tentative.py); more than 3 of 20 wrong in one stratum holds that stratum and rebuilds.
"""
import collections
import io
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
SEED = 20261026


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def draw():
    led = jl("tentative_ledger.json")["rows"]
    T = jl("tentative_placements.json")
    origin = {g: v["origin"] for g, v in T["groups"].items()}
    strata = {"renamed group": [r for r in led if origin[r[5]] == "renamed group"], "sub-heading": [r for r in led if origin[r[5]].startswith("sub-heading")]}
    rnd = random.Random(SEED)
    pick = []
    for st in ("renamed group", "sub-heading"):
        pool = sorted(strata[st], key=lambda r: (r[0], r[1], r[2], r[3], r[5]))
        pick += [(st, r) for r in rnd.sample(pool, 20)]
    cards = jl("ability_taxonomy_cards.json")["cards"]
    blind, key = [], []
    for i, (st, r) in enumerate(pick, 1):
        c = cards.get(r[0], {})
        blind.append({"n": i, "card": c.get("n", r[0]), "ability": r[4] or "(no separate rules line)"})
        key.append({"n": i, "stratum": st, "oid": r[0], "gid": r[5], "group": T["groups"][r[5]]["name"], "rests_on": r[7], "card": c.get("n", r[0])})
    with io.open(os.path.join(BUILD, "promotion_check_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "placements": blind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "promotion_check_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "placements": key, "pools": {k: len(v) for k, v in strata.items()}}, ensure_ascii=False, indent=1))
    print({k: len(v) for k, v in strata.items()}, len(pick))


def show(lo, hi):
    for b in jl("promotion_check_blind.json")["placements"]:
        if lo <= b["n"] <= hi:
            print("%2d %s | %s" % (b["n"], b["card"].encode("ascii", "replace").decode(), b["ability"][:230].encode("ascii", "replace").decode()))


def reveal():
    key = jl("promotion_check_key.json")["placements"]
    reads = jl("promotion_check_reads.json")["reads"]
    for k in key:
        r = reads[str(k["n"])]
        print("%2d [%s] read: %s || group: %s" % (k["n"], k["stratum"][:4], r["read"], k["group"].split(" › ", 1)[1].encode("ascii", "replace").decode()))


def result():
    key = jl("promotion_check_key.json")["placements"]
    d = jl("promotion_check_reads.json")
    out = collections.defaultdict(collections.Counter)
    rows = []
    for k in key:
        r = d["reads"][str(k["n"])]
        out[k["stratum"]][r["verdict"]] += 1
        rows.append(dict(k, read=r["read"], verdict=r["verdict"], why=r.get("why", "")))
    tot = collections.Counter()
    for v in out.values():
        tot.update(v)
    res = {"seed": SEED, "by_stratum": {k: dict(v) for k, v in out.items()}, "total": dict(tot), "wrong_total": tot["wrong"], "bar_overall_more_than_5_wrong": tot["wrong"] > 5,
           "bar_stratum_more_than_3_wrong": {k: v["wrong"] > 3 for k, v in out.items()}, "placements": rows}
    with io.open(os.path.join(BUILD, "promotion_check_result.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "placements"}, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"draw": draw, "reveal": reveal, "result": result}.get(cmd, lambda: show(int(sys.argv[2]), int(sys.argv[3])))()
