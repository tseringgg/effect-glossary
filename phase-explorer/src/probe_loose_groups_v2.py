#!/usr/bin/env python3
"""Part 1 of the loose-groups build: the revised split (more fields), the revised names, the recount, the catch-all reads. Investigation only: it builds nothing
that the browse page reads and changes nothing frozen. Output: build/loose_groups_probe_v2.json.

    LOOSE_CACHE=<pickle> LOOSE_RAW=<pickle> python src/probe_loose_groups_v2.py

LOOSE_CACHE is the scratch collection of probe_loose_groups.py; LOOSE_RAW adds, for each of the same abilities, the block the ability came from
(ability / trigger / replacement / static), the trigger mode and the parsed effect (all already in the parse; no text matching).

Seed 20261019, declared before any computation, draws the 20 members read from each large or catch-all group.
"""
import collections
import io
import json
import os
import pickle
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_loose_groups as P

HERE = P.HERE
BUILD = P.BUILD
SEED_READS = 20261019
CAP = 8

# ------------------------------------------------------------------ field values (all read from parse fields)
TRIGGER_WORDS = {"Phase": "at the beginning of a phase", "ChangesZone": "when a card moves between zones", "Attacks": "when a creature attacks", "YouAttack": "when you attack",
                 "SpellCast": "when a spell is cast", "DamageDone": "when damage is dealt", "CounterAdded": "when counters are added", "Unknown": "on another kind of trigger"}
TYPE_WORDS = {"Creature": "creature", "Artifact": "artifact", "Enchantment": "enchantment", "Land": "land", "Planeswalker": "planeswalker", "Permanent": "permanent",
              "Card": "card", "Instant": "instant", "Sorcery": "sorcery", "Battle": "battle"}


def types_of(o):
    """object string such as 'Creature|Planeswalker' or 'Non:Land+Permanent' -> 'creature or planeswalker' / 'nonland permanent' (the parse's own type list)."""
    o = o.split("/spell:")[0]
    parts = [p for p in o.split("|") if p]
    out = []
    for p in parts:
        w = []
        for q in p.split("+"):
            if q.startswith("Non:"):
                w.append("non" + q[4:].lower())
            elif q in TYPE_WORDS:
                w.append(TYPE_WORDS[q])
            elif q:
                w.append(q.lower())
        if w:
            nonparts = [x for x in w if x.startswith("non")]
            rest = [x for x in w if not x.startswith("non")]
            out.append(" ".join(nonparts + rest))
    seen = []
    for x in out:
        if x not in seen:
            seen.append(x)
    if not seen:
        return ""
    if len(seen) > 3:
        return "several types"
    return " or ".join(seen)


def objc2(f):
    """what the effect acts on, keeping a type list ('creature or planeswalker') instead of cutting it at the first type."""
    o = f["obj"]
    if o in ("", "-"):
        return ""
    base = P.objc(f)
    if f["ftype"] == "SearchLibrary" and base == "any target":
        return ""        # the parse did not say what is searched for; "any target" is not an answer to that
    if o in ("self", "player", "you", "triggering player", "defending player", "any target", "parent", "TrackedSet", "object") or "[" in o:
        return base
    t = types_of(o)
    if "Another" in (f.get("props") or ""):
        t = "another " + t if t else t
    return t or base


def ctr_class(f):
    c = f["ctr"]
    if c == "":
        return ""
    if c in ("p1p1", "m1m1"):
        return c
    if re.match(r"^(additional )?[+-]\d+/[+-]\d+$", c):
        return "power/toughness kinds"
    return c


def sact(f):
    """what is sacrificed, from the parsed object."""
    o = f["obj"]
    if o in ("", "-"):
        return ""
    if o == "self":
        return "this permanent"
    if o in ("parent", "TrackedSet", "any target", "object"):
        return "the thing chosen before"
    return objc2(f)


def cpk(f):
    o = f["obj"]
    if f["ftype"] == "BecomeCopy":
        return "of " + (art(objc2(f)) if o not in ("parent", "TrackedSet", "object") else "the thing chosen before")
    if o in ("parent", "TrackedSet"):
        return "chosen before"
    if o == "self":
        return "itself"
    return art(objc2(f)) or "something"


def when(info):
    b, m = info
    if b == "replacements":
        return "replacing an event"
    if b == "triggers":
        mt = m.get("type") if isinstance(m, dict) else m
        return "trigger:" + str(mt)
    if b == "static_abilities":
        return ""
    return "spell or activated ability"


