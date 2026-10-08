#!/usr/bin/env python3
"""Automated name checks on the BUILT taxonomy (the names the tester sees). Measurement only.

    python src/check_names_build.py   # -> build/ability_taxonomy_names_final_check.json

  defect scan        formatting defects over leaf, node and family names (allow-list = ability_names.TEMPLATE_VOCAB)
  claims check       a name must not state a verb / negation / modal that fewer than half of the members' text says
  coverage check     does a leaf of 10+ state each field that distinguishes it from its siblings
  minority check     a >=10% minority of members differing on a dropped field the name nonetheless states
  uniqueness         names inside one node are all different

The claims, coverage and minority tests are shared with src/probe_names_part2.py. Only the claims check reads text the generator did not
see; the coverage check uses the same field-mention tests the guard uses, so it is partly circular (see the report).
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_names as AN  # noqa: E402
import probe_names_part1 as P1  # noqa: E402
import probe_names_part2 as P2  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")


QTY = r"(?:all|each|every|two|three|four|five|six|seven|eight|nine|ten|x|up to \w+|any number of|that many|those)"
FT_VERB = {"GainLife": r"gains? (?:[\w+]+ ){0,6}life\b(?!link)|life .{0,15}gain", "LoseLife": r"lose|loses|pay .{0,12}life", "Draw": r"draw",
           "Discard": r"discard", "Mill": r"mill", "Destroy": r"destroy", "Sacrifice": r"sacrifice", "Counter": r"counter", "Scry": r"scry",
           "Surveil": r"surveil", "Regenerate": r"regenerate", "Transform": r"transform", "Tap": r"\btaps?\b|tapped", "Untap": r"untap"}


def noun_of(obj):
    t = re.sub(r"\[.*?\]", "", (obj or "").split("/spell:")[0]).split("|")[0].split("+")[0]
    t = t.split(":")[-1].strip().lower()
    return t if t and t not in ("object", "any target", "self", "player", "you", "parent", "trackedset", "-") else ""


def plural_quantifier(S, Lm):
    """Leaves of 10+ whose name says 'a/an <thing>' while at least 30% of the members' text puts a plural quantifier (all, each, two, up to N,
    any number of, ...) within three words of that thing. The noun comes from the signature's object, the quantifier test from the text."""
    A, members, leaf_info = S["A"], S["members"], S["leaf_info"]
    hits = {}
    for lf, li in leaf_info.items():
        if li["n"] < 10:
            continue
        nm = Lm[li["id"]]["new"]
        noun = noun_of(li["ret"].get("obj", ""))
        if not noun or not re.search(r"\b(a|an|another) (?:[\w'-]+ ){0,3}" + re.escape(noun), nm.lower()):
            continue
        texts = [re.sub(r"\s+", " ", A[j]["text"]).lower() for j in members[lf] if A[j]["text"]]
        if len(texts) < 5:
            continue
        # the quantifier must qualify the thing itself, not a player or a verb between them ("each player sacrifices a creature")
        rx = r"\b" + QTY + r"(?: (?!player|opponent|sacrifice|discard|mill|return|put|draw|loses|gains|chooses)[\w'+/-]+){0,3} " + re.escape(noun)
        sh = sum(1 for t in texts if re.search(rx, t)) / len(texts)
        if sh >= 0.30:
            hits[li["id"]] = round(sh, 2)
    return hits


def verb_missing(S, Lm):
    """Leaves of 10+ where at least 20% of the members' text lacks the verb of the effect type (the gain-life-versus-grant-lifelink mix)."""
    A, members, leaf_info = S["A"], S["members"], S["leaf_info"]
    hits = {}
    for lf, li in leaf_info.items():
        rx = FT_VERB.get(li["ftype"])
        if li["n"] < 10 or not rx:
            continue
        texts = [re.sub(r"\s+", " ", A[j]["text"]).lower() for j in members[lf] if A[j]["text"]]
        if len(texts) < 5:
            continue
        miss = sum(1 for t in texts if not re.search(rx, t)) / len(texts)
        if miss >= 0.20:
            hits[li["id"]] = round(miss, 2)
    return hits


