#!/usr/bin/env python3
"""Numbers for reports/ability-taxonomy-report.md. Reads the built taxonomy and the archived view; changes nothing.

    python src/report_ability_taxonomy.py   # -> build/ability_taxonomy_report.json
"""
import collections
import io
import json
import os
import random
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
SEED = 7


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def sign_of(t):
    m = re.findall(r"([+−-])(\d+|X)/([+−-])(\d+|X)", t)
    if not m:
        return None
    a, _, c, _ = m[0]
    return ("-" if a in "-−" else "+") + ("-" if c in "-−" else "+")


def main():
    T, G = jl("ability_taxonomy.json"), jl("ability_taxonomy_ledger.json")
    L = T["leaves"]
    old = {e[0]: e for e in jl("lookup.json")["entries"]}
    out = {"v": 1}
    cards = G["cards"]
    pc = [len(c["leaves"]) for c in cards.values() if c["view"] == "placed"]
    ent = []
    for c in cards.values():
        if c["view"] != "placed":
            continue
        vis = {l for l in c["leaves"] if L[l]["visible"]}
        roll = {L[l]["node"] for l in c["leaves"] if not L[l]["visible"]}
        ent.append(len(vis) + len(roll))
    out["leaves_per_placed_card"] = {"leaves_mean": round(sum(pc) / len(pc), 3), "leaves_max": max(pc), "entries_at_threshold_10_mean": round(sum(ent) / len(ent), 3),
                                     "entries_max": max(ent), "cards_in_5_or_more_leaves": sum(1 for x in pc if x >= 5)}
    # flagged leaves by reason
    fr = collections.defaultdict(lambda: [0, 0])
    for l in L.values():
        for f in l["flags"]:
            fr[f][0] += 1
            fr[f][1] += l["abilities"]
    out["flag_reasons_leaves_abilities"] = {k: v for k, v in sorted(fr.items())}
    out["flagged_leaves"] = {"all": sum(1 for l in L.values() if l["flags"]), "visible": sum(1 for l in L.values() if l["flags"] and l["visible"]),
                             "abilities": sum(l["abilities"] for l in L.values() if l["flags"])}
    # alternative to the sign flag: flag only leaves whose members measurably split (>= 20% minority sign)
    mem = collections.defaultdict(list)
    for r in G["rows"]:
        if r[6] in ("placed", "placed_broad") and r[8]:
            mem[r[8]].append(r[5] or "")
    SIGN = "sign of the power/toughness change is not recorded"
    only_sign = [k for k, l in L.items() if l["flags"] == [SIGN]]
    tot = split = 0
    for k in only_sign:
        ts = [sign_of(t) for t in mem[k]]
        ts = [t for t in ts if t]
        tot += L[k]["abilities"]
        if len(ts) >= 5:
            top = collections.Counter(ts).most_common(1)[0][1]
            if 1 - top / len(ts) >= 0.2:
                split += L[k]["abilities"]
    out["sign_flag_alternative"] = {"leaves_flagged_only_for_sign": len(only_sign), "abilities_in_them": tot,
                                    "abilities_in_those_whose_members_measurably_split": split,
                                    "abilities_in_those_that_are_overwhelmingly_one_sign": tot - split}
    # old leaves vs new leaves
    cl = jl("clusters.json")
    labels = cl["labels"]
    om = collections.defaultdict(list)
    for o, e in old.items():
        if e[3] == "c" and o in cards:
            om[e[4]].append(o)
    new_leaves = {o: {l for l in c["leaves"]} for o, c in cards.items() if c["view"] == "placed"}
    any_leaves = {o: set(c["leaves"]) | set(c["broad"]) for o, c in cards.items() if c["view"] in ("placed", "broad_only")}
    rng = random.Random(SEED)
    rows = []
    for ol, ms in om.items():
        if len(ms) < 10:
            continue
        lab = labels.get(str(ol), "")
        coherent = bool(re.search(r"\|tgt:\S+ \(100%\)", lab))
        placed = [m for m in ms if m in new_leaves]
        pairs = [(a, b) for i, a in enumerate(ms) for b in ms[i + 1:]]
        sm = pairs if len(pairs) <= 1500 else rng.sample(pairs, 1500)
        share = sum(1 for a, b in sm if new_leaves.get(a, set()) & new_leaves.get(b, set())) / len(sm)
        share_any = sum(1 for a, b in sm if any_leaves.get(a, set()) & any_leaves.get(b, set())) / len(sm)
        in_any = sum(1 for m in ms if m in any_leaves) / len(ms)
        rows.append({"old_leaf": ol, "cards": len(ms), "coherent_proxy": coherent, "still_placed": round(len(placed) / len(ms), 3),
                     "in_any_new_leaf_incl_broad": round(in_any, 3),
                     "pair_share_same_new_leaf": round(share, 3), "pair_share_incl_broad": round(share_any, 3),
                     "label": labels.get(str(ol), "")[:90]})
    coh = [r for r in rows if r["coherent_proxy"]]
    out["old_leaves_ge10_cards"] = len(rows)
    out["old_coherent_leaves_ge10"] = len(coh)
    out["old_coherent_leaves_pair_share_lt_0.3"] = sum(1 for r in coh if r["pair_share_same_new_leaf"] < 0.3)
    out["old_coherent_leaves_pair_share_incl_broad_lt_0.3"] = sum(1 for r in coh if r["pair_share_incl_broad"] < 0.3)
    out["old_coherent_leaves_wholly_flagged"] = sum(1 for r in coh if r["still_placed"] < 0.1 and r["in_any_new_leaf_incl_broad"] >= 0.7)
    out["old_coherent_leaves_median_pair_share_incl_broad"] = sorted(r["pair_share_incl_broad"] for r in coh)[len(coh) // 2]
    out["old_coherent_leaves_still_placed_lt_0.5"] = sum(1 for r in coh if r["still_placed"] < 0.5)
    out["worst_old_coherent_leaves"] = sorted([r for r in coh if r["in_any_new_leaf_incl_broad"] >= 0.5],
                                              key=lambda r: (r["pair_share_incl_broad"], -r["cards"]))[:12]
    out["old_coherent_leaves_that_really_fragment"] = sum(1 for r in coh if r["in_any_new_leaf_incl_broad"] >= 0.5 and r["pair_share_incl_broad"] < 0.3)
    out["lowest_still_placed"] = sorted(coh, key=lambda r: (r["still_placed"], -r["cards"]))[:8]
    out["old_leaves_median_pair_share"] = sorted(r["pair_share_same_new_leaf"] for r in rows)[len(rows) // 2]
    # cards placed before, not (headline) now, by new state
    notnow = collections.Counter()
    for o, c in cards.items():
        if old[o][3] in ("c", "p", "a", "k", "v", "g") and c["view"] not in ("placed", "keyword_block", "no_abilities", "replacement_group"):
            notnow[c["view"] + (":" + c["reason"] if c["reason"] else "")] += 1
    out["placed_before_not_headline_now"] = dict(notnow)
    out["placed_before_not_headline_now_total"] = sum(notnow.values())
    gain = collections.Counter()
    for o, c in cards.items():
        if old[o][3] == "u" and c["view"] in ("placed", "broad_only"):
            gain[c["view"]] += 1
    out["unplaced_before_placed_now"] = dict(gain)
    out["totals"] = T["totals"]
    out["meta"] = {k: v for k, v in T["meta"].items() if k != "rules"}
    with io.open(os.path.join(BUILD, "ability_taxonomy_report.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print(json.dumps({k: out[k] for k in ("leaves_per_placed_card", "flagged_leaves", "sign_flag_alternative", "old_coherent_leaves_ge10",
                                          "old_coherent_leaves_pair_share_lt_0.3", "old_coherent_leaves_pair_share_incl_broad_lt_0.3",
                                          "old_coherent_leaves_wholly_flagged", "old_coherent_leaves_that_really_fragment",
                                          "old_coherent_leaves_median_pair_share_incl_broad", "old_coherent_leaves_still_placed_lt_0.5",
                                          "old_leaves_median_pair_share", "placed_before_not_headline_now",
                                          "placed_before_not_headline_now_total", "unplaced_before_placed_now",
                                          "flag_reasons_leaves_abilities")}, indent=1, ensure_ascii=False))
    for r in out["worst_old_coherent_leaves"][:10]:
        print(r)


if __name__ == "__main__":
    main()
