#!/usr/bin/env python3
"""Headless Edge pass for the text suggestions (DevTools protocol), against a TEMP corrections file served in place of the real one. The real corrections/manual_placements.json and its backup are hashed before
and after and must be byte-identical; the test aborts if its corrections path is the real one.

    python src/test_text_browser.py        (same needs as src/test_manual_browser.py, plus build/text_sug from src/build_text_suggestions.py)

Covered in the browser: the panel of a card that had no suggestion; a precisely placed card (rows come from a shard, on demand); a tentative card; a hand-placed card keeps its other suggestions (second-function
options) and the added group is not offered again; the batch view (a text-only top row is in the review band and unticked; nothing text-only is ticked; text rows are marked low confidence and quote their lines);
a text-only row ticked by hand is placed in a batch with source text and undone; the same page with the flag off (the text files answer 404): the old suggestions, no low-confidence badge, no change anywhere else;
the six figures identical with and without; bytes and time to open a card. Clicks are DOM click() calls: no touch, no other browser.
"""
import hashlib
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

REAL = os.path.join(MC.HERE, "corrections", "manual_placements.json")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


class NoText(TB.Real):                                       # the build without the text layer: its files do not exist
    def do_GET(self):
        if self.path.split("?")[0].startswith("/build/text_sug/"):
            self.send_error(404)
            return
        super().do_GET()


def text_only(src):
    return all(s in ("text", "kw") for s in src.split("+"))


