#!/usr/bin/env python3
"""Placement check of the annotation layer (read-only). Seed 20261029, declared before any computation.

    python src/check_annotation.py draw          # -> build/annotation_check_blind.json (card, ability, unread text; no group), build/annotation_check_key.json (the group, hidden until the reads exist)
    python src/check_annotation.py show 1 40     # the condition stratum (40: 20 sequential-chain, 20 other sub-shapes), then 41 60 for the gap-test stratum (20 same-line)
    python src/check_annotation.py reveal        # after build/annotation_check_reads.json exists; writes build/annotation_check_result.json

Condition stratum: 40 placements, one per card, 20 from the sequential-chain sub-shape and 20 from the other sub-shapes (largest pool first only for the order of drawing: seed order), no redraw.
Gap-test stratum: 20 placements, one per card, all from the same-line failure (the stratum is oversampled on purpose: 57 of its 180 cards are same-line, the Part 2 sample had 12 of 40).
For each: I read the card text, the ability and the unread text, write the group I would file the ability in (what it does, ignoring the unread part) and whether a tester who saw only the
ability and its group (no unread text) would be misled, BEFORE the group is shown. Verdict: right / loose / wrong, compared with the group.
Bars (unchanged): more than 5 wrong of 40, or more than 3 of 20 in one condition stratum, turns the condition layer off or holds that stratum; more than 3 of 20 wrong in the gap-test stratum holds it.
"""
import collections
import io
import json
import os
import random
import sys
import textwrap

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
SEED = 20261029


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def draw():
    led = jl("annotation_ledger.json")["rows"]
    cards = jl("ability_taxonomy_cards.json")["cards"]
    pools = {"sequential-chain": [], "other sub-shapes": [], "gap same-line": []}
    for r in led:
        oid, card, b, i, ability, group, method, why, unread = r
        if method == "condition_unread":
            shape = why.split(": ", 1)[1]
            pools["sequential-chain" if shape == "sequential-chain" else "other sub-shapes"].append(r)
        elif method == "card_part_unread" and "same_line" in why:
            pools["gap same-line"].append(r)
    blind, key = [], []
    n = 0
    sizes = {}
    for st, quota in (("sequential-chain", 20), ("other sub-shapes", 20), ("gap same-line", 20)):
        rnd = random.Random(SEED)
        lst = sorted(pools[st], key=lambda r: (r[0], r[2], r[3]))
        sizes[st] = {"abilities": len(lst), "cards": len({r[0] for r in lst})}
        rnd.shuffle(lst)
        used, got = set(), 0
        for r in lst:
            if got >= quota:
                break
            if r[0] in used:
                continue
            used.add(r[0])
            got += 1
            n += 1
            blind.append({"n": n, "stratum": st, "card": r[1], "oracle_text": cards[r[0]]["t"], "ability_text": r[4], "unread_text": r[8]})
            key.append({"n": n, "oid": r[0], "stratum": st, "group": r[5], "ability": r[4]})
    with io.open(os.path.join(BUILD, "annotation_check_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "items": blind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "annotation_check_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "pools": sizes, "draws": key}, ensure_ascii=False, indent=1))
    print("pools", sizes, "drawn", n)


def show(lo, hi):
    for b in jl("annotation_check_blind.json")["items"]:
        if lo <= b["n"] <= hi:
            print("\n=== %d [%s] %s" % (b["n"], b["stratum"], b["card"].encode("ascii", "replace").decode()))
            print("ORACLE:", "\n        ".join(textwrap.wrap(b["oracle_text"].replace("\n", " / ").encode("ascii", "replace").decode()[:520], 140)))
            print("ABILITY:", b["ability_text"].encode("ascii", "replace").decode()[:360])
            print("UNREAD:", b["unread_text"].encode("ascii", "replace").decode()[:320])


def reveal():
    key = jl("annotation_check_key.json")
    reads = jl("annotation_check_reads.json")["reads"]
    rows = []
    for k in key["draws"]:
        r = reads[str(k["n"])]
        rows.append(dict(k, expected=r["expected"], misread_without_unread_text=r["misread"], verdict=r.get("verdict", ""), why=r.get("why", "")))
    print("\n".join("%2d [%-16s] read: %-58s | group: %-58s | %s" % (x["n"], x["stratum"][:16], x["expected"][:58], x["group"].split(" › ")[-1][:58], x["verdict"]) for x in rows))
    if not all(x["verdict"] for x in rows):
        return
    by = collections.defaultdict(collections.Counter)
    mis = collections.defaultdict(collections.Counter)
    for x in rows:
        by[x["stratum"]][x["verdict"]] += 1
        mis[x["stratum"]][x["misread_without_unread_text"]] += 1
    cond = collections.Counter()
    for st in ("sequential-chain", "other sub-shapes"):
        cond.update(by[st])
    res = {"seed": SEED, "condition_stratum_40": dict(cond), "by_stratum": {k: dict(v) for k, v in by.items()}, "misread_without_unread_text": {k: dict(v) for k, v in mis.items()}, "rows": rows,
           "bars": {"condition_overall_wrong_over": 5, "per_stratum_wrong_over": 3, "gap_same_line_wrong_over": 3},
           "tripped": {"overall": cond["wrong"] > 5, "sequential-chain": by["sequential-chain"]["wrong"] > 3, "other sub-shapes": by["other sub-shapes"]["wrong"] > 3, "gap same-line": by["gap same-line"]["wrong"] > 3}}
    with io.open(os.path.join(BUILD, "annotation_check_result.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    c = sys.argv[1]
    {"draw": draw, "reveal": reveal}.get(c, lambda: show(int(sys.argv[2]), int(sys.argv[3])))()
