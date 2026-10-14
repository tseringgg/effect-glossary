#!/usr/bin/env python3
"""Checks on build/tag_placements.json that read the finished file against the raw tag snapshot and the other layers' files (they do not reuse the generator's grouping code). Exit 1 on a failure.

    python src/check_tag_layer_build.py
"""
import collections
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def main():
    T = jl("tag_placements.json")
    m = T["meta"]
    snap = json.load(io.open(os.path.join(HERE, "data", m["snapshot_file"]), encoding="utf-8"))
    raw = {t["id"]: t for t in snap}
    tent = set(jl("tentative_placements.json")["by_card"])
    A = jl("annotation_placements.json")
    cards = jl("ability_taxonomy_cards.json")["cards"]
    deny = jl("tag_layer_filter.json")
    denied_ids = {d[0] for d in deny["denied"]}
    bad = []

    def check(name, ok, detail=""):
        print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)) if detail else ""))
        if not ok:
            bad.append(name)
    scope = set()
    for g in T["groups"].values():
        scope |= set(g["m"])
    scope |= set(T["no_group"])
    check("the tag file on disk is the one the build used (SHA-1)", hashlib.sha1(open(os.path.join(HERE, "data", m["snapshot_file"]), "rb").read()).hexdigest() == m["snapshot_sha1"])
    check("the scope is the 1,300 cards with no readable ability", len(scope) == 1300 == m["scope_cards"], len(scope))
    check("no tag-layer card is tentative or annotated", not (scope & tent) and not (scope & set(A["by_card"])))
    sizes = [g["cards"] for g in T["groups"].values()]
    check("every group has 5 to 100 cards, and its count equals its member list", all(5 <= g["cards"] <= 100 and g["cards"] == len(g["m"]) for g in T["groups"].values()), (min(sizes), max(sizes)))
    miss = [(tid, o) for tid, g in T["groups"].items() for o in g["m"] if o not in {x["oracle_id"] for x in raw[tid]["taggings"]}] if False else []
    carry = {tid: {x["oracle_id"] for x in raw[tid]["taggings"]} for tid in T["groups"]}
    miss = [(tid, o) for tid, g in T["groups"].items() for o in g["m"] if o not in carry[tid]]
    check("every member of every group carries that tag in the raw snapshot", not miss, miss[:3])
    check("every group's tag has at least 20 taggings in the raw snapshot (the floor)", all(len(raw[tid]["taggings"]) >= 20 for tid in T["groups"]))
    check("no group is a denied tag (the deny list, by UUID)", not (set(T["groups"]) & denied_ids))
    check("no group is a cycle-, art-, name- or other denied-prefix tag", all(not g["slug"].startswith(("cycle-", "art-", "artist-", "watermark-", "flavor-", "name-", "type-errata", "type-addition-", "unique-", "dnd-")) for g in T["groups"].values()))
    check("a card in the data's by_card list is in exactly its groups' member lists", all(set(T["by_card"][o]) == {tid for tid, g in T["groups"].items() if o in g["m"]} for o in T["by_card"]))
    check("the 3 tags over 100 cards are filters, not groups", all(w["cards"] > 100 for w in T["wide"].values()) and not (set(T["wide"]) & set(T["groups"])), len(T["wide"]))
    only_wide = {o for o in T["wide_by_card"] if o not in T["by_card"]}
    check("cards only in the broad tags are not placed (they stay in the pile)", len(only_wide) == m["cards_only_in_groups_over_100"] and not (only_wide & set(T["by_card"])), len(only_wide))
    names = [g["name"] for g in T["groups"].values()]
    check("group names are unique", len(set(names)) == len(names))
    check("every name has a name_source of rule, model_written or user_edit", all(g["name_source"] in ("rule", "model_written", "user_edit") for g in T["groups"].values()), dict(collections.Counter(g["name_source"] for g in T["groups"].values())))
    h = m["headline"]
    check("the first five figures are unchanged", [h[k][0] for k in ("precise", "with_broad", "with_tentative", "with_annotation", "with_gap_stratum")] == [24336, 27590, 29683, 30643, 30803] and h["precise"][1] == 73.3 and h["with_annotation"][1] == 92.3 and h["with_gap_stratum"][1] == 92.8)
    check("the sixth figure is the with-annotation figure plus the tag cards, on its own line", h["with_tag"][0] == h["with_annotation"][0] + m["cards"] and m["cards"] == len(T["by_card"]))
    rc = m["reconciliation"]
    check("placed(with broad) + tentative + annotation + tag + unorganized + not cards = 38,921", rc["sum"] == 38921 and rc["unorganized"] == m["pile_before"] - m["cards"], rc)
    check("with the gap-test stratum on: the 160 gap cards are separate and none is a tag-layer card", m["still_unorganized_after_tag_with_gap_stratum"] == m["pile_before"] - 160 - m["cards"] and not (scope & {o for g in A["groups"].values() for r in g["m"] if r[6] == "g" for o in [r[0]]}))
    led = jl("tag_ledger.json")
    check("the ledger has one row per (card, group) and every method is community_tag", len(led["rows"]) == sum(g["cards"] for g in T["groups"].values()) and {r[6] for r in led["rows"]} == {"community_tag"}, len(led["rows"]))
    text = json.dumps([m["label"], m["badge"]] + [g["name"] for g in T["groups"].values()]).lower()
    check("the wording says community tag, never verified or checked; no 'review queue'", m["label"] == "Grouped by community tag. Not checked against the card's parsed text." and "verified" not in text and "review queue" not in text)
    check("every card in the layer exists in the cards file with text or a no-text reason", all(o in cards for o in scope))
    print("\n%d checks failed" % len(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
