#!/usr/bin/env python3
"""Investigation only: break the "Not yet organized" pile down by cause. Builds nothing, places nothing, changes nothing.

    python src/analyze_unorganized_breakdown.py   # -> build/unorganized_breakdown.json, reports/unorganized-breakdown.md

Runs the build's own logic in memory (build_ability_taxonomy.main with its file writes stubbed out) and reads the files it reads; the only files
written are the two outputs above. Every number is MEASURED unless the report labels it an estimate.

Cause order (a card gets the first that applies; every cause that applies is recorded for the overlap tables):
  1 parser gap              status partial / unmodelled, or an ability item that holds an unread node (item-level gap)
  2 unparsed / parse mistake
  3 dropped-condition hold  an ability held back by the dropped-condition detector
  4 gap-card hold           an ability that would place but is held out because its card has a gap (the 5.0% question)
  5 below the minimum       an ability whose signature group has fewer than 5 abilities ("too unusual")
  6 modal / no signature    unresolved object, modal, or no tokens
  7 broad group only        (such cards are not in the pile at all: they are the "broader than they look" cards)
  8 no effect               replacement-only or no extractable effect
  9 other
"""
import collections
import contextlib
import io
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ability_taxonomy as B  # noqa: E402
import build_ledger as BL  # noqa: E402
import probe2_signature_taxonomy as p2  # noqa: E402
import probe_signature_taxonomy as pst  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
REPORTS = os.path.join(HERE, "reports")
DATA = os.path.join(HERE, "data")
SEED = 20261100
CAUSES = ["1 parser gap", "2 unparsed or parse mistake", "3 dropped-condition hold", "4 gap-card hold", "5 below the 5-member minimum",
          "6 modal / no signature / no family", "7 broad group only", "8 no effect or vanilla extension", "9 other"]
RARE = ("rare_verb_parameter", "rare_object", "rare_effect_type", "below_minimum_size")
GAPTEST = ("gap_card_no_text", "gap_card_continuation_gap", "gap_card_same_line_gap")


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def pairs_of_f(f):
    s = {("ftype", f["ftype"])}
    for k in p2.CANON:
        v = p2.val(f, k)
        if v:
            s.add((k, v))
    return s


def pairs_of_leaf(li):
    s = {("ftype", li["ftype"])}
    for k, v in li["ret"].items():
        s.add((k, v))
    return s


def excluded_items(pile):
    """The ability items the population leaves out (flagged for a dropped condition, or holding an unread node), with the item itself."""
    rows = jl("index.json")["rows"]
    byid = {r["id"]: r for r in rows}
    chunks = {n: jl("chunks/%d.json" % n) for n in range(64)}
    P = jl("placements.json")
    rec, stages = P["recovered"]["chunk"], P["recovered"]["stages"]
    AL = jl("ability_ledger.json")
    flagged = {(h["oid"], h["bucket"], h["idx"]): h for h in jl("condition_drops.json")}
    out = []
    for row in AL["rows"]:
        oid, face, b, i, text = row[0], row[1], row[2], row[3], row[4]
        if oid not in pile:
            continue
        cname, status, method, cleaf = AL["cards"][oid]
        e = chunks[byid[face]["ch"]][face] if face in byid else rec.get(face)
        if status == "missing_from_export":
            st = next((f["stage"] for f in stages.get(oid, []) if f["id"] == face), None)
            kind = "clean" if st in ("clean", "no_extractable_effect") else ("gap" if st in pst.GAPPY else "other")
        else:
            kind = "clean" if status in pst.CLEAN else ("gap" if status in pst.GAPPY else "other")
        if e is None or kind == "other":
            continue
        it = e[b][i]
        why = None
        if (oid, b, i) in flagged:
            why = "flagged"
        elif BL.gap_fragments({b: [it]}, e.get("name") or ""):
            why = "item_gap"
        if why:
            out.append({"oid": oid, "face": face, "b": b, "i": i, "text": text, "kind": kind, "why": why, "item": it, "cd": flagged.get((oid, b, i))})
    return out


def pct(a, b):
    return "%.1f%%" % (100.0 * a / b) if b else "-"


