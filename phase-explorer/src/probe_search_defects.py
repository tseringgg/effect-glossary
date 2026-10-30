#!/usr/bin/env python3
"""Part 1 of the search-fixes work: investigate the group-search defects the clutter probe found. READ ONLY: writes build/search_defects_probe.json (a new file) and nothing else.

    python src/probe_search_defects.py

It runs the real reports/groupsearch.js (dukpy) against the index the PAGE builds at run time: build/group_search/index.json plus the type pages (reports/typegroups.js) and the ability-type pages
(reports/abilitypages.js), with the page's defaults (tentative and community-tag groups on). The earlier clutter probe used the file alone, so its counts left out those two page kinds; this one does not.
The 100 searches: the 50 of the clutter probe (src/probe_browse_clutter.py, seed 20261029), the 30 of reports/group-search-baseline-queries.json and the 20 of reports/group-search-fresh-queries.json.
"""
import collections
import io
import json
import os
import re
import sys

import dukpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browse_probe_data as P
import probe_browse_clutter as C

OUT = os.path.join(P.BUILD, "search_defects_probe.json")
STOPW = set("a an the of to and or for in on at by with from your you it its that this is are be as".split())


def norm(s):
    s = re.sub(r"[^a-z0-9]+", " ", s.lower().replace("'", "").replace("’", ""))
    return s.strip()


def stem(w):
    n = len(w)
    if n > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if n > 4 and re.search(r"(ss|x|z|ch|sh)es$", w):
        return w[:-2]
    if n > 3 and w.endswith("s") and not re.search(r"(ss|us|is)$", w):
        return w[:-1]
    return w


def variants(w):
    s = stem(w)
    v = [s]
    if len(s) > 5 and s.endswith("ing"):
        v.append(s[:-3])
    elif len(s) > 4 and s.endswith("ed"):
        v.append(s[:-2])
    return v


def stems(s):
    t = norm(s)
    return [stem(x) for x in t.split()] if t else []


def queries():
    qs, _ = C.search_set()
    out = [("probe", q) for q in qs]
    b = json.load(open(os.path.join(P.HERE, "reports", "group-search-baseline-queries.json"), encoding="utf-8"))
    for k in ("slang", "keywords", "mechanics", "partial", "typos"):
        out += [("baseline", q) for q in b[k]]
    f = json.load(open(os.path.join(P.HERE, "reports", "group-search-fresh-queries.json"), encoding="utf-8"))
    out += [("fresh", t) for t in f["drawn_terms"].values()]
    out += [("fresh", q) for q in f["near_collisions"] + f["typos"]]
    return out


def build_page_doc(D):
    doc = json.loads(json.dumps(D.search_doc))
    td = P.jl(os.path.join(P.BUILD, "type_groups", "index.json"))
    for g in td["groups"]:
        gid = "typepage:" + g[0][3:]
        doc["groups"].append([gid, g[0], g[1], "", "ty", g[4], 0, "", 0, "", ""])
        for a in g[5]:
            if a not in doc["aliases"]:
                doc["aliases"][a] = {"p": a, "g": [gid], "fit": "", "note": "", "s": "hand"}
    ai = P.jl(os.path.join(P.BUILD, "ability_pages", "index.json"))
    for g in ai["groups"]:
        gid = "abpage:" + g[0][3:]
        doc["groups"].append([gid, g[0], g[1], "", "ab", g[3], 0, "", 0, "", ""])
        for a in g[6]:
            if a in doc["aliases"]:
                if gid not in doc["aliases"][a]["g"]:
                    doc["aliases"][a] = dict(doc["aliases"][a], g=doc["aliases"][a]["g"] + [gid])
            else:
                doc["aliases"][a] = {"p": a, "g": [gid], "fit": "", "note": "", "s": "hand"}
    return doc


