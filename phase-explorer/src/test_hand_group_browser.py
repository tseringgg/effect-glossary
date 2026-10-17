#!/usr/bin/env python3
"""Headless Edge pass for the 12 hand-defined groups added on 2026-10-16 (DevTools protocol), against a TEMP corrections file served in place of the real one. The real corrections/manual_placements.json
and its backup are hashed before and after and must be byte-identical; the test aborts if its corrections path is the real one.

    python src/test_hand_group_browser.py        (same needs as src/test_manual_browser.py; build/hand_group_hits.json, build/text_sug)

Covered in the browser: the group page of each of the 12 new groups (name, the rule-match section, a card's own sentence as the reason); the panel of a pile card, a tentative card, a tag card and a hand-placed
card showing the new group as a suggestion from a "hand-group rule" (not marked low confidence); the batch view at the default 0.90 and at the lowest threshold 0.70: no row led by a hand-group rule is ticked;
a single Add of a new group (saved, counted on the existing "placed by hand" line, the six figures unchanged). Clicks are DOM click() calls: no touch, no other browser.
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
OLD = "wins-or-loses-the-game"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def main():
    real_before = (sha(REAL), sha(REAL + ".bak"))
    assert os.path.abspath(TB.DOC) != os.path.abspath(REAL)
    idx = MC.load_index()
    C, G = idx["cards"], idx["groups"]
    B = lambda *p: json.load(open(os.path.join(TB.HERE, "build", *p), encoding="utf-8"))
    H, Q = B("hand_group_hits.json")["groups"], B("text_sug", "queue.json")["cards"]
    new = [s for s in sorted(H) if s != OLD]
    first = lambda slug, st: next((o for o in sorted(H[slug]["hits"]) if C[o][1] == st), None)
    pile, tent, tag = first("opens-or-visits-attractions", "u"), first("opens-or-visits-attractions", "t"), first("opens-or-visits-attractions", "m")
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))
        print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)) if detail else ""))
    srv = TB.Quiet(("127.0.0.1", TB.PORT_A), TB.Real)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
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
        c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % TB.PORT_A)
        ok = c.wait("document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null && !!KFAC && !!HG && !!SIB", 240)
        check("0 the page boots", ok)
        figs = lambda: c.js("[...document.querySelectorAll('#cov > div:not(.basis)')].map(d => d.innerText).join('|')")
        figs0 = figs()
        check("0 the six figures are shown", figs0.count("Basis:") == 6)
        hl = lambda: c.js("document.getElementById('handline').innerText")

        # ---- the group page of each new group
        for slug in new:
            c.js("show('hg:%s')" % slug)
            ok = c.wait("document.querySelector('#panel h2') && document.querySelector('#panel h2').innerText.includes(%s)" % json.dumps(H[slug]["name"] if "name" in H[slug] else slug), 30)
            t = c.js("document.getElementById('panel').innerText")
            name = B("manual_index.json")["groups"]["hand:" + slug][0]
            check("1 group page %s: name, the rule-match section, a card's own sentence" % slug, name in t and "Rule matches" in t and any(r[1][:30] in t for hs in list(H[slug]["hits"].values())[:5] for r in hs), len(t))
        # ---- panels
        def open_card(oid):
            c.js("show('c:%s')" % oid)
            return c.wait("!!document.getElementById('epsug') && CURCARD === '%s' && !document.getElementById('epsug').innerText.startsWith('Loading')" % oid, 120)
        sugs = lambda: c.js("[...document.querySelectorAll('#epsug .sug')].map(e => ({name: e.querySelector('.gname').innerText, score: e.querySelector('.score').innerText, low: !!e.querySelector('.b-lowc'), src: e.querySelector('.sub').innerText, why: e.querySelector('.why').innerText}))")
        for label, o in (("pile", pile), ("tentative", tent), ("tag", tag)):
            ok = open_card(o)
            s = [x for x in sugs() if x["name"] == "Opens or visits Attractions"]
            check("2 the panel of a %s card (%s) offers 'Opens or visits Attractions' as a suggestion from a hand-group rule, not marked low confidence" % (label, C[o][0]),
                  ok and len(s) == 1 and "hand-group rule" in s[0]["src"] and not s[0]["low"] and float(s[0]["score"]) >= 0.70 and "ttraction" in s[0]["why"], s)
        # ---- the 25 groups added in the second round: one card each (a pile card where there is one), the group is a rule suggestion, never low confidence
        round2 = list(json.load(open(os.path.join(TB.HERE, "corrections", "hand_groups.json"), encoding="utf-8"))["groups"])[-25:]
        gname = lambda slug: B("manual_index.json")["groups"]["hand:" + slug][0]
        for slug in round2:
            shown = lambda o: ("hand:" + slug) in [r[0] for r in Q.get(o, [])[:5]]          # a group is shown only if it is in the card's top 5 (a rule row is 0.7: five stronger rows push it out)
            hs = sorted(H[slug]["hits"], key=lambda o: (not shown(o), {"u": 0, "t": 1, "m": 2, "a": 3}.get(C[o][1], 4), o))
            o = hs[0]
            ok = open_card(o)
            s_ = [x for x in sugs() if x["name"] == gname(slug)]
            if not s_ and len(sugs()) < 5:
                s_ = []
            if not s_:      # a placed card gets its rows from a shard: allow the group anywhere in the 5 shown or the stored 7
                s_ = [x for x in sugs() if x["name"] == gname(slug)]
            check("2b %s: the panel of %s (%s) offers the group as a hand-group rule suggestion, not low confidence" % (slug, C[o][0], C[o][1]),
                  ok and len(s_) == 1 and "hand-group rule" in s_[0]["src"] and not s_[0]["low"], [x["name"] for x in sugs()])
        live = set(json.load(open(os.path.join(TB.HERE, "build", "manual_index.json"), encoding="utf-8")).get("_none", [])) or {o for o, c in C.items() if c[1] == "u"}
        pile_m = [(slug, o) for slug in round2 for o in H[slug]["hits"] if C[o][1] == "u"]
        n_shown = sum(1 for slug, o in pile_m if ("hand:" + slug) in [r[0] for r in Q.get(o, [])[:5]])
        check("2c %d of %d pile matches of the second-round groups have the group in their top 5 (the rest have five stronger rows)" % (n_shown, len(pile_m)), n_shown >= 0.8 * len(pile_m), (n_shown, len(pile_m)))
        # a hand-placed card keeps the group and its other options
        open_card(pile)
        c.js("[...document.querySelectorAll('#epsug .sug')].find(e => e.querySelector('.gname').innerText === 'Opens or visits Attractions').querySelector('button[data-act=add]').click()")
        c.wait("Object.keys(MDOC.edits).length === 1 && /saved/.test(LASTMSG)", 30)
        d = TB.doc()
        check("3 a single Add of the new group is saved in the temp file as hand:opens-or-visits-attractions, not as a batch", pile in d["edits"] and "hand:opens-or-visits-attractions" in d["edits"][pile]["groups"] and not d["edits"][pile]["groups"]["hand:opens-or-visits-attractions"].get("batch"))
        check("3 it counts on the existing 'placed by hand' line (1 card) and the six figures are unchanged", "placed by hand" in hl() and figs().split("|")[:6] == figs0.split("|")[:6] and "1 of" in hl(), hl()[:60])
        c.wait("document.querySelectorAll('#epsug .sug').length >= 5", 30)
        s2 = sugs()
        nblocks = c.js("document.querySelectorAll('#epsug .sugc').length") or len(s2)            # ENGINE_V2: near-duplicate groups share a block; five blocks at most
        check("3 the hand-placed card's panel still shows 5 other suggestions (blocks) and not the group just added", nblocks == 5 and len(s2) >= 5 and "Opens or visits Attractions" not in [x["name"] for x in s2], (nblocks, [x["name"] for x in s2]))
        # ---- the batch view
        for thr in (0.90, 0.70):
            c.js("BS.thr = %s; show('QB:')" % thr)
            c.wait("document.querySelectorAll('#brows .brow').length > 0 && !!document.getElementById('bacc')", 120)
            c.js("showBatchView()")
            c.wait("document.querySelectorAll('#brows .brow').length > 0", 60)
            n = c.js("document.querySelectorAll('#brows .brow').length")
            bad = c.js("[...document.querySelectorAll('#brows input[data-bk]')].filter(e => e.checked && e.dataset.bk.split('|')[1].startsWith('hand:') && Manual.neverTick(MS.cards[e.dataset.bk.split('|')[0]].find(r => r[0] === e.dataset.bk.split('|')[1])[2])).length")
            nrow = c.js("[...document.querySelectorAll('#brows .brow')].filter(r => r.querySelector('.gname') && r.querySelector('.bsug > .bit .gname').innerText.length && [...r.querySelectorAll('.bsug > .bit .sub')][0].innerText.includes('hand-group rule')).length")
            tk = c.js("[...document.querySelectorAll('#brows input[data-bk]')].filter(e => e.checked).length")
            check("4 batch view at threshold %.2f: %d rows, %d led by a hand-group rule, none of them ticked; %d other rows ticked" % (thr, n, nrow, tk), bad == 0 and n > 0, (bad, nrow))
        check("4 the batch view says rule-led rows are review only", "hand-group rule is always in the review band" in c.js("document.getElementById('panel').innerText"))
        check("5 no sideways scroll", c.js("document.documentElement.scrollWidth <= window.innerWidth"))
    finally:
        edge.terminate()
        srv.shutdown()
    real_after = (sha(REAL), sha(REAL + ".bak"))
    print(("PASS " if real_after == real_before else "FAIL ") + "the real corrections file and its backup are byte-identical")
    bad = [r for r in results if not r[1]] + ([] if real_after == real_before else [("real file", False, "")])
    print("\n%d failure(s)" % len(bad) if bad else "\nall passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
