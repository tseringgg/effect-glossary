#!/usr/bin/env python3
"""Part 1 probe (read-only): population and condition-text extraction for the condition-annotation layer. Changes nothing.

    python src/probe_annotation.py        # -> build/annotation_probe.json

Candidate = an ability the detector holds for a dropped condition (src == "flagged") that has text. Route (condition ignored, same machinery as probe_flag_annotation.py):
unflagged leaf / broad leaf (leaf of >=5 from B.assign_rf_ref) / tentative group (a promoted tentative group holds the ability) / none.
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_unorganized_breakdown_v3 as V3
import build_ability_taxonomy as B
import build_loose_groups as BL
import probe_remaining as PR

BUILD = V3.BUILD


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def main():
    argv, sys.argv = sys.argv, sys.argv[:1]
    items, raw, info, meta, S = PR.collect()
    sys.argv = argv
    A, leaf_info, view = S["A"], S["leaf_info"], S["view"]
    T = jl("ability_taxonomy.json")
    tg = jl("tentative_placements.json")
    cards = jl("ability_taxonomy_cards.json")["cards"]
    fam_keys = {k for k, _ in meta["families"]}
    cd = {(h["oid"], h["bucket"], h["idx"]): h for h in jl("condition_drops.json")}
    ref = [j for j, a in enumerate(A) if a["kind"] == "clean" and not a["pre"]]
    Fref = [A[j]["f"] for j in ref]
    use_idx, keys, folded, fm, names, sizes, kind_of = BL.make_groups(items, raw, info, fam_keys)
    ab_groups = collections.defaultdict(list)
    for k in folded:
        for n in fm[k]:
            ab_groups[n].append(BL.gid_of(k))
    flagged = [(n, it) for n, it in enumerate(items) if it["src"] == "flagged"]
    cand = [(n, it) for n, it in flagged if (it["text"] or "").strip()]
    usable = [(n, it) for n, it in cand if it["f"]["usable"] and it["f"]["fam"] in fam_keys]
    res = dict(zip([n for n, _ in usable], B.assign_rf_ref(Fref, [it["f"] for _, it in usable], 5)))
    tent = set(tg["by_card"])
    out_rows = []
    for n, it in cand:
        r = res.get(n)
        leaf, lid, route = "", "", "none"
        if r is not None and r[0] != "x":
            li = leaf_info.get(tuple(r))
            if li is not None and li["n"] >= 5:
                lid = li["id"]
                leaf = T["leaves"].get(lid, {}).get("name", lid)
                route = "broad leaf" if li["flags"] else "unflagged leaf"
        if route == "none":
            gs = [g for g in ab_groups.get(n, []) if g in tg["groups"]]
            if gs:
                leaf, lid, route = tg["groups"][gs[0]]["name"], gs[0], "tentative group"
        o = it["oid"]
        h = cd.get((o, it["ref"][1], it["ref"][2])) or {}
        status = "tentative" if o in tent else (view.get(o, ["?"])[0])
        out_rows.append({"n": n, "oid": o, "card": cards.get(o, {}).get("n", o), "status": status, "route": route, "leaf": leaf, "leaf_id": lid, "shape": h.get("shape", "(none)"), "sub": h.get("sub", "(none)"),
                         "text": " ".join(it["text"].split()), "clauses": h.get("clauses", []), "missing": h.get("missing", []), "fam": it["f"]["fam"], "ftype": it["f"]["ftype"], "chain": it["f"]["chain"]})
    nofl_text = sum(1 for n, it in flagged if not (it["text"] or "").strip())
    json.dump({"flagged_total": len(flagged), "flagged_no_text": nofl_text, "rows": out_rows}, io.open(os.path.join(BUILD, "annotation_probe.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False)
    c = collections.Counter((r["status"], r["route"]) for r in out_rows)
    print("flagged", len(flagged), "no text", nofl_text, "with text", len(cand))
    for k, v in sorted(c.items()):
        print(k, v)


if __name__ == "__main__":
    main()
