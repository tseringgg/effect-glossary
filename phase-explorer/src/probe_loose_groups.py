#!/usr/bin/env python3
"""Probe: a "loosely grouped" browse layer for the Not-yet-organized pile. Investigation and design only: builds nothing, places nothing, changes nothing.

    python src/probe_loose_groups.py            # measure + draw the hand-check samples -> build/loose_groups_probe.json
    python src/probe_loose_groups.py --report   # after the reads and verdicts files exist -> reports/loose-groups-probe.md

Seeds, declared before any computation: 20261016 draws the 30 groups for the coherence hand check (10 sizes 10-30, 10 sizes 31-100, 10 over 100,
by cards per group); 20261017 orders the members read in each group and the draw of 20 of the 30 for the name check.

The split uses only fields already in the parse (family, effect type, and a few fields chosen per family below); no text matching, no new parsing.
A value of a chosen field that occurs fewer than CAP times within its effect type is folded into "other", so rare values do not make tiny groups.
"""
import collections
import contextlib
import io
import json
import os
import pickle
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
REPORTS = os.path.join(HERE, "reports")
DATA = os.path.join(HERE, "data")
SEED, SEED_NAMES = 20261016, 20261017
CAP = 8
KEEP = ["fam", "ftype", "frm", "to", "ctr", "who", "mods", "sign", "recip", "obj", "ctrl", "quant", "props", "kw", "dur", "cond", "wrap", "chain", "tok", "usable"]

# ------------------------------------------------------------------ the split: which fields, per family, and why
FIELDS = {
    "Zone change": ["frm", "to", "mass", "ctrl"],            # where a card goes from and to is what a tester asks; all-of-them vs one; yours vs theirs
    "Counters": ["ctr", "objc", "mass"],                     # the counter type, what gets it (itself or another), all or one
    "Pump / grant": ["sign", "grant", "objc", "mass"],       # bigger or smaller, which keyword or kind of grant, what it affects, all or one
    "Static: continuous": ["grant", "objc"],                 # which kind of continuous effect, and what it affects
    "Library": ["to", "who"],                                # where cards end up, whose library
    "Tokens": ["objc", "kw"],                                # creature or artifact tokens, with which keyword
    "Damage": ["objc", "mass"],                              # what is hit, one or all
    "Destroy": ["objc", "mass"],
    "Tap / untap": ["objc", "mass"],
    "Sacrifice": ["who", "objc"],
    "Card draw": ["who"],
    "Life": ["who"],
    "Discard / hand": ["who"],
    "Mana": ["obj"],                                         # fixed colour, any colour, colourless
    "Static: restriction": ["objc"],
    "Static: cost change": ["objc"],
    "Static: other rule": ["objc"],
    "Control": ["objc"],
    "Copy": ["objc"],
    "Counter spell": ["objc"],
}
DEFAULT_FIELDS = ["objc"]
REASONS = {"below_minimum_size": "its shape is rare: fewer than 5 abilities are like it", "rare_object": "its shape is rare: fewer than 5 abilities are like it",
           "rare_verb_parameter": "its shape is rare: fewer than 5 abilities are like it", "rare_effect_type": "its shape is rare: fewer than 5 abilities are like it",
           "flagged": "the parser may have dropped a condition from it", "item_gap": "part of the ability was not read",
           "gap_card_continuation_gap": "the card has an unread clause that may belong to it", "gap_card_same_line_gap": "an unread clause sits on its rules line",
           "gap_card_no_text": "it has no rules text of its own"}


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def collect():
    cache = os.environ.get("LOOSE_CACHE")
    if cache and os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    import build_ability_taxonomy as B
    import analyze_unorganized_breakdown_v3 as V3
    B.dump = lambda *a, **k: None
    with contextlib.redirect_stdout(io.StringIO()):
        S = B.main()
    A, view, rows, L = S["A"], S["view"], S["rows"], S["L"]
    pile = sorted(o for o, v in view.items() if v[0] == "unorganized")
    pset = set(pile)
    testfail = {(r[1], r[2], r[3]): r[7] for r in rows if r[0] in pset and r[7] in V3.GAPTEST}
    ex = V3.held_items(pset, testfail)
    for x in ex:
        f = B.fields3({"b": x["b"], "item": x["item"]})
        if f["fam"] == "Other" and f["ftype"] in B.FAMILY_FIX:
            f["fam"] = B.FAMILY_FIX[f["ftype"]]
        x["f"] = f
    items = []
    for a in A:
        if a["oid"] in pset and not a["pre"]:
            items.append({"oid": a["oid"], "text": a["text"], "src": "A", "reason": a["reason"], "f": {k: a["f"][k] for k in KEEP}})
    for x in ex:
        items.append({"oid": x["oid"], "text": x["text"] or "", "src": x["why"], "reason": x["test"] if x["why"] == "test_fail" else x["why"], "f": {k: x["f"][k] for k in KEEP}})
    meta = {"pile": pile, "view_reason": {o: view[o][1] for o in pile}, "names": {o: L[o]["name"] for o in pile},
            "card_text": {o: S["cards"][o]["t"] for o in pile if o in S["cards"]}, "totals": S["tax"]["totals"], "fam_keys": [f["key"] for f in S["tax"]["families"]]}
    return {"items": items, "meta": meta}


