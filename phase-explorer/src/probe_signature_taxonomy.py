#!/usr/bin/env python3
"""Signature-taxonomy PROBE -- investigation only. Places nothing, changes nothing.

    python src/probe_signature_taxonomy.py   # -> build/signature_probe.json, build/signature_probe_leaves.json

Question: would leaves built from per-ability exact signatures (read from the parsed structure), with
backoff from fine to coarse levels, organize abilities better than the frozen whole-card clustering?

Population: every ability item (one row of build/ability_ledger.json) of a card whose pipeline status is
clean (clustered, noise, unclustered, placed_by_ability, no_extractable_effect, and recovered faces whose
stage is clean), plus the items of partial / unmodelled cards (and recovered partial faces). Excluded:
items flagged by the condition-drop detector (build/condition_drops.json), items holding a gap node
(build_ledger.gap_fragments on the item alone), corrections-flagged cards. No Scryfall tag data is read.

Fields per ability (all from the parse; see reports/signature-taxonomy-probe.md for the inventory):
  fam    effect family (a fixed map over effect types / static modes; a judgment call)
  rtype  raw effect type (static: "static:<mode>", replacement with no effect: "repl:<event>")
  ftype  rtype with the "All" suffix folded (DestroyAll -> Destroy)
  mods   for granted / continuous effects: the modification kinds (AddKeyword, AddPower, ...)
  frm/to zone from / zone to (origin or the target's InZone; destination, or the type's own, or the
         destination of the first zone-moving chain step for search / dig effects)
  ctr    counter type, lower-cased (counter_type / counter_kind)
  who    player scope: player_scope, else a player-kind target, else the effect's `player` field
  obj    target type: core type filters (Or -> union; ParentTarget -> the repeat_for filter if any);
         Token -> the token's card types; Mana -> what it produces; statics -> `affected` (+ spell filter)
  ctrl   the target's controller (You / Opponent / TargetPlayer / -)
  quant  all (an *All type) | each (repeat_for) | multi (multi_target max > 1) | one | -
  det    detail: subtypes + properties of the target, keyword / token names, duration, condition
         presence, wrapper unwrapped, and chain shape (up to 3 later steps: verb + target type)

Wrapper effects (TargetOnly, Choose, PayCost, CreateDelayedTrigger) are unwrapped: the head is the first
non-wrapper step; the wrapper is kept in `det`.

Levels (two orders, same finest level, so they differ only in the backoff path):
  A (as suggested):   L1 fam | L2 rtype | L3 +obj | L4 +ctrl,quant,frm,to | L5 +ctr,who,mods,det
  B (verb first):     L1 fam | L2 ftype,frm,to,ctr,who,mods | L3 +obj | L4 +ctrl,quant | L5 +det
  C (B, type floor):  L1 ftype | L2 +frm,to,ctr,who,mods | L3 +obj | L4 +ctrl,quant | L5 +det
                      (family is kept only as a browse branch, never as a leaf)

Backoff (MIN = 3 and 5), two readings, both reported:
  literal (keys "C5"): the finest level whose signature is held by >= MIN abilities in total. A node can
    hold fewer than MIN abilities directly when its other holders went finer (its "other" remainder).
  residual (keys "C5r"): finest first, a signature held by >= MIN still-unassigned abilities becomes a
    leaf, the rest pass up; every leaf has >= MIN members.
What no level reaches is "below minimum at every level".

Writes build/signature_probe.json (measurements) and build/signature_probe_leaves.json (per-ability
signatures and leaves, for the hand check). Sorted keys; identical bytes across runs.
"""
import collections
import io
import json
import os
import random
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "hdbscan" not in sys.modules:
    sys.modules["hdbscan"] = types.ModuleType("hdbscan")
import build_ledger as BL           # noqa: E402  gap_fragments only
import cluster_structural as cs     # noqa: E402  shape_tag only

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
CLEAN = {"clustered", "noise", "unclustered", "placed_by_ability", "no_extractable_effect"}
GAPPY = {"partial", "unmodelled_node"}
MINS = (3, 5)
WRAPPERS = {"TargetOnly", "Choose", "PayCost", "CreateDelayedTrigger"}
CORE_TYPES = {"Artifact", "Battle", "Card", "Creature", "Enchantment", "Instant", "Kindred", "Land",
              "Permanent", "Planeswalker", "Sorcery", "Spell", "Tribal"}
