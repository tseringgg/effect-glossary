"""Re-measure the mana-dork cluster now that the slang layer caps gloss injection.

The layer used to append every matching term's gloss. For "a mana dork" that was
two: the mana-dork gloss (creatures tapping for mana) and the `ramp` gloss
(putting lands into play). The e5 diagnostic showed the combined text ranked the
target effect 25th of 31, against 18th for the mana-dork gloss alone -- the land
half was dragging the query embedding away from the cards it was meant to find.

The cap is fixed in mtg-search-v0 but NOT ported to the current project yet; see
that repo's slang.py header. This script measures what the fix buys, so the port
has a number attached to it.

Only the mana-dork query changes. "a board wipe" matched one term before and
after, and "a clone effect" matches nothing, so the other two clusters are
untouched by the cap and are not re-run here.

Query strings below are the real layer's literal output, before and after the
cap, copied rather than imported so this project stays standalone.
"""
import json
import os

import baseline
import glossary
import search
from embedders import build_embedders

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(HERE, os.pardir, "reports")
MODELS = ["tfidf", "e5-small-v2", "bge-base-en-v1.5"]
SHORT = {"tfidf": "tfidf", "e5-small-v2": "e5", "bge-base-en-v1.5": "bge"}

TARGETS = ["llanowar_elves", "elvish_mystic", "birds_of_paradise",
           "fyndhorn_elves", "avacyns_pilgrim", "noble_hierarch"]

MANA_DORK_GLOSS = "a creature that taps to produce mana, accelerating you ahead"
RAMP_GLOSS = ("increases available mana, usually by putting extra lands into play "
              "or adding mana")

# Two families of query. "expanded" is what the layer actually emits (jargon
# kept, gloss appended). "glossed" is the gloss text alone, which is how the
# grid's fairest cell is posed. The cap changes both.
PAIRS = [
    ("expanded", "before (2 glosses)",
     "a mana dork (ramp: %s; mana dork: %s)" % (RAMP_GLOSS, MANA_DORK_GLOSS)),
    ("expanded", "after (1 gloss)",
     "a mana dork (mana dork: %s)" % MANA_DORK_GLOSS),
    ("glossed", "before (2 glosses)", "%s; %s" % (RAMP_GLOSS, MANA_DORK_GLOSS)),
    ("glossed", "after (1 gloss)", MANA_DORK_GLOSS),
]

PIPELINES = [("effect_level", "effect-level"),
             ("baseline_name", "baseline +name"),
             ("baseline_noname", "baseline -name")]


def mean_rank(ranks):
    vals = [ranks.get(c) for c in TARGETS if ranks.get(c)]
    return sum(vals) / float(len(vals)) if vals else None


