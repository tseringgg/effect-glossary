#!/usr/bin/env python3
"""Signature-taxonomy PROBE 2 -- investigation only. Places nothing, changes nothing.

    python src/probe2_signature_taxonomy.py   # -> build/signature_probe2.json, build/signature_probe2_leaves.json

Revision of src/probe_signature_taxonomy.py (probe 1, kept untouched). Changes, in the order of the brief:

 1. NO LEVEL-1 LEAVES. An ability is placed only when a signature of >= MIN abilities exists at level 2 or finer,
    and that signature is not a bare effect type standing in for a richer ability. Otherwise it is unplaced,
    by reason: rare_effect_type | rare_verb_parameter | rare_object | no_signature.
    "Bare fallback" guard: an ability that has an object but no verb parameter (zone, counter type, player scope,
    granted modification) may not fall to the bare effect type; its floor is effect type + object.
    An ability whose COMPLETE signature is a bare effect type (Surveil, plain Draw) keeps it: that is its finest
    signature, not a fallback.
 2. EQUIPPED / ENCHANTED are part of the target type: obj = "Creature[equipped]" / "Creature[enchanted]"
    (Typed.properties EquippedBy / EnchantedBy; removed from the detail bag).
 3. BACKOFF DROPS THE RAREST FIELD FIRST ("RF"). Fields that may be dropped: obj, ctrl, quant, props, kw, dur,
    cond, wrap, chain, tok. Verb-bound fields (frm, to, ctr, who, mods) are never dropped. Rarity of a field
    value = how many abilities of the same effect type carry it; ties drop in a fixed priority (detail first).
    The count that decides is the number of abilities (of the whole population) that agree on every field
    still retained -- the literal reading of probe 1. The fixed-order version ("FO", probe 1 order C: L2 verb
    fields, L3 +obj, L4 +ctrl,quant, L5 +all detail) is computed under the same rules for comparison.
 4. GAP CARDS. A clean ability on a partial / unmodelled card is also excluded when build_partial_ability_layer's
    same_line_gap or continuation_gap test fires for it (plus the layer's no_text rule). Counts reported.
 5. GENERIC LEAVES. A leaf is flagged when a field that matters for its meaning is absent from the parse
    (flag_reasons()). Flagged leaves are kept out of the headline placement counts.

Levels (leaf level is a function of the retained fields): RF: 5 any detail field retained | 4 ctrl or quant
retained | 3 obj retained | 2 none (verb fields only, or bare). FO: the level whose signature matched.

Minimum sizes 3 and 5. Writes sorted-key JSON; identical bytes across runs.
"""
import collections
import io
import json
import os
import re
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "hdbscan" not in sys.modules:
    sys.modules["hdbscan"] = types.ModuleType("hdbscan")
import build_ledger as BL                       # noqa: E402
import build_partial_ability_layer as BPL       # noqa: E402  sq, fam, CONT only
import probe_signature_taxonomy as pst          # noqa: E402  helpers; probe 1 stays untouched

BUILD = pst.BUILD
MINS = (3, 5)
L2G = ("frm", "to", "ctr", "who", "mods")
DETAIL = ("props", "kw", "dur", "cond", "wrap", "chain", "tok")
DROPPABLE = ("obj", "ctrl", "quant") + DETAIL
DROP_PRIORITY = ["tok", "chain", "wrap", "cond", "dur", "kw", "props", "quant", "ctrl", "obj"]   # dropped first -> last
CANON = list(L2G) + ["obj", "ctrl", "quant", "props", "kw", "dur", "cond", "wrap", "chain", "tok"]
EMPTY = ("", "-")
FO_LEVELS = {2: L2G, 3: L2G + ("obj",), 4: L2G + ("obj", "ctrl", "quant"), 5: L2G + ("obj", "ctrl", "quant") + DETAIL}


def jl(name):
    return json.load(io.open(os.path.join(BUILD, name), encoding="utf-8"))


