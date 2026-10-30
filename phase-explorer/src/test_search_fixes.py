#!/usr/bin/env python3
"""Verify SEARCH_FIXES (reports/config.js): the group-search ranking and layout fixes in the tester site. Headless Edge over the DevTools protocol on exported folders served by a plain static server (GET only).

    python src/test_search_fixes.py [--sections engine,exports,browser,perf] [--time-limit SECONDS] [--engine-full] [--skip-perf] [--keep]

    Default: engine,exports,browser in 10 minutes or less, one page load per export and every search typed into the same session; "perf" is separate; --engine-full compares all 837 queries.

What is independent of the code under test and what is not.
 INDEPENDENT: (1) the OLD reports/groupsearch.js, kept byte-for-byte in src/testdata/before_search_fixes/groupsearch.src.js, is the reference for "flag off": the new file must return the same
 groups, tiers, reasons, family rows and corrections on ~900 queries; (2) the flag-on invariants are re-derived here in Python from the index and the corrections/hand-placement files read as data (a separate
 stem/inflection implementation, a separate count of hand placements), not from the JS; (3) the exports are compared by hash with the export made before this work (manifest.json there); (4) the corrections,
 backups and archive are hashed before and after; (5) the page's requests and console errors are read from the DevTools protocol, not from the page.
 NOT INDEPENDENT: the 100 re-reads (reports/search-fixes-reads.json, "after") are my judgement, made by the person who built the fixes; the 4x CPU timings are one machine. Clicks are DOM click() calls and
 key presses are DevTools key events: no touch, no other browser.
Nothing here writes to corrections/ or archive/ (exports go to dist.sf_*/, removed at the end unless --keep).
"""
import collections
import hashlib
import io
import json
import os
import random
import re
import shutil
import statistics
import threading
import subprocess
import sys
import tempfile
import time

import dukpy

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_tester_static as T            # noqa: E402
import test_tester_filters as F           # noqa: E402
import browse_probe_data as P             # noqa: E402
import probe_search_defects as S          # noqa: E402  (queries() and the page's run-time index, used as set-up only)

check = T.check
SEED = 20271105                           # fixed before the extra queries were drawn
BEFORE = os.path.join(HERE, "src", "testdata", "before_search_fixes")
OLD_JS = os.path.join(BEFORE, "groupsearch.src.js")
NEW_JS = os.path.join(HERE, "reports", "groupsearch.js")
READS = os.path.join(HERE, "reports", "search-fixes-reads.json")
DIRS = {k: os.path.join(HERE, "dist.sf_" + k) for k in ("a", "b", "off", "old")}
RANK = {"Y": 2, "M": 1, "N": 0}


def rd(p):
    with io.open(p, encoding="utf-8") as fh:
        return fh.read()


def files_of(root):
    return {os.path.relpath(p, root).replace("\\", "/"): T.sha(p) for p in T.walk(root)}


def cfg_with(on):
    txt = rd(os.path.join(HERE, "reports", "config.js"))
    txt = re.sub(r"\bSEARCH_FIXES\s*:\s*(true|false)", "SEARCH_FIXES: %s" % ("true" if on else "false"), txt)
    f = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    f.write(txt); f.close()
    return f.name


def export_to(out, cfg):
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--out", os.path.relpath(out, HERE), "--config", cfg], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    return r.returncode, r.stdout + r.stderr


# ---------------------------------------------------------------- python re-implementation of the pieces the invariants need (independent of the JS)
def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower().replace("'", "").replace("’", "")).strip()


def stem(w):
    n = len(w)
    if n > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if n > 4 and re.search(r"(ss|x|z|ch|sh)es$", w):
        return w[:-2]
    if n > 3 and w.endswith("s") and not re.search(r"(ss|us|is)$", w):
        return w[:-1]
    return w


def is_infl(base, w):
    ext = w[len(base):]
    alt = ext[1:] if ext[:1] == base[-1:] else ext
    return ext == "" or bool(re.fullmatch(r"s|es|ed|d|ing|er|ers|ings", ext)) or bool(re.fullmatch(r"s|es|ed|d|ing|er|ers|ings", alt))


