#!/usr/bin/env python3
"""Name checks for the community-tag groups (read-only).

    python src/check_tag_names.py            # defect scan, vocabulary, claims check, uniqueness over all groups -> build/tag_layer_names_check.json
    python src/check_tag_names.py draw       # the 30 names for the hand check (seed 20261040, declared before the draw) -> shown with up to 6 members' text each
    python src/check_tag_names.py show

The existing checks (probe_names_part1.defect_scan, probe_names_part2 STEMS claims) over the layer's group names. The fixed words the naming rules add ("Cares about", "Removal:", "Works against", ...) are added
to the vocabulary allow list: the check is for slug jargon, not for the rules' own words.
"""
import collections
import io
import json
import os
import random
import re
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_names as AN
import probe_names_part1 as P1
import probe_names_part2 as P2
import probe_tags as PT
import tag_layer_filter as F
import tag_layer_names as N

BUILD = PT.BUILD
SEED = 20261040


def setup():
    new = PT.load(PT.NEW)
    fn = F.functional(new)
    ct = F.card_tags(fn)
    unread = set(json.load(io.open(os.path.join(BUILD, "tag_probe_cards.json"), encoding="utf-8"))["unread"])
    G = F.groups(unread, ct)
    keep = {t: v for t, v in G.items() if F.GROUP_MIN <= len(v) <= F.GROUP_MAX}
    cards = PT.jl("ability_taxonomy_cards.json")["cards"]
    return fn, keep, cards


def check():
    fn, keep, cards = setup()
    ov = N.load_overlay()
    names = {t: N.name_of(fn[t]["slug"], ov) for t in keep}
    vocab = set()
    for c in cards.values():
        for w in re.findall(r"[A-Za-z][a-z']{2,}", c["t"] or ""):
            vocab.add(w.lower())
    P1.ALLOW.update(AN.TEMPLATE_VOCAB)
    P1.ALLOW.update(set(N.load_doc().get("vocabulary_allow", [])))
    P1.ALLOW.update({"cares", "removal", "repeatable", "tutors", "conjures", "copies", "works", "against", "takes", "scales", "itself", "creature", "cards", "board", "wipe", "whole", "team", "again", "grows"})
    scan = P1.defect_scan([("group", n) for n, a in names.values()], vocab)
    soft = ("longer than 110 characters", "stacked parentheses", "disambiguation suffix ('(variant)', '#2')")
    hard = collections.defaultdict(list)
    for k, v in scan.items():
        for _, n in v:
            hard[k if k not in soft else "soft: " + k].append(n.split("  [")[0])
    bad = []
    for t, v in keep.items():
        texts = [P2.norm(cards[o]["t"]) for o in v]
        low = set(re.findall(r"[a-z']+", P2.norm(names[t][0])))
        for w, rx in P2.STEMS.items():
            if w in low or (w + "s") in low:
                if sum(1 for x in texts if re.search(rx, x)) / len(texts) < 0.5:
                    bad.append((names[t][0], fn[t]["slug"], w))
    dup = [n for n, c in collections.Counter(n for n, a in names.values()).items() if c > 1]
    res = {"groups": len(keep), "name_source": dict(collections.Counter(a for n, a in names.values())), "duplicate_names": dup, "longest": max(len(n) for n, a in names.values()),
           "defects": {k: v for k, v in hard.items()}, "claims_hits": bad, "claims_hit_count": len(bad)}
    with io.open(os.path.join(BUILD, "tag_layer_names_check.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: (v if k != "defects" else {a: (len(b), b[:8]) for a, b in v.items()}) for k, v in res.items()}, indent=1, ensure_ascii=False))


def draw():
    fn, keep, cards = setup()
    ov = N.load_overlay()
    rnd = random.Random(SEED)
    ts = sorted(keep, key=lambda t: fn[t]["slug"])
    pick = rnd.sample(ts, 30)
    out = []
    for i, t in enumerate(pick, 1):
        mem = rnd.sample(sorted(keep[t]), min(6, len(keep[t])))
        out.append({"n": i, "slug": fn[t]["slug"], "name": N.name_of(fn[t]["slug"], ov)[0], "auto": N.name_of(fn[t]["slug"], ov)[1], "size": len(keep[t]), "members": [(cards[o]["n"], cards[o]["t"]) for o in mem]})
    with io.open(os.path.join(BUILD, "tag_layer_names_sample.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1))
    print("drawn", len(out))


def show(lo=1, hi=30):
    for g in json.load(io.open(os.path.join(BUILD, "tag_layer_names_sample.json"), encoding="utf-8")):
        if lo <= g["n"] <= hi:
            print("\n=== %d  \"%s\"  (%s, %d cards)" % (g["n"], g["name"].encode("ascii", "replace").decode(), g["auto"], g["size"]))
            for c, t in g["members"]:
                print("  -", c.encode("ascii", "replace").decode()[:30], "|", t.replace("\n", " / ").encode("ascii", "replace").decode()[:170])


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "check"
    if c == "check":
        check()
    elif c == "draw":
        draw()
    else:
        show(int(sys.argv[2]) if len(sys.argv) > 2 else 1, int(sys.argv[3]) if len(sys.argv) > 3 else 30)
