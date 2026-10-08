#!/usr/bin/env python3
"""Leaf map over a curated EFFECT-TYPE-flavoured dimension set.

Third positioning attempt. The first used all 3,347 structural features and
failed (kNN 44.4%, rho 0.164). The second used a 15-column zone/choice space
and passed on the metrics (57.0% / 0.554) but positions leaves on zone
semantics, which is not what branches were built on -- branch cohesion ran
from 100% down to 43.5%.

This pass positions on effect/target structure instead, so that same-branch
cohesion has a chance of being meaningful rather than coincidental.

THE GRANULARITY QUESTION. Round one rejected "dominant effect category" at both
poles: 129 raw effect types is a near-orthogonal one-hot, 38 branches is
circular (the known-case checks are largely *defined* by branch membership).
The middle level is chosen EMPIRICALLY, by sweeping granularity against branch
cohesion (see TOP_N_TYPES): the top 40 effect types keep their own column and
everything rarer collapses into a hand-authored FAMILY taxonomy. The sweep found
a genuine interior optimum -- both poles and the families-only level score worse
-- so "dominant effect category" does have a workable granularity, which is the
answer round one left open.

The FAMILY taxonomy is authored over the effect-type vocabulary and deliberately
NOT copied from the branch rules, so same-branch cohesion stays a real test:

  * one `destroy-sacrifice` family spans Spot removal + Board wipe + Sacrifice
    removal, so only the mass dimension separates those branches;
  * `draw` / `mill` / `selection` / `search` are four families where the branch
    rules have six branches.

Reads   build/clusters.json, build/index.json, build/chunks/*.json
Writes  build/leafmap_effect.json, build/_eff_{D,XY}.npy, _eff_ids.json
"""
import collections
import importlib.metadata
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "hdbscan" not in sys.modules:      # blocked by Application Control; unused here
    import types as _t
    sys.modules["hdbscan"] = _t.ModuleType("hdbscan")
import cluster_structural as C
import branch_leaves as B

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")

RANDOM_SEED = 42
N_NEIGHBORS = 15
MIN_DIST = 0.1

# D1 granularity, chosen by sweeping it against the stated bar (branch
# cohesion), not by taste. Median 'branch is tighter than X% of all leaf
# pairs', worst branch, and branches below 60%:
#
#   22 families only            45 cols  median 78.4%  worst 46.2%  5 weak
#   top-20 types + family tail  60 cols  median 81.6%  worst 50.2%  3 weak
#   top-40 types + family tail  76 cols  median 82.2%  worst 53.3%  4 weak  <-- chosen
#   top-70 types + family tail 100 cols  median 75.2%  worst 48.7%  9 weak
#   all 129 raw types          150 cols  median 78.7%  worst 43.5% 11 weak
#
# The curve is non-monotonic with a genuine interior optimum, which is the
# direct answer to the granularity question: neither pole, and the families
# alone are too coarse. The tail below the top 40 still collapses into the
# FAMILY taxonomy, so this is a hybrid of the two middle levels.
TOP_N_TYPES = 40

# ---------------------------------------------------------------------------
# D1: effect families. Closed, documented, authored over the effect-type
# vocabulary -- the same "closed list of named rules" discipline as the zone
# classifier. Grouped by what the effect does to game objects.
FAMILY = {
    "destroy-sacrifice": ["Destroy", "DestroyAll", "Sacrifice", "SacrificeAll",
                          "ChooseAndSacrificeRest", "Fight"],
    "zone-move": ["ChangeZone", "ChangeZoneAll", "Bounce", "BounceAll",
                  "CastFromZone", "PutAtLibraryPosition", "ExileTop", "ExileAll"],
    "damage": ["DealDamage", "DamageAll", "DamageEachPlayer", "DamageEachOpponent"],
    "protect": ["PreventDamage", "Regenerate", "PreventAll", "Shield"],
    "counters": ["PutCounter", "PutCounterAll", "RemoveCounter", "MoveCounters",
                 "ProliferateCounters", "ChooseCounterAdjustment"],
    "pt-modify": ["Pump", "PumpAll", "SwitchPT", "SetPT"],
    "draw": ["Draw", "ForceDraw"],
    "mill": ["Mill", "MillAll"],
    "selection": ["Scry", "Surveil", "Dig", "RevealTop", "RevealUntil",
                  "PutOnTopOrBottom", "Seek", "Investigate"],
    "search": ["SearchLibrary"],
    "resource": ["Mana", "GainEnergy", "PayCost"],
    "life": ["GainLife", "LoseLife"],
    "hand-disruption": ["Discard", "DiscardAll", "RevealHand"],
    "tap-state": ["Tap", "Untap", "TapAll", "UntapAll"],
    "stack": ["Counter", "CopySpell", "CounterAll"],
    "token-copy": ["Token", "CopyTokenOf", "BecomeCopy", "CopyPermanent",
                   "CopyTokenBlocking"],
    "control": ["GainControl", "Goad", "BecomeMonarch", "ControlNextTurn"],
    "attach-grant": ["Attach", "AddKeyword", "AddKeywordAll", "GrantAbility"],
    "transform": ["Transform", "BecomePrepared", "TurnFaceUp", "Animate"],
    "choose-meta": ["Choose", "TargetOnly", "CreateDelayedTrigger", "Cleanup"],
}
FAM_OF = {e: f for f, es in FAMILY.items() for e in es}
FAM_ORDER = sorted(FAMILY) + ["static-continuous", "static-restriction",
                              "static-cost", "other"]


