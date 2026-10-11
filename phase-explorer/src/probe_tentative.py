#!/usr/bin/env python3
"""Probe (read-only) for the tentative promotion of loose groups: candidates, eligible members, text-less share, and the blind per-group read.

    LOOSE_CACHE=<pickle> python src/probe_tentative.py          # -> build/tentative_probe.json, build/tentative_probe_blind.json, build/tentative_probe_key.json
    python src/probe_tentative.py reveal                        # after build/tentative_probe_reads.json exists -> build/tentative_probe_result.json

Seed 20261021, declared before any computation, picks (and orders) the up-to-8 members read in each candidate group.
Candidates are the plain loose groups only (not the two catch-alls, not the "Less common effects, by kind" buckets). A member ability is eligible only if it is not held for a
dropped condition and has ability text. Nothing here is read by the builds.
"""
import collections
import io
import json
import os
import pickle
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_loose_groups as BL

BUILD = BL.BUILD
SEED = 20261021
MIN_ELIGIBLE_CARDS = 5


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def eligible(it):
    return it["src"] != "flagged" and bool((it["text"] or "").strip()) and it["reason"] != "gap_card_no_text"


def load():
    cache = os.environ.get("LOOSE_CACHE")
    if cache and os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    d = BL.collect()
    if cache:
        pickle.dump(d, open(cache, "wb"))
    return d


def measure():
    items, raw, info, meta = load()
    fam_keys = {k for k, _ in meta["families"]}
    use_idx, keys, folded, fm, names, sizes, kind_of = BL.make_groups(items, raw, info, fam_keys)
    out = {"seed": SEED, "min_eligible_cards": MIN_ELIGIBLE_CARDS}
    cand = []
    for k in sorted(folded, key=lambda k: BL.gid_of(k)):
        if kind_of(k) != "group":
            continue
        ns = fm[k]
        el = [n for n in ns if eligible(items[n])]
        cards = {items[n]["oid"] for n in ns}
        elc = {items[n]["oid"] for n in el}
        notext = {items[n]["oid"] for n in ns if not (items[n]["text"] or "").strip() or items[n]["reason"] == "gap_card_no_text"}
        # a card counts as text-less in the group only if none of its abilities in the group has text
        withtext = {items[n]["oid"] for n in ns if (items[n]["text"] or "").strip() and items[n]["reason"] != "gap_card_no_text"}
        cand.append({"gid": BL.gid_of(k), "name": names[k], "fam": k[0], "cards": len(cards), "eligible_cards": len(elc), "abilities": len(ns), "eligible_abilities": len(el),
                     "cards_without_any_text": len(cards - withtext),
                     "reasons": dict(collections.Counter(items[n]["src"] if items[n]["src"] != "A" else "rare shape" for n in ns)), "n": ns, "el": el})
    out["candidates"] = len(cand)
    out["candidate_cards_loose"] = len({items[n]["oid"] for c in cand for n in c["n"]})
    out["candidate_cards_eligible"] = len({items[n]["oid"] for c in cand for n in c["el"]})
    rnd = random.Random(SEED)
    blind, key = [], []
    for i, c in enumerate(cand, 1):
        ns = sorted(c["el"], key=lambda n: (items[n]["oid"], items[n]["text"]))
        rnd.shuffle(ns)
        seen, pick = set(), []
        for n in ns:
            if items[n]["oid"] in seen:
                continue
            seen.add(items[n]["oid"])
            pick.append(n)
            if len(pick) == 8:
                break
        blind.append({"n": i, "members": [" ".join((items[n]["text"]).split())[:170] for n in pick], "eligible_cards": c["eligible_cards"]})
        key.append({"n": i, "gid": c["gid"], "name": c["name"], "fam": c["fam"], "cards": c["cards"], "eligible_cards": c["eligible_cards"], "abilities": c["abilities"],
                    "eligible_abilities": c["eligible_abilities"], "cards_without_any_text": c["cards_without_any_text"], "reasons": c["reasons"], "read_cards": len(pick)})
    out["groups"] = [{k: v for k, v in c.items() if k not in ("n", "el")} for c in cand]
    with io.open(os.path.join(BUILD, "tentative_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    with io.open(os.path.join(BUILD, "tentative_probe_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "groups": blind}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "tentative_probe_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed": SEED, "groups": key}, ensure_ascii=False, indent=1))
    print(len(cand), "candidates;", out["candidate_cards_loose"], "cards in them;", out["candidate_cards_eligible"], "with an eligible ability")
    print("eligible cards <5:", sum(1 for c in cand if c["eligible_cards"] < MIN_ELIGIBLE_CARDS), " text-less share >50%:", sum(1 for c in cand if c["cards_without_any_text"] * 2 > c["cards"]))


