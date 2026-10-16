#!/usr/bin/env python3
"""Tests for the keyword facet (build/keyword_facet.json, src/build_keyword_facet.py).

    python src/test_keyword_facet.py

An independent recount from the parser's own records (build/chunks and the recovered cards), not from the facet's code path; the label and the Scryfall note; Mutate; that the facet is only a filter (it
imports nothing that places, writes one file, and the generated layers are byte-identical around a build); the flag; two identical builds.
"""
import collections
import glob
import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(HERE, "build")
FAILS = []


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" - " + str(detail)) if detail else ""))
    if not ok:
        FAILS.append(name)


def jl(n):
    return json.load(io.open(os.path.join(B, n), encoding="utf-8"))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run(code):
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); " + code], cwd=HERE, capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1"))
    return r.stdout + r.stderr


def main():
    F = jl("keyword_facet.json")
    m, K = F["meta"], F["keywords"]
    scope = {e[0] for e in jl("ability_taxonomy_lookup.json")["entries"] if e[3] != "o"}
    src = {}
    for p in glob.glob(os.path.join(B, "chunks", "*.json")):
        for k, c in json.load(io.open(p, encoding="utf-8")).items():
            src[k] = c.get("keywords") or []
    for k, c in jl("placements.json")["recovered"]["chunk"].items():
        src[k] = c.get("keywords") or []
    want = collections.defaultdict(set)
    for k, kws in src.items():
        oid = k.split("/")[0]
        if oid in scope:
            for x in kws:
                want[x if isinstance(x, str) else list(x)[0]].add(oid)
    check("every keyword and every card list equals an independent recount from the parser records", {n: set(v["c"]) for n, v in K.items()} == dict(want), (len(K), len(want)))
    check("counts: 172 keywords, 167 with 5 or more cards, 12,906 cards with a keyword", (m["parser_keywords"], m["keywords_5_or_more_cards"], m["cards_with_a_keyword"]) == (172, 167, 12906), m)
    check("each count n equals the length of its card list", all(v["n"] == len(v["c"]) for v in K.values()))
    check("only in-scope cards are listed (no token, art card or excluded card)", all(o in scope for v in K.values() for o in v["c"]))
    check("Mutate is in the parser's keyword list with 34 cards", "Mutate" in K and K["Mutate"]["n"] == 34, K.get("Mutate", {}).get("n"))
    check("a card with several keywords is listed under each (Flying and Trample overlap)", len(set(K["Flying"]["c"]) & set(K["Trample"]["c"])) > 100)
    check("the label says it is a filter, not a placement", "filter, not a placement" in m["label"] and "changes no group and no figure" in m["label"])
    check("the file says the parser's keyword list is narrower than Scryfall's, with both counts", "narrower than Scryfall" in m["note"] and m["scryfall_keywords"] and m["scryfall_keywords"]["names"] > m["parser_keywords"],
          (m["parser_keywords"], m["scryfall_keywords"]))
    check("the facet carries no placement field (cards only)", all(set(v) == {"d", "n", "c"} for v in K.values()))
    code = open(os.path.join(HERE, "src", "build_keyword_facet.py"), encoding="utf-8").read()
    check("the builder writes exactly one file and imports no placement code", code.count("io.open(OUT") == 1 and not any(w in code for w in ("import build_", "manual_common", "tentative_placements")), "")
    page = open(os.path.join(HERE, "reports", "browse.html"), encoding="utf-8").read()
    check("the page labels the list and the filter 'a filter, not a placement'", page.count("filter, not a placement") >= 3 and "cf-kw" in page and "By keyword" in page)
    guard = ["build/ability_taxonomy.json", "build/ability_taxonomy_lookup.json", "build/tentative_placements.json", "build/annotation_placements.json", "build/tag_placements.json", "build/loose_groups.json"]
    before = {g: sha(os.path.join(HERE, g)) for g in guard}
    h1 = sha(os.path.join(B, "keyword_facet.json"))
    run("import build_keyword_facet as K; K.main()")
    h2 = sha(os.path.join(B, "keyword_facet.json"))
    check("two builds in a row are byte-identical", h1 == h2)
    check("the six-figure layers are byte-identical around a facet build", all(sha(os.path.join(HERE, g)) == before[g] for g in guard))
    out = run("import build_keyword_facet as K; K.KEYWORD_FACET = False; K.main()")
    gone = not os.path.exists(os.path.join(B, "keyword_facet.json"))
    check("flag off: nothing written and the file is removed", gone, out.strip()[-60:])
    run("import build_keyword_facet as K; K.main()")
    check("flag on again: the identical file comes back", sha(os.path.join(B, "keyword_facet.json")) == h1 and all(sha(os.path.join(HERE, g)) == before[g] for g in guard))
    print("\n%d failure(s)" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
