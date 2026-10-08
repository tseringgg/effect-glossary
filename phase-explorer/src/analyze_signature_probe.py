#!/usr/bin/env python3
"""Analysis for the signature-taxonomy PROBE -- investigation only. Places nothing, changes nothing.

    python src/probe_signature_taxonomy.py   # first
    python src/analyze_signature_probe.py    # -> build/signature_probe_analysis.json, build/signature_probe_handcheck.json

Reads build/signature_probe_leaves.json plus the frozen clustering and display layers (clusters.json,
ledger.json, unorganized_cards.json, land_denial_roles.json). Named cases, old-vs-new comparison, and a
seeded hand-check sample (30 leaves x 8 abilities) for the chosen order. Scryfall tags are not read.
"""
import collections
import io
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_signature_taxonomy as pst  # noqa: E402

BUILD = pst.BUILD
KEYS = ("A3", "A5", "B3", "B5", "C3", "C5", "A5r", "B5r", "C3r", "C5r")
PRIMARY = os.environ.get("SIG_PRIMARY", "C5")
SEED = 20261006
HC_MIN_DIRECT = 8   # a hand-checked leaf must hold >= 8 abilities directly, so 8 can be read (see report §6)

WRONG_TARGET = ["Cleansing", "Death Cloud", "Global Ruin", "Impending Disaster", "Wave of Vitriol",
                "Bearer of the Heavens", "Pox Plague", "Strategy, Schmategy", "Upheaval", "Worldpurge",
                "Balancing Act"]
DESTROY_ALL_LANDS = ["Armageddon", "Bust", "Catastrophe", "Fall of the Thran", "Myojin of Infinite Rage",
                     "Ravages of War"]
NAMED = ["Memory Sluice", "Seedship Broodtender", "Deadly Visit", "Raucous Theater", "Spitting Dilophosaurus",
         "Bandit's Talent", "Dogged Detective", "Shuri, Wakandan Inventor", "Mulldrifter", "Spark Double",
         "Sakura-Tribe Elder"]


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def landish(r, key):
    """Does this ability's leaf signature name lands (object, subtype or chain step)?"""
    lf = r["leaf_new"][key]
    return bool(lf) and ("Land" in lf[1] or any(s in lf[1] for s in ("Island", "Plains", "Forest", "Swamp", "Mountain")))


def sig_names_land(r):
    s = r["sig"]["C"][4] if r["sig"]["C"] else ""
    return "Land" in s or any(t in s for t in ("Island", "Plains", "Forest", "Swamp", "Mountain"))


