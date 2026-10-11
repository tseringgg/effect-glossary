#!/usr/bin/env python3
"""Investigation only (v3): the "Not yet organized" pile by cause on the CURRENT build (constructed-only card set, gap-card abilities placed).
Builds nothing, places nothing, changes nothing.

    python src/analyze_unorganized_breakdown_v3.py   # -> build/unorganized_breakdown_v3.json, reports/unorganized-breakdown-v3.md

Runs the build's own logic in memory (build_ability_taxonomy.main with its file writes stubbed out) and reads the files it reads. Seed 20261200 for
the samples. Every number is MEASURED unless the report labels it an estimate.

Cause order (a card gets the first that applies; every cause that applies is recorded for the overlap tables):
  1 parser gap              status partial / unmodelled, or an ability item holding an unread node; gap type = what the parser could not read
  2 unparsed / parse mistake
  3 dropped-condition hold  an ability held back by the dropped-condition detector
  4 gap-card ability still unplaced   a gap card's ability that fails the no-text / continuation / same-line test (the item-level hole is cause 1)
  5 below the minimum       an ability whose signature group has fewer than 5 abilities
  6 modal / no signature / no family
  7 no effect               replacement-only or no extractable effect
  8 other
Gap cards are always cause 1 first, so cause 4 appears only as a second cause (that is what keeps a fix from over-promising).
"""
import collections
import contextlib
import gzip
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
SEED = 20261200
CAUSES = ["1 parser gap", "2 unparsed or parse mistake", "3 dropped-condition hold", "4 gap-card ability still unplaced",
          "5 below the 5-member minimum", "6 modal / no signature / no family", "7 no effect or vanilla extension", "8 other"]
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


def held_items(pile, testfail):
    """Items the population leaves out (dropped condition, unread node in the item) or that fail a gap-card test, with the item itself."""
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
        elif (face, b, i) in testfail:
            why = "test_fail"
        if why:
            out.append({"oid": oid, "face": face, "b": b, "i": i, "text": text, "kind": kind, "why": why, "item": it, "cd": flagged.get((oid, b, i)),
                        "test": testfail.get((face, b, i))})
    return out


