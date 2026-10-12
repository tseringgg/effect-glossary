#!/usr/bin/env python3
"""The tentative layer: loose groups promoted to TENTATIVE placements, shown beside the main groups, never counted as organized.

    python src/build_tentative.py        # -> build/tentative_placements.json, build/tentative_ledger.json   (run after build_loose_groups.py's inputs exist; about a minute)

Method name in the data: `loose_tentative` (`min3_tentative` is reserved and not built). Nothing here is read by the taxonomy build, the leaves, the loose layer, the headline or the
reconciliation: every promoted card is still a "Not yet organized" card in the build; the page subtracts it from the pile count and shows a third figure.

Rules (decided in review, 2026-10):
  * candidates are the plain loose groups, plus the qualifying SUB-HEADINGS of the catch-all groups and the "Less common effects" buckets (each promoted sub-heading becomes a tentative
    group of its own; the catch-alls and the buckets themselves are never promoted);
  * an ability is eligible only if it is not held for a dropped condition, has ability text, and is not a gap-test failure (HOLD_GAP_TEST_FAILURES);
    abilities with an unread part stay eligible and say so on their row (HOLD_UNREAD_PART_ABILITIES = True would turn them off alone);
  * a group is promoted only if its hand read (corrections/tentative_groups.json) is coherent or loose, its name states the effect, it has at least MIN_ELIGIBLE_CARDS eligible cards, at most
    half of its cards are without any ability text, and it is not both loose and a backoff residual (HOLD_LOOSE_RESIDUALS);
  * a card is tentative if one of its eligible abilities is in a promoted group; it appears under every promoted group one of its eligible abilities fits, and is counted once.
TENTATIVE_LAYER = False writes an empty layer. PROMOTE_RENAMED_GROUPS and PROMOTE_SUBHEADINGS (the 2026-10 promotions) can each be turned off alone.
"""
import collections
import hashlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_loose_groups as BL
import probe_loose_groups as P
import probe_loose_groups_v2 as V

HERE = BL.HERE
BUILD = BL.BUILD
TENTATIVE_LAYER = True
MIN_ELIGIBLE_CARDS = 5
HOLD_TEXTLESS_OVER = 0.5
HOLD_GAP_TEST_FAILURES = True
HOLD_LOOSE_RESIDUALS = True
HOLD_UNREAD_PART_ABILITIES = False      # True: abilities with an unread part are not eligible (the unread-part stratum off, alone). Default unchanged.
PROMOTE_RENAMED_GROUPS = True           # the groups that were held only for their name
PROMOTE_SUBHEADINGS = True              # sub-headings of the catch-alls and buckets, each as a tentative group of its own
LABEL = "Tentative placement: grouped by effect type, not fully checked."
METHOD = "loose_tentative"


def has_text(it):
    return bool((it["text"] or "").strip()) and it["reason"] != "gap_card_no_text"


def eligible(it, hold_gap_tests, hold_unread=False):
    if it["src"] == "flagged" or not has_text(it):
        return False
    if hold_gap_tests and it["src"] == "test_fail":
        return False
    if hold_unread and it["src"] == "item_gap":
        return False
    return True


def subgroups(items, raw, info, folded, fm, kind_of):
    """{(parent gid, sub-heading label): [ability indexes]} exactly as the loose build builds its sub-headings (labels under 3 cards fold into 'Other kinds')."""
    out = {}
    for k in folded:
        if kind_of(k) == "group":
            continue
        lab = {}
        for n in fm[k]:
            if k[2] == "OTHER":
                lab[n] = V.effect_word(items[n]["f"]["ftype"])
            else:
                v = V.field_values(items[n]["f"], n, info, raw)
                if k[1] == "Destroy":
                    lab[n] = v["objc2"] or "something"
                else:
                    g = v["grant"]
                    lab[n] = V.CONT_WORDS.get(g, ("gives " + V.KWFIX.get(g.replace("keyword ", ""), g.replace("keyword ", ""))) if g.startswith("keyword") else (g or "affects it"))
        cnt = collections.defaultdict(set)
        for n, l in lab.items():
            cnt[l].add(items[n]["oid"])
        small = {l for l, c in cnt.items() if len(c) < BL.SUB_MIN}
        for n in lab:
            if lab[n] in small:
                lab[n] = "Other kinds"
        for n, l in lab.items():
            out.setdefault((BL.gid_of(k), l), []).append(n)
    return out


