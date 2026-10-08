#!/usr/bin/env python3
"""Land denial diagnosis, part 3: how widespread is the problem (Oracle-tag sizing) and a re-run of the
no-match clustering measurement with a looser signature. DIAGNOSTIC ONLY.

Oracle tags are used here to MEASURE where unorganized cards sit. They never feed a placement: using
tags to judge or to drive placement would be circular. Writes only build/land_denial_probe3.json.
"""
import collections
import io
import json
import os
import re
import sys

try:
    import hdbscan as H
except Exception:
    H = None
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap      # noqa: E402
import ability_rules as ar      # noqa: E402
import cluster_structural as cs  # noqa: E402
import probe_land_denial as pl  # noqa: E402  (TAGS path)

LOOSE_TYPES = ("Destroy", "DestroyAll", "Sacrifice", "Bounce", "ChangeZone", "ChangeZoneAll", "Exile", "ExileTop")


def loosen(tokens):
    """target-shape token only for destroy / sacrifice / bounce / exile effects."""
    effs = {t[4:] for t in tokens if t.startswith("eff:") and "|" not in t}
    if effs & set(LOOSE_TYPES):
        return {t for t in tokens if not t.startswith("eff:")}
    return set(tokens)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sp = ap.Space()
    L = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    rec_chunk = P["recovered"]["chunk"]
    UNC = ap.jl("unorganized_cards.json")["groups"]
    group_of = {c["c"]: int(g) for g, lst in UNC.items() for c in lst}
    AL = ap.jl("ability_ledger.json")
    cols = AL["meta"]["columns"]
    best_ab = collections.defaultdict(float)
    for r in AL["rows"]:
        if r[cols.index("score")] is not None:
            best_ab[r[0]] = max(best_ab[r[0]], r[cols.index("score")])
    entry_of = lambda fid: sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]
    faces_of = collections.defaultdict(list)
    for r in sp.rows:
        faces_of[r["id"].split("/")[0]].append(r["id"])
    for fid in sorted(rec_chunk):
        faces_of[fid.split("/")[0]].append(fid)
    in_scope = {o for o, r in L.items() if r["status"] != "out_of_scope"}

    tags = json.load(io.open(pl.TAGS, encoding="utf-8"))
    rows = []
    for t in tags:
        mem = {x["oracle_id"] for x in t["taggings"]} & in_scope
        if len(mem) < 5:
            continue
        un = [o for o in mem if L[o]["placement"]["method"] == "unplaced"]
        meth = collections.Counter(L[o]["placement"]["method"] for o in mem if L[o]["placement"]["method"] != "unplaced")
        rows.append({"slug": t["slug"], "n": len(mem), "placed": len(mem) - len(un), "unorg": len(un),
                     "share": round(len(un) / len(mem), 3),
                     "groups": dict(sorted(collections.Counter(group_of.get(o) for o in un).items(), key=lambda kv: str(kv[0]))),
                     "placed_by": dict(meth), "unorg_oids": sorted(un)})
    print("tags with >= 5 in-scope cards:", len(rows))
    by_count = sorted(rows, key=lambda r: (-r["unorg"], r["slug"]))
    print("\n=== top 25 tags by number of unorganized cards")
    for r in by_count[:25]:
        print("%-34s n=%-5d unorg=%-4d share=%.2f groups=%s placed_by=%s" % (r["slug"], r["n"], r["unorg"], r["share"],
              r["groups"], {k: v for k, v in r["placed_by"].items()}))
    by_share = sorted([r for r in rows if r["n"] >= 20], key=lambda r: (-r["share"], -r["unorg"], r["slug"]))
    print("\n=== top 25 tags by share unorganized (tags with >= 20 cards)")
    for r in by_share[:25]:
        print("%-34s n=%-5d unorg=%-4d share=%.2f groups=%s" % (r["slug"], r["n"], r["unorg"], r["share"], r["groups"]))
    tot_un = sum(1 for o in in_scope if L[o]["placement"]["method"] == "unplaced")
    tagged = set().union(*({x["oracle_id"] for x in t["taggings"]} for t in tags)) & in_scope
    un_tagged = [o for o in tagged if L[o]["placement"]["method"] == "unplaced"]
    print("\nin-scope cards:", len(in_scope), "| carrying at least one oracle tag:", len(tagged),
          "| unorganized:", tot_un, "| unorganized AND tagged:", len(un_tagged))

    # --- top-20 tags: why can't the unorganized cards group on their own?
    toks = {}
    loose_sig = {}
    def card_tokens(o):
        if o in toks:
            return toks[o]
        s, ls = set(), set()
        for fid in faces_of.get(o, []):
            for b, i, it, t in ap.ability_items(entry_of(fid)):
                tt = {k for k in t if k in sp.vocab}
                s |= tt
                ls |= loosen(tt)
        toks[o], loose_sig[o] = s, ls
        return s
    print("\n=== top 20 tags (by unorganized count): what stops the unorganized cards forming a group")
    diag = {}
    for r in by_count[:20]:
        un = r["unorg_oids"]
        exact = collections.Counter(); loose = collections.Counter()
        no_tok = 0
        for o in un:
            s = card_tokens(o)
            if not s:
                no_tok += 1
                continue
            exact[frozenset(t for t in s if not (t.startswith("eff:") and "|" in t) and not t.startswith("tgt:"))] += 1   # effect types only
            loose[frozenset(loose_sig[o])] += 1
        big_e = sum(n for n in exact.values() if n >= 5); big_l = sum(n for n in loose.values() if n >= 5)
        gaps = sum(1 for o in un if group_of.get(o) == 1)
        hi = sum(1 for o in un if best_ab.get(o, 0) >= 0.9)
        d = {"unorg": len(un), "gap_cards": gaps, "no_tokens": no_tok, "distinct_effect_sigs": len(exact),
             "cards_in_sigs_of_5plus": big_e, "distinct_loose_sigs": len(loose), "cards_in_loose_sigs_of_5plus": big_l,
             "with_ability_ge_0.90": hi}
        diag[r["slug"]] = d
        print("%-30s unorg=%-4d gap=%-4d notok=%-3d | effect-type sigs: %d distinct, %d cards in sigs of >=5 | loose sigs: %d distinct, %d in >=5 | ability>=0.90: %d" % (
            r["slug"], len(un), gaps, no_tok, len(exact), big_e, len(loose), big_l, hi))

    # --- part 6: the no-match population, baseline vs looser signature
    best, rfaces = {}, collections.defaultdict(set)
    for x in P["review_queue"]:
        rfaces[x["card"]].add(x["face"])
        if x["card"] not in best or x["similarity"] > best[x["card"]]["similarity"]:
            best[x["card"]] = x
    pop_all = sorted(o for o in best if L[o]["status"] != "out_of_scope" and L[o]["placement"]["method"] in ("unplaced", "ability"))
    flat = [(o, fid, [k for k in sorted(t) if k in sp.vocab]) for o in pop_all for fid in sorted(rfaces[o])
            for b, i, it, t in ap.ability_items(entry_of(fid))]
    lv, sc = ar.score_items(sp, [f[2] for f in flat])
    mx = collections.defaultdict(float)
    for (o, fid, tk), l, s in zip(flat, lv, sc):
        if tk:
            mx[o] = max(mx[o], s)
    A = ap.jl("ability_layer.json")["cards"]
    pop = [o for o in pop_all if mx[o] < 0.90 and o not in A]
    print("\n=== no-match population:", len(pop))
    roles_path = os.environ.get("LD_ROLES")
    core = set()
    if roles_path:
        roles = json.load(io.open(roles_path, encoding="utf-8"))
        core = {o for o in pop if roles.get(L[o]["name"]) in ("D", "DP", "DB")}
        allcore = {o for o, r in L.items() if roles.get(r["name"]) in ("D", "DP", "DB")}
        print("core land denial cards in this population: %d of %d core cards (%s)" % (len(core), len(allcore), ", ".join(sorted(L[o]["name"] for o in core))[:600]))
    n_all = len(sp.order)
    gen = {k: sp.df[v] / n_all for k, v in sp.vocab.items()}

    def run(feat_fn, label):
        F = {o: feat_fn(o) for o in pop}
        X = sp.weigh(sp.encode([sorted(F[o]) for o in pop])).toarray().astype(np.float32)
        out = {}
        for mcs in (5, 3):
            lab = H.HDBSCAN(min_cluster_size=mcs, min_samples=1, metric="euclidean", cluster_selection_method="leaf").fit(X).labels_
            grp = collections.defaultdict(list)
            for o, l in zip(pop, lab):
                if l >= 0:
                    grp[int(l)].append(o)
            spec = eff = 0; cards_spec = cards_eff = 0
            coreg = 0
            for mem in grp.values():
                share = collections.Counter(t for o in mem for t in F[o])
                core_t = [t for t, c in share.items() if c / len(mem) >= 0.8]
                if any(gen[t] < 0.05 for t in core_t):
                    spec += 1
                    if len(mem) >= 5: cards_spec += len(mem)
                if any(t.startswith("eff:") for t in core_t):
                    eff += 1
                    if len(mem) >= 5: cards_eff += len(mem)
            out[mcs] = {"groups": len(grp), "cards_in_groups": sum(len(v) for v in grp.values()),
                        "cards_in_groups_ge5": sum(len(v) for v in grp.values() if len(v) >= 5),
                        "groups_ge5": sum(1 for v in grp.values() if len(v) >= 5),
                        "groups_with_specific_shared_token": spec, "cards_in_ge5_groups_with_specific_token": cards_spec,
                        "groups_with_effect_token": eff, "cards_in_ge5_groups_with_effect_token": cards_eff,
                        "core_cards_grouped": sum(1 for mem in grp.values() for o in mem if o in core)}
        print("\n%s" % label)
        for mcs, v in out.items():
            print("  min size %d: %s" % (mcs, v))
        return out
    def feats_review(o, loose_):
        s = set()
        for fid in rfaces[o]:
            tt = {k for k in cs.card_features(entry_of(fid)) if k in sp.vocab}
            s |= tt
        return s
    def loose_review(o):
        s = set()
        for fid in rfaces[o]:
            for b, i, it, t in ap.ability_items(entry_of(fid)):
                s |= loosen({k for k in t if k in sp.vocab})
        return s
    base2 = run(lambda o: feats_review(o, False), "baseline: whole-card card_features tokens (the earlier measurement's features)")
    loose2 = run(loose_review, "looser signature: target-shape token only for destroy / sacrifice / bounce / exile effects")
    res = {"tags": [{k: v for k, v in r.items() if k != "unorg_oids"} for r in by_count], "top20_diag": diag,
           "pop": len(pop), "core_in_pop": len(core), "baseline": {str(k): v for k, v in base2.items()},
           "loose": {str(k): v for k, v in loose2.items()}}
    with io.open(os.path.join(ap.BUILD, "land_denial_probe3.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
