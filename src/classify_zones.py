"""Deterministic zone labelling for the effect glossary.

Multi-label: every effect gets a SET of zones, possibly empty. An empty set is
a real answer -- a non-zone-touching effect -- not a failure to match.

No model, no embedding. Pure pattern matching, in the same spirit as
extract_effects.py: a closed, documented list of rules, each one auditable.

TWO TIERS, both of which count toward the final label:

  explicit  the zone's own name appears in the text ("graveyard", "the
            battlefield", "your library").

  entailed  a game action that, by the rules, cannot happen without that zone
            ("draw a card" is library -> hand; "destroy" is battlefield ->
            graveyard; "{T}: Add {G}" is battlefield -> mana pool).

Most oracle text never names the zone it operates on -- "Counter target spell"
never says "stack" -- so an explicit-only classifier would label the corpus
almost entirely zone-less. Every entailed rule is named and reported.

BATTLEFIELD SUB-TAGS. A flat "battlefield" tag was true of 28/34 effects and
partitioned nothing, so battlefield is refined into three sub-tags:

  battlefield:enters  an object arrives: ETB, "enter as a copy", "put onto the
                      battlefield", token creation (tokens are created on the
                      battlefield, CR 111.1).
  battlefield:leaves  an object departs: destroy, sacrifice, dies, exiled or
                      bounced FROM the battlefield. Co-occurs with the
                      destination zone's own tag (destroy -> also graveyard).
  battlefield:static  RESIDUAL: the text references an object on the
                      battlefield (a creature, a permanent, {T}, a static
                      keyword...) but describes neither entering nor leaving.
                      "Static" means static-REFERENCE, not CR static ability:
                      a one-shot "Target creature gets +3/+3" lands here.

The parent "battlefield" tag is kept and DERIVED: present iff any sub-tag is.
Because static is residual, an effect that both enters/leaves and separately
references a battlefield object gets only the enters/leaves tag -- a known
limit, acceptable while extraction keeps most chunks single-clause.

TEXT SEARCHED -- deliberately split policy:

  battlefield sub-tags   raw_text ONLY. A sub-tag that only plain_text would
                         produce is reported as a flag and NOT applied, because
                         plain_text-only matches were leaking hand-authoring
                         wording into labels.
  every other zone       raw_text AND plain_text, as before, so this refinement
                         changes nothing outside battlefield. A label whose
                         every hit comes from plain_text is still applied, but
                         flagged, so the policy question stays visible.
"""
import re

import glossary

# Canonical zone names, in report order.
ZONES = [
    "library", "hand", "battlefield", "graveyard",
    "exile", "stack", "command zone", "mana pool",
]

ENTERS = "battlefield:enters"
LEAVES = "battlefield:leaves"
STATIC = "battlefield:static"
BATTLEFIELD_SUBTAGS = [ENTERS, LEAVES, STATIC]

# Every label a zones list can contain, in display order.
ALL_TAGS = []
for _z in ZONES:
    ALL_TAGS.append(_z)
    if _z == "battlefield":
        ALL_TAGS.extend(BATTLEFIELD_SUBTAGS)

# Static keyword abilities that only function on the battlefield. Closed list.
# Matched only when the keyword OPENS the effect (exploded keyword lines).
STATIC_KEYWORDS = [
    "flying", "reach", "trample", "vigilance", "deathtouch", "lifelink",
    "first strike", "double strike", "haste", "hexproof", "indestructible",
    "menace", "defender", "shroud", "protection", "intimidate", "fear",
    "shadow", "horsemanship", "flanking", "skulk", "ward", "infect", "wither",
    r"\w+walk",
]
_STATIC_KEYWORD_RX = r"^(?:%s)(?=$|[\s({])" % "|".join(STATIC_KEYWORDS)