# ------------------------------------------------------------------ the loose key
def objc(f):
    o = f["obj"]
    if o in ("", "-"):
        return ""
    if o == "self":
        return "this permanent"
    if o in ("player", "you", "triggering player", "defending player"):
        return "a player"
    if o == "any target":
        return "any target"
    if o in ("parent", "TrackedSet"):
        return "the same object"
    if o == "object":
        return "something"
    m = re.match(r"^(.*?)\[(enchanted|equipped|enchanted\+equipped)\]$", o)
    if m:
        return m.group(2).split("+")[0] + " " + m.group(1).split("|")[0].split("+")[0].lower()
    t = o.split("/spell:")[0].split("|")[0].split("+")[0]
    if t.startswith("Non:"):
        t = "non" + t[4:].lower() + " permanent"
    return t.lower()


def grant(f):
    if f["kw"]:
        return "keyword " + f["kw"].split("|")[0].lower()
    if f["mods"]:
        return f["mods"].split(",")[0]
    return ""


FV = {
    "frm": lambda f: f["frm"], "to": lambda f: f["to"], "ctr": lambda f: f["ctr"], "sign": lambda f: f["sign"] if f["sign"] not in ("", "-") else "",
    "ctrl": lambda f: {"You": "you control", "Opponent": "an opponent controls"}.get(f["ctrl"], ""),
    "mass": lambda f: {"all": "all", "each": "all", "multi": "several"}.get(f["quant"], ""),
    "who": lambda f: {"scope:Opponent": "each opponent", "scope:All": "each player", "you": "you", "controller": "you", "player": "target player",
                      "triggering player": "that player", "defending player": "defending player", "its controller": "its controller"}.get(f["who"], f["who"]),
    "objc": objc, "grant": grant, "kw": lambda f: f["kw"].split("|")[0].lower() if f["kw"] else "", "obj": lambda f: f["obj"] if f["obj"] not in ("", "-") else "",
}


def build_keys(use):
    raw = []
    for it in use:
        f = it["f"]
        fields = FIELDS.get(f["fam"], DEFAULT_FIELDS)
        raw.append((f["fam"], f["ftype"], tuple((k, FV[k](f)) for k in fields)))
    cnt = collections.Counter()
    for fam, ft, kv in raw:
        for k, v in kv:
            cnt[(fam, ft, k, v)] += 1
    keys = []
    for fam, ft, kv in raw:
        keys.append((fam, ft, tuple((k, (v if (v == "" or cnt[(fam, ft, k, v)] >= CAP) else "other")) for k, v in kv)))
    return keys


