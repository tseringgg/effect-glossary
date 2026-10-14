#!/usr/bin/env python3
"""Names for the community-tag groups: fixed wording rules (below) plus a hand-written overlay (corrections/tag_names.json). Importable.

Every name carries a name_source: rule (the rules turn the slug into words), model_written (an entry of the overlay in corrections/tag_names.json) or user_edit (the user_edits section of that file); a user edit overrides both, the overlay overrides the rules. Rules: the slug is split at hyphens;
shorthand is expanded (pp -> +1/+1, mm -> -1/-1, etb -> enters, ltb -> leaves, cmc and mv -> mana value, p and t -> power and toughness); a leading word is replaced by its fixed phrase
(synergy- -> "Cares about", typal- -> "Cares about the creature type", gives- / gains- -> "Gives" / "Gains", protects- -> "Protects", hate- -> "Works against", removal- -> "Removal:",
repeatable- -> "Repeatable:", tutor- -> "Tutors", conjure- -> "Conjures", copy- -> "Copies", scales-with- -> "Scales with", theft- -> "Takes control of"); a trailing -matters or -matters-self ->
"Cares about ..."; the first letter is capitalized; nothing else is added. The overlay is read, not generated.
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHORT = {"pp": "+1/+1", "mm": "-1/-1", "etb": "enters", "ltb": "leaves", "cmc": "mana value", "mv": "mana value", "pt": "power and toughness"}
LEAD = [("scales-with-", "Scales with "), ("synergy-", "Cares about "), ("typal-", "Cares about the creature type "), ("gives-", "Gives "), ("gains-", "Gains "), ("protects-", "Protects "),
        ("hate-", "Works against "), ("removal-", "Removal: "), ("repeatable-", "Repeatable: "), ("tutor-", "Tutors "), ("conjure-", "Conjures "), ("copy-", "Copies "), ("theft-", "Takes control of ")]


def words(s):
    return " ".join(SHORT.get(w, w) for w in s.split("-"))


def rule_name(slug):
    for p, ph in LEAD:
        if slug.startswith(p):
            r = words(slug[len(p):])
            return (ph + r).strip()[:1].upper() + (ph + r).strip()[1:]
    m = re.match(r"^(.*)-matters(-self)?$", slug)
    if m:
        s = "Cares about " + words(m.group(1)) + (" itself" if m.group(2) else "")
        return s
    s = words(slug)
    return s[:1].upper() + s[1:]


def load_doc():
    p = os.path.join(HERE, "corrections", "tag_names.json")
    return json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else {"overlay": {}}


def load_overlay():
    d = load_doc()
    return {"model_written": d.get("overlay", {}), "user_edit": d.get("user_edits", {})}


def name_of(slug, overlay=None):
    """-> (name, name_source). name_source: rule (the fixed rules above), model_written (the overlay in corrections/tag_names.json), user_edit (the user_edits section of the same file).
    A user edit overrides both the overlay and the rules; the overlay overrides the rules."""
    ov = overlay if overlay is not None else load_overlay()
    if slug in ov["user_edit"]:
        return ov["user_edit"][slug], "user_edit"
    if slug in ov["model_written"]:
        return ov["model_written"][slug], "model_written"
    return rule_name(slug), "rule"
