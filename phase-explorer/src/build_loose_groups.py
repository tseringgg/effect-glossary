#!/usr/bin/env python3
"""The "Loosely grouped" browse layer for the Not-yet-organized pile, and the "Cards we couldn't read yet" list.

    python src/build_loose_groups.py        # -> build/loose_groups.json, build/loose_unread.json   (run after build_ability_taxonomy.py)

This is a BROWSE aid, not a placement. Nothing it writes is read by the taxonomy build, the leaves, the headline or the reconciliation: every pile card is still
counted once as "Not yet organized", however many loose groups hold it. It reads the same build (re-run in memory, nothing written) and groups the abilities of the
pile cards by fields already in the parse (family, effect type, a few fields per family; see FIELDS in probe_loose_groups_v2.py, which holds the field logic). No text
matching, no tag data, no parser change.

Rules (decided in review, 2026-10):
  * a card appears under every loose group one of its abilities fits (abilities of the pile cards only, including abilities held back for a dropped condition or an
    unread part, and gap-card abilities that failed the tests); each card row says why that ability is not a real placement;
  * a group of fewer than 10 cards backs off to a shorter key; a group over 50 cards is split once more by the refine fields (probe_loose_groups_v2.REFINE);
  * effect types with fewer than 10 cards in all go into one plainly named bucket per family ("Less common effects, by kind") with the effect types as sub-headings;
    sub-headings under 3 cards fold into "Other kinds". The two groups still over 100 cards are labeled catch-alls with sub-headings; sub-headings are not groups;
  * cards of the pile with no usable ability go to the separate "couldn't read yet" list, sorted by popularity, with the reason shown on each row.
"""
import collections
import contextlib
import gzip
import hashlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_loose_groups as P
import probe_loose_groups_v2 as V

HERE = P.HERE
BUILD = P.BUILD
DATA = P.DATA
LABEL = "Loosely grouped by effect. Not checked for accuracy."
SUB_MIN = 3

CATCH_ALL_NOTE = {
    "bucket": "Effect types that have fewer than 10 cards each in this family. They are listed by kind below; each kind is a heading, not a checked group.",
    "catchall": "A catch-all: the parse did not say enough to split these further without making groups of a few cards. The kinds below are headings only.",
}


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def collect():
    """the build, re-run in memory (nothing is written), then the abilities of the pile cards with their parsed effect and where they came from."""
    import build_ability_taxonomy as B
    import analyze_unorganized_breakdown_v3 as V3
    import probe_signature_taxonomy as pst
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

    def raw_of(b, it):
        try:
            e0, e = pst.exec_and_effect(b, it)
            if not isinstance(e, dict):
                return None
            return pst.head(e0, e)[1]
        except Exception:
            return None

    def mode_of(it):
        return it.get("mode") if isinstance(it, dict) else None
    items, raw, info = [], [], []
    for a in A:
        if a["oid"] in pset and not a["pre"]:
            items.append({"oid": a["oid"], "text": a["text"], "src": "A", "reason": a["reason"], "f": {k: a["f"][k] for k in P.KEEP}, "ref": [a["face"], a["b"], a["i"], a["mode"]]})
            ok = a.get("b") in ("abilities", "triggers", "replacements") and a.get("item") is not None
            raw.append(raw_of(a["b"], a["item"]) if ok else None)
            info.append((a.get("b"), mode_of(a.get("item"))))
    for x in ex:
        items.append({"oid": x["oid"], "text": x["text"] or "", "src": x["why"], "reason": x["test"] if x["why"] == "test_fail" else x["why"], "f": {k: x["f"][k] for k in P.KEEP}, "ref": [x["face"], x["b"], x["i"], None]})
        raw.append(raw_of(x["b"], x["item"]))
        info.append((x.get("b"), mode_of(x.get("item"))))
    meta = {"pile": pile, "view_reason": {o: view[o][1] for o in pile}, "names": {o: L[o]["name"] for o in pile}, "card_text": {o: S["cards"][o]["t"] for o in pile if o in S["cards"]},
            "totals": S["tax"]["totals"], "families": [(f["key"], f["name"]) for f in S["tax"]["families"]]}
    return items, raw, info, meta