# fixed wording per field value for the draft names
def loose_name(key):
    fam, ft, kv = key
    d = dict(kv)
    base = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", ft.replace("static:", "")).lower()
    base = {"change zone": "move cards", "bounce": "return to hand", "put counter": "put counters", "remove counter": "remove counters", "give player counter": "give a player counters",
            "deal damage": "deal damage", "generic effect": "grant an effect", "pump": "change power and toughness", "continuous": "continuous effect",
            "search library": "search a library", "put at library position": "put on a library", "dig": "look at the top cards", "reveal top": "reveal the top cards",
            "exile top": "exile the top cards", "token": "create tokens", "copy token of": "create token copies", "draw": "draw cards", "mill": "mill cards", "lose life": "lose life",
            "gain life": "gain life", "discard": "discard", "reveal hand": "reveal a hand", "sacrifice": "sacrifice", "destroy": "destroy", "tap": "tap", "untap": "untap",
            "gain control": "gain control", "copy spell": "copy a spell", "become copy": "become a copy", "counter": "counter a spell", "attach": "attach",
            "cast from zone": "cast a card", "mana": "add mana"}.get(base, base)
    parts = [base[:1].upper() + base[1:]]
    if d.get("frm"):
        parts.append("from " + d["frm"].lower())
    if d.get("to"):
        parts.append("to " + d["to"].lower())
    if d.get("objc"):
        parts.append("affecting " + d["objc"])
    if d.get("obj"):
        parts.append("of " + re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", d["obj"]).lower())
    if d.get("ctr"):
        parts.append("with " + {"p1p1": "+1/+1", "m1m1": "-1/-1"}.get(d["ctr"], d["ctr"]) + " counters")
    if d.get("sign"):
        parts.append({"boost": "bigger", "shrink": "smaller", "mixed": "bigger and smaller", "unknown": "by a counted amount", "zero": "unchanged"}.get(d["sign"], d["sign"]))
    if d.get("grant"):
        parts.append("granting " + re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", d["grant"]).lower())
    if d.get("kw"):
        parts.append("with " + d["kw"])
    if d.get("who"):
        parts.append("for " + d["who"])
    if d.get("mass"):
        parts.append("(" + d["mass"] + ")")
    if d.get("ctrl"):
        parts.append("(" + d["ctrl"] + ")")
    if "other" in d.values():
        parts.append("(other kinds)")
    return fam + " › " + " ".join(parts)


def band(n):
    return "<10" if n < 10 else "10-50" if n <= 50 else "51-100" if n <= 100 else ">100"


def dist(sizes):
    c = collections.Counter(band(n) for n in sizes)
    return {"groups": len(sizes), "<10": c["<10"], "10-50": c["10-50"], "51-100": c["51-100"], ">100": c[">100"]}


def measure():
    data = collect()
    items, meta = data["items"], data["meta"]
    fam_keys = set(meta["fam_keys"])
    pile = meta["pile"]
    use = [i for i in items if i["f"]["usable"] and i["f"]["fam"] in fam_keys]
    keys = build_keys(use)
    out = {"seeds": {"coherence": SEED, "names": SEED_NAMES}, "cap": CAP, "fields_per_family": FIELDS, "default_fields": DEFAULT_FIELDS,
           "pile": len(pile), "abilities_in_the_pile": len(items), "usable_abilities": len(use), "usable_by_source": dict(collections.Counter(i["src"] for i in use))}
    # card -> groups, with the reasons
    L1, L2, L3 = collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(set)
    reasons_of = collections.defaultdict(collections.Counter)
    members = collections.defaultdict(list)
    card_groups = collections.defaultdict(set)
    for it, k in zip(use, keys):
        L1[k[0]].add(it["oid"])
        L2[(k[0], k[1])].add(it["oid"])
        L3[k].add(it["oid"])
        reasons_of[k][REASONS.get(it["reason"], it["reason"])] += 1
        members[k].append(it)
        card_groups[it["oid"]].add(k)
    out["levels"] = {"L1 family": dist([len(v) for v in L1.values()]), "L2 family + effect type": dist([len(v) for v in L2.values()]),
                     "L3 family + effect type + chosen fields": dist([len(v) for v in L3.values()])}
    sizes3 = {k: len(v) for k, v in L3.items()}
    sizes2 = {k: len(v) for k, v in L2.items()}
    names = {k: loose_name(k) for k in L3}
    top15 = sorted(L3, key=lambda k: -sizes3[k])[:15]
    out["largest_15"] = [{"name": names[k], "cards": sizes3[k]} for k in top15]
    cards_in = set(card_groups)
    out["reach"] = {"cards_with_a_loose_group": len(cards_in), "cards_in_at_least_one_group_of_100_or_fewer": sum(1 for o in cards_in if any(sizes3[k] <= 100 for k in card_groups[o])),
                    "cards_only_in_groups_over_100": sum(1 for o in cards_in if all(sizes3[k] > 100 for k in card_groups[o])),
                    "cards_in_at_least_one_group_of_50_or_fewer": sum(1 for o in cards_in if any(sizes3[k] <= 50 for k in card_groups[o])),
                    "avg_groups_per_card": round(sum(len(v) for v in card_groups.values()) / len(cards_in), 2), "max_groups_per_card": max(len(v) for v in card_groups.values()),
                    "L2_cards_in_a_group_of_100_or_fewer": sum(1 for o in cards_in if any(sizes2[(k[0], k[1])] <= 100 for k in card_groups[o])),
                    "L2_cards_only_in_L2_groups_over_100": sum(1 for o in cards_in if all(sizes2[(k[0], k[1])] > 100 for k in card_groups[o]))}
    # the variant that mirrors the main tree: groups under 10 cards are shown together as "Other <effect type>" inside their effect type
    vis = {k: v for k, v in L3.items() if len(v) >= 10}
    other = collections.defaultdict(set)
    for k, v in L3.items():
        if len(v) < 10:
            other[(k[0], k[1])] |= v
    vsizes = [len(v) for v in vis.values()] + [len(v) for v in other.values()]
    out["rolled_variant"] = {"visible_groups_of_10_or_more": len(vis), "rolled_other_groups": len(other), "size_bands_all_visible": dist(vsizes),
                             "cards_in_a_visible_group_of_100_or_fewer": sum(1 for o in set().union(*vis.values(), *other.values())
                                                                              if any(len(v) <= 100 for v in vis.values() if o in v) or any(len(v) <= 100 for v in other.values() if o in v)),
                             "largest_rolled_other": sorted(((" / ".join(k), len(v)) for k, v in other.items()), key=lambda x: -x[1])[:8]}
    # reasons attached to assignments
    rc = collections.Counter()
    for o in cards_in:
        rs = set()
        for k in card_groups[o]:
            rs.update(reasons_of[k].keys())
        rc[len(rs)] += 1
    out["assignments"] = {"total_assignments": sum(len(v) for v in card_groups.values()),
                          "by_reason": dict(collections.Counter(REASONS.get(it["reason"], it["reason"]) for it in use)),
                          "cards_whose_only_usable_abilities_are_unread_parts": len({o for o in cards_in if all(i["src"] == "item_gap" for i in use if i["oid"] == o)}) if False else None}
    only_gap = collections.defaultdict(lambda: [0, 0])
    for it in use:
        only_gap[it["oid"]][0] += 1
        only_gap[it["oid"]][1] += it["src"] == "item_gap"
    out["assignments"]["cards_whose_every_usable_ability_has_an_unread_part"] = sum(1 for v in only_gap.values() if v[0] == v[1])
    # no-home cards
    nohome = [o for o in pile if o not in cards_in]
    rank = {}
    import gzip
    with gzip.open(os.path.join(DATA, "scryfall-oracle-cards.jsonl.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            o_ = json.loads(line)
            if o_.get("edhrec_rank") is not None:
                rank[o_["oracle_id"]] = o_["edhrec_rank"]
    vr = meta["view_reason"]
    has_text = {o: bool((meta["card_text"].get(o) or "").strip()) for o in nohome}
    out["no_home"] = {"cards": len(nohome), "by_pile_group": dict(collections.Counter(vr[o] for o in nohome)),
                      "with_no_rules_text": sum(1 for o in nohome if not has_text[o]), "in_top_3000": sum(1 for o in nohome if rank.get(o, 10 ** 9) <= 3000),
                      "in_top_10000": sum(1 for o in nohome if rank.get(o, 10 ** 9) <= 10000), "with_a_rank": sum(1 for o in nohome if o in rank),
                      "top_by_popularity": [{"card": meta["names"][o], "rank": rank[o], "why": vr[o]} for o in sorted((o for o in nohome if o in rank), key=lambda o: rank[o])[:15]]}
    # the three old junk drawers
    jd = {}
    for fam in ("Zone change", "Pump / grant", "Counters"):
        ks = sorted((k for k in L3 if k[0] == fam), key=lambda k: -sizes3[k])
        jd[fam] = {"groups": len(ks), "cards_in_the_family": len(L1[fam]), "groups_of_100_or_fewer": sum(1 for k in ks if sizes3[k] <= 100),
                   "largest_8": [{"name": names[k], "cards": sizes3[k]} for k in ks[:8]]}
    out["old_junk_drawers"] = jd
    # coherence sample (seed 20261016): 10 per size band, members read from text first
    rnd = random.Random(SEED)
    bands = {"10-30": [k for k in L3 if 10 <= sizes3[k] <= 30], "31-100": [k for k in L3 if 31 <= sizes3[k] <= 100], ">100": [k for k in L3 if sizes3[k] > 100]}
    rnd2 = random.Random(SEED_NAMES)
    sample = []
    for b in ("10-30", "31-100", ">100"):
        pool = sorted(bands[b], key=lambda k: (k[0], k[1], str(k[2])))
        out.setdefault("band_pools", {})[b] = len(pool)
        for k in rnd.sample(pool, min(10, len(pool))):
            mem = sorted(members[k], key=lambda i: (i["oid"], i["text"]))
            rnd2.shuffle(mem)
            seen, pick = set(), []
            for it in mem:
                if it["oid"] in seen:
                    continue
                seen.add(it["oid"])
                pick.append(it)
                if len(pick) == 8:
                    break
            sample.append({"n": len(sample) + 1, "band": b, "key": [k[0], k[1], list(k[2])], "name": names[k], "cards": sizes3[k],
                           "blind": [{"card": meta["names"][i["oid"]], "ability_text": " ".join((i["text"] or meta["card_text"].get(i["oid"], "")).split())[:260] or "(no ability text)"} for i in pick],
                           "reasons": dict(reasons_of[k])})
    out["sample"] = sample
    name_pick = rnd2.sample(range(1, len(sample) + 1), min(20, len(sample)))
    out["name_check_groups"] = sorted(name_pick)
    out["all_group_names"] = {"total": len(names)}
    # the name defect scan and claims check over every draft name
    import ability_names as AN
    import probe_names_part1 as P1
    import probe_names_part2 as P2
    cards_json = jl("ability_taxonomy_cards.json")["cards"]
    vocab = set()
    for c in cards_json.values():
        for w in re.findall(r"[A-Za-z][a-z']{2,}", c["t"] or ""):
            vocab.add(w.lower())
    P1.ALLOW.update(AN.TEMPLATE_VOCAB)
    P1.ALLOW.update({"affecting", "granting", "several", "bigger", "smaller", "counted", "unchanged", "amount", "continuous", "kinds", "same", "something", "state"})
    scan = P1.defect_scan([("group", n.split(" › ", 1)[1]) for n in names.values()], vocab)       # the family prefix is the tree's own label
    soft = ("longer than 110 characters", "stacked parentheses", "disambiguation suffix ('(variant)', '#2')")
    hard = {n.split("  [")[0] for k, v in scan.items() if k not in soft for _, n in v}
    # claims: stems in the name must appear in at least half of the member texts
    bad = []
    for k, nm in names.items():
        texts = [P2.norm(i["text"]) for i in members[k] if (i["text"] or "").strip()]
        if len(texts) < 5:
            continue
        low = set(re.findall(r"[a-z']+", P2.norm(nm.split("›", 1)[1])))
        for w, rx in P2.STEMS.items():
            if w in low or (w + "s") in low:
                if sum(1 for t in texts if re.search(rx, t)) / len(texts) < 0.5:
                    bad.append((nm, w))
    out["name_scan"] = {"names": len(names), "hard_defects": len(hard), "hard_examples": sorted(hard)[:8], "claims_hits": len(bad), "claims_examples": bad[:8],
                        "over_110_characters": sum(1 for n in names.values() if len(n) > 110)}
    with io.open(os.path.join(BUILD, "loose_groups_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    return out


def main():
    if "--report" in sys.argv:
        return report()
    out = measure()
    print(json.dumps({k: out[k] for k in ("pile", "abilities_in_the_pile", "usable_abilities", "usable_by_source", "levels", "largest_15", "reach", "assignments", "no_home", "old_junk_drawers", "band_pools", "name_scan")},
                     indent=1, ensure_ascii=False)[:9000])


def report():
    sys.exit("run after the verdicts exist")


if __name__ == "__main__":
    main()