SUBTYPE_CORE = {}   # filled by population(): subtype -> the core type most cards carrying it have
SEARCHY = {"SearchLibrary", "Dig", "RevealUntil", "Seek", "ExileFromTopUntil", "RevealTop", "Discover"}

FAMILY = {}
for fam, ts in {
    "Destroy": ["Destroy", "DestroyAll"],
    "Damage": ["DealDamage", "DamageAll", "DamageEachPlayer", "Fight"],
    "Life": ["GainLife", "LoseLife", "SetLifeTotal"],
    "Zone change": ["ChangeZone", "ChangeZoneAll", "Bounce", "PutAtLibraryPosition", "PutOnTopOrBottom", "PhaseOut",
                    "Shuffle"],
    "Library": ["SearchLibrary", "Dig", "ExileTop", "RevealTop", "RevealUntil", "ExileFromTopUntil", "Scry",
                "Surveil", "Mill", "Seek", "Explore", "ExploreAll", "Discover", "Learn", "Conjure"],
    "Card draw": ["Draw", "Connive"],
    "Discard / hand": ["Discard", "RevealHand"],
    "Sacrifice": ["Sacrifice", "ChooseAndSacrificeRest"],
    "Counters": ["PutCounter", "PutCounterAll", "RemoveCounter", "MoveCounters", "MultiplyCounter", "Proliferate",
                 "GivePlayerCounter", "Adapt", "Monstrosity", "Bolster", "Double", "LoseAllPlayerCounters",
                 "GainEnergy", "TimeTravel"],
    "Tokens": ["Token", "CopyTokenOf", "Investigate", "Incubate", "Populate", "Amass", "Forage"],
    "Mana": ["Mana"],
    "Pump / grant": ["Pump", "PumpAll", "GenericEffect", "SwitchPT", "DoublePT", "DoublePTAll", "Animate",
                     "BlightEffect"],
    "Tap / untap": ["Tap", "TapAll", "Untap", "UntapAll", "Detain"],
    "Counter spell": ["Counter", "ChangeTargets"],
    "Copy": ["CopySpell", "BecomeCopy"],
    "Control": ["GainControl", "ExchangeControl", "ControlNextTurn"],
    "Cast / play": ["CastFromZone", "GrantCastingPermission", "GrantNextSpellAbility", "ReduceNextSpellCost"],
    "Combat": ["ForceBlock", "Goad", "RemoveFromCombat", "AdditionalCombatPhase"],
    "Attach": ["Attach"],
    "Protection": ["Regenerate", "PreventDamage"],
    "Transform / face": ["Transform", "BecomePrepared", "Manifest", "ManifestDread", "SetDayNight"],
    "Game / player": ["WinTheGame", "LoseTheGame", "ExtraTurn", "SkipNextTurn", "BecomeMonarch", "CreateEmblem",
                      "VentureIntoDungeon", "RingTemptsYou", "SetClassLevel", "SolveCase", "GiftDelivery",
                      "RollDie", "FlipCoin", "FlipCoins", "FlipCoinUntilLose", "CollectEvidence", "Suspect",
                      "AddRestriction"],
    "Choice / wrapper": ["Choose", "TargetOnly", "PayCost", "CreateDelayedTrigger"],
    "Keyword-handled": ["RuntimeHandled"],
}.items():
    for t in ts:
        FAMILY[t] = fam


def static_family(mode):
    if mode == "Continuous":
        return "Static: continuous"
    if mode in ("ReduceCost", "RaiseCost"):
        return "Static: cost change"
    if mode.startswith(("Cant", "Must")) or mode in ("BlockRestriction", "ExtraBlockers", "CanAttackWithDefender"):
        return "Static: restriction"
    return "Static: other rule"


def jl(name):
    return json.load(io.open(os.path.join(BUILD, name), encoding="utf-8"))