def main():
    S = P2.run(False)
    leaf_info = S["leaf_info"]
    Lm = {}
    for lf, li in leaf_info.items():
        nm = li["name"] if not li["auto_named"] else li["auto_name"]          # without the flag suffix
        Lm[li["id"]] = {"old": nm, "new": nm, "n": li["n"], "sig": lf[1], "node": li["node"], "flags": li["flags"], "level": li["level"]}
    T = json.load(io.open(os.path.join(BUILD, "ability_taxonomy.json"), encoding="utf-8"))
    cards = json.load(io.open(os.path.join(BUILD, "ability_taxonomy_cards.json"), encoding="utf-8"))["cards"]
    vocab = set()
    for c in cards.values():
        for w in re.findall(r"[A-Za-z][a-z']{2,}", c["t"] or ""):
            vocab.add(w.lower())
    P1.ALLOW.update(AN.TEMPLATE_VOCAB)
    names = [("leaf", l["name"]) for l in T["leaves"].values()]
    nodes = [nd for f in T["families"] for nd in f["nodes"]]
    names += [("node", n["name"]) for n in nodes] + [("family", f["name"]) for f in T["families"]]
    scan = P1.defect_scan(names, vocab)
    soft = ("disambiguation suffix ('(variant)', '#2')", "longer than 110 characters", "stacked parentheses")
    hard = {n.split("  [")[0] for k, ns in scan.items() if k not in soft for _, n in ns}
    cl = P2.claims(S, Lm, "new")
    cov = P2.coverage({k: dict(v, name=v["new"]) for k, v in Lm.items()})
    mn = P2.minority(S, Lm, "new")
    by = collections.defaultdict(list)
    for lid, l in Lm.items():
        if l["n"] >= 5:
            by[(l["node"], l["new"])].append(lid)
    pq = plural_quantifier(S, Lm)
    vm = verb_missing(S, Lm)
    flagtxt = [nm for nm in (l["name"] for l in T["leaves"].values()) if " — " in nm and len(set(nm.split(" — ", 1)[1].split("; "))) < len(nm.split(" — ", 1)[1].split("; "))]
    dup = {"%s | %s" % (k[0][1], k[1]): len(v) for k, v in by.items() if len(v) > 1}
    res = {"names_scanned": len(names), "hard_defects": len(hard), "soft": {k: len(v) for k, v in scan.items() if k in soft},
           "allow_list": sorted(AN.TEMPLATE_VOCAB), "claims_hits": {Lm[k]["new"]: v for k, v in cl.items()},
           "coverage_omit": {Lm[k]["new"]: v for k, v in cov.items()}, "minority": {Lm[k]["new"]: v for k, v in mn.items()},
           "plural_quantifier_hits": {Lm[k]["new"]: v for k, v in pq.items()}, "verb_missing_hits": {Lm[k]["new"]: v for k, v in vm.items()},
           "names_repeating_a_flag": flagtxt,
           "duplicate_names_in_a_node": dup, "leaves": len(Lm), "leaves_10plus": sum(1 for l in Lm.values() if l["n"] >= 10),
           "names_with_varies": sum(1 for l in Lm.values() if " varies" in l["new"]),
           "names_over_110": sum(1 for l in Lm.values() if len(l["new"]) > 110)}
    with io.open(os.path.join(BUILD, "ability_taxonomy_names_final_check.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True))
    print(json.dumps({k: (v if not isinstance(v, dict) else len(v)) for k, v in res.items() if k != "allow_list"}, indent=1))
    for k, v in res["plural_quantifier_hits"].items():
        print("  plural-quantifier:", v, k[:90])
    for k, v in res["verb_missing_hits"].items():
        print("  verb-missing:", v, k[:90])
    for k, v in res["minority"].items():
        print("  minority:", k[:90], v)


if __name__ == "__main__":
    main()