# Non-battlefield zones: zone -> [(tier, label, pattern)]. Unchanged.
RULES = {
    "library": [
        ("explicit", "library",        r"\blibrar(?:y|ies)\b"),
        ("entailed", "draw",           r"\bdraws?\b[^.]{0,20}\bcards?\b"),
        ("entailed", "shuffle",        r"\bshuffles?\b"),
        ("entailed", "mill",           r"\bmills?\b"),
        ("entailed", "top-of-deck",    r"\btop \w+(?: \w+)? cards?\b"),
    ],
    "hand": [
        ("explicit", "hand",           r"\bhands?\b"),
        ("entailed", "draw",           r"\bdraws?\b[^.]{0,20}\bcards?\b"),
        ("entailed", "discard",        r"\bdiscards?\b"),
    ],
    "graveyard": [
        ("explicit", "graveyard",      r"\bgraveyards?\b"),
        ("entailed", "destroy",        r"\bdestroys?\b|\bdestroyed\b"),
        ("entailed", "sacrifice",      r"\bsacrifices?\b"),
        ("entailed", "dies",           r"\bdies\b"),
        ("entailed", "discard",        r"\bdiscards?\b"),
        # CR 701.5a: a countered spell is put into its owner's graveyard.
        ("entailed", "countered-spell", r"\bcounters? target\b|\bcountered\b"),
    ],
    "exile": [
        ("explicit", "exile",          r"\bexil(?:e|es|ed|ing)\b"),
    ],
    "stack": [
        ("explicit", "stack",          r"\bstack\b"),
        ("entailed", "spell",          r"\bspells?\b"),
        ("entailed", "cast",           r"\bcasts?\b|\bcasting\b"),
        ("entailed", "resolve",        r"\bresolves?\b"),
        ("entailed", "counter-target", r"\bcounters? target\b"),
    ],
    "command zone": [
        ("explicit", "command zone",   r"\bcommand zone\b"),
        ("entailed", "commander",      r"\bcommanders?\b"),
        ("entailed", "emblem",         r"\bemblems?\b"),
    ],
    "mana pool": [
        ("explicit", "mana pool",      r"\bmana pool\b"),
        ("entailed", "add-mana",       r"\badd\b[^.]{0,60}\bmana\b|\badd \{"),
        ("entailed", "produce-mana",   r"\bproduces?\b[^.]{0,40}\bmana\b|\bto produce\b"),
        ("entailed", "tap-for-mana",   r"\btapp?e?d?\b[^.]{0,30}\bfor mana\b"),
    ],
}

_BF_OBJECT = (r"(?:creatures?|permanents?|artifacts?|enchantments?|planeswalkers?|lands?|tokens?)"
              r"\b(?! cards?\b)")

# Battlefield: sub-tag -> [(tier, label, pattern)]. STATIC rules are
# reference rules; they only yield the static tag when no ENTERS/LEAVES rule
# fired on the same text.
BATTLEFIELD_RULES = {
    ENTERS: [
        ("entailed", "enters",                r"\benters?\b"),
        ("explicit", "put-onto-battlefield",  r"\bput\b[^.]{0,60}\bonto the battlefield\b"),
        ("explicit", "return-to-battlefield", r"\breturns?\b[^.]{0,60}\bto the battlefield\b"),
        ("entailed", "create-token",          r"\bcreates?\b[^.]{0,40}\btokens?\b"),
    ],
    LEAVES: [
        ("entailed", "destroy",               r"\bdestroys?\b|\bdestroyed\b"),
        ("entailed", "sacrifice",             r"\bsacrifices?\b|\bsacrificed\b"),
        ("entailed", "dies",                  r"\bdies\b|\bdied\b"),
        ("explicit", "leaves-battlefield",    r"\bleaves? the battlefield\b|\bfrom the battlefield\b"),
        ("entailed", "exile-permanent",
         r"\bexile (?:target|each|all|another|that)\b[^.]{0,40}?\b" + _BF_OBJECT),
        # Bounce says "its owner's hand"; graveyard recursion says "your hand".
        ("entailed", "bounce",
         r"\breturns?\b[^.]{0,60}\bto (?:its|their) owners?['’]?s?['’]? hands?\b"),
    ],
    STATIC: [
        ("explicit", "battlefield",           r"\bbattlefield\b"),
        ("entailed", "in-play",               r"\bin play\b"),
        ("entailed", "permanent",             r"\bpermanents?\b"),
        ("entailed", "you-control",           r"\byou control\b|\byour control\b"),
        ("entailed", "creature",              r"\bcreatures?\b(?! (?:cards?|spells?)\b)"),
        ("entailed", "planeswalker",          r"\bplaneswalkers?\b"),
        ("entailed", "land",                  r"\blands?\b(?! cards?\b)"),
        ("entailed", "token",                 r"\btokens?\b"),
        ("entailed", "tap",                   r"\{T\}|\btaps?\b|\btapped\b"),
        ("entailed", "on-permanent-counters",
         r"\b(?:\+1/\+1|-1/-1|loyalty|charge) counters?\b|\bcounters? on\b"),
        ("entailed", "combat",
         r"\battacks?\b|\bblocks?\b|\bblock it\b|\battacking\b|\bblocking\b"),
        ("entailed", "static-keyword",        _STATIC_KEYWORD_RX),
        # CR 115.4: "any target" means a creature, player, planeswalker, or battle.
        ("entailed", "any-target",            r"\bany target\b"),
    ],
}


