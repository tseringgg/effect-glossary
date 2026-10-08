#!/usr/bin/env python3
"""Part 1 of the name cleanup: measurements on the CURRENT names and flags. Reads the built taxonomy; changes nothing.

    python src/probe_names_part1.py   # -> build/ability_taxonomy_names_part1.json

  1  formatting-defect scan over every leaf, node and family name
  2  field-coverage check: for each leaf of 10 or more, does the name mention each signature field that distinguishes it
     from its sibling leaves (same effect-and-verb node)?
  3  "that player": every ability whose parsed player is the triggering player, against what its trigger and its text say

The mention tests (MENTION) are shared with the prototype in src/probe_names_part2.py.
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


# The mention / implied tests live in src/ability_names.py (one copy, shared by the name guard and these checks).
from ability_names import (ret_of, hum, _any, obj_tokens, mention, implied, FIELDS, DEFAULT_SKIP, ZW, MODW, SIGNW, PROPW)  # noqa: E402,F401


# ------------------------------------------------------------------ 1. defect scan
def defect_scan(names, vocab):
    out = collections.defaultdict(list)
    for kind, nm in names:
        base = nm
        if re.search(r"\s{2,}", base):
            out["double space"].append((kind, nm))
        if base[:1].islower():
            out["starts lowercase"].append((kind, nm))
        if re.search(r"\b(\w+) \1\b", base, re.I):
            out["doubled word"].append((kind, nm))
        if "()" in base or base.count("(") != base.count(")"):
            out["empty or unbalanced parentheses"].append((kind, nm))
        if re.search(r"[=|@>]|\bftype\b|\bobj\b|scope:|[a-z]:[A-Za-z]", base):
            out["raw field code"].append((kind, nm))
        if re.search(r"\b[A-Za-z]+[a-z][A-Z][a-z]+\b", base) or re.search(r"\b(p1p1|m1m1|Typed|Fixed|SetDynamic|AddDynamic|GrantTrigger)\b", base):
            out["CamelCase code word"].append((kind, nm))
        if re.search(r"\b(a|an|to|of|and|or|from|into|on|with|then|for)\s*$", base) or base.rstrip().endswith(("—", ",", "-")):
            out["ends mid-phrase (dangling word or dash)"].append((kind, nm))
        if re.search(r"\ba [aeiou]|\ban [bcdfghjklmnpqrstvwxz]", base, re.I):
            out["wrong a/an"].append((kind, nm))
        if re.search(r"\(\w[^()]*\) \(", base):
            out["stacked parentheses"].append((kind, nm))
        if len(base) > 110:
            out["longer than 110 characters"].append((kind, nm))
        if re.search(r"\(variant\)|\(other variants\)| #\d+$", base):
            out["disambiguation suffix ('(variant)', '#2')"].append((kind, nm))
        if re.search(r"\bcant\b|\bdont\b|\bwont\b|\bisnt\b|\bdoesnt\b", base, re.I):
            out["dropped apostrophe"].append((kind, nm))
        for tok in re.findall(r"[A-Za-z][a-z']{3,}", base):
            w = tok.lower()
            if w not in vocab and w.rstrip("s") not in vocab and w not in ALLOW:
                out["word not found in any card text (merged or misspelt?)"].append((kind, nm + "  [" + tok + "]"))
    return out


ALLOW = {"several", "matches", "allow", "mixed", "moving", "restrictions", "elsewhere", "triggering", "isn't", "recorded", "broader", "something", "everything", "variants", "variant", "unprepared", "recipient", "undecidable", "lure",
         "recorded", "isn", "like", "bonus", "subtype", "permanents", "unfinished", "tokens", "flagged", "generic", "conditional"}


def main():
    import ability_names as AN
    ALLOW.update(AN.TEMPLATE_VOCAB)                   # the template's own words (listed in src/ability_names.py)
    T = jl("ability_taxonomy.json")
    L = T["leaves"]
    cards = jl("ability_taxonomy_cards.json")["cards"]
    vocab = set()
    for c in cards.values():
        for w in re.findall(r"[A-Za-z][a-z']{2,}", c["t"] or ""):
            vocab.add(w.lower())
    nodes = {}
    for f in T["families"]:
        for nd in f["nodes"]:
            nodes[nd["id"]] = nd
    names = [("leaf", l["name"]) for l in L.values()] + [("node", n["name"]) for n in nodes.values()] + [("family", f["name"]) for f in T["families"]]
    scan = defect_scan(names, vocab)
    res = {"names_scanned": {"leaf": len(L), "node": len(nodes), "family": len(T["families"])}}
    res["defect_scan"] = {k: {"count": len(v), "examples": [x[1] for x in v[:8]]} for k, v in sorted(scan.items(), key=lambda kv: -len(kv[1]))}
    soft = ("disambiguation suffix ('(variant)', '#2')", "longer than 110 characters", "stacked parentheses")
    hard = {n.split("  [")[0] for k, ns in scan.items() if k not in soft for _, n in ns}
    res["names_with_a_hard_defect"] = len(hard)
    res["names_with_any_defect_incl_soft"] = len(hard | {n for k in soft for _, n in scan.get(k, [])})
    res["hard_defect_names_by_category"] = {k: len({n.split("  [")[0] for _, n in v}) for k, v in scan.items() if k not in soft}
    res["unknown_words"] = dict(collections.Counter(n.split("[")[1].rstrip("]") for k, v in scan.items() if k.startswith("word not found") for _, n in v).most_common())

    # ---- 2. coverage
    by_node = collections.defaultdict(list)
    for lid, l in L.items():
        by_node[l["node"]].append(lid)
    omit, strict = collections.Counter(), collections.Counter()
    omitted, adjusted = {}, {}
    n10 = 0
    for lid, l in L.items():
        if l["abilities"] < 10:
            continue
        n10 += 1
        ft, ret = ret_of(l["sig"])
        sib = [ret_of(L[s]["sig"])[1] for s in by_node[l["node"]] if s != lid]
        miss, adj_miss = [], []
        for f in FIELDS:
            v = ret.get(f, "")
            if not v or (f, v) in DEFAULT_SKIP:
                continue
            vals = {s.get(f, "") for s in sib}
            if sib and vals == {v}:
                continue                      # not distinguishing: every sibling has the same value
            if not mention(f, v, l["name"], ft):
                miss.append("%s=%s" % (f, v))
                strict[f] += 1
                if not implied(ft, ret, f, v, l["name"]):
                    omit[f] += 1
                    adj_miss.append("%s=%s" % (f, v))
        if adj_miss:
            adjusted[lid] = adj_miss
        if miss:
            omitted[lid] = miss
    res["coverage"] = {"leaves_of_10_or_more": n10, "omitting_strict": len(omitted), "omitting_after_allowing_implied_wording": len(adjusted),
                       "by_field_strict": dict(strict.most_common()), "by_field_adjusted": dict(omit.most_common()),
                       "all_remaining": [{"name": L[k]["name"], "n": L[k]["abilities"], "omits": v, "sig": L[k]["sig"].split(" · ", 1)[1][:130]}
                                         for k, v in sorted(adjusted.items(), key=lambda kv: -L[kv[0]]["abilities"])]}
    res["_omitted"] = omitted
    return res


if __name__ == "__main__":
    r = main()
    out = {k: v for k, v in r.items() if not k.startswith("_")}
    with io.open(os.path.join(BUILD, "ability_taxonomy_names_part1.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print(json.dumps({"names_scanned": r["names_scanned"], "names_with_a_hard_defect": r["names_with_a_hard_defect"],
                      "names_with_any_defect_incl_soft": r["names_with_any_defect_incl_soft"], "hard_by_category": r["hard_defect_names_by_category"],
                      "unknown_words": r["unknown_words"],
                      "defect_scan": {k: v["count"] for k, v in r["defect_scan"].items()},
                      "coverage_summary": {k: r["coverage"][k] for k in ("leaves_of_10_or_more", "omitting_strict", "omitting_after_allowing_implied_wording",
                                                                         "by_field_strict", "by_field_adjusted")}}, indent=1, ensure_ascii=False))
    print("\n## remaining omissions (after allowing implied wording)")
    for e in r["coverage"]["all_remaining"]:
        print("  ", e["n"], e["name"][:72], "| OMITS", e["omits"], "|", e["sig"][:70])
