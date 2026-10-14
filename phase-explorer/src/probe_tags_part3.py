#!/usr/bin/env python3
"""Tag-layer probe, Part 3 (read-only): quality of tag groups and of tags on the cards we cannot read. Builds nothing, places nothing, changes nothing.

    python src/probe_tags_part3.py draw           # -> build/tag_probe_blind.json (members' text only), build/tag_probe_key.json (tag names, hidden until the reads exist)
    python src/probe_tags_part3.py show g 1 10    # groups 1-10 (members' oracle text, no tag name);  show c 1 40 for the 40 unreadable cards
    python src/probe_tags_part3.py reveal         # after build/tag_probe_reads.json exists -> build/tag_probe_result.json
    python src/probe_tags_part3.py names          # the name-quality scan over the per-tag groups (defect scan, claims check) -> build/tag_probe_names.json

Seed 20261036 (set before computing): 30 tag groups from option 1 (one group per tag, size = unorganized cards carrying it, gap-test stratum off, 2,540 cards), 10 from 5-20, 10 from 21-100,
10 over 100, no redraw; up to 8 member cards each (seeded); for each group I write what the members do (and whether they share one thing) BEFORE the tag name is shown; the verdict
(coherent / loose / incoherent: does the tag's name state what the members do) is added after the reveal. Bar: more than 25% incoherent = not recommended in that form.
Seed 20261037 (set before computing): 40 of the 1,300 cards with no readable ability, one tag each (a seeded pick among the tags that would put the card in a group of 5 to 100); the card text is
read first and my judgment of a fair description written before the tag is shown. Verdict right / loose / wrong. Bar: more than 5 wrong turns that stratum off.
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
import probe_tags as PT

BUILD = PT.BUILD
SEED_G, SEED_C = 20261036, 20261037


def setup():
    new = PT.load(PT.NEW)
    nm = {t["id"]: t for t in new}
    tg = PT.card_tags(new)
    d = json.load(io.open(os.path.join(BUILD, "tag_probe_cards.json"), encoding="utf-8"))
    cards = PT.jl("ability_taxonomy_cards.json")["cards"]
    return nm, tg, d, cards


def groups_of(S, tg):
    G = collections.defaultdict(set)
    for o in S:
        for t in tg.get(o, ()):
            G[t].add(o)
    return G


def draw():
    nm, tg, d, cards = setup()
    off = set(d["off"])
    G = groups_of(off, tg)
    strata = (("5 to 20", 5, 20), ("21 to 100", 21, 100), ("over 100", 101, 10 ** 9))
    rnd = random.Random(SEED_G)
    blind, key = [], []
    n = 0
    for lab, lo, hi in strata:
        pool = sorted(t for t, v in G.items() if lo <= len(v) <= hi)
        rnd.shuffle(pool)
        for t in pool[:10]:
            mem = rnd.sample(sorted(G[t]), min(8, len(G[t])))
            n += 1
            blind.append({"n": n, "stratum": lab, "pile_cards": len(G[t]), "members": [{"card": cards[o]["n"], "oracle_text": cards[o]["t"]} for o in mem]})
            key.append({"n": n, "stratum": lab, "tag": nm[t]["slug"], "label": nm[t].get("label"), "description": nm[t].get("description") or "", "pile_cards": len(G[t]), "all_cards": len(nm[t]["taggings"])})
    # the unreadable cards
    unread = sorted(d["unread"])
    keep = {t for t, v in G.items() if 5 <= len(v) <= 100}
    rc = random.Random(SEED_C)
    rc.shuffle(unread)
    cb, ck, skipped = [], [], 0
    for o in unread:
        cand = sorted(t for t in tg.get(o, ()) if t in keep)
        if not cand:
            skipped += 1
            continue
        if len(cb) >= 40:
            break
        t = rc.choice(cand)
        i = len(cb) + 1
        cb.append({"n": i, "card": cards[o]["n"], "oracle_text": cards[o]["t"]})
        ck.append({"n": i, "oid": o, "tag": nm[t]["slug"], "description": nm[t].get("description") or "", "group_pile_cards": len(G[t]), "tags_in_5_to_100_groups": len(cand)})
    with io.open(os.path.join(BUILD, "tag_probe_blind.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"seed_groups": SEED_G, "seed_cards": SEED_C, "groups": blind, "cards": cb}, ensure_ascii=False, indent=1))
    with io.open(os.path.join(BUILD, "tag_probe_key.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"groups": key, "cards": ck, "skipped_cards_with_no_group_of_5_to_100_before_the_40": skipped}, ensure_ascii=False, indent=1))
    print("groups", len(blind), "cards", len(cb), "skipped", skipped)


def show(kind, lo, hi):
    b = json.load(io.open(os.path.join(BUILD, "tag_probe_blind.json"), encoding="utf-8"))
    if kind == "g":
        for g in b["groups"]:
            if lo <= g["n"] <= hi:
                print("\n=== group %d [%s] %d pile cards, %d shown" % (g["n"], g["stratum"], g["pile_cards"], len(g["members"])))
                for m in g["members"]:
                    t = m["oracle_text"].replace("\n", " / ").encode("ascii", "replace").decode()
                    print("  -", m["card"].encode("ascii", "replace").decode()[:34], "|", t[:230])
    else:
        for c in b["cards"]:
            if lo <= c["n"] <= hi:
                print("\n=== card %d  %s" % (c["n"], c["card"].encode("ascii", "replace").decode()))
                print("   ", "\n    ".join(textwrap.wrap(c["oracle_text"].replace("\n", " / ").encode("ascii", "replace").decode()[:420], 150)))


def reveal():
    key = json.load(io.open(os.path.join(BUILD, "tag_probe_key.json"), encoding="utf-8"))
    reads = json.load(io.open(os.path.join(BUILD, "tag_probe_reads.json"), encoding="utf-8"))
    out = {"groups": [], "cards": []}
    for k in key["groups"]:
        r = reads["groups"][str(k["n"])]
        out["groups"].append(dict(k, my_common=r["common"], members_share_one_thing=r["shared"], verdict=r.get("verdict", ""), why=r.get("why", "")))
    for k in key["cards"]:
        r = reads["cards"][str(k["n"])]
        out["cards"].append(dict(k, my_fair_description=r["fair"], verdict=r.get("verdict", ""), why=r.get("why", "")))
    for g in out["groups"]:
        print("G%2d [%-9s] n=%-4d %-38s | I saw: %-60s | shared=%s | %s" % (g["n"], g["stratum"], g["pile_cards"], g["tag"][:38], g["my_common"][:60], g["members_share_one_thing"], g["verdict"]))
    for c in out["cards"]:
        print("C%2d %-40s | I read: %-55s | %s" % (c["n"], c["tag"][:40], c["my_fair_description"][:55], c["verdict"]))
    if all(g["verdict"] for g in out["groups"]) and all(c["verdict"] for c in out["cards"]):
        gv = collections.Counter(g["verdict"] for g in out["groups"])
        gs = {s: collections.Counter(g["verdict"] for g in out["groups"] if g["stratum"] == s) for s in ("5 to 20", "21 to 100", "over 100")}
        cv = collections.Counter(c["verdict"] for c in out["cards"])
        out["summary"] = {"groups": dict(gv), "groups_by_stratum": {k: dict(v) for k, v in gs.items()}, "incoherent_pct": round(100.0 * gv["incoherent"] / 30, 1), "cards": dict(cv),
                          "bars": {"groups_incoherent_over_pct": 25, "cards_wrong_over": 5}, "tripped": {"groups": 100.0 * gv["incoherent"] / 30 > 25, "cards": cv["wrong"] > 5}}
        print(json.dumps(out["summary"], indent=1))
    with io.open(os.path.join(BUILD, "tag_probe_result.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1))


def names():
    import ability_names as AN
    import probe_names_part1 as P1
    import probe_names_part2 as P2
    nm, tg, d, cards = setup()
    off = set(d["off"])
    G = groups_of(off, tg)
    vocab = set()
    for c in cards.values():
        for w in re.findall(r"[A-Za-z][a-z']{2,}", c["t"] or ""):
            vocab.add(w.lower())
    P1.ALLOW.update(AN.TEMPLATE_VOCAB)
    short = {"pp": "+1/+1", "mm": "-1/-1", "etb": "enters the battlefield", "ltb": "leaves the battlefield", "cmc": "mana value", "mv": "mana value"}

    def human(slug):
        w = [short.get(x, x) for x in slug.split("-")]
        s = " ".join(w)
        return s[:1].upper() + s[1:]
    sel = {t: v for t, v in G.items() if 5 <= len(v) <= 100}
    nms = {t: human(nm[t]["slug"]) for t in sel}
    scan = P1.defect_scan([("group", n) for n in nms.values()], vocab)
    soft = ("longer than 110 characters", "stacked parentheses", "disambiguation suffix ('(variant)', '#2')")
    hard = collections.defaultdict(list)
    for k, v in scan.items():
        if k not in soft:
            for _, n in v:
                hard[k].append(n.split("  [")[0])
    hard_names = {n for v in hard.values() for n in v}
    jargon = {n for n in hard_names if n in {x.split("  [")[0] for _, x in scan.get("word not found in any card text (merged or misspelt?)", [])}}
    non_vocab = collections.Counter(k for k, v in hard.items())
    bad = []
    for t, v in sel.items():
        texts = [P2.norm(cards[o]["t"]) for o in v]
        low = set(re.findall(r"[a-z']+", P2.norm(nms[t])))
        for w, rx in P2.STEMS.items():
            if w in low or (w + "s") in low:
                if sum(1 for x in texts if re.search(rx, x)) / len(texts) < 0.5:
                    bad.append((nms[t], w))
    desc = sum(1 for t in sel if (nm[t].get("description") or "").strip())
    typal = sum(1 for t in sel if nm[t]["slug"].startswith(("typal-", "synergy-", "hate-", "gives-", "gains-", "tutor-")))
    res = {"groups_checked": len(sel), "names_with_a_hard_defect_or_vocabulary_flag": len(hard_names), "defect_kinds": {k: len(v) for k, v in hard.items()}, "claims_hits": len(bad), "claims_examples": bad[:10],
           "names_needing_a_rewrite": len(hard_names | {n for n, w in bad}), "with_a_scryfall_description": desc,
           "examples_flagged": sorted(hard_names)[:25], "tags_with_prefix_families_typal_synergy_hate_gives_gains_tutor": typal}
    with io.open(os.path.join(BUILD, "tag_probe_names.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "draw":
        draw()
    elif c == "reveal":
        reveal()
    elif c == "names":
        names()
    else:
        show(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
