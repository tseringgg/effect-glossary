#!/usr/bin/env python3
"""The literal wording behind the effect a leaf was clustered on.

Reads   build/clusters.json      leaf membership
        build/index.json         entry -> chunk lookup
        build/chunks/<n>.json    the parsed structure, incl. each node's
                                 `description` -- the source clause phase.rs
                                 matched that node from
Writes  build/leaf_phrases.json  per leaf: the phrase its cards share, verbatim
        reports/leaf-phrases.md  the same, as a readable table

A leaf's label says WHAT the parser matched, in enum form
("eff:Destroy | tgt:Typed[Creature]@Any"). This says what those cards
literally READ where it matched -- and nothing else on the card.

That last part is the whole point. Scanning a card's full oracle text finds
the most common wording on the card, which is often unrelated boilerplate: a
leaf clustered on `eff:PutCounterAll` reported "You may cast this card face
down as a 2/2 creature for", because every card in it happened to be a
megamorph Dragon. So the text here is not the card's oracle text. It is the
`description` of the specific nodes whose effect type IS the leaf's dominant
effect, found with cluster_structural.py's own `effect_features()` -- the
same function that put the cards in the leaf. The phrase can only come from
the clause the parser actually matched.

Method, and its one judgement call:

  * The leaf's dominant effect is the most common effect type across its
    cards, by the clustering's own extractor. Only nodes carrying THAT effect
    contribute text.
  * Each matched clause is cut at sentence boundaries (`.`, `;`, newline), so
    a phrase can never run across two sentences and read as something no card
    says.
  * Every 2..12-token span is counted ONCE PER CARD, so the count is "how
    many cards say this", not "how many times it occurs".
  * The winner maximises `share_of_leaf x phrase_length`. That balance is the
    judgement call: score by share alone and every leaf reports a two-word
    stub, score by length alone and it reports a long phrase one or two cards
    happen to share. Weighting length harder than linearly was tried and is
    worse -- it picks "Counter target spell unless its controller pays" (38%)
    over "Counter target spell" (99%).
  * The share is always recorded, so a weak phrase is visibly weak.

Runner-ups are kept in the JSON (filtered so two windows onto one sentence do
not both appear), but the pages lead with the first.
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cluster_structural as CS   # noqa: E402  -- reuse its exact matcher

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
REPORTS = os.path.join(HERE, "reports")
OVERRIDES = os.path.join(HERE, "corrections", "leaf_phrases.json")

NMIN, NMAX = 2, 12
BUCKETS = ("abilities", "triggers", "static_abilities", "replacements")
TOP_N = 6

# A phrase may not run across a sentence; `:` is allowed inside one (so
# "{T}: Add {G}" survives) but may not start or end it, which would leave
# a dangling ": Attach to target creature you control".
CLAUSE = re.compile(r"[.\n;]+")
TOKEN = re.compile(r"\{[^}]*\}|[\w'’/+\-]+|:")


def effect_of_node(bucket, node):
    """The effect feature this node contributes, exactly as the clustering saw it.

    Mirrors cluster_structural.card_features()'s dispatch: an ability carries
    its effect directly, a trigger/replacement carries it under `execute`, and
    a static ability has no effect node at all -- its discriminator is `mode`,
    which the clustering records as `static:<Mode>`.
    """
    if bucket == "abilities":
        return CS.effect_features(node.get("effect"))[0]
    if bucket in ("triggers", "replacements"):
        return CS.effect_features((node.get("execute") or {}).get("effect"))[0]
    if bucket == "static_abilities":
        mode = CS.tag(node.get("mode"))
        return f"static:{mode}" if mode else None
    return None


def matched_text(card, effect):
    """The source clauses this card matched `effect` from -- nothing else on it.

    `description` is phase.rs's own record of which text a node came from, so
    this is their attribution, not our guess at it. Nodes without one
    contribute nothing rather than falling back to the whole card.
    """
    out = []
    for bucket in BUCKETS:
        for node in (card.get(bucket) or []):
            if effect_of_node(bucket, node) != effect:
                continue
            desc = node.get("description")
            if desc:
                out.append(desc)
    return out


def dominant_effect(cards):
    """Most common effect type across a leaf, counted once per card."""
    tally = collections.Counter()
    for card in cards:
        seen = set()
        for bucket in BUCKETS:
            for node in (card.get(bucket) or []):
                eff = effect_of_node(bucket, node)
                if eff:
                    seen.add(eff)
        tally.update(seen)
    if not tally:
        return None, 0
    # Explicit tie-break. `most_common` falls back to insertion order, and the
    # counts are fed from a set of strings whose iteration order changes with
    # every process (hash randomisation) -- which made two runs over identical
    # input disagree about a tied leaf's dominant effect, and so about its
    # phrase. Sorting by name on ties makes the build reproducible.
    eff, n = min(tally.items(), key=lambda kv: (-kv[1], kv[0]))
    return eff, n


def card_grams(text):
    """{token tuple: the literal substring it came from} for one card."""
    out = {}
    pos = 0
    for clause in CLAUSE.split(text):
        if not clause.strip():
            continue
        start = text.find(clause, pos)
        pos = start + len(clause)
        toks = [(m.group(0), m.start() + start, m.end() + start)
                for m in TOKEN.finditer(clause)]
        low = [w.lower() for w, _, _ in toks]
        for n in range(NMIN, NMAX + 1):
            for i in range(len(toks) - n + 1):
                if low[i] == ":" or low[i + n - 1] == ":":
                    continue
                key = tuple(low[i:i + n])
                if key not in out:
                    out[key] = text[toks[i][1]:toks[i + n - 1][2]]
    return out


def longest_shared_run(a, b):
    """Length of the longest contiguous token run common to both."""
    best = 0
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while (i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]):
                k += 1
            if k > best:
                best = k
    return best


def near_duplicate(a, b, frac=0.6):
    """Same wording seen through a shifted window?

    Plain containment is not enough: "...sacrifice this creature unless you"
    and "the beginning of your upkeep, sacrifice this creature unless you pay"
    are different spans of one sentence, and listing both says nothing twice.
    Two phrases count as the same if their longest shared run covers most of
    the shorter one.
    """
    return longest_shared_run(a, b) >= frac * min(len(a), len(b))


def pick_form(counter):
    """The literal rendering most cards used, ties broken by the text itself."""
    return min(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0]


def phrases_for(texts, n_cards):
    df = collections.Counter()
    forms = collections.defaultdict(collections.Counter)
    for t in texts:
        grams = card_grams(t)
        df.update(grams.keys())
        for key, literal in grams.items():
            forms[key][literal] += 1

    cands = [(g, k) for g, k in df.items() if k >= 2]
    if not cands:
        return []
    cands.sort(key=lambda x: ((x[1] / n_cards) * len(x[0]), len(x[0]), x[1]),
               reverse=True)

    chosen = []
    for gram, k in cands:
        if any(near_duplicate(gram, c) for c, _ in chosen):
            continue
        chosen.append((gram, k))
        if len(chosen) == TOP_N:
            break
    # The first entry is the score winner -- the phrase this leaf is reported
    # by. The rest are sorted by share so the list reads top-down, rather than
    # in the score order that put the headline first.
    head, rest = chosen[:1], sorted(chosen[1:], key=lambda x: (-x[1], x[0]))
    return [{"phrase": pick_form(forms[g]),
             "n_cards": k,
             "share": round(k / n_cards, 4)} for g, k in head + rest]


def main():
    clusters = json.load(io.open(os.path.join(BUILD, "clusters.json"),
                                 encoding="utf-8"))
    index = json.load(io.open(os.path.join(BUILD, "index.json"),
                              encoding="utf-8"))
    rows = {r["id"]: r for r in index["rows"]}

    members = collections.defaultdict(list)
    for cid, leaf in clusters["cards"].items():
        if leaf >= 0:
            members[leaf].append(cid)

    # Cards come from the chunks, which hold the parsed structure and each
    # node's `description`. Grouped by chunk so each of the 64 is opened once.
    by_chunk = collections.defaultdict(list)
    for cid, leaf in clusters["cards"].items():
        if leaf >= 0 and cid in rows:
            by_chunk[rows[cid]["ch"]].append(cid)
    cards = {}
    for ch, ids in sorted(by_chunk.items()):
        blob = json.load(io.open(os.path.join(BUILD, "chunks", str(ch) + ".json"),
                                 encoding="utf-8"))
        for cid in ids:
            if cid in blob:
                cards[cid] = blob[cid]

    # Hand-written overrides live in corrections/ and are applied on top. They
    # are the editor's wording, not the cards', so they are flagged `edited`
    # and the derived phrase is kept beside them rather than overwritten.
    try:
        overrides = json.load(io.open(OVERRIDES, encoding="utf-8")).get("overrides", {})
    except Exception:
        overrides = {}

    out = {}
    no_match = 0
    for leaf, ids in sorted(members.items()):
        leaf_cards = [cards[i] for i in ids if i in cards]
        effect, n_with_effect = dominant_effect(leaf_cards)
        # Only the clauses this leaf's dominant effect was matched from.
        texts, with_text = [], 0
        for card in leaf_cards:
            got = matched_text(card, effect) if effect else []
            if got:
                with_text += 1
                # newline-joined: CLAUSE treats it as a boundary, so a
                # phrase can never span two separate matched nodes.
                texts.append(chr(10).join(got))
        no_match += len(ids) - with_text
        phrases = phrases_for(texts, len(ids))
        entry = {
            "n_cards": len(ids),
            "effect": effect,
            "n_with_effect": n_with_effect,
            "n_with_matched_text": with_text,
            "phrases": phrases,
        }
        ov = overrides.get(str(leaf))
        if ov and ov.get("phrase"):
            entry["edited"] = ov["phrase"]
            entry["derived"] = phrases[0]["phrase"] if phrases else ""
        out[str(leaf)] = entry
        if len(out) % 100 == 0 or len(out) == len(members):
            sys.stderr.write(str(len(out)) + "/" + str(len(members)) + " leaves" + chr(10))

    doc = {
        "source": "build/clusters.json + build/chunks/*.json",
        "method": ("literal 2-12 token spans taken ONLY from the `description` "
                   "of nodes whose effect type is the leaf's dominant "
                   "effect, matched with cluster_structural.effect_features "
                   "-- the same function that formed the leaf; counted once "
                   "per card, never crossing a sentence boundary; ranked by "
                   "share_of_leaf * phrase_length"),
        "n_leaves": len(out),
        "cards_without_matched_text": no_match,
        "leaves": out,
    }
    with io.open(os.path.join(BUILD, "leaf_phrases.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)

    covered = sum(1 for v in out.values() if v["phrases"])
    edited = sum(1 for v in out.values() if v.get("edited"))
    strong = sum(1 for v in out.values()
                 if v["phrases"] and v["phrases"][0]["share"] >= 0.5)
    with io.open(os.path.join(REPORTS, "leaf-phrases.md"), "w",
                 encoding="utf-8") as fh:
        fh.write("# What the parser matched, in the cards' own words\n\n")
        fh.write(
            "Generated by `src/leaf_phrases.py`. Every phrase here is a verbatim "
            "substring of the clause phase.rs matched the leaf's dominant effect "
            "from — its own `description` field, not the rest of the card. Nothing "
            "is paraphrased. The share is the fraction of that leaf's cards "
            "carrying the phrase.\n\n"
            "Scanning a card's whole oracle text was tried first and was wrong: it "
            "reported the most common wording on the card, which is often unrelated "
            "boilerplate. Restricting to the matched node's own description ties "
            "the phrase to the effect the leaf was actually built on.\n\n")
        fh.write(f"- **{len(out)}** leaves\n")
        fh.write(f"- **{covered}** have a phrase shared by at least 2 cards\n")
        fh.write(f"- **{strong}** have a top phrase carried by at least half "
                 f"the leaf\n")
        fh.write(f"- **{no_match}** clustered cards carry the leaf's effect in a node with "
                 f"no description, and contribute nothing\n\n")
        fh.write("| leaf | cards | effect | phrase (verbatim) | in |\n")
        fh.write("|---:|---:|---|---|---:|\n")
        for leaf, v in sorted(out.items(), key=lambda x: -x[1]["n_cards"]):
            if v.get("edited"):
                fh.write(f"| {leaf} | {v['n_cards']} | `{v['effect']}` | "
                         f"{v['edited']} *(edited by hand)* | — |" + chr(10))
            elif v["phrases"]:
                p = v["phrases"][0]
                txt = p["phrase"].replace("|", "\\|")
                fh.write(f"| {leaf} | {v['n_cards']} | `{v['effect']}` | `{txt}` | "
                         f"{p['n_cards']} ({p['share']*100:.0f}%) |\n")
            else:
                fh.write(f"| {leaf} | {v['n_cards']} | `{v['effect']}` | *(no phrase in 2+ cards)* "
                         f"| — |\n")

    print(f"build/leaf_phrases.json   {len(out)} leaves")
    print(f"reports/leaf-phrases.md   {covered} with a shared phrase, "
          f"{strong} at >=50%")


if __name__ == "__main__":
    main()
