#!/usr/bin/env python3
"""Run the per-ability probe (investigation only). Writes build/ability_probe.json.

    python src/run_ability_probe.py

See ability_probe.py for what is being measured and why nothing here changes anything.
"""
import collections
import io
import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap  # noqa: E402

BUILD, HERE = ap.BUILD, ap.HERE
THRESH = (0.90, 0.80, 0.70)
BANDS = [("0.70-0.80", 0.70, 2.0), ("0.50-0.70", 0.50, 0.70), ("<0.50", -1.0, 0.50)]
SEED = 20261006


def pct(a, qs=(0, 5, 10, 25, 50, 75, 90, 95, 100)):
    a = np.asarray(a, dtype=float)
    return {str(q): round(float(np.percentile(a, q)), 4) for q in qs} if len(a) else {}


def hist(a, lo=0.0, hi=1.0, bins=10):
    h, _ = np.histogram(np.asarray(a, dtype=float), bins=bins, range=(lo, hi))
    return [int(x) for x in h]


def has_gap_node(node):
    if isinstance(node, dict):
        if node.get("type") in ("Unimplemented", "Unrecognized"):
            return True
        return any(has_gap_node(v) for v in node.values())
    if isinstance(node, list):
        return any(has_gap_node(v) for v in node)
    return False


