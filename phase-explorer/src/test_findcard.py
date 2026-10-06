#!/usr/bin/env python3
"""Run reports/findcard.js (the file browse.html loads) against the real data files.

    python src/test_findcard.py

This executes the actual search and describe logic in a JavaScript engine (dukpy/Duktape,
ES5). It is NOT a render check: it proves the lookup and the plain-language answers, not how
the page draws them. Needs `pip install dukpy`.

Checks
  1. Reconciliation from the generated files: groups sum to the unplaced total and
     placed + unplaced + out of scope == universe.
  2. EVERY entry (all oracle ids, every face name) is found by an exact search of its own name.
  3. Twelve named real cards, one per state, each must return the expected kind.
  4. Ordering: in a result list no out-of-scope entry precedes a real card.
  5. Diacritic and punctuation folding (accented and slashed names).
"""
import io
import json
import os
import sys

import dukpy

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")


def load(name):
    return json.load(io.open(os.path.join(BUILD, name), encoding="utf-8"))


JS_CTX = r"""
var LOOKUP = dukpy.lookup, UNORG = dukpy.unorg, BR = dukpy.br, KW = dukpy.kw, SGL = dukpy.sgl, CLU = dukpy.clu, PHR = dukpy.phr;
var IDX = FindCard.build(LOOKUP);
function leafLabel(l) {
  var e = PHR.leaves[String(l)];
  var p = e && e.phrases && e.phrases.length ? e.phrases[0].phrase : "";
  return p || (CLU.labels[String(l)] || "").slice(0, 70);
}
var CTX = {
  leafLabel: leafLabel,
  leafBranches: function (l) { return BR.leaf_branches[String(l)] || []; },
  kwLeaf: function (id) { return KW.leaves[id]; },
  sgLeaf: function (id) { return SGL.leaves[id]; },
  sgBlock: SGL.meta.block,
  group: function (id) { var g = UNORG.groups, i; for (i = 0; i < g.length; i++) if (g[i].id === id) return g[i]; },
  words: UNORG.strength_words
};
function lookupCard(name) {
  var r = FindCard.search(IDX, name, 40), i, out = [];
  for (i = 0; i < r.matches.length; i++) out.push(FindCard.describe(IDX, r.matches[i], CTX));
  return { total: r.total, answers: out };
}
"""


