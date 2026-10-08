#!/usr/bin/env python3
"""Rule-based groups for "No effect to group", plus the newer vanilla cards.

    python src/build_ledger.py
    python src/build_placements.py
    python src/build_keyword_layer.py
    python src/build_signature_layer.py   # -> build/signature_layer.json
    python src/build_ledger.py            # again: reads the layer (method `signature_rule`, `vanilla_rule`)

WHY. `card_features()` reads only ability effects, so a card whose rules are replacement / prevention
effects with no effect of their own ("Prevent all combat damage", "If one or more +1/+1 counters would
be put on a creature you control, put that many plus one") or an additional cost has no feature and
cannot be clustered. The parser records WHICH replacement it read and its parameters, so those cards
can be grouped by an exact structural signature instead, as the keyword layer does for keywords.
Nothing is clustered, no card_features() or centroid changes.

SIGNATURE. The card's replacement items (event + scope / amount / modification / redirect fields; the
numbers inside a "next N damage" shield are not part of it) as a sorted set, plus "additional cost".
Keywords on the card never split a group; they are shown on it. A signature held by >= MIN cards is a
group (the groups below merge a few near-identical signatures under one name); else the card goes to
its family group if that reaches MIN; else it stays unplaced. NO catch-all: cards whose signature is too
rare, and the 11 damage replacements whose parser output records no parameters at all, stay in
"No effect to group" with their reason.

NAMES. Real Magic vocabulary where there is some (Fog; damage redirection; prevention shield;
additional cost); everything else is a plain description of the signature. Each group, branch and the
block carries `coined: true` when the name is ours. `basis` says where a real term comes from.

VANILLA. The seven newer cards with no rules text are given the existing "No abilities" branch
(method `vanilla_rule`, as src/build_placements.py gives the older ones). That rule is not changed.

Writes build/signature_layer.json (sorted keys; identical bytes across runs).
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ledger as BL           # noqa: E402
import build_keyword_layer as kwl   # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
MIN = 5
BLOCK = "Replacement effects and costs"
VANILLA_BRANCH = "No abilities"

# (leaf id, name, branch, coined, basis, signatures merged into it)
LEAVES = [
    ("sig:fog", "Fog: prevent all combat damage", "Damage prevention", False,
     "'Fog' is the established Magic term for a spell that prevents all combat damage",
     ["DamageDone{combat_scope=CombatOnly,shield=Prevention:All}"]),
    ("sig:fog-limited", "Prevent combat damage, limited to some creatures or players", "Damage prevention", True, None,
     ["DamageDone{combat_scope=CombatOnly,shield=Prevention:All}"]),
    ("sig:prevent-all", "Prevent all damage", "Damage prevention", True, None,
     ["DamageDone{shield=Prevention:All}"]),
    ("sig:prevent-players", "Prevent damage to players", "Damage prevention", True, None,
     ["DamageDone{damage_target_filter=PlayerOnly,shield=Prevention:All}"]),
    ("sig:prevent-creatures", "Prevent damage to creatures", "Damage prevention", True, None,
     ["DamageDone{damage_target_filter=CreatureOnly,shield=Prevention:All}",
      "DamageDone{combat_scope=CombatOnly,damage_target_filter=CreatureOnly,shield=Prevention:All}"]),
    ("sig:redirect", "Damage redirection", "Damage prevention", False,
     "'redirection effect' is rules vocabulary (Comprehensive Rules 614.9)",
     ["DamageDone{damage_target_filter=PlayerOnly,redirect_target=SelfRef,shield=Prevention:All}"]),
    ("sig:shield-next", "Prevention shield: next N damage", "Damage prevention", False,
     "'Prevent the next N damage' is the Comprehensive Rules 615.7 wording, which says such effects 'work like shields'; "
     "'prevention shield' itself is the informal judge/player term, not a defined rules term",
     ["DamageDone{shield=Prevention:Next}", "DamageDone{damage_target_filter=CreatureOnly,shield=Prevention:Next}"]),
    ("fam:prevention", "Damage prevention: other variants", "Damage prevention", True, None, None),
    ("sig:double", "Damage doubling", "Damage changes", True, None,
     ["DamageDone{damage_modification=Double}", "DamageDone{damage_modification=Double,damage_source_filter=Typed}"]),
    ("fam:damage-mod", "Damage changes: other variants", "Damage changes", True, None, None),
    ("fam:counters", "Counter-adding replacement", "Counter replacement", True, None, None),
    ("fam:mana", "Mana-production replacement", "Mana replacement", True, None, None),
    ("cost:additional", "Additional cost to cast", "Additional costs", False,
     "'additional cost' is rules vocabulary (Comprehensive Rules 118.8)", None),
]
BRANCH_ORDER = ["Damage prevention", "Damage changes", "Counter replacement", "Mana replacement", "Additional costs"]
SIGMAP = {s: l[0] for l in LEAVES if l[5] for s in l[5]}
SIGMAP["DamageDone{combat_scope=CombatOnly,shield=Prevention:All}"] = "sig:fog"   # refined by the text gates below
# The parser records WHAT is prevented (all combat damage) but drops who the damage is dealt by or to when
# the card limits it ("dealt by target creature", "to and dealt by this creature"), so the signature alone
# cannot tell a real Fog from a one-creature shield. Two deterministic text gates keep the groups honest:
#   FOG_TEXT       the card's prevent clause is exactly "prevent all combat damage that would be dealt this turn."
#                  Anything else with the same signature goes to the "from or to some creatures" group.
#   REDIRECT_TEXT  a prevent-shaped signature whose text actually redirects the damage ("is dealt to ... instead") is the parser's mistake; the card is left unplaced.
FOG_TEXT = re.compile(r"prevent all combat damage that would be dealt this turn\.", re.I)
REDIRECT_TEXT = re.compile(r"(is|are) dealt to [^.]*instead", re.I)
IGN = {"description", "mode", "execute", "valid_card", "condition", "event"}


def gsig(it):
    ps = []
    for k, v in sorted(it.items()):
        if k in IGN or v in (None, False, [], {}):
            continue
        if k == "shield_kind":
            pk = next(iter(v))
            amt = v[pk].get("amount") if isinstance(v[pk], dict) else None
            ps.append("shield=%s:%s" % (pk, amt if isinstance(amt, str) else (next(iter(amt)) if isinstance(amt, dict) else "?")))
        elif isinstance(v, str):
            ps.append("%s=%s" % (k, v))
        elif isinstance(v, dict):
            ps.append("%s=%s" % (k, v.get("type") or ",".join(sorted(v))[:20]))
        elif isinstance(v, list):
            ps.append("%s=list" % k)
    return it.get("event", "?") + "{" + ",".join(ps) + "}"


def family(repl, addc):
    s = " ".join(repl)
    if not repl:
        return "cost" if addc else None
    if "shield=" in s and "damage_modification" not in s:
        return "prevention"
    if "damage_modification" in s:
        return "damage-mod"
    return {"AddCounter": "counters", "ProduceMana": "mana"}.get(repl[0].split("{")[0])


def main():
    R = json.load(io.open(os.path.join(BUILD, "ledger.json"), encoding="utf-8"))["rows"]
    P = json.load(io.open(os.path.join(BUILD, "placements.json"), encoding="utf-8"))
    KL = json.load(io.open(os.path.join(BUILD, "keyword_layer.json"), encoding="utf-8"))
    idx = {r["id"]: r for r in json.load(io.open(os.path.join(BUILD, "index.json"), encoding="utf-8"))["rows"]}
    chunks = {}

    def entry(fid):
        if fid in idx:
            ch = idx[fid]["ch"]
            if ch not in chunks:
                chunks[ch] = json.load(io.open(os.path.join(BUILD, "chunks", str(ch) + ".json"), encoding="utf-8"))
            return chunks[ch].get(fid) or {}
        return P["recovered"]["chunk"].get(fid) or {}

    kw_cards = {f["card"] for f in KL["faces"].values()}
    pop, vanilla = {}, {}
    for oid, r in sorted(R.items()):
        ev = r["evidence"]
        rec = ev.get("recovered")
        if oid in kw_cards or r["status"] == "out_of_scope":
            continue
        if r["status"] == "no_extractable_effect" or (
                r["status"] == "missing_from_export" and rec and all(f["stage"] == "no_extractable_effect" for f in rec["faces"])):
            pop[oid] = [f["id"] for f in (ev.get("faces") or (rec or {}).get("faces") or [])]
        elif r["status"] == "vanilla" and ev.get("layer") == "new_release":
            vanilla[oid] = [f["id"] for f in ev["faces"]]

    cards, excluded = {}, collections.Counter()
    excl_cards = {}
    for oid, fids in pop.items():
        repl, other, addc, kws, per_face, text = [], False, False, [], {}, []
        for fid in fids:
            e = entry(fid)
            for b in ("abilities", "triggers", "static_abilities", "replacements"):
                for it in e.get(b) or []:
                    if b == "replacements" and not (it.get("execute") or {}).get("effect"):
                        repl.append(gsig(it))
                    else:
                        other = True
            addc = addc or bool(e.get("additional_cost"))
            text.append(e.get("oracle_text") or "")
            per_face[fid] = [kwl.shown_keyword(k) for k in (e.get("keywords") or [])]
        if other:
            excluded["other_items"] += 1
            excl_cards[oid] = "other_items"
            continue
        if not repl and not addc:
            excluded["no_replacement_or_cost"] += 1
            excl_cards[oid] = "no_replacement_or_cost"
            continue
        cards[oid] = {"repl": tuple(sorted(set(repl))), "addc": addc, "faces": fids, "kws": per_face,
                      "text": " ".join(text)}
    sigcount = collections.Counter((c["repl"], c["addc"]) for c in cards.values())
    fam_left = collections.Counter(family(c["repl"], c["addc"]) for c in cards.values()
                                   if sigcount[(c["repl"], c["addc"])] < MIN
                                   or not (len(c["repl"]) == 1 and c["repl"][0] in SIGMAP))
    placed = {}
    for oid, c in cards.items():
        key = (c["repl"], c["addc"])
        if c["repl"] == ("DamageDone{}",):
            excluded["parameters_not_recorded"] += 1
            excl_cards[oid] = "parameters_not_recorded"
            continue
        leaf = None
        if any("shield=" in r_ for r_ in c["repl"]) and not any("redirect_target" in r_ for r_ in c["repl"])                 and REDIRECT_TEXT.search(c["text"]):
            excluded["text_redirects_signature_does_not"] += 1
            excl_cards[oid] = "text_redirects_signature_does_not"
            continue
        if not c["repl"] and c["addc"]:
            leaf = "cost:additional"
        elif len(c["repl"]) == 1 and c["repl"][0] in SIGMAP and sigcount[key] >= MIN:
            leaf = SIGMAP[c["repl"][0]]
            if leaf == "sig:fog" and not FOG_TEXT.search(c["text"]):
                leaf = "sig:fog-limited"
        else:
            f = family(c["repl"], c["addc"])
            if f and fam_left[f] >= MIN:
                leaf = "fam:" + f
        if leaf is None:
            excluded["signature_too_rare"] += 1
            excl_cards[oid] = "signature_too_rare"
            continue
        placed[oid] = leaf

    leaves = {}
    for lid, name, branch, coined, basis, sigs in LEAVES:
        mem = sorted((o for o, l in placed.items() if l == lid), key=lambda o: (R[o]["name"], o))
        if not mem:
            continue
        leaves[lid] = {"id": lid, "name": name, "branches": [branch], "coined": coined, "basis": basis,
                       "kind": lid.split(":")[0], "signatures": sigs, "n_cards": len(mem),
                       "faces": [fid for o in mem for fid in cards[o]["faces"]], "sort": "name", "note": None}
    branches = []
    for b in BRANCH_ORDER:
        ls = [l for l in leaves if leaves[l]["branches"] == [b]]
        if ls:
            branches.append({"name": b, "coined": True, "catch_all": False,
                             "leaves": sorted(ls, key=lambda l: (-leaves[l]["n_cards"], l)),
                             "n_cards": sum(leaves[l]["n_cards"] for l in ls)})
    faces = {}
    for oid, lid in placed.items():
        for fid in cards[oid]["faces"]:
            faces[fid] = {"card": oid, "method": "signature_rule", "leaf": lid,
                          "keywords": cards[oid]["kws"][fid]}
    vfaces = {fid: {"card": oid, "method": "vanilla_rule", "branch": VANILLA_BRANCH, "source": "new_release"}
              for oid, fl in vanilla.items() for fid in fl}
    doc = {
        "meta": {"min_group": MIN, "block": BLOCK, "block_coined": True,
                 "population": len(pop), "cards": len(placed), "faces": len(faces),
                 "leaves": len(leaves), "branches": len(branches),
                 "stays_unplaced": dict(sorted(excluded.items())),
                 "vanilla_cards": len(vanilla),
                 "min_rule": "signature held by >= %d cards, else family group if it reaches %d, else unplaced; no catch-all" % (MIN, MIN),
                 "coined_names": sorted(l["name"] for l in leaves.values() if l["coined"]),
                 "real_terms": {l["name"]: l["basis"] for l in leaves.values() if not l["coined"]}},
        "branches": branches, "leaves": dict(sorted(leaves.items())),
        "faces": dict(sorted(faces.items())),
        "vanilla": dict(sorted(vfaces.items())),
        "unplaced_reasons": dict(sorted(excl_cards.items())),
    }
    with io.open(os.path.join(BUILD, "signature_layer.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    print(json.dumps(doc["meta"], indent=1, ensure_ascii=False))
    for l in doc["leaves"].values():
        print("%4d  %s%s" % (l["n_cards"], l["name"], "   [coined]" if l["coined"] else ""))


if __name__ == "__main__":
    main()
