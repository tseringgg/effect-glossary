#!/usr/bin/env python3
"""Card -> colour identity for the tester site's colour filter (feature COLOUR_IDENTITY in reports/config.js): build/colour_identity/cards.json.

    python src/build_colour_identity.py [--check]

Deterministic (sorted keys, no timestamps; an unchanged file is not rewritten). --check re-derives the file and compares it with the one on disk.
Reads data/scryfall-oracle-cards.jsonl.gz (Scryfall's own color_identity, matched on the oracle id) and build/ability_taxonomy_cards.json (the card list and card colour); writes only
build/colour_identity/cards.json. Nothing under corrections/ or archive/ is opened. A FILTER, never a placement: no group, id, placement, suggestion or figure changes.

  {"v":1, "sig": checksum of the card ids, "i": one character per card in the order of ability_taxonomy_cards.json, "fb": [card index, ...]}
  character = one of 0-9a-v: the identity as a 5-bit mask, bit 0 = W, 1 = U, 2 = B, 3 = R, 4 = G
  fb        the cards Scryfall's file does not have (the newest ones): their character is the CARD colour (build/ability_taxonomy_cards.json "col"), so on them identity = card colour
"""
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(BUILD, "colour_identity", "cards.json")
SRC = os.path.join(HERE, "data", "scryfall-oracle-cards.jsonl.gz")
W = "WUBRG"
A32 = "0123456789abcdefghijklmnopqrstuv"


def fnv(items):                                              # the same checksum as src/build_buckets.py and the page
    h = 2166136261
    for i, s in enumerate(items):
        if i:
            h = ((h ^ 10) * 16777619) & 0xFFFFFFFF
        for ch in s:
            h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return "%08x" % h


def mask(letters):
    return sum(1 << W.index(c) for c in letters)


def build():
    with open(os.path.join(BUILD, "ability_taxonomy_cards.json"), encoding="utf-8") as fh:
        cards = json.load(fh)["cards"]
    ident = {}
    with gzip.open(SRC, "rt", encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            ident[d["oracle_id"]] = d["color_identity"]
    chars, fb, names = [], [], []
    for i, (oid, c) in enumerate(cards.items()):
        ci = ident.get(oid)
        if ci is None:
            fb.append(i); names.append(c["n"])
            ci = c.get("col") or ""
        chars.append(A32[mask(ci)])
    doc = {"v": 1, "sig": fnv(list(cards)), "i": "".join(chars), "fb": fb}
    return doc, names


def dumps(doc):
    return (json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def write():
    doc, names = build()
    data = dumps(doc)
    if not os.path.exists(OUT) or open(OUT, "rb").read() != data:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "wb") as fh:
            fh.write(data)
    return data, names


def main():
    if "--check" in sys.argv:
        doc, names = build()
        ok = os.path.exists(OUT) and open(OUT, "rb").read() == dumps(doc)
        print("colour_identity/cards.json %s" % ("up to date" if ok else "differs"))
        sys.exit(0 if ok else 1)
    data, names = write()
    print("wrote build/colour_identity/cards.json: %s bytes; %d cards use their card colour (not in Scryfall's file): %s" % (format(len(data), ","), len(names), "; ".join(names)))


if __name__ == "__main__":
    main()