# ------------------------------------------------------------------ fields
def obj2(t, ex=None):
    """pst.obj_parts with equipped / enchanted folded into the object type."""
    o, ctrl, det, zones = pst.obj_parts(t, ex)
    att = []
    keep = []
    for d in det:
        if d.startswith("EquippedBy"):
            att.append("equipped")
        elif d.startswith("EnchantedBy"):
            att.append("enchanted")
        else:
            keep.append(d)
    if att and o not in ("-",):
        o = o + "[" + "+".join(sorted(set(att))) + "]"
    return o, ctrl, keep, zones


def fields2(x):
    b, it = x["b"], x["item"]
    blank = dict(fam="none", rtype="none", ftype="none", frm="", to="", ctr="", who="", mods="", obj="-", ctrl="-",
                 quant="-", props="", kw="", dur="", cond="", wrap="", chain="", tok="", usable=False)
    if b == "static_abilities":
        m = it.get("mode")
        mname = m if isinstance(m, str) else ",".join(sorted(m)) if isinstance(m, dict) else str(m)
        mods = sorted({md.get("type") for md in it.get("modifications") or [] if isinstance(md, dict)})
        kws = sorted({str(md.get("keyword")) for md in it.get("modifications") or []
                      if isinstance(md, dict) and md.get("type") == "AddKeyword"})
        o, ctrl, det, zones = obj2(it.get("affected"))
        if isinstance(m, dict):
            for v in m.values():
                if isinstance(v, dict) and isinstance(v.get("spell_filter"), dict):
                    o = o + "/spell:" + obj2(v["spell_filter"])[0]
        return dict(blank, fam=pst.static_family(mname), rtype="static:" + mname, ftype="static:" + mname,
                    frm=",".join(zones), mods=",".join(mods), obj=o, ctrl=ctrl, props="|".join(det),
                    kw="|".join(kws), cond="cond" if it.get("condition") else "", usable=True)
    ex, e = pst.exec_and_effect(b, it)
    if not isinstance(e, dict) or not isinstance(e.get("type"), str):
        if b == "replacements":
            o, ctrl, det, _ = obj2(it.get("valid_card"))
            scal = sorted("%s=%s" % (k, v) for k, v in it.items()
                          if isinstance(v, str) and k not in ("description", "event", "mode"))
            ev = str(it.get("event"))
            return dict(blank, fam="Replacement", rtype="repl:" + ev, ftype="repl:" + ev, obj=o, ctrl=ctrl,
                        props="|".join(det + scal), usable=True)
        return blank
    if e["type"] == "GenericEffect" and not e.get("static_abilities") and ex.get("mode_abilities"):
        modes = sorted({pst.step_verb(m) for m in ex["mode_abilities"] if isinstance(m, dict)})
        return dict(blank, fam="Choice / wrapper", rtype="Modal", ftype="Modal", wrap="Modal",
                    chain="modes:" + ">".join(modes), usable=True)
    ex, e, wraps, wrap_e = pst.head(ex, e)
    rt = e["type"]
    ft = rt[:-3] if rt.endswith("All") and rt != "ExploreAll" else rt
    if rt == "ExploreAll":
        ft = "Explore"
    t = pst.target_of(e)
    o, ctrl, det, zones = obj2(t, ex)
    if o in ("TrackedSet", "parent") and wrap_e and pst.target_of(wrap_e):
        o, ctrl, det, zones = obj2(pst.target_of(wrap_e), ex)
    frm = e.get("origin") or (zones[0] if zones else "")
    to = e.get("destination") or ""
    if rt in ("Bounce", "BounceAll"):
        to = "Hand"
    elif rt in ("PutAtLibraryPosition", "PutOnTopOrBottom"):
        to = "Library"
    steps = pst.chain_steps(ex)
    if rt in pst.SEARCHY and not to:
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
    elif o in pst.PLAYER_OBJ:
        who = o
    elif isinstance(e.get("player"), str):
        who = e["player"]
    else:
        who = ""
    if rt.endswith("All") or rt == "DamageEachPlayer":
        quant = "all"
    elif ex.get("repeat_for"):
        quant = "each"
    elif isinstance(ex.get("multi_target"), dict) and (ex["multi_target"].get("max") or 2) > 1:
        quant = "multi"
    elif o != "-":
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
    tok = ""
    if rt == "Token":
        tt = [str(v) for v in e.get("types") or []]
        o = "+".join(sorted(v for v in tt if v in pst.CORE_TYPES)) or "token"
        nm = e.get("name")
        tok = "|".join(["sub:" + v for v in sorted(v for v in tt if v not in pst.CORE_TYPES)] +
                       (["name:" + nm] if isinstance(nm, str) else []))
    if rt == "Mana":
        p = e.get("produced")
        o = (p.get("type") if isinstance(p, dict) else str(p)) or "mana"
    dur = e.get("duration") or ex.get("duration")
    return dict(fam=pst.FAMILY.get(rt, "Other"), rtype=rt, ftype=ft, frm=frm, to=to, ctr=ctr, who=who,
                mods=",".join(sorted(set(m for m in mods if m))), obj=o, ctrl=ctrl, quant=quant,
                props="|".join(det), kw="|".join(sorted(set(kws))), dur=dur if isinstance(dur, str) else "",
                cond="cond" if ex.get("condition") else "", wrap=">".join(wraps),
                chain=(">".join(pst.step_verb(s) for s in steps[:3]) + ("+" if len(steps) > 3 else "")) if steps else "",
                tok=tok, usable=True)


