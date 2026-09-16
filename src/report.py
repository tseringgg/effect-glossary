"""Run the cluster queries through both pipelines and emit a markdown report."""
import os
import sys

import numpy as np

import baseline
import glossary
import search
from embedders import build_embedders

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(HERE, os.pardir, "reports")

MODELS = ["tfidf", "e5-small-v2", "bge-base-en-v1.5"]

# The three representative queries asked for by the experiment.
PRIMARY = [
    ("a mana dork", "mana_dork"),
    ("a board wipe", "board_wipe"),
    ("a clone effect", "clone"),
]

# Diagnostic paraphrases. The primary queries are MTG jargon; none of the three
# models knows that "board wipe" means mass destruction, so those runs mostly
# measure jargon coverage and drown out the density signal this experiment is
# actually trying to read. These paraphrases say the same thing in ordinary
# English so the density question can be answered separately.
PARAPHRASE = [
    ("a creature that taps for mana", "mana_dork"),
    ("destroy all creatures", "board_wipe"),
    ("copy a creature", "clone"),
]

TARGETS = {
    "mana_dork": ["llanowar_elves", "elvish_mystic", "birds_of_paradise"],
    "board_wipe": ["wrath_of_god", "damnation", "day_of_judgment"],
    "clone": ["clone"],
}


def _fmt(rank):
    return str(rank) if rank else "--"


def _no_signal(embedder_scores):
    """True when this embedder gave every document the same score (no opinion)."""
    v = np.asarray(list(embedder_scores.values()), dtype=float)
    return bool(v.size and float(v.max() - v.min()) < 1e-9)


def run_query(el, bl, by_id, excluded, query, cluster, out):
    w = out.append
    r_el = el.search(query)
    r_bl = bl.search(query)

    w('### Query: "%s"' % query)
    w("")

    flat_el = [m for m in MODELS if _no_signal(r_el["per_model"][m]["scores"])]
    flat_bl = [m for m in MODELS if _no_signal(r_bl["per_model"][m]["scores"])]
    if flat_el or flat_bl:
        w("No lexical signal (every document tied, so the model contributes nothing to "
          "fusion): effect-level %s; baseline %s."
          % (", ".join(flat_el) or "none", ", ".join(flat_bl) or "none"))
        w("")

    w("| Card | Cluster role | EL fused | EL tfidf | EL e5 | EL bge | "
      "BL fused | BL tfidf | BL e5 | BL bge |")
    w("|---|---|---|---|---|---|---|---|---|---|")

    def sort_key(cid):
        return (r_el["fused_ranks"].get(cid, 10 ** 6),
                r_bl["fused_ranks"].get(cid, 10 ** 6), cid)

    for cid in sorted(by_id, key=sort_key):
        c = by_id[cid]
        role = "%s / %s" % (c["cluster"], c["role"])
        if cid in excluded:
            role += " (EXCLUDED)"
        mark = " **<-**" if cid in TARGETS[cluster] else ""
        row = [c["name"] + mark, role, _fmt(r_el["fused_ranks"].get(cid))]
        for m in MODELS:
            row.append(_fmt(r_el["per_model"][m]["ranks"].get(cid)))
        row.append(_fmt(r_bl["fused_ranks"].get(cid)))
        for m in MODELS:
            row.append(_fmt(r_bl["per_model"][m]["ranks"].get(cid)))
        w("| " + " | ".join(row) + " |")
    w("")
    w("`<-` marks the cards this query is supposed to find.")
    w("")
    return r_el, r_bl


def target_ranks(r, cluster):
    return [r["fused_ranks"].get(c) for c in TARGETS[cluster]]


