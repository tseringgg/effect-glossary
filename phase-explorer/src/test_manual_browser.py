#!/usr/bin/env python3
"""Drive the hand-placement panel in headless Edge (DevTools protocol), against a TEMP corrections file served in place of the real one. The real corrections file is never touched.

    python src/test_manual_browser.py          (needs msedge.exe, `pip install websocket-client`, build/manual_index.json and build/manual_suggestions.json)

Clicks are DOM .click() calls and the search box is typed with real key events; what a person would do with a mouse is the same code path, but nothing here is a human pointing device.
Covered in the browser: the work queue (counts, filters, next, skip, nothing fits and its undo); open a card; the panel beside the image; add a suggestion; add from the search box (a keyword group);
remove a generated group; undo an add and a removal; the six figures unchanged; the hand line and the reconciliation; the group page showing the hand row; Find a card for a hand-placed card;
reload keeps the edit; a rebuild keeps it; an orphaned edit is reported (page, build output, report); the endpoint missing (NOT SAVED, banner, still shown after reload, never counted);
"Show hand edits" off hides everything; the panel at 390 px (one column, image first, no sideways scroll, touch-size buttons).
Not covered: a real pointing device, touch events, other browsers, scrolling performance.
"""
import base64
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import websocket

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as MC

HERE = MC.HERE
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
def free_port():                                           # a fresh port each run: a stale server from an earlier run must never answer
    import socket
    k = socket.socket()
    k.bind(("127.0.0.1", 0))
    p_ = k.getsockname()[1]
    k.close()
    return p_


PORT_A, PORT_B, PORT_CDP = free_port(), free_port(), free_port()
TMP = tempfile.mkdtemp(prefix="manual_browser_")
DOC = os.path.join(TMP, "manual_placements.json")
BUILDOUT = os.path.join(TMP, "buildout")
os.makedirs(BUILDOUT)
MC.CORR = DOC
SHOTS = os.environ.get("SHOTS")
sys.argv = sys.argv[:1]
import serve                                                       # noqa: E402


class WithTemp(object):
    def translate_path(self, path):
        if path.split("?")[0] == "/corrections/manual_placements.json":
            return DOC
        return super().translate_path(path)


class Real(WithTemp, serve.Handler):
    def log_message(self, *a):
        pass


class NoApi(WithTemp, http.server.SimpleHTTPRequestHandler):      # a plain static server: no /api/manual at all
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def log_message(self, *a):
        pass


class Quiet(socketserver.ThreadingTCPServer):
    allow_reuse_address = False
    daemon_threads = True

    def handle_error(self, *a):
        pass


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=120, suppress_origin=True)
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

    def wait(self, expr, secs=60):
        t = time.time()
        while time.time() - t < secs:
            try:
                if self.js(expr):
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False

    def type(self, text):
        for ch in text:
            self.call("Input.dispatchKeyEvent", type="keyDown", text=ch, key=ch)
            self.call("Input.dispatchKeyEvent", type="keyUp", key=ch)


def doc():
    return json.load(open(DOC, encoding="utf-8")) if os.path.exists(DOC) else MC.empty_doc()


def write_doc(d):
    open(DOC, "w", encoding="utf-8").write(json.dumps(d, indent=1))


def build(out=BUILDOUT):
    env = dict(os.environ, MANUAL_CORRECTIONS=DOC, MANUAL_BUILD_OUT=out, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, os.path.join(HERE, "src", "build_manual_layer.py")], capture_output=True, text=True, env=env, encoding="utf-8")
    return r.stdout + r.stderr, json.load(open(os.path.join(out, "manual_layer.json"), encoding="utf-8"))


