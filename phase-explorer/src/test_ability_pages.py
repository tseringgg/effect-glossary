#!/usr/bin/env python3
"""Verify the ability-type pages and filters, each behind a flag in reports/config.js: ABILITY_TYPE_PAGES ("Ability types": triggered, activated, static and replacement pages) and
ABILITY_TYPE_FILTERS (the Trigger, Cost and Kind rows of the filter bar). Headless Edge over the DevTools protocol on exported dist folders served by a plain static server (GET only).

    python src/test_ability_pages.py [--skip-perf] [--reads OUT.json]

What is checked, and what is independent of the page's own code:
  * protected files hashed before and after (corrections/ incl. backups, archive/, the shared JS, serve.py, top-level build files, build/chunks, index.json, placements.json): nothing here writes to them;
  * the data files (src/build_ability_pages.py): built twice, same bytes, and --check agrees; every page file has the card-list signature; the rules line of a member is the card's own text;
  * exports: flags on, twice, byte-identical, whitelist check passes and planted files are refused; flags off (only the two new flags off): the same file list as the export made before this work
    (src/testdata/before_ability_pages/manifest.json) and every file but tester.js, testerfilters.js, config.js and the manifest byte-identical to it; and the flags-off page, run beside the
    pre-feature scripts (saved there from git HEAD), draws the same DOM and makes the same requests after the same steps;
  * pages: a trigger page, an activated-cost page and a static page open from the tree and show the matching ability line on each row; a search for "etb", "dies" and "anthem" finds an ability page;
  * the 42 pages: the first 20 rows of each, as drawn, are read against a text rule per page written in this file from the Magic rules wording (NOT the parser): a row is "wrong" when none of its
    lines fits the rule. Bar: more than 3 wrong among a page's first 20 fails that page. 30 pages are drawn with seed %(SEED_P)d, fixed before anything was computed; all 42 are also run and reported.
    Precision and recall of each page against the same text rule over every card's text are reported (not a bar). My own reading of the rows is NOT independent (--reads writes them out);
  * filters: Trigger, Cost, Kind chosen on a group page give exactly the group's cards that are on the chosen pages (worked out in Python from the page files), AND across rows, OR inside one row;
  * 390 px, no failed request, no console error, nothing sent; first-load size and time at 1x and 4x CPU, flags off against flags on.
Clicks are DOM click() calls and the search box is typed with key events: no touch, no other browser.
"""
import hashlib
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_tester_static as T            # noqa: E402
import test_tester_features as TF         # noqa: E402

check = T.check
SEED_P = 20263501                                           # fixed here, before any page was computed
__doc__ = __doc__ % {"SEED_P": SEED_P}
BEFORE = os.path.join(HERE, "src", "testdata", "before_ability_pages")
DIRS = {k: os.path.join(HERE, "dist." + k) for k in ("ab", "ab2", "off", "old")}
AB_FLAGS = ("ABILITY_TYPE_PAGES", "ABILITY_TYPE_FILTERS")
OUT = os.path.join(HERE, "build", "ability_pages")


def jx(c, expr):
    return json.loads(c.js("JSON.stringify(" + expr + ")"))