FIELDS = dict(P.FIELDS)
# ordered most to least important: a group of fewer than 10 cards drops its LAST field first (the main tree's own rarest-field-first backoff)
FIELDS.update({
    "Zone change": ["to", "frm", "ctrl", "mass"],
    "Counters": ["ctrc", "objc", "mass"],
    "Library": ["to", "who"],
    "Damage": ["objc2", "mass"],
    "Destroy": ["objc2", "mass"],
    "Sacrifice": ["sact", "who", "mass"],
    "Copy": ["cpk", "then"],
    "Cast / play": ["castmode", "free"],
})
# a group of more than 50 cards is split once more by these fields, in order; only parts of 10 or more cards become groups of their own
REFINE = {"Zone change": ["objc2", "when"], "Counters": ["when"], "Card draw": ["when"], "Tokens": ["when"], "Library": ["objc2", "when"], "Damage": ["when"]}
REFINE_OVER = 50
MINGROUP = 10
DEFAULT_FIELDS = ["objc"]


def field_values(f, n, info, raw):
    out = {}
    out["frm"] = f["frm"]
    out["to"] = f["to"]
    out["sign"] = f["sign"] if f["sign"] not in ("", "-") else ""
    out["ctrl"] = P.FV["ctrl"](f)
    out["mass"] = P.FV["mass"](f)
    out["who"] = P.FV["who"](f)
    out["objc"] = P.objc(f)
    out["objc2"] = objc2(f)
    out["grant"] = P.grant(f)
    out["kw"] = P.FV["kw"](f)
    out["obj"] = P.FV["obj"](f)
    out["ctr"] = f["ctr"]
    out["ctrc"] = ctr_class(f)
    out["sact"] = sact(f)
    out["cpk"] = cpk(f)
    out["then"] = "then cast it" if f["chain"].split(">")[0].startswith("CastFromZone") else ""
    e = raw[n] or {}
    out["castmode"] = {"Cast": "cast", "Play": "play"}.get(e.get("mode"), "") if f["ftype"] == "CastFromZone" else ""
    out["free"] = "free" if (f["ftype"] == "CastFromZone" and e.get("without_paying_mana_cost")) else ""
    out["when"] = when(info[n])
    return out


def build_keys(use_idx, items, info, raw):
    """key per ability: (family, effect type, ((field, value), ...)). Backoff: abilities whose full key has fewer than MINGROUP cards drop the last field, and so on
    down to the effect type alone. Refinement: a group of more than REFINE_OVER cards is split by the REFINE fields."""
    vals = {n: field_values(items[n]["f"], n, info, raw) for n in use_idx}
    fl = {n: FIELDS.get(items[n]["f"]["fam"], DEFAULT_FIELDS) for n in use_idx}
    full = {n: (items[n]["f"]["fam"], items[n]["f"]["ftype"]) for n in use_idx}
    key = {}
    left = set(use_idx)
    for L in range(max(len(v) for v in fl.values()), -1, -1):
        cards = collections.defaultdict(set)
        for n in left:
            fs = fl[n]
            if L > len(fs):
                continue
            cards[full[n] + (tuple((k, vals[n][k]) for k in fs[:L]), (len(fs), L))].add(items[n]["oid"])
        done = []
        for n in left:
            fs = fl[n]
            if L > len(fs):
                continue
            kk = full[n] + (tuple((k, vals[n][k]) for k in fs[:L]), (len(fs), L))
            if len(cards[kk]) >= MINGROUP or L == 0:
                key[n] = kk
                done.append(n)
        left -= set(done)
    # refinement of big groups
    bygroup = collections.defaultdict(list)
    for n, k in key.items():
        bygroup[k].append(n)
    final = {}
    for k, ns in bygroup.items():
        fam = k[0]
        ncards = len({items[n]["oid"] for n in ns})
        parts = {n: k[2] for n in ns}
        if ncards > REFINE_OVER and fam in REFINE:
            for fld in REFINE[fam]:
                grp = collections.defaultdict(list)
                for n in ns:
                    grp[parts[n]].append(n)
                for pk, pns in grp.items():
                    if len({items[n]["oid"] for n in pns}) <= REFINE_OVER:
                        continue
                    byv = collections.defaultdict(set)
                    for n in pns:
                        byv[vals[n][fld]].add(items[n]["oid"])
                    for n in pns:
                        v = vals[n][fld]
                        if v != "" and len(byv[v]) >= MINGROUP:
                            parts[n] = pk + ((fld, v),)
        for n in ns:
            final[n] = (k[0], k[1], parts[n], k[3])
    return [final[n] for n in use_idx]


