#!/usr/bin/env python3
"""Probe (read-only): what a minimum of 3 for the finest signature level would give the Not-yet-organized pile. Builds nothing, places nothing, changes nothing.

    python src/probe_min3_leaves.py            # measure + draw the hand-check sample -> build/min3_probe.json, build/min3_probe_blind.json
    python src/probe_min3_leaves.py reveal     # after build/min3_probe_reads.json exists -> build/min3_probe_result.json

Seed 20261019, declared before any computation, draws (1) the 30 leaves of 3 to 4 members for the coherence hand check (members shown in a fixed shuffled order by the same
generator) and then (2) the 20 cards for the old-view check, from the same generator in that order.

The main tree keeps its 5-member leaves untouched. This recomputes the rarest-field-first backoff with a minimum of 3 (the same function, build_ability_taxonomy.assign_rf_ref)
over the same clean abilities, then asks, for each ability of the pile cards, which leaf of exactly 3 or 4 members it would land in. An ability with a leaf of 5 or more already
sits in the main tree (or is held for another reason) and is not counted as new. Abilities held for a dropped condition, and abilities with no ability text, are counted and
set aside: they are not eligible in this version.
"""
import collections
import contextlib
import io
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ability_taxonomy as B
import analyze_unorganized_breakdown_v3 as V3

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
SEED = 20261019
MIN3 = 3


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def cause_sets(pile, view, rows_by):
    out = {}
    for oid in pile:
        reasons = collections.Counter(r[7] for r in rows_by.get(oid, []))
        reason = view[oid][1]
        c = set()
        if reason == "gap" or reasons["item_gap"]:
            c.add(V3.CAUSES[0])
        if reason in ("not_parsed", "known_parse_mistake"):
            c.add(V3.CAUSES[1])
        if reasons["flagged_condition_drop"]:
            c.add(V3.CAUSES[2])
        if any(reasons[k] for k in V3.GAPTEST):
            c.add(V3.CAUSES[3])
        if any(reasons[k] for k in V3.RARE):
            c.add(V3.CAUSES[4])
        if reasons["modal"] or reasons["no_signature"] or reasons["no_family"]:
            c.add(V3.CAUSES[5])
        if reason == "no_effect_to_group":
            c.add(V3.CAUSES[6])
        out[oid] = next((x for x in V3.CAUSES if x in c), V3.CAUSES[7])
    return out


