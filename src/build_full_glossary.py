"""Extract, dedupe, and zone-label the full Scryfall Oracle corpus.

Reuses the existing pipeline UNCHANGED:
  extract_effects.extract_effects  structural splitting
  glossary.build                   exact-match dedup on normalized raw_text
  classify_zones.classify          zone/direction/choice rules

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

zones is now a list of STRUCTURED records ({"zone", "direction", "choice"}),
not flat tag strings -- see classify_zones.py. This script's stats/report code
counts along all three axes: zone, direction, and choice.
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

    # ---- distribution, along all three axes: zone, direction, choice ----
    n = len(entries)
    occ_total = sum(e["occurrence_count"] for e in entries)

    # zone -> counts, split by direction
    by_zone_dir = Counter()       # (zone, direction) -> unique effects
    by_zone_dir_occ = Counter()   # (zone, direction) -> card occurrences
    by_zone_dir_choice = Counter()  # (zone, direction, choice) -> unique effects
    zone_any = Counter()          # zone -> unique effects touching it at all (any direction)
    zone_any_occ = Counter()

    for e in entries:
        zones_here = e["zones"]
        occ = e["occurrence_count"]
        seen_zones = set()
        for r in zones_here:
            key = (r["zone"], r["direction"])
            by_zone_dir[key] += 1
            by_zone_dir_occ[key] += occ
            by_zone_dir_choice[(r["zone"], r["direction"], r["choice"])] += 1
            seen_zones.add(r["zone"])
        for z in seen_zones:
            zone_any[z] += 1
            zone_any_occ[z] += occ

    empty = [e for e in entries if not e["zones"]]
    n_records = Counter(len(e["zones"]) for e in entries)
    choice_counts = Counter(r["choice"] for e in entries for r in e["zones"])
    effects_with_any_choice = sum(1 for e in entries if any(r["choice"] for r in e["zones"]))

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
        "zone_any_direction": {z: zone_any[z] for z in cz.ZONES},
        "zone_by_direction": {
            "%s:%s" % (z, d): by_zone_dir[(z, d)]
            for z in cz.ZONES for d in cz.DIRECTIONS if by_zone_dir[(z, d)]
        },
        "zone_by_direction_choice": {
            "%s:%s:%s" % (z, d, cz.CHOICE_LABEL[c]): by_zone_dir_choice[(z, d, c)]
            for z in cz.ZONES for d in cz.DIRECTIONS for c in cz.CHOICES
            if by_zone_dir_choice[(z, d, c)]
        },
        "effects_with_any_choice": effects_with_any_choice,
        "choice_records": choice_counts[cz.CHOICE], "no_choice_records": choice_counts[cz.NO_CHOICE],
        "zone_less_unique": len(empty), "record_count_histogram": dict(sorted(n_records.items())),
        "build_seconds": round(t_build, 1), "total_seconds": round(t_total, 1),
    }
    with open(STATS_PATH, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2)

    lines = []
    w = lines.append
    w("# Full-corpus zone distribution\n")
    w("Generated by `src/build_full_glossary.py` from `data/full/cards.jsonl`. "
      "Zones classified on raw_text only. Each effect now carries structured "
      "records (`zone`, `direction`, `choice`) instead of flat tag strings -- "
      "see `src/classify_zones.py`.\n")
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

    w("## Zones, by direction\n")
    w("Old flat-tag counts don't tell the whole story any more -- e.g. "
      "\"library: 7,288\" used to mean one thing; now library-as-source and "
      "library-as-destination are separate rows.\n")
    w("| zone | as source | as destination | as reference | any direction |")
    w("|---|---:|---:|---:|---:|")
    for z in cz.ZONES:
        w("| %s | %s | %s | %s | %d (%.1f%%) |" % (
            z,
            by_zone_dir[(z, cz.SOURCE)] or "-", by_zone_dir[(z, cz.DESTINATION)] or "-",
            by_zone_dir[(z, cz.REFERENCE)] or "-", zone_any[z], pct(zone_any[z], n)))
    empty_occ = sum(e["occurrence_count"] for e in empty)
    w("\n| | |\n|---|---:|")
    w("| **zones: []** (unique effects) | %d (%.1f%%) |" % (len(empty), pct(len(empty), n)))
    w("| **zones: []** (card occurrences) | %d (%.1f%%) |\n" % (empty_occ, pct(empty_occ, occ_total)))

    old_battlefield_pct = pct(zone_any["battlefield"], n)
    w("Battlefield on the 30-card sample: %d/%d = %.1f%%. Full corpus: %.1f%% of unique effects "
      "touch battlefield in some direction.\n"
      % (SMALL_SAMPLE["battlefield"], SMALL_SAMPLE["effects"],
         pct(SMALL_SAMPLE["battlefield"], SMALL_SAMPLE["effects"]), old_battlefield_pct))

    w("## Battlefield, broken out (was enters/leaves/static)\n")
    w("| direction | unique effects | % of unique |\n|---|---:|---:|")
    for d, old_name in [(cz.DESTINATION, "enters"), (cz.SOURCE, "leaves"), (cz.REFERENCE, "static")]:
        v = by_zone_dir[("battlefield", d)]
        w("| %s (was battlefield:%s) | %d | %.1f%% |" % (d, old_name, v, pct(v, n)))

    w("\n## Choice: how often is there a decision point?\n")
    w("| | |\n|---|---:|")
    w("| unique effects with >=1 choice record | %d (%.1f%%) |" % (
        effects_with_any_choice, pct(effects_with_any_choice, n)))
    w("| records with choice=true | %d of %d (%.1f%%) |" % (
        choice_counts[cz.CHOICE], sum(choice_counts.values()), pct(choice_counts[cz.CHOICE], sum(choice_counts.values()))))
    w("\n### Choice broken out by zone + direction (top 12 by choice count)\n")
    w("| zone | direction | no choice | choice | % with choice |")
    w("|---|---|---:|---:|---:|")
    ranked = sorted(
        ((z, d) for z in cz.ZONES for d in cz.DIRECTIONS if by_zone_dir[(z, d)]),
        key=lambda k: -by_zone_dir_choice[(k[0], k[1], cz.CHOICE)])
    for z, d in ranked[:12]:
        no_c = by_zone_dir_choice[(z, d, cz.NO_CHOICE)]
        yes_c = by_zone_dir_choice[(z, d, cz.CHOICE)]
        w("| %s | %s | %d | %d | %.1f%% |" % (z, d, no_c, yes_c, pct(yes_c, no_c + yes_c)))

    w("\n### Mill vs. surveil, the motivating case\n")
    w("| | library:source | library:destination | graveyard:destination |")
    w("|---|---|---|---|")
    def one(pattern):
        import re
        rx = re.compile(pattern, re.I)
        hits = [e for e in entries if rx.search(e["raw_text"])]
        return hits[0] if hits else None
    for label, pat in [("mill (e.g. \"Target player mills four cards.\")", r"^\w[\w \u2014-]* mills? \w+ cards?\.$"),
                       ("surveil (e.g. \"Surveil 2.…\")", r"^Surveil \d")]:
        e = one(pat)
        if not e:
            continue
        by_key = {(r["zone"], r["direction"]): r["choice"] for r in e["zones"]}
        def cell(key):
            if key not in by_key:
                return "-"
            return "choice" if by_key[key] else "no choice"
        w("| %s | %s | %s | %s |" % (
            label, cell(("library", cz.SOURCE)), cell(("library", cz.DESTINATION)),
            cell(("graveyard", cz.DESTINATION))))

    w("\n## Record count per effect\n")
    w("| records | effects |\n|---:|---:|")
    for k, v in sorted(n_records.items()):
        w("| %d | %d |" % (k, v))

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
