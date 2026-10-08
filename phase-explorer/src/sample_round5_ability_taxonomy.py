#!/usr/bin/env python3
"""Round-5 hand-check samples (after the naming fixes). Seed 20261012, declared before any computation. Run once; never redrawn.

    python src/sample_round5_ability_taxonomy.py   # -> build/ability_taxonomy_handcheck_round5.json

  names      40 leaves, drawn by stratum in this fixed order (leaves already judged in round 4 are excluded from every pool):
               all      6 unflagged leaves of 10+ whose name says all / each / every
               fix1     6 leaves of 5+ whose static name changed in this round (wrong default subject; player-rule modes)
               tp       both "that player" leaves (forced, flagged)
               flagged  6 other flagged leaves of 10+
               varied   10 from the 60 unflagged leaves of 10+ with the most distinct member shapes
               mid      10 unflagged leaves of 10-30 abilities, not in the varied pool
             = 6 + 6 + 2 + 6 + 10 + 10 = 40 (a leaf is taken by the first stratum it qualifies for). Each comes with 8 shuffled members plus up
             to 3 MINORITY members (they differ from the leaf's most common value on a dropped field).
  leaves     30: 10 finest (level 5), 10 middle (3-4), 10 coarsest (2); a leaf with fewer than 8 placed members is skipped and the next taken.
  placed     40 abilities in state "placed" (an unflagged leaf of 5 or more).
Random(SEED-name) per draw; pools are sorted by id first. The judge reads member text first and the reveal (name, signature) afterwards.
Bars: names more than 10% misleading, leaves more than 15% incoherent, placements more than 5% wrong. Small counts cannot show a rate.
"""
import collections
import contextlib
import io
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ability_taxonomy as B  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
SEED = 20261012
DROPPED = ["obj", "ctrl", "quant", "props", "kw", "dur", "cond", "wrap", "chain", "tok"]


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def R(name):
    return random.Random("%d-%s" % (SEED, name))


