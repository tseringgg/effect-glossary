#!/usr/bin/env python3
"""The tentative layer: loose groups promoted to TENTATIVE placements, shown beside the main groups, never counted as organized.

    python src/build_tentative.py        # -> build/tentative_placements.json, build/tentative_ledger.json   (run after build_loose_groups.py's inputs exist; about a minute)

Method name in the data: `loose_tentative` (`min3_tentative` is reserved and not built). Nothing here is read by the taxonomy build, the leaves, the loose layer, the headline or the
reconciliation: every promoted card is still a "Not yet organized" card in the build; the page subtracts it from the pile count and shows a third figure.

Rules (decided in review, 2026-10):
  * candidates are the plain loose groups only: not the catch-alls, not the "Less common effects, by kind" buckets;
  * an ability is eligible only if it is not held for a dropped condition, has ability text, and is not a gap-test failure (HOLD_GAP_TEST_FAILURES);
    abilities with an unread part stay eligible and say so on their row;
  * a group is promoted only if its hand read (corrections/tentative_groups.json) is coherent or loose, its name states the effect, it has at least MIN_ELIGIBLE_CARDS eligible cards, at most
    half of its cards are without any ability text, and it is not both loose and a backoff residual (HOLD_LOOSE_RESIDUALS);
  * a card is tentative if one of its eligible abilities is in a promoted group; it appears under every promoted group one of its eligible abilities fits.
TENTATIVE_LAYER = False writes an empty layer.
"""
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_loose_groups as BL
import probe_loose_groups as P

HERE = BL.HERE
BUILD = BL.BUILD
TENTATIVE_LAYER = True
MIN_ELIGIBLE_CARDS = 5
HOLD_TEXTLESS_OVER = 0.5
HOLD_GAP_TEST_FAILURES = True
HOLD_LOOSE_RESIDUALS = True
LABEL = "Tentative placement: grouped by effect type, not fully checked."
METHOD = "loose_tentative"


def has_text(it):
    return bool((it["text"] or "").strip()) and it["reason"] != "gap_card_no_text"


def eligible(it, hold_gap_tests):
    if it["src"] == "flagged" or not has_text(it):
        return False
    if hold_gap_tests and it["src"] == "test_fail":
        return False
    return True


def evaluate(groups, items, review, hold_residual, hold_gap_tests):
    """-> {gid: (set of tentative cards, why-not or '')} for every candidate group under the given holds."""
    out = {}
    for gid, g in groups.items():
        rev = review.get(gid)
        if rev is None:
            out[gid] = (set(), "not reviewed")
            continue
        if rev["verdict"] == "incoherent":
            out[gid] = (set(), "mixed or unreadable members")
            continue
        if not rev["key_states_effect"]:
            out[gid] = (set(), "the name does not state the effect")
            continue
        if hold_residual and g["residual"] and rev["verdict"] == "loose":
            out[gid] = (set(), "loose and a backoff residual")
            continue
        cards = {items[n]["oid"] for n in g["n"]}
        withtext = {items[n]["oid"] for n in g["n"] if has_text(items[n])}
        if (len(cards) - len(withtext)) > HOLD_TEXTLESS_OVER * len(cards):
            out[gid] = (set(), "most members have no ability text")
            continue
        el = {items[n]["oid"] for n in g["n"] if eligible(items[n], hold_gap_tests)}
        if len(el) < MIN_ELIGIBLE_CARDS:
            out[gid] = (set(), "fewer than %d eligible cards" % MIN_ELIGIBLE_CARDS)
            continue
        out[gid] = (el, "")
    return out


def main():
    items, raw, info, meta = BL.collect()
    fam_keys = {k for k, _ in meta["families"]}
    fam_name = dict(meta["families"])
    use_idx, keys, folded, fm, names, sizes, kind_of = BL.make_groups(items, raw, info, fam_keys)
    review = json.load(io.open(os.path.join(os.path.dirname(BUILD), "corrections", "tentative_groups.json"), encoding="utf-8"))["groups"]
    rank = BL.popularity()
    t = json.load(io.open(os.path.join(BUILD, "ability_taxonomy.json"), encoding="utf-8"))["totals"]
    cand = {}
    for k in folded:
        if kind_of(k) != "group":
            continue
        nf, kept = k[3]
        cand[BL.gid_of(k)] = {"key": k, "n": fm[k], "residual": kept < nf, "name": names[k]}
    scen = {}
    for nm, (r3, gt) in {"A": (False, False), "A+R3": (True, False), "A+gap tests": (False, True), "A+R3+gap tests": (True, True)}.items():
        ev = evaluate(cand, items, review, r3, gt)
        cs = set()
        for el, _ in ev.values():
            cs |= el
        scen[nm] = {"groups": sum(1 for el, _ in ev.values() if el), "cards": len(cs)}
    ev = evaluate(cand, items, review, HOLD_LOOSE_RESIDUALS, HOLD_GAP_TEST_FAILURES)
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
            if it["oid"] in el and eligible(it, HOLD_GAP_TEST_FAILURES):
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
        groups[gid] = {"name": g["name"], "short": g["name"].split(" › ", 1)[1], "fam": g["key"][0], "cards": len(el), "loose_cards": len({items[n]["oid"] for n in g["n"]}), "m": rows}
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
    src_cards = collections.defaultdict(set)
    for row in ledger:
        src_cards[row[0]].add(row[7])
    bc, wb = t["headline"]["cards"], t["with_broad"]["cards"]
    wt = wb + len(tc)
    out = {"meta": {"label": LABEL, "method": METHOD, "enabled": TENTATIVE_LAYER, "cards": len(tc), "placements": sum(len(v) for v in by_card.values()), "groups": len(groups),
                    "pile": len(pile), "still_unorganized": len(pile) - len(tc), "reasons": reasons,
                    "cards_resting_only_on_unread_part_abilities": sum(1 for v in src_cards.values() if v == {"unread part"}),
                    "cards_with_a_rare_shape_ability": sum(1 for v in src_cards.values() if "rare shape" in v),
                    "scenarios": scen, "held_groups_by_reason": dict(held),
                    "headline": {"precise": [bc, t["headline"]["pct"], t["headline"]["basis"]], "with_broad": [wb, t["with_broad"]["pct"], t["with_broad"]["basis"]],
                                 "with_tentative": [wt, round(100.0 * wt / t["in_scope"], 1),
                                                    "the broad figure plus %d not-yet-organized cards with an eligible ability in a tentative group" % len(tc)], "in_scope": t["in_scope"]},
                    "rules": {"min_eligible_cards": MIN_ELIGIBLE_CARDS, "textless_over": HOLD_TEXTLESS_OVER, "hold_gap_test_failures": HOLD_GAP_TEST_FAILURES, "hold_loose_residuals": HOLD_LOOSE_RESIDUALS}},
           "families": fams, "groups": groups, "by_card": {o: by_card[o] for o in sorted(by_card)}}
    ledger.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[5]))
    led = {"method": METHOD, "columns": ["oracle_id", "face", "bucket", "index", "ability text", "tentative group", "method", "rests on"], "rows": ledger}
    for fn, doc in (("tentative_placements.json", out), ("tentative_ledger.json", led)):
        with io.open(os.path.join(BUILD, fn), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    m = out["meta"]
    print(json.dumps({k: v for k, v in m.items() if k not in ("reasons", "rules")}, indent=1))


if __name__ == "__main__":
    main()
