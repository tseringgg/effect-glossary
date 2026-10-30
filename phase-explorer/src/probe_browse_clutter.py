#!/usr/bin/env python3
"""Part 1 of the browse-group probe (READ ONLY): how cluttered are group search results today, and how many groups share a core name.

    python src/probe_browse_clutter.py [OUT_JSON]      # default: the scratchpad-free build/browse_groups_clutter.json (a new file)

Runs the real reports/groupsearch.js (in dukpy) against the real build/group_search/index.json with the page's defaults (tentative and community-tag groups on). Changes nothing.

THE SEARCH SET. Seed 20261029, fixed here before anything was computed. 7 searches are fixed (the owner's examples); the other 43 are drawn with random.Random(SEED) from three pools written below
(mechanics, slang, card types), without looking at any result. The 10 searches whose top 10 are read are drawn from the 50 with the same generator, after the 50.
NEAR-TWINS. Two results are near-twins if they have the same core name (qualifiers, 'Family › ' prefix and 'less common kinds' removed) OR their card overlap is 70% or more. Overlap is measured
two ways and both are reported: the overlap coefficient |A∩B| / min(|A|,|B|) (a small group inside a big one counts) and the Jaccard |A∩B| / |A∪B| (strict). Distinct ideas = connected components.
"""
import collections
import itertools
import json
import os
import random
import sys

import dukpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browse_probe_data as P

SEED = 20261029
FIXED = ["dragon", "draw cards", "board wipe", "recursion", "land denial", "sacrifice", "tutor"]
POOLS = {
    "mechanics": ["flying", "deathtouch", "trample", "lifelink", "haste", "flash", "hexproof", "indestructible", "menace", "vigilance", "cascade", "proliferate", "convoke", "scry", "surveil",
                  "landfall", "equip", "kicker", "flashback", "cycling", "ward", "prowess", "undying", "storm"],
    "slang": ["ramp", "mana rock", "mana dork", "wrath", "counterspell", "removal", "burn", "reanimate", "blink", "flicker", "mill", "stax", "anthem", "cantrip", "fog", "bounce", "edict",
              "wheel", "pump", "cost reduction", "extra turn", "voltron", "discard", "lifegain", "treasure", "clone", "fetch land", "overrun", "hatebear", "looting"],
    "types": ["artifact", "enchantment", "equipment", "aura", "saga", "planeswalker", "vehicle", "instant", "land", "creature", "elf", "zombie", "goblin"],
}


def search_set():
    rng = random.Random(SEED)
    pool = [q for k in ("mechanics", "slang", "types") for q in POOLS[k]]
    pool = [q for q in pool if q not in FIXED]
    qs = FIXED + rng.sample(pool, 43)
    reads = rng.sample(qs, 10)
    return qs, reads


def components(n, edges):
    p = list(range(n))

    def f(x):
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x
    for a, b in edges:
        p[f(a)] = f(b)
    return len({f(i) for i in range(n)}), [f(i) for i in range(n)]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(P.BUILD, "browse_groups_clutter.json")
    D = P.Data()
    kf = P.jl(os.path.join(P.BUILD, "keyword_facet.json"))["keywords"]
    itp = dukpy.JSInterpreter()
    itp.evaljs(io_read(os.path.join(P.HERE, "reports", "groupsearch.js")))
    words = {w: 1 for w in io_read(os.path.join(P.BUILD, "group_search", "words.txt")).split()}
    itp.evaljs("var IDX = GroupSearch.build(%s); var WORDS = %s; function ALLOW(e){ return e.key; }" % (json.dumps(D.search_doc), json.dumps(words)))

    def cards_of(entry):
        gid, layer = entry[0], entry[4]
        if layer == "m":
            s = set()
            for m in entry[12]:
                s |= D.members.get(m, set())
            return s
        if layer == "y":
            return set(kf.get(gid[3:], {}).get("c", []))
        return D.members.get(gid, set())

    qs, reads = search_set()
    rows, top10 = [], {}
    for q in qs:
        r = json.loads(itp.evaljs("JSON.stringify((function(){var r=GroupSearch.search(IDX,%s,{allow:ALLOW,words:WORDS});return {g:r.groups.map(function(x){return [x.e.gid,x.tier,x.why]}),f:r.family.map(function(x){return x.e.gid}),d:r.dym?r.dym.to:null};})())" % json.dumps(q)))
        res = [D.sidx[g[0]] for g in r["g"]]
        n = len(res)
        cs = [cards_of(e) for e in res]
        cn = [P.core_name(e[2]) for e in res]
        e_core, e_ov, e_jac = [], [], []
        for i, j in itertools.combinations(range(n), 2):
            if cn[i] == cn[j]:
                e_core.append((i, j))
            a, b = cs[i], cs[j]
            if a and b:
                inter = len(a & b)
                if inter / min(len(a), len(b)) >= 0.7:
                    e_ov.append((i, j))
                if inter / len(a | b) >= 0.7:
                    e_jac.append((i, j))
        k_core = components(n, e_core)[0] if n else 0
        k_any, _ = components(n, e_core + e_ov) if n else (0, [])
        k_strict, _ = components(n, e_core + e_jac) if n else (0, [])
        tw = lambda edges: len({x for e in edges for x in e})
        row = {"q": q, "results": n, "family_only": len(r["f"]), "by_layer": dict(collections.Counter(e[4] for e in res)),
               "twin_results_core": tw(e_core), "twin_results_overlap": tw(e_core + e_ov), "twin_results_strict": tw(e_core + e_jac),
               "ideas_core_only": k_core, "ideas": k_any, "ideas_strict": k_strict, "dym": r["d"]}
        rows.append(row)
        if q in reads:
            top10[q] = [{"gid": e[0], "name": e[2], "layer": e[4], "size": len(cs[i]), "tier": r["g"][i][1], "why": r["g"][i][2]} for i, e in enumerate(res[:10])]
    # layers and core names, all groups
    fine = D.fine
    by_layer = collections.Counter(P.layer_of(g) for g in fine)
    cores = collections.defaultdict(list)
    for g, v in fine.items():
        cores[P.core_name(v[0])].append(g)
    share = {g for gs in cores.values() if len(gs) > 1 for g in gs}
    share_by_layer = collections.Counter(P.layer_of(g) for g in share)
    cross = sum(1 for gs in cores.values() if len({P.layer_of(g) for g in gs}) > 1)
    big = sorted(((len(gs), c) for c, gs in cores.items() if len(gs) > 1), reverse=True)[:15]
    out = {"seed": SEED, "searches": rows, "top10": top10, "reads": reads,
           "layers": dict(by_layer), "fine_groups": len(fine), "fine_groups_in_manual_index": len(D.groups_all),
           "search_index_by_layer": dict(collections.Counter(g[4] for g in D.search_doc["groups"])),
           "core_families": sum(1 for gs in cores.values() if len(gs) > 1), "groups_sharing_core": len(share), "share_by_layer": dict(share_by_layer),
           "families_spanning_layers": cross, "largest_families": [[n, c] for n, c in big], "distinct_cores": len(cores)}
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("wrote", out_path)


def io_read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    main()
