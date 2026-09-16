"""Build / load the effect glossary (data/effects.yaml).

Dedup is by EXACT string match on normalized raw_text:
  - lowercased
  - whitespace collapsed
  - mana symbols normalized ({t} -> {T}) so casing inside braces never splits
    two otherwise-identical effects.

effect_id is a hash of the normalized text, so it is stable across rebuilds
and across corpus reordering -- hand-authored plain_text stays attached to the
right entry.

Each entry also carries `zones`: the list of MTG zones the effect touches,
computed deterministically by classify_zones.py. It is DERIVED, not authored --
recomputed on every build, never preserved across rebuilds the way plain_text
is. An empty list means "touches no zone", which is a real answer.
"""
import hashlib
import json
import os
import re

import yaml

from extract_effects import extract_effects

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, os.pardir, "data")
CARDS_PATH = os.path.join(DATA, "cards.json")
GLOSSARY_PATH = os.path.join(DATA, "effects.yaml")

_MANA = re.compile(r"\{([^}]*)\}")


def normalize(text):
    t = _MANA.sub(lambda m: "{" + m.group(1).upper() + "}", text)
    t = t.lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def effect_id(normalized):
    return "eff_" + hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]


def load_cards():
    with open(CARDS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def build(cards):
    """Return an ordered list of glossary entries with empty plain_text."""
    entries = {}
    order = []
    for card in cards:
        for chunk in extract_effects(card["oracle_text"]):
            norm = normalize(chunk)
            eid = effect_id(norm)
            if eid not in entries:
                entries[eid] = {
                    "effect_id": eid,
                    "raw_text": chunk,
                    "plain_text": "",
                    "occurrence_count": 0,
                    "card_ids": [],
                    "zones": [],
                }
                order.append(eid)
            e = entries[eid]
            if card["card_id"] not in e["card_ids"]:
                e["card_ids"].append(card["card_id"])
                e["occurrence_count"] = len(e["card_ids"])
    return [entries[e] for e in order]


def load_glossary(path=GLOSSARY_PATH):
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    return doc.get("effects", [])


def write_glossary(entries, path=GLOSSARY_PATH):
    """Write YAML, preserving any plain_text already authored in the file."""
    existing = {}
    if os.path.exists(path):
        for e in load_glossary(path):
            if e.get("plain_text"):
                existing[e["effect_id"]] = e["plain_text"]
    for e in entries:
        if not e.get("plain_text") and e["effect_id"] in existing:
            e["plain_text"] = existing[e["effect_id"]]

    # zones is COMPUTED, never hand-edited: recomputed on every write so the
    # label can never drift from the rules in classify_zones.py. It runs AFTER
    # the plain_text merge above, because the classifier reads plain_text too
    # -- classifying a freshly built entry whose plain_text is still empty
    # would silently produce a thinner label. Imported here rather than at
    # module scope because classify_zones imports this module.
    import classify_zones
    for e in entries:
        classify_zones.classify_entry(e)

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Effect glossary -- deduplicated by normalized raw_text.\n")
        fh.write("# plain_text is HAND-AUTHORED. Empty plain_text => effect is\n")
        fh.write("# NOT indexed and its card is unreachable by search (by design).\n")
        fh.write("# zones is COMPUTED by classify_zones.py -- do not hand-edit.\n")
        yaml.safe_dump(
            {"effects": entries}, fh,
            sort_keys=False, allow_unicode=True, default_flow_style=False, width=100,
        )
    return path


def main():
    cards = load_cards()
    entries = build(cards)
    path = write_glossary(entries)
    authored = sum(1 for e in entries if e.get("plain_text"))
    print("%d unique effects across %d cards (%d authored) -> %s"
          % (len(entries), len(cards), authored, path))


if __name__ == "__main__":
    main()
