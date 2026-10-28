#!/usr/bin/env python3
"""Verify the three tester flags in reports/config.js: DEFAULT_POPULARITY ("Most popular first" is the default sort, "Best match" is relabelled "Default order"), ACTIVE_GROUP_HIGHLIGHT (the open group stays
marked in the search results and the tree) and QUERY_MATCH_BLOCK (a group opened from a description match lists the cards whose own ability line has the query's words). Headless Edge over the DevTools
protocol on exported dist folders served by a plain static server (GET only).

    python src/test_tester_popularity.py [--skip-perf] [--reads OUT.json]

What is checked, and what is independent of the page's own code:
  * exports: flags on, twice, byte-identical; flags off (the other four flags stay on): same file list and every file byte-identical to the export saved in src/testdata/before_popularity/ except tester.js,
    testerfilters.js, config.js and the manifest; flags on adds no file. The flags-off page, run beside the saved pre-change scripts, draws the same DOM and makes the same requests after the same steps.
  * order: the displayed order of 8 pages (large, middle, small, merged, tentative, loose; each section of a page) re-derived from the Scryfall oracle file's edhrec_rank (a different source from the
    manual_index.json the page reads); manual_index.json's rank equals Scryfall's for every card both hold. "Default order", "Mana value" and "Name" give the flags-off order. Filters, narrowing chips and
    counts do not move with the sort. The choice is remembered (and a blocked localStorage is harmless). "Might also fit" keeps its score order until a sort is chosen.
  * highlight: DOM states after click-away (blur and a click elsewhere), scrolling, a new query, a merged page opened from a member's row, a deep link, the card pin, another group, a card page, 390 px.
  * block: 20 queries drawn with seed %(SEED_Q)d from a pool fixed in the code below before anything was computed (words and 2-3 word phrases of the group descriptions); each opened through the UI by a DOM
    click on the first description-match row. The page's count is compared with a Python re-implementation of the match rule, each shown card is checked against Scryfall's oracle text (a different source),
    and the popularity order of the rows is checked. The 20 blocks are then written to --reads for reading from the card text; my own reading of them is NOT independent. Bar: more than 4 of 20 not sensible
    means tighten (borderlines are reported apart).
  * first load: size, time and request counts at 1x and 4x CPU, flags off against flags on; the deep-link first row; and whether cards.json and members.json are requested twice with the cache ON.
Clicks are DOM click() calls and the search box is typed with key events: no touch, no other browser. Protected files (corrections/ incl. backups, archive/, the shared JS, serve.py, top-level build files)
are hashed before and after; nothing here writes to them. Exports go to dist.pop/, dist.pop2/, dist.popoff/, dist.popold/, which are removed; dist/ is left as the flags-on export at the end.
"""
import gzip
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_tester_static as T            # noqa: E402

check = T.check
SEED_Q = 20263501                          # fixed before any query was tried
BEFORE = os.path.join(HERE, "src", "testdata", "before_popularity")
READY = ("document.body.classList.contains('tester') && typeof HG !== 'undefined' && !!HG && !!SIB && !!SC && !!MI && !!CARDS && !!UNORG && !!LOOSE && !!TENT && !!TAGS && !!ANN && GSON === true && PINON === true && !!MERGED"
         " && typeof TF !== 'undefined'")
DIRS = {k: os.path.join(HERE, "dist." + k) for k in ("pop", "pop2", "popoff", "popold")}
FLAGS = ("DEFAULT_POPULARITY", "ACTIVE_GROUP_HIGHLIGHT", "QUERY_MATCH_BLOCK")
STOP = set("a an the of to and or for in on at by with from your you it its that this is are be as".split())
SECTIONS = ("(()=>{const out=[];let cur=[];for(const it of LIST){if(typeof it==='string'){if(cur.length)out.push(cur);cur=[];}else{const o=itemOid(it);if(o)cur.push(o);}}if(cur.length)out.push(cur);return out;})()")


def jx(c, expr):
    return json.loads(c.js("JSON.stringify(" + expr + ")"))


def boot(root, path="/reports/browse.html", width=1280, **kw):
    s = T.Session(root, path, width, **kw)
    ok = s.c.wait(READY, 300)
    s.c.pump(1.5)
    return s, ok


def cleanup():
    for d in DIRS.values():
        shutil.rmtree(d, ignore_errors=True)


