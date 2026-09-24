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


def facts_for_leaf(members, chunks, byid):
    """Dominant structural facts for one leaf.

    Facts are flat strings so every predicate below is plain set membership:
        eff:<Type>              a top-level effect type
        tgt:<shape>             a target/filter shape
        eff:<Type>|tgt:<shape>  the two bound together
        cz:<origin>><dest>      a ChangeZone's zone transition
        ctrl:<Type>@<who>       a mass effect's target controller scope
        mod:<tag>               a static Continuous modification
        mill:<shape>            who a Mill effect points at
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
        counts.update(seen)

    n = len(members)
    return {f for f, c in counts.items() if c / n >= DOMINANT}


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
    ("Mana dork", "curated (glossary.yaml function:)",
     "Structurally identical to Ramp at the effect level (effect Mana). The "
     "distinguishing fact is the card's *type line* being a creature, which is "
     "not an effect-type or target-filter fact, so it is outside this pass's "
     "stated feature space."),
    ("Mana rock", "curated (glossary.yaml function:)",
     "Same as Mana dork: the discriminator is an artifact type line, not an "
     "effect or target shape."),
    ("Toughness sweeper / mass-shrink", "otag (mass-shrink, removal-toughness)",
     "Would be PumpAll with a negative power/toughness, but the sign lives in a "
     "quantity node that is sometimes Fixed(-2), sometimes Variable('-X'), and "
     "sometimes a Ref whose sign is not decidable without evaluating it. A rule "
     "would silently miss the Ref cases and wrongly sweep in anthems, so PumpAll "
     "is left to the broad Mass effect branch only."),
    ("Equipment / Aura attachment", "otag (synergy-equipment, synergy-aura)",
     "The Attach effect is clean and dominant in 10 leaves, but Scryfall has no "
     "structural otag for 'attaches something' -- only synergy-*/vanilla-* tags "
     "about caring-about-Equipment. No sourced name exists, so no branch was "
     "invented for it."),
    ("Multi-removal", "otag (multi-removal)",
     "'More than one, less than all' needs a target count or a distribute field, "
     "not an effect type -- the same effect node covers one and several targets."),
    ("Single-target pump", "no sourced name",
     "The largest unbranched bloc by far (leaves 580 and 566, ~930 cards): "
     "effect Pump against SelfRef or a creature filter. Scryfall's only pump "
     "slug is `shade-pump`, which names a specific repeatable {B}: +1/+1 "
     "pattern, not pump generally, and the curated glossary has no pump term. "
     "Rather than stretch `shade-pump` to cover all of it, this stays "
     "unbranched until a name is sourced."),
    ("Sacrifice outlet", "otag (sacrifice-outlet-creature, free-sacrifice-outlet)",
     "A sac outlet is Sacrifice appearing as an activation *cost*, not as an "
     "effect. Costs are outside this pass's stated feature space (effect type + "
     "target/filter shape), and the Sacrifice *effect* already belongs to "
     "Sacrifice removal, so keying this off the effect would conflate the two."),
    ("Card selection / Dig", "no sourced name",
     "Effect Dig is dominant in 8 leaves, but Scryfall has no general "
     "'look at the top N and pick' slug -- only mechanic-specific ones. No "
     "sourced name, so no branch."),
]


def main():
    CL = json.load(open(os.path.join(BUILD, "clusters.json"), encoding="utf-8"))
    rows, chunks = C.load()
    byid = {r["id"]: r for r in rows}

    leaf_members = collections.defaultdict(list)
    for cid, l in CL["cards"].items():
        if l >= 0:
            leaf_members[int(l)].append(cid)

    leaf_facts = {l: facts_for_leaf(m, chunks, byid) for l, m in leaf_members.items()}

    # many-to-many assignment
    assign = collections.defaultdict(list)   # branch -> [leaf]
    per_leaf = collections.defaultdict(list)  # leaf -> [branch]
    for name, src, otags, rule, pred in BRANCHES:
        for l, F in leaf_facts.items():
            try:
                if pred(F):
                    assign[name].append(l)
                    per_leaf[l].append(name)
            except Exception as exc:                      # a rule must never
                raise SystemExit(f"rule {name!r} failed on leaf {l}: {exc}")

    unbranched = sorted(l for l in leaf_members if not per_leaf[l])

    out = {
        "source_clusters": "build/clusters.json",
        "dominant_threshold": DOMINANT,
        "n_leaves": len(leaf_members),
        "branches": [
            {
                "name": name, "source": src, "otags": otags, "rule": rule,
                "leaves": sorted(assign[name]),
                "n_leaves": len(assign[name]),
                "n_cards": sum(len(leaf_members[l]) for l in assign[name]),
            }
            for name, src, otags, rule, _ in BRANCHES
        ],
        "gaps": [{"name": n, "source": s, "why": w} for n, s, w in GAPS],
        "leaf_branches": {str(l): sorted(v) for l, v in per_leaf.items()},
        "unbranched": [
            {"leaf": l, "n_cards": len(leaf_members[l]),
             "label": CL["labels"].get(str(l), ""),
             "sample": sorted(CL["names"][c] for c in leaf_members[l])[:6]}
            for l in unbranched
        ],
        "leaf_sizes": {str(l): len(m) for l, m in leaf_members.items()},
    }
    with open(os.path.join(BUILD, "branches.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"), ensure_ascii=False)

    write_report(os.path.join(REPORTS, "branches.md"), out, leaf_members, CL)

    nonempty = [b for b in out["branches"] if b["n_leaves"]]
    print(json.dumps({
        "leaves": len(leaf_members),
        "branches_defined": len(BRANCHES),
        "branches_with_leaves": len(nonempty),
        "branches_empty": [b["name"] for b in out["branches"] if not b["n_leaves"]],
        "unbranched_leaves": len(unbranched),
        "unbranched_cards": sum(len(leaf_members[l]) for l in unbranched),
        "gaps": len(GAPS),
    }, indent=1))


def write_report(path, out, leaf_members, CL):
    L, A = [], None
    A = L.append
    A("# Branch assignment over the structural leaves\n")
    A("Branches are assigned by **structural rule only** -- a closed list of named "
      "predicates over each leaf's dominant effect types and target/filter shapes. "
      "No card-tag membership voting: Scryfall's tags supply *vocabulary*, never "
      "assignment. The 591 leaves from "
      "[clustering-structural.md](clustering-structural.md) are read as given and "
      "not re-clustered.\n")
    A("Generated by `src/branch_leaves.py`. Rule pattern follows the zone "
      "classifier (`src/classify_zones.py` in the parent experiment): closed, "
      "named, auditable, no model.\n")
    A(f"A fact counts as *dominant* for a leaf when it holds for "
      f"**>= {int(out['dominant_threshold']*100)}%** of that leaf's cards.\n")

    A("## Vocabulary sources\n")
    A("No branch name is invented. Every one traces to:\n")
    A("| source | file | what it gave |")
    A("|---|---|---|")
    A("| `curated` | `card_function_search_v0.2/src/mtg_query/glossary.yaml` "
      "`function:` | 10 canonical function entries, each already carrying its "
      "Scryfall otag slugs |")
    A("| `otag` | `card_function_search_v0.2/data/otag_glossary_scryfall.yaml` | "
      "1,105 Scryfall oracle-tag slugs |")
    A("| `slang` | `mtg-search-v0/data/glossary.yaml` | 10 slang function terms |")
    A("")

    A("## Branches and their rules\n")
    A("| branch | source | otag slugs | rule (structural) | leaves | cards |")
    A("|---|---|---|---|---|---|")
    for b in out["branches"]:
        A(f"| **{b['name']}** | {b['source']} | "
          f"{', '.join('`'+o+'`' for o in b['otags'])} | {b['rule']} | "
          f"{b['n_leaves']} | {b['n_cards']:,} |")
    A("")
    empty = [b["name"] for b in out["branches"] if not b["n_leaves"]]
    if empty:
        A(f"**Defined but matched zero leaves:** {', '.join(empty)}. The rule is "
          "kept rather than deleted: the effect exists in the corpus but is never "
          "dominant in any leaf, which is itself the finding.\n")

    A("## Leaves per branch\n")
    A("| branch | leaves | cards |")
    A("|---|---|---|")
    for b in sorted(out["branches"], key=lambda x: -x["n_leaves"]):
        if b["n_leaves"]:
            A(f"| {b['name']} | {b['n_leaves']} | {b['n_cards']:,} |")
    A("")
    counts = [b["n_leaves"] for b in out["branches"] if b["n_leaves"]]
    A(f"{len(counts)} branches hold at least one leaf; "
      f"largest {max(counts)} leaves, median {sorted(counts)[len(counts)//2]}, "
      f"smallest {min(counts)}.\n")
    multi = collections.Counter(len(v) for v in out["leaf_branches"].values() if v)
    A("Branches per leaf (assignment is many-to-many):\n")
    A("| branches on one leaf | leaves |")
    A("|---|---|")
    A(f"| 0 (unbranched) | {len(out['unbranched'])} |")
    for k in sorted(multi):
        A(f"| {k} | {multi[k]} |")
    A("")

    A("## Unbranched leaves\n")
    A(f"**{len(out['unbranched'])} of {out['n_leaves']} leaves matched no rule**, "
      f"covering {sum(u['n_cards'] for u in out['unbranched']):,} cards. Kept "
      "visible here and as a top-level entry in the tree UI, not dropped.\n")
    A("| leaf | cards | dominant structure | sample cards |")
    A("|---|---|---|---|")
    for u in sorted(out["unbranched"], key=lambda x: -x["n_cards"]):
        A(f"| {u['leaf']} | {u['n_cards']} | `{u['label'][:70]}` | "
          f"{', '.join(u['sample'][:4])} |")
    A("")

    A("## Gaps: terms deliberately left unruled\n")
    A("Curated or otag terms that exist in the vocabulary but have no clean "
      "structural signal. A weak rule here would mislabel leaves silently, which "
      "is worse than an honest gap.\n")
    for g in out["gaps"]:
        A(f"- **{g['name']}** ({g['source']}) — {g['why']}")
    A("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


if __name__ == "__main__":
    main()