def build_report(stub=False):
    cards = glossary.load_cards()
    entries = glossary.load_glossary()
    by_id = {c["card_id"]: c for c in cards}

    el = search.EffectLevelSearch(cards, entries, embedders=build_embedders(stub=stub))
    bl = baseline.WholeCardBaseline(cards, embedders=build_embedders(stub=stub))
    eff_text = {e["effect_id"]: e for e in entries}
    excluded = el.excluded_cards

    out = []
    w = out.append
    w("# Effect-level search vs whole-card baseline")
    w("")
    n_auth = sum(1 for e in entries if (e.get("plain_text") or "").strip())
    w("Corpus: %d hand-picked cards. Glossary: %d unique effects from %d extractions, "
      "%d authored, %d unauthored." % (len(cards), len(entries), 22, n_auth, len(entries) - n_auth))
    w("")
    w("Embedders: TF-IDF, e5-small-v2, bge-base-en-v1.5%s. RRF with k=60 over 1-based "
      "ranks, ties sharing a rank." % (" (STUBBED -- NOT A VALID RUN)" if stub else ""))
    w("")
    w("`EL` = effect-level pipeline: authored plain_text effects embedded individually, "
      "fused with RRF at the effect level, then aggregated to cards by MAX. "
      "`BL` = whole-card baseline: name/type/cost/oracle text concatenated, no splitting, "
      "no rewording.")
    w("")

    w("## Cards excluded for missing plain_text coverage")
    w("")
    for cid in excluded:
        w("- **%s** -- every extracted effect is unauthored, so it is absent from every "
          "effect-level result. It still appears in the baseline." % by_id[cid]["name"])
    if not excluded:
        w("- none")
    w("")
    w("Unauthored glossary entries:")
    w("")
    for e in entries:
        if not (e.get("plain_text") or "").strip():
            w("- `%s` %r -- cards: %s" % (e["effect_id"], e["raw_text"], ", ".join(e["card_ids"])))
    w("")

    summary = []

    w("## Primary queries (as specified)")
    w("")
    for query, cluster in PRIMARY:
        r_el, r_bl = run_query(el, bl, by_id, excluded, query, cluster, out)
        summary.append((query, cluster, target_ranks(r_el, cluster), target_ranks(r_bl, cluster)))
        w("Top 5 effect-level matches, with the effect that carried each card (MAX rule):")
        w("")
        for cid in sorted(r_el["fused_ranks"], key=lambda c: r_el["fused_ranks"][c])[:5]:
            eid = r_el["best_effect"][cid]
            w("%d. **%s** via `%s` -- %r"
              % (r_el["fused_ranks"][cid], by_id[cid]["name"], eid, eff_text[eid]["plain_text"]))
        w("")

    w("## Diagnostic paraphrase queries")
    w("")
    w("Same corpus and pipelines, the same three intents phrased in ordinary English "
      "instead of MTG jargon.")
    w("")
    for query, cluster in PARAPHRASE:
        r_el, r_bl = run_query(el, bl, by_id, excluded, query, cluster, out)
        summary.append((query, cluster, target_ranks(r_el, cluster), target_ranks(r_bl, cluster)))

    w("## Summary: ranks of the cards each query should find")
    w("")
    w("| Query | Target cards | Effect-level ranks | Baseline ranks |")
    w("|---|---|---|---|")
    for query, cluster, el_r, bl_r in summary:
        names = ", ".join(by_id[c]["name"] for c in TARGETS[cluster])
        w("| %s | %s | %s | %s |"
          % (query, names,
             ", ".join(_fmt(r) for r in el_r), ", ".join(_fmt(r) for r in bl_r)))
    w("")
    return "\n".join(out) + "\n"


def main():
    stub = "--stub" in sys.argv
    text = build_report(stub=stub)
    os.makedirs(REPORTS, exist_ok=True)
    path = os.path.join(REPORTS, "results-stub.md" if stub else "results.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("wrote %s" % path)
    if not stub:
        emit_json()



def emit_json(stub=False):
    """Machine-readable dump of every rank in the report, for downstream views."""
    import json
    cards = glossary.load_cards()
    entries = glossary.load_glossary()
    el = search.EffectLevelSearch(cards, entries, embedders=build_embedders(stub=stub))
    bl = baseline.WholeCardBaseline(cards, embedders=build_embedders(stub=stub))
    doc = {
        "cards": {c["card_id"]: {k: c[k] for k in
                                 ("name", "type_line", "mana_cost", "oracle_text",
                                  "cluster", "role")} for c in cards},
        "excluded_cards": el.excluded_cards,
        "targets": TARGETS,
        "queries": [],
    }
    for query, cluster in PRIMARY + PARAPHRASE:
        r_el, r_bl = el.search(query), bl.search(query)
        doc["queries"].append({
            "query": query, "cluster": cluster,
            "primary": (query, cluster) in PRIMARY,
            "el": {"fused": r_el["fused_ranks"],
                   "models": {m: r_el["per_model"][m]["ranks"] for m in MODELS},
                   "best_effect": r_el["best_effect"],
                   "no_signal": [m for m in MODELS
                                 if _no_signal(r_el["per_model"][m]["scores"])]},
            "bl": {"fused": r_bl["fused_ranks"],
                   "models": {m: r_bl["per_model"][m]["ranks"] for m in MODELS},
                   "no_signal": [m for m in MODELS
                                 if _no_signal(r_bl["per_model"][m]["scores"])]},
        })
    doc["effects"] = {e["effect_id"]: {"raw_text": e["raw_text"],
                                       "plain_text": e["plain_text"],
                                       "occurrence_count": e["occurrence_count"],
                                       "card_ids": e["card_ids"]} for e in entries}
    path = os.path.join(REPORTS, "results.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    print("wrote %s" % path)

if __name__ == "__main__":
    main()
