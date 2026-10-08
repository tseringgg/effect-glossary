#!/usr/bin/env python3
"""Analysis for signature-taxonomy PROBE 2 -- investigation only. Places nothing, changes nothing.

    python src/probe2_signature_taxonomy.py
    python src/analyze2_signature_probe.py   # -> build/signature_probe2_analysis.json

Named cases, comparison with probe 1 and the old taxonomy, projected "Not yet organized", browsability thresholds,
leaves per card. Reads build/signature_probe2_leaves.json (and probe 1's, for comparison), ledger.json,
unorganized_cards.json, clusters.json, land_denial_roles.json. No Scryfall tags.
"""
import collections
import io
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe2_signature_taxonomy as p2  # noqa: E402

BUILD = p2.BUILD
KEYS = ("FO3", "FO5", "RF3", "RF5")
PRIMARY = "RF5"
SEED = 20261007

WRONG_TARGET = ["Cleansing", "Death Cloud", "Global Ruin", "Impending Disaster", "Wave of Vitriol",
                "Bearer of the Heavens", "Pox Plague", "Strategy, Schmategy", "Upheaval", "Worldpurge",
                "Balancing Act"]
DESTROY_ALL_LANDS = ["Armageddon", "Bust", "Catastrophe", "Fall of the Thran", "Myojin of Infinite Rage",
                     "Ravages of War"]
NAMED = ["Dogged Detective", "Spitting Dilophosaurus", "Bandit's Talent", "Memory Sluice", "Seedship Broodtender",
         "Deadly Visit", "Raucous Theater", "Shuri, Wakandan Inventor", "Mulldrifter", "Spark Double",
         "Sakura-Tribe Elder"]
LANDW = ("Land", "Island", "Plains", "Forest", "Swamp", "Mountain")


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def tables(R, key):
    """leaf -> member row indices, flags per leaf, for one variant."""
    mem = collections.defaultdict(list)
    for j, r in enumerate(R):
        a = r["a"][key]
        if a[0] != "x":
            mem[(a[0], a[1])].append(j)
    flags = {}
    for lf in mem:
        parts = lf[1].split(" · ")
        ftype = parts[1].split("=", 1)[1]
        ret = dict(p.split("=", 1) for p in parts[2:])
        fl = p2.flag_reasons(ftype, ret)
        if fl:
            flags[lf] = fl
    return mem, flags


def lv(r, key):
    a = r["a"][key]
    return None if a[0] == "x" else (a[0], a[1])


def view(R, mem, flags, r, key):
    lf = lv(r, key)
    if not lf:
        return {"unplaced": r["a"][key][1]}
    return {"level": lf[0], "sig": lf[1], "n": len(mem[lf]), "flagged": flags.get(lf, [])}


def has_land(f):
    s = " ".join([f["obj"], f["chain"], f["props"]])
    return any(w in s for w in LANDW)


