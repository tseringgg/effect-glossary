"""Deterministic, structural-only effect extraction.

Splitting rules -- and ONLY these rules:
  1. Line breaks in oracle_text.
  2. Modal / choice markers: a "Choose one --"-style lead-in is its own chunk,
     and each bullet ("*" in Scryfall oracle text, rendered as a bullet) is
     its own chunk.
  3. Keyword-ability lines are exploded: a line that is entirely a
     comma-separated list of known keyword abilities yields one effect per
     keyword, distinct from any ability text printed elsewhere on the card.

Explicitly NOT done: sentence-level or semantic splitting. An ambiguous
multi-clause sentence stays as one chunk (e.g. Wrath of God's
"Destroy all creatures. They can't be regenerated." is ONE effect).
"""
import re

# Keyword abilities that can appear as a bare comma-separated line.
# Deliberately a closed list -- this is a structural rule, not a semantic one.
KEYWORD_ABILITIES = {
    "deathtouch", "defender", "double strike", "enchant", "equip",
    "first strike", "flash", "flying", "haste", "hexproof", "indestructible",
    "intimidate", "landwalk", "lifelink", "protection", "reach", "shroud",
    "trample", "vigilance", "banding", "rampage", "cumulative upkeep",
    "flanking", "phasing", "buyback", "shadow", "echo", "horsemanship",
    "fading", "kicker", "flashback", "madness", "fear", "morph", "amplify",
    "provoke", "storm", "affinity", "entwine", "modular", "sunburst",
    "bushido", "soulshift", "splice", "offering", "ninjutsu", "epic",
    "convoke", "dredge", "transmute", "bloodthirst", "haunt", "replicate",
    "forecast", "graft", "recover", "ripple", "split second", "suspend",
    "vanishing", "absorb", "aura swap", "delve", "fortify", "frenzy",
    "gravestorm", "poisonous", "transfigure", "champion", "changeling",
    "evoke", "hideaway", "prowl", "reinforce", "conspire", "persist",
    "wither", "retrace", "devour", "exalted", "unearth", "cascade",
    "annihilator", "level up", "rebound", "totem armor", "infect",
    "battle cry", "living weapon", "undying", "miracle", "soulbond",
    "overload", "scavenge", "unleash", "cipher", "evolve", "extort",
    "fuse", "bestow", "tribute", "dethrone", "outlast", "prowess",
    "dash", "exploit", "menace", "renown", "awaken", "devoid", "ingest",
    "myriad", "surge", "skulk", "emerge", "escalate", "melee", "crew",
    "fabricate", "partner", "undaunted", "improvise", "aftermath",
    "embalm", "eternalize", "afflict", "ascend", "assist", "jump-start",
    "mentor", "afterlife", "riot", "spectacle", "escape", "companion",
    "mutate", "encore", "boast", "foretell", "demonstrate", "daybound",
    "nightbound", "disturb", "decayed", "cleave", "training", "compleated",
    "reconfigure", "blitz", "casualty", "enlist", "read ahead", "ravenous",
    "squad", "space sculptor", "visit", "prototype", "living metal",
    "backup", "bargain", "craft", "disguise", "plot", "saddle", "spree",
    "freerunning", "gift", "offspring", "impending", "flurry",
}

MODAL_LEADIN = re.compile(r"^(choose (one|two|three|any number)[^\n]*?)(?:\s*[-—•]+\s*)$",
                          re.IGNORECASE)
BULLET_PREFIX = re.compile(r"^\s*[•*∙]\s*")


def _explode_keyword_line(line):
    """If `line` is a bare comma-separated list of keyword abilities, return
    each keyword as its own chunk; otherwise return None."""
    parts = [p.strip() for p in line.split(",")]
    if not parts or any(not p for p in parts):
        return None
    for p in parts:
        # Strip a trailing reminder-text parenthetical before testing.
        bare = re.sub(r"\s*\([^)]*\)\s*$", "", p).strip().lower()
        if bare not in KEYWORD_ABILITIES:
            return None
    return [p.strip() for p in parts]


def extract_effects(oracle_text):
    """Return an ordered list of literal effect chunks for one card."""
    if not oracle_text:
        return []
    chunks = []
    for raw_line in oracle_text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        # Rule 2: bullets are their own chunk.
        if BULLET_PREFIX.match(line):
            chunks.append(BULLET_PREFIX.sub("", line).strip())
            continue

        # Rule 2: a modal lead-in ending in a dash is its own chunk; anything
        # trailing it on the same line is kept as a following chunk.
        m = MODAL_LEADIN.match(line)
        if m:
            chunks.append(line)
            continue

        # Rule 3: keyword-ability line explodes into one effect per keyword.
        exploded = _explode_keyword_line(line)
        if exploded is not None:
            chunks.extend(exploded)
            continue

        chunks.append(line)
    return chunks
