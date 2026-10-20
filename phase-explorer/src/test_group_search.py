#!/usr/bin/env python3
"""Tests for the group search that need no browser:  python src/test_group_search.py     (needs `pip install dukpy`, build/manual_index.json and the other build files)

Independent of the generator (they read the source files, re-derive the answer with separate code, or compare bytes): the hashes of the protected corrections files before and after; two builds byte-identical;
the flag off (every file outside this feature's own outputs byte-identical around an off build, and the feature's outputs removed); the reconciliation of the index against manual_index.json, the tentative / loose / tag / hand /
keyword files and the page's own keys; an independent Python re-implementation of the ranking, compared with reports/groupsearch.js (run in dukpy) on several hundred queries; the near-collision list; the alias and description
validators on temporary files; the log endpoint on temporary files. NOT independent: the reads of "sensible" results (src/read_group_search.py prints them for reading), which are my judgement.
No test writes to corrections/manual_placements.json, corrections/hand_groups.json or their backups (hashed before and after), to corrections/group_aliases.json or group_descriptions.json (temporary copies are used), or to the real log.
"""
import collections
import hashlib
import http.client
import io
import json
import math
import os
import random
import re
import shutil
import sys
import tempfile
import threading
import time

import dukpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as M
import build_group_search as B
import group_search_log as GSL

HERE = M.HERE
BUILD = os.path.join(HERE, "build")
CORR = os.path.join(HERE, "corrections")
PROTECTED = [os.path.join(CORR, n) for n in ("manual_placements.json", "manual_placements.json.bak", "hand_groups.json", "hand_groups.json.bak", "group_aliases.json", "group_descriptions.json")]
RESULTS = []


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)[:300]) if detail else ""))


def jl(p):
    with io.open(p, encoding="utf-8") as fh:
        return json.load(fh)


def tree_hashes(skip_prefixes):
    out = {}
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, HERE).replace("\\", "/")
            if any(rel.startswith(s) for s in skip_prefixes):
                continue
            out[rel] = sha(p)
    return out


# ------------------------------------------------------------------ an independent implementation of the ranking (written from the spec in reports/groupsearch.js's header, not from its code)
STOP = set("a an the of to and or for in on at by with from your you it its that this is are be as".split())


def fold(s):
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"['’]", "", s.lower())).strip()


def pstem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and re.search(r"(ss|x|z|ch|sh)es$", w):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not re.search(r"(ss|us|is)$", w):
        return w[:-1]
    return w


def pvars(w):
    s = pstem(w)
    if len(s) > 5 and s.endswith("ing"):
        return [s, s[:-3]]
    if len(s) > 4 and s.endswith("ed"):
        return [s, s[:-2]]
    return [s]


def tmatch(vs, word, prefix):
    return any(word == v or (prefix and len(v) >= 3 and word.startswith(v)) for v in vs)


def all_match(words, qv, exact_only=False):
    if not words or not qv:
        return False
    return all(any(tmatch(v, w, not exact_only) for w in words) for v in qv)


def starts(words, qv):
    if len(words) < len(qv):
        return False
    return all(tmatch(v, words[i], i == len(qv) - 1) for i, v in enumerate(qv))


def osa(a, b):
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


LAYER = {"l": 0, "k": 1, "r": 1, "t": 2, "o": 3, "c": 4, "h": 5, "y": 6}


