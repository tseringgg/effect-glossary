#!/usr/bin/env python3
"""Keyword layer: makes keyword-only cards browsable WITHOUT touching the clustering.

    python src/build_ledger.py          # statuses (a card is `keyword_only` there)
    python src/build_placements.py      # recovered / new-release rows + chunks
    python src/build_keyword_layer.py   # -> build/keyword_layer.json
    python src/build_ledger.py          # again: annotates each row's placement

WHY. `cluster_structural.card_features()` reads only the four ability buckets, so a card
whose whole text is parsed into `keywords` ("Flying", "Flying, vigilance") emits no feature
and cannot be clustered or placed by proximity. 1,257 such cards were `no_extractable_effect`
/ `no_feature_to_compare`. `card_features()` is NOT changed and nothing is re-clustered; this
is a separate, deterministic layer in the family of the proximity and vanilla layers, and
membership is exact (a rule, not a guess), so its placement method is `keyword_rule`.

WHO. A card is `keyword_only` when it has keywords on some face and NO item in
abilities / triggers / static_abilities / replacements on any face (`is_keyword_only`,
also used by build_ledger.py to assign the status). The 71 cards that have keywords AND
ability items stay where they are, as do the other 169 `no_extractable_effect` cards.

HOW (all deterministic, MIN = 5 as in the clustering's own minimum cluster size).
  Leaf id   `kw:<signature>`: the card's set of keyword names, sorted, joined by "+".
  1. A signature held by >= MIN cards is a leaf. For Landwalk (the only payload that changes
     what a player is looking for) the land type is part of the signature
     (`kw:Landwalk|Swamp`) when that alone reaches MIN, otherwise the plain signature is used.
  2. Else the card goes to `kw:other:<Keyword>` ("<Keyword>: other combinations"), keyed on
     the card's RAREST keyword by card count over the whole corpus (so Flying+Morph lands under
     Morph, not in a Flying tail), when that leaf reaches MIN.
  3. Else `kw:rare`, one leaf labelled as the catch-all it is, sorted by keyword.
  A card has exactly one leaf. A branch is one keyword; a signature leaf is listed under each
  of its keywords' branches (many-to-many at the branch level, like every existing branch), an
  "other combinations" leaf only under its own keyword's branch.
  Other payloads (Protection's colour or quality, Ward/Morph/Echo/Dash costs, Crew/Bushido
  numbers) are shown on the card and not used to split leaves: after the MIN rule only
  Protection from red would have reached a leaf of its own.

Card types are not split on. The audit rule (>= 2 permanent types at >= 20%) flags some leaves
literally, but every flagged member that is an Artifact is also a Creature (an artifact
creature); the 7 non-creature cards outside the clean Vehicle leaf are listed in meta.

Reads   build/ledger.json (statuses), build/index.json + build/chunks, build/placements.json
Writes  build/keyword_layer.json   (sorted keys; two runs give identical bytes)
"""
import collections
import io
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(BUILD, "keyword_layer.json")

MIN = 5
BUCKETS = ("abilities", "triggers", "static_abilities", "replacements")
PERMANENT = {"Artifact", "Creature", "Enchantment", "Land", "Planeswalker", "Battle", "Kindred", "Tribal"}
BASIC_LANDWALK = {"Plains", "Island", "Swamp", "Mountain", "Forest"}
RARE = "kw:rare"
RARE_NAME = "Rare keyword combinations (catch-all)"

# Display names: the engine's own Keyword variant names split on case ("FirstStrike" ->
# "First strike"). Checked against the Comprehensive Rules 702 headings; the only variant
# whose name is not just its case-split is Battle cry (CR 702.91). Defensive entries cover
# other multi-word variants phase.rs defines that the CR spells differently.
DISPLAY_OVERRIDE = {
    "Battlecry": "Battle cry",
    "BandsWithOther": "Bands with other",
    "LivingWeapon": "Living weapon",
    "TotemArmor": "Totem armor",
    "SplitSecond": "Split second",
    "UmbraArmor": "Umbra armor",
    "AuraSwap": "Aura swap",
    "ForMirrodin": "For Mirrodin!",
}


