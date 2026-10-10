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
