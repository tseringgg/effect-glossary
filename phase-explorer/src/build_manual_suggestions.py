#!/usr/bin/env python3
"""Suggestions for the hand-placement panel. NEW FILE ONLY: build/manual_suggestions.json. Suggestions are labelled suggestions on the page; nothing is ever placed from them.

    python src/build_manual_suggestions.py     # about a minute (re-runs the taxonomy in memory, as build_tentative.py does); run build_manual_layer.py first

Three sources, merged by group id, top 5 kept per not-yet-organized card (the 5,593 'u' cards):
  sig    nearest leaf by signature: for each usable ability of the card (held abilities included), each leaf with the same family and effect type scores
         (2 + shared fields) / (2 + fields in either), best ability per leaf; capped at 0.50 when nothing beyond family and effect type matches
  tag    the card's Scryfall community tags (the tag layer's own filter): a leaf scores the F1 of (share of the tag's placed cards that sit in the leaf, share of the leaf that has the tag),
         needing >= 3 placed cards and F1 >= 0.10; a tag group that exists for one of the card's tags scores 0.50
  loose  the card's own loose / tentative groups, 0.35 flat
Merge: the highest source score plus 0.10 per additional agreeing source (cap 1.0); ranked by score, number of sources, layer (leaf, tentative, loose, tag), smaller group, id.
"""
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as M

HERE = M.HERE
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(BUILD, "manual_suggestions.json")
TOP = 5
CANON = ["sign", "recip", "frm", "to", "ctr", "who", "mods", "obj", "ctrl", "quant", "props", "kw", "dur", "cond", "wrap", "chain", "tok"]
LAYER_ORDER = {"leaf": 0, "tent": 1, "loose": 2, "tag": 3, "hand": 4}
LOOSE_SCORE, TAGGROUP_SCORE, NOFIELD_CAP, TAG_MIN_N, TAG_MIN_F1, AGREE_BONUS = 0.35, 0.50, 0.50, 3, 0.10, 0.10