# ------------------------------------------------------------------ names: fixed wording per field value
ZONE = {"Graveyard": "the graveyard", "Hand": "hand", "Library": "the library", "Battlefield": "the battlefield", "Exile": "exile", "Stack": "the stack", "Command": "the command zone"}
CTRW = {"p1p1": "+1/+1", "m1m1": "-1/-1", "power/toughness kinds": "power/toughness"}
TRIGW = {"trigger:" + k: v for k, v in TRIGGER_WORDS.items()}


def art(n):
    if not n:
        return ""
    if n in ("this permanent", "any target", "the same object", "something", "the thing chosen before", "several types", "a player") or n.startswith(("enchanted", "equipped")):
        return n
    return ("an " if n[0] in "aeiou" else "a ") + n


def whenw(v):
    if v in ("trigger:None", "trigger:Unknown"):
        return "on another kind of trigger"
    return {"replacing an event": "through a replacement effect", "spell or activated ability": "from a spell or activated ability"}.get(v, TRIGW.get(v, v))


EFFECT = {
    "ChangeZone": "Move cards between zones, uncommon cases", "Draw": "Draw cards, uncommon cases", "CastFromZone": "Cast a card, uncommon cases", "Attach": "Attach, uncommon cases",
    "DealDamage": "Deal damage, uncommon cases", "Damage": "Deal damage to many things at once", "GainLife": "Gain life, uncommon cases",
    "Connive": "Connive", "ReduceNextSpellCost": "Make the next spell cost less", "GrantCastingPermission": "Allow casting a card",
    "Choose": "Make a choice", "TargetOnly": "Choose a target", "ChooseFromZone": "Choose a card from a zone", "PayCost": "Pay a cost", "Modal": "A card with several modes",
    "Goad": "Goad a creature", "RemoveFromCombat": "Remove a creature from combat", "AdditionalCombatPhase": "Add a combat phase", "ForceBlock": "Force a creature to block",
    "ExchangeControl": "Exchange control of permanents", "ControlNextTurn": "Control a player's next turn", "ChangeTargets": "Change the target of a spell or ability",
    "Fight": "Make creatures fight", "DamageEachPlayer": "Deal damage to each player", "Discard": "Discard cards", "RevealHand": "Reveal a hand",
    "FlipCoin": "Flip a coin", "RollDie": "Roll a die", "WinTheGame": "Win the game", "LoseTheGame": "Lose the game", "ExtraTurn": "Take an extra turn", "CollectEvidence": "Collect evidence",
    "FlipCoinUntilLose": "Flip coins until you lose a flip", "Suspect": "Suspect a creature", "RingTemptsYou": "The Ring tempts you", "CreateEmblem": "Get an emblem", "BecomeMonarch": "Become the monarch",
    "VentureIntoDungeon": "Venture into the dungeon", "GiftDelivery": "Promise a gift", "AddRestriction": "Add a restriction", "FlipCoins": "Flip coins", "SkipNextTurn": "Skip a turn",
    "RuntimeHandled": "A rule the game engine runs itself", "Dig": "Look at the top cards of a library", "RevealTop": "Reveal the top cards of a library", "ExileTop": "Exile the top cards of a library",
    "RevealUntil": "Reveal cards until a match", "Scry": "Scry", "Seek": "Seek a card", "Surveil": "Surveil", "ExileFromTopUntil": "Exile cards from the top until a match", "Conjure": "Conjure a card",
    "Explore": "Explore", "Discover": "Discover", "LoseLife": "Lose life", "GainLife": "Gain life", "SetLifeTotal": "Set a life total", "Regenerate": "Regenerate", "PreventDamage": "Prevent damage",
    "DoublePT": "Double power and toughness", "BlightEffect": "Blight", "SwitchPT": "Switch power and toughness", "ChooseAndSacrificeRest": "Choose permanents to keep, sacrifice the rest",
    "static:ReduceCost": "Spells cost less", "static:RaiseCost": "Spells cost more", "static:Panharmonicon": "Triggers an extra time", "static:GraveyardCastPermission": "Cast cards from a graveyard",
    "static:CastWithKeyword": "Cast spells with an added ability", "static:Other": "Other rule changes", "static:Shroud": "Has shroud", "static:CastFromHandFree": "Cast from hand without paying",
    "static:ReduceAbilityCost": "Abilities cost less", "static:CastWithFlash": "Cast as though it had flash", "static:PerTurnDrawLimit": "Limit cards drawn each turn",
    "static:MaximumHandSize": "Change the maximum hand size", "static:PerTurnCastLimit": "Limit spells cast each turn", "static:AdditionalLandDrop": "Play additional lands",
    "static:NoMaximumHandSize": "No maximum hand size", "static:MayPlayAdditionalLand": "May play an additional land", "static:MayLookAtTopOfLibrary": "May look at the top of a library",
    "static:CantBeBlockedBy": "Can't be blocked by certain creatures", "static:CantBeBlocked": "Can't be blocked", "static:CantUntap": "Doesn't untap", "static:CanAttackWithDefender": "Can attack despite defender",
    "static:CantBeCast": "Spells can't be cast", "static:CantAttack": "Can't attack", "static:MustAttack": "Must attack", "static:CantEnterBattlefieldFrom": "Can't enter the battlefield from a zone",
    "static:CantBlock": "Can't block", "static:CantCastFrom": "Can't cast from a zone", "static:CantBeCountered": "Can't be countered", "static:MustBlock": "Must block",
    "static:CantLoseTheGame": "Can't lose the game", "static:CantGainLife": "Can't gain life", "static:CantBeBlockedExceptBy": "Can't be blocked except by certain creatures",
    "static:CantWinTheGame": "Can't win the game", "static:CantCastDuring": "Can't cast spells during a phase", "static:BlockRestriction": "Restricts which creatures can block",
    "static:CantAttackOrBlock": "Can't attack or block", "static:CantBeCopied": "Can't be copied", "static:MustBeBlocked": "Must be blocked",
    "Detain": "Detain a permanent", "Investigate": "Investigate", "Forage": "Forage", "Populate": "Populate", "Transform": "Transform a permanent", "ManifestDread": "Manifest dread",
    "BecomePrepared": "Become prepared", "Manifest": "Manifest a card", "SetDayNight": "Set day or night", "PhaseOut": "Phase out", "Shuffle": "Shuffle a library", "PutOnTopOrBottom": "Put a card on top or bottom",
    "PutAtLibraryPosition": "Put a card in a library", "GivePlayerCounter": "Give a player counters", "MoveCounters": "Move counters", "Double": "Double counters", "GainEnergy": "Get energy",
    "MultiplyCounter": "Multiply counters", "Proliferate": "Proliferate", "Monstrosity": "Monstrosity",
}


