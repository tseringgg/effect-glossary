#!/usr/bin/env python3
"""The keyword facet: which in-scope cards carry which parsed keyword. A FILTER, not a placement. NEW FILE ONLY: build/keyword_facet.json.

    python src/build_keyword_facet.py        # seconds; reads build/chunks, build/placements.json (recovered cards), the lookup; optionally data/scryfall-oracle-cards.jsonl.gz for the comparison

Source: the `keywords` field of the parser's card records (faces merged to the oracle id, recovered cards included), for every in-scope card whatever its placement. Nothing here changes a status, a group, a count or any
of the six figures (73.3 / 83.1 / 89.5 / 92.3 / 92.8 / 96.0): a card keeps the placement it has, and the page shows that placement beside the keyword. The parser's keyword list is NARROWER than Scryfall's: it holds
keyword abilities only (172 names), while Scryfall's `keywords` also lists keyword actions and ability words (Mill, Scry, Landfall, ... 836 names on the same cards); the file records both counts.
KEYWORD_FACET = False writes nothing and removes this file.
"""
import collections
import glob
import gzip
import io
import json
import os
import re

KEYWORD_FACET = True
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(BUILD, "keyword_facet.json")
LABEL = "Keyword facet: a filter, not a placement. It lists cards that carry a keyword wherever they are placed; it changes no group and no figure."
NOTE = ("The parser's keyword list is narrower than Scryfall's: it holds keyword abilities only. Scryfall's list also includes keyword actions and ability words (Mill, Scry, Landfall, Fight, "
        "Investigate and so on), so a card can be a \"Landfall\" card on Scryfall and have no keyword here.")


def kname(x):
    return x if isinstance(x, str) else next(iter(x))


def display(n):
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", n)
    return s[:1].upper() + s[1:].lower()


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    if not KEYWORD_FACET:
        if os.path.exists(OUT):
            os.remove(OUT)
        print("KEYWORD_FACET is off: nothing written")
        return
    with io.open(os.path.join(BUILD, "ability_taxonomy_lookup.json"), encoding="utf-8") as fh:
        look = json.load(fh)["entries"]
    scope = {e[0] for e in look if e[3] != "o"}
    src = {}
    for p in sorted(glob.glob(os.path.join(BUILD, "chunks", "*.json"))):
        with io.open(p, encoding="utf-8") as fh:
            for k, c in json.load(fh).items():
                src[k] = c.get("keywords") or []
    with io.open(os.path.join(BUILD, "placements.json"), encoding="utf-8") as fh:
        for k, c in json.load(fh)["recovered"]["chunk"].items():
            src[k] = c.get("keywords") or []
    by = collections.defaultdict(set)
    seen = set()
    for k, kws in src.items():
        oid = k.split("/")[0]
        if oid in scope:
            seen.add(oid)
            for x in kws:
                by[kname(x)].add(oid)
    assert seen == scope, (len(seen), len(scope))
    sc = None
    p = os.path.join(HERE, "data", "scryfall-oracle-cards.jsonl.gz")
    if os.path.exists(p):
        names = set()
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            for line in fh:
                o = json.loads(line)
                if o["oracle_id"] in scope:
                    names.update(o.get("keywords") or [])
        sc = {"names": len(names), "not_in_parser_list": len({n for n in names if norm(n) not in {norm(k) for k in by}})}
    kws = {n: {"d": display(n), "n": len(s), "c": sorted(s)} for n, s in sorted(by.items())}
    doc = {"v": 1, "meta": {"enabled": True, "label": LABEL, "note": NOTE, "source": "the parsed `keywords` field of each card record (faces merged to the oracle id, recovered cards included)",
                            "in_scope_cards": len(scope), "parser_keywords": len(kws), "keywords_5_or_more_cards": sum(1 for v in kws.values() if v["n"] >= 5),
                            "cards_with_a_keyword": len(set().union(*by.values())), "scryfall_keywords": sc},
           "keywords": kws}
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    m = doc["meta"]
    print("keywords %d (>=5 cards: %d); cards with a keyword %d of %d; scryfall %s" % (m["parser_keywords"], m["keywords_5_or_more_cards"], m["cards_with_a_keyword"], m["in_scope_cards"], m["scryfall_keywords"]))


if __name__ == "__main__":
    main()
