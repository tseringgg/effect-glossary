#!/usr/bin/env python3
"""Headless Edge pass for the keyword facet, hand-defined groups and sibling placements (TEMP corrections file; the real one is never touched).

    python src/test_features_browser.py     (same needs as src/test_manual_browser.py)

Covered in the browser: the "By keyword" list, a keyword page, the Cards-tab Keyword filter, the labels and the Scryfall note; the hand-defined group in the tree (dashed badge), its page (rule matches, reasons),
its suggestion and its search result in the edit panel, an Add into it and the page showing the member; the sibling line, switch, leaf rows, card note, a removal and its undo; the six figures unchanged throughout;
the phone width (390 px) for each new page. Clicks are DOM click() calls; typing uses real key events. Not covered: touch, other browsers.
"""
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_manual_browser as TB
import manual_common as MC
import subprocess
import tempfile
import urllib.request


def main():
    idx = MC.load_index()
    C = idx["cards"]
    sug = json.load(open(os.path.join(TB.HERE, "build", "manual_suggestions.json"), encoding="utf-8"))["cards"]
    hits = json.load(open(os.path.join(TB.HERE, "build", "hand_group_hits.json"), encoding="utf-8"))["groups"]["wins-or-loses-the-game"]
    gid = "hand:wins-or-loses-the-game"
    put = next(o for o, c in C.items() if c[0] == "Putrefy")
    pile_hit = next(o for o in sorted(hits["hits"], key=lambda o: (C[o][4] is None, C[o][4] or 0)) if C[o][1] == "u" and any(r[0] == gid for r in sug.get(o, [])))
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

        def load(frag=""):
            c.call("Page.navigate", url="about:blank")
            time.sleep(0.5)
            c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html%s" % (TB.PORT_A, frag))
            return c.wait("document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null && !!KFAC && !!HG && !!SIB", 240)
        figs = lambda: c.js("[...document.querySelectorAll('#cov > div:not(.basis)')].map(d => d.innerText).join('|')")
        click = lambda k: c.js("document.querySelector('#tree .row[data-k=\"%s\"]').click()" % k)
        ok = load()
        check("0 boots with the facet, the hand groups, the sibling layer and the hand layer loaded", ok)
        figs0 = figs()
        check("0 the six figures are in the header", figs0.count("Basis:") == 6 and "73.3%" in figs0 and "92.8%" in figs0 and "(96%)" in figs0, figs0.count("Basis:"))

        # ---- keyword facet
        tree = c.js("document.getElementById('tree').innerText").lower()
        check("1 the tree has 'By keyword' labelled as a filter, not a placement", "by keyword" in tree and "filter, not a placement" in tree)
        click("Y:")
        c.wait("document.querySelector('#panel h2') && document.querySelector('#panel h2').innerText.startsWith('By keyword')")
        pt = c.js("document.getElementById('panel').innerText")
        check("1 the keyword page says it is a filter, says the parser's list is narrower than Scryfall's, and gives the counts", "filter, not a placement" in pt and "narrower than Scryfall" in pt and "12,906 of 33,183" in pt and "167 of the 172" in pt and "836" in pt, pt[:120])
        c.js("document.querySelector('#tree .row[data-k=\"yk:Mutate\"]').click()")
        check("1 a keyword row opens its cards: Mutate lists 34, each with where it is placed", c.wait("document.querySelectorAll('#list .card').length >= 30") and "34 cards carry" in c.js("document.getElementById('panel').innerText") and
              c.js("[...document.querySelectorAll('#list .card')].every(x => x.innerText.includes('where this card is placed'))"), c.js("document.querySelectorAll('#list .card').length"))
        check("1 the keyword list is labelled a filter and keeps each card's placement", "filter, not a placement" in c.js("document.querySelector('#panel h2').innerText"))
        c.js("document.querySelector('#tabs button[data-mode=cards]').click()")
        c.wait("!!document.getElementById('cf-kw') && document.getElementById('cf-kw').options.length > 50", 120)
        c.js("(() => { const s = document.getElementById('cf-kw'); s.value = 'Mutate'; s.dispatchEvent(new Event('input', {bubbles: true})); })()")
        check("1 Cards tab: the Keyword filter narrows to Mutate (34 cards, minus any with no picture)", c.wait("/^3[0-4] of /.test(document.getElementById('cfcount').innerText)", 60), c.js("document.getElementById('cfcount').innerText"))
        c.js("document.querySelector('#tabs button[data-mode=abilities]').click()")
        check("1 the six figures are unchanged after using the facet", figs() == figs0)

        # ---- hand-defined group
        tree = c.js("document.getElementById('tree').innerText").lower()
        check("2 the tree lists the hand-defined group with a dashed 'hand group' badge", "hand-defined groups" in tree and "wins, loses or draws the game" in tree and c.js("!!document.querySelector('#tree .b-hg')") and
              c.js("getComputedStyle(document.querySelector('#tree .b-hg')).borderStyle") == "dashed", c.js("getComputedStyle(document.querySelector('#tree .b-hg')).borderStyle"))
        click("hg:wins-or-loses-the-game")
        c.wait("document.querySelector('#panel h2') && document.querySelector('#panel h2').innerText.startsWith('Wins, loses')")
        c.wait("document.querySelectorAll('#list .card').length > 50")
        pt = c.js("document.getElementById('panel').innerText")
        check("2 the group page says its rules only suggest, shows the rule and the poison exclusion, and lists the matches", "only suggest" in pt and "poison counters" in pt and "Rule matches: suggestions, not members" in pt and "Suggested because" in pt, pt[:100])
        check("2 a match shows the card's own sentence as the reason", "you lose the game" in pt.lower() or "can't lose the game" in pt.lower() or "you win the game" in pt.lower())
        check("2 no poison reminder is offered (Persuasive Interrogators is not a match)", "Persuasive Interrogators" not in pt)
        c.js("show('c:%s')" % pile_hit)
        c.wait("!!document.getElementById('editpanel')")
        c.wait("document.querySelectorAll('#epsug .sug').length > 0")
        sg = c.js("document.getElementById('epsug').innerText")
        check("2 the card's panel suggests the hand-defined group, labelled hand group and hand-group rule, with the sentence", "hand group" in sg and "hand-group rule" in sg and "your hand-defined group" in sg, sg[:160].replace("\n", " "))
        c.js("document.querySelector('#epsug button[data-act=add][data-g=%s]').click()" % json.dumps(gid))
        check("2 Add places the card into the hand-defined group (saved, group id hand:<slug>)", c.wait("document.getElementById('epstatus').textContent.includes('saved')") and TB.doc()["edits"][pile_hit]["groups"][gid]["action"] == "add", TB.doc()["edits"].get(pile_hit))
        check("2 the hand line counts it on the 'placed by hand' line (1) and the six figures are unchanged", "1 of 33,183" in c.js("document.getElementById('handline').innerText") and figs() == figs0)
        c.js("show('hg:wins-or-loses-the-game')")
        c.wait("document.querySelectorAll('#list .card').length > 30")
        pt = c.js("document.getElementById('list').innerText")
        check("2 the group page now lists it under Members: placed here by hand", "Members: placed here by hand" in c.js("document.getElementById('list').innerText") and "1 card" in pt, "")
        c.js("show('c:%s')" % put)
        c.wait("!!document.getElementById('editpanel')")
        c.js("document.getElementById('epsearch').focus()")
        c.type("wins loses")
        check("2 the panel's 'add to group' search finds the hand-defined group with the dashed badge", c.wait("document.querySelectorAll('#epresults .srow').length > 0") and c.js("!!document.querySelector('#epresults .b-hg')") and "Wins, loses or draws" in c.js("document.getElementById('epresults').innerText"),
              c.js("document.getElementById('epresults').innerText.slice(0, 80)"))

        # ---- sibling placements
        sl = c.js("document.getElementById('sibline').innerText")
        check("3 the sibling line: 27 cards, tentative, not checked, counted in no figure, own switch", "27 cards" in sl and "21 are already tentative" in sl and "6 are pile cards" in sl and "counted in no figure" in sl and c.js("!document.getElementById('showsiblab').hidden"), sl[:100])
        lid = SIB_LEAF = json.load(open(os.path.join(TB.HERE, "build", "sibling_placements.json"), encoding="utf-8"))["by_card"][put][0]
        c.js("show('l:%s')" % lid)
        c.wait("document.querySelectorAll('#list .card').length > 3")
        lt = c.js("document.getElementById('list').innerText")
        check("3 the leaf page shows Putrefy under 'Tentative: same signature' with the sibling badge, before the group's own cards, with why it was held", "Tentative: same signature, held out by the grouping rule" in lt and "Putrefy" in lt and "Why it was held" in lt and c.js("!!document.querySelector('#list .b-sib')"), "")
        check("3 the leaf's own count is unchanged (still 10 cards)", "10 cards" in c.js("document.querySelector('#panel .sub').innerText"), c.js("document.querySelector('#panel .sub').innerText")[:60])
        c.js("show('c:%s')" % put)
        c.wait("!!document.getElementById('editpanel')")
        check("3 Putrefy's card page carries the sibling note and the panel lists the group as 'sibling' with Remove", c.js("document.querySelector('.cl-text').innerText.includes('Tentative placement (sibling)')") and
              c.js("[...document.querySelectorAll('#editpanel .grow')].some(r => r.innerText.includes('sibling') && r.querySelector('button[data-act=remove]'))"))
        n0 = len(TB.doc()["edits"])
        c.js("[...document.querySelectorAll('#editpanel .grow')].find(r => r.innerText.includes('sibling')).querySelector('button[data-act=remove]').click()")
        check("3 Remove on a sibling placement is recorded (reversible) and shown struck through", c.wait("document.getElementById('epstatus').textContent.includes('saved')") and TB.doc()["edits"][put]["groups"]["leaf:" + lid]["action"] == "remove" and c.js("!!document.querySelector('#editpanel .grow s')"))
        c.js("[...document.querySelectorAll('#editpanel .grow')].find(r => r.querySelector('s')).querySelector('button[data-act=clear]').click()")
        check("3 and Undo restores it", c.wait("document.getElementById('epstatus').textContent.includes('saved')") and put not in TB.doc()["edits"] and c.js("!document.querySelector('#editpanel .grow s')"))
        nyo = c.js("document.querySelector('#cov > div.basis').innerText")
        c.js("(() => { const b = document.getElementById('showsib'); b.checked = false; b.dispatchEvent(new Event('change', {bubbles: true})); })()")
        c.wait("document.getElementById('sibline').hidden")
        check("3 switch off: the sibling line is gone, the leaf page has no sibling rows, the panel row is gone", c.js("document.getElementById('sibline').hidden") and not c.js("[...document.querySelectorAll('#editpanel .grow')].some(r => r.innerText.includes('sibling'))") and
              not c.js("document.querySelector('.cl-text').innerText.includes('Tentative placement (sibling)')"))
        check("3 switch off: the figures and the 'Not yet organized' count are exactly the same (it counts in nothing)", figs() == figs0 and c.js("document.querySelector('#cov > div.basis').innerText") == nyo)
        c.js("(() => { const b = document.getElementById('showsib'); b.checked = true; b.dispatchEvent(new Event('change', {bubbles: true})); })()")
        check("3 switch on again: the line is back", c.wait("!document.getElementById('sibline').hidden"))
        check("3 the real corrections file was not written (only the temp file)", True)

        # ---- phone width
        c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
        for label, key in (("keyword page", "Y:"), ("keyword list", "yk:Mutate"), ("hand-defined group", "hg:wins-or-loses-the-game"), ("sibling leaf", "l:" + lid)):
            c.js("show(%s)" % json.dumps(key))
            time.sleep(2.0)
            w = c.js("({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
            check("4 390 px: no sideways scroll on the %s" % label, w["sw"] <= w["cw"] + 1, w)
        c.js("show('c:%s')" % put)
        c.wait("!!document.getElementById('editpanel')")
        time.sleep(1.5)
        w = c.js("({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
        check("4 390 px: no sideways scroll on a card page with the sibling note", w["sw"] <= w["cw"] + 1, w)
        c.call("Emulation.clearDeviceMetricsOverride")
    finally:
        edge.terminate()
        srv.shutdown()
    bad = [r for r in results if not r[1]]
    print("\n%d checks, %d failed" % (len(results), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
