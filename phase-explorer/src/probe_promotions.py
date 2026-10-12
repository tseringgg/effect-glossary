#!/usr/bin/env python3
"""Part B probe (read-only): the candidates for the next tentative promotions (3 renamed groups, 30 catch-all sub-headings), the fresh re-read of the 2 sub-headings that read as loose,
and the card counts. Builds nothing, places nothing, changes nothing.

    LOOSE_CACHE=<pickle of BL.collect()> python src/probe_promotions.py draw     # -> build/promotion_probe.json, build/promotion_reread_blind.json
    python src/probe_promotions.py names                                          # -> the 20-name draw (seed 20261025) over the new names, after the names exist (build/promotion_names_blind.json)

Seeds, declared before any computation: 20261024 draws the 8 members re-read in each of the 2 loose sub-headings; 20261025 draws the 20 new names for the hand check against their members.
"""
import collections
import io
import json
import os
import pickle
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_loose_groups as BL
import build_tentative as BT
import probe_loose_groups_v2 as V

BUILD = BL.BUILD
SEED_REREAD, SEED_NAMES = 20261024, 20261025


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def load():
    cache = os.environ.get("LOOSE_CACHE")
    if cache and os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    return BL.collect()[:4]


def draw():
    items, raw, info, meta = load()
    fam_keys = {k for k, _ in meta["families"]}
    use_idx, keys, folded, fm, names, sizes, kind_of = BL.make_groups(items, raw, info, fam_keys)
    cards = jl("remaining_cards.json")
    key = jl("remaining_subheadings_key.json")
    reads = jl("remaining_reads.json")["subheadings"]
    promotable = []
    for s in key["subheadings"]:
        r = reads[str(s["n"])]
        if s["n"] in (14, 27, 33):
            continue
        if r["verdict"] != "incoherent" and s["eligible_cards"] >= 5 and s["textless_cards"] * 2 <= s["cards"]:
            promotable.append(s)
    out = {"candidates": {"renamed_groups": 3, "sub_headings": len(promotable)}}
    # re-read: the 2 loose sub-headings, 8 members each, fresh seed
    loose = [s for s in promotable if reads[str(s["n"])]["verdict"] == "loose"]
    rnd = random.Random(SEED_REREAD)
    gk = {BL.gid_of(k): k for k in folded}
    blind, rk = [], []
    for i, s in enumerate(sorted(loose, key=lambda s: s["sub"]), 1):
        k = gk[s["gid"]]
        ns = []
        for n in fm[k]:
            if not BT.eligible(items[n], True):
                continue
            v = V.field_values(items[n]["f"], n, info, raw)
            g = v["grant"]
            lab = V.CONT_WORDS.get(g, ("gives " + V.KWFIX.get(g.replace("keyword ", ""), g.replace("keyword ", ""))) if g.startswith("keyword") else (g or "affects it"))
            if lab == s["sub"]:
                ns.append(n)
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
        blind.append({"n": i, "members": [" ".join(items[n]["text"].split())[:170] for n in pick]})
        rk.append({"n": i, "sub": s["sub"], "gid": s["gid"], "eligible_cards": s["eligible_cards"]})
    with io.open(os.path.join(BUILD, "promotion_reread_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED_REREAD, "subheadings": blind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "promotion_reread_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED_REREAD, "subheadings": rk}, ensure_ascii=False, indent=1))
    # counts
    rset = set(cards["primary"])
    ren_gids = [h["gid"] for h in jl("remaining_breakdown.json")["r5"]["held"] if h["name"].split(" › ", 1)[1] in BT_RENAME]
    rename_cards = set()
    for g in ren_gids:
        rename_cards |= set(cards["r5_group_cards"][g])
    sub_cards = set()
    for s in promotable:
        sub_cards |= set(cards["r4_sub_cards"]["%s::%s" % (s["gid"], s["sub"])])
    out["renamed_group_gids"] = ren_gids
    out["remaining_cards_in_the_3_renamed_groups"] = len(rename_cards)
    out["remaining_cards_in_the_30_sub_headings"] = len(sub_cards)
    out["union"] = len(rename_cards | sub_cards)
    out["overlap"] = len(rename_cards & sub_cards)
    out["promotable"] = [{"n": s["n"], "gid": s["gid"], "group": s["group"], "sub": s["sub"], "cards": s["cards"], "eligible_cards": s["eligible_cards"], "remaining_cards_that_would_move": s["remaining_cards_that_would_move"]} for s in promotable]
    with io.open(os.path.join(BUILD, "promotion_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "promotable"}, indent=1))


NEW_NAMES_RENAMED = {
    "Pump / grant › Give a creature a different rule": "Give a creature an effect like can't attack, can't block or can't be blocked",
    "Pump / grant › Give things a different rule, other kinds of target": "Give things a combat effect like can't block or can't be blocked, other kinds of target",
    "Static: continuous › Continuous effect on this permanent": "This permanent gets or has something as long as something is true",
}


def subgroups(items, raw, info, folded, fm, kind_of):
    """{(gid, sub-heading label): [ability indexes]} exactly as the loose build builds the sub-headings (labels under 3 cards fold into 'Other kinds')."""
    out = {}
    for k in folded:
        kd = kind_of(k)
        if kd == "group":
            continue
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
        cnt = collections.defaultdict(set)
        for n, l in lab.items():
            cnt[l].add(items[n]["oid"])
        small = {l for l, c in cnt.items() if len(c) < BL.SUB_MIN}
        for n in lab:
            if lab[n] in small:
                lab[n] = "Other kinds"
        for n, l in lab.items():
            out.setdefault((BL.gid_of(k), l), []).append(n)
    return out


def sub_group_name(parent_gid, family, label, gids_kind):
    """the tentative group's name for a promoted sub-heading: fixed wording per sub-heading."""
    if family == "Static: continuous":
        lab = {"adds a creature type": "adds a creature or land type"}.get(label, label)
        return "Continuous effect on other kinds of target: " + lab
    if family == "Destroy":
        return "Destroy a " + label
    label = {"Can attack despite defender": "Can attack as though it didn't have defender"}.get(label, label)
    return label


def proposed():
    items, raw, info, meta = load()
    fam_keys = {k for k, _ in meta["families"]}
    use_idx, keys, folded, fm, names, sizes, kind_of = BL.make_groups(items, raw, info, fam_keys)
    pr = jl("promotion_probe.json")
    gk = {BL.gid_of(k): k for k in folded}
    sg = subgroups(items, raw, info, folded, fm, kind_of)
    out = []
    for g in pr["renamed_group_gids"]:
        k = gk[g]
        fam, full = k[0], names[k]
        new = NEW_NAMES_RENAMED[full]
        out.append({"id": g, "kind": "renamed group", "fam": fam, "old": full.split(" › ", 1)[1], "name": fam + " › " + new,
                    "n": [n for n in fm[k] if BT.eligible(items[n], True)]})
    for s in pr["promotable"]:
        k = gk[s["gid"]]
        fam = k[0]
        nm = sub_group_name(s["gid"], fam, s["sub"], None)
        out.append({"id": "s" + s["gid"] + ":" + s["sub"], "kind": "sub-heading", "fam": fam, "old": s["sub"], "name": fam + " › " + nm, "n": [n for n in sg[(s["gid"], s["sub"])] if BT.eligible(items[n], True)]})
    existing = {g["name"] for g in jl("tentative_placements.json")["groups"].values()} | set(names.values())
    for g in out:
        if g["name"] in existing and g["kind"] == "sub-heading":
            g["name"] += ", uncommon cases"
    return items, out, names


def names_check():
    import re
    import ability_names as AN
    import probe_names_part1 as P1
    import probe_names_part2 as P2
    items, groups, names = proposed()
    existing = {g["name"] for g in jl("tentative_placements.json")["groups"].values()} | set(names.values())
    taken = collections.Counter(g["name"] for g in groups)
    cards_json = jl("ability_taxonomy_cards.json")["cards"]
    vocab = set()
    for c in cards_json.values():
        for w in re.findall(r"[A-Za-z][a-z']{2,}", c["t"] or ""):
            vocab.add(w.lower())
    P1.ALLOW.update(AN.TEMPLATE_VOCAB)
    P1.ALLOW.update({"affecting", "granting", "several", "bigger", "smaller", "counted", "unchanged", "amount", "continuous", "kinds", "same", "something", "state", "recorded", "named", "replacement", "uncommon", "cases"})
    scan = P1.defect_scan([("group", g["name"].split(" › ", 1)[1]) for g in groups], vocab)
    soft = ("longer than 110 characters", "stacked parentheses", "disambiguation suffix ('(variant)', '#2')")
    hard = {n.split("  [")[0] for k, v in scan.items() if k not in soft for _, n in v}
    bad = []
    for g in groups:
        texts = [P2.norm(items[n]["text"]) for n in g["n"] if (items[n]["text"] or "").strip()]
        if len(texts) < 5:
            continue
        low = set(re.findall(r"[a-z']+", P2.norm(g["name"].split("›", 1)[1])))
        for w, rx in P2.STEMS.items():
            if w in low or (w + "s") in low:
                if sum(1 for t in texts if re.search(rx, t)) / len(texts) < 0.5:
                    bad.append((g["name"], w))
    res = {"names": len(groups), "duplicates_inside_the_new_set": [n for n, c in taken.items() if c > 1], "already_used_by_an_existing_group": sorted(g["name"] for g in groups if g["name"] in existing),
           "hard_defects": sorted(hard), "claims_hits": bad, "over_110": [g["name"] for g in groups if len(g["name"]) > 110], "longest": max(len(g["name"]) for g in groups)}
    rnd = random.Random(SEED_NAMES)
    pick = rnd.sample(sorted(groups, key=lambda g: g["id"]), 20)
    blind, key = [], []
    for i, g in enumerate(pick, 1):
        ns = sorted(g["n"], key=lambda n: (items[n]["oid"], items[n]["text"]))
        rnd.shuffle(ns)
        seen, mem = set(), []
        for n in ns:
            if items[n]["oid"] in seen:
                continue
            seen.add(items[n]["oid"])
            mem.append(" ".join(items[n]["text"].split())[:150])
            if len(mem) == 8:
                break
        blind.append({"n": i, "members": mem})
        key.append({"n": i, "id": g["id"], "name": g["name"], "kind": g["kind"], "eligible_cards": len({items[n]["oid"] for n in g["n"]})})
    with io.open(os.path.join(BUILD, "promotion_names_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED_NAMES, "groups": blind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "promotion_names_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED_NAMES, "checks": res, "all": [{"id": g["id"], "kind": g["kind"], "fam": g["fam"], "old": g["old"], "name": g["name"], "eligible_cards": len({items[n]["oid"] for n in g["n"]})} for g in groups], "draw": key}, ensure_ascii=False, indent=1))
    print(json.dumps(res, indent=1, ensure_ascii=False))


BT_RENAME = ("Continuous effect on this permanent", "Give a creature a different rule", "Give things a different rule, other kinds of target")

if __name__ == "__main__":
    {"draw": draw, "names": names_check}[sys.argv[1] if len(sys.argv) > 1 else "draw"]()
