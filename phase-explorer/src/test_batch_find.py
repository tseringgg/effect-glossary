#!/usr/bin/env python3
"""Find a card on the real page (headless Edge) for 23 cards: 5 batch-placed, 5 single hand-placed, 5 community-tag, 5 tentative, 3 excluded. TEMP corrections file only (the real one is hashed before and after).

    python src/test_batch_find.py

The batch placements go through POST /api/manual/batch and the single ones through POST /api/manual, against the temp copy. Each answer is printed in full.
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


def post(port, route, body):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, route), data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "X-Manual-Edit": "1"})
    return json.load(urllib.request.urlopen(req))


def main():
    rb = (sha(REAL), sha(REAL + ".bak"))
    assert os.path.abspath(TB.DOC) != os.path.abspath(REAL)
    idx = MC.load_index()
    C = idx["cards"]
    S = json.load(open(os.path.join(TB.HERE, "build", "manual_suggestions.json"), encoding="utf-8"))["cards"]
    lookup = json.load(open(os.path.join(TB.HERE, "build", "ability_taxonomy_lookup.json"), encoding="utf-8"))["entries"]
    names = {}
    for e in lookup:
        for nm in [e[1]] + e[2]:
            names.setdefault(nm.lower(), []).append(e[0])
    uniq = lambda o: o in C and len(names[C[o][0].lower()]) == 1
    rank = lambda o: (C[o][4] is None, C[o][4] or 0, o)
    real_doc = MC.load_doc(REAL) if os.path.exists(REAL) else {"edits": {}}
    pile = [o for o in sorted(C, key=rank) if C[o][1] == "u" and uniq(o) and o in S and S[o][0][1] >= 0.9 and o not in real_doc["edits"]]
    batch, single = pile[:5], pile[5:10]
    tent = [o for o in sorted(C, key=rank) if C[o][1] == "t" and uniq(o)][:5]
    tagc = [o for o in sorted(C, key=rank) if C[o][1] == "m" and uniq(o)][:5]
    oos = [e for e in lookup if e[3] == "o" and e[4][0] in ("silver_border", "acorn_stamp", "playtest_card") and len(names[e[1].lower()]) == 1]
    seen, excl = set(), []
    for e in oos:
        if e[4][0] not in seen:
            seen.add(e[4][0])
            excl.append(e)
    srv = TB.Quiet(("127.0.0.1", TB.PORT_A), TB.Real)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    r = post(TB.PORT_A, "/api/manual/batch", {"id": "b-20261015-190000-find", "kind": "place", "threshold": 0.9, "items": [{"oid": o, "group": S[o][0][0], "action": "add", "score": S[o][0][1], "source": S[o][0][2]} for o in batch]})
    assert r["ok"] and r["count"] == 5, r
    for o in single:
        assert post(TB.PORT_A, "/api/manual", {"oid": o, "group": S[o][0][0], "action": "add", "note": "single"})["ok"]
    edge = subprocess.Popen([TB.EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + tempfile.mkdtemp(), "--remote-debugging-port=%d" % TB.PORT_CDP, "--remote-allow-origins=*",
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
        c.wait("document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null", 240)

        def ask(name):
            c.js("(() => { const q = document.getElementById('q'); q.value = ''; document.getElementById('findres').innerHTML = ''; q.focus(); })()")
            c.type(name)
            c.wait("document.querySelector('#findres .fr') && document.querySelector('#findres .fr .nm').innerText.length > 0", 90)
            time.sleep(0.6)
            return c.js("(() => { const f = [...document.querySelectorAll('#findres .fr')].find(x => x.querySelector('.nm').innerText.toLowerCase().startsWith(%s)) || document.querySelector('#findres .fr'); return f ? f.innerText : ''; })()" % json.dumps(name.lower()))

        def nm(o):
            return C[o][0] if o in C else next(e[1] for e in lookup if e[0] == o)
        groups = [("batch-placed", batch, lambda t: "Placed by hand: in" in t and "placed in a batch" in t and "score" in t and "threshold 0.90" in t),
                  ("single hand-placed", single, lambda t: "Placed by hand: in" in t and "in a batch" not in t),
                  ("community tag", tagc, lambda t: "Grouped by community tag" in t),
                  ("tentative", tent, lambda t: "Tentative placement" in t),
                  ("excluded", [e[0] for e in excl], lambda t: "Not a card in this tool" in t)]
        for label, oids, test in groups:
            print("\n=== %s ===" % label)
            for o in oids:
                txt = ask(nm(o)).replace("\n", " ")
                ok = test(txt) and "undefined" not in txt
                results.append(ok)
                print(("PASS " if ok else "FAIL ") + nm(o) + ": " + txt[:560])
    finally:
        edge.terminate()
        srv.shutdown()
    ra = (sha(REAL), sha(REAL + ".bak"))
    print("\n%d answers checked, %d failed; the real corrections file and its backup are byte-identical: %s" % (len(results), results.count(False), rb == ra))
    sys.exit(0 if all(results) and rb == ra else 1)


if __name__ == "__main__":
    main()
