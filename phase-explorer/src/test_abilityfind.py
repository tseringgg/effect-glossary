#!/usr/bin/env python3
"""Run reports/abilityfind.js (the file the new browse.html loads) against the real data files.

    python src/test_abilityfind.py [name ...]

Executes the actual search and describe logic in a JavaScript engine (dukpy/Duktape, ES5). It is NOT a
render check: it proves the lookup and the plain-language answers, not how the page draws them.

Checks
  1. Reconciliation from build/ability_taxonomy.json: the views sum to the universe; groups sum to the
     unorganized total; every lookup entry's code agrees with the ledger's view.
  2. EVERY entry (all oracle ids, every face name) is found by an exact search of its own name, and its
     answer is non-empty and never says "undefined".
  3. Ordering: in a result list no out-of-scope entry precedes a real card.
  4. The named lookups given on the command line (default: the Part 4 list) are printed.
  5. Hand placements (ctx.hand, optional): with no ctx.hand every answer is unchanged; with one, a hand-placed card says where it was placed and that it was by hand (a newly placed pile card,
     a confirmed soft card, an edit on a precisely placed card, a 'nothing fits' mark, a removal); nothing says "checked", "verified" or "undefined".
"""
import io
import json
import os
import sys

import dukpy

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
NAMED = ["Armageddon", "Ravages of War", "Death Cloud", "Global Ruin", "Shuri, Wakandan Inventor", "Mulldrifter",
         "Spark Double", "Lightning Bolt", "Storm Crow", "Yargle", "Grizzly Bears", "Jeska, Thrice Reborn",
         "Treasure", "Akoum"]


def load(name):
    return json.load(io.open(os.path.join(BUILD, name), encoding="utf-8"))


JS_CTX = r"""
var LOOKUP = dukpy.lookup, TAX = dukpy.tax;
var IDX = AbilityFind.build(LOOKUP);
var NODES = {}, FAMS = {};
(function () {
  var f, n, i, j;
  for (i = 0; i < TAX.families.length; i++) {
    f = TAX.families[i];
    for (j = 0; j < f.nodes.length; j++) { n = f.nodes[j]; NODES[n.id] = n; FAMS[n.id] = f.name; }
  }
})();
var CTX = {
  leafName: function (id) { return TAX.leaves[id].name; },
  leafPath: function (id) { var l = TAX.leaves[id]; return FAMS[l.node] + " › " + NODES[l.node].name; },
  leafNote: function (id) { return TAX.leaves[id].notes.join(" "); },
  kwLeaf: function (id) { return TAX.blocks.keyword.leaves[id]; },
  sgLeaf: function (id) { return TAX.blocks.replacement.leaves[id]; },
  sgBlock: TAX.blocks.replacement.name,
  group: function (id) { var g = TAX.unorganized, i; for (i = 0; i < g.length; i++) if (g[i].id === id) return g[i]; }
};
function lookupCard(name) {
  var r = AbilityFind.search(IDX, name, 40), i, out = [];
  for (i = 0; i < r.matches.length; i++) out.push(AbilityFind.describe(IDX, r.matches[i], CTX));
  return { total: r.total, answers: out };
}
function checkAll() {
  var E = LOOKUP.entries, i, j, names, hits, found, bad = [], ans, oosFirst = 0;
  for (i = 0; i < E.length; i++) {
    names = [E[i][1]].concat(E[i][2]);
    for (j = 0; j < names.length; j++) {
      hits = AbilityFind.exact(IDX, names[j]);
      found = false;
      for (var k = 0; k < hits.length; k++) if (hits[k][0] === E[i][0]) found = true;
      if (!found) bad.push("not found: " + names[j]);
    }
    ans = AbilityFind.describe(IDX, E[i], CTX);
    if (!ans.text || ans.text.indexOf("undefined") >= 0) bad.push("bad answer: " + E[i][1] + " " + E[i][3]);
  }
  return { entries: E.length, bad: bad.slice(0, 20), nbad: bad.length };
}
function orderCheck(q) {
  var r = AbilityFind.search(IDX, q, 200), i, sawOos = false, bad = 0;
  for (i = 0; i < r.matches.length; i++) {
    if (r.matches[i][3] === "o") sawOos = true; else if (sawOos) bad++;
  }
  return bad;
}
"""


