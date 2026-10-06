#!/usr/bin/env python3
"""Ability-level placement: a card is placed in a leaf by ONE of its abilities.

    python src/build_ledger.py          # statuses
    python src/build_placements.py      # build/placements.json
    python src/build_also_fits.py       # build/also_fits.json
    python src/build_ability_layer.py   # -> build/ability_layer.json, build/ability_ledger.json
    python src/build_ledger.py          # again: reads the layer (status `placed_by_ability`)

WHY. Placement scores a card as a whole. A card with two effects, one of which matches a leaf
exactly, scores about 1/sqrt(2) = 0.71 against it, under the 0.80 floor, so the good ability was
blocked by its sibling. Here each ability is judged on its own, by the rule in src/ability_rules.py
(>= 0.90 by the clustering's own tokens / IDF / centroids, a specific leaf, rules text, not
flagged, not modal, and three independent token-blind-spot checks). A card with at least one
ability that clears it is placed in that ability's leaf. One leaf per card: the best-scoring
promoted ability's; a promoted ability in a different leaf is recorded as `second_leaf`.

SCOPE (first version). Cards in "Parsed, no close group found" (the review queue) whose blended
score is >= 0.50, on the clean faces the placement layer scored. Not in scope: partial and
unmodelled cards, proximity-placed cards, clustered cards. Nothing about them changes.

WRITES (new files only; no frozen file, no centroid, no cohesion figure, no leaf count changes)
  build/ability_layer.json    the placements: faces{face id -> {card, method:"ability", leaf, ...}}
                              and per-card detail of the abilities that were not placed
  build/ability_ledger.json   one row per ability item of every in-scope card, whatever its status:
                              placed (route, leaf) or unplaced with a reason, best leaf and score
Both are sorted and written with sorted keys: two runs give identical bytes.
"""
import collections
import io
import json
import os
import sys

HERE_SRC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE_SRC)
import ability_probe as ap      # noqa: E402
import ability_rules as ar      # noqa: E402

BUILD = ap.BUILD
MIN_BLENDED = 0.50
TEXT_LIMIT = 160
REASONS = ("no_tokens", "flagged", "modal", "below_0.90", "generic_leaf", "in_between", "no_text",
           "token_blind_spot", "second_leaf", "not_scored")