def main():
    idx = MC.load_index()
    sug = json.load(open(os.path.join(HERE, "build", "manual_suggestions.json"), encoding="utf-8"))["cards"]
    cards = idx["cards"]
    pile = sorted((o for o, c in cards.items() if c[1] == "u" and c[2] in (1, 2, 3, 4, 5)), key=lambda o: (cards[o][4] is None, cards[o][4] or 0, cards[o][0], o))
    first_in_queue = pile[0]
    card = next(o for o in pile if o in sug and sug[o][0][0].startswith("leaf:") and any(x[1] == "L" for x in cards[o][3]) and cards[o][2] == 2)
    gen_group = next(x[0] for x in cards[card][3] if x[1] == "L")
    sugg = sug[card]
    soft = next(o for o, c in sorted(cards.items()) if c[1] == "t" and any(x[1] == "T" for x in c[3]))
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))
        print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)) if detail else ""))
    srvA = Quiet(("127.0.0.1", PORT_A), Real)
    srvB = Quiet(("127.0.0.1", PORT_B), NoApi)
    for s_ in (srvA, srvB):
        threading.Thread(target=s_.serve_forever, daemon=True).start()
    prof = tempfile.mkdtemp()
    edge = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + prof, "--remote-debugging-port=%d" % PORT_CDP, "--remote-allow-origins=*",
                             "--window-size=1400,1000", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT_CDP))
                break
            except Exception:
                time.sleep(0.5)
        c = CDP(next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"])
        c.call("Page.enable")
        c.call("Runtime.enable")
        errs = []

        def load(port, frag="", wait_panel=True):
            c.call("Page.navigate", url="about:blank")         # a hash-only navigation would not reload: go through a blank page first
            time.sleep(0.5)
            c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html%s" % (port, frag))
            ok = c.wait("document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null && document.querySelectorAll('#cov > div:not(.basis)').length >= 6", 180)
            return ok
        ok = load(PORT_A)
        check("0 page boots with the hand layer loaded", ok and c.js("!document.getElementById('queuetab').hidden"), c.js("document.getElementById('prov').innerText.slice(0,40)"))
        figs0 = c.js("[...document.querySelectorAll('#cov > div:not(.basis)')].map(d => d.innerText).join('|')")
        check("0 the six figures are shown", figs0.count("Basis:") == 6, figs0.count("Basis:"))
        hl = c.js("document.getElementById('handline').innerText")
        check("0 the hand line is its own line, 0 edits, with the reconciliation sum", "placed by hand" in hl and "0 of 33,183" in hl and "= 38,921" in hl, hl[:160])

        # ---- queue
        c.js("document.querySelector('#tabs button[data-mode=queue]').click()")
        check("1 queue: the tab opens the work queue", c.wait("document.querySelector('#panel h2') && document.querySelector('#panel h2').innerText.includes('To place')"))
        txt = c.js("document.querySelector('#panel .sub').innerText")
        check("1 queue default = the pile with the gap-test stratum on: 1,175 cards", "1,175 cards in this view" in txt, txt[:90])
        c.js("(() => { const g = document.getElementById('qf-gap'); g.checked = true; g.dispatchEvent(new Event('change', {bubbles: true})); })()")
        c.wait("document.querySelector('#panel .sub').innerText.includes('1,335 cards')")
        check("1 queue: ticking the gap-test stratum gives the full pile of 1,335", "1,335 cards in this view" in c.js("document.querySelector('#panel .sub').innerText"))
        c.js("(() => { const g = document.getElementById('qf-gap'); g.checked = false; g.dispatchEvent(new Event('change', {bubbles: true})); })()")
        c.wait("document.querySelector('#panel .sub').innerText.includes('1,175 cards')")
        c.js("document.querySelector('#panel button[data-act=qnext]').click()")
        check("1 queue: Next card opens the most popular pile card", c.wait("!!document.getElementById('editpanel') && document.getElementById('editpanel').dataset.oid == %s" % json.dumps(first_in_queue)),
              cards[first_in_queue][0])
        check("1 queue: the queue bar shows on the card page", c.js("!!document.querySelector('.qbar') && document.querySelector('.qbar').innerText.includes('left')"))
        c.js("document.querySelector('button[data-act=nofit]').click()")
        check("1 nothing fits: saved as a third action in the same file", c.wait("document.getElementById('epstatus').textContent.includes('saved')") and doc()["edits"][first_in_queue]["groups"]["none:fits"]["action"] == "nofit")
        hl = c.js("document.getElementById('handline').innerText")
        check("1 nothing fits: its own count, never a placement (0 placed by hand)", "0 of 33,183" in hl and "Marked “nothing fits”: 1" in hl, hl[hl.find('Marked'):hl.find('Marked') + 50])
        c.js("document.querySelector('.qbar button[data-act=qnext]').click()")
        c.wait("document.getElementById('editpanel') && document.getElementById('editpanel').dataset.oid != %s" % json.dumps(first_in_queue))
        second = c.js("document.getElementById('editpanel').dataset.oid")
        check("1 nothing fits: the card left the queue (Next goes to another card)", second != first_in_queue and second == pile[1], cards[second][0])
        c.js("document.querySelector('.qbar button[data-act=qskip]').click()")
        c.wait("document.getElementById('editpanel') && document.getElementById('editpanel').dataset.oid != %s" % json.dumps(second))
        check("1 skip moves on without marking", c.js("document.getElementById('editpanel').dataset.oid") == pile[2] and second not in doc()["edits"])
        c.js("show('c:%s')" % first_in_queue)
        c.wait("!!document.getElementById('editpanel') && document.getElementById('editpanel').dataset.oid == %s" % json.dumps(first_in_queue))
        c.js("[...document.querySelectorAll('#editpanel button[data-act=clear]')][0].click()")
        check("1 nothing fits is undoable: the entry is gone from the file", c.wait("document.getElementById('epstatus').textContent.includes('saved')") and first_in_queue not in doc()["edits"])

        # ---- the card page and its panel
        c.js("show('c:%s')" % card)
        check("2 open a card: image and edit panel are side by side", c.wait("!!document.getElementById('editpanel') && !!document.querySelector('.cl-img')"))
        c.wait("document.querySelectorAll('#epsug .sug').length > 0")
        geo = c.js("(() => { const i = document.querySelector('.cl-img img, .cl-img .noimg').getBoundingClientRect(), p = document.getElementById('editpanel').getBoundingClientRect(); return [i.right, p.left, i.top, p.top]; })()")
        check("2 panel sits to the right of the card image at 1400 px", geo[0] <= geo[1] + 1 and abs(geo[2] - geo[3]) < 60, geo)
        n_sug = c.js("document.querySelectorAll('#epsug .sugc').length") or c.js("document.querySelectorAll('#epsug .sug').length")          # ENGINE_V2: near-duplicate groups share a block; five blocks at most
        check("2 up to 5 suggestions, each with a score, a reason and an Add button", 1 <= n_sug <= 5 and c.js("[...document.querySelectorAll('#epsug .sug')].every(s => /^[01]\\.[0-9]{2}$/.test(s.querySelector('.score').innerText) && s.querySelector('.why').innerText.length > 10 && s.querySelector('button[data-act=add]'))"), n_sug)
        ept = c.js("document.getElementById('editpanel').innerText").lower()
        check("2 suggestions are labelled as not placements", "not placements" in ept and "nothing is placed until you press add" in ept)
        check("2 the card's current groups are listed with their source and a Remove button", c.js("!!document.querySelector('#editpanel .grow .badge') && !!document.querySelector('#editpanel .grow button[data-act=remove]')"))
        top_gid = sugg[0][0]
        c.js("document.querySelector('#epsug button[data-act=add][data-g=%s]').click()" % json.dumps(top_gid))
        saved = c.wait("document.getElementById('epstatus').textContent.includes('saved')")
        e = doc()["edits"].get(card, {}).get("groups", {}).get(top_gid, {})
        check("3 add a suggestion: saved to the file with date, group name and the original unplaced reason", saved and e.get("action") == "add" and e["source_at_edit"]["reason"]["code"] == 2 and e["group_name"] == idx["groups"][top_gid][0], e.get("source_at_edit"))
        check("3 the panel now lists it as 'by hand'", c.js("[...document.querySelectorAll('#editpanel .grow .b-hand')].length >= 1"))
        hl = c.js("document.getElementById('handline').innerText")
        check("3 hand line: 1 placed by hand, own line, reconciliation 1,334 unorganized", "1 of 33,183" in hl and "1,334 unorganized" in hl and "= 38,921" in hl, hl[:70])
        figs1 = c.js("[...document.querySelectorAll('#cov > div:not(.basis)')].map(d => d.innerText).join('|')")
        check("3 the six existing figures are unchanged by a hand edit", figs1 == figs0)
        nyo = c.js("document.querySelector('#cov > div.basis').innerText")
        check("3 'Not yet organized' drops by one (1,175 -> 1,174)", "Not yet organized: 1,174" in nyo, nyo[:40])
        # search box (real key events): a keyword-block group
        c.js("document.getElementById('epsearch').focus()")
        c.type("affinity")
        check("4 search box finds groups by name, with layer and size", c.wait("document.querySelectorAll('#epresults .srow').length > 0") and "Affinity" in c.js("document.getElementById('epresults').innerText"), c.js("document.getElementById('epresults').innerText.slice(0,100)"))
        c.js("document.getElementById('epnote').value = 'a keyword group, typed note'")
        c.js("[...document.querySelectorAll('#epresults .srow')].find(r => r.innerText.includes('keyword group')).querySelector('button').click()")
        c.wait("document.getElementById('epstatus').textContent.includes('saved')")
        kw = [g for g in doc()["edits"][card]["groups"] if g.startswith("kw:")]
        check("4 a keyword-block group can be added (with the note)", bool(kw) and doc()["edits"][card]["groups"][kw[0]]["note"] == "a keyword group, typed note", kw)
        c.js("[...document.querySelectorAll('#editpanel .grow')].find(r => r.innerText.includes('Affinity')).querySelector('button[data-act=clear]').click()")
        c.wait("document.getElementById('epstatus').textContent.includes('saved')")
        check("4 undo removes a hand add from the file", not [g for g in doc()["edits"][card]["groups"] if g.startswith("kw:")])
        # remove a generated group
        c.js("document.querySelector('#editpanel .grow button[data-act=remove][data-g=%s]').click()" % json.dumps(gen_group))
        c.wait("document.getElementById('epstatus').textContent.includes('saved')")
        r_ = doc()["edits"][card]["groups"].get(gen_group, {})
        check("5 remove a generated group: recorded as a removal and shown struck through", r_.get("action") == "remove" and c.js("!!document.querySelector('#editpanel .grow s')") and "removed by hand" in c.js("document.getElementById('editpanel').innerText"))
        hl = c.js("document.getElementById('handline').innerText")
        check("5 a removal changes no generated count (still 1 placed by hand; removal counted separately)", "1 of 33,183" in hl and "Removals recorded: 1" in hl)
        c.js("document.querySelector('#editpanel .grow button[data-act=clear]').click()")
        c.wait("document.getElementById('epstatus').textContent.includes('saved')")
        check("5 undo of a removal restores the group", gen_group not in doc()["edits"][card]["groups"] and c.js("!document.querySelector('#editpanel .grow s')"))
        # group page and Find a card
        c.js("show(Manual.goKey(%s))" % json.dumps(top_gid))
        check("6 the group page shows the hand-placed card under 'Placed here by hand', not counted in the group's number", c.wait("document.querySelector('#list .subhead') && document.querySelector('#list').innerText.includes('Placed here by hand')") and cards[card][0] in c.js("document.getElementById('list').innerText"))
        c.js("document.getElementById('q').value=''")
        c.js("document.getElementById('q').focus()")
        c.type(cards[card][0])
        check("6 Find a card says where it was placed and that it was by hand", c.wait("document.getElementById('findres').innerText.includes('Placed by hand: in')", 90) and "by hand" in c.js("document.getElementById('findres').innerText"),
              c.js("document.getElementById('findres').innerText.slice(0,200)").replace("\n", " "))
        # a soft-placed card confirmed by hand stays in its own figure
        c.js("document.getElementById('q').value=''")
        c.js("show('c:%s')" % soft)
        c.wait("document.getElementById('editpanel') && document.getElementById('editpanel').dataset.oid == %s" % json.dumps(soft))
        tg = next(x[0] for x in cards[soft][3] if x[1] == "T")
        # confirm = add the group it is already shown in, via a suggestion row when present, else the search
        c.js("(() => { const nm = MI.groups[%s][0]; const s = document.getElementById('epsearch'); s.value = nm.slice(-22); s.dispatchEvent(new Event('input', {bubbles: true})); })()" % json.dumps(tg))
        c.wait("document.querySelectorAll('#epresults .srow').length > 0")
        c.js("[...document.querySelectorAll('#epresults .srow button')].find(b => b.dataset.g == %s).click()" % json.dumps(tg))
        c.wait("document.getElementById('epstatus').textContent.includes('saved')")
        hl = c.js("document.getElementById('handline').innerText")
        check("7 confirming a tentative card: counted as confirmed (tentative 1), not as placed by hand; stays in its figure", "Confirmed by hand: 1 (tentative 1" in hl and "1 of 33,183" in hl, hl[hl.find('Confirmed'):hl.find('Confirmed') + 60])
        figs2 = c.js("[...document.querySelectorAll('#cov > div:not(.basis)')].map(d => d.innerText).join('|')")
        check("7 the six figures are still unchanged", figs2 == figs0)

        # ---- reload keeps it; rebuild keeps it
        ok = load(PORT_A, "#c:" + card)
        c.wait("!!document.getElementById('editpanel')")
        time.sleep(1.5)
        r8 = [ok, c.js("document.querySelectorAll('#editpanel .grow .b-hand').length"), c.js("document.getElementById('handline').innerText.slice(0, 60)")]
        check("8 reload: the edit persisted (the file is read again)", r8[0] and r8[1] >= 1 and "1 of 33,183" in r8[2], r8)
        out, layer = build()
        rc = layer["reconciliation"]
        check("9 rebuild: the edit survived and the reconciliation still sums to 38,921", layer["counts"]["placed_by_hand_new"] == 1 and layer["counts"]["confirmed_by_hand"] == 1 and rc["sum"] == 38921 and rc["unorganized"] == 1334 and layer["counts"]["orphans"] == 0,
              {k: layer["counts"][k] for k in ("placed_by_hand_new", "confirmed_by_hand", "orphans")})
        lj = json.load(open(os.path.join(BUILDOUT, "manual_layer.json"), encoding="utf-8"))
        check("9 rebuild: the hand-placed card keeps its original reason (for phase 2)", any(k.startswith("hand:2") and card in v for k, v in lj["by_reason"].items()), list(lj["by_reason"]))
        # the page's resolver agrees with the Python one on the same data
        pj = c.js("JSON.stringify({c: MRES.counts, r: MRES.reconciliation})")
        pj = json.loads(pj)
        check("9 the page's counts equal the build's (JS resolver = Python resolver)", pj["c"]["placed_by_hand_new"] == lj["counts"]["placed_by_hand_new"] and pj["r"] == lj["reconciliation"] and pj["c"]["confirmed_by_hand_of_which"] == lj["counts"]["confirmed_by_hand_of_which"])

        # ---- orphan
        d = doc()
        d["edits"][card]["groups"]["leaf:azzzzzzzzz"] = {"action": "add", "date": "2026-10-14T10:00:00", "note": "", "group_name": "A group that is gone", "source_at_edit": {"status": "unorganized"}}
        write_doc(d)
        out, layer = build()
        orph_md = open(os.path.join(BUILDOUT, "manual-placements.md"), encoding="utf-8").read()
        check("10 orphaned edit: reported in the build output, the layer file and the report", "ORPHANED EDITS: 1" in out and layer["counts"]["orphans"] == 1 and "A group that is gone" in orph_md and layer["counts"]["placed_by_hand_new"] == 1, out.split("\n")[-3:])
        ok = load(PORT_A, "#c:" + card)
        c.wait("!!document.getElementById('editpanel')")
        check("10 orphaned edit: the page says so, and does not count it", "not in this build" in c.js("document.getElementById('handline').innerText") and "1 of 33,183" in c.js("document.getElementById('handline').innerText"))
        del d["edits"][card]["groups"]["leaf:azzzzzzzzz"]
        write_doc(d)

        # ---- hide checkbox
        ok = load(PORT_A, "#c:" + card)
        c.wait("!!document.getElementById('editpanel')")
        c.js("(() => { const b = document.getElementById('showhand'); b.checked = false; b.dispatchEvent(new Event('change', {bubbles: true})); })()")
        c.wait("document.getElementById('handline').hidden")
        check("11 'Show hand edits' off: the hand line, the panel and every hand badge are gone", c.js("document.getElementById('handline').hidden") and "Hand edits are hidden" in c.js("document.getElementById('panel').innerText") and c.js("[...document.querySelectorAll('.b-hand')].filter(e => e.offsetParent !== null).length") == 0)
        nyo = c.js("document.querySelector('#cov > div.basis').innerText")
        check("11 off: 'Not yet organized' goes back to the generated 1,175", "Not yet organized: 1,175" in nyo, nyo[:40])
        c.js("show(Manual.goKey(%s))" % json.dumps(top_gid))
        c.wait("document.querySelectorAll('#list .card').length > 0")
        check("11 off: the group page has no hand rows", "Placed here by hand" not in c.js("document.getElementById('list').innerText"))
        c.js("(() => { const b = document.getElementById('showhand'); b.checked = true; b.dispatchEvent(new Event('change', {bubbles: true})); })()")
        check("11 on again: the hand line is back", c.wait("!document.getElementById('handline').hidden") and "1 of 33,183" in c.js("document.getElementById('handline').innerText"))

        # ---- 390 px
        c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
        load(PORT_A, "#c:" + card)
        c.wait("!!document.getElementById('editpanel')")
        time.sleep(1.0)
        geo = c.js("(() => { const i = document.querySelector('.cl-img').getBoundingClientRect(), p = document.getElementById('editpanel').getBoundingClientRect(), t = document.querySelector('.cl-text').getBoundingClientRect(); "
                   "return {iTop: i.top, iBottom: i.bottom, pTop: p.top, pBottom: p.bottom, tTop: t.top, pw: p.width, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, "
                   "btn: Math.min(...[...document.querySelectorAll('#editpanel button')].map(b => b.getBoundingClientRect().height))}; })()")
        check("12 390 px: one column, image first, then the edit panel, then the card text", geo["iBottom"] <= geo["pTop"] + 1 and geo["pBottom"] <= geo["tTop"] + 1, geo)
        check("12 390 px: no sideways scroll", geo["sw"] <= geo["cw"] + 1, (geo["sw"], geo["cw"]))
        check("12 390 px: buttons are touch-size (44 px)", geo["btn"] >= 43, geo["btn"])
        if SHOTS:
            open(os.path.join(SHOTS, "manual_390.png"), "wb").write(base64.b64decode(c.call("Page.captureScreenshot", format="png")["data"]))
        c.call("Emulation.clearDeviceMetricsOverride")

        # ---- endpoint missing: a plain static server
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html#c:%s" % (PORT_B, card))
        c.wait("!!document.getElementById('editpanel')", 180)
        time.sleep(1.0)
        check("13 endpoint missing: the panel says saving is not available", "no /api/manual endpoint" in c.js("document.getElementById('editpanel').innerText"))
        c.js("document.querySelector('#epsug button[data-act=add]').click()")
        c.wait("document.getElementById('epstatus').textContent.startsWith('NOT SAVED')")
        check("13 endpoint missing: NOT SAVED with the reason, never a silent failure", c.js("document.getElementById('epstatus').textContent").startswith("NOT SAVED") and c.js("!!document.querySelector('#editpanel .b-unsaved')"), c.js("document.getElementById('epstatus').textContent")[:120])
        check("13 endpoint missing: a banner with Retry and Download", c.js("!document.getElementById('savebanner').hidden") and "NOT SAVED" in c.js("document.getElementById('savebanner').innerText") and c.js("!!document.querySelector('#savebanner button[data-act=retry]')"))
        hl = c.js("document.getElementById('handline').innerText")
        check("13 endpoint missing: the unsaved edit is shown but counted in no figure (still the 1 saved placement, not 2)", "NOT SAVED" in hl and "1 of 33,183" in hl and "2 of 33,183" not in hl, hl[:60])
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html#c:%s" % (PORT_B, card))
        c.wait("!!document.getElementById('editpanel')", 180)
        time.sleep(1.0)
        check("13 endpoint missing: after a reload the unsaved edit is still flagged (kept in this browser, not lost silently)", c.js("!document.getElementById('savebanner').hidden") and c.js("!!document.querySelector('#editpanel .b-unsaved')"))
        c.js("document.querySelector('#savebanner button[data-act=retry]').click()")
        time.sleep(1.5)
        check("13 endpoint missing: Retry keeps it NOT SAVED while the endpoint is missing", c.js("!document.getElementById('savebanner').hidden"))
        check("13 the real corrections file was not written by the missing-endpoint run", len(doc()["edits"][card]["groups"]) == 1)
        errs = c.js("window.__errs || []")
    finally:
        edge.terminate()
        srvA.shutdown()
        srvB.shutdown()
    bad = [r for r in results if not r[1]]
    print("\n%d checks, %d failed" % (len(results), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
