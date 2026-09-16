"""Extract, dedupe, and zone-label the full Scryfall Oracle corpus.

Reuses the existing pipeline UNCHANGED:
  extract_effects.extract_effects  structural splitting
  glossary.build                   exact-match dedup on normalized raw_text
  classify_zones.classify          zone + battlefield sub-tag rules

Two deliberate differences from the 30-card glossary, both about I/O, not logic:

  * Zones are classified on raw_text ONLY -- classify(raw_text, "") -- for
    every effect, including the handful with authored plain_text. At corpus
    scale plain_text exists for ~0.1% of effects; letting it feed labels would
    make those few rows follow a different rule than the other 99.9%.
  * Output is JSON (data/full/effects.json), not YAML. Same fields as
    effects.yaml; PyYAML at tens of thousands of entries is slow to write and
    the file is never hand-edited.

plain_text is carried over by effect_id from data/effects.yaml (read-only) for
the already-authored effects; everything else stays empty. No authoring.
"""
import json
import os
import time
from collections import Counter

import classify_zones as cz
import glossary
from extract_effects import extract_effects

HERE = os.path.dirname(os.path.abspath(__file__))
FULL = os.path.join(HERE, os.pardir, "data", "full")
CARDS_PATH = os.path.join(FULL, "cards.jsonl")
EFFECTS_PATH = os.path.join(FULL, "effects.json")
STATS_PATH = os.path.join(FULL, "stats.json")
REPORT_PATH = os.path.join(HERE, os.pardir, "reports", "zone-distribution-full.md")

# Layouts that are not traditional Magic cards: token/emblem objects and the
# casual-variant cards (Planechase, Archenemy, Vanguard). Kept in the corpus;
# reported separately so their share of effects is visible.
NON_TRADITIONAL = {"token", "double_faced_token", "emblem", "planar", "scheme", "vanguard", "art_series"}

SMALL_SAMPLE = {"effects": 34, "battlefield": 28}


