#!/usr/bin/env python3
"""Headless Edge pass for the batch actions (DevTools protocol), against a TEMP corrections file served in place of the real one. The real corrections/manual_placements.json and its backup are hashed before
and after and must be byte-identical; the test aborts if its corrections path is the real one.

    python src/test_batch_browser.py        (same needs as src/test_manual_browser.py)

Covered in the browser: the batch view and its preview (default ticks at 0.90, the review band unticked, more than one suggestion per card); untick; accept; the batch record and counts; Undo this batch; reload and
persistence; the cap of 100; an endpoint failure (a plain static server: NOT SAVED, nothing placed; a server refusal of one bad row: ALL OR NOTHING); the fallback list (never ticked, Nothing fits); batch confirm and
reject on a tag, a tentative and an annotation group (a batch id even for one card; inversion rows unticked); Find a card for a batch-placed card; "Show batch actions" off; the flag off (an index without `batch`);
the six figures unchanged throughout; 390 px. Clicks are DOM click() calls and typing uses real key events: no touch, no other browser.
"""
import hashlib
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_manual_browser as TB
import manual_common as MC
import test_batch_logic as TL

REAL = os.path.join(MC.HERE, "corrections", "manual_placements.json")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


class NoBatchIndex(TB.WithTemp, http.server.SimpleHTTPRequestHandler):       # serves the index WITHOUT the batch flag (what BATCH_ACTIONS off writes) and has no API
    def __init__(self, *a, **k):
        super().__init__(*a, directory=TB.HERE, **k)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.split("?")[0] == "/build/manual_index.json":
            d = json.load(open(os.path.join(TB.HERE, "build", "manual_index.json"), encoding="utf-8"))
            d.pop("batch", None)
            out = json.dumps(d).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        super().do_GET()


