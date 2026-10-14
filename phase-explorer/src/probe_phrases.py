#!/usr/bin/env python3
"""Probe (read-only): would a cheap, targeted phrase supplement place more of the remaining cards? Investigation only: builds nothing, places nothing, changes nothing.

    python src/probe_phrases.py          # Part A -> build/phrase_probe.json (+ build/phrase_probe_cards.json)

STOP RULE, set before any result was looked at: if the top 30 phrase families (ranked by cards covered) would place fewer than about 150 cards (the estimate defined below), the supplement is not worth
building, and the report says so plainly with the number.

Population: the 1,231 cards of "Parsed, but with a gap" that have no readable ability (the cards with no loose group and an unread fragment). A fragment is the clause text of an Unimplemented node,
an unknown trigger mode or an unrecognized condition (build_ledger.gap_fragments). Normalization: card name to ~, numbers and number words to N, runs of mana symbols to {M}, counter names to <ctr>.
Families = identical normalized fragments. A family has a CLEAN SIBLING when the same normalized phrase occurs inside the description of an ability that parsed cleanly on a card with no gap anywhere.
Estimate of cards placed per family (an estimate, not a placement): a card counts only if the family's clause is its only unread clause, no ability of the card is held for a dropped condition, and the
family has a clean sibling whose ability sits in an unflagged leaf of 5 or more (or a broad leaf): the sibling's placement is the proxy for where the new item would land. Cumulative curves take the
union of cards, so families that share cards are not added twice. Matches to a promotable tentative group are not estimated (the sibling is a placed card, so it has no loose group): that part is left out.
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ledger as BLD
import probe_remaining as PR

HERE = PR.HERE
BUILD = PR.BUILD
NUMW = r"\b(two|three|four|five|six|seven|eight|nine|ten|twice|thrice)\b"
CTR_STOP = {"a", "an", "the", "each", "any", "that", "those", "of", "more", "additional", "another", "one", "its", "this", "these", "loyalty", "n", "or", "and", "no", "all", "target", "on", "x", "your", "their", "other", "such", "same", "kind", "kinds", "type", "types", "named", "chosen", "number"}


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def norm2(t):
    t = t.replace('"', "").replace("—", "-")
    t = re.sub(r"(\{[wubrgcxp0-9/]+\})+", "{M}", t)
    t = re.sub(NUMW, "N", t)

    def ctr(m):
        w = m.group(1)
        return m.group(0) if w in CTR_STOP or "/" in w or "+" in w or "-" in w else "<ctr> counter" + m.group(2)
    t = re.sub(r"\b([a-z][a-z\-]*) counter(s?)\b", ctr, t)
    return re.sub(r"\s+", " ", t).strip(" .,;:")


def chain_of(f):
    return f["ftype"] + (">" + f["chain"] if f["chain"] else "")


def main():
    items, raw, info, meta, S = PR.collect()
    A, L, leaf_info = S["A"], S["L"], S["leaf_info"]
    T = jl("ability_taxonomy.json")
    unorg = jl("ability_taxonomy_unorganized.json")["groups"]
    ur = jl("loose_unread.json")
    r1 = {r[0] for r in ur["rows"] if r[2] == 1}
    frag = {}
    for g in unorg:
        for c in g["list"]:
            if c["c"] in r1:
                frag[c["c"]] = c.get("g") or []
    names = meta["names"]
    flagged_oids = {it["oid"] for it in items if it["src"] == "flagged"}
    out = {"stop_rule": "if the top 30 families (by cards covered) would place fewer than about 150 cards, the supplement is not worth building", "population": len(r1)}
    # ---- fragments, families
    per_card = {}
    for o in r1:
        per_card[o] = sorted({(k, norm2(t)) for k, t in frag.get(o, [])})
    n_frag = collections.Counter(min(len(v), 3) for v in per_card.values())
    out["unread_clauses_per_card"] = {"0 (no fragment recorded)": n_frag[0], "1": n_frag[1], "2": n_frag[2], "3 or more": n_frag[3]}
    out["distinct_clauses_per_card_detail"] = dict(collections.Counter(len(v) for v in per_card.values()))
    fam_cards = collections.defaultdict(set)
    fam_sole = collections.defaultdict(set)
    raw_variants = collections.defaultdict(collections.Counter)
    for o, v in per_card.items():
        for k, p in v:
            fam_cards[(k, p)].add(o)
            if len(v) == 1:
                fam_sole[(k, p)].add(o)
    for o in r1:
        for k, t in frag.get(o, []):
            raw_variants[(k, norm2(t))][t] += 1
    fams = sorted(fam_cards, key=lambda f: (-len(fam_cards[f]), f))
    out["families"] = len(fams)
    out["families_by_kind"] = dict(collections.Counter(f[0] for f in fams))
    out["cards_with_at_least_one_fragment"] = len(per_card) - n_frag[0]
    # ---- clean siblings: index of normalized descriptions of clean abilities
    clean = []
    for j, a in enumerate(A):
        if a["kind"] != "clean" or a["pre"] or not (a["text"] or "").strip():
            continue
        t = norm2(BLD.norm_fragment(a["text"], L[a["oid"]]["name"]))
        clean.append((j, t))
    TOP = len(fams)
    KEEP = 100
    rows = []
    placed_by_family = {}
    for rank, fam in enumerate(fams[:TOP], 1):
        k, p = fam
        # a phrase of fewer than 3 words or 14 characters ("you", "phase", "otherwise") matches everywhere and means nothing: no sibling is sought for it
        if len(p.split()) < 3 or len(p) < 14:
            sib = []
        else:
            pat = re.compile(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])")
            sib = [(j, t) for j, t in clean if p in t and pat.search(t)]
        exact = [j for j, t in sib if t == p]
        outcome, leaf_name, chain, template = "no clean sibling", "", "", "none"
        pick = None
        if sib:
            pick = (exact or [j for j, _ in sib])
            # prefer a sibling that sits in a leaf
            best = None
            for j in pick[:200]:
                st = A[j]["state"]
                if st in ("placed", "placed_broad"):
                    best = j
                    break
            if best is None:
                best = pick[0]
            a = A[best]
            st = a["state"]
            outcome = {"placed": "unflagged leaf", "placed_broad": "broad leaf"}.get(st, "no leaf of 5 (" + (a["reason"] or st) + ")")
            leaf_name = T["leaves"].get(a["leaf"], {}).get("name", "") if a.get("leaf") else ""
            chain = chain_of(a["f"])
            template = "whole ability" if exact else "part of a longer ability"
        cards = fam_cards[fam]
        sole = fam_sole[fam]
        ok_cards = {o for o in sole if o not in flagged_oids}
        placed = ok_cards if outcome in ("unflagged leaf", "broad leaf") else set()
        placed_by_family[fam] = placed
        rows.append({"rank": rank, "kind": k, "phrase": p, "cards": len(cards), "sole_cause": len(sole), "sole_and_unflagged": len(ok_cards), "siblings": len(sib), "exact_whole_ability_siblings": len(exact),
                     "template": template, "sibling_chain": chain, "sibling_outcome": outcome, "sibling_leaf": leaf_name, "estimated_cards_placed": len(placed), "example_cards": sorted(names[o] for o in list(cards)[:4])})
    out["all_families_estimated_cards_placed_ceiling"] = len(set().union(*[placed_by_family[f] for f in fams]))
    out["all_families_with_a_clean_sibling"] = sum(1 for r in rows if r["siblings"])
    rows = rows[:KEEP]
    out["top_families"] = rows
    out["top50_with_a_clean_sibling"] = {"families": sum(1 for r in rows[:50] if r["siblings"]), "cards": len(set().union(*[fam_cards[f] for f in fams[:50] if rows[fams.index(f)]["siblings"]] or [set()])),
                                         "families_with_no_clean_parse_anywhere": sum(1 for r in rows[:50] if not r["siblings"]),
                                         "cards_in_those": len(set().union(*[fam_cards[f] for f in fams[:50] if not rows[fams.index(f)]["siblings"]] or [set()])),
                                         "whole_ability_template": sum(1 for r in rows[:50] if r["template"] == "whole ability"), "part_of_longer_ability": sum(1 for r in rows[:50] if r["template"] == "part of a longer ability")}
    out["top50_cards_covered"] = len(set().union(*[fam_cards[f] for f in fams[:50]]))
    curve = {}
    for n in (10, 25, 30, 50, 100):
        cs = set().union(*[placed_by_family[f] for f in fams[:n]])
        cov = set().union(*[fam_cards[f] for f in fams[:n]])
        curve[str(n)] = {"cards_covered_by_these_families": len(cov), "estimated_cards_placed": len(cs)}
    out["cumulative_curve_by_cards_covered"] = curve
    # the same curve when families are ordered by their own estimate (the best case for the same number of families)
    by_est = sorted(fams, key=lambda f: (-len(placed_by_family[f]), f))
    curve2 = {}
    for n in (10, 25, 30, 50, 100):
        curve2[str(n)] = len(set().union(*[placed_by_family[f] for f in by_est[:n]]))
    out["cumulative_curve_best_ordering_of_the_top_100"] = curve2
    out["stop_rule_result"] = {"top_30_estimated_cards": curve["30"]["estimated_cards_placed"], "threshold": 150, "worth_building": curve["30"]["estimated_cards_placed"] >= 150}
    # kinds of the clause among the estimate
    with io.open(os.path.join(BUILD, "phrase_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    cards_out = {"families": [{"kind": f[0], "phrase": f[1], "cards": sorted(fam_cards[f]), "sole": sorted(fam_sole[f]), "placed_estimate": sorted(placed_by_family.get(f, []))} for f in fams[:KEEP]],
                 "flagged_cards": sorted(flagged_oids & r1), "raw_examples": {"%s|%s" % f: raw_variants[f].most_common(2) for f in fams[:KEEP]}}
    with io.open(os.path.join(BUILD, "phrase_probe_cards.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(cards_out, ensure_ascii=False, separators=(",", ":")))
    show = {k: out[k] for k in ("population", "unread_clauses_per_card", "distinct_clauses_per_card_detail", "families", "families_by_kind", "cards_with_at_least_one_fragment", "top50_with_a_clean_sibling", "top50_cards_covered",
                                "cumulative_curve_by_cards_covered", "cumulative_curve_best_ordering_of_the_top_100", "stop_rule_result")}
    print(json.dumps(show, indent=1, ensure_ascii=False))
    for r in rows[:50]:
        print("%2d %-7s %3d sole=%-3d ok=%-3d sib=%-4d %-16s %-30s -> est %-3d | %s" % (r["rank"], r["kind"], r["cards"], r["sole_cause"], r["sole_and_unflagged"], r["siblings"], r["template"][:16], r["sibling_outcome"][:30], r["estimated_cards_placed"], r["phrase"][:80].encode("ascii", "replace").decode()))


if __name__ == "__main__":
    main()