# ---------------------------------------------------------------- population
def population():
    rows = jl("index.json")["rows"]
    byid = {r["id"]: r for r in rows}
    chunks = {n: jl("chunks/%d.json" % n) for n in range(64)}
    seen = collections.defaultdict(collections.Counter)
    for ch in chunks.values():
        for e in ch.values():
            ct = e.get("card_type") or {}
            for st in ct.get("subtypes") or []:
                for c in ct.get("core_types") or []:
                    if c != "Kindred" and c != "Tribal":
                        seen[st][c] += 1
    for st, c in seen.items():
        top, n = c.most_common(1)[0]
        if n >= 0.8 * sum(c.values()):
            SUBTYPE_CORE[st] = top
    P = jl("placements.json")
    rec, stages = P["recovered"]["chunk"], P["recovered"]["stages"]
    AL = jl("ability_ledger.json")
    flagged = {(h["oid"], h["bucket"], h["idx"]) for h in jl("condition_drops.json")}
    items, excl = [], collections.Counter()
    for row in AL["rows"]:
        oid, face, b, i, text, state, route, leaf, reason, detail, best, score, own = row
        cname, status, method, cleaf = AL["cards"][oid]
        e = chunks[byid[face]["ch"]][face] if face in byid else rec.get(face)
        if status == "missing_from_export":
            st = next((f["stage"] for f in stages.get(oid, []) if f["id"] == face), None)
            kind = "clean" if st in ("clean", "no_extractable_effect") else ("gap" if st in GAPPY else "other")
        else:
            kind = "clean" if status in CLEAN else ("gap" if status in GAPPY else "other")
        if e is None or kind == "other":
            excl["status:" + status] += 1
            continue
        it = e[b][i]
        if (oid, b, i) in flagged:
            excl["flagged:" + kind] += 1
            continue
        if BL.gap_fragments({b: [it]}, e.get("name") or ""):
            excl["item_gap:" + kind] += 1
            continue
        items.append({"oid": oid, "face": face, "b": b, "i": i, "text": text, "state": state, "route": route,
                      "leaf": leaf, "reason": reason, "best": best, "score": score, "status": status,
                      "method": method, "cleaf": cleaf, "name": e.get("name"), "kind": kind, "item": it})
    return items, excl, AL


# ---------------------------------------------------------------- fields
def exec_and_effect(b, it):
    if b == "abilities":
        return it, it.get("effect")
    if b in ("triggers", "replacements"):
        ex = it.get("execute") or {}
        return ex, ex.get("effect")
    return {}, None


def target_of(e):
    for k in ("target", "filter", "valid_card", "affected", "valid_target"):
        if isinstance(e.get(k), dict):
            return e[k]
    return None


def walk_props(node, fn):
    if isinstance(node, dict):
        fn(node)
        for v in node.values():
            walk_props(v, fn)
    elif isinstance(node, list):
        for v in node:
            walk_props(v, fn)


def obj_parts(t, ex=None):
    """(core object type, controller, detail tags, zones) of a target / filter node."""
    if not isinstance(t, dict):
        return "-", "-", [], []
    ty = t.get("type")
    if ty == "Typed":
        tf = [cs.shape_tag(f) for f in t.get("type_filters") or []]
        core = sorted(f for f in tf if f and f.split(":")[-1] in CORE_TYPES)
        sub = sorted(f for f in tf if f and f.split(":")[-1] not in CORE_TYPES)
        props = [p for p in t.get("properties") or [] if isinstance(p, dict)]
        zones = [p.get("zone") for p in props if p.get("type") == "InZone"]
        tags = sorted(cs.shape_tag(p) for p in props if p.get("type") != "InZone")
        if not core and sub:
            # the parser records "Islands" as Subtype:Island only; read the core type the corpus gives that subtype
            implied = sorted({SUBTYPE_CORE.get(f.split(":")[-1]) for f in sub} - {None})
            core = implied if len(implied) == 1 else core
        return ("+".join(core) or "object"), (t.get("controller") or "-"), sub + tags, zones
    if ty in ("Or", "And"):
        parts = [obj_parts(f) for f in t.get("filters") or []]
        core = ("|" if ty == "Or" else "&").join(sorted({p[0] for p in parts})) or ty
        ctrls = {p[1] for p in parts}
        return core, (ctrls.pop() if len(ctrls) == 1 else "mixed"), sorted({d for p in parts for d in p[2]}), \
            sorted({z for p in parts for z in p[3] if z})
    if ty == "ParentTarget" and ex and isinstance(ex.get("repeat_for"), dict):
        flt = []
        walk_props(ex["repeat_for"], lambda n: flt.append(n["filter"]) if n.get("type") == "ObjectCount" and
                   isinstance(n.get("filter"), dict) else None)
        if flt:
            return obj_parts(flt[0])
    return {"SelfRef": "self", "Any": "any target", "Player": "player", "Controller": "you",
            "TriggeringPlayer": "triggering player", "DefendingPlayer": "defending player",
            "ParentTargetController": "its controller", "ParentTarget": "parent"}.get(ty, ty or "-"), "-", [], []