# the text rule for each page, from the rules wording: a line of the card's text fits when it matches
I = re.I
RX = {
    "trig.enters": r"(when|whenever)\b[^,.]*\benters?\b", "trig.enters-other": r"(when|whenever)\b[^,.]*\benters?\b", "trig.landfall": r"\benters?\b|landfall",
    "trig.dies": r"\bdies?\b|put into a graveyard", "trig.dies-other": r"\bdies?\b|put into a graveyard|\bdie\b", "trig.leaves": r"leaves? the battlefield",
    "trig.attacks": r"\battack", "trig.you-attack": r"\battack", "trig.blocks": r"\bblock", "trig.combat-damage": r"combat damage", "trig.upkeep": r"upkeep",
    "trig.end-step": r"end step", "trig.begin-combat": r"beginning of (?:each |the |your )?(?:combat|first combat)", "trig.cast": r"\bcasts?\b", "trig.draw": r"\bdraws?\b",
    "trig.counter-added": r"counters? (?:is|are)? ?put|put[^.]*counters?|counters? on", "trig.life-gained": r"gains? (?:\d+ |that much |x )?life|life gain|lifegain|gain life", "trig.becomes-target": r"becomes? the target|is targeted",
    "act.mana-abilities": r":[^.]*\badd\b", "act.tap": r"\{t\}[^:]*:|tap[^:]*:", "act.mana": r"^(?:[\w' ]+ [—-] )?(?:\{[^}]+\}[, ]*)+:", "act.sacrifice": r"sacrifice[^:]*:",
    "act.discard": r"discard[^:]*:", "act.exile-gy": r"exile[^:]*graveyard[^:]*:", "act.remove-counter": r"remove[^:]*counters?[^:]*:", "act.pay-life": r"pay [^:]*life[^:]*:",
    "act.loyalty": r"^(?:\[?[+−\-–]?(?:\d+|x)\]?)\s*:", "stat.anthem": r"get[s]? [+\-−]\d|gets? [+\-−]x|[+\-−]\d+/[+\-−]\d+",
    "stat.keyword-grant": r"\bhave\b|\bhas\b|\bgains?\b", "stat.attached-bonus": r"equipped|enchanted|fortified|attached", "stat.cost-reduce": r"cost[s]? (?:\{[^}]+\}|[\w ]+) less|less to (?:cast|activate)|cost[s]? less",
    "stat.cost-raise": r"more to (?:cast|activate)|cost[s]?[^.]* more|more to", "stat.cant-block": r"can'?t (?:attack or )?block|cannot (?:attack or )?block|can'?t block",
    "stat.cant-attack": r"can'?t (?:attack|be declared)|cannot attack", "stat.evasion": r"can'?t be blocked|cannot be blocked", "stat.cant-be-countered": r"can'?t be countered|cannot be countered",
    "stat.cant-untap": r"untap", "stat.must-attack": r"attacks? each (?:combat|turn)|must attack|attack each", "repl.etb-tapped": r"tapped", "repl.etb-counters": r"counters?",
    "repl.damage": r"damage", "repl.dies-exile": r"instead",
}


def flags_text(**kw):
    txt = open(os.path.join(HERE, "reports", "config.js"), encoding="utf-8").read()
    for f, v in kw.items():
        txt = re.sub(r"\b%s\s*:\s*(true|false)" % f, "%s: %s" % (f, "true" if v else "false"), txt)
    return txt