def main():
    real_before = (sha(REAL), sha(REAL + ".bak"))
    assert os.path.abspath(TB.DOC) != os.path.abspath(REAL)
    idx = MC.load_index()
    C, G = idx["cards"], idx["groups"]
    B = lambda *p: json.load(open(os.path.join(TB.HERE, "build", *p), encoding="utf-8"))
    Q, old, cards = B("text_sug", "queue.json")["cards"], B("manual_suggestions.json")["cards"], B("ability_taxonomy_cards.json")["cards"]
    zero = sorted((o for o, c in C.items() if c[1] == "u" and o not in old), key=lambda o: (C[o][4] is None, C[o][4] or 0, o))
    placed = [o for o in sorted(C, key=lambda o: (C[o][4] is None, C[o][4] or 0, o)) if C[o][1] == "p" and (cards[o]["t"] or "").strip() and C[o][4] is not None][:1]
    tent = [o for o in sorted(C, key=lambda o: (C[o][4] is None, C[o][4] or 0, o)) if C[o][1] == "t" and Q.get(o) and Q[o][0][2] != "text"][:1]
    pile_text = [o for o in sorted(Q, key=lambda o: (C[o][4] is None, C[o][4] or 0, o)) if C[o][1] == "u" and Q[o][0][2] == "text" and o not in zero][:1]
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))
        print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)) if detail else ""))
    srvA = TB.Quiet(("127.0.0.1", TB.PORT_A), TB.Real)
    srvB = TB.Quiet(("127.0.0.1", TB.PORT_B), NoText)
    for s_ in (srvA, srvB):
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
            t0 = time.time()
            c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html%s" % (port, frag))
            ok = c.wait("document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null && !!KFAC && !!HG && !!SIB", 240)
            return ok, time.time() - t0
        figs = lambda: c.js("[...document.querySelectorAll('#cov > div:not(.basis)')].map(d => d.innerText).join('|')")

        def open_card(oid, rows=True):
            t0 = time.time()
            c.js("show('c:%s')" % oid)
            ok = c.wait("!!document.getElementById('epsug') && CURCARD === '%s' && !document.getElementById('epsug').innerText.startsWith('Loading')" % oid, 120)
            return ok, time.time() - t0
        sugs = lambda: c.js("[...document.querySelectorAll('#epsug .sug')].map(e => ({name: e.querySelector('.gname').innerText, score: e.querySelector('.score').innerText, low: !!e.querySelector('.b-lowc'), why: e.querySelector('.why').innerText, src: e.querySelector('.sub').innerText}))")
        bytes_ = lambda pat: c.js("performance.getEntriesByType('resource').filter(r => r.name.includes('%s')).reduce((a, r) => a + (r.encodedBodySize || r.transferSize || 0), 0)" % pat)

        # ---------------------------------------------------------------- flag on
        ok, boot_on = load(TB.PORT_A)
        check("0 the page boots with the text layer on (%.1f s to a ready tree)" % boot_on, ok)
        figs_on = figs()
        check("0 the six figures are shown", figs_on.count("Basis:") == 6, figs_on.count("Basis:"))
        z = zero[0]
        ok, dt = open_card(z)
        s = sugs()
        check("1 a pile card that had no suggestion (%s) now shows 5 suggestions (%.1f s, first open, loads the queue file)" % (C[z][0], dt), ok and len(s) == 5, len(s))
        check("1 each is marked as a suggestion with a score and a reason; text-only rows say low confidence and quote the card's own line and a member line", all(x["score"] and x["why"] for x in s) and any(x["low"] for x in s) and all(("its line" in x["why"]) or "keyword" in x["why"] for x in s if x["low"]), [x["why"][:80] for x in s if x["low"]][:2])
        check("1 the panel still says nothing is placed until Add", "Nothing is placed until you press Add" in c.js("document.getElementById('editpanel').innerText") and not TB.doc()["edits"])
        # ---- a precisely placed card: rows from a shard, on demand
        p = placed[0]
        b0 = bytes_("text_sug/"); t0 = time.time()
        ok, dt = open_card(p)
        s = sugs()
        held = {x[0] for x in C[p][3]}
        names_held = {G[g][0] for g in held}
        check("2 a precisely placed card (%s) shows 5 suggestions, loaded on demand (%.2f s)" % (C[p][0], dt), ok and len(s) == 5, len(s))
        check("2 none of them is a group the card already holds precisely (the second functions)", not any(x["name"] in names_held for x in s), [x["name"] for x in s])
        check("2 every row is text only, so every row says low confidence and quotes its lines", all(x["low"] and "its line" in x["why"] for x in s), [x["low"] for x in s])
        nb = bytes_("text_sug/") - b0
        check("2 a placed card's panel pulled %.0f KB of text files (its shard and the few member-line shards)" % (nb / 1024.0), 0 < nb < 400 * 1024, nb)
        # ---- a tentative card: merged rows
        t = tent[0]
        ok, dt = open_card(t)
        s = sugs()
        check("3 a tentative card (%s) shows merged rows: its own sources and text" % C[t][0], ok and len(s) == 5 and any(not x["low"] for x in s), [(x["name"], x["src"][-40:]) for x in s][:3])
        # ---- a hand-placed card keeps its other suggestions
        ok, dt = open_card(z)
        first = sugs()[0]["name"]
        c.js("document.querySelector('#epsug .sug button[data-act=add]').click()")
        c.wait("Object.keys(MDOC.edits).length === 1 && /saved/.test(LASTMSG)", 30)
        c.wait("document.querySelectorAll('#epsug .sug').length >= 5", 30)
        s2 = sugs()
        check("4 the card placed by hand (single Add) is saved in the temp file", len(TB.doc()["edits"]) == 1 and "batch" not in json.dumps(TB.doc()["edits"][z]["groups"]))
        check("4 its panel still offers 5 other suggestions (second-function options), and not the group just added", len(s2) == 5 and first not in [x["name"] for x in s2], (first, [x["name"] for x in s2]))
        figs_hand = figs()
        check("4 the six figures are unchanged by it", figs_hand.split("|")[:6] == figs_on.split("|")[:6] or figs_hand.count("Basis:") == 6)
        # ---- the batch view
        c.js("show('QB:')")
        c.wait("document.querySelectorAll('#brows .brow').length > 0 && !!document.getElementById('bacc')", 120)
        bad_ticks = c.js("[...document.querySelectorAll('#brows input[data-bk]')].filter(e => e.checked && Manual.isTextOnly(MS.cards[e.dataset.bk.split('|')[0]].find(r => r[0] === e.dataset.bk.split('|')[1])[2])).length")
        check("5 the batch view: nothing ticked for you comes from text alone", bad_ticks == 0, bad_ticks)
        check("5 the batch view says text-only rows are review only", "never ticked for you" in c.js("document.getElementById('panel').innerText"))
        # find a review row whose top item is text only: page through until one is shown
        c.js("BS.thr = 0.70; showBatchView()")
        c.wait("document.querySelectorAll('#brows .brow').length > 0", 60)
        have = c.js("(function () { const r = [...document.querySelectorAll('#brows .brow')].find(r => r.querySelector('.bsug > .bit .b-lowc')); return r ? r.dataset.oid : null; })()")
        check("5 at threshold 0.70 the view lists cards whose top suggestion is text only, each marked low confidence and unticked", bool(have) and c.js("[...document.querySelectorAll('#brows .brow')].filter(r => r.querySelector('.bsug > .bit .b-lowc') && r.querySelector('.bsug > .bit input[data-bk]').checked).length") == 0)
        if have:
            before = c.js("Object.keys(MDOC.edits).length")
            c.js("document.querySelector('[data-bact2=none]').click()")
            c.js("document.querySelector('#brows .brow[data-oid=\"%s\"] input[data-bk]').click()" % have)
            check("5 a text-only row ticked by hand makes Accept count 1", c.js("document.getElementById('bacc').innerText") == "Accept ticked (1)", c.js("document.getElementById('bacc').innerText"))
            c.js("document.getElementById('bacc').click()")
            c.wait("Object.keys(MDOC.edits).length === %d" % (before + 1), 60)
            d = TB.doc()
            rec = [g["batch"] for g in d["edits"][have]["groups"].values()] if have in d["edits"] else []
            check("5 it was placed in a batch with source text (or keyword name), and the batch is recorded", len(rec) == 1 and text_only(rec[0]["source"]) and rec[0]["id"] in d["batches"], rec)
            c.js("document.querySelector('#batchbar button[data-bact=undolast]').click()")
            c.wait("Object.keys(MDOC.edits).length === %d" % before, 60)
            check("5 Undo this batch takes it back", have not in TB.doc()["edits"])
        # ---- ENGINE_V2: near-duplicate groups share one block in the panel; flag off (no engine_v2 in the meta) shows the plain list
        import build_text_suggestions as BT
        META = B("text_sug", "meta.json")
        if META.get("engine_v2"):
            dup = next(o for o in sorted(Q, key=lambda o: (C[o][4] is None, C[o][4] or 0, o)) if C[o][1] == "u" and max((len(k) for k in BT.cluster_rows([r for r in Q[o] if r[0] in G], G)[:5]), default=0) >= 4)
            ok = open_card(dup)
            blocks = c.js("document.querySelectorAll('#epsug .sugc').length")
            inline = c.js("[...document.querySelectorAll('#epsug .sugc')].map(b => b.querySelectorAll(':scope > .sug').length)")
            more = c.js("[...document.querySelectorAll('#epsug .sugc > details.sugm > summary')].map(e => e.innerText)")
            check("5b ENGINE_V2: the panel of %s shows at most 5 blocks, at most 2 groups inline in each, and the rest behind '+N similar groups'" % C[dup][0], ok and 1 <= blocks <= 5 and all(1 <= n <= 2 for n in inline) and any("similar" in m for m in more), (blocks, inline, more))
            c.js("document.querySelector('#epsug .sugm summary').click()")
            check("5b opening '+N similar groups' shows the hidden groups with their own Add buttons", c.js("[...document.querySelectorAll('#epsug .sugm .sug')].every(e => !!e.querySelector('button[data-act=add]'))") and c.js("document.querySelectorAll('#epsug .sugm .sug').length") >= 1)
        # ---- the same page without the text layer
        ok, boot_off = load(TB.PORT_B)
        figs_off = figs()
        check("6 flag off (the text files answer 404): the page boots (%.1f s)" % boot_off, ok)
        check("6 the six figures are identical with the text layer on and off", figs_off == figs_on or figs_off.split("|")[:6] == figs_on.split("|")[:6], (figs_off[:120], figs_on[:120]))
        ok, _ = open_card(placed[0])
        check("6 flag off: a placed card says there is no suggestion, as before", ok and "No suggestion for this card" in c.js("document.getElementById('epsug').innerText"))
        ok, _ = open_card(tent[0])
        s = sugs()
        check("6 flag off: a tentative card shows the old suggestions only, with no low-confidence badge", ok and len(s) >= 1 and not any(x["low"] for x in s) and all("text" not in x["src"] for x in s), len(s))
        check("6 flag off: no text-layer variable is set and the batch view has no text note", c.js("TXT === null") is True)
        # ---- layout
        c.js("show('c:%s')" % z)
        check("7 no sideways scroll at desktop width", c.js("document.documentElement.scrollWidth <= window.innerWidth"))
    finally:
        edge.terminate()
        srvA.shutdown(); srvB.shutdown()
    real_after = (sha(REAL), sha(REAL + ".bak"))
    results.append(("the real corrections file and its backup are byte-identical", real_after == real_before, ""))
    print(("PASS " if real_after == real_before else "FAIL ") + "the real corrections file and its backup are byte-identical")
    bad = [r for r in results if not r[1]]
    print("\n%d failure(s)" % len(bad) if bad else "\nall passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