def effect_word(ft):
    return EFFECT.get(ft) or re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", ft.replace("static:", "")).lower().capitalize()


CONT_WORDS = {"AddPower": "adds power", "AddToughness": "adds toughness", "AddKeyword": "adds a keyword", "GrantAbility": "grants an ability", "GrantTrigger": "grants a trigger",
              "AddSubtype": "adds a creature type", "AddType": "adds a card type", "RemoveAllAbilities": "removes all abilities", "SetPower": "sets power", "SetToughness": "sets toughness",
              "AddColor": "adds a color", "SetBasicLandType": "sets land types", "AddAllCreatureTypes": "adds every creature type", "AddDynamicPower": "adds power by a count", "SetDynamicPower": "sets power by a count", "RemoveKeyword": "removes an ability", "SetColor": "sets a color", "AddStaticMode": "adds a different rule", "": "affects it"}
OBJ_FIELD = {"objc": "objc", "objc2": "objc2", "sact": "sact"}
KWFIX = {"firststrike": "first strike", "doublestrike": "double strike", "deathtouch": "deathtouch", "lifelink": "lifelink"}
GRANT_WORDS = {"AddSubtype": "a creature type", "AddType": "a card type", "RemoveAllAbilities": "no abilities", "SetPower": "a set power", "SetToughness": "a set toughness", "AddColor": "a color", "SetColor": "a color",
               "": "a gained effect", "other": "a gained effect", "GrantAbility": "a gained ability", "AddStaticMode": "a different rule", "GrantTrigger": "a gained trigger"}


