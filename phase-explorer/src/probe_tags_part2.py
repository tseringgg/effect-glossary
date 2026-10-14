#!/usr/bin/env python3
"""Tag-layer probe, Part 2 (read-only): three ways to group the remaining pile by tag. Builds nothing, places nothing, changes nothing.

    python src/probe_tags_part2.py      # -> build/tag_probe_part2.json   (needs build/tag_probe_cards.json from src/probe_tags.py)

Population: the 2,540 unorganized cards with the gap-test stratum off (and, in a second column where it matters, the 2,380 with it on); functional tags of the 2026-10-14 snapshot (floor 20, denylist).
Option 1: one group per tag (size = pile cards carrying it). Option 2: identical tag sets, and near-identical sets by leader clustering at Jaccard >= 0.6 (sets of at least 3 tags). Option 3: a
coarse family: (a) a hand-written set of 16 families by slug words, (b) Scryfall's own tag hierarchy (parent_ids) rolled up to root tags.
Seed 20261039 (declared before the draw) picks the 20 tags whose coarse-family mapping is read by hand.
"""
import collections
import io
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_tags as PT

BUILD = PT.BUILD
SEED = 20261039
FAM = collections.OrderedDict([
    ("Removal and board wipes", {"removal", "destroy", "sweeper", "wrath", "kill", "edict", "fight", "bite", "wipe"}),
    ("Damage", {"burn", "damage", "ping", "pinger", "fling", "deals"}),
    ("Card draw and advantage", {"draw", "advantage", "cantrip", "impulse", "looting", "wheel", "refill", "rummage"}),
    ("Library: search, scry, mill", {"tutor", "search", "library", "scry", "surveil", "mill", "shuffle", "top"}),
    ("Mana", {"mana", "ramp", "treasure", "fixing", "rock", "dork", "land"}),
    ("Tokens and copies", {"token", "tokens", "copy", "clone", "populate", "create"}),
    ("Counters and growth", {"counters", "pp", "mm", "proliferate", "boost", "pump", "buff", "anthem"}),
    ("Combat and evasion", {"flying", "trample", "haste", "menace", "evasion", "combat", "attack", "attacks", "block", "blocks", "unblockable", "deathtouch", "vigilance", "reach", "strike"}),
    ("Life gain and loss", {"lifegain", "lifelink", "life", "drain", "lifeloss"}),
    ("Graveyard and recursion", {"reanimate", "graveyard", "recursion", "flashback", "unearth", "dredge", "escape", "delve", "reanimation"}),
    ("Sacrifice and death", {"sacrifice", "sac", "death", "dies", "aristocrat", "fodder"}),
    ("Discard and hand", {"discard", "hand", "madness", "cycling", "hellbent"}),
    ("Protection and resilience", {"protection", "hexproof", "indestructible", "regenerate", "shroud", "ward", "flicker", "blink", "phase", "phasing"}),
    ("Counterspells and the stack", {"counterspell", "stifle", "storm", "cast", "spell", "stack"}),
    ("Costs and restrictions", {"cost", "tax", "restriction", "cant", "prevent", "hate", "stax", "reduction"}),
    ("Typal and synergy", {"typal", "synergy", "matters", "tribal", "lord"}),
])
BAND_SIZES = (("under 5", 0, 4), ("5 to 20", 5, 20), ("21 to 100", 21, 100), ("over 100", 101, 10 ** 9))


