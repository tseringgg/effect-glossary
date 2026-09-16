"""Whole-card baseline: plain concatenation of name / type / cost / oracle text.

No effect splitting, no plain-language rewording, no aggregation. Same three
embedders, same RRF fusion, so the only variable versus the effect-level
pipeline is the document unit and its wording.
"""
import glossary
from embedders import Ensemble, build_embedders


def card_document(card):
    parts = [card["name"], card["type_line"], card["mana_cost"], card["oracle_text"]]
    return "\n".join(p for p in parts if p)


def card_document_no_name(card):
    """The same document with the card's own name removed.

    The name lets the baseline win by literal string match -- a card called
    Clone ranking first for "a clone effect" is not semantic understanding.
    Stripping it is what makes the comparison against effect-level fair, since
    effects are deduplicated across cards and so can never carry a name.
    """
    parts = [card["type_line"], card["mana_cost"], card["oracle_text"]]
    return "\n".join(p for p in parts if p)


class WholeCardBaseline:
    def __init__(self, cards, embedders=None, document_fn=None):
        self.cards = list(cards)
        self.document_fn = document_fn or card_document
        self.ensemble = Ensemble(embedders if embedders is not None else build_embedders())
        self.ensemble.index([c["card_id"] for c in self.cards],
                            [self.document_fn(c) for c in self.cards])

    def search(self, query):
        res = self.ensemble.query(query)
        return {
            "fused_ranks": res["fused_ranks"],
            "fused_scores": res["fused_scores"],
            "per_model": {n: {"ranks": m["ranks"], "scores": m["scores"]}
                          for n, m in res["per_model"].items()},
        }


def load(embedders=None):
    cards = glossary.load_cards()
    return cards, WholeCardBaseline(cards, embedders=embedders)