class Eng:
    def __init__(self, D):
        self.doc = S.build_page_doc(D)
        self.words = {w: 1 for w in rd(os.path.join(P.BUILD, "group_search", "words.txt")).split()}
        self.gw = set()
        for g in self.doc["groups"]:
            for t in norm(g[2] + " " + (g[10] or "")).split():
                if len(t) >= 3:
                    self.gw.add(stem(t))
        for ph in self.doc["aliases"].values():
            for t in norm(ph["p"]).split():
                if len(t) >= 3:
                    self.gw.add(stem(t))
        self.rows = {g[0]: g for g in self.doc["groups"]}
        self.old = dukpy.JSInterpreter(); self.old.evaljs(rd(OLD_JS))
        self.new = dukpy.JSInterpreter(); self.new.evaljs(rd(NEW_JS))
        placed = self.placed_counts(D)
        self.placed = placed
        setup = "var IDX=GroupSearch.build(%s); var WORDS=%s; var PLACED=%s; function ALLOW(e){return e.key;} function PL(e){return PLACED[e.gid]||0;}" % (json.dumps(self.doc), json.dumps(self.words), json.dumps(placed))
        self.old.evaljs(setup); self.new.evaljs(setup)

    @staticmethod
    def placed_counts(D):
        """Cards placed by hand into each hand group, from corrections/manual_placements.json (read as data) and the card index: the count the group page's Members list shows."""
        mp = json.loads(rd(os.path.join(HERE, "corrections", "manual_placements.json")))
        out = collections.Counter()
        for oid, e in mp["edits"].items():
            if oid not in D.cards:
                continue
            for g, x in e["groups"].items():
                if g.startswith("hand:") and x["action"] == "add":
                    out[g] += 1
        return dict(out)

    def run(self, which, q, opts=""):
        itp = self.old if which == "old" else self.new
        js = "JSON.stringify((function(){var r=GroupSearch.search(IDX,%s,{allow:ALLOW,words:WORDS%s});return {g:r.groups.map(function(x){return [x.e.gid,x.tier,x.why,x.dym||'',x.via||'']}),f:r.family.map(function(x){return [x.e.gid,x.tier]}),ex:(r.example||[]).map(function(x){return [x.e.gid,x.tier,x.why]}),d:r.dym?r.dym.to:null};})())" % (json.dumps(q), opts)
        return json.loads(itp.evaljs(js))

    def whole_tok(self, t):
        return stem(t) in self.gw or stem(t) in self.words or t in self.words

    def name_words(self, gid):
        row = self.rows[gid]
        out = [[stem(w) for w in norm(row[2]).split()]]
        for x in (row[11] if len(row) > 11 and row[11] else []):
            out.append([stem(w) for w in norm(x).split()])
        return out

    def weak_prefix(self, q, gid):
        """True when a name match of this group for this query rests on a longer word that merely begins with a typed whole word (not an inflection)."""
        toks = [t for t in norm(q).split() if t not in ("a", "an", "the", "of", "to", "and", "or", "for", "in", "on", "at", "by", "with", "from", "your", "you", "it", "its", "that", "this", "is", "are", "be", "as")] or norm(q).split()
        for ws in self.name_words(gid):
            ok = True
            weak = False
            for t in toks:
                base = stem(t)
                hit = None
                for w in ws:
                    if w == base or (w.startswith(base) and is_infl(base, w)):
                        hit = "whole"; break
                    if len(base) >= 3 and w.startswith(base):
                        hit = hit or "prefix"
                if hit is None:
                    ok = False; break
                if hit == "prefix" and self.whole_tok(t):
                    weak = True
            if ok:
                return weak
        return False


# ---------------------------------------------------------------- time box, loud failure, and Edge cleanup
T0 = time.time()
STEP = ["start"]
LIVE = []
BROWSER_SEARCHES = ["flash", "cycl", "recursion", "exil", "creature", "blink", "cantrip", "zombie"]      # the searches the page checks cover (fixed by the owner)


class StopRun(Exception):
    pass


def step(name):
    STEP[0] = name
    print("-- [%4.0f s] %s" % (time.time() - T0, name), flush=True)


def kill_edges():
    for s in list(LIVE):
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(s.edge.pid)], capture_output=True)
        except Exception:
            pass


def timeout_die(limit):
    print("\nFAIL TIMEOUT: the run exceeded its %d s limit while: %s. Nothing after this point was checked." % (limit, STEP[0]), flush=True)
    kill_edges()
    os._exit(3)


_init = T.Session.__init__


def _session_init(self, *a, **k):
    _init(self, *a, **k)
    LIVE.append(self)


def _session_close(self):
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.edge.pid)], capture_output=True)       # the whole Edge tree, not only the parent (the shared close() leaves children running)
    except Exception:
        pass
    try:
        self.srv.shutdown()
    except Exception:
        pass
    shutil.rmtree(self.prof, ignore_errors=True)
    if self in LIVE:
        LIVE.remove(self)


T.Session.__init__ = _session_init
T.Session.close = _session_close


def must(name, ok, detail=""):
    """A browser check: recorded, and the first failure stops the browser section (a failure is reported with its reason and nothing after it is trusted)."""
    check(name, ok, detail)
    if not ok:
        raise StopRun("check failed: " + name + " -- " + str(detail)[:300])



