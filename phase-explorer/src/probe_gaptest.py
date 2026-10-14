#!/usr/bin/env python3
"""Part 2 (read-only): the gap-test holds. Seed 20261028, declared before any computation.

    python src/probe_gaptest.py counts      # population by failed test
    python src/probe_gaptest.py draw        # -> build/gaptest_blind.json (card text and ability text only), build/gaptest_key.json (leaf, hidden until the reads exist)
    python src/probe_gaptest.py show 1 40
    python src/probe_gaptest.py reveal      # after build/gaptest_reads.json exists

Population: abilities held by the gap test (src == "test_fail") on cards in the pile, no-text excluded. Stratified by failed test; one ability per card; no redraw; no hand-picking.
Leaf: the leaf the ability would find ignoring the gap (B.assign_rf_ref, n >= 5; broad leaf or unflagged), else a promoted tentative group.
"""
import collections
import io
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_unorganized_breakdown_v3 as V3
import build_ability_taxonomy as B
import build_loose_groups as BL
import probe_remaining as PR

BUILD = V3.BUILD
SEED = 20261028
N = 40


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def collect_rows():
    argv, sys.argv = sys.argv, sys.argv[:1]
    items, raw, info, meta, S = PR.collect()
    sys.argv = argv
    A, leaf_info = S["A"], S["leaf_info"]
    T = jl("ability_taxonomy.json")
    tg = jl("tentative_placements.json")
    cards = jl("ability_taxonomy_cards.json")["cards"]
    fam_keys = {k for k, _ in meta["families"]}
    ref = [j for j, a in enumerate(A) if a["kind"] == "clean" and not a["pre"]]
    Fref = [A[j]["f"] for j in ref]
    use_idx, keys, folded, fm, names, sizes, kind_of = BL.make_groups(items, raw, info, fam_keys)
    ab_groups = collections.defaultdict(list)
    for k in folded:
        for n in fm[k]:
            ab_groups[n].append(BL.gid_of(k))
    pile = set(meta["pile"])
    sel = [(n, it) for n, it in enumerate(items) if it["src"] == "test_fail" and it["oid"] in pile]
    usable = [(n, it) for n, it in sel if (it["text"] or "").strip() and it["f"]["usable"] and it["f"]["fam"] in fam_keys]
    res = dict(zip([n for n, _ in usable], B.assign_rf_ref(Fref, [it["f"] for _, it in usable], 5)))
    rows = []
    for n, it in sel:
        r = res.get(n)
        leaf, kind = "", "no leaf"
        if r is not None and r[0] != "x":
            li = leaf_info.get(tuple(r))
            if li is not None and li["n"] >= 5:
                leaf, kind = T["leaves"].get(li["id"], {}).get("name", li["id"]), ("broad leaf" if li["flags"] else "unflagged leaf")
        if not leaf:
            gs = [g for g in ab_groups.get(n, []) if g in tg["groups"]]
            if gs:
                leaf, kind = tg["groups"][gs[0]]["name"].split(" \u203a ", 1)[-1], "tentative group"
        rows.append({"n": n, "oid": it["oid"], "card": cards.get(it["oid"], {}).get("n", it["oid"]), "oracle": cards.get(it["oid"], {}).get("t", ""), "text": " ".join((it["text"] or "").split()),
                     "reason": it.get("reason"), "ref": it["ref"], "leaf": leaf, "kind": kind})
    return rows


def counts():
    rows = collect_rows()
    print("gap-test holds on pile cards:", len(rows), "cards", len({r["oid"] for r in rows}))
    print(collections.Counter(r["reason"] for r in rows))
    ok = [r for r in rows if r["text"]]
    print("with text:", len(ok), "cards", len({r["oid"] for r in ok}), collections.Counter(r["reason"] for r in ok))
    print("route:", collections.Counter(r["kind"] for r in ok))


def population():
    """The 329 cards of reason 3 (every ability is a gap-test failure or has no text; nothing eligible, nothing flagged), by the failed test of their abilities."""
    rows = collect_rows()
    rem = jl("remaining_cards.json")["primary"]
    r3 = {o for o, v in rem.items() if v == 3}
    by = collections.defaultdict(list)
    for r in rows:
        if r["oid"] in r3:
            by[r["oid"]].append(r)
    return r3, by


def card_stratum(rs):
    ok = [r for r in rs if r["text"]]
    if not ok:
        return "no text"
    reasons = {r["reason"] for r in ok}
    return "continuation" if "gap_card_continuation_gap" in reasons else ("same-line" if "gap_card_same_line_gap" in reasons else "other:" + ",".join(sorted(map(str, reasons))))


def pop_counts():
    r3, by = population()
    print("reason-3 cards", len(r3), "with a gap-test item on the pile list", len(by))
    print(collections.Counter(card_stratum(v) for v in by.values()))
    print("cards in r3 with no test_fail item:", len(r3 - set(by)))


