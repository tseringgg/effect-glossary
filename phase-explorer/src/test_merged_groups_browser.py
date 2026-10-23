#!/usr/bin/env python3
"""Headless Edge pass for the merged group pages (DevTools protocol). A TEMPORARY corrections file is served in place of the real one (hand placements and Add are made into the copy); the protected files are hashed
before and after.

    python src/test_merged_groups_browser.py     (same needs as src/test_group_search_browser.py; build/merged_groups/ and build/group_search/ must be built)
    BROWSE_BEFORE=<path to the browse.html from before the merged pages>   (optional: compares the flag-off group pages with it)

Covered: flag off (one 404 request, every member opens as its own page, no badge, separate search rows, the group pages identical to the page before the merged pages); flag on: the Draw cards page (name, badge,
display-figure note, a section per member with its full name / path / own count / limit note, "open on its own"), a card in two members shown once with an "also in" mark and "k also shown above" in the later section, the
union counted from the cards on the page, an old link to a non-first member (scrolls to its section; with &card= and &tab=matches it lands on the page key, keeps both, starts the picker on that member, hides the pin on the
matches tab and gets it back, highlighted in the right section), "open on its own", a search row (one merged row, no member rows, alias, member-name match), Add and Undo from a merged page (temporary copy), a hand placement
shown in its member's section, the tree badges, the tag switch off, the six figures and the hand line equal flag on and off, 390 px. Clicks are DOM click() calls and the box is typed with real key events: no touch, no
other browser.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_manual_browser as TB
import manual_common as MC

HERE = MC.HERE
CORR = os.path.join(HERE, "corrections")
PROTECTED = [os.path.join(CORR, n) for n in ("manual_placements.json", "manual_placements.json.bak", "hand_groups.json", "hand_groups.json.bak", "group_aliases.json", "group_descriptions.json", "group_aliases_drafted.json", "merged_groups.json")]
BEFORE_HTML = os.environ.get("BROWSE_BEFORE")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


OFF_SEARCH = tempfile.mkdtemp(prefix="mg_offsearch_")        # the group-search index as it is built with MERGED_GROUPS off (no merged index to read)


class Off(TB.Real):                                            # MERGED_GROUPS off: the files do not exist, and the search index was built without them
    def translate_path(self, path):
        p = path.split("?")[0]
        if p.startswith("/build/group_search/"):
            return os.path.join(OFF_SEARCH, p[len("/build/group_search/"):])
        return super().translate_path(path)

    def do_GET(self):
        if self.path.split("?")[0].startswith("/build/merged_groups/"):
            self.send_error(404)
            return
        super().do_GET()


class Old(Off):
    def translate_path(self, path):
        if path.split("?")[0] == "/reports/browse.html" and BEFORE_HTML:
            return BEFORE_HTML
        return super().translate_path(path)


def jl(n):
    return json.load(open(os.path.join(HERE, "build", n), encoding="utf-8"))


def main():
    before = [sha(p) for p in PROTECTED]
    assert os.path.abspath(TB.DOC) != os.path.join(CORR, "manual_placements.json")
    MI, IDX = jl("manual_index.json"), jl(os.path.join("merged_groups", "index.json"))
    r = subprocess.run([sys.executable, os.path.join(HERE, "src", "build_group_search.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, GROUP_SEARCH_OUT=OFF_SEARCH, MERGED_BUILD_OUT=tempfile.mkdtemp(prefix="mg_none_")))
    assert r.returncode == 0 and os.path.exists(os.path.join(OFF_SEARCH, "index.json")), r.stdout[-300:] + r.stderr[-300:]
    cards = MI["cards"]
    pages = {p["slug"]: p for p in IDX["pages"]}
    draw, engines, copies = pages["draw-cards"], pages["draw-engines"], pages["copies-instants-and-sorceries"]
    mem = jl("ability_taxonomy_members.json")["leaves"]
    sugg = jl(os.path.join("suggested_cards", "meta.json"))
    results = []
    port_c = TB.free_port()

    def check(name, ok, detail=""):
        results.append((name, bool(ok)))
        print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)[:300]) if detail else ""))
    tagg = jl("tag_placements.json")["groups"]
    oids = lambda m: {x[0] for x in mem[m["gid"][5:]]} if m["gid"].startswith("leaf:") else set(tagg[m["gid"][4:]]["m"])
    # the card in two members of Draw cards, and a card only in the third member (leaf:ac62240d34) for the old-link test
    d0, d1, d2 = [oids(m) for m in draw["members"]]
    two = sorted(d0 & d1 | d0 & d2 | d1 & d2)
    third = draw["members"][2]
    only3 = sorted(d2 - d0 - d1)
    nm_count = __import__("collections").Counter(v[0].lower() for v in cards.values())
    link_card = next(o for o in only3 if cards[o][1] == "p" and nm_count[cards[o][0].lower()] == 1)
    hand_card = next(o for o in sorted(cards) if cards[o][1] == "u" and o not in d0 | d1 | d2 and nm_count[cards[o][0].lower()] == 1)
    eng_two = sorted(oids(engines["members"][0]) & oids(engines["members"][1]))
    print("cards: two-member=%s link=%s hand=%s" % (cards[two[0]][0], cards[link_card][0], cards[hand_card][0]))
    srvs = [TB.Quiet(("127.0.0.1", TB.PORT_A), TB.Real), TB.Quiet(("127.0.0.1", TB.PORT_B), Off)]
    if BEFORE_HTML:
        srvs.append(TB.Quiet(("127.0.0.1", port_c), Old))
    for s_ in srvs:
        threading.Thread(target=s_.serve_forever, daemon=True).start()
    edge = subprocess.Popen([TB.EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + tempfile.mkdtemp(), "--remote-debugging-port=%d" % TB.PORT_CDP, "--remote-allow-origins=*",
                             "--window-size=1400,1000", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def post(body):
        r = urllib.request.Request("http://127.0.0.1:%d/api/manual" % TB.PORT_A, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json", "X-Manual-Edit": "1"})
        return json.load(urllib.request.urlopen(r))
    try:
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % TB.PORT_CDP))
                break
            except Exception:
                time.sleep(0.5)
        c = TB.CDP(next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"])
        c.call("Page.enable")
        READY = "document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null && !!KFAC && !!HG && !!TENT && !!TAGS && typeof MERGEDP !== 'undefined' && MERGEDP !== null && typeof GSON !== 'undefined'"

        def load(port, frag="", clear=True):
            c.call("Page.navigate", url="about:blank")
            time.sleep(0.4)
            if clear:
                c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % port)
                c.wait("document.readyState === 'complete'", 60)
                c.js("localStorage.clear()")
                c.call("Page.navigate", url="about:blank")
                time.sleep(0.3)
            c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html%s" % (port, frag))
            ok = c.wait(READY, 240)
            c.wait("(!GSON || !document.getElementById('gsnote').textContent.endsWith('…'))", 30)
            c.wait("!document.querySelector('#panel .explain') || !/Loading/.test(document.querySelector('#panel .explain').textContent)", 60)
            return ok

        def settle():
            last, same = None, 0
            for _ in range(80):
                h = c.js("document.getElementById('findres').innerHTML")
                if h == last and not h.startswith('<div class="sub">Loading'):
                    same += 1
                    if same >= 3:
                        return h
                else:
                    same = 0
                last = h
                time.sleep(0.2)
            return last

        def search(text):
            c.js("(() => { const q = document.getElementById('q'); q.value = ''; q.dispatchEvent(new Event('input')); q.focus(); })()")
            time.sleep(0.4)
            c.type(text)
            time.sleep(0.5)
            return settle()
        figs = lambda: c.js("[...document.querySelectorAll('#cov > div:not(.basis)')].map(d => d.innerText).join('|')")
        gos = lambda: c.js("[...document.querySelectorAll('#findres .gr[data-go]')].map(e => e.dataset.go)")
        NHID = ("(slug) => { const pg = MERGED.pageBy[slug], s = new Set(); for (const m of pg.members) for (const o of memberOidsOf(m)) s.add(o); return [s.size, [...s].filter(o => !visible(o)).length]; }")
        # the page's figure counts the cards the browser lists: with 'hide cards without a picture' on (the default) a card with no picture is not counted, as on every group page
        shown_n = lambda slug: (lambda t: (t[0], t[0] - t[1]))(c.js("(" + NHID + ")(%s)" % json.dumps(slug)))

        def open_key(k):
            c.js("show(%s)" % json.dumps(k))
            c.wait("selected === %s && !!document.getElementById('list')" % json.dumps(IDX["pages"][0]["key"] if k == draw["key"] else k), 120)
            time.sleep(1.0)

        selected_is = lambda k: c.js("selected") == k

        def all_cards():                                                  # page everything in, then every card row in document order
            c.js("(() => { let g = 0; while (LISTN < LIST.length && g++ < 400) renderList(); })()")
            return c.js("[...document.querySelectorAll('#list .card[data-oid]')].map(e => e.dataset.oid)")
        SECOF = ("(oid) => { const els = [...document.querySelectorAll('#list .msec, #list .card[data-oid=\"' + oid + '\"], #list .pinhit')]; let s = -1; for (const e of els) { if (e.classList.contains('msec')) s++; "
                 "else return s; } return -1; }")
        STATE = ("(() => { const w = document.getElementById('pinwrap'), hit = document.querySelector('#list .pinhit'); return {sel: selected, pin: !!w, hit: !!hit, hitOid: hit ? hit.dataset.oid : '', "
                 "hash: decodeURIComponent(location.hash), off: w ? w.classList.contains('sc-off') : null, "
                 "hitSec: hit ? (() => { let s = -1; for (const e of document.querySelectorAll('#list .msec, #list .pinhit')) { if (e.classList.contains('msec')) s++; else return s; } return -1; })() : -2}; })()")
        state = lambda: c.js(STATE)

        # ---------------------------------------------------------------- flag off
        ok = load(TB.PORT_B)
        check("0 flag off: the page boots, no merged pages, and it asked for the one small file (a 404)", ok and c.js("MERGED") is None and c.js("performance.getEntriesByType('resource').filter(r => r.name.includes('merged_groups/')).length") == 1)
        figs_off = figs()
        hand_off = c.js("document.getElementById('handline') ? document.getElementById('handline').innerText : ''")
        c.js("show(%s)" % json.dumps(draw["members"][2]["key"]))
        c.wait("selected === %s" % json.dumps(draw["members"][2]["key"]), 60)
        time.sleep(1.0)
        check("0 flag off: a member opens as its own page (its own key, no merged badge, no section heads)", c.js("selected") == draw["members"][2]["key"] and c.js("document.querySelectorAll('.b-merged, .msec').length") == 0)
        check("0 flag off: the tree has no 'merged' badge", c.js("document.querySelectorAll('#tree .b-merged').length") == 0)
        h_off = search("draw cards")
        check("0 flag off: search lists a member as its own row (%d of them) and no merged row" % len([g for g in gos() if g in [m["key"] for m in draw["members"]]]), draw["members"][0]["key"] in gos() and "merged page" not in h_off and "merged page" not in c.js("document.getElementById('findres').innerText"), (gos()[:5], [i for i in range(len(h_off)) if h_off.startswith("merged page", i)][:1] and h_off[max(0, h_off.find("merged page") - 80):h_off.find("merged page") + 40]))
        panels_off = {}
        for m in draw["members"]:
            c.js("show(%s)" % json.dumps(m["key"]))
            c.wait("selected === %s" % json.dumps(m["key"]), 60)
            time.sleep(0.8)
            panels_off[m["key"]] = c.js("document.getElementById('panel').innerHTML")
        if BEFORE_HTML:
            load(port_c)
            same = True
            for m in draw["members"]:
                c.js("show(%s)" % json.dumps(m["key"]))
                c.wait("selected === %s" % json.dumps(m["key"]), 60)
                time.sleep(0.8)
                same = same and c.js("document.getElementById('panel').innerHTML") == panels_off[m["key"]]
            check("0 flag off: the three member pages are identical to the page before the merged pages (the same HTML)", same)
        # ---------------------------------------------------------------- flag on: the Draw cards page
        ok = load(TB.PORT_A)
        check("1 flag on: the page boots with %d merged pages" % len(IDX["pages"]), ok and c.js("MERGED.pages.length") == len(IDX["pages"]))
        check("1 the six figures and the hand line are the same flag on and off (%s ...)" % figs()[:60], figs() == figs_off and "73.3%" in figs() and
              c.js("document.getElementById('handline') ? document.getElementById('handline').innerText : ''") == hand_off)
        open_key(draw["key"])
        head = c.js("document.querySelector('#panel h2').innerText + '|' + document.querySelector('#panel > p.sub, #panel .sub').innerText")
        un, vis = shown_n("draw-cards")
        check("2 the Draw cards page: name, 'merged page' badge, '%s cards shown · 3 groups together' (the build's union is %s; %d card has no picture and is hidden, as on every group page)" % (format(vis, ","), format(un, ","), un - vis),
              "Draw cards" in head and "merged page" in head and ("%s cards shown" % format(vis, ",")) in head and "3 groups together" in head and un == draw["union"], head)
        note = c.js("document.querySelector('#panel .note').innerText")
        check("2 ... the note says it is display only and that the number is a display figure (each group keeps its own count)", "Display only" in note and "display figure" in note and "own count" in note, note[:140])
        shown = all_cards()
        secs = c.js("[...document.querySelectorAll('#list .msec')].map(e => e.innerText)")
        check("2 ... one section per member (3), each with its full name's limit note visible, its own count and 'open on its own'", len(secs) == 3 and all(
            "open on its own" in s for s in secs) and all(__import__("re").search(r"\d[\d,]* cards? in this group", s) for s in secs) and "who draws" in secs[0].lower() and "end of turn" in secs[2].lower(), [s[:90] for s in secs])
        notes_ok = all(any(w in s for w in (m["full"].split(" — ")[-1][:25],)) for s, m in zip(secs, draw["members"]))
        check("2 ... each section heading carries the tail of its group's full name (the limit)", notes_ok, [m["full"][-40:] for m in draw["members"]])
        check("2 ... the cards on the page are each listed once (%d), and that equals the union of the three groups' cards that have a picture (%d), a display figure" % (len(shown), vis), len(shown) == len(set(shown)) == vis, (len(shown), len(set(shown))))
        tc = two[0]
        sec_a = c.js("(" + SECOF + ")(%s)" % json.dumps(tc))
        check("3 the card in two members (%s) is on the page once, in the first of them (section %d)" % (cards[tc][0], sec_a + 1), shown.count(tc) == 1 and sec_a == min(i for i, o in enumerate((d0, d1, d2)) if tc in o), sec_a)
        mark = c.js("(() => { const e = document.querySelector('#list .card[data-oid=%s]'); const m = e && e.querySelector('.also'); return m ? m.innerText : ''; })()" % json.dumps(tc))
        check("3 ... with an 'also in' mark naming the other group (%s)" % mark[:60], mark.lower().startswith("also in") and len(mark) > 10, mark)
        later = c.js("[...document.querySelectorAll('#list .msec .sub')].map(e => e.innerText)")
        check("3 ... and the later section says '1 also shown above' (it still lists its own count)", any("1 also shown above" in s for s in later), later)
        # Draw engine: 31 cards in two members
        open_key(engines["key"])
        sh2 = all_cards()
        eh = c.js("[...document.querySelectorAll('#list .msec .sub')].map(e => e.innerText)")
        check("3 the Draw engine page: %d cards in both members are shown once each (%d cards on the page = union %d), the second section says '%d also shown above'" % (len(eng_two), len(sh2), engines["union"], len(eng_two)),
              len(sh2) == len(set(sh2)) == shown_n("draw-engines")[1] == engines["union"] and any(("%d also shown above" % len(eng_two)) in s for s in eh), eh)
        # ---------------------------------------------------------------- old links
        link = "#" + urllib.parse.quote(third["key"], safe="") + "&card=" + link_card + "&tab=matches"
        load(TB.PORT_A, frag=link, clear=False)
        c.wait("selected === %s" % json.dumps(draw["key"]), 120)
        time.sleep(2.0)
        s = state()
        check("4 an old link to the third member with &card= and &tab=matches: the address becomes the page key and keeps both (%s)" % s["hash"][-60:], s["sel"] == draw["key"] and s["hash"].startswith("#" + draw["key"]) and "&card=" + link_card in s["hash"] and s["hash"].endswith("&tab=matches"), s["hash"])
        tabopen = c.js("(document.querySelector('#suggsec') || {}).hidden === false || (!!document.querySelector('#suggsec') && getComputedStyle(document.querySelector('#suggsec')).display !== 'none')")
        pick = c.js("(document.querySelector('#suggsec [data-sctl=member]') || {}).value")
        check("4 ... the Possible matches tab is open and its group picker starts on that third member (%s)" % pick, tabopen and pick == third["gid"], (tabopen, pick))
        check("4 ... the pin is hidden while the matches tab is open", s["off"] is True, s)
        c.js("document.querySelector('#sctabs button[data-sctab=members]').click()")
        time.sleep(1.0)
        s = state()
        check("4 ... back on the cards tab the pin is back, the card is highlighted, and it is in the third member's section", s["pin"] and s["off"] is False and s["hit"] and s["hitOid"] == link_card and s["hitSec"] == 2, s)
        load(TB.PORT_A, frag="#" + urllib.parse.quote(third["key"], safe=""), clear=False)
        c.wait("selected === %s" % json.dumps(draw["key"]), 120)
        time.sleep(1.5)
        top = c.js("(() => { const e = document.getElementById('msec-2'); return e ? e.getBoundingClientRect().top : null; })()")
        check("5 an old link to the third member alone scrolls to its section (top at %s px)" % (round(top) if top is not None else None), top is not None and 0 <= top < 600 and c.js("selected") == draw["key"], top)
        c.js("document.querySelector('#list .msec[data-gid=%s] [data-alone]').click()" % json.dumps(third["gid"]))
        c.wait("selected === %s && document.querySelectorAll('.msec').length === 0" % json.dumps(third["key"]), 60)
        time.sleep(1.0)
        check("5 'open on its own' shows that member by itself (its own page, no merged badge), and its count is its own (%s)" % format(third["size"], ","),
              c.js("selected") == third["key"] and c.js("document.querySelectorAll('#panel .b-merged').length") == 0 and ("%s cards" % format(third["size"], ",")) in c.js("document.getElementById('panel').innerText"))
        # ---------------------------------------------------------------- search
        load(TB.PORT_A, clear=False)
        h = search("draw cards")
        g = gos()
        check("6 search 'draw cards': one merged row (the page key) and no row for the other two members", draw["key"] in g and not any(m["key"] in g for m in draw["members"][1:]) and "merged page" in h, g[:6])
        row = c.js("(() => { const e = document.querySelector('#findres .gr[data-go=%s]'); return e ? e.innerText : ''; })()" % json.dumps(draw["key"]))
        check("6 ... the row shows the display figure %s (cards with a picture) and says it is a merged page" % format(vis, ","), format(vis, ",") in row and "merged" in row.lower(), row[:120])
        search("counterspell")
        g = gos()
        check("6 an alias that pointed at a member ('counterspell') now answers with the page (first row %s)" % (g[:1],), g and g[0] == pages["counter-a-spell"]["key"], g[:3])
        search("who draws or gains it isn't reliably recorded")
        g = gos()
        check("6 a member's own name finds the page (one row for it, the page key)", draw["key"] in g[:3], g[:4])
        c.js("document.querySelector('#findres .gr[data-go=%s]').click()" % json.dumps(draw["key"]))
        c.wait("selected === %s && document.querySelectorAll('#panel .b-merged').length >= 1" % json.dumps(draw["key"]), 60)
        check("6 ... and the row opens the merged page", selected_is(draw["key"]) and c.js("document.querySelectorAll('#panel .b-merged').length") >= 1)
        # tree badges
        check("7 the tree marks a merged member with a 'merged' badge (%d members badged)" % c.js("document.querySelectorAll('#tree .b-merged').length"), c.js("document.querySelectorAll('#tree .b-merged').length") >= 1)
        # ---------------------------------------------------------------- Add / Undo from a merged page, hand placement
        open_key(draw["key"])
        c.js("document.querySelector('#sctabs button[data-sctab=matches]').click()")
        time.sleep(1.5)
        pickers = c.js("[...document.querySelectorAll('#suggsec [data-sctl=member] option')].map(o => o.value)")
        third_pick = third["gid"] if third["gid"] in pickers else pickers[0]
        c.js("(() => { const s = document.querySelector('#suggsec [data-sctl=member]'); s.value = %s; s.dispatchEvent(new Event('change', {bubbles: true})); })()" % json.dumps(third_pick))
        time.sleep(1.5)
        rows = c.js("[...document.querySelectorAll('#suggsec .sgrow')].map(e => e.dataset.oid)")
        check("8 the Possible matches tab of the page has a group picker (%d groups) and lists that group's matches (%d)" % (len(pickers), len(rows)), len(pickers) >= 1 and len(rows) >= 1, (pickers, rows))
        o1 = rows[0]
        c.js("document.querySelector('#suggsec .sgrow[data-oid=\"%s\"] [data-sact=add]').click()" % o1)
        c.wait("Object.keys(MDOC.edits).length === 1 && /saved/.test(LASTMSG)", 30)
        time.sleep(0.5)
        e = TB.doc()["edits"].get(o1, {}).get("groups", {}).get(third_pick)
        check("8 Add from the merged page saves the placement for that member's own group (%s), in the temporary copy only" % third_pick, e and e["action"] == "add" and "batch" not in e, e)
        check("8 the six figures do not move because of it", figs() == figs_off)
        c.js("document.querySelector('#suggsec .sgrow[data-oid=\"%s\"] [data-sact=undo]').click()" % o1)
        c.wait("Object.keys(MDOC.edits).length === 0", 30)
        time.sleep(0.5)
        check("8 Undo removes it again (the temporary file has no edits)", not TB.doc()["edits"])
        member1 = draw["members"][1]
        r1 = post({"oid": hand_card, "group": member1["gid"], "action": "add", "note": "test"})
        load(TB.PORT_A, frag="#" + urllib.parse.quote(draw["key"], safe=""), clear=False)
        c.wait("selected === %s" % json.dumps(draw["key"]), 120)
        time.sleep(1.5)
        shown = all_cards()
        sec_h = c.js("(" + SECOF + ")(%s)" % json.dumps(hand_card))
        check("9 a card placed by hand in the second member (temporary copy) shows in that member's section (%s, section %d)" % (cards[hand_card][0], sec_h + 1), r1.get("ok") and shown.count(hand_card) == 1 and sec_h == 1, (r1, sec_h))
        # ---------------------------------------------------------------- the switches, 390 px
        c.js("document.getElementById('showtag').click()")
        time.sleep(1.0)
        cp = copies["key"]
        tagpage = pages["draw-engines"]
        c.js("show(%s)" % json.dumps(tagpage["key"]))
        time.sleep(1.5)
        check("10 community-tag switch off: the tag-only page says so (nothing breaks)", "switched off" in c.js("document.getElementById('panel').innerText") or c.js("selected") != tagpage["key"], c.js("document.getElementById('panel').innerText.slice(0, 100)"))
        c.js("document.getElementById('showtag').click()")
        time.sleep(0.8)
        c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
        time.sleep(0.6)
        open_key(draw["key"])
        c.js("window.scrollTo(0, 0)")
        c.js("document.querySelector('#sctabs button[data-sctab=matches]').click()")
        time.sleep(1.2)
        m = c.js("(() => ({w: document.documentElement.scrollWidth, iw: innerWidth, tabs: [...document.querySelectorAll('#sctabs button')].map(b => Math.round(b.getBoundingClientRect().height)), "
                 "sel: Math.round(document.querySelector('#suggsec [data-sctl=member]').getBoundingClientRect().height), heads: [...document.querySelectorAll('.msec')].map(e => Math.round(e.getBoundingClientRect().width))}))()")
        check("11 390 px: no sideways scroll (%d <= %d), tabs and the group picker at least 44 px tall, section heads fit" % (m["w"], m["iw"]), m["w"] <= m["iw"] and all(h >= 44 for h in m["tabs"]) and m["sel"] >= 44 and all(w <= m["iw"] for w in m["heads"]), m)
        c.call("Emulation.clearDeviceMetricsOverride")
        after = [sha(p) for p in PROTECTED]
        check("12 the real corrections files (and the alias, description and merge files) are byte-identical before and after: every hand edit went to a temporary copy", before == after)
    finally:
        edge.terminate()
        for s_ in srvs:
            s_.shutdown()
    bad = [n for n, ok in results if not ok]
    print("\n%d checks, %d failed" % (len(results), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