def tmp_config(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    f.write(text); f.close()
    return f.name


def cleanup():
    for d in DIRS.values():
        shutil.rmtree(d, ignore_errors=True)


def files_of(root):
    return {os.path.relpath(p, root).replace("\\", "/"): T.sha(p) for p in T.walk(root)}


def extra_protected():
    out = {}
    for p in T.walk(os.path.join(HERE, "build", "chunks")) + [os.path.join(HERE, "build", n) for n in ("index.json", "placements.json")]:
        if os.path.exists(p):
            out["x:" + os.path.relpath(p, HERE).replace("\\", "/")] = T.sha(p)
    return out


def wait_page(c, key, secs=90):
    c.js("show(%s)" % json.dumps(key))
    return c.wait("selected===%s && !document.getElementById('panel').classList.contains('tpend') && !!document.querySelector('#list [data-oid]') && !!document.getElementById('fwrap') && TF.full().length > 0" % json.dumps(key), secs)


def page_state(c):
    return jx(c, "{h1:(document.querySelector('.thead h1')||{}).textContent, cnt:(document.querySelector('.tcnt')||{}).textContent, note:(document.querySelector('.tgnote')||{}).textContent, crumb:(document.querySelector('.crumb')||{}).textContent, n:document.querySelectorAll('#list [data-oid]').length, lines:document.querySelectorAll('#list .aptile, #list .apline').length, hash:location.hash}")


def top_rows(c, n=20):
    """The first n rows as drawn: card id, name and every matching line the row carries."""
    return jx(c, "[...document.querySelectorAll('#list [data-oid]')].slice(0,%d).map(e=>({oid:e.dataset.oid,name:(e.querySelector('.nm')||e.querySelector('.tname')||e.querySelector('b')||e).textContent.trim(),lines:[...e.querySelectorAll('.aptile')].map(x=>x.title||x.textContent).concat([...e.querySelectorAll('.apline')].map(x=>x.textContent)).join(' / ').split(' / ')}))" % n)


def main():
    skip_perf = "--skip-perf" in sys.argv
    reads_out = sys.argv[sys.argv.index("--reads") + 1] if "--reads" in sys.argv else os.path.join(tempfile.gettempdir(), "ability_pages_reads.json")
    before = dict(T.protected()); before.update(extra_protected())
    cleanup()
    cards = json.load(open(os.path.join(HERE, "build", "ability_taxonomy_cards.json"), encoding="utf-8"))["cards"]
    order = list(cards)

    # ------------------------------------------------------------ 1. the data files
    def build_hashes():
        return {os.path.relpath(p, OUT).replace("\\", "/"): T.sha(p) for p in T.walk(OUT)}
    r1 = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "build_ability_pages.py")], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    check("build_ability_pages.py runs", r1.returncode == 0, r1.stdout + r1.stderr)
    h1 = build_hashes()
    r2 = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "build_ability_pages.py")], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    h2 = build_hashes()
    check("built twice: %d files, byte-identical" % len(h1), r2.returncode == 0 and h1 == h2)
    r3 = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "build_ability_pages.py"), "--check"], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    check("--check agrees with the files on disk", r3.returncode == 0, r3.stdout)
    index = json.load(open(os.path.join(OUT, "index.json"), encoding="utf-8"))
    check("index: 42 pages, keys 'ab:kind.name', unique", len(index["groups"]) == 42 and len({g[0] for g in index["groups"]}) == 42 and all(re.match(r"^ab:(trig|act|stat|repl)\.[a-z\-]+$", g[0]) for g in index["groups"]))
    shard = {}
    bad_sig, bad_idx, nolines, tot = [], [], 0, 0
    for g in index["groups"]:
        d = json.load(open(os.path.join(OUT, "p", g[0][3:] + ".json"), encoding="utf-8"))
        shard[g[0]] = d
        if d["sig"] != index["sig"]:
            bad_sig.append(g[0])
        r = d["r"]
        for n in range(len(r) // 2):
            tot += 1
            if not (0 <= r[2 * n] < len(order)) or r[2 * n + 1] >= len((cards[order[r[2 * n]]].get("t") or "").split("\n")):
                bad_idx.append((g[0], n))
            if r[2 * n + 1] < 0:
                nolines += 1
    check("page files: signature matches the index, every card and line index in range", not bad_sig and not bad_idx, (bad_sig[:2], bad_idx[:2]))
    check("rules line found for %d of %d memberships (%.1f%%); the rest carry the parser's wording" % (tot - nolines, tot, 100 * (tot - nolines) / tot), nolines / tot < 0.01)
    check("cards and items per page agree with the page files", all(g[3] == len({shard[g[0]]["r"][2 * n] for n in range(len(shard[g[0]]["r"]) // 2)}) and g[4] == len(shard[g[0]]["r"]) // 2 for g in index["groups"]))

    # ------------------------------------------------------------ 2. exports
    def export_to(out, cfg=None):
        cmd = [sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--out", os.path.relpath(out, HERE)] + (["--config", cfg] if cfg else [])
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=HERE)
        return r.returncode, r.stdout + r.stderr
    rc, out = export_to(DIRS["ab"])
    rc2, out2 = export_to(DIRS["ab2"])
    check("exports with the flags on succeed (twice)", rc == 0 and rc2 == 0, (out + out2)[-300:])
    f1, f2 = files_of(DIRS["ab"]), files_of(DIRS["ab2"])
    check("two flags-on exports: every file byte-identical (%d files)" % len(f1), f1 == f2)
    ab_files = sorted(k for k in f1 if "ability_pages" in k or "abilitypages" in k)
    check("flags on: the new files are exactly abilitypages.js/.css, the index and 42 page files (%d)" % len(ab_files), len(ab_files) == 2 + 1 + 42 and "reports/abilitypages.js" in ab_files and "build/ability_pages/index.json" in ab_files, ab_files[:4])
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--check", "--out", os.path.relpath(DIRS["ab"], HERE)], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    check("whitelist check passes on the flags-on export", r.returncode == 0, r.stdout + r.stderr)
    for plant in ("build/ability_pages/p/extra.json.bak", "build/ability_pages/notes.txt", "build/ability_pages/p/UPPER.json", "corrections/group_aliases.json"):
        p = os.path.join(DIRS["ab"], *plant.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write("{}")
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--check", "--out", os.path.relpath(DIRS["ab"], HERE)], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
        check("planted %s is refused" % plant, r.returncode != 0)
        os.remove(p)
        if plant.startswith("corrections"):
            shutil.rmtree(os.path.dirname(p))
    private = [k for k in ab_files if k.endswith((".js", ".css", ".json"))]
    leak = [k for k in private if re.search(rb"corrections|group_aliases|manual_placements|backups", open(os.path.join(DIRS["ab"], *k.split("/")), "rb").read())]
    check("nothing private in the new files (no corrections/, aliases or hand-placement names)", not leak, leak[:3])
    cfg_off = tmp_config(flags_text(ABILITY_TYPE_PAGES=False, ABILITY_TYPE_FILTERS=False))
    rc, out = export_to(DIRS["off"], cfg_off)
    check("export with the two flags off succeeds", rc == 0, out[-300:])
    old = json.load(open(os.path.join(BEFORE, "manifest.json"), encoding="utf-8"))
    oldf = {f["path"]: f["sha256"] for f in old["files"]}
    offf = files_of(DIRS["off"])
    skip = {"reports/tester.js", "reports/testerfilters.js", "reports/config.js", "manifest.json", "reports/browse.html"}
    # browse.html is untouched by this work; the earlier export was made from a copy with other line endings, so compare it with git HEAD, ignoring line endings
    head = subprocess.run(["git", "show", "HEAD:phase-explorer/reports/browse.html"], capture_output=True, cwd=HERE).stdout
    cur = open(os.path.join(HERE, "reports", "browse.html"), "rb").read()
    norm = lambda b: b.replace(bytes([13, 10]), bytes([10]))
    check("browse.html is unchanged from git HEAD (line endings aside)", norm(head) == norm(cur) and open(os.path.join(DIRS["off"], "reports", "browse.html"), "rb").read() == open(os.path.join(HERE, "reports", "browse.html"), "rb").read())
    check("flags off: the same file list as the export made before this work (%d files)" % len(oldf), set(offf) - {"manifest.json"} == set(oldf), (sorted(set(offf) ^ set(oldf))[:4]))
    diff = [k for k in oldf if k not in skip and offf.get(k) != oldf[k]]
    check("flags off: every file but tester.js, testerfilters.js, config.js is byte-identical to that export (data files included)", not diff, diff[:4])
    check("flags off: no ability file is exported or listed", not [k for k in offf if "ability_pages" in k or "abilitypages" in k])

    # ------------------------------------------------------------ 3. flags off against the old scripts: same DOM, same requests
    shutil.copytree(DIRS["off"], DIRS["old"])
    for n in ("tester.js", "testerfilters.js", "config.js"):
        shutil.copyfile(os.path.join(BEFORE, n), os.path.join(DIRS["old"], "reports", n))

    def drive(root):
        s, ok = TF.boot(root, 1280)
        c = s.c
        try:
            m = s.mark()
            sig = []
            if not ok:
                return None
            sig.append(c.js("document.getElementById('tree').innerHTML.length"))
            for key in ("ty:u.saga", "l:ab2d4667c5"):
                c.js("show(%s)" % json.dumps(key)); c.wait("selected===%s && !document.getElementById('panel').classList.contains('tpend') && !!document.querySelector('#list [data-oid]')" % json.dumps(key), 120); c.pump(1)
                sig.append(hashlib.sha256(c.js("document.getElementById('panel').innerHTML").encode()).hexdigest()[:16])
                sig.append(hashlib.sha256(c.js("document.getElementById('tree').innerHTML").encode()).hexdigest()[:16])
            c.js("document.getElementById('q').focus()"); c.type("etb"); c.wait("document.querySelectorAll('#findres .gr, #findres .fr').length > 0", 90); c.pump(1.2)
            sig.append(hashlib.sha256(c.js("document.getElementById('findres').innerHTML").encode()).hexdigest()[:16])
            reqs = sorted((r["method"], r["url"].replace(s.base(), "")) for r in s.net(m) if r["url"].startswith(s.base()))
            return sig, reqs
        finally:
            s.close()
    a, b = drive(DIRS["off"]), drive(DIRS["old"])
    check("flags off: the page draws the same DOM (tree, two pages, search results) as with the pre-feature scripts", a is not None and b is not None and a[0] == b[0], (a and a[0], b and b[0]))
    check("flags off: the same requests (%d) as with the pre-feature scripts" % (len(a[1]) if a else -1), a is not None and b is not None and a[1] == b[1], [x for x in (set(a[1]) ^ set(b[1]))][:4] if a and b else "")

    # ------------------------------------------------------------ 4. flags on: pages, search, filters, 390 px
    s, ok = TF.boot(DIRS["ab"], 1280)
    c = s.c
    reads = {}
    try:
        check("flags on: page boots, no AP error", ok and c.js("typeof AP") == "object")
        m0 = s.mark()
        # the tree
        c.js("document.querySelector('#tree .row[data-k=\"AB:\"]').click()"); c.pump(0.8)
        kinds = jx(c, "[...document.querySelectorAll('#tree .row')].filter(r=>r.dataset.k.startsWith('ABd:')).map(r=>r.dataset.k)")
        check("tree: 'Ability types' opens with Triggered, Activated, Static, Replacement", kinds == ["ABd:trig", "ABd:act", "ABd:stat", "ABd:repl"], kinds)
        c.js("document.querySelector('#tree .row[data-k=\"ABd:trig\"]').click()"); c.pump(0.5)
        trows = jx(c, "[...document.querySelectorAll('#tree .row')].filter(r=>r.dataset.k.startsWith('ab:trig.')).map(r=>r.dataset.k)")
        check("tree: the Triggered folder lists its 18 pages", len(trows) == 18 and trows[0] == "ab:trig.enters", trows[:2])
        c.js("document.querySelector('#tree .row[data-k=\"ab:trig.dies\"]').click()")
        okp = c.wait("selected==='ab:trig.dies' && !document.getElementById('panel').classList.contains('tpend') && !!document.querySelector('#list [data-oid]') && !!document.getElementById('fwrap')", 90); c.pump(1)
        st = page_state(c)
        g = {x[0]: x for x in index["groups"]}["ab:trig.dies"]
        check("trigger page (opened from the tree): name, '%s cards', crumb, the parser note" % format(g[3], ","), okp and st["h1"] == g[1] and st["cnt"] == "%s cards" % format(g[3], ",") and "Cards the parser couldn’t read aren’t included." in st["note"] and "Triggered" in st["crumb"] and "not a placement" in st["note"], st)
        check("trigger page: every row drawn carries the matching ability line; address carries the key", st["n"] > 0 and st["lines"] >= st["n"] and "ab%3Atrig.dies" in st["hash"] + "ab%3Atrig.dies", st)
        c.js("document.querySelector('[data-view=text]').click()"); c.pump(0.8)
        tx = jx(c, "[...document.querySelectorAll('#list .card')].slice(0,5).map(e=>({n:e.querySelector('.nm').textContent,l:[...e.querySelectorAll('.apline')].map(x=>x.textContent)}))")
        check("trigger page (Text view): rows show the card's own ability line", len(tx) == 5 and all(x["l"] and re.search(r"\bdies?\b|graveyard", " ".join(x["l"]), re.I) for x in tx), tx[:2])
        c.js("document.querySelector('[data-view=images]').click()"); c.pump(0.5)
        for key, h1, rx in (("ab:act.sacrifice", None, r"sacrifice"), ("ab:stat.anthem", None, r"\+\d")):
            oko = wait_page(c, key); c.pump(1)
            st = page_state(c)
            gg = {x[0]: x for x in index["groups"]}[key]
            check("%s page opens: '%s', %s cards, lines on the rows, the parser note" % (key, gg[1], format(gg[3], ",")), oko and st["h1"] == gg[1] and st["cnt"] == "%s cards" % format(gg[3], ",") and st["lines"] > 0 and "parser couldn’t read" in st["note"], st)
            rows = top_rows(c, 20)
            check("%s: the first rows' lines fit the page (%s)" % (key, rx), sum(1 for r in rows if any(re.search(rx, l, re.I) for l in r["lines"])) >= 17, [r["lines"][:1] for r in rows[:3]])
        wait_page(c, "ab:act.mana"); check("activated page note says keyword abilities (Equip, cycling) are not on it", "Keyword abilities" in page_state(c)["note"])
        # a page that is partly read says so
        wait_page(c, "ab:trig.enters"); nt = page_state(c)["note"]
        check("ETB page says some abilities are only partly read", "only partly read" in nt, nt)
        # the page is a filter, not a placement: no group chip for it on a group page, nothing placed
        wait_page(c, "l:ab2d4667c5")
        chips = jx(c, "TF.chipsAll().map(x=>x.key)")
        check("ability pages are never offered as 'Narrow by group' chips", not [k for k in chips if str(k).startswith("ab:") or "abpage" in str(k)], len(chips))
        # search
        def search(q):
            c.js("document.querySelector('.sclr').click()"); c.pump(0.3)
            c.js("document.getElementById('q').focus()"); c.type(q)
            c.wait("document.querySelectorAll('#findres .gr, #findres .fr').length > 0", 90); c.pump(1.2)
            return jx(c, "[...document.querySelectorAll('#findres .gr')].map(g=>[g.dataset.go, g.querySelector('.gn').textContent, (g.querySelector('.gd')||{}).textContent||''])")
        want = {"etb": "ab:trig.enters", "dies": "ab:trig.dies", "anthem": "ab:stat.anthem", "death trigger": "ab:trig.dies", "tap ability": "ab:act.tap", "lord": "ab:stat.anthem",
                "cost reduction": "ab:stat.cost-reduce", "landfall": "ab:trig.landfall", "enters tapped": "ab:repl.etb-tapped"}
        bad = []
        pos = {}
        for q, key in want.items():
            res = search(q)
            keys = [r[0] for r in res]
            pos[q] = keys.index(key) if key in keys else -1
            if key not in keys[:4]:
                bad.append((q, keys[:5]))
        check("search: " + ", ".join("%s (#%d)" % (q, pos[q] + 1) for q in want) + " each find their ability page in the first four results", not bad, bad[:3])
        res = search("etb")
        check("search 'etb': the row says 'a filter, not a placement' and shows the card count", "not a placement" in res[0][2] and c.js("/%s cards/.test(document.querySelector('#findres .gr').innerText)" % format({x[0]: x for x in index['groups']}['ab:trig.enters'][3], ",")), res[0])
        for q, key in (("saga", "ty:u.saga"), ("creature", "ty:t.creature"), ("elves", "ty:u.elf")):
            res = search(q)
            check("search '%s': the type page is still first" % q, res and res[0][0] == key, res[:2])
        for q in ("draw cards", "board wipe"):
            res = search(q)
            check("search '%s': no ability page above the existing results" % q, res and not res[0][0].startswith("ab:"), res[:2])
        res = search("etb"); c.js("document.querySelector('#findres .gr').click()")
        check("search result opens the page", c.wait("selected==='ab:trig.enters' && !!document.querySelector('#list [data-oid]')", 90))
        c.js("document.querySelector('.sclr').click()"); c.pump(0.3)

        # ---- the filter rows on a group page
        wait_page(c, "l:ab2d4667c5"); c.pump(1)
        labels = jx(c, "[...document.querySelectorAll('.fbar .flab')].map(x=>x.textContent)")
        check("filter bar: Trigger, Cost and Kind rows after Subtype", labels[labels.index("Subtype"):labels.index("Subtype") + 4] == ["Subtype", "Trigger", "Cost", "Kind"], labels)
        full = jx(c, "TF.full()")

        def members(key):
            d = shard[key]
            return {order[d["r"][2 * n]] for n in range(len(d["r"]) // 2)}

        def choose(row, key):
            c.js("(()=>{const s=document.querySelector('select[data-f=ab][data-r=%s]'); s.value=%s; s.dispatchEvent(new Event('change',{bubbles:true}))})()" % (row, json.dumps(key)))
            c.wait("TF.state().ab.%s.has(%s) && AP.loaded(%s)" % (row, json.dumps(key), json.dumps(key)), 60); c.pump(0.8)
        opts = jx(c, "[...document.querySelectorAll('select[data-f=ab]')].map(s=>[s.dataset.r,[...s.options].length-1])")
        check("filter rows: Trigger offers 18, Cost 9, Kind 15 pages", opts == [["trig", 18], ["cost", 9], ["kind", 15]], opts)
        choose("trig", "ab:trig.enters")
        e1 = members("ab:trig.enters") & set(full)
        got = set(jx(c, "TF.shown()"))
        pic = set(jx(c, "TF.shown()"))
        check("Trigger = ETB on 'Draw cards': shows %d, the group's cards on the ETB page (page file): %d" % (len(got), len(e1)), got <= e1 and len(got) > 0 and len(got) >= 0.8 * len(e1), (len(got), len(e1)))
        stn = c.js("document.querySelector('.fbar .fstat span').textContent")
        choose("trig", "ab:trig.dies")
        e2 = (members("ab:trig.enters") | members("ab:trig.dies")) & set(full)
        got2 = set(jx(c, "TF.shown()"))
        check("Trigger = ETB or Dies (OR inside a row): %d shown, expected %d of the pictured cards" % (len(got2), len(e2)), got2 <= e2 and len(got2) >= 0.8 * len(e2) and len(got2) > len(got), (len(got2), len(e2)))
        choose("cost", "ab:act.sacrifice")
        e3 = e2 & members("ab:act.sacrifice")
        got3 = set(jx(c, "TF.shown()"))
        check("plus Cost = Sacrifice (AND across rows): %d shown, expected %d" % (len(got3), len(e3)), got3 <= e3 and len(got3) >= 0.8 * len(e3), (len(got3), len(e3)))
        summ = c.js("document.querySelector('.fbar').parentElement.querySelector('.fpills').textContent")
        check("the folded filter line names the chosen pages", "ETB" in summ and "Sacrifice" in summ, summ)
        c.js("document.querySelector('[data-f=abx][data-v=\"ab:act.sacrifice\"]').click()"); c.pump(0.6)
        got4 = set(jx(c, "TF.shown()"))
        check("removing a chip restores the wider list", got4 == got2)
        choose("kind", "ab:stat.anthem")
        got5 = set(jx(c, "TF.shown()"))
        check("Kind = Anthems on top of the Trigger row: a subset of the Trigger result", got5 <= got2)
        c.js("document.querySelector('[data-f=clear]').click()"); c.pump(0.6)
        check("Clear filters empties the three rows", c.js("TF.state().ab.trig.size+TF.state().ab.cost.size+TF.state().ab.kind.size") == 0 and len(jx(c, "TF.shown()")) >= len(got2))
        # the filter bar also works on an ability page itself
        wait_page(c, "ab:trig.enters"); choose("cost", "ab:act.tap")
        got6 = set(jx(c, "TF.shown()"))
        exp6 = members("ab:trig.enters") & members("ab:act.tap")
        check("on the ETB page, Cost = Tap abilities shows cards that are on both pages (%d of %d expected)" % (len(got6), len(exp6)), got6 <= exp6 and len(got6) >= 0.8 * len(exp6) > 0, (len(got6), len(exp6)))
        # ---- the ability pages in a different viewing: no POST, nothing sent
        net = [r for r in s.net(m0) if r["url"].startswith(s.base())]
        check("no POST and no endpoint request (%d requests)" % len(net), not [r for r in net if r["method"] != "GET" or "/api/" in r["url"]])
        bad = [r for r in net if r["failed"] or (r["status"] or 0) >= 400]
        con = [x for x in s.console(m0) if not re.search(r"cards\.scryfall\.io", x)]
        check("1280 px run: no failed request, no console error", not bad and not con, (bad[:2], con[:2]))
        # lazy loading: only the pages that were opened were requested
        pg_req = sorted({r["url"].rsplit("/", 1)[1] for r in net if "/ability_pages/p/" in r["url"]})
        check("lazy: only the page files that were opened or chosen were requested (%d of 42)" % len(pg_req), 0 < len(pg_req) < 15, pg_req)

        # ---- the 42 pages, first 20 rows each, read against the text rules
        keys = [g[0] for g in index["groups"]]
        seed30 = sorted(random.Random(SEED_P).sample(keys, 30))
        c.js("TF.reset && TF.reset()")
        per = {}
        for key in keys:
            oko = wait_page(c, key, 120); c.pump(0.6)
            rows = top_rows(c, 20)
            rx = re.compile(RX[key[3:]], re.I)
            wrong = [r for r in rows if not any(rx.search(l) for l in r["lines"] if l)]
            per[key] = (oko, len(rows), wrong)
            reads[key] = [{"name": r["name"], "lines": r["lines"][:2], "wrong": r in wrong} for r in rows]
        short = [k for k in keys if per[k][1] < 20 and {x[0]: x for x in index["groups"]}[k][3] >= 20]
        check("all 42 pages open and draw 20 rows (where they have them)", all(per[k][0] for k in keys) and not short, short)
        over = [(k, len(per[k][2])) for k in seed30 if len(per[k][2]) > 3]
        check("30 pages (seed %d): no page has more than 3 wrong among its first 20 rows" % SEED_P, not over, over)
        over_all = [(k, len(per[k][2])) for k in keys if len(per[k][2]) > 3]
        check("all 42 pages: no page has more than 3 wrong among its first 20 rows" , not over_all, over_all)
        T.NOTES.append("wrong-in-first-20 per page (text rule, not the parser): " + ", ".join("%s %d" % (k[3:], len(per[k][2])) for k in keys if per[k][2]) + " (all other pages 0)")
        T.NOTES.append("the 30 seeded pages: " + ", ".join(k[3:] for k in seed30))
        # precision and recall against the text rule over every card's text (information, not a bar)
        pr = []
        for key in keys:
            rx = re.compile(RX[key[3:]], re.I)
            mem = members(key)
            hit = {o for o in mem if rx.search(cards[o].get("t") or "")}
            pr.append("%s %.0f%%" % (key[3:], 100 * len(hit) / max(1, len(mem))))
        T.NOTES.append("share of each page's cards whose text fits its text rule anywhere: " + ", ".join(pr))
    finally:
        s.close()
    json.dump(reads, open(reads_out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    # ------------------------------------------------------------ 5. 390 px
    s, ok = TF.boot(DIRS["ab"], 390)
    c = s.c
    try:
        m0 = s.mark()
        for key in ("ab:trig.attacks", "ab:act.loyalty", "ab:stat.cost-reduce", "ab:repl.etb-tapped"):
            oko = wait_page(c, key, 120); c.pump(0.8)
            w = jx(c, "{sw:document.documentElement.scrollWidth, iw:window.innerWidth, lines:document.querySelectorAll('#list .aptile, #list .apline').length, h1:(document.querySelector('.thead h1')||{}).textContent}")
            check("390 px %s: page opens, rows carry a line, nothing scrolls sideways" % key, oko and w["lines"] > 0 and w["sw"] <= w["iw"], w)
        c.js("document.querySelector('.fsum[data-f=fold]').click()"); c.pump(0.5)
        fb = jx(c, "{sels:[...document.querySelectorAll('select[data-f=ab]')].map(s=>{const r=s.getBoundingClientRect();return [r.left>=0, r.right<=window.innerWidth, r.height]}), sw:document.documentElement.scrollWidth, iw:window.innerWidth}")
        check("390 px: the Trigger, Cost and Kind selects fit the screen and are 36 px or taller", len(fb["sels"]) == 3 and all(x[0] and x[1] and x[2] >= 36 for x in fb["sels"]) and fb["sw"] <= fb["iw"], fb)
        bad = [r for r in s.net(m0) if r["url"].startswith(s.base()) and (r["failed"] or (r["status"] or 0) >= 400)]
        con = [x for x in s.console(m0) if not re.search(r"cards\.scryfall\.io", x)]
        check("390 px run: no failed request, no console error", not bad and not con, (bad[:2], con[:2]))
    finally:
        s.close()

    # ------------------------------------------------------------ 6. first load and timing
    if not skip_perf:
        perf = {}
        for label, root in (("off", DIRS["off"]), ("on", DIRS["ab"])):
            for cpu in (1, 4):
                runs_ = []
                for rep in range(3):
                    s = T.Session(root, "/reports/browse.html", 1280, gz=True, cpu=cpu)
                    try:
                        s.c.wait(TF.READY.replace(" && typeof TF !== 'undefined'", ""), 400)
                        tboot = time.time() - s.t0
                        s.c.pump(2)
                        net = [r for r in s.net() if r["url"].startswith(s.base())]
                        a_ = s.c.js("performance.now()")
                        s.c.js("show('l:ab2d4667c5')"); s.c.wait("selected==='l:ab2d4667c5' && !document.getElementById('panel').classList.contains('tpend') && !!document.querySelector('#list [data-oid]')", 120)
                        topen = (s.c.js("performance.now()") - a_) / 1000
                        runs_.append((tboot, len(net), sum(r["bytes"] or 0 for r in net), topen))
                    finally:
                        s.close()
                perf[(label, cpu)] = tuple(statistics.median(x[i] for x in runs_) for i in range(4))
        for cpu in (1, 4):
            o, n = perf[("off", cpu)], perf[("on", cpu)]
            T.NOTES.append("first load at %dx CPU (median of 3, gzip server): flags off %.2f s to ready, %d requests, %s bytes on the wire; flags on %.2f s, %d requests, %s bytes; open a group page: %.2f s off, %.2f s on" %
                           (cpu, o[0], o[1], format(int(o[2]), ","), n[0], n[1], format(int(n[2]), ","), o[3], n[3]))
        check("first load: flags on adds only the 2 small page files at boot (requests %d -> %d)" % (perf[("off", 1)][1], perf[("on", 1)][1]), perf[("on", 1)][1] - perf[("off", 1)][1] == 2)

    # ------------------------------------------------------------ done
    after = dict(T.protected()); after.update(extra_protected())
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    check("protected files byte-identical before and after (%d hashed: corrections/ incl. backups, archive/, the shared JS, serve.py, top-level build files, chunks)" % len(before), not changed, changed[:5])
    cleanup()
    print("\n%d checks, %d failed" % (len(T.RESULTS), len([r for r in T.RESULTS if not r[1]])))
    for n in T.NOTES:
        print("NOTE", n)
    sys.exit(1 if any(not r[1] for r in T.RESULTS) else 0)


if __name__ == "__main__":
    main()
