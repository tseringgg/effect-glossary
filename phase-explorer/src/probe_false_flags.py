#!/usr/bin/env python3
"""Probe (read-only): how many abilities held by the dropped-condition detector are FALSE flags. Changes nothing: it does not touch the detector, the holds, or any build output.

    python src/probe_false_flags.py draw      # -> build/false_flag_blind.json (card text and parsed structure only), build/false_flag_key.json (detector evidence, hidden until the reads exist)
    python src/probe_false_flags.py reveal    # after build/false_flag_reads.json exists -> build/false_flag_result.json and the estimate

Population: every ability on a card that is still in "Not yet organized" (not placed, not tentative) that the dropped-condition detector holds (condition_drops.json), once each.
Seed 20261023, declared before any computation. Draw: 100 abilities, one per card, stratified by detector sub-shape in proportion to the sub-shape's size (largest remainder), none hand-picked, no redraw.
Within a sub-shape the abilities are put in a fixed order (card id, bucket, index), shuffled once with the seed, and taken in that order; an ability whose card was already drawn, or that has no ability text,
is skipped and the next in seed order is taken (skips are counted and reported).
Judging: for each ability the card's full oracle text and the parsed structure of the flagged item are read and a verdict written (real drop / false flag / unclear, with the reason for a false flag) BEFORE the
detector's evidence (sub-shape, the "if" clauses and families it found missing) is looked at.
"""
import collections
import io
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_unorganized_breakdown_v3 as V3

HERE = V3.HERE
BUILD = V3.BUILD
SEED = 20261023
N = 100


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def compact(x):
    if isinstance(x, dict):
        d = {k: compact(v) for k, v in x.items() if v not in (None, "", [], {}) and k not in ("description",)}
        return {k: v for k, v in d.items() if v not in (None, "", [], {})}
    if isinstance(x, list):
        return [compact(v) for v in x]
    return x


def population():
    unorg = jl("ability_taxonomy_unorganized.json")["groups"]
    pile = {c["c"] for g in unorg for c in g["list"]}
    tent = set(jl("tentative_placements.json")["by_card"])
    rset = pile - tent
    ex = V3.held_items(rset, {})
    flagged = [x for x in ex if x["why"] == "flagged" and x["oid"] in rset]
    return rset, pile, tent, flagged