def val(f, k):
    v = f[k]
    return "" if v in EMPTY else v


def sigstr(f, retained):
    return " · ".join(["fam=%s" % f["fam"], "ftype=%s" % f["ftype"]] +
                      ["%s=%s" % (k, f[k]) for k in CANON if k in retained and f[k] not in EMPTY])


def level_of(f, retained):
    if any(k in retained and f[k] not in EMPTY for k in DETAIL):
        return 5
    if any(k in retained and f[k] not in EMPTY for k in ("ctrl", "quant")):
        return 4
    if "obj" in retained and f["obj"] not in EMPTY:
        return 3
    return 2


# ------------------------------------------------------------------ generic flags
def flag_reasons(ftype, ret):
    """ret: the leaf's retained non-empty fields (dict). Reasons the leaf cannot be trusted to mean what it says."""
    out = []
    if ftype == "Draw" and "who" not in ret:
        out.append("who draws is not in the parse")
    if ftype == "Bounce":
        out.append("'all' vs 'target' is not recorded on return-to-hand")
    if ftype in ("ChangeZone", "Bounce") and ret.get("obj") == "self" and "frm" not in ret:
        out.append("source zone of a self-return is not in the parse")
    if ftype == "GenericEffect" and "mods" not in ret:
        out.append("grant with no parsed modification")
    o = ret.get("obj")
    if o in ("parent", "TrackedSet") or (o == "any target" and ftype != "DealDamage"):
        out.append("object unresolved by the parser")
    return out


# ------------------------------------------------------------------ gap-card tests
def gap_tests(items):
    """Apply the partial layer's same_line / continuation / no_text tests to clean abilities on gap cards."""
    rows = jl("index.json")["rows"]
    byid = {r["id"]: r for r in rows}
    chunks = {n: jl("chunks/%d.json" % n) for n in range(64)}
    rec = jl("placements.json")["recovered"]["chunk"]
    cache = {}

    def face_info(face):
        if face not in cache:
            e = chunks[byid[face]["ch"]][face] if face in byid else rec[face]
            lines = [BPL.sq(re.sub(r"\([^)]*\)", "", ln)) for ln in (e.get("oracle_text") or "").split("\n")]
            frags = BL.gap_fragments(e, e.get("name") or "")
            fsq = [(BPL.fam(k, c), BPL.sq(t)) for k, c, t in frags]
            cont = any(f.startswith("Unimplemented:") and f.split(":", 1)[1] in BPL.CONT for f, _ in fsq)
            cache[face] = (lines, fsq, cont)
        return cache[face]
    keep, excl = [], collections.Counter()
    for x in items:
        if x["kind"] != "gap":
            keep.append(x)
            continue
        lines, fsq, cont = face_info(x["face"])
        text = (x["item"].get("description") or "").strip()
        if not text or re.fullmatch(r"Chapter \d+", text):
            excl["no_text"] += 1
            continue
        d = BPL.sq(text)
        mine = [ln for ln in lines if ln and (d[:40] in ln or ln in d)]
        if any(t and any((t[:25] in ln) or (ln[:25] in t) for ln in mine) for _, t in fsq):
            excl["same_line_gap"] += 1
            continue
        if cont:
            excl["continuation_gap"] += 1
            continue
        keep.append(x)
    return keep, excl