class Engine:
    def __init__(self, D):
        self.D = D
        self.doc = build_page_doc(D)
        self.itp = dukpy.JSInterpreter()
        with io.open(os.path.join(P.HERE, "reports", "groupsearch.js"), encoding="utf-8") as fh:
            self.itp.evaljs(fh.read())
        words = {w: 1 for w in io.open(os.path.join(P.BUILD, "group_search", "words.txt"), encoding="utf-8").read().split()}
        self.words = words
        self.itp.evaljs("GroupSearch.LAYER_RANK.ty = 5.5; GroupSearch.LAYER_RANK.ab = 5.6; var IDX = GroupSearch.build(%s); var WORDS = %s; function ALLOW(e){ return e.key; }" % (json.dumps(self.doc), json.dumps(words)))
        self.rows = {g[0]: g for g in self.doc["groups"]}
        self.hand_members = collections.Counter()
        for g, ms in D.members.items():
            if g.startswith("hand:"):
                self.hand_members[g] = len(ms)

    def run(self, q):
        r = json.loads(self.itp.evaljs("JSON.stringify((function(){var r=GroupSearch.search(IDX,%s,{allow:ALLOW,words:WORDS});return {g:r.groups.map(function(x){return [x.e.gid,x.tier,x.why,x.via,x.dym||'',x.drafted?1:0]}),f:r.family.length,d:r.dym?r.dym.to:null};})())" % json.dumps(q)))
        return r

    def kind(self, q, row, tier, why, via, dym, drafted):
        """A refined match kind for a result: what the weak kinds are (prefix of a longer word, description, 'most', slug, drafted alias, fuzzy)."""
        if dym:
            return "fuzzy"
        if why == "name" and tier == 0:
            return "name exact"
        if why == "alias":
            return "alias exact (drafted)" if drafted else ("alias exact" if tier == 1 else "alias partial")
        if why == "slug":
            return "slug exact" if tier == 1 else "slug words"
        if why == "most":
            return "most words"
        if why == "description":
            return "description" + (" (auto-drafted example line)" if row[8] and (row[7] or "").startswith("Example") else " (written)" if not row[8] else " (drafted)")
        if why == "name":
            toks = [t for t in norm(q).split()]
            core = [t for t in toks if t not in STOPW] or toks
            names = [stems(row[2])] + [stems(x) for x in (row[11] if len(row) > 11 and row[11] else [])]
            for ns in names:
                ok = True
                for t in core:
                    vs = variants(t)
                    if not any(w in vs for w in ns):
                        ok = False
                        break
                if ok:
                    return "name word"
            return "name prefix (query word is the start of a longer word)"
        return why


WEAK = ("fuzzy", "most words", "slug words", "alias partial", "alias exact (drafted)")


def is_weak(k):
    return k in WEAK or k.startswith("description") or k.startswith("name prefix")


