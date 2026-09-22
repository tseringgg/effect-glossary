"""Deterministic zone labelling for the effect glossary.

Every effect gets a SET of structured zone records, possibly empty:

    {"zone": "library", "direction": "source", "choice": False}

An empty list is a real answer -- a non-zone-touching effect -- not a failure.
No model, no embedding: a closed, documented list of rules, each auditable.

DIRECTION -- what the effect does to that zone:
    source       cards/objects come FROM the zone (draw, mill, "from your
                 graveyard", countering a spell off the stack)
    destination  cards/objects go TO it (discard, destroy, exile, "add {G}")
    reference    the zone or something in it is referenced, but nothing moves
                 ("creatures you control get +1/+1", "shuffle your library")

CHOICE -- whether a player decides anything about this interaction:
    True   there is a decision point. Declining entirely ("you MAY put it into
           your graveyard"), choosing an amount that may be zero ("put ANY
           NUMBER into your graveyard") and picking between alternatives
           ("cast it for its madness cost OR put it into your graveyard") are
           all the same answer: a player chooses.
    False  unconditional. It just happens.

A plain bool, on purpose. An earlier version split True into "optional" vs
"conditional" -- decline-entirely vs pick-which. That is a real difference in
the rules of Magic and an irrelevant one to someone browsing effects: both
read as "this might not put anything in my graveyard". See THE BAR FOR A NEW
TAG below.

WHY THIS EXISTS. A flat list of zone names cannot tell mill from surveil: both
are library + graveyard. Direction and choice separate them -- mill fills the
graveyard unconditionally, surveil only if the player elects to.

RULES EMIT RECORDS, NOT ZONE NAMES. One rule can emit several records, which
is what lets a single "surveil" rule say library-source, library-destination
and graveyard-destination-with-a-choice at once.

THE BAR FOR A NEW TAG. Tags exist to separate kinds of effects a browsing user
would think of differently -- not to record every way two similar effects
differ. Before adding a dimension or splitting a value, the question is
"would someone browsing want these in separate groups?", not "are these
technically different?". Magic's rules support endless true distinctions; most
of them would only make the browsing surface noisier.

REFERENCE IS RESIDUAL, per zone: a reference record is dropped if the same
zone also has a source or destination record, so "Destroy all creatures" is
battlefield-source, not also battlefield-reference. This generalizes the old
battlefield:static rule to every zone.

NO MORE battlefield:enters/leaves/static TAGS. They were exactly
(battlefield, destination/source/reference) and are now derived, not stored --
one source of truth, and the same three-way split is available for every zone.

TEXT SEARCHED: raw_text ONLY. plain_text is hand-authored for ~31 effects out
of 42,000 and its wording leaked authoring artifacts into labels, so it never
sets a label. What it WOULD have added is reported as a flag instead.
"""
import re

import glossary

# Canonical zone names, in report order.
ZONES = [
    "library", "hand", "battlefield", "graveyard",
    "exile", "stack", "command zone", "mana pool",
]

SOURCE, DESTINATION, REFERENCE = "source", "destination", "reference"
DIRECTIONS = [SOURCE, DESTINATION, REFERENCE]

CHOICE, NO_CHOICE = True, False
CHOICES = [NO_CHOICE, CHOICE]
CHOICE_LABEL = {NO_CHOICE: "no choice", CHOICE: "choice"}

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

_BF_OBJECT = (r"(?:creatures?|permanents?|artifacts?|enchantments?|planeswalkers?|lands?|tokens?)"
              r"\b(?! cards?\b)")

# Two ways the text can signal a decision point. They are not different kinds
# of choice -- they are two wordings of the same one, and both set choice=True.
# 1. an opt-out ("you may ...") earlier in the same sentence.
_MAY_RX = re.compile(r"\bmay\b", re.I)
# 2. a choice between alternatives anywhere in the same sentence: an "or"
#    followed by another action, or old-style inline modal templating.
_CHOICE_BETWEEN_RX = re.compile(
    r"\bor (?:put|exile|return|draw|mill|discard|sacrifice|destroy|shuffle|counter|"
    r"into|on top|on the bottom)\b"
    r"|;\s*or\b"
    r"|\bchoose (?:one|two|three|any number|one or both|one or more)\b", re.I)