def family_of(et):
    if et in FAM_OF:
        return FAM_OF[et]
    if et.startswith("static:"):
        m = et[7:]
        if m == "Continuous":
            return "static-continuous"
        if m.startswith("Cant") or m.startswith("Must"):
            return "static-restriction"
        return "static-cost"
    return "other"


# D3: target type head, collapsed to the heads that actually occur in volume.
HEAD_ORDER = ["Creature", "Land", "Artifact", "Enchantment", "Permanent",
              "Card", "Player", "SelfRef", "AnyOr", "ParentTarget"]


def head_of(node):
    if not isinstance(node, dict):
        return None
    t = node.get("type")
    if t == "Typed":
        tf = [C.shape_tag(x) for x in (node.get("type_filters") or [])]
        h = tf[0] if tf else None
        if h in ("Creature", "Land", "Artifact", "Enchantment", "Permanent",
                 "Card", "Planeswalker"):
            return "Creature" if h == "Creature" else (
                "Permanent" if h == "Planeswalker" else h)
        return "Card" if h is None else None
    if t in ("Player", "Controller", "Opponent", "TriggeringPlayer",
             "DefendingPlayer", "Owner", "TriggeringSpellController",
             "ParentTargetController"):
        return "Player"
    if t == "SelfRef":
        return "SelfRef"
    if t in ("Any", "Or", "And"):
        return "AnyOr"
    if t in ("ParentTarget", "TriggeringSource", "LastCreated", "TrackedSet",
             "TrackedSetFiltered", "AttachedTo", "StackSpell", "StackAbility",
             "ExiledBySource", "HasChosenName"):
        return "ParentTarget"
    return None


COST_ORDER = ["cost:none", "cost:mana", "cost:tap", "cost:other"]


def cost_bucket(c):
    if not isinstance(c, dict):
        return "cost:none"
    t = c.get("type")
    if t in ("Mana", "Cost", "SelfManaCost", "DynamicGeneric"):
        return "cost:mana"
    if t in ("Tap", "TapCreatures"):
        return "cost:tap"
    if t == "Composite":
        return "cost:mana"          # composites are mana+something in practice
    return "cost:other"


def abilities_of(d):
    """Every top-level AbilityDefinition on the card, from all four buckets."""
    out = []
    for a in d.get("abilities") or []:
        out.append(a)
    for t in d.get("triggers") or []:
        e = t.get("execute")
        if isinstance(e, dict):
            out.append(e)
    for r in d.get("replacements") or []:
        e = r.get("execute")
        if isinstance(e, dict):
            out.append(e)
    return out


