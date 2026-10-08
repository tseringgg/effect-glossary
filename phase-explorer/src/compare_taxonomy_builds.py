#!/usr/bin/env python3
"""Compare two builds of the per-ability taxonomy (before / after a rule change). Measurement only.

    python src/compare_taxonomy_builds.py <dir with the older ability_taxonomy.json + _ledger.json> -> build/ability_taxonomy_round3_compare.json

Matches abilities by (face, bucket, index, mode). Reports: old leaves that split, new leaves under 5, abilities and cards that
move into or out of the headline, and (using the text of each ability, read for a sign) whether the sign leaves separate cleanly.
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")


def jl(path):
    return json.load(io.open(path, encoding="utf-8"))


def text_sign(t):
    m = re.findall(r"([+−-])(\d+|X)/([+−-])(\d+|X)", t or "")
    if not m:
        return None
    a, _, c, _ = m[0]
    s = lambda x: "-" if x in "-−" else "+"   # noqa: E731
    sa, sc = s(a), s(c)
    return sa if sa == sc else "+/-"


def main():
    old_dir = sys.argv[1]
    OT, OG = jl(os.path.join(old_dir, "ability_taxonomy.json")), jl(os.path.join(old_dir, "ability_taxonomy_ledger.json"))
    NT, NG = jl(os.path.join(BUILD, "ability_taxonomy.json")), jl(os.path.join(BUILD, "ability_taxonomy_ledger.json"))
    key = lambda r: (r[1], r[2], r[3], -1 if r[4] is None else r[4])   # noqa: E731
    orow = {key(r): r for r in OG["rows"]}
    nrow = {key(r): r for r in NG["rows"]}
    out = {"v": 1}
    # headline movement, per ability
    mv = collections.Counter()
    for k, o in orow.items():
        n = nrow.get(k)
        so, sn = o[6], n[6] if n else None
        mv["%s -> %s" % (so, sn)] += 1
    out["ability_state_moves"] = {k: v for k, v in sorted(mv.items(), key=lambda kv: -kv[1]) if k.split(" -> ")[0] != k.split(" -> ")[1]}
    out["ability_headline_before_after"] = [OT["meta"]["abilities_by_state"].get("placed"), NT["meta"]["abilities_by_state"].get("placed")]
    # leaves: split
    children = collections.defaultdict(set)
    for k, o in orow.items():
        n = nrow.get(k)
        if o[8] and n and n[8] and o[6] in ("placed", "placed_broad") and n[6] in ("placed", "placed_broad"):
            children[o[8]].add(n[8])
    split = {ol: cs for ol, cs in children.items() if len(cs) > 1}
    out["old_leaves_with_members"] = len(children)
    out["old_leaves_that_split"] = len(split)
    out["old_leaves_that_split_by_family"] = dict(collections.Counter(OT["leaves"][ol]["family"] for ol in split).most_common())
    out["new_leaves_from_splits"] = len({c for cs in split.values() for c in cs})
    kinds = collections.Counter()
    for ol in split:
        sig = OT["leaves"][ol]["sig"]
        kinds["power/toughness (sign)" if ("AddPower" in sig or "ftype=Pump" in sig) else "damage" if "Damage" in sig else "other"] += 1
    out["old_leaves_that_split_by_kind"] = dict(kinds)
    # new leaves under 5
    nl = NT["leaves"]
    out["new_leaves_total"] = NT["meta"]["leaves_all"]
    out["old_leaves_total"] = OT["meta"]["leaves_all"]
    out["new_leaves_ge5"] = NT["meta"]["leaves_ge_min"]
    out["old_leaves_ge5"] = OT["meta"]["leaves_ge_min"]
    # abilities that were in a >=5 leaf and now sit in a node under 5 (below_minimum_size) or went unplaced
    fell = [k for k, o in orow.items() if o[6] in ("placed", "placed_broad") and nrow[k][6] == "unplaced"]
    out["abilities_placed_before_now_unplaced"] = len(fell)
    out["abilities_placed_before_now_unplaced_by_reason"] = dict(collections.Counter(nrow[k][7] for k in fell))
    # cards
    out["cards_headline_before_after"] = [OT["totals"]["headline"]["cards"], NT["totals"]["headline"]["cards"]]
    out["cards_with_broad_before_after"] = [OT["totals"]["with_broad"]["cards"], NT["totals"]["with_broad"]["cards"]]
    out["views_before"], out["views_after"] = OT["totals"]["views"], NT["totals"]["views"]
    cm = collections.Counter()
    for oid, c in OG["cards"].items():
        n = NG["cards"][oid]
        if c["view"] != n["view"]:
            cm["%s -> %s" % (c["view"], n["view"])] += 1
    out["card_view_moves"] = dict(cm.most_common())
    out["flagged_leaves_before_after"] = [OT["meta"]["leaves_flagged"], NT["meta"]["leaves_flagged"]]
    out["flagged_abilities_before_after"] = [sum(l["abilities"] for l in OT["leaves"].values() if l["flags"]),
                                              sum(l["abilities"] for l in NT["leaves"].values() if l["flags"])]
    # sign leaves: does the leaf's sign class agree with the sign read from each member's text?
    agree = collections.Counter()
    sign_leaves = {k: l for k, l in nl.items() if " · sign=" in " " + l["sig"] and "sign=" in l["sig"]}
    for k, l in sign_leaves.items():
        cls = re.search(r"sign=([^ ·]+)", l["sig"]).group(1)
        for r in NG["rows"]:
            pass
    mem = collections.defaultdict(list)
    for r in NG["rows"]:
        if r[8] and r[6] in ("placed", "placed_broad"):
            mem[r[8]].append(r[5] or "")
    tot = collections.Counter()
    leafrows = []
    for k, l in sign_leaves.items():
        cls = re.search(r"sign=(\S+)", l["sig"]).group(1)
        ts = [text_sign(t) for t in mem[k]]
        ts = [t for t in ts if t]
        if not ts:
            continue
        cl2 = {"boost": "+", "shrink": "-", "mixed": "+/-", "unknown": "?", "zero": "0"}.get(cls, cls)
        ok = sum(1 for t in ts if t == cl2) if cl2 in ("+", "-", "+/-") else None
        for t in ts:
            tot[(cl2, t)] += 1
        leafrows.append({"leaf": k, "name": l["name"], "sign": cls, "n": len(ts), "agree": None if ok is None else round(ok / len(ts), 3)})
    out["sign_leaves"] = {"count": len(sign_leaves), "abilities": sum(l["abilities"] for l in sign_leaves.values())}
    out["sign_leaf_class_vs_text_sign"] = {"%s|%s" % k: v for k, v in sorted(tot.items())}
    dec = {c: sum(v for (cl, t), v in tot.items() if cl == c) for c in ("+", "-", "+/-")}
    right = {c: tot.get((c, c), 0) for c in ("+", "-", "+/-")}
    out["sign_leaf_text_agreement"] = {c: {"members_with_a_readable_sign": dec[c], "text_agrees": right[c],
                                            "share": round(right[c] / dec[c], 3) if dec[c] else None} for c in dec}
    out["sign_unknown_leaves_text_signs"] = {t: v for (cl, t), v in sorted(tot.items()) if cl == "?"}
    out["lowest_agreement_leaves"] = sorted([r for r in leafrows if r["agree"] is not None and r["n"] >= 8], key=lambda r: r["agree"])[:6]
    # the old big mixed leaf
    for ol, l in OT["leaves"].items():
        if l["name"].startswith("A creature gets") and l["abilities"] > 400:
            dist = collections.Counter()
            for k, o in orow.items():
                if o[8] == ol and nrow[k][8]:
                    dist[(nl[nrow[k][8]]["name"], re.search(r"sign=(\S+)", nl[nrow[k][8]]["sig"]).group(1) if "sign=" in nl[nrow[k][8]]["sig"] else "-")] += 1
            out["old_big_creature_pump_leaf"] = {"name": l["name"], "abilities": l["abilities"],
                                                 "now_in": [[n, s, c] for (n, s), c in dist.most_common(8)]}
    with io.open(os.path.join(BUILD, "ability_taxonomy_round3_compare.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
