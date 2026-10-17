#!/usr/bin/env python3
"""Tests (no browser) for the text suggestions, on the real build output (build/text_sug/*) with a TEMP corrections file only: the real corrections/manual_placements.json and its backup are hashed before and after.

    python src/test_text_suggestions.py          (needs build/text_sug: run python src/build_text_suggestions.py)

Checks that do not depend on the generator: coverage counted straight from the files; every row names an offered group the card does not already hold precisely; every quoted line exists in the card's own text and
the member-line table; the 65 pile / tentative cards that had no suggestion; a text-only top row is never ticked (JS logic in a JavaScript engine, and an independent Python rule on the real rows); a text-only row
can be placed in a batch (server) with its score checked and "text" recorded as the source, and undone; a hand-placed card keeps second-function options; nothing is written to the real corrections file.
"""
import collections
import hashlib
import io
import json
import os
import sys
import tempfile

import dukpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as MC
import manual_batch as MB

HERE = MC.HERE
BUILD = os.path.join(HERE, "build")
REAL = os.path.join(HERE, "corrections", "manual_placements.json")
FAILS = []


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" - " + str(detail)) if detail else ""))
    if not ok:
        FAILS.append(name)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def jl(*p):
    with io.open(os.path.join(BUILD, *p), encoding="utf-8") as fh:
        return json.load(fh)


def text_only(src):
    return all(s in ("text", "kw") for s in src.split("+"))


def never_tick(src):
    return all(s in ("text", "kw", "rule") for s in src.split("+"))


