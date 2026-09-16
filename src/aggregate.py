"""Effect-score -> card-score aggregation.

This is the ONLY place the aggregation rule lives. v1 is MAX: a card's score is
the score of its single best-matching effect.

SEAM: to try a SUM-based variant later, add `aggregate_sum` with the same
signature and swap the `AGGREGATOR` binding (or pass `aggregator=` through
search.py). Nothing else in the pipeline needs to change -- no caller inspects
effect scores directly.

    def aggregate_sum(effect_scores, effect_to_cards):  # not implemented (out of scope)
        ...
"""


def aggregate_max(effect_scores, effect_to_cards):
    """MAX rule (v1).

    effect_scores:   {effect_id: score}   -- only indexed (authored) effects
    effect_to_cards: {effect_id: [card_id, ...]}

    Returns {card_id: {"score": float, "best_effect_id": str}}.
    Cards with no indexed effect are absent -- that is the no-fallback rule.
    """
    out = {}
    for eid, score in effect_scores.items():
        for cid in effect_to_cards.get(eid, []):
            cur = out.get(cid)
            if cur is None or score > cur["score"]:
                out[cid] = {"score": float(score), "best_effect_id": eid}
    return out


AGGREGATOR = aggregate_max
