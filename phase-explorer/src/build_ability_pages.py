#!/usr/bin/env python3
"""Ability-type pages: build/ability_pages/index.json and build/ability_pages/p/<page>.json.

    python src/build_ability_pages.py [--check]

Deterministic and read-only on everything but its own output: it reads build/ability_taxonomy_cards.json (which cards are in scope, their order and rules text),
build/ability_taxonomy_ledger.json (one row per ability: card, face, bucket, index), build/index.json + build/chunks/*.json and build/placements.json (the parsed faces) and
writes only build/ability_pages/. Same inputs, same bytes (sorted keys, no timestamps). src/export_static.py runs it when the flag ABILITY_TYPE_PAGES is on (reports/config.js).
Nothing under corrections/ or archive/ is opened; the slang below is written in this file on purpose.

Ability-type pages are FILTERS AND PAGES, never placements: they are in no group, no count, no figure, and change no leaf, group, id, suggestion or placement. Membership is by ABILITY:
a card is on a page once for every one of its abilities the page's rule accepts, and the page shows the card's own rules line for it.

  build/ability_pages/index.json   {v, sig, n, groups:[[key, name, kind, cards, items, partly, aliases[], description]...]}   key "ab:trig.enters"; kind trig/act/stat/repl.
                                   partly = items on the page whose parse holds an Unimplemented node somewhere (the page still lists them; the page says "only partly read").
  build/ability_pages/p/<page>.json  {v, sig, r:[card index, line index, ...], x:{pair number: text}}   card index = place in the key order of build/ability_taxonomy_cards.json
                                   ("sig" checks it is the same file); line index = the line of the card's text ("t", split on newlines); -1 = no line found, x[pair] then holds the
                                   parser's wording (or nothing).
Keyword abilities (Equip, cycling, Level up ...) are left out of the cost pages; Saga chapters out of the counter pages.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(BUILD, "ability_pages")
KINDS = [("trig", "Triggered"), ("act", "Activated"), ("stat", "Static"), ("repl", "Replacement")]
BUCKET = {"trig": "triggers", "act": "abilities", "stat": "static_abilities", "repl": "replacements"}


def J(rel):
    with open(os.path.join(BUILD, *rel.split("/")), encoding="utf-8") as fh:
        return json.load(fh)


def sig_of(oids):
    """FNV-1a (32 bit) of the ids joined by newlines (the same checksum as build_type_groups.sig_of)."""
    h = 2166136261
    for b in "\n".join(oids).encode("utf-8"):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return "%08x" % h


# ---------------------------------------------------------------- reading the parse
def parts(c):
    if c is None:
        return []
    if c.get("type") == "Composite":
        return [p for x in c["costs"] for p in parts(x)]
    return [c]


def refs_self(f):
    if not isinstance(f, dict):
        return False
    return f.get("type") == "SelfRef" or (f.get("type") == "Or" and any(refs_self(x) for x in f.get("filters", [])))


def typed(f):
    return isinstance(f, dict) and f.get("type") in ("Typed", "Or")


def tfs(f):
    if not isinstance(f, dict):
        return []
    return [a if isinstance(a, str) else next(iter(a)) for a in f.get("type_filters", [])]


def attached(f):
    if not isinstance(f, dict):
        return False
    if f.get("type") == "AttachedTo":
        return True
    if f.get("type") == "Or":
        return any(attached(x) for x in f.get("filters", []))
    return any(p.get("type") in ("EnchantedBy", "EquippedBy", "FortifiedBy") for p in f.get("properties", []))


def mname(m):
    return "Unknown" if isinstance(m, dict) and "Unknown" in m else (m if isinstance(m, str) else next(iter(m)))


def mods(s):
    return {x.get("type") for x in s.get("modifications") or [] if isinstance(x, dict)}


def desc(x):
    return x.get("description") or ""


def has_unimpl(x):
    if isinstance(x, dict):
        return x.get("type") == "Unimplemented" or any(has_unimpl(v) for v in x.values())
    if isinstance(x, list):
        return any(has_unimpl(v) for v in x)
    return False


chapter = lambda x: re.match(r"^Chapter \d", desc(x)) is not None
tm = lambda t: mname(t["mode"])
cp = lambda a: {p["type"] for p in parts(a["cost"])}
eff = lambda a: (a.get("effect") or {}).get("type")
ex_eff = lambda r: ((r.get("execute") or {}).get("effect") or {}).get("type") if isinstance(r.get("execute"), dict) else None
is_act = lambda a: a["kind"] == "Activated" and bool(desc(a))        # keyword abilities (no description) are not on the cost pages
smode = lambda s: s["mode"] if isinstance(s["mode"], str) else next(iter(s["mode"]))

# (key, name, kind, rule in one line for the page, aliases, test)
PAGES = []


def page(key, name, rule, aliases, fn):
    PAGES.append(("ab:" + key, name, key.split(".")[0], rule, aliases, fn))


# ---- triggered
page("trig.enters", "Enters the battlefield (ETB)", "Triggered abilities that happen when the card itself enters the battlefield, including “this or another”.",
     ["etb", "enters the battlefield", "enter the battlefield", "comes into play", "when this enters", "enters trigger", "enter triggers", "etb trigger"],
     lambda t: tm(t) == "ChangesZone" and t.get("destination") == "Battlefield" and refs_self(t.get("valid_card")) and not chapter(t))
page("trig.enters-other", "Another permanent enters", "Triggered abilities that happen when another creature, artifact or other permanent enters (lands are on Landfall).",
     ["whenever another creature enters", "creature enters trigger", "enters under your control", "other etb", "constellation"],
     lambda t: tm(t) == "ChangesZone" and t.get("destination") == "Battlefield" and typed(t.get("valid_card")) and tfs(t.get("valid_card")) != ["Land"])
page("trig.landfall", "Landfall (a land enters)", "Triggered abilities that happen when a land enters the battlefield.",
     ["landfall", "land enters", "land etb"],
     lambda t: tm(t) == "ChangesZone" and t.get("destination") == "Battlefield" and typed(t.get("valid_card")) and tfs(t.get("valid_card")) == ["Land"])
page("trig.dies", "Dies (this creature)", "Triggered abilities that happen when the card itself dies.",
     ["dies", "death trigger", "death triggers", "when this dies", "dies trigger", "leaves to the graveyard", "ltb dies"],
     lambda t: tm(t) == "ChangesZone" and t.get("origin") == "Battlefield" and t.get("destination") == "Graveyard" and refs_self(t.get("valid_card")))
page("trig.dies-other", "Another creature or permanent dies", "Triggered abilities that happen when another creature or permanent is put into a graveyard from the battlefield.",
     ["whenever a creature dies", "creature dies", "another creature dies", "morbid", "death watch", "aristocrats"],
     lambda t: tm(t) == "ChangesZone" and t.get("origin") == "Battlefield" and t.get("destination") == "Graveyard" and typed(t.get("valid_card")))
page("trig.leaves", "Leaves the battlefield", "Triggered abilities that happen when a permanent leaves the battlefield.",
     ["leaves the battlefield", "leaves play", "ltb", "leave the battlefield trigger"],
     lambda t: tm(t) == "LeavesBattlefield")
page("trig.attacks", "Attacks", "Triggered abilities that happen when a creature attacks (also “attacks or blocks” and “enters or attacks”).",
     ["attacks", "attack trigger", "attack triggers", "whenever this attacks", "when attacking"],
     lambda t: tm(t) in ("Attacks", "AttacksOrBlocks", "EntersOrAttacks"))
page("trig.you-attack", "You attack (one or more creatures)", "Triggered abilities that happen when you attack with one or more creatures.",
     ["whenever you attack", "you attack", "battalion", "attack with creatures"],
     lambda t: tm(t) == "YouAttack")
page("trig.blocks", "Blocks", "Triggered abilities that happen when a creature blocks (also “attacks or blocks”).",
     ["blocks", "block trigger", "whenever this blocks"],
     lambda t: tm(t) in ("Blocks", "AttacksOrBlocks"))
page("trig.combat-damage", "Deals combat damage", "Triggered abilities that happen when a creature deals combat damage.",
     ["combat damage", "deals combat damage", "combat damage trigger", "hits a player", "saboteur", "connects"],
     lambda t: tm(t) in ("DamageDone", "DamageDoneOnceByController") and t.get("damage_kind") == "CombatOnly")
page("trig.upkeep", "Upkeep", "Triggered abilities that happen at the beginning of an upkeep.",
     ["upkeep", "upkeep trigger", "at the beginning of your upkeep", "beginning of upkeep"],
     lambda t: tm(t) == "Phase" and t.get("phase") == "Upkeep")
page("trig.end-step", "End step", "Triggered abilities that happen at the beginning of an end step.",
     ["end step", "end of turn trigger", "at the beginning of your end step", "end step trigger", "eot"],
     lambda t: tm(t) == "Phase" and t.get("phase") == "End")
page("trig.begin-combat", "Beginning of combat", "Triggered abilities that happen at the beginning of combat.",
     ["beginning of combat", "begin combat", "start of combat", "combat trigger"],
     lambda t: tm(t) == "Phase" and t.get("phase") == "BeginCombat")
page("trig.cast", "Casts a spell", "Triggered abilities that happen when a player (you, an opponent, anyone) casts a spell.",
     ["cast trigger", "whenever you cast", "casts a spell", "spell cast trigger", "magecraft", "prowess trigger"],
     lambda t: tm(t) in ("SpellCast", "SpellCastOrCopy") and not (isinstance(t.get("valid_card"), dict) and t["valid_card"].get("type") == "SelfRef"))
page("trig.draw", "Draws a card", "Triggered abilities that happen when a player draws a card.",
     ["draw trigger", "whenever you draw", "when you draw a card", "draws a card"],
     lambda t: tm(t) == "Drawn")
page("trig.counter-added", "Counters are put on something", "Triggered abilities that happen when one or more counters are put on a permanent (not Saga chapters).",
     ["counter trigger", "counters put on", "whenever counters are put", "+1/+1 counter trigger"],
     lambda t: tm(t) == "CounterAdded" and not chapter(t))
page("trig.life-gained", "Gains life", "Triggered abilities that happen when a player gains life.",
     ["lifegain trigger", "whenever you gain life", "life gain trigger", "gains life"],
     lambda t: tm(t) == "LifeGained")
page("trig.becomes-target", "Becomes the target", "Triggered abilities that happen when a permanent becomes the target of a spell or ability.",
     ["becomes the target", "targeted trigger", "when targeted", "heroic"],
     lambda t: tm(t) == "BecomesTarget")
# ---- activated
page("act.mana-abilities", "Mana abilities", "Activated abilities that produce mana, whatever they cost.",
     ["mana ability", "mana abilities", "tap for mana", "mana rock", "mana dork"],
     lambda a: is_act(a) and eff(a) == "Mana")
page("act.tap", "Tap abilities ({T}), not mana", "Activated abilities with {T} in the cost that do something other than add mana.",
     ["tap ability", "tap abilities", "{t} ability", "tap to activate", "tap cost"],
     lambda a: is_act(a) and "Tap" in cp(a) and eff(a) not in ("Mana", "Attach"))
page("act.mana", "Pay mana, no other cost", "Activated abilities whose whole cost is mana (not Equip and not mana abilities).",
     ["mana ability cost", "pay mana ability", "mana only cost", "pump ability", "firebreathing"],
     lambda a: is_act(a) and cp(a) == {"Mana"} and eff(a) not in ("Mana", "Attach"))
page("act.sacrifice", "Sacrifice as a cost", "Activated abilities that have sacrificing something in the cost.",
     ["sacrifice ability", "sacrifice cost", "sac ability", "sac outlet", "sacrifice outlet"],
     lambda a: is_act(a) and "Sacrifice" in cp(a))
page("act.discard", "Discard a card as a cost", "Activated abilities that have discarding a card in the cost (cycling is not here).",
     ["discard cost", "discard ability", "discard a card cost", "rummage cost"],
     lambda a: is_act(a) and any(p["type"] == "Discard" and not p.get("self_ref") for p in parts(a["cost"])))
page("act.exile-gy", "Exile from graveyard as a cost", "Activated abilities that exile cards from a graveyard to pay for them.",
     ["exile from graveyard", "graveyard ability", "exile this card from your graveyard", "graveyard activated"],
     lambda a: is_act(a) and any(p["type"] == "Exile" and p.get("zone") == "Graveyard" for p in parts(a["cost"])))
page("act.remove-counter", "Remove a counter as a cost", "Activated abilities that remove counters from something to pay for them.",
     ["remove a counter", "remove counter cost", "counter cost", "remove counters"],
     lambda a: is_act(a) and "RemoveCounter" in cp(a))
page("act.pay-life", "Pay life as a cost", "Activated abilities that have paying life in the cost.",
     ["pay life", "pay life cost", "life cost"],
     lambda a: is_act(a) and "PayLife" in cp(a))
page("act.loyalty", "Loyalty abilities", "Planeswalker abilities: the plus, minus and zero loyalty abilities.",
     ["loyalty ability", "loyalty abilities", "planeswalker ability", "planeswalker abilities", "plus ability", "minus ability", "ultimate"],
     lambda a: a["kind"] == "Activated" and "Loyalty" in cp(a))
# ---- static
page("stat.anthem", "Anthems and lords (+N/+N to others)", "Static abilities that give other creatures or permanents +N/+N (not Equipment or Auras).",
     ["anthem", "anthems", "lord", "lords", "tribal lord", "overrun", "buff all", "creatures you control get"],
     lambda s: smode(s) == "Continuous" and (mods(s) & {"AddPower", "AddToughness"}) and typed(s.get("affected")) and (tfs(s.get("affected")) or s["affected"].get("type") == "Or")
     and not refs_self(s.get("affected")) and not attached(s.get("affected")))
page("stat.keyword-grant", "Gives keywords to other permanents", "Static abilities that give a keyword (flying, lifelink, ward ...) to other permanents (not Equipment or Auras).",
     ["gives keywords", "grant flying", "keyword lord", "creatures you control have", "keyword grant"],
     lambda s: smode(s) == "Continuous" and "AddKeyword" in mods(s) and typed(s.get("affected")) and (tfs(s.get("affected")) or s["affected"].get("type") == "Or")
     and not refs_self(s.get("affected")) and not attached(s.get("affected")))
page("stat.attached-bonus", "Equipment and Aura bonuses", "Static abilities that give the equipped or enchanted permanent +N/+N or a keyword.",
     ["equipment bonus", "aura bonus", "equipped creature gets", "enchanted creature gets", "equipment buff", "aura buff"],
     lambda s: smode(s) == "Continuous" and (mods(s) & {"AddPower", "AddToughness", "AddKeyword"}) and attached(s.get("affected")))
page("stat.cost-reduce", "Cost reduction", "Static abilities that make spells or abilities cost less.",
     ["cost reduction", "cost reducer", "costs less", "spells cost less", "cost reduction effect", "reduce cost"],
     lambda s: smode(s) in ("ReduceCost", "ReduceAbilityCost"))
page("stat.cost-raise", "Cost increase (taxes)", "Static abilities that make spells or abilities cost more.",
     ["cost increase", "tax", "taxes", "tax effect", "costs more", "spells cost more", "rhystic tax"],
     lambda s: smode(s) == "RaiseCost")
page("stat.cant-block", "Can't block", "Static abilities that stop creatures from blocking.",
     ["cant block", "can't block", "cannot block", "no blockers"],
     lambda s: smode(s) in ("CantBlock", "CantAttackOrBlock"))
page("stat.cant-attack", "Can't attack", "Static abilities that stop creatures from attacking.",
     ["cant attack", "can't attack", "cannot attack", "pacifism effect", "propaganda"],
     lambda s: smode(s) in ("CantAttack", "CantAttackOrBlock"))
page("stat.evasion", "Can't be blocked (by anyone or by some)", "Static abilities that make a creature unable to be blocked, or unable to be blocked by some creatures.",
     ["evasion", "unblockable", "cant be blocked", "can't be blocked", "cannot be blocked"],
     lambda s: smode(s) in ("CantBeBlocked", "CantBeBlockedBy"))
page("stat.cant-be-countered", "Can't be countered", "Static abilities that stop a spell from being countered.",
     ["uncounterable", "cant be countered", "can't be countered", "cannot be countered"],
     lambda s: smode(s) == "CantBeCountered")
page("stat.cant-untap", "Doesn't untap", "Static abilities that stop a permanent from untapping.",
     ["doesnt untap", "doesn't untap", "does not untap", "stay tapped", "no untap"],
     lambda s: smode(s) == "CantUntap")
page("stat.must-attack", "Must attack", "Static abilities that force a creature to attack each combat.",
     ["must attack", "attacks each combat", "forced attack", "attacks each turn"],
     lambda s: smode(s) == "MustAttack")
# ---- replacement
page("repl.etb-tapped", "Enters tapped", "Replacement effects that make a permanent enter the battlefield tapped.",
     ["enters tapped", "etb tapped", "tapland", "tapped land", "enter tapped"],
     lambda r: r["event"] in ("Moved", "ChangeZone") and ex_eff(r) == "Tap")
page("repl.etb-counters", "Enters with counters", "Replacement effects that make a permanent enter the battlefield with counters on it.",
     ["enters with counters", "etb counters", "enter with counters", "enters with +1/+1 counters"],
     lambda r: r["event"] in ("Moved", "ChangeZone") and ex_eff(r) == "PutCounter" and "Saga ETB" not in desc(r))
page("repl.damage", "Damage is prevented or changed", "Replacement effects that prevent, redirect or change damage.",
     ["damage prevention", "prevent damage", "damage replacement", "redirect damage", "prevention"],
     lambda r: r["event"] == "DamageDone")
page("repl.dies-exile", "Leaves for another place instead of the graveyard", "Replacement effects that exile (or shuffle away) a card instead of letting it go to the graveyard.",
     ["exile instead", "exile instead of dying", "dies exile", "rest in peace", "graveyard replacement"],
     lambda r: (r["event"] == "Moved" and r.get("destination_zone") == "Graveyard" and ex_eff(r) == "ChangeZone") or (r["event"] == "Destroy" and ex_eff(r) == "ChangeZone"))


# ---------------------------------------------------------------- rules line of the card for an ability
def nrm(s):
    return re.sub(r"\s+", " ", s.replace("—", "-").replace("−", "-").replace("–", "-")).strip().lower()


KEYLINE = [(lambda a: eff(a) == "Attach", r"^(equip|reconfigure|fortify)"), (lambda a: any(p["type"] == "Discard" and p.get("self_ref") for p in parts(a.get("cost"))), r"cycling")]


def find_line(lines, e, item, bucket):
    """Index of the card text line that holds this ability, or (-1, parser wording)."""
    d = desc(item)
    name = e.get("name") or ""
    if d:
        cands = [d.replace("~", name), d.replace("~", name.split(",")[0]), d.replace("~", name.split(" ")[0])]
        for c in cands:
            nd = nrm(c)[:60]
            for i, l in enumerate(lines):
                if nd and nd in l:
                    return i, None
            if " - " in nd[:40]:                                   # an ability word the line carries: "landfall - whenever ..."
                nd2 = nd.split(" - ", 1)[1]
                for i, l in enumerate(lines):
                    if nd2 and nd2 in l:
                        return i, None
        if "~" in d:                                               # the parser keeps “~” for the card's own name; the text says the name or “this creature”
            rx = re.compile(r"(?:this [a-z]+|[^,.:;]{1,40}?)".join(re.escape(x) for x in nrm(d)[:70].split("~")))
            for i, l in enumerate(lines):
                if rx.search(l):
                    return i, None
        if ", " in nrm(d):                                         # the parser split “enters or dies” into two triggers: match on what happens
            tail = re.sub(r" ([.,;])", r"", nrm(d).split(", ", 1)[1])[:40]
            if len(tail) >= 12:
                for i, l in enumerate(lines):
                    if tail in re.sub(r" ([.,;])", r"", l):
                        return i, None
        return -1, cands[0]
    if bucket == "abilities":
        for test, rx in KEYLINE:
            if test(item):
                for i, l in enumerate(lines):
                    if re.search(rx, l):
                        return i, None
    return -1, None


# ---------------------------------------------------------------- the build
def build():
    cards = J("ability_taxonomy_cards.json")["cards"]
    oids = list(cards)
    cidx = {o: i for i, o in enumerate(oids)}
    ledger = J("ability_taxonomy_ledger.json")["rows"]
    idx = {r["id"]: r for r in J("index.json")["rows"]}
    rec = J("placements.json")["recovered"]["chunk"]
    chunks = {}

    def face(fid):
        if fid in idx:
            c = idx[fid]["ch"]
            if c not in chunks:
                chunks[c] = J("chunks/%d.json" % c)
            return chunks[c].get(fid) or {}
        return rec.get(fid) or {}

    lines_of = {}
    members = {k: {} for k, *_ in PAGES}               # key -> {(card idx, line idx, text): partly}
    items = {k: 0 for k, *_ in PAGES}
    partly = {k: 0 for k, *_ in PAGES}
    by_kind = {}
    for k, name, kind, rule, al, fn in PAGES:
        by_kind.setdefault(kind, []).append((k, fn))
    for row in ledger:
        oid, fid, bucket, i, mode = row[0], row[1], row[2], row[3], row[4]
        if oid not in cidx or mode is not None:
            continue                                    # a modal row is the same ability as the row it comes from
        kind = {v: k for k, v in BUCKET.items()}[bucket]
        e = face(fid)
        item = (e.get(bucket) or [])[i]
        todo = []
        for k, fn in by_kind.get(kind, []):
            try:
                ok = bool(fn(item))
            except Exception:
                ok = False
            if ok:
                todo.append(k)
        if not todo:
            continue
        if oid not in lines_of:
            lines_of[oid] = [nrm(l) for l in (cards[oid].get("t") or "").split("\n")]
        li, tx = find_line(lines_of[oid], e, item, bucket)
        u = has_unimpl(item)
        for k in todo:
            items[k] += 1
            if u:
                partly[k] += 1
            members[k].setdefault((cidx[oid], li, tx if li < 0 else None), u)
    sig = sig_of(oids)
    groups, pages = [], {}
    for k, name, kind, rule, al, fn in PAGES:
        ms = sorted(members[k], key=lambda m: (m[0], m[1], m[2] or ""))
        flat, x = [], {}
        for n, (c, l, tx) in enumerate(ms):
            flat += [c, l]
            if tx:
                x[str(n)] = tx
        doc = {"v": 1, "sig": sig, "r": flat}
        if x:
            doc["x"] = x
        pages[k] = doc
        groups.append([k, name, kind, len({m[0] for m in ms}), len(ms), partly[k], sorted(set(al)), rule])
    index = {"v": 1, "sig": sig, "n": len(oids), "groups": groups}
    return index, pages


def dumps(d):
    return (json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def fname(key):
    return key[3:] + ".json"


def outputs():
    index, pages = build()
    outs = {"ability_pages/index.json": dumps(index)}
    for k, doc in pages.items():
        outs["ability_pages/p/" + fname(k)] = dumps(doc)
    return outs, index


def write():
    outs, index = outputs()
    for rel, data in outs.items():
        p = os.path.join(BUILD, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not os.path.exists(p) or open(p, "rb").read() != data:      # an unchanged file is not rewritten
            with open(p, "wb") as fh:
                fh.write(data)
    keep = {os.path.join(BUILD, *r.split("/")) for r in outs}
    for p in glob.glob(os.path.join(OUT, "p", "*.json")):              # a page that was dropped from the list leaves no file behind
        if p not in keep:
            os.remove(p)
    return outs, index


def main():
    if "--check" in sys.argv:
        outs, _ = outputs()
        bad = [r for r, d in outs.items() if not os.path.exists(os.path.join(BUILD, *r.split("/"))) or open(os.path.join(BUILD, *r.split("/")), "rb").read() != d]
        print("ability_pages files %s" % ("up to date" if not bad else "differ: " + ", ".join(bad)))
        sys.exit(1 if bad else 0)
    outs, index = write()
    print("wrote %d files to build/ability_pages (%s bytes); %d pages" % (len(outs), format(sum(len(d) for d in outs.values()), ","), len(index["groups"])))


if __name__ == "__main__":
    main()
