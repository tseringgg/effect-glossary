#!/usr/bin/env python3
"""Per-ability "also fits" suggestions for cards in "Parsed, no close group found".

    python src/build_also_fits.py        # -> build/also_fits.json

DISPLAY ONLY. A card that scored 0.50-0.80 against its best leaf as a whole is very often a
two-effect card whose abilities each match a different existing leaf (see
reports/ability-placement-probe.md). This lists, per card, the individual abilities that match
a leaf closely, as SUGGESTIONS. It places nothing: the card stays in its "Not yet organized"
group, no leaf gains a member, no centroid, score, status or frozen file changes.

Scorer. Exactly the probe's (src/ability_probe.py): the clustering's own vocabulary, binary
presence x IDF, L2 normalisation and leaf centroids, with card_features()'s token rules applied
to ONE ability item, scored by cosine against every leaf.

Rules (approved):
  population  cards in the unplaced group (all are clean-parse) with a blended score >= 0.50
  skip        flagged cards (the condition-drop detector flags any of their items), modal spells
              (modes are separate ability items), and any individually flagged ability
  threshold   an ability must score >= 0.90 against a leaf
  specific    the ability has >= 3 tokens AND its best leaf has <= 300 cards. Generic matches
              (a single bare token such as eff:Draw / eff:Token / eff:Mana, or a leaf of 500+
              cards) and the in-between ones (2 tokens, or a 301-499 card leaf) are not shown;
              nor are abilities with no text to display (keyword-generated equip/cycling, Saga
              chapters whose text is only "Chapter N")
Partial, unmodelled and corrections-flagged cards never reach the unplaced group, so they are
skipped by construction.

Output is sorted and written with sorted keys: two runs give identical bytes.
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap  # noqa: E402

BUILD = ap.BUILD
MIN_BLENDED = 0.50
THRESHOLD = 0.90
MIN_TOKENS = 3
MAX_LEAF = 300
GENERIC_LEAF = 500
TEXT_LIMIT = 140


def is_modal(entry, items):
    return bool(entry.get("modal")) or bool(entry.get("mode_abilities")) or any(
        it.get("modal") or it.get("mode_abilities") for _, _, it, _ in items)


def main():
    sp = ap.Space()
    L = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    rec_chunk = P["recovered"]["chunk"]
    flagged_cards = set()
    flagged_items = collections.defaultdict(set)
    for h in ap.jl("condition_drops.json"):
        flagged_cards.add(h["oid"])
        flagged_items[h["oid"]].add((h["bucket"], h["idx"]))

    best = {}
    for x in P["review_queue"]:
        c = x["card"]
        if c not in best or x["similarity"] > best[c]["similarity"]:
            best[c] = x
    # the review queue's cards, not the ledger's "unplaced" reason: a card the ability layer has since
    # placed stays in this population (its remaining abilities keep their suggestions)
    pop = sorted(o for o in best if L[o]["status"] != "out_of_scope"
                 and L[o]["placement"]["method"] in ("unplaced", "ability"))
    assert len(pop) == 4175, len(pop)

    def entry_of(fid):
        return sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]

    stats = collections.Counter()
    cards = {}
    for oid in pop:
        x = best[oid]
        if x["similarity"] < MIN_BLENDED:
            stats["below_0.50"] += 1
            continue
        stats["in_population"] += 1
        if oid in flagged_cards:
            stats["skipped_flagged_card"] += 1
            continue
        e = entry_of(x["face"])
        items = ap.ability_items(e)
        if is_modal(e, items):
            stats["skipped_modal"] += 1
            continue
        toks = [[k for k in sorted(t) if k in sp.vocab] for *_, t in items]
        leaf, sc, _ = sp.score(toks)
        matches = []
        for k, (b, i, it, _) in enumerate(items):
            if not toks[k] or sc[k] < THRESHOLD:
                continue
            size = sp.leaf_size[int(leaf[k])]
            stats["abilities_at_0.90"] += 1
            if (b, i) in flagged_items.get(oid, ()):
                stats["skipped_flagged_ability"] += 1
                continue
            if len(toks[k]) == 1 or size >= GENERIC_LEAF:
                stats["skipped_generic"] += 1
                continue
            if len(toks[k]) < MIN_TOKENS or size > MAX_LEAF:
                stats["skipped_in_between"] += 1
                continue
            text = (it.get("description") or "").strip()
            if not text or re.fullmatch(r"Chapter \d+", text):
                # keyword-generated abilities (equip, cycling...) carry no text, and a Saga chapter's
                # text is only "Chapter N": nothing to show beside the link
                stats["skipped_no_text"] += 1
                continue
            matches.append({"b": b, "i": i, "t": text[:TEXT_LIMIT],
                            "l": int(leaf[k]), "s": round(float(sc[k]), 4)})
        if matches:
            cards[oid] = {"f": x["face"], "m": matches}
    stats["cards_with_also_fits"] = len(cards)
    stats["matches_shown"] = sum(len(c["m"]) for c in cards.values())
    stats["cards_with_2plus_matches"] = sum(1 for c in cards.values() if len(c["m"]) >= 2)
    doc = {"v": 1,
           "meta": {"rules": {"population": "unplaced 'Parsed, no close group found' with blended score >= %.2f" % MIN_BLENDED,
                              "threshold": THRESHOLD, "min_tokens": MIN_TOKENS, "max_leaf_cards": MAX_LEAF,
                              "generic": "1 token, or a leaf of >= %d cards" % GENERIC_LEAF},
                    "counts": dict(sorted(stats.items()))},
           "cards": dict(sorted(cards.items()))}
    with io.open(os.path.join(BUILD, "also_fits.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    print(json.dumps(doc["meta"], indent=1))


if __name__ == "__main__":
    main()