def jl(n):
    with io.open(os.path.join(BUILD, n), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    import build_manual_layer as BML
    if not BML.MANUAL_PLACEMENTS:
        if os.path.exists(OUT):
            os.remove(OUT)
        print("MANUAL_PLACEMENTS is off: nothing written")
        return
    import build_loose_groups as BL
    import tag_layer_filter as F
    import probe_tags as PT
    argv, sys.argv = sys.argv, sys.argv[:1]              # build_ability_taxonomy.main() parses sys.argv
    try:
        items, _meta = BL.collect()[0], None
    finally:
        sys.argv = argv
    idx = jl("manual_index.json")
    G = idx["groups"]
    tax, mem = jl("ability_taxonomy.json"), jl("ability_taxonomy_members.json")["leaves"]
    tent, loose, tags = jl("tentative_placements.json"), jl("loose_groups.json"), jl("tag_placements.json")
    leaf_tok = {}
    for lid, l in tax["leaves"].items():
        d = dict(p.split("=", 1) for p in l["sig"].split(" · "))
        leaf_tok[lid] = (d.get("fam"), d.get("ftype"), {"%s=%s" % (k, v) for k, v in d.items() if k not in ("fam", "ftype") and v not in ("", "-")})
    by_ft = collections.defaultdict(list)
    for lid in sorted(leaf_tok):
        by_ft[(leaf_tok[lid][0], leaf_tok[lid][1])].append(lid)
    ab = collections.defaultdict(list)
    for it in items:
        if it["f"]["usable"]:
            ab[it["oid"]].append(it)
    new = PT.load(PT.NEW)
    fn = F.functional(new)
    ct = F.card_tags(fn)
    placed = collections.defaultdict(set)
    for lid, ms in mem.items():
        for m in ms:
            placed[lid].add(m[0])
    n_t, n_tl = collections.Counter(), collections.defaultdict(collections.Counter)
    for lid, cs in placed.items():
        for o in cs:
            for t in ct.get(o, ()):
                n_tl[t][lid] += 1
    allp = set().union(*placed.values())
    for o in allp:
        for t in ct.get(o, ()):
            n_t[t] += 1
    import build_hand_groups as BHG
    hits = {}
    hp = os.path.join(BUILD, "hand_group_hits.json")
    if BHG.HAND_GROUPS and os.path.exists(hp):                    # hand-defined group rules: suggestions only, scored by the rule's own confidence
        for slug, g in jl("hand_group_hits.json")["groups"].items():
            if g["retired"]:
                continue
            conf = {r["id"]: r["confidence"] for r in g["rules"]}
            for oid, hs in g["hits"].items():
                best = max(hs, key=lambda h: conf[h[0]])
                hits.setdefault(oid, []).append(("hand:" + slug, conf[best[0]], "your hand-defined group “%s” (rule %s) matches: “%s”" % (g["name"], best[0], best[1][:120])))
    out, sources = {}, collections.Counter()
    for oid, c in sorted(idx["cards"].items()):
        if c[1] not in ("u", "t", "a", "m"):
            continue
        cand = {}

        def add(gid, sc, why, src):
            g = G.get(gid)
            if g is None or not g[4]:
                return
            e = cand.setdefault(gid, {"s": {}, "w": {}})
            if sc > e["s"].get(src, 0):
                e["s"][src], e["w"][src] = sc, why
        for it in ab.get(oid, ()):
            f = it["f"]
            at = {"%s=%s" % (k, f[k]) for k in CANON if f.get(k) not in ("", "-", None)}
            for lid in by_ft.get((f["fam"], f["ftype"]), ()):
                lt = leaf_tok[lid][2]
                inter = len(at & lt)
                sc = (2 + inter) / float(2 + len(at | lt))
                if inter == 0:
                    sc = min(sc, NOFIELD_CAP)
                txt = " ".join((it["text"] or "(no separate rules line)").split())[:100]
                miss = sorted(lt - at)[:2]
                add("leaf:" + lid, sc, "ability “%s” shares %d of the group's %d signature fields%s" % (txt, inter, len(lt), (" (not matched: " + ", ".join(miss) + ")") if miss else ""), "sig")
        for t in sorted(ct.get(oid, ())):
            slug = fn[t]["slug"]
            for lid in sorted(n_tl.get(t, ())):
                n = n_tl[t][lid]
                if n < TAG_MIN_N:
                    continue
                p, q = n / float(n_t[t]), n / float(len(placed[lid]))
                f1 = 2 * p * q / (p + q)
                if f1 >= TAG_MIN_F1:
                    add("leaf:" + lid, f1, "community tag “%s”: %d of the group's %d cards carry it" % (slug, n, len(placed[lid])), "tag")
            if t in tags["groups"]:
                add("tag:" + t, TAGGROUP_SCORE, "the card carries the community tag “%s”, which has a group" % slug, "tag")
        for gid in sorted(loose["by_card"].get(oid, ())):
            add(("tent:" if gid in tent["groups"] else "loose:") + gid, LOOSE_SCORE, "the card is already shown in this loose group (not checked)", "loose")
        for gid, sc_, why_ in hits.get(oid, ()):
            add(gid, sc_, why_, "rule")
        rows = []
        for gid, e in cand.items():
            sc = min(1.0, max(e["s"].values()) + AGREE_BONUS * (len(e["s"]) - 1))
            rows.append((-round(sc, 3), -len(e["s"]), LAYER_ORDER[G[gid][3]], G[gid][1], gid, e))
        rows.sort(key=lambda r: r[:5])
        if rows:
            out[oid] = [[r[4], -r[0], "+".join(sorted(r[5]["s"])), "; ".join(r[5]["w"][s] for s in sorted(r[5]["w"]))] for r in rows[:TOP]]
            for r in rows[:TOP]:
                for s in r[5]["s"]:
                    sources[s] += 1
    doc = {"v": 1, "top": TOP, "rules": {"loose": LOOSE_SCORE, "tag_group": TAGGROUP_SCORE, "no_field_cap": NOFIELD_CAP, "tag_min_placed": TAG_MIN_N, "tag_min_f1": TAG_MIN_F1, "agree_bonus": AGREE_BONUS},
           "label": "Suggestion, not a placement", "cards": out}
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    import build_manual_layer as BML
    fb_path = os.path.join(BUILD, "manual_fallback.json")
    if not BML.BATCH_ACTIONS:
        if os.path.exists(fb_path):
            os.remove(fb_path)
    else:
        write_fallback(fb_path, idx, G, out, n_tl, n_t, placed, ct, fn, tag_names_ok=True)
    n_u = sum(1 for c in idx["cards"].values() if c[1] == "u")
    print("cards with suggestions %d of %d eligible (%d not-yet-organized pile cards: %d with a suggestion)" % (len(out), sum(1 for c in idx["cards"].values() if c[1] in ("u", "t", "a", "m")),
                                                                                                 n_u, sum(1 for o in out if idx["cards"][o][1] == "u")), dict(sources))


FALLBACK_LABEL = "Low confidence: this card has no suggestion. These are possible homes found from its keyword, a community tag or words in its text; never pre-ticked."
STOP = set("the a an of to and or you your that this it is in on for with target each any as at if then from by be can't".split())


def _words(t):
    import re
    return {w for w in re.findall(r"[a-z]+", (t or "").lower()) if w not in STOP and len(w) > 2}


def write_fallback(path, idx, G, out, n_tl, n_t, placed, ct, fn, tag_names_ok=True):
    """build/manual_fallback.json: for each pile card with no suggestion, up to 5 possible homes, in this order: the keyword block named after a keyword the card carries (exact), a weak community-tag
    leaf (F1 >= 0.02, at least 2 placed cards), then name-word overlap (at least 2 words and half of the group's name words). Deterministic; labelled low confidence; used only by the batch view."""
    cards = jl("ability_taxonomy_cards.json")["cards"]
    kfp = os.path.join(BUILD, "keyword_facet.json")
    kw_of = collections.defaultdict(list)
    if os.path.exists(kfp):
        for k, v in jl("keyword_facet.json")["keywords"].items():
            for o in v["c"]:
                kw_of[o].append(k)
    norm = lambda x: "".join(ch for ch in x.lower() if ch.isalnum())
    kwg = {norm(g[3:].replace("+", "")): g for g, v in G.items() if v[3] == "kw" and v[4]}
    gw = {g: _words(v[0]) for g, v in G.items() if v[4] and v[3] in ("leaf", "tent", "loose", "tag", "kw", "rp")}
    res = {}
    for oid in sorted(idx["cards"]):
        c = idx["cards"][oid]
        if c[1] != "u" or oid in out:
            continue
        cand, seen = [], set()

        def add(gid, kind, why):
            if gid in G and G[gid][4] and gid not in seen and len(cand) < 5:
                seen.add(gid)
                cand.append([gid, kind, why])
        for k in sorted(kw_of.get(oid, ())):
            g = kwg.get(norm(k))
            if g:
                add(g, "keyword", "the card carries the keyword %s (keyword block, exact name)" % k)
        weak = {}
        for t in sorted(ct.get(oid, ())):
            for lid in sorted(n_tl.get(t, ())):
                n = n_tl[t][lid]
                if n < 2:
                    continue
                p_, q_ = n / float(n_t[t]), n / float(len(placed[lid]))
                f1 = 2 * p_ * q_ / (p_ + q_)
                if f1 >= 0.02 and f1 > weak.get(lid, (0,))[0]:
                    weak[lid] = (f1, "weakly: community tag “%s”, %d of the group's %d cards carry it" % (fn[t]["slug"], n, len(placed[lid])))
        for lid, (f1, why) in sorted(weak.items(), key=lambda x: (-x[1][0], x[0]))[:2]:
            add("leaf:" + lid, "tag", why)
        tw = _words(cards[oid]["t"])
        lex = sorted(((len(tw & w) / float(len(w)), len(tw & w), g) for g, w in gw.items() if w and len(tw & w) >= 2 and len(tw & w) / float(len(w)) >= 0.5), key=lambda x: (-x[0], -x[1], x[2]))[:3]
        for j, n, g in lex:
            add(g, "words", "%d of the %d words of the group's name appear in the card's text" % (n, len(gw[g])))
        res[oid] = cand
    doc = {"v": 1, "label": FALLBACK_LABEL, "cards": res}
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    print("fallback: %d pile cards without a suggestion; %d have at least one possible home" % (len(res), sum(1 for v in res.values() if v)))


if __name__ == "__main__":
    main()
