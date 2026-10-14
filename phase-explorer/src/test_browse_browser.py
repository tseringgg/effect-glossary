#!/usr/bin/env python3
"""Drive reports/browse.html in headless Edge through the DevTools protocol: real clicks and typing.

    python src/test_browse_browser.py

Starts a local HTTP server and headless Edge (needs msedge.exe and `pip install websocket-client`), loads the
page, and exercises:
  1  page boots: both coverage figures and their bases are in the header
  2  tree: click a family, then a node, then a leaf: the card list for that leaf appears, each card showing the text
     of the ability that put it there, with the leaf name in the heading
  3  a card row's "Also in" link opens another leaf
  4  clicking a card name expands its detail (rules text and abilities)
  5  a roll-up ("Other: ...") opens and lists cards under small groups
  6  a broad-group leaf shows its plain-language note
  7  a "Not yet organized" group opens and lists cards, and "Show more" adds cards
  8  Find a card: typing a name shows the plain-language answer; clicking its group link opens the group
  9  the keyword block and the replacement block open
 10 a leaf deep link (#l:<id>) opens directly
 11 sign leaves: a boost leaf and a shrink leaf open as separate, correctly named groups
 12 dev-only links are hidden by default and shown with ?dev=1
 13 ledger.html and card-explorer.html show the dev-only banner
Not covered here (nothing can check them in a headless run): layout on small screens, dark/light theme switching by
the OS, scrolling performance. Screenshots are written next to the report's scratch dir if SHOTS is set.
"""
import base64
import http.server
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import websocket

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT_HTTP, PORT_CDP = 8791, 9333
SHOTS = os.environ.get("SHOTS")


