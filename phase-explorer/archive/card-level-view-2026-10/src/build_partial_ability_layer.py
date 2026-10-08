#!/usr/bin/env python3
"""Ability-level placement for partial and unmodelled cards ("Parsed, but with a gap").

    python src/build_ledger.py                  # statuses
    python src/build_placements.py              # build/placements.json
    python src/build_partial_ability_layer.py   # -> build/partial_ability_layer.json
    python src/build_ability_layer.py           # ability ledger reads this layer
    python src/build_ledger.py                  # again: reads the layer (placement method `ability`)

A card the parser read all of but one clause is placed in a leaf when one of its abilities matches
that leaf closely on its own, by the SAME rule as src/build_ability_layer.py (src/ability_rules.py:
>= 0.90, a specific leaf, rules text, non-modal, not flagged, and the effect-type / wording /
structure checks), plus conditions that only matter on gap cards:

  item_gap          the ability's own item holds an Unimplemented / GenericEffect[?] / Unrecognized /
                    unknown-trigger-mode node anywhere
  same_line_gap     a gap fragment of the face sits in the same rules-text line as the ability, so the
                    ability is a partial reading of that line (the Spark Double pattern)
  continuation_gap  the face has an unread clause that begins with a continuation word (it, that, the,
                    this, ~, then, instead, otherwise, unless, choose, ...): the lost text probably
                    belongs to a neighbouring clause, so the cards are left alone entirely

The card keeps its status (`partial` / `unmodelled_node`): the gap is real parser work still owed and
stays in the gap-cause ranking. Only its placement method becomes `ability`. Its unread parts are
recorded as plain gap text for the card detail. One leaf per card; abilities in a second leaf are
`second_leaf`. Per-item reasons for the whole gap population are stored for the ability ledger.

Writes build/partial_ability_layer.json (sorted keys; identical bytes across runs). No frozen file,
centroid or clustered count changes.
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap      # noqa: E402
import ability_rules as ar      # noqa: E402
import build_ledger as BL       # noqa: E402
import build_unorganized as BU  # noqa: E402  clean_gaps only

BUILD = ap.BUILD
TEXT_LIMIT = 160
CONT = {"it", "that", "the", "this", "its", "they", "those", "~", "then", "instead", "otherwise", "unless", "if",
        "them", "he", "she", "his", "her", "their", "and", "or", "also", "except", "where", "for", "at", "x", "a", "an",
        "choose"}


def sq(s):
    return re.sub(r"[^a-z]+", "", re.sub(r"\d+", "", (s or "").lower().replace("~", "")))


def fam(kind, cat):
    if kind == "Unimplemented":
        return "Unimplemented:" + cat.split(":", 1)[1]
    return "GenericEffect[?]" if kind == "GenericEffect" else cat


def in_population(r):
    """Gap cards by pipeline stage, independent of any placement made later."""
    if r["status"] in ("partial", "unmodelled_node"):
        return True
    rec = r["evidence"].get("recovered")
    return (r["status"] == "missing_from_export" and bool(rec)
            and min((f["stage"] for f in rec["faces"]),
                    key=lambda x: BL.STAGE_ORDER.index(x) if x in BL.STAGE_ORDER else -1) == "partial")


def main():
    sp = ap.Space()
    rules = ar.Rules(sp)
    R = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    rec_chunk = P["recovered"]["chunk"]
    flagged_items = collections.defaultdict(set)
    for h in ap.jl("condition_drops.json"):
        flagged_items[h["oid"]].add((h["bucket"], h["idx"]))
    faces_of = collections.defaultdict(list)
    for r in sp.rows:
        faces_of[r["id"].split("/")[0]].append(r["id"])
    for fid in sorted(rec_chunk):
        faces_of[fid.split("/")[0]].append(fid)
    entry_of = lambda fid: sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]

    pop = sorted(o for o, r in R.items() if in_population(r))
    flat = []
    gaps_of = {}
    for oid in pop:
        gl = []
        for fid in faces_of[oid]:
            e = entry_of(fid)
            its = ap.ability_items(e)
            modal = ar.is_modal(e, its)
            lines = [sq(re.sub(r"\([^)]*\)", "", ln)) for ln in (e.get("oracle_text") or "").split("\n")]
            frags = BL.gap_fragments(e, e.get("name") or "")
            gl.extend(frags)
            fsq = [(fam(k, c), sq(t)) for k, c, t in frags]
            cont = any(f.startswith("Unimplemented:") and f.split(":", 1)[1] in CONT for f, _ in fsq)
            for b, i, it, t in its:
                gaps = BL.gap_fragments({b: [it]}, e.get("name") or "")
                flat.append({"oid": oid, "face": fid, "b": b, "i": i, "item": it, "modal": modal, "lines": lines,
                             "fsq": fsq, "cont": cont, "gaps": gaps,
                             "tk": [k for k in sorted(t) if k in sp.vocab]})
        gaps_of[oid] = BU.clean_gaps(sorted(set(gl)))
    leaves, scores = ar.score_items(sp, [x["tk"] for x in flat])
    reasons = {}
    for x, l, s in zip(flat, leaves, scores):
        x["leaf"], x["score"] = (l, s) if x["tk"] else (None, None)
        size = int(sp.leaf_size[l]) if x["tk"] else 0
        x["text"] = ar.text_of(x["item"])
        base = ar.base_class(len(x["tk"]), size, x["score"] or 0.0)
        x["ok"] = False
        if base == "no_tokens":
            r_ = "no_tokens"
        elif (x["b"], x["i"]) in flagged_items.get(x["oid"], ()):
            r_ = "flagged"
        elif x["modal"]:
            r_ = "modal"
        elif base != "specific":
            r_ = base
        elif not ar.has_text(x["text"]):
            r_ = "no_text"
        elif rules.blind_spot(x["b"], x["item"], x["tk"], x["leaf"], x["text"]):
            r_ = "token_blind_spot"
        elif x["gaps"]:
            r_ = "item_gap"
        else:
            d = sq(x["text"])
            mine = [ln for ln in x["lines"] if ln and (d[:40] in ln or ln in d)]
            if any(t and any((t[:25] in ln) or (ln[:25] in t) for ln in mine) for _, t in x["fsq"]):
                r_ = "same_line_gap"
            elif x["cont"]:
                r_ = "continuation_gap"
            else:
                r_, x["ok"] = "eligible", True
        x["reason"] = r_

    by = collections.defaultdict(list)
    for x in flat:
        by[x["oid"]].append(x)
    faces, cards = {}, {}
    for oid in pop:
        el = [x for x in by[oid] if x["ok"]]
        if not el:
            continue
        top = max(el, key=lambda x: (round(x["score"], 6), -x["leaf"], x["face"]))
        for x in el:
            x["reason"] = "placed" if (x["leaf"] == top["leaf"] and x["face"] == top["face"]) else "second_leaf"
        pl = [x for x in el if x["reason"] == "placed"]
        fid = top["face"]
        faces[fid] = {"card": oid, "method": "ability", "source": "ability", "leaf": top["leaf"],
                      "similarity": round(top["score"], 4), "n_placed": len(pl)}
        on = [x for x in by[oid] if x["face"] == fid]
        cards[oid] = {
            "face": fid,
            "placed": [{"b": x["b"], "i": x["i"], "t": x["text"][:TEXT_LIMIT], "l": x["leaf"],
                        "s": round(x["score"], 4)} for x in on if x["reason"] == "placed"],
            "rest": [{"b": x["b"], "i": x["i"], "t": x["text"][:TEXT_LIMIT], "r": x["reason"], "l": x["leaf"],
                      "s": None if x["score"] is None else round(x["score"], 4)}
                     for x in on if x["reason"] != "placed"],
            "gaps": gaps_of[oid][:6], "gaps_more": max(0, len(gaps_of[oid]) - 6)}
    rs = {"%s|%s|%d" % (x["face"], x["b"], x["i"]): x["reason"] for x in flat}
    cnt = collections.Counter(x["reason"] for x in flat)
    fam_cards = collections.Counter()
    for oid in cards:
        for g in sorted({f for x in by[oid] for f, _ in x["fsq"]}):
            fam_cards[g] += 1
    doc = {"v": 1,
           "meta": {"rule": "src/ability_rules.py + item_gap / same_line_gap / continuation_gap",
                    "population": len(pop), "cards": len(cards), "faces": len(faces),
                    "by_status": dict(sorted(collections.Counter(R[o]["status"] for o in cards).items())),
                    "items": len(flat), "item_reasons": dict(sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))),
                    "abilities_per_card": dict(sorted(collections.Counter(c["placed"].__len__() for c in cards.values()).items())),
                    "gap_families_on_placed_cards": dict(sorted(fam_cards.items(), key=lambda kv: (-kv[1], kv[0]))[:40]),
                    "continuation_words": sorted(CONT)},
           "faces": dict(sorted(faces.items())), "cards": dict(sorted(cards.items())),
           "reasons": dict(sorted(rs.items()))}
    with io.open(os.path.join(BUILD, "partial_ability_layer.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    print(json.dumps({k: v for k, v in doc["meta"].items() if k != "gap_families_on_placed_cards"}, indent=1))


if __name__ == "__main__":
    main()
