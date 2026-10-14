#!/usr/bin/env python3
"""Part 1 (c) probe (read-only): candidates whose leaf's key verb appears only in the cost / "may" lead-in / condition clause of the ability, not in its effect (the Akuta, Born of Ash failure).
Reads build/annotation_extract.json; writes build/annotation_verbs.json. Seed 20261031 (declared before the draw) for the 20 read examples."""
import collections
import io
import json
import os
import random
import re
import sys
import textwrap

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
SEED = 20261031
BS = chr(92)
STOPV = {"a", "an", "the", "all", "each", "any", "target", "put", "give", "gain", "gets", "get", "your", "you", "pump", "zone", "counters", "continuous", "static", "triggered", "an", "one", "this", "that", "add", "x", "set"}
LEAD = re.compile(r"\b(if you do|when you do|if you don't|if you do not|unless you)\b", re.I)


def stem(w):
    w = re.sub(r"[^a-z]", "", w.lower())
    for suf in ("ing", "ed", "es", "s", "e"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def key_verb(r):
    name = r["leaf"].split(" \u203a ", 1)[-1]
    for w in re.findall(r"[A-Za-z']+", name):
        if w.lower() not in STOPV:
            return stem(w)
    return ""


def regions(full):
    """-> (cost_side, effect_side): activated cost = text before the first ': '; a 'may X.' lead-in = text before the first 'if you do / when you do / unless you' sentence."""
    low = full.lower()
    cost, eff = "", low
    m = re.match(r"^([^:]{1,120}):\s+(.*)$", low)
    if m:
        cost, eff = m.group(1), m.group(2)
    m = LEAD.search(eff)
    if m:
        cost, eff = cost + " " + eff[: m.start()], eff[m.start():]
    return cost, eff


def main():
    rows = json.load(io.open(os.path.join(BUILD, "annotation_extract.json"), encoding="utf-8"))
    out, cnt = [], collections.Counter()
    for r in rows:
        v = key_verb(r)
        r["verb"] = v
        if not v:
            cnt["no key verb"] += 1
            continue
        cost, eff = regions(r["full"])
        eff = re.sub(r"[a-z]+ed" + BS + "b", " ", eff)           # a participle ("the sacrificed creature's power") refers back to the lead-in; it is not the effect
        in_c, in_e = v in cost, v in eff
        cl = v in r["ext"].lower() if r["ext"] else False
        if in_c and not in_e:
            r["shared"] = "cost/lead-in only"
        elif cl and not in_e and not in_c:
            r["shared"] = "condition clause only"
        elif cl and in_e:
            r["shared"] = "also in condition clause (and effect)"
        elif in_c and in_e:
            r["shared"] = "cost and effect"
        else:
            r["shared"] = ""
        cnt[r["shared"] or "ok"] += 1
        if r["shared"]:
            out.append(r)
    print(dict(cnt))
    risky = [r for r in out if r["shared"] in ("cost/lead-in only", "condition clause only")]
    json.dump({"counts": dict(cnt), "risky": [r["n"] for r in risky]}, io.open(os.path.join(BUILD, "annotation_verbs.json"), "w", encoding="utf-8", newline="\n"))
    rnd = random.Random(SEED)
    lst = sorted(risky, key=lambda r: (r["oid"], r["n"]))
    rnd.shuffle(lst)
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        for i, r in enumerate(lst[:20], 1):
            print(i, r["shared"], "| verb:", r["verb"], "| leaf:", r["leaf"][:60])
            print("   T:", "\n      ".join(textwrap.wrap(r["full"], 150)))
    bysub = collections.Counter(r["sub"] for r in risky)
    print("risky", len(risky), "by sub", bysub.most_common(6))


if __name__ == "__main__":
    main()