def engine_section(E, D, qs100, full):
    step("engine: flag-off identity and flag-on invariants")
    # ------------------------------------------------------------ 1. flag off: the new file is the old file
    rng = random.Random(SEED)
    names = sorted({g[2] for g in E.doc["groups"] if g[4] in "lktochrm"})
    extra = []
    for n in rng.sample(names, 300 if full else 40):
        w = norm(n).split()
        extra.append(" ".join(w[:2]))
        extra.append(w[0][: max(3, len(w[0]) - 1)])                                                       # a partial
    al = sorted(E.doc["aliases"])
    extra += al if full else rng.sample(al, 60)
    allq = list(dict.fromkeys(qs100 + extra))
    check("the extra query set is drawn on a fixed seed (%d) from group names, their partials and aliases (all of them with --engine-full): %d distinct queries in all" % (SEED, len(allq)), len(allq) > (800 if full else 150), len(allq))
    bad = []
    for q in allq:
        a = E.run("old", q); b = E.run("new", q); c = E.run("new", q, ",fixes:false")
        if not (a["g"] == b["g"] == c["g"] and a["f"] == b["f"] == c["f"] and a["d"] == b["d"] == c["d"] and b["ex"] == []):
            bad.append(q)
    check("flag off: the new groupsearch.js returns exactly the old file's groups, tiers, reasons, family rows and corrections on all %d queries (also with fixes:false)" % len(allq), not bad, bad[:5])

    # ------------------------------------------------------------ 2. flag on: invariants re-derived in Python
    on = ",fixes:true,placed:PL"
    lost, appeared, ex_bad, ord_bad, r1_bad, r3_bad, t01_bad, partial_bad = [], [], [], [], [], [], [], []
    n_changed_top5 = 0
    res_on = {}
    for q in allq:
        a = E.run("old", q); b = E.run("new", q, on); res_on[q] = b
        ag = [x[0] for x in a["g"]]; bg = [x[0] for x in b["g"]]; eg = [x[0] for x in b["ex"]]
        oldtier = {x[0]: x[1] for x in a["g"]}; oldwhy = {x[0]: x[2] for x in a["g"]}
        # nothing appears that the old search did not return; what is missing is either in the example row or a stripped-stem prefix (cycling -> Cyclops)
        for g in set(ag) - set(bg) - set(eg):
            toks = [t for t in norm(q).split()]
            if not any(len(t) > 5 and t.endswith(("ing", "ed")) and stem(t) in E.gw for t in toks):
                lost.append((q, E.rows[g][2]))
        appeared += [(q, g) for g in set(bg) | set(eg) if g not in ag]
        # the example row holds only description-only matches of an auto-written example line; the main list holds none
        for g in eg:
            row = E.rows[g]
            if not (oldwhy.get(g) == "description" and row[8] and (row[7] or "").startswith("Example")):
                ex_bad.append((q, row[2]))
        for g in bg:
            row = E.rows[g]
            if oldwhy.get(g) == "description" and row[8] and (row[7] or "").startswith("Example"):
                ex_bad.append((q, "main:" + row[2]))
        # exact names and exact aliases (old tiers 0 and 1) keep their place at the top
        k = sum(1 for x in a["g"] if x[1] <= 1)
        if bg[:k] != ag[:k]:
            t01_bad.append(q)
        # R1: a hand group with no placed member and an old tier of 2 or more comes after every other name match
        for i, x in enumerate(b["g"]):
            g = x[0]
            if g.startswith("hand:") and E.placed.get(g, 0) == 0 and oldtier.get(g, 0) >= 2 and oldtier[g] < 4.9:
                later = [y for y in b["g"][i + 1:] if y[1] <= 4.5 and not (y[0].startswith("hand:") and E.placed.get(y[0], 0) == 0)]
                if later:
                    r1_bad.append((q, E.rows[g][2]))
        # R3: a weak prefix match never comes before a whole-word name match
        wk = [i for i, x in enumerate(b["g"]) if x[2] == "name" and not x[3] and E.weak_prefix(q, x[0])]
        wh = [i for i, x in enumerate(b["g"]) if x[2] == "name" and not x[3] and not E.weak_prefix(q, x[0]) and x[1] <= 3.5]
        if wk and wh and min(wk) < max(wh):
            r3_bad.append((q, E.rows[b["g"][min(wk)][0]][2]))
        # a query with no whole typed word (a partial or a typo) is ordered exactly as before, apart from the hand and example rules
        toks = [t for t in norm(q).split()]
        if toks and not any(E.whole_tok(t) for t in toks) and not b["d"]:
            keep_old = [g for g in ag if g in set(bg) and not (g.startswith("hand:") and E.placed.get(g, 0) == 0)]
            keep_new = [g for g in bg if not (g.startswith("hand:") and E.placed.get(g, 0) == 0)]
            if keep_old != keep_new:
                partial_bad.append(q)
        if [x[0] for x in a["g"][:5]] != [x[0] for x in b["g"][:5]]:
            n_changed_top5 += 1
    check("flag on: no group appears that the old search did not return (%d queries)" % len(allq), not appeared, appeared[:3])
    check("flag on: every group the old search returned is still returned, in the main list or the example row, except stripped-stem prefix matches (cycling -> Cyclops)", not lost, lost[:5])
    check("flag on: the example row holds only description-only matches of auto-written example lines, and the main list holds none", not ex_bad, ex_bad[:3])
    check("flag on: results whose old tier was 0 or 1 (exact name, exact alias) keep the top places in the same order", not t01_bad, t01_bad[:5])
    check("flag on (R1): a hand group with no placed member and a weak tier comes after every other name match", not r1_bad, r1_bad[:3])
    check("flag on (R3): a longer word that merely begins with a typed whole word never comes before a whole-word name match", not r3_bad, r3_bad[:3])
    check("flag on: a query with no whole typed word (a partial or a typo) keeps its old order", not partial_bad, partial_bad[:5])
    spec = {}
    for q in ("flash", "cycling", "cycl", "ramp", "zombie", "exil", "equip", "blink", "cantrip", "mana rock", "flicker", "tok", "sacrific", "saga", "recursion", "fetch land", "rump"):
        spec[q] = res_on.get(q) or E.run("new", q, on)
    nm = lambda q, i: E.rows[spec[q]["g"][i][0]][2] if len(spec[q]["g"]) > i else None
    names_of = lambda q: [E.rows[x[0]][2] for x in spec[q]["g"]]
    fl = names_of("flash")
    check("'flash': Flashback and the 'gains flashback' group come after 'Flash + Flying' and 'Spells can be cast as though they had flash'", fl.index("Flashback") > fl.index("Flash + Flying") and fl.index("Flashback") > [i for i, n in enumerate(fl) if n.startswith("Spells can be cast")][0], fl)
    check("'cycling' no longer returns Cyclops; 'cycl' (a partial) still returns Cycling", "Cyclops" not in names_of("cycling") and "Cycling" in names_of("cycl") and "Cycling" in names_of("cycling"), (names_of("cycling"), names_of("cycl")))
    check("'ramp': Rampage comes after the alias groups and 'Ramp: speeds up your resources'", names_of("ramp").index("Rampage") > names_of("ramp").index("Ramp: speeds up your resources"), names_of("ramp"))
    check("'zombie': none of the six example-line groups is in the main list; they are in the example row", len(spec["zombie"]["ex"]) == 6 and all(g[2] == "description" for g in spec["zombie"]["ex"]) and len(spec["zombie"]["g"]) == 4, (len(spec["zombie"]["g"]), len(spec["zombie"]["ex"])))
    check("'blink', 'cantrip', 'mana rock', 'flicker': the hand group is still first (an exact alias always wins)", all(spec[q]["g"][0][0].startswith("hand:") and spec[q]["g"][0][1] == 1 for q in ("blink", "cantrip", "mana rock", "flicker")), [nm(q, 0) for q in ("blink", "cantrip", "mana rock", "flicker")])
    check("'exil': the blink hand group (no placed member, a prefix match) no longer comes first", not spec["exil"]["g"][0][0].startswith("hand:") and any(x[0].startswith("hand:") for x in spec["exil"]["g"]), names_of("exil")[:3])
    check("'sacrific', 'tok' (partials) and 'equip' keep returning their groups", len(spec["sacrific"]["g"]) > 30 and len(spec["tok"]["g"]) > 100 and any(n == "Equip" for n in names_of("equip")))
    check("'recursion' and 'fetch land' return no group (no alias is written) and 'rump' is still not corrected to 'ramp'", all(not spec[q]["g"] and not spec[q]["ex"] for q in ("recursion", "fetch land", "rump")), [spec[q]["g"] for q in ("recursion", "fetch land", "rump")])
    check("%d of %d queries change their top 5 with the flag on (the 100 are listed below)" % (n_changed_top5, len(allq)), n_changed_top5 > 0)

    # ------------------------------------------------------------ 3. the 100 re-read
    rd_ = json.loads(rd(READS))
    marks = rd_["marks"]
    changed = []
    for i, q in enumerate(qs100, 1):
        a = E.run("old", q); b = res_on[q] if q in res_on else E.run("new", q, on)
        if [x[0] for x in a["g"][:5]] != [x[0] for x in b["g"][:5]]:
            changed.append((i, q, [E.rows[x[0]][2][:38] for x in b["g"][:5]], len(b["g"]), len(b["ex"]), [E.rows[x[0]][2][:38] for x in a["g"][:5]]))
    after = rd_.get("after", {})
    unmarked = [c for c in changed if str(c[0]) not in after]
    print("changed searches among the 100: %d" % len(changed))
    for c in changed:
        print("   ", c[0], c[1], "| groups", c[3], "| example row", c[4], "\n        NOW:", " || ".join(c[2]), "\n        WAS:", " || ".join(c[5]))
    check("every changed search among the 100 has an 'after' read in reports/search-fixes-reads.json (%d changed)" % len(changed), not unmarked, [c[:2] for c in unmarked][:8])
    t1b = t5b = t1a = t5a = 0
    worse = []
    for i, m in marks.items():
        a_ = after.get(i, {"top1": m["top1"], "top5": m["top5"]})
        if m["top1"] in RANK:
            t1b += RANK[m["top1"]] == 2; t1a += RANK[a_["top1"]] == 2
            t5b += RANK[m["top5"]] == 2; t5a += RANK[a_["top5"]] == 2
            if RANK[a_["top1"]] < RANK[m["top1"]] or RANK[a_["top5"]] < RANK[m["top5"]]:
                worse.append((i, m["q"], m["top1"], a_["top1"], m["top5"], a_["top5"]))
        elif a_["top5"] != m["top5"]:
            worse.append((i, m["q"], "expected none", a_["top5"]))
    print("top-1 sensible %d -> %d, top-5 sensible %d -> %d (of 99 that should return something)" % (t1b, t1a, t5b, t5a))
    check("no search read as sensible before became wrong, and no search got worse", not worse, worse[:5])
    check("top-5 sensible (%d) did not fall below the baseline (%d); top-1 sensible %d vs %d" % (t5a, t5b, t1a, t1b), t5a >= t5b and t1a >= t1b)



