#!/usr/bin/env python3
"""The community-tag layer: the 1,300 cards with no readable ability, grouped by Scryfall community (Tagger) tag. A separate, labeled layer; it never feeds the main tree, the tentative layer or
the annotation layer, and it is never counted in the first five figures.

    python src/build_tag_layer.py        # -> build/tag_placements.json, build/tag_ledger.json   (seconds; reads build files and data/oracle-tags-20261014.json)

Method name in the data: `community_tag`. Flag: TAG_LAYER = False writes an empty layer. Scope: cards whose primary reason in build/remaining_cards.json is "no readable ability" and that are still in the
pile after the tentative and annotation layers (the 1,300). Groups: one per tag, tag keyed by UUID, groups of 5 to 100 of those cards (tags over 100 are not groups: they are kept as filters only);
tags: type oracle, floor of 20 taggings, the card_function_search denylist and corrections/tag_denylist.json (src/tag_layer_filter.py). Names: src/tag_layer_names.py (name_source rule, model_written,
user_edit). A card is counted once however many groups hold it.
Wording on the page (fixed here): "Grouped by community tag. Not checked against the card's parsed text."
"""
import collections
import hashlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_tags as PT
import tag_layer_filter as F
import tag_layer_names as N

BUILD = PT.BUILD
TAG_LAYER = True
METHOD = "community_tag"
LABEL = "Grouped by community tag. Not checked against the card's parsed text."
BADGE = "community tag"


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def dump(name, obj):
    with io.open(os.path.join(BUILD, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def main():
    tg = jl("tentative_placements.json")
    A = jl("annotation_placements.json")
    cards = jl("ability_taxonomy_cards.json")["cards"]
    tent = set(tg["by_card"])
    ann = set(A["by_card"])
    cs = {}
    for g in A["groups"].values():
        for r in g["m"]:
            if cs.get(r[0]) != "c":
                cs[r[0]] = r[6]
    cond_new = {o for o, s in cs.items() if s == "c" and o not in tent}
    pile = {c["c"] for g in jl("ability_taxonomy_unorganized.json")["groups"] for c in g["list"]}
    prim = jl("remaining_cards.json")["primary"]
    scope = {o for o in pile if prim.get(o) == 1 and o not in tent and o not in cond_new}
    assert len(scope) == 1300, len(scope)
    assert not (scope & ann), "a tag-layer card is also annotated"
    new = PT.load(PT.NEW)
    meta = json.load(io.open(PT.NEW.replace(".json", ".meta.json"), encoding="utf-8"))
    fn = F.functional(new)
    ct = F.card_tags(fn)
    G = F.groups(scope, ct)
    doc = N.load_overlay()
    groups, wide = {}, {}
    if TAG_LAYER:
        for t, v in G.items():
            tag = fn[t]
            if F.GROUP_MIN <= len(v) <= F.GROUP_MAX:
                name, src = N.name_of(tag["slug"], doc)
                groups[t] = {"name": name, "name_source": src, "slug": tag["slug"], "description": " ".join((tag.get("description") or "").split()), "cards": len(v), "all_cards": len(tag["taggings"]), "m": sorted(v)}
            elif len(v) > F.GROUP_MAX:
                name, src = N.name_of(tag["slug"], doc)
                wide[t] = {"name": name, "name_source": src, "slug": tag["slug"], "cards": len(v), "m": sorted(v)}
    by_card, wide_by_card = collections.defaultdict(list), collections.defaultdict(list)
    for t, g in groups.items():
        for o in g["m"]:
            by_card[o].append(t)
    for t, g in wide.items():
        for o in g["m"]:
            wide_by_card[o].append(t)
    for o in by_card:
        by_card[o].sort(key=lambda t: (groups[t]["cards"], t))
    placed = set(by_card)
    only_wide = {o for o in wide_by_card if o not in placed}
    with_tags_no_group = {o for o in scope if ct.get(o) and o not in placed}
    no_tag = {o for o in scope if not ct.get(o)}
    order = sorted(groups, key=lambda t: (-groups[t]["cards"], groups[t]["name"], t))
    am = A["meta"]
    head = am["headline"]
    n_in = head["in_scope"]
    n_tag = len(placed)
    fig6 = head["with_annotation"][0] + n_tag
    pile_off = am["still_unorganized_after_annotation"]
    out = {"meta": {"enabled": bool(groups), "method": METHOD, "label": LABEL, "badge": BADGE, "snapshot": meta["updated_at"], "snapshot_file": os.path.basename(PT.NEW), "snapshot_sha1": hashlib.sha1(open(PT.NEW, "rb").read()).hexdigest(),
                     "tag_count_snapshot": len(new), "functional_tags": len(fn), "denied_by_the_deny_list": json.load(io.open(os.path.join(BUILD, "tag_layer_filter_report.json"), encoding="utf-8"))["tags"]["denied_by_the_deny_list"],
                     "scope_cards": len(scope), "groups": len(groups), "wide_tags_not_groups": len(wide), "cards": n_tag, "cards_only_in_groups_over_100": len(only_wide), "cards_with_tags_but_no_usable_group": len(with_tags_no_group),
                     "cards_with_no_functional_tag": len(no_tag), "cards_without_a_usable_group": len(scope) - n_tag,
                     "name_source": dict(collections.Counter(g["name_source"] for g in groups.values())),
                     "rules": {"tag_layer": TAG_LAYER, "floor": PT.FLOOR, "group_min": F.GROUP_MIN, "group_max": F.GROUP_MAX, "scope": "primary reason 'no readable ability' (remaining_cards.json), not tentative, not condition-annotated"},
                     "headline": {"in_scope": n_in, "precise": head["precise"], "with_broad": head["with_broad"], "with_tentative": head["with_tentative"], "with_annotation": head["with_annotation"], "with_gap_stratum": head["with_gap_stratum"],
                                  "with_tag": [fig6, round(100.0 * fig6 / n_in, 1), "the with-annotation figure plus %s of the 1,300 cards with no readable ability that sit in a community-tag group of 5 to 100 cards (browsable by community tag, not organized; not checked against the parse)" % format(n_tag, ",")]},
                     "pile_before": pile_off, "still_unorganized_after_tag": pile_off - n_tag, "still_unorganized_after_tag_with_gap_stratum": am["still_unorganized_after_gap_stratum"] - n_tag,
                     "reconciliation": {"placed_with_broad": head["with_broad"][0], "tentative": tg["meta"]["cards"], "annotation": am["condition_cards_new"], "tag": n_tag, "unorganized": pile_off - n_tag, "not_cards": 5738,
                                        "sum": head["with_broad"][0] + tg["meta"]["cards"] + am["condition_cards_new"] + n_tag + (pile_off - n_tag) + 5738, "gap_stratum_separately": am["gap_cards_new"]}},
           "groups": groups, "order": order, "wide": wide, "by_card": {o: v for o, v in sorted(by_card.items())}, "wide_by_card": {o: sorted(v) for o, v in sorted(wide_by_card.items())},
           "no_group": sorted(set(scope) - placed)}
    dump("tag_placements.json", out)
    led = []
    for t in order:
        g = groups[t]
        for o in g["m"]:
            led.append([o, cards[o]["n"], g["name"], g["slug"], t, g["name_source"], METHOD])
    dump("tag_ledger.json", {"columns": ["oracle_id", "card", "group", "tag slug", "tag uuid", "name_source", "method"], "rows": sorted(led)})
    m = out["meta"]
    print("scope", m["scope_cards"], "groups", m["groups"], "wide", m["wide_tags_not_groups"], "tag-placed cards", m["cards"], "only wide", m["cards_only_in_groups_over_100"], "tags but no group", m["cards_with_tags_but_no_usable_group"], "no tag", m["cards_with_no_functional_tag"])
    print("figure 6", m["headline"]["with_tag"][:2], "pile", m["pile_before"], "->", m["still_unorganized_after_tag"], "(gap stratum on:", m["still_unorganized_after_tag_with_gap_stratum"], ") recon", m["reconciliation"])
    print("name_source", m["name_source"])


if __name__ == "__main__":
    main()
