#!/usr/bin/env python3
"""Probe (read-only): what is left in "Not yet organized" after the tentative layer, why, and what each lever would move. Builds nothing, places nothing, changes nothing.

    python src/probe_remaining.py            # measure -> build/remaining_breakdown.json (+ blind files for the hand reads)
    python src/probe_remaining.py reveal     # after build/remaining_reads.json exists -> adds the reads to build/remaining_breakdown.json

Seed 20261023, declared before any computation, draws the 10 sample cards per reason and the 8 members read in each catch-all sub-heading; the 10 typing-check members use the same generator, in that order.
Fixed order of primary reasons (a card has one primary reason; any others are recorded):
  1 no readable ability (no loose group at all)
  2 dropped-condition hold: no eligible ability, and at least one ability held for a possible dropped condition
  3 gap-test hold: no eligible ability, none held for a dropped condition (abilities that fail a gap-card test or have no text)
  4 catch-all: an eligible ability sits in a catch-all group or a "Less common effects" bucket
  5 held group: an eligible ability sits in a plain loose group that was not promoted
  6 other
Eligible = not held for a dropped condition, has ability text, not a gap-test failure (the tentative layer's own rule). Abilities with an unread part stay eligible.
"""
import collections
import io
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ability_taxonomy as B
import build_loose_groups as BL
import build_tentative as BT
import analyze_unorganized_breakdown_v3 as V3
import probe_loose_groups_v2 as V

HERE = BL.HERE
BUILD = BL.BUILD
SEED = 20261023
REASONS = ["1 no readable ability", "2 dropped-condition hold", "3 gap-test hold", "4 only in a catch-all or less-common bucket", "5 only in a held group", "6 other"]


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def collect():
    orig = B.main
    holder = {}

    def wrap(*a, **k):
        r = orig(*a, **k)
        holder["S"] = r
        return r
    B.main = wrap
    try:
        items, raw, info, meta = BL.collect()
    finally:
        B.main = orig
    return items, raw, info, meta, holder["S"]


def tag_of(it):
    if it["src"] == "flagged":
        return "D"
    if not BT.has_text(it):
        return "T"
    if it["src"] == "test_fail":
        return "G"
    return "E"