def main():
    R = jl("signature_probe_leaves.json")["rows"]
    L = jl("ledger.json")["rows"]
    C = jl("clusters.json")
    idx = {r["id"]: r for r in jl("index.json")["rows"]}
    roles = jl("land_denial_roles.json")["roles"]
    by_name = collections.defaultdict(list)
    for r in R:
        by_name[r["name"]].append(r)
    members = {k: collections.defaultdict(list) for k in KEYS}
    for j, r in enumerate(R):
        for k in KEYS:
            if r["leaf_new"][k]:
                members[k][tuple(r["leaf_new"][k])].append(j)
    low = {k: {lf for lf, js in members[k].items() if pst.low_info(lf[0], R[js[0]]["f"])} for k in KEYS}
    out = {"v": 1, "primary": PRIMARY}

    def leaf_view(r, k):
        lf = r["leaf_new"][k]
        if not lf:
            return None
        js = members[k][tuple(lf)]
        return {"level": lf[0], "sig": lf[1], "n": len(js), "low_info": tuple(lf) in low[k]}

    # ---- named: land denial core
    core = sorted(n for n, ro in roles.items() if ro in ("D", "DP", "DB"))
    ld = []
    for n in core:
        rs = by_name.get(n, [])
        oid = next((o for o, v in L.items() if v["name"] == n), None)
        row = {"card": n, "role": roles[n], "status": L[oid]["status"] if oid else None, "abilities": []}
        for r in rs:
            row["abilities"].append({"text": r["text"][:120], "land_in_sig": sig_names_land(r),
                                     "sigC5": r["sig"]["C"][4] if r["sig"]["C"] else None,
                                     "leaf": {k: leaf_view(r, k) for k in KEYS}})
        ld.append(row)
    out["land_denial_core"] = ld
    dal = {}
    for k in KEYS:
        lv = {}
        for n in DESTROY_ALL_LANDS:
            rs = [r for r in by_name.get(n, []) if sig_names_land(r)]
            lv[n] = [tuple(r["leaf_new"][k]) if r["leaf_new"][k] else None for r in rs]
        firsts = {v[0] for v in lv.values() if v}
        dal[k] = {"per_card": {n: [list(x) if x else None for x in v] for n, v in lv.items()},
                  "one_shared_leaf": len(firsts) == 1 and all(lv.values()),
                  "leaf_size": len(members[k][next(iter(firsts))]) if len(firsts) == 1 and None not in firsts else None,
                  "leaf_members": sorted({R[j]["name"] for j in members[k][next(iter(firsts))]})
                  if len(firsts) == 1 and None not in firsts else None}
    out["destroy_all_lands"] = dal
    # ---- named: wrong-target
    wt = []
    for n in WRONG_TARGET:
        rs = by_name.get(n, [])
        oid = next((o for o, v in L.items() if v["name"] == n), None)
        old = rs[0]["cleaf"] if rs else None
        ent = {"card": n, "status": L[oid]["status"] if oid else None, "old_leaf": old,
               "old_label": C["labels"].get(str(old)) if old is not None else None, "in_population": bool(rs),
               "abilities": []}
        for r in rs:
            a = {"text": r["text"][:140], "land_in_sig": sig_names_land(r), "f": r["f"], "leaf": {}}
            for k in KEYS:
                v = leaf_view(r, k)
                if v:
                    js = members[k][tuple(r["leaf_new"][k])]
                    old_mates = [R[j] for j in js if R[j]["cleaf"] == old and R[j]["oid"] != r["oid"]]
                    v["old_leaf_mates_here"] = len(old_mates)
                    v["land_specific"] = landish(r, k)
                    v["sample"] = sorted({R[j]["name"] for j in js})[:12]
                a["leaf"][k] = v
            ent["abilities"].append(a)
        wt.append(ent)
    out["wrong_target"] = wt
    # ---- named: others
    nm = {}
    for n in NAMED:
        rs = by_name.get(n, [])
        lst = []
        for r in rs:
            a = {"b": r["b"], "i": r["i"], "text": r["text"][:160], "f": r["f"],
                 "old": {"state": r["state"], "route": r["route"], "leaf": r["leaf"], "best": r["best"],
                         "score": r["score"], "cleaf": r["cleaf"]},
                 "leaf": {k: leaf_view(r, k) for k in KEYS}}
            for k in ("C5",):
                if r["leaf_new"][k]:
                    js = members[k][tuple(r["leaf_new"][k])]
                    a["sample_C5"] = [(R[j]["name"], R[j]["text"][:90]) for j in random.Random(SEED).sample(js, min(6, len(js)))]
            lst.append(a)
        nm[n] = lst
    out["named"] = nm
    # Spark Double is corrections-flagged, so outside the population: compute its fields for display only
    sd = next((o for o, v in L.items() if v["name"] == "Spark Double"), None)
    if sd:
        fid = L[sd]["evidence"]["faces"][0]["id"]
        e = jl("chunks/%d.json" % idx[fid]["ch"])[fid]
        out["spark_double_outside_population"] = {
            "status": L[sd]["status"],
            "items": [{"b": b, "i": i, "text": (it.get("description") or "")[:160],
                       "sigC5": pst.sig(pst.fields({"b": b, "item": it}), pst.ORDERS["C"][4])}
                      for b in ("abilities", "triggers", "static_abilities", "replacements")
                      for i, it in enumerate(e.get(b) or [])]}

    # ---- comparison with the old taxonomy
    comp = {}
    for k in KEYS:
        card_leaves = collections.defaultdict(set)
        for r in R:
            if r["leaf_new"][k]:
                card_leaves[r["oid"]].add(tuple(r["leaf_new"][k]))
        old_members = collections.defaultdict(list)
        for oid, v in L.items():
            if v["status"] == "clustered":
                f = [x for x in v["evidence"]["faces"] if x.get("leaf") is not None]
                if f and oid in card_leaves:
                    old_members[f[0]["leaf"]].append(oid)
        rng = random.Random(SEED)
        pairs = same = 0
        cover80, kept = [], []
        frag = []
        for ol, ms in old_members.items():
            ms = sorted(ms)
            n = len(ms)
            if n < 2:
                continue
            allp = [(a, b) for ai, a in enumerate(ms) for b in ms[ai + 1:]]
            sm = allp if len(allp) <= 3000 else rng.sample(allp, 3000)
            s = sum(1 for a, b in sm if card_leaves[a] & card_leaves[b])
            w = n * (n - 1) / 2
            pairs += w
            same += w * s / len(sm)
            cnt = collections.Counter(lf for o in ms for lf in card_leaves[o])
            covered, need = set(), 0
            for lf, _ in cnt.most_common():
                if len(covered) >= 0.8 * n:
                    break
                covered |= {o for o in ms if lf in card_leaves[o]}
                need += 1
            cover80.append(need)
            kp = sum(1 for o in ms if any(cnt[lf] >= 2 for lf in card_leaves[o])) / n
            kept.append(kp)
            lab = C["labels"].get(str(ol), "")
            # proxy for a coherent old leaf: every member shares one exact effect+target token
            coherent = bool(re.search(r"\|tgt:\S+ \(100%\)", lab))
            frag.append({"old_leaf": ol, "n": n, "label": lab[:120], "coherent_proxy": coherent,
                         "kept_together": round(kp, 3), "leaves_for_80pct": need,
                         "top_new_leaf_share": round(cnt.most_common(1)[0][1] / n, 3) if cnt else 0})
        dist = collections.Counter(min(c, 6) for c in cover80)
        coh = [f for f in frag if f["coherent_proxy"]]
        comp[k] = {"old_leaves": len(frag), "pair_share_same_new_leaf": round(same / pairs, 4) if pairs else None,
                   "leaves_for_80pct_hist": {("6+" if a == 6 else str(a)): b for a, b in sorted(dist.items())},
                   "old_leaves_one_new_leaf_covers_80pct": sum(1 for c in cover80 if c <= 1),
                   "median_kept_together": sorted(kept)[len(kept) // 2],
                   "coherent_proxy_leaves": len(coh),
                   "coherent_fragmenting": sorted([f for f in coh if f["kept_together"] < 0.5],
                                                  key=lambda f: (f["kept_together"], -f["n"]))[:25],
                   "coherent_fragmenting_count": sum(1 for f in coh if f["kept_together"] < 0.5)}
        # unplaced / noise abilities today
        un = [r for r in R if r["state"] == "unplaced"]
        lv = collections.Counter()
        size5 = only_low = 0
        for r in un:
            lf = r["leaf_new"][k]
            if not lf:
                lv["none"] += 1
                continue
            sz = len(members[k][tuple(lf)])
            if sz >= 5:
                size5 += 1
                lv["L%d" % lf[0]] += 1
        un_cards = collections.defaultdict(list)
        for r in un:
            un_cards[r["oid"]].append(r)
        for oid, rs in un_cards.items():
            lfs = [tuple(r["leaf_new"][k]) for r in rs if r["leaf_new"][k] and len(members[k][tuple(r["leaf_new"][k])]) >= 5]
            if lfs and all(lf in low[k] or lf[0] <= 2 for lf in lfs):
                only_low += 1
        comp[k]["unplaced_abilities"] = {"total": len(un), "in_leaf_ge5": size5, "by_level": dict(sorted(lv.items())),
                                         "by_card_status": dict(collections.Counter(r["status"] for r in un)),
                                         "cards_with_unplaced": len(un_cards),
                                         "cards_only_coarse_or_generic": only_low}
    out["comparison"] = comp

    # ---- blind spots re-opened by backoff: the ability HAS the field, its leaf's level does not use it
    lvl_keys = {o: pst.ORDERS[o] for o in pst.ORDERS}
    bs = {}
    for k in KEYS:
        o = k[0]
        c = collections.Counter()
        for r in R:
            lf = r["leaf_new"][k]
            if not lf:
                continue
            used = set(lvl_keys[o][lf[0] - 1])
            for fld, name in (("frm", "zone from"), ("to", "zone to"), ("ctr", "counter type"), ("who", "player scope")):
                if r["f"][fld]:
                    c[name + ": has"] += 1
                    if fld not in used:
                        c[name + ": leaf ignores it"] += 1
            if r["f"]["det"] and "chain:" in r["f"]["det"]:
                c["chain: has"] += 1
                if "det" not in used:
                    c["chain: leaf ignores it"] += 1
        bs[k] = dict(sorted(c.items()))
    out["blind_spot_reopened"] = bs

    # ---- Not yet organized, by group
    U = jl("unorganized_cards.json")["groups"]
    gname = {"1": "Parsed, but with a gap", "2": "Parsed, no close group found", "3": "No effect to group",
             "4": "Not parsed yet", "5": "Known parse mistake"}
    abil_by_card = collections.defaultdict(list)
    for r in R:
        abil_by_card[r["oid"]].append(r)
    nyo = {}
    for k in KEYS:
        g = {}
        tot = any_ = spec = 0
        for gid, cards in U.items():
            n = len(cards)
            a = s = 0
            for c in cards:
                lfs = [tuple(r["leaf_new"][k]) for r in abil_by_card.get(c["c"], []) if r["leaf_new"][k]]
                lfs = [lf for lf in lfs if len(members[k][lf]) >= 5]
                if lfs:
                    a += 1
                    if any(lf not in low[k] and lf[0] >= 3 for lf in lfs):
                        s += 1
            g[gname.get(gid, gid)] = {"cards": n, "any_leaf_ge5": a, "specific_leaf_L3plus": s}
            tot += n
            any_ += a
            spec += s
        nyo[k] = {"groups": g, "total": tot, "projected_unorganized_any": tot - any_,
                  "projected_unorganized_specific_only": tot - spec}
    out["not_yet_organized"] = nyo

    # ---- hand-check sample (primary order)
    k = PRIMARY
    rng = random.Random(SEED)
    lv = collections.defaultdict(list)
    for lf, js in members[k].items():
        if len(js) >= HC_MIN_DIRECT:
            lv[lf[0]].append(lf)
    finest = sorted(lv[5])
    coarsest = sorted(lv[1])
    mid = sorted(lv[2] + lv[3] + lv[4])

    def strat(pool, n):
        """n leaves stratified by size (small / medium / large thirds)."""
        pool = sorted(pool, key=lambda lf: (len(members[k][lf]), lf))
        if len(pool) <= n:
            return pool
        t = len(pool) // 3
        parts = [pool[:t], pool[t:2 * t], pool[2 * t:]]
        take = [n // 3 + (1 if i < n % 3 else 0) for i in range(3)]
        return [lf for p, m in zip(parts, take) for lf in rng.sample(p, m)]
    pick = [("finest", lf) for lf in strat(finest, 10)] + [("coarsest", lf) for lf in strat(coarsest, 10)] + \
        [("middle", lf) for lf in strat(mid, 10)]
    hc = []
    for band, lf in pick:
        js = members[k][lf]
        sm = rng.sample(js, min(8, len(js)))
        ab = []
        for j in sm:
            r = R[j]
            t = r["text"]
            if len(t) < 45:
                ot = (idx.get(r["face"]) or {}).get("text") or ""
                t = t + "  [card: " + ot.replace("\n", " / ")[:220] + "]"
            ab.append({"name": r["name"], "text": t[:300], "sig5": r["sig"][k[0]][4]})
        hc.append({"band": band, "level": lf[0], "sig": lf[1], "n": len(js), "low_info": lf in low[k],
                   "abilities": ab, "verdict": None, "note": None})
    with io.open(os.path.join(BUILD, "signature_probe_handcheck.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"v": 1, "order": k, "seed": SEED, "leaves": hc}, ensure_ascii=False, indent=1,
                            sort_keys=True))
    with io.open(os.path.join(BUILD, "signature_probe_analysis.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True, default=list))
    print("ok", {k: comp[k]["pair_share_same_new_leaf"] for k in KEYS})


if __name__ == "__main__":
    main()
