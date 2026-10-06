#!/usr/bin/env python3
"""Diagnosis only: why are mass land denial cards in "Not yet organized", and how widespread is the problem?

    python src/probe_land_denial.py

Reads the ledger, ability ledger, unorganized files, clustering, also-fits, the placement layers and the
Scryfall oracle-tag file (data/oracle-tags-raw.json lives in development/versions/card_function_search_v0.2;
it is read in place, dated 2026-07-16, so cards released after that have no tags). Writes only
build/land_denial_probe.json (a measurement). Places nothing, changes nothing. Tag data is used for
measurement ONLY and never feeds a placement: using it to judge placement would be circular.
"""
import collections
import io
import json
import os
import re
import sys

import numpy as np

try:
    import hdbscan as _h  # noqa: F401  (import the real one before ability_probe stubs it)
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap      # noqa: E402
import ability_rules as ar      # noqa: E402
import build_ledger as BL       # noqa: E402

TAGS = r"C:\source\deckdoctor\development\versions\card_function_search_v0.2\data\oracle-tags-raw.json"
BUILD = ap.BUILD

# ---------------------------------------------------------------------------- text patterns
VERB = r"(?:destroy|destroys|exile|exiles|sacrifice|sacrifices|return|returns|put|puts)"
PATTERNS = {
    "destroy_all_lands": re.compile(r"\bdestroy all (?:[a-z,'-]+ ){0,8}?lands?\b", re.I),
    "exile_all_lands": re.compile(r"\bexile all (?:[a-z,'-]+ ){0,8}?lands?\b", re.I),
    "sacrifice_lands": re.compile(r"\b(?:each (?:player|opponent)|all players|that player|target player|you) sacrifices? (?:all |each |x |\d+ |two |three |four |five |half )?(?:[a-z-]+ ){0,3}?lands\b|\bsacrifices? all (?:[a-z-]+ )?lands\b", re.I),
    "bounce_all_lands": re.compile(r"\breturn all (?:[a-z,'-]+ ){0,6}?(?:lands?|permanents)\b[^.]*\b(?:hands?|library|libraries)\b", re.I),
    "each_player_chooses_lands": re.compile(r"\beach player chooses [^.]*\blands?\b[^.]*\bsacrifices? the rest\b|\bsacrifices? the rest\b", re.I),
    "all_lands_verb": re.compile(r"\b(?:destroy|exile|sacrifice|return)[a-z]* [^.]*\ball (?:[a-z,'-]+ ){0,4}?lands\b", re.I),
}
VARIANTS = ["destroy_all_lands", "exile_all_lands", "sacrifice_lands", "bounce_all_lands", "each_player_chooses_lands", "all_lands_verb"]