# (tier, label, pattern, [(zone, direction, choice), ...]).
# Closed list; edit here, nowhere else.
RULES = [
    # ---- library ----
    ("explicit", "library",        r"\blibrar(?:y|ies)\b",
     [("library", REFERENCE, NO_CHOICE)]),
    ("entailed", "draw",           r"\bdraws?\b[^.]{0,20}\bcards?\b",
     [("library", SOURCE, NO_CHOICE), ("hand", DESTINATION, NO_CHOICE)]),
    ("entailed", "shuffle",        r"\bshuffles?\b",
     [("library", REFERENCE, NO_CHOICE)]),
    ("entailed", "mill",           r"\bmills?\b",
     [("library", SOURCE, NO_CHOICE), ("graveyard", DESTINATION, NO_CHOICE)]),
    # CR 701.42a: look at the top N, put any number into the graveyard, the
    # rest back on top. The graveyard half may be zero cards; the rest return.
    ("entailed", "surveil",        r"\bsurveils?\b",
     [("library", SOURCE, NO_CHOICE), ("library", DESTINATION, NO_CHOICE),
      ("graveyard", DESTINATION, CHOICE)]),
    ("entailed", "top-of-deck",    r"\btop \w+(?: \w+)? cards?\b",
     [("library", REFERENCE, NO_CHOICE)]),
    ("entailed", "search-library", r"\bsearch(?:es)?\b[^.]{0,30}\blibrar(?:y|ies)\b",
     [("library", SOURCE, NO_CHOICE)]),
    ("entailed", "put-into-library",
     r"\b(?:on top of|on the bottom of|into)\b[^.]{0,20}\blibrar(?:y|ies)\b",
     [("library", DESTINATION, NO_CHOICE)]),

    # ---- hand ----
    ("explicit", "hand",           r"\bhands?\b",
     [("hand", REFERENCE, NO_CHOICE)]),
    ("entailed", "discard",        r"\bdiscards?\b|\bdiscarded\b",
     [("hand", SOURCE, NO_CHOICE), ("graveyard", DESTINATION, NO_CHOICE)]),
    ("entailed", "to-hand",
     r"\b(?:in)?to (?:its owner's|their|your|his or her|an opponent's|that player's) hands?\b"
     r"|\bto (?:its|their) owners?['’]?s?['’]? hands?\b",
     [("hand", DESTINATION, NO_CHOICE)]),

    # ---- graveyard ----
    ("explicit", "graveyard",      r"\bgraveyards?\b",
     [("graveyard", REFERENCE, NO_CHOICE)]),
    ("entailed", "from-graveyard", r"\bfrom (?:your|a|their|its owner's|an opponent's) graveyards?\b",
     [("graveyard", SOURCE, NO_CHOICE)]),
    ("entailed", "put-into-graveyard", r"\binto (?:its owner's|their|your|a) graveyards?\b",
     [("graveyard", DESTINATION, NO_CHOICE)]),

    # ---- battlefield: destination ----
    ("entailed", "enters",         r"\benters?\b",
     [("battlefield", DESTINATION, NO_CHOICE)]),
    ("explicit", "put-onto-battlefield", r"\bput\b[^.]{0,60}\bonto the battlefield\b",
     [("battlefield", DESTINATION, NO_CHOICE)]),
    ("explicit", "return-to-battlefield", r"\breturns?\b[^.]{0,60}\bto the battlefield\b",
     [("battlefield", DESTINATION, NO_CHOICE)]),
    ("entailed", "create-token",   r"\bcreates?\b[^.]{0,40}\btokens?\b",
     [("battlefield", DESTINATION, NO_CHOICE)]),

    # ---- battlefield: source (with the destination zone it implies) ----
    ("entailed", "destroy",        r"\bdestroys?\b|\bdestroyed\b",
     [("battlefield", SOURCE, NO_CHOICE), ("graveyard", DESTINATION, NO_CHOICE)]),
    ("entailed", "sacrifice",      r"\bsacrifices?\b|\bsacrificed\b",
     [("battlefield", SOURCE, NO_CHOICE), ("graveyard", DESTINATION, NO_CHOICE)]),
    ("entailed", "dies",           r"\bdies\b|\bdied\b",
     [("battlefield", SOURCE, NO_CHOICE), ("graveyard", DESTINATION, NO_CHOICE)]),
    ("explicit", "leaves-battlefield", r"\bleaves? the battlefield\b|\bfrom the battlefield\b",
     [("battlefield", SOURCE, NO_CHOICE)]),
    ("entailed", "exile-permanent",
     r"\bexile (?:target|each|all|another|that)\b[^.]{0,40}?\b" + _BF_OBJECT,
     [("battlefield", SOURCE, NO_CHOICE), ("exile", DESTINATION, NO_CHOICE)]),
    ("entailed", "bounce",
     r"\breturns?\b[^.]{0,60}\bto (?:its|their) owners?['’]?s?['’]? hands?\b",
     [("battlefield", SOURCE, NO_CHOICE), ("hand", DESTINATION, NO_CHOICE)]),

    # ---- battlefield: reference ----
    ("explicit", "battlefield",    r"\bbattlefield\b", [("battlefield", REFERENCE, NO_CHOICE)]),
    ("entailed", "in-play",        r"\bin play\b", [("battlefield", REFERENCE, NO_CHOICE)]),
    ("entailed", "permanent",      r"\bpermanents?\b", [("battlefield", REFERENCE, NO_CHOICE)]),
    ("entailed", "you-control",    r"\byou control\b|\byour control\b", [("battlefield", REFERENCE, NO_CHOICE)]),
    ("entailed", "creature",       r"\bcreatures?\b(?! (?:cards?|spells?)\b)", [("battlefield", REFERENCE, NO_CHOICE)]),
    ("entailed", "planeswalker",   r"\bplaneswalkers?\b", [("battlefield", REFERENCE, NO_CHOICE)]),
    ("entailed", "land",           r"\blands?\b(?! cards?\b)", [("battlefield", REFERENCE, NO_CHOICE)]),
    ("entailed", "token",          r"\btokens?\b", [("battlefield", REFERENCE, NO_CHOICE)]),
    ("entailed", "tap",            r"\{T\}|\btaps?\b|\btapped\b", [("battlefield", REFERENCE, NO_CHOICE)]),
    ("entailed", "on-permanent-counters",
     r"\b(?:\+1/\+1|-1/-1|loyalty|charge) counters?\b|\bcounters? on\b", [("battlefield", REFERENCE, NO_CHOICE)]),
    ("entailed", "combat",
     r"\battacks?\b|\bblocks?\b|\bblock it\b|\battacking\b|\bblocking\b", [("battlefield", REFERENCE, NO_CHOICE)]),
    ("entailed", "static-keyword",  _STATIC_KEYWORD_RX, [("battlefield", REFERENCE, NO_CHOICE)]),
    # CR 115.4: "any target" means a creature, player, planeswalker, or battle.
    ("entailed", "any-target",     r"\bany target\b", [("battlefield", REFERENCE, NO_CHOICE)]),

    # ---- exile ----
    ("explicit", "exile",          r"\bexil(?:e|es|ed|ing)\b", [("exile", DESTINATION, NO_CHOICE)]),
    ("explicit", "from-exile",     r"\bfrom exile\b|\bexiled with\b",
     [("exile", SOURCE, NO_CHOICE)]),

    # ---- stack ----
    ("explicit", "stack",          r"\bstack\b", [("stack", REFERENCE, NO_CHOICE)]),
    ("entailed", "spell",          r"\bspells?\b", [("stack", REFERENCE, NO_CHOICE)]),
    ("entailed", "cast",           r"\bcasts?\b|\bcasting\b", [("stack", DESTINATION, NO_CHOICE)]),
    ("entailed", "resolve",        r"\bresolves?\b", [("stack", REFERENCE, NO_CHOICE)]),
    # CR 701.5a: a countered spell is put into its owner's graveyard.
    ("entailed", "counter-target", r"\bcounters? target\b|\bcountered\b",
     [("stack", SOURCE, NO_CHOICE), ("graveyard", DESTINATION, NO_CHOICE)]),

    # ---- command zone ----
    ("explicit", "command zone",   r"\bcommand zone\b", [("command zone", REFERENCE, NO_CHOICE)]),
    ("entailed", "commander",      r"\bcommanders?\b", [("command zone", REFERENCE, NO_CHOICE)]),
    ("entailed", "emblem",         r"\bemblems?\b", [("command zone", DESTINATION, NO_CHOICE)]),

    # ---- mana pool ----
    ("explicit", "mana pool",      r"\bmana pool\b", [("mana pool", REFERENCE, NO_CHOICE)]),
    ("entailed", "add-mana",       r"\badd\b[^.]{0,60}\bmana\b|\badd \{", [("mana pool", DESTINATION, NO_CHOICE)]),
    ("entailed", "produce-mana",   r"\bproduces?\b[^.]{0,40}\bmana\b|\bto produce\b",
     [("mana pool", DESTINATION, NO_CHOICE)]),
    ("entailed", "tap-for-mana",   r"\btapp?e?d?\b[^.]{0,30}\bfor mana\b", [("mana pool", DESTINATION, NO_CHOICE)]),
]

