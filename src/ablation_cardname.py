"""Ablation: how much of the whole-card baseline's strength on jargon queries
comes from the CARD NAME, which the effect-level pipeline discards entirely?

Runs the baseline over three document variants and reports where the target
cards land.
"""
import glossary
from baseline import WholeCardBaseline
from embedders import build_embedders

VARIANTS = {
    "full (name+type+cost+oracle)": lambda c: "\n".join(
        p for p in [c["name"], c["type_line"], c["mana_cost"], c["oracle_text"]] if p),
    "no name (type+cost+oracle)": lambda c: "\n".join(
        p for p in [c["type_line"], c["mana_cost"], c["oracle_text"]] if p),
    "oracle text only": lambda c: c["oracle_text"],
}

CASES = [
    ("a board wipe", ["wrath_of_god", "damnation", "day_of_judgment"]),
    ("a clone effect", ["clone"]),
    ("a mana dork", ["llanowar_elves", "elvish_mystic", "birds_of_paradise"]),
]


def main():
    cards = glossary.load_cards()
    names = {c["card_id"]: c["name"] for c in cards}
    results = {}
    for label, docfn in VARIANTS.items():
        bl = WholeCardBaseline(cards, embedders=build_embedders())
        bl.ensemble.index([c["card_id"] for c in cards], [docfn(c) for c in cards])
        results[label] = {q: bl.search(q)["fused_ranks"] for q, _ in CASES}

    lines = ["# Ablation: does the card name carry the baseline's jargon signal?", ""]
    for query, targets in CASES:
        lines += ['## "%s"' % query, "",
                  "| Baseline document | " + " | ".join(names[t] for t in targets) + " |",
                  "|---" * (len(targets) + 1) + "|"]
        for label in VARIANTS:
            r = results[label][query]
            lines.append("| %s | %s |" % (label, " | ".join(str(r[t]) for t in targets)))
        lines.append("")
    text = "\n".join(lines) + "\n"
    with open("../reports/ablation-cardname.md", "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
