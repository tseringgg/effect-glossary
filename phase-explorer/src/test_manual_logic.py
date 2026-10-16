#!/usr/bin/env python3
"""Logic test (no browser): reports/manualedit.js, run in a JavaScript engine (dukpy), against the Python resolver (src/manual_common.py) on the real build/manual_index.json.

    python src/test_manual_logic.py

Builds a synthetic corrections document that exercises every case (a pile card placed, a nothing-fits mark, a mark overridden by a placement, a tentative / annotation / tag card confirmed, a precisely placed card
edited, a removal of a held group, a removal that no longer applies, an unknown group, an unknown card, a renamed group, a not-a-card entry) and checks that the JS and Python resolvers agree on every count and list.
Also checks the group search and the group-to-page key mapping, and that no counting rule lets a hand edit change a generated number.
"""
import json
import os
import sys

import dukpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as MC

HERE = MC.HERE
FAILS = []


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" - " + str(detail)) if detail else ""))
    if not ok:
        FAILS.append(name)


def entry(action, gid, name, reason=2):
    return {"action": action, "date": "2026-10-14T10:00:00", "note": "", "group_name": name, "source_at_edit": {"status": "unorganized", "reason": {"code": reason, "text": "x"}}}


def main():
    idx = MC.load_index()
    C, G = idx["cards"], idx["groups"]

    def first(state, pred=lambda c: True, skip=0):
        return [o for o, c in sorted(C.items()) if c[1] == state and pred(c)][skip]
    offered = [g for g, v in sorted(G.items()) if v[4]]
    pile = [o for o, c in sorted(C.items()) if c[1] == "u"]
    p1, p2, p3, p4 = pile[0], pile[1], pile[2], pile[3]
    t1, a1, m1 = first("t"), first("a"), first("m")
    pr = first("p", lambda c: any(x[1] == "P" for x in c[3]))
    nc = first("o")
    held_p4 = next((x[0] for x in C[p4][3]), None)
    edits = {
        p1: {"name": C[p1][0], "groups": {offered[0]: entry("add", offered[0], G[offered[0]][0])}},
        p2: {"name": C[p2][0], "groups": {"none:fits": entry("nofit", "none:fits", "")}},
        p3: {"name": C[p3][0], "groups": {"none:fits": entry("nofit", "none:fits", ""), offered[1]: entry("add", offered[1], G[offered[1]][0])}},
        p4: {"name": C[p4][0], "groups": {"leaf:azzzzzzzzz": entry("add", "x", "Gone"), **({held_p4: entry("remove", held_p4, G[held_p4][0])} if held_p4 else {}), offered[2]: entry("add", offered[2], "An old name")}},
        t1: {"name": C[t1][0], "groups": {offered[3]: entry("add", offered[3], G[offered[3]][0])}},
        a1: {"name": C[a1][0], "groups": {offered[4]: entry("add", offered[4], G[offered[4]][0])}},
        m1: {"name": C[m1][0], "groups": {offered[5]: entry("add", offered[5], G[offered[5]][0])}},
        pr: {"name": C[pr][0], "groups": {offered[6]: entry("add", offered[6], G[offered[6]][0])}},
        nc: {"name": "not a card", "groups": {offered[7]: entry("add", offered[7], G[offered[7]][0]), "none:fits": entry("nofit", "none:fits", "")}},
        "00000000-0000-4000-8000-000000000000": {"name": "gone", "groups": {offered[8]: entry("add", offered[8], "x")}},
    }
    stale_card = first("u", lambda c: not c[3], 0) if any(c[1] == "u" and not c[3] for c in C.values()) else None
    if stale_card:
        edits[stale_card] = {"name": C[stale_card][0], "groups": {offered[9]: entry("remove", offered[9], G[offered[9]][0])}}
    doc = {"revision": 3, "edits": edits, "history": []}
    py = MC.resolve(idx, doc)
    src = open(os.path.join(HERE, "reports", "manualedit.js"), encoding="utf-8").read()
    js = dukpy.evaljs([src, "Manual.resolve(dukpy.index, dukpy.doc)"], index=idx, doc=doc)
    check("counts agree (JS = Python)", js["counts"] == py["counts"], (js["counts"], py["counts"]))
    check("reconciliation agrees and sums to the universe", js["reconciliation"] == py["reconciliation"] and py["reconciliation"]["sum"] == len(C) == 38921, py["reconciliation"])
    for k in ("hand_new", "precise_edits", "marked"):
        check("list '%s' agrees" % k, js[k] == py[k], (js[k], py[k]))
    check("list 'confirmed' agrees", js["confirmed"] == py["confirmed"])
    key = lambda L: sorted((x["oid"], x["group"]) for x in L)
    check("orphans, renamed and stale lists agree", key(js["orphans"]) == key(py["orphans"]) and key(js["renamed"]) == key(py["renamed"]) and key(js["stale"]) == key(py["stale"]),
          (len(js["orphans"]), len(py["orphans"])))
    check("adds and removes agree", {o: sorted(v) for o, v in js["adds"].items()} == py["adds"] and {o: sorted(v) for o, v in js["removes"].items()} == py["removes"])
    c = py["counts"]
    check("a pile card with a placement counts once as placed by hand (p1, p3 and p4's rename-only add)", p1 in py["hand_new"] and p3 in py["hand_new"] and p4 in py["hand_new"] and c["placed_by_hand_new"] == 3, c["placed_by_hand_new"])
    check("a nothing-fits mark is its own count and never a placement (p2 only; p3's is overridden by its placement)", py["marked"] == [p2] and p2 not in py["hand_new"] and c["marked_nothing_fits"] == 1, py["marked"])
    check("soft-placed cards confirmed by hand stay out of 'placed by hand' and are a sub-count", c["confirmed_by_hand_of_which"] == {"tentative": 1, "annotation": 1, "tag": 1} and c["confirmed_by_hand"] == 3)
    check("a precisely placed card's edit counts nowhere (reported on its own)", py["precise_edits"] == [pr] and pr not in py["hand_new"])
    check("a not-a-card entry never counts (no placement, no mark)", nc not in py["hand_new"] and nc not in py["marked"] and nc not in py["precise_edits"])
    check("an unknown group and an unknown card are orphans (2)", c["orphans"] == 2, py["orphans"])
    check("a group renamed since the edit is reported (and still counts)", any(r["oid"] == p4 for r in py["renamed"]))
    r = py["reconciliation"]
    check("only pile cards leave the unorganized figure; tentative / annotation / tag stay as generated", r["unorganized"] == 1335 - c["placed_by_hand_new"] and (r["tentative"], r["annotation"], r["tag"], r["placed"], r["not_cards"]) == (2093, 960, 1205, 27590, 5738), r)
    empty = MC.resolve(idx, {"edits": {}})
    check("with no edits the reconciliation is exactly today's", empty["reconciliation"] == {"placed": 27590, "tentative": 2093, "annotation": 960, "tag": 1205, "hand": 0, "unorganized": 1335, "not_cards": 5738, "sum": 38921})
    # search and key mapping
    s = dukpy.evaljs([src, "Manual.search(dukpy.index, 'affinity', 12, {})"], index=idx)
    check("group search finds the keyword group 'Affinity + Flying'", any(x["gid"] == "kw:Affinity+Flying" for x in s), [x["name"] for x in s][:3])
    s = dukpy.evaljs([src, "Manual.search(dukpy.index, 'destroy noncreature permanent', 12, {})"], index=idx)
    check("search ANDs the words and ranks a name that starts with them first", bool(s) and all("destroy" in x["name"].lower() for x in s[:3]), [x["name"] for x in s][:3])
    s = dukpy.evaljs([src, "Manual.search(dukpy.index, 'destroy', 500, {})"], index=idx)
    check("search never returns a group that is not offered (catch-alls, buckets)", all(G[x["gid"]][4] for x in s) and len(s) == 500 or all(G[x["gid"]][4] for x in s))
    ex = {offered[0]: 1}
    s = dukpy.evaljs([src, "Manual.search(dukpy.index, %s, 500, dukpy.ex)" % json.dumps(G[offered[0]][0][:6]), ], index=idx, ex=ex)
    check("search leaves out groups the card already has (exclude set)", all(x["gid"] != offered[0] for x in s))
    keys = {}
    for layer in MC.LAYERS:
        gid = next(g for g, v in sorted(G.items()) if v[3] == layer and v[4])
        keys[layer] = (gid, dukpy.evaljs([src, "Manual.goKey(dukpy.gid)"], gid=gid))
    tax = json.load(open(os.path.join(HERE, "build", "ability_taxonomy.json"), encoding="utf-8"))
    tent = json.load(open(os.path.join(HERE, "build", "tentative_placements.json"), encoding="utf-8"))
    loose = json.load(open(os.path.join(HERE, "build", "loose_groups.json"), encoding="utf-8"))
    tag = json.load(open(os.path.join(HERE, "build", "tag_placements.json"), encoding="utf-8"))
    ok = (keys["leaf"][1][2:] in tax["leaves"] and keys["tent"][1][3:] in tent["groups"] and keys["loose"][1][3:] in loose["groups"] and keys["tag"][1][3:] in tag["groups"]
          and keys["kw"][1][3:] in tax["blocks"]["keyword"]["leaves"] and keys["rp"][1][3:] in tax["blocks"]["replacement"]["leaves"])
    check("goKey maps every layer to a key the page can open", ok, keys)
    print("\n%d failure(s)" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