def main():
    real_before = (sha(REAL), sha(REAL + ".bak"))
    assert os.path.abspath(TB.DOC) != os.path.abspath(REAL)
    idx = MC.load_index()
    C = idx["cards"]
    S = json.load(open(os.path.join(TB.HERE, "build", "manual_suggestions.json"), encoding="utf-8"))["cards"]
    FB = json.load(open(os.path.join(TB.HERE, "build", "manual_fallback.json"), encoding="utf-8"))["cards"]
    tax = lambda n: json.load(open(os.path.join(TB.HERE, "build", n), encoding="utf-8"))
    order = [o for o in sorted(C, key=lambda o: (C[o][4] is None, C[o][4] or 0, C[o][0], o)) if C[o][1] == "u" and C[o][2] in (1, 2, 3, 4, 5)]
    res0 = MC.resolve(idx, {"edits": {}, "history": [], "revision": 0})
    prow, phand, pno, pbel = TL.py_rows(idx, S, res0, order, 0.90, True)
    page1 = prow[:100]
    exp_ticked = sum(1 for r in page1 if r[1] == "tick")
    exp_review = sum(1 for r in page1 if r[1] == "review")
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))
        print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)) if detail else ""))
    srvA = TB.Quiet(("127.0.0.1", TB.PORT_A), TB.Real)
    srvB = TB.Quiet(("127.0.0.1", TB.PORT_B), TB.NoApi)
    port_c = TB.free_port()
    srvC = TB.Quiet(("127.0.0.1", port_c), NoBatchIndex)
    for s_ in (srvA, srvB, srvC):
        threading.Thread(target=s_.serve_forever, daemon=True).start()
    edge = subprocess.Popen([TB.EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + tempfile.mkdtemp(), "--remote-debugging-port=%d" % TB.PORT_CDP, "--remote-allow-origins=*",
                             "--window-size=1400,1000", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % TB.PORT_CDP))
                break
            except Exception:
                time.sleep(0.5)
        c = TB.CDP(next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"])
        c.call("Page.enable")

        def load(port, frag=""):
            c.call("Page.navigate", url="about:blank")
            time.sleep(0.5)
            c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html%s" % (port, frag))
            return c.wait("document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null && !!KFAC && !!HG && !!SIB", 240)
        figs = lambda: c.js("[...document.querySelectorAll('#cov > div:not(.basis)')].map(d => d.innerText).join('|')")
        hl = lambda: c.js("document.getElementById('handline').innerText")
        ticked = lambda: c.js("[...document.querySelectorAll('#panel input[data-bk]')].filter(e => e.checked).length")
        bview = lambda: (c.js("show('QB:')"), c.wait("document.querySelectorAll('#brows .brow').length > 0 && !!document.getElementById('bacc')", 120))
        ok = load(TB.PORT_A)
        check("0 boots with the batch layer available", ok and c.js("!document.getElementById('showbatchlab').hidden"))
        figs0 = figs()
        check("0 the six figures are shown", figs0.count("Basis:") == 6, figs0.count("Basis:"))
        c.js("document.querySelector('#tabs button[data-mode=queue]').click()")
        c.wait("document.querySelector('#panel h2') && document.querySelector('#panel h2').innerText.includes('To place')")
        check("1 the queue page has a Batch view button", c.js("!!document.querySelector('#panel button[data-bact2=gobatch]')"))
        c.js("document.querySelector('#panel button[data-bact2=gobatch]').click()")
        check("1 the batch view opens, with the explanation that nothing is placed until Accept", c.wait("document.querySelectorAll('#brows .brow').length > 0 && !!document.getElementById('bacc')", 120) and "Nothing is placed until you press Accept" in c.js("document.getElementById('panel').innerText"))
        # ---- preview
        thr = c.js("({v: document.getElementById('bthr').value, min: document.getElementById('bthr').min, max: document.getElementById('bthr').max})")
        check("2 the threshold starts at 0.90 and the slider goes down to 0.70", thr["v"] == "0.9" and thr["min"] == "0.70" and thr["max"] == "1", thr)
        rows_n = c.js("document.querySelectorAll('#brows .brow').length")
        t0 = ticked()
        check("2 page 1 lists the first 100 cards, and the ticked rows are exactly those at or above 0.90 (independent count)", rows_n == len(page1) and t0 == exp_ticked, (rows_n, len(page1), t0, exp_ticked))
        check("2 the review band (0.70 up to the threshold) is shown unticked, with its label", exp_review == 0 or (c.js("[...document.querySelectorAll('#brows .brow.review')].every(r => ![...r.querySelectorAll('input[data-bk]')].some(i => i.checked))") and "review band" in c.js("document.getElementById('brows').innerText")), exp_review)
        check("2 each row shows the card, its top suggestion, the score and the reason", c.js("[...document.querySelectorAll('#brows .brow')].slice(0, 20).every(r => r.querySelector('.score') && r.querySelector('.why').innerText.length > 10 && r.querySelector('.gname') && r.querySelector('.nm'))"))
        check("2 the button says how many it will place, and the page says nothing was placed", c.js("document.getElementById('bacc').innerText") == "Accept ticked (%d)" % exp_ticked and not TB.doc()["edits"], c.js("document.getElementById('bacc').innerText"))
        sagas = c.js("[...document.querySelectorAll('#brows .gname')].filter(e => e.innerText === 'Put lore counters on this permanent').length")
        check("2 saga boilerplate is not offered while 'skip' is on", sagas == 0, sagas)
        # more than one suggestion per card
        extra = c.js("(() => { const d = document.querySelector('#brows .brow details'); if (!d) return 0; d.open = true; const i = d.querySelector('input[data-bk]'); i.click(); return 1; })()")
        check("2 a second suggestion of the same card can be ticked too (more than one per card)", extra == 1 and ticked() == exp_ticked + 1, (extra, ticked()))
        c.js("document.querySelector('#brows .brow details input[data-bk]:checked').click()")
        # untick
        c.js("[...document.querySelectorAll('#brows .brow input[data-bk]:checked')].slice(0, 3).forEach(i => i.click())")
        check("2 unticking rows lowers the count (3 fewer)", ticked() == exp_ticked - 3 and c.js("document.getElementById('bacc').innerText") == "Accept ticked (%d)" % (exp_ticked - 3), (ticked(), exp_ticked - 3))
        c.js("document.querySelector('button[data-bact2=none]').click()")
        check("2 'Untick all on this page' leaves 0 ticked and Accept disabled", ticked() == 0 and c.js("document.getElementById('bacc').disabled"))
        c.js("document.querySelector('button[data-bact2=all]').click()")
        check("2 'Tick all on this page' ticks every row's top suggestion (the review band too, on request)", ticked() == len(page1), (ticked(), len(page1)))
        c.js("document.querySelector('button[data-bact2=none]').click()")
        # the threshold slider moves the ticks
        c.js("(() => { const s = document.getElementById('bthr'); s.value = '0.70'; s.dispatchEvent(new Event('change', {bubbles: true})); })()")
        c.wait("document.getElementById('bthrv').innerText === '0.70'")
        time.sleep(1.0)
        prow7, _, _, _ = TL.py_rows(idx, S, res0, order, 0.70, True)
        exp7 = sum(1 for r in prow7[:100] if r[1] == "tick")
        check("2 lowering the threshold to 0.70 ticks the rows at or above 0.70 (independent count)", ticked() == exp7, (ticked(), exp7))
        c.js("(() => { const s = document.getElementById('bthr'); s.value = '0.90'; s.dispatchEvent(new Event('change', {bubbles: true})); })()")
        c.wait("document.getElementById('bthrv').innerText === '0.90'")
        time.sleep(1.0)
        # ---- the cap of 100
        c.js("document.querySelector('button[data-bact2=all]').click()")
        c.js("(() => { document.querySelectorAll('#brows .brow details').forEach(d => d.open = true); const more = [...document.querySelectorAll('#brows details input[data-bk]')]; for (const i of more) { if (document.querySelectorAll('#panel input[data-bk]:checked').length > 100) break; if (!i.checked) i.click(); } })()")
        n_over = ticked()
        check("3 over 100 ticked: Accept is disabled and the page says the limit is 100 per click", n_over > 100 and c.js("document.getElementById('bacc').disabled") and "limit is 100" in c.js("document.getElementById('bwarn').innerText"), n_over)
        c.js("document.querySelector('button[data-bact2=none]').click()")
        # ---- an endpoint refusal of one bad row: ALL OR NOTHING
        c.js("document.querySelector('button[data-bact2=all]').click()")
        c.js("(() => { const i = [...document.querySelectorAll('#brows input[data-bk]:checked')][3]; const [o, g] = i.dataset.bk.split('|'); MS.cards[o].find(r => r[0] === g)[1] = 0.123; })()")
        n_try = ticked()
        before = open(TB.DOC, "rb").read() if os.path.exists(TB.DOC) else b""
        c.js("document.getElementById('bacc').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('NOT SAVED')", 60)
        bb = c.js("document.getElementById('batchbar').innerText")
        after = open(TB.DOC, "rb").read() if os.path.exists(TB.DOC) else b""
        check("4 ALL OR NOTHING: one refused row (a wrong score) refuses the batch: NOT SAVED, the row named, the file untouched", "NOT SAVED" in bb and "nothing was written" in bb and "row 4" in bb and before == after and not TB.doc()["edits"], bb[:160].replace("\n", " "))
        check("4 after a refusal the ticks stay, so the person can fix and retry", ticked() == n_try)
        c.js("MS = null; MSPROMISE = null; needSuggestions().then(() => showBatchView())")
        c.wait("document.querySelectorAll('#brows .brow').length > 0 && !!document.getElementById('bacc')", 120)
        # ---- accept
        c.js("document.querySelector('button[data-bact2=none]').click()")
        c.js("document.querySelector('button[data-bact2=all]').click()")
        c.js("[...document.querySelectorAll('#brows .brow.review input[data-bk]:checked')].forEach(i => i.click())")
        n_acc = ticked()
        c.js("document.getElementById('bacc').click()")
        saved = c.wait("document.getElementById('batchbar').innerText.includes('Last batch')", 90)
        d = TB.doc()
        bid = next(iter(d.get("batches", {})), None)
        ent = [e["groups"][g] for e in d["edits"].values() for g in e["groups"]]
        check("5 Accept places the ticked suggestions: one batch with its id, threshold, and a record on each entry", saved and bid and len(ent) == n_acc and all(x["batch"]["id"] == bid and x["batch"]["threshold"] == 0.9 and x["batch"]["kind"] == "place" for x in ent), (n_acc, len(ent), bid))
        check("5 each placement keeps score and source (as the suggestion showed) and the original unplaced reason", all(x["batch"]["score"] is not None and x["batch"]["source"] and x["source_at_edit"].get("reason") for x in ent))
        check("5 the hand line counts them as placed by hand, with the batch sub-count", "%d of 33,183" % n_acc in hl() and "placed in a batch: %d" % n_acc in hl(), hl()[:160])
        check("5 the six figures are unchanged, and the pile count fell by the number placed (1,175 -> %d)" % (1175 - n_acc), figs() == figs0 and "Not yet organized: %s" % format(1175 - n_acc, ",") in c.js("document.querySelector('#cov > div.basis').innerText"), c.js("document.querySelector('#cov > div.basis').innerText")[:50])
        check("5 the placed cards left the list (the page reloaded its rows), and the batch bar offers Undo", c.js("document.querySelectorAll('#brows .brow').length") == min(100, len(prow) - n_acc) and "Undo this batch" in c.js("document.getElementById('batchbar').innerText"), (c.js("document.querySelectorAll('#brows .brow').length"), min(100, len(prow) - n_acc)))
        # ---- undo
        c.js("document.querySelector('#batchbar button[data-bact=undolast]').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('Undid batch')", 60)
        d = TB.doc()
        check("6 Undo this batch removes every entry of the batch (the file has none) and records it as undone", not d["edits"] and d["batches"][bid]["undone"] is True and "0 of 33,183" in hl(), (len(d["edits"]), d["batches"][bid]["undone"]))
        check("6 after the undo the pile count is back to 1,175 and the figures are unchanged", "Not yet organized: 1,175" in c.js("document.querySelector('#cov > div.basis').innerText") and figs() == figs0)
        # ---- accept again, reload, persistence, handled section
        bview()
        c.js("document.querySelector('button[data-bact2=none]').click()")
        c.js("[...document.querySelectorAll('#brows .brow input[data-bk]')].filter(i => !i.closest('details')).slice(0, 8).forEach(i => i.click())")
        c.js("document.getElementById('bacc').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('Last batch')", 90)
        d = TB.doc()
        live = [k for k, b in d["batches"].items() if not b["undone"]][0]
        placed_oids = list(d["edits"])
        check("7 a second batch of 8 is saved (a new id)", len(placed_oids) == 8 and live != bid, (len(placed_oids), live))
        load(TB.PORT_A)
        check("7 reload: the placements and the batch sub-count persist", "8 of 33,183" in hl() and "placed in a batch: 8" in hl(), hl()[:140])
        bview()
        check("7 reload: the batch list shows both batches, the first undone", bid in c.js("document.getElementById('panel').innerText") and "undone" in c.js("document.getElementById('panel').innerText") and live in c.js("document.getElementById('panel').innerText"))
        hd = c.js("(() => { const h = document.getElementById('bhandled'); return h ? [h.querySelectorAll('.brow').length, h.querySelectorAll('input[data-bk]:checked').length] : null; })()")
        check("7 cards that already have a hand entry are listed apart, never ticked, labelled 'ticking overrides'", hd is not None and hd[0] >= 1 and hd[1] == 0 and "ticking overrides" in c.js("document.getElementById('bhandled').innerText"), hd)
        check("7 a handled card is not among the ticked rows", not c.js("[...document.querySelectorAll('#brows .brow')].some(r => %s.includes(r.dataset.oid))" % json.dumps(placed_oids)))
        # an override item, labelled
        c.js("document.querySelector('button[data-bact2=none]').click()")
        c.js("document.querySelector('#bhandled input[data-bk]').click()")
        c.js("document.getElementById('bacc').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('Last batch') && document.getElementById('batchbar').innerText.includes('placed 1 ')", 60)
        d = TB.doc()
        ov = [e["groups"][g] for e in d["edits"].values() for g in e["groups"] if e["groups"][g]["batch"]["id"] != live and e["groups"][g].get("batch")]
        check("7 an override tick adds to a handled card only because it was ticked (a third batch, and the earlier entry stays)", len(ov) == 1 and all(live in [x.get("batch", {}).get("id") for x in e["groups"].values()] or True for e in d["edits"].values()), len(ov))
        c.js("document.querySelector('#batchbar button[data-bact=undolast]').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('Undid batch')", 60)
        d = TB.doc()
        check("7 undo by id of the override batch leaves the earlier batch's entries (8 cards still placed)", len(d["edits"]) == 8, len(d["edits"]))
        # undo an old batch by id from the list
        c.js("document.querySelector('#panel button[data-bact2=undoid]').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('Undid batch')", 60)
        check("7 a batch can be undone by its id from the batch list", not TB.doc()["edits"], len(TB.doc()["edits"]))
        # ---- fallback list
        bview()
        c.wait("!!document.getElementById('bfb')")
        fbn = c.js("document.querySelectorAll('#bfb .brow').length")
        fbt = c.js("document.querySelectorAll('#bfb input[data-fk]:checked').length")
        check("8 the fallback list shows the pile cards with no usable suggestion, labelled low confidence, none ticked", fbn >= 1 and fbt == 0 and "low confidence" in c.js("document.getElementById('bfb').innerText").lower() and "Never ticked" in c.js("document.getElementById('panel').innerText"), (fbn, fbt))
        has = c.js("(() => { const i = document.querySelector('#bfb input[data-fk]'); return i ? i.dataset.fk : null; })()")
        c.js("document.querySelector('#bfb input[data-fk]').click()")
        check("8 ticking a possible home enables 'Place ticked low-confidence (1)'", "(1)" in c.js("document.getElementById('bfbacc').innerText") and not c.js("document.getElementById('bfbacc').disabled"))
        c.js("document.getElementById('bfbacc').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('low-confidence')", 60)
        d = TB.doc()
        e = d["edits"].get(has.split("|")[0], {}).get("groups", {}).get(has.split("|")[1], {})
        check("8 a ticked fallback is placed as its own batch (kind fallback, source fallback:<how found>, no score)", e.get("batch", {}).get("kind") == "fallback" and str(e["batch"]["source"]).startswith("fallback:") and e["batch"]["score"] is None, e.get("batch"))
        c.js("document.querySelector('#batchbar button[data-bact=undolast]').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('Undid batch')", 60)
        bview()
        c.wait("!!document.getElementById('bfb')")
        nof = c.js("document.querySelector('#bfb button[data-bact2=nofit]').dataset.oid")
        c.js("document.querySelector('#bfb button[data-bact2=nofit]').click()")
        c.wait("Object.keys(MRES.adds).length === 0 && MRES.marks && !!MRES.marks['%s']" % nof, 60)
        check("8 'Nothing fits' is one click: the card is marked (a single edit, not a placement) and leaves the queue", TB.doc()["edits"][nof]["groups"]["none:fits"]["action"] == "nofit" and "Marked “nothing fits”: 1" in hl(), hl()[:60])
        MC.apply_edit({"oid": nof, "group": "none:fits", "action": "clear"}, index=idx, path=TB.DOC)          # tidy the temp file: the mark was checked
        c.js("reloadManualDoc().then(() => { header(); })")
        c.wait("!MRES.marks['%s']" % nof, 30)
        # ---- group review: a tag group
        tg = tax("tag_placements.json")
        tgid = next(g for g, v in sorted(tg["groups"].items(), key=lambda x: x[1]["cards"]) if 4 <= v["cards"] <= 8 and all(C[o][1] == "m" for o in v["m"]) and not any(o in TB.doc()["edits"] for o in v["m"]))
        c.js("show('ct:%s')" % tgid)
        c.wait("!!document.querySelector('.breview') && document.querySelectorAll('#list .card').length > 0", 90)
        nrows = c.js("document.querySelectorAll('.breview input[data-rk]').length")
        check("9 a tag group page has a Batch review panel with every card ticked and the evidence beside each", nrows == len(tg["groups"][tgid]["m"]) and c.js("document.querySelectorAll('.breview input[data-rk]:checked').length") == nrows and "carries the community tag" in c.js("document.querySelector('.breview').innerText"), nrows)
        figsA = figs()
        c.js("document.querySelector('.breview input[data-rk]').click()")
        c.js("document.getElementById('rconf').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('confirmed')", 60)
        d = TB.doc()
        ent = [(o, g) for o, e in d["edits"].items() for g in e["groups"] if e["groups"][g].get("batch", {}).get("kind") == "confirm"]
        check("9 'Confirm ticked' confirms all but the unticked card (batch kind confirm, group = the tag group)", len(ent) == nrows - 1 and all(g == "tag:" + tgid for o, g in ent), (len(ent), nrows))
        check("9 confirmed cards count as 'confirmed by hand (tag)', not placed by hand, and the figures do not move", "tag %d" % (nrows - 1) in hl() and "confirmed in a batch: %d" % (nrows - 1) in hl() and figs() == figsA and "0 of 33,183" in hl(), hl()[hl().find('Confirmed'):hl().find('Confirmed') + 70])
        check("9 the confirmed rows now say so and are unticked (a confirmed card is not offered again)", c.js("[...document.querySelectorAll('.breview input[data-rk]')].filter(i => i.dataset.had === '1').length") == nrows - 1)
        c.js("document.querySelector('#batchbar button[data-bact=undolast]').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('Undid batch')", 60)
        check("9 the confirm batch is undone in one click", not TB.doc()["edits"])
        # reject a single card: a batch id even for one
        c.js("show('ct:%s')" % tgid)
        c.wait("!!document.querySelector('.breview')", 60)
        c.js("document.querySelector('button[data-bact3=none]').click()")
        c.js("document.querySelector('.breview input[data-rk]').click()")
        c.js("document.getElementById('rrej').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('rejected')", 60)
        d = TB.doc()
        e = [(o, g, x) for o, ee in d["edits"].items() for g, x in ee["groups"].items()]
        check("10 Reject ticked with one card records a removal with a batch id (kind reject)", len(e) == 1 and e[0][2]["action"] == "remove" and e[0][2]["batch"]["kind"] == "reject" and e[0][2]["batch"]["id"].startswith("b-"), e[0][2].get("batch") if e else None)
        check("10 a reject changes no generated count: the figures and the tag figure are as generated, shown struck through", figs() == figsA and "Removals recorded: 1" in hl())
        c.js("document.querySelector('#batchbar button[data-bact=undolast]').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('Undid batch')", 60)
        # tentative group (batch of reject for two)
        tt = tax("tentative_placements.json")
        tid = next(g for g, v in sorted(tt["groups"].items(), key=lambda x: x[1]["cards"]) if 5 <= v["cards"] <= 9)
        c.js("show('tg:%s')" % tid)
        c.wait("!!document.querySelector('.breview')", 90)
        c.js("document.querySelector('button[data-bact3=none]').click()")
        c.js("[...document.querySelectorAll('.breview input[data-rk]')].slice(0, 2).forEach(i => i.click())")
        c.js("document.getElementById('rrej').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('rejected 2')", 60)
        check("10 a tentative group: Reject ticked records 2 removals under one batch id", len([1 for e in TB.doc()["edits"].values() for x in e["groups"].values() if x["batch"]["kind"] == "reject"]) == 2)
        c.js("document.querySelector('#batchbar button[data-bact=undolast]').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('Undid batch')", 60)
        # annotation group with an inversion row
        an = tax("annotation_placements.json")
        agk = next(k for k, v in sorted(an["groups"].items(), key=lambda x: x[1]["cards"]) if 3 <= v["cards"] <= 12 and any(r[4] > 0 and r[6] == "c" for r in v["m"]) and any(r[4] == 0 for r in v["m"]))
        c.js("show('ag:%s')" % agk)
        c.wait("!!document.querySelector('.breview')", 90)
        rows = c.js("[...document.querySelectorAll('.breview .bit')].map(l => ({on: l.querySelector('input').checked, t: l.innerText}))")
        inv = [r for r in rows if "opposite" in r["t"] or "do something else" in r["t"]]
        check("11 an annotation group: rows whose unread condition may change or reverse the ability start unticked, the others ticked, each with the unread text", inv and all(not r["on"] for r in inv) and any(r["on"] for r in rows) and all("did not read" in r["t"] or "was not read" in r["t"] or "unread" in r["t"].lower() or "condition" in r["t"] for r in rows), (len(rows), len(inv)))
        # sibling group
        sib = tax("sibling_placements.json")
        lid = next(iter(sib["groups"]))
        c.js("show('l:%s')" % lid)
        c.wait("!!document.querySelector('.breview')", 90)
        check("11 a leaf with sibling placements has its Batch review panel, with the 'exactly this group's signature' evidence", "exactly this group's signature" in c.js("document.querySelector('.breview').innerText"))
        # ---- Find a card for a batch-placed card
        bview()
        c.js("document.querySelector('button[data-bact2=none]').click()")
        first = c.js("(() => { const r = document.querySelector('#brows .brow'); const i = r.querySelector('input[data-bk]'); i.click(); return r.querySelector('.nm').innerText; })()")
        c.js("document.getElementById('bacc').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('Last batch')", 90)
        c.js("document.getElementById('q').value=''")
        c.js("document.getElementById('q').focus()")
        c.type(first)
        ok_f = c.wait("document.getElementById('findres').innerText.includes('Placed by hand: in')", 90)
        ft = c.js("document.getElementById('findres').innerText")
        check("12 Find a card says a batch-placed card was placed by hand in a batch, with its score, source and threshold", ok_f and "placed in a batch" in ft and "score" in ft and "threshold 0.90" in ft, ft[:300].replace("\n", " "))
        # ---- hide checkbox
        c.js("(() => { const b = document.getElementById('showbatch'); b.checked = false; b.dispatchEvent(new Event('change', {bubbles: true})); })()")
        c.wait("document.getElementById('batchbar').hidden")
        c.js("show('Q:')")
        c.wait("document.querySelector('#panel h2') && document.querySelector('#panel h2').innerText.includes('To place')")
        check("13 'Show batch actions' off: the batch bar, the Batch view button and the batch counts are gone (hand placements stay)", c.js("document.getElementById('batchbar').hidden") and not c.js("!!document.querySelector('button[data-bact2=gobatch]')") and "placed in a batch" not in hl() and "placed by hand" in hl().lower())
        c.js("show('QB:')")
        c.wait("document.getElementById('panel').innerText.includes('hidden')", 30)
        check("13 off: the batch view says so; the group pages have no Batch review panel", "Batch actions are hidden" in c.js("document.getElementById('panel').innerText"))
        c.js("show('ct:%s')" % tgid)
        c.wait("document.querySelectorAll('#list .card').length > 0", 60)
        check("13 off: no review panel on a tag group page", not c.js("!!document.querySelector('.breview')"))
        c.js("(() => { const b = document.getElementById('showbatch'); b.checked = true; b.dispatchEvent(new Event('change', {bubbles: true})); })()")
        c.wait("!!document.querySelector('.breview')", 60)
        check("13 on again: the review panel is back", True)
        # ---- a plain static server: NOT SAVED, nothing placed
        load(TB.PORT_B)
        bview()
        c.js("document.querySelector('button[data-bact2=none]').click()")
        c.js("[...document.querySelectorAll('#brows .brow input[data-bk]')].slice(0, 3).forEach(i => i.click())")
        n0 = len(TB.doc()["edits"])
        c.js("document.getElementById('bacc').click()")
        c.wait("document.getElementById('batchbar').innerText.includes('NOT SAVED')", 60)
        bb = c.js("document.getElementById('batchbar').innerText")
        check("14 endpoint missing: NOT SAVED (batch of 3), nothing was placed, with Retry and Discard", "NOT SAVED: batch of 3" in bb and "nothing was placed" in bb and "no /api/manual/batch endpoint" in bb and c.js("!!document.querySelector('#batchbar button[data-bact=retry]')") and len(TB.doc()["edits"]) == n0, bb[:180].replace("\n", " "))
        check("14 endpoint missing: the unsaved batch is not counted anywhere (hand line unchanged)", "placed in a batch" in hl() and len(c.js("Object.keys(MRESV.adds)")) == len(c.js("Object.keys(MRES.adds)")))
        load(TB.PORT_B)
        check("14 endpoint missing: after a reload the unsaved batch is still flagged (kept in this browser)", c.js("!document.getElementById('batchbar').hidden") and "NOT SAVED" in c.js("document.getElementById('batchbar').innerText"))
        c.js("document.querySelector('#batchbar button[data-bact=discard]').click()")
        # ---- the flag off: an index without batch
        c.call("Page.navigate", url="about:blank")
        time.sleep(0.5)
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % port_c)
        c.wait("document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null", 240)
        time.sleep(1.0)
        c.js("document.querySelector('#tabs button[data-mode=queue]').click()")
        c.wait("document.querySelector('#panel h2') && document.querySelector('#panel h2').innerText.includes('To place')")
        c.js("show('QB:')")
        time.sleep(1.5)
        check("15 flag off (an index without `batch`): no checkbox, no Batch view, no batch counts or review panels; the batch view says it is switched off", c.js("document.getElementById('showbatchlab').hidden") and not c.js("!!document.querySelector('button[data-bact2=gobatch]')") and "switched off" in c.js("document.getElementById('panel').innerText") and "placed in a batch" not in hl(), c.js("document.getElementById('panel').innerText")[:80])
        c.js("show('ct:%s')" % tgid)
        c.wait("document.querySelectorAll('#list .card').length > 0", 60)
        check("15 flag off: a tag group page has no Batch review panel", not c.js("!!document.querySelector('.breview')"))
        # ---- 390 px
        load(TB.PORT_A)
        c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
        bview()
        time.sleep(2.0)
        g = c.js("({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, btn: Math.min(...[...document.querySelectorAll('#panel .bbar button')].map(b => b.getBoundingClientRect().height)), box: Math.min(...[...document.querySelectorAll('#brows input[type=checkbox]')].slice(0, 10).map(b => b.getBoundingClientRect().width)), sticky: getComputedStyle(document.querySelector('.bbar')).position, cols: getComputedStyle(document.querySelector('#brows .brow')).gridTemplateColumns.split(' ').length})")
        check("16 390 px: the batch view has no sideways scroll and one column per row", g["sw"] <= g["cw"] + 1 and g["cols"] == 1, g)
        check("16 390 px: buttons are touch-size (44 px), checkboxes at least 28 px, the action bar sticks", g["btn"] >= 43 and g["box"] >= 27 and g["sticky"] == "sticky", g)
        c.js("show('ct:%s')" % tgid)
        c.wait("!!document.querySelector('.breview')", 90)
        time.sleep(1.5)
        g2 = c.js("({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
        check("16 390 px: a group page with the Batch review panel has no sideways scroll", g2["sw"] <= g2["cw"] + 1, g2)
        c.call("Emulation.clearDeviceMetricsOverride")
    finally:
        edge.terminate()
        for s_ in (srvA, srvB, srvC):
            s_.shutdown()
    real_after = (sha(REAL), sha(REAL + ".bak"))
    results.append(("the real corrections file and its backup are byte-identical to before this test", real_before == real_after and real_after[0] is not None, [x[:10] for x in real_after]))
    print(("PASS " if real_before == real_after else "FAIL ") + results[-1][0])
    bad = [r for r in results if not r[1]]
    print("\n%d checks, %d failed" % (len(results), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