def main():
    sp_ = ap.Space()
    ledger = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    unc = ap.jl("unorganized_cards.json")["groups"]
    br = ap.jl("branches.json")
    phr = ap.jl("leaf_phrases.json")["leaves"]
    flagged_items = collections.defaultdict(set)      # oid -> {(bucket, idx)}
    for h in ap.jl("condition_drops.json"):
        flagged_items[h["oid"]].add((h["bucket"], h["idx"]))
    rec_chunk = P["recovered"]["chunk"]

    def entry_of(fid):
        if fid in sp_.byid:
            return sp_.chunks[sp_.byid[fid]["ch"]][fid]
        return rec_chunk[fid]

    def leaf_info(l):
        e = phr.get(str(l)) or {}
        ph = e.get("edited") or (e["phrases"][0]["phrase"] if e.get("phrases") else "")
        return {"leaf": int(l), "size": int(sp_.leaf_size[l]),
                "label": (sp_.clusters["labels"].get(str(l)) or "")[:90], "phrase": ph,
                "branches": br["leaf_branches"].get(str(l)) or []}

    out = {"seed": SEED}

    # ======================================================= abilities of clustered faces
    cl_faces = [i for i in sp_.order if sp_.lab[i] >= 0]
    recs = []          # one per ability item: (face, bucket, idx, tokens, in-vocab tokens)
    face_items = {}
    mism_union = 0
    for fid in cl_faces:
        e = sp_.chunks[sp_.byid[fid]["ch"]][fid]
        items = ap.ability_items(e)
        face_items[fid] = items
        u = set()
        for _, _, _, t in items:
            u |= t
        if u != set(sp_.feats[fid]):
            mism_union += 1
        for b, i, it, t in items:
            recs.append((fid, b, i, t))
    n_items = len(recs)
    tok_lists = [sorted(t) for *_, t in recs]
    in_vocab = [[k for k in t if k in sp_.vocab] for t in tok_lists]
    bearing = np.array([bool(v) for v in in_vocab])
    notok = [r for r, v, t in zip(recs, in_vocab, tok_lists) if not v]
    out["token_scheme_check"] = {"clustered_faces": len(cl_faces), "faces_where_union_of_items != card_features": mism_union}
    out["items_clustered"] = {
        "ability_items": n_items, "with_no_tokens": int((~bearing).sum()),
        "with_no_tokens_by_bucket": dict(collections.Counter(r[1] for r, b in zip(recs, bearing) if not b)),
        "by_bucket": dict(collections.Counter(r[1] for r in recs)),
        "tokens_all_outside_vocab": sum(1 for t, v in zip(tok_lists, in_vocab) if t and not v)}

    best_leaf_all, best_sc_all, S_all = sp_.score(in_vocab)
    best_sc_all = np.where(bearing, best_sc_all, 0.0)

    # ======================================================= STEP 2: validation on clustered faces
    face_pos = collections.defaultdict(list)
    for k, r in enumerate(recs):
        face_pos[r[0]].append(k)
    blended_own, best_ab_own, any90, n_bear_face = [], [], 0, collections.Counter()
    per_face = {}
    Xrow = {fid: k for k, fid in enumerate(sp_.order)}
    SB = np.asarray(sp_.X @ sp_.C.T)
    for fid in cl_faces:
        ks = [k for k in face_pos[fid] if bearing[k]]
        if not ks:
            continue
        j = sp_.leaf_index[sp_.lab[fid]]
        own = [float(S_all[k, j]) for k in ks]
        bl = float(SB[Xrow[fid], j])
        per_face[fid] = (own, bl)
        n_bear_face[min(len(ks), 3)] += 1
    for fid, (own, bl) in per_face.items():
        best_ab_own.append(max(own))
        blended_own.append(bl)
    best_ab_own = np.array(best_ab_own)
    blended_own = np.array(blended_own)
    multi = [fid for fid, (own, bl) in per_face.items() if len(own) >= 2]
    single = [fid for fid, (own, bl) in per_face.items() if len(own) == 1]
    out["validation_clustered"] = {
        "faces_scored": len(per_face), "by_n_bearing_abilities": dict(n_bear_face),
        "best_ability_vs_own_leaf": {"percentiles": pct(best_ab_own), "hist10": hist(best_ab_own),
                                     "ge_0.90": int((best_ab_own >= 0.90).sum()),
                                     "ge_0.80": int((best_ab_own >= 0.80).sum()),
                                     "ge_0.70": int((best_ab_own >= 0.70).sum())},
        "blended_vs_own_leaf": {"percentiles": pct(blended_own), "hist10": hist(blended_own),
                                "ge_0.90": int((blended_own >= 0.90).sum()),
                                "ge_0.80": int((blended_own >= 0.80).sum()),
                                "ge_0.70": int((blended_own >= 0.70).sum())},
        "multi_ability_faces": len(multi),
        "multi_best_ability_vs_own": {"percentiles": pct([max(per_face[f][0]) for f in multi]),
                                      "ge_0.90": sum(1 for f in multi if max(per_face[f][0]) >= 0.90)},
        "multi_blended_vs_own": {"percentiles": pct([per_face[f][1] for f in multi]),
                                 "ge_0.90": sum(1 for f in multi if per_face[f][1] >= 0.90)},
        "multi_ability_best_exceeds_blended": sum(1 for f in multi if max(per_face[f][0]) > per_face[f][1] + 1e-6),
    }
    # exactness: faces with exactly ONE token-bearing item: item vector == card vector, scores identical
    exact_checked = exact_bad = 0
    exact_total_single = 0
    for fid in single:
        ks = [k for k in face_pos[fid] if bearing[k]]
        k = ks[0]
        Y = sp_.weigh(sp_.encode([in_vocab[k]]))
        a, b = Y.tocsr(), sp_.X[Xrow[fid]].tocsr()
        same_vec = (a.shape == b.shape and (a != b).nnz == 0)
        s_item = np.asarray(Y @ sp_.C.T).ravel()
        s_card = np.asarray(sp_.X[Xrow[fid]] @ sp_.C.T).ravel()
        exact_checked += 1
        if not (same_vec and np.array_equal(s_item, s_card) and np.array_equal(S_all[k], s_item)):
            exact_bad += 1
        if len(face_pos[fid]) == 1:
            exact_total_single += 1
    out["validation_clustered"]["single_ability_exactness"] = {
        "faces_with_exactly_one_token_bearing_item": exact_checked,
        "of_which_exactly_one_item_at_all": exact_total_single,
        "vector_or_score_not_bit_identical": exact_bad}

    # ======================================================= STEP 3/4: group 2 (no close group found)
    g2 = [o for o, r in ledger.items() if r["placement"].get("reason") == "below_similarity_floor"
          and r["status"] != "out_of_scope"]
    best_item = {}
    for x in P["review_queue"]:
        c = x["card"]
        if c in set(g2) and (c not in best_item or x["similarity"] > best_item[c]["similarity"]):
            best_item[c] = x
    assert len(best_item) == len(g2) == 4175, (len(best_item), len(g2))
    cards2 = []
    mism_blend = 0
    flat_tokens = []
    flat_meta = []
    for oid in sorted(g2):
        x = best_item[oid]
        fid = x["face"]
        e = entry_of(fid)
        feats = cs.card_features(e) if False else ap.cs.card_features(e)
        bl_leaf, bl_sc, _ = sp_.score([sorted(feats)])
        if bl_leaf[0] != x["best_leaf"] or abs(round(float(bl_sc[0]), 4) - x["similarity"]) > 1e-4:
            mism_blend += 1
        items = ap.ability_items(e)
        meta = {"oid": oid, "face": fid, "name": ledger[oid]["name"], "blended": x["similarity"],
                "blended_leaf": x["best_leaf"], "n_items": len(items), "first": len(flat_tokens),
                "layer": ledger[oid]["evidence"].get("layer") or ("recovered" if ledger[oid]["evidence"].get("recovered") else "snapshot"),
                "flagged": bool(flagged_items.get(oid)), "status": ledger[oid]["status"]}
        for b, i, it, t in items:
            flat_tokens.append([k for k in sorted(t) if k in sp_.vocab])
            flat_meta.append((oid, b, i, (it.get("description") or "")[:160], sorted(t)))
        meta["last"] = len(flat_tokens)
        cards2.append(meta)
    bl2, bs2, S2 = sp_.score(flat_tokens)
    bear2 = np.array([bool(t) for t in flat_tokens])
    bs2 = np.where(bear2, bs2, 0.0)
    out["group2_blend_reproduction"] = {"cards": len(cards2), "blended_leaf_or_score_mismatch": mism_blend}
    out["items_group2"] = {"ability_items": len(flat_tokens), "with_no_tokens": int((~bear2).sum())}

    def card_abilities(m):
        ks = [k for k in range(m["first"], m["last"]) if bear2[k]]
        return ks

    for m in cards2:
        ks = card_abilities(m)
        m["n_bearing"] = len(ks)
        m["ab_scores"] = [round(float(bs2[k]), 4) for k in ks]
        m["ab_leaves"] = [int(bl2[k]) for k in ks]
        kbest = max(ks, key=lambda k: bs2[k]) if ks else None
        m["best_ab"] = round(float(bs2[kbest]), 4) if ks else 0.0
        m["best_ab_leaf"] = int(bl2[kbest]) if ks else None
        m["same_leaf"] = bool(ks) and m["best_ab_leaf"] == m["blended_leaf"]
        m["ab_k"] = ks
    sel_flag = lambda m: m["flagged"]

    def band_stats(sel):
        o = {"cards": len(sel)}
        if not sel:
            return o
        o["one_bearing_ability"] = sum(1 for m in sel if m["n_bearing"] == 1)
        o["two_or_more_bearing"] = sum(1 for m in sel if m["n_bearing"] >= 2)
        o["abilities_without_tokens_on_these_cards"] = sum(m["n_items"] - m["n_bearing"] for m in sel)
        for T in THRESH:
            any_ = [m for m in sel if m["best_ab"] >= T]
            multi_ = [m for m in sel if m["n_bearing"] >= 2]
            o[f"rescued_any_ge_{T:.2f}"] = len(any_)
            o[f"rescued_any_ge_{T:.2f}_multi_ability_only"] = sum(1 for m in multi_ if m["best_ab"] >= T)
            o[f"rescued_any_ge_{T:.2f}_same_leaf"] = sum(1 for m in any_ if m["same_leaf"])
            o[f"rescued_any_ge_{T:.2f}_different_leaf"] = sum(1 for m in any_ if not m["same_leaf"])
            o[f"all_abilities_ge_{T:.2f}_multi"] = sum(1 for m in multi_ if min(m["ab_scores"]) >= T)
            o[f"all_abilities_ge_{T:.2f}_multi_and_same_leaf"] = sum(
                1 for m in multi_ if min(m["ab_scores"]) >= T and all(l == m["blended_leaf"] for l in m["ab_leaves"]))
        o["best_ability_percentiles"] = pct([m["best_ab"] for m in sel])
        o["best_ability_hist10"] = hist([m["best_ab"] for m in sel])
        o["blended_percentiles"] = pct([m["blended"] for m in sel])
        o["best_ability_gain_over_blended_percentiles"] = pct([m["best_ab"] - m["blended"] for m in sel])
        return o

    out["group2"] = {"all": band_stats(cards2)}
    out["group2_by_band"] = {}
    for name, lo, hi in BANDS:
        sel = [m for m in cards2 if lo <= m["blended"] < hi]
        out["group2_by_band"][name] = band_stats(sel)
    # quality split: fully clean (no detector-flagged item) vs clean-but-flagged
    out["group2_by_quality"] = {
        "clean_unflagged": band_stats([m for m in cards2 if not m["flagged"]]),
        "clean_but_condition_drop_flagged": band_stats([m for m in cards2 if m["flagged"]])}
    out["group2_band_by_quality"] = {}
    for name, lo, hi in BANDS:
        for tag, pred in (("clean_unflagged", lambda m: not m["flagged"]), ("flagged", lambda m: m["flagged"])):
            sel = [m for m in cards2 if lo <= m["blended"] < hi and pred(m)]
            st = band_stats(sel)
            out["group2_band_by_quality"][f"{name}|{tag}"] = {k: v for k, v in st.items() if "percentiles" not in k and "hist" not in k}

    # ---- the "exactly the 1/sqrt(2)" mechanism, checked directly: two bearing abilities, one score ~1?
    two = [m for m in cards2 if m["n_bearing"] == 2]
    out["group2_two_ability_cards"] = {
        "cards": len(two),
        "one_ability_ge_0.90": sum(1 for m in two if m["best_ab"] >= 0.90),
        "blended_in_0.70_0.72_of_those": sum(1 for m in two if m["best_ab"] >= 0.90 and 0.70 <= m["blended"] < 0.72)}

    # ======================================================= rescue by LEAF characteristics (step 6 support)
    big = [l for l, _ in sp_.leaf_size.most_common(20)]
    resc = [(m, k) for m in cards2 for k in m["ab_k"] if bs2[k] >= 0.90]
    top_df = set(np.argsort(-sp_.df)[:15].tolist())

    def generic_tokens(toks):
        return all(sp_.vocab[t] in top_df for t in toks)
    out["rescues_ge_0.90"] = {
        "abilities": len(resc), "cards": len({m["oid"] for m, k in resc}),
        "in_20_largest_leaves": sum(1 for m, k in resc if int(bl2[k]) in big),
        "single_token_abilities": sum(1 for m, k in resc if len(flat_tokens[k]) == 1),
        "only_top15_df_tokens": sum(1 for m, k in resc if generic_tokens(flat_tokens[k])),
        "leaf_size_percentiles": pct([sp_.leaf_size[int(bl2[k])] for m, k in resc]),
        "ability_token_count": dict(collections.Counter(min(len(flat_tokens[k]), 4) for m, k in resc)),
        "top_leaves": [[int(l), n] for l, n in collections.Counter(int(bl2[k]) for m, k in resc).most_common(10)]}
    out["largest_leaves"] = [{**leaf_info(l), "n": n} for l, n in sp_.leaf_size.most_common(10)]

    # ---- false-rescue sample (30 abilities clearing 0.90, one per card, seeded)
    rng = random.Random(SEED)
    pool = sorted({m["oid"]: (m, k) for m, k in resc}.items())
    sample = rng.sample(pool, 30)
    members_by_leaf = collections.defaultdict(list)
    for fid in cl_faces:
        members_by_leaf[sp_.lab[fid]].append(fid)
    samp = []
    for oid, (m, k) in sample:
        l = int(bl2[k])
        toks = flat_tokens[k]
        mem = members_by_leaf[l]
        cov = sum(1 for f in mem if all(t in sp_.feats[f] for t in toks)) / len(mem)
        cj = sp_.leaf_index[l]
        topc = np.argsort(-sp_.C[cj])[:5]
        ex = []
        for f in sorted(mem, key=lambda f: sp_.clusters["names"][f])[:3]:
            e = entry_of(f)
            first = next(((it.get("description") or "")[:110] for b in ap.BUCKETS for it in (e.get(b) or [])), "")
            ex.append([sp_.clusters["names"][f], first])
        samp.append({"card": m["name"], "oid": oid, "blended": m["blended"], "ability": flat_meta[k][3],
                     "bucket": flat_meta[k][1], "tokens": flat_meta[k][4], "score": round(float(bs2[k]), 4),
                     "leaf": leaf_info(l), "members_with_all_tokens": round(cov, 3),
                     "centroid_top": [[sp_.inv_vocab[int(t)], round(float(sp_.C[cj][t]), 3), int(sp_.df[t])] for t in topc],
                     "member_examples": ex, "other_abilities": [flat_meta[x][3][:90] for x in m["ab_k"] if x != k]})
    out["false_rescue_sample"] = samp

    # ======================================================= STEP 7 extra: partial / unmodelled cards
    g1 = unc["1"]
    toks1, meta1 = [], []
    cards1 = []
    for c in g1:
        first = len(toks1)
        for fid in c["f"]:
            e = entry_of(fid)
            for b, i, it, t in ap.ability_items(e):
                if has_gap_node(it):
                    continue
                v = [k for k in sorted(t) if k in sp_.vocab]
                toks1.append(v)
                meta1.append((c["c"], fid, b, i))
        cards1.append((c, first, len(toks1)))
    l1, s1, _ = sp_.score(toks1)
    b1 = np.array([bool(t) for t in toks1])
    s1 = np.where(b1, s1, 0.0)
    q1 = {"cards": len(cards1), "cards_with_a_gap_free_token_bearing_ability": 0}
    for T in THRESH:
        q1[f"cards_with_a_gap_free_ability_ge_{T:.2f}"] = 0
    for c, a, b in cards1:
        ks = [k for k in range(a, b) if b1[k]]
        if ks:
            q1["cards_with_a_gap_free_token_bearing_ability"] += 1
            best = max(float(s1[k]) for k in ks)
            for T in THRESH:
                if best >= T:
                    q1[f"cards_with_a_gap_free_ability_ge_{T:.2f}"] += 1
    out["partial_unmodelled_extra"] = q1

    # ======================================================= keep per-card records (compact)
    out["group2_cards"] = [{k: m[k] for k in ("oid", "name", "blended", "blended_leaf", "n_items", "n_bearing",
                                              "ab_scores", "ab_leaves", "best_ab", "best_ab_leaf", "same_leaf",
                                              "flagged", "layer", "status")} for m in cards2]
    with io.open(os.path.join(BUILD, "ability_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    # ---- named-card probe support (printed; the report generator re-reads these)
    return out, sp_, ledger, entry_of, leaf_info, flat_tokens


if __name__ == "__main__":
    o, *_ = main()
    skip = ("group2_cards", "false_rescue_sample", "largest_leaves")
    print(json.dumps({k: v for k, v in o.items() if k not in skip}, indent=1, ensure_ascii=False))
