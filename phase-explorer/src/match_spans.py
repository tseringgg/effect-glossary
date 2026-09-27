#!/usr/bin/env python3
"""Where in a card's oracle text each parsed node was matched from.

Reads   build/index.json         entry -> oracle text + chunk
        build/chunks/<n>.json    the parsed structure, incl. each node's
                                 `description`
Writes  build/match_spans.json   entry -> [[start, end, effect_idx], ...]

phase.rs records, per node, a `description`: the clause it matched that node
from. This pass locates that clause back inside the card's own oracle text and
stores the character range, so the pages can show which words the parser
actually consumed and which it passed over.

This is THEIR attribution, not a re-parse and not a guess. We do not have
their regexes; we have the text they say each node came from, and we find it.
Where it cannot be found, the node is counted and reported, never approximated.

The one substitution: `~` is their self-reference token, and modern oracle text
spells it "This creature" (or the card's name on older wordings). A description
of "~ can't be blocked." against text of "This creature can't be blocked." is
the same clause, so a small fixed list of self-references is tried, plus a
bounded wildcard as a last resort. Nothing else is normalised -- no case
folding beyond one exact-case retry, no whitespace repair, no fuzzy matching.

Measured on the full corpus; the run prints the breakdown.
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import leaf_phrases as LP   # noqa: E402  -- effect_of_node + BUCKETS

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


def spans_for(card, text):
    """Non-overlapping (start, end, effect) ranges, plus the misses."""
    found, no_desc, not_found = [], 0, 0
    for bucket in LP.BUCKETS:
        for node in (card.get(bucket) or []):
            desc = node.get("description")
            if not desc:
                no_desc += 1
                continue
            at = locate(desc, text, card.get("name") or "")
            if not at:
                not_found += 1
                continue
            effect = LP.effect_of_node(bucket, node) or bucket
            found.append((at[0], at[1], effect))

    # Two nodes can be attributed to the same clause, or to overlapping ones.
    # Keep the longest at each conflict rather than nesting marks.
    found.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    out = []
    for s in found:
        if out and s[0] < out[-1][1]:
            if (s[1] - s[0]) > (out[-1][1] - out[-1][0]):
                out[-1] = s
            continue
        out.append(s)
    return out, no_desc, not_found


def main():
    index = json.load(io.open(os.path.join(BUILD, "index.json"), encoding="utf-8"))
    rows = index["rows"]
    by_chunk = collections.defaultdict(list)
    for r in rows:
        if r["text"]:
            by_chunk[r["ch"]].append(r)

    effects, eff_idx = [], {}
    spans = {}
    stat = collections.Counter()
    for ch in sorted(by_chunk):
        blob = json.load(io.open(os.path.join(BUILD, "chunks", str(ch) + ".json"),
                                 encoding="utf-8"))
        for r in by_chunk[ch]:
            card = blob.get(r["id"])
            if not card:
                continue
            got, no_desc, not_found = spans_for(card, r["text"])
            stat["nodes located"] += len(got)
            stat["nodes with no description"] += no_desc
            stat["nodes whose text was not found"] += not_found
            if not got:
                stat["entries with nothing highlighted"] += 1
                continue
            enc = []
            for s, e, eff in got:
                if eff not in eff_idx:
                    eff_idx[eff] = len(effects)
                    effects.append(eff)
                enc.append([s, e, eff_idx[eff]])
            spans[r["id"]] = enc
            stat["entries with at least one span"] += 1
        sys.stderr.write("  chunk " + str(ch) + "/63" + chr(10)
                         if ch % 16 == 0 else "")

    doc = {
        "source": "build/index.json + build/chunks/*.json",
        "method": ("each parsed node's own `description` located inside the "
                   "card's oracle text; `~` self-references substituted, "
                   "nothing else normalised; overlapping attributions resolved "
                   "to the longest"),
        "effects": effects,
        "n_entries_with_spans": len(spans),
        "stats": dict(stat),
        "spans": spans,
    }
    with io.open(os.path.join(BUILD, "match_spans.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))

    total_nodes = (stat["nodes located"] + stat["nodes with no description"]
                   + stat["nodes whose text was not found"])
    print("build/match_spans.json")
    print(f"  {len(spans):,} entries carry at least one highlight")
    print(f"  {stat['entries with nothing highlighted']:,} entries carry none")
    for k in ("nodes located", "nodes with no description",
              "nodes whose text was not found"):
        pct = 100 * stat[k] / total_nodes if total_nodes else 0
        print(f"  {stat[k]:>7,}  {pct:5.1f}%  {k}")


if __name__ == "__main__":
    main()
