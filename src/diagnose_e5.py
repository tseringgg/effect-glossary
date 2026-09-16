"""Why does e5 rank "tap this permanent to produce one green mana" 25th of 31
for a makes-mana query, when TF-IDF ranks the same effect 3rd?

Read-only. Nothing here is imported by the pipeline; it indexes the same
authored effects with the same embedders and writes reports/e5_diagnostic.json.

Three questions, in order:
  1. Is e5's "query: " / "passage: " prefix convention applied correctly?
     Checked twice -- by reading the wrapper, and by spying on what actually
     reaches model.encode() -- then ablated against no prefixes and swapped
     prefixes, because a code reading is not a measurement.
  2. What does e5 actually rank highly for this query?
  3. What are the raw cosines, not just the ranks? A rank is only as meaningful
     as the score separation underneath it.
"""
import json
import os

import numpy as np

import glossary
from embedders import build_embedders, SentenceTransformerEmbedder

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(HERE, os.pardir, "reports")

TARGET = "eff_3b48c12159"  # "{T}: Add {G}." -> "Tap this permanent to produce one green mana."
GLOSSED = ("increases available mana, usually by putting extra lands into play or "
           "adding mana; a creature that taps to produce mana, accelerating you ahead")

# The glossed query is two glosses joined, because the real slang layer matched
# both "ramp" and "mana dork". Splitting them apart is the whole point: one half
# is about lands, the other about creatures.
QUERY_FORMS = [
    ("full glossed (both glosses joined)", GLOSSED),
    ("mana-dork gloss only",
     "a creature that taps to produce mana, accelerating you ahead"),
    ("ramp gloss only",
     "increases available mana, usually by putting extra lands into play or adding mana"),
    ("makes mana", "makes mana"),
    ("a creature that taps for mana", "a creature that taps for mana"),
    ("tap this creature for green mana", "tap this creature for green mana"),
    ("produces green mana", "produces green mana"),
]


def _rank_of(sims, i):
    return int(np.where(np.argsort(-sims) == i)[0][0]) + 1


def confirm_prefixes(texts):
    """Report the configured prefixes, prove they reach model.encode(), and
    ablate them. If the convention were the bug, 'no prefixes' would be the
    configuration that looks correct."""
    e5 = [e for e in build_embedders() if e.name == "e5-small-v2"][0]
    configured = {"query_prefix": e5.query_prefix, "doc_prefix": e5.doc_prefix}

    e5._load()
    inner, calls = e5._model, []

    class Spy:
        def encode(self, t, **kw):
            calls.append(list(t)[0])
            return inner.encode(t, **kw)

    e5._model = Spy()
    e5.index(texts[:1])
    e5.similarities(GLOSSED)
    e5._model = inner

    ablation = {}
    for label, qp, dp in [("shipped", "query: ", "passage: "),
                          ("none", "", ""),
                          ("swapped", "passage: ", "query: ")]:
        m = SentenceTransformerEmbedder("e5", "intfloat/e5-small-v2", qp, dp)
        m.index(texts)
        sims = np.asarray(m.similarities(GLOSSED), dtype=float)
        ablation[label] = {"query_prefix": qp, "doc_prefix": dp,
                           "target_rank": _rank_of(sims, TARGET_I),
                           "target_cos": float(sims[TARGET_I]),
                           "range": float(sims.max() - sims.min())}
    return {"configured": configured,
            "encoded_doc_example": calls[0],
            "encoded_query_example": calls[1],
            "correct": (configured["query_prefix"] == "query: "
                        and configured["doc_prefix"] == "passage: "
                        and calls[0].startswith("passage: ")
                        and calls[1].startswith("query: ")),
            "ablation": ablation}


def main():
    global TARGET_I
    entries = [e for e in glossary.load_glossary() if e["plain_text"].strip()]
    ids = [e["effect_id"] for e in entries]
    texts = [e["plain_text"] for e in entries]
    TARGET_I = ids.index(TARGET)

    prefixes = confirm_prefixes(texts)

    embs = build_embedders()
    for e in embs:
        e.index(texts)
    by_name = {e.name: e for e in embs}

    # Q3: score separation per model. A rank means little without it.
    spread = {}
    for e in embs:
        s = np.asarray(e.similarities(GLOSSED), dtype=float)
        spread[e.name] = {
            "max": float(s.max()), "min": float(s.min()),
            "range": float(s.max() - s.min()), "stdev": float(s.std()),
            "relative_range": float((s.max() - s.min()) / s.max()) if s.max() else 0.0,
            "target_rank": _rank_of(s, TARGET_I), "target_score": float(s[TARGET_I]),
        }

    # Q2: what e5 actually likes, with the text so it can be judged.
    s5 = np.asarray(by_name["e5-small-v2"].similarities(GLOSSED), dtype=float)
    order = np.argsort(-s5)
    raw = {e["effect_id"]: e["raw_text"] for e in entries}
    top = [{"pos": p, "effect_id": ids[i], "cos": float(s5[i]),
            "raw_text": raw[ids[i]], "plain_text": texts[i]}
           for p, i in enumerate(order[:10], 1)]
    tr = spread["e5-small-v2"]["target_rank"]
    neighbours = {
        "gap_to_top": float(s5[order[0]] - s5[TARGET_I]),
        "gap_to_one_above": float(s5[order[tr - 2]] - s5[TARGET_I]),
        "percentile_in_range": float(100 * (s5[TARGET_I] - s5.min()) / (s5.max() - s5.min())),
        "all_sorted": [round(float(x), 4) for x in np.sort(s5)[::-1]],
    }

    # Is it the query rather than the target? Vary the query, hold all else.
    forms = []
    for label, q in QUERY_FORMS:
        row = {"label": label, "query": q}
        for e in embs:
            s = np.asarray(e.similarities(q), dtype=float)
            row[e.name] = {"target_rank": _rank_of(s, TARGET_I),
                           "target_cos": float(s[TARGET_I]), "top_cos": float(s.max())}
        forms.append(row)

    doc = {"target_effect_id": TARGET, "target_plain_text": texts[TARGET_I],
           "target_raw_text": raw[TARGET], "n_indexed": len(ids),
           "glossed_query": GLOSSED, "prefixes": prefixes, "spread": spread,
           "e5_top10": top, "target_vs_field": neighbours, "query_forms": forms}
    path = os.path.join(REPORTS, "e5_diagnostic.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    print("wrote %s" % path)
    print("prefix convention correct: %s" % prefixes["correct"])
    for k, v in prefixes["ablation"].items():
        print("  ablation %-8s target rank %2d  cos %.4f" % (k, v["target_rank"], v["target_cos"]))
    for n, v in spread.items():
        print("  %-18s range %.4f (%.1f%% of max)  target #%d"
              % (n, v["range"], 100 * v["relative_range"], v["target_rank"]))
    return doc


if __name__ == "__main__":
    main()