def text_hits(t):
    t = re.sub(r"\([^)]*\)", " ", t or "")          # reminder text
    return sorted(k for k in VARIANTS if PATTERNS[k].search(t))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sp = ap.Space()
    rules = ar.Rules(sp)
    L = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    rec_chunk = P["recovered"]["chunk"]
    UNC = ap.jl("unorganized_cards.json")["groups"]
    UNO = ap.jl("unorganized.json")
    gname = {g["id"]: g["name"] for g in UNO["groups"]}
    group_of = {c["c"]: int(g) for g, lst in UNC.items() for c in lst}
    AL = ap.jl("ability_ledger.json")
    cols = AL["meta"]["columns"]
    arows = collections.defaultdict(list)
    for r in AL["rows"]:
        arows[r[0]].append(dict(zip(cols, r)))
    ALSO = ap.jl("also_fits.json")["cards"]
    phr = ap.jl("leaf_phrases.json")["leaves"]
    br = ap.jl("branches.json")
    clu = ap.jl("clusters.json")

    def phrase(l):
        e = phr.get(str(l)) or {}
        return e.get("edited") or (e["phrases"][0]["phrase"] if e.get("phrases") else "") or clu["labels"].get(str(l), "")[:70]

    def branches(l):
        return (br["leaf_branches"].get(str(l)) or [])[:3]

    faces_of = collections.defaultdict(list)
    for r in sp.rows:
        faces_of[r["id"].split("/")[0]].append(r["id"])
    for fid in sorted(rec_chunk):
        faces_of[fid.split("/")[0]].append(fid)
    entry_of = lambda fid: sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]

    # ------------------------------------------------------------------ tags
    tags = json.load(io.open(TAGS, encoding="utf-8"))
    tag_cards = {t["slug"]: {x["oracle_id"] for x in t["taggings"]} for t in tags}
    in_scope = {o for o, r in L.items() if r["status"] != "out_of_scope"}
    mld = tag_cards["mass-land-denial"]
    rl = tag_cards["removal-land"]

    # ------------------------------------------------------------------ text patterns over in-scope cards
    texts = {}
    for o in sorted(in_scope):
        t = []
        for fid in faces_of.get(o, []):
            e = entry_of(fid)
            t.append(e.get("oracle_text") or "")
        texts[o] = "\n".join(t)
    thits = {o: text_hits(t) for o, t in texts.items()}
    thits = {o: h for o, h in thits.items() if h}
    cards = sorted(set(thits) | (mld & in_scope), key=lambda o: L[o]["name"])
    out = {"tag_file": TAGS, "tag_file_date": "2026-07-16", "mass_land_denial_tag_cards": len(mld),
           "mass_land_denial_in_scope": len(mld & in_scope), "removal_land_tag_cards": len(rl),
           "text_pattern_hits": len(thits), "list": len(cards),
           "text_only": sum(1 for o in cards if o in thits and o not in mld),
           "tag_only": sum(1 for o in cards if o in mld and o not in thits),
           "both": sum(1 for o in cards if o in mld and o in thits)}
    print(json.dumps(out, indent=1))

    # ------------------------------------------------------------------ per card
    per = {}
    for o in cards:
        r = L[o]
        pl = r["placement"]
        info = {"name": r["name"], "status": r["status"], "reason": r["reason"], "method": pl["method"],
                "leaf": pl.get("leaf"), "sim": pl.get("similarity"), "best_leaf": pl.get("best_leaf"),
                "group": group_of.get(o), "found_by": [k for k, v in (("text", o in thits), ("tag", o in mld)) if v],
                "text_variants": thits.get(o, []), "in_removal_land_tag": o in rl,
                "oracle": texts.get(o, "")[:1500], "abilities": [],
                "gaps": [[f[1], f[2][:80]] for f in (r["evidence"].get("fragments") or [])[:5]],
                "also_fits": [{"l": m["l"], "t": m["t"][:70]} for m in (ALSO.get(o, {}).get("m") or [])]}
        # abilities: ability ledger rows
        for a in arows.get(o, []):
            info["abilities"].append({"face": a["face"], "b": a["bucket"], "i": a["idx"], "t": a["text"][:110],
                                      "state": a["state"], "route": a["route"], "reason": a["reason"],
                                      "best_leaf": a["best_leaf"], "score": a["score"]})
        per[o] = info

    # tokens per ability (recomputed, same tokens as the clustering)
    for o, info in per.items():
        for a in info["abilities"]:
            e = entry_of(a["face"])
            its = {(b, i): t for b, i, it, t in ap.ability_items(e)}
            a["tokens"] = sorted(k for k in its.get((a["b"], a["i"]), set()) if k in sp.vocab)
            a["leaf_phrase"] = phrase(a["best_leaf"]) if a["best_leaf"] is not None else None
            a["leaf_branches"] = branches(a["best_leaf"]) if a["best_leaf"] is not None else []
            a["leaf_size"] = int(sp.leaf_size[a["best_leaf"]]) if a["best_leaf"] is not None else None
    out["per_card"] = per
    with io.open(os.path.join(BUILD, "land_denial_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return out


if __name__ == "__main__":
    main()