def build():
    CL = json.load(open(os.path.join(BUILD, "clusters.json"), encoding="utf-8"))
    rows, chunks = C.load()
    byid = {r["id"]: r for r in rows}
    members = collections.defaultdict(list)
    for cid, l in CL["cards"].items():
        if l >= 0:
            members[int(l)].append(cid)
    leaf_ids = sorted(members)

    # Two passes: first count effect-type frequency so the top N can have
    # their own columns, then build. The tail falls back to FAMILY.
    freq = collections.Counter()
    for l in leaf_ids:
        for cid in members[l]:
            d = chunks[byid[cid]["ch"]][cid]
            seen = set()
            for a in abilities_of(d):
                e = a.get("effect")
                if isinstance(e, dict) and isinstance(e.get("type"), str):
                    seen.add(e["type"])
            for sa in d.get("static_abilities") or []:
                m = C.tag(sa.get("mode"))
                if m:
                    seen.add("static:" + m)
            freq.update(seen)
    top_types = [t for t, _ in freq.most_common(TOP_N_TYPES)]
    top_set = set(top_types)
    tail_fams = sorted({family_of(t) for t in freq if t not in top_set})

    COLS = (["eff:" + t for t in top_types] + ["fam:" + f for f in tail_fams]
            + ["mass"]
            + ["head:" + h for h in HEAD_ORDER]
            + ["ctrl:Any", "ctrl:You", "ctrl:Opponent"]
            + ["target_props", "sub_frac", "sub_depth"] + COST_ORDER)
    V = np.zeros((len(leaf_ids), len(COLS)), dtype=np.float64)
    ci = {c: j for j, c in enumerate(COLS)}
    fam_by_branch = collections.defaultdict(collections.Counter)
    other_types = collections.Counter()
    fam_hits = collections.Counter()

    for k, l in enumerate(leaf_ids):
        mem = members[l]
        n = len(mem)
        acc = collections.Counter()
        props_tot = props_n = 0
        depth_tot = 0
        for cid in mem:
            d = chunks[byid[cid]["ch"]][cid]
            fams, heads, ctrls, costs = set(), set(), set(), set()
            has_sub = False
            mx = 0
            for a in abilities_of(d):
                e = a.get("effect")
                if isinstance(e, dict) and isinstance(e.get("type"), str):
                    et = e["type"]
                    if et in top_set:
                        fams.add("eff:" + et)
                    else:
                        fams.add("fam:" + family_of(et))
                    fam_hits[family_of(et)] += 1
                    if et in B.MASS_EFFECTS:
                        acc["mass"] += 1
                    tg = None
                    for kk in C.TARGET_KEYS:
                        if kk in e:
                            tg = e[kk]
                            break
                    h = head_of(tg)
                    if h:
                        heads.add(h)
                    if isinstance(tg, dict) and tg.get("type") == "Typed":
                        ctrls.add(tg.get("controller") or "Any")
                        props_tot += len(tg.get("properties") or [])
                        props_n += 1
                costs.add(cost_bucket(a.get("cost")))
                s = a.get("sub_ability")
                dep = 0
                while isinstance(s, dict):
                    dep += 1
                    s = s.get("sub_ability")
                if dep:
                    has_sub = True
                mx = max(mx, dep)
            for sa in d.get("static_abilities") or []:
                m = C.tag(sa.get("mode"))
                if m:
                    et = "static:" + m
                    if et in top_set:
                        fams.add("eff:" + et)
                    else:
                        fams.add("fam:" + family_of(et))
                    fam_hits[family_of(et)] += 1
                    h = head_of(sa.get("affected"))
                    if h:
                        heads.add(h)
            for f in fams:
                acc[f] += 1
            for h in heads:
                acc["head:" + h] += 1
            for c0 in ctrls:
                if "ctrl:" + c0 in ci:
                    acc["ctrl:" + c0] += 1
            for c0 in costs:
                acc[c0] += 1
            if has_sub:
                acc["sub_frac"] += 1
            depth_tot += mx

        for c, v in acc.items():
            if c in ci:
                V[k, ci[c]] = v / n
        V[k, ci["target_props"]] = (props_tot / props_n) if props_n else 0.0
        V[k, ci["sub_depth"]] = depth_tot / n

    return leaf_ids, COLS, V, members, CL, fam_hits, other_types


def cosine_D(M):
    nrm = np.linalg.norm(M, axis=1, keepdims=True)
    nrm[nrm == 0] = 1.0
    Z = M / nrm
    S = Z @ Z.T
    np.clip(S, -1.0, 1.0, out=S)
    D = 1.0 - S
    np.fill_diagonal(D, 0.0)
    return np.maximum(D, D.T)


def knn_pres(D, XY, K=10):
    L = D.shape[0]
    d2 = np.sqrt(((XY[:, None, :] - XY[None, :, :]) ** 2).sum(-1))
    keep = 0
    for i in range(L):
        a = [x for x in np.argsort(D[i]) if x != i][:K]
        b = [x for x in np.argsort(d2[i]) if x != i][:K]
        keep += len(set(a) & set(b))
    return keep / (L * K)


def spearman(x, y):
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    rx -= rx.mean(); ry -= ry.mean()
    return float((rx @ ry) / np.sqrt((rx @ rx) * (ry @ ry)))


