#!/usr/bin/env python3
"""Land denial diagnosis, part 2: variants, tokens, clustering and leaf coherence (diagnosis only).
Reads build/land_denial_probe.json (probe_land_denial.py) and the hand roles (a judgement call recorded in
build/land_denial_roles.json by this script). Prints; writes only build/land_denial_probe2.json.
"""
import collections
import io
import json
import os
import re
import sys

try:
    import hdbscan  # noqa: F401
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap      # noqa: E402
import cluster_structural as cs  # noqa: E402

ROLES_PATH = os.environ.get("LD_ROLES")


def variant(t):
    t = re.sub(r"\([^)]*\)", " ", t).lower()
    if re.search(r"destroy all lands\b|destroy all lands\.", t):
        return "destroy all lands"
    if re.search(r"destroy all (?:artifacts, )?(?:creatures|artifacts)[^.]*lands", t):
        return "destroy all artifacts/creatures AND lands"
    if re.search(r"destroy all nonbasic lands", t):
        return "destroy all nonbasic lands"
    if re.search(r"destroy all (?:islands|forests|mountains|swamps|plains)", t):
        return "destroy all <basic type>"
    if re.search(r"exile all lands", t):
        return "exile all lands"
    if re.search(r"return all lands|return all (?:islands|plains)", t):
        return "return all lands (bounce)"
    if re.search(r"return all permanents", t):
        return "return all permanents (bounce)"
    if re.search(r"(?:exile|destroy) all (?:nontoken |nonartifact )?permanents", t):
        return "exile/destroy all permanents"
    if re.search(r"each player sacrifices (?:\w+ )?(?:x |\w+ )?lands", t) or re.search(r"sacrifices x lands|sacrifices (?:four|five|three) lands|sacrifices all lands", t):
        return "each player sacrifices N lands"
    if re.search(r"chooses [^.]*lands? [^.]*sacrifices the rest|chooses a number of lands|sacrifices half", t):
        return "each player keeps N lands / balance"
    if re.search(r"for each land|each land", t):
        return "per-land effect"
    if re.search(r"destroy (?:all|each|x) ", t) and "land" in t:
        return "other destroy-lands"
    return "other"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    d = json.load(io.open(os.path.join(ap.BUILD, "land_denial_probe.json"), encoding="utf-8"))
    roles = json.load(io.open(ROLES_PATH, encoding="utf-8"))
    pc = d["per_card"]
    sp = ap.Space()
    R = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    rec_chunk = P["recovered"]["chunk"]
    phr = ap.jl("leaf_phrases.json")["leaves"]
    entry_of = lambda fid: sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]
    core = {o: i for o, i in pc.items() if roles.get(i["name"]) in ("D", "DP", "DB")}
    print("core cards:", len(core), collections.Counter(roles[i["name"]] for i in core.values()))

    # -- token signatures by variant
    sigs = collections.defaultdict(collections.Counter)
    ex = collections.defaultdict(lambda: collections.defaultdict(list))
    for o, i in core.items():
        v = variant(i["oracle"])
        i["variant"] = v
        # the ability whose text mentions land / permanents most directly
        best = None
        for a in i["abilities"]:
            if a.get("tokens") and re.search(r"land|permanent|island|forest|mountain|plains|swamp", (a["t"] or "").lower()):
                best = a
                break
        toks = tuple(t for t in (best["tokens"] if best else []) if t.startswith("eff:") and "|" not in t) + \
               tuple(t for t in (best["tokens"] if best else []) if t.startswith("tgt:"))
        s = " ".join(toks) or "(no tokens on a land ability)"
        sigs[v][s] += 1
        ex[v][s].append(i["name"])
    print("\n=== token signature of the land-relevant ability, grouped by variant")
    for v, c in sorted(sigs.items(), key=lambda kv: -sum(kv[1].values())):
        print("\n%s  (%d cards, %d distinct signatures)" % (v, sum(c.values()), len(c)))
        for s, n in c.most_common():
            print("    %2d  %s   e.g. %s" % (n, s[:150], ", ".join(ex[v][s][:3])))

    # -- cluster only the core cards, min size 3, whole-card tokens
    import hdbscan as H
    import numpy as np
    oids = sorted(core)
    feats = []
    for o in oids:
        fs = set()
        for fid in {a["face"] for a in core[o]["abilities"]} or []:
            fs |= {k for k in cs.card_features(entry_of(fid)) if k in sp.vocab}
        feats.append(sorted(fs))
    have = [k for k, f in enumerate(feats) if f]
    X = sp.weigh(sp.encode([feats[k] for k in have])).toarray().astype(np.float32)
    res = {}
    for mcs, ms in ((3, 1), (3, 3)):
        lab = H.HDBSCAN(min_cluster_size=mcs, min_samples=ms, metric="euclidean", cluster_selection_method="leaf").fit(X).labels_
        grp = collections.defaultdict(list)
        for k, l in zip(have, lab):
            if l >= 0:
                grp[int(l)].append(core[oids[k]]["name"])
        res["min%d_ms%d" % (mcs, ms)] = {"cards_with_features": len(have), "cards_without": len(oids) - len(have),
                                         "grouped": sum(len(v) for v in grp.values()), "groups": sorted(grp.values(), key=lambda v: -len(v))}
        print("\n=== cluster only the core cards: min_cluster_size=%d min_samples=%d: %d of %d cards with features grouped, %d groups" % (
            mcs, ms, sum(len(v) for v in grp.values()), len(have), len(grp)))
        for g in sorted(grp.values(), key=lambda v: -len(v)):
            print("    %d: %s" % (len(g), ", ".join(g)))
    # -- leaves holding placed core cards
    print("\n=== leaves that hold core cards (members that are core / leaf size)")
    leafcards = collections.defaultdict(list)
    for o, i in core.items():
        if i["method"] != "unplaced" and i.get("leaf") is not None:
            leafcards[i["leaf"]].append(i["name"])
    for l, names in sorted(leafcards.items(), key=lambda kv: -len(kv[1])):
        mem = [f for f, ll in sp.lab.items() if ll == l]
        tx = []
        for f in mem[:400]:
            e = entry_of(f) if f in sp.byid or f in rec_chunk else {}
        e_ = phr.get(str(l)) or {}
        ph = e_.get("edited") or (e_["phrases"][0]["phrase"] if e_.get("phrases") else "") or sp.clusters["labels"].get(str(l), "")[:60]
        import random
        random.Random(l).shuffle(mem)
        sample = []
        for f in mem[:6]:
            e = entry_of(f)
            sample.append("%s :: %s" % (e.get("name"), re.sub(r"\s+", " ", (e.get("oracle_text") or ""))[:70]))
        print("\nleaf %d '%s' (%d cards); core cards in it: %s" % (l, ph[:50], len(mem), ", ".join(names)))
        for s in sample:
            print("      ", s)
    with io.open(os.path.join(ap.BUILD, "land_denial_probe2.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"cluster": res, "variants": {v: dict(c) for v, c in sigs.items()}}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