PLAYER_OBJ = {"player", "you", "triggering player", "defending player", "its controller"}


def chain_steps(ex):
    out, n = [], ex
    while isinstance(n, dict) and isinstance(n.get("sub_ability"), dict):
        n = n["sub_ability"]
        out.append(n)
    return out


def head(ex, e):
    """Unwrap wrapper effects: (exec node, effect node, wrapper chain)."""
    wraps, wrap_e = [], None
    for _ in range(4):
        if not isinstance(e, dict) or e.get("type") not in WRAPPERS:
            break
        if e["type"] == "CreateDelayedTrigger" and isinstance(e.get("effect"), dict):
            nxt = e["effect"]
            nex, ne = nxt, nxt.get("effect")
        elif isinstance(ex.get("sub_ability"), dict):
            nex = ex["sub_ability"]
            ne = nex.get("effect")
        else:
            break
        if not isinstance(ne, dict):
            break
        wraps.append(e["type"])
        wrap_e = e
        ex, e = nex, ne
    return ex, e, wraps, wrap_e


def step_verb(st):
    e = st.get("effect") or {}
    t = e.get("type") or "?"
    to = e.get("destination") or ""
    ctr = (e.get("counter_type") or "").lower()
    o = obj_parts(target_of(e), st)[0]
    return t + (">" + to if to else "") + ("/" + ctr if ctr else "") + ("@" + o if o != "-" else "")