def main():
    B.dump = lambda *a, **k: None
    with contextlib.redirect_stdout(io.StringIO()):
        S = B.main()
    A, mem, leaf_info = S["A"], S["members"], S["leaf_info"]
    T, G, C = jl("ability_taxonomy.json"), jl("ability_taxonomy_ledger.json"), jl("ability_taxonomy_cards.json")["cards"]
    prev = jl("ability_taxonomy_round5_prev_names.json")
    r4 = {n["leaf"] for n in jl("ability_taxonomy_handcheck_round4.json")["names"]}
    leaves = T["leaves"]
    by_id = {li["id"]: (lf, li) for lf, li in leaf_info.items()}
    cname = lambda oid: C.get(oid, {}).get("n", oid)    # noqa: E731

    def text_j(j):
        t = (A[j]["text"] or "").strip()
        return t if t else "(no ability text) card: " + C.get(A[j]["oid"], {}).get("t", "")[:200].replace("\n", " / ")

    def shape(j):
        f = A[j]["f"]
        return tuple((f.get(k, "") if f.get(k, "") != "-" else "") for k in DROPPED)

    def members_for(lid, k=8):
        lf = by_id[lid][0]
        js = sorted(mem[lf], key=lambda j: (A[j]["oid"], A[j]["b"], str(A[j]["i"])))
        R("members-" + lid).shuffle(js)
        main_rows = [[cname(A[j]["oid"]), text_j(j)[:240]] for j in js[:k]]
        modal = [collections.Counter(shape(j)[i] for j in mem[lf]).most_common(1)[0][0] for i in range(len(DROPPED))]
        diff = lambda j: [DROPPED[i] for i in range(len(DROPPED)) if shape(j)[i] != modal[i]]   # noqa: E731
        minor = [j for j in sorted(mem[lf], key=lambda j: (A[j]["oid"], A[j]["b"], str(A[j]["i"]))) if diff(j) and j not in js[:k]]
        R("minority-" + lid).shuffle(minor)
        return main_rows, [[cname(A[j]["oid"]), text_j(j)[:240], diff(j)] for j in minor[:3]], sum(1 for j in mem[lf] if diff(j))

    def reveal(lid):
        l = leaves[lid]
        return {"name": l["name"], "sig": l["sig"], "flags": l["flags"], "level": l["level"], "abilities": l["abilities"], "auto_named": l["auto_named"]}

    out = {"v": 1, "seed": SEED}
    vis10 = sorted(k for k, l in leaves.items() if l["abilities"] >= 10 and k not in r4)
    flagged = {k for k in vis10 if leaves[k]["flags"]}
    unfl = [k for k in vis10 if k not in flagged]
    chosen, taken = {}, set()

    def take(stage, pool, n):
        pool = sorted(k for k in pool if k not in taken)
        pick = R(stage).sample(pool, n)
        chosen[stage] = pick
        taken.update(pick)
        return len(pool)
    pools = {}
    allp = [k for k in unfl if any(w in (" " + leaves[k]["name"].lower().split(" — ")[0] + " ") for w in (" all ", " each ", " every "))]
    pools["all"] = take("all", allp, 6)
    fix1 = [k for k, l in leaves.items() if l["abilities"] >= 5 and "static:" in l["sig"] and k in prev and prev[k] != l["name"] and k not in r4 and not l["flags"]]
    pools["fix1"] = take("fix1", fix1, 6)
    tp = sorted(k for k, l in leaves.items() if l["flags"] and ("ftype=Draw" in l["sig"] or "ftype=GainLife" in l["sig"]) and "TriggeringPlayer" in l["sig"])
    chosen["tp"] = tp
    taken.update(tp)
    fpool = sorted(k for k in flagged if k not in taken)
    pools["flagged"] = take("flagged", fpool, 6)
    variety = {k: len({shape(j) for j in mem[by_id[k][0]]}) for k in unfl}
    vpool = sorted(unfl, key=lambda k: (-variety[k], k))[:60]
    pools["varied"] = take("varied", vpool, 10)
    mpool = [k for k in unfl if 10 <= leaves[k]["abilities"] <= 30 and k not in vpool]
    pools["mid"] = take("mid", mpool, 10)
    out["name_pools"] = pools
    names = []
    for st in ("all", "fix1", "tp", "flagged", "varied", "mid"):
        for lid in chosen[st]:
            m, mi, nm = members_for(lid)
            names.append({"leaf": lid, "drawn_as": st, "members": m, "minority": mi, "n_minority": nm, "reveal": reveal(lid)})
    out["names"] = names
    # ---------------- leaves (30) and placements (40)
    rows = G["rows"]
    by_leaf = {}
    for r in rows:
        if r[6] in ("placed", "placed_broad") and r[8]:
            by_leaf.setdefault(r[8], []).append(r)

    def text_r(r):
        t = (r[5] or "").strip()
        return t if t else "(no ability text) card: " + C.get(r[0], {}).get("t", "")[:200].replace("\n", " / ")

    def lmembers(lid, k=8):
        m = sorted(by_leaf.get(lid, []), key=lambda r: (r[0], r[2], r[3], -1 if r[4] is None else r[4]))
        R("lmembers-" + lid).shuffle(m)
        return [[cname(r[0]), text_r(r)[:240]] for r in m[:k]]
    bands = {"finest": lambda l: l["level"] == 5, "middle": lambda l: l["level"] in (3, 4), "coarsest": lambda l: l["level"] == 2}
    lv, skipped = [], {}
    for band, pred in bands.items():
        ids = sorted(k for k, l in leaves.items() if pred(l))
        R("leaves-" + band).shuffle(ids)
        got, sk = [], []
        for lid in ids:
            if len(got) == 10:
                break
            if len(by_leaf.get(lid, [])) < 8:
                sk.append([lid, len(by_leaf.get(lid, []))])
                continue
            got.append({"band": band, "leaf": lid, "members": lmembers(lid), "reveal": reveal(lid)})
        skipped[band] = sk
        lv.extend(got)
    out["leaves"], out["leaves_skipped_under_8"] = lv, skipped
    pool = sorted((r for r in rows if r[6] == "placed"), key=lambda r: (r[0], r[1], r[2], r[3], -1 if r[4] is None else r[4]))
    out["placed_pool"] = len(pool)
    out["placed"] = [{"card": cname(r[0]), "oid": r[0], "text": text_r(r)[:300], "card_text": C.get(r[0], {}).get("t", "")[:400],
                     "reveal": {"leaf": r[8], "name": leaves[r[8]]["name"], "sig": leaves[r[8]]["sig"]}} for r in R("placed").sample(pool, 40)]
    with io.open(os.path.join(BUILD, "ability_taxonomy_handcheck_round5.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print(pools, {k: len(v) for k, v in chosen.items()}, "names", len(names), "leaves", len(lv), "placed", len(out["placed"]),
          {b: len(s) for b, s in skipped.items()})


if __name__ == "__main__":
    main()