PUT = {"Hand": "put it in hand", "Battlefield": "put it onto the battlefield", "Graveyard": "put it in the graveyard", "Exile": "put it in exile", "Library": "put it back in the library"}
OBJ_FTYPES = {"Destroy", "DealDamage", "Untap", "Tap", "Sacrifice", "PutCounter", "RemoveCounter", "ChangeZone", "Bounce", "GenericEffect", "Pump", "static:Continuous", "CopyTokenOf", "Attach", "Counter", "GainControl", "Token"}
CONSUMED = {"Bounce": {"to"}, "Mill": {"to"}, "PutAtLibraryPosition": {"to"}, "ChangeZone": {"frm", "to"}, "SearchLibrary": {"to"}, "PutCounter": {"ctrc"}, "Token": {"kw"}, "Pump": {"sign"}, "GenericEffect": {"grant"}, "static:Continuous": {"grant"},
            "Draw": {"who"}, "Sacrifice": {"who"}, "Mana": {"obj"}, "CopySpell": {"cpk", "then"}, "BecomeCopy": {"cpk", "then"}, "CastFromZone": {"castmode", "free"}}
WHOW = {"you": "by you", "target player": "by target player", "each opponent": "by each opponent", "each player": "by each player", "that player": "by that player", "defending player": "by the defending player"}
TOW = {"Hand": "cards go to hand", "Battlefield": "cards go to the battlefield", "Exile": "cards go to exile", "Graveyard": "cards go to the graveyard", "Library": "cards go to the library"}
LEFTOVER = {"to": lambda v: ", " + TOW.get(v, "cards go to " + v.lower()), "frm": lambda v: ", from " + ZONE.get(v, v.lower()),
            "who": lambda v: ", " + WHOW.get(v, "by " + v), "sign": lambda v: {"boost": ", power and toughness up", "shrink": ", power and toughness down", "mixed": ", power and toughness up and down"}.get(v, ""),
            "ctrc": lambda v: ", " + CTRW.get(v, v) + " counters", "kw": lambda v: ", with " + v, "grant": lambda v: ", " + v.replace("keyword ", "")}


