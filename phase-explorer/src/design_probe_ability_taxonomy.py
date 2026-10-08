#!/usr/bin/env python3
"""Design measurements for the per-ability taxonomy as the main view -- investigation only.

    python src/design_probe_ability_taxonomy.py   # -> build/ability_taxonomy_design_probe.json

Builds nothing that a page reads. Reuses src/probe2_signature_taxonomy.py's fields2(), flag_reasons() and rules
UNCHANGED, with one scope difference decided for the main view: leaves are built from CLEAN abilities on CLEAN cards
only. Gap-card abilities that pass the partial layer's same-line / continuation / no-text tests are then assigned
against those clean-built counts (they add nothing to a count) and are reported separately.

Measures: card inventory by how the new view would handle each card, replacement / prevention coverage against the
old signature layer, tree sizes at display thresholds 5 / 10 / 20, leaves per card, the text each placed ability can
show, naming workload.
"""
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe2_signature_taxonomy as p2  # noqa: E402
import probe_signature_taxonomy as pst  # noqa: E402

BUILD = p2.BUILD
MIN = 5


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def assign_rf_ref(Fref, Ftgt, mn):
    """probe 2's rarest-field-first backoff; counts and rarity come from Fref only, targets are Ftgt."""
    rar = collections.Counter()
    for f in Fref:
        if f["usable"]:
            for k in p2.DROPPABLE:
                rar[(f["ftype"], k, p2.val(f, k))] += 1
    counters = {}

    def count(D):
        if D not in counters:
            keep = [k for k in p2.CANON if k not in D]
            counters[D] = collections.Counter(tuple(p2.val(f, k) for k in ["ftype"] + keep) for f in Fref if f["usable"])
        return counters[D]
    out = []
    for f in Ftgt:
        if not f["usable"]:
            out.append(("x", "no_signature"))
            continue
        l2_empty = not any(p2.val(f, k) for k in p2.L2G)
        has_obj = p2.val(f, "obj") != ""
        D = frozenset()
        S = [k for k in p2.DROPPABLE if p2.val(f, k)]
        placed = None
        while True:
            Dk = tuple(sorted(D))
            keep = [k for k in p2.CANON if k not in D]
            if count(Dk)[tuple(p2.val(f, k) for k in ["ftype"] + keep)] >= mn:
                placed = (p2.level_of(f, keep), p2.sigstr(f, set(keep)))
                break
            cand = [k for k in S if k not in D and not (k == "obj" and l2_empty and has_obj)]
            if not cand:
                break
            drop = min(cand, key=lambda k: (rar[(f["ftype"], k, p2.val(f, k))], p2.DROP_PRIORITY.index(k)))
            D = D | {drop}
        out.append(placed or ("x", "rare_verb_parameter" if not l2_empty else ("rare_object" if has_obj else "rare_effect_type")))
    return out


