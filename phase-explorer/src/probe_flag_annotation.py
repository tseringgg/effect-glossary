#!/usr/bin/env python3
"""Part C (read-only): if the dropped condition were ignored, would a flagged ability land in the right leaf, and could the condition change or invert the effect? Changes nothing.

    python src/probe_flag_annotation.py draw      # -> build/flag_annotation_blind.json (card text only), build/flag_annotation_key.json (assigned leaf and sub-shape, hidden until the reads exist)
    python src/probe_flag_annotation.py show 1 20
    python src/probe_flag_annotation.py reveal    # after build/flag_annotation_reads.json exists

Seed 20261027, declared before any computation. Population: the 1,606 abilities held by the dropped-condition detector on the 1,545 cards that were left in "Not yet organized" before the 2026-10 promotions
(build/remaining_cards.json), so the count matches the earlier rounds (226 of those cards have since become tentative; their flags still block a precise placement).
Draw: 100 abilities, one per card, stratified by sub-shape in proportion to size (largest remainder), taken in seed order inside each sub-shape; none hand-picked, no redraw; an ability with no text would be
skipped (counted). For each ability I read the card's oracle text and the ability text and write (a) which effect and leaf I expect and (b) whether the dropped condition could change or invert the effect
("if you don't", "unless", "instead", "otherwise", "only if"), BEFORE the leaf the build would assign is shown. Right / loose / wrong compares my expectation with that leaf.
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
import build_ability_taxonomy as B
import probe_remaining as PR

BUILD = V3.BUILD
SEED = 20261027
N = 100


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def draw():
    argv, sys.argv = sys.argv, sys.argv[:1]        # the taxonomy build parses argv
    items, raw, info, meta, S = PR.collect()
    sys.argv = argv
    A, leaf_info = S["A"], S["leaf_info"]
    T = jl("ability_taxonomy.json")
    tg = jl("tentative_placements.json")
    rset = set(jl("remaining_cards.json")["primary"])
    fam_keys = {k for k, _ in meta["families"]}
    cd = {(h["oid"], h["bucket"], h["idx"]): h for h in jl("condition_drops.json")}
    ref = [j for j, a in enumerate(A) if a["kind"] == "clean" and not a["pre"]]
    Fref = [A[j]["f"] for j in ref]
    flagged = [(n, it) for n, it in enumerate(items) if it["src"] == "flagged" and it["oid"] in rset]
    shape = lambda it: (cd.get((it["oid"], it["ref"][1], it["ref"][2])) or {}).get("shape", "(no detector record)")
    by = collections.defaultdict(list)
    for n, it in flagged:
        by[shape(it)].append((n, it))
    total = len(flagged)
    shapes = sorted(by)
    raw_q = {s: N * len(by[s]) / total for s in shapes}
    quota = {s: int(math.floor(raw_q[s])) for s in shapes}
    left = N - sum(quota.values())
    for s in sorted(shapes, key=lambda s: (-(raw_q[s] - quota[s]), s))[:left]:
        quota[s] += 1
    rnd = random.Random(SEED)
    used, pick, skipped = set(), [], 0
    for s in shapes:
        lst = sorted(by[s], key=lambda x: (x[1]["oid"], x[1]["ref"][1], x[1]["ref"][2]))
        rnd.shuffle(lst)
        got = 0
        for n, it in lst:
            if got >= quota[s]:
                break
            if it["oid"] in used:
                continue
            if not (it["text"] or "").strip():
                skipped += 1
                continue
            used.add(it["oid"])
            pick.append((s, n, it))
            got += 1
    usable = [(s, n, it) for s, n, it in pick if it["f"]["usable"] and it["f"]["fam"] in fam_keys]
    res = dict(zip([n for _, n, _ in usable], B.assign_rf_ref(Fref, [it["f"] for _, _, it in usable], 5)))
    cards = jl("ability_taxonomy_cards.json")["cards"]
    ab_groups = collections.defaultdict(list)
    import build_loose_groups as BL
    use_idx, keys, folded, fm, names, sizes, kind_of = BL.make_groups(items, raw, info, fam_keys)
    for k in folded:
        for n in fm[k]:
            ab_groups[n].append(BL.gid_of(k))
    blind, key = [], []
    for i, (s, n, it) in enumerate(pick, 1):
        c = cards.get(it["oid"], {})
        blind.append({"n": i, "card": c.get("n", it["oid"]), "oracle_text": c.get("t", ""), "ability_text": " ".join(it["text"].split())})
        r = res.get(n)
        if r is None or r[0] == "x":
            leaf, kind = "", "no usable signature"
        else:
            li = leaf_info.get(tuple(r))
            if li is None or li["n"] < 5:
                leaf, kind = "", "no leaf of 5"
            else:
                leaf, kind = T["leaves"].get(li["id"], {}).get("name", li["id"]), ("broad leaf" if li["flags"] else "unflagged leaf")
        if not leaf:
            gs = [g for g in ab_groups.get(n, []) if g in tg["groups"]]
            if gs:
                leaf, kind = tg["groups"][gs[0]]["name"].split(" › ", 1)[1], "tentative group"
        key.append({"n": i, "oid": it["oid"], "stratum": s, "assigned_kind": kind, "assigned": leaf, "family": it["f"]["fam"], "ftype": it["f"]["ftype"]})
    with io.open(os.path.join(BUILD, "flag_annotation_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "items": blind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "flag_annotation_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "population": total, "cards": len({it['oid'] for _, it in flagged}), "by_shape": {s: len(by[s]) for s in shapes}, "quota": quota, "skipped_no_text": skipped, "draws": key}, ensure_ascii=False, indent=1))
    print("population", total, "cards", len({it["oid"] for _, it in flagged}), "drawn", len(pick), "skipped", skipped)
    print(quota)


def show(lo, hi):
    for b in jl("flag_annotation_blind.json")["items"]:
        if lo <= b["n"] <= hi:
            print("\n=== %d  %s" % (b["n"], b["card"].encode("ascii", "replace").decode()))
            print("ORACLE:", b["oracle_text"].replace("\n", " / ").encode("ascii", "replace").decode()[:600])
            print("ABILITY:", b["ability_text"].encode("ascii", "replace").decode()[:300])


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((c - m) / d, 3), round((c + m) / d, 3)


def reveal():
    key = jl("flag_annotation_key.json")
    reads = jl("flag_annotation_reads.json")["reads"]
    rows, by, tot = [], collections.defaultdict(collections.Counter), collections.Counter()
    for k in key["draws"]:
        r = reads[str(k["n"])]
        rows.append(dict(k, expected=r["expected"], inverts=r["inverts"], inverting_word=r.get("word", ""), verdict=r.get("verdict", ""), why=r.get("why", "")))
    print("\n".join("%2d [%-22s] %-16s read: %-60s | %s | %s" % (x["n"], x["stratum"][:22], x["assigned_kind"][:16], x["expected"][:60], x["assigned"][:60], x["inverts"]) for x in rows))
    if all(x["verdict"] for x in rows):
        for x in rows:
            by[x["stratum"]][x["verdict"]] += 1
            tot[x["verdict"]] += 1
            by[x["stratum"]]["condition " + x["inverts"]] += 1
            tot["condition " + x["inverts"]] += 1
        n = 100
        res = {"seed": SEED, "total": dict(tot), "wrong_rate_95pct_range": wilson(tot["wrong"], n), "by_shape": {k: dict(v) for k, v in sorted(by.items())}, "rows": rows}
        with io.open(os.path.join(BUILD, "flag_annotation_result.json"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(res, ensure_ascii=False, indent=1))
        print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    c = sys.argv[1]
    {"draw": draw, "reveal": reveal}.get(c, lambda: show(int(sys.argv[2]), int(sys.argv[3])))()