def sub_group_name(family, label):
    """the tentative group's name for a promoted sub-heading: fixed wording per sub-heading."""
    if family == "Static: continuous":
        return "Continuous effect on other kinds of target: " + label
    if family == "Destroy":
        return "Destroy a " + label
    return label


def sub_gid(parent, label):
    return "s" + hashlib.sha1((parent + "::" + label).encode("utf-8")).hexdigest()[:8]


def evaluate(cand, items, review, flags, gap=None):
    """-> {gid: (set of tentative cards, why-not or '')} for every candidate group under the given flags (a dict: residual, gap, unread, renamed, subs).
    The older call evaluate(cand, items, review, residual, gap) is still understood."""
    if not isinstance(flags, dict):
        flags = dict(residual=flags, gap=gap, unread=False, renamed=True, subs=True)
    out = {}
    for gid, g in cand.items():
        rev = review.get(gid)
        if rev is None:
            out[gid] = (set(), "not reviewed")
            continue
        if g.get("kind") == "renamed" and not flags["renamed"]:
            out[gid] = (set(), "the renamed-group promotions are switched off")
            continue
        if g.get("kind") == "sub" and not flags["subs"]:
            out[gid] = (set(), "the sub-heading promotions are switched off")
            continue
        if rev["verdict"] == "incoherent":
            out[gid] = (set(), "mixed or unreadable members")
            continue
        if not rev["key_states_effect"]:
            out[gid] = (set(), "the name does not state the effect")
            continue
        if flags["residual"] and g["residual"] and rev["verdict"] == "loose":
            out[gid] = (set(), "loose and a backoff residual")
            continue
        cards = {items[n]["oid"] for n in g["n"]}
        withtext = {items[n]["oid"] for n in g["n"] if has_text(items[n])}
        if (len(cards) - len(withtext)) > HOLD_TEXTLESS_OVER * len(cards):
            out[gid] = (set(), "most members have no ability text")
            continue
        el = {items[n]["oid"] for n in g["n"] if eligible(items[n], flags["gap"], flags["unread"])}
        if len(el) < MIN_ELIGIBLE_CARDS:
            out[gid] = (set(), "fewer than %d eligible cards" % MIN_ELIGIBLE_CARDS)
            continue
        out[gid] = (el, "")
    return out


def cards_of(ev):
    cs = set()
    for el, _ in ev.values():
        cs |= el
    return cs