def draw():
    rset, pile, tent, flagged = population()
    cards = jl("ability_taxonomy_cards.json")["cards"]
    names = {}
    idx = {r["id"]: r for r in jl("index.json")["rows"]}
    by = collections.defaultdict(list)
    for x in flagged:
        by[x["cd"]["shape"] if x["cd"] else "(no detector record)"].append(x)
    total = len(flagged)
    shapes = sorted(by)
    raw = {s: N * len(by[s]) / total for s in shapes}
    quota = {s: int(math.floor(raw[s])) for s in shapes}
    left = N - sum(quota.values())
    for s in sorted(shapes, key=lambda s: (-(raw[s] - quota[s]), s))[:left]:
        quota[s] += 1
    rnd = random.Random(SEED)
    used, pick, skipped = set(), [], []
    for s in shapes:
        lst = sorted(by[s], key=lambda x: (x["oid"], x["b"], x["i"]))
        rnd.shuffle(lst)
        got = 0
        for x in lst:
            if got >= quota[s]:
                break
            if x["oid"] in used:
                continue
            if not (x["text"] or "").strip():
                skipped.append((s, x["oid"]))
                continue
            used.add(x["oid"])
            pick.append((s, x))
            got += 1
    blind, key = [], []
    for i, (s, x) in enumerate(pick, 1):
        o = x["oid"]
        c = cards.get(o, {})
        e = {}
        ch = idx.get(x["face"])
        items = []
        if ch:
            e = json.load(io.open(os.path.join(BUILD, "chunks", "%d.json" % ch["ch"]), encoding="utf-8")).get(x["face"], {})
            for b in ("abilities", "triggers", "static_abilities", "replacements"):
                for j, it in enumerate(e.get(b) or []):
                    ty = (it.get("effect") or {}).get("type") if b == "abilities" else ((it.get("execute") or {}).get("effect") or {}).get("type") if b in ("triggers", "replacements") else (it.get("mode") or it.get("type"))
                    items.append("%s[%d]%s %s: %s" % (b, j, " <- THIS" if (b == x["b"] and j == x["i"]) else "", ty, " ".join((it.get("description") or "").split())[:70]))
        blind.append({"n": i, "card": c.get("n", o), "oracle_text": c.get("t", ""), "ability_text": " ".join((x["text"] or "").split()), "parsed_item": json.dumps(compact(x["item"]), ensure_ascii=False, separators=(",", ":"))[:1100],
                      "card_items": items})
        d = x["cd"] or {}
        key.append({"n": i, "oid": o, "stratum": s, "sub": d.get("sub"), "tier": d.get("tier"), "clauses": d.get("clauses"), "missing": d.get("missing"), "families": d.get("families"), "evidence": d.get("evidence"),
                    "item_gap": d.get("item_gap"), "b": x["b"], "i": x["i"]})
    out_key = {"seed": SEED, "population": total, "cards_with_a_flagged_ability": len({x["oid"] for x in flagged}), "flagged_on_tentative_cards": None,
               "by_shape": {s: len(by[s]) for s in shapes}, "quota": quota, "skipped_for_no_text_or_repeated_card": len(skipped), "skipped_no_text": [s for s in skipped], "draws": key}
    with io.open(os.path.join(BUILD, "false_flag_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "items": blind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "false_flag_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out_key, ensure_ascii=False, indent=1))
    print("population", total, "cards", out_key["cards_with_a_flagged_ability"])
    print("by shape", out_key["by_shape"])
    print("quota", quota, "drawn", len(pick), "skipped", len(skipped), skipped[:5])


def show(lo, hi):
    for b in jl("false_flag_blind.json")["items"]:
        if lo <= b["n"] <= hi:
            print("\n=== %d  %s" % (b["n"], b["card"].encode("ascii", "replace").decode()))
            print("ORACLE:", b["oracle_text"].replace("\n", " / ").encode("ascii", "replace").decode()[:700])
            print("ABILITY:", b["ability_text"].encode("ascii", "replace").decode()[:400])
            print("PARSED:", b["parsed_item"].encode("ascii", "replace").decode()[:900])
            print("ITEMS:", " | ".join(b["card_items"]).encode("ascii", "replace").decode()[:600])


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def reveal():
    reads = jl("false_flag_reads.json")["reads"]
    key = jl("false_flag_key.json")
    rows, by = [], collections.defaultdict(collections.Counter)
    tot = collections.Counter()
    for k in key["draws"]:
        r = reads[str(k["n"])]
        by[k["stratum"]][r["verdict"]] += 1
        tot[r["verdict"]] += 1
        rows.append(dict(k, verdict=r["verdict"], reason=r.get("reason", ""), read=r.get("read", "")))
    n = sum(tot.values())
    lo, hi = wilson(tot["false"], n)
    res = {"seed": SEED, "drawn": n, "overall": dict(tot), "false_flag_rate": round(tot["false"] / n, 3), "false_rate_95pct_range": [round(lo, 3), round(hi, 3)],
           "real_rate": round(tot["real"] / n, 3), "by_shape": {s: dict(v) for s, v in sorted(by.items())}, "false_reasons": dict(collections.Counter(r["reason"] for r in rows if r["verdict"] == "false")), "rows": rows}
    with io.open(os.path.join(BUILD, "false_flag_result.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    c = sys.argv[1]
    {"draw": draw, "reveal": reveal}.get(c, lambda: show(int(sys.argv[2]), int(sys.argv[3])))()
