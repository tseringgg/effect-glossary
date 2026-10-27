#!/usr/bin/env python3
"""Verify the tester site's filter and sort bar and "Narrow by group" row (feature TESTER_FILTERS), on the exported dist/ served by a plain static server, in headless Edge (DevTools protocol).

    python src/test_tester_filters.py [--skip-perf] [--reads OUT.json]

Run src/test_tester_static.py as well (the existing static test). Needs msedge.exe, websocket-client, dist/ (python src/export_static.py).

Independent of the page's own code: src/tester_filters_ref.py re-derives every chip and count in Python from the build files, and the group pages themselves are opened to check a chip's count against the real
page size. Not independent: my reads of the narrowed lists (the seed draw is fixed before anything is computed; --reads writes the 30 lists for reading). Clicks are DOM click() calls: no touch, no other browser.
The corrections files and the archive are hashed before and after; nothing here writes to them (the flag-off export goes to dist.off/, which is removed).
"""
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
import test_tester_static as T            # noqa: E402  (Session, check, protected, export helpers)
import tester_filters_ref as REF          # noqa: E402

check = T.check
READY = "document.body.classList.contains('tester') && typeof HG !== 'undefined' && !!HG && !!SIB && !!SC && !!MI && !!CARDS && !!UNORG && !!LOOSE && !!TENT && !!TAGS && !!ANN && GSON === true && PINON === true && !!MERGED && typeof TF !== 'undefined'"
GOKEY = "Manual.goKey"


def open_page(c, key, need_bar=True):
    c.js("show(%s)" % json.dumps(key))
    return c.wait("!document.getElementById('panel').classList.contains('tpend') && " + ("!!document.getElementById('fwrap') && TF.full().length > 0" if need_bar else "true"), 90)


def page_key(R, gid):
    if gid.startswith("P:"):
        return R.pages[gid[2:]]["key"]
    layer, _, i = gid.partition(":")
    return {"leaf": "l:" + i, "tent": "tg:" + i, "loose": "lg:" + i, "tag": "ct:" + i, "kw": "kl:" + gid, "rp": "gl:" + i}[layer]


def js_chips(c):
    return [(x["key"], x["label"], x["n"]) for x in json.loads(c.js("JSON.stringify(TF.chips())"))]


def draw_pairs(R):
    elig = sorted(g for g, v in R.G.items() if v[4] and v[3] in ("leaf", "tent", "loose", "tag", "kw", "rp") and v[1] >= 40)
    rng = random.Random(20263301)
    gids = rng.sample(elig, 60)
    ranks = [rng.randint(1, 5) for _ in gids]
    return list(zip(gids, ranks)), len(elig)


