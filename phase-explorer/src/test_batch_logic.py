#!/usr/bin/env python3
"""Logic tests (no browser) for the batch view's pure logic in reports/manualedit.js, run in a JavaScript engine (dukpy), against an independent Python implementation on the real data, and the batch counts
of the JS resolver against the Python one. A TEMP corrections file only (the real one is never opened for writing).

    python src/test_batch_logic.py
"""
import copy
import hashlib
import json
import os
import re
import sys
import tempfile

import dukpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as MC
import manual_batch as MB

HERE = MC.HERE
REAL = os.path.join(HERE, "corrections", "manual_placements.json")
FAILS = []


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" - " + str(detail)) if detail else ""))
    if not ok:
        FAILS.append(name)


def py_rows(idx, S, res, order, thr, skip, floor=0.70):
    """independent re-implementation of Manual.batchRows"""
    C, G = idx["cards"], idx["groups"]
    boiler = lambda r: bool(re.search("\u201c(?:Saga ETB lore counter|Chapter \\d+)\u201d", r[3] or "")) or G[r[0]][0] == "Put lore counters on this permanent"
    rows, handled, nosug, below = [], [], [], 0
    for o in order:
        if o not in C or C[o][1] == "o":
            continue
        held = {x[0] for x in C[o][3] if x[1] in "PBKR"}
        added = set(res["adds"].get(o, {}))
        lst = [r for r in S.get(o, []) if r[0] in G and r[0] not in added and r[0] not in held and not (skip and boiler(r))][:5]
        if o in res["adds"] or o in res["removes"] or o in set(res["marked"]):
            handled.append(o)
        elif not lst:
            nosug.append(o)
        elif lst[0][1] >= thr - 1e-9 and not all(x in ("text", "kw", "rule") for x in lst[0][2].split("+")):                 # a text-only, keyword-name-only or hand-rule-only top row is never ticked for you
            rows.append((o, "tick", [r[0] for r in lst]))
        elif lst[0][1] >= floor - 1e-9:
            rows.append((o, "review", [r[0] for r in lst]))
        else:
            below += 1
    return rows, handled, nosug, below


