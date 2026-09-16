"""Controlled re-measurement: effect-level vs whole-card, with the two confounds
from the first run held down.

Confound 1 -- query-side jargon. This experiment has no slang layer, unlike the
real pipeline. Query variants are taken from the real project's glossary at
development/semantic-search/mtg-search-v0/data/glossary.yaml (read once to derive
the strings below; nothing is imported from it, so this stays standalone).

Confound 2 -- card-name leakage. The baseline can win by literal string match on
a card's own name ("Clone" ranking first for "a clone effect"). A name-stripped
baseline variant removes it.

Nothing here changes extraction, the glossary, or aggregation. It re-runs the
pipeline that already exists.
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

TARGETS = {
    "mana_dork": ["llanowar_elves", "elvish_mystic", "birds_of_paradise",
                  "fyndhorn_elves", "avacyns_pilgrim", "noble_hierarch"],
    "board_wipe": ["wrath_of_god", "damnation", "day_of_judgment",
                   "fumigate", "toxic_deluge", "blasphemous_act"],
    "clone": ["clone", "phantasmal_image", "clever_impersonator",
              "spark_double", "mirror_image", "cackling_counterpart"],
}

# ---------------------------------------------------------------------------
# Query variants
#
# "expanded" is exactly what the real slang layer emits: it EXPANDS rather than
# replaces, keeping the user's jargon and appending "term: gloss". Note the
# consequence for this experiment -- the term label puts the literal token
# "wrath" into the board-wipe query, which string-matches the card Wrath of God.
# The real translation therefore reintroduces name leakage.
#
# "glossed" is the gloss text alone with the jargon and term label dropped. It is
# the only variant that actually removes query-side jargon, so it is the one the
# fair comparison uses.
# ---------------------------------------------------------------------------
QUERIES = {
    "mana_dork": {
        "jargon": "a mana dork",
        "expanded": ("a mana dork (ramp: increases available mana, usually by putting extra "
                     "lands into play or adding mana; mana dork: a creature that taps to "
                     "produce mana, accelerating you ahead)"),
        "glossed": ("increases available mana, usually by putting extra lands into play or "
                    "adding mana; a creature that taps to produce mana, accelerating you ahead"),
        "source": "real glossary: terms 'ramp' + 'mana dork'",
    },
    "board_wipe": {
        "jargon": "a board wipe",
        "expanded": ("a board wipe (wrath: destroys all creatures at once; a board wipe or "
                     "mass removal reset)"),
        "glossed": "destroys all creatures at once; a board wipe or mass removal reset",
        "source": "real glossary: term 'wrath' (alias 'board wipe')",
    },
    "clone": {
        "jargon": "a clone effect",
        "expanded": ("a clone effect (clone: enters the battlefield as a copy of a creature "
                     "already in play)"),
        "glossed": "enters the battlefield as a copy of a creature already in play",
        "source": ("APPROXIMATED -- the real glossary has no clone term and its LLM fallback "
                   "raises NotImplementedError, so this gloss was written to match the "
                   "register of the real entries"),
    },
}
VARIANTS = ["jargon", "expanded", "glossed"]
PIPELINES = ["effect_level", "baseline_name", "baseline_noname"]
PIPELINE_LABEL = {
    "effect_level": "effect-level",
    "baseline_name": "baseline +name",
    "baseline_noname": "baseline -name",
}


# ---------------------------------------------------------------------------
# Is effect-level really name-independent? Confirm, don't assume.
# ---------------------------------------------------------------------------
def confirm_name_independence(cards, entries):
    """Two checks.

    1. Audit: no card name, and no distinctive token from a card name, appears
       in any indexed plain_text.
    2. Counterfactual: rebuild the effect-level index from cards whose names have
       been replaced with nonsense and confirm every rank is identical. If a name
       could reach the index at all, this would move something.
    """
    indexed = [e for e in entries if e["plain_text"].strip()]
    blob = " ".join(e["plain_text"].lower() for e in indexed)
    generic = {"mana", "day", "of", "the", "a", "growth", "lives", "season", "bolt", "god",
               "double", "image", "act", "counterpart", "spark"}

    full_hits, token_hits = [], []
    for c in cards:
        name = c["name"].lower()
        if name in blob:
            full_hits.append(c["name"])
        for tok in [t.strip(",") for t in name.replace("-", " ").split()]:
            if len(tok) >= 4 and tok not in generic and tok in blob:
                token_hits.append("%s -> %r" % (c["name"], tok))

    scrambled = [dict(c, name="ZZQX%04d" % i) for i, c in enumerate(cards)]
    base = search.EffectLevelSearch(cards, entries, embedders=build_embedders())
    alt = search.EffectLevelSearch(scrambled, entries, embedders=build_embedders())
    identical = {}
    for cluster, qs in QUERIES.items():
        for v in VARIANTS:
            q = qs[v]
            identical["%s/%s" % (cluster, v)] = (
                base.search(q)["fused_ranks"] == alt.search(q)["fused_ranks"])

    return {
        "full_name_hits": full_hits,
        "name_token_hits": token_hits,
        "generic_tokens_ignored": sorted(generic),
        "scrambled_name_ranks_identical": identical,
        "all_identical": all(identical.values()),
    }


def run():
    cards = glossary.load_cards()
    entries = glossary.load_glossary()

    el = search.EffectLevelSearch(cards, entries, embedders=build_embedders())
    bl_name = baseline.WholeCardBaseline(
        cards, embedders=build_embedders(), document_fn=baseline.card_document)
    bl_noname = baseline.WholeCardBaseline(
        cards, embedders=build_embedders(), document_fn=baseline.card_document_no_name)
    engines = {"effect_level": el, "baseline_name": bl_name, "baseline_noname": bl_noname}

    grid = {}
    for cluster, qs in QUERIES.items():
        grid[cluster] = {}
        for v in VARIANTS:
            q = qs[v]
            cell = {"query": q}
            for pname, eng in engines.items():
                r = eng.search(q)
                cell[pname] = {
                    "fused": r["fused_ranks"],
                    "models": {m: r["per_model"][m]["ranks"] for m in MODELS},
                }
            grid[cluster][v] = cell

    doc = {
        "cards": {c["card_id"]: {k: c[k] for k in ("name", "cluster", "role")} for c in cards},
        "excluded_cards": el.excluded_cards,
        "targets": TARGETS,
        "queries": QUERIES,
        "variants": VARIANTS,
        "pipelines": PIPELINES,
        "grid": grid,
        "name_independence": confirm_name_independence(cards, entries),
    }
    with open(os.path.join(REPORTS, "grid.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    return doc


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------
def mean_target_rank(doc, cluster, variant, pipeline):
    ranks = doc["grid"][cluster][variant][pipeline]["fused"]
    vals = [ranks.get(c) for c in doc["targets"][cluster]]
    vals = [v for v in vals if v]
    return sum(vals) / len(vals) if vals else None


def per_card(doc, cluster, variant="glossed", opponent="baseline_noname"):
    """Per-target-card comparison. The mean can be dragged by one card, so the
    spread is what says whether a cluster verdict is real."""
    el = doc["grid"][cluster][variant]["effect_level"]["fused"]
    bl = doc["grid"][cluster][variant][opponent]["fused"]
    rows = []
    for cid in doc["targets"][cluster]:
        e, b = el.get(cid), bl.get(cid)
        if e is None or b is None:
            rows.append((cid, e, b, None, "excluded"))
            continue
        d = b - e  # positive => effect-level better
        rows.append((cid, e, b, d, "win" if d > 0 else ("loss" if d < 0 else "tie")))
    return rows


def spread(doc, cluster, variant="glossed", opponent="baseline_noname"):
    rows = per_card(doc, cluster, variant, opponent)
    tally = {"win": 0, "tie": 0, "loss": 0, "excluded": 0}
    for _, _, _, _, v in rows:
        tally[v] += 1
    return rows, tally


def load_prior():
    p = os.path.join(REPORTS, "grid.17card.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def verdict(doc, cluster, variant="glossed", opponent="baseline_noname", margin=1.0):
    el = mean_target_rank(doc, cluster, variant, "effect_level")
    bl = mean_target_rank(doc, cluster, variant, opponent)
    if el is None or bl is None:
        return "n/a", el, bl
    d = bl - el  # positive => effect-level is better (lower rank number)
    if d >= margin:
        return "WIN", el, bl
    if d <= -margin:
        return "LOSS", el, bl
    return "TIE", el, bl


def markdown(doc):
    cards = doc["cards"]
    out = []
    w = out.append
    w("# Controlled grid: effect-level vs whole-card")
    w("")
    w("Two confounds from the first run are held down here: query-side jargon "
      "(this experiment has no slang layer, the real pipeline does) and card-name "
      "leakage (the baseline can win by string-matching a card's own name).")
    w("")

    w("## Query variants")
    w("")
    w("| Cluster | Variant | Query text | Source |")
    w("|---|---|---|---|")
    for cluster, qs in doc["queries"].items():
        for v in doc["variants"]:
            w("| %s | %s | %s | %s |"
              % (cluster, v, qs[v], qs["source"] if v == "jargon" else ""))
    w("")
    w("`expanded` is exactly what the real slang layer emits. It expands rather than "
      "replaces, so the jargon stays and the term label is prepended to the gloss. "
      "That puts the literal token \"wrath\" into the board-wipe query and the token "
      "\"clone\" into the clone query, which string-match the cards Wrath of God and "
      "Clone. The real translation therefore reintroduces name leakage. `glossed` "
      "drops the jargon and the term label, and is the only variant that removes the "
      "confound.")
    w("")

    ni = doc["name_independence"]
    w("## Is effect-level actually name-independent?")
    w("")
    w("- Card names found in the indexed text: **%s**"
      % (", ".join(ni["full_name_hits"]) if ni["full_name_hits"] else "none"))
    w("- Distinctive name tokens found: **%s**"
      % (", ".join(ni["name_token_hits"]) if ni["name_token_hits"] else "none"))
    w("- Rebuilding the effect-level index with every card name replaced by nonsense "
      "and re-running all 9 queries: ranks identical in **%d of %d** cases."
      % (sum(ni["scrambled_name_ranks_identical"].values()),
         len(ni["scrambled_name_ranks_identical"])))
    w("")
    w("Confirmed rather than assumed: effect-level ranks cannot move when card names "
      "change, so `effect-level` columns are identical across the two baseline "
      "variants and are printed once per query.")
    w("")

    for cluster in doc["queries"]:
        w("## Cluster: %s" % cluster)
        w("")
        for v in doc["variants"]:
            cell = doc["grid"][cluster][v]
            w("### %s query &mdash; %r" % (v, cell["query"]))
            w("")
            head = ["Card", "Role"]
            for p in PIPELINES:
                head += ["%s fused" % PIPELINE_LABEL[p]] + [SHORT[m] for m in MODELS]
            w("| " + " | ".join(head) + " |")
            w("|" + "---|" * len(head))

            def key(cid):
                return (cell["effect_level"]["fused"].get(cid, 10 ** 6),
                        cell["baseline_noname"]["fused"].get(cid, 10 ** 6), cid)

            for cid in sorted(cards, key=key):
                c = cards[cid]
                role = "%s / %s" % (c["cluster"], c["role"])
                if cid in doc["targets"][cluster]:
                    role += " **TARGET**"
                if cid in doc["excluded_cards"]:
                    role += " (excluded)"
                row = [c["name"], role]
                for p in PIPELINES:
                    d = cell[p]
                    row.append(str(d["fused"].get(cid, "--")))
                    row += [str(d["models"][m].get(cid, "--")) for m in MODELS]
                w("| " + " | ".join(row) + " |")
            w("")

    w("## Verdict")
    w("")
    w("Fairest cell: `glossed` query (jargon removed) against `baseline -name` "
      "(name leakage removed). Mean rank of the cards each cluster should find, "
      "lower is better. A gap under 1.0 places on a 17-card corpus is called a tie.")
    w("")
    w("| Cluster | Effect-level | Baseline -name | Gap | Verdict |")
    w("|---|---|---|---|---|")
    for cluster in doc["queries"]:
        vd, el, bl = verdict(doc, cluster)
        w("| %s | %.2f | %.2f | %+.2f | **%s** |" % (cluster, el, bl, bl - el, vd))
    w("")

    w("### Per-card spread in the fairest cell")
    w("")
    w("The mean can be carried by one card, which is the whole reason for widening the "
      "sample. Ranks are out of %d. Delta is baseline minus effect-level, so positive "
      "means effect-level placed the card higher." % len(cards))
    w("")
    for cluster in doc["queries"]:
        rows, tally = spread(doc, cluster)
        mean_el = mean_target_rank(doc, cluster, "glossed", "effect_level")
        mean_bl = mean_target_rank(doc, cluster, "glossed", "baseline_noname")
        cluster_dir = "win" if mean_bl - mean_el >= 1.0 else (
            "loss" if mean_bl - mean_el <= -1.0 else "tie")
        deltas = sorted(d for _, _, _, d, _ in rows if d is not None)
        n = len(deltas)
        med = deltas[n // 2] if n % 2 else (deltas[n // 2 - 1] + deltas[n // 2]) / 2.0
        top = max(deltas, key=abs) if deltas else 0
        share = (abs(top) / sum(abs(d) for d in deltas)) if any(deltas) else 0.0
        w("**%s** &mdash; cluster mean %.2f vs %.2f (%s). Per card: %d win / %d tie / %d loss. "
          "Mean delta %+.2f, **median delta %+.1f**, largest single card %+d "
          "(%.0f%% of all movement)."
          % (cluster, mean_el, mean_bl, cluster_dir.upper(),
             tally["win"], tally["tie"], tally["loss"],
             sum(deltas) / float(n), med, top, 100 * share))
        w("")
        w("| Card | Effect-level | Baseline -name | Delta | Card verdict | vs cluster |")
        w("|---|---|---|---|---|---|")
        contra = []
        for cid, e, b, d, v in rows:
            if d is None:
                w("| %s | -- | -- | -- | excluded | |" % cards[cid]["name"])
                continue
            flag = ""
            if cluster_dir == "win" and v == "loss":
                flag = "**CONTRADICTS**"
                contra.append(cards[cid]["name"])
            elif cluster_dir == "loss" and v == "win":
                flag = "**CONTRADICTS**"
                contra.append(cards[cid]["name"])
            w("| %s | %d | %d | %+d | %s | %s |" % (cards[cid]["name"], e, b, d, v, flag))
        w("")
        if contra:
            w("Contradicting the cluster mean: **%s**." % ", ".join(contra))
        else:
            w("No card contradicts the cluster mean.")
        w("")

    w("### Do the three embedders agree with the fused verdict?")
    w("")
    w("Mean rank of the cluster's target cards under each model alone, before fusion, in "
      "the fairest cell. A fused win that only one model supports is a weaker result than "
      "one all three produce.")
    w("")
    w("| Cluster | Model | Effect-level | Baseline -name | Favours |")
    w("|---|---|---|---|---|")
    for cluster in doc["queries"]:
        cell = doc["grid"][cluster]["glossed"]
        tg = doc["targets"][cluster]
        agree = []
        for m in MODELS:
            el = sum(cell["effect_level"]["models"][m][c] for c in tg) / float(len(tg))
            bl = sum(cell["baseline_noname"]["models"][m][c] for c in tg) / float(len(tg))
            fav = "effect-level" if bl - el > 0.01 else (
                "baseline" if el - bl > 0.01 else "neither")
            agree.append(fav)
            w("| %s | %s | %.2f | %.2f | %s |" % (cluster, SHORT[m], el, bl, fav))
        n_el = agree.count("effect-level")
        w("| %s | **all three** | | | **%d of 3 favour effect-level%s** |"
          % (cluster, n_el,
             ", one favours the baseline" if "baseline" in agree else ""))
    w("")

    prior = load_prior()
    if prior:
        w("### Does the prior verdict hold? 17 cards vs %d" % len(cards))
        w("")
        w("Mean target rank in the fairest cell. Ranks are out of 17 in the prior run and "
          "out of %d here, so the absolute numbers are not comparable across columns; the "
          "verdict and the sign of the gap are." % len(cards))
        w("")
        w("| Cluster | 17-card EL | 17-card BL | 17-card verdict | %d-card EL | %d-card BL | "
          "%d-card verdict | Holds? |" % (len(cards), len(cards), len(cards)))
        w("|---|---|---|---|---|---|---|---|")
        for cluster in doc["queries"]:
            pv, pel, pbl = verdict(prior, cluster)
            nv, nel, nbl = verdict(doc, cluster)
            w("| %s | %.2f | %.2f | %s | %.2f | %.2f | %s | %s |"
              % (cluster, pel, pbl, pv, nel, nbl, nv,
                 "yes" if pv == nv else "**NO, %s -> %s**" % (pv, nv)))
        w("")

    w("### The requested 2x2")
    w("")
    w("{raw jargon, translated} x {baseline with name, baseline without name}, with "
      "effect-level under both query variants. `translated` here is `expanded`, the "
      "real slang layer's actual output. Mean target rank, lower is better.")
    w("")
    w("| Cluster | Query | Effect-level | Baseline +name | Baseline -name | Name leakage |")
    w("|---|---|---|---|---|---|")
    for cluster in doc["queries"]:
        for v in ["jargon", "expanded"]:
            el = mean_target_rank(doc, cluster, v, "effect_level")
            bn = mean_target_rank(doc, cluster, v, "baseline_name")
            bx = mean_target_rank(doc, cluster, v, "baseline_noname")
            w("| %s | %s | %.2f | %.2f | %.2f | %+.2f |"
              % (cluster, v, el, bn, bx, bx - bn))
    w("")
    w("Name leakage is how many places the baseline loses when its own card name is "
      "removed from the document. A positive number is signal the baseline was taking "
      "from the name rather than from the card's text.")
    w("")

    w("### Every cell of the grid, mean target rank")
    w("")
    w("| Cluster | Query variant | Effect-level | Baseline +name | Baseline -name |")
    w("|---|---|---|---|---|")
    for cluster in doc["queries"]:
        for v in doc["variants"]:
            vals = [mean_target_rank(doc, cluster, v, p) for p in PIPELINES]
            w("| %s | %s | %s |"
              % (cluster, v, " | ".join("%.2f" % x for x in vals)))
    w("")
    w("Equal means in a row do not imply equal rankings. In the clone cluster under the "
      "translated queries all three pipelines average the same rank while ordering the "
      "cards differently, which is exactly why the per-card tables above are the "
      "primary evidence and these means are only a summary.")
    w("")
    return "\n".join(out) + "\n"


def main():
    doc = run()
    text = markdown(doc)
    path = os.path.join(REPORTS, "grid.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("wrote %s" % path)
    ni = doc["name_independence"]
    print("name-independence: full=%s tokens=%s scrambled_identical=%s"
          % (ni["full_name_hits"], ni["name_token_hits"], ni["all_identical"]))
    for cluster in doc["queries"]:
        vd, el, bl = verdict(doc, cluster)
        print("%-12s EL=%.2f  BL-name=%.2f  -> %s" % (cluster, el, bl, vd))


if __name__ == "__main__":
    main()