def fields(x):
    b, it = x["b"], x["item"]
    if b == "static_abilities":
        m = it.get("mode")
        mname = m if isinstance(m, str) else ",".join(sorted(m)) if isinstance(m, dict) else str(m)
        mods = sorted({md.get("type") for md in it.get("modifications") or [] if isinstance(md, dict)})
        kws = sorted({str(md.get("keyword")) for md in it.get("modifications") or []
                      if isinstance(md, dict) and md.get("type") == "AddKeyword"})
        o, ctrl, det, zones = obj_parts(it.get("affected"))
        if isinstance(m, dict):
            for v in m.values():
                if isinstance(v, dict) and isinstance(v.get("spell_filter"), dict):
                    o = o + "/spell:" + obj_parts(v["spell_filter"])[0]
        det = det + ["kw:" + k for k in kws] + (["cond"] if it.get("condition") else [])
        return dict(fam=static_family(mname), rtype="static:" + mname, ftype="static:" + mname,
                    mods=",".join(mods), frm=",".join(zones), to="", ctr="", who="", obj=o, ctrl=ctrl, quant="-",
                    det="|".join(det), wraps=[], usable=True)
    ex, e = exec_and_effect(b, it)
    if not isinstance(e, dict) or not isinstance(e.get("type"), str):
        if b == "replacements":
            o, ctrl, det, _ = obj_parts(it.get("valid_card"))
            scal = sorted("%s=%s" % (k, v) for k, v in it.items()
                          if isinstance(v, str) and k not in ("description", "event", "mode"))
            ev = str(it.get("event"))
            return dict(fam="Replacement", rtype="repl:" + ev, ftype="repl:" + ev, mods="", frm="", to="", ctr="",
                        who="", obj=o, ctrl=ctrl, quant="-", det="|".join(det + scal), wraps=[], usable=True)
        return dict(fam="none", rtype="none", ftype="none", mods="", frm="", to="", ctr="", who="", obj="-",
                    ctrl="-", quant="-", det="", wraps=[], usable=False)
    if e["type"] == "GenericEffect" and not e.get("static_abilities") and ex.get("mode_abilities"):
        # modal placeholder: the content is in mode_abilities (one mode = one AbilityDefinition)
        modes = sorted({step_verb(m) for m in ex["mode_abilities"] if isinstance(m, dict)})
        return dict(fam="Choice / wrapper", rtype="Modal", ftype="Modal", mods="", frm="", to="", ctr="", who="",
                    obj="-", ctrl="-", quant="-", det="modes:" + ">".join(modes), wraps=["Modal"], usable=True)
    ex, e, wraps, wrap_e = head(ex, e)
    rt = e["type"]
    ft = rt[:-3] if rt.endswith("All") and rt not in ("ExploreAll",) else rt
    if rt == "ExploreAll":
        ft = "Explore"
    t = target_of(e)
    o, ctrl, det, zones = obj_parts(t, ex)
    if o in ("TrackedSet", "parent") and wrap_e and target_of(wrap_e):
        # "choose a land ..., then sacrifice the rest": the object is the wrapper's target
        o, ctrl, det, zones = obj_parts(target_of(wrap_e), ex)
    frm = e.get("origin") or (zones[0] if zones else "")
    to = e.get("destination") or ""
    if rt in ("Bounce", "BounceAll"):
        to = "Hand"
    elif rt in ("PutAtLibraryPosition", "PutOnTopOrBottom"):
        to = "Library"
    steps = chain_steps(ex)
    if rt in SEARCHY and not to:
        for st in steps:
            d = (st.get("effect") or {}).get("destination")
            if d:
                to = d
                break
    ctr = (e.get("counter_type") or e.get("counter_kind") or "")
    ctr = ctr.lower() if isinstance(ctr, str) else ""
    ps = ex.get("player_scope")
    if isinstance(ps, dict) and ps.get("type"):
        who = "scope:" + ps["type"]
    elif o in PLAYER_OBJ:
        who = o
    elif isinstance(e.get("player"), str):
        who = e["player"]
    else:
        who = ""
    if rt.endswith("All") or rt in ("DamageEachPlayer",):
        quant = "all"
    elif ex.get("repeat_for"):
        quant = "each"
    elif isinstance(ex.get("multi_target"), dict) and (ex["multi_target"].get("max") or 2) > 1:
        quant = "multi"
    elif o not in ("-",):
        quant = "one"
    else:
        quant = "-"
    mods, kws = [], []
    if rt == "GenericEffect":
        for s in e.get("static_abilities") or []:
            m = s.get("mode")
            if isinstance(m, str) and m != "Continuous":
                mods.append(m)
            elif isinstance(m, dict):
                mods.extend(m)
            for md in s.get("modifications") or []:
                if isinstance(md, dict):
                    mods.append(md.get("type"))
                    if md.get("type") == "AddKeyword":
                        kws.append(str(md.get("keyword")))
    for k in e.get("keywords") or []:
        kws.append(k if isinstance(k, str) else next(iter(k)) if isinstance(k, dict) and k else str(k))
    if rt in ("Token",):
        tt = [str(x) for x in e.get("types") or []]
        o = "+".join(sorted(x for x in tt if x in CORE_TYPES)) or "token"
        nm = e.get("name")
        det = det + ["sub:" + x for x in sorted(x for x in tt if x not in CORE_TYPES)] + \
            (["name:" + nm] if isinstance(nm, str) else [])
    if rt == "Mana":
        p = e.get("produced")
        o = (p.get("type") if isinstance(p, dict) else str(p)) or "mana"
    dur = e.get("duration") or ex.get("duration")
    det = det + ["kw:" + k for k in sorted(set(kws))]
    if isinstance(dur, str):
        det.append("dur:" + dur)
    if ex.get("condition"):
        det.append("cond")
    if wraps:
        det.append("wrap:" + ">".join(wraps))
    if steps:
        det.append("chain:" + ">".join(step_verb(s) for s in steps[:3]) + ("+" if len(steps) > 3 else ""))
    return dict(fam=FAMILY.get(rt, "Other"), rtype=rt, ftype=ft, mods=",".join(sorted(set(m for m in mods if m))),
                frm=frm, to=to, ctr=ctr, who=who, obj=o, ctrl=ctrl, quant=quant, det="|".join(det), wraps=wraps,
                usable=True)


