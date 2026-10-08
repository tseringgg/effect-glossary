#!/usr/bin/env python3
"""The per-ability taxonomy: the main view.

    python src/build_ability_taxonomy.py [--include-gap-cards]

Writes (sorted keys; identical bytes across runs):
    build/ability_taxonomy.json            tree: families -> effect-and-verb nodes -> leaves (names, sizes, flags), blocks,
                                           totals, rules, name corrections applied / orphaned
    build/ability_taxonomy_members.json    leaf id -> member abilities [card, ability number]
    build/ability_taxonomy_cards.json      card -> name, cost, type, rules text, abilities [text, leaf, state]
    build/ability_taxonomy_ledger.json     one row per ability (state, reason, leaf) + one row per card (view)
                                           + reconciliation checks
    build/ability_taxonomy_unorganized.json "Not yet organized" groups and their cards
    build/ability_taxonomy_lookup.json     "Find a card": one entry per oracle id in the universe

RULES. Probe 2 (src/probe2_signature_taxonomy.py) is imported, not copied: fields2(), the rarest-field-first backoff
at minimum 5 with literal counts and the bare-fallback guard, the generic-leaf flags, the partial layer's gap-card
tests. Differences from probe 2, all approved in reports/ability-taxonomy-design.md section 9:
  1. Leaves are built from clean abilities on clean cards only. Gap-card abilities that pass the gap tests are assigned
     against those counts and add nothing to any count. They are held out unless --include-gap-cards is given
     (decided by the gap-card hand check).
  2. Replacement items with no effect node (signature "repl:*") are not ability leaves: the old signature layer stays,
     unchanged, as the "Replacement effects and costs" block.
  3. Inline modal items (one item holding its modes in mode_abilities) are read as one ability per mode; the
     placeholder item itself is not placed (reason "modal").
  4. A card is a gap card when any of its faces is (one card differs from the per-face rule).
  5. The three effect types probe 2 filed under a catch-all family are mapped to real families (Tribute and
     AddPendingETBCounters -> Counters, ChooseFromZone -> Choices); any effect type with no family is unplaced
     (reason "no_family"). There is no catch-all family.
  6. Added after the first hand check (decided with the owner): four more "important field not recorded" flags, found
     by scanning every leaf for facets that split its members: who is damaged (DamageEachPlayer, "all" damage,
     damage to a player or an unresolved object), the sign of a power/toughness change, who loses or gains life when
     no player is recorded. A flagged leaf's name says what is not recorded.
  7. Sign and recipient moved into the signature (round 3, decided with the owner after measuring how often the parse
     records them: sign 91% of the abilities in the sign-flagged leaves, DamageEachPlayer recipient 98.9%, "players hit"
     on DamageAll 2.1%, who loses or gains life 89%). Two verb-bound fields, never dropped by the backoff:
       sign   the sign class of a power/toughness change: "+", "-", "+/-", "0", or "?" when a count or reference makes it
              undecidable (src/measure_field_presence.sign_class)
       recip  DamageEachPlayer / DamageAll player_filter ("opponents" / "each player")
     Flags are now per ability: a leaf is flagged for sign only when its sign is "?", for the damage recipient only when
     DamageEachPlayer lacks it, when DamageAll lacks it (97.9% do), or when the target has no type filter; the life rule
     (who empty) is unchanged. Names no longer add a duration for effects that do not carry their own, and the lure
     (MustBeBlocked on itself) has its own name.
Display only: leaf names (auto-generated, corrections/ability_taxonomy_names.json overrides, keyed by signature),
the display threshold (10) and the roll-up. Names never place anything. No Scryfall tag data is read.
"""
import argparse
import collections
import hashlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ledger as BL                 # noqa: E402  gap_fragments
import build_unorganized as BU            # noqa: E402  clean_gaps, walk_unrecognized, fold_char, oos_code, OOS_TEXT
import build_partial_ability_layer as BPL  # noqa: E402  sq, fam, CONT (via p2.gap_tests' logic)
import probe_signature_taxonomy as pst    # noqa: E402
import probe2_signature_taxonomy as p2    # noqa: E402
import measure_field_presence as MFP      # noqa: E402  sign_class only
import ability_names as AN                # noqa: E402  display names derived from the signature

# rule 7: two more verb-bound fields. probe 2's functions read these module globals at call time.
p2.L2G = tuple(p2.L2G) + ("sign", "recip")
p2.CANON = list(p2.L2G) + ["obj", "ctrl", "quant", "props", "kw", "dur", "cond", "wrap", "chain", "tok"]
RECIP = {"Opponent": "opponents", "All": "each player"}
# words, not symbols: probe 2's EMPTY treats "-" as "no value", so a "-" sign class would silently merge with "no sign"
SIGNW = {"+": "boost", "-": "shrink", "+/-": "mixed", "0": "zero", "?": "unknown"}


def fields3(x):
    """probe 2's fields2 plus the sign class and the damage recipient (rule 7)."""
    f = p2.fields2(x)
    f["sign"] = ""
    f["recip"] = ""
    if not f["usable"]:
        return f
    b, it = x["b"], x["item"]
    if b == "static_abilities":
        sc = MFP.sign_class(None, [it])
        f["sign"] = SIGNW.get(sc, "")
        return f
    ex, e = pst.exec_and_effect(b, it)
    if not isinstance(e, dict):
        return f
    if f["ftype"] == "Modal":
        return f
    ex, e, _w, _we = pst.head(ex, e)
    statics = e.get("static_abilities") if e.get("type") == "GenericEffect" else None
    sc = MFP.sign_class(e, statics)
    f["sign"] = SIGNW.get(sc, "")
    if e.get("type") in ("DamageEachPlayer", "DamageAll"):
        pf = e.get("player_filter")
        if isinstance(pf, dict) and pf.get("type"):
            f["recip"] = RECIP.get(pf["type"], pf["type"].lower())
    return f

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
CORR = os.path.join(HERE, "corrections", "ability_taxonomy_names.json")
MIN = 5
SHOW = 10
SNAPSHOT = "phase.rs card-data.json, last modified 2026-04-20, plus the post-snapshot overlays in data/overlay/"