def main():
    ledger = load("ledger.json")
    R = ledger["rows"]
    unorg = load("unorganized.json")
    lookup = load("lookup.json")
    cards = load("unorganized_cards.json")["groups"]
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("PASS  " if cond else "FAIL  ") + msg)
        ok = ok and cond

    # 1. reconciliation, from the generated files
    t = unorg["totals"]
    check(sum(g["cards"] for g in unorg["groups"]) == t["not_yet_organized"] ==
          sum(len(v) for v in cards.values()),
          "group totals %s == unplaced in scope %d == cards listed in the lazy file" %
          ("+".join(str(g["cards"]) for g in unorg["groups"]), t["not_yet_organized"]))
    check(t["organized"] + t["not_yet_organized"] + t["not_cards"] == t["universe"] == len(R) ==
          len(lookup["entries"]),
          "placed %d + not yet organized %d + not cards %d == universe %d == lookup entries %d" %
          (t["organized"], t["not_yet_organized"], t["not_cards"], t["universe"], len(lookup["entries"])))
    check(t["organized"] + t["not_yet_organized"] == t["in_scope"], "organized + unorganized == in-scope %d" % t["in_scope"])

    js = dukpy.JSInterpreter()
    with io.open(os.path.join(HERE, "reports", "findcard.js"), encoding="utf-8") as fh:
        js.evaljs(fh.read())
    js.evaljs(JS_CTX, lookup=lookup, unorg=unorg, br=load("branches.json"), kw=load("keyword_layer.json"), sgl=load("signature_layer.json"),
              clu={"labels": load("clusters.json")["labels"]}, phr=load("leaf_phrases.json"))

    # 2. every card is findable by its own name (every face name too)
    bad = js.evaljs("""
      var bad = [], E = LOOKUP.entries, i, j, names, hit, k;
      for (i = 0; i < E.length; i++) {
        names = [E[i][1]].concat(E[i][2]);
        for (j = 0; j < names.length; j++) {
          hit = FindCard.exact(IDX, names[j]); var found = false;
          for (k = 0; k < hit.length; k++) if (hit[k][0] === E[i][0]) found = true;
          if (!found) bad.push(E[i][0] + " " + names[j]);
        }
      }
      bad;""")
    n_names = sum(1 + len(e[2]) for e in lookup["entries"])
    check(not bad, "exact search finds all %d oracle ids by all %d face names (misses: %d %s)" %
          (len(lookup["entries"]), n_names, len(bad), list(bad)[:3]))

    # 3. twelve real cards, one per state
    want = [
        ("Murder", "grouped", None),
        ("Shuri, Wakandan Inventor", "grouped", None),
        ("Serra Angel", "keyword", None),
        ("Storm Crow", "keyword", None),
        ("Hulk, Bruce Banner", "keyword", "new"),
        ("Grizzly Bears", "norules", None),
        ("Nissa, Worldsoul Speaker", "unorganized", 1),
        ("Guul Draz Vampire", "unorganized", 1),
        ("Ravnica at War", "unorganized", 2),
        ("Comeuppance", "signature", None),
        ("Scavenger Hunt", "unorganized", "recovered"),
        ("Yargle, Goliath of Otaria", "norules", None),
        ("Fog Bank", "signature", None),
        ("Hardened Scales", "signature", None),
        ("Jeska, Thrice Reborn", "unorganized", 1),
        ("Glen Elendra's Answer", "grouped", None),
        ("Fire Covenant", "unorganized", 5),
        ("Arcbound Wanderer", "unorganized", 4),
        ("The Great Aerie", "notcard", None),
        ("Tyranid", "notcard", None),
    ]
    # a proximity card: take a real one from the ledger (no hand-picking bias)
    prox = sorted(r["name"] for r in R.values() if r["placement"]["method"] == "proximity"
                  and r["status"] == "noise" and not r["name"].startswith("A-"))[0]
    want.append((prox, "nearby", None))
    n_ab = sum(1 for e in lookup["entries"] if e[3] == "a")
    n_layer = len(load("ability_layer.json")["cards"]) + len(load("partial_ability_layer.json")["cards"])
    check(n_ab == n_layer == sum(1 for r in R.values() if r["placement"]["method"] == "ability") > 0,
          "ability-placed cards: lookup %d == layer %d == ledger" % (n_ab, n_layer))
    print()
    for name, kind, extra in want:
        res = js.evaljs("lookupCard(dukpy.n)", n=name)
        named = [a for a in res["answers"] if a["name"].lower() == name.lower()
                 or name.lower() in [o.lower() for o in a["others"]]]

        def fits(a):
            if a["kind"] != kind:
                return False
            if extra == "new":
                return a["isNew"]
            if extra == "recovered":
                return a["recovered"] and a["group"] == 1
            return extra is None or a["group"] == extra
        a = next((x for x in named if fits(x)), named[0] if named else None)
        good = bool(a) and fits(a)
        check(good, "%-28s -> %-11s %s" % (name, a["kind"] if a else "NOT FOUND",
                                           (a["text"][:150] if a else "")))
    print()

    # 4. ordering: no out-of-scope entry before a real card, for several queries
    order_ok = True
    for q in ("brightglass gearhulk", "elemental", "spirit", "treasure", "gearhulk"):
        res = js.evaljs("lookupCard(dukpy.n)", n=q)
        kinds = [a["kind"] == "notcard" for a in res["answers"]]
        if True in kinds and any(not k for k in kinds[kinds.index(True):]):
            order_ok = False
        print("      %-22s %3d match(es): %s" % (q, res["total"], "".join("o" if k else "C" for k in kinds)))
    check(order_ok, "real cards are always listed before out-of-scope matches")

    # 5. folding
    folds = [("dunedain", "Dúnedain"), ("aether", "Æther"), ("jotun", "Jötun")]
    names = {e[1] for e in lookup["entries"]} | {n for e in lookup["entries"] for n in e[2]}
    for q, sample in folds:
        present = [n for n in names if q in js.evaljs("IDX.norm(dukpy.n)", n=n)] if False else None
    ascii_q = js.evaljs("""[IDX.norm("Brándis // Thör"), IDX.norm("  Fire // Ice  "), IDX.norm("Æther Flash")];""")
    check(ascii_q == ["brandis thor", "fire ice", "aether flash"], "normalisation folds accents and '//': %s" % ascii_q)
    accented = sorted(n for n in names if any(ord(c) > 127 for c in n))[:3]
    for n in accented:
        folded = js.evaljs("IDX.norm(dukpy.n)", n=n)
        res = js.evaljs("lookupCard(dukpy.n)", n=folded)
        check(any(a["name"] == n or n in a["others"] for a in res["answers"]),
              "typing the folded form %r finds %r" % (folded, n))

    print("\nOVERALL:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