# ------------------------------------------------------------------ backoff
def assign_fo(F, mn):
    cnt = {lv: collections.Counter(tuple(val(f, k) for k in ("ftype",) + flds) for f in F if f["usable"])
           for lv, flds in FO_LEVELS.items()}
    out = []
    for f in F:
        if not f["usable"]:
            out.append(("x", "no_signature"))
            continue
        l2_empty = not any(val(f, k) for k in L2G)
        has_obj = val(f, "obj") != ""
        res = None
        for lv in (5, 4, 3, 2):
            if cnt[lv][tuple(val(f, k) for k in ("ftype",) + FO_LEVELS[lv])] >= mn:
                if lv == 2 and l2_empty and has_obj:
                    res = ("x", "rare_object")           # would fall to the bare effect type
                else:
                    res = (lv, sigstr(f, FO_LEVELS[lv]))
                break
        if res is None:
            res = ("x", "rare_verb_parameter" if not l2_empty else ("rare_object" if has_obj else "rare_effect_type"))
        out.append(res)
    return out


def assign_rf(F, mn):
    rar = collections.Counter()
    for f in F:
        if f["usable"]:
            for k in DROPPABLE:
                rar[(f["ftype"], k, val(f, k))] += 1
    counters = {}

    def count(D):
        if D not in counters:
            keep = [k for k in CANON if k not in D]
            counters[D] = collections.Counter(
                tuple(val(f, k) for k in ["ftype"] + keep) for f in F if f["usable"])
        return counters[D]
    out = []
    for f in F:
        if not f["usable"]:
            out.append(("x", "no_signature"))
            continue
        l2_empty = not any(val(f, k) for k in L2G)
        has_obj = val(f, "obj") != ""
        D = frozenset()
        S = [k for k in DROPPABLE if val(f, k)]
        placed = None
        while True:
            Dk = tuple(sorted(D))
            keep = [k for k in CANON if k not in D]
            if count(Dk)[tuple(val(f, k) for k in ["ftype"] + keep)] >= mn:
                placed = (level_of(f, keep), sigstr(f, set(keep)))
                break
            cand = [k for k in S if k not in D and not (k == "obj" and l2_empty and has_obj)]
            if not cand:
                break
            drop = min(cand, key=lambda k: (rar[(f["ftype"], k, val(f, k))], DROP_PRIORITY.index(k)))
            D = D | {drop}
        out.append(placed or ("x", "rare_verb_parameter" if not l2_empty else ("rare_object" if has_obj else "rare_effect_type")))
    return out