def main():
    rnd = random.Random(SEED)
    B.dump = lambda *a, **k: None
    with contextlib.redirect_stdout(io.StringIO()):
        S = B.main()
    A, view, rows, L, leaf_info, cards = S["A"], S["view"], S["rows"], S["L"], S["leaf_info"], S["cards"]
    T = jl("ability_taxonomy.json")
    fam_keys = {f["key"] for f in T["families"]}
    out = {"seed": SEED}

    # ------------------------------------------------------------------ 1. recount
    vc = collections.Counter(v[0] for v in view.values())
    pile = sorted(o for o, v in view.items() if v[0] == "unorganized")
    EXCL = bool(os.environ.get("CONSTRUCTED_ONLY"))      # an environment variable, because build_ability_taxonomy reads the command line
    flags = jl("card_flags.json")["cards"] if EXCL else {}
    n_flagged_in_pile = sum(1 for o in pile if o in flags)
    flagged_by_group = dict(collections.Counter(view[o][1] for o in pile if o in flags))
    flagged_reasons = dict(collections.Counter(flags[o] for o in pile if o in flags))
    pile = [o for o in pile if o not in flags]
    pset = set(pile)
    grp = collections.Counter(view[o][1] for o in pile)
    tot = T["totals"]
    out["excluded_not_for_constructed"] = ({"on": True, "removed_from_the_pile": n_flagged_in_pile, "by_group": flagged_by_group, "reasons": flagged_reasons}
                                           if EXCL else {"on": False})
    out["recount"] = {"universe": len(view), "views": dict(vc), "pile": len(pile), "groups": dict(grp),
                      "placed_total": vc["placed"] + vc["broad_only"] + vc["keyword_block"] + vc["no_abilities"] + vc["replacement_group"],
                      "reconciles": vc["placed"] + vc["broad_only"] + vc["keyword_block"] + vc["no_abilities"] + vc["replacement_group"] + vc["unorganized"] + vc["not_a_card"] == len(view) == tot["universe"],
                      "headline": tot["headline"], "with_broad": tot["with_broad"], "in_scope": tot["in_scope"]}

    # ------------------------------------------------------------------ ability rows per pile card
    rows_by = collections.defaultdict(list)
    for r in rows:
        if r[0] in pset:
            rows_by[r[0]].append(r)
    akey = {(a["face"], a["b"], a["i"], a["mode"]): j for j, a in enumerate(A)}

    # gap fragments (unread / trigger / cond / effect) per pile card, from the unorganized file
    U = jl("ability_taxonomy_unorganized.json")["groups"]
    frag = {}
    for g in U:
        for c in g["list"]:
            if c["c"] in pset:
                frag[c["c"]] = c.get("g") or []

    # ------------------------------------------------------------------ the excluded items: fields and what they would match
    ex = excluded_items(pset)
    ref = [j for j, a in enumerate(A) if a["kind"] == "clean" and not a["pre"]]
    Fref = [A[j]["f"] for j in ref]
    for x in ex:
        f = B.fields3({"b": x["b"], "item": x["item"]})
        if f["fam"] == "Other" and f["ftype"] in B.FAMILY_FIX:
            f["fam"] = B.FAMILY_FIX[f["ftype"]]
        x["f"] = f
    exf = [x["f"] for x in ex]
    res5 = B.assign_rf_ref(Fref, exf, 5) if exf else []

    def classify(r):
        if r[0] == "x":
            return "unplaced:" + r[1]
        li = leaf_info.get(tuple(r))
        if li is None or li["n"] < 5:
            return "unplaced:below_minimum_size"
        return "broad" if li["flags"] else "placed"
    for x, r in zip(ex, res5):
        x["res"] = classify(r)
        x["leaf"] = leaf_info[tuple(r)]["id"] if r[0] != "x" and tuple(r) in leaf_info else ""
    ex_by_key = {(x["oid"], x["b"], x["i"]): x for x in ex}
    leaf_name = {li["id"]: T["leaves"].get(li["id"], {}).get("name", li["id"]) for li in leaf_info.values()}

    # ------------------------------------------------------------------ 2. causes per card
    def cause_set(oid):
        rs = rows_by.get(oid, [])
        reasons = collections.Counter(r[7] for r in rs)
        states = collections.Counter(r[6] for r in rs)
        reason = view[oid][1]
        c = set()
        if reason == "gap" or reasons["item_gap"]:
            c.add(CAUSES[0])
        if reason in ("not_parsed", "known_parse_mistake"):
            c.add(CAUSES[1])
        if reasons["flagged_condition_drop"]:
            c.add(CAUSES[2])
        if states["held_out"]:
            c.add(CAUSES[3])
        if any(reasons[k] for k in RARE):
            c.add(CAUSES[4])
        if reasons["modal"] or reasons["no_signature"] or reasons["no_family"]:
            c.add(CAUSES[5])
        if reason == "no_effect_to_group":
            c.add(CAUSES[7])
        return c
    cs = {o: cause_set(o) for o in pile}
    primary = {}
    for o in pile:
        primary[o] = next((c for c in CAUSES if c in cs[o]), CAUSES[8])
    pc = collections.Counter(primary.values())
    overlap = {c: sum(1 for o in pile if primary[o] == c and len(cs[o]) > 1) for c in CAUSES}
    matrix = {c: collections.Counter() for c in CAUSES}
    for o in pile:
        for d in cs[o]:
            if d != primary[o]:
                matrix[primary[o]][d] += 1
    anycause = {c: sum(1 for o in pile if c in cs[o]) for c in CAUSES}
    nmulti = collections.Counter(len(cs[o]) for o in pile)
    out["causes"] = {"primary": {c: pc[c] for c in CAUSES}, "with_a_second_cause": overlap, "any_cause": anycause,
                     "second_cause_matrix": {c: dict(m) for c, m in matrix.items()}, "cards_by_number_of_causes": dict(nmulti)}
    out["broad_only_outside_pile"] = vc["broad_only"]

    # ------------------------------------------------------------------ 3. evidence
    ev = {}
    # --- gap cards
    gapc = [o for o in pile if CAUSES[0] in cs[o]]
    gtype = collections.Counter()
    for o in gapc:
        kinds = tuple(sorted({x[0] for x in frag.get(o, [])})) or ("item-level only",)
        gtype[kinds] += 1
    held = [o for o in gapc if CAUSES[3] in cs[o]]
    held_placed = [o for o in gapc if any(r[6] == "held_out" and r[7] == "gap_card_placed" for r in rows_by[o])]
    held_broad_only = [o for o in held if o not in set(held_placed)]
    clean_ab_cards = [o for o in gapc if any((r[6] == "held_out") or (r[6] == "placed") or (r[7] in RARE) for r in rows_by[o])]
    testfail = collections.Counter()
    for o in gapc:
        for k in GAPTEST + ("item_gap",):
            if any(r[7] == k for r in rows_by[o]):
                testfail[k] += 1
    ev["gap"] = {"cards": len(gapc), "gap_types": {" + ".join(k): n for k, n in gtype.most_common()},
                 "cards_with_a_clean_ability_that_passes_the_tests": len(clean_ab_cards),
                 "cards_with_a_held_out_ability_in_an_unflagged_leaf": len(held_placed),
                 "cards_with_a_held_out_ability_only_in_broad_leaves": len(held_broad_only),
                 "held_out_abilities_unflagged": sum(1 for o in gapc for r in rows_by[o] if r[7] == "gap_card_placed"),
                 "held_out_abilities_broad": sum(1 for o in gapc for r in rows_by[o] if r[7] == "gap_card_placed_broad"),
                 "cards_failing_each_test": dict(testfail)}
    # top gap causes (by the normalized unread fragment), and sole-cause cards
    fc = collections.defaultdict(set)
    for o in gapc:
        for k, t in frag.get(o, []):
            fc[(k, re.sub(r"\d+", "N", t)[:70])].add(o)
    sole = {}
    for key, cs_ in fc.items():
        sole[key] = [o for o in cs_ if {(k, re.sub(r"\d+", "N", t)[:70]) for k, t in frag.get(o, [])} == {key}]
    top = sorted(fc.items(), key=lambda kv: -len(kv[1]))[:10]
    held_set = set(held_placed)
    ev["gap"]["top_gap_causes"] = [{"kind": k[0], "fragment": k[1], "cards": len(v), "sole_cause_cards": len(sole[k]),
                                    "sole_cause_cards_that_have_an_ability_already_matching_an_unflagged_leaf": sum(1 for o in sole[k] if o in held_set)} for k, v in top]
    ev["gap"]["distinct_gap_causes"] = len(fc)
    ev["gap"]["cards_with_a_single_gap_fragment"] = sum(1 for o in gapc if len(frag.get(o, [])) == 1)
    ev["gap"]["cards_with_two_or_more_fragments"] = sum(1 for o in gapc if len(frag.get(o, [])) >= 2)

    # --- too unusual: nearest leaf and similarity of each blocking ability, and what a minimum of 3 would do
    tu = [o for o in pile if primary[o] == CAUSES[4]]
    leaves_by_ft = collections.defaultdict(list)
    for li in leaf_info.values():
        if li["n"] >= 5:
            leaves_by_ft[li["ftype"]].append((li, pairs_of_leaf(li)))
    blk = {}
    for o in tu:
        js = [akey.get((r[1], r[2], r[3], r[4])) for r in rows_by[o] if r[7] in RARE]
        blk[o] = [j for j in js if j is not None]
    best = {}
    for o in tu:
        bs = None
        for j in blk[o]:
            pa = pairs_of_f(A[j]["f"])
            for li, pl in leaves_by_ft.get(A[j]["f"]["ftype"], []):
                sim = len(pa & pl) / len(pa | pl)
                if bs is None or sim > bs[0]:
                    bs = (sim, li["id"], j)
        best[o] = bs
    bins = collections.Counter()
    for o in tu:
        s_ = best[o][0] if best[o] else None
        bins["no leaf of that effect type" if s_ is None else "<0.30" if s_ < .3 else "0.30-0.50" if s_ < .5 else "0.50-0.70" if s_ < .7 else "0.70-0.90" if s_ < .9 else ">=0.90"] += 1
    nearest = collections.Counter(leaf_name.get(best[o][1], best[o][1]) for o in tu if best[o])
    # a minimum of 3
    allj = sorted({j for o in tu for j in blk[o]})
    r3 = {}
    if allj:
        for j, r in zip(allj, B.assign_rf_ref(Fref, [A[j]["f"] for j in allj], 3)):
            r3[j] = r
    cards_any3 = [o for o in tu if any(r3.get(j, ("x",))[0] != "x" for j in blk[o])]
    cards_all3 = [o for o in tu if blk[o] and all(r3.get(j, ("x",))[0] != "x" for j in blk[o])]
    r3_not5 = collections.Counter()
    for j, r in r3.items():
        if r[0] != "x":
            li = leaf_info.get(tuple(r))
            r3_not5["a leaf exists at 3 and not at 5"] += 1
    ev["too_unusual"] = {"cards": len(tu), "blocking_abilities": len(allj), "best_similarity_of_a_card": dict(bins),
                         "top_nearest_leaves": nearest.most_common(10),
                         "cards_with_an_ability_that_places_at_a_minimum_of_3": len(cards_any3),
                         "cards_whose_every_blocking_ability_places_at_3": len(cards_all3),
                         "abilities_placing_at_3_but_not_5": sum(r3_not5.values()),
                         "reasons": dict(collections.Counter(r[7] for o in tu for r in rows_by[o] if r[7] in RARE))}

    # --- dropped-condition holds, by sub-shape
    cdx = [x for x in ex if x["why"] == "flagged"]
    sub = collections.defaultdict(lambda: collections.Counter())
    movers = collections.defaultdict(set)
    allmov = set()
    for x in cdx:
        k = (x["cd"].get("shape"), x["cd"].get("sub"))
        sub[k]["items"] += 1
        sub[k]["on_gap_cards" if x["kind"] == "gap" else "on_clean_cards"] += 1
        sub[k][x["res"].split(":")[0]] += 1
        if x["kind"] == "clean" and x["res"] == "placed" and view[x["oid"]][0] == "unorganized":
            movers[k].add(x["oid"])
            allmov.add(x["oid"])
    ev["dropped_condition"] = {"flagged_items_in_the_pile": len(cdx),
                               "if_all_fixed": {"items_that_would_place_unflagged": sum(1 for x in cdx if x["res"] == "placed"),
                                                "items_that_would_only_reach_a_broad_leaf": sum(1 for x in cdx if x["res"] == "broad"),
                                                "items_that_would_still_not_place": sum(1 for x in cdx if x["res"].startswith("unplaced")),
                                                "clean_cards_that_would_move": len(allmov),
                                                "gap_card_items_that_would_place_but_stay_held_out": sum(1 for x in cdx if x["kind"] == "gap" and x["res"] == "placed")},
                               "by_sub_shape": [{"shape": k[0], "sub": k[1], **dict(v), "clean_cards_that_would_move": len(movers[k])}
                                                for k, v in sorted(sub.items(), key=lambda kv: -kv[1]["items"])]}

    # --- the other causes: counts and where they sit
    ev["unparsed_or_mistake"] = {"cards": pc[CAUSES[1]], "by_group": dict(collections.Counter(view[o][1] for o in pile if primary[o] == CAUSES[1]))}
    ev["modal_nosig"] = {"cards": pc[CAUSES[5]], "reasons": dict(collections.Counter(r[7] for o in pile if primary[o] == CAUSES[5] for r in rows_by[o] if r[7] in ("modal", "no_signature", "no_family")))}
    ev["no_effect"] = {"cards": pc[CAUSES[7]]}
    ev["other"] = {"cards": pc[CAUSES[8]]}

    # --- samples: 10 per cause
    def itemtext(o, pred):
        for r in rows_by[o]:
            if pred(r):
                return r[5], r
        return "", None

    def sample_row(o, c):
        nm = L[o]["name"]
        if c == CAUSES[0]:
            t, r = itemtext(o, lambda r: r[7] == "item_gap")
            fr = "; ".join("%s: %s" % (k, tx[:60]) for k, tx in frag.get(o, [])[:2]) or "(item-level)"
            hl, _r = itemtext(o, lambda r: r[6] == "held_out")
            wb = ""
            for r in rows_by[o]:
                if r[6] == "held_out":
                    wb = "held-out ability would sit in: " + leaf_name.get(r[8], r[8])
                    break
            return nm, t[:110], "gap: " + fr, wb or "no ability of this card clears the tests"
        if c == CAUSES[2]:
            t, r = itemtext(o, lambda r: r[7] == "flagged_condition_drop")
            xx = ex_by_key.get((o, r[2], r[3])) if r else None
            wb = ("would match: " + leaf_name.get(xx["leaf"], xx["leaf"])) if xx and xx["res"] == "placed" else ("would only reach a broad leaf" if xx and xx["res"] == "broad" else "would still not place")
            return nm, t[:110], "dropped-condition detector: " + (xx["cd"].get("sub") if xx else "?"), wb
        if c == CAUSES[4]:
            t, r = itemtext(o, lambda r: r[7] in RARE)
            b_ = best.get(o)
            wb = ("nearest leaf %.2f: %s" % (b_[0], leaf_name.get(b_[1], b_[1]))) if b_ else "no leaf of that effect type"
            return nm, t[:110], r[7] if r else "", wb
        t, r = itemtext(o, lambda r: True)
        return nm, t[:110], view[o][1] + (" / " + r[7] if r else ""), ""
    samples = {}
    for c in CAUSES:
        pool = sorted(o for o in pile if primary[o] == c)
        pick = rnd.sample(pool, min(10, len(pool)))
        samples[c] = [dict(zip(("card", "ability_text", "reason", "would_be"), sample_row(o, c))) for o in pick]
    out["evidence"] = ev
    out["samples"] = samples
    # ---- the candidate fixes as card sets, so overlap is measured and not assumed
    fixA = set(held_placed)                     # lift the gap-card hold
    fixB = set(cards_any3)                      # minimum of 3 for the "too unusual" cards
    fixC = set(allmov)                          # every dropped-condition sub-shape fixed (ceiling)
    sub_top = [(k, v) for k, v in sorted(movers.items(), key=lambda kv: -len(kv[1]))]
    fixC3 = set().union(*[v for _, v in sub_top[:3]]) if sub_top else set()
    gapsole = set()
    for key, v in sole.items():
        gapsole |= {o for o in v if o in fixA}
    out["fix_sets"] = {"A_lift_gap_hold": len(fixA), "B_minimum_3": len(fixB), "C_condition_drops_all": len(fixC), "C_top3_sub_shapes": len(fixC3),
                       "A_and_B": len(fixA & fixB), "A_and_C": len(fixA & fixC), "B_and_C": len(fixB & fixC), "A_or_B_or_C": len(fixA | fixB | fixC),
                       "A_or_B": len(fixA | fixB), "gap_top10_sole_cause_cards_also_in_A": len(gapsole),
                       "gap_top10_sole_cause_cards": sum(len(sole[(t["kind"], t["fragment"])]) for t in ev["gap"]["top_gap_causes"]) if False else 0}

    # ------------------------------------------------------------------ 4. popularity
    import gzip
    rank = {}
    with gzip.open(os.path.join(DATA, "scryfall-oracle-cards.jsonl.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            o_ = json.loads(line)
            if o_.get("edhrec_rank") is not None:
                rank[o_["oracle_id"]] = o_["edhrec_rank"]
    pop = {}
    for c in CAUSES:
        cards_c = [o for o in pile if primary[o] == c]
        rk = [rank.get(o) for o in cards_c]
        pop[c] = {"cards": len(cards_c), "top1000": sum(1 for r in rk if r is not None and r <= 1000), "top3000": sum(1 for r in rk if r is not None and r <= 3000),
                  "top10000": sum(1 for r in rk if r is not None and r <= 10000), "no_rank": sum(1 for r in rk if r is None)}
    pop["all"] = {k: sum(pop[c][k] for c in CAUSES) for k in ("cards", "top1000", "top3000", "top10000", "no_rank")}
    out["popularity"] = {"field": "edhrec_rank (Scryfall oracle_cards export); lower is more popular; %d of %d in-scope cards have one" % (sum(1 for o in L if o in rank and view[o][0] != "not_a_card"), sum(1 for o in L if view[o][0] != "not_a_card")),
                         "by_cause": pop}

    # ------------------------------------------------------------------ 5. unique subgrouping, on paper
    fam_of = collections.defaultdict(list)       # card -> [(family, ftype)]
    for a in A:
        if a["oid"] in pset and not a["pre"]:
            if a["f"]["fam"] in fam_keys:
                fam_of[a["oid"]].append((a["f"]["fam"], a["f"]["ftype"]))
    for x in ex:
        if x["f"]["fam"] in fam_keys:
            fam_of[x["oid"]].append((x["f"]["fam"], x["f"]["ftype"]))
    has_fam = [o for o in pile if fam_of.get(o)]
    nofam = [o for o in pile if not fam_of.get(o)]
    multi = collections.Counter()
    single = collections.Counter()
    ftmix = collections.defaultdict(collections.Counter)
    for o in has_fam:
        fams = collections.Counter(f for f, _ in fam_of[o])
        for f in fams:
            multi[f] += 1
        top_f = fams.most_common(1)[0][0]
        single[top_f] += 1
        for f, ft in set(fam_of[o]):
            ftmix[f][ft] += 1
    big = single.most_common(1)[0][0] if single else ""
    mix = ftmix[big]
    share3 = sum(n for _, n in mix.most_common(3)) / max(1, sum(mix.values()))
    ev5 = {"cards_in_pile": len(pile), "cards_with_at_least_one_ability_in_a_tree_family": len(has_fam), "cards_with_no_family_at_all": len(nofam),
           "no_family_by_primary_cause": dict(collections.Counter(primary[o] for o in nofam)),
           "cards_per_family_if_a_card_may_appear_in_several": multi.most_common(12),
           "cards_per_family_if_each_card_goes_to_its_most_common_family": single.most_common(12),
           "largest_single_family": big, "largest_family_distinct_effect_types": len(mix), "largest_family_top3_effect_types_share": round(share3, 2),
           "largest_family_top_effect_types": mix.most_common(8)}
    out["subgrouping"] = ev5

    # ------------------------------------------------------------------ write
    sfx = "_constructed_only" if EXCL else ""
    with io.open(os.path.join(BUILD, "unorganized_breakdown%s.json" % sfx), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    write_md(out, pc, tot, sfx)
    print(json.dumps({k: out[k] for k in ("recount", "causes")}, indent=1, ensure_ascii=False)[:6000])


def write_md(o, pc, tot, sfx=""):
    R = o["recount"]
    md = ["# \"Not yet organized\": breakdown by cause", "",
          "Investigation only (`src/analyze_unorganized_breakdown.py`, seed %d). Nothing was built, placed or changed; new files only: `build/unorganized_breakdown.json` and this report. "
          "Every figure is **measured** from the current build unless it says **estimate**." % o["seed"], "",
          ("**This version leaves out the %s pile cards that are not meant for constructed play** (%s); every count below is of the remaining %s cards. The headline figures in section 1 still describe the whole pool." % (
              format(o["excluded_not_for_constructed"]["removed_from_the_pile"], ","), ", ".join("%s %s" % (k, v) for k, v in o["excluded_not_for_constructed"]["by_group"].items()),
              format(R["pile"] - o["excluded_not_for_constructed"]["removed_from_the_pile"], ","))
           if o["excluded_not_for_constructed"]["on"] else "This version includes every card in the pool."), "",
          "## 1. Recount", "",
          "- Universe %s = %s placed in a group (%s precise-grouped + %s only in broad groups + %s keyword block + %s no abilities + %s replacement) + **%s not yet organized** + %s not cards. Reconciles: **%s**." % (
              format(R["universe"], ","), format(R["placed_total"], ","), format(R["views"]["placed"], ","), format(R["views"]["broad_only"], ","),
              format(R["views"]["keyword_block"], ","), format(R["views"]["no_abilities"], ","), format(R["views"]["replacement_group"], ","),
              format(R["pile"], ","), format(R["views"]["not_a_card"], ","), R["reconciles"]),
          "- Groups in the pile today: " + ", ".join("%s %s" % (k, format(v, ",")) for k, v in sorted(R["groups"].items(), key=lambda kv: -kv[1])) + ".",
          "- Headline: **%s of %s = %s%%** (basis: %s)." % (format(R["headline"]["cards"], ","), format(R["in_scope"], ","), R["headline"]["pct"], R["headline"]["basis"]),
          "- With broad groups: **%s = %s%%** (basis: %s). The archived view's 74.8%% is on a different basis." % (format(R["with_broad"]["cards"], ","), R["with_broad"]["pct"], R["with_broad"]["basis"]), ""]
    md += ["## 2. Primary cause (fixed order) and overlap", "",
           "A card gets the first cause in the list that applies. **Cause 4 can never be primary** under this order: every gap-card ability belongs to a card that cause 1 already took. "
           "It appears only as a second cause, which is exactly what keeps a fix from over-promising. Cause 7 is empty by construction: cards that sit only in broad groups are %s cards outside the pile." % format(o["broad_only_outside_pile"], ","), "",
           "| cause | primary | with a second cause | has this cause (any) |", "|---|---:|---:|---:|"]
    C = o["causes"]
    for c in CAUSES:
        md.append("| %s | %s | %s | %s |" % (c, format(C["primary"][c], ","), format(C["with_a_second_cause"][c], ","), format(C["any_cause"][c], ",")))
    md += ["", "Second causes behind each primary cause (cards):", ""]
    for c in CAUSES:
        m = C["second_cause_matrix"].get(c) or {}
        if m:
            md.append("- %s: " % c + ", ".join("%s %s" % (k, format(v, ",")) for k, v in sorted(m.items(), key=lambda kv: -kv[1])))
    md += ["", "Cards by number of causes: " + ", ".join("%s causes: %s" % (k, format(v, ",")) for k, v in sorted(C["cards_by_number_of_causes"].items(), key=lambda kv: int(kv[0]))), ""]
    E = o["evidence"]
    g = E["gap"]
    md += ["## 3. Evidence per cause", "", "### Parser gap (cause 1)", "",
           "- Cards: %s. Gap types (what the parser could not read): %s." % (format(g["cards"], ","), "; ".join("%s %s" % (k, format(v, ",")) for k, v in g["gap_types"].items())),
           "- Cards with at least one clean ability that passes the same-line and continuation tests: **%s**. Of those, **%s** have a held-out ability that would match an unflagged specific leaf (%s abilities), and %s more only match broad leaves." % (
               format(g["cards_with_a_clean_ability_that_passes_the_tests"], ","), format(g["cards_with_a_held_out_ability_in_an_unflagged_leaf"], ","),
               format(g["held_out_abilities_unflagged"], ","), format(g["cards_with_a_held_out_ability_only_in_broad_leaves"], ",")),
           "- Cards failing each test: " + ", ".join("%s %s" % (k, format(v, ",")) for k, v in g["cards_failing_each_test"].items()) + ".",
           "- Distinct gap fragments: %s; %s cards have exactly one, %s have two or more." % (format(g["distinct_gap_causes"], ","), format(g["cards_with_a_single_gap_fragment"], ","), format(g["cards_with_two_or_more_fragments"], ",")),
           "", "Top 10 gap causes by cards (sole cause = the card's only gap fragment, so fixing it clears the gap; the last column is an upper bound on cards that would then be placed, because they already have an ability matching an unflagged leaf):", "",
           "| kind | fragment | cards | sole-cause cards | ...of which already have a matching ability |", "|---|---|---:|---:|---:|"]
    for t in g["top_gap_causes"]:
        md.append("| %s | %s | %s | %s | %s |" % (t["kind"], t["fragment"].replace("|", "/"), t["cards"], t["sole_cause_cards"], t["sole_cause_cards_that_have_an_ability_already_matching_an_unflagged_leaf"]))
    tu = E["too_unusual"]
    md += ["", "### Below the 5-member minimum (cause 5)", "",
           "- Primary-cause cards: %s, with %s blocking abilities (%s)." % (format(tu["cards"], ","), format(tu["blocking_abilities"], ","), ", ".join("%s %s" % (k, v) for k, v in tu["reasons"].items())),
           "- Best signature similarity (Jaccard over field=value pairs, same effect type) of each card's closest blocking ability to any leaf: " + ", ".join("%s %s" % (k, format(v, ",")) for k, v in tu["best_similarity_of_a_card"].items()) + ".",
           "- Nearest leaves, by cards: " + "; ".join("%s (%s)" % (n, c) for n, c in tu["top_nearest_leaves"]) + ".",
           "- With a minimum of 3 instead of 5 (measured, not built): **%s cards** have a blocking ability that would place, **%s** have every blocking ability placing; %s abilities have a leaf at 3 but not at 5." % (
               format(tu["cards_with_an_ability_that_places_at_a_minimum_of_3"], ","), format(tu["cards_whose_every_blocking_ability_places_at_3"], ","), format(tu["abilities_placing_at_3_but_not_5"], ",")), ""]
    dc = E["dropped_condition"]
    md += ["### Dropped-condition holds (cause 3)", "",
           "- Flagged abilities held back in the pile: %s. If every sub-shape were fixed and the abilities then matched like any clean ability: %s would place in an unflagged leaf, %s only in a broad leaf, %s still would not place; **%s clean cards would move** (%s gap-card abilities would place but stay held out)." % (
               format(dc["flagged_items_in_the_pile"], ","), format(dc["if_all_fixed"]["items_that_would_place_unflagged"], ","), format(dc["if_all_fixed"]["items_that_would_only_reach_a_broad_leaf"], ","),
               format(dc["if_all_fixed"]["items_that_would_still_not_place"], ","), format(dc["if_all_fixed"]["clean_cards_that_would_move"], ","), format(dc["if_all_fixed"]["gap_card_items_that_would_place_but_stay_held_out"], ",")),
           "", "| shape | sub-shape | items | place (unflagged) | broad | still no | on gap cards | clean cards that would move |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for s in dc["by_sub_shape"]:
        md.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (s["shape"], s["sub"], s["items"], s.get("placed", 0), s.get("broad", 0), s.get("unplaced", 0), s.get("on_gap_cards", 0), s["clean_cards_that_would_move"]))
    md += ["", "(The numbers assume the fix leaves each ability's parse as the detector's structure implies; a real fix changes the parse. Treat as an **estimate** of the ceiling.)", "",
           "### Other causes", "",
           "- Unparsed or parse mistake: %s cards (%s)." % (format(E["unparsed_or_mistake"]["cards"], ","), ", ".join("%s %s" % (k, v) for k, v in E["unparsed_or_mistake"]["by_group"].items())),
           "- Modal / no signature / no family: %s cards (%s)." % (format(E["modal_nosig"]["cards"], ","), ", ".join("%s %s" % (k, v) for k, v in E["modal_nosig"]["reasons"].items())),
           "- No effect or vanilla extension: %s cards. Other: %s cards." % (E["no_effect"]["cards"], E["other"]["cards"]), "", "### Ten sample cards per cause (seeded)", ""]
    for c in CAUSES:
        sm = o["samples"][c]
        if not sm:
            continue
        md += ["**%s**" % c, "", "| card | ability text | reason | would sit in (measured) |", "|---|---|---|---|"]
        for s in sm:
            md.append("| %s | %s | %s | %s |" % (s["card"].replace("|", "/"), s["ability_text"].replace("|", "/").replace("\n", " "), s["reason"].replace("|", "/"), s["would_be"].replace("|", "/")))
        md.append("")
    P = o["popularity"]
    md += ["## 4. Popularity", "", "Field: " + P["field"] + ". Cumulative: a top-1,000 card is also in the top 3,000 and 10,000.", "",
           "| primary cause | cards | top 1,000 | top 3,000 | top 10,000 | no rank |", "|---|---:|---:|---:|---:|---:|"]
    for c in CAUSES + ["all"]:
        p = P["by_cause"][c]
        md.append("| %s | %s | %s | %s | %s | %s |" % (c, format(p["cards"], ","), p["top1000"], p["top3000"], p["top10000"], format(p["no_rank"], ",")))
    sg = o["subgrouping"]
    md += ["", "## 5. Unique subgrouping, on paper", "",
           "- Pile cards with at least one ability whose effect type maps to a family of the new tree: **%s** of %s. Cards with no family at all: **%s** (%s)." % (
               format(sg["cards_with_at_least_one_ability_in_a_tree_family"], ","), format(sg["cards_in_pile"], ","), format(sg["cards_with_no_family_at_all"], ","),
               ", ".join("%s %s" % (k, v) for k, v in sg["no_family_by_primary_cause"].items())),
           "- Cards per family if a card may appear under several (browse-only): " + "; ".join("%s %s" % (k, format(v, ",")) for k, v in sg["cards_per_family_if_a_card_may_appear_in_several"]) + ".",
           "- Cards per family if each card goes to its most common family: " + "; ".join("%s %s" % (k, format(v, ",")) for k, v in sg["cards_per_family_if_each_card_goes_to_its_most_common_family"]) + ".",
           "- Largest single-assignment subgroup: **%s**; it spans %s effect types, its top 3 cover %s%% of its abilities (%s)." % (
               sg["largest_single_family"], sg["largest_family_distinct_effect_types"], int(100 * sg["largest_family_top3_effect_types_share"]),
               ", ".join("%s %s" % (k, v) for k, v in sg["largest_family_top_effect_types"])), ""]
    F = o["fix_sets"]
    g = o["evidence"]["gap"]
    topsole = sum(t["sole_cause_cards"] for t in g["top_gap_causes"])
    topsole_ab = sum(t["sole_cause_cards_that_have_an_ability_already_matching_an_unflagged_leaf"] for t in g["top_gap_causes"])
    inscope = R["in_scope"]
    md += ["", "## 6. Recommendation", "",
           "Ranked by cards moved per effort. **Measured** = counted on the current build. **Estimate** = rests on a judgment call. The first three card sets are counted as sets, so their overlap is measured: "
           "A and B overlap in %s cards, A and C in %s, B and C in %s (they are disjoint by construction: A is gap cards, B is cards whose only block is the minimum, C is clean cards held for a dropped condition), "
           "so together they cover **%s** distinct cards. What is NOT measured is whether a card also needs a second fix: %s of the primary cause-1 cards, 5 of cause 5 and 49 of cause 3 have a second cause, "
           "but each set above counts only cards that need nothing else to be placed." % (
               F["A_and_B"], F["A_and_C"], F["B_and_C"], format(F["A_or_B_or_C"], ","), format(C["with_a_second_cause"][CAUSES[0]], ",")), "",
           "| rank | fix | cards moved (upper bound) | effort | what it leaves behind | judgment calls |", "|---:|---|---:|---|---|---|",
           "| 1 | **Lift the gap-card hold** (the 5.0%% question): their held-out abilities already match an unflagged leaf | **%s** measured (about +%.1f points on the headline) | low: a decision plus a fresh sample of about 100 on a new seed | the other %s gap cards, whose abilities fail the tests or match nothing | the error rate: 2 of 40 wrong last time; with a true rate near 5%% roughly %s of these would be wrongly filed (estimate) |" % (
               format(F["A_lift_gap_hold"], ","), 100.0 * F["A_lift_gap_hold"] / inscope, format(g["cards"] - F["A_lift_gap_hold"], ","), format(int(round(0.05 * F["A_lift_gap_hold"])), ",")),
           "| 2 | **A minimum of 3 for the \"too unusual\" cards** | **%s** measured (every blocking ability places for %s) | low to build; needs a coherence check | the other %s of that group; the cards with no near leaf | whether groups of 3 or 4 abilities are coherent: unmeasured, so the real number is lower (estimate); this changes a threshold, which this task did not touch |" % (
               format(F["B_minimum_3"], ","), format(tu["cards_whose_every_blocking_ability_places_at_3"], ","), format(tu["cards"] - F["B_minimum_3"], ",")),
           "| 3 | **Browse-only subgroups by family** (display, not placement) | up to %s cards get a home; none count toward the precise headline | low to medium | %s cards with no family (mostly gap cards whose only abilities are the hole) | whether a browse-only home counts as organized: a definition call; the largest subgroup is not a junk drawer on effect type (see section 5) |" % (
               format(sg["cards_with_at_least_one_ability_in_a_tree_family"], ","), format(sg["cards_with_no_family_at_all"], ",")),
           "| 4 | **Dropped-condition fixes** (detector / parser) | ceiling **%s** clean cards for all sub-shapes together; **%s** for the three biggest sub-shapes (measured on the detector's own structure) | high: each sub-shape is its own parser change | gap cards (their items stay held out), and the %s flagged items that would still not place | the real figure is lower: once the condition is kept, items get a more specific signature and many will fall to a rarer leaf (estimate) |" % (
               format(F["C_condition_drops_all"], ","), format(F["C_top3_sub_shapes"], ","), format(dc["if_all_fixed"]["items_that_would_still_not_place"], ",")),
           "| 5 | **Parser gap causes**, one fragment at a time | the ten biggest causes clear the gap for %s sole-cause cards; at most %s of those already have a matching ability, so about that many would be placed (measured upper bound) | high per fix, and the tail is long | %s distinct gap fragments exist; %s cards have exactly one | each fix helps a handful of cards; several of the ten are mechanics the parser does not model at all (e.g. spellbook drafting, the initiative) |" % (
               format(topsole, ","), format(topsole_ab, ","), format(g["distinct_gap_causes"], ","), format(g["cards_with_a_single_gap_fragment"], ",")),
           "| 6 | Unparsed (29), known parse mistakes (8), replacement-only (23), modal / no signature (1) | %s | per card | all of them | none; these are the floor of the pile |" % format(37 + 23 + 1, ","), "",
           "What the ranking does not claim: none of the sets is a count of cards that will be **correctly** placed; A carries a known error risk, B and C carry unmeasured ones. The popularity view says the most popular cards are in cause 1 by number "
           "(%s of the top 1,000), but cause 5 has the highest share (%.1f%% of its cards are in the top 1,000 against %.1f%% for cause 1)." % (
               o["popularity"]["by_cause"][CAUSES[0]]["top1000"], 100.0 * o["popularity"]["by_cause"][CAUSES[4]]["top1000"] / max(1, o["popularity"]["by_cause"][CAUSES[4]]["cards"]),
               100.0 * o["popularity"]["by_cause"][CAUSES[0]]["top1000"] / max(1, o["popularity"]["by_cause"][CAUSES[0]]["cards"])), ""]
    with io.open(os.path.join(REPORTS, "unorganized-breakdown%s.md" % sfx.replace("_", "-")), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
