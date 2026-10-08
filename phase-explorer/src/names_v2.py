#!/usr/bin/env python3
"""PROTOTYPE of the signature-derived naming template (Part 2 of the name cleanup). Not used by the build yet.

Extracted from src/build_ability_taxonomy.py and then changed by the patches listed in src/probe_names_part2.py. The production
module replaces this file after approval.
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_signature_taxonomy as pst  # noqa: E402,F401
import probe2_signature_taxonomy as p2  # noqa: E402,F401

# ---------------------------------------------------------------- names (display only)
CONTR = {"cant": "can't", "dont": "don't", "doesnt": "doesn't", "wont": "won't", "isnt": "isn't"}


def split_camel(s):
    t = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s).lower()
    return " ".join(CONTR.get(w, w) for w in t.split())


def a_an(phrase):
    """'a' / 'an' by the first letter of the phrase as it will be read (not the capitalised word it came from)."""
    return "an " + phrase if phrase[:1].lower() in "aeiou" else "a " + phrase


OBJ_PH = {"TriggeringSource": "triggering source", "StackAbility": "ability on the stack", "StackSpell": "spell on the stack",
          "TrackedSet": "them", "AnyOneColor": "mana of any one color"}
DURW = {"UntilEndOfTurn": "until end of turn", "Permanent": "permanently", "UntilYourNextTurn": "until your next turn",
        "UntilControllerNextUntapStep": "until its controller's next untap step", "UntilHostLeavesPlay": "for as long as the source stays",
        "UntilEndOfCombat": "until end of combat"}
WRAPW = {"Choose": "after a choice", "TargetOnly": "after choosing a target", "PayCost": "if you pay a cost",
         "CreateDelayedTrigger": "at a later time", "Modal": "as a chosen mode"}
MODE_PH = {"Panharmonicon": "makes triggered abilities trigger an extra time", "SuppressTriggers": "suppresses triggered abilities",
           "BlockRestriction": "has a blocking restriction", "PerTurnCastLimit": "limits how many spells can be cast each turn",
           "NoMaximumHandSize": "has no maximum hand size", "MaximumHandSize": "has a set maximum hand size",
           "MayPlayAdditionalLand": "may play an additional land each turn", "MayLookAtTopOfLibrary": "may look at the top card of the library",
           "CastWithFlash": "can be cast as though it had flash", "GraveyardCastPermission": "may be cast from the graveyard",
           "CantBeActivated": "has abilities that can't be activated", "CantCastDuring": "can't cast spells during a phase or turn",
           "MustBeBlocked": "must be blocked if able", "MustAttack": "must attack if able", "CantAttack": "can't attack",
           "CantBlock": "can't block", "CantAttackOrBlock": "can't attack or block", "CantBeBlocked": "can't be blocked",
           "CantUntap": "doesn't untap", "CantBeCountered": "can't be countered", "CantBeTargeted": "can't be the target of spells or abilities",
           "MayChooseNotToUntap": "may choose not to untap", "CanAttackWithDefender": "can attack as though it didn't have defender",
           "CantBeBlockedBy": "can't be blocked by some creatures"}
CLAUSE = {"mods": "grants: ", "who": "for ", "wrap": "", "chain": ""}


def kw_words(kw):
    out = []
    if kw.startswith("{'"):                                    # a dict dump: keep only the keyword names
        kw = "|".join(re.findall(r"'([A-Z][A-Za-z]+)': ", kw)[:1]) or kw
    for k in kw.split("|"):
        k = re.sub(r"\{[^}]*type: [^}]*\}", "", k)           # a typed cost dump ("Flashback{type: Mana, data: ...}") keeps only the keyword
        k = re.sub(r"[{}'\"]", "", k).replace(": ", " ")
        out.append(split_camel(k))
    return ", ".join(x for x in out if x)


TERM = {"Surveil": "Surveil", "Scry": "Scry", "Investigate": "Investigate", "Explore": "Explore", "Proliferate": "Proliferate",
        "Amass": "Amass", "Monstrosity": "Monstrosity", "Adapt": "Adapt", "Connive": "Connive", "Populate": "Populate",
        "Manifest": "Manifest", "ManifestDread": "Manifest dread", "TimeTravel": "Time travel", "Learn": "Learn",
        "Seek": "Seek", "Discover": "Discover", "Bolster": "Bolster", "Incubate": "Incubate", "Suspect": "Suspect",
        "Forage": "Forage", "CollectEvidence": "Collect evidence", "VentureIntoDungeon": "Venture into the dungeon",
        "RingTemptsYou": "The Ring tempts you", "BecomeMonarch": "Become the monarch", "Fight": "Fight", "Goad": "Goad",
        "Detain": "Detain", "Transform": "Transform", "Regenerate": "Regenerate", "Shuffle": "Shuffle",
        "RollDie": "Roll a die", "FlipCoin": "Flip a coin", "CreateEmblem": "Get an emblem", "ExtraTurn": "Take an extra turn",
        "SetClassLevel": "Gain a Class level", "BecomePrepared": "Become prepared", "Conjure": "Conjure a card",
        "GainEnergy": "Get energy", "Tribute": "Tribute", "Double": "Double", "SolveCase": "Solve a Case",
        "GiftDelivery": "Give a gift", "PhaseOut": "Phase out", "Animate": "Become a creature", "RuntimeHandled": "Keyword action",
        "SwitchPT": "Switch power and toughness", "DoublePT": "Double power and toughness", "AddRestriction": "Add a restriction",
        "Choose": "Make a choice as it enters", "ChooseFromZone": "Choose a card from a zone", "TargetOnly": "Choose a target",
        "PayCost": "Pay a cost", "CreateDelayedTrigger": "Set up a later effect", "AddPendingETBCounters": "Enter with counters",
        "Transform ": "Transform"}
CTR = {"p1p1": "+1/+1", "m1m1": "−1/−1"}
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}
ZONE = {"Graveyard": "a graveyard", "Hand": "hand", "Library": "a library", "Exile": "exile", "Battlefield": "the battlefield",
        "Stack": "the stack"}


def obj_words(o, plural=False):
    if not o or o in ("-",):
        return ""
    if o == "self":
        return "this permanent"
    if o == "parent":
        return "it"
    if o == "TrackedSet":
        return "those cards"
    if o in ("triggering player", "defending player"):
        return "that player" if o == "triggering player" else "the defending player"
    if o in ("any target", "player", "you"):
        return {"any target": "any target", "player": "a player", "you": "you"}[o]
    att = ""
    m = re.match(r"^(.*)\[(equipped|enchanted|equipped\+enchanted)\]$", o)
    if m:
        o, att = m.group(1), m.group(2).replace("+", " or ") + " "
    o = o.split("/spell:")[0]
    alts = []
    for part in o.split("|"):
        ws = []
        for t in re.split(r"[+&]", part):
            if t.startswith("Non:"):
                ws.insert(0, "non" + t[4:].lower())
            elif t.startswith("Subtype:"):
                ws.append(t.split(":", 1)[1])
            elif t in OBJ_PH:
                ws.append(OBJ_PH[t])
            elif re.search(r"[a-z][A-Z]", t):
                ws.append(split_camel(t))
            else:
                ws.append(t.lower())
        w = " ".join(ws) or "permanent"
        w = w.replace("card", "card").replace("object", "permanent").replace("anyonecolor", "mana of any one color")
        alts.append(w)
    words = " or ".join(alts)
    if plural and not att:
        words = words + "s" if not words.endswith("s") else words
    return att + words


# an effect carries its own duration only for these; for the rest the duration field is read from the whole ability and may
# belong to another clause, so a name never claims it ("Gain life until end of turn" was a misread in the round-2 name check)
DUR_TYPES = {"Pump", "GenericEffect", "GainControl", "Animate", "PreventDamage", "Regenerate", "DoublePT", "SwitchPT"}
QUAL = {"PowerGE": "with power N or greater", "PowerLE": "with power N or less", "ToughnessGE": "with toughness N or greater",
        "ToughnessLE": "with toughness N or less", "CmcLE": "with mana value N or less", "CmcGE": "with mana value N or greater",
        "CmcEQ": "with mana value N", "Attacking": "that's attacking", "Blocking": "that's blocking",
        "EnchantedBy": "it enchants", "EquippedBy": "it equips", "Owned": "you own", "CountersGE": "with counters on it",
        "Named": "with a chosen name", "InAnyZone": "in any zone", "SameNameAsParentTarget": "with the same name as the target", "Modified": "that's modified", "IsChosenCreatureType": "of the chosen type"}
STEPW = {"Token": "create a token", "Draw": "draw", "GainLife": "gain life", "LoseLife": "lose life", "Discard": "discard",
         "SearchLibrary": "search a library", "PutCounter": "put counters", "Mill": "mill", "Scry": "scry", "Surveil": "surveil",
         "Pump": "pump", "PumpAll": "pump all", "DealDamage": "deal damage", "Untap": "untap", "Tap": "tap",
         "Bounce": "return to hand", "Sacrifice": "sacrifice", "Destroy": "destroy", "GenericEffect": "grant an ability",
         "CastFromZone": "cast", "GrantCastingPermission": "allow casting", "CreateDelayedTrigger": "set up a later effect",
         "PutAtLibraryPosition": "put a card on a library", "Investigate": "investigate", "Proliferate": "proliferate",
         "ExileTop": "exile the top card", "ChangeZone": "move", "ChangeZoneAll": "move", "ChooseFromZone": "choose a card", "RegisterBending": "register a bending", "TargetOnly": "choose a target", "CopySpell": "copy a spell", "GainEnergy": "get energy"}


def plural_verbs(nm):
    for a, b in ((" gets ", " get "), (" has ", " have "), (" gains ", " gain "), (" becomes ", " become "), (" may ", " may "), (" makes ", " make "), (" limits ", " limit "), (" suppresses ", " suppress "),
                 (" can't ", " can't "), (" is changed", " are changed"), (" changes control", " change control")):
        nm = nm.replace(a, b)
    return nm


def tidy(nm):
    nm = re.sub(r" +", " ", nm).strip()
    nm = re.sub(r" \b(?:to|of|on|from|for|into)$", "", nm).strip()       # only a node name, which leaves its object out on purpose
    nm = re.sub(r" +", " ", nm).replace(" ,", ",")
    return nm[0].upper() + nm[1:] if nm else nm


TAGW = {"self": "itself", "parent": "it", "you": "you", "player": "target player", "triggering player": "that player", "TrackedSet": "those cards",
        "TrackedSetFiltered": "the matching cards", "any target": ""}
ACTOR = {"Discard": ("discard", "discards"), "LoseLife": ("lose life", "loses life"), "Draw": ("draw", "draws"), "GainLife": ("gain life", "gains life"),
         "Mill": ("mill", "mills"), "Sacrifice": ("sacrifice", "sacrifices")}


def chain_steps(ch, ft):
    """The follow-up steps of a chain, each with its target word where the chain records one (so two chains that differ only in who or what
    the step applies to do not get the same name)."""
    items = [x for x in ch.rstrip("+").split(">") if x]
    out = []
    for ix, st in enumerate(items):
        if not st[0].isupper():
            continue
        head_full, _, tag = st.partition("@")
        head, _, cty = head_full.partition("/")
        if head in ZONE:
            continue
        if not tag and ix + 1 < len(items) and items[ix + 1].split("@")[0] in ZONE and "@" in items[ix + 1]:
            tag = items[ix + 1].split("@", 1)[1]
        if ft == "SearchLibrary" and head in ("Shuffle", "ChangeZone"):
            continue
        w = STEPW.get(head, split_camel(head))
        if head == "PutCounter" and cty:
            w = "put " + CTR.get(cty, cty) + " counters"
        t = TAGW.get(tag, obj_words(tag) if tag and tag[0].isupper() and tag not in ("TrackedSetFiltered",) else "")
        if tag == "any target" and head in ("CastFromZone", "ChangeZone"):
            t = "a chosen card"
        if head in ACTOR and t:
            w = ("you " + ACTOR[head][0]) if tag == "you" else (t + " " + ACTOR[head][1])
        elif t == "it" and head in ("TargetOnly",):
            pass                                              # "choose a target it" says nothing the verb does not
        elif t and head not in ("Shuffle",):
            w = w + (" on " if head == "PutCounter" else " to " if (t == "it" and head in ("GenericEffect", "DealDamage")) else " ") + t
        elif head in ("ChangeZone", "CastFromZone", "GrantCastingPermission"):
            w = w + " it"
        elif head == "ChangeZoneAll":
            w = w + " them"
        out.append(w)
    return out


def name_leaf(ftype, ret, buckets, node=False):
    """A plain-language name from a leaf's signature (rules vocabulary only). node=True: no object, no default
    object words (a node holds every object)."""
    o = ret.get("obj", "")
    quant = ret.get("quant", "")
    ctrl = ret.get("ctrl", "")
    props = [p for p in ret.get("props", "").split("|") if p]
    adj, another, quals = [], False, []
    merged, skip = [], False
    for ix, p in enumerate(props):
        if skip:
            skip = False
        elif p == "Non" and ix + 1 < len(props):
            merged.append("NON:" + props[ix + 1])
            skip = True
        else:
            merged.append(p)
    for p in merged:
        kind, _, val = p.partition(":")
        if kind == "NON":
            adj.insert(0, "non" + val.split(":")[-1].lower())
        elif kind == "NotColor":
            adj.insert(0, "non" + val.lower())
        elif kind == "HasColor":
            adj.insert(0, val.lower())
        elif kind == "WithKeyword":
            quals.append("with " + split_camel(val))
        elif kind == "WithoutKeyword":
            quals.append("without " + split_camel(val))
        elif kind in QUAL:
            quals.append(QUAL[kind])
        elif p.startswith("Subtype:"):
            adj.append(p.split(":", 1)[1])
        elif p == "Another":
            another = True
        elif p in ("Attacking", "Blocking", "Tapped", "Untapped", "Token"):
            adj.insert(0, p.lower())
        elif kind == "HasSupertype":
            adj.insert(0, val.lower())
        elif kind == "NotSupertype":
            adj.insert(0, "non" + val.lower())
        elif kind == "IsCommander":
            adj.insert(0, "commander")
        elif kind == "Non":
            pass                                   # a bare "Non" marker carries no word of its own
        else:
            quals.append("with " + split_camel(kind) + ((" " + val.lower()) if val else ""))
    allq = quant == "all"
    plural_obj = quant in ("all", "multi", "")
    base = obj_words(o, plural=plural_obj)
    SPECIAL = ("self", "any target", "player", "you", "parent", "TrackedSet")
    frm0 = ret.get("frm", "")
    card_zone = frm0 in ("Graveyard", "Hand", "Library", "Exile")
    if base and card_zone and o not in SPECIAL and not base.endswith(("card", "cards")):
        base += " cards" if plural_obj else " card"
    if base and adj and o not in SPECIAL:
        base = " ".join(adj) + " " + base
    ob = base
    if allq and ob:
        ob = ("all other " if another else "all ") + ob
    elif quant == "multi" and ob:
        ob = "up to several " + ("other " if another else "") + ob
    elif quant == "each" and ob:
        ob = "each " + ob
    elif ob and o not in SPECIAL and not ob.startswith(("enchanted", "equipped")):
        if quant == "one":
            ob = "another " + ob if another else a_an(ob)
        elif another:
            ob = "other " + ob
    if ob and quals and o not in SPECIAL:
        ob += " " + " and ".join(quals)
    if ctrl == "You" and ob and card_zone:
        pass
    elif ctrl == "You" and ob:
        ob += " you control"
    elif ctrl == "Opponent" and ob:
        ob += " an opponent controls"
    D = (lambda x: "") if node else (lambda x: x)
    QD = lambda sing, pl: D({"one": "a " + sing, "all": "all " + pl, "multi": "several " + pl, "each": "each " + sing}.get(quant, pl))
    PTW = {"boost": "+N/+N", "shrink": "\u2212N/\u2212N", "mixed": "+N/\u2212N or \u2212N/+N", "zero": "+0/+0"}.get(ret.get("sign", ""), "\u00b1N/\u00b1N")
    RECW = {"opponents": "each opponent", "each player": "each player"}.get(ret.get("recip", ""), "")
    if o == "object" and not node:
        ob = "everything it names" if allq else "something"
        if adj:
            ob = ("all " if allq else "a ") + " ".join(adj) + (" permanents" if allq else " permanent")
        if ctrl == "Opponent":
            ob += " an opponent controls"
        elif ctrl == "You":
            ob += " you control"
    if node:
        ob = ""
    who = ret.get("who", "")
    subj = {"scope:Opponent": "Each opponent", "scope:All": "Each player", "scope:TriggeringPlayer": "That player",
            "player": "Target player", "defending player": "Defending player", "triggering player": "That player",
            "its controller": "Its controller"}.get(who, "")
    to, frm, ctr = ret.get("to", ""), ret.get("frm", ""), ret.get("ctr", "")
    zone_of = (lambda z: {"Graveyard": "your graveyard", "Hand": "your hand", "Library": "your library",
                          "Exile": "exile"}.get(z, ZONE.get(z, z.lower()))) if ctrl == "You" else (lambda z: ZONE.get(z, z.lower()))
    ft = ftype
    if o == "any target" and ft not in ("DealDamage", "Damage", "PreventDamage") and not node:
        ob = "a card" if ft in ("Dig", "SearchLibrary", "RevealTop", "CastFromZone", "ChangeZone", "ExileTop",
                                "PutAtLibraryPosition", "RevealUntil") else "a target"
    if ft.startswith("static:"):
        mode = ft[7:]
        mods = ret.get("mods", "")
        target = ob or D("this permanent")
        plural = False
        if ob and o not in SPECIAL and not ob.startswith(("enchanted", "equipped")):
            # a static applies to every matching object: "creatures you control", not "a creature you control"
            pl = "objects" if o == "object" else obj_words(o, plural=True)
            if adj:
                pl = " ".join(adj) + " " + pl
            target = ("other " if another else "") + pl + ((" " + " and ".join(quals)) if quals else "") + (
                " you control" if ctrl == "You" else " your opponents control" if ctrl == "Opponent" else "")
            plural = True
        if mode == "Continuous":
            parts = []
            if "AddPower" in mods or "AddDynamicPower" in mods:
                parts.append("gets " + PTW + "")
            if "SetPower" in mods or "SetDynamicPower" in mods:
                parts.append("has set power and toughness")
            elif "SetToughness" in mods or "SetDynamicToughness" in mods:
                parts.append("has set toughness")
            if "AddKeyword" in mods:
                parts.append("has " + (kw_words(ret.get("kw", "")) or "a keyword"))
            if "GrantAbility" in mods or "GrantTrigger" in mods:
                parts.append("has an extra ability")
            if "AddType" in mods or "AddSubtype" in mods:
                parts.append("has an extra type")
            if "ChangeController" in mods:
                parts.append("changes control")
            if not parts:
                m0 = mods.split(",")[0] if mods else "continuous"
                parts.append({"RemoveType": "loses a card type", "RemoveSubtype": "loses a creature type", "RemoveColor": "loses its colors"}.get(m0, "is changed: " + split_camel(m0)))
            nm = "%s %s" % (target, " and ".join(parts))
        elif mode in ("ReduceCost", "RaiseCost"):
            sp = o.split("/spell:")[1] if "/spell:" in o else ""
            nm = "%s spells cost %s" % (obj_words(sp).capitalize() if sp else "", "less" if mode == "ReduceCost" else "more")
        else:
            nm = "%s %s" % (target, MODE_PH.get(mode, split_camel(mode)))
        if ret.get("cond"):
            nm += ", while a condition holds"
        elif mode in ("CantAttack", "CantBlock", "CantAttackOrBlock"):
            nm += ", sometimes only unless a condition is met"
        for _k, _lab in (("kw", ""), ("dur", ""), ("wrap", "")):
            pass
        dur = ret.get("dur", "")
        if dur:
            nm += ", " + DURW.get(dur, split_camel(dur))
        if plural:
            nm = plural_verbs(nm)
        return tidy(nm)
    if ft.startswith("repl:"):
        return tidy("Replacement: " + split_camel(ft[5:]))
    if ft == "Destroy":
        nm = "Destroy " + (ob or QD("permanent", "permanents"))
    elif ft == "ChangeZone":
        tw, fw = ZONE.get(to, to.lower()), ZONE.get(frm, frm.lower())
        what = ob or QD("card", "cards")
        if to == "Exile":
            nm = "Exile " + what + (" from " + zone_of(frm) if frm else "")
        elif to == "Battlefield":
            nm = ("Return " if frm == "Graveyard" else "Put ") + what + (" from " + zone_of(frm) if frm else "") + " onto the battlefield"
        elif to == "Hand":
            nm = "Return " + what + (" from " + zone_of(frm) if frm else "") + " to hand"
        else:
            nm = "Move " + what + (" from " + zone_of(frm) if frm else "") + " to " + tw
    elif ft == "Bounce":
        nm = "Return " + (ob or QD("permanent", "permanents")) + (" from " + zone_of(frm) if frm else "") + (" to their owners' hands" if o == "TrackedSet" else " to its owner's hand")
    elif ft == "Draw":
        nm = (subj + " draws cards") if subj else "Draw cards"
    elif ft == "Discard":
        nm = (subj + " discards") if subj else "Discard cards"
    elif ft == "Mill":
        nm = (subj + " mills cards") if subj else ("Mill cards" if who in ("", "you") else "A player mills cards")
    elif ft == "LoseLife":
        nm = (subj + " loses life") if subj else "Lose life"
    elif ft == "GainLife":
        nm = (subj + " gains life") if subj else "Gain life"
    elif ft == "Sacrifice":
        nm = ((subj + " sacrifices ") if subj else "Sacrifice ") + (ob or D("a permanent"))
    elif ft in ("PutCounter", "RemoveCounter", "MoveCounters", "MultiplyCounter"):
        cw = CTR.get(ctr, ctr) + " counter" if ctr else "counter"
        verb = {"PutCounter": "Put", "RemoveCounter": "Remove", "MoveCounters": "Move", "MultiplyCounter": "Double"}[ft]
        nm = "%s %ss %s %s" % (verb, cw, "from" if ft == "RemoveCounter" else "on", ob or D("permanents"))
    elif ft == "GivePlayerCounter":
        nm = (subj or "A player") + " gets " + (ctr or "") + " counters"
    elif ft == "Token":
        tok = ret.get("tok", "")
        nmt = re.search(r"name:([^|]+)", tok)
        subt = [t[4:] for t in tok.split("|") if t.startswith("sub:")]
        what = nmt.group(1) if nmt else (" ".join(subt) if subt else obj_words(o) or "")
        nm = "Create " + (what + " " if what else "") + "tokens"
        if "kw" in ret:
            nm += " with " + kw_words(ret["kw"])
    elif ft == "CopyTokenOf":
        nm = "Create a token copy" + (" of " + ob if ob else (" of a permanent" if not node else ""))
    elif ft == "Mana":
        nm = {"AnyOneColor": "Add one mana of any color", "Fixed": "Add mana of a fixed color", "Colorless": "Add colorless mana",
              "ChosenColor": "Add mana of the chosen color"}.get(o, "Add mana" + ("" if node or not o else " of kind " + split_camel(o)))
    elif ft in ("Pump", "PumpAll"):
        nm = (ob or D("a creature")) + " gets " + PTW + ""
    elif ft == "GenericEffect":
        mods = ret.get("mods", "")
        target = ob or D("a permanent")
        bits = []
        if "AddKeyword" in mods:
            bits.append("gains " + (kw_words(ret.get("kw", "")) or "a keyword"))
        if "AddPower" in mods:
            bits.append("gets " + PTW + "")
        if "MustBeBlocked" in mods and o == "self":
            return tidy("All creatures able to block this creature must do so (like Lure)")
        MODW = {"SetPower": "has set base power and toughness", "SetDynamicPower": "has set base power and toughness", "SetPowerDynamic": "has set base power and toughness",
                "AddType": "gains a card type", "AddSubtype": "gains a creature type", "AddColor": "changes color",
                "SetColor": "changes color", "GrantAbility": "gains an ability", "GrantTrigger": "gains a triggered ability",
                "RemoveKeyword": "loses a keyword", "RemoveAllAbilities": "loses all abilities",
                "AddDynamicPower": "gets ±X/±X", "AddAllCreatureTypes": "gains every creature type",
                "MustBeBlocked": "must be blocked if able", "MustAttack": "must attack if able", "CantBeBlockedExceptBy": "can't be blocked except by certain creatures",
                "CantBlock": "can't block", "CantUntap": "doesn't untap", "CantBeBlocked": "can't be blocked", "CantAttack": "can't attack",
                "CantBeBlockedBy": "can't be blocked by some creatures", "AddStaticMode": ""}
        for m in mods.split(","):
            if m and m not in ("AddKeyword", "AddPower", "AddToughness", "SetToughness", "SetToughnessDynamic",
                               "SetDynamicToughness", "AddDynamicToughness"):
                w = MODW.get(m, split_camel(m))
                if w and w not in bits:
                    bits.append(w)
        nm = target + " " + (", ".join(bits) or "gains an ability")
    elif ft in ("Tap", "Untap"):
        if o == "self" and buckets.get("replacements", 0) * 2 > sum(buckets.values()):
            nm = "Enters tapped"
        else:
            nm = ft + " " + (ob or QD("permanent", "permanents"))
    elif ft == "DealDamage" or ft == "Damage":
        nm = "Deal damage" + (" to " + ob if ob else (" to a player" if not node else "")) + (" and " + RECW if RECW and ft == "Damage" else "")
    elif ft == "Counter":
        nm = "Counter " + (ob.replace("a card", "a spell") if ob else "a spell")
    elif ft == "Attach":
        nm = "Attach" + (" to " + ob if ob else (" to a permanent" if not node else ""))
    elif ft == "GainControl":
        nm = "Gain control" + (" of " + ob if ob else (" of a permanent" if not node else ""))
    elif ft == "SearchLibrary":
        nm = "Search your library" + (" for " + ob if ob else D(" for a card")) + (" and put it " + {"Battlefield": "onto the battlefield",
                                                                                     "Hand": "into your hand"}.get(to, "into " + ZONE.get(to, to.lower())) if to else "")
    elif ft in ("Dig", "RevealTop", "ExileTop", "RevealUntil", "ExileFromTopUntil"):
        lead = {"Dig": "Look at the top cards", "RevealTop": "Reveal the top card", "ExileTop": "Exile the top card",
                "RevealUntil": "Reveal cards until one matches", "ExileFromTopUntil": "Exile cards from the top until one matches"}[ft]
        nm = lead + (" and put " + (ob or D("one")) + (" onto " if to == "Battlefield" else " into ") + ZONE.get(to, to.lower()) if to else "")
    elif ft == "CastFromZone":
        nm = "Cast " + (ob or D("a card")) + (" from " + zone_of(frm) if frm else "")
    elif ft == "PutAtLibraryPosition":
        nm = "Put " + (ob or D("a card")) + (" from " + zone_of(frm) if frm else "") + " on top or bottom of a library"
    elif ft == "CopySpell":
        nm = "Copy " + (ob.replace("a card", "a spell") if ob else "a spell")
    elif ft == "BecomeCopy":
        nm = (ob or D("it")) + " becomes a copy"
    elif ft == "Animate":
        nm = ((ob[0].upper() + ob[1:]) if ob else "A permanent") + " becomes a creature"
    elif ft == "RevealHand":
        nm = (subj or "A player") + " reveals their hand"
    elif ft == "DamageEachPlayer":
        nm = "Deal damage to " + (RECW or D("each player"))
    elif ft == "PreventDamage":
        nm = "Prevent damage" + (" to " + ob if ob else "")
    elif ft in TERM:
        nm = TERM[ft] + ((" " + ob) if ob and ob != "you" else "")
    else:
        nm = split_camel(ft).capitalize() + ((" " + ob) if ob else "")
    if ft in ("DealDamage", "Damage") and o in ("player", "triggering player", "defending player") and subj:
        nm = "Deal damage to " + ({"scope:TriggeringPlayer": "that player", "triggering player": "that player", "player": "target player",
                                   "defending player": "the defending player"}.get(who, subj.lower()))
        subj = ""
    if subj and ft not in ("Draw", "Discard", "Mill", "LoseLife", "GainLife", "Sacrifice", "GivePlayerCounter", "RevealHand", "DamageEachPlayer"):
        nm = subj + ": " + nm[:1].lower() + nm[1:]
    dur = ret.get("dur", "")
    if dur and ft in DUR_TYPES:
        nm += " " + DURW.get(dur, split_camel(dur))           # the duration belongs to the first clause, so it comes before ", then ..."
    ch = ret.get("chain", "")
    if ch and not ch.startswith("modes:"):
        steps = chain_steps(ch, ft)
        if steps:
            nm += ", then " + " and ".join(steps[:3]) + (" and more" if len(steps) > 3 or ch.endswith("+") else "")
    if dur and ft not in DUR_TYPES:
        nm += " (ability duration: " + DURW.get(dur, split_camel(dur)) + ")"
    wraps = [x for x in ret.get("wrap", "").split(">") if x]
    ifs = (["you pay a cost"] if "PayCost" in wraps else []) + (["a condition holds"] if ret.get("cond") else [])
    other_wraps = [WRAPW.get(x, split_camel(x)) for x in wraps if x != "PayCost"]
    if other_wraps:
        nm += ", " + ", ".join(other_wraps)
    if ifs:
        nm += ", if " + " and ".join(ifs)
    if allq:
        nm = plural_verbs(nm)
    return tidy(nm)


def name_node(ftype, ret):
    r = {k: v for k, v in ret.items() if k in p2.L2G}
    return name_leaf(ftype, r, {}, node=True)




# Words the template itself emits that do not occur in any card's rules text. The defect scan accepts exactly these (and nothing else) as
# template vocabulary; any other word missing from the card text is reported as a possible typo or merged word.
TEMPLATE_VOCAB = ["duration", "sometimes", "register", "bending", "restriction", "certain", "limits", "matching", "suppresses", "varies",
                  "recorded", "filter", "scope", "excluding", "follow-up", "isn't"]


# ---------------------------------------------------------------- coverage guard: a retained field the name does not state is appended in fixed wording
GUARD_FIELDS = ["frm", "to", "ctr", "who", "mods", "sign", "recip", "obj", "ctrl", "quant", "props", "kw", "dur", "cond", "wrap", "chain", "tok"]
GUARD_W = {
    "quant": lambda v: {"one": "exactly one", "all": "all", "multi": "several", "each": "each"}.get(v, v),
    "ctrl": lambda v: {"You": "you control", "Opponent": "an opponent controls"}.get(v, split_camel(v).lower()),
    "obj": lambda v: obj_words(v),
    "props": lambda v: ", ".join(QUAL.get(x.split(":")[0], split_camel(x.split(":")[-1])) for x in v.split("|") if x and x != "Non") or "excluding some kind",
    "kw": lambda v: "with " + kw_words(v),
    "dur": lambda v: "for as long as the source stays" if v == "UntilHostLeavesPlay" else split_camel(v).lower(),
    "cond": lambda v: "if a condition holds",
    "wrap": lambda v: ", ".join(WRAPW.get(x, split_camel(x)) for x in v.split(">") if x),
    "chain": lambda v: "then " + " and ".join(chain_steps(v, ""))[:60],
    "tok": lambda v: v.replace("sub:", "").replace("name:", "").replace("|", " "),
    "frm": lambda v: "from the " + v.lower(), "to": lambda v: "to the " + v.lower(), "sign": lambda v: {"unknown": "sign not recorded", "zero": "no change"}.get(v, v),
    "recip": lambda v: v, "mods": lambda v: split_camel(v.replace(",", ", ")).lower(), "who": lambda v: "recorded as a player scope" if v.startswith("scope:") else "recorded as a player filter", "ctr": lambda v: v,
}


def _sibling_values(f, sibs):
    return {x.get(f, "") for x in sibs}


def name_leaf_final(ftype, ret, buckets, sibs=None):
    """name_leaf + the guard. A retained field the name does not state is appended in fixed wording only when it distinguishes this
    leaf from its siblings in the node (a sibling has another value, or lacks it)."""
    import probe_names_part1 as P1
    nm = name_leaf(ftype, ret, buckets)
    extra = []
    for f in GUARD_FIELDS:
        v = ret.get(f, "")
        if not v or v == "-" or (f, v) in P1.DEFAULT_SKIP:
            continue
        if sibs is not None and sibs and _sibling_values(f, sibs) == {v}:
            continue                                         # every sibling shares it: it does not distinguish
        if P1.mention(f, v, nm, ftype) or P1.implied(ftype, ret, f, v, nm):
            continue
        if f == "obj" and v in ("triggering player", "defending player", "player", "you"):
            continue                                         # the subject already says it
        w = GUARD_W.get(f, lambda x: x)(v).strip()
        if f == "chain" and ", then " in nm:
            continue                                         # name_leaf already worded the follow-up steps
        if w and w.lower() not in nm.lower():
            extra.append(w)
    return nm + (" (" + "; ".join(extra) + ")" if extra else "")