def main():
    real_before = (sha(REAL), sha(REAL + ".bak"))
    meta, queue = jl("text_sug", "meta.json"), jl("text_sug", "queue.json")["cards"]
    idx = MC.load_index()
    G, C = idx["groups"], idx["cards"]
    cards = jl("ability_taxonomy_cards.json")["cards"]
    old = jl("manual_suggestions.json")["cards"]
    per = meta["line_shard"]
    lines = {}
    for n in range((meta["lines"] + per - 1) // per):
        for k, row in enumerate(jl("text_sug", "l", "%d.json" % n)):
            lines[n * per + k] = row
    check("the member-line table has every line the meta says (%d)" % meta["lines"], len(lines) == meta["lines"])
    shards = {}
    for f in sorted(os.listdir(os.path.join(BUILD, "text_sug", "c"))):
        shards.update(jl("text_sug", "c", f))
    scope = [o for o, c in C.items() if c[1] != "o"]
    # ---- coverage, counted from the files
    n5, none = 0, []
    rows_of = {}
    for o in scope:
        r = queue.get(o) if C[o][1] in "utam" else shards.get(o)
        rows_of[o] = r or []
        if r and len(r) >= 5:
            n5 += 1
        else:
            none.append(o)
    check("every in-scope card with text has at least 5 suggestions stored (%d of %d)" % (n5, len(scope)), all(not (cards[o]["t"] or "").strip() for o in none), len(none))
    check("the only cards without any are the no-text cards in the No abilities block (%d)" % len(none), all(C[o][1] == "v" and not (cards[o]["t"] or "").strip() for o in none) and len(none) == 346, collections.Counter(C[o][1] for o in none))
    check("the queue file holds exactly the u/t/a/m cards (%d)" % len(queue), set(queue) == {o for o, c in C.items() if c[1] in "utam"})
    # ---- row integrity
    bad = collections.Counter()
    for o in scope:
        held = {x[0] for x in C[o][3] if x[1] in MC.PRECISE}
        prev = 2.0
        for r in rows_of[o]:
            if o in queue:
                gid, sc, src = r[0], r[1], r[2]
                if sc > prev + 1e-9 and not (meta.get("engine_v2") and "rule" in src.split("+")):                    # ENGINE_V2 may move a rule row to the fifth place
                    bad["queue row out of order"] += 1
                if "rule" not in src.split("+") or not meta.get("engine_v2"):
                    prev = sc
                ref = r[4:7] if len(r) > 6 else None
            else:
                gid, sc, src = meta["groups"][r[0]], r[1] / 1000.0, "kw" if r[2] < 0 else "text"
                ref = r[2:5] if r[2] >= 0 else None
            if gid not in G or not G[gid][4]:
                bad["group not offered"] += 1
            if gid in held:
                bad["a group the card already holds precisely"] += 1
            if not 0 <= sc <= 1:
                bad["score outside 0..1"] += 1
            if ref:
                qs, ql, lid = ref
                if qs < 0 or not cards[o]["t"][qs:qs + ql].strip() or lid not in lines:
                    bad["a quoted line does not resolve"] += 1
            if "text" in src.split("+") and not ref:
                bad["a text row without a quoted line"] += 1
    check("every row: an offered group, not already held precisely, a score in 0..1, queue rows in score order, every quoted line found in the card's text and the line table", not bad, dict(bad))
    check("every card keeps at least 5 suggestions after two hand adds (7 rows stored)", all(len(rows_of[o]) >= 7 for o in scope if o in queue or (cards[o]["t"] or "").strip()), sum(1 for o in scope if 0 < len(rows_of[o]) < 7))
    # ---- the 65 pile / tentative cards that had no suggestion
    zero = [o for o, c in C.items() if c[1] in "ut" and o not in old]
    check("the %d pile / tentative cards the existing engine has no suggestion for (65 before the hand groups of 2026-10-16) have at least 5 each now" % len(zero), 0 < len(zero) <= 65 and all(len(queue[o]) >= 5 for o in zero), len(zero))
    print("   what they get, by source of the top row:", dict(collections.Counter(queue[o][0][2] for o in zero)))
    # ---- text-only never ticked: the JS logic and an independent Python rule
    src = open(os.path.join(HERE, "reports", "manualedit.js"), encoding="utf-8").read()
    row = lambda g, s, k: [g, s, k, "w"]
    G2 = {"leaf:a": ["A", 9, "p", "leaf", 1], "leaf:b": ["B", 9, "p", "leaf", 1]}
    idx2 = {"groups": G2, "cards": {"o1": ["n", "u", 1, [], 1], "o2": ["n", "u", 1, [], 2], "o3": ["n", "u", 1, [], 3], "o4": ["n", "u", 1, [], 4], "o5": ["n", "u", 1, [], 5]}}
    sg = {"o1": [row("leaf:a", 0.95, "text")], "o2": [row("leaf:a", 0.95, "sig")], "o3": [row("leaf:a", 0.95, "kw+text")], "o4": [row("leaf:a", 0.95, "sig+text")], "o5": [row("leaf:a", 0.60, "text")]}
    res = {"adds": {}, "removes": {}, "marks": {}, "marked": []}
    out = dukpy.evaljs(src + "; var R = Manual.batchRows(%s, %s, %s, %s, 0.90, true, 0.70); JSON.stringify([R.rows.map(function (r) { return r.oid + ':' + r.tier; }), R.below, [Manual.isTextOnly('text'), Manual.isTextOnly('kw+text'), Manual.isTextOnly('sig+text'), Manual.isTextOnly('')]]);" % (
        json.dumps(idx2), json.dumps(sg), json.dumps(res), json.dumps(["o1", "o2", "o3", "o4", "o5"])))
    rows_, below, flags = json.loads(out)
    check("JS: a text-only (or keyword-name-only) top row scoring 0.95 is review, not tick; sig, and sig+text, still tick; 0.60 is below the band", rows_ == ["o1:review", "o2:tick", "o3:review", "o4:tick"] and below == 1 and flags == [True, True, False, False], (rows_, below, flags))
    order = sorted(queue)
    res0 = {"adds": {}, "removes": {}, "marks": {}, "marked": []}
    out = dukpy.evaljs(src + "; var R = Manual.batchRows(%s, %s, %s, %s, 0.90, true, 0.70); JSON.stringify(R.rows.map(function (r) { return [r.oid, r.tier]; }));" % (
        json.dumps({"groups": G, "cards": C}), json.dumps(queue), json.dumps(res0), json.dumps(order)))
    tier = dict(json.loads(out))
    risky = [o for o in order if queue[o] and queue[o][0][1] >= 0.90 and text_only(queue[o][0][2])]
    check("on the real rows: %d cards have a text-only top row scoring 0.90 or more; none is a tick row (the batch logic run over all %d queue cards)" % (len(risky), len(order)),
          all(tier.get(o) != "tick" for o in risky) and any(v == "tick" for v in tier.values()), len(risky))
    ticks_bad = [o for o, t in tier.items() if t == "tick" and never_tick(queue[o][0][2])]
    check("no tick row anywhere has a text-only, keyword-name-only or hand-rule-only top row", not ticks_bad, ticks_bad[:3])
    out2 = dukpy.evaljs(src + "; var R = Manual.batchRows(%s, %s, %s, %s, 0.70, true, 0.70); JSON.stringify(R.rows.map(function (r) { return [r.oid, r.tier]; }));" % (
        json.dumps({"groups": G, "cards": C}), json.dumps(queue), json.dumps(res0), json.dumps(order)))
    tier70 = dict(json.loads(out2))
    hand_top = [o for o in order if queue[o] and queue[o][0][0].startswith("hand:") and never_tick(queue[o][0][2])]
    check("even with the slider at 0.70, no row led by a hand-group rule alone is ticked (%d such cards)" % len(hand_top), bool(hand_top) and all(tier70.get(o) != "tick" for o in hand_top), len(hand_top))
    # ---- the server: place a text-only row from the merged file, in a TEMP corrections file
    tmp = tempfile.mkdtemp(prefix="text_test_")
    path = os.path.join(tmp, "manual_placements.json")
    assert os.path.abspath(path) != os.path.abspath(REAL)
    MC.CORR = path
    S = MB.load_suggestions()
    check("the server validates against the merged rows (the queue file) when the text layer is on", S is not None and S.get(next(iter(queue))) == queue[next(iter(queue))])
    pile = [o for o in sorted(queue) if C[o][1] == "u" and queue[o] and text_only(queue[o][0][2])][:3]
    check("there are pile cards whose top row is text only", len(pile) == 3)
    items = [{"oid": o, "group": S[o][0][0], "action": "add", "score": S[o][0][1], "source": S[o][0][2]} for o in pile]
    try:
        MB.apply_batch({"id": "b-20261016-100000-tx01", "kind": "place", "threshold": 0.9, "items": [dict(items[0], score=items[0]["score"] + 0.01)]}, index=idx, path=path)
        refused = False
    except MC.ApiError as e:
        refused = e.status == 422
    check("a text row with a changed score is refused (422), nothing written", refused and not os.path.exists(path))
    r = MB.apply_batch({"id": "b-20261016-100001-tx02", "kind": "place", "threshold": 0.9, "items": items}, index=idx, path=path)
    d = json.load(open(path, encoding="utf-8"))
    srcs = {d["edits"][o]["groups"][S[o][0][0]]["batch"]["source"] for o in pile}
    check("a batch of 3 text-only rows is placed, with the source recorded as text / kw", r.get("ok", True) and len(d["edits"]) == 3 and all(text_only(s) for s in srcs), srcs)
    res_ = MC.resolve(idx, d)
    check("they count as placed by hand (batch), and the reconciliation still sums to 38,921", res_["counts"]["placed_by_hand_new"] == 3 and res_["reconciliation"]["sum"] == 38921, res_["counts"].get("placed_by_hand_batch"))
    # ---- a hand-placed card keeps second-function options
    o = pile[0]
    shown = [x for x in queue[o] if x[0] not in res_["adds"].get(o, {})]
    check("a hand-placed pile card still has at least 5 other suggestions to show (second-function options)", len(shown) >= 5 and S[o][0][0] not in [x[0] for x in shown[:5]], len(shown))
    u = MB.apply_batch({"undo": "b-20261016-100001-tx02"}, index=idx, path=path)
    check("Undo this batch takes all three back", len(json.load(open(path, encoding="utf-8"))["edits"]) == 0, u)
    # ---- ENGINE_V2: clusters in the page's JavaScript against the build's Python on every queue card, the keyword rows, and the slot for a rule row
    import build_text_suggestions as BT
    if meta.get("engine_v2"):
        py = {o: [[r[0] for r in c] for c in BT.cluster_rows([r for r in queue[o] if r[0] in G], G)] for o in order}
        jsout = dukpy.evaljs(src + "; var Q = %s, X = %s, out = {}; for (var o in Q) { out[o] = Manual.clusterRows(X, Q[o].filter(function (r) { return X.groups[r[0]]; })).map(function (c) { return c.map(function (r) { return r[0]; }); }); } JSON.stringify(out);" % (
            json.dumps(queue), json.dumps({"groups": G})))
        js = json.loads(jsout)
        bad = [o for o in order if js[o] != py[o]]
        check("ENGINE_V2: the page's clusterRows (JavaScript) equals the build's cluster_rows (Python) on all %d queue cards" % len(order), not bad, bad[:3])
        shown_missing = [o for o in order for r in queue[o] if "rule" in r[2].split("+") and r[0] not in {x for c in py[o][:5] for x in c}]
        check("ENGINE_V2: every rule row is among the first 5 clusters of its card", not shown_missing, shown_missing[:3])
        ev = [(o, r) for o in order for r in queue[o] if r[2] == "kw" and r[0] in ("kw:Flying", "kw:Haste", "kw:Deathtouch", "kw:Menace", "kw:Trample", "kw:Vigilance")]
        check("ENGINE_V2: evergreen keyword rows score 0.30 (%d rows) and a keyword row never scores above 0.60" % len(ev), ev and all(abs(r[1] - 0.30) < 1e-9 for o, r in ev) and all(r[1] <= 0.60 + 1e-9 for o in order for r in queue[o] if r[2] == "kw"), len(ev))
        nm = {c[0]: o for o, c in C.items()}
        rd = {r[0] for r in queue[nm["Rime Dryad"]]}
        gf = {r[0] for r in queue[nm["Goblin Flotilla"]]}
        od = {r[0]: r for r in queue[nm["Odric, Blood-Cursed"]]}
        check("ENGINE_V2: Rime Dryad gets the Forestwalk block, Goblin Flotilla the Islandwalk block and not the generic landwalk one, Odric (keywords only named in an effect) no keyword-pair row",
              "kw:Landwalk|Forest" in rd and "kw:Landwalk|Island" in gf and "kw:Landwalk" not in gf and not [g for g in od if od[g][2] == "kw" and "+" in g], (sorted(rd)[:3], sorted(gf)[:3]))
    # ---- reasons
    lowq = [o for o in queue if queue[o][0][2] == "text"][:1]
    check("a text-only queue row quotes a card line and a member line", bool(lowq) and len(queue[lowq[0]][0]) == 7 and lines[queue[lowq[0]][0][6]][0], queue[lowq[0]][0] if lowq else None)
    check("the real corrections file and its backup are byte-identical", (sha(REAL), sha(REAL + ".bak")) == real_before)
    print("\n%d failure(s)" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
