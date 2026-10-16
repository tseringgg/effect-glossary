#!/usr/bin/env python3
"""Test POST /api/manual (src/serve.py + src/manual_common.py) with good and bad input, against a TEMP corrections file (the real one is never touched).

    python src/test_manual_endpoint.py

Needs build/manual_index.json (python src/build_manual_layer.py). Covers: a good add / remove / nofit / clear; unknown card; malformed id; unknown group; unknown layer; a group that is not offered;
bad action; unknown field; oversized note; oversized body; missing header; foreign Host; remove of a group the card does not hold; add to a group it already holds precisely; undo of a hand add by remove;
nofit with a hand placement; a corrupt file (refused, untouched); a failed rename (original intact, no temp file left); concurrent writes (60 distinct edits and 20 on one key).
"""
import http.client
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as MC

sys.argv = sys.argv[:1]
import serve                                           # noqa: E402

TMP = tempfile.mkdtemp(prefix="manual_test_")
MC.CORR = os.path.join(TMP, "manual_placements.json")
IDX = MC.load_index()
PORT = 8794
FAILS = []


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" - " + str(detail)) if detail else ""))
    if not ok:
        FAILS.append(name)


def post(body, headers=None, raw=None, host=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=20)
    data = raw if raw is not None else json.dumps(body).encode("utf-8")
    h = {"Content-Type": "application/json", "X-Manual-Edit": "1", "Content-Length": str(len(data))}
    if headers is not None:
        h = headers
        h["Content-Length"] = str(len(data))
    if host:
        h["Host"] = host
    c.request("POST", "/api/manual", body=data, headers=h)
    r = c.getresponse()
    out = r.read()
    c.close()
    try:
        return r.status, json.loads(out)
    except Exception:
        return r.status, out


def doc():
    return MC.load_doc(MC.CORR)


def pick():
    cards, groups = IDX["cards"], IDX["groups"]
    u = sorted(o for o, c in cards.items() if c[1] == "u")
    offered = sorted(g for g, v in groups.items() if v[4] and v[3] == "leaf")
    p = next(o for o, c in sorted(cards.items()) if c[1] == "p" and any(x[1] == "P" for x in c[3]))
    t = next(o for o, c in sorted(cards.items()) if c[1] == "t" and any(x[1] == "T" for x in c[3]))
    return {"pile": u, "leaf": offered, "precise": p, "precise_group": next(x[0] for x in cards[p][3] if x[1] == "P"),
            "tent": t, "tent_group": next(x[0] for x in cards[t][3] if x[1] == "T"),
            "notcard": next(o for o, c in sorted(cards.items()) if c[1] == "o"),
            "catchall": next(g for g, v in sorted(groups.items()) if not v[4]),
            "loose_only": next(g for g, v in sorted(groups.items()) if v[3] == "loose" and v[4]),
            "kw": next(g for g, v in sorted(groups.items()) if v[3] == "kw"), "rp": next(g for g, v in sorted(groups.items()) if v[3] == "rp"),
            "tag": next(g for g, v in sorted(groups.items()) if v[3] == "tag")}