def loose_name(key):
    fam, ft, kv, (nf, kept) = key
    d = dict(kv)
    fields = FIELDS.get(fam, DEFAULT_FIELDS)
    objfield = next((f for f in fields if f in OBJ_FIELD), None)
    objdrop = bool(objfield) and objfield not in d
    o = d.get("objc2") or d.get("objc") or d.get("sact") or ""
    ob = "" if objdrop else art(o)
    base = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", ft.replace("static:", "")).lower()
    z = lambda k: ZONE.get(d.get(k, ""), d.get(k, "").lower())
    sp = lambda w: (" " + w) if w else ""
    mass = ", all of them" if d.get("mass") == "all" else ", several" if d.get("mass") == "several" else ""
    if ft == "Destroy":
        head = "Destroy" + sp(ob)
    elif ft == "DealDamage":
        head = "Deal damage" + (" to " + ob if ob else "")
    elif ft == "Untap":
        head = "Untap" + sp(ob)
    elif ft == "Tap":
        head = "Tap" + sp(ob)
    elif ft == "Sacrifice":
        who = {"": "Sacrifice", "each opponent": "Each opponent sacrifices", "each player": "Each player sacrifices", "that player": "That player sacrifices", "target player": "Target player sacrifices"}.get(d.get("who", ""), "A player sacrifices")
        head = who + sp(ob)
    elif ft == "PutCounter":
        c = d.get("ctrc", "")
        cw = (CTRW.get(c, c) + " counters") if c else "counters"
        head = "Put " + cw + (" on " + ob if ob else "")
    elif ft == "RemoveCounter":
        head = "Remove counters" + (" from " + ob if ob else "")
    elif ft == "ChangeZone":
        head = "Move " + (ob if ob else "cards") + (" from " + z("frm") if d.get("frm") else "") + (" to " + z("to") if d.get("to") else "")
        if o in ("something",):
            head = head
    elif ft == "Bounce":
        head = "Return " + (ob + " to its owner's hand" if ob else "things to their owners' hands")
    elif ft == "Draw":
        head = {"": "Draw cards", "you": "You draw cards", "each opponent": "Each opponent draws cards", "each player": "Each player draws cards", "target player": "Target player draws cards", "that player": "That player draws cards"}.get(d.get("who", ""), "A player draws cards")
    elif ft == "SearchLibrary":
        head = "Search a library" + (" for " + ob if ob and ob != "any target" else "") + (", " + PUT.get(d.get("to"), "put it in " + z("to")) if d.get("to") else "")
    elif ft == "Damage":
        head = "Deal damage to each " + (o[2:] if o.startswith("a ") else o) if o and not objdrop and o not in ("something", "card", "cards") else "Deal damage to many things at once"
        mass = ""
    elif ft == "Mill":
        head = "Mill cards"
    elif ft == "Token":
        head = "Create " + (o + " " if o and not objdrop else "") + "tokens" + (" with " + d["kw"] if d.get("kw") else "")
    elif ft == "CopyTokenOf":
        head = "Create a token that is a copy of " + (ob or "something")
    elif ft == "CopySpell":
        head = "Copy a spell or ability (which one is not recorded)" + (", " + d["cpk"] if d.get("cpk") else "") + (", " + d["then"] if d.get("then") else "")
    elif ft == "BecomeCopy":
        head = "Become a copy" + sp(d.get("cpk", ""))
    elif ft == "CastFromZone":
        head = {"cast": "Cast", "play": "Play"}.get(d.get("castmode"), "Cast or play") + " a card (the zone is not recorded)" + (", without paying its cost" if d.get("free") else "")
    elif ft == "Pump":
        sg = {"boost": "bigger", "shrink": "smaller", "mixed": "bigger and smaller", "unknown": "bigger or smaller by a counted amount"}.get(d.get("sign", ""), "different")
        head = "Make " + (ob or "things") + " " + sg
    elif ft == "GenericEffect":
        g = d.get("grant", "")
        head = "Give " + (ob or "things") + " " + (KWFIX.get(g.replace("keyword ", ""), g.replace("keyword ", "")) if g.startswith("keyword") else GRANT_WORDS.get(g, g or "a gained effect"))
    elif ft == "static:Continuous":
        g = d.get("grant", "")
        head = "Continuous effect on " + (ob or "things") + ((": " + CONT_WORDS.get(g, "gives " + KWFIX.get(g.replace("keyword ", ""), g.replace("keyword ", "")) if g.startswith("keyword") else g)) if g else "")
    elif ft == "Attach":
        head = "Attach" + (" to " + ob if ob else "")
    elif ft == "Counter":
        head = "Counter " + (ob or "a spell")
    elif ft == "GainControl":
        head = "Gain control of " + (ob or "things")
    elif ft == "Mana":
        head = "Add mana" + ({"Fixed": ", of one specific color", "AnyOneColor": ", of any one color", "AnyCombination": ", in any combination of colors"}.get(d.get("obj", ""), ""))
    else:
        head = effect_word(ft) + (", " + o if o and not objdrop and o not in ("something", "card", "cards") else "")
    name = head + mass
    # every key field the template above did not use gets a plain phrase, so two different groups never share a name
    used = CONSUMED.get(ft, set()) | {"objc", "objc2", "sact", "mass", "ctrl", "when"}
    for fld, val in kv:
        if fld in used or not val:
            continue
        ph = LEFTOVER.get(fld)
        if ph:
            name += ph(val)
    if d.get("when"):
        name += ", " + whenw(d["when"])
    if d.get("ctrl") == "you control":
        name += ", ones you control"
    elif d.get("ctrl") == "an opponent controls":
        name += ", ones an opponent controls"
    if kept == 0 and nf > 0:
        name += ", less common kinds"
    elif objdrop and ft in OBJ_FTYPES:
        name += ", other kinds of target"
    elif objdrop:
        name += ", less common kinds"
    elif kept < nf and nf > 0:
        name += ", less common kinds"
    name = re.sub(r"\s+", " ", name).strip().replace("Cant ", "Can't ").replace("the same object", "the thing chosen before")
    return fam + " › " + name