def pop_detail():
    argv, sys.argv = sys.argv, sys.argv[:1]
    items, raw, info, meta, S = PR.collect()
    sys.argv = argv
    rem = jl("remaining_cards.json")["primary"]
    r3 = {o for o, v in rem.items() if v == 3}
    cards = jl("ability_taxonomy_cards.json")["cards"]
    per = collections.defaultdict(list)
    for it in items:
        if it["oid"] in r3:
            per[it["oid"]].append((it["src"], it.get("reason"), bool((it["text"] or "").strip())))
    kinds = collections.Counter()
    ex = collections.defaultdict(list)
    for o in r3:
        sig = tuple(sorted({(s, r, t) for s, r, t in per.get(o, [])}))
        kinds[sig] += 1
        if len(ex[sig]) < 2:
            ex[sig].append(cards[o]["n"])
    for k, v in kinds.most_common():
        print(v, k, ex[k])


def draw():
    import math
    rows = collect_rows()
    r3, by = population()
    pool = {"continuation": [], "same-line": []}
    for o, rs in sorted(by.items()):
        st = card_stratum(rs)
        if st in pool:
            pool[st].append(o)
    total = sum(len(v) for v in pool.values())
    raw_q = {s: N * len(v) / total for s, v in pool.items()}
    quota = {s: int(math.floor(q)) for s, q in raw_q.items()}
    for s in sorted(pool, key=lambda s: (-(raw_q[s] - quota[s]), s))[: N - sum(quota.values())]:
        quota[s] += 1
    unorg = jl("ability_taxonomy_unorganized.json")["groups"]
    frag = {}
    for g in unorg:
        for c in g["list"]:
            frag[c["c"]] = c.get("g") or []
    rnd = random.Random(SEED)
    blind, key = [], []
    n = 0
    for st in ("continuation", "same-line"):
        lst = list(pool[st])
        rnd.shuffle(lst)
        for o in lst[: quota[st]]:
            cand = sorted([r for r in by[o] if r["text"] and r["reason"] == ("gap_card_continuation_gap" if st == "continuation" else "gap_card_same_line_gap")], key=lambda r: r["n"])
            r = cand[rnd.randrange(len(cand))]
            n += 1
            blind.append({"n": n, "card": r["card"], "oracle_text": r["oracle"], "ability_text": r["text"], "unread_parts_of_the_card": [t for k, t in frag.get(o, [])]})
            key.append({"n": n, "oid": o, "stratum": st, "assigned_kind": r["kind"], "assigned": r["leaf"]})
    with io.open(os.path.join(BUILD, "gaptest_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "items": blind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "gaptest_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "population_cards": total, "by_stratum": {s: len(v) for s, v in pool.items()}, "quota": quota, "draws": key}, ensure_ascii=False, indent=1))
    print("population", total, {s: len(v) for s, v in pool.items()}, "quota", quota, "drawn", n)


def show(lo, hi):
    import textwrap
    for b in jl("gaptest_blind.json")["items"]:
        if lo <= b["n"] <= hi:
            print("\n=== %d  %s" % (b["n"], b["card"].encode("ascii", "replace").decode()))
            print("ORACLE:", "\n        ".join(textwrap.wrap(b["oracle_text"].replace("\n", " / ").encode("ascii", "replace").decode()[:520], 140)))
            print("ABILITY:", b["ability_text"].encode("ascii", "replace").decode()[:300])
            print("UNREAD:", " | ".join(t[:110] for t in b["unread_parts_of_the_card"][:3]).encode("ascii", "replace").decode())


def reveal():
    key = jl("gaptest_key.json")
    reads = jl("gaptest_reads.json")["reads"]
    tot, by = collections.Counter(), collections.defaultdict(collections.Counter)
    rows = []
    for k in key["draws"]:
        r = reads[str(k["n"])]
        x = dict(k, expected=r["expected"], could_change=r["could_change"], verdict=r.get("verdict", ""), why=r.get("why", ""))
        rows.append(x)
        tot[x["verdict"]] += 1
        by[x["stratum"]][x["verdict"]] += 1
        tot["unread part could change the leaf: " + x["could_change"]] += 1
    print("\n".join("%2d [%-12s] %-14s read: %-55s | leaf: %-55s | %s | %s" % (x["n"], x["stratum"], x["assigned_kind"][:14], x["expected"][:55], x["assigned"][:55], x["could_change"], x["verdict"]) for x in rows))
    if not all(x["verdict"] for x in rows):
        return
    res = {"seed": SEED, "total": dict(tot), "by_stratum": {k: dict(v) for k, v in by.items()}, "rows": rows}
    with io.open(os.path.join(BUILD, "gaptest_result.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    c = sys.argv[1]
    {"counts": counts, "pop": pop_counts, "detail": pop_detail, "draw": draw, "reveal": reveal}.get(c, lambda: show(int(sys.argv[2]), int(sys.argv[3])))()
