#!/usr/bin/env python3
"""Find a card on the real page (headless Edge) for 21 cards: 5 hand-placed, 5 community-tag, 5 placed, 5 tentative, 3 excluded. Prints each answer in full.

    python src/test_manual_find.py

Uses the same temp-corrections server as src/test_manual_browser.py; the 5 hand placements are made through POST /api/manual first (3 pile cards placed by hand, 1 tentative card and 1 tag card confirmed by hand).
Checks that each answer names its state in words (and, for a hand placement, where it was placed and that it was by hand).
"""
import json
import os
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_manual_browser as TB
import manual_common as MC

import subprocess
import tempfile


def post(port, body):
    req = urllib.request.Request("http://127.0.0.1:%d/api/manual" % port, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "X-Manual-Edit": "1"})
    return json.load(urllib.request.urlopen(req))


def main():
    idx = MC.load_index()
    C, G = idx["cards"], idx["groups"]
    sug = json.load(open(os.path.join(TB.HERE, "build", "manual_suggestions.json"), encoding="utf-8"))["cards"]
    lookup = json.load(open(os.path.join(TB.HERE, "build", "ability_taxonomy_lookup.json"), encoding="utf-8"))["entries"]
    names = {}
    for e in lookup:
        for nm in [e[1]] + e[2]:
            names.setdefault(nm.lower(), []).append(e[0])
    uniq = lambda o: len(names[C[o][0].lower()]) == 1 if o in C else False
    pick = lambda state, n, pred=lambda o: True: [o for o in sorted(C, key=lambda o: (C[o][4] is None, C[o][4] or 0, o)) if C[o][1] == state and uniq(o) and pred(o)][:n]
    pile = pick("u", 3, lambda o: o in sug and sug[o][0][0].startswith("leaf:") and C[o][2] in (1, 2, 3, 4, 5))
    tent = pick("t", 6, lambda o: any(x[1] == "T" for x in C[o][3]))
    tagc = pick("m", 6, lambda o: any(x[1] == "M" for x in C[o][3]))
    placed = pick("p", 5, lambda o: any(x[1] == "P" for x in C[o][3]))
    oos = [e for e in lookup if e[3] == "o" and e[4][0] in ("silver_border", "acorn_stamp", "playtest_card") and len(names[e[1].lower()]) == 1]
    seen, excl = set(), []
    for e in oos:
        if e[4][0] not in seen:
            seen.add(e[4][0])
            excl.append(e)
    conf_t, conf_m = tent[0], tagc[0]
    hand = pile + [conf_t, conf_m]
    tent, tagc = tent[1:6], tagc[1:6]
    srvA = TB.Quiet(("127.0.0.1", TB.PORT_A), TB.Real)
    threading.Thread(target=srvA.serve_forever, daemon=True).start()
    for o in pile:
        r = post(TB.PORT_A, {"oid": o, "group": sug[o][0][0], "action": "add", "note": "find-a-card check"})
        assert r["ok"], r
    r = post(TB.PORT_A, {"oid": conf_t, "group": next(x[0] for x in C[conf_t][3] if x[1] == "T"), "action": "add"})
    assert r["ok"], r
    r = post(TB.PORT_A, {"oid": conf_m, "group": next(x[0] for x in C[conf_m][3] if x[1] == "M"), "action": "add"})
    assert r["ok"], r
    prof = tempfile.mkdtemp()
    edge = subprocess.Popen([TB.EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + prof, "--remote-debugging-port=%d" % TB.PORT_CDP, "--remote-allow-origins=*",
                             "--window-size=1400,1000", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    results = []
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
        c.wait("document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null", 180)

        def ask(name):
            c.js("(() => { const q = document.getElementById('q'); q.value = ''; document.getElementById('findres').innerHTML = ''; q.focus(); })()")
            c.type(name)
            c.wait("document.querySelector('#findres .fr') && document.querySelector('#findres .fr .nm').innerText.length > 0", 90)
            time.sleep(0.6)
            return c.js("(() => { const f = [...document.querySelectorAll('#findres .fr')].find(x => x.querySelector('.nm').innerText.toLowerCase().startsWith(%s)) || document.querySelector('#findres .fr'); return f ? f.innerText : ''; })()" % json.dumps(name.lower()))
        groups = [("hand-placed", hand, ["Placed by hand", "Also placed by hand"]), ("community tag", tagc, ["Grouped by community tag"]), ("placed", placed, ["Grouped by what its abilities do", "In Keyword", "In Replacement", "Only in a group broader"]),
                  ("tentative", tent, ["Tentative placement"]), ("excluded", [e[0] for e in excl], ["Not a card in this tool"])]
        for label, oids, want in groups:
            print("\n=== %s ===" % label)
            for o in oids:
                nm = C[o][0] if o in C else next(e[1] for e in lookup if e[0] == o)
                txt = ask(nm).replace("\n", " ")
                ok = any(w in txt for w in want) and "undefined" not in txt
                if label == "hand-placed":
                    ok = ok and "by hand" in txt and ("“" in txt)
                results.append((label, nm, ok))
                print(("PASS " if ok else "FAIL ") + nm + ": " + txt[:700])
    finally:
        edge.terminate()
        srvA.shutdown()
    bad = [r for r in results if not r[2]]
    print("\n%d answers checked, %d failed" % (len(results), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