def main():
    D = P.Data()
    E = Engine(D)
    qs = queries()
    seen = set()
    runs = []
    for src, q in qs:
        r = E.run(q)
        res = []
        for gid, tier, why, via, dym, drafted in r["g"]:
            row = E.rows[gid]
            k = E.kind(q, row, tier, why, via, dym, drafted)
            res.append({"gid": gid, "name": row[2], "layer": row[4], "size": row[5], "tier": tier, "why": why, "via": via, "kind": k, "members": E.hand_members[gid] if gid.startswith("hand:") else None,
                        "desc": (row[7] or "")[:90]})
        runs.append({"src": src, "q": q, "n": len(res), "family": r["f"], "dym": r["d"], "res": res})
    out = {"runs": runs}
    # ---- 1 empty groups
    idx = E.doc["groups"]
    by_layer = collections.Counter(g[4] for g in idx)
    zero = collections.Counter(g[4] for g in idx if g[5] == 0)
    hand = [g for g in idx if g[4] == "h"]
    hand_zero_mem = [g for g in hand if E.hand_members["hand:" + g[1][3:]] == 0] if hand else []
    out["layers_in_index"] = dict(by_layer)
    out["zero_size_by_layer"] = dict(zero)
    out["hand"] = {"groups": len(hand), "no_members": len(hand_zero_mem), "no_hits": sum(1 for g in hand if g[5] == 0),
                   "rows": [[g[0], g[2], g[5], E.hand_members["hand:" + g[1][3:]]] for g in hand]}
    out["pages_without_cards"] = {"ty": sum(1 for g in idx if g[4] == "ty" and g[5] == 0), "ab": sum(1 for g in idx if g[4] == "ab" and g[5] == 0)}
    memberless_first = [r["q"] for r in runs if r["res"] and r["res"][0]["gid"].startswith("hand:") and (r["res"][0]["members"] or 0) == 0]
    memberless_any = [r["q"] for r in runs if any(x["gid"].startswith("hand:") and (x["members"] or 0) == 0 for x in r["res"])]
    out["memberless_first"] = memberless_first
    out["memberless_any"] = memberless_any
    aliases_first_hand = [a for a, v in D.search_doc["aliases"].items() if v["g"] and v["g"][0].startswith("hand:") and E.hand_members[v["g"][0]] == 0]
    out["aliases_whose_first_target_is_memberless_hand"] = aliases_first_hand
    out["aliases_total"] = len(D.search_doc["aliases"])
    # ---- 2 weak matches
    def weak_stats(sel):
        searches = [r for r in runs if sel(r)]
        a = {"searches": len(searches), "with_results": sum(1 for r in searches if r["n"]), "with_weak_any": 0, "with_weak_top5": 0, "with_weak_top10": 0, "weak_results": 0, "results": 0, "kinds": collections.Counter()}
        for r in searches:
            ks = [is_weak(x["kind"]) for x in r["res"]]
            a["results"] += len(ks)
            a["weak_results"] += sum(ks)
            a["with_weak_any"] += any(ks)
            a["with_weak_top5"] += any(ks[:5])
            a["with_weak_top10"] += any(ks[:10])
            for x in r["res"]:
                a["kinds"][x["kind"]] += 1
        a["kinds"] = dict(a["kinds"])
        return a
    out["weak_probe50"] = weak_stats(lambda r: r["src"] == "probe")
    out["weak_all100"] = weak_stats(lambda r: True)
    # every weak kind in a top-5, by query (short list)
    out["weak_top5_examples"] = [[r["q"], x["name"][:60], x["kind"], x["desc"] if x["kind"].startswith("description") else ""] for r in runs for x in r["res"][:5] if is_weak(x["kind"])]
    # ---- 3 no results
    out["no_result"] = [{"q": r["q"], "src": r["src"], "family": r["family"], "dym": r["dym"], "real_word": all(norm(w) in E.words or stem(norm(w)) in E.words for w in r["q"].split()),
                         "known_in_group_vocabulary": None} for r in runs if r["n"] == 0]
    # groups whose name or description mentions the term, to see what each could reach
    cand = {}
    for q in ("recursion", "fetch land", "overrun", "blink", "stax"):
        cand[q] = []
        toks = [t for t in norm(q).split()]
        for g in idx:
            if g[4] in ("ty", "ab"):
                continue
            hay = norm(g[2] + " " + (g[7] or ""))
            if all(t in hay.split() or stem(t) in [stem(x) for x in hay.split()] for t in toks):
                cand[q].append([g[0], g[2][:70], g[4], g[5]])
    out["candidates_by_text"] = cand
    # ---- 4 generic words
    gen = {}
    for q in ("creature", "artifact", "sacrifice", "draw cards", "damage", "token", "land"):
        r = E.run(q)
        res = []
        for gid, tier, why, via, dym, drafted in r["g"]:
            row = E.rows[gid]
            res.append({"gid": gid, "name": row[2], "layer": row[4], "size": row[5], "tier": tier, "why": why, "kind": E.kind(q, row, tier, why, via, dym, drafted)})
        gen[q] = {"n": len(res), "family": r["f"], "by_layer": dict(collections.Counter(x["layer"] for x in res)), "by_tier": dict(collections.Counter(x["tier"] for x in res)), "top10": res[:10],
                  "exactish": sum(1 for x in res if x["tier"] <= 1), "name_tiers": sum(1 for x in res if x["tier"] <= 3)}
    out["generic"] = gen
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("wrote", OUT, "runs", len(runs))


if __name__ == "__main__":
    main()
