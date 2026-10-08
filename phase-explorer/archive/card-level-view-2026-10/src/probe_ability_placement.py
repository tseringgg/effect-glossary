#!/usr/bin/env python3
"""Step-1 investigation for ability-level placement. Reads only; writes
build/ability_placement_probe.json (new file) and prints the findings.

    python src/probe_ability_placement.py

Nothing is placed or changed. It answers: why does each ability of an unplaced card fail to
place, how many cards have a clearing ability held back only by a sibling, how good would a
"promotion bar" (specific leaf + no token-blind-spot wording) be on today's also-fits links,
and how big are the other candidate populations (partial / unmodelled cards, proximity cards).
"""
import collections
import io
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap  # noqa: E402

BUILD = ap.BUILD
THRESHOLD, MIN_TOKENS, MAX_LEAF, GENERIC_LEAF = 0.90, 3, 300, 500
BLIND_SHARE = 0.20          # a term in the ability must appear in >= 20% of the leaf's member cards

ZONE_TERMS = ["graveyard", "exile", "library", "battlefield", "hand"]
PLAYER_TERMS = ["opponent", "each player", "target player", "that player"]
COUNTER_RE = re.compile(r"([+-]\d+/[+-]\d+|[a-z]+) counters?\b")
COUNTER_STOP = {"a", "an", "the", "that", "those", "any", "each", "one", "more", "of", "this", "target", "no",
                "all", "other", "another", "its", "their", "your", "its", "one", "two", "three", "x", "not",
                "to", "and", "or", "you", "it", "spell", "can't", "cannot", "unless", "then", "if"}


def terms_in(text):
    """The token-blind terms an ability's text mentions: zones, player scope, counter type."""
    t = (text or "").lower()
    out = set()
    for z in ZONE_TERMS:
        if re.search(r"\b" + z, t):
            out.add("zone:" + z)
    for p in PLAYER_TERMS:
        if re.search(r"\b" + p, t):
            out.add("player:" + p)
    for m in COUNTER_RE.finditer(t):
        k = m.group(1)
        if k not in COUNTER_STOP and k != "+1/+1":
            out.add("counter:" + k)
    return out