class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def log_message(self, *a):
        pass


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=60, suppress_origin=True)
        self.n = 0

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})

    def js(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", str(r["exceptionDetails"])))
        return r["result"].get("value")

    def wait(self, expr, secs=40):
        t = time.time()
        while time.time() - t < secs:
            try:
                if self.js(expr):
                    return True
            except Exception:
                pass
            time.sleep(0.25)
        return False


def main():
    class Quiet(socketserver.TCPServer):
        def handle_error(self, *a):          # Edge closes connections mid-download; not an error here
            pass
    srv = Quiet(("127.0.0.1", PORT_HTTP), Q)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    prof = tempfile.mkdtemp()
    edge = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + prof,
                             "--remote-debugging-port=%d" % PORT_CDP, "--remote-allow-origins=*", "--window-size=1400,1000",
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))
        print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)) if detail else ""))
    try:
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT_CDP))
                break
            except Exception:
                time.sleep(0.5)
        page = next(t for t in tabs if t["type"] == "page")
        c = CDP(page["webSocketDebuggerUrl"])
        c.call("Page.enable")
        errors = []
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % PORT_HTTP)
        ok = c.wait("document.querySelectorAll('#tree .row').length > 10")
        check("1 boots: tree rows present", ok, c.js("document.querySelectorAll('#tree .row').length"))
        cov = c.js("document.getElementById('cov').innerText")
        check("1 header shows both figures and bases", "Basis:" in cov and cov.count("Basis:") >= 2 and "%" in cov, cov[:120].replace("\n", " "))
        prov = c.js("document.getElementById('prov').innerText")
        check("1 header shows snapshot and provenance", "Snapshot:" in prov and "build_ability_taxonomy" in prov, prov[:80])
        # 2 family -> node -> leaf
        c.js("document.querySelector('#tree .row[data-k^=\"f:\"]').click()")
        c.wait("document.querySelectorAll('#tree .row.l2').length > 0")
        c.js("document.querySelector('#tree .row.l2').click()")
        c.wait("document.querySelectorAll('#tree .row.l3').length > 0")
        leaf_label = c.js("document.querySelector('#tree .row.l3 span').innerText")
        c.js("[...document.querySelectorAll('#tree .row.l3')].find(r => r.dataset.k.startsWith('l:')).click()")
        ok = c.wait("document.querySelectorAll('#list .card').length > 3")
        check("2 leaf opens with cards", ok, c.js("document.querySelector('#panel h2') && document.querySelector('#panel h2').innerText"))
        has_text = c.js("[...document.querySelectorAll('#list .card')].slice(0,10).every(x => x.querySelector('.ab .why') && x.querySelector('.ab .why').innerText.length > 3)")
        check("2 each card shows its matching ability text", has_text)
        if SHOTS:
            open(os.path.join(SHOTS, "browser_leaf.png"), "wb").write(base64.b64decode(c.call("Page.captureScreenshot", format="png")["data"]))
        # 3 also-in link
        link = c.js("(() => { const a = document.querySelector('#list .also .lnk'); return a ? a.dataset.go : null })()")
        if link:
            first = c.js("document.querySelector('#panel h2').innerText")
            c.js("document.querySelector('#list .also .lnk').click()")
            c.wait("document.querySelector('#panel h2') && document.querySelector('#panel h2').innerText !== %s" % json.dumps(first))
            check("3 'Also in' link opens another leaf", c.js("document.querySelector('#panel h2').innerText") != first,
                  c.js("document.querySelector('#panel h2').innerText"))
        else:
            check("3 'Also in' link present on a card", False, "no card in the first leaf had one")
        # 4 card detail
        c.js("document.querySelector('#list .card .top').click()")
        check("4 card detail expands with rules text", c.wait("(() => { const d = document.querySelector('#list .card .det'); return d && !d.hidden && d.innerText.length > 10 })()"))
        # 5 roll-up
        c.js("location.hash=''")
        ru = c.js("(() => { const n = TAX.families.flatMap(f => f.nodes).find(n => n.rolled.length); return n.id })()")
        c.js("show('r:%s')" % ru)
        check("5 roll-up lists cards under small groups", c.wait("document.querySelectorAll('#list .card').length > 0 && document.querySelectorAll('#list .subhead').length > 0"))
        # 6 broad leaf note
        bl = c.js("Object.keys(TAX.leaves).find(k => TAX.leaves[k].flags.length && TAX.leaves[k].visible)")
        c.js("show('l:%s')" % bl)
        check("6 broad-group leaf shows its note", c.wait("document.querySelector('#panel .note') && document.querySelector('#panel .note').innerText.includes('broader than it looks')"),
              c.js("document.querySelector('#panel h2').innerText"))
        # 7 unorganized + show more
        c.js("document.querySelector('#tree .row[data-k=\"u:1\"]').click()")
        check("7 'Not yet organized' group lists cards", c.wait("document.querySelectorAll('#list .card').length > 50"))
        n0 = c.js("document.querySelectorAll('#list .card').length")
        c.js("document.querySelector('button.morebtn').click()")
        check("7 'Show more' adds cards", c.wait("document.querySelectorAll('#list .card').length > %d" % n0), "%d -> %s" % (n0, c.js("document.querySelectorAll('#list .card').length")))
        # 8 find a card, typed with real key events
        c.js("document.getElementById('q').focus()")
        for ch in "Mulldrifter":
            c.call("Input.dispatchKeyEvent", type="keyDown", text=ch, key=ch)
            c.call("Input.dispatchKeyEvent", type="keyUp", key=ch)
        check("8 typing in Find shows an answer", c.wait("document.querySelector('#findres .fr') && document.querySelector('#findres').innerText.includes('Mulldrifter')", 90),
              (c.js("document.getElementById('findres').innerText") or "")[:160].replace("\n", " "))
        check("8 answer names the broad-group reason", "broader than it looks" in (c.js("document.getElementById('findres').innerText") or ""))
        c.js("document.querySelector('#findres .lnk').click()")
        check("8 clicking the answer's group link opens that group", c.wait("document.querySelectorAll('#list .card').length > 0"),
              c.js("document.querySelector('#panel h2').innerText"))
        # 9 blocks
        c.js("document.querySelector('#tree .row[data-k=\"K\"]').click()")
        c.js("document.querySelector('#tree .row[data-k^=\"kb:\"]').click()")
        c.js("document.querySelector('#tree .row[data-k^=\"kl:\"]').click()")
        check("9 keyword block opens to a leaf of cards", c.wait("document.querySelectorAll('#list .card').length > 0"))
        c.js("show('G')") if False else None
        c.js("document.querySelector('#tree .row[data-k=\"G\"]').click()")
        c.js("document.querySelector('#tree .row[data-k^=\"gb:\"]').click()")
        c.js("document.querySelector('#tree .row[data-k^=\"gl:\"]').click()")
        check("9 replacement block opens to a leaf of cards", c.wait("document.querySelectorAll('#list .card').length > 0"))
        # 10 deep link
        lid = c.js("Object.keys(TAX.leaves).find(k => TAX.leaves[k].visible && !TAX.leaves[k].flags.length)")
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html#l:%s" % (PORT_HTTP, lid))
        check("10 deep link opens a leaf directly", c.wait("document.querySelectorAll('#list .card').length > 0"))
        # 11 sign leaves separate boosts from shrinks
        sl = c.js("(() => { const L = TAX.leaves; return [Object.keys(L).find(k => L[k].sig.includes('sign=boost') && L[k].abilities > 100), Object.keys(L).find(k => L[k].sig.includes('sign=shrink') && L[k].abilities > 50)] })()")
        res = []
        for lid_ in sl:
            c.js("show('l:%s')" % lid_)
            c.wait("document.querySelectorAll('#list .card').length > 0")
            res.append(c.js("document.querySelector('#panel h2').innerText"))
        check("11 boost and shrink leaves are separate groups with their own names",
              len(set(res)) == 2 and "+N/+N" in res[0] and "−N/−N" in res[1], " | ".join(res))
        # 12 dev-only links: hidden by default, visible with ?dev=1
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % PORT_HTTP)
        c.wait("document.querySelectorAll('#tree .row').length > 10")
        hid = c.js("getComputedStyle(document.querySelector('.devonly')).display")
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html?dev=1" % PORT_HTTP)
        c.wait("document.querySelectorAll('#tree .row').length > 10")
        vis = c.js("getComputedStyle(document.querySelector('.devonly')).display")
        check("12 dev links hidden by default and shown with ?dev=1", hid == "none" and vis != "none", "%s / %s" % (hid, vis))
        # 13 the two archived-view pages carry the dev-only banner
        for pg in ("ledger", "card-explorer"):
            c.call("Page.navigate", url="http://127.0.0.1:%d/reports/%s.html" % (PORT_HTTP, pg))
            ok = c.wait("document.getElementById('dev-only-banner') && document.getElementById('dev-only-banner').innerText.includes('archived card-level view')")
            check("13 %s.html shows the dev-only banner" % pg, ok)
        # 14 a node closes on a second click (it used to re-open itself)
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % PORT_HTTP)
        c.wait("document.querySelectorAll('#tree .row').length > 10")
        c.js("document.querySelector('#tree .row[data-k^=\"f:\"]').click()")
        c.wait("document.querySelectorAll('#tree .row.l2').length > 0")
        c.js("document.querySelector('#tree .row.l2').click()")
        opened = c.wait("document.querySelectorAll('#tree .row.l3').length > 0")
        c.js("document.querySelector('#tree .row.l2').click()")
        closed = c.wait("document.querySelectorAll('#tree .row.l3').length === 0")
        arrow = c.js("document.querySelector('#tree .row.l2 .tw').innerText")
        check("14 a node opens and then closes on the next click", opened and closed and arrow == "\u25b8", "opened=%s closed=%s arrow=%s" % (opened, closed, arrow))
        # 15 Cards mode: tab, typed filter, card page, group link
        c.js("document.querySelector('#tabs button[data-mode=\"cards\"]').click()")
        check("15 Cards tab shows the filters and a card list", c.wait("!document.getElementById('cardf').hidden && document.getElementById('tree').hidden && document.querySelectorAll('#list .crow').length > 100", 90),
              c.js("document.getElementById('cfcount').innerText"))
        c.js("document.getElementById('cf-name').focus()")
        for ch in "Mulldrifter":
            c.call("Input.dispatchKeyEvent", type="keyDown", text=ch, key=ch)
            c.call("Input.dispatchKeyEvent", type="keyUp", key=ch)
        check("15 typing a name narrows the list", c.wait("document.querySelectorAll('#list .crow').length >= 1 && document.querySelectorAll('#list .crow').length < 5 && document.querySelector('#list .crow').innerText.includes('Mulldrifter')", 60),
              c.js("document.getElementById('cfcount').innerText"))
        c.js("document.querySelector('#list .crow').click()")
        check("15 clicking a card opens its page with rules text, status and a way back",
              c.wait("!!(document.querySelector('.cardpage h2') && document.querySelector('.cardpage h2').innerText.includes('Mulldrifter') && document.querySelector('.cardpage .rt') && document.querySelector('.cardpage [data-go=\"C:\"]'))"),
              (c.js("document.querySelector('.cardpage') && document.querySelector('.cardpage').innerText") or "")[:140].replace("\n", " "))
        c.js("document.querySelector('.cardpage li .lnk').click()")
        check("15 a group link on the card page opens that group", c.wait("document.querySelectorAll('#list .card').length > 0"), c.js("document.querySelector('#panel h2').innerText"))
        # status filter
        c.js("(() => { const s = document.getElementById('cf-st'); document.getElementById('cf-name').value = ''; s.value = 'k'; s.dispatchEvent(new Event('input', { bubbles: true })); show('C:') })()")
        check("15 the status filter keeps only that kind of card", c.wait("document.querySelectorAll('#list .crow').length > 20 && [...document.querySelectorAll('#list .crow .badge')].every(b => b.innerText === 'keyword block')", 60),
              c.js("document.getElementById('cfcount').innerText"))
        # a leaf's card row links to the card page
        c.js("setMode('abilities'); show('l:' + Object.keys(TAX.leaves)[0])")
        c.wait("document.querySelectorAll('#list .card').length > 0")
        c.js("document.querySelector('#list .card .top [data-go^=\"c:\"]').click()")
        check("15 a card row in a group opens the card page", c.wait("!!document.querySelector('.cardpage h2')"), c.js("document.querySelector('.cardpage h2') && document.querySelector('.cardpage h2').innerText"))
        # 16 deep link to the cards list; dev-only parsed structure
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % PORT_HTTP + "#C%3A")
        check("16 a link to the card list (#C:) opens Cards mode", c.wait("!document.getElementById('cardf').hidden && document.querySelectorAll('#list .crow').length > 100", 90))
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html?dev=1" % PORT_HTTP)
        c.wait("document.querySelectorAll('#tree .row').length > 10")
        oid = c.js("(async () => { await needLookup(); return LOOK.entries.find(e => e[1] === 'Mulldrifter')[0] })()")
        c.js("show('c:%s')" % oid)
        c.wait("!!document.querySelector('.psbtn')")
        c.js("document.querySelector('.psbtn').click()")
        check("16 dev: parsed structure loads on demand", c.wait("document.querySelector('.psout') && document.querySelector('.psout').innerText.includes('abilities')", 60))
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % PORT_HTTP)
        c.wait("document.querySelectorAll('#tree .row').length > 10")
        c.js("show('c:%s')" % oid)
        c.wait("!!document.querySelector('.cardpage h2')")
        check("16 the parsed-structure button is dev-only", c.js("document.querySelector('.psbtn')") is None)
        # 17 card images view of a group (the picture index is read from build/card_images.json; pictures themselves come from Scryfall,
        # so this checks the tile, its source address and the click behaviour, not that the network delivered the files)
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % PORT_HTTP)
        c.wait("document.querySelectorAll('#tree .row').length > 10")
        c.js("show('l:' + Object.keys(TAX.leaves).find(k => TAX.leaves[k].cards > 200 && !TAX.leaves[k].flags.length))")
        c.wait("document.querySelectorAll('#list .card').length > 3")
        check("17 a group offers a text / card images switch", c.js("document.querySelectorAll('.viewbar .vbtn').length") == 2)
        c.js("document.querySelector('.viewbar [data-view=\"images\"]').click()")
        check("17 card images view shows a grid of tiles", c.wait("document.querySelectorAll('#list.grid .tile').length > 20", 60),
              c.js("document.querySelectorAll('#list.grid .tile').length"))
        src = c.js("(document.querySelector('#list.grid .tile img') || {}).src") or ""
        check("17 a tile's picture comes from the picture index", src.startswith("https://cards.scryfall.io/normal/front/"), src[:80])
        check("17 the page says pictures come from Scryfall", "Scryfall" in (c.js("document.getElementById('viewnote').innerText") or ""))
        c.js("document.querySelector('#list.grid .tile').click()")
        check("17 clicking a tile shows the ability text and rules text under it", c.wait("!!(document.querySelector('#list .tiledet .why') && document.querySelector('#list .tiledet .rt'))"))
        c.js("document.querySelector('#list.grid .tile').click()")
        check("17 clicking the tile again closes it", c.wait("document.querySelectorAll('#list .tiledet').length === 0"))
        c.js("document.querySelector('.viewbar [data-view=\"text\"]').click()")
        check("17 switching back shows the text list", c.wait("document.querySelectorAll('#list .card').length > 3 && !document.querySelector('#list.grid')"))
        c.js("show('C:')")
        c.wait("document.querySelectorAll('#list .crow').length > 100", 90)
        c.js("document.querySelector('.viewbar [data-view=\"images\"]').click()")
        check("17 the card list can also be shown as pictures", c.wait("document.querySelectorAll('#list.grid .tile').length > 20", 60))
        # 18 "hide cards with no picture": on by default, and it works in lists, in the card list and in the picture view
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % PORT_HTTP)
        c.wait("document.querySelectorAll('#tree .row').length > 10")
        check("18 the hide-no-picture switch is on by default", c.js("document.getElementById('hidenopic').checked") is True)
        c.js("setMode('cards', true); show('C:')")
        c.wait("document.querySelectorAll('#list .crow').length > 100", 90)
        c.js("(() => { const i = document.getElementById('cf-name'); i.value = 'Wheel of Not Ideal'; i.dispatchEvent(new Event('input', { bubbles: true })) })()")
        check("18 a card with no picture is hidden from the card list", c.wait("document.getElementById('cfcount').innerText.startsWith('0 of') && document.querySelectorAll('#list .crow').length === 0", 30),
              c.js("document.getElementById('cfcount').innerText"))
        c.js("document.getElementById('hidenopic').click()")
        check("18 unticking the switch lists it again", c.wait("document.querySelectorAll('#list .crow').length === 1 && document.querySelector('#list .crow').innerText.includes('Wheel of Not Ideal')", 30))
        c.js("document.getElementById('hidenopic').click()")
        c.wait("document.querySelectorAll('#list .crow').length === 0")
        c.js("(() => { document.getElementById('cf-name').value = ''; show('C:') })()")
        c.wait("document.querySelectorAll('#list .crow').length > 100", 90)
        c.js("document.querySelector('.viewbar [data-view=\"images\"]').click()")
        c.wait("document.querySelectorAll('#list.grid .tile').length > 20", 60)
        check("18 the picture view never shows a tile without a picture while the switch is on", c.js("document.querySelectorAll('#list.grid .noimg').length") == 0
              and c.js("document.querySelectorAll('#list.grid .tile img').length") == c.js("document.querySelectorAll('#list.grid .tile').length"))
        # 19 the not-for-constructed cards are out of the card set (out_of_scope); there is no switch for them any more
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % PORT_HTTP)
        c.wait("document.querySelectorAll('#tree .row').length > 10")
        check("19 there is no not-for-constructed switch", c.js("document.getElementById('hidenc')") is None)
        check("19 the picture switch is still there and on", c.js("document.getElementById('hidenopic').checked") is True)
        c.wait("typeof CARDS !== 'undefined' && !!CARDS && !!FLAGS", 120)
        got = c.js("""(() => { const by = n => Object.keys(FLAGS.cards).find(o => FLAGS.evidence[o].name === n);
          return ['Abbot of the Sacred Meeple', 'Bolshack Dragon', 'Boltfire', 'Bounce Chamber', 'Rikala, Homarid King'].map(n => { const o = by(n); return !!o && !!CARDS[o] }) })()""")
        check("19 the test cards are no longer in the card set; Bounce Chamber (legal in Commander) was never flagged", got == [False, False, False, False, False], str(got))
        in_cards = c.js("(() => { const n = ['Bounce Chamber', 'Rikala, Homarid King']; return n.map(x => Object.values(CARDS).some(v => v.n === x)) })()")
        check("19 Bounce Chamber and Rikala are in the card set", in_cards == [True, True], str(in_cards))
        # 20 the 'Left out' section under 'Not yet organized'
        check("20 the section appears in the tree", c.wait("!!document.querySelector('#tree .row[data-k=\"N:all\"]')", 60))
        n_tree = c.js("+document.querySelector('#tree .row[data-k=\"N:all\"] .n').innerText.replace(/,/g, '')")
        check("20 it has a row per reason", c.js("[...document.querySelectorAll('#tree .row')].filter(r => r.dataset.k.startsWith('N:')).length") >= 5)
        c.js("document.querySelector('#tree .row[data-k=\"N:all\"]').click()")
        c.wait("document.querySelectorAll('#list .card').length > 50", 60)
        listed = c.js("document.querySelector('#panel .sub').innerText")
        check("20 it lists every left-out card, with its reason and where it was printed", ("%s cards" % format(n_tree, ",")) in listed and n_tree == 1464
              and c.js("[...document.querySelectorAll('#list .card')].slice(0, 20).every(x => x.innerText.includes('Printed only in'))") is True, listed[:80])
        check("20 a reason row opens only its own cards", c.js("(() => { show('N:playtest_card'); return true })()") and c.wait("document.querySelector('#panel h2').innerText.includes('Playtest card') && document.querySelectorAll('#list .card').length > 50", 60))
        # 21 headline is on the constructed-only card set
        cov = c.js("document.getElementById('cov').innerText")
        check("21 the header gives the constructed-only figures and bases", "33,183" in cov and "Basis:" in cov, cov[:120].replace("\n", " "))
        # 22 gap cards whose abilities are placed: the gap stays visible as plain card detail
        gc = c.js("(() => { const o = Object.keys(CARDS).find(k => CARDS[k].g && CARDS[k].g.length && CARDS[k].ab.some(a => a[2] === 'p')); return o })()")
        check("22 some placed cards carry the part the parser did not read", bool(gc))
        c.js("show('c:%s')" % gc)
        check("22 the card page says what was not read, and the cards ability is in a group",
              c.wait("!!(document.querySelector('.cardpage .gap') && document.querySelector('.cardpage .gap').innerText.includes('did not read'))", 60)
              and c.js("document.querySelector('.cardpage li.st-p') !== null") is True)
        gl = c.js("Object.keys(TAX.leaves).find(k => TAX.leaves[k].gap_abilities > 0)")
        c.js("show('l:%s')" % gl)
        check("22 a group says how many of its abilities came from cards with an unread part", c.wait("document.querySelector('#panel .sub') && document.querySelector('#panel .sub').innerText.includes('placed from cards with a part the parser did not read')", 60))
        # 23 the loosely grouped layer and the "couldn't read yet" list
        c.js("location.hash=''")
        check("23 the tree has the loosely grouped section, labeled not checked", c.wait("!!document.querySelector('#tree .row[data-k=\"LG:\"]')", 60)
              and "not checked" in c.js("[...document.querySelectorAll('#tree .blk')].map(x => x.innerText).join('|')").lower())
        check("23 it has a 'Cards we couldn't read yet' row", c.js("!!document.querySelector('#tree .row[data-k=\"UR:\"]')") is True)
        c.js("document.querySelector('#tree .row[data-k=\"LG:\"]').click()")
        check("23 the section opens to families and says it is not organized", c.wait("document.querySelectorAll('#tree .row[data-k^=\"lf:\"]').length > 10")
              and "Not checked for accuracy" in c.js("document.querySelector('#panel').innerText"), c.js("document.querySelector('#panel').innerText.slice(0, 160)"))
        c.js("document.querySelector('#tree .row[data-k^=\"lf:\"]').click()")
        check("23 a family opens to groups", c.wait("document.querySelectorAll('#tree .row[data-k^=\"lg:\"]').length > 0"))
        c.js("document.querySelector('#tree .row[data-k^=\"lg:\"]').click()")
        check("23 a loose group lists cards, each with its text and why it is not a real placement",
              c.wait("document.querySelectorAll('#list .card').length > 3") and c.js("[...document.querySelectorAll('#list .card')].slice(0, 10).every(x => x.innerText.includes('Not a real placement because'))") is True,
              c.js("document.querySelector('#panel h2').innerText"))
        check("23 the group heading carries the label", "Not checked for accuracy" in c.js("document.querySelector('#panel').innerText"))
        bk = c.js("Object.keys(LOOSE.groups).find(g => LOOSE.groups[g].kind === 'bucket' && LOOSE.groups[g].subs.length >= 3)")
        c.js("show('lg:%s')" % bk)
        check("23 a bucket shows its kinds as headings with counts", c.wait("document.querySelectorAll('#list .subhead').length >= 2") and c.js("document.querySelector('#panel .note').innerText.length") > 20)
        ca = c.js("Object.keys(LOOSE.groups).find(g => LOOSE.groups[g].kind === 'catchall')")
        c.js("show('lg:%s')" % ca)
        check("23 a catch-all group shows its kinds as headings", c.wait("document.querySelectorAll('#list .subhead').length >= 3"), c.js("document.querySelector('#panel h2').innerText"))
        c.js("document.querySelector('#tree .row[data-k=\"UR:\"]').click()")
        check("23 the couldn't-read list shows a reason on every row", c.wait("document.querySelectorAll('#list .card').length > 10")
              and c.js("[...document.querySelectorAll('#list .card')].slice(0, 20).every(x => x.innerText.includes('Why:'))") is True)
        first = c.js("UNREAD.rows[0][1]")
        check("23 the list is sorted by popularity", c.js("UNREAD.rows.slice(0, 200).every((r, i, a) => i === 0 || (r[1] != null && a[i - 1][1] != null && r[1] >= a[i - 1][1]))") is True, str(first))
        # the headline did not move
        cov = c.js("document.getElementById('cov').innerText")
        check("23 the headline is unchanged by the layer", "24,336 of 33,183" in cov and "73.3%" in cov and "27,590" in cov and "83.1%" in cov, cov[:150].replace("\n", " "))
        check("23 the tree still counts every pile card once", c.js("TAX.totals.not_yet_organized") == 5593 and c.js("LOOSE.meta.cards_with_a_group + LOOSE.meta.cards_not_read") == 5593)
        # 24 Find a card for loose-group cards, no-family cards, placed cards and left-out cards
        picks = c.js("""(() => {
          const pick = (arr, n) => { const out = []; for (let i = 1; out.length < n && i < arr.length; i++) { const k = arr[Math.floor(arr.length * i / (n + 1))]; out.push(k); } return out; };
          const ok = o => CARDS[o] && /^[A-Za-z' ,-]+$/.test(CARDS[o].n);
          const loose = Object.keys(LOOSE.by_card).filter(ok).sort();
          const unread = UNREAD.rows.map(r => r[0]).filter(ok).sort();
          const placed = Object.keys(CARDS).filter(o => ok(o) && CARDS[o].ab.some(a => a[2] === 'p') && !LOOSE.by_card[o]).sort();
          const left = Object.keys(FLAGS.cards).filter(o => FLAGS.evidence[o] && FLAGS.evidence[o].in_card_set === false || true).sort();
          return {loose: pick(loose, 5).map(o => CARDS[o].n), unread: pick(unread, 5).map(o => CARDS[o].n), placed: pick(placed, 5).map(o => CARDS[o].n),
                  left: pick(left, 3).map(o => FLAGS.evidence[o].name)};
        })()""")
        def ask(name):
            return c.js("""(async () => { document.getElementById('q').value = %s; await find(%s);
              const want = %s.toLowerCase(); const frs = [...document.querySelectorAll('#findres .fr')];
              const fr = frs.find(f => f.querySelector('.nm').innerText.toLowerCase() === want) || frs[0];
              return fr ? {text: fr.innerText, lg: fr.querySelectorAll('[data-go^=\"lg:\"]').length, ur: fr.querySelectorAll('[data-go=\"UR:\"]').length, n: frs.length} : null })()""" % (json.dumps(name), json.dumps(name), json.dumps(name)))
        for nm in picks["loose"]:
            a = ask(nm)
            check("24 Find a card: %s resolves to its loose groups with the label" % nm, bool(a) and a["lg"] >= 1 and "Not checked for accuracy" in a["text"] and "not yet organized" in a["text"].lower(), str(a)[:140])
        for nm in picks["unread"]:
            a = ask(nm)
            check("24 Find a card: %s resolves to the couldn't-read-yet list" % nm, bool(a) and a["ur"] == 1 and a["lg"] == 0, str(a)[:140])
        for nm in picks["placed"]:
            a = ask(nm)
            check("24 Find a card: placed card %s shows no loose-group text" % nm, bool(a) and a["lg"] == 0 and a["ur"] == 0 and "Not checked" not in a["text"], str(a)[:140])
        for nm in picks["left"]:
            a = ask(nm)
            check("24 Find a card: left-out card %s is answered, with no loose-group text" % nm, bool(a) and a["lg"] == 0 and a["ur"] == 0, str(a)[:140])
        # a chip from Find a card opens the group
        a = ask(picks["loose"][0])
        c.js("document.querySelector('#findres .fr [data-go^=\"lg:\"]').click()")
        check("24 a loose-group link in Find a card opens that group", c.wait("document.querySelectorAll('#list .card').length > 0 && !!document.querySelector('#panel .loosehead')"),
              str(c.js("[document.querySelector('#panel h2') && document.querySelector('#panel h2').innerText, document.querySelectorAll('#list .card').length, location.hash]")))
        c.js("show('c:' + Object.keys(LOOSE.by_card)[0])")
        check("24 the card page of a loose-group card links its groups", c.wait("document.querySelectorAll('.cardpage .loosenote [data-go^=\"lg:\"]').length >= 1", 60))
        c.js("show('c:' + UNREAD.rows[0][0])")
        check("24 the card page of a no-family card links the couldn't-read-yet list", c.wait("!!document.querySelector('.cardpage .loosenote [data-go=\"UR:\"]')", 60))
        # 25 the hide switch drops the layer's counts too
        c.js("document.getElementById('hidenopic').checked = false; document.getElementById('hidenopic').dispatchEvent(new Event('change'))")
        n_off = c.js("lAllN()")
        c.js("document.getElementById('hidenopic').checked = true; document.getElementById('hidenopic').dispatchEvent(new Event('change'))")
        n_on = c.js("lAllN()")
        check("25 hidden (no-picture) cards drop out of the layer's counts, and come back when the switch is off", n_on < n_off and n_off == c.js("LOOSE.meta.cards_with_a_group"), "%s -> %s" % (n_off, n_on))
        # 26 the tentative layer
        TM = json.load(open(os.path.join(HERE, 'build', 'tentative_placements.json'), encoding='utf-8'))['meta']
        c.js("location.hash=''")
        c.wait("!!document.getElementById('showtent')", 60)
        c.wait("document.getElementById('cov').innerText.includes('counting tentative placements')", 60)
        # sections 26-28 were written before the condition annotations: run them with the annotation switch off (section 29 covers it)
        c.js("document.getElementById('showann').checked = false; document.getElementById('showann').dispatchEvent(new Event('change'))")
        c.js("document.getElementById('showtag').checked = false; document.getElementById('showtag').dispatchEvent(new Event('change'))")
        check("26 the switch is on by default", c.js("document.getElementById('showtent').checked") is True)
        check("26 the header gives three figures with bases, the precise and broad ones unchanged",
              c.wait("document.getElementById('cov').innerText.includes('counting tentative placements')", 60)
              and all(x in c.js("document.getElementById('cov').innerText") for x in ("24,336 of 33,183", "73.3%", "27,590", "83.1%", format(TM["headline"]["with_tentative"][0], ","), str(TM["headline"]["with_tentative"][1]) + "%")), c.js("document.getElementById('cov').innerText")[:400].replace("\n", " "))
        check("26 the pile shown is the build's pile minus the tentative cards", ("Not yet organized: " + format(TM["still_unorganized"], ",")) in c.js("document.getElementById('cov').innerText") and ("tentatively placed: " + format(TM["cards"], ",")) in c.js("document.getElementById('cov').innerText"))
        fam = c.js("TENT.families[0].key")
        c.js("(() => { open.add('f:%s'); renderTree(); return true })()" % fam)
        check("26 a family has a Tentative groups row with the tentative badge", c.wait("!!document.querySelector('#tree .row[data-k=\"tf:%s\"] .b-tent')" % fam))
        c.js("document.querySelector('#tree .row[data-k=\"tf:%s\"]').click()" % fam)
        check("26 it opens to tentative groups, each badged", c.wait("document.querySelectorAll('#tree .row[data-k^=\"tg:\"] .b-tent').length > 0")
              and "Tentative placement: grouped by effect type, not fully checked." in c.js("document.getElementById('panel').innerText"))
        c.js("document.querySelector('#tree .row[data-k^=\"tg:\"]').click()")
        check("26 a tentative group lists cards with the text and why it is not a real placement",
              c.wait("document.querySelectorAll('#list .card').length > 3") and c.js("[...document.querySelectorAll('#list .card')].slice(0, 10).every(x => x.innerText.includes('Not a real placement because'))") is True
              and "Not counted in the precise or the broad figure" in c.js("document.getElementById('panel').innerText"))
        gu = c.js("(() => { const g = Object.keys(TENT.groups).find(k => TENT.groups[k].m.some(r => TENT.meta.reasons[r[2]] === 'part of the ability was not read')); return g })()")
        c.js("show('tg:%s')" % gu)
        check("26 an unread-part row says part of the ability was not read", c.wait("document.querySelectorAll('#list .card').length > 0") and
              c.js("[...document.querySelectorAll('#list .card')].some(x => x.innerText.includes('part of the ability was not read'))") is True)
        check("26 no gap-test failure is placed", c.js("TENT.meta.rules.hold_gap_test_failures") is True and c.js("!TENT.meta.reasons.some(r => r.includes('unread clause') || r.includes('no rules text of its own'))") is True)
        # reconciliation, from the data the page holds
        tot = c.js("(() => { const v = TAX.totals.views; return [v.placed + v.broad_only + v.keyword_block + v.no_abilities + v.replacement_group, TENT.meta.cards, TAX.totals.not_yet_organized - TENT.meta.cards, v.not_a_card, TAX.totals.universe] })()")
        check("26 placed + tentative + still unorganized + not cards = 38,921", sum(tot[:4]) == tot[4] == 38921, str(tot))
        # u: lists lose the tentative cards
        c.js("show('u:2')")
        n_on = c.js("(c => c)(document.querySelector('#panel .sub').innerText)")
        check("26 the Not-yet-organized lists leave the tentative cards out", c.wait("document.querySelectorAll('#list .card').length > 3") and "tentatively placed" in n_on, n_on[:120])
        # the switch removes every tentative placement
        c.js("document.getElementById('showtent').checked = false; document.getElementById('showtent').dispatchEvent(new Event('change'))")
        check("26 switched off: no third figure, no tentative rows, the pile is back to 5,593",
              c.wait("!document.getElementById('cov').innerText.includes('counting tentative')") and "Not yet organized: 5,593" in c.js("document.getElementById('cov').innerText")
              and c.js("document.querySelectorAll('#tree .b-tent').length") == 0 and c.js("document.querySelectorAll('#tree .row[data-k^=\"tf:\"]').length") == 0)
        check("26 switched off: the headline's first two figures are unchanged", "24,336 of 33,183" in c.js("document.getElementById('cov').innerText") and "27,590" in c.js("document.getElementById('cov').innerText"))
        c.js("show('tg:%s')" % gu)
        check("26 switched off: a link to a tentative group says it is switched off", c.wait("document.getElementById('panel').innerText.includes('switched off')"))
        c.js("document.getElementById('showtent').checked = true; document.getElementById('showtent').dispatchEvent(new Event('change'))")
        check("26 switched on again: the third figure is back", c.wait("document.getElementById('cov').innerText.includes('counting tentative placements')"))
        # Find a card: 5 tentative, 5 loose-only, 5 placed, 3 excluded
        pk = c.js("""(() => {
          const pick = (arr, n) => { const out = []; for (let i = 1; out.length < n && i < arr.length; i++) out.push(arr[Math.floor(arr.length * i / (n + 1))]); return out; };
          const ok = o => CARDS[o] && /^[A-Za-z' ,-]+$/.test(CARDS[o].n);
          const tent = Object.keys(TENT.by_card).filter(ok).sort();
          const loose = Object.keys(LOOSE.by_card).filter(o => ok(o) && !TENT.by_card[o]).sort();
          const placed = Object.keys(CARDS).filter(o => ok(o) && CARDS[o].ab.some(a => a[2] === 'p') && !LOOSE.by_card[o]).sort();
          const left = Object.keys(FLAGS.cards).filter(o => FLAGS.evidence[o]).sort();
          return {tent: pick(tent, 5).map(o => CARDS[o].n), loose: pick(loose, 5).map(o => CARDS[o].n), placed: pick(placed, 5).map(o => CARDS[o].n), left: pick(left, 3).map(o => FLAGS.evidence[o].name)};
        })()""")

        def ask2(name):
            return c.js("""(async () => { document.getElementById('q').value = %s; await find(%s);
              const want = %s.toLowerCase(); const frs = [...document.querySelectorAll('#findres .fr')];
              const fr = frs.find(f => f.querySelector('.nm').innerText.toLowerCase() === want) || frs[0];
              return fr ? {text: fr.innerText, tg: fr.querySelectorAll('[data-go^=\\"tg:\\"]').length, lg: fr.querySelectorAll('[data-go^=\\"lg:\\"]').length, ur: fr.querySelectorAll('[data-go=\\"UR:\\"]').length} : null })()""" % (json.dumps(name), json.dumps(name), json.dumps(name)))
        for nm in pk["tent"]:
            a = ask2(nm)
            check("27 Find a card: tentative card %s names its tentative groups and says not fully checked" % nm, bool(a) and a["tg"] >= 1 and "not fully checked" in a["text"] and "Not counted in the precise or the broad figure" in a["text"], str(a)[:160])
        for nm in pk["loose"]:
            a = ask2(nm)
            check("27 Find a card: loose-only card %s has loose groups and no tentative group" % nm, bool(a) and a["lg"] >= 1 and a["tg"] == 0 and "Not checked for accuracy" in a["text"], str(a)[:160])
        for nm in pk["placed"]:
            a = ask2(nm)
            check("27 Find a card: placed card %s shows no loose or tentative text" % nm, bool(a) and a["lg"] == 0 and a["tg"] == 0 and a["ur"] == 0 and "tentative" not in a["text"].lower(), str(a)[:160])
        for nm in pk["left"]:
            a = ask2(nm)
            check("27 Find a card: left-out card %s is answered with no loose or tentative text" % nm, bool(a) and a["lg"] == 0 and a["tg"] == 0 and "tentative" not in a["text"].lower(), str(a)[:160])
        a = ask2(pk["tent"][0])
        c.js("document.querySelector('#findres .fr [data-go^=\"tg:\"]').click()")
        check("27 a tentative-group link in Find a card opens the group", c.wait("document.querySelectorAll('#list .card').length > 0 && !!document.querySelector('#panel .tentnote')"))
        c.js("show('c:' + Object.keys(TENT.by_card)[0])")
        check("27 the card page of a tentative card says so", c.wait("!!document.querySelector('.cardpage .loosenote .b-tent')", 60))
        c.js("show('C:')")
        c.wait("document.querySelectorAll('#list .crow').length > 5", 60)
        c.js("document.getElementById('cf-st').value = 't'; document.getElementById('cf-st').dispatchEvent(new Event('input', {bubbles: true}))")
        check("27 the Cards tab can filter tentatively placed cards", c.wait("document.getElementById('cfcount').innerText.startsWith('%s')" % format(TM['cards'] - 15, ',')[:3]), c.js("document.getElementById('cfcount').innerText"))
        # 28 the 2026-10 promotions: the renamed groups and the sub-heading groups
        check("28 the build says what the new promotions are and the unread-part switch is off by default",
              c.js("TENT.meta.rules.promote_renamed_groups && TENT.meta.rules.promote_subheadings && TENT.meta.rules.hold_unread_part_abilities === false") is True
              and c.js("TENT.meta.unread_part_off.cards") < c.js("TENT.meta.cards"))
        check("28 groups of the three kinds are present", c.js("[...new Set(Object.values(TENT.groups).map(g => g.origin.startsWith('sub-heading') ? 'sub-heading' : g.origin))].sort().join('|')") == "plain group|renamed group|sub-heading")
        check("28 the cards that only the new promotions reach number what the build says",
              c.js("Object.keys(TENT.by_card).filter(o => TENT.by_card[o].every(g => TENT.groups[g].origin !== 'plain group')).length") == TM["new_cards_from_the_2026_10_promotions"],
              str(c.js("Object.keys(TENT.by_card).filter(o => TENT.by_card[o].every(g => TENT.groups[g].origin !== 'plain group')).length")))
        newg = c.js("Object.keys(TENT.groups).find(g => TENT.groups[g].origin.startsWith('sub-heading'))")
        c.js("location.hash=''; show('tg:%s')" % newg)
        check("28 a sub-heading group opens as a tentative group with the badge, label and reasons",
              c.wait("document.querySelectorAll('#list .card').length > 3 && !!document.querySelector('#panel h2 .b-tent')") and "Tentative placement: grouped by effect type, not fully checked." in c.js("document.getElementById('panel').innerText")
              and c.js("[...document.querySelectorAll('#list .card')].every(x => x.innerText.includes('Not a real placement because'))") is True)
        rg = c.js("Object.keys(TENT.groups).find(g => TENT.groups[g].origin === 'renamed group')")
        c.js("show('tg:%s')" % rg)
        check("28 a renamed group opens too", c.wait("document.querySelectorAll('#list .card').length > 3 && !!document.querySelector('#panel h2 .b-tent')"), c.js("document.querySelector('#panel h2').innerText"))
        check("28 the as-long-as group claims no subject", "this permanent" not in " ".join(c.js("Object.values(TENT.groups).filter(g => g.name.includes('as long as')).map(g => g.name)")).lower())
        npk = c.js("""(() => {
          const ok = o => CARDS[o] && /^[A-Za-z' ,-]+$/.test(CARDS[o].n);
          const only = Object.keys(TENT.by_card).filter(o => ok(o) && TENT.by_card[o].every(g => TENT.groups[g].origin !== 'plain group')).sort();
          const out = []; for (let i = 1; out.length < 5 && i < only.length; i++) out.push(only[Math.floor(only.length * i / 6)]);
          return out.map(o => CARDS[o].n);
        })()""")
        for nm in npk:
            a = ask2(nm)
            check("28 Find a card: newly promoted card %s names its tentative groups" % nm, bool(a) and a["tg"] >= 1 and "not fully checked" in a["text"] and "Not counted in the precise or the broad figure" in a["text"], str(a)[:160])
        c.js("document.getElementById('showtent').checked = false; document.getElementById('showtent').dispatchEvent(new Event('change'))")
        check("28 switched off: the new groups disappear with the rest", c.wait("document.querySelectorAll('#tree .b-tent').length === 0") and "Not yet organized: 5,593" in c.js("document.getElementById('cov').innerText"))
        c.js("document.getElementById('showtent').checked = true; document.getElementById('showtent').dispatchEvent(new Event('change'))")
        check("28 switched on again", c.wait("document.getElementById('cov').innerText.includes('counting tentative placements')"))
        # 29 the condition annotations (abilities held for an unread condition; the gap-test stratum on its own line)
        AM = json.load(open(os.path.join(HERE, 'build', 'annotation_placements.json'), encoding='utf-8'))['meta']
        c.js("document.getElementById('showann').checked = true; document.getElementById('showann').dispatchEvent(new Event('change'))")
        check("29 the annotation switch is on by default (checkbox exists, labelled)", c.js("document.getElementById('showann').checked") is True and "Show condition annotations" in c.js("document.getElementById('showann').parentElement.innerText"))
        cov = c.js("document.getElementById('cov').innerText")
        hl = AM["headline"]
        check("29 the header gives the fourth figure with its basis, and the gap-test figure on its own line, the first three unchanged",
              c.wait("document.getElementById('cov').innerText.includes('condition annotations')", 60)
              and all(x in cov for x in ("24,336 of 33,183", "27,590", "29,683")) and (format(hl["with_annotation"][0], ",") + " of 33,183") in cov and (str(hl["with_annotation"][1]) + "%") in cov
              and (format(hl["with_gap_stratum"][0], ",") + " of 33,183") in cov and (str(hl["with_gap_stratum"][1]) + "%") in cov, cov[:700].replace("\n", " "))
        check("29 the fourth and the gap-test figures are separate lines (not blended)",
              c.js("[...document.querySelectorAll('#cov > div')].filter(d => d.innerText.includes('condition annotations') || d.innerText.includes('unread-part stratum')).length") == 2)
        check("29 the pile is the build's pile minus tentative and annotated; both annotated counts are named",
              ("Not yet organized: " + format(AM["still_unorganized_after_gap_stratum"], ",")) in cov and ("annotated: " + format(AM["condition_cards_new"], ",")) in cov and (format(AM["gap_cards_new"], ",") + " (card part not read)") in cov, cov[-420:].replace("\n", " "))
        tot = c.js("(() => { const v = TAX.totals.views; return [v.placed + v.broad_only + v.keyword_block + v.no_abilities + v.replacement_group, TENT.meta.cards, ANN.meta.condition_cards_new, ANN.meta.gap_cards_new, TAX.totals.not_yet_organized - TENT.meta.cards - ANN.meta.condition_cards_new - ANN.meta.gap_cards_new, v.not_a_card, TAX.totals.universe] })()")
        check("29 placed + tentative + annotated (both strata) + still unorganized + not cards = 38,921", sum(tot[:6]) == tot[6] == 38921, str(tot))
        fam = c.js("ANN.families[0].key")
        c.js("(() => { open.add('f:%s'); renderTree(); return true })()" % fam)
        check("29 a family has a Condition annotations row with its own badge", c.wait("!!document.querySelector('#tree .row[data-k=\"af:%s\"] .b-ann')" % fam))
        sty = c.js("""(() => { const m = document.querySelector('#tree .b-ann'); const t = document.querySelector('#tree .b-tent'); const a = document.querySelector('#tree .b-auto'); const b = document.querySelector('#tree .b-broad');
          const bs = e => e ? getComputedStyle(e).borderTopStyle : null; return [bs(m), bs(t), bs(a), bs(b), m.className, t ? t.className : null] })()""")
        check("29 the annotation badge is dotted and differs from the tentative (striped), broad and other badges", sty[0] == "dotted" and sty[0] not in (sty[1], sty[3]) , str(sty))
        c.js("document.querySelector('#tree .row[data-k=\"af:%s\"]').click()" % fam)
        check("29 the family row opens to annotation groups, each badged", c.wait("document.querySelectorAll('#tree .row[data-k^=\"ag:\"] .b-ann').length > 0"))
        kc = c.js("Object.keys(ANN.groups).find(k => ANN.groups[k].m.some(r => r[6] === 'c' && r[4] === 0))")
        c.js("show('ag:%s')" % kc)
        check("29 a group lists cards with the leaf's ability text, the badge and the unread condition, in the agreed wording",
              c.wait("document.querySelectorAll('#list .card').length > 0")
              and c.js("[...document.querySelectorAll('#list .card')].every(x => x.innerText.includes('Condition not read') && x.innerText.includes('This ability has a condition the tool did not read:') && x.innerText.includes('The condition may change what the ability does.'))") is True
              and "Not counted in the precise, with-broad or with-tentative figure" in c.js("document.getElementById('panel').innerText"))
        c.js("show('ag:%s')" % kc)
        check("29 the condition text on a row is a quote from that card's own oracle text",
              c.js("""(() => { const g = ANN.groups[%s]; return g.m.filter(r => r[6] === 'c').slice(0, 25).every(r => { const t = CARDS[r[0]].t.replace(/\\s+/g, ' '); const cl = r[2].replace(/[.]$/, ''); return t.includes(cl) || t.replace(CARDS[r[0]].n, '~').includes(cl) }) })()""" % json.dumps(kc)) is True)
        ko = c.js("Object.keys(ANN.groups).find(k => ANN.groups[k].m.some(r => r[4] === 2))")
        c.js("show('ag:%s')" % ko)
        check("29 an 'unless / if you don't' condition says it may change what the ability does, even to the opposite", c.wait("document.querySelectorAll('#list .card').length > 0") and "even to the opposite" in c.js("document.getElementById('list').innerText"))
        ki = c.js("Object.keys(ANN.groups).find(k => ANN.groups[k].m.some(r => r[4] === 1))")
        c.js("show('ag:%s')" % ki)
        check("29 an 'instead / otherwise' condition says it may make the ability do something else instead", c.wait("document.querySelectorAll('#list .card').length > 0") and "or make it do something else instead" in c.js("document.getElementById('list').innerText"))
        kg = c.js("Object.keys(ANN.groups).find(k => ANN.groups[k].m.some(r => r[6] === 'g'))")
        c.js("show('ag:%s')" % kg)
        check("29 a gap-test group row says the ability was read and another part of the card was not, with the unread text",
              c.wait("document.querySelectorAll('#list .card').length > 0") and "Card part not read" in c.js("document.getElementById('list').innerText")
              and "This ability was read, but another part of this card was not:" in c.js("document.getElementById('list').innerText"))
        # Find a card: 5 annotated (condition stratum), 3 annotated (gap stratum), 5 tentative, 5 loose, 5 placed, 3 excluded
        pk2 = c.js("""(() => {
          const pick = (arr, n) => { const out = []; for (let i = 1; out.length < n && i < arr.length; i++) out.push(arr[Math.floor(arr.length * i / (n + 1))]); return out; };
          const ok = o => CARDS[o] && /^[A-Za-z' ,-]+$/.test(CARDS[o].n);
          const a1 = Object.keys(ANN.by_card).filter(o => ok(o) && ANN.cs[o] === 'c' && !TENT.by_card[o]).sort();
          const a2 = Object.keys(ANN.by_card).filter(o => ok(o) && ANN.cs[o] === 'g' && !TENT.by_card[o]).sort();
          const a3 = Object.keys(ANN.by_card).filter(o => ok(o) && TENT.by_card[o]).sort();
          const tent = Object.keys(TENT.by_card).filter(o => ok(o) && !ANN.by_card[o]).sort();
          const loose = Object.keys(LOOSE.by_card).filter(o => ok(o) && !TENT.by_card[o] && !ANN.by_card[o]).sort();
          const placed = Object.keys(CARDS).filter(o => ok(o) && CARDS[o].ab.some(a => a[2] === 'p') && !LOOSE.by_card[o]).sort();
          const left = Object.keys(FLAGS.cards).filter(o => FLAGS.evidence[o]).sort();
          return {ann: pick(a1, 5).map(o => CARDS[o].n), gap: pick(a2, 3).map(o => CARDS[o].n), both: pick(a3, 2).map(o => CARDS[o].n), tent: pick(tent, 5).map(o => CARDS[o].n), loose: pick(loose, 5).map(o => CARDS[o].n), placed: pick(placed, 5).map(o => CARDS[o].n), left: pick(left, 3).map(o => FLAGS.evidence[o].name)};
        })()""")

        def ask3(name):
            return c.js("""(async () => { document.getElementById('q').value = %s; await find(%s);
              const want = %s.toLowerCase(); const frs = [...document.querySelectorAll('#findres .fr')];
              const fr = frs.find(f => f.querySelector('.nm').innerText.toLowerCase() === want) || frs[0];
              return fr ? {text: fr.innerText, ann: fr.querySelectorAll('.b-ann').length, ag: fr.querySelectorAll('[data-go^=\\"ag:\\"]').length, tg: fr.querySelectorAll('[data-go^=\\"tg:\\"]').length, lg: fr.querySelectorAll('[data-go^=\\"lg:\\"]').length} : null })()""" % (json.dumps(name), json.dumps(name), json.dumps(name)))
        for nm in pk2["ann"]:
            a = ask3(nm)
            check("29 Find a card: annotated card %s says what is unread, in the same wording" % nm, bool(a) and a["ann"] >= 1 and a["ag"] >= 1 and "This ability has a condition the tool did not read:" in a["text"] and "Condition not read" in a["text"] and "may change what the ability does" in a["text"], str(a)[:200])
        for nm in pk2["gap"]:
            a = ask3(nm)
            check("29 Find a card: gap-test card %s says another part of the card was not read" % nm, bool(a) and a["ann"] >= 1 and "Card part not read" in a["text"] and "another part of this card was not" in a["text"], str(a)[:200])
        for nm in pk2["both"]:
            a = ask3(nm)
            check("29 Find a card: card %s is tentative and annotated and says it is counted once" % nm, bool(a) and a["ann"] >= 1 and a["tg"] >= 1 and "counted once, as tentative" in a["text"], str(a)[:200])
        for nm in pk2["tent"]:
            a = ask3(nm)
            check("29 Find a card: tentative card %s has no annotation text" % nm, bool(a) and a["ann"] == 0 and a["tg"] >= 1, str(a)[:160])
        for nm in pk2["loose"]:
            a = ask3(nm)
            check("29 Find a card: loose card %s has no annotation text" % nm, bool(a) and a["ann"] == 0 and a["lg"] >= 1, str(a)[:160])
        for nm in pk2["placed"]:
            a = ask3(nm)
            check("29 Find a card: placed card %s has no annotation text" % nm, bool(a) and a["ann"] == 0 and a["ag"] == 0, str(a)[:160])
        for nm in pk2["left"]:
            a = ask3(nm)
            check("29 Find a card: left-out card %s has no annotation text" % nm, bool(a) and a["ann"] == 0 and a["ag"] == 0, str(a)[:160])
        a = ask3(pk2["ann"][0])
        c.js("document.querySelector('#findres .fr [data-go^=\"ag:\"]').click()")
        check("29 an annotation link in Find a card opens the group", c.wait("document.querySelectorAll('#list .card').length > 0 && !!document.querySelector('#panel .annnote')"))
        oa = c.js("Object.keys(ANN.by_card).find(o => !TENT.by_card[o] && ANN.cs[o] === 'c')")
        c.js("show('c:%s')" % oa)
        check("29 the card page of an annotated card shows the badge and the unread condition", c.wait("!!document.querySelector('.cardpage .annnote .b-ann')", 60))
        c.js("show('C:')")
        c.wait("document.querySelectorAll('#list .crow').length > 5", 60)
        c.js("document.getElementById('cf-st').value = 'a'; document.getElementById('cf-st').dispatchEvent(new Event('input', {bubbles: true}))")
        check("29 the Cards tab can filter annotated cards", c.wait("document.getElementById('cfcount').innerText.startsWith('%s')" % format(AM['condition_cards_new'] + AM['gap_cards_new'] - 15, ',')[:3]), c.js("document.getElementById('cfcount').innerText"))
        c.js("document.getElementById('cf-st').value = ''; document.getElementById('cf-st').dispatchEvent(new Event('input', {bubbles: true}))")
        # phone width: 390 px
        c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
        c.js("show('ag:%s')" % kc)
        c.wait("document.querySelectorAll('#list .card').length > 0", 60)
        ph = c.js("""(() => { const cs = [...document.querySelectorAll('#list .card')].slice(0, 30); const hs = cs.map(x => x.getBoundingClientRect().height).sort((a, b) => a - b);
          const ns = cs.map(x => (x.querySelector('.annnote') || x).getBoundingClientRect().height).sort((a, b) => a - b); const lh = parseFloat(getComputedStyle(document.body).lineHeight) || 20;
          return {w: window.innerWidth, scrollW: document.documentElement.scrollWidth, cardMedianPx: hs[Math.floor(hs.length / 2)], cardMaxPx: hs[hs.length - 1], noteMedianPx: ns[Math.floor(ns.length / 2)], noteMaxPx: ns[ns.length - 1], lineHeight: lh, cards: cs.length} })()""")
        check("29 phone width 390 px: no sideways scroll on an annotation list", ph["scrollW"] <= ph["w"] + 1, str(ph))
        json.dump(ph, open(os.path.join(HERE, 'build', 'annotation_phone_width.json'), 'w'), indent=1)
        c.js("show('c:%s')" % oa)
        c.wait("!!document.querySelector('.cardpage .annnote .b-ann')", 60)
        ph2 = c.js("(() => { const n = document.querySelector('.cardpage .annnote'); return {w: window.innerWidth, scrollW: document.documentElement.scrollWidth, noteHeightPx: n.getBoundingClientRect().height} })()")
        check("29 phone width 390 px: no sideways scroll on an annotated card page", ph2["scrollW"] <= ph2["w"] + 1, str(ph2))
        c.call("Emulation.clearDeviceMetricsOverride")
        # the switch removes every annotation
        c.js("document.getElementById('showann').checked = false; document.getElementById('showann').dispatchEvent(new Event('change'))")
        cov = c.js("document.getElementById('cov').innerText")
        check("29 switched off: no annotation rows or badges, no fourth figure or gap-test figure, no annotated counts, the pile is back to the tentative-only count",
              c.wait("document.querySelectorAll('#tree .b-ann').length === 0") and "condition annotations" not in cov and "unread-part stratum" not in cov and "annotated:" not in cov
              and ("Not yet organized: " + format(AM["still_unorganized_after_tentative"], ",")) in cov and c.js("document.querySelectorAll('#tree .row[data-k^=\"af:\"]').length") == 0, cov[-300:].replace("\n", " "))
        check("29 switched off: the first three figures are unchanged", all(x in cov for x in ("24,336 of 33,183", "27,590", "29,683")))
        c.js("show('ag:%s')" % kc)
        check("29 switched off: a link to an annotation group says it is switched off", c.wait("document.getElementById('panel').innerText.includes('switched off')"))
        a = ask3(pk2["ann"][0])
        check("29 switched off: Find a card shows no annotation text for an annotated card", bool(a) and a["ann"] == 0 and "did not read" not in a["text"], str(a)[:160])
        c.js("document.getElementById('showann').checked = true; document.getElementById('showann').dispatchEvent(new Event('change'))")
        check("29 switched on again: the fourth figure is back", c.wait("document.getElementById('cov').innerText.includes('condition annotations')"))
        c.js("document.getElementById('showtent').checked = false; document.getElementById('showtent').dispatchEvent(new Event('change'))")
        cov = c.js("document.getElementById('cov').innerText")
        check("29 tentative switched off alone: the annotations stay, and every annotated card (both strata, tentative or not) leaves the pile",
              c.wait("document.querySelectorAll('#tree .b-tent').length === 0") and "condition annotations" in cov and ("Not yet organized: " + format(5593 - AM["cards"], ",")) in cov, cov[-260:].replace("\n", " "))
        c.js("document.getElementById('showtent').checked = true; document.getElementById('showtent').dispatchEvent(new Event('change'))")
        c.wait("document.getElementById('cov').innerText.includes('counting tentative placements')")
        # 30 the community-tag layer (the 1,300 cards with no readable ability, grouped by Scryfall community tag)
        TG = json.load(open(os.path.join(HERE, 'build', 'tag_placements.json'), encoding='utf-8'))['meta']
        c.js("localStorage.removeItem('showTags')")
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % PORT_HTTP)
        c.wait("document.querySelectorAll('#tree .row').length > 10", 90)
        c.wait("!!document.getElementById('showtag') && document.getElementById('cov').innerText.includes('Basis')", 90)
        c.wait("typeof TAGS !== 'undefined' && !!TAGS", 90)
        check("30 the community-tag switch is on by default (checkbox exists, labelled)", c.js("document.getElementById('showtag').checked") is True and "Show community-tag groups" in c.js("document.getElementById('showtag').parentElement.innerText"))
        c.wait("document.getElementById('cov').innerText.includes('community-tag group')", 60)
        cov = c.js("document.getElementById('cov').innerText")
        h6 = TG["headline"]["with_tag"]
        check("30 the header gives the sixth figure with its basis and the snapshot date on its own line; the first five unchanged",
              all(x in cov for x in ("24,336 of 33,183", "27,590", "29,683", "30,643", "30,803")) and (format(h6[0], ",") + " of 33,183") in cov and ("%g" % h6[1] + "%") in cov and "Tag snapshot 2026-10-14" in cov.replace("\n", " "), cov[:900].replace("\n", " "))
        check("30 the sixth figure is its own line (not blended with the annotation or gap-test lines)",
              c.js("[...document.querySelectorAll('#cov > div')].filter(d => d.innerText.includes('community-tag group')).length") == 1 and c.js("[...document.querySelectorAll('#cov > div')].filter(d => d.innerText.includes('community-tag group') && (d.innerText.includes('unread-part stratum') || d.innerText.includes('condition annotations'))).length") == 0)
        check("30 the pile is the pile after tentative, annotation (both strata) and tag; the tag count is named",
              ("Not yet organized: " + format(TG["still_unorganized_after_tag_with_gap_stratum"], ",")) in cov and ("grouped by community tag: " + format(TG["cards"], ",")) in cov, cov[-420:].replace("\n", " "))
        tot = c.js("(() => { const v = TAX.totals.views; return [v.placed + v.broad_only + v.keyword_block + v.no_abilities + v.replacement_group, TENT.meta.cards, ANN.meta.condition_cards_new, ANN.meta.gap_cards_new, TAGS.meta.cards, TAX.totals.not_yet_organized - TENT.meta.cards - ANN.meta.condition_cards_new - ANN.meta.gap_cards_new - TAGS.meta.cards, v.not_a_card, TAX.totals.universe] })()")
        check("30 placed + tentative + annotation + gap stratum + tag + unorganized + not cards = 38,921", sum(tot[:7]) == tot[7] == 38921, str(tot))
        c.js("(() => { open.add('LG:'); renderTree(); return true })()")
        check("30 the tree has a 'Grouped by community tag' section with its own badge, beside 'Cards we couldn't read yet'", c.wait("!!document.querySelector('#tree .row[data-k=\"CT:\"] .b-tag') && !!document.querySelector('#tree .row[data-k=\"UR:\"]')"))
        sty = c.js("""(() => { const m = document.querySelector('#tree .b-tag'); const a = document.querySelector('#tree .b-ann'); const t = document.querySelector('#tree .b-tent'); const bs = e => e ? getComputedStyle(e).borderTopStyle : null; return [bs(m), bs(a), bs(t)] })()""")
        check("30 the tag badge is double-bordered and differs from the annotation (dotted) and tentative badges", sty[0] == "double" and sty[0] not in (sty[1], sty[2]), str(sty))
        c.js("document.querySelector('#tree .row[data-k=\"CT:\"]').click()")
        check("30 the section opens with the wording, the counts, the snapshot date and what happens to cards without a group",
              c.wait("document.getElementById('panel').innerText.includes(\"Not checked against the card's parsed text.\")") and "Tag snapshot 2026-10-14" in c.js("document.getElementById('panel').innerText")
              and "stay in that list and in the pile" in c.js("document.getElementById('panel').innerText") and (format(TG["groups"], ",") + " groups") in c.js("document.getElementById('panel').innerText"))
        check("30 the section lists one row per group (the 3 broad tags are not groups)", c.js("document.querySelectorAll('#tree .row[data-k^=\"ct:\"]').length") == TG["groups"] and TG["wide_tags_not_groups"] == 3)
        gid = c.js("TAGS.order[Math.floor(TAGS.order.length / 2)]")
        c.js("document.querySelector('#tree .row[data-k=\"ct:%s\"]').click()" % gid)
        check("30 a group lists its cards, each with the label, the tag and the snapshot date",
              c.wait("document.querySelectorAll('#list .card').length > 3")
              and c.js("[...document.querySelectorAll('#list .card')].every(x => x.innerText.includes(\"Grouped by community tag. Not checked against the card's parsed text.\") && x.innerText.includes('Tag:') && x.innerText.includes('Tag snapshot 2026-10-14'))") is True)
        check("30 the group's count matches the data", c.js("TAGS.groups['%s'].cards" % gid) == c.js("TAGS.groups['%s'].m.length" % gid) and (str(c.js("TAGS.groups['%s'].cards" % gid)) + " cards") in c.js("document.querySelector('#panel .sub').innerText"))
        check("30 every name has a name_source of rule or model_written (user_edit allowed), and no 'verified' wording",
              c.js("Object.values(TAGS.groups).every(g => ['rule', 'model_written', 'user_edit'].includes(g.name_source))") is True and c.js("!document.body.innerText.toLowerCase().includes('verified')") is True)
        # Cards we couldn't read yet: tag chips and the tag filter
        c.js("show('UR:')")
        check("30 'Cards we couldn't read yet' has a tag filter and shows each card's tag chips",
              c.wait("!!document.getElementById('urtag') && document.querySelectorAll('#list .card').length > 3") and c.js("document.getElementById('urtag').options.length") == TG["groups"] + TG["wide_tags_not_groups"] + 1
              and c.js("[...document.querySelectorAll('#list .card')].slice(0, 5).every(x => x.innerText.includes('community tag'))") is True)
        c.js("(() => { const s = document.getElementById('urtag'); s.value = %s; s.dispatchEvent(new Event('change')); return true })()" % json.dumps(gid))
        n_g = c.js("TAGS.groups['%s'].cards" % gid)
        check("30 choosing a tag filters the list to that tag's cards", c.wait("document.querySelector('#panel .sub:last-of-type') && document.querySelector('#panel').innerText.includes('%d cards carry the chosen tag')" % n_g, 30) and c.js("document.querySelectorAll('#list .card').length") <= n_g)
        wt = c.js("Object.keys(TAGS.wide)[0]")
        c.js("(() => { const s = document.getElementById('urtag'); s.value = 'w:%s'; s.dispatchEvent(new Event('change')); return true })()" % wt)
        n_w = c.js("TAGS.wide['%s'].cards" % wt)
        check("30 a broad tag (over 100 cards, not a group) works as a filter", c.wait("document.querySelector('#panel').innerText.includes('%d cards carry the chosen tag')" % n_w, 30), "%s cards" % n_w)
        c.js("URTAG = ''; show('UR:')")
        # Find a card: 5 tagged, 5 unreadable without a usable group, 5 placed, 5 tentative, 3 excluded
        pk3 = c.js("""(() => {
          const pick = (arr, n) => { const out = []; for (let i = 1; out.length < n && i < arr.length; i++) out.push(arr[Math.floor(arr.length * i / (n + 1))]); return out; };
          const ok = o => CARDS[o] && /^[A-Za-z' ,-]+$/.test(CARDS[o].n);
          const tagged = Object.keys(TAGS.by_card).filter(ok).sort();
          const nog = TAGS.no_group.filter(ok).sort();
          const tent = Object.keys(TENT.by_card).filter(o => ok(o) && !TAGS.by_card[o]).sort();
          const placed = Object.keys(CARDS).filter(o => ok(o) && CARDS[o].ab.some(a => a[2] === 'p') && !LOOSE.by_card[o]).sort();
          const left = Object.keys(FLAGS.cards).filter(o => FLAGS.evidence[o]).sort();
          return {tagged: pick(tagged, 5).map(o => CARDS[o].n), nog: pick(nog, 5).map(o => CARDS[o].n), tent: pick(tent, 5).map(o => CARDS[o].n), placed: pick(placed, 5).map(o => CARDS[o].n), left: pick(left, 3).map(o => FLAGS.evidence[o].name)};
        })()""")

        def ask4(name):
            return c.js("""(async () => { document.getElementById('q').value = %s; await find(%s);
              const want = %s.toLowerCase(); const frs = [...document.querySelectorAll('#findres .fr')];
              const fr = frs.find(f => f.querySelector('.nm').innerText.toLowerCase() === want) || frs[0];
              return fr ? {text: fr.innerText, tag: fr.querySelectorAll('.b-tag').length, ct: fr.querySelectorAll('[data-go^=\\"ct:\\"]').length} : null })()""" % (json.dumps(name), json.dumps(name), json.dumps(name)))
        for nm in pk3["tagged"]:
            a = ask4(nm)
            check("30 Find a card: tagged card %s names its tag groups with the label and the snapshot date" % nm, bool(a) and a["tag"] >= 1 and a["ct"] >= 1 and "Not checked against the card's parsed text." in a["text"] and "Tag snapshot 2026-10-14" in a["text"], str(a)[:200])
        for nm in pk3["nog"]:
            a = ask4(nm)
            check("30 Find a card: unreadable card %s without a usable group says so" % nm, bool(a) and a["tag"] >= 1 and a["ct"] == 0 and "No community-tag group yet" in a["text"], str(a)[:200])
        for nm in pk3["placed"]:
            a = ask4(nm)
            check("30 Find a card: placed card %s shows no community-tag text" % nm, bool(a) and a["tag"] == 0 and "community tag" not in a["text"].lower(), str(a)[:160])
        for nm in pk3["tent"]:
            a = ask4(nm)
            check("30 Find a card: tentative card %s shows no community-tag text" % nm, bool(a) and a["tag"] == 0 and "community tag" not in a["text"].lower(), str(a)[:160])
        for nm in pk3["left"]:
            a = ask4(nm)
            check("30 Find a card: left-out card %s shows no community-tag text" % nm, bool(a) and a["tag"] == 0 and "community tag" not in a["text"].lower(), str(a)[:160])
        a = ask4(pk3["tagged"][0])
        c.js("document.querySelector('#findres .fr [data-go^=\"ct:\"]').click()")
        check("30 a tag link in Find a card opens the group", c.wait("document.querySelectorAll('#list .card').length > 0 && !!document.querySelector('#panel .tagnote')"))
        oa = c.js("Object.keys(TAGS.by_card)[0]")
        c.js("show('c:%s')" % oa)
        check("30 the card page of a tagged card shows the badge, the label and the snapshot date", c.wait("!!document.querySelector('.cardpage .tagnote .b-tag')", 60) and "Tag snapshot 2026-10-14" in c.js("document.querySelector('.cardpage .tagnote').innerText"))
        c.js("show('C:')")
        c.wait("document.querySelectorAll('#list .crow').length > 5", 60)
        c.js("document.getElementById('cf-st').value = 'm'; document.getElementById('cf-st').dispatchEvent(new Event('input', {bubbles: true}))")
        check("30 the Cards tab can filter community-tag cards", c.wait("document.getElementById('cfcount').innerText.startsWith('%s')" % format(TG['cards'], ',')), c.js("document.getElementById('cfcount').innerText"))
        c.js("document.getElementById('cf-st').value = ''; document.getElementById('cf-st').dispatchEvent(new Event('input', {bubbles: true}))")
        # phone width
        c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
        c.js("show('ct:%s')" % gid)
        c.wait("document.querySelectorAll('#list .card').length > 0", 60)
        ph = c.js("""(() => { const cs = [...document.querySelectorAll('#list .card')].slice(0, 30); const ns = cs.map(x => (x.querySelector('.tagnote') || x).getBoundingClientRect().height).sort((a, b) => a - b);
          return {w: window.innerWidth, scrollW: document.documentElement.scrollWidth, noteMedianPx: ns[Math.floor(ns.length / 2)], noteMaxPx: ns[ns.length - 1], lineHeight: parseFloat(getComputedStyle(document.body).lineHeight) || 20, cards: cs.length} })()""")
        check("30 phone width 390 px: no sideways scroll on a tag group list", ph["scrollW"] <= ph["w"] + 1, str(ph))
        json.dump(ph, open(os.path.join(HERE, 'build', 'tag_layer_phone_width.json'), 'w'), indent=1)
        c.js("show('UR:')")
        c.wait("!!document.getElementById('urtag')", 60)
        ph2 = c.js("(() => ({w: window.innerWidth, scrollW: document.documentElement.scrollWidth}))()")
        check("30 phone width 390 px: no sideways scroll on 'Cards we couldn't read yet' with the filter", ph2["scrollW"] <= ph2["w"] + 1, str(ph2))
        c.call("Emulation.clearDeviceMetricsOverride")
        # switched off
        c.js("document.getElementById('showtag').checked = false; document.getElementById('showtag').dispatchEvent(new Event('change'))")
        cov = c.js("document.getElementById('cov').innerText")
        check("30 switched off: no tag rows or badges, no sixth figure, no tag counts, the pile back to the annotation-state count",
              c.wait("document.querySelectorAll('#tree .b-tag').length === 0") and "community-tag group" not in cov and "grouped by community tag" not in cov
              and ("Not yet organized: " + format(TG["pile_before"] - AM['gap_cards_new'], ",")) in cov and c.js("document.querySelectorAll('#tree .row[data-k=\"CT:\"]').length") == 0, cov[-300:].replace("\n", " "))
        check("30 switched off: the first five figures are unchanged", all(x in cov for x in ("24,336 of 33,183", "27,590", "29,683", "30,643", "30,803")))
        c.js("show('UR:')")
        check("30 switched off: 'Cards we couldn't read yet' shows all the cards, with no tag filter and no tag chips",
              c.wait("document.querySelectorAll('#list .card').length > 3") and c.js("!document.getElementById('urtag')") is True and c.js("!document.getElementById('list').innerText.includes('community tag')") is True)
        c.js("show('ct:%s')" % gid)
        check("30 switched off: a link to a tag group says it is switched off", c.wait("document.getElementById('panel').innerText.includes('switched off')"))
        a = ask4(pk3["tagged"][0])
        check("30 switched off: Find a card shows no community-tag text for a tagged card", bool(a) and a["tag"] == 0 and "community tag" not in a["text"].lower(), str(a)[:160])
        c.js("document.getElementById('showtag').checked = true; document.getElementById('showtag').dispatchEvent(new Event('change'))")
        check("30 switched on again: the sixth figure is back", c.wait("document.getElementById('cov').innerText.includes('community-tag group')"))
        if SHOTS:
            open(os.path.join(SHOTS, "browser_deeplink.png"), "wb").write(base64.b64decode(c.call("Page.captureScreenshot", format="png")["data"]))
    finally:
        edge.terminate()
        srv.shutdown()
    bad = [r for r in results if not r[1]]
    print("\n%d checks, %d failed" % (len(results), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