def main():
    items, excl, AL = pst.population()
    items, gexcl = p2.gap_tests(items)
    F = [p2.fields2(x) for x in items]
    repl_block = {j for j in range(len(items)) if F[j]["ftype"].startswith("repl:")}
    clean_idx = [j for j, x in enumerate(items) if x["kind"] == "clean" and j not in repl_block]
    gap_idx = [j for j, x in enumerate(items) if x["kind"] == "gap" and j not in repl_block]
    Fc = [F[j] for j in clean_idx]
    Fg = [F[j] for j in gap_idx]
    A = {}
    for j, a in zip(clean_idx, assign_rf_ref(Fc, Fc, MIN)):
        A[j] = a
    for j, a in zip(gap_idx, assign_rf_ref(Fc, Fg, MIN)):
        A[j] = a
    # nodes: direct members come from CLEAN abilities only; gap abilities are measured against them
    mem = collections.defaultdict(list)
    for j in clean_idx:
        if A[j][0] != "x":
            mem[tuple(A[j])].append(j)
    flags = {}
    for lf in mem:
        parts = lf[1].split(" · ")
        ret = dict(p.split("=", 1) for p in parts[2:])
        fl = p2.flag_reasons(parts[1].split("=", 1)[1], ret)
        if fl:
            flags[lf] = fl
    out = {"v": 1, "scope": "clean abilities on clean cards define the leaves; gap-card abilities are assigned against them",
           "population": {"abilities": len(items), "clean": len(clean_idx), "gap_passing_tests": len(gap_idx),
                          "gap_test_exclusions": dict(gexcl)}}
    direct = {lf: len(v) for lf, v in mem.items()}
    placed_state = {}          # ability index -> 'headline' | 'flagged' | 'small' | reason
    for j in range(len(items)):
        if j in repl_block:
            placed_state[j] = "replacement_block"
            continue
        a = A[j]
        if a[0] == "x":
            placed_state[j] = a[1]
        else:
            lf = tuple(a)
            if direct.get(lf, 0) < MIN:
                placed_state[j] = "below_minimum_size"
            elif lf in flags:
                placed_state[j] = "flagged_generic"
            else:
                placed_state[j] = "headline"
    out["clean_ability_states"] = dict(collections.Counter(placed_state[j] for j in clean_idx))
    out["gap_ability_states"] = dict(collections.Counter(placed_state[j] for j in gap_idx))
    out["leaves"] = {"nodes": len(mem), "flagged_nodes": len(flags),
                     "flag_reasons": dict(collections.Counter(r for fl in flags.values() for r in fl)),
                     "nodes_ge5": sum(1 for v in direct.values() if v >= 5),
                     "unflagged_ge5": sum(1 for lf, v in direct.items() if v >= 5 and lf not in flags),
                     "unflagged_ge10": sum(1 for lf, v in direct.items() if v >= 10 and lf not in flags),
                     "flagged_ge10": sum(1 for lf, v in direct.items() if v >= 10 and lf in flags)}

    # ------------------------------------------------------------- card-level
    L = jl("ledger.json")["rows"]
    lookup = jl("lookup.json")["entries"]
    oldstate = {e[0]: e[3] for e in lookup}
    P = jl("placements.json")
    stages = P["recovered"]["stages"]
    sig = jl("signature_layer.json")
    abil_ledger_cards = AL["cards"]
    n_items = collections.Counter(row[0] for row in AL["rows"])        # all ability items per card
    by_card = collections.defaultdict(list)
    for j, x in enumerate(items):
        by_card[x["oid"]].append(j)

    def kind_of(oid):
        st = L[oid]["status"]
        if st == "missing_from_export":
            ss = {f["stage"] for f in stages.get(oid, [])}
            if "partial" in ss or "unmodelled_node" in ss:
                return "gap"
            if "unparsed" in ss:
                return "unparsed"
            return "clean"
        if st in pst.CLEAN:
            return "clean"
        if st in pst.GAPPY:
            return "gap"
        return st
    card_view = {}
    reasons = collections.Counter()
    for oid, r in L.items():
        old = oldstate.get(oid)
        if r["status"] == "out_of_scope":
            card_view[oid] = ("not_a_card", ""); continue
        if old == "k":
            card_view[oid] = ("keyword_block", ""); continue
        if old == "v":
            card_view[oid] = ("no_abilities", ""); continue
        if old == "g":
            card_view[oid] = ("replacement_block", ""); continue
        k = kind_of(oid)
        js = by_card.get(oid, [])
        clean_js = [j for j in js if items[j]["kind"] == "clean"]
        gap_js = [j for j in js if items[j]["kind"] == "gap"]
        if k == "clean":
            st = collections.Counter(placed_state[j] for j in clean_js)
            if st["headline"]:
                card_view[oid] = ("placed_by_ability", "")
            elif st["flagged_generic"]:
                card_view[oid] = ("broad_group_only", "")
            elif st["below_minimum_size"] or any(s.startswith("rare") or s == "no_signature" for s in st):
                card_view[oid] = ("unorganized", "too_unusual")
            elif st["replacement_block"] and not any(placed_state[j] not in ("replacement_block",) for j in clean_js):
                card_view[oid] = ("unorganized", "no_effect_to_group")
            elif n_items.get(oid, 0) > 0:
                card_view[oid] = ("unorganized", "text_may_be_lost")
            else:
                card_view[oid] = ("unorganized", "no_effect_to_group")
        elif k == "gap":
            st = collections.Counter(placed_state[j] for j in gap_js)
            card_view[oid] = ("unorganized", "gap")
            if st["headline"]:
                reasons["gap_cards_with_a_passing_headline_ability"] += 1
        elif k == "unparsed":
            card_view[oid] = ("unorganized", "not_parsed")
        elif k == "corrections_flagged":
            card_view[oid] = ("unorganized", "known_parse_mistake")
        else:
            card_view[oid] = ("unorganized", "other:" + str(k))
    cv = collections.Counter(v[0] for v in card_view.values())
    ur = collections.Counter(v[1] for v in card_view.values() if v[0] == "unorganized")
    out["inventory"] = {"universe": len(card_view), "by_view": dict(cv), "unorganized_by_reason": dict(ur),
                        "gap_cards_that_would_place_if_included": reasons["gap_cards_with_a_passing_headline_ability"],
                        "reconciles": sum(cv.values()) == len(card_view)}
    # old state x new view
    cross = collections.Counter((oldstate.get(o), v[0] + (":" + v[1] if v[1] else "")) for o, v in card_view.items())
    out["old_by_new"] = {"%s|%s" % k: n for k, n in sorted(cross.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))}
    # leaves per card (headline placed abilities)
    node_of = {}
    for j in range(len(items)):
        if placed_state[j] == "headline":
            node_of[j] = tuple(A[j])
    per_card = collections.defaultdict(set)
    for j, lf in node_of.items():
        if items[j]["kind"] == "clean":
            per_card[items[j]["oid"]].add(lf)
    out["placed_cards"] = len(per_card)
    out["placed_cards_any_headline_incl_other_views"] = len(per_card)
    # thresholds
    th = {}
    parent = lambda lf: (lf[1].split(" · ")[1],) + tuple(  # noqa: E731
        x for x in lf[1].split(" · ")[2:] if x.split("=")[0] in p2.L2G)
    for T in (5, 10, 20):
        vis = {lf for lf, v in direct.items() if v >= T and lf not in flags}
        ab_vis = sum(direct[lf] for lf in vis)
        ab_all = sum(v for lf, v in direct.items() if v >= MIN and lf not in flags)
        entries, vis_counts, roll_only = [], [], 0
        nodes_all = set()
        nodes_vis = set()
        for oid, lfs in per_card.items():
            v = [lf for lf in lfs if lf in vis]
            r = {parent(lf) for lf in lfs if lf not in vis}
            entries.append(len(v) + len(r))
            vis_counts.append(len(v))
            if not v:
                roll_only += 1
        for lf in (lf for lf, v in direct.items() if v >= MIN and lf not in flags):
            nodes_all.add(parent(lf))
        for lf in vis:
            nodes_vis.add(parent(lf))
        e = sorted(entries); vc = sorted(vis_counts)
        th[T] = {"visible_leaves": len(vis), "abilities_in_visible_leaves": ab_vis, "abilities_rolled_up": ab_all - ab_vis,
                 "effect_and_verb_nodes_with_a_visible_leaf": len(nodes_vis), "effect_and_verb_nodes_total": len(nodes_all),
                 "cards_with_a_visible_leaf": len(per_card) - roll_only, "cards_only_via_roll_up": roll_only,
                 "cards_placed": len(per_card),
                 "visible_leaves_per_card_mean": round(sum(vc) / len(vc), 3), "visible_leaves_per_card_max": vc[-1],
                 "entries_per_card_mean": round(sum(e) / len(e), 3), "entries_per_card_median": e[len(e) // 2],
                 "entries_per_card_p95": e[int(len(e) * 0.95)], "entries_per_card_max": e[-1],
                 "cards_with_5_or_more_entries": sum(1 for x in e if x >= 5)}
    out["thresholds"] = th
    fam_vis = {lf[1].split(" · ")[0].split("=", 1)[1] for lf, v in direct.items() if v >= 10 and lf not in flags}
    out["families_with_a_leaf_ge10"] = len(fam_vis)
    # size distribution
    sizes = sorted(direct.values(), reverse=True)
    out["size_hist_direct"] = {"%d-%d" % b: sum(1 for s in sizes if b[0] <= s <= b[1])
                               for b in [(1, 4), (5, 9), (10, 19), (20, 49), (50, 99), (100, 499), (500, 10 ** 6)]}
    out["unflagged_size_hist_ge5"] = {"%d-%d" % b: sum(1 for lf, s in direct.items() if lf not in flags and b[0] <= s <= b[1])
                                      for b in [(5, 9), (10, 19), (20, 49), (50, 99), (100, 499), (500, 10 ** 6)]}

    # ------------------------------------------------------------- replacement / prevention vs the old signature layer
    sf = sig["faces"]
    oid_of = {}
    for oid, r in L.items():
        for f in r["evidence"].get("faces", []):
            oid_of[f["id"]] = oid
    old_group = {}
    for fid, v in sf.items():
        if v.get("method") == "signature_rule":
            old_group[oid_of.get(fid, fid.split("/")[0])] = v.get("leaf")
    gcross = collections.defaultdict(collections.Counter)
    for oid, g in old_group.items():
        cvw = card_view.get(oid, ("?", ""))
        leafs = sorted({"%s (%d)" % (lf[1].split(" · ")[1], direct.get(lf, 0)) for lf in per_card.get(oid, [])})
        gcross[g]["cards"] += 1
        gcross[g]["placed_by_ability_now"] += cvw[0] == "placed_by_ability"
        gcross[g]["unorganized_now:" + cvw[1]] += cvw[0] == "unorganized"
    out["old_signature_layer_cards"] = len(old_group)
    out["old_signature_layer_by_group"] = {g: dict(c) for g, c in sorted(gcross.items(), key=lambda kv: str(kv[0]))}
    # which new leaves do the old layer's cards land in
    land = collections.Counter()
    for oid in old_group:
        for lf in per_card.get(oid, []):
            land[lf[1]] += 1
    out["old_signature_layer_cards_land_in"] = land.most_common(25)
    # all cards whose abilities include a replacement item: how many, how many placed
    repl_cards = {items[j]["oid"] for j in range(len(items)) if items[j]["b"] == "replacements"}
    out["cards_with_replacement_items"] = {"cards": len(repl_cards),
                                           "placed_by_ability": sum(1 for o in repl_cards if card_view[o][0] == "placed_by_ability")}
    bare_repl = collections.Counter()
    for j in clean_idx:
        f = F[j]
        if f["ftype"].startswith("repl:") and placed_state[j] == "headline":
            bare_repl[A[j][1]] += 1
    out["replacement_leaves_headline"] = bare_repl.most_common(20)
    # prevention / damage replacement items specifically
    dmg = [j for j in clean_idx if F[j]["ftype"] == "repl:DamageDone"]
    out["repl_DamageDone"] = {"items": len(dmg), "distinct_leaves": len({tuple(A[j]) for j in dmg}),
                              "states": dict(collections.Counter(placed_state[j] for j in dmg))}

    # ------------------------------------------------------------- display text
    chunks = {n: jl("chunks/%d.json" % n) for n in range(64)}
    rows = {r["id"]: r for r in jl("index.json")["rows"]}
    rec = P["recovered"]["chunk"]
    notext = collections.Counter()
    for j in node_of:
        x = items[j]
        t = (x["item"].get("description") or "").strip()
        if t:
            notext["has_text"] += 1
            continue
        e = chunks[rows[x["face"]]["ch"]][x["face"]] if x["face"] in rows else rec.get(x["face"])
        modal = e.get("modal") if e else None
        if x["b"] == "abilities" and modal and modal.get("mode_descriptions"):
            na = len(e.get("abilities") or [])
            nm = len(modal["mode_descriptions"])
            notext["modal_mode:descriptions_align" if na == nm else "modal_mode:descriptions_do_not_align"] += 1
        elif x["b"] == "abilities" and (x["item"].get("effect") or {}).get("type") in ("Attach",):
            notext["keyword_generated:equip/attach"] += 1
        elif x["b"] == "abilities" and not x["item"].get("cost") and x["item"].get("kind") == "Spell":
            notext["spell_no_text"] += 1
        else:
            notext["other_no_text:" + x["b"]] += 1
    out["headline_ability_text"] = dict(notext)
    # ------------------------------------------------------------- extra: discrepancy, overlaps, flagged display, names
    odd = [o for o in per_card if card_view[o][0] != "placed_by_ability"]
    out["placed_cards_not_in_placed_view"] = [(L[o]["name"], card_view[o]) for o in odd][:10]
    kwp = 0
    for o in per_card:
        if card_view[o][0] != "placed_by_ability":
            continue
        fid = items[by_card[o][0]]["face"]
        e = chunks[rows[fid]["ch"]][fid] if fid in rows else rec.get(fid)
        if e and e.get("keywords"):
            kwp += 1
    out["placed_cards_that_also_have_keywords"] = kwp
    # cards in any flagged leaf (>= 5) and the visible flagged leaves
    flagged_cards = set()
    for j in clean_idx:
        if placed_state[j] == "flagged_generic":
            flagged_cards.add(items[j]["oid"])
    out["cards_with_an_ability_in_a_flagged_leaf"] = len(flagged_cards)
    fvis = [(direct[lf], lf[1], flags[lf]) for lf in flags if direct[lf] >= 10]
    out["flagged_leaves_ge10"] = {"leaves": len(fvis), "abilities": sum(n for n, _, _ in fvis),
                                  "largest": sorted(fvis, reverse=True)[:8]}
    # naming workload at the display threshold
    CR701 = {"Destroy", "Sacrifice", "Discard", "Scry", "Surveil", "Mill", "Counter", "Tap", "Untap", "Attach", "Regenerate",
             "Proliferate", "Investigate", "Explore", "Amass", "Monstrosity", "Adapt", "Connive", "Populate", "Manifest",
             "ManifestDread", "Fight", "Goad", "Detain", "Transform", "Learn", "Seek", "Discover", "Bolster", "Incubate",
             "Suspect", "TimeTravel", "Double", "Shuffle", "SearchLibrary", "RevealHand", "RevealTop", "CopySpell", "CastFromZone",
             "Forage", "Collect", "ExchangeControl", "ExploreAll", "Token", "CopyTokenOf", "RollDie", "FlipCoin", "Conjure",
             "ChangeZone", "Bounce", "Draw", "GainLife", "LoseLife", "DealDamage", "Mana", "PutCounter", "RemoveCounter"}
    vis_all = [(lf, v) for lf, v in direct.items() if v >= 10]
    names = collections.Counter()
    bare_term = 0
    for lf, v in vis_all:
        ft = lf[1].split(" · ")[1].split("=", 1)[1]
        names["effect_type_is_a_rules_term" if ft in CR701 else ("static" if ft.startswith("static:") else "other_effect_type")] += 1
        if lf[1].count(" · ") == 1:
            bare_term += 1
    out["naming"] = {"leaves_ge10_unflagged": sum(1 for lf, v in vis_all if lf not in flags),
                     "leaves_ge10_flagged": sum(1 for lf, v in vis_all if lf in flags),
                     "nodes_with_a_visible_leaf": th[10]["effect_and_verb_nodes_with_a_visible_leaf"],
                     "nodes_total": th[10]["effect_and_verb_nodes_total"], "families": out["families_with_a_leaf_ge10"],
                     "leaves_by_effect_type_class": dict(names), "leaves_whose_whole_signature_is_just_the_effect_type": bare_term}
    # ledger: every ability row, one reason
    cd = {(h["oid"], h["bucket"], h["idx"]) for h in jl("condition_drops.json")}
    idx_of = {(x["face"], x["b"], x["i"]): j for j, x in enumerate(items)}
    rr = collections.Counter()
    for row in AL["rows"]:
        oid, face, b, i = row[0], row[1], row[2], row[3]
        j = idx_of.get((face, b, i))
        if j is not None:
            ps = placed_state[j]
            k = items[j]["kind"]
            if ps == "headline" and k == "gap":
                rr["gap_card_ability_held_out_in_v1 (would place)"] += 1
            elif k == "gap":
                rr["gap_card_ability_held_out_in_v1 (" + ps + ")"] += 1
            else:
                rr[ps] += 1
        else:
            if (oid, b, i) in cd:
                rr["flagged_by_condition_drop_detector"] += 1
            else:
                kd = kind_of(oid)
                if kd == "gap":
                    rr["gap_card_item_gap_or_failed_gap_tests"] += 1
                elif kd == "clean":
                    rr["item_holds_a_gap_node"] += 1
                else:
                    rr["card_not_in_scope:" + str(L[oid]["status"])] += 1
    out["ability_rows_by_reason"] = dict(sorted(rr.items(), key=lambda kv: -kv[1]))
    out["ability_rows_total"] = len(AL["rows"])
    modal_items = [j for j in range(len(items)) if F[j]["ftype"] == "Modal"]
    out["modal_placeholders"] = {"items": len(modal_items), "cards": len({items[j]["oid"] for j in modal_items}),
                                 "states": dict(collections.Counter(placed_state[j] for j in modal_items)),
                                 "cards_placed_only_via_a_placeholder": sum(
                                     1 for o in {items[j]["oid"] for j in modal_items}
                                     if per_card.get(o) and all("ftype=Modal" in lf[1] for lf in per_card[o]))}
    # inline modal placeholders: what would their modes do if each mode were read as an ability?
    exp_items, exp_owner = [], []
    for j in modal_items:
        ex, _e = pst.exec_and_effect(items[j]["b"], items[j]["item"])
        for m in (ex.get("mode_abilities") or []):
            if isinstance(m, dict):
                exp_items.append({"b": "abilities", "item": m})
                exp_owner.append(j)
    Fm = [p2.fields2(x) for x in exp_items]
    Am = assign_rf_ref(Fc, Fm, MIN)
    ms = collections.Counter()
    gain = collections.defaultdict(list)
    for j, a, f in zip(exp_owner, Am, Fm):
        if a[0] == "x":
            ms["unplaced:" + a[1]] += 1
        else:
            lf = tuple(a)
            st = "headline" if (direct.get(lf, 0) >= MIN and lf not in flags) else ("flagged_generic" if lf in flags else "below_minimum_size")
            ms[st] += 1
            if st == "headline":
                gain[items[j]["oid"]].append(a[1])
    out["modal_expansion"] = {"mode_abilities": len(exp_items), "by_state": dict(ms),
                              "cards_with_a_placeable_mode": len(gain),
                              "of_those_not_otherwise_placed": sum(1 for o in gain if card_view[o][0] != "placed_by_ability")}
    # tree excerpt + family sizes
    fam_stats = collections.defaultdict(lambda: [0, 0, 0])
    tree = collections.defaultdict(lambda: collections.defaultdict(list))
    for lf, v in direct.items():
        if v < MIN:
            continue
        fam = lf[1].split(" · ")[0].split("=", 1)[1]
        fam_stats[fam][0] += 1 if v >= 10 else 0
        fam_stats[fam][1] += v
        fam_stats[fam][2] += 1 if lf in flags else 0
        tree[fam][parent(lf)].append((v, lf[1], lf in flags))
    out["families"] = {f: {"visible_leaves": a, "abilities": b, "flagged_leaves": c} for f, (a, b, c) in sorted(fam_stats.items())}
    exc = {}
    for fam in ("Destroy", "Library"):
        nodes = []
        for nd, lv_ in sorted(tree[fam].items(), key=lambda kv: -sum(x[0] for x in kv[1])):
            nodes.append({"node": " ".join(str(x) for x in nd), "abilities": sum(x[0] for x in lv_),
                          "leaves_ge10": [(n, sg.split(" · ", 2)[2] if sg.count(" · ") > 1 else "(bare)", fl) for n, sg, fl in sorted(lv_, reverse=True) if n >= 10][:6],
                          "rolled_up_leaves": sum(1 for x in lv_ if x[0] < 10), "rolled_up_abilities": sum(x[0] for x in lv_ if x[0] < 10)})
        exc[fam] = nodes[:6]
    out["tree_excerpt"] = exc
    # named lookups
    import re as _re
    fold = lambda t: _re.sub(r"[^a-z0-9 ]+", "", t.lower())   # noqa: E731
    want = ["Armageddon", "Ravages of War", "Death Cloud", "Global Ruin", "Shuri, Wakandan Inventor", "Mulldrifter",
            "Spark Double", "Lightning Bolt", "Storm Crow", "Yargle, Glutton of Urborg", "Grizzly Bears",
            "Jeska, Thrice Reborn", "Treasure", "Akoum"]
    ent = {fold(e[1]): e for e in lookup}
    lk = {}
    for n in want:
        e = ent.get(fold(n)) or next((x for x in lookup if fold(n).split(",")[0] in fold(x[1])), None)
        if not e:
            lk[n] = None
            continue
        o = e[0]
        lk[n] = {"name": e[1], "old_state": e[3], "old_group_or_leaf": e[4], "status": L[o]["status"],
                 "new_view": card_view[o], "leaves": sorted("%s (%d)" % (lf[1][:90], direct.get(lf, 0)) for lf in per_card.get(o, []))}
    out["lookup_preview"] = lk
    with io.open(os.path.join(BUILD, "ability_taxonomy_design_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=1, default=list))
    print(json.dumps({k: out[k] for k in ("population", "clean_ability_states", "gap_ability_states", "leaves", "inventory",
                                          "thresholds", "headline_ability_text")}, indent=1, default=list))


if __name__ == "__main__":
    main()
