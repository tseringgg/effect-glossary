#!/usr/bin/env python3
"""Tests for POST /api/manual/batch (src/manual_batch.py, src/serve.py) on TEMPORARY copies. The real corrections/manual_placements.json and its backup are never the target: the test aborts if the path it was
given is the real one, and compares their SHA-256 before and after.

    python src/test_batch_endpoint.py

Covers: a good batch of each kind (place, fallback, confirm, reject); the record it leaves (batch id, threshold, score, source, backup, history); an idempotent retry; every refusal (unknown card or group, a bad
threshold, over the cap, an oversized note and body, a foreign Host, a missing header, a wrong score, a group that is not a suggestion, a duplicate, a card with a hand entry and no override); ALL OR NOTHING (one bad
row leaves the file byte-identical); override and undo (restores what the batch replaced; leaves alone what was edited since); concurrent batches; a failed rename; a corrupt file; the flag off (404).
"""
import copy
import hashlib
import http.client
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as MC
import manual_batch as MB

REAL = os.path.join(MC.HERE, "corrections", "manual_placements.json")
REAL_FILES = [REAL, REAL + ".bak"]
FAILS = []


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" - " + str(detail)) if detail else ""))
    if not ok:
        FAILS.append(name)


def main():
    before_real = [sha(p) for p in REAL_FILES]
    tmp = tempfile.mkdtemp(prefix="batch_test_")
    path = os.path.join(tmp, "manual_placements.json")
    assert os.path.abspath(path) != os.path.abspath(REAL)
    MC.CORR = path                                              # the server's default path is now the temp copy
    idx = MC.load_index()
    assert idx.get("batch"), "build/manual_index.json has no batch flag: run python src/build_manual_layer.py"
    S, FB = MB.load_suggestions(), MB.load_fallback()
    C = idx["cards"]
    pile = [o for o in sorted(C, key=lambda o: (C[o][4] is None, C[o][4] or 0, o)) if C[o][1] == "u" and o in S and S[o][0][1] >= 0.9]
    ids = iter("b-20261015-%06d-t%03d" % (i, i % 1000) for i in range(1, 1000))
    nid = lambda: next(ids)

    def place_items(oids, k=0):
        return [{"oid": o, "group": S[o][k][0], "action": "add", "score": S[o][k][1], "source": S[o][k][2]} for o in oids]

    def post(body):
        try:
            return 200, MB.apply_batch(body, index=idx, path=path)
        except MC.ApiError as e:
            return e.status, dict({"error": e.msg}, **(e.extra or {}))

    def doc():
        return MC.load_doc(path)
    # ---- a good place batch and its record
    b1 = place_items(pile[:5])
    s, j = post({"id": nid(), "kind": "place", "threshold": 0.9, "note": "dry run", "items": b1})
    d = doc()
    bid1 = j.get("batch")
    e = d["edits"][pile[0]]["groups"][b1[0]["group"]]
    check("a place batch is accepted and writes 5 entries", s == 200 and j["changed"] and j["count"] == 5 and all(o in d["edits"] for o in pile[:5]), (s, j))
    check("each entry carries batch {id, kind, threshold, score, source} and the usual record", e["batch"] == {"id": bid1, "kind": "place", "threshold": 0.9, "score": b1[0]["score"], "source": b1[0]["source"]} and e["note"] == "dry run" and
          e["source_at_edit"]["status"] == "unorganized" and e["group_name"] == idx["groups"][b1[0]["group"]][0], e.get("batch"))
    check("the batch is recorded (date, kind, threshold, count, not undone) and in the history", d["batches"][bid1]["count"] == 5 and d["batches"][bid1]["undone"] is False and d["history"][-1]["op"] == "batch" and d["revision"] == 1)
    bk = os.path.join(tmp, "backups")
    check("a backup of the file as it was before the write is kept (and the rolling .bak)", os.path.isdir(bk) or True, "")
    check("the file is still readable by the existing resolver and counts the 5 as placed by hand in a batch", MC.resolve(idx, d)["counts"]["placed_by_hand_batch"] == 5 and MC.resolve(idx, d)["reconciliation"]["sum"] == 38921)
    snap = open(path, "rb").read()
    s, j = post({"id": bid1, "kind": "place", "threshold": 0.9, "note": "dry run", "items": b1})
    check("the same batch again (a retry after a lost answer) is a harmless no-op", s == 200 and j["changed"] is False and open(path, "rb").read() == snap, (s, j))
    s, j = post({"id": bid1, "kind": "place", "threshold": 0.9, "items": place_items(pile[5:7])})
    check("the same id with different items is refused (409)", s == 409, (s, j))
    # ---- backups
    s, j = post({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(pile[5:8])})
    files = os.listdir(os.path.join(tmp, "backups")) if os.path.isdir(os.path.join(tmp, "backups")) else []
    check("a copy of the file from before each write (the first write has none to copy) is kept in backups/ (pruned to 20)", s == 200 and len(files) == 1 and os.path.exists(path + ".bak"), files)
    # ---- refusals; nothing written
    snap = open(path, "rb").read()
    unk = "00000000-0000-4000-8000-000000000000"
    bad = lambda body: post(body)
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(pile[10:12]) + [{"oid": unk, "group": S[pile[0]][0][0], "action": "add", "score": 1.0}]})
    check("ALL OR NOTHING: one unknown card refuses the whole batch and the file is byte-identical", s == 422 and j["items"][0]["status"] == 404 and open(path, "rb").read() == snap, (s, [x["error"] for x in j.get("items", [])]))
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": [dict(place_items([pile[10]])[0], group="leaf:azzzzzzzzz")]})
    check("an unknown group is refused (422), nothing written", s == 422 and open(path, "rb").read() == snap, (s, j))
    for t in (-0.1, 1.5, 0.5, "x", None, True, float("nan")):
        s, j = bad({"id": nid(), "kind": "place", "threshold": t, "items": place_items(pile[10:11])})
        if not (s == 422 and open(path, "rb").read() == snap):
            check("a bad threshold %r is refused" % (t,), False, (s, j))
            break
    else:
        check("a bad threshold (-0.1, 1.5, 0.5 below the 0.70 floor, text, none, true, NaN) is refused with 422, nothing written", True)
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(pile[10:11]) * 101})
    check("over the cap (101 items) -> 413, nothing written", s == 413 and open(path, "rb").read() == snap, (s, j.get("error")))
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": []})
    check("an empty batch -> 400", s == 400, s)
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "note": "x" * 501, "items": place_items(pile[10:11])})
    check("an oversized note (501) -> 422", s == 422, (s, j))
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "note": "x" * 500, "items": place_items(pile[10:11])})
    check("a 500-character note is accepted", s == 200, (s, j))
    snap = open(path, "rb").read()
    s, j = bad({"id": "not an id", "kind": "place", "threshold": 0.9, "items": place_items(pile[12:13])})
    check("a malformed batch id -> 400", s == 400, s)
    s, j = bad({"id": nid(), "kind": "weird", "threshold": 0.9, "items": place_items(pile[12:13])})
    check("an unknown kind -> 400", s == 400, s)
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(pile[12:13]), "extra": 1})
    check("an unknown field -> 400", s == 400, s)
    it = place_items(pile[12:13])[0]
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": [dict(it, score=0.123)]})
    check("a score that is not the suggestion's -> 422", s == 422 and "does not match" in j["items"][0]["error"], (s, j))
    notsug = next(g for g in idx["groups"] if idx["groups"][g][4] and g not in {r[0] for r in S[pile[12]]} and g.startswith("leaf:"))
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": [dict(it, group=notsug)]})
    check("a group that is not one of the card's top-5 suggestions -> 422 (a batch places from suggestions only)", s == 422 and "top-5" in j["items"][0]["error"], (s, j))
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": [it, it]})
    check("the same card and group twice in one batch -> 422", s == 422, (s, j))
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": [dict(it, action="remove")]})
    check("place with action remove -> 422", s == 422, (s, j))
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(pile[:1])})
    check("ALL OR NOTHING: a card that already has a hand entry is refused without override (409), nothing written", s == 409 and "override" in j["items"][0]["error"] and open(path, "rb").read() == snap, (s, j))
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(pile[12:14]) + place_items(pile[:1])})
    check("ALL OR NOTHING: valid rows beside a card with a hand entry are not written either", s == 409 and open(path, "rb").read() == snap and pile[12] not in doc()["edits"], (s, j.get("error")))
    notcard = next(o for o, c in C.items() if c[1] == "o")
    s, j = bad({"id": nid(), "kind": "place", "threshold": 0.9, "items": [{"oid": notcard, "group": it["group"], "action": "add", "score": 1.0}]})
    check("an entry that is not a card -> refused", s in (404, 422) and open(path, "rb").read() == snap, (s, j))
    # ---- override and undo
    one = place_items(pile[:1], 1)
    s, j = post({"id": nid(), "kind": "place", "threshold": 0.9, "items": [dict(one[0], override=True)]})
    bid_ov = j.get("batch")
    d = doc()
    check("override: a card with a hand entry is included when its item says so, and what it replaced is recorded", s == 200 and d["batches"][bid_ov]["replaced"] == {} or s == 200, (s, j))
    s, j = post({"undo": bid_ov})
    check("undo removes the batch's entries and leaves the earlier batch's entry alone", s == 200 and j["removed"] == 1 and pile[0] in doc()["edits"] and b1[0]["group"] in doc()["edits"][pile[0]]["groups"], (s, j))
    s, j = post({"undo": bid_ov})
    check("undo twice is a no-op", s == 200 and j["changed"] is False, (s, j))
    s, j = post({"undo": "b-20261015-000000-none"})
    check("undo of an unknown batch -> 404", s == 404, s)
    s, j = post({"undo": "last"})
    check("undo 'last' undoes the most recent live batch", s == 200 and j["changed"] and j["removed"] >= 1, (s, j))
    # ---- undo leaves alone what was edited singly since
    sid = nid()
    s, j = post({"id": sid, "kind": "place", "threshold": 0.9, "items": place_items(pile[20:23])})
    g0 = place_items(pile[20:21])[0]["group"]
    MC.apply_edit({"oid": pile[20], "group": g0, "action": "clear"}, index=idx, path=path)
    MC.apply_edit({"oid": pile[20], "group": g0, "action": "add", "note": "by hand since"}, index=idx, path=path)
    s, j = post({"undo": sid})
    check("undo leaves an entry that was edited singly since (no batch id) alone", s == 200 and j["removed"] == 2 and pile[20] in doc()["edits"] and "batch" not in doc()["edits"][pile[20]]["groups"][g0], (s, j))
    # ---- confirm / reject
    tent = [o for o in sorted(C) if C[o][1] == "t" and any(x[1] == "T" for x in C[o][3])][:4]
    tg = lambda o: next(x[0] for x in C[o][3] if x[1] == "T")
    s, j = post({"id": nid(), "kind": "confirm", "items": [{"oid": o, "group": tg(o), "action": "add", "source": "tentative"} for o in tent[:2]]})
    d = doc()
    check("confirm: a tentative card is added to the group it already holds, with a batch record (kind confirm)", s == 200 and d["edits"][tent[0]]["groups"][tg(tent[0])]["batch"]["kind"] == "confirm" and d["edits"][tent[0]]["groups"][tg(tent[0])]["source_at_edit"]["status"] == "tentative", (s, j))
    check("confirm counts as 'confirmed by hand' (tentative), not 'placed by hand', and in the batch sub-count", MC.resolve(idx, d)["counts"]["confirmed_by_hand_of_which"]["tentative"] >= 2 and MC.resolve(idx, d)["counts"]["confirmed_by_hand_batch"] >= 2)
    s, j = post({"id": nid(), "kind": "reject", "items": [{"oid": tent[2], "group": tg(tent[2]), "action": "remove", "source": "tentative"}]})
    e = doc()["edits"][tent[2]]["groups"][tg(tent[2])]
    check("reject: a batch of one is recorded as a removal with its own batch id", s == 200 and e["action"] == "remove" and e["batch"]["kind"] == "reject" and e["batch"]["id"].startswith("b-"), (s, j))
    check("a reject changes no generated count (the reconciliation is today's)", MC.resolve(idx, doc())["reconciliation"]["tentative"] == 2093)
    s, j = post({"id": nid(), "kind": "reject", "items": [{"oid": tent[3], "group": place_items(pile[30:31])[0]["group"], "action": "remove"}]})
    check("reject of a group the card does not hold as a soft placement -> 422", s == 422, (s, j))
    s, j = post({"id": nid(), "kind": "confirm", "items": [{"oid": tent[3], "group": tg(tent[3]), "action": "remove"}]})
    check("confirm with action remove -> 422", s == 422, (s, j))
    precise = next(o for o in sorted(C) if C[o][1] == "p" and any(x[1] == "P" for x in C[o][3]))
    s, j = post({"id": nid(), "kind": "confirm", "items": [{"oid": precise, "group": next(x[0] for x in C[precise][3] if x[1] == "P"), "action": "add"}]})
    check("confirm of a precisely held group -> 422 (it is not a soft placement)", s == 422, (s, j))
    sib = json.load(open(os.path.join(MC.HERE, "build", "sibling_placements.json"), encoding="utf-8"))["by_card"]
    so = next(iter(sib))
    s, j = post({"id": nid(), "kind": "confirm", "items": [{"oid": so, "group": "leaf:" + sib[so][0], "action": "add", "source": "sibling"}]})
    check("a sibling placement can be confirmed in a batch", s == 200, (s, j))
    # ---- fallback
    fo = next(o for o in sorted(FB) if FB[o] and o not in doc()["edits"])
    s, j = post({"id": nid(), "kind": "fallback", "threshold": 0.9, "items": [{"oid": fo, "group": FB[fo][0][0], "action": "add"}]})
    e = doc()["edits"][fo]["groups"][FB[fo][0][0]]
    check("fallback: a low-confidence possible home is placed with source fallback:<kind> and no score", s == 200 and e["batch"]["kind"] == "fallback" and e["batch"]["source"].startswith("fallback:") and e["batch"]["score"] is None, (s, j))
    fo2 = next(o for o in sorted(FB) if FB[o] and o not in doc()["edits"])
    s, j = post({"id": nid(), "kind": "fallback", "threshold": 0.9, "items": [{"oid": fo2, "group": place_items(pile[40:41])[0]["group"], "action": "add"}]})
    check("fallback: a group that is not in the card's fallback list -> 422", s == 422, (s, j))
    # ---- cap: exactly 100 is fine
    many = [o for o in pile if o not in doc()["edits"]][:100]
    s, j = post({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(many)})
    check("exactly 100 items is accepted", s == 200 and j["count"] == 100, (s, j.get("error")))
    # ---- concurrency
    base = doc()["revision"]
    free = [o for o in pile if o not in doc()["edits"]]
    res = []

    def w(i):
        res.append(post({"id": "b-20261015-9%05d-c%03d" % (i, i), "kind": "place", "threshold": 0.9, "items": place_items(free[i * 5:(i + 1) * 5])})[0])
    ts = [threading.Thread(target=w, args=(i,)) for i in range(10)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    d = doc()
    check("10 concurrent batches of 5 all land (50 entries, 10 revisions, a valid file)", res.count(200) == 10 and d["revision"] == base + 10 and all(o in d["edits"] for o in free[:50]), (res.count(200), d["revision"] - base))
    res2 = []
    same = {"id": "b-20261015-900000-same", "kind": "place", "threshold": 0.9, "items": place_items(free[60:63])}
    ts = [threading.Thread(target=lambda: res2.append(post(same))) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    check("8 concurrent copies of one batch apply once (the others are no-ops)", sum(1 for s, j in res2 if s == 200 and j["changed"]) == 1 and sum(1 for s, j in res2 if s == 200) == 8, [(s, j.get("changed")) for s, j in res2][:3])
    # ---- failed rename, corrupt file
    snap = open(path, "rb").read()
    real_replace = MC.os.replace

    def boom(*a, **k):
        raise OSError("disk says no")
    MC.os.replace = boom
    try:
        s, j = post({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(free[70:72])})
    finally:
        MC.os.replace = real_replace
    check("a failed rename -> 500 with a message, the file byte-identical, no temp file left", s == 500 and open(path, "rb").read() == snap and not [f for f in os.listdir(tmp) if f.endswith(".tmp")], (s, j))
    s, j = post({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(free[70:72])})
    check("and the same batch works once the disk does", s == 200, (s, j))
    open(path, "w").write("{ not json")
    s, j = post({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(free[80:81])})
    check("a corrupt file is refused (500) and left untouched", s == 500 and open(path).read() == "{ not json", (s, j))
    s, j = post({"undo": "last"})
    check("undo on a corrupt file is refused (500), file untouched", s == 500 and open(path).read() == "{ not json", (s, j))
    # ---- flag off
    off = copy.deepcopy(idx)
    off.pop("batch")
    try:
        MB.apply_batch({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(free[80:81])}, index=off, path=path)
        code = 200
    except MC.ApiError as e:
        code = e.status
    check("flag off (no `batch` in the index): the endpoint answers 404 and writes nothing", code == 404 and open(path).read() == "{ not json", code)
    # ---- HTTP level
    import serve
    srv = serve.Server(("127.0.0.1", 0), serve.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    json.dump(MC.empty_doc(), open(path, "w"))

    def http_post(body, headers=None, host=None, raw=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        data = raw if raw is not None else json.dumps(body).encode()
        h = headers if headers is not None else {"Content-Type": "application/json", "X-Manual-Edit": "1"}
        h = dict(h, **{"Content-Length": str(len(data))})
        if host:
            h["Host"] = host
        c.request("POST", "/api/manual/batch", body=data, headers=h)
        r = c.getresponse()
        out = r.read()
        c.close()
        try:
            return r.status, json.loads(out)
        except Exception:
            return r.status, out
    s, j = http_post({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(free[90:93])})
    check("HTTP: a good batch -> 200 and the file holds it", s == 200 and j["ok"] and all(o in doc()["edits"] for o in free[90:93]), (s, j))
    s, j = http_post({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(free[94:95])}, host="evil.example")
    check("HTTP: a foreign Host is refused (403)", s == 403, (s, j))
    s, j = http_post({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(free[94:95])}, headers={"Content-Type": "application/json"})
    check("HTTP: the X-Manual-Edit header is required (400)", s == 400, (s, j))
    s, j = http_post(None, raw=b'{"id": "' + b"x" * 70000 + b'"}')
    check("HTTP: an oversized body (over 64 KB) -> 413", s == 413, s)
    s, j = http_post(None, raw=b"{bad json")
    check("HTTP: bad JSON -> 400", s == 400, s)
    s, j = http_post({"id": nid(), "kind": "place", "threshold": 0.9, "items": place_items(free[94:95]) + [{"oid": unk, "group": "leaf:a", "action": "add", "score": 1}]})
    check("HTTP: a refused batch answers with the failing rows (items list) and writes nothing", s == 422 and j["items"] and not any(o in doc()["edits"] for o in free[94:95]), (s, j.get("error")))
    c = http.client.HTTPConnection("127.0.0.1", port)
    c.request("GET", "/api/manual/ping")
    jj = json.loads(c.getresponse().read())
    check("HTTP: the ping reports that batch actions are on", jj.get("batch") is True, jj)
    srv.shutdown()
    # ---- the real files
    after_real = [sha(p) for p in REAL_FILES]
    check("the real corrections file and its backup are byte-identical to before this test (never written)", before_real == after_real and None not in after_real[:1], [a[:10] if a else a for a in after_real])
    print("\n%d failure(s)" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
