#!/usr/bin/env python3
"""Group -> topic ("bucket") map for the tester site's "Narrow by group" row (feature BROAD_NARROWING in reports/config.js).

    python src/build_buckets.py [--check]

Writes build/buckets/map.json, deterministically (no timestamps; an unchanged file is not rewritten). --check re-derives it and compares with the file on disk.
A topic is a FILTER, never a placement: no group, id, placement, suggestion or figure changes. Reads build/ files only; corrections/ is not opened.

The file: {"v":1, "sig": checksum of the group-id list, "b": [[id, name, rule], ...15], "m": [mask, ...]}; m[i] is the topic bitmask of the i-th key of build/manual_index.json "groups"
(a group may be in several topics, mask 0 = in none). The page checks "sig" against its own copy of that key list and ignores the file if they differ.

How a group gets topics (hand-written rules in this file; no description text is used for tag groups):
  leaf          its signature: the effect type (ftype), the zones it moves cards between, the modifiers it grants, and every later step of its chain ("Put counters, then draw" is
                Counters and Card draw). The name is used only when the signature gives nothing.
  loose, tent   the family's default plus words in the group's short name (qualifier phrases like "from a spell or activated ability" removed first).
  tag           the slug of a branch's otag list (build/branches.json) first, then words in the slug and the name. "Works against ..." and "hate-..." tags are never bucketed by words.
  keyword       a table of keywords. rp, hand  words in the name.
Groups with no topic (Regenerate, monarch, dice, emblems, voting, choices, ...) stay in none; the page reaches them through "Show all groups".
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(BUILD, "buckets", "map.json")

BUCKETS = [
    ("draw", "Card draw", "Draws cards, or a draw is one step of the ability."),
    ("counters", "Counters", "Puts, removes, moves or multiplies counters, or proliferates."),
    ("tokens", "Tokens", "Creates tokens, or copies of things as tokens."),
    ("sac", "Sacrifice", "Sacrifices permanents, or sacrifice is one step of the ability."),
    ("removal", "Removal", "Destroys, exiles or returns permanents to hand."),
    ("mana", "Mana", "Adds mana."),
    ("dmg", "Damage and life", "Deals or prevents damage, gains or loses life."),
    ("lib", "Library", "Searches, mills, scries, surveils or looks at the top of a library."),
    ("gy", "Graveyard", "Uses cards in graveyards, or puts cards there."),
    ("hand", "Hand and discard", "Discards, or looks at or changes a hand."),
    ("combat", "Combat and evasion", "Attack, block and evasion rules, combat keywords."),
    ("buff", "Buffs and equipment", "Changes power and toughness, grants keywords or abilities, equips and enchants."),
    ("tap", "Tap and untap", "Taps or untaps things, or stops them untapping."),
    ("spells", "Spells and casting", "Counters or copies spells, casts from elsewhere, changes costs."),
    ("ctrl", "Steal and copy", "Gains control of things, or copies creatures and permanents."),
]
IDX = {b[0]: i for i, b in enumerate(BUCKETS)}

FT = {
    "Draw": ["draw"], "Connive": ["draw", "hand"],
    "PutCounter": ["counters"], "Proliferate": ["counters"], "RemoveCounter": ["counters"], "MoveCounters": ["counters"], "MultiplyCounter": ["counters"],
    "Adapt": ["counters"], "Monstrosity": ["counters"], "GainEnergy": ["counters"], "Amass": ["counters", "tokens"],
    "Token": ["tokens"], "Investigate": ["tokens"], "Incubate": ["tokens", "counters"], "Populate": ["tokens"], "CopyTokenOf": ["tokens", "ctrl"],
    "Sacrifice": ["sac"],
    "Destroy": ["removal"], "Bounce": ["removal"], "Fight": ["dmg", "removal"], "PhaseOut": ["removal"],
    "Mana": ["mana"],
    "DealDamage": ["dmg"], "Damage": ["dmg"], "DamageEachPlayer": ["dmg"], "GainLife": ["dmg"], "LoseLife": ["dmg"], "PreventDamage": ["dmg"], "static:PreventDamage": ["dmg"],
    "SearchLibrary": ["lib"], "Mill": ["lib", "gy"], "Dig": ["lib"], "Scry": ["lib"], "ExileTop": ["lib"], "Surveil": ["lib", "gy"], "RevealTop": ["lib"], "Seek": ["lib"],
    "PutAtLibraryPosition": ["lib"], "PutOnTopOrBottom": ["lib"], "Shuffle": ["lib"], "static:MayLookAtTopOfLibrary": ["lib"], "static:RevealTopOfLibrary": ["lib"],
    "Discard": ["hand"], "RevealHand": ["hand"], "static:NoMaximumHandSize": ["hand"],
    "Tap": ["tap"], "Untap": ["tap"], "Detain": ["tap", "combat"], "static:CantUntap": ["tap"], "static:MayChooseNotToUntap": ["tap"],
    "Counter": ["spells"], "ChangeTargets": ["spells"], "CopySpell": ["spells"], "CastFromZone": ["spells"], "GrantNextSpellAbility": ["spells"],
    "static:ReduceCost": ["spells"], "static:RaiseCost": ["spells"], "static:CastWithFlash": ["spells"], "static:CastWithKeyword": ["spells"],
    "static:GraveyardCastPermission": ["spells", "gy"], "static:CantBeCountered": ["spells"],
    "GainControl": ["ctrl"], "ExchangeControl": ["ctrl"], "BecomeCopy": ["ctrl"],
    "static:CantBlock": ["combat"], "static:CantAttack": ["combat"], "static:CantBeBlocked": ["combat"], "static:CantBeBlockedBy": ["combat"],
    "static:CantAttackOrBlock": ["combat"], "static:MustAttack": ["combat"], "ForceBlock": ["combat"], "Goad": ["combat"], "AdditionalCombatPhase": ["combat"],
    "Attach": ["buff"], "Pump": ["buff"], "PumpAll": ["buff"], "DoublePT": ["buff"], "SwitchPT": ["buff"], "Animate": ["buff"],
}
CHAIN = {
    "Draw": ["draw"], "Discard": ["hand"], "GainLife": ["dmg"], "LoseLife": ["dmg"], "DealDamage": ["dmg"], "Token": ["tokens"], "Untap": ["tap"], "Tap": ["tap"],
    "Scry": ["lib"], "SearchLibrary": ["lib"], "Shuffle": ["lib"], "Mill": ["lib", "gy"], "Surveil": ["lib", "gy"], "Sacrifice": ["sac"], "Bounce": ["removal"], "Destroy": ["removal"],
    "Mana": ["mana"], "Fight": ["dmg", "removal"], "CastFromZone": ["spells"], "GrantCastingPermission": ["spells"], "Attach": ["buff"], "Pump": ["buff"], "PumpAll": ["buff"],
    "PutCounter": ["counters"], "Proliferate": ["counters"], "AdditionalCombatPhase": ["combat"], "CopySpell": ["spells"], "GainControl": ["ctrl"], "PutAtLibraryPosition": ["lib"],
}
GRANT_MODS = r"AddKeyword|AddPower|AddToughness|AddDynamic|SetDynamic|SetPower|SetToughness|GrantTrigger|GrantAbility|AddAbility|RemoveAbility|RemoveKeyword|AddType|AddAllCreatureTypes|AddColor|SetColor"
COMBAT_KW = r"flying|haste|trample|vigilance|menace|first strike|double strike|deathtouch|reach|can't be blocked|unblockable|shadow|fear|intimidate|horsemanship"


def sigparse(sig):
    d = {}
    for p in sig.split(" · "):
        k, _, v = p.partition("=")
        d[k] = v
    return d


def zone_buckets(d):
    b = set()
    frm, to = d.get("frm", ""), d.get("to", "")
    if frm == "Graveyard":
        b.add("gy")
    if to == "Graveyard" and frm != "Graveyard":
        b.add("gy")
    if to in ("Exile", "Graveyard") and frm in ("Battlefield", ""):
        b.add("removal")
    if to == "Hand" and frm == "Battlefield":
        b.add("removal")
    if to == "Library" or frm == "Library":
        b.add("lib")
    return b


def leaf_buckets(sig, name):
    d = sigparse(sig)
    ft = d.get("ftype", "")
    b = set()
    m = d.get("mods", "")
    if ft in FT:
        b |= set(FT[ft])
    elif ft == "ChangeZone":
        b |= zone_buckets(d)
    elif ft == "GenericEffect":
        if re.search(GRANT_MODS, m):
            b.add("buff")
        if re.search(r"CantBlock|CantAttack|CantBeBlocked|MustAttack|MustBlock", m):
            b.add("combat")
        if "CantUntap" in m:
            b.add("tap")
    elif ft == "static:Continuous":
        if re.search(GRANT_MODS, m):
            b.add("buff")
        if re.search(r"CantBlock|CantAttack|CantBeBlocked", m):
            b.add("combat")
        if "ChangeController" in m:
            b.add("ctrl")
    for s in d.get("chain", "").split(">"):
        key = s.split("@")[0].split("/")[0]
        if key in CHAIN:
            b |= set(CHAIN[key])
    if d.get("frm") == "Graveyard":
        b.add("gy")
        if ft == "Bounce":
            b.discard("removal")
    if d.get("obj") == "self" and ft in ("Bounce", "ChangeZone"):                           # "Exile / return this permanent" is not removal of anything else
        b.discard("removal")
    if "gy" in b and "Bounce" in d.get("chain", ""):                                        # "Mill cards, then return a creature to hand": graveyard recursion, not removal
        b.discard("removal")
    if ft == "Bounce" and d.get("obj") == "Card" and not d.get("frm"):       # "Return a card to its owner's hand": a card, not a permanent, so from a graveyard
        b.discard("removal")
        b.add("gy")
    if ft in ("GenericEffect", "static:Continuous") and "AddKeyword" in m and re.search(COMBAT_KW, (d.get("kw", "") + " " + name).lower()):
        b.add("combat")
    return b


NR = [
    ("draw", r"\bdraws?\b|\bloot|cantrip|card advantage|\bwheel|\bconnive"),
    ("counters", r"poisonous|(?<!spell )(?<!target )\bcounters?\b(?! (a|target|that|spells?|abilit|it\b))|proliferat|\benergy\b|\bpoison\b|\+1/\+1|-1/-1|\bloyalty\b|\bmonstrosity|\badapt\b|\bamass"),
    ("tokens", r"\btokens?\b|treasure|\bfood\b|\bclues?\b|\bblood\b|populate|investigat|incubat"),
    ("sac", r"sacrific|\bedict|aristocrat|\bfodder"),
    ("removal", r"\bdestroy|\bexile[sd]? (a |an |target |each |all |up to )?(creature|permanent|artifact|enchantment|land|nonland|planeswalker|spell|card|it|them|that|those|another)\b|removal|sweeper|\bwrath|\bbounce|owners?'?s?'? hands?|\bto exile\b|\bphase out|\bkill|\bboard wipe|\bblink|\bflicker"),
    ("mana", r"\bmana\b(?! (value|cost))|\bramp\b|\bdork|\bmana rock|fixing|\bland(s)? (onto|to) the battlefield"),
    ("dmg", r"\bdamage|\bburn\b|\blife\b|\blifegain|\blifelink|\bdrain|\bfight|\bping"),
    ("lib", r"\blibrar|\bsearch|\btutor|\bscry|\bsurveil|\bmill|\btop of|\breveal the top|\bdig\b|\bshuffle|\bimpulse|\blook at the top|\bcascade|\bdiscover|\bconsult"),
    ("gy", r"graveyard|reanimat|recurs|flashback|dredge|self-mill|\bunearth|\bescape\b|\bundying|\bpersist|\bembalm|\beternalize|\bdies\b|\bdeath trigger"),
    ("hand", r"\bdiscard|\bwheel|\bmadness|\bcycling|\breveals? (their |your )?hand|\bhellbent|\bhand size|\bmaximum hand|\bditch hand|\bpeek hand"),
    ("combat", r"\battack|\bblock|\bcombat|\bevasion|\bflying|\btrample|\bmenace|\bhaste\b|\bvigilance|first strike|double strike|\bdeathtouch|\bgoad|\bfog\b|\bunblockable|\bfear\b|\bintimidate|\bshadow\b|\bhorsemanship|\blandwalk|\bdefender"),
    ("buff", r"\bgets? [+±-]|[+-]\d+/[+-]\d+|\banthem|\bpump|\bequip|\baura\b|\battach|\bgains? (flying|first|haste|vigilance|trample|lifelink|menace|reach|hexproof|indestructible|deathtouch|a keyword|an ability|abilit|protection)|\bbase power|\bindestructible|\bhexproof|\bprotection from|\bboost|\badds? (power|toughness)|\braises the (power|toughness)|\bdoubles power|\bbuff|\bgrants? "),
    ("tap", r"\btaps?\b|\buntap(?!ped lands)|\btapped|\bstun\b|\bfreeze|doesn'?t untap"),
    ("spells", r"\bspells?\b|counterspell|\bstorm\b|\bflash\b|\bcost[s]? .{0,25}(less|more)|\bcast\b|\bcasting|\bprowess|\bmagecraft|\bcopies (instant|sorcery)|\bsplice|\bretrace|\bconvoke|\bimprovise|\bkicker|\bbuyback|\bcost reduction"),
    ("ctrl", r"gain control|\bsteal|control of|exchange control|\bclone|copy of|becomes? a copy|\bthreaten|\bcopies of|\bcopy (a |target )?(creature|permanent|artifact)"),
]
NRC = [(b, re.compile(r, re.I)) for b, r in NR]
FAM = {
    "Card draw": ["draw"], "Counters": ["counters"], "Tokens": ["tokens"], "Mana": ["mana"], "Destroy": ["removal"], "Sacrifice": ["sac"], "Discard / hand": ["hand"],
    "Counter spell": ["spells"], "Tap / untap": ["tap"], "Attach": ["buff"], "Damage": ["dmg"], "Life": ["dmg"], "Control": ["ctrl"], "Copy": ["ctrl"], "Cast / play": ["spells"],
    "Combat": ["combat"], "Static: restriction": ["combat"], "Static: cost change": ["spells"], "Pump / grant": ["buff"], "Protection": ["dmg"], "Library": ["lib"],
}
FAM_ONLY = {"Card draw", "Counters", "Tokens", "Mana", "Destroy", "Sacrifice", "Discard / hand", "Counter spell", "Tap / untap", "Attach", "Damage", "Life", "Control", "Combat", "Cast / play", "Static: cost change"}
QUALIFIERS = re.compile(r", (from a spell or activated ability|on another kind of trigger|on an? [a-z ]*trigger)")


def name_buckets(text):
    return {b for b, rx in NRC if rx.search(text)}


KW = {
    "combat": "Flying Haste Vigilance Trample Menace Reach FirstStrike DoubleStrike Deathtouch Defender Fear Intimidate Horsemanship Shadow Landwalk Banding Bushido Rampage Flanking Exalted Prowess Mentor Enlist Myriad Unleash Riot Infect Wither Renown Evolve Battle Dash Ward Hexproof Shroud Protection Indestructible".split(),
    "dmg": ["Lifelink", "Extort"],
    "spells": "Flash Cascade Convoke Improvise Delve Madness Suspend Prototype Storm Affinity Bloodthirst Morph Megamorph Splice".split(),
    "gy": "Undying Persist Unearth Embalm Eternalize Dredge Flashback Escape".split(),
    "tokens": ["Fabricate", "Afterlife", "Backup", "Modular"],
    "counters": ["Modular", "Backup", "Evolve", "Fabricate", "Renown"],
}
KWMAP = collections.defaultdict(set)
for _b, _ks in KW.items():
    for _k in _ks:
        KWMAP[_k].add(_b)


def kw_buckets(gid):
    body = gid[3:]
    if body == "rare":
        return set()
    if body.startswith("other:"):
        body = body[6:]
    out = set()
    for k in body.split("|")[0].split("+"):
        out |= KWMAP.get(k, set())
    return out


def tag_buckets(slug, name, otag_map):
    b = set(otag_map.get(slug, []))
    if b:
        return b
    if slug.startswith("hate-") or name.lower().startswith("works against"):
        return set()
    nb = name_buckets(slug.replace("-", " ") + " . " + name)
    if "counters" in nb and "buff" in nb and not re.search(r"\b(gets?|anthem|pump|equip|aura|gains?|keyword|power|toughness)\b", slug.replace("-", " ") + " " + name, re.I):
        nb.discard("buff")
    return nb


BR2B = {
    "Untapper": "tap", "Anthem": "buff", "Evasion grant": "combat", "Keyword grant": "buff", "Damage prevention": "dmg", "Cost reduction": "spells", "Drain": "dmg", "Theft": "ctrl",
    "Copy spell": "spells", "Impulse": "lib", "Attach": "buff",
    "Board wipe": "removal", "One-sided sweeper": "removal", "Spot removal": "removal", "Creature removal": "removal", "Destroy removal": "removal", "Exile removal": "removal",
    "Bounce removal": "removal", "Sacrifice removal": "sac", "Reanimation": "gy", "Graveyard hate": "gy", "Self-mill": "lib", "Opponent mill": "lib", "Surveil": "lib", "Scry": "lib",
    "Card draw": "draw", "Tutor": "lib", "Discard": "hand", "Counterspell": "spells", "Burn": "dmg", "Mass burn": "dmg", "Lifegain": "dmg", "Ramp": "mana", "Mana dork": "mana",
    "Mana rock": "mana", "Land ramp": "mana", "Token maker": "tokens", "Clone effect": "ctrl", "+1/+1 counters": "counters", "Mass +1/+1 counters": "counters",
}


def J(rel):
    with open(os.path.join(BUILD, *rel.split("/")), encoding="utf-8") as fh:
        return json.load(fh)


def fnv(items):                                 # the same checksum as reports/abilitypages.js
    h = 2166136261
    for i, s in enumerate(items):
        if i:
            h ^= 10
            h = (h * 16777619) & 0xFFFFFFFF
        for ch in s:
            for u in ((ord(ch),) if ord(ch) < 0x10000 else (0xD800 + ((ord(ch) - 0x10000) >> 10), 0xDC00 + ((ord(ch) - 0x10000) & 0x3FF))):
                h ^= u
                h = (h * 16777619) & 0xFFFFFFFF
    return "%08x" % h


def build():
    mi = J("manual_index.json")["groups"]
    leaves = J("ability_taxonomy.json")["leaves"]
    tent = J("tentative_placements.json")["groups"]
    loose = J("loose_groups.json")["groups"]
    tags = J("tag_placements.json")["groups"]
    br = J("branches.json")
    otag = collections.defaultdict(set)
    for b in br["branches"] + br["auto_branches"]:
        k = BR2B.get(b["name"])
        if k:
            for t in b["otags"]:
                otag[t].add(k)
    keys = list(mi)
    masks = []
    for gid in keys:
        layer = mi[gid][3]
        name = mi[gid][0]
        if layer == "leaf":
            l = leaves[gid[5:]]
            s = leaf_buckets(l["sig"], l["name"]) or name_buckets(l["name"])
        elif layer in ("tent", "loose"):
            g = (tent if layer == "tent" else loose)[gid.split(":", 1)[1]]
            short = QUALIFIERS.sub("", g["short"])
            if g["fam"] in FAM_ONLY:                                    # a one-idea family: its default, plus only what the name adds after ", then"
                s = set(FAM[g["fam"]]) | name_buckets(short.partition(", then ")[2])
            else:
                nb = name_buckets(short)
                s = nb or set(FAM.get(g["fam"], []))
        elif layer == "tag":
            g = tags[gid[4:]]
            s = tag_buckets(g["slug"], g["name"], otag)
        elif layer == "kw":
            s = kw_buckets(gid)
        else:
            s = name_buckets(name)
        masks.append(sum(1 << IDX[b] for b in s))
    return {"v": 1, "sig": fnv(keys), "b": [[b[0], b[1], b[2]] for b in BUCKETS], "m": masks}


def dumps(d):
    return (json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def write():
    data = dumps(build())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if not os.path.exists(OUT) or open(OUT, "rb").read() != data:      # an unchanged file is not rewritten
        with open(OUT, "wb") as fh:
            fh.write(data)
    return data


def main():
    if "--check" in sys.argv:
        ok = os.path.exists(OUT) and open(OUT, "rb").read() == dumps(build())
        print("build/buckets/map.json " + ("matches" if ok else "DIFFERS from") + " a fresh derivation")
        sys.exit(0 if ok else 1)
    data = write()
    d = json.loads(data)
    print("wrote build/buckets/map.json: %d groups, %d with a topic, %d bytes" % (len(d["m"]), sum(1 for m in d["m"] if m), len(data)))


if __name__ == "__main__":
    main()