COMPILED = [(tier, label, re.compile(pat, re.I), records) for tier, label, pat, records in RULES]

_SENTENCE_SPLIT = re.compile(r"(?<=\.)\s+|\n+")


def _sentence_span(text, pos):
    """Start/end offsets of the sentence containing `pos`."""
    start = 0
    for m in _SENTENCE_SPLIT.finditer(text):
        if m.end() > pos:
            return start, m.start()
        start = m.end()
    return start, len(text)


def _choice_in_context(text, pos):
    """True if the sentence around the match puts a decision in the player's
    hands -- an opt-out before the match, or a choice between alternatives
    anywhere in the sentence. Both answer the same yes/no question."""
    start, end = _sentence_span(text, pos)
    sentence = text[start:end]
    return bool(_MAY_RX.search(sentence[:pos - start])
                or _CHOICE_BETWEEN_RX.search(sentence))


def _records_for(text):
    """Return ({(zone, direction): choice}, {(zone, direction): [(tier, label)]})."""
    best, evidence = {}, {}
    for tier, label, rx, records in COMPILED:
        m = rx.search(text)
        if not m:
            continue
        for zone, direction, declared in records:
            # Declared by the rule, or signalled by the surrounding sentence.
            # Merging across rules is a plain OR: if any rule sees a decision
            # point for this (zone, direction), the player has one.
            choice = declared or _choice_in_context(text, m.start())
            key = (zone, direction)
            best[key] = best.get(key, NO_CHOICE) or choice
            evidence.setdefault(key, []).append((tier, label))
    # reference is residual: drop it where the same zone also moves something
    moved = {z for z, d in best if d != REFERENCE}
    for key in [k for k in best if k[1] == REFERENCE and k[0] in moved]:
        del best[key]
        del evidence[key]
    return best, evidence


