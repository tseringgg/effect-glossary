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