def run():
    cards = glossary.load_cards()
    entries = glossary.load_glossary()
    engines = {
        "effect_level": search.EffectLevelSearch(cards, entries, embedders=build_embedders()),
        "baseline_name": baseline.WholeCardBaseline(
            cards, embedders=build_embedders(), document_fn=baseline.card_document),
        "baseline_noname": baseline.WholeCardBaseline(
            cards, embedders=build_embedders(), document_fn=baseline.card_document_no_name),
    }

    cells = []
    for family, phase, q in PAIRS:
        cell = {"family": family, "phase": phase, "query": q}
        for pname, _ in PIPELINES:
            r = engines[pname].search(q)
            cell[pname] = {"fused": r["fused_ranks"],
                           "models": {m: r["per_model"][m]["ranks"] for m in MODELS}}
        cells.append(cell)

    doc = {"cards": {c["card_id"]: c["name"] for c in cards},
           "n_cards": len(cards), "targets": TARGETS, "cells": cells}
    with open(os.path.join(REPORTS, "mana_dork_recheck.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    return doc


def markdown(doc):
    names, out = doc["cards"], []
    w = out.append
    w("# Mana dork, re-measured after the slang gloss cap")
    w("")
    w("Only this cluster's query changed. The board-wipe query matched one term "
      "before and after the cap, and the clone query matches nothing, so neither "
      "moves. Ranks are out of %d, lower is better." % doc["n_cards"])
    w("")

    by = {(c["family"], c["phase"]): c for c in doc["cells"]}
    families = ["expanded", "glossed"]
    phases = ["before (2 glosses)", "after (1 gloss)"]

    w("## Cluster means")
    w("")
    w("| Query family | Phase | Effect-level | Baseline +name | Baseline -name |")
    w("|---|---|---|---|---|")
    for f in families:
        for p in phases:
            c = by[(f, p)]
            w("| %s | %s | %s |"
              % (f, p, " | ".join("%.2f" % mean_rank(c[k]["fused"]) for k, _ in PIPELINES)))
    w("")
    for f in families:
        b = mean_rank(by[(f, phases[0])]["effect_level"]["fused"])
        a = mean_rank(by[(f, phases[1])]["effect_level"]["fused"])
        w("- **%s**, effect-level: %.2f -> %.2f (%+.2f)" % (f, b, a, b - a))
    w("")

    # The fair cell, the way the grid poses it. Report the mean AND the spread:
    # the widening round showed a six-card mean can be steered by one card, and
    # here it is again -- pointing the opposite way this time.
    w("## Verdict in the fair cell (glossed query vs baseline -name)")
    w("")
    w("| Phase | Effect-level | Baseline -name | Gap | Mean verdict | Per card | Median delta |")
    w("|---|---|---|---|---|---|---|")
    for p in phases:
        c = by[("glossed", p)]
        el, bl = c["effect_level"]["fused"], c["baseline_noname"]["fused"]
        mel, mbl = mean_rank(el), mean_rank(bl)
        gap = mbl - mel
        verdict = "WIN" if gap >= 1 else ("LOSS" if gap <= -1 else "TIE")
        deltas = sorted(bl[c2] - el[c2] for c2 in TARGETS)
        wins = sum(1 for d in deltas if d > 0)
        ties = sum(1 for d in deltas if d == 0)
        loss = sum(1 for d in deltas if d < 0)
        med = (deltas[2] + deltas[3]) / 2.0
        w("| %s | %.2f | %.2f | %+.2f | **%s** | %dW / %dT / %dL | %+.1f |"
          % (p, mel, mbl, gap, verdict, wins, ties, loss, med))
    w("")
    w("The mean and the spread disagree after the fix, so read both. Effect-level "
      "improves on every one of the six cards. The baseline's larger mean gain "
      "comes almost entirely from a single card, so the mean closes to a tie while "
      "the median card still favours effect-level by two places.")
    w("")

    for f in families:
        w("## %s query" % f)
        w("")
        for p in phases:
            w("- %s: `%s`" % (p, by[(f, p)]["query"]))
        w("")
        for pname, plabel in PIPELINES:
            w("### %s &mdash; %s" % (f, plabel))
            w("")
            head = ["Card"]
            for p in phases:
                head += ["%s fused" % p.split(" ")[0]] + [SHORT[m] for m in MODELS]
            head += ["fused delta"]
            w("| " + " | ".join(head) + " |")
            w("|" + "---|" * len(head))
            for cid in TARGETS:
                row = [names[cid]]
                fused = []
                for p in phases:
                    d = by[(f, p)][pname]
                    fused.append(d["fused"].get(cid))
                    row.append(str(d["fused"].get(cid, "--")))
                    row += [str(d["models"][m].get(cid, "--")) for m in MODELS]
                delta = (fused[0] - fused[1]) if None not in fused else None
                row.append("%+d" % delta if delta is not None else "--")
                w("| " + " | ".join(row) + " |")
            w("")
    return "\n".join(out) + "\n"


def main():
    doc = run()
    path = os.path.join(REPORTS, "mana_dork_recheck.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(markdown(doc))
    print("wrote %s" % path)
    by = {(c["family"], c["phase"]): c for c in doc["cells"]}
    for f in ["expanded", "glossed"]:
        for pname, plabel in PIPELINES:
            b = mean_rank(by[(f, "before (2 glosses)")][pname]["fused"])
            a = mean_rank(by[(f, "after (1 gloss)")][pname]["fused"])
            print("%-9s %-16s %.2f -> %.2f  (%+.2f)" % (f, plabel, b, a, b - a))


if __name__ == "__main__":
    main()
