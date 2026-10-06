#!/usr/bin/env python3
"""Extra probe cuts (investigation only) -> build/ability_probe_extra.json.

  A. How many rescues are SPECIFIC (>= 3 tokens, leaf <= 300 cards) vs GENERIC (a bare single
     token such as eff:Draw / eff:Token / eff:Mana, or a leaf of >= 500 cards)?
  B. Rescued abilities that the condition-drop detector flags individually.
  C. Modal spells: modes are separate ability items, so "all abilities >= 0.90" is not meaningful.
  D. Placement multiplicity: into how many distinct leaves would a card land?
"""
import collections
import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap  # noqa: E402

BUILD = ap.BUILD
GENERIC_LEAF = 500
SPECIFIC_LEAF = 300


def main():
    sp = ap.Space()
    L = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    probe = ap.jl("ability_probe.json")
    rec_chunk = P["recovered"]["chunk"]
    flagged = collections.defaultdict(set)
    for h in ap.jl("condition_drops.json"):
        flagged[h["oid"]].add((h["bucket"], h["idx"]))
    best_face = {}
    for x in P["review_queue"]:
        if x["card"] not in best_face or x["similarity"] > best_face[x["card"]]["similarity"]:
            best_face[x["card"]] = x

    def entry_of(fid):
        return sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]

    cards = []
    for m in probe["group2_cards"]:
        e = entry_of(best_face[m["oid"]]["face"])
        items = ap.ability_items(e)
        toks = [[k for k in sorted(t) if k in sp.vocab] for *_, t in items]
        leaf, sc, _ = sp.score(toks)
        cards.append((m, e, items, toks, leaf, sc))

    def kind(tok, l, s):
        if not tok or s < 0.90:
            return None
        size = sp.leaf_size[l]
        if len(tok) == 1 or size >= GENERIC_LEAF:
            return "generic"
        if len(tok) >= 3 and size <= SPECIFIC_LEAF:
            return "specific"
        return "middling"

    bands = [("0.70-0.80", 0.70, 2.0), ("0.50-0.70", 0.50, 0.70), ("<0.50", -1, 0.50), ("all", -1, 2.0)]
    out = {"definitions": {"generic": "ability has exactly 1 token, or its best leaf has >= %d cards" % GENERIC_LEAF,
                           "specific": ">= 3 tokens and best leaf <= %d cards" % SPECIFIC_LEAF,
                           "middling": "everything else that scores >= 0.90"}}
    for name, lo, hi in bands:
        sel = [c for c in cards if lo <= c[0]["blended"] < hi]
        agg = collections.Counter()
        abil = collections.Counter()
        for m, e, items, toks, leaf, sc in sel:
            ks = [k for k in range(len(items)) if toks[k]]
            kinds = [kind(toks[k], int(leaf[k]), float(sc[k])) for k in ks]
            good = [kd for kd in kinds if kd]
            for kd in good:
                abil[kd] += 1
            if good:
                agg["rescued"] += 1
                if "specific" in good:
                    agg["rescued_with_>=1_specific_ability"] += 1
                elif "middling" in good:
                    agg["rescued_best_is_middling_no_specific"] += 1
                else:
                    agg["rescued_only_by_generic_matches"] += 1
            if len(ks) >= 2 and all(kinds):
                agg["all_abilities_>=0.90"] += 1
                if all(kd == "specific" for kd in kinds):
                    agg["all_abilities_>=0.90_all_specific"] += 1
                if any(kd == "generic" for kd in kinds):
                    agg["all_abilities_>=0.90_but_some_generic"] += 1
            nleaf = len({int(leaf[k]) for k in ks if sc[k] >= 0.90})
            agg[f"distinct_leaves_{min(nleaf, 4)}"] += 1
            modal = bool(e.get("modal")) or bool(e.get("mode_abilities")) or any(
                it.get("modal") for *_, it in [(b, i, it) for b, i, it, _ in items])
            if modal:
                agg["modal_cards"] += 1
                if good:
                    agg["modal_cards_rescued"] += 1
        out[name] = {"cards": len(sel), **dict(agg), "rescuing_abilities": dict(abil)}
    # B: abilities individually flagged by the detector among the >= 0.90 rescuers
    tot = fl = cardsfl = 0
    for m, e, items, toks, leaf, sc in cards:
        any_fl = False
        for k, (b, i, it, t) in enumerate(items):
            if toks[k] and sc[k] >= 0.90:
                tot += 1
                if (b, i) in flagged.get(m["oid"], ()):
                    fl += 1
                    any_fl = True
        cardsfl += any_fl
    out["rescuing_abilities_individually_flagged_by_detector"] = {"rescuing_abilities": tot, "flagged": fl, "cards": cardsfl}
    # the top bare-token leaves by rescue count
    top = collections.Counter()
    for m, e, items, toks, leaf, sc in cards:
        for k in range(len(items)):
            if toks[k] and sc[k] >= 0.90 and len(toks[k]) == 1:
                top[(int(leaf[k]), toks[k][0])] += 1
    out["bare_single_token_rescues_by_token"] = [[l, t, n, int(sp.leaf_size[l])] for (l, t), n in top.most_common(8)]
    with io.open(os.path.join(BUILD, "ability_probe_extra.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
