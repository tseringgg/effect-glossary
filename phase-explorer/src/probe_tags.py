#!/usr/bin/env python3
"""Tag-layer probe, Part 1 (read-only): tag data, filtering and coverage of the remaining pile. Builds nothing, places nothing, changes nothing.

    python src/probe_tags.py            # -> build/tag_probe_part1.json (+ build/tag_probe_cards.json: the card sets and tags the later parts read)

Inputs: the old snapshot (development/versions/card_function_search_v0.2/data/oracle-tags-raw.json, 2026-07-16, never touched), the new one (data/oracle-tags-20261014.json, fetched by
src/fetch_tags_probe.py), the build's card sets and the project's Scryfall oracle-card file (release dates and EDHREC rank).
Functional-tag rule = the existing rules of the card_function_search_v0.2 project: type "oracle" (generate_otag_glossary.py), a floor of 20 taggings (its default threshold), and the denylist of
otag_grounding.py (exact slugs and the prefixes cycle-, art-, artist-, watermark-, flavor-, name-, with the one narrow exception it keeps).
Seed 20261038 (declared before the draw) picks the 30 dropped tags shown. Tags are keyed by tag UUID, never by slug.
"""
import collections
import gzip
import io
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
OLD = os.path.join(os.path.dirname(os.path.dirname(HERE)), "development", "versions", "card_function_search_v0.2", "data", "oracle-tags-raw.json")
OLD = os.path.normpath(os.path.join(HERE, "..", "..", "..", "development", "versions", "card_function_search_v0.2", "data", "oracle-tags-raw.json"))
NEW = os.path.join(HERE, "data", "oracle-tags-20261014.json")
SEED = 20261038
FLOOR = 20
OLD_DATE = "2026-07-16"
DENIED_SLUGS = frozenset({"meme", "alliteration", "single-english-word-name", "unique-type-line", "namesake-spell", "intervening-if-clause", "virtual-vanilla", "virtual-french-vanilla", "french-vanilla",
                          "vanilla", "activated-ability", "triggered-ability", "flavor-text", "reprint", "funny"})
DENIED_PREFIXES = ("cycle-", "art-", "artist-", "watermark-", "flavor-", "name-")
PREFIX_EXCEPTIONS = frozenset({"cycle-dual-surveil-land"})
CAUSE = {1: "no readable ability", 2: "dropped-condition hold", 3: "gap-test hold", 4: "catch-all", 5: "held group", 6: "other"}


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def load(p):
    return json.load(io.open(p, encoding="utf-8"))


def drop_reason(t, floor=FLOOR):
    if t.get("type") != "oracle":
        return "not an oracle tag"
    s = t["slug"]
    if s in DENIED_SLUGS:
        return "denied slug"
    if s.startswith(DENIED_PREFIXES) and s not in PREFIX_EXCEPTIONS:
        return "denied prefix"
    if len(t.get("taggings", [])) < floor:
        return "below the floor of %d taggings" % floor
    return ""


def card_tags(tags, floor=FLOOR):
    """{oracle_id: set(tag uuid)} over the functional tags."""
    out = collections.defaultdict(set)
    for t in tags:
        if drop_reason(t, floor):
            continue
        for g in t["taggings"]:
            out[g["oracle_id"]].add(t["id"])
    return out


def pile_sets():
    unorg = jl("ability_taxonomy_unorganized.json")["groups"]
    pile = {c["c"] for g in unorg for c in g["list"]}
    tent = set(jl("tentative_placements.json")["by_card"])
    A = jl("annotation_placements.json")
    cs = {}
    for g in A["groups"].values():
        for r in g["m"]:
            if cs.get(r[0]) != "c":
                cs[r[0]] = r[6]
    cond_new = {o for o, s in cs.items() if s == "c" and o not in tent}
    gap_new = {o for o, s in cs.items() if s == "g" and o not in tent}
    off = pile - tent - cond_new                    # the pile with the gap-test stratum off: 2,540
    on = off - gap_new                              # with it on: 2,380
    prim = {o: v for o, v in jl("remaining_cards.json")["primary"].items()}
    return pile, tent, cond_new, gap_new, off, on, prim