def popularity():
    rank = {}
    with gzip.open(os.path.join(DATA, "scryfall-oracle-cards.jsonl.gz"), "rt", encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            if o.get("edhrec_rank") is not None:
                rank[o["oracle_id"]] = o["edhrec_rank"]
    return rank


def band(n):
    return "under 10" if n < 10 else "10-50" if n <= 50 else "51-100" if n <= 100 else "over 100"


def gid_of(k):
    return ("o-" + re.sub(r"[^a-z]+", "-", k[0].lower()).strip("-")) if k[2] == "OTHER" else "g" + hashlib.sha1(json.dumps([k[0], k[1], k[2], k[3]], sort_keys=True).encode()).hexdigest()[:8]


def make_groups(items, raw, info, fam_keys):
    """the loose groups: (use_idx, keys, folded {key: cards}, fm {key: ability indexes}, names, sizes, kind_of). Used by the build and by the tentative layer."""
    use_idx = [n for n, i in enumerate(items) if i["f"]["usable"] and i["f"]["fam"] in fam_keys]
    keys = V.build_keys(use_idx, items, info, raw)
    L3 = collections.defaultdict(set)
    members = collections.defaultdict(list)
    for n, k in zip(use_idx, keys):
        L3[k].add(items[n]["oid"])
        members[k].append(n)
    # fold: effect types too small for a group of their own go to one bucket per family
    folded = collections.defaultdict(set)
    fm = collections.defaultdict(list)
    for k, v in L3.items():
        tgt = k if len(v) >= V.MINGROUP else (k[0], "ALL", "OTHER")
        folded[tgt] |= v
        fm[tgt] += members[k]
    sizes = {k: len(v) for k, v in folded.items()}
    names = {}
    for k in folded:
        names[k] = (k[0] + " › Less common effects, by kind") if k[2] == "OTHER" else V.loose_name(k)
    dup = collections.Counter(names.values())
    assert max(dup.values()) == 1, [n for n, c in dup.items() if c > 1]

    def kind_of(k):
        return "bucket" if k[2] == "OTHER" else "catchall" if sizes[k] > 100 else "group"
    return use_idx, keys, folded, fm, names, sizes, kind_of


def main():
    items, raw, info, meta = collect()
    rank = popularity()
    fam_name = dict(meta["families"])
    fam_keys = set(fam_name)
    pile = meta["pile"]
    unorg = jl("ability_taxonomy_unorganized.json")["groups"]
    cause = {g["id"]: g for g in unorg}
    frag, pile_group = {}, {}
    for g in unorg:
        for c in g["list"]:
            pile_group[c["c"]] = g["id"]
            if c.get("g"):
                frag[c["c"]] = "; ".join(x[1] for x in c["g"])
    assert sorted(c["c"] for g in unorg for c in g["list"]) == pile, "the pile in the build differs from the pile in the unorganized file"
    use_idx, keys, folded, fm, names, sizes, kind_of = make_groups(items, raw, info, fam_keys)
    reasons = []

    def ridx(code):
        t = P.REASONS.get(code, "it is held back for a reason the tool does not describe yet")
        if t not in reasons:
            reasons.append(t)
        return reasons.index(t)

    def sublabel(k, n):
        if k[2] == "OTHER":
            return V.effect_word(items[n]["f"]["ftype"])
        v = V.field_values(items[n]["f"], n, info, raw)
        if k[1] == "Destroy":
            return v["objc2"] or "something"
        g = v["grant"]
        return V.CONT_WORDS.get(g, ("gives " + V.KWFIX.get(g.replace("keyword ", ""), g.replace("keyword ", ""))) if g.startswith("keyword") else (g or "affects it"))

    def pop(o):
        return rank.get(o, 10 ** 9)
    groups, by_card = {}, collections.defaultdict(list)
    order = sorted(folded, key=lambda k: (-sizes[k], names[k]))
    for k in order:
        kind = kind_of(k)
        gid = gid_of(k)
        subs = None
        mem_by = collections.defaultdict(list)
        if kind != "group":
            lab = {n: sublabel(k, n) for n in fm[k]}
            cnt = collections.defaultdict(set)
            for n, l in lab.items():
                cnt[l].add(items[n]["oid"])
            small = {l for l, c in cnt.items() if len(c) < SUB_MIN}
            fix = {n: ("Other kinds" if l in small else l) for n, l in lab.items()}
            cnt2 = collections.defaultdict(set)
            for n, l in fix.items():
                cnt2[l].add(items[n]["oid"])
            sl = sorted((l for l in cnt2 if l != "Other kinds"), key=lambda l: (min(pop(o) for o in cnt2[l]), -len(cnt2[l]), l))
            if "Other kinds" in cnt2:
                sl.append("Other kinds")
            subs = [{"name": l, "cards": len(cnt2[l])} for l in sl]
            sidx = {l: i for i, l in enumerate(sl)}
            for n in fm[k]:
                mem_by[items[n]["oid"]].append((n, sidx[fix[n]]))
        else:
            for n in fm[k]:
                mem_by[items[n]["oid"]].append((n, 0))
        rows_ = []
        for oid, lst in mem_by.items():
            lst.sort(key=lambda t: (t[1], items[t[0]]["text"]))
            n0, s0 = lst[0]
            rows_.append([oid, " ".join((items[n0]["text"] or "").split())[:240], ridx(items[n0]["reason"]), s0, len(lst) - 1])
        rows_.sort(key=lambda r: (r[3], pop(r[0]), meta["names"][r[0]]))
        groups[gid] = {"name": names[k], "short": names[k].split(" › ", 1)[1], "fam": k[0], "kind": kind, "cards": sizes[k], "m": rows_}
        if subs:
            groups[gid]["subs"] = subs
            groups[gid]["note"] = CATCH_ALL_NOTE[kind]
        for oid in mem_by:
            by_card[oid].append(gid)
    fams = []
    for key, nm in meta["families"]:
        gids = [g for g, v in groups.items() if v["fam"] == key]
        if not gids:
            continue
        gids.sort(key=lambda g: ({"group": 0, "catchall": 1, "bucket": 2}[groups[g]["kind"]], -groups[g]["cards"], groups[g]["name"]))
        fams.append({"key": key, "name": nm, "cards": len({m[0] for g in gids for m in groups[g]["m"]}), "groups": gids})
    for oid in by_card:
        by_card[oid].sort(key=lambda g: (groups[g]["cards"], g))
    cards_in = set(by_card)
    nohome = [o for o in pile if o not in cards_in]
    assert len(cards_in) + len(nohome) == len(pile) == meta["totals"]["not_yet_organized"]
    sz = [v["cards"] for v in groups.values()]
    out = {
        "meta": {"label": LABEL, "pile": len(pile), "cards_with_a_group": len(cards_in), "cards_not_read": len(nohome), "groups": len(groups),
                 "size_bands": dict(collections.Counter(band(n) for n in sz)),
                 "in_a_group_of_100_or_fewer": sum(1 for o in cards_in if any(groups[g]["cards"] <= 100 for g in by_card[o])),
                 "only_in_groups_over_100": sum(1 for o in cards_in if all(groups[g]["cards"] > 100 for g in by_card[o])),
                 "in_a_group_of_50_or_fewer": sum(1 for o in cards_in if any(groups[g]["cards"] <= 50 for g in by_card[o])),
                 "avg_groups_per_card": round(sum(len(v) for v in by_card.values()) / len(by_card), 2), "max_groups_per_card": max(len(v) for v in by_card.values()),
                 "abilities_used": len(use_idx), "reasons": reasons, "not_counted": "No card here counts toward the headline or the reconciliation: each is still counted once as Not yet organized.",
                 "rules": {"fields": V.FIELDS, "refine": V.REFINE, "refine_over_cards": V.REFINE_OVER, "min_group_cards": V.MINGROUP, "sub_heading_min_cards": SUB_MIN}},
        "families": fams, "groups": groups, "by_card": {o: by_card[o] for o in sorted(by_card)},
    }
    causes = {str(i): {"name": cause[i]["name"], "explain": cause[i]["explain"]} for i in sorted(cause)}
    unread = []
    for o in nohome:
        unread.append([o, rank.get(o), pile_group[o], frag.get(o, "")[:300]])
    unread.sort(key=lambda r: (r[1] is None, r[1] or 0, meta["names"][r[0]]))
    out_unread = {"label": "Cards we couldn't read yet", "cards": len(unread), "in_top_3000": sum(1 for r in unread if r[1] is not None and r[1] <= 3000), "causes": causes, "rows": unread}
    for fn, doc in (("loose_groups.json", out), ("loose_unread.json", out_unread)):
        with io.open(os.path.join(BUILD, fn), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(doc, ensure_ascii=False, indent=None, sort_keys=True, separators=(",", ":")))
    print(json.dumps({k: v for k, v in out["meta"].items() if k not in ("rules", "reasons")}, indent=1))
    print("unread:", out_unread["cards"], "in top 3000:", out_unread["in_top_3000"], "reasons:", len(reasons))


if __name__ == "__main__":
    main()