def main():
    data = P.collect()
    items, meta = data["items"], data["meta"]
    R = pickle.load(open(os.environ["LOOSE_RAW"], "rb"))
    raw, info = R["raw"], R["src"]
    fam_keys = set(meta["fam_keys"])
    use_idx = [n for n, i in enumerate(items) if i["f"]["usable"] and i["f"]["fam"] in fam_keys]
    keys = build_keys(use_idx, items, info, raw)
    L3 = collections.defaultdict(set)
    members = collections.defaultdict(list)
    for n, k in zip(use_idx, keys):
        L3[k].add(items[n]["oid"])
        members[k].append(n)
    names = {k: loose_name(k) for k in L3}
    sizes = {k: len(v) for k, v in L3.items()}
    # folded form: groups under 10 cards become "Other <effect type>" within their effect type
    folded = collections.defaultdict(set)
    fold_members = collections.defaultdict(list)
    for k, v in L3.items():
        tgt = k if len(v) >= 10 else (k[0], "ALL", "OTHER")
        folded[tgt] |= v
        fold_members[tgt] += members[k]
    fsizes = {k: len(v) for k, v in folded.items()}
    card_groups = collections.defaultdict(set)
    for k, v in folded.items():
        for o in v:
            card_groups[o].add(k)
    cards_in = set(card_groups)
    out = {"seed_reads": SEED_READS, "cap": CAP, "fields": FIELDS}
    out["unfolded"] = P.dist(list(sizes.values()))
    out["folded"] = P.dist(list(fsizes.values()))
    out["folded_visible"] = sum(1 for k in folded if k[2] != "OTHER")
    out["folded_other_buckets"] = sorted(((k[0] + " / " + k[1], fsizes[k]) for k in folded if k[2] == "OTHER"), key=lambda x: -x[1])
    out["largest_15"] = [{"name": names[k] if k[2] != "OTHER" else k[0] + " › Less common effects, by kind", "cards": fsizes[k]} for k in sorted(folded, key=lambda k: -fsizes[k])[:15]]
    out["reach"] = {"cards": len(cards_in), "in_a_group_of_100_or_fewer": sum(1 for o in cards_in if any(fsizes[k] <= 100 for k in card_groups[o])),
                    "only_in_groups_over_100": sum(1 for o in cards_in if all(fsizes[k] > 100 for k in card_groups[o])),
                    "in_a_group_of_50_or_fewer": sum(1 for o in cards_in if any(fsizes[k] <= 50 for k in card_groups[o])),
                    "in_a_group_that_is_not_an_Other_bucket_and_100_or_fewer": sum(1 for o in cards_in if any(fsizes[k] <= 100 and k[2] != "OTHER" for k in card_groups[o])),
                    "avg_groups_per_card": round(sum(len(v) for v in card_groups.values()) / len(cards_in), 2), "max_groups_per_card": max(len(v) for v in card_groups.values())}
    out["groups_over_100"] = [{"name": names[k] if k[2] != "OTHER" else k[0] + " › Less common effects, by kind", "cards": fsizes[k]} for k in sorted(folded, key=lambda k: -fsizes[k]) if fsizes[k] > 100]
    # name scan
    import ability_names as AN
    import probe_names_part1 as P1
    import probe_names_part2 as P2
    cards_json = P.jl("ability_taxonomy_cards.json")["cards"]
    vocab = set()
    for c in cards_json.values():
        for w in re.findall(r"[A-Za-z][a-z']{2,}", c["t"] or ""):
            vocab.add(w.lower())
    P1.ALLOW.update(AN.TEMPLATE_VOCAB)
    P1.ALLOW.update({"affecting", "granting", "several", "bigger", "smaller", "counted", "unchanged", "amount", "continuous", "kinds", "same", "something", "state", "recorded", "reader", "named", "replacement"})
    shown = {k: (names[k] if k[2] != "OTHER" else k[0] + " › Less common effects, by kind") for k in folded}
    scan = P1.defect_scan([("group", n.split(" › ", 1)[1]) for n in shown.values()], vocab)
    soft = ("longer than 110 characters", "stacked parentheses", "disambiguation suffix ('(variant)', '#2')")
    hard = {n.split("  [")[0] for k, v in scan.items() if k not in soft for _, n in v}
    bad = []
    for k in L3:
        texts = [P2.norm(items[n]["text"]) for n in members[k] if (items[n]["text"] or "").strip()]
        if len(texts) < 5:
            continue
        low = set(re.findall(r"[a-z']+", P2.norm(names[k].split("›", 1)[1])))
        for w, rx in P2.STEMS.items():
            if w in low or (w + "s") in low:
                if sum(1 for t in texts if re.search(rx, t)) / len(texts) < 0.5:
                    bad.append((names[k], w))
    out["name_scan"] = {"names": len(shown), "hard_defects": len(hard), "examples": sorted(hard)[:25], "claims_hits": len(bad), "claims_examples": bad[:8],
                        "over_110": sum(1 for n in shown.values() if len(n) > 110),
                        "by_kind": {k: [n for _, n in v][:6] for k, v in scan.items() if v}}
    # catch-all reads: 20 members of: the 3 largest, the groups named in the brief, every Other bucket over 20 cards
    rnd = random.Random(SEED_READS)
    targets = []
    for k in sorted(folded, key=lambda k: -fsizes[k])[:3]:
        targets.append(k)
    for k in folded:
        if k[2] == "OTHER" and fsizes[k] > 20 and k not in targets:
            targets.append(k)
    for k in sorted(folded, key=lambda k: -fsizes[k]):
        if k[2] != "OTHER" and fsizes[k] > 20 and ("less common" in shown[k] or "other kinds" in shown[k]) and k not in targets:
            targets.append(k)
    for k in folded:
        if k[2] != "OTHER" and k[1] == "PutCounter" and dict(k[2]).get("ctrc") == "other" and dict(k[2]).get("objc") == "this permanent" and k not in targets:
            targets.append(k)
    reads = []
    for k in targets:
        mem = sorted(fold_members[k], key=lambda n: (items[n]["oid"], items[n]["text"]))
        rnd.shuffle(mem)
        seen, pick = set(), []
        for n in mem:
            if items[n]["oid"] in seen:
                continue
            seen.add(items[n]["oid"])
            pick.append(n)
            if len(pick) == 20:
                break
        reads.append({"id": len(reads) + 1, "cards": fsizes[k], "name": shown[k], "key": [k[0], k[1], k[2] if k[2] == "OTHER" else list(k[2])],
                      "blind": [{"card": meta["names"][items[n]["oid"]], "ability_text": " ".join((items[n]["text"] or meta["card_text"].get(items[n]["oid"], "")).split())[:230],
                                 "ftype": items[n]["f"]["ftype"]} for n in pick]})
    out["reads"] = reads
    # sub-headings: the browse unit inside the plainly labeled catch-all groups. They are not groups: no card gets a new membership from them.
    import gzip
    rank = {}
    with gzip.open(os.path.join(P.DATA, "scryfall-oracle-cards.jsonl.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            o_ = json.loads(line)
            if o_.get("edhrec_rank") is not None:
                rank[o_["oracle_id"]] = o_["edhrec_rank"]

    def subs(ns, labeler):
        by = collections.defaultdict(set)
        for n in ns:
            by[labeler(n)].add(items[n]["oid"])
        big = {l: c for l, c in by.items() if len(c) >= 3}
        rest = set().union(*[c for l, c in by.items() if len(c) < 3]) if any(len(c) < 3 for c in by.values()) else set()
        out_ = [{"name": l, "cards": len(c), "best_rank": min((rank[o] for o in c if o in rank), default=None)} for l, c in big.items()]
        out_.sort(key=lambda r: (r["best_rank"] is None, r["best_rank"] or 0, -r["cards"], r["name"]))
        if rest:
            out_.append({"name": "Other kinds", "cards": len(rest), "best_rank": min((rank[o] for o in rest if o in rank), default=None)})
        return out_
    vcache = {}

    def vals_of(n):
        if n not in vcache:
            vcache[n] = field_values(items[n]["f"], n, info, raw)
        return vcache[n]
    catch = []
    for k in sorted(folded, key=lambda k: -fsizes[k]):
        if k[2] == "OTHER":
            catch.append({"group": shown[k], "cards": fsizes[k], "by": "effect type", "subs": subs(fold_members[k], lambda n: effect_word(items[n]["f"]["ftype"]))})
        elif fsizes[k] > 100:
            fam_, ft_ = k[0], k[1]
            if ft_ == "Destroy":
                catch.append({"group": shown[k], "cards": fsizes[k], "by": "what is destroyed", "subs": subs(fold_members[k], lambda n: vals_of(n)["objc2"] or "something")})
            elif ft_ == "static:Continuous":
                catch.append({"group": shown[k], "cards": fsizes[k], "by": "what it does", "subs": subs(fold_members[k], lambda n: CONT_WORDS.get(vals_of(n)["grant"], ("gives " + KWFIX.get(vals_of(n)["grant"].replace("keyword ", ""), vals_of(n)["grant"].replace("keyword ", ""))) if vals_of(n)["grant"].startswith("keyword") else (vals_of(n)["grant"] or "affects it")))})
    out["catch_all_subheadings"] = catch
    with io.open(os.path.join(BUILD, "loose_groups_probe_v2.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print(json.dumps({k: out[k] for k in ("unfolded", "folded", "folded_visible", "largest_15", "reach", "groups_over_100", "name_scan")}, indent=1, ensure_ascii=False)[:7000])
    print(out["folded_other_buckets"][:30])


if __name__ == "__main__":
    main()
