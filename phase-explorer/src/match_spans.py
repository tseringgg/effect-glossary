#!/usr/bin/env python3
"""Where in a card's oracle text each parsed effect was matched from.

Reads   build/index.json          entry -> oracle text + chunk
        build/chunks/<n>.json     the parsed structure, incl. each node's
                                  `description`
Writes  build/match_spans.json    entry -> [[start, end, effect_idx], ...]
        build/effect_anchors.json effect -> the words learned to recognise it

phase.rs records, per ability, a `description`: the clause it matched that
ability from. Two steps turn that into a highlight:

  1. LOCATE the description inside the card's own oracle text. This is their
     attribution, found verbatim -- not a re-parse, not a guess. The one
     substitution is `~`, their self-reference token, against oracle text
     that spells it "This creature" (or the card's name on older wordings).

  2. NARROW it (src/effect_span.py) to just the top-level effect -- the part
     the clustering actually matched. A description is the whole ability:
     cost, trigger condition, and every chained sub-effect. For Angrath's Fury
     that is "Destroy target creature. Angrath's Fury deals 3 damage to target
     player or planeswalker. You may search ..." -- one span, four effects.
     The clustering reads `node.effect` only, so the match is the first
     sentence and nothing after it.

Narrowing needs to know what a clause of each effect type reads like. That is
learned here, from the corpus, before any narrowing happens: every ability
whose chain has a single link is an unambiguous example of its effect type.
The learned words are written to build/effect_anchors.json so they can be
read and checked rather than trusted. They are only ever used to find
boundaries; the highlighted text is always the card's own.

Both passes are measured and the run prints the breakdown.
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cluster_structural as CS   # noqa: E402  -- the clustering's own matcher
import effect_span as ES           # noqa: E402
import leaf_phrases as LP          # noqa: E402  -- effect_of_node + BUCKETS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")

SELF_REFS = ("This creature", "this creature", "This permanent", "this permanent",
             "This land", "this land", "This artifact", "this artifact",
             "This enchantment", "this enchantment", "This spell", "this spell")


def locate(desc, text, name):
    """(start, end) of `desc` inside `text`, or None. Their words, found -- not fixed."""
    i = text.find(desc)
    if i >= 0:
        return i, i + len(desc)

    if "~" in desc:
        short = name.split(",")[0]
        for sub in (name, short) + SELF_REFS:
            if not sub:
                continue
            cand = desc.replace("~", sub)
            i = text.find(cand)
            if i >= 0:
                return i, i + len(cand)
        # last resort: ~ stands for some short self-reference we did not list
        pat = re.escape(desc).replace(re.escape("~"), r"[^.]{0,40}?")
        m = re.search(pat, text)
        if m:
            return m.start(), m.end()

    i = text.lower().find(desc.lower())
    if i >= 0:
        return i, i + len(desc)
    return None


def effect_type(effect_node):
    return CS.effect_features(effect_node)[0]


def collect(rows):
    """Pass 1: every locatable node, reduced to what narrowing needs.

    Only the node's kind and its chain of effect types are kept, not the node
    itself -- holding every parsed node would keep most of the 68 MB parse in
    memory for no reason.
    """
    by_chunk = collections.defaultdict(list)
    for r in rows:
        if r["text"]:
            by_chunk[r["ch"]].append(r)

    located, stat = [], collections.Counter()
    for ch in sorted(by_chunk):
        blob = json.load(io.open(os.path.join(BUILD, "chunks", str(ch) + ".json"),
                                 encoding="utf-8"))
        for r in by_chunk[ch]:
            card = blob.get(r["id"])
            if not card:
                continue
            name = card.get("name") or ""
            for bucket in LP.BUCKETS:
                for node in (card.get(bucket) or []):
                    desc = node.get("description")
                    if not desc:
                        stat["nodes with no description"] += 1
                        continue
                    at = locate(desc, r["text"], name)
                    if not at:
                        stat["nodes whose text was not found"] += 1
                        continue
                    stat["nodes located"] += 1
                    located.append({
                        "id": r["id"], "name": name, "bucket": bucket,
                        "kind": node.get("kind"), "at": at,
                        "top": LP.effect_of_node(bucket, node),
                        "chain": ES.chain_effects(bucket, node, effect_type),
                    })
        if ch % 16 == 0:
            sys.stderr.write("  read chunk " + str(ch) + "/63" + chr(10))
    return located, stat


def main():
    index = json.load(io.open(os.path.join(BUILD, "index.json"), encoding="utf-8"))
    text_of = {r["id"]: r["text"] for r in index["rows"]}
    located, stat = collect(index["rows"])

    # ---- learn what each effect's own clause reads like
    samples = []
    for n in located:
        if n["top"] and len(n["chain"]) <= 1:
            clause = text_of[n["id"]][n["at"][0]:n["at"][1]]
            s, e, _ = ES.narrow(n["bucket"], {"kind": n["kind"]}, clause,
                                n["top"], n["chain"], {}, name=n["name"])
            samples.append((n["top"], clause[s:e], n["name"]))
    anchors = ES.learn_anchors(samples)

    # ---- narrow every located clause to its top-level effect
    per_entry = collections.defaultdict(list)
    cuts = collections.Counter()
    chars_full = chars_narrow = 0
    for n in located:
        a0, a1 = n["at"]
        clause = text_of[n["id"]][a0:a1]
        s, e, how = ES.narrow(n["bucket"], {"kind": n["kind"]}, clause,
                              n["top"], n["chain"], anchors, name=n["name"])
        for h in how:
            cuts[h] += 1
        chars_full += a1 - a0
        chars_narrow += e - s
        per_entry[n["id"]].append((a0 + s, a0 + e, n["top"] or n["bucket"]))

    # Two abilities can resolve to overlapping text. Keep the longer at each
    # conflict rather than nesting marks.
    effects, eff_idx, spans = [], {}, {}
    for eid in sorted(per_entry):
        found = sorted(per_entry[eid], key=lambda x: (x[0], -(x[1] - x[0]), x[2]))
        kept = []
        for sp in found:
            if kept and sp[0] < kept[-1][1]:
                if (sp[1] - sp[0]) > (kept[-1][1] - kept[-1][0]):
                    kept[-1] = sp
                continue
            kept.append(sp)
        enc = []
        for s, e, eff in kept:
            if eff not in eff_idx:
                eff_idx[eff] = len(effects)
                effects.append(eff)
            enc.append([s, e, eff_idx[eff]])
        spans[eid] = enc

    stat["entries with at least one span"] = len(spans)
    stat["entries with nothing highlighted"] = sum(
        1 for eid, t in text_of.items() if t and eid not in spans)

    doc = {
        "source": "build/index.json + build/chunks/*.json",
        "method": ("each ability's own `description` located in the card's "
                   "oracle text (`~` substituted, nothing else normalised), then "
                   "narrowed to the top-level effect by src/effect_span.py: cost, "
                   "trigger condition and restriction sentences removed, and "
                   "chained sub-effects cut at the first clause that reads as a "
                   "different effect in the chain"),
        "effects": effects,
        "n_entries_with_spans": len(spans),
        "stats": dict(stat),
        "narrowing": {"cuts": dict(cuts), "chars_full": chars_full,
                      "chars_highlighted": chars_narrow},
        "spans": spans,
    }
    with io.open(os.path.join(BUILD, "match_spans.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))

    with io.open(os.path.join(BUILD, "effect_anchors.json"), "w",
                 encoding="utf-8") as fh:
        json.dump({
            "note": ("Words learned, per effect type, from unambiguous "
                     "single-effect clauses (smoothed log-odds, card names "
                     "excluded, at least 3% of that effect's clauses). Used only "
                     "to find where one effect's text ends and the next "
                     "begins; never displayed."),
            "n_training_clauses": len(samples),
            "anchors": anchors,
        }, fh, ensure_ascii=False, indent=1, sort_keys=True)

    total = (stat["nodes located"] + stat["nodes with no description"]
             + stat["nodes whose text was not found"])
    print("build/match_spans.json")
    print(f"  {len(spans):,} entries carry at least one highlight")
    print(f"  {stat['entries with nothing highlighted']:,} entries carry none")
    for k in ("nodes located", "nodes with no description",
              "nodes whose text was not found"):
        pct = 100 * stat[k] / total if total else 0
        print(f"  {stat[k]:>7,}  {pct:5.1f}%  {k}")
    print("  narrowed to the matched effect:")
    for k, v in sorted(cuts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {v:>7,}  {k}")
    print(f"  highlighted characters {chars_full:,} -> {chars_narrow:,} "
          f"({100 * chars_narrow / chars_full:.0f}%)")
    print(f"build/effect_anchors.json  {len(anchors)} effect types, "
          f"learned from {len(samples):,} clauses")


if __name__ == "__main__":
    main()
