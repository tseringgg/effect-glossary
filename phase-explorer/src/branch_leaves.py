#!/usr/bin/env python3
"""Assign the 591 structural leaves to named branches, by rule only.

Same shape as the zone classifier (src/classify_zones.py in the parent
experiment): a closed, documented list of named predicates, each auditable,
no model and no voting. The difference is what they match on -- the zone rules
run regexes over raw_text; these run set membership over a leaf's *dominant
structural facts*, because the whole point of this pass is that structure, not
wording, is the signal.

NO MEMBERSHIP VOTING. A branch never asks "how many of this leaf's cards carry
Scryfall tag X". Branch vocabulary is sourced from curated data; branch
*assignment* is purely the structural predicate below.

Leaves are NOT re-clustered here -- build/clusters.json is read as given.

Reads   build/clusters.json, build/index.json, build/chunks/*.json
Writes  build/branches.json        branch -> leaves, for the tree UI
        reports/branches.md        the human-readable report

BRANCH VOCABULARY SOURCES (no invented names):
  * curated  development/versions/card_function_search_v0.2/src/mtg_query/
             glossary.yaml, `function:` section -- 10 canonical entries, each
             already carrying the Scryfall otag slugs it covers.
  * otag     development/versions/card_function_search_v0.2/data/
             otag_glossary_scryfall.yaml -- 1,105 Scryfall oracle-tag slugs.
  * slang    development/semantic-search/mtg-search-v0/data/glossary.yaml --
             10 slang function terms (ramp, wrath, removal, burn, ...).

A branch is only defined where the structural signal is unambiguous. Where a
curated term exists but the structure cannot express it, there is NO rule and
the term is recorded in GAPS instead -- a weak rule would quietly mislabel
leaves, which is worse than an honest gap.
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cluster_structural as C

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
REPORTS = os.path.join(HERE, "reports")

# A fact must hold for at least this share of a leaf's cards to count as
# "dominant" for that leaf. A leaf is a tight structural group by construction,
# so a simple majority is a meaningful bar rather than an arbitrary one.
DOMINANT = 0.5

# A fact scoring in [NEAR_MISS, DOMINANT) is a *near miss*: it did not earn the
# leaf a branch, but it is close enough that a human should look rather than the
# rule silently deciding. These go to the review queue, never straight into a
# branch -- loosening the threshold globally is exactly how coverage numbers get
# inflated with wrong placements.
NEAR_MISS = 0.35

# An auto-named branch needs at least this many leaves. The bar is the whole
# point of the category: "shared functional identity" is a claim about more than
# one leaf. A lone leaf that fits nowhere is not an unnamed group -- it is a
# Unique effect, which is a finding, not a gap.
MIN_AUTO_LEAVES = 2

# Cohesion floor for NEW / loosened / auto-named rules, measured on the
# effect-flavoured map as "tighter than X% of all leaf pairs". Burn -- the defect
# the branch audit existed to remove -- scored 52%. The weakest branches that
# survived that audit sit at 57-58% (Card draw, Tapper). 60% is therefore set
# just above the known-bad band: a new rule that scores here is behaving like
# Burn did, so it is routed to the review queue instead of being kept.
# Pre-existing curated branches are NOT re-litigated against this bar; the audit
# already ruled on them.
COHESION_MIN = 0.60

# ---------------------------------------------------------------- fact sets

# Effects that remove a permanent from the battlefield, one target at a time.
SPOT_REMOVAL_EFFECTS = {"Destroy", "Bounce", "Sacrifice", "Fight"}
# The mass ("...All") counterparts. ChangeZoneAll covers mass exile/bounce.
MASS_EFFECTS = {
    "DestroyAll", "DamageAll", "ChangeZoneAll", "PumpAll", "PutCounterAll",
    "TapAll", "UntapAll", "SacrificeAll", "BounceAll", "DiscardAll",
    "CounterAll", "ExileAll", "MillAll", "DamageEachPlayer",
}
# Of those, the ones that actually remove creatures. PumpAll is excluded on
# purpose: it covers both anthems (+1/+1 to your team) and -X/-X sweepers, and
# telling them apart needs the sign of a quantity node -- see GAPS.
MASS_REMOVAL_EFFECTS = {
    "DestroyAll", "DamageAll", "ChangeZoneAll", "SacrificeAll", "BounceAll",
    "ExileAll",
}
# Burn is SINGLE-TARGET damage only. It previously read
#   {"DealDamage", "DamageAll", "DamageEachPlayer"}
# which bundled "deal 3 damage to one target" with "deal 3 damage to
# EVERYTHING". Those are different kinds of card, and the branch scored
# worst of all 33 branches in both leaf-similarity maps (42% zone/choice,
# 52% effect) because no layout can make a category cohere that is drawn
# across that line. 15 of its 41 leaves were mass-dominant.
BURN_EFFECTS = {"DealDamage"}
# DamageAll is deliberately NOT here. Bundling it with DamageEachPlayer
# repeated the very defect this audit exists to remove: the two halves
# scored 99.4% and 98.5% cohesion separately but 62.9% together, sitting
# 9.05 apart against a 4.94 corpus mean -- further apart than random
# leaves. DamageAll hits each CREATURE (mass removal, already Board wipe,
# which claims all 11 of those leaves); DamageEachPlayer hits each PLAYER.
MASS_BURN_EFFECTS = {"DamageEachPlayer"}
DRAW_EFFECTS = {"Draw"}
EVASION_KEYWORDS = {
    "Flying", "Menace", "Fear", "Intimidate", "Shadow", "Skulk",
    "Horsemanship", "Protection",
}


def fact_scores(members, chunks, byid):
    """Every structural fact for one leaf -> share of its cards carrying it.

    Facts are flat strings so every predicate below is plain set membership:
        eff:<Type>              a top-level effect type
        tgt:<shape>             a target/filter shape
        eff:<Type>|tgt:<shape>  the two bound together
        cz:<origin>><dest>      a ChangeZone's zone transition
        ctrl:<Type>@<who>       a mass effect's target controller scope
        mod:<tag>               a static Continuous modification
        mill:<shape>            who a Mill effect points at
        type:<CoreType>         a card-type-line core type

    `type:` is the feature extension added for Mana dork / Mana rock. Those two
    were refused by the first pass for one reason only: both are effect Mana,
    and the thing that tells them apart is the *type line* (creature vs
    artifact), which was outside the stated effect-and-target feature space.
    Nothing else about the space changed, and no existing rule reads `type:`.
    """
    counts = collections.Counter()
    for cid in members:
        d = chunks[byid[cid]["ch"]][cid]
        seen = set()

        def note_effect(e):
            if not isinstance(e, dict):
                return
            et, ts = C.effect_features(e)
            if not et:
                return
            seen.add(f"eff:{et}")
            if ts:
                seen.add(f"tgt:{ts}")
                seen.add(f"eff:{et}|tgt:{ts}")
            if et == "ChangeZone":
                seen.add(f"cz:{e.get('origin')}>{e.get('destination')}")
            if et in MASS_EFFECTS:
                tg = e.get("target")
                who = (tg.get("controller") or "Any") if isinstance(tg, dict) else "Any"
                seen.add(f"ctrl:{et}@{who}")
            if et == "Mill":
                seen.add(f"mill:{C.target_shape(e.get('target'))}")

        for a in d.get("abilities") or []:
            note_effect(a.get("effect"))
        for t in d.get("triggers") or []:
            note_effect((t.get("execute") or {}).get("effect"))
        for r in d.get("replacements") or []:
            note_effect((r.get("execute") or {}).get("effect"))
        for s in d.get("static_abilities") or []:
            m = C.tag(s.get("mode"))
            if not m:
                continue
            ts = C.target_shape(s.get("affected"))
            seen.add(f"eff:static:{m}")
            if ts:
                seen.add(f"tgt:{ts}")
                seen.add(f"eff:static:{m}|tgt:{ts}")
            if m == "Continuous":
                for mod in s.get("modifications") or []:
                    mt = mod if isinstance(mod, str) else C.shape_tag(mod)
                    if mt:
                        seen.add(f"mod:{mt}")
        ct = d.get("card_type") or {}
        for t in ct.get("core_types") or []:
            seen.add(f"type:{t}")

        counts.update(seen)

    n = len(members)
    return {f: c / n for f, c in counts.items()}


def facts_for_leaf(members, chunks, byid):
    """The dominant subset of fact_scores() -- what the rules actually see."""
    return {f for f, sc in fact_scores(members, chunks, byid).items()
            if sc >= DOMINANT}


# ------------------------------------------------------- predicate helpers

def effs(F):
    return {f[4:] for f in F if f.startswith("eff:")}


def pairs(F):
    out = []
    for f in F:
        if f.startswith("eff:") and "|tgt:" in f:
            e, t = f[4:].split("|tgt:", 1)
            out.append((e, t))
    return out


def mods(F):
    return {f[4:] for f in F if f.startswith("mod:")}


def types_of(F):
    return {f[5:] for f in F if f.startswith("type:")}


def targets_creature(F, allowed):
    """True if a removal-ish effect in `allowed` points at a creature filter."""
    return any(e in allowed and t.startswith("Typed[Creature") for e, t in pairs(F))


# --------------------------------------------------------------- the rules
# (name, source, otag slugs it stands for, rule text, predicate)
BRANCHES = [
    # ---- mass / sweeper -------------------------------------------------
    ("Board wipe", "curated", ["sweeper"],
     "dominant effect in {DestroyAll, DamageAll, ChangeZoneAll, SacrificeAll, "
     "BounceAll, ExileAll} -- mass removal only; PumpAll deliberately excluded",
     lambda F: bool(effs(F) & MASS_REMOVAL_EFFECTS)),

    ("One-sided sweeper", "otag", ["sweeper-one-sided"],
     "a mass-removal effect whose target controller scope is Opponent",
     lambda F: any(f.startswith("ctrl:") and f.endswith("@Opponent")
                   and f[5:].split("@")[0] in MASS_REMOVAL_EFFECTS for f in F)),

    ("Mass effect", "otag", ["sweeper", "mass-shrink", "anthem"],
     "dominant effect is any '...All' / each-player mass effect, removal or not "
     "-- the broad superset of Board wipe",
     lambda F: bool(effs(F) & MASS_EFFECTS)),

    # ---- targeted removal ----------------------------------------------
    ("Spot removal", "curated", ["spot-removal"],
     "dominant effect in {Destroy, Bounce, Sacrifice, Fight}, or a ChangeZone "
     "ending in Exile, with no mass effect dominant",
     lambda F: (bool(effs(F) & SPOT_REMOVAL_EFFECTS)
                or any(f.startswith("cz:") and f.endswith(">Exile") for f in F))
               and not (effs(F) & MASS_EFFECTS)),

    # Was `SPOT_REMOVAL_EFFECTS | MASS_REMOVAL_EFFECTS` -- a literal union of the
    # single-target and mass sets, 10 of its 39 leaves mass-dominant. The mass
    # half is not given a new branch: mass removal of creatures is *exactly*
    # Board wipe's definition, and all 10 of those leaves already carry Board
    # wipe, so a second name would only duplicate it.
    ("Creature removal", "curated", ["removal-creature"],
     "a SINGLE-TARGET removal effect whose bound target filter is "
     "Typed[Creature...]; mass creature removal is Board wipe",
     lambda F: targets_creature(F, SPOT_REMOVAL_EFFECTS)),

    ("Destroy removal", "otag", ["removal-destroy"],
     "dominant effect is Destroy",
     lambda F: "Destroy" in effs(F)),

    ("Exile removal", "otag", ["removal-exile"],
     "a dominant ChangeZone transition ending in Exile, not originating in a graveyard",
     lambda F: any(f.startswith("cz:") and f.endswith(">Exile")
                   and not f.startswith("cz:Graveyard>") for f in F)),

    ("Bounce removal", "otag", ["removal-bounce"],
     "dominant effect is Bounce",
     lambda F: "Bounce" in effs(F)),

    ("Sacrifice removal", "otag", ["removal-sacrifice"],
     "dominant effect is Sacrifice",
     lambda F: "Sacrifice" in effs(F)),

    # ---- graveyard -----------------------------------------------------
    ("Reanimation", "otag", ["reanimate-creature", "mass-reanimation"],
     "a dominant ChangeZone transition Graveyard -> Battlefield",
     lambda F: "cz:Graveyard>Battlefield" in F),

    ("Graveyard hate", "otag", ["hate-graveyard", "sweeper-graveyard"],
     "a dominant ChangeZone transition Graveyard -> Exile",
     lambda F: "cz:Graveyard>Exile" in F),

    # ---- library / card flow -------------------------------------------
    ("Self-mill", "otag", ["mill-self"],
     "a dominant Mill effect pointed at Controller",
     lambda F: "mill:Controller" in F),

    ("Opponent mill", "otag", ["mill-opponent", "mill-any", "mill-each"],
     "a dominant Mill effect pointed at Player / an Opponent-scoped filter",
     lambda F: any(f.startswith("mill:") and f != "mill:Controller" for f in F)),

    ("Surveil", "otag", ["surveil"],
     "dominant effect is Surveil",
     lambda F: "Surveil" in effs(F)),

    ("Scry", "otag", ["scry"],
     "dominant effect is Scry",
     lambda F: "Scry" in effs(F)),

    ("Card draw", "otag", ["pure-draw", "draw-engine", "burst-draw"],
     "dominant effect is Draw",
     lambda F: bool(effs(F) & DRAW_EFFECTS)),

    ("Tutor", "otag", ["tutor-to-hand"],
     "dominant effect is SearchLibrary",
     lambda F: "SearchLibrary" in effs(F)),

    ("Discard", "otag", ["discard"],
     "dominant effect is Discard",
     lambda F: "Discard" in effs(F)),

    # ---- stack ---------------------------------------------------------
    ("Counterspell", "slang", ["counterspell"],
     "dominant effect is Counter",
     lambda F: "Counter" in effs(F)),

    # ---- damage / life -------------------------------------------------
    ("Burn", "slang+otag", ["burn-creature", "burn-any", "burn-player"],
     "dominant effect is DealDamage (single target)",
     lambda F: bool(effs(F) & BURN_EFFECTS)),

    # The mass half keeps a name of its own rather than dissolving into the
    # generic Mass effect bucket: `burn-player-each` is a real Scryfall otag
    # (132 cards), and "deals damage to each player" is a function people
    # actually look for. Scoped to DamageEachPlayer only -- see
    # MASS_BURN_EFFECTS for why DamageAll is excluded.
    ("Mass burn", "otag", ["burn-player-each"],
     "dominant effect is DamageEachPlayer -- damage to every player. Damage to "
     "every creature (DamageAll) is Board wipe, not this",
     lambda F: bool(effs(F) & MASS_BURN_EFFECTS)),

    ("Lifegain", "otag", ["lifegain", "repeatable-lifegain"],
     "dominant effect is GainLife",
     lambda F: "GainLife" in effs(F)),

    # ---- mana ----------------------------------------------------------
    ("Ramp", "curated", ["ramp"],
     "dominant effect is Mana",
     lambda F: "Mana" in effs(F)),

    # Unblocked by the type: feature extension. Both were refused before for a
    # single stated reason -- the discriminator is the type line, not an effect
    # or target -- and nothing else about them was in doubt. Each is Ramp's
    # effect narrowed by one type fact, so they are strict subsets of Ramp and
    # do not compete with it.
    ("Mana dork", "curated (glossary.yaml function:)", ["mana-creature"],
     "dominant effect is Mana AND the type line is a Creature",
     lambda F: "Mana" in effs(F) and "Creature" in types_of(F)),

    ("Mana rock", "curated (glossary.yaml function:)", ["mana-artifact"],
     "dominant effect is Mana AND the type line is an Artifact",
     lambda F: "Mana" in effs(F) and "Artifact" in types_of(F)),

    ("Land ramp", "curated", ["land-ramp"],
     "a dominant ChangeZone ending on the Battlefield bound to a Typed[Land...] filter",
     lambda F: any(e == "ChangeZone" and t.startswith("Typed[Land")
                   for e, t in pairs(F))
               and any(f.startswith("cz:") and f.endswith(">Battlefield") for f in F)),

    # ---- tokens / copies -----------------------------------------------
    ("Token maker", "curated", ["repeatable-creature-tokens"],
     "dominant effect is Token",
     lambda F: "Token" in effs(F)),

    ("Clone effect", "curated", ["clone", "copy-creature"],
     "dominant effect is BecomeCopy",
     lambda F: "BecomeCopy" in effs(F)),

    # ---- counters ------------------------------------------------------
    # Was {PutCounter, PutCounterAll}: the same single/mass "or" as Burn, though
    # milder in effect (5 of 50 leaves mass-dominant). Split anyway, because the
    # rule is drawn across the same line.
    ("+1/+1 counters", "otag", ["gives-pp-counters", "gains-pp-counters",
                                "counters-matter"],
     "dominant effect is PutCounter (single target)",
     lambda F: "PutCounter" in effs(F)),

    ("Mass +1/+1 counters", "otag", ["gives-pp-counters-to-all"],
     "dominant effect is PutCounterAll -- counters on every matching permanent",
     lambda F: "PutCounterAll" in effs(F)),

    # ---- combat / static -----------------------------------------------
    ("Tapper", "otag", ["tapper-creature"],
     "dominant effect is Tap",
     lambda F: "Tap" in effs(F)),

    ("Untapper", "otag", ["untapper-creature"],
     "dominant effect is Untap",
     lambda F: "Untap" in effs(F)),

    ("Anthem", "otag", ["anthem"],
     "a dominant static Continuous modification adding power or toughness",
     lambda F: any(m.startswith(("AddPower", "AddToughness", "AddDynamicPower",
                                 "AddDynamicToughness")) for m in mods(F))),

    ("Evasion grant", "otag", ["evasion"],
     "a dominant static Continuous modification granting an evasion keyword "
     "(Flying, Menace, Fear, Intimidate, Shadow, Skulk, Horsemanship, Protection)",
     lambda F: any(m.startswith("AddKeyword:") and m.split(":", 1)[1] in EVASION_KEYWORDS
                   for m in mods(F))),

    ("Keyword grant", "otag", ["gives-trample", "evasion"],
     "a dominant static Continuous AddKeyword modification, or a dominant "
     "AddKeyword effect",
     lambda F: any(m.startswith("AddKeyword") for m in mods(F))
               or "AddKeyword" in effs(F)),

    ("Damage prevention", "otag", ["damage-prevention"],
     "dominant effect is PreventDamage",
     lambda F: "PreventDamage" in effs(F)),

    ("Cost reduction", "otag", ["cost-reduction"],
     "dominant static mode is ReduceCost",
     lambda F: "static:ReduceCost" in effs(F)),

    # ---- recovered from the unbranched set ------------------------------
    # Each of these was sitting unbranched until a real Scryfall slug was
    # confirmed for it; none is an invented name.
    ("Regeneration", "otag", ["regenerates-self", "regenerates-other"],
     "dominant effect is Regenerate",
     lambda F: "Regenerate" in effs(F)),

    ("Drain", "otag", ["drain-life", "drain-creature"],
     "LoseLife AND GainLife both dominant -- the pair is what makes it a drain "
     "rather than plain life loss, which has no sourced name of its own",
     lambda F: {"LoseLife", "GainLife"} <= effs(F)),

    ("Theft", "otag", ["theft-creature", "theft-permanent", "exchange-control"],
     "dominant effect is GainControl",
     lambda F: "GainControl" in effs(F)),

    ("Copy spell", "otag", ["copy-spell"],
     "dominant effect is CopySpell",
     lambda F: "CopySpell" in effs(F)),

    ("Impulse", "otag", ["impulse", "repeatable-impulse", "impulse-onto-battlefield"],
     "dominant effect is ExileTop -- exile off the top, playable from exile",
     lambda F: "ExileTop" in effs(F)),
]

# Curated / otag terms deliberately left WITHOUT a rule, and why. Reported as
# gaps rather than approximated -- see this module's docstring.
GAPS = [
    ("Token doubler", "curated (glossary.yaml function:)",
     "Needs a replacement effect that doubles a token-creation event. The one "
     "canonical example in reach, Parallel Lives, parses to an Unimplemented "
     "replacement_structure node and is excluded from the clean-parse input "
     "entirely, so there is no structure left to key on."),
    ("Toughness sweeper / mass-shrink", "otag (mass-shrink, removal-toughness)",
     "Would be PumpAll with a negative power/toughness, but the sign lives in a "
     "quantity node that is sometimes Fixed(-2), sometimes Variable('-X'), and "
     "sometimes a Ref whose sign is not decidable without evaluating it. A rule "
     "would silently miss the Ref cases and wrongly sweep in anthems, so PumpAll "
     "is left to the broad Mass effect branch only."),
    ("Equipment / Aura attachment", "otag (synergy-equipment, synergy-aura)",
     "The Attach effect is clean and dominant in 10 leaves, but Scryfall has no "
     "structural otag for 'attaches something' -- only synergy-*/vanilla-* tags "
     "about caring-about-Equipment. The NAMING gap is unchanged and no term was "
     "invented; the leaves are now carried by the flagged auto-named branch "
     "**Attach** instead of sitting in a bucket that reads as unprocessed."),
    ("Multi-removal", "otag (multi-removal)",
     "'More than one, less than all' needs a target count or a distribute field, "
     "not an effect type -- the same effect node covers one and several targets."),
    ("Single-target pump", "no sourced name",
     "The largest unbranched bloc by far (leaves 580 and 566, ~930 cards): "
     "effect Pump against SelfRef or a creature filter. Scryfall's only pump "
     "slug is `shade-pump`, which names a specific repeatable {B}: +1/+1 "
     "pattern, not pump generally, and the curated glossary has no pump term. "
     "`shade-pump` is still NOT stretched to cover it; the bloc is carried by "
     "the flagged auto-named branch **Pump** until a real name is sourced."),
    ("Sacrifice outlet", "otag (sacrifice-outlet-creature, free-sacrifice-outlet)",
     "A sac outlet is Sacrifice appearing as an activation *cost*, not as an "
     "effect. Costs are outside this pass's stated feature space (effect type + "
     "target/filter shape), and the Sacrifice *effect* already belongs to "
     "Sacrifice removal, so keying this off the effect would conflate the two."),
    ("Card selection / Dig", "no sourced name",
     "Effect Dig is dominant in 8 leaves, but Scryfall has no general "
     "'look at the top N and pick' slug -- only mechanic-specific ones. Still "
     "no sourced name; the leaves are carried by the flagged auto-named branch "
     "**Dig**."),
]


# ------------------------------------------------- auto-naming (the fallback)
# Some unbranched blocs have perfectly clean, dominant structure and simply have
# no MTG term to call them: Scryfall has no general slug for "attaches
# something" or "look at the top N and pick", and the curated glossary has no
# pump entry. The first pass therefore refused to name them, which is honest but
# leaves large blocs (Single-target pump alone is ~930 cards) sitting in a
# bucket labelled "no rule matched" -- as if they were unprocessed, when in fact
# their structure is known exactly.
#
# The fallback names them from that structure and FLAGS every one, so a
# machine-generated starting point is never mistaken for sourced vocabulary.
# The name is a plain description of what the member leaves have in common. It
# is deliberately not made to sound like a real term.

_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")


# Readability fixups for generated names. These change spelling only -- never
# which leaves a branch holds -- so they cannot affect assignment.
_SPELL = {"cant": "can't", "dont": "don't", "isnt": "isn't"}


def _words(camel):
    out = _CAMEL.sub(" ", camel).lower()
    return " ".join(_SPELL.get(w, w) for w in out.split())


def _target_phrase(shape):
    """A readable noun phrase for a target/filter shape."""
    m = re.match(r"Typed\[([A-Za-z]+)", shape)
    if m:
        noun = _words(m.group(1))
        who = shape.split("@", 1)[1].split("{", 1)[0] if "@" in shape else "Any"
        if who == "You":
            return f"your {noun}"
        if who == "Opponent":
            return f"opponent's {noun}"
        return noun
    if shape == "SelfRef":
        return "itself"
    return _words(shape.split("[", 1)[0].split("@", 1)[0])


def auto_name(sig, shared_target):
    """A functional description for one auto-named branch. Never a real term."""
    eff = sig[4:]                                     # strip "eff:"
    if eff.startswith("static:"):
        base = f"{_words(eff[7:])} static effect"
    else:
        base = _words(eff)
    if shared_target:
        base = f"{base} ({_target_phrase(shared_target)})"
    return base[:1].upper() + base[1:]


def primary_fact(F, scores):
    """The one effect fact an unnamed leaf is grouped by: its strongest."""
    cands = [f for f in F if f.startswith("eff:") and "|tgt:" not in f]
    if not cands:
        return None
    return max(cands, key=lambda f: (scores.get(f, 0.0), f))


# ------------------------------------------------------- cohesion safeguard
def load_effect_xy():
    """leaf -> (x, y) on the effect-flavoured map, for the cohesion check."""
    p = os.path.join(BUILD, "leafmap_effect.json")
    if not os.path.exists(p):
        return {}
    M = json.load(open(p, encoding="utf-8"))
    return {int(e["leaf"]): (e["x"], e["y"]) for e in M["leaves"]}


def corpus_pair_distances(XY):
    import numpy as np
    pts = np.array([XY[l] for l in sorted(XY)], dtype=float)
    n = len(pts)
    d = []
    for i in range(n - 1):
        d.append(np.hypot(*(pts[i + 1:] - pts[i]).T))
    return np.sort(np.concatenate(d)) if d else np.array([])


def cohesion(leaves, XY, corpus_sorted):
    """(tighter_than, mean_distance) for a branch, or (None, None).

    `tighter_than` is the share of all leaf pairs on the map that are FARTHER
    apart than this branch's mean -- the same statistic the map validation
    reports use, so a new rule is measured on exactly the scale Burn was.
    """
    import numpy as np
    pts = [XY[l] for l in leaves if l in XY]
    if len(pts) < 2 or not len(corpus_sorted):
        return None, None
    pts = np.array(pts, dtype=float)
    d = []
    for i in range(len(pts) - 1):
        d.append(np.hypot(*(pts[i + 1:] - pts[i]).T))
    mean = float(np.concatenate(d).mean())
    idx = int(np.searchsorted(corpus_sorted, mean))
    return 1.0 - idx / len(corpus_sorted), mean


# ---------------------------------------------------- persistent review queue
REVIEW_PATH = os.path.join(HERE, "corrections", "branch_review.json")


def load_review():
    """Decisions made in the queue UI. Hand-editable; survives rebuilds."""
    if not os.path.exists(REVIEW_PATH):
        return {}
    try:
        return json.load(open(REVIEW_PATH, encoding="utf-8")).get("decisions", {})
    except Exception:
        return {}


def save_review(decisions):
    os.makedirs(os.path.dirname(REVIEW_PATH), exist_ok=True)
    with open(REVIEW_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "_comment": "Decisions from the branch review queue. 'assign' places "
                        "the leaf in that branch (marked manual); 'reject' means "
                        "it does not belong there and the entry never returns; "
                        "'defer' keeps it queued but out of the new-items view. "
                        "Hand-editable. Keys are '<leaf>|<candidate branch>'.",
            "decisions": decisions,
        }, fh, indent=1, ensure_ascii=False)


def load_sub_branches():
    """Type sub-branches from src/sub_branches.py, if it has run.

    Carried through into branches.json so the pages need one fetch. The heavy
    `cards` list is dropped here -- the UI needs counts and names, and the full
    membership stays available in build/sub_branches.json.
    """
    p = os.path.join(BUILD, "sub_branches.json")
    if not os.path.exists(p):
        return []
    try:
        subs = json.load(open(p, encoding="utf-8")).get("sub_branches", [])
    except Exception:
        return []
    return [{k: v for k, v in s.items() if k != "cards"} for s in subs]


def load_type_audit():
    """Type-heterogeneity findings from src/audit_leaf_types.py, if it has run.

    The clustering was type-blind, so a leaf can merge a mana dork, a mana rock
    and a mana land under one "effect Mana". That is invisible to every rule
    here -- a branch rule cannot split what the clustering already merged -- so
    the finding is routed to the queue as a decision rather than acted on.

    Order of operations: this file, then audit_leaf_types.py, then this file
    again to pick the findings up. A missing file just means no type-mix
    entries, never an error.
    """
    p = os.path.join(BUILD, "type_audit.json")
    if not os.path.exists(p):
        return []
    try:
        return json.load(open(p, encoding="utf-8")).get("findings", [])
    except Exception:
        return []


# ----------------------------------------------------- auto-name rename overlay
# An auto-named branch must stay renameable without re-deriving anything. The
# derivation is keyed by the STRUCTURAL SIGNATURE, never by the display name, so
# renaming is a one-line edit here and nothing downstream has to be recomputed.
NAMES_PATH = os.path.join(HERE, "corrections", "branch_names.json")


def load_name_overrides():
    if not os.path.exists(NAMES_PATH):
        return {}
    try:
        return json.load(open(NAMES_PATH, encoding="utf-8")).get("names", {})
    except Exception:
        return {}


def main():
    CL = json.load(open(os.path.join(BUILD, "clusters.json"), encoding="utf-8"))
    rows, chunks = C.load()
    byid = {r["id"]: r for r in rows}

    leaf_members = collections.defaultdict(list)
    for cid, l in CL["cards"].items():
        if l >= 0:
            leaf_members[int(l)].append(cid)

    scores = {l: fact_scores(m, chunks, byid) for l, m in leaf_members.items()}
    leaf_facts = {l: {f for f, sc in S.items() if sc >= DOMINANT}
                  for l, S in scores.items()}
    # the same facts at the near-miss floor -- used ONLY to spot candidates for
    # the review queue, never to assign a branch
    loose_facts = {l: {f for f, sc in S.items() if sc >= NEAR_MISS}
                   for l, S in scores.items()}

    decisions = load_review()
    overrides = load_name_overrides()
    XY = load_effect_xy()
    corpus_sorted = corpus_pair_distances(XY)

    assign = collections.defaultdict(list)
    per_leaf = collections.defaultdict(list)

    # ---- layer 1: curated structural rules (unchanged in kind) -------------
    for name, src, otags, rule, pred in BRANCHES:
        for l, F in leaf_facts.items():
            try:
                if pred(F):
                    assign[name].append(l)
                    per_leaf[l].append(name)
            except Exception as exc:
                raise SystemExit(f"rule {name!r} failed on leaf {l}: {exc}")

    # ---- layer 2: manual placements already decided in the queue -----------
    manual = []
    for key, dec in sorted(decisions.items()):
        if dec.get("action") != "assign":
            continue
        head_, _, tail_ = key.partition("|")
        try:
            l = int(head_)
        except ValueError:
            continue
        bn = dec.get("branch") or tail_
        if l in leaf_members and bn and bn not in per_leaf[l]:
            assign[bn].append(l)
            per_leaf[l].append(bn)
            manual.append({"leaf": l, "branch": bn, "note": dec.get("note", "")})

    # ---- layer 3: auto-named fallback over what is still unclaimed ---------
    unclaimed = sorted(l for l in leaf_members if not per_leaf[l])
    groups = collections.defaultdict(list)
    for l in unclaimed:
        sig = primary_fact(leaf_facts[l], scores[l])
        if sig:
            groups[sig].append(l)

    auto_branches, cohesion_failures = [], []
    for sig, leaves in sorted(groups.items()):
        if len(leaves) < MIN_AUTO_LEAVES:
            continue
        # qualify the name with a target shape only when EVERY member leaf
        # shares it -- otherwise the name would describe part of the group
        eff = sig[4:]
        per = []
        for l in leaves:
            per.append({f[4:].split("|tgt:", 1)[1] for f in leaf_facts[l]
                        if f.startswith("eff:") and "|tgt:" in f
                        and f[4:].split("|tgt:", 1)[0] == eff})
        shared = set.intersection(*per) if per and all(per) else set()
        shared_t = sorted(shared)[0] if shared else None

        name = overrides.get(sig) or auto_name(sig, shared_t)
        tight, meand = cohesion(leaves, XY, corpus_sorted)
        rec = {
            "key": sig, "name": name, "auto_named": True,
            "renamed": sig in overrides,
            "target_qualifier": shared_t,
            "leaves": sorted(leaves), "n_leaves": len(leaves),
            "n_cards": sum(len(leaf_members[x]) for x in leaves),
            "cohesion": None if tight is None else round(tight, 4),
            "mean_2d": None if meand is None else round(meand, 3),
            "rule": f"fallback: dominant fact {sig} and no curated rule matched",
        }
        # ---- layer 3b: the safeguard, applied BEFORE the branch is kept ----
        if tight is not None and tight < COHESION_MIN:
            rec["why_queued"] = (
                f"cohesion {tight:.1%} is below the {COHESION_MIN:.0%} floor for "
                f"new rules -- this rule is behaving the way Burn did, so it is "
                f"routed for a decision instead of kept")
            cohesion_failures.append(rec)
            continue
        auto_branches.append(rec)
        for l in leaves:
            assign[name].append(l)
            per_leaf[l].append(name)

    # ---- layer 4: the review queue ----------------------------------------
    def resolved(k):
        # "split" is a resolution like the others: the finding was acted on by
        # building a sub-branch layer, so it must not come back on rebuild.
        return decisions.get(k, {}).get("action") in ("assign", "reject", "split")

    queue = []
    for rec in cohesion_failures:
        for l in rec["leaves"]:
            key = f"{l}|{rec['name']}"
            if resolved(key):
                continue
            queue.append({
                "key": key, "leaf": l, "kind": "cohesion",
                "placed_in": sorted(per_leaf[l]),
                "n_cards": len(leaf_members[l]),
                "label": CL["labels"].get(str(l), ""),
                "sample": sorted(CL["names"][c] for c in leaf_members[l])[:8],
                "candidates": [{"branch": rec["name"], "auto_named": True,
                                "cohesion": rec["cohesion"], "evidence": []}],
                "why": rec["why_queued"],
                "deferred": decisions.get(key, {}).get("action") == "defer",
            })

    # Scanned over EVERY leaf, not only the unplaced ones. The motivating case
    # is leaf 44: 513 cards holding the canonical mana dorks AND mana rocks
    # together, type:Creature at 44.2% and type:Artifact at 28.5%. It already
    # carries Ramp, so an unplaced-only scan skips it -- yet it is exactly the
    # borderline call a human should make. A leaf having one branch is no reason
    # to stop asking whether it deserves another.
    for l in sorted(leaf_members):
        F, L = leaf_facts[l], loose_facts[l]
        near = sorted(((round(scores[l][f], 3), f) for f in (L - F)), reverse=True)
        cands = []
        for name, src, otags, rule, pred in BRANCHES:
            try:
                if not pred(F) and pred(L) and name not in per_leaf[l]:
                    cands.append({
                        "branch": name, "auto_named": False, "cohesion": None,
                        "evidence": [{"fact": f, "score": sc} for sc, f in near[:4]],
                    })
            except Exception:
                continue
        if not cands:
            continue
        key = f"{l}|near-miss"
        if resolved(key):
            continue
        queue.append({
            "key": key, "leaf": l, "kind": "near-miss",
            "placed_in": sorted(per_leaf[l]),
            "n_cards": len(leaf_members[l]),
            "label": CL["labels"].get(str(l), ""),
            "sample": sorted(CL["names"][c] for c in leaf_members[l])[:8],
            "candidates": cands,
            "why": (f"no fact reached the {DOMINANT:.0%} dominance bar, but one or "
                    f"more reached {NEAR_MISS:.0%} and would have matched a real "
                    f"rule -- too close to decide silently"),
            "deferred": decisions.get(key, {}).get("action") == "defer",
        })

    # ---- layer 4c: type-mix findings -----------------------------------
    # Detection lives in audit_leaf_types.py; this only routes it. The `state`
    # recorded there is ignored in favour of this run's own per_leaf, so a
    # stale audit file cannot misreport where a leaf currently sits.
    for f in load_type_audit():
        l = f["leaf"]
        if l not in leaf_members:
            continue
        key = f"{l}|type-mix"
        if resolved(key):
            continue
        top = ", ".join(f"{t} {s:.0%}" for t, s in
                        list(f["shares"].items())[:4])
        tier = f.get("tier", "B")
        queue.append({
            "key": key, "leaf": l, "kind": "type-mix", "tier": tier,
            "placed_in": sorted(per_leaf[l]),
            "n_cards": f["n_cards"],
            "label": f.get("label", ""),
            "sample": f.get("sample", []),
            "type_shares": f["shares"],
            "candidates": [],
            "why": (
                f"no card type reaches the {DOMINANT:.0%} bar -- this leaf merges "
                f"{top}. The clustering was type-blind, so different kinds of "
                f"card sharing one effect became a single leaf"
                + (" (leaf 44's shape: two or more distinct PERMANENT types)"
                   if tier == "A" else
                   " (permanent vs non-permanent: same effect, different delivery)")
                + ". Splitting it means re-clustering with card type in the "
                  "feature set, which would invalidate every leaf id, branch, "
                  "map and sector -- so it is a decision, not a fix."),
            "deferred": decisions.get(key, {}).get("action") == "defer",
        })

    queued_leaves = {q["leaf"] for q in queue}
    # A queued leaf may already be placed (see leaf 44). The four coverage
    # states below are about PLACEMENT and stay mutually exclusive; the queue is
    # a separate axis that can touch any of them, and is counted separately so
    # the four never double-count.
    unplaced_queued = {l for l in queued_leaves if not per_leaf[l]}
    queued_on_placed = sorted(queued_leaves - unplaced_queued)

    # ---- layer 5: Unique effect, a finding rather than a remainder ---------
    unique = sorted(l for l in leaf_members
                    if not per_leaf[l] and l not in unplaced_queued)

    # ---------------------------------------------------------------- output
    curated_out = [
        {"name": name, "source": src, "otags": otags, "rule": rule,
         "auto_named": False,
         "leaves": sorted(assign[name]), "n_leaves": len(assign[name]),
         "n_cards": sum(len(leaf_members[l]) for l in assign[name])}
        for name, src, otags, rule, _ in BRANCHES
    ]
    auto_out = [
        {"name": r["name"], "source": "auto-named (machine-generated)",
         "otags": [], "rule": r["rule"], "auto_named": True,
         "key": r["key"], "renamed": r["renamed"],
         "cohesion": r["cohesion"], "mean_2d": r["mean_2d"],
         "leaves": r["leaves"], "n_leaves": r["n_leaves"], "n_cards": r["n_cards"]}
        for r in auto_branches
    ]

    def cards_of(leaves):
        return sum(len(leaf_members[l]) for l in leaves)

    real_leaves = sorted({l for b in curated_out for l in b["leaves"]})
    auto_leaves = sorted({l for b in auto_out for l in b["leaves"]})
    coverage = {
        "real_branches": {"leaves": len(real_leaves), "cards": cards_of(real_leaves)},
        "auto_named": {"leaves": len(auto_leaves), "cards": cards_of(auto_leaves)},
        "review_queue": {"leaves": len(unplaced_queued),
                         "cards": cards_of(sorted(unplaced_queued))},
        "unique_effect": {"leaves": len(unique), "cards": cards_of(unique)},
        "total_leaves": len(leaf_members),
        "total_cards": sum(len(m) for m in leaf_members.values()),
        # separate axis, deliberately NOT part of the exclusive four
        "open_questions_on_placed_leaves": {
            "leaves": len(queued_on_placed),
            "cards": cards_of(queued_on_placed)},
    }

    out = {
        "source_clusters": "build/clusters.json",
        "dominant_threshold": DOMINANT,
        "near_miss_threshold": NEAR_MISS,
        "cohesion_min": COHESION_MIN,
        "min_auto_leaves": MIN_AUTO_LEAVES,
        "n_leaves": len(leaf_members),
        "branches": curated_out + auto_out,
        "auto_branches": auto_out,
        "manual_assignments": manual,
        "review_queue": sorted(queue, key=lambda q: -q["n_cards"]),
        "cohesion_failures": cohesion_failures,
        "unique_effect": [
            {"leaf": l, "n_cards": len(leaf_members[l]),
             "label": CL["labels"].get(str(l), ""),
             "sample": sorted(CL["names"][c] for c in leaf_members[l])[:6]}
            for l in unique
        ],
        "coverage": coverage,
        "gaps": [{"name": n, "source": s_, "why": w} for n, s_, w in GAPS],
        "leaf_branches": {str(l): sorted(v) for l, v in per_leaf.items()},
        "auto_branch_names": {r["key"]: r["name"] for r in auto_branches},
        "leaf_sizes": {str(l): len(m) for l, m in leaf_members.items()},
        # Additive card-level drill-down from src/sub_branches.py. Parents keep
        # their full card set; this never replaces a branch.
        "sub_branches": load_sub_branches(),
    }
    with open(os.path.join(BUILD, "branches.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"), ensure_ascii=False)

    if not os.path.exists(REVIEW_PATH):
        save_review(decisions)

    write_report(os.path.join(REPORTS, "branches.md"), out, leaf_members, CL)

    print(json.dumps({
        "leaves": len(leaf_members),
        "curated_branches_with_leaves": len([b for b in curated_out if b["n_leaves"]]),
        "auto_named_branches": len(auto_out),
        "auto_rejected_by_cohesion": len(cohesion_failures),
        "review_queue_entries": len(queue),
        "type_mix_entries": len([q for q in queue if q["kind"] == "type-mix"]),
        "queued_leaves_already_placed": len(queued_on_placed),
        "manual_assignments": len(manual),
        "coverage": coverage,
    }, indent=1))


def write_report(path, out, leaf_members, CL):
    L = []
    A = L.append
    cov = out["coverage"]
    A("# Branch assignment over the structural leaves\n")
    A("Branches are assigned by **structural rule only** -- a closed list of named "
      "predicates over each leaf's dominant effect types, target/filter shapes and "
      "card types. No card-tag membership voting: Scryfall's tags supply "
      "*vocabulary*, never assignment. The 591 leaves from "
      "[clustering-structural.md](clustering-structural.md) are read as given and "
      "not re-clustered.\n")
    A("Generated by `src/branch_leaves.py`.\n")
    A(f"A fact counts as *dominant* for a leaf when it holds for "
      f"**>= {int(out['dominant_threshold']*100)}%** of that leaf's cards.\n")

    A("## Coverage\n")
    A("Every leaf lands in exactly one of four states. None of them means "
      "'unprocessed'.\n")
    A("| state | leaves | cards | what it means |")
    A("|---|---|---|---|")
    A(f"| **Real branches** | {cov['real_branches']['leaves']} | "
      f"{cov['real_branches']['cards']:,} | placed by a curated rule, named from "
      f"sourced vocabulary |")
    A(f"| **Auto-named (flagged)** | {cov['auto_named']['leaves']} | "
      f"{cov['auto_named']['cards']:,} | clean shared structure, machine-generated "
      f"name, always badged |")
    A(f"| **Review queue** | {cov['review_queue']['leaves']} | "
      f"{cov['review_queue']['cards']:,} | genuinely uncertain, awaiting a human "
      f"decision |")
    A(f"| **Unique effect** | {cov['unique_effect']['leaves']} | "
      f"{cov['unique_effect']['cards']:,} | structure shared with no other leaf -- "
      f"a finding, not a gap |")
    A(f"| total | {cov['total_leaves']} | {cov['total_cards']:,} | |")
    A("")
    A("The four states are mutually exclusive and sum to the total: the "
      "auto-named fallback only ever claims leaves that no curated rule "
      "matched. Branch assignment is still many-to-many WITHIN a state, so the "
      "per-branch card counts further down sum to more than the corpus.\n")

    A("## The feature extension: card types\n")
    A("Mana dork and Mana rock were refused by the first pass for one stated "
      "reason -- both are effect `Mana`, and the discriminator is the *type line*, "
      "which was outside the effect-and-target feature space. The space now also "
      "carries `type:<CoreType>` facts, drawn from `card_type.core_types` in the "
      "upstream export. Nothing else changed, and no pre-existing rule reads "
      "`type:`, so no previously-assigned leaf moved because of this.\n")

    A("## Branches and their rules\n")
    A("| branch | source | otag slugs | rule (structural) | leaves | cards |")
    A("|---|---|---|---|---|---|")
    for b in out["branches"]:
        badge = " `AUTO`" if b.get("auto_named") else ""
        A(f"| **{b['name']}**{badge} | {b['source']} | "
          f"{', '.join('`'+o+'`' for o in b['otags'])} | {b['rule']} | "
          f"{b['n_leaves']} | {b['n_cards']:,} |")
    A("")
    empty = [b["name"] for b in out["branches"] if not b["n_leaves"]]
    if empty:
        A(f"**Defined but matched zero leaves:** {', '.join(empty)}. The rule is "
          "kept rather than deleted: the effect exists in the corpus but is never "
          "dominant in any leaf, which is itself the finding.\n")

    A("## Leaves per branch")
    A("")
    A("| branch | auto | leaves | cards |")
    A("|---|---|---|---|")
    for b in sorted(out["branches"], key=lambda x: -x["n_leaves"]):
        if b["n_leaves"]:
            A(f"| {b['name']} | {'yes' if b.get('auto_named') else ''} | "
              f"{b['n_leaves']} | {b['n_cards']:,} |")
    A("")
    counts = [b["n_leaves"] for b in out["branches"] if b["n_leaves"]]
    A(f"{len(counts)} branches hold at least one leaf; largest {max(counts)} "
      f"leaves, median {sorted(counts)[len(counts)//2]}, smallest {min(counts)}.")
    A("")
    multi = collections.Counter(len(v) for v in out["leaf_branches"].values() if v)
    A("Branches per leaf (assignment is many-to-many):")
    A("")
    A("| branches on one leaf | leaves |")
    A("|---|---|")
    A(f"| 0 (Unique effect, or queued and unplaced) | "
      f"{cov['unique_effect']['leaves'] + cov['review_queue']['leaves']} |")
    for k in sorted(multi):
        A(f"| {k} | {multi[k]} |")
    A("")

    A("## Auto-named branches\n")
    A("These have clean, dominant, shared structure and **no sourced MTG term**. "
      "Rather than leave large blocs looking unprocessed, the name is generated "
      "from the structure itself and flagged everywhere it appears. An auto name "
      "is a starting point for a human, never a claim that the term is real.\n")
    A(f"A group needs **>= {out['min_auto_leaves']} leaves** to qualify: 'shared "
      "functional identity' is a claim about more than one leaf. A lone leaf that "
      "fits nowhere is a Unique effect instead.\n")
    A("Renaming one is a one-line edit in `corrections/branch_names.json`, keyed "
      "by the **structural signature** and not the display name -- so a rename "
      "re-derives nothing.\n")
    if out["auto_branches"]:
        A("| auto name | signature | leaves | cards | cohesion | renamed |")
        A("|---|---|---|---|---|---|")
        for b in out["auto_branches"]:
            coh = "n/a" if b["cohesion"] is None else f"{b['cohesion']:.1%}"
            A(f"| **{b['name']}** | `{b['key']}` | {b['n_leaves']} | "
              f"{b['n_cards']:,} | {coh} | {'yes' if b['renamed'] else 'no'} |")
        A("")
    else:
        A("*None qualified.*\n")

    if out["cohesion_failures"]:
        A("### Auto-name candidates rejected by the cohesion safeguard\n")
        A(f"Every new / loosened / auto-named rule is measured on the "
          f"effect-flavoured map before it is kept. The floor is "
          f"**{int(out['cohesion_min']*100)}%** 'tighter than all leaf pairs', set "
          f"just above the band where the Burn defect (52%) and the weakest "
          f"surviving branches (57-58%) sit. A candidate below it is not silently "
          f"kept and not silently dropped -- it goes to the queue.\n")
        A("| candidate | leaves | cards | cohesion | outcome |")
        A("|---|---|---|---|---|")
        for r in out["cohesion_failures"]:
            coh = "n/a" if r["cohesion"] is None else f"{r['cohesion']:.1%}"
            A(f"| {r['name']} | {r['n_leaves']} | {r['n_cards']:,} | {coh} | "
              f"routed to review queue |")
        A("")

    A("## Review queue\n")
    A("A **persistent, browsable** list -- not a prompt that blocks a build. It "
      "holds the cases a rule should not decide alone, and it is read back on "
      "every rebuild so a resolved entry never returns.\n")
    A(f"- **near miss** -- no fact reached {int(out['dominant_threshold']*100)}%, "
      f"but one reached {int(out['near_miss_threshold']*100)}% and would have "
      f"matched a real rule")
    A(f"- **type-mix** -- the leaf merges different card types; the clustering "
      f"was type-blind, so a branch rule cannot separate them "
      f"(see [leaf-type-audit.md](leaf-type-audit.md))")
    A("- **cohesion** -- an auto-named candidate that scored below the floor\n")
    A(f"**{len(out['review_queue'])} entries** awaiting a decision, covering "
      f"{cov['review_queue']['cards']:,} cards. Browse and resolve them at "
      "[review-queue.html](review-queue.html); decisions are written to "
      "`corrections/branch_review.json`.\n")
    if out["review_queue"]:
        A("| leaf | cards | kind | top candidate | dominant structure |")
        A("|---|---|---|---|---|")
        for q in out["review_queue"][:25]:
            top = q["candidates"][0]["branch"] if q["candidates"] else "--"
            A(f"| {q['leaf']} | {q['n_cards']} | {q['kind']} | {top} | "
              f"`{q['label'][:46]}` |")
        if len(out["review_queue"]) > 25:
            A(f"\n*...and {len(out['review_queue'])-25} more, in the UI.*")
        A("")
    if out["manual_assignments"]:
        A(f"**{len(out['manual_assignments'])} manual placements** have been made "
          "from the queue and are live in the branch table above.\n")

    A("## Unique effect\n")
    A(f"**{cov['unique_effect']['leaves']} leaves**, "
      f"{cov['unique_effect']['cards']:,} cards. This is the terminal bucket, and "
      "it replaces 'unbranched' / 'uncategorized'. It is a **positive finding**: "
      "after the curated rules, the auto-named fallback and the review queue, "
      "these leaves' structure is not shared with the rest of the corpus. Nothing "
      "is pending on them.\n")
    A("| leaf | cards | dominant structure | sample cards |")
    A("|---|---|---|---|")
    for u in sorted(out["unique_effect"], key=lambda x: -x["n_cards"])[:40]:
        A(f"| {u['leaf']} | {u['n_cards']} | `{u['label'][:70]}` | "
          f"{', '.join(u['sample'][:4])} |")
    A("")

    A("## Gaps: terms deliberately left unruled\n")
    A("Curated or otag terms that exist in the vocabulary but have no clean "
      "structural signal. A weak rule here would mislabel leaves silently, which "
      "is worse than an honest gap.\n")
    A("Three of these were blocked *only* by the lack of a sourced name, and "
      "are now carried by flagged auto-named branches. The naming gap is "
      "unchanged and is still recorded here -- what changed is that those "
      "leaves no longer sit in a bucket that reads as unprocessed.")
    A("")
    for g in out["gaps"]:
        A(f"- **{g['name']}** ({g['source']}) - {g['why']}")
    A("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


if __name__ == "__main__":
    main()