def measure():
    B.dump = lambda *a, **k: None
    with contextlib.redirect_stdout(io.StringIO()):
        S = B.main()
    A, view, rows, L, leaf_info, cards = S["A"], S["view"], S["rows"], S["L"], S["leaf_info"], S["cards"]
    pile = sorted(o for o, v in view.items() if v[0] == "unorganized")
    pset = set(pile)
    rows_by = collections.defaultdict(list)
    for r in rows:
        if r[0] in pset:
            rows_by[r[0]].append(r)
    cause = cause_sets(pile, view, rows_by)
    pile_group = {}
    for g in jl("ability_taxonomy_unorganized.json")["groups"]:
        for c in g["list"]:
            pile_group[c["c"]] = g["name"]
    testfail = {(r[1], r[2], r[3]): r[7] for r in rows if r[0] in pset and r[7] in V3.GAPTEST}
    ex = V3.held_items(pset, testfail)
    for x in ex:
        f = B.fields3({"b": x["b"], "item": x["item"]})
        if f["fam"] == "Other" and f["ftype"] in B.FAMILY_FIX:
            f["fam"] = B.FAMILY_FIX[f["ftype"]]
        x["f"] = f
    ref = [j for j, a in enumerate(A) if a["kind"] == "clean" and not a["pre"]]
    Fref = [A[j]["f"] for j in ref]
    rr = B.assign_rf_ref(Fref, Fref, MIN3)
    n3 = collections.Counter(tuple(r) for r in rr if r[0] != "x")
    members3 = collections.defaultdict(list)
    for j, r in zip(ref, rr):
        if r[0] != "x":
            members3[tuple(r)].append(j)
    # the items: every ability of a pile card that the tool knows about (the same population the loose groups use), once each
    items, seen = [], set()
    for a in A:
        if a["oid"] in pset and not a["pre"]:
            k = (a["face"], a["b"], a["i"], a["mode"])
            seen.add((a["face"], a["b"], a["i"]))
            items.append({"oid": a["oid"], "face": a["face"], "text": a["text"] or "", "src": "A", "reason": a["reason"], "f": a["f"], "kind": a["kind"]})
    dup = 0
    for x in ex:
        if (x["face"], x["b"], x["i"]) in seen and x["why"] != "flagged":
            dup += 1
        items.append({"oid": x["oid"], "face": x["face"], "text": x["text"] or "", "src": x["why"], "reason": x["test"] if x["why"] == "test_fail" else x["why"], "f": x["f"], "kind": x["kind"]})
    fam_keys = {f["key"] for f in S["tax"]["families"]}
    usable = [i for i in items if i["f"]["usable"] and i["f"]["fam"] in fam_keys]
    r3 = B.assign_rf_ref(Fref, [i["f"] for i in usable], MIN3)
    out = {"seed": SEED, "pile": len(pile), "abilities_seen": len(items), "usable": len(usable),
           "duplicates_between_A_and_held_lists": dup}
    # classify each usable ability
    cls = collections.Counter()
    landed = []          # eligible abilities that land in a new leaf of 3 or 4
    removed = collections.Counter()
    for it, r in zip(usable, r3):
        if r[0] == "x":
            cls["no leaf even at 3"] += 1
            continue
        n = n3.get(tuple(r), 0)
        if n < MIN3:
            cls["leaf has fewer than 3 members when formed"] += 1
            continue
        if n >= 5:
            cls["lands in a leaf of 5 or more (already a main-tree leaf)"] += 1
            continue
        cls["lands in a leaf of 3 or 4"] += 1
        it["leaf"] = list(r)
        it["leaf_n"] = n
        if it["src"] == "flagged":
            removed["held for a dropped condition"] += 1
        elif not (it["text"] or "").strip() or it["reason"] == "gap_card_no_text":
            removed["no ability text"] += 1
        else:
            landed.append(it)
    out["classes"] = dict(cls)
    out["removed_from_the_eligible_set"] = dict(removed)
    out["eligible_abilities_landing_in_3_4_leaves"] = len(landed)
    by_src = collections.Counter(i["src"] for i in landed)
    out["eligible_by_source"] = dict(by_src)
    # leaves
    leaves = {}
    for i in landed:
        k = tuple(i["leaf"])
        leaves.setdefault(k, []).append(i)
    # all new 3-4 leaves (formed by clean abilities), whether or not a pile ability is eligible in them
    all34 = {k: v for k, v in members3.items() if 3 <= len(v) <= 4}
    existing_ids = {li["id"] for li in leaf_info.values() if li["n"] >= 5}
    out["leaves_of_3_or_4_members_in_total"] = len(all34)
    out["leaves_of_3_or_4_with_an_eligible_pile_ability"] = len(leaves)
    out["leaves_size_split"] = dict(collections.Counter(len(members3[k]) for k in leaves))
    import hashlib
    # members of those leaves: all clean abilities assigned there
    def lid(k):
        return "m" + hashlib.sha1(k[1].encode("utf-8")).hexdigest()[:9]
    out["abilities_in_those_leaves"] = sum(len(members3[k]) for k in leaves)
    out["pile_abilities_in_those_leaves"] = len(landed)
    gain = collections.defaultdict(list)
    for i in landed:
        gain[i["oid"]].append(i)
    out["gaining_cards"] = sorted(gain)
    out["cards_gaining_a_leaf"] = len(gain)
    out["cards_gaining_by_cause"] = dict(collections.Counter(cause[o] for o in gain))
    out["cards_gaining_by_pile_group"] = dict(collections.Counter(pile_group[o] for o in gain))
    out["cards_in_pile_by_cause"] = dict(collections.Counter(cause.values()))
    # overlap with the loose groups
    lg = jl("loose_groups.json")
    loose_cards = set(lg["by_card"])
    out["gaining_cards_that_already_have_a_loose_group"] = sum(1 for o in gain if o in loose_cards)
    out["gaining_cards_with_no_loose_group"] = sum(1 for o in gain if o not in loose_cards)
    out["gaining_cards_in_the_unread_list"] = sum(1 for o in gain if o not in loose_cards)
    ur = {r[0] for r in jl("loose_unread.json")["rows"]}
    out["gaining_cards_in_the_unread_list"] = sum(1 for o in gain if o in ur)
    # old view
    old = {e[0]: e for e in jl("lookup.json")["entries"]}
    oldnames = jl("clusters.json")["names"]
    tu = [o for o in gain if pile_group[o] == "Parsed, but too unusual to group"]
    out["gaining_cards_in_too_unusual"] = len(tu)
    oc = collections.Counter(old[o][3] for o in tu)
    out["old_view_codes_of_those"] = dict(oc)
    placed_old = [o for o in tu if old[o][3] in ("c", "p", "a")]
    out["too_unusual_gaining_cards_the_old_view_placed"] = len(placed_old)
    # the sample
    rnd = random.Random(SEED)
    pool = sorted(leaves, key=lambda k: k[1])
    draw = rnd.sample(pool, min(30, len(pool)))
    blind, key = [], []
    for n, k in enumerate(draw, 1):
        mem = [A[j] for j in members3[k]]
        mem.sort(key=lambda a: (a["oid"], a["text"]))
        rnd.shuffle(mem)
        blind.append({"n": n, "members": [{"card": L[a["oid"]]["name"], "text": " ".join((a["text"] or "(no separate rules line)").split())[:200]} for a in mem]})
        key.append({"n": n, "leaf": lid(k), "sig": k[1], "size": len(members3[k]), "pile_cards": sorted({i["oid"] for i in leaves[k]}),
                    "members": [{"card": L[a["oid"]]["name"], "oid": a["oid"], "in_pile": a["oid"] in pset} for a in mem]})
    out["sample_pool"] = len(pool)
    # the 20 cards of the old-view check
    pick = rnd.sample(sorted(placed_old), min(20, len(placed_old)))
    ov = []
    for o in pick:
        e = old[o]
        oname = ("cluster: " + oldnames.get(str(e[4]), oldnames.get(e[4], str(e[4])))) if e[3] == "c" else "(%s)" % e[3]
        ov.append({"card": L[o]["name"], "oid": o, "old_code": e[3], "old_group": oname, "abilities": [i["text"][:160] for i in gain[o]], "new_sig": [i["leaf"][1] for i in gain[o]]})
    out["old_view_sample"] = ov
    out["leaf_list"] = [{"leaf": lid(k), "sig": k[1], "size": len(members3[k]), "pile_abilities": len(leaves[k]), "level": k[0]} for k in sorted(leaves, key=lambda k: (-len(members3[k]), k[1]))]
    with io.open(os.path.join(BUILD, "min3_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    with io.open(os.path.join(BUILD, "min3_probe_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "pool": len(pool), "leaves": blind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "min3_probe_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "leaves": key}, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("leaf_list", "old_view_sample")}, indent=1, ensure_ascii=False))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "reveal":
        return reveal()
    measure()


def reveal():
    reads = jl("min3_probe_reads.json")
    key = jl("min3_probe_key.json")
    res = {"leaves": [], "summary": collections.Counter()}
    for k in key["leaves"]:
        r = reads["leaves"][str(k["n"])]
        res["summary"][r["verdict"]] += 1
        res["leaves"].append({"n": k["n"], "leaf": k["leaf"], "sig": k["sig"], "size": k["size"], "read": r["read"], "verdict": r["verdict"]})
        print("%2d (%d) %s | read: %s | %s" % (k["n"], k["size"], k["sig"].encode("ascii", "replace").decode(), r["read"], r["verdict"]))
    n = sum(res["summary"].values())
    res["incoherent_pct"] = round(100.0 * res["summary"]["incoherent"] / n, 1)
    res["summary"] = dict(res["summary"])
    if "old_view" in reads:
        res["old_view"] = reads["old_view"]
    with io.open(os.path.join(BUILD, "min3_probe_result.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(res["summary"], res["incoherent_pct"])


if __name__ == "__main__":
    main()