def reveal():
    reads = jl("tentative_probe_reads.json")["groups"]
    key = jl("tentative_probe_key.json")["groups"]
    rows, cv = [], collections.Counter()
    for k in key:
        r = reads[str(k["n"])]
        cv[r["verdict"]] += 1
        rows.append(dict(k, read=r["read"], verdict=r["verdict"], key_states_effect=r["key_ok"], note=r.get("note", "")))
    with io.open(os.path.join(BUILD, "tentative_probe_result.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"summary": dict(cv), "groups": rows}, ensure_ascii=False, indent=1))
    print(dict(cv))


SEED_NAMES = 20261022        # declared before the name hand check: draws 20 promoted groups whose names are compared with the members read


def decide():
    """apply the promotion rule to the reads: not incoherent, the key states the effect, at least MIN_ELIGIBLE_CARDS eligible cards, and no more than half of the group's cards text-less."""
    res = jl("tentative_probe_result.json")["groups"]
    pr = jl("tentative_probe.json")
    rows, why = [], collections.Counter()
    for g in res:
        reasons = []
        if g["verdict"] == "incoherent":
            reasons.append("mixed or unreadable members")
        if not g["key_states_effect"]:
            reasons.append("the key does not state the effect")
        if g["eligible_cards"] < MIN_ELIGIBLE_CARDS:
            reasons.append("fewer than %d eligible cards" % MIN_ELIGIBLE_CARDS)
        if g["cards_without_any_text"] * 2 > g["cards"]:
            reasons.append("most members have no ability text")
        residual = any(w in g["name"] for w in ("less common kinds", "other kinds of target"))
        rows.append(dict(g, promote=not reasons, held_reasons=reasons, residual=residual))
        for r in reasons:
            why[r] += 1
    return rows, why


def analyze():
    rows, why = decide()
    out = {"rule": "promote if not incoherent, the key states the effect, at least %d eligible cards, and at most half the cards text-less" % MIN_ELIGIBLE_CARDS}
    out["groups_read"] = len(rows)
    prom = [g for g in rows if g["promote"]]
    out["promoted_groups"] = len(prom)
    out["held_groups"] = len(rows) - len(prom)
    out["held_reasons_count_of_groups"] = dict(why)
    out["promoted_that_are_loose"] = sum(1 for g in prom if g["verdict"] == "loose")
    out["promoted_that_are_backoff_residual"] = sum(1 for g in prom if g["residual"])
    out["promoted_loose_and_residual"] = sum(1 for g in prom if g["residual"] and g["verdict"] == "loose")
    out["promoted_by_family"] = dict(collections.Counter(g["fam"] for g in prom))
    # cards: recompute from the build
    items, raw, info, meta = load()
    fam_keys = {k for k, _ in meta["families"]}
    use_idx, keys, folded, fm, names, sizes, kind_of = BL.make_groups(items, raw, info, fam_keys)
    gid_k = {BL.gid_of(k): k for k in folded}
    pset = set(g["gid"] for g in prom)
    tcards, per_group = collections.defaultdict(set), {}
    for gid in pset:
        k = gid_k[gid]
        cs = {items[n]["oid"] for n in fm[k] if eligible(items[n])}
        per_group[gid] = len(cs)
        for o in cs:
            tcards[o].add(gid)
    out["tentative_cards"] = len(tcards)
    out["tentative_placements"] = sum(len(v) for v in tcards.values())
    out["groups_per_card_avg"] = round(out["tentative_placements"] / len(tcards), 2)
    out["groups_per_card_max"] = max(len(v) for v in tcards.values())
    pile_group = {}
    for g in jl("ability_taxonomy_unorganized.json")["groups"]:
        for c in g["list"]:
            pile_group[c["c"]] = g["name"]
    out["tentative_cards_by_pile_group"] = dict(collections.Counter(pile_group[o] for o in tcards))
    lg = jl("loose_groups.json")
    out["tentative_cards_that_are_in_a_loose_group"] = sum(1 for o in tcards if o in lg["by_card"])
    m3 = set(jl("min3_probe.json")["gaining_cards"])
    out["min3_gaining_cards"] = len(m3)
    out["min3_gaining_cards_also_tentative_by_a_promoted_group"] = len(m3 & set(tcards))
    out["pile"] = 5593
    out["left_in_not_yet_organized"] = 5593 - len(tcards)
    t = jl("ability_taxonomy.json")["totals"]
    out["headline_precise"] = [t["headline"]["cards"], t["headline"]["pct"]]
    out["headline_with_broad"] = [t["with_broad"]["cards"], t["with_broad"]["pct"]]
    wt = t["with_broad"]["cards"] + len(tcards)
    out["headline_with_tentative"] = [wt, round(100.0 * wt / t["in_scope"], 1)]
    out["in_scope"] = t["in_scope"]
    # the 20 names
    rnd = random.Random(SEED_NAMES)
    pick = rnd.sample(sorted(prom, key=lambda g: g["gid"]), min(20, len(prom)))
    out["name_check"] = [{"gid": g["gid"], "name": g["name"], "read": g["read"], "verdict": g["verdict"], "cards": g["cards"], "eligible_cards": g["eligible_cards"]} for g in pick]
    # defect and claims checks on the promoted names
    import re
    import ability_names as AN
    import probe_names_part1 as P1
    cards_json = jl("ability_taxonomy_cards.json")["cards"]
    vocab = set()
    for c in cards_json.values():
        for w in re.findall(r"[A-Za-z][a-z']{2,}", c["t"] or ""):
            vocab.add(w.lower())
    P1.ALLOW.update(AN.TEMPLATE_VOCAB)
    P1.ALLOW.update({"affecting", "granting", "several", "bigger", "smaller", "counted", "unchanged", "amount", "continuous", "kinds", "same", "something", "state", "recorded", "reader", "named", "replacement"})
    scan = P1.defect_scan([("group", g["name"].split(" › ", 1)[1]) for g in prom], vocab)
    soft = ("longer than 110 characters", "stacked parentheses", "disambiguation suffix ('(variant)', '#2')")
    hard = {n.split("  [")[0] for k, v in scan.items() if k not in soft for _, n in v}
    import probe_names_part2 as P2
    bad = []
    for g in prom:
        k = gid_k[g["gid"]]
        texts = [P2.norm(items[n]["text"]) for n in fm[k] if eligible(items[n])]
        if len(texts) < 5:
            continue
        low = set(re.findall(r"[a-z']+", P2.norm(g["name"].split("›", 1)[1])))
        for w, rx in P2.STEMS.items():
            if w in low or (w + "s") in low:
                if sum(1 for t in texts if re.search(rx, t)) / len(texts) < 0.5:
                    bad.append((g["name"], w))
    out["name_scan"] = {"names": len(prom), "hard_defects": len(hard), "examples": sorted(hard)[:6], "claims_hits": len(bad), "claims_examples": bad[:6],
                        "over_110_characters": sum(1 for g in prom if len(g["name"]) > 110)}
    out["table"] = [{k: g[k] for k in ("n", "gid", "name", "fam", "cards", "eligible_cards", "cards_without_any_text", "verdict", "key_states_effect", "promote", "held_reasons", "residual", "note")} for g in rows]
    out["per_group_tentative_cards"] = per_group
    with io.open(os.path.join(BUILD, "tentative_probe_decision.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print(json.dumps({k: v for k, v in out.items() if k not in ("table", "per_group_tentative_cards", "name_check")}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    {"reveal": reveal, "analyze": analyze}.get(sys.argv[1] if len(sys.argv) > 1 else "", measure)()
