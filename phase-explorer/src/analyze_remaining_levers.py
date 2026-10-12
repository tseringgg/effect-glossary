#!/usr/bin/env python3
"""Lever sizes and their overlap for the remaining Not-yet-organized cards (read-only). Reads build/remaining_breakdown.json, build/remaining_cards.json, build/remaining_reads.json and
build/remaining_subheadings_key.json, adds a "levers" section to build/remaining_breakdown.json. Changes nothing else.

    python src/analyze_remaining_levers.py
"""
import io
import itertools
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


NAME_FAILS = {14: "'Choose a target' does not say what happens (mixed)", 27: "'Other rule changes' does not say what the rule is", 33: "'uncommon cases' does not say what happens (mixed)"}
RENAME_ONLY = ("Continuous effect on this permanent", "Give a creature a different rule", "Give things a different rule, other kinds of target")
FIELD_OR_PARSER = ("Give things a gained effect, other kinds of target", "Give things a gained effect, less common kinds", "A card with several modes",
                   "Put counters, through a replacement effect, less common kinds", "Give things a set power, other kinds of target", "Give things a gained ability",
                   "Cast a card (the zone is not recorded)", "Attach to a creature")


def main():
    out = jl("remaining_breakdown.json")
    cards = jl("remaining_cards.json")
    key = jl("remaining_subheadings_key.json")
    reads = jl("remaining_reads.json")["subheadings"]
    rem = set(cards["primary"])
    # --- catch-all sub-headings
    rows, promotable = [], set()
    union_by = {}
    for s in key["subheadings"]:
        r = reads[str(s["n"])]
        name_ok = s["n"] not in NAME_FAILS
        rule = r["verdict"] != "incoherent" and name_ok and s["eligible_cards"] >= 5 and s["textless_cards"] * 2 <= s["cards"]
        mv = set(cards["r4_sub_cards"]["%s::%s" % (s["gid"], s["sub"])])
        rows.append({"n": s["n"], "group": s["group"], "sub_heading": s["sub"], "cards": s["cards"], "eligible_cards": s["eligible_cards"], "textless_cards": s["textless_cards"], "read": r["verdict"],
                     "what_i_read": r["read"], "name_states_effect": name_ok, "promotable_under_the_existing_rule": rule, "remaining_cards_that_would_move": len(mv),
                     "why_not": "" if rule else NAME_FAILS.get(s["n"], "")})
        if rule:
            promotable |= mv
    other = [s for s in key["all"] if s["sub"] == "Other kinds" or s["eligible_cards"] < 5]
    not_read_cards = set()
    for s in key["all"]:
        k = "%s::%s" % (s["gid"], s["sub"])
        if (s["sub"] == "Other kinds" or s["eligible_cards"] < 5) and k in cards["r4_sub_cards"]:
            not_read_cards |= set(cards["r4_sub_cards"][k])
    out["r4_subheadings"] = {"read": rows, "promotable": sum(1 for r in rows if r["promotable_under_the_existing_rule"]), "cards_moved_by_promoting_them": len(promotable),
                             "of_which_read_as_loose": sum(1 for r in rows if r["promotable_under_the_existing_rule"] and r["read"] == "loose"),
                             "remaining_cards_in_sub_headings_that_cannot_qualify": len(not_read_cards), "of_which_also_in_a_promotable_one": len(not_read_cards & promotable)}
    # --- held groups
    held = out["r5"]["held"]
    gset = lambda pred: set().union(*[set(cards["r5_group_cards"][h["gid"]]) for h in held if pred(h)] or [set()])
    short = lambda h: h["name"].split(" › ", 1)[1]
    L = {}
    L["rename only (coherent or loose, a one-phrase name exists)"] = gset(lambda h: short(h) in RENAME_ONLY)
    L["allow loose backoff residuals (policy)"] = gset(lambda h: h["why"] == "loose and a backoff residual" and h["eligible_cards"] >= 5)
    L["lower the eligible-card minimum from 5 to 3 (policy)"] = gset(lambda h: h["why"] == "fewer than 5 eligible cards" and 3 <= h["eligible_cards"] < 5)
    L["a field or a parser fix (mixed members, text-less, unrecorded)"] = gset(lambda h: short(h) in FIELD_OR_PARSER)
    L["promote the qualifying catch-all sub-headings"] = promotable
    pg = out["r5"]
    # --- dropped-condition lever, pieces (card sets over the remaining cards)
    L["R2: lift or fix every dropped-condition flag, cards that gain a precise placement"] = set(cards["r2_precise"])
    L["R2: ...cards that gain a broad-leaf placement only"] = set(cards["r2_broad_only"])
    L["R2: ...cards that gain a tentative placement only"] = set(cards["r2_tentative_only"])
    names = list(L)
    out["levers"] = {"sizes_remaining_cards": {k: len(v) for k, v in L.items()}, "overlaps": {}}
    for a, b in itertools.combinations(names, 2):
        n = len(L[a] & L[b])
        if n:
            out["levers"]["overlaps"]["%s  &  %s" % (a, b)] = n
    nopar = L["rename only (coherent or loose, a one-phrase name exists)"] | L["allow loose backoff residuals (policy)"] | L["lower the eligible-card minimum from 5 to 3 (policy)"] | promotable
    out["levers"]["union_of_the_four_changes_that_need_no_parser_work_and_no_detector_work"] = len(nopar)
    r2all = L["R2: lift or fix every dropped-condition flag, cards that gain a precise placement"] | L["R2: ...cards that gain a broad-leaf placement only"] | L["R2: ...cards that gain a tentative placement only"]
    out["levers"]["R2_any_gain"] = len(r2all)
    out["levers"]["R2_and_the_four_changes_together"] = len(r2all | nopar)
    out["levers"]["overlap_between_R2_and_the_four_changes"] = len(r2all & nopar)
    primary = cards["primary"]
    byp = {}
    for o in nopar:
        byp[primary[o]] = byp.get(primary[o], 0) + 1
    out["levers"]["the_four_changes_by_the_primary_reason_of_the_cards_they_move"] = byp
    out["levers"]["R2_shape_cards_gaining_precise"] = {k: len(v["precise"]) for k, v in cards["r2_by_shape"].items()}
    with io.open(os.path.join(BUILD, "remaining_breakdown.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print(json.dumps(out["levers"], indent=1))
    print({k: v for k, v in out["r4_subheadings"].items() if k != "read"})


if __name__ == "__main__":
    main()