def _compile(rules):
    return [(tier, label, re.compile(pat, re.I)) for tier, label, pat in rules]


COMPILED = {z: _compile(r) for z, r in RULES.items()}
COMPILED_BF = {t: _compile(r) for t, r in BATTLEFIELD_RULES.items()}


def _battlefield_tags(text):
    """Sub-tags for ONE text field. Returns {subtag: [(tier, label), ...]}."""
    hits = {}
    for tag in (ENTERS, LEAVES):
        fired = [(t, l) for t, l, rx in COMPILED_BF[tag] if rx.search(text)]
        if fired:
            hits[tag] = fired
    if not hits:
        fired = [(t, l) for t, l, rx in COMPILED_BF[STATIC] if rx.search(text)]
        if fired:
            hits[STATIC] = fired
    return hits


def classify(raw_text, plain_text=""):
    """Return (zones, evidence, flags).

    zones     labels in ALL_TAGS order; may be empty.
    evidence  {tag: [(tier, label, field), ...]} for every APPLIED tag.
    flags     [(tag, applied, [(tier, label), ...])] -- tags supported only by
              plain_text. applied=False for battlefield sub-tags (raw-only
              policy); applied=True for other zones (policy unchanged).
    """
    raw_text = raw_text or ""
    plain_text = plain_text or ""
    evidence, flags = {}, []

    # Non-battlefield zones: raw + plain, attributed per field.
    for zone, rules in COMPILED.items():
        hits = []
        for tier, label, rx in rules:
            for field, text in (("raw", raw_text), ("plain", plain_text)):
                if text and rx.search(text):
                    hits.append((tier, label, field))
        if hits:
            evidence[zone] = hits
            if all(f == "plain" for _, _, f in hits):
                flags.append((zone, True, [(t, l) for t, l, _ in hits]))

    # Battlefield: raw decides; plain can only raise a flag.
    raw_bf = _battlefield_tags(raw_text)
    for tag, fired in raw_bf.items():
        evidence[tag] = [(t, l, "raw") for t, l in fired]
    if raw_bf:
        evidence["battlefield"] = [("derived", tag, "raw")
                                   for tag in BATTLEFIELD_SUBTAGS if tag in raw_bf]
    if plain_text:
        for tag, fired in _battlefield_tags(plain_text).items():
            if tag not in raw_bf:
                flags.append((tag, False, fired))

    zones = [t for t in ALL_TAGS if t in evidence]
    flags.sort(key=lambda f: ALL_TAGS.index(f[0]))
    return zones, evidence, flags


def classify_entry(entry):
    """Compute and attach entry['zones']. Returns (evidence, flags)."""
    zones, evidence, flags = classify(entry.get("raw_text", ""), entry.get("plain_text", ""))
    entry["zones"] = zones
    return evidence, flags


def top_level(zones):
    """The zones list with battlefield sub-tags dropped (the 8-zone view)."""
    return [z for z in zones if z in ZONES]


def main():
    entries = glossary.load_glossary()
    results = {e["effect_id"]: classify_entry(e) for e in entries}
    glossary.write_glossary(entries)

    for e in entries:
        evidence, flags = results[e["effect_id"]]
        zones = e["zones"]
        marks = []
        if len(top_level(zones)) >= 3:
            marks.append("3+ ZONES")
        if not zones:
            marks.append("ZERO ZONES")
        if flags:
            marks.append("PLAIN-ONLY FLAG")
        print("%s  [%s]%s" % (e["effect_id"], ", ".join(zones) or "-",
                              ("  <-- " + ", ".join(marks)) if marks else ""))
        print("    %s" % e["raw_text"].replace("\n", " ")[:110])
        for tag in zones:
            print("      %-19s %s" % (tag, ", ".join("%s:%s(%s)" % h for h in evidence[tag])))
        for tag, applied, fired in flags:
            print("      ! %-17s plain-only, %s: %s" % (
                tag, "APPLIED" if applied else "NOT applied",
                ", ".join("%s:%s" % f for f in fired)))
        print("")

    print("%d effects labelled. %d with 3+ top-level zones, %d with zero zones, "
          "%d with plain-only flags."
          % (len(entries),
             sum(1 for e in entries if len(top_level(e["zones"])) >= 3),
             sum(1 for e in entries if not e["zones"]),
             sum(1 for e in entries if results[e["effect_id"]][1])))
    for tag in ALL_TAGS:
        print("  %-20s %d" % (tag, sum(1 for e in entries if tag in e["zones"])))


if __name__ == "__main__":
    main()