def export_to(out, config=None):
    cmd = [sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--out", os.path.relpath(out, HERE)] + (["--config", config] if config else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    return r.returncode, r.stdout + r.stderr


def files_of(root):
    return {os.path.relpath(p, root).replace("\\", "/"): T.sha(p) for p in T.walk(root)}


ABILITY_FLAGS = ("ABILITY_TYPE_PAGES", "ABILITY_TYPE_FILTERS")      # the ability-type pages and filters (src/test_ability_pages.py tests them); this file tests the page without them, as it was


def ability_off_config():
    """reports/config.js as it is, with only the two ability-type flags switched off (the 'flags on' arm of this file: its own flags on, the later ones off)."""
    import tempfile
    txt = open(os.path.join(HERE, "reports", "config.js"), encoding="utf-8").read()
    for f in ABILITY_FLAGS:
        txt = re.sub(r"\b%s\s*:\s*true" % f, "%s: false" % f, txt)
    t = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8"); t.write(txt); t.close()
    return t.name


def flags_off_cfg():
    txt = open(os.path.join(HERE, "reports", "config.js"), encoding="utf-8").read()
    for f in FLAGS + ABILITY_FLAGS:
        txt = re.sub(r"\b%s\s*:\s*true" % f, "%s: false" % f, txt)
    import tempfile
    t = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8"); t.write(txt); t.close()
    return t.name


def wait_page(c, key, secs=90, bar=True):
    c.js("show(%s)" % json.dumps(key))
    return c.wait("selected===%s && !document.getElementById('panel').classList.contains('tpend') && !!document.querySelector('#list [data-oid]')" % json.dumps(key) + (" && !!document.getElementById('fwrap') && TF.full().length > 0" if bar else ""), secs)


def pick_sort(c, v, sel="#fwrap select[data-f=sort]"):
    c.js("(()=>{const s=document.querySelector(%s);s.value=%s;s.dispatchEvent(new Event('change',{bubbles:true}))})()" % (json.dumps(sel), json.dumps(v)))
    c.pump(0.7)


# ---------------------------------------------------------------- independent source: Scryfall's oracle file
SCRY = {}


def scry():
    if SCRY:
        return SCRY
    with gzip.open(os.path.join(HERE, "data", "scryfall-oracle-cards.jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip().rstrip(",")
            if line.startswith("{"):
                o = json.loads(line)
                faces = o.get("card_faces") or []
                txt = o.get("oracle_text") or " ".join((x.get("oracle_text") or "") for x in faces)
                SCRY[o["oracle_id"]] = (o.get("edhrec_rank"), txt)
    return SCRY


def norm(x):
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"['’]", "", x.lower())).strip()


def stem(w):
    n = len(w)
    if n > 4 and w.endswith("ies"): return w[:-3] + "y"
    if n > 4 and re.search(r"(ss|x|z|ch|sh)es$", w): return w[:-2]
    if n > 3 and w.endswith("s") and not re.search(r"(ss|us|is)$", w): return w[:-1]
    return w


def variants(w):
    s = stem(w); v = [s]
    if len(s) > 5 and s.endswith("ing"): v.append(s[:-3])
    elif len(s) > 4 and s.endswith("ed"): v.append(s[:-2])
    return v


def py_match(line, q):
    """The match rule, written again in Python: stop words dropped, each word by stem, in order, span <= typed words + 3."""
    words = norm(q).split()
    core = [w for w in words if w not in STOP] or words
    toks = [re.sub(r"[^a-z0-9]", "", m.group(0).lower().replace("'", "").replace("’", "")) for m in re.finditer(r"[A-Za-z0-9’']+", line)]
    toks = [t for t in toks if t]
    terms = [(w, variants(w)) for w in core]
    hit = lambda t, term: t == term[0] or stem(t) in term[1]
    best = None
    for i, t in enumerate(toks):
        if not hit(t, terms[0]): continue
        at, ok = i, True
        for term in terms[1:]:
            f = next((x for x in range(at + 1, len(toks)) if hit(toks[x], term)), -1)
            if f < 0: ok = False; break
            at = f
        if ok and at - i + 1 <= len(words) + 3: best = True; break
    return bool(best)


def sort_key(rank, name, oid):
    return (rank is None, rank or 0, name.lower(), oid)


# ---------------------------------------------------------------- the query pool, fixed before any query was tried
def query_pool():
    doc = json.load(open(os.path.join(HERE, "dist", "build", "group_search", "index.json"), encoding="utf-8"))
    single, phrase = {}, {}
    for g in doc["groups"]:
        desc = g[7] or ""
        toks = norm(desc).split()
        gid = g[0]
        for t in set(toks):
            if len(t) >= 4 and t.isalpha() and t not in STOP:
                single.setdefault(stem(t), set()).add(gid)
        for n in (2, 3):
            for i in range(len(toks) - n + 1):
                w = toks[i:i + n]
                if w[0] in STOP or w[-1] in STOP or not all(x.isalpha() for x in w):
                    continue
                phrase.setdefault(" ".join(w), set()).add(gid)
    s = sorted(k for k, v in single.items() if len(v) >= 3)
    p = sorted(k for k, v in phrase.items() if len(v) >= 2)
    rng = random.Random(SEED_Q)
    rng.shuffle(s); rng.shuffle(p)
    return s, p


def main():
    skip_perf = "--skip-perf" in sys.argv
    reads_out = sys.argv[sys.argv.index("--reads") + 1] if "--reads" in sys.argv else os.path.join(os.environ.get("TEMP", "."), "query_blocks_reads.json")
    before = T.protected()
    cleanup()
    # ------------------------------------------------------------ 1. exports
    rc, out = export_to(DIRS["pop"], ability_off_config()); check("export (flags on) succeeds", rc == 0, out[-300:])
    rc, out = export_to(DIRS["pop2"], ability_off_config()); check("export (flags on), again, succeeds", rc == 0, out[-300:])
    a, b = files_of(DIRS["pop"]), files_of(DIRS["pop2"])
    check("two flags-on exports: every file byte-identical (%d files)" % len(a), a == b, [k for k in set(a) | set(b) if a.get(k) != b.get(k)][:4])
    shutil.rmtree(DIRS["pop2"])
    off_cfg = flags_off_cfg()
    rc, out = export_to(DIRS["popoff"], off_cfg); check("export (three flags off) succeeds", rc == 0, out[-300:])
    base = {f["path"]: f["sha256"] for f in json.load(open(os.path.join(BEFORE, "dist_manifest_before.json"), encoding="utf-8"))["files"]}
    offf = files_of(DIRS["popoff"])
    base_all = dict(base); base_all["manifest.json"] = None
    check("flags off: the file list is exactly the one before the flags (%d files)" % len(offf), set(offf) == set(base_all), sorted(set(offf) ^ set(base_all))[:5])
    differ = sorted(k for k in base if offf.get(k) != base[k])
    check("flags off: every file is byte-identical to the pre-change export except tester.js, testerfilters.js and config.js %s" % differ, differ == ["reports/config.js", "reports/tester.js", "reports/testerfilters.js"], differ)
    check("flags on adds no file", sorted(set(a) - set(offf)) == [], sorted(set(a) - set(offf)))
    other = sorted(k for k in offf if k in a and offf[k] != a[k] and k != "manifest.json")
    check("flags on, against flags off, changes no file but config.js %s (the scripts are the same files)" % other, other == ["reports/config.js"], other)
    css = [k for k in a if k.endswith(".css") and a[k] != offf.get(k)]
    check("no stylesheet differs (the new rules are added by the script, only while a flag is on)", not css, css)
    rcc = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--check", "--config", ability_off_config(), "--out", os.path.relpath(DIRS["pop"], HERE)], capture_output=True, text=True, cwd=HERE)
    check("export_static.py --check passes on the flags-on export", rcc.returncode == 0, rcc.stdout + rcc.stderr)
    blob = " ".join(open(os.path.join(DIRS["pop"], "reports", n), encoding="utf-8").read() for n in ("tester.js", "testerfilters.js"))
    old_blob = " ".join(open(os.path.join(BEFORE, n), encoding="utf-8").read() for n in ("tester.js", "testerfilters.js"))
    pat = r"corrections/|backups|archive|manual_placements|/api/"
    check("the scripts name no more private paths than before (%d mentions, %d before; existing comments only)" % (len(re.findall(pat, blob)), len(re.findall(pat, old_blob))), len(re.findall(pat, blob)) <= len(re.findall(pat, old_blob)))
    t = json.load(open(os.path.join(DIRS["pop"], "build", "ability_taxonomy.json"), encoding="utf-8"))["totals"]
    ten = json.load(open(os.path.join(DIRS["pop"], "build", "tentative_placements.json"), encoding="utf-8"))["meta"]["headline"]
    ann = json.load(open(os.path.join(DIRS["pop"], "build", "annotation_placements.json"), encoding="utf-8"))["meta"]["headline"]
    tag = json.load(open(os.path.join(DIRS["pop"], "build", "tag_placements.json"), encoding="utf-8"))["meta"]["headline"]
    got = [t["headline"]["pct"], t["with_broad"]["pct"], ten["with_tentative"][1], ann["with_annotation"][1], ann["with_gap_stratum"][1], tag["with_tag"][1]]
    check("the six figures are unchanged %s" % got, got == T.FIGURES)

    # ------------------------------------------------------------ 2. flags off: the same page as before (current scripts vs the saved pre-change scripts)
    shutil.copytree(DIRS["popoff"], DIRS["popold"])
    for n in ("tester.js", "testerfilters.js"):
        shutil.copyfile(os.path.join(BEFORE, n), os.path.join(DIRS["popold"], "reports", n))
    runs, off_orders = {}, {}
    for label, root in (("now", DIRS["popoff"]), ("before", DIRS["popold"])):
        s, ok = boot(root)
        c = s.c
        try:
            check("flags off (%s scripts): page boots" % label, ok)
            ids = jx(c, "(()=>{const L=Object.entries(TAX.leaves).filter(([id,l])=>!l.flags.length&&memOids(id).length>25&&memOids(id).length<400);return [L[0][0],L[7][0]]})()")
            snaps = []
            snap = "(()=>{const g=id=>{const e=document.getElementById(id);return e?e.innerHTML:''};return [g('panel'),g('tree'),g('findres')].join('\\n=====\\n')})()"

            def take():
                c.pump(0.6); snaps.append(c.js(snap))
            wait_page(c, "l:" + ids[0]); take()
            c.js("document.querySelector('[data-f=col][data-v=U]') && document.querySelector('[data-f=col][data-v=U]').click()"); take()
            c.js("document.querySelector('[data-f=type][data-v=Creature]') && document.querySelector('[data-f=type][data-v=Creature]').click()"); take()
            c.js("document.querySelector('[data-f=clear]') && document.querySelector('[data-f=clear]').click()")
            wait_page(c, "l:" + ids[1]); take()
            dk = c.js("MERGED.pageBy['draw-cards'].key")
            wait_page(c, dk); take()
            c.js("document.querySelector('#list .tile').click()"); c.wait("document.querySelector('.tmodal:not([hidden]) .toracle')", 60); c.pump(0.8)
            snaps.append(c.js("document.querySelector('.tmodal').innerHTML")); c.key("Escape"); c.pump(0.3)
            c.js("document.getElementById('q').focus()"); c.type("untap target")
            c.wait("document.querySelectorAll('#findres .gr').length > 0", 90); c.pump(1.5); take()
            c.js("[...document.querySelectorAll('#findres .gr')].find(e=>/description/.test(e.textContent)).click()")
            c.wait("!document.getElementById('panel').classList.contains('tpend') && !!document.querySelector('#list [data-oid]')", 60); c.pump(1.5); take()
            c.js("document.querySelector('.sclr').click()"); c.pump(0.4)
            c.js("document.querySelector('#tree .row[data-k^=\"f:\"]').click()"); take()
            # the orders under the three old sorts, on the pages used below (flags-off reference for the new "Default order", "Mana value" and "Name")
            if label == "now":
                for key in ORDER_KEYS(c):
                    wait_page(c, key)
                    for v in ("best", "mv", "name"):
                        pick_sort(c, v)
                        off_orders[(key, v)] = jx(c, SECTIONS)
                    pick_sort(c, "best")
            reqs = sorted(r["url"].replace(s.base(), "") for r in s.net() if r["url"].startswith(s.base()))
            bad = [r for r in s.net() if r["url"].startswith(s.base()) and (r["failed"] or (r["status"] or 0) >= 400)]
            runs[label] = (snaps, reqs, bad, [x for x in s.console() if not re.search(r"cards\.scryfall\.io", x)])
        finally:
            s.close()
    sn, sb = runs["now"][0], runs["before"][0]
    check("flags off: the DOM after %d identical steps (page, filters, merged page, card dialog, search, a description-match click, tree) is identical to the page with the pre-change scripts" % len(sn), sn == sb, [i for i in range(min(len(sn), len(sb))) if sn[i] != sb[i]])
    check("flags off: the requests are identical to the pre-change page (%d requests)" % len(runs["now"][1]), runs["now"][1] == runs["before"][1], sorted(set(runs["now"][1]) ^ set(runs["before"][1]))[:5])
    check("flags off: no failed request, no console error", not runs["now"][2] and not runs["now"][3], (runs["now"][2][:2], runs["now"][3][:2]))
    check("flags off: no highlight class, no block, no new attribute in the DOM", not any(re.search(r'class="[^"]*\bcur\b|qmwrap|data-why|data-pop-note', x) for x in sn))

    # ------------------------------------------------------------ 3. popularity
    S = scry()
    s, ok = boot(DIRS["pop"])
    c = s.c
    reads = {"order_pages": []}
    try:
        check("flags on: page boots", ok)
        mi = jx(c, "Object.fromEntries(Object.entries(MI.cards).map(([o,v])=>[o,v[4]]))")
        diff = [o for o, r in mi.items() if o in S and S[o][0] != r]
        check("manual_index.json's rank equals Scryfall's edhrec_rank for every card both hold (%d cards, %d not in the Scryfall file)" % (sum(1 for o in mi if o in S), sum(1 for o in mi if o not in S)), not diff, diff[:3])
        check("%d of %d cards ranked, %d unranked" % (sum(1 for v in mi.values() if v is not None), len(mi), sum(1 for v in mi.values() if v is None)), True)
        keys = ORDER_KEYS(c)
        check("order pages drawn: %d" % len(keys), len(keys) == 8, keys)
        names = jx(c, "Object.fromEntries(Object.entries(CARDS).map(([o,v])=>[o,v.n]))")
        for key in keys:
            ok = wait_page(c, key)
            sel = jx(c, "[...document.querySelectorAll('select[data-f=sort] option')].map(o=>[o.value,o.textContent,o.selected])")
            lab = [x[1] for x in sel]
            if key == keys[0]:
                check("sort choices are Most popular first, Default order, Mana value, Name; the default is Most popular first", lab == ["Most popular first", "Default order", "Mana value", "Name"] and [x[0] for x in sel if x[2]] == ["pop"], sel)
                check("one line says what the rank measures", c.js("!!document.querySelector('#fwrap [data-pop-note]') && /EDHREC rank/.test(document.querySelector('#fwrap [data-pop-note]').textContent) && /no rank come last/.test(document.querySelector('#fwrap [data-pop-note]').textContent)"))
            secs = jx(c, SECTIONS)
            exp = [sorted(sec, key=lambda o: sort_key(S[o][0] if o in S else None, names[o], o)) for sec in secs]
            check("order by Scryfall's rank, unranked last, ties by name then id: %s (%d cards, %d sections)" % (key, sum(map(len, secs)), len(secs)), secs == exp, [i for i, (x, y) in enumerate(zip(secs, exp)) if x != y][:2])
            dom = jx(c, "[...document.querySelectorAll('#list [data-oid]')].map(e=>e.dataset.oid).slice(0,30)")
            flat = [o for sec in secs for o in sec]
            check("the cards drawn (first %d) are the first of that order: %s" % (len(dom), key), dom == flat[:len(dom)])
            unr = [o for o in flat if (S[o][0] if o in S else None) is None]
            if unr:
                for sec in secs:
                    ix = [i for i, o in enumerate(sec) if (S[o][0] if o in S else None) is None]
                    if ix and ix != list(range(len(sec) - len(ix), len(sec))):
                        check("unranked cards come last in every section: %s" % key, False); break
                else:
                    check("unranked cards come last in every section: %s (%d unranked here)" % (key, len(unr)), True)
            reads["order_pages"].append(key)
            for v in ("best", "mv", "name"):
                pick_sort(c, v)
                got = jx(c, SECTIONS)
                check("sort %s equals the flags-off order: %s" % (v, key), got == off_orders.get((key, v)), (len(got), len(off_orders.get((key, v), []))))
            pick_sort(c, "pop")
        # remembered, across pages and a reload; localStorage blocked
        wait_page(c, keys[1]); pick_sort(c, "name")
        wait_page(c, keys[2])
        check("a chosen sort is remembered on the next page", c.js("document.querySelector('#fwrap select[data-f=sort]').value") == "name")
        c.call("Page.reload"); ok = c.wait(READY, 300); c.pump(1)
        wait_page(c, keys[2])
        check("... and after a reload", c.js("document.querySelector('#fwrap select[data-f=sort]').value") == "name")
        c.js("localStorage.removeItem('sortPref')")
        c.call("Page.reload"); c.wait(READY, 300); c.pump(1); wait_page(c, keys[2])
        check("with nothing stored the default is Most popular first", c.js("document.querySelector('#fwrap select[data-f=sort]').value") == "pop")
        # filters and narrowing: independent of the sort
        wait_page(c, keys[1])
        pick_sort(c, "pop")
        c.js("document.querySelector('[data-f=col][data-v=U]').click()"); c.pump(0.5)
        c.js("document.querySelector('[data-f=type][data-v=Creature]') && document.querySelector('[data-f=type][data-v=Creature]').click()"); c.pump(0.5)
        chips1, shown1 = jx(c, "TF.chips()"), jx(c, "TF.shown()")
        pick_sort(c, "name")
        chips2, shown2 = jx(c, "TF.chips()"), jx(c, "TF.shown()")
        check("with a colour and a type filter on: the same cards, the same narrowing chips and counts under both sorts (%d cards, %d chips)" % (len(shown1), len(chips1)), sorted(shown1) == sorted(shown2) and chips1 == chips2)
        pick_sort(c, "pop")
        secs = jx(c, SECTIONS)
        check("... and the filtered list is in rank order", secs == [sorted(sec, key=lambda o: sort_key(S[o][0] if o in S else None, names[o], o)) for sec in secs])
        c.js("document.querySelector('[data-f=clear]').click()"); c.pump(0.4)
        # merged page: sections kept
        dk = c.js("MERGED.pageBy['draw-cards'].key")
        wait_page(c, dk)
        check("a merged page keeps its sections and sorts inside each", jx(c, "LIST.filter(x=>typeof x==='string' && x.includes('id=\"msec-')).length") >= 2)
        # Might also fit: score order until a sort is chosen; an explicit choice applies to both tabs
        c.js("localStorage.removeItem('sortPref')")
        gid = jx(c, "(()=>{for (const [lid,l] of Object.entries(TAX.leaves)){ const g='leaf:'+lid; if (MI.groups[g] && MI.groups[g][4] && Suggested.count(SC,g,SCFLOOR,SCINC)>=25 && memOids(lid).length>=25 && memOids(lid).length<300) return lid; } return null})()")
        if gid:
            c.call("Page.reload"); c.wait(READY, 300); c.pump(1)
            wait_page(c, "l:" + gid)
            c.js("scSetTab('matches')"); c.wait("document.querySelectorAll('#suggsec .sgrow').length > 0", 60); c.pump(0.8)
            sel0 = c.js("document.querySelector('#fwrap2 select[data-f=sort]').value")
            rows0 = jx(c, "[...document.querySelectorAll('#suggsec .sgrow')].map(e=>e.dataset.oid)")
            check("Might also fit opens on Default order (its score order), not popularity (select = %s)" % sel0, sel0 == "best")
            pick_sort(c, "pop", "#fwrap2 select[data-f=sort]")
            c.wait("document.querySelectorAll('#suggsec .sgrow').length > 0", 30); c.pump(0.5)
            rows1 = jx(c, "[...document.querySelectorAll('#suggsec .sgrow')].map(e=>e.dataset.oid)")
            ref = [o for o in rows1]
            full = jx(c, "TF.sugg ? 1 : 0")
            check("a chosen Most popular first re-orders Might also fit by rank (%d rows shown)" % len(rows1), len(rows1) > 3 and all(sort_key(S[x][0] if x in S else None, names[x], x) <= sort_key(S[y][0] if y in S else None, names[y], y) for x, y in zip(rows1, rows1[1:])) and full == 1)
            c.js("scSetTab('members')"); c.pump(1)
            check("the choice applies to the Cards tab too", c.js("document.querySelector('#fwrap select[data-f=sort]').value") == "pop")
            c.js("localStorage.removeItem('sortPref')")
        else:
            check("a group with suggestions was found for the Might also fit test", False)
        check("no console error so far", not s.console(), s.console()[:3])
    finally:
        s.close()
    # storage blocked
    s, ok = boot(DIRS["pop"])
    try:
        s.c.call("Page.addScriptToEvaluateOnNewDocument", source="Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})")
        s.c.call("Page.reload"); ok = s.c.wait(READY, 300); s.c.pump(1)
        k = ORDER_KEYS(s.c)[1]
        wait_page(s.c, k); pick_sort(s.c, "name")
        wait_page(s.c, ORDER_KEYS(s.c)[2])
        check("localStorage blocked: the page works, the choice lasts for the page only, no console error", ok and s.c.js("document.querySelector('#fwrap select[data-f=sort]').value") in ("name", "pop") and not [x for x in s.console() if "blocked" in x and "exception" in x], s.console()[:3])
    finally:
        s.close()

    # ------------------------------------------------------------ 4. highlight
    s, ok = boot(DIRS["pop"])
    c = s.c
    try:
        cur = lambda: jx(c, "[...document.querySelectorAll('.cur')].map(e=>[e.closest('#findres')?'res':e.closest('#tree')?'tree':'?',e.dataset.go||e.dataset.k,e.getAttribute('aria-current')])")
        c.js("document.getElementById('q').focus()"); c.type("untap target")
        c.wait("document.querySelectorAll('#findres .gr').length > 0", 90); c.pump(1)
        check("before anything opens, no row is marked", cur() == [])
        key = c.js("[...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.why==='description').dataset.go")
        c.js("[...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.why==='description').click()")
        c.wait("selected===%s && !!document.querySelector('#list [data-oid]')" % json.dumps(key), 60); c.pump(1)
        st = cur()
        check("a result row and a tree row are marked for the open group (aria-current) %s" % st, sorted(x[0] for x in st) == ["res", "tree"] and all(x[1] == key and x[2] == "true" for x in st))
        c.js("document.activeElement && document.activeElement.blur()"); c.pump(0.3)
        check("still marked after the row lost focus", len(cur()) == 2)
        c.js("document.getElementById('panel').click(); document.body.click()"); c.pump(0.3)
        check("still marked after a click elsewhere", len(cur()) == 2)
        c.js("window.scrollTo(0, 600); document.getElementById('panel').scrollTop = 600; document.getElementById('list').scrollIntoView(); window.scrollTo(0, 0)"); c.pump(0.3)
        check("still marked after scrolling", len(cur()) == 2)
        check("the mark does not depend on focus or hover: the tree row's class and the result's class are set on the element", c.js("document.querySelector('#findres .gr.cur') !== document.activeElement"))
        c.js("document.getElementById('q').focus()"); c.js("document.getElementById('q').select()"); c.type("untap")
        c.wait("document.querySelectorAll('#findres .gr').length > 0", 90); c.pump(1.2)
        res = [x for x in cur() if x[0] == "res"]
        inres = c.js("!![...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.go===%s)" % json.dumps(key))
        check("after a new query the open group is marked again wherever it is in the results (in results: %s)" % inres, (len(res) == 1) == inres and len([x for x in cur() if x[0] == "tree"]) == 1)
        # another group opens: the mark moves
        other = c.js("[...document.querySelectorAll('#tree .row[data-k^=\"l:\"]')].map(e=>e.dataset.k).find(k=>k!==%s)" % json.dumps(key))
        c.js("document.querySelector('#tree .row[data-k=%s]').click()" % json.dumps(other))
        c.wait("selected===%s" % json.dumps(other), 60); c.pump(1)
        st = cur()
        check("another group opens: the mark moves to it and only it %s" % st, st and all(x[1] == other for x in st) and not [x for x in st if x[0] == "res" and x[1] == key])
        # a non-group page clears the group rows
        c.js("document.querySelector('#tree .row[data-k^=\"f:\"]').click()"); c.pump(1)
        c.js("show(document.querySelector('#tree .row[data-k^=\"f:\"]').dataset.k)"); c.pump(1.5)
        st = cur()
        check("a family overview opens: no leaf row is marked, only its own tree row %s" % [x[:2] for x in st], all(x[0] == "tree" and x[1].startswith("f:") for x in st) and not [x for x in st if x[1].startswith("l:")])
        # merged page, opened from a result row that belongs to it
        found = None
        for mp in jx(c, "MERGED.pages.filter(p=>p.members.length>=2).slice(0,12)"):
            for m in mp["members"]:
                if m["layer"] != "leaf":
                    continue
                nm = c.js("TAX.leaves[%s].name" % json.dumps(m["gid"].split(":", 1)[1]))
                c.js("document.getElementById('q').focus(); document.getElementById('q').select()"); c.type(re.sub(r"\(.*", "", nm).strip())
                c.pump(1.6)
                k = c.js("(()=>{const e=[...document.querySelectorAll('#findres .gr')].find(e=>MERGED.redirects[e.dataset.go]===%s);return e?e.dataset.go:null})()" % json.dumps(mp["slug"]))
                if k:
                    found = (mp, k); break
            if found:
                break
        if found:
            mp, k = found
            c.js("[...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.go===%s).click()" % json.dumps(k))
            c.wait("!!document.querySelector('#list [data-oid]') && !!MERGED.redirects[selected]", 60); c.pump(1.2)
            st = cur()
            check("merged page '%s' opened from a result row of it: a result row and the page's tree rows are marked %s" % (mp["name"], [x[:2] for x in st][:4]), any(x[0] == "res" and x[1] == k for x in st) and any(x[0] == "tree" for x in st))
            check("... and every marked row belongs to that merged page", all(jx(c, "MERGED.redirects[%s]" % json.dumps(x[1])) == mp["slug"] for x in st))
        else:
            check("a result row belonging to a merged page was found by searching member names", False)
        # card pin
        c.js("document.getElementById('q').focus(); document.getElementById('q').select()"); c.type("Maze of Ith")
        c.wait("document.querySelectorAll('#findres .fr[data-go^=\"pin:\"]').length > 0", 90); c.pump(1)
        c.js("document.querySelector('#findres .fr[data-go^=\"pin:\"]').click()")
        c.wait("!!document.querySelector('#pinwrap') && !!document.querySelector('.pinhit')", 60); c.pump(1)
        st = cur()
        check("card pin: the group the card opened in is marked in the tree, and the card is pinned at its top %s" % [x[:2] for x in st][:3], any(x[0] == "tree" for x in st) and c.js("!!document.querySelector('#pinwrap')"))
        check("no console error, no failed request", not s.console() and not [r for r in s.net() if r["failed"] or (r["status"] or 0) >= 400], s.console()[:3])
    finally:
        s.close()
    # deep link
    lid = None
    s0, ok0 = boot(DIRS["pop"]); lid = s0.c.js("Object.entries(TAX.leaves).filter(([id,l])=>!l.flags.length&&memOids(id).length>30)[3][0]"); s0.close()
    s, ok = boot(DIRS["pop"], "/reports/browse.html#" + "l%3A" + lid)
    try:
        s.c.wait("!!document.querySelector('#list [data-oid]')", 90); s.c.pump(1)
        st = jx(s.c, "[...document.querySelectorAll('.cur')].map(e=>[e.dataset.go||e.dataset.k])")
        check("deep link: the tree row of the group is marked, nothing else, and there is no block", st == [["l:" + lid]] and s.c.js("!document.getElementById('qmwrap')"), st)
    finally:
        s.close()
    # 390 px
    s, ok = boot(DIRS["pop"], width=390)
    c = s.c
    try:
        c.js("document.getElementById('tmenu').click()"); c.pump(0.4)
        c.js("document.getElementById('q').focus()"); c.type("untap target")
        c.wait("document.querySelectorAll('#findres .gr').length > 0", 90); c.pump(1)
        key = c.js("[...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.why==='description').dataset.go")
        c.js("[...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.why==='description').click()")
        c.wait("selected===%s && !!document.querySelector('#list [data-oid]') && !!document.getElementById('qmwrap')" % json.dumps(key), 60); c.pump(1.2)
        check("390 px: the open group stays marked in the results and the tree", jx(c, "[...document.querySelectorAll('.cur')].length") == 2)
        check("390 px: block and sort bar draw without horizontal scroll (scrollWidth %s <= 390)" % c.js("document.documentElement.scrollWidth"), c.js("document.documentElement.scrollWidth") <= 391)
        r = jx(c, "(()=>{const b=document.querySelector('#qmwrap .qb');const s=document.querySelector('select[data-f=sort]');return [b?b.getBoundingClientRect().height:null, s?s.getBoundingClientRect().height:null]})()")
        check("390 px: Show more is a 44 px target %s" % r, r[0] is None or r[0] >= 43)
        check("390 px: no console error, no failed request", not s.console() and not [x for x in s.net() if x["failed"]], s.console()[:3])
    finally:
        s.close()

    # ------------------------------------------------------------ 5. the query-match block
    single, phrase = query_pool()
    print("pool: %d words, %d phrases" % (len(single), len(phrase)))
    results = []
    s, ok = boot(DIRS["pop"])
    c = s.c
    try:
        def run_query(q, kind):
            c.js("document.getElementById('q').focus(); document.getElementById('q').select()"); c.type(q)
            c.wait("document.getElementById('findres').innerText.length > 0 && !/Loading/.test(document.getElementById('findres').innerText)", 60); c.pump(1.3)
            desc = c.js("(()=>{const e=[...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.why==='description');return e?e.dataset.go:null})()")
            if not desc:
                return None
            nwhy = jx(c, "[...document.querySelectorAll('#findres .gr[data-why]')].reduce((a,e)=>{a[e.dataset.why]=(a[e.dataset.why]||0)+1;return a},{})")
            c.js("[...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.why==='description').click()")
            c.wait("selected===%s && !document.getElementById('panel').classList.contains('tpend') && !!document.querySelector('#list [data-oid]')" % json.dumps(desc), 60); c.pump(1.5)
            info = jx(c, """(()=>{const b=document.getElementById('qmwrap'); const g=GSIDX.byGid[[...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.why==='description').dataset.gid];
              const lineOf=it=>{ if(typeof it==='string') return ''; if(Array.isArray(it)){const c=CARDS[it[0]], a=it[1]!=null&&c&&c.ab[it[1]]; return a?a[0]||'':'';} const m=/<span class="why">([\\s\\S]*?)<\\/span>/.exec(it.html||''); return m?m[1].replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&amp;/g,'&'):''; };
              const lines=[]; const seen=new Set(); for(const it of TF.items()){ if(typeof it==='string') continue; const o=itemOid(it); if(!o||seen.has(o)) continue; seen.add(o); lines.push([o,lineOf(it)]); }
              return {group:g.name, layer:g.layer, desc:g.desc, key:selected, n_page:seen.size, hasBlock:!!b, none:!!(b&&b.classList.contains('qnone')), text:b?b.innerText:'',
                rows:b?[...b.querySelectorAll('.qr')].map(r=>({oid:r.querySelector('.nm').dataset.go.slice(2), name:r.querySelector('.nm').textContent, line:r.querySelector('.ln').textContent, marks:[...r.querySelectorAll('mark')].map(m=>m.textContent)})):[],
                more:!!(b&&b.querySelector('[data-qm=more]')), lines:lines, whys:null}})()""")
            info["whys"] = nwhy; info["q"] = q; info["kind"] = kind
            return info
        want = {"word": 10, "phrase": 10}
        got = {"word": [], "phrase": []}
        tried = []
        pools = {"word": list(single), "phrase": list(phrase)}
        for kind in ("word", "phrase"):
            while len(got[kind]) < want[kind] and pools[kind]:
                q = pools[kind].pop(0)
                tried.append((kind, q))
                r = run_query(q, kind)
                if r is None:
                    continue                               # no description-match group: the next draw (the rule fixed in advance)
                got[kind].append(r)
        results = got["word"] + got["phrase"]
        check("20 description-match queries drawn (%d words, %d phrases; %d draws tried, %d without a description match)" % (len(got["word"]), len(got["phrase"]), len(tried), len(tried) - 20), len(results) == 20)
        # independent checks, query by query
        bad_count, bad_oracle, bad_order, bad_hl, bad_cap = [], [], [], [], []
        for r in results:
            if not r["lines"] or not any(l for _, l in r["lines"]):
                r["supported"] = False; continue
            r["supported"] = True
            full = [o for o, l in r["lines"] if l and py_match(l, r["q"])]
            m = re.search(r"(\d[\d,]*) cards? match", r["text"])
            shown_n = int(m.group(1).replace(",", "")) if m else 0
            r["py_matches"] = len(full)
            if (len(full) > 0 and (not r["hasBlock"] or r["none"] or shown_n != len(full))) or (len(full) == 0 and not r["none"]):
                bad_count.append((r["q"], len(full), shown_n, r["hasBlock"]))
            qw = [w for w in norm(r["q"]).split() if w not in STOP] or norm(r["q"]).split()
            for row in r["rows"]:
                txt = norm(S[row["oid"]][1]) if row["oid"] in S else ""
                if row["oid"] in S and not all(any(t.startswith(stem(w)[:max(3, len(stem(w)) - 2)]) for t in txt.split()) for w in qw):
                    bad_oracle.append((r["q"], row["name"]))
                if not row["marks"]:
                    bad_hl.append((r["q"], row["name"]))
            ranks = [(S[x["oid"]][0] if x["oid"] in S else None, x["name"], x["oid"]) for x in r["rows"]]
            if [sort_key(*x) for x in ranks] != sorted(sort_key(*x) for x in ranks):
                bad_order.append(r["q"])
            if len(r["rows"]) > 10 or (len(full) > 10 and len(r["rows"]) != 10):
                bad_cap.append((r["q"], len(r["rows"]), len(full)))
        check("every page's block count equals a Python re-implementation of the rule over the same lines (%d supported pages)" % sum(1 for r in results if r["supported"]), not bad_count, bad_count[:3])
        check("every shown card has all the query's words (by prefix) in Scryfall's oracle text, a different source", not bad_oracle, bad_oracle[:3])
        check("every shown row has its matched words marked", not bad_hl, bad_hl[:3])
        check("rows are in popularity order (Scryfall's rank, unranked last)", not bad_order, bad_order[:3])
        check("at most 10 rows first; Show more is offered when more match", not bad_cap, bad_cap[:3])
        json.dump([{k: v for k, v in r.items() if k != "lines"} for r in results], open(reads_out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        nb = sum(1 for r in results if r["hasBlock"] and not r["none"]); ne = sum(1 for r in results if r["none"]); nu = sum(1 for r in results if not r["supported"])
        T.NOTES.append("20 blocks: %d with cards, %d with the empty line, %d on pages that show no ability line (nothing shown); reads written to %s" % (nb, ne, nu, reads_out))
        check("20 blocks written for reading from the card text: %d with cards, %d empty-line, %d unsupported page" % (nb, ne, nu), True)

        # ---- functional cases for the block
        def open_via(q, why, nth=0):
            c.js("document.getElementById('q').focus(); document.getElementById('q').select()"); c.type(q)
            c.wait("document.querySelectorAll('#findres .gr').length > 0", 90); c.pump(1.3)
            k = c.js("(()=>{const e=[...document.querySelectorAll('#findres .gr')].filter(e=>e.dataset.why===%s)[%d];return e?e.dataset.go:null})()" % (json.dumps(why), nth))
            if not k:
                return None
            c.js("[...document.querySelectorAll('#findres .gr')].filter(e=>e.dataset.why===%s)[%d].click()" % (json.dumps(why), nth))
            c.wait("selected===%s && !document.getElementById('panel').classList.contains('tpend') && !!document.querySelector('#list [data-oid]')" % json.dumps(k), 60); c.pump(1.2)
            return k
        k = open_via("untap target", "description")
        check("a description match opens its group with the block, wording 'These cards matched your query: untap target'", k and c.js("(document.getElementById('qmwrap')||{innerText:''}).innerText.startsWith('These cards matched your query: untap target')"))
        rows = c.js("document.querySelectorAll('#qmwrap .qr').length")
        check("cap: 10 rows, then Show more (%s rows)" % rows, rows == 10 and c.js("!!document.querySelector('#qmwrap [data-qm=more]')"))
        c.js("document.querySelector('#qmwrap [data-qm=more]').click()"); c.pump(0.8)
        check("Show more adds up to 20 and no more (%s rows, button gone, 'in the list below')" % c.js("document.querySelectorAll('#qmwrap .qr').length"), c.js("document.querySelectorAll('#qmwrap .qr').length") == 20 and c.js("!document.querySelector('#qmwrap [data-qm=more]') && /in the list below/.test(document.getElementById('qmwrap').innerText)"))
        n0 = c.js("+/(\\d+) cards? match/.exec(document.getElementById('qmwrap').innerText)[1]")
        c.js("document.querySelector('[data-f=col][data-v=U]') && document.querySelector('[data-f=col][data-v=U]').click()"); c.pump(0.9)
        n1 = c.js("(()=>{const m=/(\\d+) cards? match/.exec(document.getElementById('qmwrap')?document.getElementById('qmwrap').innerText:'');return m?+m[1]:0})()")
        shown = set(jx(c, "TF.shown()"))
        rows_o = jx(c, "[...document.querySelectorAll('#qmwrap .qr .nm')].map(e=>e.dataset.go.slice(2))")
        check("the block respects filters: a colour filter changes its count (%s to %s) and every row is in the filtered list" % (n0, n1), n1 <= n0 and all(o in shown for o in rows_o))
        c.js("document.querySelector('[data-f=clear]').click()"); c.pump(0.8)
        check("clearing the filters brings the count back (%s)" % n0, c.js("+/(\\d+) cards? match/.exec(document.getElementById('qmwrap').innerText)[1]") == n0)
        # a list sort does not move the block
        rows_before = jx(c, "[...document.querySelectorAll('#qmwrap .qr .nm')].map(e=>e.dataset.go.slice(2))")
        pick_sort(c, "name")
        check("the block stays in popularity order, whatever the list sort (%d rows)" % len(rows_before), jx(c, "[...document.querySelectorAll('#qmwrap .qr .nm')].map(e=>e.dataset.go.slice(2))") == rows_before)
        c.js("localStorage.removeItem('sortPref')")
        # the tab: hidden on Possible matches
        c.js("scSetTab('matches')"); c.pump(1)
        hid = c.js("document.getElementById('qmwrap') ? getComputedStyle(document.getElementById('qmwrap')).display : 'none'")
        check("the block is hidden on the Possible matches tab", hid == "none", hid)
        c.js("scSetTab('members')"); c.pump(0.5)
        # same group again from the tree keeps it; another group clears it
        other = c.js("[...document.querySelectorAll('#tree .row[data-k^=\"l:\"]')].map(e=>e.dataset.k).find(k=>k!==selected)")
        c.js("document.querySelector('#tree .row[data-k=%s]').click()" % json.dumps(other)); c.wait("selected===%s" % json.dumps(other), 60); c.pump(1)
        check("another group opens: no block", c.js("!document.getElementById('qmwrap')"))
        # name and alias matches: no block
        k2 = open_via("board wipe", "alias")
        check("an alias match opens its group without a block (%s)" % k2, k2 and c.js("!document.getElementById('qmwrap')"))
        k3 = open_via("untap a creature", "name")
        check("a name match opens its group without a block (%s)" % k3, k3 and c.js("!document.getElementById('qmwrap')"))
        # the empty line (drawn from the 20 blocks above: a page that has lines, none matching)
        nones = [r for r in results if r["none"]]
        check("empty case: %d of the 20 show the one muted line, worded 'Your words (...) are in this group's description, but no card's own text has them together.'" % len(nones), bool(nones) and all(re.fullmatch(r"Your words \(“.+”\) are in this group’s description, but no card’s own text has them together\.", r["text"]) for r in nones), [r["text"] for r in nones][:2])
        # deep link / reload / pin drop the query
        k = open_via("untap target", "description")
        h = c.js("location.hash")
        check("the address does not carry the query (%s)" % h, "untap" not in h.lower() and "target" not in h.lower())
        c.call("Page.reload"); c.wait(READY, 300); c.pump(1)
        c.wait("!!document.querySelector('#list [data-oid]')", 60); c.pump(1)
        check("reload of the group: no block", c.js("!document.getElementById('qmwrap')"))
        c.js("document.getElementById('q').focus()"); c.type("untap target")
        c.wait("document.querySelectorAll('#findres .gr').length > 0", 90); c.pump(1.2)
        c.js("[...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.why==='description').click()")
        c.wait("!!document.getElementById('qmwrap')", 60)
        c.js("document.getElementById('q').focus(); document.getElementById('q').select()"); c.type("Maze of Ith")
        c.wait("document.querySelectorAll('#findres .fr[data-go^=\"pin:\"]').length > 0", 90); c.pump(1)
        c.js("document.querySelector('#findres .fr[data-go^=\"pin:\"]').click()")
        c.wait("!!document.querySelector('#pinwrap')", 60); c.pump(1.2)
        check("opening a card (the pin) in a group clears the block", c.js("!document.getElementById('qmwrap')"))
        # merged page: a description match on one member group lists only that member's cards
        done = False
        pairs = jx(c, "(()=>{const out=[];const STOP=new Set(['example','that','this','with','your','from','until','end','turn','target','creature','you','control']);for(const e of GSIDX.entries){if(!((e.layer==='l'&&MERGED.by_gid[e.gid])||e.layer==='m')||!e.desc)continue;const ws=[...new Set(e.desc.toLowerCase().replace(/[^a-z ]+/g,' ').split(' ').filter(w=>w.length>=5&&!STOP.has(w)))];for(const q of ws){const r=GroupSearch.search(GSIDX,q,{allow:gsAllow,words:GSWORDS});if(r.groups.some(g=>g.e.gid===e.gid&&g.why==='description')){out.push([q,e.gid,e.name]);break;}} if(out.length>=4)break;}return out;})()")
        for q, gid_, name_ in pairs:
            c.js("document.getElementById('q').focus(); document.getElementById('q').select()"); c.type(q)
            c.wait("document.querySelectorAll('#findres .gr').length > 0", 90); c.pump(1.2)
            has = c.js("!![...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.gid===%s && e.dataset.why==='description')" % json.dumps(gid_))
            if not has:
                continue
            c.js("[...document.querySelectorAll('#findres .gr')].find(e=>e.dataset.gid===%s && e.dataset.why==='description').click()" % json.dumps(gid_))
            c.wait("!!MERGED.redirects[selected] && !!document.querySelector('#list [data-oid]')", 60); c.pump(1.5)
            rows_m = jx(c, "[...document.querySelectorAll('#qmwrap .qr .nm')].map(e=>e.dataset.go.slice(2))")
            mem = set(jx(c, "(()=>{const e=GSIDX.byGid[%s]; const ids = e.layer==='m' ? e.members.filter(g=>g.startsWith('leaf:')).map(g=>g.slice(5)) : [e.gid.slice(5)]; return [...new Set(ids.flatMap(i=>memOids(i)))]})()" % json.dumps(gid_)))
            check("merged page opened from a description match (%s, query '%s'): every block row is in the matched group or, for the page itself, one of its member groups (%d rows, block %s)" % (name_, q, len(rows_m), "shown" if c.js("!!document.getElementById('qmwrap')") else "absent"), all(o in mem for o in rows_m) and c.js("!!MERGED.redirects[selected]"), [o for o in rows_m if o not in mem][:2])
            done = True
            break
        if not done:
            check("a merged-page member with a description match was found for the merged-page block test", False)
        check("no console error, no failed request in the block tests", not s.console() and not [x for x in s.net() if x["failed"] or (x["status"] or 0) >= 400], s.console()[:3])
    finally:
        s.close()

    # ------------------------------------------------------------ 6. first load: size and time; double requests with the cache on
    if not skip_perf:
        perf(DIRS["popoff"], DIRS["pop"])
    after = T.protected()
    changed = [k for k in before if after.get(k) != before[k]]
    check("protected files (corrections, backups, archive, shared JS, serve.py, top-level build files) are byte-identical before and after (%d files)" % len(before), not changed and set(before) == set(after), changed[:3])
    # leave dist/ as the flags-on export
    rc, out = export_to(T.DIST)
    check("dist/ re-exported with the flags on", rc == 0, out[-200:])
    cleanup()
    print()
    ok = sum(1 for r in T.RESULTS if r[1]); bad = [r for r in T.RESULTS if not r[1]]
    print("%d checks, %d passed, %d failed" % (len(T.RESULTS), ok, len(bad)))
    for n in T.NOTES:
        print("NOTE", n)
    return 1 if bad else 0


def ORDER_KEYS(c):
    return jx(c, """(()=>{
      const L = Object.entries(TAX.leaves).filter(([id,l]) => !l.flags.length).map(([id]) => [id, memOids(id).length]);
      const big = L.sort((a,b)=>b[1]-a[1])[0][0];
      const mid = L.find(([id,n]) => n>25 && n<400)[0];
      const mid2 = L.filter(([id,n]) => n>25 && n<400)[7][0];
      const small = L.find(([id,n]) => n>=6 && n<=9)[0];
      const tg = Object.keys(TENT.groups)[3], lg = Object.keys(LOOSE.groups)[2];
      return ['l:'+big, 'l:'+mid, 'l:'+mid2, 'l:'+small, MERGED.pageBy['draw-cards'].key, 'tg:'+tg, 'lg:'+lg, 'l:'+L[40][0]];
    })()""")


def perf(off_root, on_root):
    # (a) first load at 1x and 4x CPU, 5 runs each, gzip server, cache off; flags off against flags on. cards.json is sometimes requested twice (a race in browse.html's needCards, which two callers enter
    # at once); a run with a doubled request is a different load, so the medians are also given over the runs without one.
    runs = {}
    for label, root in (("off", off_root), ("on", on_root)):
        for cpu in (None, 4):
            rr = []
            for _ in range(5):
                s = T.Session(root, "/reports/browse.html#l%3A" + DEEP_ID(), 1280, gz=True, cpu=cpu)
                c = s.c; t0 = time.time(); first = None
                while time.time() - t0 < 180:
                    try:
                        if c.js("!!document.querySelector('#list [data-oid]')"):
                            first = time.time() - t0; break
                    except Exception:
                        pass
                    c.pump(0.05)
                c.wait(READY, 300); ready = time.time() - t0; c.pump(1)
                net = [r for r in s.net() if r["url"].startswith(s.base())]
                urls = {}
                for r in net:
                    urls.setdefault(r["url"], []).append(r["bytes"] or 0)
                dup = sum(1 for v in urls.values() if len(v) > 1)
                uniq_bytes = sum(v[0] for v in urls.values())
                rr.append((first if first is not None else 999, ready, len(net), len(urls), uniq_bytes, dup))
                s.close()
            runs[(label, cpu)] = rr
    for cpu in (None, 4):
        for label in ("off", "on"):
            rr = runs[(label, cpu)]
            clean = [r for r in rr if r[5] == 0] or rr
            T.NOTES.append("deep-link first load, %sx CPU, flags %s: first card row %s s per run; %d of 5 runs had a doubled request; median over the runs without one: first row %.2f s, data ready %.2f s, %d distinct files, %d bytes" % (
                cpu or 1, label, [round(r[0], 2) for r in rr], sum(1 for r in rr if r[5]), statistics.median(r[0] for r in clean), statistics.median(r[1] for r in clean), statistics.median(r[3] for r in clean), statistics.median(r[4] for r in clean)))
    a, b = runs[("off", None)], runs[("on", None)]
    check("first load: flags on requests the same distinct files and the same bytes per file (%d vs %d distinct files; %d vs %d bytes, first request of each)" % (a[0][3], b[0][3], a[0][4], b[0][4]), a[0][3] == b[0][3] and abs(a[0][4] - b[0][4]) < 20000)
    def med(label, cpu):
        rr = runs[(label, cpu)]; clean = [r for r in rr if r[5] == 0] or rr
        return statistics.median(r[0] for r in clean)
    slip = med("on", 4) - med("off", 4)
    T.NOTES.append("4x CPU deep-link first row, flags on minus flags off (runs without a doubled request): %+.2f s (threshold for the compact rank file, fixed before measuring: slip of more than 0.30 s and more than 10%%)" % slip)
    check("4x CPU deep-link first row does not slip past the threshold (%+.2f s)" % slip, slip <= 0.30 or slip <= 0.10 * med("off", 4))
    # (b) are cards.json and members.json requested twice with the cache ON? 5 loads of each page, flags off and flags on
    orig = T.CDP.call

    def call(self, method, **p):
        if method == "Network.setCacheDisabled":
            p["cacheDisabled"] = False
        return orig(self, method, **p)
    T.CDP.call = call
    try:
        for label, root in (("off", off_root), ("on", on_root)):
            for pl, path in (("deep link", "/reports/browse.html#l%3A" + DEEP_ID()), ("no hash", "/reports/browse.html")):
                cnt = {"ability_taxonomy_cards.json": [], "ability_taxonomy_members.json": []}
                for _ in range(5):
                    s = T.Session(root, path, 1280, gz=True)
                    s.c.wait(READY, 300); s.c.pump(2)
                    ids = {}
                    for e in s.c.events:
                        if e["method"] == "Network.requestWillBeSent":
                            ids.setdefault(e["params"]["request"]["url"].replace(s.base(), ""), []).append(e["params"]["requestId"])
                    cache = {e["params"]["requestId"] for e in s.c.events if e["method"] == "Network.requestServedFromCache"}
                    for f in cnt:
                        v = ids.get("/build/" + f, [])
                        cnt[f].append((len(v), sum(1 for i in v if i in cache)))
                    s.close()
                for f, v in cnt.items():
                    T.NOTES.append("cache ON, flags %s, %s, %s over 5 loads: requests per load %s, of which served from cache %s" % (label, pl, f, [x[0] for x in v], [x[1] for x in v]))
        check("double requests measured with the cache on", True)
    finally:
        T.CDP.call = orig


_DEEP = []


def DEEP_ID():
    if not _DEEP:
        _DEEP.append("ab2d4667c5")
    return _DEEP[0]


if __name__ == "__main__":
    sys.exit(main())
