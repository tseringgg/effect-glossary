"""Fetch the hand-picked card sample from Scryfall and cache it locally.

Sample is deliberately small (30 cards) and hand-picked into three clusters.
Every card is in the corpus for every query -- the "controls" of one cluster
act as distractors for the others.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, os.pardir, "data")
CARDS_PATH = os.path.join(DATA, "cards.json")

SCRYFALL_COLLECTION = "https://api.scryfall.com/cards/collection"

# (card_id, scryfall exact name, cluster, role)
#
# Widened from 17 to 30: each cluster now carries 6 target cards instead of
# 3/3/1, so a cluster verdict rests on a spread of cards rather than on one or
# two. Targets are deliberately varied in PHRASING, not just in count -- the
# board wipes include -X/-X and mass-damage wordings, and the clones include a
# token-copy wording, so the cluster cannot be won by matching a single stock
# sentence. Distractors and controls are unchanged plus one stronger competitor
# per cluster.
SAMPLE = [
    # --- Cluster A: mana dorks + plausible density-failure distractors ---
    ("llanowar_elves",     "Llanowar Elves",       "mana_dork", "target"),
    ("elvish_mystic",      "Elvish Mystic",        "mana_dork", "target"),
    ("birds_of_paradise",  "Birds of Paradise",    "mana_dork", "target"),
    ("fyndhorn_elves",     "Fyndhorn Elves",       "mana_dork", "target"),
    ("avacyns_pilgrim",    "Avacyn's Pilgrim",     "mana_dork", "target"),
    ("noble_hierarch",     "Noble Hierarch",       "mana_dork", "target"),
    ("nykthos",            "Nykthos, Shrine to Nyx", "mana_dork", "distractor"),
    ("chromatic_lantern",  "Chromatic Lantern",    "mana_dork", "distractor"),
    ("mana_reflection",    "Mana Reflection",      "mana_dork", "distractor"),
    ("gilded_lotus",       "Gilded Lotus",         "mana_dork", "distractor"),

    # --- Cluster B: board wipes + controls ---
    ("wrath_of_god",       "Wrath of God",         "board_wipe", "target"),
    ("damnation",          "Damnation",            "board_wipe", "target"),
    ("day_of_judgment",    "Day of Judgment",      "board_wipe", "target"),
    ("fumigate",           "Fumigate",             "board_wipe", "target"),
    ("toxic_deluge",       "Toxic Deluge",         "board_wipe", "target"),
    ("blasphemous_act",    "Blasphemous Act",      "board_wipe", "target"),
    ("doom_blade",         "Doom Blade",           "board_wipe", "distractor"),
    ("giant_growth",       "Giant Growth",         "board_wipe", "control"),
    ("counterspell",       "Counterspell",         "board_wipe", "control"),
    ("ponder",             "Ponder",               "board_wipe", "control"),

    # --- Cluster C: genuine clone vs token doubler + controls ---
    ("clone",              "Clone",                "clone", "target"),
    ("phantasmal_image",   "Phantasmal Image",     "clone", "target"),
    ("clever_impersonator", "Clever Impersonator", "clone", "target"),
    ("spark_double",       "Spark Double",         "clone", "target"),
    ("mirror_image",       "Mirror Image",         "clone", "target"),
    ("cackling_counterpart", "Cackling Counterpart", "clone", "target"),
    ("parallel_lives",     "Parallel Lives",       "clone", "distractor"),
    ("doubling_season",    "Doubling Season",      "clone", "distractor"),
    ("lightning_bolt",     "Lightning Bolt",       "clone", "control"),
    ("divination",         "Divination",           "clone", "control"),
]


def _post(url, payload):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Scryfall asks for an identifying UA.
            "User-Agent": "effect-glossary-experiment/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch():
    identifiers = [{"name": name} for _, name, _, _ in SAMPLE]
    got = {}
    # Scryfall collection endpoint takes max 75 identifiers; we have 30.
    data = _post(SCRYFALL_COLLECTION, {"identifiers": identifiers})
    for c in data.get("data", []):
        got[c["name"].lower()] = c
    missing = data.get("not_found", [])
    if missing:
        print("NOT FOUND on Scryfall: %r" % (missing,), file=sys.stderr)

    cards = []
    for cid, name, cluster, role in SAMPLE:
        c = got.get(name.lower())
        if c is None:
            raise SystemExit("Missing card from Scryfall response: %s" % name)
        cards.append({
            "card_id": cid,
            "name": c["name"],
            "mana_cost": c.get("mana_cost", "") or "",
            "type_line": c.get("type_line", "") or "",
            "oracle_text": c.get("oracle_text", "") or "",
            "cluster": cluster,
            "role": role,
            "scryfall_id": c.get("id"),
        })
    return cards


def main():
    cards = fetch()
    os.makedirs(DATA, exist_ok=True)
    with open(CARDS_PATH, "w", encoding="utf-8") as fh:
        json.dump(cards, fh, indent=2, ensure_ascii=False)
    print("wrote %d cards -> %s" % (len(cards), CARDS_PATH))


if __name__ == "__main__":
    main()