ORDERS = {
    "A": [("fam",), ("fam", "rtype"), ("fam", "rtype", "obj"),
          ("fam", "rtype", "obj", "ctrl", "quant", "frm", "to"),
          ("fam", "rtype", "obj", "ctrl", "quant", "frm", "to", "ctr", "who", "mods", "det")],
    "B": [("fam",), ("fam", "ftype", "frm", "to", "ctr", "who", "mods"),
          ("fam", "ftype", "frm", "to", "ctr", "who", "mods", "obj"),
          ("fam", "ftype", "frm", "to", "ctr", "who", "mods", "obj", "ctrl", "quant"),
          ("fam", "ftype", "frm", "to", "ctr", "who", "mods", "obj", "ctrl", "quant", "det")],
    "C": [("fam", "ftype"), ("fam", "ftype", "frm", "to", "ctr", "who", "mods"),
          ("fam", "ftype", "frm", "to", "ctr", "who", "mods", "obj"),
          ("fam", "ftype", "frm", "to", "ctr", "who", "mods", "obj", "ctrl", "quant"),
          ("fam", "ftype", "frm", "to", "ctr", "who", "mods", "obj", "ctrl", "quant", "det")],
}


def sig(f, keys):
    return " · ".join("%s=%s" % (k, f[k]) for k in keys if f[k] not in ("", "-") or k in ("fam", "rtype", "ftype"))


def backoff(sigs, mn, mode="literal"):
    """sigs: list of [s1..s5] per ability (None = unusable) -> [(level, sig) | None].

    literal   the finest level whose signature is held by >= mn abilities in total (the ability sits at
              that node; a node can hold fewer than mn abilities directly when the rest went finer --
              its "other" remainder in a tree)
    residual  finest first, a signature held by >= mn abilities NOT yet assigned is a leaf, the rest pass
              up; every leaf has >= mn members
    """
    n = len(sigs)
    if mode == "literal":
        cnt = [collections.Counter(s[l] for s in sigs if s) for l in range(5)]
        out = []
        for s in sigs:
            a = None
            if s:
                for l in range(4, -1, -1):
                    if cnt[l][s[l]] >= mn:
                        a = (l + 1, s[l])
                        break
            out.append(a)
        return out
    assigned = [None] * n
    pending = [j for j in range(n) if sigs[j] is not None]
    for lvl in range(4, -1, -1):
        groups = collections.defaultdict(list)
        for j in pending:
            groups[sigs[j][lvl]].append(j)
        nxt = []
        for s, js in groups.items():
            if len(js) >= mn:
                for j in js:
                    assigned[j] = (lvl + 1, s)
            else:
                nxt.extend(js)
        pending = nxt
    return assigned


def low_info(level, f):
    """Generic: an L1 leaf (bare family), or a leaf whose signature names no object and no verb parameter."""
    if level == 1:
        return True
    if level >= 3 and f["obj"] not in ("-",):
        return False
    return not any(f[k] for k in ("frm", "to", "ctr", "who", "mods")) and (level < 5 or not f["det"])


