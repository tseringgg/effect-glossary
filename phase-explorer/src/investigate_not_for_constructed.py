#!/usr/bin/env python3
"""Part 1a: what making the not-for-constructed cards out_of_scope would do. Investigation only; builds, places and changes nothing.

    python src/investigate_not_for_constructed.py   # -> build/not_for_constructed_investigation.json, reports/not-for-constructed-investigation.md

Hand-check seed 20261014 (declared before any computation): 20 flagged cards and 20 unflagged "odd" cards, drawn from fixed pools:
  flagged   every in-scope card in build/card_flags.json
  odd       in-scope cards NOT flagged that either (a) have at least one printing that is silver-border / acorn / playtest / funny-set /
            memorabilia but also an ordinary printing, or (b) are legal in no format and first printed at least 12 months ago
The leaf-membership simulation re-runs the build in memory with the flagged cards treated like the "A-" cards (out of scope); nothing is written.
"""
import collections
import contextlib
import gzip
import io
import json
import os
import random
import sys
import types
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_card_flags as BCF  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
DATA = os.path.join(HERE, "data")
REPORTS = os.path.join(HERE, "reports")
SEED = 20261014
TODAY = "2026-10-09"


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s.casefold()) if not unicodedata.combining(c)).strip()


def run_build(excluded=None):
    """build_ability_taxonomy.main() in memory. `excluded`: oracle ids treated as out of scope (like the A- cards). Writes nothing."""
    src = io.open(os.path.join(HERE, "src", "build_ability_taxonomy.py"), encoding="utf-8").read()
    # the build extends probe 2's field lists at import time; running it twice in one process must not extend them twice
    old = 'p2.L2G = tuple(p2.L2G) + ("sign", "recip")'
    assert src.count(old) == 1
    src = src.replace(old, 'p2.L2G = tuple(k for k in p2.L2G if k not in ("sign", "recip")) + ("sign", "recip")')
    if excluded:
        assert src.count("    ASIDE = ALCH\n") == 1
        src = src.replace("    ASIDE = ALCH\n", "    ASIDE = ALCH | EXTRA_ASIDE\n")
    mod = types.ModuleType("B_sim")
    mod.__file__ = os.path.join(HERE, "src", "build_ability_taxonomy.py")
    mod.__dict__["EXTRA_ASIDE"] = set(excluded or [])
    exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    mod.dump = lambda *a, **k: None
    with contextlib.redirect_stdout(io.StringIO()):
        return mod.main()