def exports_section():
    step("exports")
    # ------------------------------------------------------------ 4. exports
    rc1, o1 = export_to(DIRS["a"], cfg_with(True)); rc2, o2 = export_to(DIRS["b"], cfg_with(True)); rc3, o3 = export_to(DIRS["off"], cfg_with(False))
    check("exports with the flag on (twice) and off succeed", rc1 == 0 and rc2 == 0 and rc3 == 0, (o1 + o2 + o3)[-300:])
    fa, fb, fo = files_of(DIRS["a"]), files_of(DIRS["b"]), files_of(DIRS["off"])
    check("two flag-on exports: every file byte-identical (%d files)" % len(fa), fa == fb)
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--check", "--config", cfg_with(True), "--out", os.path.relpath(DIRS["a"], HERE)], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    check("the whitelist check passes on the flag-on export", r.returncode == 0, r.stdout + r.stderr)
    check("flag on vs flag off: the same file list and only reports/config.js differs (no new file, no new data)", set(fa) == set(fo) and sorted(k for k in fa if fa[k] != fo[k] and k != "manifest.json") == ["reports/config.js"], [k for k in fa if fa.get(k) != fo.get(k)])
    base = json.load(open(os.path.join(BEFORE, "manifest.json"), encoding="utf-8"))
    basef = {x["path"]: x["sha256"] for x in base["files"]}
    check("flag off: the same file list as the export made before this work (%d files)" % len(basef), set(fo) - {"manifest.json"} == set(basef), sorted(set(fo) ^ set(basef))[:4])
    diff = sorted(k for k in basef if fo.get(k) != basef[k])
    check("flag off: every file is byte-identical to that export except reports/config.js (the flag), reports/tester.js and reports/groupsearch.js (the code; its behaviour is proven in section 1)", diff == ["reports/config.js", "reports/groupsearch.js", "reports/tester.js"], diff)
    check("flag off: every data file (build/, hand_view.json, manifest entries for them) is byte-identical to the earlier export", all(fo.get(k) == v for k, v in basef.items() if k.startswith("build/")))
    for k in ("a", "off"):
        check("[%s] no corrections/ or archive/ path and no private file is exported" % k, not [p for p in files_of(DIRS[k]) if p.startswith(("corrections/", "archive/", "src/", "data/")) or p.endswith((".bak", ".py"))])
    shutil.copytree(DIRS["off"], DIRS["old"])
    for n in ("config.js", "tester.js", "groupsearch.js"):
        shutil.copyfile(os.path.join(BEFORE, n), os.path.join(DIRS["old"], "reports", n))