def main():
    items, excl, AL = population()
    for x in items:
        x["f"] = fields(x)
    sigs = {o: [None if not x["f"]["usable"] else [sig(x["f"], k) for k in ORDERS[o]] for x in items]
            for o in ORDERS}
    out = {"v": 1, "population": {
        "abilities": len(items), "by_kind": dict(collections.Counter(x["kind"] for x in items)),
        "cards": len({x["oid"] for x in items}), "excluded": dict(sorted(excl.items())),
        "usable": sum(x["f"]["usable"] for x in items),
        "unusable": sum(not x["f"]["usable"] for x in items),
        "unwrapped": sum(bool(x["f"]["wraps"]) for x in items)}}
    out["distinct_signatures"] = {o: [len({s[l] for s in sigs[o] if s}) for l in range(5)] for o in ORDERS}
    leaves_out = {}
    res = {}
    for o, mn, mode in [(o, mn, m) for o in ORDERS for mn in MINS for m in ("literal", "residual")]:
        if True:
            asg = backoff(sigs[o], mn, mode)
            key = "%s%d%s" % (o, mn, "" if mode == "literal" else "r")
            leaf = collections.defaultdict(list)
            for j, a in enumerate(asg):
                if a:
                    leaf[a].append(j)
            sizes = sorted((len(v) for v in leaf.values()), reverse=True)
            by_level = collections.Counter(a[0] for a in asg if a)
            leaves_by_level = collections.Counter(k[0] for k in leaf)
            lowinfo = [k for k, js in leaf.items() if low_info(k[0], items[js[0]]["f"])]
            few_cards = sum(1 for js in leaf.values() if len({items[j]["oid"] for j in js}) < mn)

            def band(lo, hi):
                return sum(len(v) for v in leaf.values() if lo <= len(v) <= hi)
            res[key] = {
                "leaves": len(leaf), "leaves_by_level": dict(sorted(leaves_by_level.items())),
                "abilities_by_level": dict(sorted(by_level.items())),
                "below_min_everywhere": sum(1 for s, a in zip(sigs[o], asg) if s and not a),
                "low_info_leaves": len(lowinfo), "abilities_in_low_info": sum(len(leaf[k]) for k in lowinfo),
                "leaves_under_min_distinct_cards": few_cards,
                "size_hist": {"%d-%d" % b: sum(1 for s in sizes if b[0] <= s <= b[1])
                              for b in [(1, 2), (3, 4), (5, 9), (10, 19), (20, 49), (50, 99), (100, 499), (500, 10 ** 6)]},
                "abilities_in_size": {"%d-%d" % b: band(*b)
                                      for b in [(1, 2), (3, 4), (5, 9), (10, 49), (50, 10 ** 6)]},
                "median_size": sizes[len(sizes) // 2] if sizes else 0,
                "leaves_with_fewer_direct_members_than_min": sum(1 for s_ in sizes if s_ < mn),
                "abilities_in_those": sum(s_ for s_ in sizes if s_ < mn),
                "largest": [{"level": k[0], "sig": k[1], "n": len(v)}
                            for k, v in sorted(leaf.items(), key=lambda kv: -len(kv[1]))[:15]],
            }
            leaves_out[key] = asg
    out["backoff"] = res
    with io.open(os.path.join(BUILD, "signature_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=1))
    rows = []
    for j, x in enumerate(items):
        rows.append({"oid": x["oid"], "face": x["face"], "b": x["b"], "i": x["i"], "name": x["name"],
                     "text": x["text"], "kind": x["kind"], "status": x["status"], "state": x["state"],
                     "route": x["route"], "leaf": x["leaf"], "reason": x["reason"], "best": x["best"],
                     "score": x["score"], "cleaf": x["cleaf"], "method": x["method"],
                     "f": {k: v for k, v in x["f"].items() if k != "usable"},
                     "sig": {o: sigs[o][j] for o in ORDERS},
                     "leaf_new": {k: (list(v[j]) if v[j] else None) for k, v in leaves_out.items()}})
    with io.open(os.path.join(BUILD, "signature_probe_leaves.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"v": 1, "rows": rows}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    print(json.dumps({k: out[k] for k in ("population", "distinct_signatures")}, indent=1))
    for k, v in res.items():
        print(k, {kk: v[kk] for kk in ("leaves", "leaves_by_level", "abilities_by_level", "below_min_everywhere",
                                        "low_info_leaves", "abilities_in_low_info", "median_size")})


if __name__ == "__main__":
    random.seed(0)
    main()
