#!/usr/bin/env python3
"""Round-4 hand-check samples (the naming cleanup round). Seed 20261011, declared before any computation. Run once; never redrawn.

    python src/sample_round4_ability_taxonomy.py   # -> build/ability_taxonomy_handcheck_round4.json

  names      40 leaves of 10 or more abilities, drawn by stratum in this fixed order:
               varies   5 unflagged leaves whose name contains "varies"            (forced stratum, counts toward "mid-size")
               destroy  the leaf named "Destroy nonartifact creatures"            (forced, counts toward "varied")
               tp       both "that player" leaves (Draw, GainLife)                 (forced, counts toward "flagged")
               varied   14 from the 60 unflagged leaves with the most distinct member shapes (distinct tuples of the dropped fields)
               mid      10 unflagged leaves of 10-30 abilities, not in the varied pool
               flagged  8 flagged leaves of 10 or more, excluding the two "that player" leaves
             = 15 varied + 15 mid-size + 10 flagged. Each name comes with 8 shuffled members plus up to 3 MINORITY members (members that
             differ from the leaf's most common value on a dropped field), so the judge reads the minority specifically.
  leaves     30: 10 finest (level 5), 10 middle (3-4), 10 coarsest (2); a leaf with fewer than 8 placed members is skipped and the next taken.
  placed     40 abilities in state "placed" (an unflagged leaf of 5 or more).
Random(SEED-name) per draw; pools are sorted by id first. The judge reads member text first and the reveal (name, signature) afterwards.
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
SEED = 20261011
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
        minor = [j for j in sorted(mem[lf], key=lambda j: (A[j]["oid"], A[j]["b"], str(A[j]["i"]))) if any(shape(j)[i] != modal[i] for i in range(len(DROPPED)))
                 and j not in js[:k]]
        R("minority-" + lid).shuffle(minor)
        minor_rows = [[cname(A[j]["oid"]), text_j(j)[:240], [DROPPED[i] for i in range(len(DROPPED)) if shape(j)[i] != modal[i]]] for j in minor[:3]]
        n_minor = sum(1 for j in mem[lf] if any(shape(j)[i] != modal[i] for i in range(len(DROPPED))))
        return main_rows, minor_rows, n_minor

    def reveal(lid):
        l = leaves[lid]
        return {"name": l["name"], "sig": l["sig"], "flags": l["flags"], "level": l["level"], "abilities": l["abilities"], "auto_named": l["auto_named"]}

    out = {"v": 1, "seed": SEED}
    # ---------------- names
    vis10 = sorted(k for k, l in leaves.items() if l["abilities"] >= 10)
    flagged = {k for k in vis10 if leaves[k]["flags"]}
    unfl = [k for k in vis10 if k not in flagged]
    # both "that player" leaves, whatever their size (the GainLife one has 8 abilities; the brief names both explicitly)
    tp = sorted(k for k, l in leaves.items() if l["flags"] and ("ftype=Draw" in l["sig"] or "ftype=GainLife" in l["sig"]) and "TriggeringPlayer" in l["sig"])
    destroy = sorted(k for k in unfl if leaves[k]["name"] == "Destroy nonartifact creatures")
    varies_pool = [k for k in unfl if " varies" in leaves[k]["name"]]
    chosen = {}
    chosen["varies"] = R("varies").sample(varies_pool, 5)
    chosen["destroy"] = destroy[:1]
    chosen["tp"] = tp[:2]
    forced = set(sum(chosen.values(), []))
    variety = {}
    for k in unfl:
        lf = by_id[k][0]
        variety[k] = len({shape(j) for j in mem[lf]})
    vpool = sorted(unfl, key=lambda k: (-variety[k], k))[:60]
    vdraw_pool = sorted(k for k in vpool if k not in forced)
    chosen["varied"] = R("varied").sample(vdraw_pool, 14)
    midpool = sorted(k for k in unfl if 10 <= leaves[k]["abilities"] <= 30 and k not in vpool and k not in forced)
    chosen["mid"] = R("mid").sample(midpool, 10)
    fpool = sorted(k for k in flagged if k not in tp)
    chosen["flagged"] = R("flagged").sample(fpool, 8)
    out["name_pools"] = {"varies": len(varies_pool), "varied_pool": len(vdraw_pool), "mid_pool": len(midpool), "flagged_pool": len(fpool),
                         "tp_leaves": len(tp), "destroy_leaves": len(destroy)}
    names = []
    stratum_slot = {"varies": "mid", "destroy": "varied", "tp": "flagged", "varied": "varied", "mid": "mid", "flagged": "flagged"}
    for st in ("varies", "destroy", "tp", "varied", "mid", "flagged"):
        for lid in chosen[st]:
            m, mi, nm = members_for(lid)
            names.append({"leaf": lid, "drawn_as": st, "slot": stratum_slot[st], "members": m, "minority": mi, "n_minority": nm, "reveal": reveal(lid)})
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
        taken, sk = [], []
        for lid in ids:
            if len(taken) == 10:
                break
            if len(by_leaf.get(lid, [])) < 8:
                sk.append([lid, len(by_leaf.get(lid, []))])
                continue
            taken.append({"band": band, "leaf": lid, "members": lmembers(lid), "reveal": reveal(lid)})
        skipped[band] = sk
        lv.extend(taken)
    out["leaves"], out["leaves_skipped_under_8"] = lv, skipped
    pool = sorted((r for r in rows if r[6] == "placed"), key=lambda r: (r[0], r[1], r[2], r[3], -1 if r[4] is None else r[4]))
    out["placed_pool"] = len(pool)
    out["placed"] = [{"card": cname(r[0]), "oid": r[0], "text": text_r(r)[:300], "card_text": C.get(r[0], {}).get("t", "")[:400],
                     "reveal": {"leaf": r[8], "name": leaves[r[8]]["name"], "sig": leaves[r[8]]["sig"]}} for r in R("placed").sample(pool, 40)]
    with io.open(os.path.join(BUILD, "ability_taxonomy_handcheck_round4.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print(out["name_pools"], {k: len(v) for k, v in chosen.items()}, "names", len(names), "leaves", len(lv), "placed", len(out["placed"]),
          {b: len(s) for b, s in skipped.items()})


if __name__ == "__main__":
    main()
