"""Hand-authored plain_text for the effects needed by the three cluster queries.

AUTHORING DISCIPLINE (important for the validity of this experiment):
  * plain_text is a faithful plain-language restatement of what the effect
    does, in the vocabulary a player would use.
  * The literal query strings ("mana dork", "board wipe", "clone effect") are
    deliberately NEVER written into any plain_text. Planting the query in the
    document would guarantee a win by string echo and would tell us nothing
    about whether effect-level splitting fixes the density problem.
  * Distractors are authored just as carefully as targets. If only the
    "right answers" were indexed, effect-level search would win trivially.

Deliberately left UNAUTHORED (=> excluded from the index, => their cards are
unreachable by any search, by design):
  * Ponder's two effects
  * Divination's "Draw two cards."
Both are controls that are irrelevant to all three cluster queries, so leaving
them out does not remove a real competitor -- it demonstrates the no-fallback
rule with cards that were never contenders.

This script only fills entries whose plain_text is empty, so later hand edits
to data/effects.yaml stick. Use --force to overwrite.
"""
import sys

import glossary

AUTHORED = {
    # --- mana production ---
    "eff_3b48c12159": "Tap this permanent to produce one green mana.",
    "eff_b711c42e82": "Tap this permanent to produce one mana of whatever color you need.",
    "eff_7d99ccfccd": "Tap this permanent to produce one colorless mana.",
    "eff_84a90976db": (
        "Pay two generic mana and tap this permanent to produce a large burst of mana in a "
        "single color, as much as your devotion to that color."
    ),
    "eff_98db4267ea": (
        "Every land you control gains the ability to tap for one mana of any color."
    ),
    "eff_086b340da2": (
        "Whenever you tap a permanent for mana, it produces double the mana instead."
    ),

    # --- keyword ability, extracted separately from the ability text beside it ---
    "eff_0974abfe45": (
        "This creature has flying, so only creatures with flying or reach can block it."
    ),

    # --- mass removal ---
    "eff_938d0cc426": (
        "Destroy every creature on the battlefield at once. None of them can be regenerated."
    ),
    "eff_f9b49aade0": "Destroy every creature on the battlefield at once.",

    # --- copying vs doubling ---
    "eff_ed25a537f6": (
        "This creature can enter the battlefield as a copy of any creature already in play."
    ),
    "eff_71a59f59ae": (
        "Whenever you would create tokens, you create twice as many of them instead."
    ),
    "eff_e824a91695": (
        "Whenever you would put counters on a permanent you control, it gets twice as many "
        "counters instead."
    ),

    # --- controls, authored so they are real competitors in the index ---
    "eff_d34b58ccf5": "Give a single creature +3/+3 until the turn ends.",
    "eff_0c8995549c": "Counter a spell being cast so that it never resolves.",
    "eff_87a7b6018c": "Deal 3 damage to any creature, player, or planeswalker.",

    # ======================================================================
    # WIDENING PASS: 17 -> 30 cards. 13 new cards introduced 16 new effects;
    # Fyndhorn Elves introduced none, reusing "{T}: Add {G}." outright.
    # Same discipline as above: no query string and no card name is ever
    # written into a plain_text, and distractors get the same care as targets.
    # ======================================================================

    # --- mana production ---
    "eff_924b2ac0c1": "Tap this permanent to produce one white mana.",
    "eff_6ba24fb6df": "Tap this permanent to produce one green, white, or blue mana.",
    "eff_a92ad0b096": (
        "Tap this permanent to produce three mana, all of a single color of your choice."
    ),

    # --- mass removal, in three different wordings ---
    "eff_1f152043dd": (
        "Destroy every creature on the battlefield at once, and gain 1 life for each one "
        "destroyed."
    ),
    "eff_afb5679e1b": (
        "Give every creature on the battlefield the same amount of -X/-X until end of turn, "
        "which destroys any whose toughness drops to zero."
    ),
    "eff_c262b3de4a": "Deal 13 damage to every creature on the battlefield at once.",
    "eff_c25866cdeb": "Pay any amount of life as an extra cost when you cast this spell.",
    "eff_974a6041c8": (
        "This spell costs one less generic mana to cast for each creature on the battlefield, "
        "so it gets cheaper as the board fills up."
    ),

    # --- single-target removal, the board-wipe cluster's strong competitor ---
    "eff_71e819d2d6": "Destroy a single creature of your choice, as long as it is not black.",

    # --- copying, in five different wordings ---
    "eff_676d325a65": (
        "This creature can enter the battlefield as a copy of any creature already in play, "
        "except it is also an Illusion and it is sacrificed as soon as it becomes the target "
        "of a spell or ability."
    ),
    "eff_b2839b45b6": (
        "This creature can enter the battlefield as a copy of any nonland permanent already "
        "in play."
    ),
    "eff_5c74bbe0be": (
        "This creature can enter the battlefield as a copy of a creature or planeswalker you "
        "already control, arriving with one extra counter on it and never legendary."
    ),
    "eff_0edb5a1fd9": (
        "This creature can enter the battlefield as a copy of a creature you already control."
    ),
    "eff_d9e646fb5c": "Create a token that is a copy of a creature you already control.",

    # --- keyword abilities, extracted separately from the text beside them ---
    "eff_a836b0d4b1": (
        "This creature has exalted, so whenever a creature you control attacks by itself, "
        "that creature gets +1/+1 until end of turn."
    ),
    "eff_04f790315a": (
        "This card has flashback, so you may cast it once from your graveyard for its "
        "flashback cost and then it is exiled."
    ),
}


def main(force=False):
    entries = glossary.load_glossary()
    known = {e["effect_id"] for e in entries}
    unknown = set(AUTHORED) - known
    if unknown:
        raise SystemExit("authored ids not in glossary (rebuild drift?): %s" % sorted(unknown))

    filled = 0
    for e in entries:
        pt = AUTHORED.get(e["effect_id"])
        if pt and (force or not e.get("plain_text")):
            e["plain_text"] = pt
            filled += 1

    glossary.write_glossary(entries)
    authored = sum(1 for e in entries if e.get("plain_text"))
    print("filled %d; %d/%d entries authored, %d intentionally unauthored"
          % (filled, authored, len(entries), len(entries) - authored))
    for e in entries:
        if not e.get("plain_text"):
            print("  UNAUTHORED %s %r cards=%s"
                  % (e["effect_id"], e["raw_text"][:60], e["card_ids"]))


if __name__ == "__main__":
    main(force="--force" in sys.argv)