def main():
    srv = serve.Server(("127.0.0.1", PORT), serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    P = pick()
    a, b, c = P["pile"][0], P["pile"][1], P["pile"][2]
    g1, g2 = P["leaf"][0], P["leaf"][1]

    c0 = http.client.HTTPConnection("127.0.0.1", PORT)
    c0.request("GET", "/api/manual/ping")
    r = c0.getresponse()
    j = json.loads(r.read())
    check("ping says the endpoint exists and is enabled", r.status == 200 and j["ok"] and j["enabled"], j)

    s, j = post({"oid": a, "group": g1, "action": "add", "note": "test"})
    d = doc()
    e = d["edits"].get(a, {}).get("groups", {}).get(g1, {})
    check("good add: 200 and written", s == 200 and j["ok"] and e.get("action") == "add" and e.get("note") == "test", (s, j.get("error")))
    check("the server fills date, group_name and source_at_edit (with the unplaced reason)", bool(e.get("date")) and e.get("group_name") == IDX["groups"][g1][0] and e["source_at_edit"]["status"] == "unorganized" and "reason" in e["source_at_edit"], e.get("source_at_edit"))
    check("revision and history advance", d["revision"] == 1 and d["history"][-1]["op"] == "add")
    s, j = post({"oid": a, "group": g1, "action": "add", "note": "test"})
    check("the same add again is accepted (idempotent update)", s == 200 and len(doc()["edits"][a]["groups"]) == 1)
    s, j = post({"oid": a, "group": P["kw"], "action": "add"})
    check("a keyword-block group can be added", s == 200, j)
    s, j = post({"oid": a, "group": P["rp"], "action": "add"})
    check("a replacement-block group can be added", s == 200, j)
    s, j = post({"oid": a, "group": P["tag"], "action": "add"})
    check("a tag group can be added", s == 200, j)
    s, j = post({"oid": a, "group": P["loose_only"], "action": "add"})
    check("a loose-only group can be added", s == 200, j)

    s, j = post({"oid": "00000000-0000-4000-8000-000000000000", "group": g1, "action": "add"})
    check("unknown card -> 404", s == 404, (s, j))
    s, j = post({"oid": "not-an-id", "group": g1, "action": "add"})
    check("malformed card id -> 400", s == 400, (s, j))
    s, j = post({"oid": b, "group": "leaf:azzzzzzzzz", "action": "add"})
    check("unknown group -> 422", s == 422, (s, j))
    s, j = post({"oid": b, "group": "nolayer:abc", "action": "add"})
    check("unknown layer -> 400", s == 400, (s, j))
    s, j = post({"oid": b, "group": P["catchall"], "action": "add"})
    check("a catch-all / bucket is not offered -> 422", s == 422, (s, j))
    s, j = post({"oid": b, "group": g1, "action": "delete"})
    check("bad action -> 400", s == 400, (s, j))
    s, j = post({"oid": b, "group": g1, "action": "add", "extra": 1})
    check("unknown field -> 400", s == 400, (s, j))
    s, j = post({"oid": b, "group": g1, "action": "add", "note": "x" * 501})
    check("oversized note (501) -> 422", s == 422, (s, j))
    s, j = post({"oid": b, "group": g1, "action": "add", "note": "x" * 500})
    check("a 500-character note is accepted", s == 200, (s, str(j)[:80]))
    s, j = post({"oid": b, "group": g1, "action": "add", "note": "line\x00 with\x07 controls"})
    check("control characters in a note are stripped", s == 200 and doc()["edits"][b]["groups"][g1]["note"] == "line with controls", doc()["edits"][b]["groups"][g1]["note"])
    s, j = post(None, raw=b'{"oid": "' + b"x" * 9000 + b'"}')
    check("oversized body -> 413", s == 413, (s, j))
    s, j = post(None, raw=b"{not json")
    check("bad JSON -> 400", s == 400, (s, j))
    s, j = post(None, raw=b"[1,2]")
    check("a JSON array -> 400", s == 400, (s, j))
    s, j = post({"oid": b, "group": g2, "action": "add"}, headers={"Content-Type": "application/json"})
    check("missing X-Manual-Edit header -> 400 (blocks cross-site posts)", s == 400, (s, j))
    s, j = post({"oid": b, "group": g2, "action": "add"}, host="evil.example")
    check("a foreign Host header -> 403", s == 403, (s, j))
    s, j = post({"oid": P["notcard"], "group": g1, "action": "add"})
    check("an entry that is not a card -> 422", s == 422, (s, j))

    s, j = post({"oid": c, "group": g1, "action": "remove"})
    check("remove of a group the card does not hold -> 422", s == 422, (s, j))
    s, j = post({"oid": P["precise"], "group": P["precise_group"], "action": "add"})
    check("add to a group the card already holds precisely -> 409", s == 409, (s, j))
    s, j = post({"oid": P["tent"], "group": P["tent_group"], "action": "remove", "note": "wrong"})
    e = doc()["edits"].get(P["tent"], {}).get("groups", {}).get(P["tent_group"], {})
    check("remove of a generated (tentative) membership is recorded", s == 200 and e.get("action") == "remove" and e["source_at_edit"]["status"] == "tentative", (s, j))
    s, j = post({"oid": a, "group": g1, "action": "remove"})
    check("remove of a hand-added group -> 409 (use undo)", s == 409, (s, j))
    s, j = post({"oid": P["tent"], "group": P["tent_group"], "action": "clear"})
    check("clear undoes a removal", s == 200 and P["tent"] not in doc()["edits"], (s, j))
    s, j = post({"oid": P["tent"], "group": P["tent_group"], "action": "clear"})
    check("clear of nothing is a harmless no-op", s == 200 and j["changed"] is False, (s, j))

    s, j = post({"oid": c, "group": "none:fits", "action": "nofit", "note": "nothing fits"})
    e = doc()["edits"].get(c, {}).get("groups", {}).get("none:fits", {})
    check("nothing fits is a third action in the same structure", s == 200 and e.get("action") == "nofit" and "reason" in e["source_at_edit"], (s, j))
    s, j = post({"oid": c, "group": "none:fits", "action": "add"})
    check("none:fits only takes nofit or clear -> 400", s == 400, (s, j))
    s, j = post({"oid": c, "group": g1, "action": "nofit"})
    check("nofit on a real group -> 400", s == 400, (s, j))
    s, j = post({"oid": c, "group": g1, "action": "add"})
    check("placing a card ends its nothing-fits mark", s == 200 and "none:fits" not in doc()["edits"][c]["groups"], (s, j))
    s, j = post({"oid": c, "group": "none:fits", "action": "nofit"})
    check("nofit on a hand-placed card -> 409", s == 409, (s, j))
    s, j = post({"oid": c, "group": g1, "action": "clear"})
    check("undo of the only edit drops the card from the file", s == 200 and c not in doc()["edits"], (s, j))

    # concurrency
    before = doc()["revision"]
    res = []

    def w(i):
        o = P["pile"][10 + i]
        res.append(post({"oid": o, "group": P["leaf"][i % 50], "action": "add", "note": "t%d" % i})[0])
    ts = [threading.Thread(target=w, args=(i,)) for i in range(60)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    d = doc()
    check("60 concurrent distinct writes all land", res.count(200) == 60 and all(P["pile"][10 + i] in d["edits"] for i in range(60)) and d["revision"] == before + 60, (res.count(200), d["revision"] - before))
    res2 = []
    o2 = P["pile"][100]

    def w2(i):
        res2.append(post({"oid": o2, "group": P["leaf"][5], "action": "add", "note": "same%d" % i})[0])
    ts = [threading.Thread(target=w2, args=(i,)) for i in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    d = doc()
    check("20 concurrent writes to one key leave one valid entry", res2.count(200) == 20 and list(d["edits"][o2]["groups"]) == [P["leaf"][5]], res2.count(200))
    check("the file is valid JSON with consistent history after concurrency", len(d["history"]) == d["revision"] or len(d["history"]) >= d["revision"] - 1, (len(d["history"]), d["revision"]))
    check("no temp or lock file is left behind, and a .bak exists", not [f for f in os.listdir(TMP) if f.endswith(".tmp") or f.endswith(".lock")] and os.path.exists(MC.CORR + ".bak"), os.listdir(TMP))

    # failed rename: original intact, nothing partial
    snap = open(MC.CORR, "rb").read()
    real = MC.os.replace

    def boom(*a, **k):
        raise OSError("disk says no")
    MC.os.replace = boom
    try:
        s, j = post({"oid": P["pile"][200], "group": g1, "action": "add"})
    finally:
        MC.os.replace = real
    check("a failed rename -> 500 with a message, original byte-identical, no temp file", s == 500 and open(MC.CORR, "rb").read() == snap and not [f for f in os.listdir(TMP) if f.endswith(".tmp")], (s, j))

    # corrupt file: refused, untouched
    open(MC.CORR, "w").write("{ this is not json")
    s, j = post({"oid": P["pile"][201], "group": g1, "action": "add"})
    check("a corrupt corrections file is refused (500) and left untouched", s == 500 and open(MC.CORR).read() == "{ this is not json", (s, j))
    srv.shutdown()
    print("\n%d failure(s)" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
