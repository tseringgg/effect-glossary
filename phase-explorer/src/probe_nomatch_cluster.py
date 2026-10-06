#!/usr/bin/env python3
"""Part 3 measurement: cluster ONLY the cards whose abilities match no leaf at 0.90, among
themselves, with a smaller minimum group size. Places nothing and writes no layer; the only file
written is build/nomatch_cluster_probe.json (a measurement). Reads only.

Population: the review-queue cards (clean parse, unplaced by the whole-card floor) none of whose
abilities scores >= 0.90 against any leaf (by the clustering's own tokens / IDF / centroids), and
which the ability layer did not place. Features: card_features() tokens of the whole card, the same
IDF weights and L2 normalisation as the clustering (computed over the clustering's own cards).
"""
import collections
import io
import json
import os
import sys

import numpy as np

try:
    import hdbscan as _h
    _ok = hasattr(_h, "HDBSCAN")
except Exception:
    _ok = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap      # noqa: E402
import ability_rules as ar      # noqa: E402



def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import cluster_structural as cs
    sp = ap.Space()
    R = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    A = ap.jl("ability_layer.json")
    clusters = ap.jl("clusters.json")
    print("hdbscan usable:", _ok, "| clustering params:", json.dumps(clusters.get("params"))[:300])
    rec_chunk = P["recovered"]["chunk"]
    entry_of = lambda fid: sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]
    best, rfaces = {}, collections.defaultdict(set)
    for x in P["review_queue"]:
        rfaces[x["card"]].add(x["face"])
        if x["card"] not in best or x["similarity"] > best[x["card"]]["similarity"]:
            best[x["card"]] = x
    pop_all = sorted(o for o in best if R[o]["status"] != "out_of_scope"
                     and R[o]["placement"]["method"] in ("unplaced", "ability"))
    # per card: best ability score (any ability with tokens), n abilities with tokens
    info = {}
    flat = []
    for o in pop_all:
        for fid in sorted(rfaces[o]):
            e = entry_of(fid)
            for b, i, it, t in ap.ability_items(e):
                flat.append((o, fid, [k for k in sorted(t) if k in sp.vocab]))
    leaves, scores = ar.score_items(sp, [f[2] for f in flat])
    for (o, fid, tk), l, s in zip(flat, leaves, scores):
        d = info.setdefault(o, {"n": 0, "ntok": 0, "max": 0.0, "toks": []})
        d["n"] += 1
        if tk:
            d["ntok"] += 1
            d["max"] = max(d["max"], s)
            d["toks"].append(tk)
    placed_by_ab = set(A["cards"])
    cnt = {}
    cnt["review_queue_cards"] = len(pop_all)
    cnt["placed_by_ability_layer"] = len(placed_by_ab)
    nomatch_all = [o for o in pop_all if info.get(o, {"max": 0})["max"] < 0.90]
    cnt["no_ability_at_0.90 (all review cards)"] = len(nomatch_all)
    cnt["no_ability_at_0.90, blended >= 0.50"] = sum(1 for o in nomatch_all if best[o]["similarity"] >= 0.50)
    cnt["no_ability_at_0.90, blended < 0.50"] = sum(1 for o in nomatch_all if best[o]["similarity"] < 0.50)
    cnt["still_unplaced_review_cards"] = len([o for o in pop_all if o not in placed_by_ab])
    cnt["still_unplaced_with_any_ability_at_0.90"] = len([o for o in pop_all if o not in placed_by_ab and info[o]["max"] >= 0.90])
    cnt["blended>=0.50 and no ability at 0.90"] = cnt["no_ability_at_0.90, blended >= 0.50"]
    print(json.dumps(cnt, indent=1))

    pop = nomatch_all                       # the measured population (none were placed by the ability layer)
    assert not (set(pop) & placed_by_ab)
    feats = {}
    for o in pop:
        fs = set()
        for fid in rfaces[o]:
            fs |= {k for k in cs.card_features(entry_of(fid)) if k in sp.vocab}
        feats[o] = fs
    Xc = sp.weigh(sp.encode([sorted(feats[o]) for o in pop]))
    # single-ability / token-count facts
    single = sum(1 for o in pop if info[o]["n"] == 1)
    notok = sum(1 for o in pop if not feats[o])
    res = {"counts": cnt, "population": len(pop), "single_ability": single, "no_features": notok,
           "tokens_per_card": dict(sorted(collections.Counter(len(feats[o]) for o in pop).items())[:12])}
    import hdbscan
    D = Xc.toarray().astype(np.float32)
    # cosine on L2-normalised rows == euclidean on them; use the same metric the clustering used
    runs = {}
    for mcs in (5, 4, 3, 2):
        for ms in (None,):
            cl = hdbscan.HDBSCAN(min_cluster_size=mcs, min_samples=1, metric="euclidean",
                                 cluster_selection_method="leaf").fit(D)
            lab = cl.labels_
            grp = collections.defaultdict(list)
            for o, l in zip(pop, lab):
                if l >= 0:
                    grp[int(l)].append(o)
            sizes = sorted((len(v) for v in grp.values()), reverse=True)
            runs[mcs] = {"groups": len(grp), "cards_in_groups": sum(sizes),
                         "cards_in_groups_ge5": sum(s for s in sizes if s >= 5),
                         "groups_ge5": sum(1 for s in sizes if s >= 5),
                         "size_hist": dict(sorted(collections.Counter(min(s, 20) for s in sizes).items())),
                         "noise": int((lab < 0).sum())}
            runs[mcs]["_grp"] = grp
    # the chosen run for the samples: min_cluster_size=3
    sel = 3
    grp = runs[sel]["_grp"]
    # generic-token domination: a group is dominated by a generic token when the tokens shared by >= 80% of its
    # members are all "generic" (df share of the clustering corpus >= 5%) -- or when only 1 token is shared
    n_all = len(sp.order)
    gen = {k: sp.df[v] / n_all for k, v in sp.vocab.items()}
    dom = 0
    sample = []
    for l, mem in sorted(grp.items(), key=lambda kv: -len(kv[1])):
        share = collections.Counter()
        for o in mem:
            for k in feats[o]:
                share[k] += 1
        core = [k for k, c in share.items() if c / len(mem) >= 0.8]
        spec = [k for k in core if gen[k] < 0.05]
        if not spec:
            dom += 1
        if len(sample) < 60:
            sample.append({"n": len(mem), "core": sorted(core), "specific_core": sorted(spec), "cards": mem})
    for k_, v_ in runs.items():
        cores = []
        for mem in v_["_grp"].values():
            share = collections.Counter(t for o in mem for t in feats[o])
            core = [t for t, c in share.items() if c / len(mem) >= 0.8]
            cores.append((len(mem), core))
        v_["groups_with_no_effect_token_in_core"] = sum(1 for n_, c_ in cores if not any(t.startswith("eff:") for t in c_))
        v_["groups_with_empty_core"] = sum(1 for n_, c_ in cores if not c_)
        v_["cards_in_groups_ge5_with_an_effect_token_core"] = sum(n_ for n_, c_ in cores if n_ >= 5 and any(t.startswith("eff:") for t in c_))
    res["runs"] = {str(k): {kk: vv for kk, vv in v.items() if kk != "_grp"} for k, v in runs.items()}
    res["chosen_min_cluster_size"] = sel
    res["groups_dominated_by_generic_tokens"] = dom
    res["groups_total_chosen"] = len(grp)
    res["generic_rule"] = "no token shared by >= 80% of members has document frequency < 5% of the clustering corpus"
    res["_sample"] = sample
    res["_single"] = {o: info[o]["n"] for o in pop}
    with io.open(os.path.join(ap.BUILD, "nomatch_cluster_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({k: v for k, v in res.items() if not k.startswith("_")}, ensure_ascii=False,
                            sort_keys=True, separators=(",", ":")))
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("_")}, indent=1, ensure_ascii=False))
    # group detail for samples (printed): five mid-sized groups with a specific shared token, spaced through the list,
    # and one generic-dominated group, each in full
    names = {o: R[o]["name"] for o in pop}
    mid = [x for x in sample if 5 <= x["n"] <= 12 and x["specific_core"]]
    gen_ = [x for x in sample if x["n"] >= 5 and not x["specific_core"]]
    step = max(1, len(mid) // 5)
    chosen = mid[::step][:5] + gen_[:1]
    for s_ in chosen:
        print(chr(10) + "=== group of %d | shared tokens: %s%s" % (s_["n"], s_["core"], "" if s_["specific_core"] else "   <-- GENERIC-DOMINATED"))
        for o in s_["cards"]:
            e = entry_of(sorted(rfaces[o])[0])
            print("   %-32s %s" % (names[o][:32], (e.get("oracle_text") or "").replace(chr(10), " / ")[:150]))


if __name__ == "__main__":
    main()