def dump(name, obj):
    with io.open(os.path.join(BUILD, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def main():
    sp = ap.Space()
    rules = ar.Rules(sp)
    R = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    also = ap.jl("also_fits.json")["cards"]
    rec_chunk = P["recovered"]["chunk"]
    flagged_cards, flagged_items = set(), collections.defaultdict(set)
    for h in ap.jl("condition_drops.json"):
        flagged_cards.add(h["oid"])
        flagged_items[h["oid"]].add((h["bucket"], h["idx"]))

    # ---- every face of every in-scope card, in a fixed order
    faces_of = collections.defaultdict(list)
    for r in sp.rows:
        faces_of[r["id"].split("/")[0]].append(r["id"])
    for fid in sorted(rec_chunk):
        faces_of[fid.split("/")[0]].append(fid)

    def entry_of(fid):
        return sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]

    # ---- the unplaced population: review-queue cards, blended >= MIN_BLENDED
    best = {}
    review_faces = collections.defaultdict(set)
    for x in P["review_queue"]:
        review_faces[x["card"]].add(x["face"])
        if x["card"] not in best or x["similarity"] > best[x["card"]]["similarity"]:
            best[x["card"]] = x
    pop = sorted(o for o in best
                 if R[o]["status"] != "out_of_scope"
                 and R[o]["placement"]["method"] in ("unplaced", "ability"))
    assert len(pop) == 4175, len(pop)
    in_band = [o for o in pop if best[o]["similarity"] >= MIN_BLENDED]

    # ---- score every ability of every in-scope face once
    flat = []          # (oid, fid, bucket, idx, item, tokens, modal)
    for oid in sorted(faces_of):
        r = R.get(oid)
        if r is None or r["status"] == "out_of_scope":
            continue
        for fid in faces_of[oid]:
            e = entry_of(fid)
            its = ap.ability_items(e)
            modal = ar.is_modal(e, its)
            for b, i, it, t in its:
                flat.append((oid, fid, b, i, it, [k for k in sorted(t) if k in sp.vocab], modal))
    leaves, scores = ar.score_items(sp, [f[5] for f in flat])
    rec = []
    for (oid, fid, b, i, it, tk, modal), l, s in zip(flat, leaves, scores):
        rec.append({"oid": oid, "face": fid, "b": b, "i": i, "item": it, "tk": tk, "modal": modal,
                    "leaf": l if tk else None, "score": s if tk else None,
                    "size": int(sp.leaf_size[l]) if tk else 0, "text": ar.text_of(it)})

    # ---- promotion, per ability
    promo_pool = set(in_band)
    by_card = collections.defaultdict(list)
    for x in rec:
        by_card[x["oid"]].append(x)
    stats = collections.Counter()
    for oid in sorted(by_card):
        cand_faces = review_faces.get(oid, set())
        for x in by_card[oid]:
            x["reason"], x["detail"], x["ok"] = "not_scored", None, False
            if oid not in promo_pool or x["face"] not in cand_faces:
                continue
            base = ar.base_class(len(x["tk"]), x["size"], x["score"] or 0.0)
            if base == "no_tokens":
                x["reason"] = "no_tokens"
            elif oid in flagged_cards or (x["b"], x["i"]) in flagged_items.get(oid, ()):
                x["reason"] = "flagged"
            elif x["modal"]:
                x["reason"] = "modal"
            elif base != "specific":
                x["reason"] = base
            elif not ar.has_text(x["text"]):
                x["reason"] = "no_text"
            else:
                why = rules.blind_spot(x["b"], x["item"], x["tk"], x["leaf"], x["text"])
                if why:
                    x["reason"], x["detail"] = "token_blind_spot", why
                else:
                    x["reason"], x["ok"] = "eligible", True

    placed_cards = {}      # oid -> (leaf, face, score)
    for oid in in_band:
        el = [x for x in by_card[oid] if x["ok"]]
        if not el:
            continue
        top = max(el, key=lambda x: (round(x["score"], 6), -x["leaf"], x["face"]))
        placed_cards[oid] = top["leaf"]
        for x in el:
            if x["leaf"] == top["leaf"]:
                x["reason"] = "placed"
            else:
                x["reason"] = "second_leaf"

    # ---- the layer file
    faces, cards = {}, {}
    for oid, leaf in sorted(placed_cards.items()):
        mine = by_card[oid]
        pl = [x for x in mine if x["reason"] == "placed"]
        top = max(pl, key=lambda x: (round(x["score"], 6), x["face"]))
        fid = top["face"]
        faces[fid] = {"card": oid, "method": "ability", "source": "ability", "leaf": leaf,
                      "similarity": round(top["score"], 4), "n_placed": len(pl)}
        on_face = [x for x in mine if x["face"] == fid]
        placed_keys = {(x["b"], x["i"]) for x in pl if x["face"] == fid}
        a = also.get(oid)
        cards[oid] = {
            "face": fid,
            "placed": [{"b": x["b"], "i": x["i"], "t": x["text"][:TEXT_LIMIT], "l": x["leaf"],
                        "s": round(x["score"], 4)} for x in on_face if (x["b"], x["i"]) in placed_keys],
            "rest": [{"b": x["b"], "i": x["i"], "t": x["text"][:TEXT_LIMIT], "r": x["reason"],
                      "l": x["leaf"], "s": None if x["score"] is None else round(x["score"], 4)}
                     for x in on_face if (x["b"], x["i"]) not in placed_keys],
            "also": [m for m in (a["m"] if a and a["f"] == fid else []) if (m["b"], m["i"]) not in placed_keys],
        }
    cnt = collections.Counter()
    for x in rec:
        if x["oid"] in placed_cards:
            cnt[x["reason"]] += 1
    layer = {"v": 1,
             "meta": {"rule": "src/ability_rules.py", "min_blended": MIN_BLENDED,
                      "threshold": ar.THRESHOLD, "min_tokens": ar.MIN_TOKENS, "max_leaf_cards": ar.MAX_LEAF,
                      "excluded_effect_types": sorted(ar.EXCLUDED_TYPES),
                      "population": len(pop), "in_band": len(in_band), "cards": len(placed_cards),
                      "faces": len(faces),
                      "abilities_on_promoted_cards": dict(sorted(cnt.items()))},
             "faces": dict(sorted(faces.items())), "cards": dict(sorted(cards.items()))}
    dump("ability_layer.json", layer)

    # ---- the ability ledger
    pl_faces = P["faces"]
    card_rows = {}
    rows_out = []
    state_n = collections.Counter()
    by_route = collections.Counter()
    unplaced_reason = collections.Counter()
    own_n = collections.Counter()
    for x in rec:                       # rec is already in (oid, face order, bucket order, idx) order
        oid = x["oid"]
        r = R[oid]
        if oid not in card_rows:
            if oid in placed_cards:
                st, method, cleaf = "placed_by_ability", "ability", placed_cards[oid]
            else:
                st, method = r["status"], r["placement"]["method"]
                cleaf = r["placement"].get("leaf")
                if method == "ability" or st == "placed_by_ability":      # previous run's annotation
                    st, method, cleaf = r["evidence"].get("pipeline_status", st), "unplaced", None
            card_rows[oid] = [r["name"], st, method, cleaf]
        st, method, cleaf = card_rows[oid][1:]
        if method == "ability":
            if x["reason"] == "placed":
                state, route, leaf, reason = "placed", "ability", x["leaf"], None
            else:
                state, route, leaf, reason = "unplaced", None, None, x["reason"]
        elif method in ("clustered", "proximity"):
            state, route, leaf, reason = "placed", method, cleaf, None
        else:
            state, route, leaf, reason = "unplaced", None, None, x["reason"]
        if reason == "eligible":
            reason = "not_scored"
        own = None
        if x["leaf"] is not None and method in ("clustered", "proximity", "ability") and leaf is not None:
            own = x["leaf"] == leaf
        state_n[state] += 1
        if state == "placed":
            by_route[route] += 1
            own_n[(route, own)] += 1
        else:
            unplaced_reason[reason] += 1
        rows_out.append([oid, x["face"], x["b"], x["i"], x["text"][:TEXT_LIMIT], state, route, leaf, reason,
                         x["detail"], x["leaf"], None if x["score"] is None else round(x["score"], 4), own])
    n_cards_scope = len(card_rows)
    cards_with_items = len(card_rows)
    led = {"v": 1,
           "meta": {"columns": ["card", "face", "bucket", "idx", "text", "state", "route", "leaf", "reason",
                                "detail", "best_leaf", "score", "own_leaf_is_best"],
                    "rows": len(rows_out), "cards_with_ability_items": cards_with_items,
                    "placed": state_n["placed"], "unplaced": state_n["unplaced"],
                    "placed_by_route": dict(sorted(by_route.items())),
                    "unplaced_by_reason": dict(sorted(unplaced_reason.items(), key=lambda kv: (-kv[1], kv[0]))),
                    "own_leaf_is_best_by_route": {"%s:%s" % (k[0], k[1]): v for k, v in sorted(
                        own_n.items(), key=lambda kv: (kv[0][0], str(kv[0][1])))},
                    "reasons": list(REASONS), "scope": "ability_layer: review-queue cards with blended >= %.2f"
                                                     % MIN_BLENDED},
           "cards": dict(sorted(card_rows.items())), "rows": rows_out}
    dump("ability_ledger.json", led)

    print(json.dumps({"population": len(pop), "in_band": len(in_band), "promoted_cards": len(placed_cards),
                      "faces": len(faces), "layer_abilities": layer["meta"]["abilities_on_promoted_cards"],
                      "ledger_rows": len(rows_out), "placed": state_n["placed"], "unplaced": state_n["unplaced"],
                      "by_route": led["meta"]["placed_by_route"],
                      "unplaced_by_reason": led["meta"]["unplaced_by_reason"]}, indent=1))


if __name__ == "__main__":
    main()