def main():
    items, raw, info, meta = BL.collect()
    fam_keys = {k for k, _ in meta["families"]}
    use_idx, keys, folded, fm, names, sizes, kind_of = BL.make_groups(items, raw, info, fam_keys)
    rv = json.load(io.open(os.path.join(os.path.dirname(BUILD), "corrections", "tentative_groups.json"), encoding="utf-8"))
    review = dict(rv["groups"])
    rank = BL.popularity()
    t = json.load(io.open(os.path.join(BUILD, "ability_taxonomy.json"), encoding="utf-8"))["totals"]
    cand = {}
    for k in folded:
        if kind_of(k) != "group":
            continue
        nf, kept = k[3]
        gid = BL.gid_of(k)
        cand[gid] = {"key": k, "n": fm[k], "residual": kept < nf, "name": names[k], "kind": "renamed" if review.get(gid, {}).get("renamed") else "plain", "origin": "renamed group" if review.get(gid, {}).get("renamed") else "plain group"}
    taken = set(names.values())
    sg = subgroups(items, raw, info, folded, fm, kind_of)
    gk = {BL.gid_of(k): k for k in folded}
    for key_, rec in sorted(rv.get("subheadings", {}).items()):
        parent, label = key_.split("::", 1)
        if (parent, label) not in sg:
            raise SystemExit("a reviewed sub-heading no longer exists: %s" % key_)
        k = gk[parent]
        nm = k[0] + " › " + sub_group_name(k[0], label)
        if nm in taken:
            nm += ", uncommon cases"
        assert nm not in taken, nm
        taken.add(nm)
        gid = sub_gid(parent, label)
        cand[gid] = {"key": k, "n": sg[(parent, label)], "residual": False, "name": nm, "kind": "sub", "origin": "sub-heading of: " + names[k].split(" › ", 1)[1]}
        review[gid] = {"verdict": rec["verdict"], "key_states_effect": rec["key_states_effect"]}
    base = dict(residual=HOLD_LOOSE_RESIDUALS, gap=HOLD_GAP_TEST_FAILURES, unread=HOLD_UNREAD_PART_ABILITIES, renamed=PROMOTE_RENAMED_GROUPS, subs=PROMOTE_SUBHEADINGS)
    scen = {}

    def run(**kw):
        f_ = dict(base, **kw)
        e_ = evaluate(cand, items, review, f_)
        return e_, cards_of(e_)
    ev0, c0 = run(renamed=False, subs=False)
    ev1, c1 = run(subs=False)
    ev2, c2 = run(renamed=False)
    ev3, c3 = run()
    ev4, c4 = run(unread=True)
    ev5, c5 = run(renamed=False, subs=False, unread=True)
    scen = {"before the 2026-10 promotions": {"groups": sum(1 for el, _ in ev0.values() if el), "cards": len(c0)},
            "+ renamed groups only": {"groups": sum(1 for el, _ in ev1.values() if el), "cards": len(c1)},
            "+ sub-headings only": {"groups": sum(1 for el, _ in ev2.values() if el), "cards": len(c2)},
            "all (the build)": {"groups": sum(1 for el, _ in ev3.values() if el), "cards": len(c3)},
            "unread-part abilities off, all promotions": {"groups": sum(1 for el, _ in ev4.values() if el), "cards": len(c4)},
            "unread-part abilities off, before the 2026-10 promotions": {"groups": sum(1 for el, _ in ev5.values() if el), "cards": len(c5)}}
    ev = ev3
    if not TENTATIVE_LAYER:
        ev = {gid: (set(), "layer switched off") for gid in cand}
    pile = meta["pile"]
    reasons = []

    def ridx(code):
        txt = P.REASONS.get(code, "it is held back for a reason the tool does not describe yet")
        if txt not in reasons:
            reasons.append(txt)
        return reasons.index(txt)

    def pop(o):
        return rank.get(o, 10 ** 9)
    groups, by_card, ledger = {}, collections.defaultdict(list), []
    held = collections.Counter()
    for gid in sorted(cand, key=lambda g: (-len(ev[g][0]), cand[g]["name"])):
        el, why = ev[gid]
        if not el:
            held[why] += 1
            continue
        g = cand[gid]
        mem = collections.defaultdict(list)
        for n in g["n"]:
            it = items[n]
            if it["oid"] in el and eligible(it, HOLD_GAP_TEST_FAILURES, HOLD_UNREAD_PART_ABILITIES):
                mem[it["oid"]].append(n)
        rows = []
        for oid, ns in mem.items():
            ns.sort(key=lambda n: (items[n]["src"] != "A", items[n]["text"]))
            n0 = ns[0]
            rows.append([oid, " ".join((items[n0]["text"] or "").split())[:240], ridx(items[n0]["reason"]), len(ns) - 1])
            for n in ns:
                it = items[n]
                ledger.append([oid, it["ref"][0], it["ref"][1], it["ref"][2], " ".join((it["text"] or "").split())[:240], gid, METHOD, "rare shape" if it["src"] == "A" else "unread part"])
        rows.sort(key=lambda r: (pop(r[0]), meta["names"][r[0]]))
        short = g["name"].split(" › ", 1)[1]
        groups[gid] = {"name": g["name"], "short": short, "fam": g["key"][0], "cards": len(el), "loose_cards": len({items[n]["oid"] for n in g["n"]}), "origin": g["origin"], "m": rows}
        for oid in mem:
            by_card[oid].append(gid)
    fams = []
    for key, nm in meta["families"]:
        gids = [g for g, v in groups.items() if v["fam"] == key]
        if gids:
            gids.sort(key=lambda g: (-groups[g]["cards"], groups[g]["name"]))
            fams.append({"key": key, "name": nm, "cards": len({m[0] for g in gids for m in groups[g]["m"]}), "groups": gids})
    for o in by_card:
        by_card[o].sort(key=lambda g: (groups[g]["cards"], g))
    tc = set(by_card)
    pset = set(meta["pile"])
    assert tc <= pset, "a tentative card is not a Not-yet-organized card"
    assert not TENTATIVE_LAYER or tc == c3, (len(tc), len(c3))
    src_cards = collections.defaultdict(set)
    for row in ledger:
        src_cards[row[0]].add(row[7])
    bc, wb = t["headline"]["cards"], t["with_broad"]["cards"]
    wt = wb + len(tc)
    new_cards = tc - c0
    out = {"meta": {"label": LABEL, "method": METHOD, "enabled": TENTATIVE_LAYER, "cards": len(tc), "placements": sum(len(v) for v in by_card.values()), "groups": len(groups),
                    "pile": len(pile), "still_unorganized": len(pile) - len(tc), "reasons": reasons,
                    "groups_by_origin": dict(collections.Counter("sub-heading" if v["origin"].startswith("sub-heading") else v["origin"] for v in groups.values())),
                    "cards_resting_only_on_unread_part_abilities": sum(1 for v in src_cards.values() if v == {"unread part"}),
                    "cards_with_a_rare_shape_ability": sum(1 for v in src_cards.values() if "rare shape" in v),
                    "new_cards_from_the_2026_10_promotions": len(new_cards),
                    "scenarios": scen, "held_groups_by_reason": dict(held),
                    "headline": {"precise": [bc, t["headline"]["pct"], t["headline"]["basis"]], "with_broad": [wb, t["with_broad"]["pct"], t["with_broad"]["basis"]],
                                 "with_tentative": [wt, round(100.0 * wt / t["in_scope"], 1),
                                                    "the broad figure plus %d not-yet-organized cards with an eligible ability in a tentative group" % len(tc)], "in_scope": t["in_scope"]},
                    "rules": {"min_eligible_cards": MIN_ELIGIBLE_CARDS, "textless_over": HOLD_TEXTLESS_OVER, "hold_gap_test_failures": HOLD_GAP_TEST_FAILURES, "hold_loose_residuals": HOLD_LOOSE_RESIDUALS,
                              "hold_unread_part_abilities": HOLD_UNREAD_PART_ABILITIES, "promote_renamed_groups": PROMOTE_RENAMED_GROUPS, "promote_subheadings": PROMOTE_SUBHEADINGS}},
           "families": fams, "groups": groups, "by_card": {o: by_card[o] for o in sorted(by_card)}}
    # what the unread-part switch would give (default unchanged), as a figure
    out["meta"]["unread_part_off"] = {"cards": len(c4), "with_tentative": [wb + len(c4), round(100.0 * (wb + len(c4)) / t["in_scope"], 1)], "pile": len(pile) - len(c4)}
    ledger.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[5]))
    led = {"method": METHOD, "columns": ["oracle_id", "face", "bucket", "index", "ability text", "tentative group", "method", "rests on"], "rows": ledger}
    for fn, doc in (("tentative_placements.json", out), ("tentative_ledger.json", led)):
        with io.open(os.path.join(BUILD, fn), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    m = out["meta"]
    print(json.dumps({k: v for k, v in m.items() if k not in ("reasons", "rules")}, indent=1))


if __name__ == "__main__":
    main()
