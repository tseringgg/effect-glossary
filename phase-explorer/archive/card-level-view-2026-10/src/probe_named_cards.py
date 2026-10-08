#!/usr/bin/env python3
"""Per-ability table for named cards (investigation only) -> build/ability_probe_named.json."""
import collections
import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap  # noqa: E402

BUILD = ap.BUILD
FIXED = ["Mulldrifter", "Spark Double", "Sakura-Tribe Elder", "Hallowed Fountain", "Psychosis Crawler",
         "Rhystic Study", "Wall of Omens", "Eternal Witness", "Solemn Simulacrum", "Tireless Tracker"]


def main():
    sp = ap.Space()
    L = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    probe = ap.jl("ability_probe.json")
    br = ap.jl("branches.json")
    phr = ap.jl("leaf_phrases.json")["leaves"]
    rec_chunk = P["recovered"]["chunk"]

    def entry_of(fid):
        return sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]

    def linfo(l):
        e = phr.get(str(l)) or {}
        ph = e.get("edited") or (e["phrases"][0]["phrase"] if e.get("phrases") else "")
        return {"leaf": int(l), "size": int(sp.leaf_size[l]), "phrase": ph,
                "label": (sp.clusters["labels"].get(str(l)) or "")[:80],
                "branches": br["leaf_branches"].get(str(l)) or []}

    g2 = {m["oid"]: m for m in probe["group2_cards"]}
    by_name = collections.defaultdict(list)
    for o, r in L.items():
        if r["status"] != "out_of_scope":
            by_name[r["name"]].append(o)
    # extras: 3 proximity cards, 1 group-2 card in 0.50-0.70, 1 in <0.50 (deterministic picks, real cards only)
    prox = sorted((r["name"], o) for o, r in L.items() if r["placement"]["method"] == "proximity"
                  and r["status"] == "noise" and not r["name"].startswith("A-")
                  and len(r["evidence"]["faces"]) == 1)
    extras = [prox[i][0] for i in (len(prox) // 6, len(prox) // 2, 5 * len(prox) // 6)]
    mid = sorted((m["name"], m["oid"]) for m in g2.values() if 0.5 <= m["blended"] < 0.7 and m["n_bearing"] == 2
                 and not m["name"].startswith("A-"))
    low = sorted((m["name"], m["oid"]) for m in g2.values() if m["blended"] < 0.5 and m["n_bearing"] >= 3
                 and not m["name"].startswith("A-"))
    extras += [mid[len(mid) // 2][0], low[len(low) // 2][0]]
    names = FIXED + extras
    out = []
    for name in names:
        oid = next(o for o in by_name[name] if L[o]["status"] != "out_of_scope")
        r = L[oid]
        card = {"name": name, "oid": oid, "status": r["status"],
                "placement": {k: v for k, v in r["placement"].items() if k in ("method", "leaf", "similarity", "reason", "best_leaf")},
                "faces": []}
        for f in r["evidence"]["faces"]:
            fid = f["id"]
            e = entry_of(fid)
            items = ap.ability_items(e)
            toks = [[k for k in sorted(t) if k in sp.vocab] for *_, t in items]
            best_leaf, best_sc, S = sp.score(toks)
            blended_leaf, blended_sc, _ = sp.score([sorted(ap.cs.card_features(e))])
            face = {"face": e.get("name"), "blended_best_leaf": linfo(blended_leaf[0]),
                    "blended_score": round(float(blended_sc[0]), 4),
                    "own_leaf": sp.lab.get(fid), "abilities": []}
            for (b, i, it, t), tk, bl, bs in zip(items, toks, best_leaf, best_sc):
                a = {"bucket": b, "idx": i, "text": (it.get("description") or "")[:150], "tokens": tk}
                if tk:
                    a["score"] = round(float(bs), 4)
                    a["best"] = linfo(bl)
                    top = np.argsort(-S[len(face["abilities"])])[:3] if False else None
                else:
                    a["score"] = None
                    a["note"] = "no tokens (item has no effect/mode feature)"
                face["abilities"].append(a)
            card["faces"].append(face)
        out.append(card)
    with io.open(os.path.join(BUILD, "ability_probe_named.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    for c in out:
        print(f"\n=== {c['name']} | status {c['status']} | {c['placement']}")
        for f in c["faces"]:
            print(f"  face {f['face']}: blended {f['blended_score']} -> leaf {f['blended_best_leaf']['leaf']} "
                  f"'{f['blended_best_leaf']['phrase'][:40]}' {f['blended_best_leaf']['branches'][:2]}; own leaf {f['own_leaf']}")
            for a in f["abilities"]:
                if a["score"] is None:
                    print(f"    [{a['bucket']}#{a['idx']}] {a['text'][:100]!r} -> {a['note']}")
                else:
                    b = a["best"]
                    print(f"    [{a['bucket']}#{a['idx']}] {a['text'][:100]!r} {len(a['tokens'])}tok -> {a['score']:.3f} leaf {b['leaf']} "
                          f"(n={b['size']}) '{b['phrase'][:42]}' | {b['label'][:40]} | {b['branches'][:3]}")


if __name__ == "__main__":
    main()