def kw_name(k):
    return k if isinstance(k, str) else next(iter(k))


def kw_payload(k):
    return None if isinstance(k, str) else k[next(iter(k))]


def is_keyword_only(entries):
    """True when some face has keywords and no face has an item in the four ability buckets."""
    entries = [e for e in entries if e]
    return (any(e.get("keywords") for e in entries)
            and not any(e.get(b) for e in entries for b in BUCKETS))


def display(name):
    return DISPLAY_OVERRIDE.get(name) or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).capitalize()


# ---- payload display (shown on the card; never splits a leaf except Landwalk) -------------

_COLOR = {"White": "W", "Blue": "U", "Black": "B", "Red": "R", "Green": "G", "Colorless": "C", "Snow": "S"}


def _shard(s):
    if s in _COLOR:
        return "{%s}" % _COLOR[s]
    parts = re.findall(r"White|Blue|Black|Red|Green|Colorless", s)
    if len(parts) == 2 and "".join(parts) == s:
        return "{%s/%s}" % (_COLOR[parts[0]], _COLOR[parts[1]])
    return "{%s}" % s


def _cost(c):
    if not isinstance(c, dict):
        return str(c)
    if c.get("type") == "Mana" and isinstance(c.get("data"), dict):
        return _cost(c["data"])
    if "shards" in c or "generic" in c:
        g = c.get("generic") or 0
        return ((("{%d}" % g) if g or not c.get("shards") else "") +
                "".join(_shard(s) for s in c.get("shards") or []))
    return json.dumps(c, ensure_ascii=False, sort_keys=True)


def _filter(f):
    if isinstance(f, dict) and f.get("type_filters"):
        out = []
        for t in f["type_filters"]:
            out.append(t if isinstance(t, str) else
                       (next(iter(t.values())) if isinstance(t, dict) and isinstance(next(iter(t.values())), str)
                        else json.dumps(t, ensure_ascii=False)))
        return " ".join(out)
    return None


def payload_text(name, v):
    if v is None:
        return ""
    if name == "Protection":
        if isinstance(v, dict) and "Color" in v:
            return "from " + str(v["Color"]).lower()
        if isinstance(v, dict) and "CardType" in v:
            return "from " + str(v["CardType"])
        return "from " + str(v).lower()
    if name == "Landwalk":
        return str(v)
    if isinstance(v, (int, str)):
        return str(v)
    if isinstance(v, dict):
        if name == "Affinity":
            return "for " + (_filter(v) or "?")
        if "cost" in v and "count" in v:                    # Suspend / Escape-style
            return "%s %s" % (v["count"], _cost(v["cost"])) if isinstance(v["count"], int) else _cost(v["cost"])
        if "cost" in v:
            return _cost(v["cost"])
        if v.get("type") in ("Cost", "Mana") or "shards" in v:
            return _cost(v)
        if v.get("type") == "Generic":
            return ""
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


def shown_keyword(k):
    n = kw_name(k)
    v = kw_payload(k)
    if n == "Landwalk" and isinstance(v, str):
        return display_landwalk(v)
    t = payload_text(n, v)
    return display(n) + (" " + t if t else "")


def display_landwalk(land):
    return land + "walk" if land in BASIC_LANDWALK else "Landwalk (%s)" % land


def landwalk_class(k):
    v = kw_payload(k)
    return v if isinstance(v, str) and v in BASIC_LANDWALK else "other"


# ---- build -------------------------------------------------------------------------------

def load_entries(ledger):
    """face id -> parsed entry, for every in-scope face (corpus keyword frequency) and the
    layer's own faces."""
    idx = {r["id"]: r for r in json.load(io.open(os.path.join(BUILD, "index.json"), encoding="utf-8"))["rows"]}
    P = json.load(io.open(os.path.join(BUILD, "placements.json"), encoding="utf-8"))
    chunks = {}

    def entry(fid):
        if fid in idx:
            ch = idx[fid]["ch"]
            if ch not in chunks:
                chunks[ch] = json.load(io.open(os.path.join(BUILD, "chunks", str(ch) + ".json"), encoding="utf-8"))
            return idx[fid], chunks[ch].get(fid) or {}
        row = next((r for r in P["recovered"]["rows"] if r["id"] == fid), None)
        return row, P["recovered"]["chunk"].get(fid) or {}
    return entry


