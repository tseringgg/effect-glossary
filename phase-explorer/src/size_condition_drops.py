#!/usr/bin/env python3
"""Corpus-wide sizing of silent condition drops (KNOWN_LIMITATIONS.md §4).

DETECTION AND SIZING ONLY -- no parser change, no fix. Runs the per-item
detector in detect_condition_drops.py over the whole in-scope corpus (the
34,645 snapshot entries plus the 63 collision-recovered cards), assigns each
flagged item a sub-shape, and writes

    build/condition_drops.json      every flagged item + its sub-shape
    reports/condition-drops.md      the sizing report

Sub-shape is assigned from the *first unsatisfied* clause, by the first rule
that matches (order matters):

    branch-structural      FlipCoin branch followed by an unconditional sub_ability
    nested-wrapper         "only if" + RequiresCondition{condition:null}
    activation-restriction-missing   "only if" + no activation_restrictions entry
    static-level           static_abilities[] item
    embedded-replacement   "If X would Y, Z instead" written inside a spell/trigger/
                           activated ability (replacement semantics, sequential parse)
    replacement-level      replacements[] item
    negative               "if you don't / they didn't ..." (no else/IfYouDo)
    result-dependent       "this way", "if you do/does", "if you win", "if it dies"
    compound               "A or B" / "A and B" inside the condition
    filter-targeting       "<verb> target X if it ..." (restriction on the target)
    trigger-intervening    "When/At ..., if X, ..." on a trigger
    sequential-chain       everything else: a later clause of the chain that
                           should be gated ("Do A. If X, do B.", "Do A if X.",
                           "...if X, B instead.")
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect_condition_drops as D  # noqa: E402

HERE = D.HERE

NEG_RE = re.compile(
    r"^if (?:you|they|he or she|that player|the player|each player|a player|"
    r"its controller|that creature's controller|an opponent|[a-z]+ player) "
    r"(?:don't|doesn't|didn't|do not|does not|did not)\b(?! (?:control|have|own|"
    r"cast (?:a|an|any|two|three|no)\b|play (?:a|an)\b|attack|activate))", re.I)
THIS_WAY_RE = re.compile(
    r"\bthis way\b|\bas a result\b|\bthat way\b|\bexcess damage\b|"
    r"\bif (?:that|the|it|they) [a-z' ]{0,25}?\b(?:dies|died|is destroyed|was destroyed|"
    r"is exiled|was exiled|is countered|was countered|is put into)\b", re.I)
SEARCH_SHUFFLE_RE = re.compile(r"^if you search your library this way", re.I)
OR_MORE_RE = re.compile(r"\bor (?:more|less|fewer|greater|lower|higher|greater|equal)\b", re.I)
# a second condition, not a list inside one property ("rare or mythic rare"):
# the conjunction must introduce a new subject/predicate
CONJ_RE = re.compile(
    r"\b(?:or|and|and/or)\s+(?:if\s+)?(?:you|your|they|it|its|that|this|those|there|"
    r"a|an|the|one|no|each|any|at least|an opponent|another|either)\b|\beither\b", re.I)
INTERVENING_RE = re.compile(r"^(?:when|whenever|at)\b[^,]*,\s*if\b", re.I)


def cond_span(tail):
    """The condition itself: from 'if' to the first comma (the clause head)."""
    return tail.split(",", 1)[0]


def classify(h, item):
    """-> (shape, subtype)"""
    if "STRUCT" in h["short"]:
        return "branch-structural", "FlipCoin sub_ability outside the branch"
    b = h["bucket"]
    unsat = [c for c in h["clause_info"] if c["fam"] in (h["missing"] + h["short"])]
    c = (unsat or h["clause_info"])[0]
    tail, sent, pos = c["tail"], c["sent"], c["pos"]
    # An "Activate only if ..." sentence whose restriction is absent/empty. Decided on the
    # first UNSATISFIED clause being the restriction one (family RESTR), so an ability that
    # also has a separate dropped clause in its body is classified by that clause instead.
    if b == "abilities" and c["fam"] == "RESTR":
        if h["empty_wrapper"]:
            return "nested-wrapper", "RequiresCondition with null condition"
        return "activation-restriction-missing", "'Activate only if' with no restriction at all"
    if b == "static_abilities":
        mode = item.get("mode")
        mode = mode if isinstance(mode, str) else (list(mode)[0] if isinstance(mode, dict) else "?")
        return "static-level", mode
    if b == "replacements":
        if re.search(r"enters? (?:the battlefield )?(?:tapped|with)\b", sent, re.I):
            sub = "enters tapped / with counters if"
        elif item.get("event") == "DamageDone":
            sub = "damage prevention / modification"
        else:
            sub = "other replacement"
        return "replacement-level", sub
    if re.search(r"\bwould\b", cond_span(tail), re.I):
        return "embedded-replacement", "'if X would Y, Z instead' inside an ability"
    if NEG_RE.match(tail):
        before = h["text"].split(c["snip"][:20])[0] if c["snip"][:20] in h["text"] else sent[:pos]
        if re.search(r"\bmay\b|\bpay\b|\bunless\b", sent[:pos] + before[-160:], re.I):
            return "negative", "declined option ('may/pay ... if you don't')"
        return "negative", "negated event/state ('if you didn't ...')"
    if SEARCH_SHUFFLE_RE.match(tail):
        return "result-dependent", "search this way -> shuffle (benign)"
    if c["fam"] == "FLIP":
        return "result-dependent", "if you win/lose"
    if c["fam"] == "DO" or THIS_WAY_RE.search(tail):
        return "result-dependent", "this way / if you do"
    span = OR_MORE_RE.sub(" ", cond_span(tail))
    if CONJ_RE.search(span):
        return "compound", "two conditions joined by or / and"
    prefix = sent[:pos]
    if pos > 0 and re.search(r"\btarget\b[^,.;:]*$", prefix):
        return "filter-targeting", "restriction on the target ('X target Y if it ...')"
    if b == "triggers" and INTERVENING_RE.match(sent):
        return "trigger-intervening", "intervening if"
    if re.search(r"\binstead\b", tail, re.I):
        return "sequential-chain", "if ... instead"
    if pos == 0 or re.match(r"^(?:then|and|also)\s", sent[:pos + 1], re.I) or pos < 8:
        return "sequential-chain", "later sentence 'If X, B.'"
    return "sequential-chain", "inline 'A if X.'"


def load_universe(without=()):
    d = D.load()
    # The universe is what the explorer actually serves: the snapshot WITH the
    # parser-fix overlays applied (same order as build_index.PARSER_FIX_OVERLAYS).
    for name in ("commander-eligibility-fix", "commander-creatures-fix",
                 "unrecognized-restriction-fix", "activation-timing-split-fix"):
        if name in without:
            continue
        path = os.path.join(HERE, "data", "overlay", name + ".json")
        if os.path.exists(path):
            for faces in json.load(open(path, encoding="utf-8"))["cards"].values():
                for face in faces:
                    d[face["name"].lower()] = face
    uni = {}                     # entry key -> entry
    for k, e in d.items():
        uni[k] = e
    rec = json.load(open(os.path.join(HERE, "data", "overlay", "recovered-cards.json"),
                         encoding="utf-8"))["cards"]
    for oid, faces in rec.items():
        for j, f in enumerate(faces):
            f.setdefault("scryfall_oracle_id", oid)
            uni["recovered:%s:%d" % (oid, j)] = f
    idx = {r["key"]: r for r in json.load(open(os.path.join(HERE, "build", "index.json"),
                                               encoding="utf-8"))["rows"]}
    return uni, idx


def main():
    uni, idx = load_universe()
    hits = []
    for key, e in uni.items():
        for h in D.detect_entry(e):
            it = e[h["bucket"]][h["idx"]]
            shape, sub = classify(h, it)
            ir = idx.get(key)
            # "silent" = the card shows `clean` (the §4 definition: 20 silent / 8 visible
            # in the baseline). Soft gaps (unmodelled nodes) / corrections are an
            # overlapping signal, kept separately.
            visible = (ir["q"] != "clean") if ir else D.entry_has_gap(e)
            soft = bool(ir and (ir["sg"] > 0 or ir["corr"] > 0))
            h.update(name=e["name"], oid=e.get("scryfall_oracle_id"), key=key,
                     shape=shape, sub=sub, card_visible=bool(visible), card_soft=soft,
                     recovered=key.startswith("recovered:"),
                     alchemy=e["name"].startswith("A-"))
            hits.append(h)
    out = [{k: v for k, v in h.items() if k != "clause_info"} for h in hits]
    json.dump(out, open(os.path.join(HERE, "build", "condition_drops.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    return uni, hits


if __name__ == "__main__":
    uni, hits = main()
    print(len(hits), "items,", len({h["oid"] for h in hits}), "cards")