def main():
    sp = ap.Space()
    L = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    unc = ap.jl("unorganized_cards.json")["groups"]
    also = ap.jl("also_fits.json")["cards"]
    br = ap.jl("branches.json")
    phr = ap.jl("leaf_phrases.json")["leaves"]
    rec_chunk = P["recovered"]["chunk"]
    flagged_cards, flagged_items = set(), collections.defaultdict(set)
    for h in ap.jl("condition_drops.json"):
        flagged_cards.add(h["oid"])
        flagged_items[h["oid"]].add((h["bucket"], h["idx"]))

    def entry_of(fid):
        return sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]

    def linfo(l):
        e = phr.get(str(l)) or {}
        ph = e.get("edited") or (e["phrases"][0]["phrase"] if e.get("phrases") else "")
        return {"leaf": int(l), "size": int(sp.leaf_size[l]), "phrase": ph,
                "branches": br["leaf_branches"].get(str(l)) or []}

    # ---- per-leaf share of member faces whose item texts mention a term (the blind-spot check)
    members = collections.defaultdict(list)
    for fid, l in sp.lab.items():
        if l >= 0 and fid in sp.byid:
            members[l].append(fid)
    leaf_terms = {}
    for l, mem in members.items():
        c = collections.Counter()
        for fid in mem:
            e = sp.chunks[sp.byid[fid]["ch"]][fid]
            ts = set()
            for b in ap.BUCKETS:
                for it in e.get(b) or []:
                    ts |= terms_in(it.get("description"))
            for t in ts:
                c[t] += 1
        leaf_terms[l] = {t: n / len(mem) for t, n in c.items()}

    def blind_hits(text, leaf):
        return sorted(t for t in terms_in(text) if leaf_terms.get(leaf, {}).get(t, 0.0) < BLIND_SHARE)

    def classify(tok, size, score):
        if not tok:
            return "no_tokens"
        if score < THRESHOLD:
            return "below_0.90"
        if len(tok) == 1 or size >= GENERIC_LEAF:
            return "generic"
        if len(tok) < MIN_TOKENS or size > MAX_LEAF:
            return "in_between"
        return "specific"

    out = {"definitions": {"blind_share": BLIND_SHARE, "zone_terms": ZONE_TERMS, "player_terms": PLAYER_TERMS,
                           "counter_type": "any '<type> counter' other than +1/+1"}}

    # =========================================================== Shuri
    shuri = next(o for o, r in L.items() if r["name"] == "Shuri, Wakandan Inventor")
    fid = shuri
    e = entry_of(fid)
    items = ap.ability_items(e)
    toks = [[k for k in sorted(t) if k in sp.vocab] for *_, t in items]
    leaf, sc, S = sp.score(toks)
    rows = []
    for k, (b, i, it, _) in enumerate(items):
        text = it.get("description") or ""
        kind = classify(toks[k], sp.leaf_size[int(leaf[k])] if toks[k] else 0, float(sc[k]) if toks[k] else 0)
        top = np.argsort(-S[k])[:3] if toks[k] else []
        rows.append({"bucket": b, "idx": i, "text": text, "tokens": toks[k],
                     "best": linfo(leaf[k]) if toks[k] else None, "score": round(float(sc[k]), 4),
                     "top3": [[int(sp.leaves[j]), round(float(S[k][j]), 4)] for j in top], "rule": kind,
                     "blind": blind_hits(text, int(leaf[k])) if toks[k] else []})
    out["shuri"] = {"oid": shuri, "ledger": L[shuri]["placement"], "blended_best": L[shuri]["placement"],
                    "abilities": rows, "also_fits_today": also.get(shuri)}

    # =========================================================== group 2: why each ability fails
    best = {}
    for x in P["review_queue"]:
        if x["card"] not in best or x["similarity"] > best[x["card"]]["similarity"]:
            best[x["card"]] = x
    g2 = sorted(o for o, r in L.items() if r["placement"].get("reason") == "below_similarity_floor"
                and r["status"] != "out_of_scope")
    reasons_ab = collections.Counter()
    reasons_card_any = collections.Counter()
    cards = []
    links = []                           # (oid, ability record) for the 1,473 existing also-fits
    for oid in g2:
        x = best[oid]
        e = entry_of(x["face"])
        items = ap.ability_items(e)
        modal = ap_modal = (bool(e.get("modal")) or bool(e.get("mode_abilities")) or
                            any(it.get("modal") or it.get("mode_abilities") for _, _, it, _ in items))
        toks = [[k for k in sorted(t) if k in sp.vocab] for *_, t in items]
        leaf, sc, _ = sp.score(toks)
        recs = []
        for k, (b, i, it, _) in enumerate(items):
            text = (it.get("description") or "").strip()
            l = int(leaf[k]) if toks[k] else None
            size = sp.leaf_size[l] if toks[k] else 0
            base = classify(toks[k], size, float(sc[k]) if toks[k] else 0.0)
            reason = base
            if base != "no_tokens":
                if oid in flagged_cards or (b, i) in flagged_items.get(oid, ()):
                    reason = "flagged" if base in ("specific", "generic", "in_between") or True else base
                if modal and reason not in ("flagged",):
                    reason = "modal"
            if reason == "specific" and (not text or re.fullmatch(r"Chapter \d+", text)):
                reason = "no_text"
            bl = []
            if reason == "specific":
                bl = blind_hits(text, l)
                if bl:
                    reason = "specific_but_blind_spot"
            recs.append({"b": b, "i": i, "text": text, "leaf": l, "score": float(sc[k]) if toks[k] else 0.0,
                         "ntok": len(toks[k]), "size": int(size), "reason": reason, "blind": bl, "base": base})
            reasons_ab[reason] += 1
        cards.append({"oid": oid, "blended": x["similarity"], "n": len(items), "recs": recs,
                      "flagged": oid in flagged_cards, "modal": modal})
        for r_ in recs:
            if oid in also and any(m["b"] == r_["b"] and m["i"] == r_["i"] for m in also[oid]["m"]):
                links.append((oid, r_))
    out["group2_ability_reasons"] = dict(reasons_ab.most_common())
    out["group2_ability_items"] = sum(len(c["recs"]) for c in cards)

    # cards: clearing abilities (specific, passes blind-spot), siblings
    def clear(r_, strict):
        return r_["reason"] == "specific" or (not strict and r_["reason"] == "specific_but_blind_spot")
    for strict in (False, True):
        key = "strict_no_blind_spot" if strict else "as_built_today"
        stat = collections.Counter()
        sib = collections.Counter()
        for c in cards:
            if c["blended"] < 0.50:
                stat["blended<0.50"] += 1
                continue
            clr = [r_ for r_ in c["recs"] if clear(r_, strict)]
            if not clr:
                continue
            stat["cards_with_>=1_clearing_ability"] += 1
            others = [r_ for r_ in c["recs"] if not clear(r_, strict)]
            if not others:
                stat["all_abilities_clear (nothing held back by a sibling)"] += 1
            else:
                stat["held_back_by_a_sibling"] += 1
                for r_ in others:
                    sib[r_["reason"]] += 1
                stat["...siblings_have_no_tokens_only"] += all(r_["reason"] == "no_tokens" for r_ in others)
        out["group2_clearing_" + key] = {"cards": dict(stat), "sibling_reasons_over_cards": dict(sib)}
    # all of group 2 regardless of blended band
    stat = collections.Counter()
    for c in cards:
        clr = [r_ for r_ in c["recs"] if clear(r_, False)]
        if clr:
            stat["cards_with_>=1_clearing_ability_any_band"] += 1
            if len(clr) < len(c["recs"]):
                stat["of_which_held_back_by_a_sibling_any_band"] += 1
    out["group2_clearing_any_band"] = dict(stat)
    # per-card reason of the NON-clearing siblings only (for cards with >=1 clearing ability, blended >= 0.50)
    # ---------------------------------------------------------- promotion bar on today's links
    passed = failed = 0
    failed_ex = []
    by_term = collections.Counter()
    for oid, r_ in links:
        bl = blind_hits(r_["text"], r_["leaf"])
        if bl:
            failed += 1
            for t in bl:
                by_term[t.split(":")[0]] += 1
            if len(failed_ex) < 14:
                failed_ex.append([L[oid]["name"], r_["text"][:90], r_["leaf"], bl])
        else:
            passed += 1
    out["promotion_bar_on_existing_links"] = {
        "links": len(links), "pass_no_blind_spot": passed, "fail": failed,
        "failing_term_kinds": dict(by_term), "failing_examples": failed_ex}
    # the three known misses (+ the others found by hand) against the rule
    known = [("Spitting Dilophosaurus", "put a -1/-1"), ("Bandit's Talent", "each opponent discards"),
             ("Dogged Detective", "return this card from your graveyard"),
             ("Gollum the Abandoned", "return this card from your graveyard"),
             ("Helvault", "return all cards exiled"), ("Relic of Progenitus", "exiles a card from their graveyard"),
             ("Biotransference", "you lose 1 life and create")]
    res = []
    for name, frag in known:
        oid = next((o for o, r in L.items() if r["name"] == name and r["placement"].get("reason") == "below_similarity_floor"), None)
        if oid is None:
            res.append({"card": name, "found": False})
            continue
        for oid_, r_ in links:
            if oid_ == oid and frag.lower() in r_["text"].lower():
                res.append({"card": name, "text": r_["text"][:100], "leaf": r_["leaf"], "phrase": linfo(r_["leaf"])["phrase"],
                            "blind": blind_hits(r_["text"], r_["leaf"]), "caught": bool(blind_hits(r_["text"], r_["leaf"]))})
                break
        else:
            res.append({"card": name, "in_links_today": False})
    out["known_misses_vs_rule"] = res

    # =========================================================== partial / unmodelled
    def has_gap(node):
        if isinstance(node, dict):
            if node.get("type") in ("Unimplemented", "Unrecognized"):
                return True
            return any(has_gap(v) for v in node.values())
        if isinstance(node, list):
            return any(has_gap(v) for v in node)
        return False
    pc = collections.Counter()
    for c in unc["1"]:
        oid = c["c"]
        got = got_spec = got_strict = False
        for fid in c["f"]:
            e = entry_of(fid)
            its = ap.ability_items(e)
            tk = [[k for k in sorted(t) if k in sp.vocab] for *_, t in its]
            lf, s_, _ = sp.score(tk)
            for k, (b, i, it, _) in enumerate(its):
                if not tk[k] or has_gap(it) or oid in flagged_cards or (b, i) in flagged_items.get(oid, ()):
                    continue
                if s_[k] >= THRESHOLD:
                    got = True
                    size = sp.leaf_size[int(lf[k])]
                    txt = (it.get("description") or "").strip()
                    if len(tk[k]) >= MIN_TOKENS and size <= MAX_LEAF and txt and not re.fullmatch(r"Chapter \d+", txt):
                        got_spec = True
                        if not blind_hits(txt, int(lf[k])):
                            got_strict = True
        pc["cards"] += 1
        pc["clean_unflagged_ability_>=0.90"] += got
        pc["...and specific leaf + text"] += got_spec
        pc["...and no blind-spot wording"] += got_strict
    out["partial_unmodelled"] = dict(pc)

    # =========================================================== proximity-placed cards
    prox_cards = collections.defaultdict(list)
    for fid, f in P["faces"].items():
        if f["method"] == "proximity":
            prox_cards[f["card"]].append((fid, f["leaf"]))
    qc = collections.Counter()
    for oid, fl in prox_cards.items():
        fid, placed = sorted(fl)[0]
        e = entry_of(fid)
        its = ap.ability_items(e)
        modal = (bool(e.get("modal")) or bool(e.get("mode_abilities")) or
                 any(it.get("modal") or it.get("mode_abilities") for _, _, it, _ in its))
        tk = [[k for k in sorted(t) if k in sp.vocab] for *_, t in its]
        lf, s_, _ = sp.score(tk)
        qc["cards"] += 1
        diff = [k for k in range(len(its)) if tk[k] and s_[k] >= THRESHOLD and int(lf[k]) != placed]
        if diff:
            qc["other_ability_>=0.90_in_a_different_leaf"] += 1
            sp_ok = []
            for k in diff:
                txt = (its[k][2].get("description") or "").strip()
                if (len(tk[k]) >= MIN_TOKENS and sp.leaf_size[int(lf[k])] <= MAX_LEAF and txt
                        and not re.fullmatch(r"Chapter \d+", txt) and oid not in flagged_cards and not modal):
                    sp_ok.append((k, txt))
            if sp_ok:
                qc["...specific, text, not flagged/modal"] += 1
                if any(not blind_hits(t, int(lf[k])) for k, t in sp_ok):
                    qc["...and no blind-spot wording"] += 1
        # ability that matches the PLACED leaf at all?
        if any(tk[k] and s_[k] >= THRESHOLD and int(lf[k]) == placed for k in range(len(its))):
            qc["has_an_ability_>=0.90_in_the_placed_leaf"] += 1
    out["proximity_cards"] = dict(qc)

    with io.open(os.path.join(BUILD, "ability_placement_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