def main():
    global LIVE
    opt = lambda n, d=None: (sys.argv[sys.argv.index(n) + 1] if n in sys.argv and sys.argv.index(n) + 1 < len(sys.argv) else d)
    limit = int(opt("--time-limit", 600))
    sections = set(opt("--sections", "engine,exports,browser").split(","))
    full = "--engine-full" in sys.argv
    keep = "--keep" in sys.argv
    if "--skip-perf" in sys.argv:
        sections.discard("perf")
    wd = threading.Timer(limit, timeout_die, args=(limit,)); wd.daemon = True; wd.start()
    before = T.protected()
    corr_before = {k: v for k, v in before.items() if k.startswith(("corrections/", "archive/"))}
    D = P.Data()
    E = Eng(D)
    qs100 = [q for _, q in S.queries()]
    check("the 100 searches are the 50 probe + 30 baseline + 20 fresh", len(qs100) == 100, len(qs100))
    if "engine" in sections:
        engine_section(E, D, qs100, full)
    if sections & {"exports", "browser", "perf"}:
        exports_section()
    stop = None
    try:
        if "browser" in sections:
            browser(E, D)
        if "perf" in sections:
            perf()
    except StopRun as e:
        stop = str(e)
        print("STOPPED:", stop)
    step("hashes")
    after_h = T.protected()
    changed_p = [k for k in set(before) | set(after_h) if before.get(k) != after_h.get(k)]
    check("protected files byte-identical before and after (%d hashed: corrections/ and its backups, archive/, shared JS, serve.py, top-level build files)" % len(before), not changed_p, changed_p[:5])
    check("corrections/ and archive/ (%d files): the same hashes before and after" % len(corr_before), all(after_h.get(k) == v for k, v in corr_before.items()))
    if not keep:
        for d in DIRS.values():
            if os.path.exists(d):
                shutil.rmtree(d)
    fails = [r for r in T.RESULTS if not r[1]]
    print("%d checks, %d failed, %.0f s" % (len(T.RESULTS), len(fails), time.time() - T0))
    for f in fails:
        print("FAILED:", f[0])
    sys.exit(1 if fails or stop else 0)


# ---------------------------------------------------------------- the browser (one page load per export, every search typed into the same session)
def search(c, q):
    c.js("(function(){var q=document.getElementById('q');q.value='';q.dispatchEvent(new Event('input',{bubbles:true}));})()")
    c.pump(0.25)
    c.js("(function(){var q=document.getElementById('q');q.value=%s;q.dispatchEvent(new Event('input',{bubbles:true}));})()" % json.dumps(q))
    ok = c.wait("!!(function(){var f=document.getElementById('findres');return f.innerHTML.length>0 && f.innerHTML.indexOf('Loading the card list')<0 && (f.querySelector('.gs-jump')||f.querySelector('.gs-none')||f.textContent.indexOf('No card or group matches')>=0);})()", 25)
    c.pump(0.3)
    return ok


DOMJS = """JSON.stringify((function(){
  var f=document.getElementById('findres');
  function kind(a){var l=a.closest('.gs-famlist');return l?(l.previousElementSibling.textContent.indexOf('example card line')>=0?'ex':'fam'):'';}
  function block(a){var p=a.previousElementSibling;while(p&&!p.hasAttribute('data-gsb'))p=p.previousElementSibling;return p?p.getAttribute('data-gsb'):'';}
  var rows=[].slice.call(f.querySelectorAll('.gr')).map(function(a){return {n:a.querySelector('.gn').textContent,c:(a.querySelector('.gc')||{}).textContent||'',hidden:!!a.closest('[hidden]'),k:kind(a),b:kind(a)?'':block(a),why:(a.querySelector('.gm')||{}).textContent||''};});
  return {rows:rows,heads:[].slice.call(f.querySelectorAll('[data-gsb]')).map(function(h){return h.textContent;}),
    more:[].slice.call(f.querySelectorAll('[data-gsfxmore]')).map(function(b){return b.dataset.gsfxmore+':'+b.textContent;}),flatmore:[].slice.call(f.querySelectorAll('[data-gsmore=groups]')).map(function(b){return b.textContent;}),
    count:(f.querySelector('#gs-groups > .sub:not(.gs-dym)')||{}).textContent||'',text:f.textContent,famb:[].slice.call(f.querySelectorAll('.gs-famb')).map(function(b){return b.textContent+'|'+b.getAttribute('aria-expanded');})};})())"""

CLICK_MORE = "document.querySelector('#findres [data-gsfxmore=%s]').click()"
HAS_MORE = "!!document.querySelector('#findres [data-gsfxmore=%s]')"
CLICK_EX = "[].slice.call(document.querySelectorAll('#findres .gs-famb')).filter(function(b){return b.textContent.indexOf('example card line')>=0})[0].click()"
CLICK_FLAT = "document.querySelector('#findres [data-gsmore=groups]').click()"


def dom(c):
    return json.loads(c.js(DOMJS))


def vis(d, k="", b=None):
    return [r["n"] for r in d["rows"] if not r["hidden"] and r["k"] == k and (b is None or r["b"] == b)]