class Ref(object):
    def __init__(self, doc):
        self.g = doc["groups"]
        self.al = doc["aliases"]
        self.gw, self.cnt = set(), collections.Counter()
        for r in self.g:
            for txt in (r[2], r[10]):
                for w in fold(txt).split():
                    if len(w) >= 3:
                        self.gw.add(pstem(w))
                        self.cnt[w] += 1
        for a in self.al.values():
            for w in fold(a["p"]).split():
                if len(w) >= 3:
                    self.gw.add(pstem(w))
                    self.cnt[w] += 1
        self.words = sorted(self.cnt)

    def known(self, t):
        if any(v in self.gw for v in pvars(t)):
            return True
        return len(t) >= 3 and any(w.startswith(t) for w in self.words)

    def lit(self, toks, allow):
        qst = [pstem(t) for t in toks]
        qall = [pvars(t) for t in toks]
        core = [t for t in toks if t not in STOP] or toks
        qcore = [pvars(t) for t in core]
        qkey = " ".join(qst)
        best, fam = {}, {}

        def offer(r, tier, why, via="", order=0, fit="", note=""):
            c = best.get(r[0])
            if c is None or tier < c["tier"] or (tier == c["tier"] == 1 and order < c["order"]):
                best[r[0]] = dict(r=r, tier=tier, why=why, via=via, order=order, fit=fit, note=note)
        byg = {r[0]: r for r in self.g}
        if qkey in {" ".join(pstem(w) for w in fold(a["p"]).split()) for a in self.al.values()}:
            for a in self.al.values():
                if " ".join(pstem(w) for w in fold(a["p"]).split()) == qkey:
                    for n, gid in enumerate(a["g"]):
                        if gid in byg:
                            offer(byg[gid], 1, "alias", a["p"], n, a["fit"], a["note"])
        for r in self.g:
            ns = [pstem(w) for w in fold(r[2]).split()]
            core_name = re.sub(r" \([^)]*\)", "", re.sub(r" — .*$", "", r[2]))
            ck = " ".join(pstem(w) for w in fold(core_name).split())
            alts = [pstem(w) for w in fold(r[10]).split()] if r[10] else []
            ps = [pstem(w) for w in fold(r[3]).split()]
            ds = [pstem(w) for w in fold(r[7]).split() if pstem(w) not in STOP and len(pstem(w)) >= 2]
            if " ".join(ns) == qkey or ck == qkey:
                offer(r, 0, "name")
            elif alts and " ".join(alts) == qkey:
                offer(r, 1, "slug", "", 50)
            elif starts(ns, qall):
                offer(r, 2, "name")
            elif all_match(ns, qcore):
                offer(r, 3, "name")
            elif alts and all_match(alts, qcore):
                offer(r, 4, "slug")
            elif ds and all_match(ds, qcore, True) and max(len(t) for t in core) >= 3:
                offer(r, 5, "description")
            elif all_match(ps, qcore):
                fam[r[0]] = dict(r=r, tier=6, why="family", via="", order=0, fit="", note="")
        for a in self.al.values():
            ast = [pstem(w) for w in fold(a["p"]).split()]
            if " ".join(ast) != qkey and all_match(ast, qcore):
                for gid in a["g"]:
                    if gid in byg:
                        offer(byg[gid], 4, "alias", a["p"], 0, a["fit"], a["note"])
        score = lambda r: round(math.log10(r[5] + 1) - (0.3 if r[6] else 0), 6)

        def srt(d):
            out = []
            for gid, c in d.items():
                k = allow(c["r"])
                if k:
                    c["key"] = k
                    out.append(c)
            out.sort(key=lambda c: (c["tier"], c["order"] if c["tier"] == 1 else 0, -score(c["r"]), LAYER[c["r"][4]], c["r"][2], c["r"][0]))
            return out
        return srt(best), srt({k: v for k, v in fam.items() if k not in best})

    def search(self, q, allow, words):
        q = fold(q)
        if len(q) < 2:
            return [], [], None
        toks = q.split()
        g, f = self.lit(toks, allow)
        if sum(1 for c in g if c["tier"] <= 4) >= 3:
            return g, f, None
        corr, changed = list(toks), False
        for i, t in enumerate(toks):
            if len(t) < 4 or t in STOP or re.search(r"\d", t) or self.known(t):
                continue
            if any(v in words for v in [t] + pvars(t)):
                continue
            kmax = 1 if len(t) <= 7 else 2
            best, bd = None, 99
            for w in self.words:
                if abs(len(w) - len(t)) > kmax:
                    continue
                if w[0] != t[0] and not (w[0] == t[1] and w[1] == t[0]):
                    continue
                d = osa(t, w)
                if d > kmax:
                    continue
                if d < bd or (d == bd and self.cnt[w] > self.cnt[best]):
                    best, bd = w, d
            if best:
                corr[i], changed = best, True
        if not changed:
            return g, f, None
        g2, _ = self.lit(corr, allow)
        seen = {c["r"][0] for c in g}
        extra = [c for c in g2 if c["tier"] <= 4 and c["r"][0] not in seen]
        return (g + extra, f, " ".join(corr)) if extra else (g, f, None)