def main():
    skip_perf = "--skip-perf" in sys.argv
    reads_out = sys.argv[sys.argv.index("--reads") + 1] if "--reads" in sys.argv else os.path.join(tempfile.gettempdir(), "narrow30_reads.json")
    before = T.protected()
    rc, out = T.export(T.DIST)
    check("export dist/ (flag on) succeeds", rc == 0, out[-200:])
    R = REF.Ref()
    pairs, n_elig = draw_pairs(R)

    s = T.Session(T.DIST, "/reports/browse.html", 1280)
    c = s.c
    try:
        check("page boots with the filter feature loaded", c.wait(READY, 300))
        c.pump(1.5)
        boot_names = [r["url"].replace(s.base(), "") for r in s.net()]
        check("boot requests testerfilters.js and .css and nothing for shards", any(n.endswith("testerfilters.js") for n in boot_names) and any(n.endswith("testerfilters.css") for n in boot_names) and not [n for n in boot_names if "shard" in n or "narrow" in n])

        # ---- 1. chips and counts against the Python reference: the 30-list draw, every merged page, the biggest pages
        sel, reads = [], []
        for gid, rank in pairs:
            if len(sel) >= 30:
                break
            pk = page_key(R, gid)
            if not open_page(c, pk):
                continue
            full = json.loads(c.js("JSON.stringify(TF.full())"))
            ref = R.chips(full, full, pk)
            if len(ref) < rank:
                continue
            sel.append((gid, rank, pk, full, ref))
            got = js_chips(c)
            if got != ref:
                check("chips equal the reference for %s" % R.G[gid][0], False, (got[:3], ref[:3]))
        check("seed 20263301: %d (page, rank) draws read (of 60 drawn from %d eligible pages)" % (len(sel), n_elig), len(sel) == 30)
        bad = []
        for gid, rank, pk, full, ref in sel:
            open_page(c, pk)
            if js_chips(c) != ref:
                bad.append(R.G[gid][0])
        check("chips and counts equal the Python reference on all %d drawn pages" % len(sel), not bad, bad[:3])
        merged = list(R.pages.values())
        bad = []
        for p in merged:
            open_page(c, p["key"])
            full = json.loads(c.js("JSON.stringify(TF.full())"))
            ref = R.chips(full, full, p["key"])
            if js_chips(c) != ref:
                bad.append(p["name"])
        check("chips and counts equal the reference on all %d merged pages" % len(merged), not bad, bad[:3])
        big = sorted([g for g in R.mem if not g.startswith("P:") and R.G[g][3] in ("leaf", "tent", "loose", "tag", "kw", "rp")], key=lambda g: -len(R.mem[g]))[:12]
        bad = []
        for g in big:
            pk = page_key(R, g)
            open_page(c, pk)
            full = json.loads(c.js("JSON.stringify(TF.full())"))
            if js_chips(c) != R.chips(full, full, pk):
                bad.append(R.G[g][0])
        check("chips and counts equal the reference on the 12 biggest pages", not bad, bad[:3])

        # ---- 2. chip counts against the real page sizes: open the page, open the chip's own page, intersect
        pairs40 = []
        for gid, rank, pk, full, ref in sel:
            for k, label, n in ref[:2]:
                pairs40.append([pk, page_key(R, k), n, label])
        for p in merged[:6]:
            lst = sorted(R.mem["P:" + p["slug"]] & set(R.img))
            top = R.chips(lst, lst, p["key"])
            if top:
                pairs40.append([p["key"], page_key(R, top[0][0]), top[0][2], "merged top"])
        res = json.loads(c.js("""(async (pairs) => { const bad = []; for (const [pk, ck, n, label] of pairs) { await show(pk); const P = new Set(TF.full()); await show(ck); const C = new Set(TF.full()); let i = 0; for (const o of C) if (P.has(o)) i++; if (i !== n) bad.push([pk, ck, n, i, label]); } return JSON.stringify(bad); })(%s)""" % json.dumps(pairs40)))
        check("%d chip counts equal the size of (page AND the chip's own page), measured on the group pages" % len(pairs40), not res, res[:4])

        # ---- 3. facets, sort and the status line on the Draw cards merged page
        dk = [p for p in merged if p["name"] == "Draw cards"][0]["key"]
        open_page(c, dk)
        full = json.loads(c.js("JSON.stringify(TF.full())"))
        F = {o: R.facts(o) for o in full}

        def expect(cols=(), types=(), mvs=()):
            return [o for o in full if (not cols or any(REF.col_match(F[o], x) for x in cols)) and (not types or any(t in F[o]["ts"] for t in types)) and (not mvs or REF.mvb(F[o]["mv"]) in mvs)]
        c.js("TF.reset(); TF.refresh()")
        cases = [(("U",), (), ()), (("U", "B"), (), ()), (("U",), ("Creature",), ()), (("U",), ("Creature",), ("2", "3")), (("C",), (), ()), (("M",), (), ()), ((), (), ("none",)), ((), (), ("0",)), ((), ("Instant", "Sorcery"), ("6+",)), ((), ("Land",), ("none",))]
        bad = []
        for cols, types, mvs in cases:
            c.js("document.querySelector('[data-f=clear]') && document.querySelector('[data-f=clear]').click()")
            for x in cols: c.js("document.querySelector('[data-f=col][data-v=%s]').click()" % x)
            for x in types: c.js("document.querySelector('[data-f=type][data-v=%s]').click()" % x)
            for x in mvs: c.js("document.querySelector('[data-f=mv][data-v=\"%s\"]').click()" % x)
            exp = len(set(expect(cols, types, mvs)))
            got = c.js("TF.shown().length")
            status = c.js("document.querySelector('.fbar .fstat span').textContent")
            if got != exp or ("Showing %s of %s" % (format(exp, ","), format(len(set(full)), ","))) not in status:
                bad.append((cols, types, mvs, exp, got, status))
        check("filters: AND across kinds, OR inside one, and 'Showing N of M' match an independent count (%d combinations)" % len(cases), not bad, bad[:2])
        c.js("document.querySelector('[data-f=clear]') && document.querySelector('[data-f=clear]').click()")
        cnt = json.loads(c.js("""JSON.stringify(Object.fromEntries([...document.querySelectorAll('[data-f=col],[data-f=type],[data-f=mv]')].map(b => [b.dataset.f + ':' + b.dataset.v, b.getAttribute('aria-label') || b.querySelector('b').textContent])))"""))
        want_mv = {m: len([o for o in full if REF.mvb(F[o]["mv"]) == m]) for m in ("0", "1", "2", "3", "4", "5", "6+", "none")}
        got_mv = {m: int(cnt["mv:" + m].split()[-1].replace(",", "")) for m in want_mv}
        check("mana value chips show the independent counts, 0 apart from 'No cost / unknown' %s" % got_mv, got_mv == want_mv, want_mv)
        check("the colour note is under the pips", c.js("/Card colour, not colour identity/.test(document.querySelector('.fbar').innerText)"))
        check("one chip is labelled 'No cost / unknown'", c.js("[...document.querySelectorAll('[data-f=mv]')].some(b => /No cost \\/ unknown/.test(b.textContent))"))

        # sort, on a plain page (no hand or sibling rows, so no sections)
        pg = json.loads(c.js("""(() => { const L = Object.entries(TAX.leaves).filter(([id]) => !(SIB && SIB.groups[id]) && !Object.values(MRESV.adds).some(a => a['leaf:' + id])).sort((a, b) => memOids(b[0]).length - memOids(a[0]).length)[0]; return JSON.stringify(L[0]); })()"""))
        open_page(c, "l:" + pg)
        c.js("TF.reset(); TF.refresh()")
        sres = {}
        for mode in ("name", "mv", "best"):
            c.js("(()=>{const s=document.querySelector('select[data-f=sort]'); s.value='%s'; s.dispatchEvent(new Event('change',{bubbles:true}))})()" % mode)
            sres[mode] = json.loads(c.js("JSON.stringify(TF.shown())"))
        nm = [R.C[o]["n"].lower() for o in sres["name"]]
        check("sort by name: A to Z over the whole page (%d cards)" % len(nm), nm == sorted(nm) or all(nm[i] <= nm[i + 1] for i in range(len(nm) - 1)))
        key = [((R.C[o]["mv"] is None), R.C[o]["mv"] or 0, R.C[o]["n"].lower()) for o in sres["mv"]]
        check("sort by mana value: low to high, 'No cost / unknown' last, ties by name", all(key[i] <= key[i + 1] for i in range(len(key) - 1)))
        check("best match restores the page's own order and loses no card", sres["best"] == json.loads(c.js("JSON.stringify(TF.full())")) and sorted(sres["best"]) == sorted(sres["name"]))

        # ---- 4. narrowing: stacking, recomputed counts, clear, show more, zero-count chips hidden
        pk = "l:" + pg
        open_page(c, pk)
        c.js("TF.reset(); TF.refresh()")
        full = json.loads(c.js("JSON.stringify(TF.full())"))
        ref0 = R.chips(full, full, pk)
        c1 = ref0[0]
        c.js("document.querySelector('[data-f=nar]').click()")
        shown1 = json.loads(c.js("JSON.stringify(TF.shown())"))
        exp1 = sorted(o for o in full if o in R.mem[c1[0]])
        check("narrowing by '%s': %d cards, all in both groups (independent)" % (c1[1], len(shown1)), sorted(shown1) == exp1 and len(shown1) == c1[2], (len(shown1), len(exp1), c1[2]))
        ref1 = R.chips(shown1, full, pk, selected=[c1[0]])
        check("after one tick the chips are recomputed on the narrowed list and equal the reference", js_chips(c) == ref1, (js_chips(c)[:3], ref1[:3]))
        check("no chip with a zero count, none under 3, none that would not narrow", all(3 <= n < len(shown1) for _, _, n in js_chips(c)))
        if ref1:
            c2 = ref1[0]
            c.js("document.querySelector('[data-f=nar]').click()")
            shown2 = json.loads(c.js("JSON.stringify(TF.shown())"))
            exp2 = sorted(o for o in full if o in R.mem[c1[0]] and o in R.mem[c2[0]])
            check("stacking a second group is AND: %d cards" % len(shown2), sorted(shown2) == exp2 and len(shown2) == c2[2])
            check("two tick chips are shown, each with a clear mark", c.js("document.querySelectorAll('.nrow [data-f=narx]').length") == 2)
            c.js("document.querySelectorAll('.nrow [data-f=narx]')[0].click()")
            shown3 = json.loads(c.js("JSON.stringify(TF.shown())"))
            check("removing the first tick leaves only the second", sorted(shown3) == sorted(o for o in full if o in R.mem[c2[0]]))
            c.js("document.querySelector('.nrow [data-f=nclear]').click()")
            check("'Clear' empties the narrowing", c.js("TF.shown().length") == len(full) and c.js("document.querySelectorAll('.nrow [data-f=narx]').length") == 0)
        # show more, on a page with many chips
        mp = max(sel, key=lambda x: len(x[4]))
        open_page(c, mp[2])
        c.js("TF.reset(); TF.refresh()")
        n0 = c.js("document.querySelectorAll('.nrow [data-f=nar]').length")
        if len(mp[4]) > 12:
            c.js("document.querySelector('.nrow [data-f=nmore]').click()")
            n1 = c.js("document.querySelectorAll('.nrow [data-f=nar]').length")
            check("'Show more' adds 12 chips (%d to %d of %d)" % (n0, n1, len(mp[4])), n0 == 12 and n1 == min(24, len(mp[4])))
        else:
            check("top 12 chips are shown (%d chips on the busiest drawn page)" % len(mp[4]), n0 == len(mp[4]))

        # ---- 5. merged page: member groups and twins are not chips; headings with no card left are dropped
        open_page(c, dk)
        c.js("TF.reset(); TF.refresh()")
        full = json.loads(c.js("JSON.stringify(TF.full())"))
        chips = js_chips(c)
        own, _names = R.own(dk)
        check("merged Draw cards page: no member group and no twin is a chip (%d chips; none is one of the 3 member groups or the page)" % len(chips), not [x for x in chips if x[0] in own] and chips == R.chips(full, full, dk))
        c.js("document.querySelector('[data-f=col][data-v=W]').click(); document.querySelector('[data-f=type][data-v=Land]').click()")
        adj = c.js("(() => { let bad = 0; for (let i = 0; i < LIST.length; i++) if (typeof LIST[i] === 'string' && (i === LIST.length - 1 || typeof LIST[i + 1] === 'string')) bad++; return bad; })()")
        check("filtered merged page: no heading is left without a card under it", adj == 0, adj)
        c.js("document.querySelector('[data-f=clear]').click()")

        # ---- 6. Might also fit
        tab_gid = c.js("(() => { const x = Object.entries(SC.groups).filter(([g, e]) => e[1][Suggested.stepIdx(SC, 0.7)] > 20).sort((a, b) => b[1][1][0] - a[1][1][0])[0]; return x[0]; })()")
        open_page(c, page_key(R, tab_gid), need_bar=False)
        c.wait("!!document.querySelector('#sctabs')", 60)
        c.js("document.querySelector('#sctabs button[data-sctab=matches]').click()")
        c.wait("!!document.getElementById('fwrap2') && !!document.querySelector('#suggsec .sgrow')", 60)
        n_all = c.js("document.querySelectorAll('#suggsec .sgrow').length")
        c.js("TF.reset(); document.querySelector('#suggsec [data-f=col][data-v=U]').click()")
        c.wait("!!document.getElementById('fwrap2')", 30)
        rows = json.loads(c.js("JSON.stringify([...document.querySelectorAll('#suggsec .sgrow')].map(e => e.dataset.oid))"))
        check("Might also fit: the bar sits over the rows, a colour filter keeps only blue cards (%d rows)" % len(rows), c.js("!!document.querySelector('#fwrap2 .fbar')") and all("U" in R.C[o]["col"] for o in rows), rows[:2])
        check("Might also fit: still no Add, no slider, no tick", not c.js("!!document.querySelector('#suggsec [data-sact=add], #suggsec input[type=range], #suggsec input[type=checkbox]')"))
        c.js("TF.reset(); TF.refresh()")

        # ---- 7. card pin
        c.js("document.getElementById('q').focus()")
        c.js("(()=>{const q=document.getElementById('q'); q.value='Wrath of God'; q.dispatchEvent(new Event('input',{bubbles:true}))})()")
        c.wait("document.querySelectorAll('#findres .fr').length > 0", 60)
        c.js("document.querySelector('#findres .fr').click()")
        c.wait("!!document.getElementById('pinwrap') && !!document.getElementById('fwrap')", 60)
        c.js("document.querySelector('[data-f=type][data-v=Instant]').click()")
        check("card pin: a filter that hides the pinned card says so and keeps the pin", c.js("!!document.getElementById('pinwrap') && /Hidden by your filters/.test(document.getElementById('pinwrap').textContent)"))
        c.js("document.querySelector('#pinwrap [data-f=clear]').click()")
        check("card pin: Clear filters in the pin restores the list", c.js("!/Hidden by your filters/.test(document.getElementById('pinwrap').textContent) && TF.shown().length === TF.full().length"))

        cons = [x for x in s.console() if not re.search(r"cards\.scryfall\.io", x)]
        check("desktop run: no console errors or warnings", not cons, cons[:3])
        allnet = s.net()
        bad = [r for r in allnet if r["url"].startswith(s.base()) and (r["failed"] or (r["status"] or 0) >= 400)]
        check("desktop run: no failed same-origin request (%d requests), no POST, no /api/" % len(allnet), not bad and not [r for r in allnet if r["method"] != "GET" or "/api/" in r["url"]], bad[:3])
        # ---- the 30 narrowed lists, written out for reading
        c.js("SCTAB = 'members'; try { localStorage.removeItem('groupTab'); } catch (e) { }")      # the page remembers the last tab; the reads are of the group's own list
        for gid, rank, pk, full, ref in sel:
            open_page(c, pk)
            c.js("(document.querySelector('#sctabs button[data-sctab=members]') || { click() {} }).click()")
            c.pump(0.3)
            c.js("TF.reset(); TF.refresh()")
            k, label, n = ref[rank - 1]
            c.js("[...document.querySelectorAll('.nrow [data-f=nar]')].find(b => b.dataset.v === %s).click()" % json.dumps(k))
            ids = json.loads(c.js("JSON.stringify(TF.shown())"))
            reads.append({"page": R.G[gid][0], "page_cards": len(full), "chip_rank": rank, "chip": label, "count": n, "shown": len(ids), "cards": [{"name": R.C[o]["n"], "text": R.C[o]["t"][:140].replace("\n", " / ")} for o in ids[:8]]})
        json.dump(reads, open(reads_out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        check("30 narrowed lists written for reading (%s)" % reads_out, len(reads) == 30 and all(r["shown"] == r["count"] for r in reads))
    finally:
        s.close()

    # ---- 8. 390 px
    s = T.Session(T.DIST, "/reports/browse.html", 390)
    c = s.c
    try:
        c.wait(READY, 300); c.pump(1.5)
        open_page(c, "l:" + pg)
        m = json.loads(c.js("""(() => { const b = document.querySelector('.fbar'), f = document.querySelector('.fsum'); return JSON.stringify({barShown: b.getClientRects().length > 0, sum: f.getBoundingClientRect().height, sw: document.documentElement.scrollWidth, txt: f.innerText.replace(/\\n+/g, ' | ')}); })()"""))
        check("390 px: the bar starts collapsed to one 44 px line that shows the count (%s)" % m["txt"], not m["barShown"] and m["sum"] >= 44 and "Showing" in m["txt"] and m["sw"] <= 390, m)
        c.js("document.querySelector('.fsum[data-f=fold]').click()"); c.pump(0.4)
        m = json.loads(c.js("""(() => { const q = s => [...document.querySelectorAll(s)].map(e => Math.round(e.getBoundingClientRect().height)); return JSON.stringify({bar: document.querySelector('.fbar').getClientRects().length > 0, pips: q('.fpip'), chips: q('.fch').slice(0, 20), sel: q('.fsel'), sw: document.documentElement.scrollWidth, pw: document.getElementById('panel').scrollWidth}); })()"""))
        check("390 px: the bar opens in place; pips, chips and the sort are 40 px or taller; no sideways scroll", m["bar"] and min(m["pips"]) >= 40 and min(x for x in m["chips"] if x) >= 40 and min(m["sel"]) >= 44 and m["sw"] <= 390 and m["pw"] <= 390, m)
        c.js("document.querySelector('[data-f=col][data-v=U]').click()"); c.pump(0.4)
        txt = c.js("document.querySelector('.fsum[data-f=fold]').innerText.replace(/\\n+/g,' | ')")
        check("390 px: the summary names what is on and the count (%s)" % txt, "Blue" in txt and "Showing" in txt)
        c.js("document.querySelector('.fsum[data-f=nfold]') && document.querySelector('.fsum[data-f=nfold]').click()"); c.pump(0.4)
        m = json.loads(c.js("""(() => { const n = document.querySelector('.nrow'); const ch = n ? [...n.querySelectorAll('.fch')].map(e => Math.round(e.getBoundingClientRect().height)) : []; return JSON.stringify({n: !!n && n.getClientRects().length > 0, ch: ch, sw: document.documentElement.scrollWidth, lefts: [...new Set([...document.querySelectorAll('#list .tile')].slice(0, 6).map(e => Math.round(e.getBoundingClientRect().left)))].length}); })()"""))
        check("390 px: 'Narrow by group' opens as its own fold, chips 40 px or taller, cards two across", m["n"] and (not m["ch"] or min(m["ch"]) >= 40) and m["sw"] <= 390 and m["lefts"] == 2, m)
        cons = [x for x in s.console() if not re.search(r"cards\.scryfall\.io", x)]
        bad = [r for r in s.net() if r["url"].startswith(s.base()) and (r["failed"] or (r["status"] or 0) >= 400)]
        check("390 px run: no console errors, no failed request", not cons and not bad, (cons[:2], bad[:2]))
    finally:
        s.close()

    # ---- 9. the flag off: nothing requested, nothing drawn, every other file byte-identical
    off = os.path.join(HERE, "dist.off")
    cfg = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    cfg.write(T.flags_off_text(("TESTER_FILTERS",)))
    cfg.close()
    try:
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--out", "dist.off", "--config", cfg.name], capture_output=True, text=True, cwd=HERE, encoding="utf-8")
        check("export with the flag off succeeds", r.returncode == 0, r.stdout[-200:] + r.stderr[-300:])
        on = {os.path.relpath(p, T.DIST).replace("\\", "/"): T.sha(p) for p in T.walk(T.DIST)}
        offf = {os.path.relpath(p, off).replace("\\", "/"): T.sha(p) for p in T.walk(off)}
        diff = sorted(k for k in set(on) | set(offf) if on.get(k) != offf.get(k))
        check("flag off: every other file is byte-identical to the flag-on export; only config.js, the two feature files and the manifest differ %s" % diff, diff == sorted(["manifest.json", "reports/config.js", "reports/testerfilters.css", "reports/testerfilters.js"]), diff)
        s = T.Session(off, "/reports/browse.html", 1280)
        c = s.c
        try:
            c.wait("document.body.classList.contains('tester') && typeof HG !== 'undefined' && !!HG && !!SIB && !!SC && !!MI && !!CARDS && !!UNORG && !!LOOSE && !!TENT && !!TAGS && !!ANN && GSON === true && PINON === true && !!MERGED", 300)
            c.js("show('l:%s')" % pg); c.wait("!!document.querySelector('#list [data-oid]') && !document.getElementById('panel').classList.contains('tpend')", 60); c.pump(1)
            names = [r["url"] for r in s.net()]
            check("flag off: no filter files requested, no bar, no TF object, the page works", not [n for n in names if "testerfilters" in n] and not c.js("!!document.getElementById('fwrap') || typeof TF !== 'undefined'") and c.js("document.querySelectorAll('#list .tile').length") > 0)
            check("flag off: no console errors", not [x for x in s.console() if not re.search(r"cards\.scryfall\.io", x)])
        finally:
            s.close()
    finally:
        os.unlink(cfg.name)
        shutil.rmtree(off, ignore_errors=True)

    # ---- 10. timing on the real built page, 4x CPU slowdown
    perf = None
    if not skip_perf:
        perf = {}
        for cpu in (1, 4):
            s = T.Session(T.DIST, "/reports/browse.html", 1280, cpu=cpu)
            c = s.c
            try:
                c.wait(READY, 400); c.pump(2)
                perf[cpu] = json.loads(c.js("""(async () => {
                  const t = f => { const a = performance.now(); f(); return Math.round((performance.now() - a) * 10) / 10; };
                  const med = (f, n) => { const r = []; for (let i = 0; i < n; i++) r.push(f()); r.sort((x, y) => x - y); return r[n >> 1]; };
                  const dk = MERGED.pageBy['draw-cards'].key, out = {};
                  let a = performance.now(); await show(dk); out.open_page_ms = Math.round(performance.now() - a);
                  out.cards = TF.full().length;
                  const click = sel => () => t(() => document.querySelector(sel).click());
                  out.filter_blue_ms = med(() => { const x = click('[data-f=col][data-v=U]')(); document.querySelector('[data-f=clear]') && document.querySelector('[data-f=clear]').click(); return x; }, 5);
                  document.querySelector('[data-f=col][data-v=U]').click();
                  out.add_creature_ms = med(() => { const x = click('[data-f=type][data-v=Creature]')(); click('[data-f=type][data-v=Creature]')(); return x; }, 5);
                  document.querySelector('[data-f=type][data-v=Creature]').click();
                  out.sort_mv_ms = med(() => t(() => { const s = document.querySelector('select[data-f=sort]'); s.value = 'mv'; s.dispatchEvent(new Event('change', { bubbles: true })); }), 5);
                  out.sort_name_ms = med(() => t(() => { const s = document.querySelector('select[data-f=sort]'); s.value = 'name'; s.dispatchEvent(new Event('change', { bubbles: true })); }), 5);
                  { const s = document.querySelector('select[data-f=sort]'); s.value = 'best'; s.dispatchEvent(new Event('change', { bubbles: true })); }
                  document.querySelector('[data-f=clear]').click();
                  out.narrow_tick_ms = med(() => { const x = t(() => document.querySelector('.nrow [data-f=nar]').click()); document.querySelector('.nrow [data-f=narx]').click(); return x; }, 5);
                  document.querySelector('.nrow [data-f=nar]').click();
                  out.narrow_stack_ms = med(() => { if (!document.querySelector('.nrow [data-f=nar]')) return 0; const x = t(() => document.querySelector('.nrow [data-f=nar]').click()); const xs = document.querySelectorAll('.nrow [data-f=narx]'); xs[xs.length - 1].click(); return x; }, 5);
                  out.clear_ms = t(() => document.querySelector('[data-f=clear]').click());
                  return JSON.stringify(out);
                })()"""))
                print("PERF cpu x%d" % cpu, perf[cpu])
            finally:
                s.close()
        check("timing measured on the built page at 1x and 4x CPU", all(v for v in perf.values()))
        check("every filter, sort and narrowing click takes under 150 ms at 4x CPU (the bar is mine; Clear, which redraws the whole first page, is the slowest)", all(v < 150 for k, v in perf[4].items() if k.endswith("_ms") and k != "open_page_ms"), perf[4])

    after = T.protected()
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    check("protected files byte-identical before and after (%d hashed)" % len(before), not changed, changed[:3])
    print("\n%d checks, %d failed" % (len(T.RESULTS), len([r for r in T.RESULTS if not r[1]])))
    if perf:
        print("PERF", json.dumps(perf))
    sys.exit(1 if any(not r[1] for r in T.RESULTS) else 0)


if __name__ == "__main__":
    main()