def main():
    items, excl, AL = pst.population()
    items, gexcl = gap_tests(items)
    F = []
    for x in items:
        F.append(fields2(x))
    out = {"v": 1, "population": {
        "abilities": len(items), "cards": len({x["oid"] for x in items}),
        "by_kind": dict(collections.Counter(x["kind"] for x in items)),
        "probe1_exclusions": dict(sorted(excl.items())), "new_gap_exclusions": dict(sorted(gexcl.items())),
        "usable": sum(f["usable"] for f in F), "unusable": sum(not f["usable"] for f in F)}}
    asg = {}
    for mn in MINS:
        asg["FO%d" % mn] = assign_fo(F, mn)
        asg["RF%d" % mn] = assign_rf(F, mn)
    # per-variant leaf tables
    res = {}
    for key, a in asg.items():
        mn = int(key[2:])
        leaf = collections.defaultdict(list)
        rep = {}
        for j, r in enumerate(a):
            if r[0] != "x":
                leaf[r].append(j)
                rep.setdefault(r, j)
        flags = {}
        for lf, j in rep.items():
            f = F[j]
            ret = dict(part.split("=", 1) for part in lf[1].split(" · ")[2:])
            fl = flag_reasons(f["ftype"], ret)
            if fl:
                flags[lf] = fl
        reasons = collections.Counter(r[1] for r in a if r[0] == "x")
        sizes = sorted((len(v) for v in leaf.values()), reverse=True)
        by_lvl = collections.Counter(lf[0] for lf in leaf)
        ab_lvl = collections.Counter(r[0] for r in a if r[0] != "x")
        direct5 = sum(len(v) for v in leaf.values() if len(v) >= 5)
        res[key] = {
            "leaves": len(leaf), "leaves_by_level": dict(sorted(by_lvl.items())),
            "abilities_assigned": sum(len(v) for v in leaf.values()), "abilities_by_level": dict(sorted(ab_lvl.items())),
            "unplaced_by_reason": dict(sorted(reasons.items())),
            "leaves_flagged_generic": len(flags), "abilities_in_flagged": sum(len(leaf[lf]) for lf in flags),
            "flag_reason_leaves": dict(collections.Counter(r for fl in flags.values() for r in fl)),
            "flag_reason_abilities": dict(collections.Counter(
                r for lf, fl in flags.items() for r in fl for _ in range(len(leaf[lf])))),
            "leaves_direct_lt_min": sum(1 for v in leaf.values() if len(v) < mn),
            "abilities_in_direct_lt_min": sum(len(v) for v in leaf.values() if len(v) < mn),
            "abilities_in_leaves_ge5_direct": direct5,
            "size_hist": {"%d-%d" % b: sum(1 for s in sizes if b[0] <= s <= b[1])
                          for b in [(1, 2), (3, 4), (5, 9), (10, 19), (20, 49), (50, 99), (100, 499), (500, 10 ** 6)]},
            "abilities_in_size": {"%d-%d" % b: sum(s for s in sizes if b[0] <= s <= b[1])
                                  for b in [(1, 4), (5, 9), (10, 49), (50, 10 ** 6)]},
            "median_size": sizes[len(sizes) // 2] if sizes else 0,
            "largest": [{"level": lf[0], "sig": lf[1], "n": len(v), "flags": flags.get(lf, [])}
                        for lf, v in sorted(leaf.items(), key=lambda kv: -len(kv[1]))[:20]],
        }
    out["variants"] = res
    with io.open(os.path.join(BUILD, "signature_probe2.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=1))
    rows = []
    for j, x in enumerate(items):
        f = F[j]
        rows.append({"oid": x["oid"], "face": x["face"], "b": x["b"], "i": x["i"], "name": x["name"],
                     "text": x["text"], "kind": x["kind"], "status": x["status"], "state": x["state"],
                     "route": x["route"], "leaf": x["leaf"], "reason": x["reason"], "best": x["best"],
                     "score": x["score"], "cleaf": x["cleaf"], "method": x["method"],
                     "f": {k: v for k, v in f.items() if k != "usable"},
                     "a": {k: list(v[j]) for k, v in asg.items()}})
    with io.open(os.path.join(BUILD, "signature_probe2_leaves.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"v": 1, "rows": rows}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    print(json.dumps(out["population"], indent=1))
    for k, v in res.items():
        print(k, {kk: v[kk] for kk in ("leaves", "leaves_by_level", "abilities_assigned", "abilities_by_level",
                                         "unplaced_by_reason", "leaves_flagged_generic", "abilities_in_flagged",
                                         "median_size")})


if __name__ == "__main__":
    main()