def main():
    new = PT.load(PT.NEW)
    nm = {t["id"]: t for t in new}
    surv = {t["id"] for t in new if not PT.drop_reason(t)}
    tg = PT.card_tags(new)
    d = json.load(io.open(os.path.join(BUILD, "tag_probe_cards.json"), encoding="utf-8"))
    cards = PT.jl("ability_taxonomy_cards.json")["cards"]
    name = lambda o: cards[o]["n"]
    out = {}
    for lab, S in (("gap_off", set(d["off"])), ("gap_on", set(d["on"]))):
        # ---------------------------------------------------------------- option 1: one group per tag
        G = collections.defaultdict(set)
        for o in S:
            for t in tg.get(o, ()):
                G[t].add(o)
        sizes = {t: len(v) for t, v in G.items()}
        bands = {b: sum(1 for s in sizes.values() if lo <= s <= hi) for b, lo, hi in BAND_SIZES}
        keep = {t for t, s in sizes.items() if 5 <= s <= 100}
        reach = collections.Counter()
        reach_cards = {o for o in S if any(t in keep for t in tg.get(o, ()))}
        reach_ge5 = {o for o in S if any(sizes.get(t, 0) >= 5 for t in tg.get(o, ()))}
        per_card = sorted(sum(1 for t in tg.get(o, ()) if t in keep) for o in reach_cards)
        per_card_all = sorted(len(tg.get(o, ())) for o in S)
        top = sorted(G, key=lambda t: -sizes[t])[:15]
        o1 = {"tags_with_a_pile_card": len(G), "group_size_bands": bands, "groups_of_5_to_100": len(keep), "cards_reached_by_a_group_of_5_to_100": len(reach_cards), "pct_of_pile": round(100.0 * len(reach_cards) / len(S), 1),
              "cards_reached_by_any_group_of_5_or_more": len(reach_ge5), "cards_only_in_groups_over_100": len(reach_ge5) - len(reach_cards), "cards_in_no_group_of_5_or_more": len(S) - len(reach_ge5),
              "groups_per_card_5_to_100": {"median": per_card[len(per_card) // 2] if per_card else 0, "mean": round(sum(per_card) / len(per_card), 1) if per_card else 0, "max": per_card[-1] if per_card else 0, "p90": per_card[int(len(per_card) * 0.9)] if per_card else 0},
              "tags_per_card_all": {"median": per_card_all[len(per_card_all) // 2], "mean": round(sum(per_card_all) / len(per_card_all), 1), "max": per_card_all[-1]},
              "largest_15": [{"slug": nm[t]["slug"], "pile_cards": sizes[t], "all_cards": len(nm[t]["taggings"])} for t in top]}
        # ---------------------------------------------------------------- option 2: tag sets
        sets = {o: frozenset(tg.get(o, ())) for o in S}
        ident = collections.Counter(sets.values())
        id5 = [s for s, n in ident.items() if n >= 5 and s]
        cards_id5 = sum(ident[s] for s in id5)
        # leader clustering, Jaccard >= 0.6, sets of >= 3 tags, biggest-set order (deterministic)
        order = sorted((o for o in S if len(sets[o]) >= 3), key=lambda o: (-len(sets[o]), o))
        leaders = []
        members = collections.defaultdict(list)
        for o in order:
            s = sets[o]
            best, bj = None, 0.0
            for li, l in enumerate(leaders):
                ls = sets[l]
                inter = len(s & ls)
                if inter == 0:
                    continue
                j = inter / len(s | ls)
                if j > bj:
                    best, bj = li, j
            if best is not None and bj >= 0.6:
                members[best].append(o)
            else:
                leaders.append(o)
                members[len(leaders) - 1].append(o)
        csz = sorted((len(m) for m in members.values()), reverse=True)
        big = [m for m in members.values() if len(m) >= 5]
        ex = []
        for m in sorted(big, key=lambda m: (-len(m), m[0]))[:5]:
            common = set.intersection(*[set(sets[o]) for o in m])
            ex.append({"size": len(m), "tags_shared_by_all": sorted(nm[t]["slug"] for t in common)[:8], "example_cards": [name(o) for o in sorted(m)[:5]]})
        o2 = {"distinct_identical_sets": len(ident), "identical_sets_shared_by_5_or_more_cards": len(id5), "cards_in_them": cards_id5, "pct_of_pile": round(100.0 * cards_id5 / len(S), 1),
              "largest_identical_set_sizes": sorted(ident.values(), reverse=True)[:8], "cards_with_fewer_than_3_tags_not_clustered": sum(1 for o in S if len(sets[o]) < 3),
              "near_identical_clusters": len(leaders), "clusters_of_5_or_more": len(big), "cards_in_clusters_of_5_or_more": sum(len(m) for m in big), "pct_of_pile_in_clusters_of_5_or_more": round(100.0 * sum(len(m) for m in big) / len(S), 1),
              "cluster_size_bands": {b: sum(1 for s in csz if lo <= s <= hi) for b, lo, hi in (("1", 1, 1), ("2 to 4", 2, 4), ("5 to 20", 5, 20), ("21 to 100", 21, 100), ("over 100", 101, 10 ** 9))}, "examples": ex}
        # ---------------------------------------------------------------- option 3
        fam_of = {}
        for t in surv:
            toks = set(re.split(r"[^a-z0-9+]+", nm[t]["slug"]))
            # a slug with "counterspell" is not a counters tag
            hit = [f for f, w in FAM.items() if toks & w]
            fam_of[t] = hit
        clean = sum(1 for h in fam_of.values() if len(h) == 1)
        o3a = {"surviving_tags": len(surv), "map_to_exactly_one_family": clean, "match_several": sum(1 for h in fam_of.values() if len(h) > 1), "match_none": sum(1 for h in fam_of.values() if not h)}
        # cards reached: a card goes to the families of its mapped tags; "clean" = tags that map to exactly one
        cf = collections.defaultdict(set)
        for o in S:
            for t in tg.get(o, ()):
                if len(fam_of.get(t, [])) == 1:
                    cf[fam_of[t][0]].add(o)
        o3a["cards_reached_by_a_cleanly_mapped_tag"] = len(set().union(*cf.values())) if cf else 0
        o3a["pct_of_pile"] = round(100.0 * o3a["cards_reached_by_a_cleanly_mapped_tag"] / len(S), 1)
        o3a["family_sizes"] = {f: len(v) for f, v in sorted(cf.items(), key=lambda kv: -len(kv[1]))}
        o3a["families_per_card_median"] = sorted(sum(1 for f in cf if o in cf[f]) for o in S)[len(S) // 2]
        # (b) the tag hierarchy
        def roots(t, seen=()):
            ps = nm[t].get("parent_ids") or []
            if not ps:
                return {t}
            r = set()
            for p in ps:
                if p in nm and p not in seen:
                    r |= roots(p, seen + (t,))
            return r or {t}
        rt = {t: roots(t) for t in surv}
        rc = collections.defaultdict(set)
        for o in S:
            for t in tg.get(o, ()):
                for r in rt.get(t, ()):
                    rc[r].add(o)
        o3b = {"surviving_tags_with_a_parent": sum(1 for t in surv if nm[t].get("parent_ids")), "root_tags_reached": len(rc), "root_tag_size_bands": {b: sum(1 for v in rc.values() if lo <= len(v) <= hi) for b, lo, hi in BAND_SIZES},
               "cards_reached_by_a_root_of_5_to_100": len({o for v in rc.values() if 5 <= len(v) <= 100 for o in v}), "largest_roots": [(nm[r]["slug"], len(v)) for r, v in sorted(rc.items(), key=lambda kv: -len(kv[1]))[:10]]}
        out[lab] = {"cards": len(S), "option1_one_group_per_tag": o1, "option2_tag_sets": o2, "option3a_hand_written_families": o3a, "option3b_tag_hierarchy": o3b}
    # the 20 tags read by hand for option 3a
    rnd = random.Random(SEED)
    clean_tags = sorted((t for t in surv if sum(1 for f, w in FAM.items() if set(re.split(r"[^a-z0-9+]+", nm[t]["slug"])) & w) == 1), key=lambda t: nm[t]["slug"])
    pick = rnd.sample(clean_tags, 20)
    out["family_map_sample_seed_%d" % SEED] = [{"slug": nm[t]["slug"], "description": (nm[t].get("description") or "")[:110], "family": [f for f, w in FAM.items() if set(re.split(r"[^a-z0-9+]+", nm[t]["slug"])) & w][0]} for t in pick]
    with io.open(os.path.join(BUILD, "tag_probe_part2.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