def main():
    ledger = json.load(io.open(os.path.join(BUILD, "ledger.json"), encoding="utf-8"))["rows"]
    P = json.load(io.open(os.path.join(BUILD, "placements.json"), encoding="utf-8"))
    rec_rows = {r["id"]: r for r in P["recovered"]["rows"]}
    entry = load_entries(ledger)

    # corpus-wide keyword frequency (cards): "rarest keyword" = most specific
    freq = collections.Counter()
    cards = {}
    for oid, r in ledger.items():
        if r["status"] in ("out_of_scope", "missing_from_export"):
            continue
        faces = [f["id"] for f in r["evidence"].get("faces", [])]
        ents = [entry(fid) for fid in faces]
        names = {kw_name(k) for _, e in ents for k in (e.get("keywords") or [])}
        for n in names:
            freq[n] += 1
        if r["status"] == "keyword_only":
            kws = [k for _, e in ents for k in (e.get("keywords") or [])]
            types = set()
            for _, e in ents:
                types |= set((e.get("card_type") or {}).get("core_types") or [])
            cards[oid] = {"name": r["name"], "faces": faces, "kws": kws, "types": types,
                          "face_kws": {fid: (e.get("keywords") or []) for fid, (_, e) in zip(faces, ents)}}

    def key_for(kws, with_pay):
        parts = set()
        for k in kws:
            n = kw_name(k)
            parts.add(n + ("|" + landwalk_class(k) if with_pay and n == "Landwalk" else ""))
        return "+".join(sorted(parts))

    by_pay, by_plain = collections.defaultdict(list), collections.defaultdict(list)
    for oid, c in cards.items():
        c["sig_pay"], c["sig"] = key_for(c["kws"], True), key_for(c["kws"], False)
        c["rarest"] = min({kw_name(k) for k in c["kws"]}, key=lambda n: (freq[n], n))
        by_pay[c["sig_pay"]].append(oid)
        by_plain[c["sig"]].append(oid)
    leaf_of = {}
    for oid, c in cards.items():
        if len(by_pay[c["sig_pay"]]) >= MIN:
            leaf_of[oid] = ("sig", c["sig_pay"])
        elif len(by_plain[c["sig"]]) >= MIN:
            leaf_of[oid] = ("sig", c["sig"])
        else:
            leaf_of[oid] = ("other", c["rarest"])
    other_n = collections.Counter(v[1] for v in leaf_of.values() if v[0] == "other")
    for oid, v in list(leaf_of.items()):
        if v[0] == "other" and other_n[v[1]] < MIN:
            leaf_of[oid] = ("rare", "")

    def leaf_id(v):
        return {"sig": "kw:" + v[1], "other": "kw:other:" + v[1], "rare": RARE}[v[0]]

    def leaf_name(v):
        if v[0] == "rare":
            return RARE_NAME
        if v[0] == "other":
            return "%s: other combinations" % display(v[1])
        if v[1] == "Landwalk":
            return "Landwalk: other land types"
        names = []
        for p in v[1].split("+"):
            if "|" in p:
                names.append(display_landwalk(p.split("|")[1]))
            else:
                names.append(display(p))
        return " + ".join(names)

    leaves = {}
    for oid, v in leaf_of.items():
        lid = leaf_id(v)
        L = leaves.setdefault(lid, {"id": lid, "name": leaf_name(v), "kind": v[0], "cards": []})
        L["cards"].append(oid)
        if v[0] == "sig":
            L["keywords"] = sorted({p.split("|")[0] for p in v[1].split("+")})
        elif v[0] == "other":
            L["keywords"] = [v[1]]
    for L in leaves.values():
        if L["kind"] == "rare":
            L["keywords"] = []
            L["sort"] = "keyword"
            L["cards"].sort(key=lambda o: (display(cards[o]["rarest"]), cards[o]["name"], o))
        else:
            L["sort"] = "name"
            L["cards"].sort(key=lambda o: (cards[o]["name"], o))
        L["n_cards"] = len(L["cards"])
        L["branches"] = (["Rare keyword combinations"] if L["kind"] == "rare"
                         else sorted(display(k) for k in L["keywords"]))
        L["note"] = ("Catch-all: signatures too rare for a leaf of their own (< %d cards) and whose "
                     "rarest keyword has too few cards for an 'other combinations' leaf. Sorted by "
                     "rarest keyword." % MIN) if L["kind"] == "rare" else None

    branches = collections.OrderedDict()
    for lid, L in leaves.items():
        for b in L["branches"]:
            B = branches.setdefault(b, {"name": b, "leaves": [], "cards": set(),
                                        "catch_all": b == "Rare keyword combinations"})
            B["leaves"].append(lid)
            B["cards"] |= set(L["cards"])

    faces = {}
    for oid, c in cards.items():
        lid = leaf_id(leaf_of[oid])
        for fid in c["faces"]:
            faces[fid] = {"card": oid, "method": "keyword_rule", "leaf": lid,
                          "keywords": [shown_keyword(k) for k in c["face_kws"][fid]],
                          "rarest": display(c["rarest"])}

    # ---- type notes (docs only; no split is applied)
    strays = sorted(c["name"] for c in cards.values() if "Creature" not in c["types"])
    vehicle_leaf = [c["name"] for oid, c in cards.items()
                    if "Creature" not in c["types"] and leaf_of[oid] == ("other", "Crew")]
    stray_outside_vehicles = sorted(set(strays) - set(vehicle_leaf))
    audit_flagged = []
    for lid, L in leaves.items():
        cnt = collections.Counter()
        for oid in L["cards"]:
            for t in (cards[oid]["types"] & PERMANENT) or {"Spell"}:
                cnt[t] += 1
        big = [t for t, v in cnt.items() if t in PERMANENT and v / L["n_cards"] >= 0.20]
        if len(big) >= 2:
            audit_flagged.append(lid)

    sizes = sorted(L["n_cards"] for L in leaves.values())
    meta = {
        "what": "keyword-only cards placed by rule (kw:<signature>); additive, no clustering input changed",
        "min_leaf": MIN,
        "cards": len(cards), "faces": len(faces),
        "leaves": len(leaves), "branches": len(branches),
        "leaf_kinds": dict(collections.Counter(L["kind"] for L in leaves.values())),
        "cards_by_leaf_kind": dict(collections.Counter(L["kind"] for L in leaves.values() for _ in L["cards"])),
        "largest_leaf": max(((L["n_cards"], L["id"]) for L in leaves.values())),
        "smallest_leaf": min(((L["n_cards"], L["id"]) for L in leaves.values())),
        "median_leaf": sizes[len(sizes) // 2],
        "type_notes": {
            "non_creature_cards": len(strays),
            "in_clean_vehicle_leaf": len(vehicle_leaf),
            "strays_outside_vehicles": stray_outside_vehicles,
            "audit_rule_flagged_leaves": len(audit_flagged),
            "audit_flag_cause": "artifact creatures counted under both Artifact and Creature; no split applied",
        },
        "distinct_signatures": len({c["sig"] for c in cards.values()}),
    }
    doc = {
        "meta": meta,
        "branches": [{"name": b["name"], "leaves": sorted(b["leaves"], key=lambda l: (-leaves[l]["n_cards"], l)),
                      "n_cards": len(b["cards"]), "catch_all": b["catch_all"]}
                     for b in sorted(branches.values(), key=lambda b: (b["catch_all"], -len(b["cards"]), b["name"]))],
        "leaves": {lid: {k: v for k, v in L.items() if k != "cards"} | {"faces": [
            fid for oid in L["cards"] for fid in cards[oid]["faces"]]} for lid, L in sorted(leaves.items())},
        "faces": dict(sorted(faces.items())),
    }
    blob = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(blob)
    print(json.dumps(meta, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