def frag_family(kind, text):
    t = re.sub(r"\{[^}]*\}", "", text.lower())
    t = re.sub(r"\d+", "N", t)
    w = re.findall(r"[a-z~']+", t)
    return (kind, " ".join(w[:2]) if w else "(empty)")


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
    pset = set(pile)
    grp = collections.Counter(view[o][1] for o in pile)
    tot = T["totals"]
    placed_total = vc["placed"] + vc["broad_only"] + vc["keyword_block"] + vc["no_abilities"] + vc["replacement_group"]
    out["recount"] = {"universe": len(view), "views": dict(vc), "pile": len(pile), "groups": dict(grp), "placed_total": placed_total,
                      "reconciles": placed_total + vc["unorganized"] + vc["not_a_card"] == len(view) == tot["universe"] == 38921,
                      "headline": tot["headline"], "with_broad": tot["with_broad"], "in_scope": tot["in_scope"]}
    rows_by = collections.defaultdict(list)
    for r in rows:
        if r[0] in pset:
            rows_by[r[0]].append(r)
    akey = {(a["face"], a["b"], a["i"], a["mode"]): j for j, a in enumerate(A)}
    U = jl("ability_taxonomy_unorganized.json")["groups"]
    frag = {}
    for g in U:
        for c in g["list"]:
            if c["c"] in pset:
                frag[c["c"]] = c.get("g") or []

    # ------------------------------------------------------------------ held items and what they would match
    testfail = {}
    for r in rows:
        if r[0] in pset and r[7] in GAPTEST:
            testfail[(r[1], r[2], r[3])] = r[7]
    ex = held_items(pset, testfail)
    ref = [j for j, a in enumerate(A) if a["kind"] == "clean" and not a["pre"]]
    Fref = [A[j]["f"] for j in ref]
    for x in ex:
        f = B.fields3({"b": x["b"], "item": x["item"]})
        if f["fam"] == "Other" and f["ftype"] in B.FAMILY_FIX:
            f["fam"] = B.FAMILY_FIX[f["ftype"]]
        x["f"] = f
    res5 = B.assign_rf_ref(Fref, [x["f"] for x in ex], 5) if ex else []

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
        reason = view[oid][1]
        c = set()
        if reason == "gap" or reasons["item_gap"]:
            c.add(CAUSES[0])
        if reason in ("not_parsed", "known_parse_mistake"):
            c.add(CAUSES[1])
        if reasons["flagged_condition_drop"]:
            c.add(CAUSES[2])
        if any(reasons[k] for k in GAPTEST):
            c.add(CAUSES[3])
        if any(reasons[k] for k in RARE):
            c.add(CAUSES[4])
        if reasons["modal"] or reasons["no_signature"] or reasons["no_family"]:
            c.add(CAUSES[5])
        if reason == "no_effect_to_group":
            c.add(CAUSES[6])
        return c
    cs = {o: cause_set(o) for o in pile}
    primary = {o: next((c for c in CAUSES if c in cs[o]), CAUSES[7]) for o in pile}
    pc = collections.Counter(primary.values())
    matrix = {c: collections.Counter() for c in CAUSES}
    for o in pile:
        for d in cs[o]:
            if d != primary[o]:
                matrix[primary[o]][d] += 1
    out["causes"] = {"primary": {c: pc[c] for c in CAUSES}, "with_a_second_cause": {c: sum(1 for o in pile if primary[o] == c and len(cs[o]) > 1) for c in CAUSES},
                     "any_cause": {c: sum(1 for o in pile if c in cs[o]) for c in CAUSES}, "second_cause_matrix": {c: dict(m) for c, m in matrix.items()},
                     "cards_by_number_of_causes": dict(collections.Counter(len(cs[o]) for o in pile))}

    # ------------------------------------------------------------------ 3. evidence
    ev = {}
    gapc = [o for o in pile if CAUSES[0] in cs[o]]
    gtype = collections.Counter(" + ".join(sorted({x[0] for x in frag.get(o, [])})) or "item-level only" for o in gapc)
    failing = collections.Counter()
    for o in gapc:
        for k in GAPTEST + ("item_gap",):
            if any(r[7] == k for r in rows_by[o]):
                failing[k] += 1
    secondary = collections.Counter()
    for o in gapc:
        for c in cs[o]:
            if c != CAUSES[0]:
                secondary[c] += 1
    # distinct fragment families
    fam_cards = collections.defaultdict(set)
    for o in gapc:
        for k, t in frag.get(o, []):
            fam_cards[frag_family(k, t)].add(o)
    ranked = sorted(fam_cards.items(), key=lambda kv: -len(kv[1]))
    cards_with_frag = [o for o in gapc if frag.get(o)]
    unread_cards = [o for o in gapc if any(x[0] == "unread" for x in frag.get(o, []))]
    cover = {}
    for n in (12, 24, 36, 48, 100, 200):
        top = {k for k, _ in ranked[:n]}
        cover[str(n)] = {"cards_with_any_fragment_in_the_top_n": len({o for k, v in ranked[:n] for o in v}),
                         "cards_whose_every_fragment_is_in_the_top_n": sum(1 for o in cards_with_frag if all(frag_family(k, t) in top for k, t in frag[o]))}
    exact = collections.defaultdict(set)
    for o in gapc:
        for k, t in frag.get(o, []):
            exact[(k, re.sub(r"\d+", "N", t)[:70])].add(o)
    sole = {key: [o for o in v if {(k, re.sub(r"\d+", "N", t)[:70]) for k, t in frag[o]} == {key}] for key, v in exact.items()}
    top10 = sorted(exact.items(), key=lambda kv: -len(kv[1]))[:10]
    ev["gap"] = {"cards": len(gapc), "gap_types": dict(gtype.most_common()), "failing_the_tests_or_holding_an_item_gap": dict(failing),
                 "second_causes_of_gap_cards": dict(secondary), "cards_with_a_single_gap_fragment": sum(1 for o in gapc if len(frag.get(o, [])) == 1),
                 "distinct_exact_fragments": len(exact), "distinct_fragment_families": len(ranked), "cards_with_a_fragment": len(cards_with_frag),
                 "unread_clause_cards": len(unread_cards),
                 "family_cover": cover, "top_families": [{"kind": k[0], "leading_words": k[1], "cards": len(v)} for k, v in ranked[:30]],
                 "top_gap_causes": [{"kind": k[0], "fragment": k[1], "cards": len(v), "sole_cause_cards": len(sole[k])} for k, v in top10]}

    tu = [o for o in pile if primary[o] == CAUSES[4]]
    leaves_by_ft = collections.defaultdict(list)
    for li in leaf_info.values():
        if li["n"] >= 5:
            leaves_by_ft[li["ftype"]].append((li, pairs_of_leaf(li)))
    blk = {o: [akey.get((r[1], r[2], r[3], r[4])) for r in rows_by[o] if r[7] in RARE] for o in tu}
    blk = {o: [j for j in v if j is not None] for o, v in blk.items()}
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
    allj = sorted({j for o in tu for j in blk[o]})
    r3 = dict(zip(allj, B.assign_rf_ref(Fref, [A[j]["f"] for j in allj], 3))) if allj else {}
    any3 = [o for o in tu if any(r3.get(j, ("x",))[0] != "x" for j in blk[o])]
    all3 = [o for o in tu if blk[o] and all(r3.get(j, ("x",))[0] != "x" for j in blk[o])]
    ev["below_minimum"] = {"cards": len(tu), "blocking_abilities": len(allj), "best_similarity": dict(bins),
                           "top_nearest_leaves": collections.Counter(leaf_name.get(best[o][1], best[o][1]) for o in tu if best[o]).most_common(10),
                           "cards_with_an_ability_placing_at_3": len(any3), "cards_whose_every_blocking_ability_places_at_3": len(all3),
                           "abilities_placing_at_3_not_5": sum(1 for r in r3.values() if r[0] != "x")}

    cdx = [x for x in ex if x["why"] == "flagged"]
    sub = collections.defaultdict(collections.Counter)
    mov_clean, mov_gap = collections.defaultdict(set), collections.defaultdict(set)
    for x in cdx:
        k = (x["cd"].get("shape"), x["cd"].get("sub"))
        sub[k]["items"] += 1
        sub[k]["on_gap_cards" if x["kind"] == "gap" else "on_clean_cards"] += 1
        sub[k][x["res"].split(":")[0]] += 1
        if x["res"] == "placed":
            (mov_gap if x["kind"] == "gap" else mov_clean)[k].add(x["oid"])
    allclean = set().union(*mov_clean.values()) if mov_clean else set()
    allgap = set().union(*mov_gap.values()) if mov_gap else set()
    ev["dropped_condition"] = {"flagged_abilities_in_the_pile": len(cdx),
                               "would_place_in_an_unflagged_leaf": sum(1 for x in cdx if x["res"] == "placed"),
                               "would_reach_only_a_broad_leaf": sum(1 for x in cdx if x["res"] == "broad"),
                               "would_still_not_place": sum(1 for x in cdx if x["res"].startswith("unplaced")),
                               "pile_cards_on_clean_cards_that_would_move": len(allclean), "pile_gap_cards_that_would_have_an_ability_placing": len(allgap),
                               "by_sub_shape": [{"shape": k[0], "sub": k[1], **dict(v), "clean_cards_that_would_move": len(mov_clean[k]), "gap_cards_with_an_ability_that_would_place": len(mov_gap[k])}
                                                for k, v in sorted(sub.items(), key=lambda kv: -kv[1]["items"])]}

    tfx = [x for x in ex if x["why"] == "test_fail"]
    by_test = collections.defaultdict(collections.Counter)
    for x in tfx:
        by_test[x["test"]][x["res"].split(":")[0]] += 1
    mov_tests = {o for o in {x["oid"] for x in tfx if x["res"] == "placed"}}
    ev["gap_tests"] = {"abilities_failing_a_test": len(tfx), "if_the_test_were_dropped_they_would_match": {k: dict(v) for k, v in by_test.items()},
                       "gap_cards_in_the_pile_with_such_an_ability_matching_an_unflagged_leaf": len(mov_tests),
                       "note": "dropping a test is what the Spark Double pattern warns against: these are the cases the tests exist to keep out"}
    ev["unparsed_or_mistake"] = {"cards": pc[CAUSES[1]], "by_group": dict(collections.Counter(view[o][1] for o in pile if primary[o] == CAUSES[1]))}
    ev["modal_nosig"] = {"cards": pc[CAUSES[5]]}
    ev["no_effect"] = {"cards": pc[CAUSES[6]]}
    out["evidence"] = ev

    # ------------------------------------------------------------------ samples
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
            return nm, t[:110], "gap: " + fr, ""
        if c == CAUSES[2]:
            t, r = itemtext(o, lambda r: r[7] == "flagged_condition_drop")
            xx = ex_by_key.get((o, r[2], r[3])) if r else None
            wb = ("would match: " + leaf_name.get(xx["leaf"], xx["leaf"])) if xx and xx["res"] == "placed" else ("would only reach a broad leaf" if xx and xx["res"] == "broad" else "would still not place")
            return nm, t[:110], "dropped condition: " + (xx["cd"].get("sub") if xx else "?"), wb
        if c == CAUSES[3]:
            t, r = itemtext(o, lambda r: r[7] in GAPTEST)
            return nm, t[:110], r[7] if r else "", ""
        if c == CAUSES[4]:
            t, r = itemtext(o, lambda r: r[7] in RARE)
            b_ = best.get(o)
            return nm, t[:110], r[7] if r else "", ("nearest leaf %.2f: %s" % (b_[0], leaf_name.get(b_[1], b_[1]))) if b_ else "no leaf of that effect type"
        t, r = itemtext(o, lambda r: True)
        return nm, t[:110], view[o][1] + (" / " + r[7] if r else ""), ""
    samples = {}
    for c in CAUSES:
        pool = sorted(o for o in pile if primary[o] == c)
        if c == CAUSES[3]:
            pool = sorted(o for o in pile if CAUSES[3] in cs[o])          # cause 4 is never primary: sample the cards that have it
        pick = rnd.sample(pool, min(10, len(pool)))
        samples[c] = [dict(zip(("card", "ability_text", "reason", "would_be"), sample_row(o, c))) for o in pick]
    out["samples"] = samples

    # ------------------------------------------------------------------ 4. popularity
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
    out["popularity"] = {"field": "edhrec_rank (Scryfall oracle_cards export); lower is more popular", "by_cause": pop}

    # ------------------------------------------------------------------ 5. browse-only family subgroups, on paper
    fam_of = collections.defaultdict(list)
    for a in A:
        if a["oid"] in pset and not a["pre"] and a["f"]["fam"] in fam_keys:
            fam_of[a["oid"]].append((a["f"]["fam"], a["f"]["ftype"], a["text"]))
    for x in ex:
        if x["f"]["fam"] in fam_keys:
            fam_of[x["oid"]].append((x["f"]["fam"], x["f"]["ftype"], x["text"] or ""))
    has_fam = [o for o in pile if fam_of.get(o)]
    nofam = [o for o in pile if not fam_of.get(o)]
    multi, single = collections.Counter(), collections.Counter()
    ftmix = collections.defaultdict(collections.Counter)
    single_of = {}
    for o in has_fam:
        fams = collections.Counter(f for f, _, _ in fam_of[o])
        for f in fams:
            multi[f] += 1
        top_f = sorted(fams.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        single[top_f] += 1
        single_of[o] = top_f
        for f, ft, _ in set(fam_of[o]):
            ftmix[f][ft] += 1
    big3 = [f for f, _ in single.most_common(3)]
    fam_samples = {}
    for f in big3:
        pool = sorted(o for o in has_fam if single_of[o] == f)
        pick = rnd.sample(pool, min(20, len(pool)))
        fam_samples[f] = [{"card": L[o]["name"], "primary_cause": primary[o], "mapped_ability": next((t for ff, _, t in fam_of[o] if ff == f and t), "")[:130],
                           "effect_types": sorted({ft for ff, ft, _ in fam_of[o] if ff == f})} for o in pick]
    out["subgrouping"] = {"cards_in_pile": len(pile), "cards_with_a_family": len(has_fam), "cards_with_no_family": len(nofam),
                          "no_family_by_primary_cause": dict(collections.Counter(primary[o] for o in nofam)),
                          "cards_per_family_may_appear_in_several": multi.most_common(28), "cards_per_family_one_each": single.most_common(28),
                          "largest": big3, "effect_type_mix_of_the_largest": {f: ftmix[f].most_common(10) for f in big3}, "samples_of_the_largest": fam_samples}

    # ------------------------------------------------------------------ 6. fix sets, so overlap is measured
    fixMin3, fixCond, fixCondGap, fixTests = set(any3), allclean, allgap, mov_tests
    fixFam = set(has_fam)
    out["fix_sets"] = {"min3": len(fixMin3), "cond_clean_cards": len(fixCond), "cond_gap_cards": len(fixCondGap), "relax_gap_tests": len(fixTests),
                       "min3_and_cond": len(fixMin3 & fixCond), "min3_and_tests": len(fixMin3 & fixTests), "cond_and_tests": len((fixCond | fixCondGap) & fixTests),
                       "cond_gap_and_tests": len(fixCondGap & fixTests), "placement_fixes_union": len(fixMin3 | fixCond | fixCondGap | fixTests),
                       "placement_fixes_sum": len(fixMin3) + len(fixCond) + len(fixCondGap) + len(fixTests),
                       "browse_only_family_cards": len(fixFam), "family_cards_also_in_a_placement_fix": len(fixFam & (fixMin3 | fixCond | fixCondGap | fixTests))}
    with io.open(os.path.join(BUILD, "unorganized_breakdown_v3.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    write_md(out, tot)
    print(json.dumps({k: out[k] for k in ("recount", "causes", "fix_sets")}, indent=1, ensure_ascii=False)[:7000])


def fm(n):
    return format(n, ",") if isinstance(n, int) else str(n)


def write_md(o, tot):
    R, C, E, F = o["recount"], o["causes"], o["evidence"], o["fix_sets"]
    md = ['# "Not yet organized": breakdown by cause (v3, current build)', "",
          "Investigation only (`src/analyze_unorganized_breakdown_v3.py`, seed %d). Nothing was built, placed or changed; new files only. Every figure is **measured** unless it says **estimate**." % o["seed"], "",
          "## 1. Recount", "",
          "- Universe %s = %s grouped (%s precise + %s only in broad groups + %s keyword block + %s no abilities + %s replacement) + **%s not yet organized** + %s not cards. Reconciles: **%s**." % (
              fm(R["universe"]), fm(R["placed_total"]), fm(R["views"]["placed"]), fm(R["views"]["broad_only"]), fm(R["views"]["keyword_block"]), fm(R["views"]["no_abilities"]),
              fm(R["views"]["replacement_group"]), fm(R["pile"]), fm(R["views"]["not_a_card"]), R["reconciles"]),
          "- Groups in the pile: " + ", ".join("%s %s" % (k, fm(v)) for k, v in sorted(R["groups"].items(), key=lambda kv: -kv[1])) + ".",
          "- Headline: **%s of %s = %s%%** (basis: %s)." % (fm(R["headline"]["cards"]), fm(R["in_scope"]), R["headline"]["pct"], R["headline"]["basis"]),
          "- With broad groups: **%s = %s%%** (basis: %s). The archived view's 74.8%% is on a different basis." % (fm(R["with_broad"]["cards"]), R["with_broad"]["pct"], R["with_broad"]["basis"]), "",
          "## 2. Primary cause (fixed order) and overlap", "",
          "Gap cards always take cause 1 first, so **cause 4 is never primary**: it is counted as a second cause (and sampled from the cards that have it).", "",
          "| cause | primary | with a second or third cause | has this cause (any) |", "|---|---:|---:|---:|"]
    for c in CAUSES:
        md.append("| %s | %s | %s | %s |" % (c, fm(C["primary"][c]), fm(C["with_a_second_cause"][c]), fm(C["any_cause"][c])))
    md += ["", "Second causes behind each primary cause (cards):", ""]
    for c in CAUSES:
        m = C["second_cause_matrix"].get(c) or {}
        if m:
            md.append("- %s: " % c + ", ".join("%s %s" % (k, fm(v)) for k, v in sorted(m.items(), key=lambda kv: -kv[1])))
    md += ["", "Cards by number of causes: " + ", ".join("%s: %s" % (k, fm(v)) for k, v in sorted(C["cards_by_number_of_causes"].items(), key=lambda kv: int(kv[0]))), "",
           "## 3. Evidence per cause", "", "### Parser gap and gap-card abilities still unplaced (causes 1 and 4)", ""]
    g = E["gap"]
    md += ["- Cards: %s. Gap types: %s." % (fm(g["cards"]), "; ".join("%s %s" % (k, fm(v)) for k, v in g["gap_types"].items())),
           "- Why gap-card abilities are not placed (cards having at least one): %s." % ", ".join("%s %s" % (k, fm(v)) for k, v in g["failing_the_tests_or_holding_an_item_gap"].items()),
           "- Second causes of gap cards: %s. Cards with exactly one gap fragment: %s." % (", ".join("%s %s" % (k, fm(v)) for k, v in g["second_causes_of_gap_cards"].items()), fm(g["cards_with_a_single_gap_fragment"])),
           "- **Fragment families** (node type + the first two words): %s families cover %s cards that have a fragment (%s distinct exact fragments); %s of those cards have an unread clause." % (
               fm(g["distinct_fragment_families"]), fm(g["cards_with_a_fragment"]), fm(g["distinct_exact_fragments"]), fm(g["unread_clause_cards"])), "",
           "| top N families | cards with any fragment in them | cards whose every fragment is in them |", "|---:|---:|---:|"]
    for n, v in g["family_cover"].items():
        md.append("| %s | %s | %s |" % (n, fm(v["cards_with_any_fragment_in_the_top_n"]), fm(v["cards_whose_every_fragment_is_in_the_top_n"])))
    md += ["", "Largest families: " + "; ".join("%s \"%s\" (%s)" % (f["kind"], f["leading_words"], fm(f["cards"])) for f in g["top_families"][:20]) + ".", "",
           "Top 10 exact gap causes:", "", "| kind | fragment | cards | sole-cause cards |", "|---|---|---:|---:|"]
    for t in g["top_gap_causes"]:
        md.append("| %s | %s | %s | %s |" % (t["kind"], t["fragment"].replace("|", "/"), t["cards"], t["sole_cause_cards"]))
    bm = E["below_minimum"]
    md += ["", "### Below the 5-member minimum (cause 5)", "",
           "- Primary-cause cards %s, %s blocking abilities. Best similarity of a card's closest blocking ability to any leaf: %s." % (fm(bm["cards"]), fm(bm["blocking_abilities"]), ", ".join("%s %s" % (k, fm(v)) for k, v in bm["best_similarity"].items())),
           "- Nearest leaves: " + "; ".join("%s (%s)" % (n, c) for n, c in bm["top_nearest_leaves"]) + ".",
           "- At a minimum of 3 (measured, not built): **%s cards** have a blocking ability that would place; **%s** have every blocking ability placing; %s abilities have a leaf at 3 and not at 5." % (
               fm(bm["cards_with_an_ability_placing_at_3"]), fm(bm["cards_whose_every_blocking_ability_places_at_3"]), fm(bm["abilities_placing_at_3_not_5"])), ""]
    dc = E["dropped_condition"]
    md += ["### Dropped-condition holds (cause 3)", "",
           "- Flagged abilities in the pile: %s. If every sub-shape were fixed and they then matched like any clean ability: %s would place in an unflagged leaf, %s only in a broad leaf, %s still would not. **%s pile cards on clean cards would move**; %s gap cards would gain a placeable ability (they would still need the gap-card tests to pass). **Estimate**: the real figure is lower, because a kept condition makes the signature more specific." % (
               fm(dc["flagged_abilities_in_the_pile"]), fm(dc["would_place_in_an_unflagged_leaf"]), fm(dc["would_reach_only_a_broad_leaf"]), fm(dc["would_still_not_place"]),
               fm(dc["pile_cards_on_clean_cards_that_would_move"]), fm(dc["pile_gap_cards_that_would_have_an_ability_placing"])), "",
           "| shape | sub-shape | items | place (unflagged) | broad | still no | on gap cards | clean cards moved | gap cards with a placeable ability |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for s in dc["by_sub_shape"]:
        md.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (s["shape"], s["sub"], s["items"], s.get("placed", 0), s.get("broad", 0), s.get("unplaced", 0), s.get("on_gap_cards", 0),
                                                                    s["clean_cards_that_would_move"], s["gap_cards_with_an_ability_that_would_place"]))
    gt = E["gap_tests"]
    md += ["", "### Gap-card tests (what they hold back)", "",
           "- %s gap-card abilities fail a test. If a test were dropped they would match: %s. %s pile gap cards have such an ability matching an unflagged leaf. %s" % (
               fm(gt["abilities_failing_a_test"]), "; ".join("%s -> %s" % (k, ", ".join("%s %s" % (a, b) for a, b in v.items())) for k, v in gt["if_the_test_were_dropped_they_would_match"].items()),
               fm(gt["gap_cards_in_the_pile_with_such_an_ability_matching_an_unflagged_leaf"]), gt["note"]), "",
           "### Other causes", "", "- Unparsed or parse mistake: %s cards (%s). Modal / no signature: %s. No effect: %s." % (
               fm(E["unparsed_or_mistake"]["cards"]), ", ".join("%s %s" % (k, v) for k, v in E["unparsed_or_mistake"]["by_group"].items()), E["modal_nosig"]["cards"], E["no_effect"]["cards"]), "",
           "### Ten sample cards per cause (seeded)", ""]
    for c in CAUSES:
        sm = o["samples"][c]
        if not sm:
            continue
        md += ["**%s**" % c, "", "| card | ability text | reason | would sit in (measured) |", "|---|---|---|---|"]
        for s in sm:
            md.append("| %s | %s | %s | %s |" % (s["card"].replace("|", "/"), s["ability_text"].replace("|", "/").replace("\n", " "), s["reason"].replace("|", "/"), s["would_be"].replace("|", "/")))
        md.append("")
    P = o["popularity"]["by_cause"]
    md += ["## 4. Popularity", "", "Field: %s. Cumulative: a top-1,000 card is also in the top 3,000 and 10,000." % o["popularity"]["field"], "",
           "| primary cause | cards | top 1,000 | top 3,000 | top 10,000 | no rank |", "|---|---:|---:|---:|---:|---:|"]
    for c in CAUSES + ["all"]:
        p = P[c]
        md.append("| %s | %s | %s | %s | %s | %s |" % (c, fm(p["cards"]), p["top1000"], p["top3000"], p["top10000"], fm(p["no_rank"])))
    sg = o["subgrouping"]
    md += ["", "## 5. Browse-only family subgroups, on paper", "",
           "- Pile cards with at least one ability whose effect type maps to a family of the tree: **%s** of %s; **%s have no family** (%s)." % (
               fm(sg["cards_with_a_family"]), fm(sg["cards_in_pile"]), fm(sg["cards_with_no_family"]), ", ".join("%s %s" % (k, v) for k, v in sg["no_family_by_primary_cause"].items())),
           "- Per family if a card may appear under several: " + "; ".join("%s %s" % (k, fm(v)) for k, v in sg["cards_per_family_may_appear_in_several"][:14]) + ".",
           "- Per family if each card goes to its most common family: " + "; ".join("%s %s" % (k, fm(v)) for k, v in sg["cards_per_family_one_each"][:14]) + ".", ""]
    for f in sg["largest"]:
        md.append("- %s effect types: %s." % (f, ", ".join("%s %s" % (a, b) for a, b in sg["effect_type_mix_of_the_largest"][f])))
    md += ["", "Twenty cards read from each of the three largest:", ""]
    for f, lst in sg["samples_of_the_largest"].items():
        md += ["**%s**" % f, "", "| card | mapped ability | effect type | primary cause |", "|---|---|---|---|"]
        for s in lst:
            md.append("| %s | %s | %s | %s |" % (s["card"].replace("|", "/"), s["mapped_ability"].replace("|", "/").replace("\n", " "), ", ".join(s["effect_types"]), s["primary_cause"]))
        md.append("")
    md += ["## 6. Fix sets and their overlap (measured)", "",
           "- Minimum of 3: %s cards. Dropped-condition fixes: %s pile cards on clean cards, plus %s gap cards. Relaxing a gap-card test: %s gap cards. Pairwise overlaps: min3 and cond %s, min3 and tests %s, cond and tests %s. "
           "**Union of the four placement fixes: %s cards (the plain sum is %s).** Browse-only family subgroups: %s cards, of which %s are also in one of the placement fixes." % (
               fm(F["min3"]), fm(F["cond_clean_cards"]), fm(F["cond_gap_cards"]), fm(F["relax_gap_tests"]), F["min3_and_cond"], F["min3_and_tests"], F["cond_and_tests"],
               fm(F["placement_fixes_union"]), fm(F["placement_fixes_sum"]), fm(F["browse_only_family_cards"]), fm(F["family_cards_also_in_a_placement_fix"])), ""]
    with io.open(os.path.join(REPORTS, "unorganized-breakdown-v3.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