def main():
    t0 = time.time()
    leaf_ids, COLS, V, members, CL, fam_hits, other_types = build()
    L = len(leaf_ids)
    tot = sum(len(m) for m in members.values())
    named = sum(v for f, v in fam_hits.items() if f != "other")
    print(f"[{time.time()-t0:5.1f}s] {L} leaves, {len(COLS)} columns; family "
          f"coverage {100*named/max(1,sum(fam_hits.values())):.1f}% named",
          file=sys.stderr)
    if other_types:
        print("  top unfamilied effect types: "
              + ", ".join(f"{k}({v})" for k, v in other_types.most_common(6)),
              file=sys.stderr)

    import umap

    def embed(D):
        return umap.UMAP(n_neighbors=N_NEIGHBORS, min_dist=MIN_DIST,
                         metric="precomputed", random_state=RANDOM_SEED,
                         verbose=False).fit_transform(D)

    ci = {c: j for j, c in enumerate(COLS)}
    fam_cols = [ci[c] for c in COLS if c.startswith(("fam:", "eff:"))]
    cost_cols = [ci[c] for c in COLS if c.startswith("cost:")]
    keep_no_cost = [j for j in range(len(COLS)) if j not in cost_cols]
    keep_no_fam = [j for j in range(len(COLS)) if j not in fam_cols]

    cands = {
        "all columns, raw-fraction cosine": cosine_D(V),
        "without cost block": cosine_D(V[:, keep_no_cost]),
        "without effect-family block": cosine_D(V[:, keep_no_fam]),
    }
    report = {}
    for name, D in cands.items():
        XY = embed(D)
        iu = np.triu_indices(L, 1)
        d2 = np.sqrt(((XY[:, None, :] - XY[None, :, :]) ** 2).sum(-1))
        report[name] = {"knn": knn_pres(D, XY), "rho": spearman(D[iu], d2[iu]),
                        "D": D, "XY": XY}
        print(f"[{time.time()-t0:5.1f}s] {name:34s} kNN@10 "
              f"{100*report[name]['knn']:5.1f}%  rho {report[name]['rho']:.3f}",
              file=sys.stderr)

    # Selection is NOT by kNN here. Dropping the effect/type block scores the
    # best kNN (68.9%) precisely because it throws away effect identity -- which
    # is the one thing this pass exists to encode, and it collapses branch
    # cohesion (median 64.2%, 14 branches under 60%). The stated bar for this
    # map is branch cohesion, so that is what selects.
    best = "all columns, raw-fraction cosine"
    D, XY = report[best]["D"], report[best]["XY"]
    print(f"[{time.time()-t0:5.1f}s] selected: {best}", file=sys.stderr)

    np.save(os.path.join(BUILD, "_eff_D.npy"), D)
    np.save(os.path.join(BUILD, "_eff_XY.npy"), XY)
    json.dump(leaf_ids, open(os.path.join(BUILD, "_eff_ids.json"), "w"))

    out = {
        "params": {
            "random_seed": RANDOM_SEED, "n_neighbors": N_NEIGHBORS,
            "min_dist": MIN_DIST, "encoding": best,
            "n_columns": len(COLS), "columns": COLS,
            "n_effect_families": len(FAM_ORDER),
            "umap_learn": importlib.metadata.version("umap-learn"),
            "numba": importlib.metadata.version("numba"),
            "numpy": np.__version__,
        },
        "encodings_tested": {k: {"knn_at_10": report[k]["knn"],
                                 "spearman_rho": report[k]["rho"]}
                             for k in report},
        "prior_passes": {
            "full_feature": {"knn_at_10": 0.444, "spearman_rho": 0.164,
                             "n_columns": 3347},
            "zone_choice": {"knn_at_10": 0.5695, "spearman_rho": 0.5537,
                            "n_columns": 15},
        },
        "family_coverage_named_pct": 100 * named / max(1, sum(fam_hits.values())),
        "n_leaves": L, "n_cards": tot,
        "leaves": [
            {"leaf": l, "x": float(XY[k][0]), "y": float(XY[k][1]),
             "n_cards": len(members[l]),
             "label": CL["labels"].get(str(l), ""),
             "sample": sorted(CL["names"][c] for c in members[l])[:6]}
            for k, l in enumerate(leaf_ids)
        ],
    }
    json.dump(out, open(os.path.join(BUILD, "leafmap_effect.json"), "w",
                        encoding="utf-8"), separators=(",", ":"),
              ensure_ascii=False)
    print(json.dumps({"selected": best,
                      "knn_at_10": round(report[best]["knn"], 4),
                      "spearman_rho": round(report[best]["rho"], 4),
                      "all": {k: [round(report[k]["knn"], 4),
                                  round(report[k]["rho"], 4)] for k in report}},
                     indent=1))


if __name__ == "__main__":
    main()