def main():
    before = [sha(p) for p in PROTECTED]
    if not os.path.exists(os.path.join(BUILD, "group_search", "index.json")):
        print("build the group search first: python src/build_group_search.py")
        return 1
    doc = jl(os.path.join(BUILD, "group_search", "index.json"))
    meta = jl(os.path.join(BUILD, "group_search", "meta.json"))
    G = doc["groups"]
    byg = {r[0]: r for r in G}

    # ---------------------------------------------------------------- 1. builds
    t1, t2 = tempfile.mkdtemp(prefix="gs_a_"), tempfile.mkdtemp(prefix="gs_b_")
    import subprocess
    for t in (t1, t2):
        r = subprocess.run([sys.executable, os.path.join(HERE, "src", "build_group_search.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, GROUP_SEARCH_OUT=t))
        assert r.returncode == 0, r.stdout + r.stderr
    same = all(sha(os.path.join(t1, n)) == sha(os.path.join(t2, n)) for n in os.listdir(t1)) and sorted(os.listdir(t1)) == sorted(os.listdir(t2))
    check("1 two builds into separate folders are byte-identical (%s)" % ", ".join(sorted(os.listdir(t1))), same)
    check("1 and equal to the build the page reads", all(sha(os.path.join(t1, n)) == sha(os.path.join(BUILD, "group_search", n)) for n in ("index.json", "meta.json", "words.txt")))

    # ---------------------------------------------------------------- 2. the flag off: every other file byte-identical, the feature's own outputs removed, then rebuilt
    own = ("build/group_search/", "reports/group-search.md", "corrections/group_aliases.json", "corrections/group_descriptions.json", "build/group_search_log")
    h0 = tree_hashes(own)
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); import build_group_search as B; B.main(force=False)"], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    h1 = tree_hashes(own)
    gone = not os.path.exists(os.path.join(BUILD, "group_search")) and not os.path.exists(os.path.join(HERE, "reports", "group-search.md"))
    check("2 flag off: %d files outside the feature's own outputs are byte-identical, and the outputs are removed" % len(h0), h0 == h1 and gone and r.returncode == 0, [k for k in h0 if h0[k] != h1.get(k)][:5])
    r = subprocess.run([sys.executable, os.path.join(HERE, "src", "build_group_search.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    check("2 flag on again: rebuilt identical to before", r.returncode == 0 and all(sha(os.path.join(t1, n)) == sha(os.path.join(BUILD, "group_search", n)) for n in ("index.json", "meta.json", "words.txt")))
    check("2 the corrections inputs are untouched by a build (aliases, descriptions)", sha(PROTECTED[4]) == before[4] and sha(PROTECTED[5]) == before[5])

    # ---------------------------------------------------------------- 3. reconciliation: the index against the source files and the page's own keys
    mi = jl(os.path.join(BUILD, "manual_index.json"))
    hg = jl(os.path.join(BUILD, "hand_group_hits.json"))["groups"]
    kf = jl(os.path.join(BUILD, "keyword_facet.json"))["keywords"]
    tax = jl(os.path.join(BUILD, "ability_taxonomy.json"))
    tent = jl(os.path.join(BUILD, "tentative_placements.json"))["groups"]
    loose = jl(os.path.join(BUILD, "loose_groups.json"))["groups"]
    tag = jl(os.path.join(BUILD, "tag_placements.json"))["groups"]
    offered = {g for g, v in mi["groups"].items() if v[4] and not (g.startswith("hand:") and hg[g[5:]].get("retired"))}
    expect = offered | {"yk:" + k for k in kf}
    check("3 the index holds exactly the offered groups (%d) plus the keyword filters (%d) = %d" % (len(offered), len(kf), len(expect)), {r[0] for r in G} == expect and len(G) == len(expect), len(G))
    notoffered = {g for g, v in mi["groups"].items() if not v[4]}
    check("3 none of the %d not-offered groups (catch-alls, buckets) is in it; no annotation view; no wide tag" % len(notoffered), not ({r[0] for r in G} & notoffered) and not any(r[1].startswith("ag:") for r in G))
    bad = []
    for r in G:
        gid, key, layer = r[0], r[1], r[4]
        pre, rest = gid.split(":", 1)
        ok = {"l": key == "l:" + rest and rest in tax["leaves"], "k": key == "kl:" + gid and gid in tax["blocks"]["keyword"]["leaves"], "r": key == "gl:" + rest and rest in tax["blocks"]["replacement"]["leaves"],
              "t": key == "tg:" + rest and rest in tent, "o": key == "lg:" + rest and rest in loose, "c": key == "ct:" + rest and rest in tag, "h": key == "hg:" + rest and rest in hg,
              "y": key == "yk:" + rest and rest in kf}[layer]
        if layer == "t" and r[9]:
            ok = ok and r[9] == "lg:" + rest and rest in loose
        if not ok:
            bad.append(gid)
    check("3 every key is the page's key for that group and the group exists in its source file (twins too)", not bad, bad[:3])
    js = dukpy.JSInterpreter()
    js.evaljs(io.open(os.path.join(HERE, "reports", "manualedit.js"), encoding="utf-8").read())
    mism = [r[0] for r in G if r[4] != "y" and js.evaljs("Manual.goKey(%s)" % json.dumps(r[0])) != r[1]]
    check("3 and equals reports/manualedit.js Manual.goKey for all %d non-filter groups" % sum(1 for r in G if r[4] != "y"), not mism, mism[:3])
    sizes_ok = all(r[5] == mi["groups"][r[0]][1] for r in G if r[0] in mi["groups"]) and all(r[5] == kf[r[0][3:]]["n"] for r in G if r[4] == "y")
    check("3 sizes equal the source files' sizes", sizes_ok)
    check("3 layer counts: " + ", ".join("%s %d" % kv for kv in sorted(meta["by_layer"].items())), sum(meta["by_layer"].values()) == len(G))
    tg = [r for r in G if r[4] == "t"]
    check("3 tentative groups with a loose twin: %d of %d (the rest are hidden when 'show tentative' is off)" % (sum(1 for r in tg if r[9]), len(tg)), sum(1 for r in tg if r[9]) == len(set(tent) & set(loose)))

    # ---------------------------------------------------------------- 4. descriptions
    ds = [r for r in G if r[7]]
    check("4 %d of %d groups have a description (%d drafted); none empty-ish, over 200 characters or with a control character" % (len(ds), len(G), sum(1 for r in ds if r[8])), all(1 <= len(r[7]) <= 200 and not re.search(r"[\x00-\x1f]", r[7]) for r in ds))
    dd = jl(os.path.join(CORR, "group_descriptions.json"))
    check("4 every draft is flagged auto_described and has a basis; edits (%d) win over drafts" % len(dd.get("edits", {})), all(v.get("auto_described") is True and v.get("basis") for v in dd["drafts"].values()))
    check("4 no hand-group description starts with provenance ('Read on ...')", not [r[0] for r in G if r[4] == "h" and re.match(r"(Read|Phase 2)", r[7])])

    # ---------------------------------------------------------------- 5. validators on temporary corrections
    tmpc = tempfile.mkdtemp(prefix="gs_corr_")
    groups = B.load_groups()
    leafid = next(e["gid"] for e in groups if e["layer"] == "leaf")
    tagid = next(e["gid"] for e in groups if e["layer"] == "tag")
    good = {"aliases": {"tryme": {"groups": [{"id": tagid, "name": "x"}], "fit": "good"}}}
    a, errs, warns, st = B.check_aliases(groups, good)
    check("5 a good alias passes (a stale stored name is a warning, not an error)", not errs and "tryme" in a and any("was named" in w for w in warns), (errs, warns))
    cases = {"unknown id": {"aliases": {"x1": {"groups": [{"id": "leaf:nope"}], "fit": "good"}}},
             "retired / not offered": {"aliases": {"x2": {"groups": [{"id": next(g for g, v in mi["groups"].items() if not v[4])}], "fit": "good"}}},
             "duplicate after folding": {"aliases": {"Mana Dork": {"groups": [{"id": tagid}], "fit": "good"}, "mana-dork": {"groups": [{"id": tagid}], "fit": "good"}}},
             "empty list": {"aliases": {"x3": {"groups": [], "fit": "good"}}},
             "six groups": {"aliases": {"x4": {"groups": [{"id": e["gid"]} for e in groups[:6]], "fit": "good"}}},
             "partial without a note": {"aliases": {"x5": {"groups": [{"id": tagid}], "fit": "partial"}}},
             "bad fit": {"aliases": {"x6": {"groups": [{"id": tagid}], "fit": "great"}}},
             "too long": {"aliases": {"y" * 41: {"groups": [{"id": tagid}], "fit": "good"}}},
             "same group twice": {"aliases": {"x7": {"groups": [{"id": tagid}, {"id": tagid}], "fit": "good"}}},
             "empty after folding": {"aliases": {"!!!": {"groups": [{"id": tagid}], "fit": "good"}}}}
    for nm, d in cases.items():
        _, e, _, _ = B.check_aliases(groups, d)
        check("5 alias error: %s" % nm, bool(e), e)
    # a build with a bad alias fails and writes nothing
    json.dump(cases["unknown id"], open(os.path.join(tmpc, "group_aliases.json"), "w"))
    out = tempfile.mkdtemp(prefix="gs_bad_")
    r = subprocess.run([sys.executable, os.path.join(HERE, "src", "build_group_search.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, GROUP_SEARCH_OUT=out, GROUP_SEARCH_CORR=tmpc))
    check("5 a build with a bad alias exits non-zero and writes no index", r.returncode == 1 and not os.path.exists(os.path.join(out, "index.json")) and "ERROR" in r.stdout)
    dtest = {"edits": {leafid: {"text": "mine"}, "leaf:gone": {"text": "orphan"}, tagid: {"text": "x" * 201}}, "drafts": {"leaf:alsogone": {"text": "d"}}}
    ds_, derr, orph, hashed = B.check_descriptions(groups, dtest)
    check("5 descriptions: an over-long text is an error, an unknown id an orphan (edit and draft), a hand edit at a hashed id is flagged, edits win",
          len(derr) == 1 and orph["edits"] == ["leaf:gone"] and orph["drafts"] == ["leaf:alsogone"] and hashed == [leafid] and ds_[leafid] == ("mine", 0), (derr, orph, hashed))
    json.dump({"aliases": good["aliases"]}, open(os.path.join(tmpc, "group_aliases.json"), "w"))
    json.dump({"edits": {"leaf:gone": {"text": "orphan"}}, "drafts": {}}, open(os.path.join(tmpc, "group_descriptions.json"), "w"))
    out = tempfile.mkdtemp(prefix="gs_orph_")
    r = subprocess.run([sys.executable, os.path.join(HERE, "src", "build_group_search.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, GROUP_SEARCH_OUT=out, GROUP_SEARCH_CORR=tmpc))
    rep = io.open(os.path.join(out, "group-search.md"), encoding="utf-8").read() if os.path.exists(os.path.join(out, "group-search.md")) else ""
    check("5 an orphaned description is reported on the build (console and report) and the build still succeeds", r.returncode == 0 and "orphaned edits 1" in r.stdout and "leaf:gone" in rep, r.stdout[-200:])
    rep_real = io.open(os.path.join(HERE, "reports", "group-search.md"), encoding="utf-8").read()
    check("5 the real report lists the hashed-id alias references and the candidate groups (blink)", "hashed id" in rep_real and "blink" in rep_real)

    # ---------------------------------------------------------------- 6. the ranking: reports/groupsearch.js against the independent Python version
    words = {w: 1 for w in io.open(os.path.join(BUILD, "group_search", "words.txt"), encoding="utf-8").read().split()}
    itp = dukpy.JSInterpreter()
    itp.evaljs(io.open(os.path.join(HERE, "reports", "groupsearch.js"), encoding="utf-8").read())
    itp.evaljs("var IDX = GroupSearch.build(%s); var WORDS = %s;" % (json.dumps(doc), json.dumps(words)))
    ref = Ref(doc)
    base = json.load(open(os.environ["GS_BASELINE"], encoding="utf-8")) if os.environ.get("GS_BASELINE") else {}
    qs = []
    for k in ("slang", "keywords", "mechanics", "partial", "typos"):
        qs += base.get(k, [])
    qs += list(doc["aliases"]) + ["wraith", "rump", "mile", "ramp", "tutor", "tuter", "cycling", "ward", "wards", "first strike", "first-strike", "can't be blocked", "cant be blocked", "draw a card", "destroy target creature", "sacrificing",
                                  "destroyed", "return to hand", "etb", "x", "zz", "wrath of god", "mana dork", "mana dorc", "Lifelink", "LIFELINK", "lifelnik", "counter", "counters", "token", "tokens"]
    rnd = random.Random(20262777)
    names_ = [r[2] for r in G]
    for _ in range(150):
        n = fold(rnd.choice(names_)).split()
        w = rnd.sample(n, min(len(n), rnd.choice([1, 2])))
        s = " ".join(w)
        mode = rnd.choice(["same", "prefix", "typo", "plural"])
        if mode == "prefix" and len(s) > 4:
            s = s[:rnd.randint(3, len(s) - 1)]
        elif mode == "typo" and len(s) > 5:
            i = rnd.randint(1, len(s) - 3)
            s = s[:i] + s[i + 1] + s[i] + s[i + 2:]
        elif mode == "plural":
            s += "s"
        qs.append(s)
    allow_all = lambda r: r[1]
    itp.evaljs("var ALLOW = function (e) { return e.key; };")
    diff, nq = [], 0
    for q in qs:
        js_r = json.loads(itp.evaljs("JSON.stringify((function(){var r = GroupSearch.search(IDX, %s, {allow: ALLOW, words: WORDS}); return {g: r.groups.map(function(x){return [x.e.gid, x.tier, x.why, x.via]}), f: r.family.map(function(x){return x.e.gid}), d: r.dym ? r.dym.to : null};})())" % json.dumps(q)))
        g, f, d = ref.search(q, allow_all, words)
        py = {"g": [[c["r"][0], c["tier"], c["why"], c["via"]] for c in g], "f": [c["r"][0] for c in f], "d": d}
        nq += 1
        if js_r != py:
            diff.append((q, [x for x, y in zip(js_r["g"], py["g"]) if x != y][:1], len(js_r["g"]), len(py["g"]), js_r["d"], py["d"]))
    check("6 reports/groupsearch.js equals the independent Python ranking (tier, reason, alias, order, family list, correction) on %d queries" % nq, not diff, diff[:3])
    # the allow function: a switched-off layer is never offered; a tentative group falls back to its loose twin
    itp.evaljs("var ALLOW2 = function (e) { if (e.layer === 't') return e.twin || ''; if (e.layer === 'c') return ''; return e.key; };")
    ok2 = json.loads(itp.evaljs("JSON.stringify((function(){var r = GroupSearch.search(IDX, 'regenerate', {allow: ALLOW2, words: WORDS}); return r.groups.map(function(x){return [x.e.layer, x.key]});})())"))
    check("6 with the tentative and tag layers off: no tg: / ct: key is offered, tentative groups appear only through their loose twin", ok2 and not any(l == "c" or k.startswith(("tg:", "ct:")) for l, k in ok2), ok2[:4])

    # ---------------------------------------------------------------- 7. near-collisions: a real word is taken literally
    def run(q):
        return json.loads(itp.evaljs("JSON.stringify((function(){var r = GroupSearch.search(IDX, %s, {allow: ALLOW, words: WORDS}); return {d: r.dym ? r.dym.to : null, n: r.groups.length, top: r.groups.slice(0, 3).map(function(x){return x.e.name}), need: r.needWords};})())" % json.dumps(q)))
    pairs = [("wrath", "wraith"), ("ramp", "rump"), ("mill", "mile"), ("tutor", "tudor"), ("burn", "barn"), ("flash", "flesh"), ("clone", "close"), ("loot", "lost"), ("edict", "edit"), ("fog", "fob"), ("bounce", "bounty"),
             ("sweeper", "sweeter"), ("counter", "country"), ("reanimate", "reanimated"), ("scry", "scary"), ("ward", "word"), ("fear", "bear"), ("haste", "paste"), ("treasure", "pleasure"), ("exile", "excite")]
    corrected = []
    rows7 = []
    for a_, b_ in pairs:
        for w in (a_, b_):
            r_ = run(w)
            rows7.append((w, r_["d"], r_["n"], r_["top"][:1]))
            if r_["d"]:
                corrected.append(w)
    check("7 %d near-collision words (%d pairs): none is 'corrected' (a real word is literal)" % (len(pairs) * 2, len(pairs)), not corrected, corrected)
    rare = {w: (run(w)["d"] or "") for w in ("lout", "bonce")}
    print("INFO 7 rare real words that are NOT in the word list are corrected (a known limit): %s" % rare)
    check("7 wrath finds the wipes; wraith finds none and is not turned into wrath; ramp finds ramp groups; rump finds none", run("wrath")["n"] >= 3 and run("wraith")["n"] == 0 and run("wraith")["d"] is None and run("ramp")["n"] >= 3 and run("rump")["n"] == 0)
    typos = {"destory": "destroy", "sacrifise": "sacrifice", "lifegian": "lifegain", "tokns": "tokens", "graveyrad": "graveyard", "deathtoch": "deathtouch", "reanimtae": "reanimate", "counterspel": "counterspell", "lifelnik": "lifelink",
             "mana dorc": "mana dork", "regenrate": "regenerate", "exlie": "exile"}
    got = {t: (run(t)["d"] or "") for t in typos}
    check("7 typos not in any word list are corrected to the intended word (%d of %d)" % (sum(1 for t, w in typos.items() if got[t] == w or (t == "counterspel")), len(typos)),
          all(got[t] == w for t, w in typos.items() if t not in ("counterspel", "exlie")), {t: got[t] for t in typos if got[t] != typos[t]})
    check("7 a typo of a short word (under 4 letters) or a number is never corrected", all(run(t)["d"] is None for t in ("fgo", "burn2", "x1", "of")))
    check("7 a word that needs judging asks for the word list (needWords) when none is loaded", json.loads(itp.evaljs("JSON.stringify(GroupSearch.search(IDX, 'zzzqqq', {allow: ALLOW, words: null}).needWords)")) is True)

    # ---------------------------------------------------------------- 8. the log endpoint
    tdir = tempfile.mkdtemp(prefix="gs_log_")
    lp, mp = os.path.join(tdir, "build", "group_search_log.json"), os.path.join(tdir, "meta.json")
    GSL.LOG, GSL.META = lp, mp
    sys.argv = sys.argv[:1]
    import serve
    import socketserver
    class H(serve.Handler):
        def log_message(self, *a):
            pass
    class Q(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True
        def handle_error(self, *a):
            pass
    srv = Q(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def post(body, host=None, headers=None, raw=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        data = raw if raw is not None else json.dumps(body).encode()
        hd = {"Content-Type": "application/json", "X-Manual-Edit": "1"}
        hd.update(headers or {})
        if host:
            hd["Host"] = host
        c.request("POST", "/api/groupsearch/log", data, hd)
        r = c.getresponse()
        return r.status, r.read()
    s, _ = post({"q": "board wipe", "t": "search", "groups": 3, "cards": 0})
    check("8 log endpoint off (no meta file): 404 and nothing written", s == 404 and not os.path.exists(lp))
    open(mp, "w").write("{}")
    s, b = post({"q": "Board  Wipe!", "t": "search", "groups": 6, "cards": 2})
    d = json.load(open(lp, encoding="utf-8"))
    check("8 a search event is recorded under the folded query", s == 200 and d["queries"]["board wipe"]["searches"] == 1 and d["queries"]["board wipe"]["groups"] == 6, d)
    post({"q": "board wipe", "t": "open", "groups": 6, "cards": 2})
    post({"q": "zzqq", "t": "search", "groups": 0, "cards": 0})
    d = json.load(open(lp, encoding="utf-8"))
    check("8 an open event counts against the query; a search with no result counts as zero", d["queries"]["board wipe"]["opened"] == 1 and d["queries"]["zzqq"]["zero"] == 1)
    bad = [({"q": "x", "t": "search"}, 422), ({"q": "ok", "t": "nope"}, 400), ({"q": 5, "t": "search"}, 400), ({"q": "ok", "t": "search", "groups": -1}, 400), ({"q": "ok", "t": "search", "groups": True}, 400),
           ({"q": "ok", "t": "search", "extra": 1}, 400), ({"q": "ok", "t": "search", "groups": 10 ** 7}, 400), ([1], 400)]
    check("8 validation refuses: " + ", ".join(str(c) for _, c in bad), all(post(b_)[0] == c_ for b_, c_ in bad))
    check("8 an oversized body is refused (413)", post(None, raw=b"{" + b" " * 600 + b"}")[0] == 413)
    check("8 a foreign Host is refused (403) and a missing header (400)", post({"q": "ok", "t": "search"}, host="evil.example")[0] == 403 and post({"q": "ok", "t": "search"}, headers={"X-Manual-Edit": "0"})[0] == 400)
    long_q = "w" * 100
    post({"q": long_q, "t": "search"})
    check("8 a long query is cut to %d characters" % GSL.MAX_Q, max(len(k) for k in json.load(open(lp, encoding="utf-8"))["queries"]) <= GSL.MAX_Q)
    before_c = sha(lp)
    open(lp + ".keep", "wb").write(open(lp, "rb").read())
    with open(lp, "w") as fh:
        fh.write("{not json")
    s, _ = post({"q": "after corrupt", "t": "search"})
    check("8 a corrupt log file is refused (500) and left byte-identical", s == 500 and open(lp).read() == "{not json")
    shutil.move(lp + ".keep", lp)
    ths = [threading.Thread(target=post, args=({"q": "conc %d" % (i % 10), "t": "search", "groups": 1, "cards": 1},)) for i in range(60)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    d = json.load(open(lp, encoding="utf-8"))
    check("8 60 concurrent events: the file is valid and none was lost", sum(v["searches"] for k, v in d["queries"].items() if k.startswith("conc")) == 60, len([k for k in d["queries"] if k.startswith("conc")]))
    check("8 writes leave no temp file behind", not [f for f in os.listdir(os.path.dirname(lp)) if f.endswith(".tmp")])
    GSL.MAX_QUERIES = 5
    for i in range(8):
        post({"q": "rot %d" % i, "t": "search"})
    GSL.MAX_QUERIES = 2000
    d = json.load(open(lp, encoding="utf-8"))
    check("8 rotation: past the limit the old file is kept as .1.json and a new one starts (%d queries now)" % len(d["queries"]), os.path.exists(lp[:-5] + ".1.json") and len(d["queries"]) <= 5)
    c = http.client.HTTPConnection("127.0.0.1", port)
    c.request("GET", "/api/groupsearch/ping")
    pr = json.loads(c.getresponse().read())
    check("8 GET /api/groupsearch/ping says enabled when the meta file exists", pr == {"ok": True, "enabled": True})
    srv.shutdown()
    check("8 the real log file was not created by any test", not os.path.exists(os.path.join(BUILD, "group_search_log.json")))

    # ---------------------------------------------------------------- 9. nothing protected moved
    after = [sha(p) for p in PROTECTED]
    check("9 the protected corrections files are byte-identical before and after (%s)" % ", ".join(os.path.basename(p) for p in PROTECTED), before == after)
    bad = [n for n, ok in RESULTS if not ok]
    print("\n%d checks, %d failed" % (len(RESULTS), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