def main():
    R = jl("signature_probe2_leaves.json")["rows"]
    P1 = jl("signature_probe_leaves.json")["rows"]
    p1 = {(r["face"], r["b"], r["i"]): r for r in P1}
    L = jl("ledger.json")["rows"]
    C = jl("clusters.json")
    roles = jl("land_denial_roles.json")["roles"]
    T = {k: tables(R, k) for k in KEYS}
    by_name = collections.defaultdict(list)
    for j, r in enumerate(R):
        by_name[r["name"]].append(j)
    out = {"v": 1, "seed": SEED, "primary": PRIMARY}

    # ---- headline counts per variant
    head = {}
    today_new = lambda r: r["state"] == "unplaced" or r["status"] == "noise"   # noqa: E731
    for k in KEYS:
        mem, flags = T[k]
        direct = {lf: len(v) for lf, v in mem.items()}
        n_assigned = sum(direct.values())
        small = sum(n for n in direct.values() if n < 5)
        hl = fl = 0
        newly = collections.Counter()
        newly_flag = 0
        bare = lambda lf: lf[1].count(" · ") == 1   # noqa: E731
        for lf, js in mem.items():
            if direct[lf] < 5:
                continue
            if lf in flags:
                fl += len(js)
                newly_flag += sum(1 for j in js if today_new(R[j]))
            else:
                hl += len(js)
                for j in js:
                    if today_new(R[j]):
                        newly["L%d" % lf[0]] += 1
        unpl = collections.Counter(r["a"][k][1] for r in R if r["a"][k][0] == "x")
        head[k] = {"population": len(R), "assigned": n_assigned, "assigned_to_nodes_lt5_direct": small,
                   "headline_placed_unflagged_direct_ge5": hl, "placed_but_flagged_generic": fl,
                   "unplaced": sum(unpl.values()), "unplaced_by_reason": dict(sorted(unpl.items())),
                   "newly_placed_vs_today_unflagged_by_level": dict(sorted(newly.items())),
                   "newly_placed_vs_today_unflagged": sum(newly.values()), "newly_placed_vs_today_flagged": newly_flag,
                   "leaves": len(mem), "leaves_flagged": len(flags)}
        # size classes over unflagged leaves with direct >= 5
        sizes = [len(v) for lf, v in mem.items() if lf not in flags]
        head[k]["unflagged_leaves"] = len(sizes)
        head[k]["unflagged_5_9"] = [sum(1 for s in sizes if 5 <= s <= 9), sum(s for s in sizes if 5 <= s <= 9)]
        head[k]["unflagged_50plus"] = [sum(1 for s in sizes if s >= 50), sum(s for s in sizes if s >= 50)]
        head[k]["all_5_9"] = [sum(1 for v in mem.values() if 5 <= len(v) <= 9), sum(len(v) for v in mem.values() if 5 <= len(v) <= 9)]
        head[k]["all_50plus"] = [sum(1 for v in mem.values() if len(v) >= 50), sum(len(v) for v in mem.values() if len(v) >= 50)]
        head[k]["all_lt5_direct"] = [sum(1 for v in mem.values() if len(v) < 5), sum(len(v) for v in mem.values() if len(v) < 5)]
    out["headline"] = head

    # ---- flagged generic leaves: reasons, text check for Draw
    gen = {}
    for k in ("FO5", "RF5"):
        mem, flags = T[k]
        reason = collections.Counter()
        for lf, fl in flags.items():
            for r in fl:
                reason[r] += len(mem[lf])
        big = sorted(((len(mem[lf]), lf, fl) for lf, fl in flags.items()), reverse=True)[:12]
        draw_text = [0, 0]
        for lf, fl in flags.items():
            if "who draws is not in the parse" in fl:
                for j in mem[lf]:
                    draw_text[0] += 1
                    t = R[j]["text"].lower()
                    if any(w in t for w in ("target player", "each player", "each opponent", "target opponent", "that player")):
                        draw_text[1] += 1
        gen[k] = {"abilities_by_reason(overlapping)": dict(reason),
                  "largest_flagged": [{"n": n, "level": lf[0], "sig": lf[1], "flags": fl} for n, lf, fl in big],
                  "draw_leaf_members": draw_text[0], "draw_members_whose_text_names_another_player": draw_text[1]}
    out["generic"] = gen

    # ---- named: land denial
    core = sorted(n for n, ro in roles.items() if ro in ("D", "DP", "DB"))
    dal = {}
    for k in KEYS:
        mem, flags = T[k]
        per = {}
        for n in DESTROY_ALL_LANDS:
            per[n] = [lv(R[j], k) for j in by_name.get(n, []) if has_land(R[j]["f"]) and R[j]["f"]["quant"] == "all"]
        firsts = {v[0] for v in per.values() if v}
        shared = len(firsts) == 1 and all(per.values()) and None not in firsts
        dal[k] = {"one_shared_leaf": shared,
                  "leaf": list(next(iter(firsts))) if shared else None,
                  "leaf_size": len(mem[next(iter(firsts))]) if shared else None,
                  "members": sorted({R[j]["name"] for j in mem[next(iter(firsts))]}) if shared else None,
                  "per_card": {n: [list(x) if x else None for x in v] for n, v in per.items()}}
    out["destroy_all_lands"] = dal
    cnt = {}
    for k in KEYS:
        mem, flags = T[k]
        c = collections.Counter()
        cards = []
        for n in core:
            js = by_name.get(n, [])
            if not js:
                c["not in population"] += 1
                continue
            lj = [j for j in js if has_land(R[j]["f"])]
            if not lj:
                c["no land in any ability's parse"] += 1
                continue
            ok = any(lv(R[j], k) and any(w in lv(R[j], k)[1] for w in LANDW) for j in lj)
            c["land-specific leaf" if ok else "land in parse, leaf not land-specific"] += 1
            if ok:
                cards.append(n)
        cnt[k] = {"counts": dict(c), "land_specific_cards": cards}
    out["land_denial_core"] = cnt

    # ---- named: wrong target, others
    def case(n, keys=("FO5", "RF5", "RF3")):
        res = []
        for j in by_name.get(n, []):
            r = R[j]
            a = {"b": r["b"], "i": r["i"], "text": r["text"][:140], "status": r["status"], "old_state": r["state"],
                 "old_cardleaf": r["cleaf"], "fields": {k: v for k, v in r["f"].items() if v not in ("", "-")}}
            for k in keys:
                v = view(R, *T[k], r, k)
                if "level" in v:
                    mem = T[k][0]
                    v["sample"] = sorted({R[x]["name"] for x in mem[lv(r, k)]})[:10]
                a[k] = v
            q = p1.get((r["face"], r["b"], r["i"]))
            if q and q["leaf_new"]["C5"]:
                a["probe1_C5"] = {"level": q["leaf_new"]["C5"][0], "sig": q["leaf_new"]["C5"][1]}
            res.append(a)
        return res
    out["wrong_target"] = {n: case(n) for n in WRONG_TARGET}
    out["named"] = {n: case(n) for n in NAMED}
    # probe-1 leaf sizes for the same abilities (for the comparison)
    p1mem = collections.defaultdict(int)
    for r in P1:
        if r["leaf_new"]["C5"]:
            p1mem[tuple(r["leaf_new"]["C5"])] += 1
    for grp in (out["wrong_target"], out["named"]):
        for n, lst in grp.items():
            for a in lst:
                if "probe1_C5" in a:
                    a["probe1_C5"]["n"] = p1mem[(a["probe1_C5"]["level"], a["probe1_C5"]["sig"])]

    # ---- projected "Not yet organized"
    U = jl("unorganized_cards.json")["groups"]
    gname = {"1": "Parsed, but with a gap", "2": "Parsed, no close group found", "3": "No effect to group",
             "4": "Not parsed yet", "5": "Known parse mistake"}
    abil = collections.defaultdict(list)
    for j, r in enumerate(R):
        abil[r["oid"]].append(j)
    nyo = {}
    for k in KEYS:
        mem, flags = T[k]
        ok_leaf = lambda lf: len(mem[lf]) >= 5   # noqa: E731
        g = {}
        tot = [0, 0, 0, 0]
        for gid, cards in U.items():
            a = b = c = 0
            for card in cards:
                lfs = [lv(R[j], k) for j in abil.get(card["c"], [])]
                lfs = [lf for lf in lfs if lf and ok_leaf(lf)]
                if lfs:
                    c += 1
                    un = [lf for lf in lfs if lf not in flags]
                    if un:
                        b += 1
                        if any(lf[1].count(" · ") > 1 for lf in un):
                            a += 1
            g[gname.get(gid, gid)] = {"cards": len(cards), "specific_unflagged_nonbare": a, "unflagged": b, "any_incl_flagged": c}
            tot[0] += len(cards); tot[1] += a; tot[2] += b; tot[3] += c
        nyo[k] = {"groups": g, "total": tot[0],
                  "projected_after_specific_only": tot[0] - tot[1],
                  "projected_after_unflagged": tot[0] - tot[2], "projected_after_any_incl_flagged": tot[0] - tot[3]}
    out["not_yet_organized"] = nyo

    # ---- old taxonomy: pair share
    comp = {}
    for k in ("FO5", "RF5"):
        mem, flags = T[k]
        cl = collections.defaultdict(set)
        for j, r in enumerate(R):
            lf = lv(r, k)
            if lf and len(mem[lf]) >= 5:
                cl[r["oid"]].add(lf)
        om = collections.defaultdict(list)
        for oid, v in L.items():
            if v["status"] == "clustered":
                f = [x for x in v["evidence"]["faces"] if x.get("leaf") is not None]
                if f and oid in cl:
                    om[f[0]["leaf"]].append(oid)
        rng = random.Random(1)
        shares, pairs, same = [], 0, 0.0
        need = collections.Counter()
        for ol, ms in om.items():
            if len(ms) < 2:
                continue
            ms = sorted(ms)
            allp = [(a, b) for i, a in enumerate(ms) for b in ms[i + 1:]]
            sm = allp if len(allp) <= 2000 else rng.sample(allp, 2000)
            s = sum(1 for a, b in sm if cl[a] & cl[b]) / len(sm)
            shares.append(s)
            w = len(allp)
            pairs += w
            same += w * s
            cnt_ = collections.Counter(lf for o in ms for lf in cl[o])
            cov, nn = set(), 0
            for lf, _ in cnt_.most_common():
                if len(cov) >= 0.8 * len(ms):
                    break
                cov |= {o for o in ms if lf in cl[o]}
                nn += 1
            need[min(nn, 6)] += 1
        shares.sort()
        n = len(shares)
        comp[k] = {"pair_share_weighted": round(same / pairs, 4), "median_old_leaf": round(shares[n // 2], 3),
                   "quartiles": [round(shares[n // 4], 3), round(shares[3 * n // 4], 3)],
                   "old_leaves_ge80": sum(s >= 0.8 for s in shares), "old_leaves_lt20": sum(s < 0.2 for s in shares),
                   "old_leaves": n, "new_leaves_to_cover_80pct": dict(sorted(need.items()))}
    out["old_taxonomy"] = comp

    # ---- browsability and leaves per card
    br = {}
    for k in ("RF5", "FO5"):
        mem, flags = T[k]
        parents = {}
        for j, r in enumerate(R):
            if lv(r, k):
                f = r["f"]
                parents[j] = (f["ftype"],) + tuple(f[x] for x in p2.L2G)
        fams = {R[j]["f"]["fam"] for j in parents}
        rows = []
        for thr in (5, 10, 20, 50):
            vis = [lf for lf, js in mem.items() if len(js) >= thr and lf not in flags]
            visset = set(vis)
            ab = sum(len(mem[lf]) for lf in vis)
            placed_unflagged = sum(len(js) for lf, js in mem.items() if len(js) >= 5 and lf not in flags)
            percard = collections.Counter()
            for j, r in enumerate(R):
                lf = lv(r, k)
                if lf in visset:
                    percard[r["oid"]].add(lf) if False else None
            pc = collections.defaultdict(set)
            for j, r in enumerate(R):
                lf = lv(r, k)
                if lf in visset:
                    pc[r["oid"]].add(lf)
            nums = sorted(len(v) for v in pc.values())
            rows.append({"threshold": thr, "visible_leaves": len(vis), "abilities_in_visible_leaves": ab,
                         "abilities_rolled_up": placed_unflagged - ab,
                         "parent_nodes_effect_plus_verb_parameters": len({parents[j] for lf in vis for j in mem[lf]}),
                         "cards_with_a_visible_leaf": len(pc),
                         "avg_leaves_per_card": round(sum(nums) / len(nums), 3), "median": nums[len(nums) // 2],
                         "p95": nums[int(len(nums) * 0.95)], "max": nums[-1],
                         "cards_in_5_or_more": sum(1 for x in nums if x >= 5)})
        mx = max(pc.items(), key=lambda kv: len(kv[1])) if pc else None
        br[k] = {"families": len(fams), "rows": rows}
    out["browse"] = br
    # who has the max leaves per card at threshold 5 (RF5)
    mem, flags = T["RF5"]
    pc = collections.defaultdict(set)
    for r in R:
        lf = lv(r, "RF5")
        if lf and len(mem[lf]) >= 5 and lf not in flags:
            pc[r["oid"]].add(lf)
    top = sorted(pc.items(), key=lambda kv: -len(kv[1]))[:5]
    out["browse"]["most_leaves_cards_RF5_thr5"] = [
        {"name": next(R[j]["name"] for j in abil[o]), "leaves": len(v)} for o, v in top]
    with io.open(os.path.join(BUILD, "signature_probe2_analysis.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True, default=list))
    print("ok")


if __name__ == "__main__":
    main()