def load_cards():
    with open(CARDS_PATH, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def pct(n, d):
    return 100.0 * n / d if d else 0.0


def main():
    t0 = time.time()
    cards = load_cards()
    chunks_total = sum(len(extract_effects(c["oracle_text"])) for c in cards)
    cards_with_effects = sum(1 for c in cards if c["oracle_text"])

    entries = glossary.build(cards)
    t_build = time.time() - t0

    authored = {e["effect_id"]: e["plain_text"] for e in glossary.load_glossary() if e.get("plain_text")}
    carried = 0
    for e in entries:
        if e["effect_id"] in authored:
            e["plain_text"] = authored[e["effect_id"]]
            carried += 1
        e["zones"] = cz.classify(e["raw_text"], "")[0]
    t_total = time.time() - t0

    with open(EFFECTS_PATH, "w", encoding="utf-8") as fh:
        json.dump({"effects": entries}, fh, ensure_ascii=False)

    # ---- distribution ----
    n = len(entries)
    occ_total = sum(e["occurrence_count"] for e in entries)
    tag_unique = Counter(t for e in entries for t in e["zones"])
    tag_occ = Counter()
    for e in entries:
        for t in e["zones"]:
            tag_occ[t] += e["occurrence_count"]
    empty = [e for e in entries if not e["zones"]]
    n_top = Counter(len(cz.top_level(e["zones"])) for e in entries)
    bf_sub = Counter(tuple(t for t in e["zones"] if t in cz.BATTLEFIELD_SUBTAGS)
                     for e in entries if "battlefield" in e["zones"])

    layout = {c["card_id"]: c["layout"] for c in cards}
    name = {c["card_id"]: c["name"] for c in cards}
    only_nontrad = sum(1 for e in entries if all(layout[c] in NON_TRADITIONAL for c in e["card_ids"]))
    singletons = sum(1 for e in entries if e["occurrence_count"] == 1)
    # Oracle text names the card itself ("Lightning Bolt deals 3 damage..."),
    # so exact-match dedup cannot merge otherwise-identical effects across cards.
    self_named = sum(1 for e in entries if e["occurrence_count"] == 1
                     and name[e["card_ids"][0]].split(" // ")[0].lower() in e["raw_text"].lower())

    stats = {
        "cards_ingested": len(cards), "cards_with_oracle_text": cards_with_effects,
        "effect_chunks_extracted": chunks_total, "card_effect_occurrences": occ_total,
        "unique_effects": n, "singleton_effects": singletons, "singleton_effects_naming_own_card": self_named,
        "effects_only_on_non_traditional_layouts": only_nontrad,
        "authored_plain_text_carried_over": carried, "authored_plain_text_in_small_sample": len(authored),
        "zones_unique": {t: tag_unique[t] for t in cz.ALL_TAGS},
        "zones_occurrence_weighted": {t: tag_occ[t] for t in cz.ALL_TAGS},
        "zone_less_unique": len(empty), "top_level_zone_count_histogram": dict(sorted(n_top.items())),
        "battlefield_subtag_combinations": {"+".join(k) or "(none)": v for k, v in bf_sub.most_common()},
        "build_seconds": round(t_build, 1), "total_seconds": round(t_total, 1),
    }
    with open(STATS_PATH, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2)

    lines = []
    w = lines.append
    w("# Full-corpus zone distribution\n")
    w("Generated by `src/build_full_glossary.py` from `data/full/cards.jsonl`. "
      "Zones classified on raw_text only.\n")
    w("## Scale\n")
    w("| | |\n|---|---:|")
    w("| cards ingested (Scryfall oracle_cards) | %d |" % len(cards))
    w("| cards with oracle text | %d |" % cards_with_effects)
    w("| effect chunks extracted | %d |" % chunks_total)
    w("| card-effect occurrences after per-card dedup | %d |" % occ_total)
    w("| unique deduped effects | %d |" % n)
    w("| unique effects on exactly one card | %d (%.1f%%) |" % (singletons, pct(singletons, n)))
    w("| ...of which name their own card | %d |" % self_named)
    w("| unique effects only on tokens/emblems/planes/schemes/vanguards | %d (%.1f%%) |"
      % (only_nontrad, pct(only_nontrad, n)))
    w("| authored plain_text carried over | %d of %d |\n" % (carried, len(authored)))
    w("## Zones\n")
    w("| zone | unique effects | % of unique | card occurrences | % of occurrences |")
    w("|---|---:|---:|---:|---:|")
    for t in cz.ALL_TAGS:
        w("| %s | %d | %.1f%% | %d | %.1f%% |" % (t, tag_unique[t], pct(tag_unique[t], n),
                                               tag_occ[t], pct(tag_occ[t], occ_total)))
    empty_occ = sum(e["occurrence_count"] for e in empty)
    w("| **zones: []** | %d | %.1f%% | %d | %.1f%% |\n" % (len(empty), pct(len(empty), n),
                                                         empty_occ, pct(empty_occ, occ_total)))
    w("Battlefield on the 30-card sample: %d/%d = %.1f%%. Full corpus: %.1f%% of unique effects.\n"
      % (SMALL_SAMPLE["battlefield"], SMALL_SAMPLE["effects"],
         pct(SMALL_SAMPLE["battlefield"], SMALL_SAMPLE["effects"]), pct(tag_unique["battlefield"], n)))
    w("## Top-level zones per effect\n")
    w("| zones | effects |\n|---:|---:|")
    for k, v in sorted(n_top.items()):
        w("| %d | %d |" % (k, v))
    w("\n## Battlefield sub-tag combinations\n")
    w("| combination | effects |\n|---|---:|")
    for k, v in bf_sub.most_common():
        w("| %s | %d |" % ("+".join(x.split(":")[1] for x in k), v))
    w("\n## Most common zone-less effects\n")
    w("| occurrences | raw_text |\n|---:|---|")
    for e in sorted(empty, key=lambda e: -e["occurrence_count"])[:40]:
        w("| %d | %s |" % (e["occurrence_count"], e["raw_text"].replace("|", "\\|").replace("\n", " ")))
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("\n".join(lines))
    print("\nbuild %.1fs, total %.1fs -> %s" % (t_build, t_total, os.path.normpath(EFFECTS_PATH)))


if __name__ == "__main__":
    main()
