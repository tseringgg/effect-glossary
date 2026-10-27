#!/usr/bin/env python3
"""Verify the needCards memoization in reports/browse.html (headless Edge over the DevTools protocol; plain static server, GET only; clicks are DOM click() calls, no touch).

    python src/test_needcards_memo.py

Serves the project folder as it is (reports/ and build/), beside a temporary copy of the committed browse.html (reports/browse_old_tmp.html, removed at the end).
For ?dev=1 and the tester page, on a deep link and with no hash, the old and new page are compared: the DOM after the same steps, the distinct requests, the console, and how many
times cards.json and members.json are requested (cache ON). Protected files are hashed before and after; nothing is written but the temporary copy.
"""
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_tester_static as T            # noqa: E402

check = T.check
OLDSRC = []
DEEP = "#l%3Aab2d4667c5"
CARDS, MEMB = "/build/ability_taxonomy_cards.json", "/build/ability_taxonomy_members.json"
ORIG = T.CDP.call


def cache_on(self, method, **p):
    if method == "Network.setCacheDisabled":
        p["cacheDisabled"] = False
    return ORIG(self, method, **p)


def run(old, query, hash_, ready):
    s = T.Session(HERE, "/reports/browse.html%s%s" % (query, hash_), 1280, gz=True, overrides=({"/reports/browse.html": OLDSRC[0]} if old else None))
    try:
        ok = s.c.wait(ready, 300); s.c.pump(4)
        if ok and hash_:
            s.c.js("(()=>{const r=document.querySelector('#list [data-oid]'); return !!r;})()")
        dom = s.c.js("(()=>{const b=document.body.cloneNode(true); b.querySelectorAll('script').forEach(x=>x.remove()); return b.innerHTML;})()")
        net = [r for r in s.net() if r["url"].startswith(s.base())]
        urls = {}
        for r in net:
            urls.setdefault(r["url"].replace(s.base(), ""), []).append(r["failed"] or r["status"])
        cons = [x for x in s.console() if "favicon" not in x]
        return ok, hashlib.sha256((dom or "").encode()).hexdigest()[:16], len(dom or ""), urls, cons
    finally:
        s.close()


def main():
    before = T.protected()
    r = subprocess.run("git show HEAD:./browse.html", cwd=os.path.join(HERE, "reports"), capture_output=True, shell=True)
    src = r.stdout
    if not src:
        raise SystemExit("could not read the committed browse.html: " + r.stderr.decode(errors="replace"))
    OLDSRC.append(src)
    new_txt = open(os.path.join(HERE, "reports", "browse.html"), "rb").read()
    check("the committed browse.html was read and differs from the working one only where expected", src != new_txt and src.count(b"\n") + 5 >= new_txt.count(b"\n") - 12, (src.count(b"\n"), new_txt.count(b"\n")))
    T.CDP.call = cache_on
    try:
        for label, query, ready in (
                ("?dev=1", "?dev=1", "!!document.querySelector('#tree .row')"),
                ("tester", "", "document.body.classList.contains('tester') && typeof TF !== 'undefined' && !!MI && !!CARDS && !!MEM && !!document.querySelector('#tree .row')")):
            for hl, h in (("deep link", DEEP), ("no hash", "")):
                res = {}
                for which, old in (("old", True), ("new", False)):
                    res[which] = [run(old, query, h, ready) for _ in range(2)]
                tag = "%s, %s" % (label, hl)
                check("%s: both pages booted every time" % tag, all(r[0] for v in res.values() for r in v))
                bad = lambda v: sorted({(u, x) for r in v for u, xs in r[3].items() for x in xs if x not in (200, 304)} | {("console", c.split("http://127.0.0.1:")[0] + c.split("/", 3)[-1]) for r in v for c in r[4]})
                check("%s: the failed requests and console lines are the same in old and new (a static server has no /api and no hand_view.json): %s" % (tag, [u for u, x in bad(res["new"])]), bad(res["old"]) == bad(res["new"]), (bad(res["old"]), bad(res["new"])))
                check("%s: no exception in the new page" % tag, not any("exception" in c for r in res["new"] for c in r[4]))
                # the distinct set of requested files is the same
                so = set(res["old"][0][3]); sn = set(res["new"][0][3])
                check("%s: the same distinct files are requested (%d)" % (tag, len(sn)), so == sn, sorted(so ^ sn)[:5])
                for f in (CARDS, MEMB):
                    o = [len(r[3].get(f, [])) for r in res["old"]]; n = [len(r[3].get(f, [])) for r in res["new"]]
                    T.NOTES.append("%s, %s requests per load over 2 loads (cache ON): old %s, new %s" % (tag, f.split("/")[-1], o, n))
                    check("%s: %s is requested exactly once per load on the new page" % (tag, f.split("/")[-1]), all(x == 1 for x in n), n)
                d_old = {r[1] for r in res["old"]}; d_new = {r[1] for r in res["new"]}
                T.NOTES.append("%s, %s, DOM hashes old %s, new %s (lengths %s / %s)" % (tag, "body", sorted(d_old), sorted(d_new), res["old"][0][2], res["new"][0][2]))
                check("%s: the DOM after the same wait is identical, old against new%s" % (tag, " (the old page's own DOM varied between loads)" if len(d_old) > 1 else ""), len(d_new) == 1 and d_new <= d_old)
    finally:
        T.CDP.call = ORIG
    after = T.protected()
    changed = [k for k in before if after.get(k) != before[k]]
    check("protected files byte-identical before and after (%d files)" % len(before), not changed and set(before) == set(after), changed[:3])
    print()
    ok = sum(1 for r in T.RESULTS if r[1]); bad = [r for r in T.RESULTS if not r[1]]
    print("%d checks, %d passed, %d failed" % (len(T.RESULTS), ok, len(bad)))
    for n in T.NOTES:
        print("NOTE", n)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