FAMILY_FIX = {"Tribute": "Counters", "AddPendingETBCounters": "Counters", "ChooseFromZone": "Choice / wrapper"}
FAMILY_NAME = {
    "Destroy": "Destroy", "Damage": "Damage", "Life": "Life gain and loss", "Zone change": "Moving cards between zones",
    "Library": "Library: search, reveal, mill", "Card draw": "Card draw", "Discard / hand": "Discard and hands",
    "Sacrifice": "Sacrifice", "Counters": "Counters", "Tokens": "Tokens", "Mana": "Mana",
    "Pump / grant": "Pump and grant abilities", "Tap / untap": "Tap and untap", "Counter spell": "Counter spells",
    "Copy": "Copy", "Control": "Gain control", "Cast / play": "Cast or play from elsewhere", "Combat": "Combat",
    "Attach": "Attach and equip", "Protection": "Regenerate and prevent damage", "Transform / face": "Transform and face-down",
    "Game / player": "Game and player effects", "Choice / wrapper": "Choices", "Keyword-handled": "Keyword actions the rules engine runs",
    "Static: continuous": "Continuous effects (static)", "Static: cost change": "Cost changes (static)",
    "Static: restriction": "Restrictions (static)", "Static: other rule": "Rules changes (static)",
}
FLAG_NOTE = {
    "who draws is not in the parse":
        "Who draws isn't recorded, so this group is broader than it looks: it mixes “you draw” with “target player draws” and “each opponent draws”.",
    "'all' vs 'target' is not recorded on return-to-hand":
        "“Return all” and “return target” are recorded the same way, so this group mixes mass return with single-target return and is broader than it looks.",
    "source zone of a self-return is not in the parse":
        "Where the card returns from isn't recorded, so “return this from your graveyard” and “return this from the battlefield” are mixed, and this group is broader than it looks.",
    "object unresolved by the parser":
        "The parser doesn't say what this applies to (it recorded “that thing” or “any target”), so this group is broader than it looks.",
    "grant with no parsed modification":
        "The parser recorded that something is granted but not what, so this group is broader than it looks.",
}
FLAG_NOTE.update({
    "who is damaged is not recorded":
        "Who is damaged isn't recorded for these abilities (the parser kept no recipient, or only “something”), so this group is broader than it looks.",
    "players hit by an 'all' damage effect are not recorded":
        "Whether players are damaged as well as the creatures isn't recorded for most “damage to all …” abilities (the parser kept it for only a few), so this group is broader than it looks.",
    "sign of the power/toughness change is not recorded":
        "For these abilities the change depends on a count, so whether it is + or − isn't recorded, and this group is broader than it looks.",
    "who loses or gains life is not recorded":
        "Who loses or gains the life isn't recorded (you, an opponent, each player), and paying life is read the same way, so this group is broader than it looks.",
    "“that player” is not reliable here":
        "The parse records the triggering player as the one who draws or gains the life, but in the card text it is usually you, so who actually draws or gains is not reliably recorded and this group is broader than it looks.",
})
FLAG_SHORT = {
    "who draws is not in the parse": "who draws isn't recorded",
    "'all' vs 'target' is not recorded on return-to-hand": "“all” vs “target” isn't recorded",
    "source zone of a self-return is not in the parse": "where it returns from isn't recorded",
    "object unresolved by the parser": "what it applies to isn't recorded",
    "grant with no parsed modification": "what is granted isn't recorded",
    "who is damaged is not recorded": "who is damaged isn't recorded",
    "players hit by an 'all' damage effect are not recorded": "whether players are hit isn't recorded",
    "sign of the power/toughness change is not recorded": "+ or − isn't recorded",
    "who loses or gains life is not recorded": "who loses or gains it isn't recorded",
    "“that player” is not reliable here": "who draws or gains it isn't reliably recorded (the parse says “that player”, the text usually means you)",
}


def extra_flags(ftype, ret):
    """Rules 6 and 7: fields that are not recorded and split a leaf's members. Per ability: the signature now carries
    sign and recipient where the parse has them, so a leaf is flagged only for the abilities that lack the field."""
    out = []
    if ftype == "DamageEachPlayer" and not ret.get("recip"):
        out.append("who is damaged is not recorded")
    if ftype == "Damage" and not ret.get("recip"):
        out.append("players hit by an 'all' damage effect are not recorded")
    if ftype == "DealDamage" and ret.get("obj") == "object":
        out.append("who is damaged is not recorded")
    if ret.get("sign") == "unknown":
        out.append("sign of the power/toughness change is not recorded")
    if ftype in ("LoseLife", "GainLife") and not ret.get("who"):
        out.append("who loses or gains life is not recorded")
    if ftype in ("Draw", "GainLife") and ret.get("who") in ("scope:TriggeringPlayer", "triggering player"):
        out.append("\u201cthat player\u201d is not reliable here")
    return out


