#!/usr/bin/env python3
"""Placement check of the community-tag layer (read-only). Seed 20261039, declared before any computation.

    python src/check_tag_layer.py draw          # -> build/tag_check_blind.json (card text only), build/tag_check_key.json (the group and tag, hidden until the reads exist)
    python src/check_tag_layer.py show 1 40
    python src/check_tag_layer.py reveal        # after build/tag_check_reads.json exists -> build/tag_check_result.json

40 placements, one per card: a placement is a (card, group) pair of the layer; for each card one of its groups is picked by the seed. The top 3,000 (EDHREC rank of the oracle-card file) are oversampled on
purpose: 20 cards from the top-3,000 pool and 20 from the others, so the result is NOT a rate over the layer. For each: I read the card text first, write what the card does (a fair description), and only then
is the group shown; verdict right (the group name fairly describes the card), loose, wrong. Bar (unchanged from the brief): more than 5 wrong of 40 turns the layer off. 40 cannot show a rate.
"""
import collections
import gzip
import io
import json
import os
import random
import sys
import textwrap

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
SEED = 20261039


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def draw():
    T = jl("tag_placements.json")
    cards = jl("ability_taxonomy_cards.json")["cards"]
    rank = {}
    for l in gzip.open(os.path.join(HERE, "data", "scryfall-oracle-cards.jsonl.gz"), "rt", encoding="utf-8"):
        o = json.loads(l)
        rank[o["oracle_id"]] = o.get("edhrec_rank")
    top = sorted(o for o in T["by_card"] if rank.get(o) is not None and rank[o] <= 3000)
    rest = sorted(o for o in T["by_card"] if not (rank.get(o) is not None and rank[o] <= 3000))
    rnd = random.Random(SEED)
    blind, key = [], []
    for st, pool in (("top 3,000", top), ("rest", rest)):
        lst = list(pool)
        rnd.shuffle(lst)
        for o in lst[:20]:
            g = rnd.choice(T["by_card"][o])
            i = len(blind) + 1
            blind.append({"n": i, "stratum": st, "card": cards[o]["n"], "oracle_text": cards[o]["t"]})
            gr = T["groups"][g]
            key.append({"n": i, "oid": o, "stratum": st, "rank": rank.get(o), "group": gr["name"], "name_source": gr["name_source"], "tag": gr["slug"], "description": gr["description"], "group_cards": gr["cards"], "groups_of_the_card": len(T["by_card"][o])})
    with io.open(os.path.join(BUILD, "tag_check_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "items": blind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "tag_check_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "pools": {"top 3,000": len(top), "rest": len(rest)}, "draws": key}, ensure_ascii=False, indent=1))
    print("pools: top 3,000 =", len(top), "cards, rest =", len(rest), "cards; drawn", len(blind))


def show(lo, hi):
    for b in jl("tag_check_blind.json")["items"]:
        if lo <= b["n"] <= hi:
            print("\n=== %d [%s] %s" % (b["n"], b["stratum"], b["card"].encode("ascii", "replace").decode()))
            print("   ", "\n    ".join(textwrap.wrap(b["oracle_text"].replace("\n", " / ").encode("ascii", "replace").decode()[:520], 150)))


def reveal():
    key = jl("tag_check_key.json")
    reads = jl("tag_check_reads.json")["reads"]
    rows = []
    for k in key["draws"]:
        r = reads[str(k["n"])]
        rows.append(dict(k, my_fair_description=r["fair"], verdict=r.get("verdict", ""), why=r.get("why", "")))
    print("\n".join("%2d [%-9s] r%-6s read: %-52s | group: %-48s | %s" % (x["n"], x["stratum"][:9], x["rank"], x["my_fair_description"][:52], x["group"][:48], x["verdict"]) for x in rows))
    if not all(x["verdict"] for x in rows):
        return
    tot = collections.Counter(x["verdict"] for x in rows)
    by = {st: dict(collections.Counter(x["verdict"] for x in rows if x["stratum"] == st)) for st in ("top 3,000", "rest")}
    res = {"seed": SEED, "pools": key["pools"], "total": dict(tot), "by_stratum": by, "bar": "more than 5 wrong of 40 turns the layer off", "tripped": tot["wrong"] > 5, "rows": rows}
    with io.open(os.path.join(BUILD, "tag_check_result.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    c = sys.argv[1]
    {"draw": draw, "reveal": reveal}.get(c, lambda: show(int(sys.argv[2]), int(sys.argv[3])))()