def band(rank):
    if rank is None:
        return "no rank"
    return "top 1,000" if rank <= 1000 else ("1,001-3,000" if rank <= 3000 else ("3,001-10,000" if rank <= 10000 else "below 10,000"))


def main():
    old, new = load(OLD), load(NEW)
    om, nm = {t["id"]: t for t in old}, {t["id"]: t for t in new}
    out = {"old_snapshot": {"updated_at": json.load(io.open(OLD.replace(".json", ".meta.json"), encoding="utf-8"))["updated_at"], "tags": len(old), "taggings": sum(len(t["taggings"]) for t in old)},
           "new_snapshot": {"updated_at": json.load(io.open(NEW.replace(".json", ".meta.json"), encoding="utf-8"))["updated_at"], "tags": len(new), "taggings": sum(len(t["taggings"]) for t in new)}}
    both = set(om) & set(nm)
    chg = [(om[i]["slug"], nm[i]["slug"]) for i in sorted(both) if om[i]["slug"] != nm[i]["slug"]]
    out["uuid_comparison"] = {"in_both": len(both), "only_old": len(set(om) - set(nm)), "only_new": len(set(nm) - set(om)), "slug_changed_same_uuid": len(chg), "slug_changes_examples": chg[:12],
                              "label_changed_same_uuid": sum(1 for i in both if om[i].get("label") != nm[i].get("label")),
                              "slugs_in_both_snapshots_pointing_at_different_uuids": len({t["slug"] for t in old} & {t["slug"] for t in new}) - sum(1 for i in both if om[i]["slug"] == nm[i]["slug"]),
                              "slugs_the_old_file_has_and_new_does_not": len({t["slug"] for t in old} - {t["slug"] for t in new})}
    # ---- filtering
    reasons = collections.Counter(drop_reason(t) for t in new)
    surv = [t for t in new if not drop_reason(t)]
    out["filter"] = {"floor": FLOOR, "all": len(new), "survive": len(surv), "dropped_by_reason": {k or "(survive)": v for k, v in reasons.items()},
                     "survive_if_floor_5": sum(1 for t in new if not drop_reason(t, 5)), "survive_if_floor_10": sum(1 for t in new if not drop_reason(t, 10)),
                     "survive_old_snapshot_same_rules": sum(1 for t in old if not drop_reason(t))}
    rnd = random.Random(SEED)
    dropped = collections.defaultdict(list)
    for t in sorted(new, key=lambda t: t["id"]):
        r = drop_reason(t)
        if r:
            dropped[r.split(" of ")[0] if r.startswith("below") else r].append(t)
    shown = []
    for k in sorted(dropped):
        lst = dropped[k]
        rnd.shuffle(lst)
        shown += [{"reason": k, "slug": t["slug"], "taggings": len(t["taggings"]), "description": (t.get("description") or "")[:100]} for t in lst[:10 if k != "denied slug" else 10]]
    out["dropped_examples_seed_%d" % SEED] = shown[:30]
    # ---- card sets
    pile, tent, cond_new, gap_new, off, on, prim = pile_sets()
    tags_new, tags_old = card_tags(new), card_tags(old)
    oc = {}
    for l in gzip.open(os.path.join(HERE, "data", "scryfall-oracle-cards.jsonl.gz"), "rt", encoding="utf-8"):
        o = json.loads(l)
        oc[o["oracle_id"]] = (o.get("released_at", ""), o.get("edhrec_rank"), o["name"])

    def cover(S, tg):
        n = len(S)
        c = collections.Counter(min(len(tg.get(o, ())), 3) for o in S)
        return {"cards": n, "none": c[0], "1_or_2": c[1] + c[2], "at_least_1": n - c[0], "at_least_3": c[3], "pct_at_least_1": round(100.0 * (n - c[0]) / n, 1) if n else None}
    out["sets"] = {"pile": len(pile), "tentative": len(tent), "condition_annotated_new": len(cond_new), "gap_stratum_new": len(gap_new), "unorganized_gap_off": len(off), "unorganized_gap_on": len(on),
                   "reconciliation_gap_off": "%d pile - %d tentative - %d condition-annotated = %d" % (len(pile), len(tent), len(cond_new), len(off))}
    out["coverage_new_snapshot"] = {"gap_off": cover(off, tags_new), "gap_on": cover(on, tags_new)}
    out["coverage_old_snapshot"] = {"gap_off": cover(off, tags_old), "gap_on": cover(on, tags_old)}
    missing = [o for o in off if o not in prim]
    out["cards_without_a_primary_reason"] = len(missing)
    by = {}
    for lab, S in (("gap_off", off), ("gap_on", on)):
        rows = {}
        for k in (1, 2, 3, 4, 5, 6):
            ss = {o for o in S if prim.get(o) == k}
            rows[CAUSE[k]] = cover(ss, tags_new)
        by[lab] = rows
    out["coverage_by_cause_new_snapshot"] = by
    # ---- the 1,300 with no readable ability
    unread = {o for o in off if prim.get(o) == 1}
    rel_new = {o for o in unread if oc.get(o, ("",))[0] > OLD_DATE}
    out["no_readable_ability"] = {"cards": len(unread), "new_snapshot": cover(unread, tags_new), "old_snapshot": cover(unread, tags_old),
                                  "released_after_the_old_snapshot": {"cards": len(rel_new), "new_snapshot": cover(rel_new, tags_new), "old_snapshot": cover(rel_new, tags_old), "latest_release_date": max((oc[o][0] for o in rel_new), default="")},
                                  "released_on_or_before": {"cards": len(unread) - len(rel_new), "new_snapshot": cover(unread - rel_new, tags_new), "old_snapshot": cover(unread - rel_new, tags_old)},
                                  "not_in_the_oracle_card_file": sum(1 for o in unread if o not in oc)}
    # ---- readable cards for comparison: in the cards file, not in the pile, not left out
    cards = jl("ability_taxonomy_cards.json")["cards"]
    left = set(jl("card_flags.json")["cards"])
    readable = {o for o in cards if o not in pile and o not in left and (cards[o].get("t") or "").strip()}
    out["comparison_sets"] = {"readable_cards_with_text": len(readable), "new_snapshot": cover(readable, tags_new)}
    # ---- popularity bands (EDHREC rank of the oracle-card file): coverage per band, all cards with text and the unreadable ones
    bands = collections.defaultdict(lambda: {"all": set(), "unread": set(), "pile_off": set(), "readable": set()})
    for o in cards:
        if o in left or not (cards[o].get("t") or "").strip():
            continue
        b = band(oc.get(o, ("", None))[1])
        bands[b]["all"].add(o)
        if o in readable:
            bands[b]["readable"].add(o)
    for o in off:
        bands[band(oc.get(o, ("", None))[1])]["pile_off"].add(o)
    for o in unread:
        bands[band(oc.get(o, ("", None))[1])]["unread"].add(o)
    out["coverage_by_popularity_band"] = {b: {k: cover(v, tags_new) for k, v in d.items() if v} for b, d in sorted(bands.items())}
    out["median_functional_tags_per_card"] = {"readable": sorted(len(tags_new.get(o, ())) for o in readable)[len(readable) // 2], "unreadable_1300": sorted(len(tags_new.get(o, ())) for o in unread)[len(unread) // 2],
                                              "unorganized_gap_off": sorted(len(tags_new.get(o, ())) for o in off)[len(off) // 2]}
    with io.open(os.path.join(BUILD, "tag_probe_part1.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "tag_probe_cards.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"off": sorted(off), "on": sorted(on), "unread": sorted(unread), "primary": {o: prim.get(o) for o in sorted(off)}, "gap_new": sorted(gap_new)}, separators=(",", ":")))
    print(json.dumps({k: v for k, v in out.items() if k not in ("dropped_examples_seed_%d" % SEED,)}, indent=1, ensure_ascii=False))
    for d in shown[:30]:
        print("%-24s %-40s n=%-5d %s" % (d["reason"][:24], d["slug"][:40], d["taggings"], d["description"][:60].encode("ascii", "replace").decode()))


if __name__ == "__main__":
    main()