GROUPS = [
    (1, "Parsed, but with a gap",
     "The parser read most of this card but could not understand part of its text (shown next to the card). We don't "
     "group a card on a partial reading, because it could put it in the wrong place."),
    (2, "Parsed, but too unusual to group",
     "The parser read this card fully, but its abilities are rare: fewer than five other abilities have the same shape, "
     "so there is no group of five to put it in yet."),
    (3, "Parsed, but part of its text may not have been read",
     "A check found that the parser may have left out a condition (an “if”, “unless” or “as long as”) from this card's "
     "abilities. We don't group an ability that may be incomplete."),
    (4, "No effect to group",
     "The parser read this card fully, but its rules change how other things happen (for example “if X would happen, "
     "do Y instead”) rather than doing something themselves, and no replacement group covers it."),
    (5, "Not parsed yet",
     "The parser produced nothing usable for this card's rules text, so there is nothing to group it on."),
    (6, "Known parse mistake",
     "We checked this card by hand and the parser got part of it wrong, for example reading a cost as free. It is held "
     "back until that is fixed."),
]
REASON_GROUP = {"gap": 1, "too_unusual": 2, "text_may_be_lost": 3, "no_effect_to_group": 4, "not_parsed": 5,
                "known_parse_mistake": 6}
RARE_WORDS = {"rare_object": "no other ability does this to this kind of object",
              "rare_verb_parameter": "no other ability does this with these details",
              "rare_effect_type": "fewer than five abilities do this at all",
              "below_minimum_size": "its exact group has fewer than five abilities",
              "no_signature": "the parser recorded no effect", "no_family": "this effect has no family yet"}


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def dump(name, obj):
    with io.open(os.path.join(BUILD, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


# ---------------------------------------------------------------- backoff (probe 2's, counts from a reference set)
def assign_rf_ref(Fref, Ftgt, mn):
    """probe 2's assign_rf, generalised: counts and rarity come from Fref; Ftgt are assigned against them.
    With Ftgt == Fref this is probe 2's function exactly."""
    rar = collections.Counter()
    for f in Fref:
        if f["usable"]:
            for k in p2.DROPPABLE:
                rar[(f["ftype"], k, p2.val(f, k))] += 1
    counters = {}

    def count(D):
        if D not in counters:
            keep = [k for k in p2.CANON if k not in D]
            counters[D] = collections.Counter(tuple(p2.val(f, k) for k in ["ftype"] + keep) for f in Fref if f["usable"])
        return counters[D]
    out = []
    for f in Ftgt:
        if not f["usable"]:
            out.append(("x", "no_signature"))
            continue
        l2_empty = not any(p2.val(f, k) for k in p2.L2G)
        has_obj = p2.val(f, "obj") != ""
        D = frozenset()
        S = [k for k in p2.DROPPABLE if p2.val(f, k)]
        placed = None
        while True:
            keep = [k for k in p2.CANON if k not in D]
            if count(tuple(sorted(D)))[tuple(p2.val(f, k) for k in ["ftype"] + keep)] >= mn:
                placed = (p2.level_of(f, keep), p2.sigstr(f, set(keep)))
                break
            cand = [k for k in S if k not in D and not (k == "obj" and l2_empty and has_obj)]
            if not cand:
                break
            drop = min(cand, key=lambda k: (rar[(f["ftype"], k, p2.val(f, k))], p2.DROP_PRIORITY.index(k)))
            D = D | {drop}
        out.append(placed or ("x", "rare_verb_parameter" if not l2_empty else ("rare_object" if has_obj else "rare_effect_type")))
    return out


def gap_tests(items):
    """p2.gap_tests with the reason kept per item (same logic, same order of tests)."""
    rows = jl("index.json")["rows"]
    byid = {r["id"]: r for r in rows}
    chunks = {}
    rec = jl("placements.json")["recovered"]["chunk"]
    cache = {}

    def face_info(face):
        if face not in cache:
            if face in byid:
                ch = byid[face]["ch"]
                if ch not in chunks:
                    chunks[ch] = jl("chunks/%d.json" % ch)
                e = chunks[ch][face]
            else:
                e = rec[face]
            lines = [BPL.sq(re.sub(r"\([^)]*\)", "", ln)) for ln in (e.get("oracle_text") or "").split("\n")]
            frags = BL.gap_fragments(e, e.get("name") or "")
            fsq = [(BPL.fam(k, c), BPL.sq(t)) for k, c, t in frags]
            cont = any(f.startswith("Unimplemented:") and f.split(":", 1)[1] in BPL.CONT for f, _ in fsq)
            cache[face] = (lines, fsq, cont)
        return cache[face]
    keep, why = [], {}
    for x in items:
        if x["kind"] != "gap":
            keep.append(x)
            continue
        lines, fsq, cont = face_info(x["face"])
        text = (x["item"].get("description") or "").strip()
        key = (x["face"], x["b"], x["i"])
        if not text or re.fullmatch(r"Chapter \d+", text):
            why[key] = "no_text"
            continue
        d = BPL.sq(text)
        mine = [ln for ln in lines if ln and (d[:40] in ln or ln in d)]
        if any(t and any((t[:25] in ln) or (ln[:25] in t) for ln in mine) for _, t in fsq):
            why[key] = "same_line_gap"
            continue
        if cont:
            why[key] = "continuation_gap"
            continue
        keep.append(x)
    return keep, why


# ---------------------------------------------------------------- names (display only)
# The naming template lives in src/ability_names.py (derived from the signature; see its docstring).
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-gap-cards", action="store_true")
    args = ap.parse_args()
    include_gap = args.include_gap_cards

    L = jl("ledger.json")["rows"]
    P = jl("placements.json")
    stages = P["recovered"]["stages"]
    KL = jl("keyword_layer.json")
    SL = jl("signature_layer.json")
    old_lookup = jl("lookup.json")
    cdrops = jl("condition_drops.json")
    corr_cards = {c["oracle_id"]: c for c in json.load(io.open(os.path.join(HERE, "corrections", "corrections.json"),
                                                             encoding="utf-8"))}

    def card_kind(oid):
        st = L[oid]["status"]
        if st == "missing_from_export":
            ss = {f["stage"] for f in stages.get(oid, [])}
            if ss & set(pst.GAPPY):
                return "gap"
            if "unparsed" in ss:
                return "unparsed"
            return "clean"
        if st in pst.CLEAN:
            return "clean"
        if st in pst.GAPPY:
            return "gap"
        return st

    items, excl, AL = pst.population()
    for x in items:                                       # rule 4: card-level gap
        if x["kind"] == "clean" and card_kind(x["oid"]) == "gap":
            x["kind"] = "gap"
    items, gap_why = gap_tests(items)

    # ---- card data (rows, entries) for texts
    idx = {r["id"]: r for r in jl("index.json")["rows"]}
    rec_rows = {r["id"]: r for r in P["recovered"]["rows"]}
    rec_chunk = P["recovered"]["chunk"]
    chunks = {}

    def entry(fid):
        if fid in idx:
            ch = idx[fid]["ch"]
            if ch not in chunks:
                chunks[ch] = jl("chunks/%d.json" % ch)
            return chunks[ch].get(fid) or {}
        return rec_chunk.get(fid) or {}

    def row(fid):
        return idx.get(fid) or rec_rows.get(fid) or {}

    # ---- abilities: fields, modal expansion (rule 3), families (rule 5), replacement block (rule 2)
    A = []          # dicts: oid, face, b, i, mode, text, kind, f, state, reason
    for x in items:
        f = fields3(x)
        base = {"oid": x["oid"], "face": x["face"], "b": x["b"], "i": x["i"], "mode": None, "kind": x["kind"],
                "item": x["item"]}
        text = (x["item"].get("description") or "").strip()
        if f["ftype"] == "Modal":
            ex, _ = pst.exec_and_effect(x["b"], x["item"])
            md = ((ex.get("modal") or {}).get("mode_descriptions")) or []
            A.append(dict(base, text=text, f=f, pre="modal"))
            for k, m in enumerate(ex.get("mode_abilities") or []):
                if not isinstance(m, dict):
                    continue
                mt = md[k] if k < len(md) else ""
                fm = fields3({"b": "abilities", "item": m})
                A.append(dict(base, mode=k, item=m, f=fm, pre=None,
                              text=((text + " — " if text else "") + mt).strip()))
            continue
        if not text:
            e = entry(x["face"])
            md = (e.get("modal") or {}).get("mode_descriptions") or []
            if x["b"] == "abilities" and md and len(md) == len(e.get("abilities") or []) and x["i"] < len(md):
                text = md[x["i"]]
            elif x["b"] == "abilities" and f["ftype"] == "Attach":
                kl = [ln for ln in (e.get("oracle_text") or "").split("\n") if re.match(r"^(Equip|Reconfigure|Fortify)\b", ln)]
                text = kl[0] if kl else ""
        m_ch = re.fullmatch(r"Chapter (\d+)", text)
        if m_ch:                                     # display only: show the chapter's own line, not "Chapter N"
            n_ch = int(m_ch.group(1))
            for ln in (entry(x["face"]).get("oracle_text") or "").split("\n"):
                mm = re.match(r"^((?:[IVX]+)(?:, [IVX]+)*) — ", ln)
                if mm and n_ch in [ROMAN.get(r_.strip()) for r_ in mm.group(1).split(",")]:
                    text = ln
                    break
        A.append(dict(base, text=text, f=f, pre=None))
    for a in A:
        f = a["f"]
        if a["pre"]:
            continue
        if f["fam"] == "Other":
            if f["ftype"] in FAMILY_FIX:
                f["fam"] = FAMILY_FIX[f["ftype"]]
            else:
                a["pre"] = "no_family"
        if f["ftype"].startswith("repl:"):
            a["pre"] = "replacement_group"
        elif not f["usable"]:
            a["pre"] = "no_signature"
    ref = [j for j, a in enumerate(A) if a["kind"] == "clean" and not a["pre"]]
    tgt = [j for j, a in enumerate(A) if a["kind"] == "gap" and not a["pre"]]
    Fref = [A[j]["f"] for j in ref]
    for j, r in zip(ref, assign_rf_ref(Fref, Fref, MIN)):
        A[j]["asg"] = r
    for j, r in zip(tgt, assign_rf_ref(Fref, [A[j]["f"] for j in tgt], MIN)):
        A[j]["asg"] = r

    # ---- leaves (clean members only), flags, ids
    members = collections.defaultdict(list)
    for j in ref:
        r = A[j]["asg"]
        if r[0] != "x":
            members[tuple(r)].append(j)
    leaf_info = {}
    for lf, js in members.items():
        parts = lf[1].split(" · ")
        fam, ftype = parts[0].split("=", 1)[1], parts[1].split("=", 1)[1]
        ret = dict(p.split("=", 1) for p in parts[2:])
        lid = "a" + hashlib.sha1(lf[1].encode("utf-8")).hexdigest()[:9]
        node = (fam, ftype) + tuple(ret.get(k, "") for k in p2.L2G)
        leaf_info[lf] = {"id": lid, "fam": fam, "ftype": ftype, "ret": ret, "flags": p2.flag_reasons(ftype, ret) + extra_flags(ftype, ret),
                         "level": lf[0], "n": len(js), "node": node}
    assert len({v["id"] for v in leaf_info.values()}) == len(leaf_info), "leaf id collision"

    def state_of(a):
        if a["pre"]:
            return "unplaced", a["pre"]
        r = a["asg"]
        if r[0] == "x":
            return "unplaced", r[1]
        li = leaf_info.get(tuple(r))
        if li is None or li["n"] < MIN:
            return "unplaced", "below_minimum_size"
        if li["flags"]:
            return "placed_broad", "generic_flagged"
        return "placed", ""
    for a in A:
        st, rs = state_of(a)
        if a["kind"] == "gap" and st in ("placed", "placed_broad") and not include_gap:
            a["state"], a["reason"] = "held_out", "gap_card_" + st
        else:
            a["state"], a["reason"] = st, rs
        a["leaf"] = leaf_info[tuple(a["asg"])]["id"] if a.get("asg") and a["asg"][0] != "x" and tuple(a["asg"]) in leaf_info else ""

    # ---- names
    corrections = {"v": 1, "leaves": {}, "nodes": {}, "families": {}}
    if os.path.exists(CORR):
        corrections = json.load(io.open(CORR, encoding="utf-8"))
    used = {"leaves": set(), "nodes": set(), "families": set()}
    leaf_by_id = {}
    node_rets = collections.defaultdict(list)
    for lf, li in leaf_info.items():
        node_rets[li["node"]].append((li["id"], li["ret"]))
    auto_items = {}
    leaf_by_id_n = {li["id"]: li["n"] for li in leaf_info.values()}
    for lf, li in leaf_info.items():
        buckets = collections.Counter(A[j]["b"] for j in members[lf])
        sibs = [r for i, r in node_rets[li["node"]] if i != li["id"]]
        auto_items[li["id"]] = {"name": AN.name_leaf_final(li["ftype"], li["ret"], buckets, sibs), "node": li["node"], "sig": lf[1]}
    # names that still collide inside a node get the fewest extra fields until they differ; only leaves of MIN or more are shown, so only they compete
    shown_items = {i: v for i, v in auto_items.items() if leaf_by_id_n[i] >= MIN}
    AN.disambiguate(shown_items)
    for lf, li in leaf_info.items():
        if li["n"] >= MIN:
            mino = {}
            for f_ in ("props", "kw", "obj", "ctrl"):
                if not li["ret"].get(f_):
                    vals = [(A[j]["f"].get(f_, "") if A[j]["f"].get(f_, "") != "-" else "") for j in members[lf]]
                    mino[f_] = 1 - collections.Counter(vals).most_common(1)[0][1] / len(vals)
            shown_items[li["id"]]["name"] = AN.universal_marker(shown_items[li["id"]]["name"], li["ret"], mino)
    for lf, li in leaf_info.items():
        auto = auto_items[li["id"]]["name"]
        c = corrections.get("leaves", {}).get(lf[1])
        if c:
            used["leaves"].add(lf[1])
        li["name"] = c["name"] if c else auto
        li["auto_name"] = auto
        li["auto_named"] = not c
        li["coined"] = bool(c and c.get("coined"))
        li["sig"] = lf[1]
        leaf_by_id[li["id"]] = li
    for li in leaf_info.values():
        if li["flags"] and li["auto_named"]:
            li["name"] += " — " + "; ".join(FLAG_SHORT[f] for f in li["flags"])
    nodes = {}
    for lf, li in leaf_info.items():
        nk = li["node"]
        if nk not in nodes:
            key = "|".join(nk)
            c = corrections.get("nodes", {}).get(key)
            if c:
                used["nodes"].add(key)
            ret = {k: v for k, v in zip(p2.L2G, nk[2:]) if v}
            auto = AN.name_node(li["ftype"], ret)
            nodes[nk] = {"id": "n" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:9], "key": key, "fam": nk[0],
                         "ftype": nk[1], "name": c["name"] if c else auto, "auto_named": not c, "leaves": []}
        nodes[nk]["leaves"].append(li["id"])
    fam_names = {}
    for f_ in sorted({li["fam"] for li in leaf_info.values()}):
        c = corrections.get("families", {}).get(f_)
        if c:
            used["families"].add(f_)
        fam_names[f_] = c["name"] if c else FAMILY_NAME.get(f_, f_)
    orphans = {k: sorted(set(corrections.get(k, {})) - used[k]) for k in ("leaves", "nodes", "families")}

    # ---- card views
    kw_card = {}
    for fid, v in KL["faces"].items():
        kw_card.setdefault(v["card"], v["leaf"])
    sig_card = {}
    for fid, v in SL["faces"].items():
        if v.get("method") == "signature_rule":
            sig_card.setdefault(v["card"], v["leaf"])
    van_card = {v["card"] for v in P["faces"].values() if v.get("method") == "vanilla_rule"} | \
        {v["card"] for v in SL["vanilla"].values()}
    by_card = collections.defaultdict(list)
    for j, a in enumerate(A):
        by_card[a["oid"]].append(j)
    n_items = collections.Counter(r[0] for r in AL["rows"])
    view = {}
    for oid, r in sorted(L.items()):
        if r["status"] == "out_of_scope":
            view[oid] = ("not_a_card", "")
        elif oid in kw_card:
            view[oid] = ("keyword_block", "")
        elif oid in van_card:
            view[oid] = ("no_abilities", "")
        elif oid in sig_card:
            view[oid] = ("replacement_group", "")
        else:
            k = card_kind(oid)
            js = by_card.get(oid, [])
            sts = collections.Counter(A[j]["state"] for j in js)
            rss = collections.Counter(A[j]["reason"] for j in js)
            if k in ("clean", "gap") and sts["placed"]:
                view[oid] = ("placed", "")
            elif k in ("clean", "gap") and sts["placed_broad"]:
                view[oid] = ("broad_only", "")
            elif k == "gap":
                view[oid] = ("unorganized", "gap")
            elif k == "clean":
                if any(rs in RARE_WORDS for rs in rss):
                    view[oid] = ("unorganized", "too_unusual")
                elif js and all(A[j]["reason"] in ("replacement_group", "modal") for j in js):
                    view[oid] = ("unorganized", "no_effect_to_group")
                elif n_items.get(oid, 0) > 0:
                    view[oid] = ("unorganized", "text_may_be_lost")
                else:
                    view[oid] = ("unorganized", "no_effect_to_group")
            elif k == "unparsed":
                view[oid] = ("unorganized", "not_parsed")
            elif k == "corrections_flagged":
                view[oid] = ("unorganized", "known_parse_mistake")
            else:
                raise SystemExit("in-scope card with no view: %s %s %s" % (r["name"], r["status"], k))

    # ---- ledger rows: every ability item of the old ability ledger (+ modal modes)
    cd = {(h["oid"], h["bucket"], h["idx"]): h for h in cdrops}
    a_by_key = collections.defaultdict(list)
    for j, a in enumerate(A):
        a_by_key[(a["face"], a["b"], a["i"])].append(j)
    rows_out = []
    for row_ in AL["rows"]:
        oid, face, b, i, text = row_[0], row_[1], row_[2], row_[3], row_[4]
        js = a_by_key.get((face, b, i))
        if js:
            for j in js:
                a = A[j]
                rows_out.append([oid, face, b, i, a["mode"], a["text"][:200], a["state"], a["reason"], a["leaf"]])
            continue
        if view[oid][0] in ("keyword_block", "no_abilities", "not_a_card"):
            reason = "not_in_scope:" + view[oid][0]
        elif (face, b, i) in gap_why:
            reason = "gap_card_" + gap_why[(face, b, i)]
        elif (oid, b, i) in cd:
            reason = "flagged_condition_drop"
        elif card_kind(oid) in ("clean", "gap"):
            reason = "item_gap"
        else:
            reason = "not_in_scope:" + str(L[oid]["status"])
        rows_out.append([oid, face, b, i, None, (text or "")[:200], "unplaced", reason, ""])
    rows_out.sort(key=lambda r: (r[0], r[1], r[2], r[3], -1 if r[4] is None else r[4]))

    # ---- cards file (in-scope cards): name, cost, type, text, abilities
    cards = {}
    for oid, r in sorted(L.items()):
        if view[oid][0] == "not_a_card":
            continue
        fids = [f["id"] for f in r["evidence"].get("faces", [])] or \
               [f["id"] for f in (r["evidence"].get("recovered") or {}).get("faces", [])] or [oid]
        rr = [row(fid) for fid in fids]
        rr0 = next((x for x in rr if x), {})
        ab = []
        for j in sorted(by_card.get(oid, []), key=lambda j: (A[j]["face"], A[j]["b"], A[j]["i"], -1 if A[j]["mode"] is None else A[j]["mode"])):
            a = A[j]
            if a["pre"] == "modal":
                continue
            ab.append([a["text"][:300], a["leaf"] if a["state"] in ("placed", "placed_broad") else "",
                       {"placed": "p", "placed_broad": "b", "held_out": "h"}.get(a["state"], "u")])
        cards[oid] = {"n": r["name"], "ty": rr0.get("type") or "", "col": rr0.get("col") or "",
                      "mv": rr0.get("mv"), "t": "\n//\n".join((x.get("text") or "") for x in rr if x)[:1500], "ab": ab}

    # ---- members per leaf (cards, ability number within the card's ab list)
    mem_out = collections.defaultdict(list)
    for oid, c in cards.items():
        seen = set()
        for k, (t, lid, st) in enumerate(c["ab"]):
            if lid and st in ("p", "b") and lid not in seen:
                seen.add(lid)
                mem_out[lid].append([oid, k])
    for lid in mem_out:
        mem_out[lid].sort(key=lambda m: (cards[m[0]]["n"].lower(), m[0]))

    # ---- tree
    fam_tree = collections.defaultdict(list)
    for nk, nd in nodes.items():
        lis = [leaf_by_id[i] for i in nd["leaves"] if leaf_by_id[i]["n"] >= MIN]
        if not lis:
            continue
        vis = [li for li in lis if li["n"] >= SHOW]
        roll = [li for li in lis if li["n"] < SHOW]
        nd_out = {"id": nd["id"], "name": nd["name"], "auto_named": nd["auto_named"], "key": nd["key"],
                  "abilities": sum(li["n"] for li in lis),
                  "leaves": [li["id"] for li in sorted(vis, key=lambda li: (-li["n"], li["name"]))],
                  "rolled": [li["id"] for li in sorted(roll, key=lambda li: (-li["n"], li["name"]))]}
        nd_out["cards"] = len({m[0] for li in lis for m in mem_out.get(li["id"], [])})
        fam_tree[nk[0]].append(nd_out)
    families = []
    for f_, nds in fam_tree.items():
        nds.sort(key=lambda n: (-n["abilities"], n["name"]))
        families.append({"key": f_, "name": fam_names[f_], "abilities": sum(n["abilities"] for n in nds),
                         "cards": len({m[0] for n in nds for lid in n["leaves"] + n["rolled"] for m in mem_out.get(lid, [])}),
                         "nodes": nds})
    families.sort(key=lambda f: (-f["abilities"], f["name"]))
    leaves_out = {}
    for li in leaf_info.values():
        if li["n"] < MIN:
            continue
        leaves_out[li["id"]] = {"name": li["name"], "auto_named": li["auto_named"], "coined": li["coined"],
                                "sig": li["sig"], "level": li["level"], "abilities": li["n"],
                                "cards": len(mem_out.get(li["id"], [])), "flags": li["flags"],
                                "notes": [FLAG_NOTE.get(f, f) for f in li["flags"]],
                                "node": nodes[li["node"]]["id"], "family": li["fam"], "visible": li["n"] >= SHOW}

    # ---- unorganized groups
    ucards = collections.defaultdict(list)
    for oid, (v, rs) in view.items():
        if v != "unorganized":
            continue
        r = L[oid]
        c = {"c": oid, "n": r["name"]}
        gid = REASON_GROUP[rs]
        if gid == 1:
            frags = r["evidence"].get("fragments") or []
            if not frags:
                for fid in [f["id"] for f in (r["evidence"].get("recovered") or {}).get("faces", [])] or [oid]:
                    e = entry(fid)
                    frags.extend(BL.gap_fragments(e, e.get("name") or ""))
            gaps = BU.clean_gaps(frags)
            if gaps:
                c["g"] = gaps[:6]
            held = [A[j]["text"][:120] for j in by_card.get(oid, []) if A[j]["state"] == "held_out"]
            if held:
                c["held"] = len(held)
        elif gid == 2:
            c["why"] = sorted({RARE_WORDS[A[j]["reason"]] for j in by_card.get(oid, []) if A[j]["reason"] in RARE_WORDS})
        elif gid == 3:
            cl = [h["clauses"][0] for (o, b, i), h in cd.items() if o == oid and h.get("clauses")]
            if cl:
                c["clause"] = sorted(cl)[0][:160]
        elif gid == 6:
            cr = corr_cards.get(oid)
            if cr:
                c["note"] = re.split(r"(?<=[.!?])\s", cr["issue"].strip())[0][:220]
        ucards[gid].append(c)
    groups = []
    for gid, name, explain in GROUPS:
        lst = sorted(ucards.get(gid, []), key=lambda c: (c["n"].lower(), c["c"]))
        if lst:
            groups.append({"id": gid, "name": name, "explain": explain, "cards": len(lst), "list": lst})

    # ---- totals and reconciliation
    vc = collections.Counter(v for v, _ in view.values())
    universe = len(view)
    in_scope = universe - vc["not_a_card"]
    headline = vc["placed"] + vc["keyword_block"] + vc["no_abilities"] + vc["replacement_group"]
    with_broad = headline + vc["broad_only"]
    card_leafcount = {oid: len({lid for _, lid, st in c["ab"] if lid and st == "p"}) for oid, c in cards.items()}
    pc = [n for oid, n in card_leafcount.items() if view[oid][0] == "placed"]
    checks = {
        "views_sum_to_universe": sum(vc.values()) == universe,
        "every_placed_card_has_a_placed_ability": all(card_leafcount.get(o, 0) >= 1 for o, v in view.items() if v[0] == "placed"),
        "no_unorganized_card_has_a_placed_ability": all(
            not any(st in ("p", "b") for _, _, st in cards[o]["ab"]) for o, v in view.items() if v[0] == "unorganized"),
        "broad_only_cards_have_no_placed_ability": all(
            not any(st == "p" for _, _, st in cards[o]["ab"]) and any(st == "b" for _, _, st in cards[o]["ab"])
            for o, v in view.items() if v[0] == "broad_only"),
        "leaf_memberships_match": sum(len(v) for lid, v in mem_out.items() if not leaves_out.get(lid, {}).get("flags")) ==
        sum(card_leafcount.values()),
        "one_state_per_ability_row": all(r[6] in ("placed", "placed_broad", "unplaced", "held_out") for r in rows_out),
        "groups_sum_to_unorganized": sum(g["cards"] for g in groups) == vc["unorganized"],
        "ability_rows_cover_old_ledger": len({(r[1], r[2], r[3]) for r in rows_out}) == len(AL["rows"]),
    }
    totals = {"universe": universe, "not_cards": vc["not_a_card"], "in_scope": in_scope,
              "views": dict(sorted(vc.items())),
              "headline": {"cards": headline, "pct": round(100.0 * headline / in_scope, 1),
                           "basis": "placed by an ability in an unflagged leaf of 5 or more, plus the keyword block, "
                                    "“No abilities” and the replacement groups, out of the {:,} in-scope cards".format(in_scope)},
              "with_broad": {"cards": with_broad, "pct": round(100.0 * with_broad / in_scope, 1),
                             "basis": "the headline plus the {:,} cards whose abilities sit only in groups broader than they look".format(
                                 vc["broad_only"])},
              "not_yet_organized": vc["unorganized"],
              "unorganized_by_group": {g["name"]: g["cards"] for g in groups},
              "leaves_per_placed_card": {"mean": round(sum(pc) / max(1, len(pc)), 3), "max": max(pc) if pc else 0},
              "archived_view": {"cards": 26085, "pct": 74.8,
                                "basis": "the archived card-level view (clustered, nearby, ability, keyword, no-abilities, replacement)"},
              "include_gap_cards": include_gap}
    ab_states = collections.Counter(r[6] for r in rows_out)
    ab_reasons = collections.Counter(r[7] for r in rows_out if r[6] != "placed")
    sizes = [li["n"] for li in leaf_info.values()]
    meta = {"rules": {"minimum": MIN, "display_threshold": SHOW, "backoff": "rarest field first, literal counts",
                      "population": "clean abilities on clean cards" + ("; gap-card abilities included" if include_gap else
                                                                         "; gap-card abilities measured and held out"),
                      "snapshot": SNAPSHOT, "source": "src/build_ability_taxonomy.py"},
            "leaves_all": len(leaf_info), "leaves_ge_min": len(leaves_out),
            "leaves_visible": sum(1 for v in leaves_out.values() if v["visible"] and not v["flags"]),
            "leaves_flagged": sum(1 for v in leaves_out.values() if v["flags"]),
            "leaves_flagged_visible": sum(1 for v in leaves_out.values() if v["flags"] and v["visible"]),
            "nodes": sum(len(f["nodes"]) for f in families), "families": len(families),
            "size_hist": {"%d-%d" % b: sum(1 for s in sizes if b[0] <= s <= b[1])
                          for b in [(1, 4), (5, 9), (10, 19), (20, 49), (50, 99), (100, 499), (500, 10 ** 6)]},
            "abilities_by_state": dict(sorted(ab_states.items())),
            "abilities_by_reason": dict(sorted(ab_reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
            "name_corrections": {"applied": {k: len(v) for k, v in used.items()}, "orphaned": orphans}}
    # sig and keyword blocks for the page
    blocks = {
        "keyword": {"name": "Keyword abilities", "branches": KL["branches"],
                    "leaves": {k: {"name": v["name"], "n": v["n_cards"], "cards": sorted({KL["faces"][f]["card"] for f in v["faces"]})}
                               for k, v in KL["leaves"].items()}},
        "replacement": {"name": SL["meta"].get("block", "Replacement effects and costs"), "branches": SL["branches"],
                        "leaves": {k: {"name": v["name"], "n": v["n_cards"], "coined": v.get("coined"), "basis": v.get("basis"),
                                       "cards": sorted({SL["faces"][f]["card"] for f in v["faces"]})} for k, v in SL["leaves"].items()}},
        "no_abilities": {"name": "No abilities", "cards": sorted(van_card)},
    }
    tax = {"v": 1, "meta": meta, "totals": totals, "checks": checks, "families": families, "leaves": leaves_out,
           "blocks": blocks, "flag_notes": FLAG_NOTE,
           "unorganized": [{k: g[k] for k in ("id", "name", "explain", "cards")} for g in groups]}
    dump("ability_taxonomy.json", tax)
    dump("ability_taxonomy_members.json", {"v": 1, "leaves": dict(sorted(mem_out.items()))})
    dump("ability_taxonomy_cards.json", {"v": 1, "cards": cards})
    dump("ability_taxonomy_unorganized.json", {"v": 1, "groups": groups})
    dump("ability_taxonomy_ledger.json", {
        "v": 1, "meta": dict(meta, totals=totals, checks=checks,
                             columns=["card", "face", "bucket", "idx", "mode", "text", "state", "reason", "leaf"]),
        "cards": {oid: {"name": L[oid]["name"], "status": L[oid]["status"], "view": v, "reason": rs,
                        "leaves": sorted({lid for _, lid, st in cards.get(oid, {"ab": []})["ab"] if lid and st == "p"}),
                        "broad": sorted({lid for _, lid, st in cards.get(oid, {"ab": []})["ab"] if lid and st == "b"})}
                  for oid, (v, rs) in sorted(view.items())},
        "rows": rows_out})
    # ---- lookup
    entries = []
    for e in old_lookup["entries"]:
        oid = e[0]
        v, rs = view[oid]
        if v == "not_a_card":
            entries.append([oid, e[1], e[2], "o", e[4], 0, e[6]])
            continue
        c = cards[oid]
        if v == "placed":
            code, extra = "l", sorted({lid for _, lid, st in c["ab"] if lid and st == "p"})
        elif v == "broad_only":
            code, extra = "b", sorted({lid for _, lid, st in c["ab"] if lid and st == "b"})
        elif v == "keyword_block":
            code, extra = "k", kw_card[oid]
        elif v == "replacement_group":
            code, extra = "g", sig_card[oid]
        elif v == "no_abilities":
            code, extra = "v", "No abilities"
        else:
            code, extra = "u", REASON_GROUP[rs]
        entries.append([oid, e[1], e[2], code, extra, e[5], e[6]])
    dump("ability_taxonomy_lookup.json", {"v": 1, "fold": old_lookup["fold"], "oos": old_lookup["oos"], "entries": entries})
    print(json.dumps({"totals": totals, "checks": checks,
                      "meta": {k: meta[k] for k in ("leaves_all", "leaves_ge_min", "leaves_visible", "leaves_flagged",
                                                    "leaves_flagged_visible", "nodes", "families", "size_hist",
                                                    "abilities_by_state", "abilities_by_reason", "name_corrections")}},
                     indent=1, ensure_ascii=False))
    # internals for the measurement scripts (src/probe_names_v2.py); writing nothing and changing no output
    return {"A": A, "leaf_info": leaf_info, "members": members, "nodes": nodes, "tax": tax, "rows": rows_out, "cards": cards,
            "view": view, "by_card": by_card, "L": L}


if __name__ == "__main__":
    main()
