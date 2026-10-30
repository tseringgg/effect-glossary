#!/usr/bin/env python3
"""Verify PERSIST_FILTERS (filters kept when the group changes) and COLOUR_IDENTITY (a "Based on" switch, colour identity) in the tester site.

    python src/test_persist_identity.py [--skip-perf] [--keep] [--reads OUT.json]

Exports dist.pi_*/ with several flag settings (removed at the end), serves each with a plain static server and drives headless Edge through the DevTools protocol (clicks are DOM click() calls:
no touch, no other browser). Needs msedge.exe, websocket-client.

Independent of the page code: the colour modes re-derived in Python with set logic (colmodes below), the card types and mana value from the card record, the identity of every card from MTGJSON
(data/AtomicCards-20261003.json.gz, matched by name; build/colour_identity/cards.json is written from Scryfall's file, so the two sources check each other), the byte comparisons and the hashes.
NOT independent: the file against Scryfall's own file (the same source the builder reads), and my choice of wording and defaults. The seed of the 30 lists is fixed before anything is computed.
The corrections files, the archive and the shared scripts are hashed before and after; nothing here writes to them.
"""
import gzip
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_tester_static as T            # noqa: E402
import test_tester_filters as F           # noqa: E402
import tester_filters_ref as REF          # noqa: E402

check = T.check
SEED_30 = 20271106                        # fixed before any list was computed
B = os.path.join(HERE, "build")
BEFORE = os.path.join(HERE, "src", "testdata", "before_persist_identity")
CIJ = os.path.join(B, "colour_identity", "cards.json")
DIRS = {k: os.path.join(HERE, "dist.pi_" + k) for k in ("a", "b", "off", "old", "p", "c")}
FLAGS = ("PERSIST_FILTERS", "COLOUR_IDENTITY")
KNOWN_SOURCE_DISAGREEMENTS = {"Pick Your Poison", "Red Herring"}       # Scryfall and MTGJSON differ on these two (Scryfall: G and R; MTGJSON: BG and RU)
MODES = ["any", "all", "only", "exactly", "not"]
W = "WUBRG"


def jx(c, expr):
    return json.loads(c.js("JSON.stringify(" + expr + ")"))


def files_of(root):
    return {os.path.relpath(p, root).replace("\\", "/"): T.sha(p) for p in T.walk(root)}


