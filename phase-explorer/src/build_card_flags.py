#!/usr/bin/env python3
"""Mark the cards that are not meant for constructed play. Reads local files only (no network); changes nothing else.

    python src/build_card_flags.py     # -> build/card_flags.json

Reads   build/ledger.json                       the card set (oracle ids)
        data/scryfall-default-cards.jsonl.gz    every printing of every card
        data/scryfall-sets.json                 set names (for the playtest sets)
Writes  build/card_flags.json    {"cards": {oracle id: reason}, "reasons": {reason: wording}, "rule": ...}

The rule: a card is flagged only if EVERY printing of it is one of
    silver border              border_color is silver (Unglued, Unhinged, Unstable, ...)
    acorn stamp                security_stamp is acorn (Unfinity: not tournament legal)
    playtest card              promo_types contains "playtest" (the Mystery Booster 2 test cards, whose images read "TEST CARD - not for
                               constructed play", and a few promo test cards); Scryfall files the set itself as an ordinary one
    joke / test set            the set type is "funny" (the Un-sets, Unknown Event, Mystery Booster playtest cards, ...)
    memorabilia                the set type is "memorabilia" (collector items)
A card that is also printed in an ordinary set (Counterspell, Daze, ...) is a normal card and is never flagged.
Legality exception: a card that is legal (or restricted, or banned) in at least one format is never flagged. Unfinity's non-acorn cards sit in a
"funny" set but are legal in Commander and the eternal formats, so they ARE meant for constructed play (170 cards found in the Part 1a hand check).
Each flagged card stores its evidence (sets, borders, stamps, promo tags, legal-format count) next to its reason code.
The reason shown is the first that applies in the order above. The browse page hides flagged cards by default, behind one switch.
"""
import collections
import gzip
import io
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
DATA = os.path.join(HERE, "data")
REASONS = {"silver_border": "silver-border", "acorn_stamp": "acorn-stamped", "playtest_card": "playtest card", "joke_or_test_set": "joke or test set", "memorabilia": "memorabilia"}
PLAYTEST = ("cmb1", "cmb2")


def printing_kind(o):
    if o.get("border_color") == "silver":
        return "silver_border"
    if o.get("security_stamp") == "acorn":
        return "acorn_stamp"
    if "playtest" in (o.get("promo_types") or []):
        return "playtest_card"
    if o.get("set_type") == "funny":
        return "joke_or_test_set"
    if o.get("set_type") == "memorabilia":
        return "memorabilia"
    return None


def main():
    ledger = json.load(io.open(os.path.join(BUILD, "ledger.json"), encoding="utf-8"))["rows"]
    ours = set(ledger)
    legal_in = {}
    with gzip.open(os.path.join(DATA, "scryfall-oracle-cards.jsonl.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            legal_in[o["oracle_id"]] = sum(1 for v in o["legalities"].values() if v != "not_legal")
    kinds = collections.defaultdict(list)
    evid = collections.defaultdict(lambda: {"sets": set(), "borders": set(), "stamps": set(), "promo_types": set()})
    with gzip.open(os.path.join(DATA, "scryfall-default-cards.jsonl.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            oid = o.get("oracle_id")
            if oid in ours:
                kinds[oid].append(printing_kind(o))
                e = evid[oid]
                e["sets"].add(o["set"] + ":" + o["set_type"])
                e["borders"].add(o.get("border_color") or "")
                e["stamps"].add(o.get("security_stamp") or "-")
                e["promo_types"].update(o.get("promo_types") or [])
    cards, evidence, exempt = {}, {}, 0
    for oid, ks in kinds.items():
        if ks and all(ks):
            if legal_in.get(oid, 0) > 0:
                exempt += 1                                  # legal somewhere: meant for constructed play
                continue
            for r in REASONS:                     # first reason, in the order of REASONS
                if r in ks:
                    cards[oid] = r
                    e = evid[oid]
                    evidence[oid] = {"name": ledger[oid]["name"], "in_card_set": ledger[oid]["status"] != "out_of_scope" and not ledger[oid]["name"].startswith("A-"),
                                     "sets": sorted(e["sets"])[:12], "borders": sorted(e["borders"]), "stamps": sorted(e["stamps"]),
                                     "promo_types": sorted(e["promo_types"])[:6], "legal_formats": 0}
                    break
    out = {"v": 2, "rule": "flagged only if every printing is a silver-border, acorn-stamped, playtest-tagged, joke or test set (set type funny) or memorabilia printing, "
                           "and the card is legal in no format",
           "reasons": REASONS, "legal_in_some_format_so_not_flagged": exempt, "cards": dict(sorted(cards.items())), "evidence": dict(sorted(evidence.items()))}
    with io.open(os.path.join(BUILD, "card_flags.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=0, sort_keys=True))
    print("flagged", len(cards), "of", len(kinds), "cards with printings;", dict(collections.Counter(cards.values())), "| exempt (legal somewhere):", exempt)


if __name__ == "__main__":
    main()
