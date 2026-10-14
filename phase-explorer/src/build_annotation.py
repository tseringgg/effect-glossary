#!/usr/bin/env python3
"""The condition-annotation layer: abilities held for a dropped condition (and, as a separate stratum, abilities held by the gap test) shown in the leaf or tentative group they would
belong in if the unread part were ignored, with the unread text on the row. TENTATIVE, FLAGGED, never counted in the precise, with-broad or with-tentative figure.

    python src/build_annotation.py        # -> build/annotation_placements.json, build/annotation_ledger.json   (about two minutes)

Method names in the data: `condition_unread` (the condition stratum) and `card_part_unread` (the gap-test stratum). Nothing here is read by the taxonomy build, the leaves, the loose
layer, the tentative layer, the headline or the reconciliation: an annotated card is still a "Not yet organized" card in the build; the page subtracts it from the pile and shows the
fourth figure (condition stratum) and, on its own line, the gap-test figure.

Rules (decided in review, 2026-10):
  * condition stratum candidate = an ability the dropped-condition detector holds, with text, whose leaf (condition ignored: `assign_rf_ref`, leaf of 5 or more) is unflagged or whose
    promoted tentative group exists. Abilities with no leaf, with a leaf in a group broader than it looks (the broad route), with no text, or with no condition word in the text are not annotated;
  * the shared-verb exclusion: if the leaf's key verb occurs only in the cost or in the "you may X" lead-in before an "If you do / When you do / If you don't / Unless you" sentence, not in
    the effect after it, the ability is not annotated (the leaf would name the lead-in: Akuta, Born of Ash);
  * a card is counted once: a card already tentative gains the badge row and no extra count; a card with abilities in both strata counts in the condition stratum;
  * gap-test stratum = cards held by the gap test only (reason 3 of build/remaining_cards.json) whose failed test is the continuation or same-line test; the ability is the one the test
    held; its leaf must be unflagged or a promoted tentative group (broad leaf, no leaf, no text: not annotated).
HOLD_CONDITION_ANNOTATION = True writes an empty condition stratum; HOLD_GAP_STRATUM = True an empty gap-test stratum; ANNOTATION_LAYER = False writes an empty layer.
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ability_taxonomy as B
import build_loose_groups as BL
import probe_annotation_extract as X
import probe_annotation_verbs as VB
import probe_remaining as PR

HERE = BL.HERE
BUILD = BL.BUILD
ANNOTATION_LAYER = True
HOLD_CONDITION_ANNOTATION = False
HOLD_GAP_STRATUM = False
METHOD_C, METHOD_G = "condition_unread", "card_part_unread"
LABEL_C = "Condition not read"
LABEL_G = "Card part not read"
NOTE_C = "This ability has a condition the tool did not read:"
TAIL = {0: "The condition may change what the ability does.", 1: "The condition may change what the ability does, or make it do something else instead.",
        2: "The condition may change what the ability does, even to the opposite."}
NOTE_G = "This ability was read, but another part of this card was not:"
TAIL_G = "The unread part is a different ability on the card; it does not change which group this ability is in."
BS = chr(92)
STRICT = re.compile(BS + "b(unless|if you (don't|do not|didn't|can't|cannot)|if it (doesn't|didn't)|if that (doesn't|didn't))" + BS + "b", re.I)
ANY = re.compile(BS + "b(unless|instead|otherwise|if you (don't|do not|didn't|can't|cannot)|if it (doesn't|didn't)|if that (doesn't|didn't))" + BS + "b", re.I)
PARTICIPLE = re.compile("[a-z]+ed" + BS + "b")


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def dump(name, obj):
    with io.open(os.path.join(BUILD, name), "w", encoding="utf-8", newline=chr(10)) as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def unself(text, name):
    """The tool writes the card's own name as ~ when the oracle line is not found verbatim; show the card's name instead (before the comma for a legendary name)."""
    if "~" not in text:
        return text
    return text.replace("~", name.split(" // ")[0].split(",")[0])


def main():
    argv, sys.argv = sys.argv, sys.argv[:1]
    items, raw, info, meta, S = PR.collect()
    sys.argv = argv
    A, leaf_info = S["A"], S["leaf_info"]
    T = jl("ability_taxonomy.json")
    tg = jl("tentative_placements.json")
    cards = jl("ability_taxonomy_cards.json")["cards"]
    tm = tg["meta"]
    fam_keys = {k for k, _ in meta["families"]}
    fam_name = {f["key"]: f["name"] for f in T["families"]}
    cd = {(h["oid"], h["bucket"], h["idx"]): h for h in jl("condition_drops.json")}
    ref = [j for j, a in enumerate(A) if a["kind"] == "clean" and not a["pre"]]
    Fref = [A[j]["f"] for j in ref]
    use_idx, keys, folded, fm, names, sizes, kind_of = BL.make_groups(items, raw, info, fam_keys)
    ab_groups = collections.defaultdict(list)
    for k in folded:
        for n in fm[k]:
            ab_groups[n].append(BL.gid_of(k))
    pile, tent = set(meta["pile"]), set(tg["by_card"])
    rem = jl("remaining_cards.json")["primary"]
    r3 = {o for o, v in rem.items() if v == 3}
    empty = not ANNOTATION_LAYER
    cond_sel = [] if (empty or HOLD_CONDITION_ANNOTATION) else [(n, it) for n, it in enumerate(items) if it["src"] == "flagged" and it["oid"] in pile and (it["text"] or "").strip()]
    gap_sel = [] if (empty or HOLD_GAP_STRATUM) else [(n, it) for n, it in enumerate(items) if it["src"] == "test_fail" and it["oid"] in r3 and (it["text"] or "").strip()
                                                      and it["reason"] in ("gap_card_continuation_gap", "gap_card_same_line_gap")]
    usable = [(n, it) for n, it in cond_sel + gap_sel if it["f"]["usable"] and it["f"]["fam"] in fam_keys]
    res = dict(zip([n for n, _ in usable], B.assign_rf_ref(Fref, [it["f"] for _, it in usable], 5)))

    def route(n):
        r = res.get(n)
        if r is not None and r[0] != "x":
            li = leaf_info.get(tuple(r))
            if li is not None and li["n"] >= 5:
                return ("broad leaf" if li["flags"] else "unflagged leaf"), li["id"]
        gs = [g for g in ab_groups.get(n, []) if g in tg["groups"]]
        if gs:
            return "tentative group", gs[0]
        return "none", ""

    def target(kind, tid):
        if kind == "unflagged leaf":
            l = T["leaves"][tid]
            return "l:" + tid, l["name"], l["family"]
        g = tg["groups"][tid]
        return "t:" + tid, g["name"], g["fam"]

    groups, by_card, ledger = {}, collections.defaultdict(list), []
    excl, excl_g = collections.Counter(), collections.Counter()

    def add(oid, it, kind, tid, strat, ability, clause, how, inv, shape, frag):
        key, name, fam = target(kind, tid)
        g = groups.setdefault(key, {"name": name.split(" " + chr(0x203a) + " ", 1)[-1], "full_name": name, "fam": fam, "kind": "leaf" if key[0] == "l" else "tentative group", "m": []})
        g["m"].append([oid, ability, clause, how, inv, shape, strat, frag])
        if key not in by_card[oid]:
            by_card[oid].append(key)
        why = "ability held for a dropped condition: " + shape if strat == "c" else "ability held by the gap test (" + it["reason"] + ")"
        ledger.append([oid, cards[oid]["n"], it["ref"][1], it["ref"][2], ability, name, METHOD_C if strat == "c" else METHOD_G, why, clause if strat == "c" else " | ".join(frag)])

    # ---------------------------------------------------------------- condition stratum
    for n, it in sorted(cond_sel, key=lambda x: (x[1]["oid"], x[1]["ref"][1], x[1]["ref"][2])):
        oid = it["oid"]
        kind, tid = route(n)
        if kind in ("none", "broad leaf"):
            excl["no leaf" if kind == "none" else "broad route (not annotated)"] += 1
            continue
        h = cd.get((oid, it["ref"][1], it["ref"][2])) or {}
        r = {"text": " ".join(it["text"].split()), "oid": oid, "clauses": h.get("clauses", [])}
        full, found = X.full_text(r, cards[oid])
        if not found and "~" not in r["text"]:
            excl["ability text not found in the card's oracle text"] += 1
            continue
        full = unself(full, cards[oid]["n"])
        ek, clause = X.extract(full, r["clauses"])
        if ek == "none":
            excl["no condition word in the text"] += 1
            continue
        clause, how = X.finish(full, ek, clause)
        leafname = T["leaves"][tid]["name"] if kind == "unflagged leaf" else tg["groups"][tid]["name"]
        v = VB.key_verb({"leaf": leafname})
        if v:
            cost, eff = VB.regions(full)
            eff = PARTICIPLE.sub(" ", eff)
            if v in cost and v not in eff:
                excl["shared-verb exclusion"] += 1
                continue
        inv = 2 if STRICT.search(clause) else (1 if ANY.search(full) else 0)
        add(oid, it, kind, tid, "c", full, clause, how, inv, h.get("shape", ""), [])
    # ---------------------------------------------------------------- gap-test stratum (one ability per card: best route, lowest index)
    unorg = jl("ability_taxonomy_unorganized.json")["groups"]
    frag = {}
    for g in unorg:
        for c in g["list"]:
            frag[c["c"]] = [t for _, t in (c.get("g") or [])]
    cond_cards = set(by_card)
    best = {}
    gap_cards_total = len({it["oid"] for _, it in gap_sel})
    for n, it in sorted(gap_sel, key=lambda x: (x[1]["oid"], x[0])):
        kind, tid = route(n)
        if kind in ("none", "broad leaf"):
            continue
        rk = 0 if kind == "unflagged leaf" else 1
        if it["oid"] not in best or rk < best[it["oid"]][0]:
            best[it["oid"]] = (rk, n, it, kind, tid)
    for oid, (rk, n, it, kind, tid) in sorted(best.items()):
        if oid in cond_cards:
            continue
        r = {"text": " ".join(it["text"].split()), "oid": oid}
        full, found = X.full_text(r, cards[oid])
        if not found and "~" not in r["text"]:
            excl_g["ability text not found in the card's oracle text (a rule the tool describes, e.g. a saga's lore counter)"] += 1
            continue
        full = unself(full, cards[oid]["n"])
        fr = []
        for t in frag.get(oid, []):
            t = " ".join(t.split())
            if t and t not in fr:
                fr.append(t[:200])
        how = "continuation" if it["reason"] == "gap_card_continuation_gap" else "same-line"
        add(oid, it, kind, tid, "g", full, "", how, 0, "", fr[:3])

    # ---------------------------------------------------------------- counts and headline
    def strat_cards(s):
        return {r[0] for g in groups.values() for r in g["m"] if r[6] == s}
    c_cards = strat_cards("c")
    g_cards = strat_cards("g") - c_cards
    new_c = {o for o in c_cards if o not in tent}
    new_g = {o for o in g_cards if o not in tent}
    wt = tm["headline"]["with_tentative"][0]
    n_in = tm["headline"]["in_scope"]
    pct = lambda x: round(100.0 * x / n_in, 1)
    fig4 = wt + len(new_c)
    fig5 = fig4 + len(new_g)
    pile_t = tm["still_unorganized"]
    head = {"in_scope": n_in, "precise": tm["headline"]["precise"], "with_broad": tm["headline"]["with_broad"], "with_tentative": tm["headline"]["with_tentative"],
            "with_annotation": [fig4, pct(fig4), "the with-tentative figure plus %s pile cards with an annotated ability (condition not read) and no tentative placement" % format(len(new_c), ",")],
            "with_gap_stratum": [fig5, pct(fig5), "the with-annotation figure plus %s pile cards whose only reading is an ability held by the gap test (card part not read); reported on its own line, never blended" % format(len(new_g), ",")]}
    fams = collections.OrderedDict((f["key"], {"key": f["key"], "name": fam_name[f["key"]], "groups": []}) for f in T["families"])
    for k, g in sorted(groups.items(), key=lambda kv: (-len({r[0] for r in kv[1]["m"]}), kv[0])):
        g["cards"] = len({r[0] for r in g["m"]})
        g["m"].sort(key=lambda r: (r[0], r[1]))
        fams[g["fam"]]["groups"].append(k)
    fam_list = []
    for f in fams.values():
        if f["groups"]:
            f["cards"] = len({r[0] for k in f["groups"] for r in groups[k]["m"]})
            fam_list.append(f)
    c_ab = sum(1 for g in groups.values() for r in g["m"] if r[6] == "c")
    g_ab = sum(1 for g in groups.values() for r in g["m"] if r[6] == "g")
    out = {"meta": {"enabled": bool(groups), "method": {"c": METHOD_C, "g": METHOD_G}, "labels": {"c": LABEL_C, "g": LABEL_G}, "note": {"c": NOTE_C, "g": NOTE_G, "tail": {str(k): v for k, v in TAIL.items()}, "tail_g": TAIL_G},
                    "cards": len(set(by_card)), "condition_cards": len(c_cards), "condition_cards_new": len(new_c), "condition_cards_already_tentative": len(c_cards) - len(new_c),
                    "gap_cards": len(g_cards), "gap_cards_new": len(new_g), "gap_cards_in_population": gap_cards_total, "condition_abilities": c_ab, "gap_abilities": g_ab,
                    "inversion": {"opposite": sum(1 for g in groups.values() for r in g["m"] if r[6] == "c" and r[4] == 2), "something_else": sum(1 for g in groups.values() for r in g["m"] if r[6] == "c" and r[4] == 1)},
                    "excluded_abilities": dict(excl), "excluded_gap_stratum_cards": dict(excl_g), "headline": head, "pile_before": tm["pile"], "still_unorganized_after_tentative": pile_t, "still_unorganized_after_annotation": pile_t - len(new_c),
                    "still_unorganized_after_gap_stratum": pile_t - len(new_c) - len(new_g), "tentative_cards": tm["cards"],
                    "reconciliation": {"placed_with_broad": head["with_broad"][0], "tentative": tm["cards"], "annotation": len(new_c), "unorganized": pile_t - len(new_c), "not_cards": 5738,
                                       "sum": head["with_broad"][0] + tm["cards"] + len(new_c) + pile_t - len(new_c) + 5738, "gap_stratum_separately": len(new_g)},
                    "rules": {"hold_condition_annotation": HOLD_CONDITION_ANNOTATION, "hold_gap_stratum": HOLD_GAP_STRATUM, "broad_route_annotated": False}},
           "families": fam_list, "groups": groups, "by_card": {o: v for o, v in sorted(by_card.items())}}
    dump("annotation_placements.json", out)
    dump("annotation_ledger.json", {"columns": ["oracle_id", "card", "bucket", "index", "ability text", "group", "method", "rests on", "unread text"], "rows": sorted(ledger)})
    m = out["meta"]
    print("annotated cards", m["cards"], "condition", m["condition_cards"], "(new %d, already tentative %d)" % (m["condition_cards_new"], m["condition_cards_already_tentative"]), "gap", m["gap_cards"], "(new %d)" % m["gap_cards_new"])
    print("abilities", c_ab, g_ab, "excluded", dict(excl), dict(excl_g), "inversion", m["inversion"])
    print("figures", head["with_tentative"][:2], head["with_annotation"][:2], head["with_gap_stratum"][:2], "pile", m["still_unorganized_after_annotation"], m["still_unorganized_after_gap_stratum"], "recon", m["reconciliation"]["sum"])


if __name__ == "__main__":
    main()