def enter(c):
    c.call("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13, text="\r")
    c.call("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)
    c.pump(0.4)


def exp_blocks(E, q):
    """What the page must show, from the engine (a separate run of the same rules): the main list in order, the example list, and the three blocks."""
    r = E.run("new", q, ",fixes:true,placed:PL")
    main = [(E.rows[x[0]][2], x[1], x[0]) for x in r["g"]]
    ex = [E.rows[x[0]][2] for x in r["ex"]]
    blocks = collections.OrderedDict((("named", [m for m in main if m[1] <= 2]), ("contains", [m for m in main if 2 < m[1] < 4]), ("related", [m for m in main if m[1] >= 4])))
    return main, ex, blocks


def browser(E, D):
    def boot(root, w=1280, **kw):
        s = T.Session(root, "/reports/browse.html", w, **kw)
        ok = s.c.wait(F.READY, 90)
        s.c.pump(0.5)
        return s, ok
    qs = BROWSER_SEARCHES

    # ---- flag off against the old scripts: same results markup, same requests
    step("browser: flag off against the old scripts")

    def drive(root):
        s, ok = boot(root)
        try:
            must("[%s] page boots (tester mode, group search on)" % os.path.basename(root), ok)
            m0 = s.mark()
            snaps = {}
            for q in qs:
                must("[%s] search '%s' answers" % (os.path.basename(root), q), search(s.c, q))
                snaps[q] = s.c.js("document.getElementById('findres').innerHTML")
            return snaps, sorted({r["url"].replace(s.base(), "") for r in s.net(m0)}), s.console()
        finally:
            s.close()
    sn, un, cn = drive(DIRS["off"])
    so, uo, co = drive(DIRS["old"])
    must("flag off: the new scripts and the old ones draw the same results markup for the %d searches" % len(qs), sn == so and all(len(v) > 20 for v in sn.values()), [q for q in qs if sn[q] != so[q]])
    must("flag off: the same requests (%d) and no console errors" % len(un), un == uo and not cn and not co, (set(un) ^ set(uo), cn[:2]))

    # ---- flag on, 1280 px
    step("browser: flag on, 1280 px")
    s, ok = boot(DIRS["a"])
    c = s.c
    try:
        must("flag on: page boots", ok)
        m0 = s.mark()
        for q in qs:
            must("flag on: search '%s' answers" % q, search(c, q))
        urls_on = sorted({r["url"].replace(s.base(), "") for r in s.net(m0)})
        must("flag on: the same requests as flag off for the same %d searches (%d): the fixes fetch nothing" % (len(qs), len(un)), urls_on == un, sorted(set(urls_on) ^ set(un))[:4])
        for q in qs:
            main, ex, blocks = exp_blocks(E, q)
            must("flag on: search '%s' answers" % q, search(c, q))
            d = dom(c)
            n = len(main)
            if n == 0:
                must("'%s': no group matches and the page says so plainly (No card or group matches “%s”)" % (q, q), ("No card or group matches “%s”" % q) in d["text"] and not [r for r in d["rows"] if r["k"] == ""], d["text"][:80])
            elif n <= 10:
                shown = [r["n"] for r in d["rows"] if r["k"] == "" and not r["hidden"]]
                allr = [r["n"] for r in d["rows"] if r["k"] == ""]
                must("'%s': %d groups, a flat list as before (no headed blocks), %d shown first, all in the engine's order" % (q, n, min(n, 5)), not d["heads"] and allr == [m[0] for m in main] and len(shown) == min(n, 5), (allr, [m[0] for m in main]))
                if n > 5:
                    c.js(CLICK_FLAT)
                    must("'%s': 'Show %d more' reveals the rest" % (q, n - 5), len(vis(dom(c))) == n)
            else:
                want = ["%s (%d)" % (lab, len(blocks[k])) for k, lab in (("named", "Named"), ("contains", "Contains the word"), ("related", "Related")) if blocks[k]]
                must("'%s': headed blocks with the honest count in each heading: %s" % (q, want), d["heads"] == want, d["heads"])
                must("'%s': the header says '%s groups match' (the real list length), not the old total" % (q, format(n, ",")), ("%s groups match." % format(n, ",")) in d["count"], d["count"])
                for k, lab in (("named", "Named"), ("contains", "Contains the word"), ("related", "Related")):
                    bl = blocks[k]
                    if not bl:
                        continue
                    names = [r["n"] for r in d["rows"] if r["b"] == k and r["k"] == ""]
                    must("'%s' block %s: the first %d rows are the engine's, in order, and 10 are shown" % (q, lab, min(30, len(bl))), names == [m[0] for m in bl[:30]] and len(vis(d, "", k)) == min(10, len(bl)), (names[:3], len(vis(d, "", k))))
                    if len(bl) > 10:
                        for t, w in enumerate([min(len(bl), 20), min(len(bl), 30)]):
                            if not c.js(HAS_MORE % k):
                                break
                            c.js(CLICK_MORE % k)
                            must("'%s' block %s: 'Show 10 more' click %d shows %d (never more than 30)" % (q, lab, t + 1, w), len(vis(dom(c), "", k)) == w, len(vis(dom(c), "", k)))
            fb = [x for x in d["famb"] if "example card line" in x]
            if ex:
                must("'%s': one collapsed row 'N more groups matched only in an example card line' with %d" % (q, len(ex)), len(fb) == 1 and fb[0].startswith("%d more group" % len(ex)) and fb[0].endswith("|false") and not [r for r in d["rows"] if r["k"] == "ex" and not r["hidden"]], fb)
                c.js(CLICK_EX)
                exr = [r for r in dom(c)["rows"] if r["k"] == "ex" and not r["hidden"]]
                must("'%s': the row opens on a click: %d rows, each 'matched: an example card line', in the engine's order" % (q, min(len(ex), 30)), len(exr) == min(len(ex), 30) and all("example card line" in r["why"] for r in exr) and [r["n"] for r in exr] == ex[:30], [r["n"] for r in exr][:3])
            else:
                must("'%s': no example-line row (nothing matched only that way)" % q, not fb, fb)
            for nm_, gid in [(m[0], m[2]) for m in main if m[2].startswith("hand:")]:
                rows = [r for r in dom(c)["rows"] if r["n"] == nm_ and r["k"] == ""]
                if rows:
                    must("'%s': the hand group row says 'N possible cards, %d placed by hand' (rule matches, then the placed count)" % (q, E.placed.get(gid, 0)), re.fullmatch(r"[\d,]+ possible cards, %d placed by hand" % E.placed.get(gid, 0), rows[0]["c"]) is not None, rows[0]["c"])
        main, ex, blocks = exp_blocks(E, "exil")
        pos = [i for i, m in enumerate(main) if m[2].startswith("hand:")]
        must("'exil': the blink hand group (no placed member) is not first, and ranks after every other name match", bool(pos) and pos[0] > 0 and main[pos[0]][1] == 4.9 and all(m[1] < 4.9 for m in main[:pos[0]]), pos)

        step("browser: keyboard")
        search(c, "creature")
        c.js("document.getElementById('q').focus()")
        c.key("ArrowDown")
        c.pump(0.25)
        must("keyboard: ArrowDown from the box lands on a result", c.js("!!document.activeElement && document.activeElement.hasAttribute('data-nav')"))
        reached = False
        presses = 0
        for presses in range(1, 61):
            c.key("ArrowDown")
            c.pump(0.03)
            if c.js("document.activeElement.hasAttribute('data-gsfxmore')"):
                reached = True
                break
        must("keyboard: ArrowDown walks the results and reaches the first 'Show 10 more' button (%d presses)" % presses, reached)
        before_n = len(vis(dom(c), "", "named"))
        enter(c)
        after_n = len(vis(dom(c), "", "named"))
        must("keyboard: Enter on 'Show 10 more' reveals 10 more (%d -> %d)" % (before_n, after_n), after_n == before_n + 10, (before_n, after_n))
        search(c, "flash")
        c.js("document.getElementById('q').focus()")
        c.key("ArrowDown")
        c.pump(0.25)
        for _ in range(40):
            if c.js("document.activeElement.classList.contains('gr')"):
                break
            c.key("ArrowDown")
            c.pump(0.03)
        must("keyboard: arrows reach a group row", c.js("document.activeElement.classList.contains('gr')"))
        enter(c)
        must("keyboard: Enter on a group result opens its page", c.wait("!!document.querySelector('#list [data-oid]') && !document.querySelector('#panel.tpend')", 30))
        c.js("document.getElementById('q').focus()")
        c.key("Escape")
        c.pump(0.3)
        must("keyboard: Escape in the box clears the box and the results", c.js("document.getElementById('q').value === '' && document.getElementById('findres').innerHTML === ''"))
        reqs = [r for r in s.net(m0) if r["url"].startswith(s.base())]
        must("flag on, 1280 px: no failed request, nothing but GET, no 4xx/5xx (%d requests)" % len(reqs), all(not r["failed"] and r["method"] == "GET" and (r["status"] or 200) < 400 for r in reqs), [r for r in reqs if r["failed"] or (r["status"] or 200) >= 400][:3])
        must("flag on, 1280 px: no console error or warning", not s.console(), s.console()[:3])
    finally:
        s.close()

    # ---- 390 px
    step("browser: 390 px")
    LINK = """JSON.stringify((function(){var m=document.querySelector('#findres .gs-miss'),b=m&&m.querySelector('a,button');if(!b)return null;var r=b.getBoundingClientRect(),mr=m.getBoundingClientRect(),p=m.previousElementSibling,pr=p?p.getBoundingClientRect():null;
      var cs=getComputedStyle(b),ms=getComputedStyle(m);
      return {left:Math.round(r.left*10)/10,width:Math.round(r.width*10)/10,height:Math.round(r.height*10)/10,gap:pr?Math.round((mr.top-pr.bottom)*10)/10:null,text:b.textContent,
              margins:[cs.marginTop,cs.marginRight,cs.marginBottom,cs.marginLeft,ms.marginTop].join(' '),prev:p?p.tagName+'.'+(p.classList[0]||''):'',prevMargin:p?getComputedStyle(p).marginBottom:''};})())"""
    TOUCH = """JSON.stringify({sw:document.documentElement.scrollWidth,iw:window.innerWidth,
      small:[].slice.call(document.querySelectorAll('#findres .gr, #findres [data-gsfxmore], #findres .gs-famb')).filter(function(e){return !e.closest('[hidden]') && e.getBoundingClientRect().height<44}).map(function(e){return e.className+':'+e.textContent.slice(0,30)+':'+e.getBoundingClientRect().height}),
      n:[].slice.call(document.querySelectorAll('#findres .gr, #findres [data-gsfxmore], #findres .gs-famb')).filter(function(e){return !e.closest('[hidden]')}).length,
      clip:[].slice.call(document.querySelectorAll('#findres *')).filter(function(e){if(e.closest('[hidden]'))return false;var r=e.getBoundingClientRect();return r.width>0 && r.right>window.innerWidth+1}).length})"""

    def phone(root, label):
        s, ok = boot(root, 390)
        c = s.c
        out = {}
        try:
            must("390 px [%s]: page boots" % label, ok)
            c.js("document.getElementById('tmenu').click()")
            m0 = s.mark()
            for q in qs:
                must("390 px [%s]: search '%s' answers" % (label, q), search(c, q))
                link = json.loads(c.js(LINK))
                c.js("[].slice.call(document.querySelectorAll('#findres .gs-famb')).forEach(function(b){b.click()})")
                c.pump(0.2)
                out[q] = {"link": link, "touch": json.loads(c.js(TOUCH))}
            reqs = [r for r in s.net(m0) if r["url"].startswith(s.base())]
            must("390 px [%s]: no failed request and no console error" % label, all(not r["failed"] for r in reqs) and not s.console(), s.console()[:2])
        finally:
            s.close()
        return out
    on390 = phone(DIRS["a"], "flag on")
    for q in qs:
        m = on390[q]["touch"]
        must("390 px, '%s': no sideways scroll (%d <= %d) and nothing wider than the screen" % (q, m["sw"], m["iw"]), m["sw"] <= m["iw"] and m["clip"] == 0, m)
        must("390 px, '%s': every group row, 'Show 10 more' button and example-line row button this change adds or moves is at least 44 px tall (%d checked; a search with no group has none to check, and the engine says whether it has any)" % (q, m["n"]), (m["n"] > 0) == bool(exp_blocks(E, q)[0] or exp_blocks(E, q)[1]) and not m["small"], (m["n"], m["small"]))
    off390 = phone(DIRS["off"], "flag off")
    exempt = []
    for q in qs:
        a, b = on390[q]["link"], off390[q]["link"]
        must("390 px, '%s': the 'Can't find it?' link has the same size, left edge and its own margins with the flag on and off (%s, margins %s)" % (q, a and "%sx%s px" % (a["width"], a["height"]), a and a["margins"]),
             a is not None and b is not None and (a["width"], a["height"], a["left"], a["margins"]) == (b["width"], b["height"], b["left"], b["margins"]), (a, b))
        if a["prev"] == b["prev"]:
            must("390 px, '%s': the element above the link is the same kind (%s) in both states, so the gap above it is the same (%s px)" % (q, a["prev"], a["gap"]), a["gap"] == b["gap"], (a, b))
        else:
            exempt.append((q, a["prev"], a["prevMargin"], a["gap"], b["prev"], b["prevMargin"], b["gap"]))
    for e in exempt:
        print("EXEMPT from the gap comparison: '%s': above the link with the flag on is %s (margin-bottom %s, gap %s px); with the flag off %s (margin-bottom %s, gap %s px)" % e, flush=True)
    check("the gap comparison was exempt for %d of 8 searches (%s); the other %d were compared" % (len(exempt), ", ".join(e[0] for e in exempt) or "none", 8 - len(exempt)), True)
    own_top = {on390[q]["link"]["margins"].split(" ")[-1] for q in qs}
    must("390 px: with the flag on the gap above the link is never below the spacing used elsewhere (the link block's own top margin %s; smallest gap seen with the flag on %s px, with the flag off %s px)" % (sorted(own_top), min(on390[q]["link"]["gap"] for q in qs), min(off390[q]["link"]["gap"] for q in qs)),
         len(own_top) == 1 and min(on390[q]["link"]["gap"] for q in qs) >= float(next(iter(own_top)).replace("px", "")), (own_top,))



def perf():
    step("perf: first load and typing latency at 4x CPU (flag off and on)")
    out = {}
    for label, root in (("off", DIRS["off"]), ("on", DIRS["a"])):
        boots, lat, srch = [], [], []
        for rep in range(2):
            t0 = time.time()
            s = T.Session(root, "/reports/browse.html", 1280, cpu=4)
            try:
                # first load = the tree on screen and the search box answering (the first search loads the card list and the group index); the full F.READY wait (every lazy file) is not what a visitor waits for
                ok = s.c.wait("document.body.classList.contains('tester') && GSON === true && !!document.querySelector('#tree .row')", 600)
                t_tree = time.time() - t0
                must("[%s] perf page shows the tree" % label, ok)
                s.c.js("(function(){var q=document.getElementById('q');q.value='board wipe';q.dispatchEvent(new Event('input',{bubbles:true}));})()")
                ok = s.c.wait("document.querySelectorAll('#findres .gr').length>0", 900)
                tr = time.time() - t0
                must("[%s] perf first search answers (%.0f s from navigation, tree at %.0f s)" % (label, tr, t_tree), ok)
                s.c.pump(1)
                br = [r for r in s.net() if r["url"].startswith(s.base())]
                boots.append((round(tr, 2), len(br), sum(r["bytes"] or 0 for r in br), round(t_tree, 2)))
                for q in ("board wipe", "creature", "artifact", "sacrifice", "draw cards"):
                    s.c.js("(function(){var q=document.getElementById('q');q.value='';q.dispatchEvent(new Event('input',{bubbles:true}));q.focus();})()")
                    s.c.pump(0.4)
                    s.c.type(q[:-1])
                    s.c.pump(1.0)
                    s.c.js("window.__t0 = performance.now(); document.getElementById('findres').innerHTML='';")
                    s.c.type(q[-1])
                    s.c.wait("document.querySelectorAll('#findres .gr').length>0", 60)
                    lat.append(s.c.js("performance.now() - window.__t0"))
                srch.append(s.c.js("(function(){var o={allow:gsAllow,words:GSWORDS};%s var t=performance.now();for(var i=0;i<20;i++){GroupSearch.search(GSIDX,'creature',o);GroupSearch.search(GSIDX,'draw cards',o);}return (performance.now()-t)/40;})()" % ("o.fixes=true;o.placed=function(e){return 0};" if label == "on" else "")))
            finally:
                s.close()
        out[label] = {"first_search_answers_s": [b[0] for b in boots], "tree_visible_s": [b[3] for b in boots], "boot_requests": boots[0][1], "boot_bytes": boots[0][2], "typing_to_results_ms_median": round(statistics.median(lat)), "typing_to_results_ms_all": [round(x) for x in lat],
                      "search_call_ms_median": round(statistics.median(srch), 1)}
        print(label, json.dumps(out[label]), flush=True)
    must("first load (tree, then the first search): the same requests and about the same bytes with the flag on (%s vs %s requests)" % (out["off"]["boot_requests"], out["on"]["boot_requests"]), out["off"]["boot_requests"] == out["on"]["boot_requests"] and abs(out["off"]["boot_bytes"] - out["on"]["boot_bytes"]) < 3000, (out["off"]["boot_bytes"], out["on"]["boot_bytes"]))
    must("typing latency at 4x CPU: flag on no more than 100 ms slower than off at the median (%d vs %d ms)" % (out["on"]["typing_to_results_ms_median"], out["off"]["typing_to_results_ms_median"]), out["on"]["typing_to_results_ms_median"] <= out["off"]["typing_to_results_ms_median"] + 100)
    with open(os.path.join(HERE, "reports", "search-fixes-perf.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