def main():
    rnd = random.Random(SEED)
    items, raw, info, meta, S = collect()
    A, view, rows, L, leaf_info, cards = S["A"], S["view"], S["rows"], S["L"], S["leaf_info"], S["cards"]
    fam_keys = {k for k, _ in meta["families"]}
    use_idx, keys, folded, fm, names, sizes, kind_of = BL.make_groups(items, raw, info, fam_keys)
    review = jl("../corrections/tentative_groups.json")["groups"] if False else json.load(io.open(os.path.join(HERE, "corrections", "tentative_groups.json"), encoding="utf-8"))["groups"]
    cand = {}
    for k in folded:
        if kind_of(k) == "group":
            nf, kept = k[3]
            cand[BL.gid_of(k)] = {"key": k, "n": fm[k], "residual": kept < nf, "name": names[k]}
    ev = BT.evaluate(cand, items, review, BT.HOLD_LOOSE_RESIDUALS, BT.HOLD_GAP_TEST_FAILURES)
    promoted = {g for g, (el, why) in ev.items() if el}
    why_held = {g: why for g, (el, why) in ev.items() if not el}
    T = jl("tentative_placements.json")
    tent = set(T["by_card"])
    loose = jl("loose_groups.json")
    unread = jl("loose_unread.json")
    unread_set = {r[0] for r in unread["rows"]}
    pile = list(meta["pile"])
    pset = set(pile)
    out = {"seed": SEED}
    # ---------------------------------------------------------------- 1. recount
    tcalc = set()
    for g in promoted:
        tcalc |= ev[g][0]
    assert tcalc == tent, (len(tcalc), len(tent))
    remaining = sorted(pset - tent)
    rset = set(remaining)
    vc = collections.Counter(v[0] for v in view.values())
    placed_total = vc["placed"] + vc["broad_only"] + vc["keyword_block"] + vc["no_abilities"] + vc["replacement_group"]
    tot = S["tax"]["totals"]
    out["recount"] = {"pile_in_build": len(pile), "tentative": len(tent), "remaining": len(remaining), "placed": placed_total, "not_cards": vc["not_a_card"],
                      "reconciles": placed_total + len(tent) + len(remaining) + vc["not_a_card"] == len(view) == 38921,
                      "headline": tot["headline"], "with_broad": tot["with_broad"], "with_tentative": T["meta"]["headline"]["with_tentative"],
                      "no_loose_group": len(rset & unread_set), "loose_group_not_promoted": len(rset - unread_set)}
    # ---------------------------------------------------------------- 2. abilities, groups, primary reason
    ab_by_card = collections.defaultdict(list)
    for n in use_idx:
        if items[n]["oid"] in rset:
            ab_by_card[items[n]["oid"]].append(n)
    ab_groups = collections.defaultdict(list)
    for k in folded:
        gid = BL.gid_of(k)
        kd = kind_of(k)
        for n in fm[k]:
            ab_groups[n].append((gid, kd))
    primary, allr, detail = {}, {}, {}
    for o in remaining:
        ns = ab_by_card.get(o, [])
        rs = []
        if not ns:
            rs.append(1)
            detail[o] = {}
        else:
            tags = [tag_of(items[n]) for n in ns]
            c = collections.Counter(tags)
            has_e = c["E"] > 0
            if not has_e:
                rs.append(2 if c["D"] else 3)
            else:
                kinds = set()
                for n in ns:
                    if tag_of(items[n]) == "E":
                        for gid, kd in ab_groups[n]:
                            kinds.add("C" if kd != "group" else "H")
                if "C" in kinds:
                    rs.append(4)
                if "H" in kinds:
                    rs.append(5)
                if not kinds:
                    rs.append(6)
            if c["D"] and 2 not in rs:
                rs.append(2)
            if (c["G"] or c["T"]) and 3 not in rs:
                rs.append(3)
            detail[o] = dict(c)
        rs = sorted(set(rs), key=lambda r: r)
        primary[o] = rs[0]
        allr[o] = rs
    pc = collections.Counter(primary.values())
    out["primary_reason_counts"] = {REASONS[r - 1]: pc[r] for r in sorted(pc)}
    anyc = collections.Counter(r for rs in allr.values() for r in rs)
    out["cards_with_each_reason_at_all"] = {REASONS[r - 1]: anyc[r] for r in sorted(anyc)}
    out["cards_with_more_than_one_reason"] = sum(1 for rs in allr.values() if len(rs) > 1)
    pair = collections.Counter()
    for rs in allr.values():
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                pair["%d+%d" % (rs[i], rs[j])] += 1
    out["reason_overlap_pairs"] = dict(pair)
    out["reason_combinations"] = dict(collections.Counter("+".join(map(str, rs)) for rs in allr.values()).most_common())
    # ---------------------------------------------------------------- R1 detail: the cards with no readable ability
    unorg = jl("ability_taxonomy_unorganized.json")["groups"]
    cause_name = {g["id"]: g["name"] for g in unorg}
    pile_group, frag = {}, {}
    for g in unorg:
        for c in g["list"]:
            pile_group[c["c"]] = g["id"]
            if c.get("g"):
                frag[c["c"]] = c["g"]
    r1 = [o for o in remaining if primary[o] == 1]
    kinds_by_card = {o: sorted({x[0] for x in frag.get(o, [])}) for o in r1}
    out["r1"] = {"cards": len(r1), "by_pile_group": dict(collections.Counter(cause_name[pile_group[o]] for o in r1)),
                 "gap_cards_by_fragment_kinds": dict(collections.Counter("+".join(kinds_by_card[o]) or "(none)" for o in r1 if pile_group[o] == 1))}
    cnt, sole = collections.defaultdict(set), collections.defaultdict(set)

    def nrm(t):
        return re.sub(r"\d+", "N", " ".join(t.split()))[:70]
    for o in r1:
        fr = {(k, nrm(t)) for k, t in frag.get(o, [])}
        for f_ in fr:
            cnt[f_].add(o)
        if len(fr) == 1:
            sole[next(iter(fr))].add(o)
    top = sorted(cnt.items(), key=lambda kv: -len(kv[1]))[:10]
    out["r1"]["top_fragments"] = [{"kind": k[0], "fragment": k[1], "cards": len(v), "sole_cause_cards": len(sole.get(k, ()))} for k, v in top]
    fam_cards = collections.defaultdict(set)
    for o in r1:
        for k, t in frag.get(o, []):
            fam_cards[V3.frag_family(k, t)].add(o)
    ranked = sorted(fam_cards.items(), key=lambda kv: -len(kv[1]))
    covered, nfam = set(), 0
    cover = {}
    for fk, v in ranked:
        covered |= v
        nfam += 1
        for pct in (50, 80, 90):
            if pct not in cover and len(covered) >= pct / 100.0 * sum(1 for o in r1 if o in frag):
                cover[pct] = nfam
    out["r1"]["gap_cards_with_a_fragment"] = sum(1 for o in r1 if o in frag)
    out["r1"]["distinct_fragments"] = len(cnt)
    out["r1"]["distinct_fragment_families"] = len(fam_cards)
    out["r1"]["families_needed_to_cover_percent_of_gap_cards"] = cover
    out["r1"]["top_families"] = [{"family": list(fk), "cards": len(v)} for fk, v in ranked[:10]]
    # ---------------------------------------------------------------- R2: dropped-condition holds, by sub-shape
    cd = {(h["oid"], h["bucket"], h["idx"]): h for h in jl("condition_drops.json")}
    ref = [j for j, a in enumerate(A) if a["kind"] == "clean" and not a["pre"]]
    Fref = [A[j]["f"] for j in ref]
    flagged = [n for n in range(len(items)) if items[n]["src"] == "flagged" and items[n]["oid"] in rset]
    usable_fl = [n for n in flagged if items[n]["f"]["usable"] and items[n]["f"]["fam"] in fam_keys]
    r5 = dict(zip(usable_fl, B.assign_rf_ref(Fref, [items[n]["f"] for n in usable_fl], 5))) if usable_fl else {}

    def leaf_class(r):
        if r[0] == "x":
            return "unplaced"
        li = leaf_info.get(tuple(r))
        if li is None or li["n"] < 5:
            return "unplaced"
        return "broad" if li["flags"] else "placed"
    in_use = set(use_idx)
    shape_stats = collections.defaultdict(lambda: {"cards": set(), "abilities": 0, "to_leaf": 0, "to_broad_leaf": 0, "to_promoted_group": 0, "to_neither": 0, "unusable": 0,
                                                    "cards_to_leaf": set(), "cards_to_broad": set(), "cards_to_tentative": set()})
    for n in flagged:
        it = items[n]
        h = cd.get((it["oid"], it["ref"][1], it["ref"][2]))
        shape = (h["shape"] if h else "(not in the detector file)")
        st = shape_stats[shape]
        st["cards"].add(it["oid"])
        st["abilities"] += 1
        if n not in r5:
            st["unusable"] += 1
            continue
        lc = leaf_class(r5[n])
        pg = n in in_use and any(gid in promoted for gid, kd in ab_groups.get(n, []))
        if lc == "placed":
            st["to_leaf"] += 1
            st["cards_to_leaf"].add(it["oid"])
        elif lc == "broad":
            st["to_broad_leaf"] += 1
            st["cards_to_broad"].add(it["oid"])
        elif pg:
            st["to_promoted_group"] += 1
            st["cards_to_tentative"].add(it["oid"])
        else:
            st["to_neither"] += 1
    out["r2"] = {"cards_with_a_flagged_ability": len({items[n]["oid"] for n in flagged}), "flagged_abilities": len(flagged),
                 "primary_r2_cards": sum(1 for o in remaining if primary[o] == 2),
                 "by_shape": {k: {"cards": len(v["cards"]), "abilities": v["abilities"], "abilities_to_unflagged_leaf": v["to_leaf"], "abilities_to_broad_leaf": v["to_broad_leaf"],
                                  "abilities_to_promoted_group": v["to_promoted_group"], "abilities_to_neither": v["to_neither"], "unusable_for_matching": v["unusable"],
                                  "cards_gaining_a_precise_placement": len(v["cards_to_leaf"]), "cards_gaining_broad_only": len(v["cards_to_broad"] - v["cards_to_leaf"]),
                                  "cards_gaining_tentative_only": len(v["cards_to_tentative"] - v["cards_to_leaf"] - v["cards_to_broad"])} for k, v in sorted(shape_stats.items(), key=lambda kv: -len(kv[1]["cards"]))}}
    allleaf, allbroad, alltent = set(), set(), set()
    for v in shape_stats.values():
        allleaf |= v["cards_to_leaf"]
        allbroad |= v["cards_to_broad"]
        alltent |= v["cards_to_tentative"]
    out["r2"]["if_every_sub_shape_were_fixed"] = {"cards_gaining_a_precise_placement": len(allleaf), "cards_gaining_broad_only": len(allbroad - allleaf),
                                                  "cards_gaining_tentative_only": len(alltent - allleaf - allbroad), "any_of_these": len(allleaf | allbroad | alltent)}
    prim2 = [o for o in remaining if primary[o] == 2]
    out["r2"]["primary_r2_cards_that_would_gain_something"] = len(set(prim2) & (allleaf | allbroad | alltent))
    # ---------------------------------------------------------------- R3: gap-test holds
    g3 = collections.Counter()
    for o in remaining:
        if primary[o] == 3:
            ns = ab_by_card[o]
            rs = {items[n]["reason"] if tag_of(items[n]) == "G" else "no ability text" for n in ns if tag_of(items[n]) in ("G", "T")}
            g3["+".join(sorted(rs))] += 1
    out["r3"] = {"cards": pc[3], "by_blocker": dict(g3)}
    # ---------------------------------------------------------------- R4: catch-all groups and bucket sub-headings
    rank = BL.popularity()
    subs_info = []
    for k in folded:
        kd = kind_of(k)
        if kd == "group":
            continue
        gid = BL.gid_of(k)
        lab = {}
        for n in fm[k]:
            if k[2] == "OTHER":
                lab[n] = V.effect_word(items[n]["f"]["ftype"])
            else:
                v = V.field_values(items[n]["f"], n, info, raw)
                if k[1] == "Destroy":
                    lab[n] = v["objc2"] or "something"
                else:
                    g = v["grant"]
                    lab[n] = V.CONT_WORDS.get(g, ("gives " + V.KWFIX.get(g.replace("keyword ", ""), g.replace("keyword ", ""))) if g.startswith("keyword") else (g or "affects it"))
        cnt_ = collections.defaultdict(set)
        for n, l in lab.items():
            cnt_[l].add(items[n]["oid"])
        small = {l for l, c in cnt_.items() if len(c) < BL.SUB_MIN}
        for n in lab:
            if lab[n] in small:
                lab[n] = "Other kinds"
        by = collections.defaultdict(list)
        for n, l in lab.items():
            by[l].append(n)
        for l, ns in by.items():
            allc = {items[n]["oid"] for n in ns}
            el = {items[n]["oid"] for n in ns if BT.eligible(items[n], True)}
            wt = {items[n]["oid"] for n in ns if BT.has_text(items[n])}
            tl = len(allc) - len(allc & wt)
            subs_info.append({"gid": gid, "group": names[k], "kind": kd, "sub": l, "cards": len(allc), "eligible_cards": len(el), "textless_cards": tl,
                              "remaining_cards_that_would_move": len(el & rset), "_n": ns})
    out["r4"] = {"cards_with_reason_4": anyc[4], "primary": pc[4], "sub_headings": len(subs_info),
                 "sub_headings_with_5_or_more_eligible_cards": sum(1 for s in subs_info if s["eligible_cards"] >= 5)}
    cands = sorted([s for s in subs_info if s["eligible_cards"] >= 5 and s["sub"] != "Other kinds"], key=lambda s: (s["gid"], s["sub"]))
    blind, key = [], []
    for i, s in enumerate(cands, 1):
        ns = [n for n in s["_n"] if BT.eligible(items[n], True)]
        ns.sort(key=lambda n: (items[n]["oid"], items[n]["text"]))
        rnd.shuffle(ns)
        seen, pick = set(), []
        for n in ns:
            if items[n]["oid"] in seen:
                continue
            seen.add(items[n]["oid"])
            pick.append(n)
            if len(pick) == 8:
                break
        blind.append({"n": i, "members": [" ".join(items[n]["text"].split())[:150] for n in pick]})
        key.append({"n": i, "gid": s["gid"], "group": s["group"], "sub": s["sub"], "cards": s["cards"], "eligible_cards": s["eligible_cards"], "textless_cards": s["textless_cards"],
                    "remaining_cards_that_would_move": s["remaining_cards_that_would_move"], "read_cards": len(pick)})
    out["r4"]["sub_headings_not_read_because_under_5_eligible_cards_or_Other_kinds"] = len(subs_info) - len(cands)
    out["r4"]["under_5_eligible_remaining_cards"] = len({o for s in subs_info if s["eligible_cards"] < 5 or s["sub"] == "Other kinds" for n in s["_n"] if BT.eligible(items[n], True) for o in [items[n]["oid"]] if o in rset})
    # ---------------------------------------------------------------- R5: held groups
    held = []
    for gid, why in sorted(why_held.items(), key=lambda kv: kv[0]):
        c = cand[gid]
        ns = c["n"]
        allc = {items[n]["oid"] for n in ns}
        el = {items[n]["oid"] for n in ns if BT.eligible(items[n], True)}
        rv = review.get(gid, {})
        tags = collections.Counter(tag_of(items[n]) for n in ns)
        held.append({"gid": gid, "name": c["name"], "why": why, "cards": len(allc), "eligible_cards": len(el), "remaining_eligible_cards": len(el & rset), "abilities_by_tag": dict(tags),
                     "read": rv.get("verdict"), "name_ok": rv.get("key_states_effect"), "residual": c["residual"], "note": rv.get("note", "")})
    out["r5"] = {"cards_with_reason_5": anyc[5], "primary": pc[5], "held_groups": len(held), "held": held}
    # ---------------------------------------------------------------- 4. popularity
    pop = {}
    for r in sorted(set(primary.values())):
        os_ = [o for o in remaining if primary[o] == r]
        pop[REASONS[r - 1]] = {"cards": len(os_), "no_rank": sum(1 for o in os_ if o not in rank), "top1000": sum(1 for o in os_ if rank.get(o, 10 ** 9) <= 1000),
                               "top3000": sum(1 for o in os_ if rank.get(o, 10 ** 9) <= 3000), "top10000": sum(1 for o in os_ if rank.get(o, 10 ** 9) <= 10000)}
    pop["all remaining"] = {"cards": len(remaining), "no_rank": sum(1 for o in remaining if o not in rank), "top1000": sum(1 for o in remaining if rank.get(o, 10 ** 9) <= 1000),
                            "top3000": sum(1 for o in remaining if rank.get(o, 10 ** 9) <= 3000), "top10000": sum(1 for o in remaining if rank.get(o, 10 ** 9) <= 10000)}
    out["popularity"] = pop
    # ---------------------------------------------------------------- samples (10 per primary reason)
    samples = {}
    for r in sorted(pc):
        pool = [o for o in remaining if primary[o] == r]
        pick = rnd.sample(pool, min(10, len(pool)))
        rowsx = []
        for o in pick:
            ns = ab_by_card.get(o, [])
            if r == 1:
                fr = frag.get(o, [])
                rowsx.append({"card": meta["names"][o], "ability_text": (cards[o]["t"] if o in cards else "")[:200].replace("\n", " / "), "blocking": cause_name[pile_group[o]] + ("; not understood: " + "; ".join("%s: %s" % (k, t) for k, t in fr[:2]) if fr else "")})
                continue
            if r in (2, 3):
                n = next((n for n in ns if tag_of(items[n]) in (("D",) if r == 2 else ("G", "T"))), ns[0])
                it = items[n]
                h = cd.get((it["oid"], it["ref"][1], it["ref"][2]))
                bl = ("held for a possible dropped condition (%s)" % (h["shape"] if h else "?")) if tag_of(it) == "D" else ("gap-card test failed: " + it["reason"] if tag_of(it) == "G" else "no ability text")
            else:
                n = next(n for n in ns if tag_of(items[n]) == "E")
                it = items[n]
                gs = [(gid, kd) for gid, kd in ab_groups[n]]
                gid, kd = gs[0]
                bl = ("in the catch-all / bucket '%s'" % [names[k] for k in folded if BL.gid_of(k) == gid][0].split(" › ", 1)[1]) if kd != "group" else ("in the held group '%s': %s" % ([names[k] for k in folded if BL.gid_of(k) == gid][0].split(" › ", 1)[1], why_held.get(gid, "?")))
            rowsx.append({"card": meta["names"][o], "ability_text": " ".join(it["text"].split())[:200], "blocking": bl})
        samples[REASONS[r - 1]] = rowsx
    out["samples"] = samples
    # ---------------------------------------------------------------- 5. typing audit
    typ = {}
    bounce = [(j, a) for j, a in enumerate(A) if not a["pre"] and a["f"]["ftype"] == "Bounce"]
    placed_o = {o for o, v in view.items() if v[0] in ("placed", "broad_only")}
    grp_gids = {}
    for k in folded:
        if k[1] == "Bounce":
            grp_gids[BL.gid_of(k)] = names[k]
    bt = collections.Counter()
    miss = []
    for j, a in bounce:
        t = " ".join((a["text"] or "").split()).lower()
        status = "tentative" if a["oid"] in tent else ("placed" if a["oid"] in placed_o else ("remaining" if a["oid"] in rset else "other"))
        gy = a["f"]["frm"] == "Graveyard"
        mis = ("battlefield" in t) and ("hand" not in t)
        bt[(status, "frm Graveyard" if gy else "frm not recorded or other", "text says battlefield and not hand" if mis else "ordinary")] += 1
        if mis:
            miss.append((status, a["oid"], t[:160]))
    typ["bounce_abilities"] = len(bounce)
    typ["bounce_breakdown"] = {" | ".join(k): v for k, v in sorted(bt.items())}
    typ["bounce_texts_saying_battlefield_without_hand"] = len(miss)
    typ["bounce_mistyped_by_status"] = dict(collections.Counter(m[0] for m in miss))
    ms = [m for m in miss if m[0] in ("tentative", "placed")]
    pk = rnd.sample(ms, min(10, len(ms)))
    typ["bounce_mistyped_sample10"] = [{"card": L[o]["name"], "status": st, "text": t} for st, o, t in pk]
    # the same kind of check for other effect types: the ability text lacks every verb of its own type
    STEM = {"Destroy": r"destroy", "DealDamage": r"damage", "Draw": r"draw|connive|cycl", "Untap": r"untap", "Tap": r"\btap", "Sacrifice": r"sacrific", "PutCounter": r"counter|enters with|distribute",
            "RemoveCounter": r"remove|proliferate", "Token": r"token|create|investigat|treasure|food|clue|blood", "CopyTokenOf": r"cop(y|ies)|token", "GainControl": r"control",
            "SearchLibrary": r"search|library|seek", "Mill": r"mill", "LoseLife": r"lose|pay|life", "GainLife": r"gain|life", "Discard": r"discard", "Counter": r"counter", "Regenerate": r"regenerat",
            "ChangeZone": r"exile|return|battlefield|graveyard|hand|library|put|sacrifice|destroy|dies", "Bounce": r"return|hand|owner|bounce", "Pump": r"get|\+|-|power|toughness", "GenericEffect": r"."}
    chk = collections.defaultdict(lambda: [0, 0, []])
    for j, a in enumerate(A):
        if a["pre"] or not a["text"] or a["f"]["ftype"] not in STEM:
            continue
        ft = a["f"]["ftype"]
        t = " ".join(a["text"].split()).lower()
        chk[ft][0] += 1
        if not re.search(STEM[ft], t):
            chk[ft][1] += 1
            if len(chk[ft][2]) < 3:
                chk[ft][2].append((L[a["oid"]]["name"], t[:110]))
    typ["verb_missing_check"] = {k: {"abilities": v[0], "text_lacks_the_effect_type_stem": v[1], "examples": v[2]} for k, v in sorted(chk.items(), key=lambda kv: -kv[1][1])}
    # mismatch of destination: ChangeZone to X whose text names a different destination only
    cz = collections.Counter()
    for j, a in enumerate(A):
        if a["pre"] or a["f"]["ftype"] != "ChangeZone" or not a["text"]:
            continue
        t = " ".join(a["text"].split()).lower()
        to = a["f"]["to"]
        words = {"Exile": "exile", "Battlefield": "battlefield", "Hand": "hand", "Graveyard": "graveyard", "Library": "library"}
        if to in words and words[to] not in t:
            cz[to] += 1
    typ["changezone_destination_not_named_in_text"] = dict(cz)
    out["typing"] = typ
    # ---------------------------------------------------------------- card lists for the lever overlap (new file)
    lists = {"primary": {o: primary[o] for o in remaining}, "all_reasons": {o: allr[o] for o in remaining},
             "r2_precise": sorted(allleaf & rset), "r2_broad_only": sorted((allbroad - allleaf) & rset), "r2_tentative_only": sorted((alltent - allleaf - allbroad) & rset),
             "r2_by_shape": {k: {"precise": sorted(v["cards_to_leaf"]), "broad_only": sorted(v["cards_to_broad"] - v["cards_to_leaf"]), "tentative_only": sorted(v["cards_to_tentative"] - v["cards_to_leaf"] - v["cards_to_broad"])} for k, v in shape_stats.items()},
             "r4_sub_cards": {"%s::%s" % (s_["gid"], s_["sub"]): sorted({items[n]["oid"] for n in s_["_n"] if BT.eligible(items[n], True)} & rset) for s_ in subs_info},
             "r5_group_cards": {h["gid"]: sorted({items[n]["oid"] for n in cand[h["gid"]]["n"] if BT.eligible(items[n], True)} & rset) for h in held}}
    with io.open(os.path.join(BUILD, "remaining_cards.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(lists, sort_keys=True, separators=(",", ":")))
    # ---------------------------------------------------------------- write
    out["_internal_note"] = "samples and reads are in build/remaining_*.json"
    with io.open(os.path.join(BUILD, "remaining_breakdown.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    with io.open(os.path.join(BUILD, "remaining_subheadings_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "subheadings": blind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "remaining_subheadings_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "subheadings": key, "all": [{k: v for k, v in s.items() if k != "_n"} for s in subs_info]}, ensure_ascii=False, indent=1))
    show = {k: out[k] for k in ("recount", "primary_reason_counts", "cards_with_each_reason_at_all", "cards_with_more_than_one_reason", "reason_overlap_pairs", "reason_combinations")}
    print(json.dumps(show, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
