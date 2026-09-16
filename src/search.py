"""Effect-level search pipeline.

Index = ONLY glossary entries with a non-empty plain_text. No raw-text
fallback: a card whose every effect is unauthored is unreachable. That is by
design -- coverage equals exactly what has been authored.
"""
import glossary
from aggregate import AGGREGATOR
from embedders import Ensemble, build_embedders, ranks_from_scores


class EffectLevelSearch:
    def __init__(self, cards, entries, embedders=None, aggregator=None):
        self.cards = {c["card_id"]: c for c in cards}
        self.aggregator = aggregator or AGGREGATOR

        self.indexed = [e for e in entries if (e.get("plain_text") or "").strip()]
        self.excluded_entries = [e for e in entries if not (e.get("plain_text") or "").strip()]

        self.effect_to_cards = {e["effect_id"]: list(e["card_ids"]) for e in self.indexed}
        reachable = {c for e in self.indexed for c in e["card_ids"]}
        self.excluded_cards = sorted(set(self.cards) - reachable)

        self.ensemble = Ensemble(embedders if embedders is not None else build_embedders())
        self.ensemble.index([e["effect_id"] for e in self.indexed],
                            [e["plain_text"] for e in self.indexed])

    def search(self, query):
        """Returns per-model card rankings and the fused card ranking.

        Fusion happens at the EFFECT level (RRF over the three effect
        rankings); the fused effect scores are then aggregated to cards.
        Per-model card rankings come from aggregating that single model's
        effect similarities -- same aggregation function, so the breakdown is
        comparable to the fused result.
        """
        res = self.ensemble.query(query)

        fused_cards = self.aggregator(res["fused_scores"], self.effect_to_cards)
        card_ids = sorted(fused_cards)
        fused_ranks = ranks_from_scores(card_ids, [fused_cards[c]["score"] for c in card_ids])

        per_model = {}
        for name, m in res["per_model"].items():
            agg = self.aggregator(m["scores"], self.effect_to_cards)
            ids = sorted(agg)
            per_model[name] = {
                "ranks": ranks_from_scores(ids, [agg[c]["score"] for c in ids]),
                "scores": {c: agg[c]["score"] for c in ids},
                "best_effect": {c: agg[c]["best_effect_id"] for c in ids},
            }

        return {
            "fused_ranks": fused_ranks,
            "fused_scores": {c: fused_cards[c]["score"] for c in card_ids},
            "best_effect": {c: fused_cards[c]["best_effect_id"] for c in card_ids},
            "per_model": per_model,
            "effect_fused_ranks": res["fused_ranks"],
            "excluded_cards": self.excluded_cards,
        }


def load(embedders=None):
    cards = glossary.load_cards()
    entries = glossary.load_glossary()
    return cards, EffectLevelSearch(cards, entries, embedders=embedders)