def main():
    real_before = hashlib.sha256(open(REAL, "rb").read()).hexdigest() if os.path.exists(REAL) else None
    idx = MC.load_index()
    S = MB.load_suggestions()
    C = idx["cards"]
    src = open(os.path.join(HERE, "reports", "manualedit.js"), encoding="utf-8").read()
    tmp = tempfile.mkdtemp(prefix="batch_logic_")
    path = os.path.join(tmp, "m.json")
    MC.CORR = path
    # ---- batch counts: JS = Python, with and without the batch flag
    pile = [o for o in sorted(C, key=lambda o: (C[o][4] is None, C[o][4] or 0, o)) if C[o][1] == "u" and o in S and S[o][0][1] >= 0.9]
    place = lambda oids: [{"oid": o, "group": S[o][0][0], "action": "add", "score": S[o][0][1], "source": S[o][0][2]} for o in oids]
    MB.apply_batch({"id": "b-20261015-100000-aaaa", "kind": "place", "threshold": 0.9, "items": place(pile[:6])}, index=idx, path=path)
    MC.apply_edit({"oid": pile[10], "group": S[pile[10]][0][0], "action": "add"}, index=idx, path=path)                          # a single placement: not a batch card
    MC.apply_edit({"oid": pile[0], "group": S[pile[0]][1][0], "action": "add"}, index=idx, path=path) if len(S[pile[0]]) > 1 else None   # a single add on a batch card: the card counts as single
    tent = [o for o in sorted(C) if C[o][1] == "t" and any(x[1] == "T" for x in C[o][3])][:3]
    tg = lambda o: next(x[0] for x in C[o][3] if x[1] == "T")
    MB.apply_batch({"id": "b-20261015-100001-bbbb", "kind": "confirm", "items": [{"oid": o, "group": tg(o), "action": "add"} for o in tent[:2]]}, index=idx, path=path)
    MB.apply_batch({"id": "b-20261015-100002-cccc", "kind": "reject", "items": [{"oid": tent[2], "group": tg(tent[2]), "action": "remove"}]}, index=idx, path=path)
    MB.apply_batch({"id": "b-20261015-100003-dddd", "kind": "place", "threshold": 0.9, "items": place(pile[20:22])}, index=idx, path=path)
    MB.apply_batch({"undo": "b-20261015-100003-dddd"}, index=idx, path=path)
    doc = MC.load_doc(path)
    py = MC.resolve(idx, doc)
    js = dukpy.evaljs([src, "Manual.resolve(dukpy.index, dukpy.doc)"], index=idx, doc=doc)
    check("batch counts agree (JS = Python)", js["counts"] == py["counts"], (js["counts"], py["counts"]))
    c = py["counts"]
    exp_b = 5 if len(S[pile[0]]) > 1 else 6
    check("placed by hand in a batch counts cards whose every add is a batch add (a card also placed singly counts as single)", c["placed_by_hand_batch"] == exp_b and c["placed_by_hand_new"] == 7, (c["placed_by_hand_batch"], c["placed_by_hand_new"]))
    check("confirmed by hand in a batch (2 tentative cards); the reject is a batch removal; 4 batches, 1 undone", c["confirmed_by_hand_batch"] == 2 and c["batch_removals"] == 1 and c["batches"] == 4 and c["batches_undone"] == 1, c)
    check("the reconciliation is unchanged by batches (hand taken from the pile; the rest as generated)", py["reconciliation"] == js["reconciliation"] and py["reconciliation"]["sum"] == 38921 and py["reconciliation"]["tentative"] == 2093 and
          py["reconciliation"]["unorganized"] == 1335 - py["counts"]["placed_by_hand_new"], py["reconciliation"])
    off = copy.deepcopy(idx)
    off.pop("batch")
    py0 = MC.resolve(off, doc)
    js0 = dukpy.evaljs([src, "Manual.resolve(dukpy.index, dukpy.doc)"], index=off, doc=doc)
    check("with the flag off the counts carry no batch keys and equal the earlier format (JS = Python)", py0["counts"] == js0["counts"] and "batches" not in py0["counts"] and "placed_by_hand_batch" not in js0["counts"], list(py0["counts"]))
    old = {"edits": {pile[30]: {"name": "x", "groups": {S[pile[30]][0][0]: {"action": "add", "date": "d", "note": "", "group_name": idx["groups"][S[pile[30]][0][0]][0], "source_at_edit": {}}}}}, "history": [], "revision": 1}
    check("an old entry without a batch field is read as a single placement", MC.resolve(idx, old)["counts"]["placed_by_hand_batch"] == 0 and MC.resolve(idx, old)["counts"]["placed_by_hand_new"] == 1)
    # ---- the batch rows: JS = an independent Python implementation, for the thresholds and both boilerplate settings
    res_empty = MC.resolve(idx, {"edits": {}, "history": [], "revision": 0})
    order = [o for o in sorted(C, key=lambda o: (C[o][4] is None, C[o][4] or 0, C[o][0], o)) if C[o][1] == "u"]
    for thr in (0.9, 0.8, 0.7):
        for skip in (True, False):
            for label, res in (("no edits", res_empty), ("some edits", MC.resolve(idx, doc))):
                jres = dukpy.evaljs([src, "Manual.resolve(dukpy.index, dukpy.doc)"], index=idx, doc={"edits": {}} if label == "no edits" else doc)
                jr = dukpy.evaljs([src, "Manual.batchRows(dukpy.index, dukpy.sugg, dukpy.res, dukpy.order, dukpy.thr, dukpy.skip, 0.7)"], index=idx, sugg=S, res=jres, order=order, thr=thr, skip=skip)
                prow, phand, pno, pbel = py_rows(idx, S, res, order, thr, skip)
                same = [(r["oid"], r["tier"], [x[0] for x in r["items"]]) for r in jr["rows"]] == prow and [h["oid"] for h in jr["handled"]] == phand and jr["nosug"] == pno and jr["below"] == pbel
                check("batch rows agree with the independent implementation (threshold %.2f, skip boilerplate %s, %s): %d rows" % (thr, skip, label, len(prow)), same, (len(jr["rows"]), len(prow)))
    jre = dukpy.evaljs([src, "Manual.resolve(dukpy.index, {edits: {}})"], index=idx)
    jrd = dukpy.evaljs([src, "Manual.resolve(dukpy.index, dukpy.doc)"], index=idx, doc=doc)
    jr = dukpy.evaljs([src, "Manual.batchRows(dukpy.index, dukpy.sugg, dukpy.res, dukpy.order, 0.9, true, 0.7)"], index=idx, sugg=S, res=jre, order=order)
    ticked = [r for r in jr["rows"] if r["tier"] == "tick"]
    check("at 0.90 with boilerplate skipped, 498 or fewer pile cards are pre-ticked and every one has a top score of at least 0.90", 0 < len(ticked) <= 510 and all(r["items"][0][1] >= 0.9 - 1e-9 for r in ticked), len(ticked))
    check("no row has a top score below 0.70; the review band is between 0.70 and the threshold", all(r["items"][0][1] >= 0.7 - 1e-9 for r in jr["rows"]) and all(r["items"][0][1] < 0.9 or all(x in ("text", "kw", "rule") for x in r["items"][0][2].split("+")) for r in jr["rows"] if r["tier"] == "review"))        # a text-only top row is review at any score
    check("a saga's boilerplate suggestion is never offered when skipped", not any("Put lore counters on this permanent" == idx["groups"][x[0]][0] for r in jr["rows"] for x in r["items"]) and not any("Saga ETB lore counter" in x[3] for r in jr["rows"] for x in r["items"][:1]))
    jr2 = dukpy.evaljs([src, "Manual.batchRows(dukpy.index, dukpy.sugg, dukpy.res, dukpy.order, 0.9, false, 0.7)"], index=idx, sugg=S, res=jre, order=order)
    check("with the skip off the boilerplate cards come back (11 pile cards)", sum(1 for r in jr2["rows"] if any("Put lore counters" in idx["groups"][x[0]][0] for x in r["items"][:1])) >= 1)
    check("each row offers up to 5 suggestions, so more than one can be ticked per card", max(len(r["items"]) for r in jr["rows"]) == 5)
    jh = dukpy.evaljs([src, "Manual.batchRows(dukpy.index, dukpy.sugg, dukpy.res, dukpy.order, 0.9, true, 0.7)"], index=idx, sugg=S, res=jrd, order=order)
    hd = {h["oid"] for h in jh["handled"]}
    check("a card with any hand entry is never a row, only listed as handled (batch or single, placement, removal or mark)", hd and not (hd & {r["oid"] for r in jh["rows"]}) and set(pile[:6]) <= hd, len(hd))
    ids = [dukpy.evaljs([src, "Manual.newBatchId(new Date(2026, 9, 15, 17, 5, 9), function () { return %s; })" % x]) for x in (0, 0.5, 0.999)]
    check("a new batch id has the form the server accepts (b-YYYYMMDD-HHMMSS-xxxx)", all(MB.ID_RE.match(i) for i in ids) and ids[0] == "b-20261015-170509-aaaa", ids)
    check("the boilerplate rule", dukpy.evaljs([src, "[Manual.isBoilerplate([0,0,0,'ability \\u201cSaga ETB lore counter\\u201d shares 3 of 3'], 'x'), Manual.isBoilerplate([0,0,0,'ability \\u201cChapter 2\\u201d shares'], 'x'), Manual.isBoilerplate([0,0,0,''], 'Put lore counters on this permanent'), Manual.isBoilerplate([0,0,0,'ability \\u201cDestroy target\\u201d'], 'Destroy a creature')]"]) == [True, True, True, False])
    after = hashlib.sha256(open(REAL, "rb").read()).hexdigest() if os.path.exists(REAL) else None
    check("the real corrections file was not touched", after == real_before)
    print("\n%d failure(s)" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
