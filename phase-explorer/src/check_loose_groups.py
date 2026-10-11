#!/usr/bin/env python3
"""Hand checks for the loosely grouped layer, drawn from the built files (build/loose_groups.json). Nothing here changes the build.

    python src/check_loose_groups.py draw     # -> build/loose_groups_check_blind.json  (member texts only: no names, keys or reasons)
    python src/check_loose_groups.py reveal   # after build/loose_groups_check_reads.json exists -> build/loose_groups_check_result.json + printed comparison

Seeds, declared before any computation:
  20261017  coherence check: 30 groups = every group over 100 cards (10 wanted; fewer exist), 10 groups of 31-100 cards, 10 from the bucket and catch-all groups
            (the catch-alls already drawn in the first stratum are not drawn twice); 8 members read from each, chosen by the same seed;
  20261018  name check: 40 groups across the size bands (15 of 10-30 cards, 15 of 31-100, 10 buckets or catch-alls); 6 members read from each.
Order of work: the reads (what each group is, from the member text alone; for names also what I would call it) are written to
build/loose_groups_check_reads.json BEFORE the name, key or reasons of any sampled group is looked at.
"""
import io
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
SEED_COH, SEED_NAMES = 20261017, 20261018


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def members(g, rnd, k):
    rows = sorted(g["m"], key=lambda r: r[0])
    rnd.shuffle(rows)
    return [{"text": " ".join((r[1] or "(no separate rules line)").split())[:150]} for r in rows[:k]]


def draw():
    d = jl("loose_groups.json")
    G = d["groups"]
    cards = {gid: g["cards"] for gid, g in G.items()}
    over = sorted(g for g in G if cards[g] > 100)
    mid = sorted(g for g in G if 31 <= cards[g] <= 100 and G[g]["kind"] == "group")
    bucket = sorted(g for g in G if G[g]["kind"] in ("bucket", "catchall") and g not in over)
    rnd = random.Random(SEED_COH)
    coh = over[:10] + rnd.sample(mid, min(10, len(mid))) + rnd.sample(bucket, min(10, len(bucket)))
    strata = ["over 100"] * len(over[:10]) + ["31-100"] * min(10, len(mid)) + ["bucket or catch-all"] * min(10, len(bucket))
    pools = {"over 100": len(over), "31-100 (plain groups)": len(mid), "buckets and catch-alls not already drawn": len(bucket)}
    blind = {"seed": SEED_COH, "pools": pools, "groups": [{"n": i + 1, "members": members(G[g], rnd, 8)} for i, g in enumerate(coh)]}
    key = {"seed": SEED_COH, "groups": [{"n": i + 1, "gid": g, "stratum": strata[i]} for i, g in enumerate(coh)]}
    rn = random.Random(SEED_NAMES)
    small = sorted(g for g in G if 10 <= cards[g] <= 30 and G[g]["kind"] == "group")
    big = sorted(g for g in G if 31 <= cards[g] <= 100 and G[g]["kind"] == "group")
    bk = sorted(g for g in G if G[g]["kind"] in ("bucket", "catchall"))
    nm = rn.sample(small, 15) + rn.sample(big, 15) + rn.sample(bk, 10)
    nblind = {"seed": SEED_NAMES, "pools": {"10-30": len(small), "31-100": len(big), "bucket or catch-all": len(bk)},
              "groups": [{"n": i + 1, "members": members(G[g], rn, 6)} for i, g in enumerate(nm)]}
    nkey = {"seed": SEED_NAMES, "groups": [{"n": i + 1, "gid": g} for i, g in enumerate(nm)]}
    with io.open(os.path.join(BUILD, "loose_groups_check_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"coherence": blind, "names": nblind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "loose_groups_check_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"coherence": key, "names": nkey}, ensure_ascii=False, indent=1))
    print("pools", pools, nblind["pools"], "coherence groups:", len(coh), "name groups:", len(nm))


def show(part, lo=None, hi=None):
    b = jl("loose_groups_check_blind.json")[part]
    for g in b["groups"]:
        if lo and not (lo <= g["n"] <= hi):
            continue
        print("\n### %s %d" % (part[:4], g["n"]))
        for m in g["members"]:
            print("  -", m["text"].encode("ascii", "replace").decode())


def reveal():
    reads = jl("loose_groups_check_reads.json")
    d = jl("loose_groups_loaded.json") if False else jl("loose_groups.json")
    key = jl("loose_groups_check_key.json")
    out = {"coherence": [], "names": []}
    cv = {"coherent": 0, "loose": 0, "incoherent": 0}
    for k in key["coherence"]["groups"]:
        g = d["groups"][k["gid"]]
        r = reads["coherence"][str(k["n"])]
        cv[r["verdict"]] += 1
        out["coherence"].append({"n": k["n"], "stratum": k["stratum"], "name": g["name"], "cards": g["cards"], "kind": g["kind"], "read": r["read"], "verdict": r["verdict"]})
        print("%2d [%s] %s (%d) | read: %s | %s" % (k["n"], k["stratum"], g["name"].encode("ascii", "replace").decode(), g["cards"], r["read"], r["verdict"]))
    nv = {"fine": 0, "misleads": 0}
    for k in key["names"]["groups"]:
        g = d["groups"][k["gid"]]
        r = reads["names"][str(k["n"])]
        nv[r["verdict"]] += 1
        out["names"].append({"n": k["n"], "name": g["name"], "cards": g["cards"], "kind": g["kind"], "my_name": r["my_name"], "verdict": r["verdict"], "why": r.get("why", "")})
        print("%2d %s (%d) | I would call it: %s | %s %s" % (k["n"], g["name"].encode("ascii", "replace").decode(), g["cards"], r["my_name"], r["verdict"], r.get("why", "")))
    out["coherence_summary"] = cv
    out["names_summary"] = nv
    n = sum(cv.values())
    out["coherence_incoherent_pct"] = round(100.0 * cv["incoherent"] / n, 1)
    out["names_misleading_pct"] = round(100.0 * nv["misleads"] / sum(nv.values()), 1)
    with io.open(os.path.join(BUILD, "loose_groups_check_result.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1))
    print(cv, out["coherence_incoherent_pct"], nv, out["names_misleading_pct"])


if __name__ == "__main__":
    {"draw": draw, "reveal": reveal, "show": lambda: show(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))}[sys.argv[1]]()