HAND_JS = r"""
function handCases(names) {
  var out = [], i, r, e, h, a0, a1, kinds = {
    fresh: { adds: [{ name: "Destroy a noncreature permanent", layer: "leaf", date: "2026-10-14T15:02:11", note: "artifact, enchantment or land" }], fresh: true, was: "only in a held group", confirmed: "", nofit: null, removed: [] },
    confirmed: { adds: [{ name: "Gain life", layer: "leaf", date: "2026-10-14T15:02:11", note: "" }], fresh: false, was: "", confirmed: "tentative", nofit: null, removed: [] },
    edit: { adds: [{ name: "Gain life", layer: "tentative group", date: "2026-10-14T15:02:11", note: "" }], fresh: false, was: "", confirmed: "", nofit: null, removed: [] },
    nofit: { adds: [], fresh: false, was: "", confirmed: "", nofit: { date: "2026-10-14T15:02:11", note: "" }, removed: [] },
    removed: { adds: [], fresh: false, was: "", confirmed: "", nofit: null, removed: [{ name: "Draw cards" }] },
    batchplace: { adds: [{ name: "Destroy a noncreature permanent", layer: "leaf", date: "2026-10-15T15:02:11", note: "", batch: { id: "b-20261015-150211-ab12", kind: "place", score: 0.93, source: "sig+tag", threshold: 0.9 } }], fresh: true, was: "only in a held group", confirmed: "", nofit: null, removed: [] },
    batchfallback: { adds: [{ name: "Gain life", layer: "leaf", date: "2026-10-15T15:02:11", note: "", batch: { id: "b-20261015-150211-ab13", kind: "fallback", score: null, source: "fallback:words", threshold: 0.9 } }], fresh: true, was: "no readable ability", confirmed: "", nofit: null, removed: [] },
    batchconfirm: { adds: [{ name: "Gain life", layer: "tentative group", date: "2026-10-15T15:02:11", note: "", batch: { id: "b-20261015-150211-ab14", kind: "confirm", score: null, source: "tentative", threshold: null } }], fresh: false, was: "", confirmed: "tentative", nofit: null, removed: [] },
    batchreject: { adds: [], fresh: false, was: "", confirmed: "", nofit: null, removed: [{ name: "Draw cards", batch: { id: "b-20261015-150211-ab15", kind: "reject", score: null, source: "tag", threshold: null } }] }
  };
  for (i = 0; i < names.length; i++) {
    e = AbilityFind.search(IDX, names[i], 1).matches[0];
    a0 = AbilityFind.describe(IDX, e, CTX);
    for (var k in kinds) {
      CTX.hand = (function (kk) { return function (oid) { return kk; }; })(kinds[k]);
      a1 = AbilityFind.describe(IDX, e, CTX);
      delete CTX.hand;
      out.push({ card: names[i], kind: k, base: a0.text, text: a1.text, rk: a1.kind });
    }
    CTX.hand = function () { return null; };
    a1 = AbilityFind.describe(IDX, e, CTX);
    delete CTX.hand;
    out.push({ card: names[i], kind: "null", base: a0.text, text: a1.text, rk: a1.kind });
  }
  return out;
}
"""