def main():
    rnd = random.Random(SEED)
    S0 = run_build()
    view, L, cards, A = S0["view"], S0["L"], S0["cards"], S0["A"]
    FL = jl("card_flags.json")
    flags = FL["cards"]
    F = sorted(o for o in cards if o in flags)                 # flagged and in the card set
    out = {"seed": SEED, "rule": FL["rule"]}

    # ------------------------------------------------------------ counts
    out["flagged_in_card_set"] = len(F)
    out["flagged_in_whole_catalogue"] = len(flags)
    out["by_reason_in_card_set"] = dict(collections.Counter(flags[o] for o in F))
    out["by_reason_in_whole_catalogue"] = dict(collections.Counter(flags.values()))
    out["by_current_view"] = dict(collections.Counter(view[o][0] for o in F))
    out["unorganized_by_group"] = dict(collections.Counter(view[o][1] for o in F if view[o][0] == "unorganized"))
    out["currently_placed_in"] = {"leaf_precise": sum(1 for o in F if view[o][0] == "placed"), "leaf_broad_only": sum(1 for o in F if view[o][0] == "broad_only"),
                                  "keyword_block": sum(1 for o in F if view[o][0] == "keyword_block"), "replacement_block": sum(1 for o in F if view[o][0] == "replacement_group"),
                                  "no_abilities": sum(1 for o in F if view[o][0] == "no_abilities")}

    # ------------------------------------------------------------ printings (one pass over every printing)
    ours = set(L)
    pr = collections.defaultdict(list)
    with gzip.open(os.path.join(DATA, "scryfall-default-cards.jsonl.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            if o.get("oracle_id") in ours:
                pr[o["oracle_id"]].append(o)

    # ------------------------------------------------------------ name collisions
    byname = collections.defaultdict(set)
    for oid, r in L.items():
        names = {r["name"]} | {x for x in (r["name"] or "").split(" // ")}
        for f in (r.get("evidence") or {}).get("faces", []):
            if f.get("name"):
                names.add(f["name"])
        for n in names:
            byname[fold(n)].add(oid)
    coll = []
    inset = set(cards)
    for n, oids in byname.items():
        fl = sorted(o for o in oids if o in flags and o in inset)
        if fl and len(oids) > 1:
            for o in fl:
                others = sorted(oids - {o})
                coll.append({"name": n, "flagged": {"oracle_id": o, "name": L[o]["name"], "reason": flags[o]},
                             "other_entries": [{"oracle_id": x, "name": L[x]["name"], "in_card_set": x in inset, "flagged": x in flags, "view": view[x][0]} for x in others]})
    out["name_collisions"] = coll
    out["name_collisions_with_an_unflagged_card_in_the_set"] = [c for c in coll if any(x["in_card_set"] and not x["flagged"] for x in c["other_entries"])]
    out["name_collisions_with_only_non_cards_or_flagged_cards"] = len(coll) - len(out["name_collisions_with_an_unflagged_card_in_the_set"])

    # ------------------------------------------------------------ hand-check samples
    def card_facts(o):
        v = pr.get(o, [])
        leg = [k for k, x in (v[0]["legalities"].items() if v else []) if x != "not_legal"]
        return {"oracle_id": o, "name": L[o]["name"], "type": cards[o]["ty"], "text": cards[o]["t"].replace("\n", " / ")[:170], "view": view[o][0],
                "printings": len(v), "sets": sorted({x["set"] + ":" + x["set_type"] for x in v})[:8], "borders": sorted({x["border_color"] for x in v}),
                "stamps": sorted({x.get("security_stamp") or "-" for x in v}), "promo_types": sorted({t for x in v for t in (x.get("promo_types") or [])})[:6],
                "legal_in": len(leg), "first_printed": min((x["released_at"] for x in v), default="")}
    odd = []
    for o in sorted(cards):
        if o in flags:
            continue
        v = pr.get(o, [])
        if not v:
            continue
        nonc = lambda x: x.get("border_color") == "silver" or x.get("security_stamp") == "acorn" or "playtest" in (x.get("promo_types") or []) or x.get("set_type") in ("funny", "memorabilia")   # noqa: E731
        mixed = any(nonc(x) for x in v)
        nolegal = all(t == "not_legal" for t in v[0]["legalities"].values()) and min(x["released_at"] for x in v) <= "2025-10-09"
        if mixed or nolegal:
            odd.append((o, "mixed printings" if mixed else "legal in no format, first printed a year ago"))
    out["hand_check"] = {"flagged_pool": len(F), "odd_pool": len(odd),
                         "flagged": [card_facts(o) for o in rnd.sample(F, 20)],
                         "odd": [dict(card_facts(o), why_odd=w) for o, w in rnd.sample(odd, 20)]}

    # ------------------------------------------------------------ what excluding them does to the leaves (in-memory re-run; nothing written)
    S1 = run_build(excluded=set(F))
    li0 = {li["id"]: li for li in S0["leaf_info"].values()}
    li1 = {li["id"]: li for li in S1["leaf_info"].values()}
    t0, t1 = S0["tax"], S1["tax"]
    L0, L1 = t0["leaves"], t1["leaves"]
    key0 = {(a["face"], a["b"], a["i"], a["mode"]): a for a in S0["A"]}
    changed_assign = 0
    moved = []
    for a in S1["A"]:
        b = key0.get((a["face"], a["b"], a["i"], a["mode"]))
        if b is not None and a.get("leaf") != b.get("leaf"):
            changed_assign += 1
            moved.append((a["oid"], b.get("leaf"), a.get("leaf")))
    lost = [(lid, L0[lid]["abilities"], L1.get(lid, {}).get("abilities", 0)) for lid in L0 if L1.get(lid, {}).get("abilities", 0) != L0[lid]["abilities"]]
    out["leaf_effect"] = {
        "leaves_now": len(L0), "leaves_after": len(L1),
        "leaves_that_disappear_below_the_5_minimum": sorted(set(L0) - set(L1)).__len__(),
        "leaves_whose_size_changes": len(lost),
        "leaves_that_cross_below_the_display_threshold_10": sum(1 for lid, n0, n1 in lost if n0 >= 10 and n1 < 10 and lid in L1),
        "leaves_in_new_build_not_in_old": len(set(L1) - set(L0)),
        "abilities_of_unflagged_cards_whose_leaf_changes": changed_assign,
        "cards_of_those_abilities": len({m[0] for m in moved}),
        "views_now": dict(collections.Counter(v[0] for v in S0["view"].values())),
        "views_after": dict(collections.Counter(v[0] for v in S1["view"].values())),
        "totals_now": {k: t0["totals"][k] for k in ("in_scope", "not_cards", "headline", "with_broad", "not_yet_organized")},
        "totals_after": {k: t1["totals"][k] for k in ("in_scope", "not_cards", "headline", "with_broad", "not_yet_organized")},
        "flags_changed": sum(1 for lid in L0 if lid in L1 and bool(L0[lid]["flags"]) != bool(L1[lid]["flags"])),
        "names_changed": sum(1 for lid in L0 if lid in L1 and L0[lid]["name"] != L1[lid]["name"]),
        "reconciles_after": all(t1["checks"].values())}
    out["leaf_effect"]["examples_of_leaves_that_shrink_most"] = [{"leaf": L0[lid]["name"], "before": n0, "after": n1} for lid, n0, n1 in sorted(lost, key=lambda x: x[2] - x[1])[:8]]
    out["leaf_effect"]["leaves_that_disappear_names"] = [L0[lid]["name"] for lid in sorted(set(L0) - set(L1))][:10]
    with io.open(os.path.join(BUILD, "not_for_constructed_investigation.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    keys = ("flagged_in_card_set", "flagged_in_whole_catalogue", "by_reason_in_card_set", "by_reason_in_whole_catalogue", "by_current_view", "unorganized_by_group", "currently_placed_in", "leaf_effect")
    print(json.dumps({k: out[k] for k in keys}, indent=1, ensure_ascii=False))
    print("name collisions: flagged cards of the set sharing a name with another entry:", len(coll), "| with an UNFLAGGED card of the set:", len(out["name_collisions_with_an_unflagged_card_in_the_set"]))


if __name__ == "__main__":
    main()