def _ordered(best):
    return sorted(best, key=lambda k: (ZONES.index(k[0]), DIRECTIONS.index(k[1])))


def classify(raw_text, plain_text=""):
    """Return (zones, evidence, flags).

    zones     list of {"zone", "direction", "choice"} records, in ZONES order.
    evidence  {"zone:direction": [(tier, label), ...]} for every applied record.
    flags     [(tag, applied, [(tier, label), ...])] for records plain_text
              alone would have produced. Always applied=False: plain_text never
              sets a label, it only raises a flag.
    """
    raw_text = raw_text or ""
    best, evidence = _records_for(raw_text)
    zones = [{"zone": z, "direction": d, "choice": best[(z, d)]} for z, d in _ordered(best)]
    ev = {"%s:%s" % k: v for k, v in evidence.items()}

    flags = []
    if plain_text:
        plain_best, plain_ev = _records_for(plain_text)
        for key in _ordered(plain_best):
            if key not in best:
                flags.append(("%s:%s" % key, False, plain_ev[key]))
    return zones, ev, flags


def classify_entry(entry):
    """Compute and attach entry['zones']. Returns (evidence, flags)."""
    zones, evidence, flags = classify(entry.get("raw_text", ""), entry.get("plain_text", ""))
    entry["zones"] = zones
    return evidence, flags


# ---- helpers for consumers ----

def zone_names(records):
    """Unique zone names in ZONES order (the old flat view)."""
    seen = [r["zone"] for r in records]
    return [z for z in ZONES if z in seen]


def top_level(records):
    """Back-compat alias: zone names only."""
    return zone_names(records)


def tag_strings(records):
    """['library:source', 'graveyard:destination', ...] in record order."""
    return ["%s:%s" % (r["zone"], r["direction"]) for r in records]


def describe(record):
    return "%s:%s (%s)" % (record["zone"], record["direction"],
                           CHOICE_LABEL[record["choice"]])


def main():
    entries = glossary.load_glossary()
    results = {e["effect_id"]: classify_entry(e) for e in entries}
    glossary.write_glossary(entries)

    for e in entries:
        evidence, flags = results[e["effect_id"]]
        zones = e["zones"]
        marks = []
        if len(zone_names(zones)) >= 3:
            marks.append("3+ ZONES")
        if not zones:
            marks.append("ZERO ZONES")
        if flags:
            marks.append("PLAIN-ONLY FLAG")
        print("%s  [%s]%s" % (e["effect_id"], ", ".join(describe(r) for r in zones) or "-",
                              ("  <-- " + ", ".join(marks)) if marks else ""))
        print("    %s" % e["raw_text"].replace("\n", " ")[:110])
        for r in zones:
            tag = "%s:%s" % (r["zone"], r["direction"])
            print("      %-26s %-11s %s" % (tag, CHOICE_LABEL[r["choice"]],
                                            ", ".join("%s:%s" % h for h in evidence[tag])))
        for tag, _applied, fired in flags:
            print("      ! %-24s plain-only, NOT applied: %s"
                  % (tag, ", ".join("%s:%s" % f for f in fired)))
        print("")

    print("%d effects labelled. %d with zero zones, %d with plain-only flags."
          % (len(entries), sum(1 for e in entries if not e["zones"]),
             sum(1 for e in entries if results[e["effect_id"]][1])))
    for zone in ZONES:
        for direction in DIRECTIONS:
            n = sum(1 for e in entries
                    if any(r["zone"] == zone and r["direction"] == direction for r in e["zones"]))
            if n:
                print("  %-13s %-12s %d" % (zone, direction, n))


if __name__ == "__main__":
    main()