def main():
    tax = load("ability_taxonomy.json")
    lookup = load("ability_taxonomy_lookup.json")
    ledger = load("ability_taxonomy_ledger.json")
    src = io.open(os.path.join(HERE, "reports", "abilityfind.js"), encoding="utf-8").read()
    t = tax["totals"]
    ok = True
    v = t["views"]
    if sum(v.values()) != t["universe"]:
        print("FAIL views do not sum to the universe"); ok = False
    if sum(g["cards"] for g in tax["unorganized"]) != v.get("unorganized", 0):
        print("FAIL groups do not sum to unorganized"); ok = False
    code_of = {"placed": "l", "broad_only": "b", "keyword_block": "k", "replacement_group": "g", "no_abilities": "v",
               "unorganized": "u", "not_a_card": "o"}
    mism = [e[1] for e in lookup["entries"] if code_of[ledger["cards"][e[0]]["view"]] != e[3]]
    if mism or len(lookup["entries"]) != t["universe"]:
        print("FAIL lookup/ledger mismatch", len(mism), mism[:5]); ok = False
    res = dukpy.evaljs([src, JS_CTX, "checkAll()"], lookup=lookup, tax=tax)
    print("entries", res["entries"], "problems", res["nbad"], res["bad"])
    ok = ok and res["nbad"] == 0
    for q in ("dragon", "goblin", "storm", "angel", "treasure"):
        b = dukpy.evaljs([src, JS_CTX, "orderCheck(%s)" % json.dumps(q)], lookup=lookup, tax=tax)
        if b:
            print("FAIL ordering", q, b); ok = False
    # excluded cards: not meant for constructed play. A flagged twin must never win a name that a real card has.
    flags = load("card_flags.json")
    ent = {e[0]: e for e in lookup["entries"]}
    inv = load("not_for_constructed_investigation.json")["name_collisions_with_an_unflagged_card_in_the_set"]
    for c in inv:
        fo = c["flagged"]["oracle_id"]
        reals = [y for y in c["other_entries"] if y["in_card_set"] and not y["flagged"]]
        if fo in flags["cards"] and flags["cards"][fo]:
            if ent[fo][3] != "o" or ent[fo][4][0] != flags["cards"][fo]:
                print("FAIL flagged twin is not a left-out entry with its reason:", c["flagged"]["name"]); ok = False
        for q in {c["flagged"]["name"]} | {y["name"] for y in reals}:
            r = dukpy.evaljs([src, JS_CTX, "AbilityFind.search(IDX, %s, 40)" % json.dumps(q)], lookup=lookup, tax=tax)
            first = r["matches"][0][0] if r["matches"] else None
            real_ids = {y["oracle_id"] for y in reals}
            if first is not None and ent[first][3] == "o" and any(m[3] != "o" for m in r["matches"]):
                print("FAIL a left-out entry ranks above a real card for %r" % q); ok = False
            if q in {y["name"] for y in reals} and first not in real_ids:
                print("FAIL the real card does not come first for %r" % q); ok = False
    print("name collisions checked:", len(inv), "(a left-out twin never ranks above a real card)")
    hc = dukpy.evaljs([src, JS_CTX, HAND_JS, "handCases(%s)" % json.dumps(["Lightning Bolt", "Armageddon", "Yargle"])], lookup=lookup, tax=tax)
    bad = []
    for r in hc:
        t = r["text"]
        if r["kind"] == "null" and t != r["base"]:
            bad.append("a null hand answer changed the text: " + r["card"])
        if r["kind"] != "null" and ("undefined" in t or "verified" in t.lower() or " checked placement" in t.replace("not a checked one", "")):
            bad.append("bad wording: " + t)
        if r["kind"] in ("fresh", "confirmed", "edit", "batchplace", "batchfallback", "batchconfirm") and not ("by hand" in t and "“" in t):
            bad.append("%s/%s does not say where and by hand: %s" % (r["card"], r["kind"], t))
        if r["kind"] in ("fresh", "batchplace", "batchfallback") and (r["rk"] != "hand" or "Placed by hand: in" not in t or ("no readable ability" if r["kind"] == "batchfallback" else "only in a held group") not in t):
            bad.append("fresh answer lacks the place or the original reason: " + t)
        if r["kind"] not in ("fresh", "null", "batchplace", "batchfallback") and not t.startswith(r["base"]):
            bad.append("%s/%s dropped the generated answer" % (r["card"], r["kind"]))
        if r["kind"] == "nofit" and "nothing fits" not in t:
            bad.append("nofit not stated")
        if r["kind"] == "removed" and "Removed by hand" not in t:
            bad.append("removal not stated")
        if r["kind"] == "batchplace" and not all(x in t for x in ("placed in a batch", "score 0.93", "sig + tag", "threshold 0.90", "Placed by hand: in")):
            bad.append("batch place wording: " + t)
        if r["kind"] == "batchfallback" and "from the low-confidence fallback list" not in t:
            bad.append("batch fallback wording: " + t)
        if r["kind"] == "batchconfirm" and "confirmed in a batch" not in t:
            bad.append("batch confirm wording: " + t)
        if r["kind"] == "batchreject" and ("rejected in a batch" not in t or "Removed by hand" not in t):
            bad.append("batch reject wording: " + t)
        if r["kind"] in ("edit", "fresh", "confirmed") and "in a batch" in t:
            bad.append("a single placement says it was in a batch: " + t)
    print("hand-placement answers: %d cases, %d problems" % (len(hc), len(bad)), bad[:5])
    for r in hc[:6]:
        print("   -", r["card"], "[%s]" % r["kind"], r["text"][:200])
    ok = ok and not bad
    for name in ("Boltfire", "Abbot of the Sacred Meeple", "Bolshack Dragon", "Dogsnail Engine", "Very Cryptic Command", "Red Herring", "Pick Your Poison",
                 "Fast // Furious", "Bind // Liberate", "Start // Finish"):
        r = dukpy.evaljs([src, JS_CTX, "lookupCard(%s)" % json.dumps(name)], lookup=lookup, tax=tax)
        print("\n== %s  (%d matches)" % (name, r["total"]))
        for a in r["answers"][:3]:
            print("   - %s [%s]: %s" % (a["name"], a["kind"], a["text"][:150]))
    for name in ("Mercurial Spelldancer", "Cactus Preserve", "Ignis Scientia", "Shield of Kaldra", "Gunk Slug"):
        r = dukpy.evaljs([src, JS_CTX, "lookupCard(%s)" % json.dumps(name)], lookup=lookup, tax=tax)
        print(chr(10) + "== gap card: %s  (%d matches)" % (name, r["total"]))
        for a_ in r["answers"][:2]:
            print("   - %s [%s]: %s" % (a_["name"], a_["kind"], a_["text"][:190]))
    for name in (sys.argv[1:] or NAMED):
        r = dukpy.evaljs([src, JS_CTX, "lookupCard(%s)" % json.dumps(name)], lookup=lookup, tax=tax)
        print("\n== %s  (%d matches)" % (name, r["total"]))
        for a in r["answers"][:4]:
            print("   - %s [%s]: %s" % (a["name"], a["kind"], a["text"]))
    print("\nALL CHECKS PASS" if ok else "\nSOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