def export_to(out, cfg=None):
    cmd = [sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--out", os.path.relpath(out, HERE)] + (["--config", cfg] if cfg else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    return r.returncode, r.stdout + r.stderr


def run_py(*args):
    return subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", args[0])] + list(args[1:]), capture_output=True, text=True, encoding="utf-8", cwd=HERE)


def cfg_with(**kw):
    kw.setdefault("SEARCH_FIXES", False)                                                   # SEARCH_FIXES is tested by src/test_search_fixes.py; these configs keep it off
    txt = open(os.path.join(HERE, "reports", "config.js"), encoding="utf-8").read()
    for k, v in kw.items():
        txt = re.sub(r"\b" + k + r"\s*:\s*(true|false)", "%s: %s" % (k, "true" if v else "false"), txt)
    f = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    f.write(txt); f.close()
    return f.name


def colmodes(idset, cols, mode):
    """The colour modes by set logic. idset: the colours (letters) the card is judged on; cols: chosen chips (W U B R G C M)."""
    letters, c, m, n = {x for x in cols if x in W}, "C" in cols, "M" in cols, len(idset)
    if mode == "any":
        return any((x == "C" and n == 0) or (x == "M" and n >= 2) or (x in W and x in idset) for x in cols)
    if mode == "all":
        return letters <= idset and not (c and n > 0) and not (m and n < 2)
    if mode == "only":
        if n == 0:
            return c
        if m and not letters:
            return n >= 2
        return idset <= letters and not (m and n < 2)
    if mode == "exactly":
        if c:
            return n == 0 and not letters
        if not letters:
            return n >= 2
        return idset == letters and not (m and n < 2)
    return not (letters & idset) and not (c and n == 0) and not (m and n >= 2)          # not


class Ref:
    def __init__(self):
        self.cards = json.load(open(os.path.join(B, "ability_taxonomy_cards.json"), encoding="utf-8"))["cards"]
        self.oids = list(self.cards)
        self.faces = json.load(open(os.path.join(B, "faces", "faces.json"), encoding="utf-8"))["cards"]
        at = json.load(gzip.open(os.path.join(HERE, "data", "AtomicCards-20261003.json.gz"), "rt", encoding="utf-8"))["data"]
        by = {}
        for k, v in at.items():
            ci = set()
            for fc in v:
                ci |= set(fc.get("colorIdentity") or [])
            by[k] = ci
            if " // " in k:
                for part in k.split(" // "):
                    by.setdefault(part, ci)
        self.mj, self.unresolved = {}, []
        for o, c in self.cards.items():
            keys = [c["n"]]
            fl = self.faces.get(o)
            if fl:
                keys += [" // ".join(x["n"] for x in fl["f"])] + [x["n"] for x in fl["f"]]
            hit = next((by[k] for k in keys if k in by), None)
            if hit is None:
                self.unresolved.append(o); hit = set(c["col"])
            self.mj[o] = frozenset(hit)
        self.sc = {}
        with gzip.open(os.path.join(HERE, "data", "scryfall-oracle-cards.jsonl.gz"), "rt", encoding="utf-8") as fh:
            for line in fh:
                d = json.loads(line)
                self.sc[d["oracle_id"]] = frozenset(d["color_identity"])
        self.card_col = {}
        for o, c in self.cards.items():                      # the card colour the tester reads (the union of the faces for a two-faced card)
            fl = self.faces.get(o)
            self.card_col[o] = frozenset("".join(x["c"] for x in fl["f"]) if fl else c["col"])


def click(c, sel):
    return c.js("(()=>{const e=document.querySelector(%s);if(!e)return false;e.click();return true})()" % json.dumps(sel))


def pips(c, cols):
    for x in cols:
        click(c, '.fpip[data-v="%s"]' % x)


def setmode(c, mode):
    click(c, '[data-f="cmode"][data-v="%s"]' % mode)


def clear_all(c):
    click(c, ".fkept .flink[data-f=clear]") or click(c, ".fstat .flink[data-f=clear]")


def state(c):
    return jx(c, "(()=>{const s=TF.state();return {k:s.k,cols:[...s.cols].sort(),mode:s.cmode,types:[...s.types].sort(),mvs:[...s.mvs].sort(),subs:[...s.subs],ab:[...s.ab.trig,...s.ab.cost,...s.ab.kind],nar:s.nar.length,bk:s.bk.size,kept:!!s.kept}})()")


def shown(c):
    return set(jx(c, "TF.shown()"))


def expect(R, full, cols, mode, basis):
    src = R.mj if basis == "identity" else R.card_col
    return {o for o in full if colmodes(set(src[o]), cols, mode)}


def run_session(root, width, fn, **kw):
    s = T.Session(root, "/reports/browse.html", width, **kw); c = s.c
    try:
        if not c.wait(F.READY, 400):
            check("page boots (%s)" % os.path.basename(root), False)
            return None
        c.pump(1.2)
        return fn(s, c)
    finally:
        s.close()


def main():
    skip_perf = "--skip-perf" in sys.argv
    reads_out = sys.argv[sys.argv.index("--reads") + 1] if "--reads" in sys.argv else os.path.join(tempfile.gettempdir(), "persist30_lists.json")
    before = dict(T.protected())
    for d in DIRS.values():
        shutil.rmtree(d, ignore_errors=True)

    # ------------------------------------------------------------ 1. the data file
    r1 = run_py("build_colour_identity.py"); h1 = T.sha(CIJ)
    r2 = run_py("build_colour_identity.py"); h2 = T.sha(CIJ)
    check("build_colour_identity.py runs twice and writes the same bytes", r1.returncode == 0 and r2.returncode == 0 and h1 == h2, r1.stdout + r1.stderr)
    check("--check agrees with the file on disk", run_py("build_colour_identity.py", "--check").returncode == 0)
    raw = open(CIJ, "rb").read(); doc = json.loads(raw)
    gz = len(gzip.compress(raw, 9))
    R = Ref()
    check("colour_identity/cards.json: %s bytes raw, %s gzipped; version 1; one character per card (%d)" % (format(len(raw), ","), format(gz, ","), len(R.oids)), doc["v"] == 1 and len(doc["i"]) == len(R.oids) and len(doc["i"]) == 33183)
    check("it holds no card ids, no group ids and no paths", not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-|leaf:|tag:|corrections|archive", raw.decode("utf-8")))
    A32 = "0123456789abcdefghijklmnopqrstuv"
    dec = {o: frozenset(W[b] for b in range(5) if A32.index(doc["i"][i]) >> b & 1) for i, o in enumerate(R.oids)}
    fb = {R.oids[i] for i in doc["fb"]}
    check("the 15 cards Scryfall's file lacks are listed (fb) and carry their card colour: %s" % sorted(R.cards[o]["n"] for o in fb)[:3], len(fb) == 15 and all(o not in R.sc for o in fb) and all(dec[o] == frozenset(R.cards[o]["col"]) for o in fb), len(fb))
    check("every other card equals Scryfall's colour_identity (33,168 cards; same source as the builder, NOT independent)", all(dec[o] == R.sc[o] for o in R.oids if o not in fb))
    dis = sorted(R.cards[o]["n"] for o in R.oids if o not in fb and o not in R.unresolved and dec[o] != R.mj[o])
    print("cards MTGJSON could not resolve by name:", len(R.unresolved), "; sources disagree on:", dis)
    check("against MTGJSON (a different source, matched by name): %d of the cards resolve and the two sources disagree on %s only" % (len(R.oids) - len(R.unresolved), dis), set(dis) <= KNOWN_SOURCE_DISAGREEMENTS and len(R.unresolved) <= 40, (len(R.unresolved), dis[:6]))

    # ------------------------------------------------------------ 2. exports
    rc, out = export_to(DIRS["a"]); rc2, out2 = export_to(DIRS["b"])
    check("exports with both flags on succeed (twice)", rc == 0 and rc2 == 0, (out + out2)[-300:])
    fa, fb2 = files_of(DIRS["a"]), files_of(DIRS["b"])
    check("two flag-on exports: every file byte-identical (%d files)" % len(fa), fa == fb2)
    check("flag on: build/colour_identity/cards.json is exported and is the build file", fa.get("build/colour_identity/cards.json") == T.sha(CIJ))
    chk = lambda d: subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--check", "--out", os.path.relpath(DIRS[d], HERE)], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    check("whitelist check passes on the flag-on export", chk("a").returncode == 0)
    for plant in ("build/colour_identity/cards.json.bak", "build/colour_identity/extra.json", "build/colour_identity/notes.txt"):
        p = os.path.join(DIRS["a"], *plant.split("/")); open(p, "w").write("{}")
        check("planted %s is refused" % plant, chk("a").returncode != 0); os.remove(p)
    rc, out = export_to(DIRS["off"], cfg_with(PERSIST_FILTERS=False, COLOUR_IDENTITY=False))
    check("export with both flags off succeeds", rc == 0, out[-300:])
    offf = files_of(DIRS["off"])
    base = {x["path"]: x["sha256"] for x in json.load(open(os.path.join(BEFORE, "manifest.json"), encoding="utf-8"))["files"]}
    check("flags off: the same file list as the export made before this work (%d files)" % len(base), set(offf) - {"manifest.json"} == set(base), sorted(set(offf) ^ set(base))[:4])
    diff = [k for k in base if offf.get(k) != base[k]]
    check("flags off: every file is byte-identical to that export except config.js and testerfilters.js (the flags and the code behind them), plus groupsearch.js and tester.js (SEARCH_FIXES; src/test_search_fixes.py proves its flag-off behaviour)", sorted(diff) == ["reports/config.js", "reports/groupsearch.js", "reports/tester.js", "reports/testerfilters.js"], diff[:6])
    check("flags off: no colour_identity file is exported or listed", not [k for k in offf if "colour_identity" in k] and not [x for x in json.load(open(os.path.join(DIRS["off"], "manifest.json")))["files"] if "colour_identity" in x["path"]])
    shutil.copytree(DIRS["off"], DIRS["old"])
    shutil.copyfile(os.path.join(BEFORE, "testerfilters.js"), os.path.join(DIRS["old"], "reports", "testerfilters.js"))
    shutil.copyfile(os.path.join(BEFORE, "config.js"), os.path.join(DIRS["old"], "reports", "config.js"))
    rc, out = export_to(DIRS["p"], cfg_with(COLOUR_IDENTITY=False)); rc2, out2 = export_to(DIRS["c"], cfg_with(PERSIST_FILTERS=False))
    check("each flag alone exports and passes the whitelist; only COLOUR_IDENTITY adds a file", rc == 0 and rc2 == 0 and not [k for k in files_of(DIRS["p"]) if "colour_identity" in k] and "build/colour_identity/cards.json" in files_of(DIRS["c"]), (out + out2)[-200:])

    # ------------------------------------------------------------ 3. flags off against the old scripts
    PR = REF.Ref()
    big = sorted((g for g, v in PR.G.items() if v[4] and v[3] == "leaf"), key=lambda g: -PR.G[g][1])
    keys = [F.page_key(PR, g) for g in (big[0], big[3], big[10], big[40])]

    def drive_old(s, c):
        snaps = []
        for k in keys:
            F.open_page(c, k); c.wait("!!TF.topics()", 60); c.pump(0.3)             # the topic map arrives a moment after the page; wait for it so both runs are compared in the same state
            snaps.append(c.js("document.getElementById('fwrap').outerHTML"))
            click(c, '.fpip[data-v="U"]'); setmode(c, "exactly"); click(c, '.fch[data-v="Creature"]')
            snaps.append(c.js("document.getElementById('fwrap').outerHTML") + "|" + json.dumps(sorted(shown(c))))
        F.open_page(c, keys[1])
        snaps.append(json.dumps(state(c)))                       # today: another group starts with nothing on
        return snaps, sorted({r["url"].replace(s.base(), "") for r in s.net()}), s.console()
    on_ = run_session(DIRS["off"], 1280, drive_old); old = run_session(DIRS["old"], 1280, drive_old)
    check("flags off: the new testerfilters.js and the old one draw the same bar and list for 4 groups with filters on (%d snapshots)" % len(on_[0]), on_[0] == old[0] and all(len(x) > 100 for x in on_[0][:-1]))
    check("flags off: filters are reset when another group opens, as before", json.loads(on_[0][-1])["cols"] == [] and json.loads(on_[0][-1])["types"] == [])
    check("flags off: the same requests (%d), no colour_identity request, no console errors" % len(on_[1]), on_[1] == old[1] and not [u for u in on_[1] if "colour_identity" in u] and not on_[2] and not old[2], (set(on_[1]) ^ set(old[1]), on_[2][:2]))

    # ------------------------------------------------------------ 4. flag on, 1280 px
    pages = [keys[0], keys[1]]
    s = T.Session(DIRS["a"], "/reports/browse.html", 1280); c = s.c
    lists = []
    try:
        check("page boots with both flags on", c.wait(F.READY, 300) and c.js("TF.identityState().loaded===true"))
        c.pump(1)
        boot = [r["url"].replace(s.base(), "") for r in s.net()]
        check("first load: the colour identity file is requested once, and no other new file", boot.count("/build/colour_identity/cards.json") == 1, [u for u in boot if "colour" in u])
        F.open_page(c, pages[0])
        check("identity is the default basis; the 'Based on' row and the line under the pips say so", jx(c, "TF.basis()") == "identity" and "Colour identity: the colours in the cost and rules text" in c.js("document.querySelector('[data-basis-note]').textContent") and c.js("document.querySelector('[data-f=basis][data-v=identity]').getAttribute('aria-checked')") == "true")
        # a. blue selected, group changed, state kept
        pips(c, ["U"])
        st1 = state(c); full0 = jx(c, "TF.full()")
        F.open_page(c, pages[1])
        st2 = state(c); full1 = jx(c, "TF.full()")
        check("blue selected, group changed: colour, mode (Only these) kept; the list is the blue-identity cards of the new group (%d of %d)" % (len(shown(c)), len(full1)), st2["cols"] == ["U"] and st2["mode"] == "only" and shown(c) == expect(R, full1, {"U"}, "only", "identity") and st2["kept"])
        kt = c.js("(document.querySelector('.fkept')||{}).textContent||''")
        check("the line over the bar names the kept filters and has Clear all ('%s')" % kt, "Colour identity" in kt and "Only these" in kt and "Blue" in kt and "Clear all" in kt)
        check("sessionStorage holds colour, mode, type, mana value; sort is not in it", json.loads(c.js("sessionStorage.getItem('filterState')"))["c"] == ["U"] and "sort" not in c.js("sessionStorage.getItem('filterState')"))
        # b. type and mana value kept too; sort stays in localStorage
        click(c, '.fch[data-v="Creature"]'); click(c, '.fch[data-f="mv"][data-v="3"]')
        c.js("(()=>{const s=document.querySelector('select[data-f=sort]');s.value='name';s.dispatchEvent(new Event('change',{bubbles:true}))})()")
        F.open_page(c, pages[0])
        st3 = state(c)
        check("type and mana value are kept across a group change too", st3["types"] == ["Creature"] and st3["mvs"] == ["3"] and st3["cols"] == ["U"])
        check("sort stays in localStorage (sortPref=name) and is not in the session state", c.js("localStorage.getItem('sortPref')") == "name" and "name" not in c.js("sessionStorage.getItem('filterState')"))
        # c. reset: narrowing, subtype, trigger
        click(c, '[data-f="nfold"]'); click(c, '[data-f="bk"]')
        c.js("(()=>{const s=document.querySelector('select[data-f=ab][data-r=trig]');if(s&&s.options.length>1){s.value=s.options[1].value;s.dispatchEvent(new Event('change',{bubbles:true}))}})()"); c.pump(1.5)
        c.js("(()=>{const s=document.querySelector('select[data-f=sub]');if(s&&s.options.length>1){s.value=s.options[1].value;s.dispatchEvent(new Event('change',{bubbles:true}))}})()"); c.pump(1.5)
        sx = state(c)
        F.open_page(c, pages[1])
        sy = state(c)
        check("narrowing topic / trigger / subtype were on (%s) and are empty on the next group, colour kept" % {k: sx[k] for k in ("bk", "ab", "subs")}, (sx["bk"] or sx["ab"] or sx["subs"]) and sy["bk"] == 0 and sy["nar"] == 0 and sy["ab"] == [] and sy["subs"] == [] and sy["cols"] == ["U"] and sy["types"] == ["Creature"], (sx, sy))
        # d. reload keeps the tab's state
        c.call("Page.reload"); c.pump(2); c.wait(F.READY, 300); c.pump(1)
        F.open_page(c, pages[1])
        sr = state(c)
        check("a reload in the same tab keeps the filters; the sort and the basis come back too", sr["cols"] == ["U"] and sr["types"] == ["Creature"] and sr["mvs"] == ["3"] and c.js("document.querySelector('select[data-f=sort]').value") == "name")
        # e. each mode under identity; a mana rock excluded when blue is excluded
        byname = {}
        for o, cc in R.cards.items():
            byname.setdefault(cc["n"], o)
        egg = byname["Darkwater Egg"]
        gid = jx(c, "MI.cards[%s][3][0][0]" % json.dumps(egg))
        pk = F.page_key(PR, gid)
        F.open_page(c, pk); clear_all(c); c.pump(0.2)
        fullE = jx(c, "TF.full()")
        check("Darkwater Egg (card colour: none; identity: blue-black) is on the page %s" % PR.G[gid][0], egg in fullE and not R.card_col[egg] and R.mj[egg] == {"U", "B"})
        res = {}
        for cols in ({"U"}, {"U", "G"}):
            clear_all(c); pips(c, sorted(cols))
            for m in MODES:
                setmode(c, m)
                got = shown(c); exp = expect(R, fullE, cols, m, "identity")
                res[(tuple(sorted(cols)), m)] = (egg in got)
                if got != exp:
                    check("identity, %s, %s: list equals the MTGJSON-identity expectation" % (sorted(cols), m), False, (len(got), len(exp), sorted(got ^ exp)[:3]))
        check("each of the 5 modes, for blue and for blue+green, gives the MTGJSON-identity list on this page (10 lists)", True)
        check("with blue chosen: the rock is kept by Any / Includes all and left out by Only these / Exactly these; with 'Not these' it is excluded", res[(("U",), "any")] and res[(("U",), "all")] and not res[(("U",), "only")] and not res[(("U",), "exactly")] and not res[(("U",), "not")])
        clear_all(c); pips(c, ["U"]); setmode(c, "not")
        n_id = shown(c)
        click(c, '[data-f="basis"][data-v="card"]')
        check("Card colour basis: 'Not these: blue' keeps the rock (its card colour is none) and the list equals the card-colour expectation; the line says so", egg in shown(c) and shown(c) == expect(R, fullE, {"U"}, "not", "card") and egg not in n_id and "Card colour, not colour identity" in c.js("document.querySelector('[data-basis-note]').textContent") and jx(c, "TF.basis()") == "card")
        check("the basis is remembered in localStorage (colourBasis=card) and shows in the kept line after a group change", c.js("localStorage.getItem('colourBasis')") == "card")
        F.open_page(c, pages[0])
        check("…and the kept line names the basis", "Card colour" in c.js("(document.querySelector('.fkept')||{}).textContent||''"))
        click(c, '[data-f="basis"][data-v="identity"]')
        # f. forest, colourless, multicolour under identity
        F.open_page(c, pk); clear_all(c); pips(c, ["C"]); setmode(c, "any")
        fullE = jx(c, "TF.full()")
        check("◇ colourless under identity: exactly the cards whose identity is empty (%d)" % len(shown(c)), shown(c) == {o for o in fullE if not R.mj[o]})
        clear_all(c); pips(c, ["M"]); setmode(c, "any")
        check("M multicolour under identity: identity of two or more colours", shown(c) == {o for o in fullE if len(R.mj[o]) >= 2})
        # g. clear all
        clear_all(c)
        F.open_page(c, pages[1])
        sc_ = state(c)
        check("Clear all: nothing on, sessionStorage entry removed, no kept line on the next group", sc_["cols"] == [] and sc_["types"] == [] and sc_["mvs"] == [] and c.js("sessionStorage.getItem('filterState')") is None and not c.js("!!document.querySelector('.fkept')"))
        # h. empty results
        F.open_page(c, pages[1]); full1 = jx(c, "TF.full()")
        setmode(c, "exactly"); pips(c, list(W)); click(c, '.fch[data-v="Land"]')
        for mv in ("0",):
            if not shown(c):
                break
            click(c, '.fch[data-f="mv"][data-v="%s"]' % mv)
        msg = c.js("(document.querySelector('.fempty')||{}).textContent||''")
        empty_ok = (not shown(c)) and "No cards match these filters" in msg and ("%s card" % format(len(full1), ",")) in msg
        check("a group with nothing left says so with the group's size ('%s')" % msg[:160], empty_ok)
        # the 'without X it would show N' numbers, from the card records
        TYPES_ = {"Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Land", "Planeswalker", "Battle", "Kindred"}
        ts = lambda o: TYPES_ & set(w for ty in ([x["ty"] for x in R.faces[o]["f"]] if o in R.faces else [R.cards[o]["ty"]]) for w in ty.split(" - ")[0].split())           # FLIP_FACES: a two-faced card has the types of both faces
        sel_ = state(c)
        mvb = lambda o: (lambda mv: "none" if mv is None else "6+" if mv >= 6 else str(int(mv)))(R.cards[o]["mv"])
        okc = lambda o: colmodes(set(R.mj[o]), set(sel_["cols"]), sel_["mode"])
        okt = lambda o: not sel_["types"] or bool(ts(o) & set(sel_["types"]))
        okm = lambda o: not sel_["mvs"] or mvb(o) in sel_["mvs"]
        drops = {"colour": sum(1 for o in full1 if okt(o) and okm(o)), "type": sum(1 for o in full1 if okc(o) and okm(o)), "mana value": sum(1 for o in full1 if okc(o) and okt(o))}
        said = dict((m_.group(1), int(m_.group(2).replace(",", ""))) for m_ in re.finditer(r"without ([a-z ,]+?) it would show ([\d,]+)", msg.replace("Without", "without")))
        check("…and each 'without X it would show N' equals the count from the card records %s" % drops, bool(said) and all(drops.get(k) == v for k, v in said.items() if k in drops) and all(k in drops for k in said), (said, drops, msg))
        check("the empty message's Clear all filters button empties the filters and brings the list back", click(c, ".fempty .flink") and not state(c)["cols"] and len(shown(c)) == len(full1))
        # i. a pinned card the filters hide
        mc = byname["Mana Crypt"]
        F.open_page(c, pages[0]); pips(c, ["U"]); setmode(c, "only")
        c.js("openPin(%s)" % json.dumps(mc)); c.wait("!!document.getElementById('pinwrap')", 60); c.pump(1)
        pin_txt = c.js("document.getElementById('pinwrap').textContent")
        listed = jx(c, "TF.shown()")
        check("pinned card hidden by the kept filters: it stays in its pinned row, not in the list, with a note naming the filters", "Mana Crypt" in pin_txt and mc not in listed and "Hidden by your filters" in pin_txt and "Colour identity" in pin_txt and "not listed in this group any more" not in pin_txt, pin_txt[-220:])
        click(c, ".pinfilt .flink")
        check("its Clear all filters button removes the filters; the card is then in the list and the note is gone", not state(c)["cols"] and mc in jx(c, "TF.shown()") and not c.js("!!document.querySelector('.pinfilt')"))
        # j. the 30 lists against MTGJSON identity
        rng = random.Random(SEED_30)
        elig = sorted(g for g, v in PR.G.items() if v[4] and v[3] in ("leaf", "tent", "loose", "tag", "kw", "rp") and v[1] >= 40)
        draw = rng.sample(elig, 30)
        wrong, nbad, total = [], 0, 0
        for gid in draw:
            letters = rng.sample(list(W), rng.choice([1, 1, 2, 2, 3]))
            extra = rng.choice([[], [], [], ["C"], ["M"]])
            mode = rng.choice(MODES)
            if mode == "only" and "M" in extra:
                extra = []
            cols = set(letters) | set(extra)
            pk_ = F.page_key(PR, gid)
            F.open_page(c, pk_); clear_all(c); setmode(c, mode); pips(c, sorted(cols))             # the mode first: the multicolour chip is switched off under Only these
            full_ = jx(c, "TF.full()"); got = shown(c); exp = expect(R, full_, cols, mode, "identity")
            lists.append({"page": PR.G[gid][0], "cols": sorted(cols), "mode": mode, "page_size": len(full_), "shown": len(got), "expected": len(exp), "only_page": sorted(R.cards[o]["n"] for o in got - exp)[:5], "only_mtgjson": sorted(R.cards[o]["n"] for o in exp - got)[:5]})
            total += len(exp)
            if got != exp:
                wrong.append(lists[-1]); nbad += len(got ^ exp)
        json.dump(lists, open(reads_out, "w", encoding="utf-8"), indent=1)
        check("30 filtered lists (seed %d) against MTGJSON colour identity: %d lists differ (bar: more than 3 means fix), %d cards in dispute of %d expected" % (SEED_30, len(wrong), nbad, total), len(wrong) <= 3, [(w["page"], w["cols"], w["mode"], w["only_page"], w["only_mtgjson"]) for w in wrong][:3])
        print("lists that differ:", [(w["page"], w["cols"], w["mode"], w["only_page"], w["only_mtgjson"]) for w in wrong])
        # k. no failed requests, no console errors for the session
        net = [r for r in s.net() if r["url"].startswith(s.base())]
        check("no failed request, only GET, no console errors in the whole 1280 px session (%d requests)" % len(net), not [r for r in net if r["failed"] or (r["status"] or 200) >= 400 or r["method"] != "GET"] and not s.console(), [r for r in net if r["failed"] or (r["status"] or 200) >= 400][:3])
    finally:
        s.close()

    # ------------------------------------------------------------ 5. one flag at a time
    def only_persist(s_, c_):
        F.open_page(c_, pages[0]); pips(c_, ["U"]); F.open_page(c_, pages[1])
        return state(c_)["cols"], c_.js("!!document.querySelector('[data-f=basis]')"), [r["url"] for r in s_.net() if "colour_identity" in r["url"]]
    cols_, basis_, ci_ = run_session(DIRS["p"], 1280, only_persist)
    check("PERSIST_FILTERS alone: the colour is kept, there is no 'Based on' row and no colour_identity request", cols_ == ["U"] and not basis_ and not ci_)

    def only_ci(s_, c_):
        F.open_page(c_, pages[1]); pips(c_, ["U"]); st_a = state(c_)
        full_ = jx(c_, "TF.full()"); ok_ = shown(c_) == expect(R, full_, {"U"}, "only", "identity")
        F.open_page(c_, pages[0])
        return state(c_)["cols"], ok_, bool(c_.js("!!document.querySelector('.fkept')"))
    cols_, ok_, kept_ = run_session(DIRS["c"], 1280, only_ci)
    check("COLOUR_IDENTITY alone: identity filtering works; filters are still reset on a group change and no kept line shows", cols_ == [] and ok_ and not kept_)

    # ------------------------------------------------------------ 6. 390 px
    def phone(s_, c_):
        F.open_page(c_, pages[0]); pips(c_, ["U"]); click(c_, '.fch[data-v="Creature"]')
        F.open_page(c_, pages[1])
        out = {}
        out["kept"] = c_.js("(document.querySelector('.fkept')||{}).textContent||''")
        out["pills"] = c_.js("document.querySelector('.fsum .fpills').textContent")
        out["bar_hidden"] = c_.js("getComputedStyle(document.querySelector('.fbar')).display==='none'")
        out["scroll"] = c_.js("document.documentElement.scrollWidth<=window.innerWidth")
        click(c_, '.fsum[data-f="fold"]'); c_.pump(0.3)
        out["pip_h"] = c_.js("Math.min(...[...document.querySelectorAll('.fpip')].map(e=>e.getBoundingClientRect().height))")
        out["basis_h"] = c_.js("Math.min(...[...document.querySelectorAll('[data-f=basis]')].map(e=>e.getBoundingClientRect().height))")
        out["basis_visible"] = c_.js("document.querySelector('[data-f=basis]').getBoundingClientRect().width>0")
        out["scroll2"] = c_.js("document.documentElement.scrollWidth<=window.innerWidth")
        click(c_, '.fsum[data-f="fold"]')
        for t in ("Land", "Battle", "Kindred", "Planeswalker"):
            click(c_, '.fch[data-v="%s"]' % t)
        c_.js("(()=>{const s=document.querySelector('select[data-f=cmodesel]');if(!s)return false;s.value='exactly';s.dispatchEvent(new Event('change',{bubbles:true}));return true})()")
        pips(c_, list(W))
        for mv in ("0",):
            click(c_, '.fch[data-f="mv"][data-v="%s"]' % mv)
        out["empty_visible"] = c_.js("(()=>{const e=document.querySelector('.fempty');return !!e&&e.getBoundingClientRect().height>0&&getComputedStyle(e.closest('.fwrap').querySelector('.fbar')).display==='none'})()") if not shown(c_) else "not empty"
        out["clear_h"] = c_.js("(()=>{const e=document.querySelector('.fkept .flink');return e?e.getBoundingClientRect().height:0})()")
        out["scroll3"] = c_.js("document.documentElement.scrollWidth<=window.innerWidth")
        net = [r for r in s_.net() if r["url"].startswith(s_.base())]
        out["fail"] = [r for r in net if r["failed"] or (r["status"] or 200) >= 400]
        out["cons"] = s_.console()
        return out
    ph = run_session(DIRS["a"], 390, phone)
    check("390 px: the folded line shows 'Identity · Only these…' ('%s'), the kept line is above it ('%s')" % (ph["pills"], ph["kept"][:60]), "Identity" in ph["pills"] and "Blue" in ph["pills"] and "Clear all" in ph["kept"] and ph["bar_hidden"])
    check("390 px: opened, the pips are %spx and the basis buttons %spx high (>= 40 / 44), the switch is visible" % (ph["pip_h"], ph["basis_h"]), ph["pip_h"] >= 40 and ph["basis_h"] >= 44 and ph["basis_visible"])
    check("390 px: the empty message shows while the bar is folded; Clear all is tall enough (%s)" % ph["clear_h"], ph["empty_visible"] is True and ph["clear_h"] >= 40, ph["empty_visible"])
    check("390 px: nothing scrolls sideways (folded, opened, empty)", ph["scroll"] and ph["scroll2"] and ph["scroll3"])
    check("390 px: no failed request, no console error", not ph["fail"] and not ph["cons"], (ph["fail"][:2], ph["cons"][:2]))

    # ------------------------------------------------------------ 7. first load and timing (flags off against flags on, 4x CPU, 9 Mbps / 170 ms, 390 px)
    if not skip_perf:
        perf = {}
        for label, root in (("flags off", DIRS["off"]), ("flags on", DIRS["a"])):
            runs = []
            for _ in range(3):
                s = T.Session(root, "/reports/browse.html", 390, gz=True, throttle=(9000, 170), cpu=4); c = s.c
                try:
                    t0 = time.time()
                    ok = c.wait(F.READY, 900); t_ready = time.time() - t0
                    c.pump(1)
                    boot = [r for r in s.net() if r["url"].startswith(s.base())]
                    F.open_page(c, keys[0])
                    times = []
                    for _i in range(5):
                        times.append(round(c.js("(()=>{const b=document.querySelector('.fpip[data-v=\"U\"]');const t=performance.now();b.click();const d=performance.now()-t;return d})()"), 1))
                        c.pump(0.2)
                        times.append(round(c.js("(()=>{const b=document.querySelector('.fpip[data-v=\"U\"]');const t=performance.now();b.click();const d=performance.now()-t;return d})()"), 1))
                        c.pump(0.2)
                    t_change = None
                    if label == "flags on":
                        pips(c, ["U"]); c.pump(0.3)
                        t_change = round(c.js("(()=>{const t=performance.now();window.__r=null;return t})()"))
                        t1 = time.time(); F.open_page(c, keys[1]); t_change = round((time.time() - t1) * 1000)
                    runs.append({"ready_s": round(t_ready, 2), "boot_requests": len(boot), "boot_bytes": sum(r["bytes"] or 0 for r in boot), "click_ms": sorted(times)[len(times) // 2], "group_change_ms": t_change, "ok": ok, "files": sorted(r["url"].replace(s.base(), "") for r in boot if "colour" in r["url"])})
                finally:
                    s.close()
            perf[label] = runs
            print(label, runs)
        a, b_ = perf["flags on"], perf["flags off"]
        med = lambda L, k: sorted(x[k] for x in L)[len(L) // 2]
        check("first load: boot requests with the flags on are the flags-off ones plus colour_identity/cards.json (%d vs %d)" % (a[0]["boot_requests"], b_[0]["boot_requests"]), a[0]["boot_requests"] == b_[0]["boot_requests"] + 1 and a[0]["files"] == ["/build/colour_identity/cards.json"])
        print("median ready_s off/on: %s / %s; boot bytes off/on: %s / %s; median filter click (draw of the biggest group) off/on: %s / %s ms; group change with filters kept: %s ms" % (
            med(b_, "ready_s"), med(a, "ready_s"), med(b_, "boot_bytes"), med(a, "boot_bytes"), med(b_, "click_ms"), med(a, "click_ms"), med(a, "group_change_ms")))

    # ------------------------------------------------------------ 8. nothing changed that must not change
    after = dict(T.protected())
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    check("corrections/, archive/, the shared scripts and the top-level build files are byte-identical to before (%d hashed)" % len(before), not changed, changed[:4])
    T.test_figures()
    if "--keep" not in sys.argv:
        for dd in DIRS.values():
            shutil.rmtree(dd, ignore_errors=True)
    bad = [n for n, ok, _ in T.RESULTS if not ok]
    print("\n%d checks, %d failed" % (len(T.RESULTS), len(bad)))
    for n in bad:
        print("FAILED:", n)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
