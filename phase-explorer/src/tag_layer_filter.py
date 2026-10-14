#!/usr/bin/env python3
"""The community-tag layer's tag filter: the existing rules (type oracle, a floor of 20 taggings, the card_function_search denylist; see probe_tags.py) plus corrections/tag_denylist.json.
Importable; run it to write the before/after report.

    python src/tag_layer_filter.py     # -> build/tag_layer_filter.json (the denied tags by UUID), build/tag_layer_filter_report.json
"""
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_tags as PT

HERE = PT.HERE
BUILD = PT.BUILD
GROUP_MIN, GROUP_MAX = 5, 100


def load_deny():
    d = json.load(io.open(os.path.join(HERE, "corrections", "tag_denylist.json"), encoding="utf-8"))
    return d["categories"]


def deny_category(slug, cats):
    for name, c in cats.items():
        if slug in c.get("slugs", []) or slug.startswith(tuple(c.get("prefixes", []))) or slug.endswith(tuple(c.get("suffixes", []))):
            return name
    return ""


def functional(tags, cats=None, use_deny=True):
    """-> {tag uuid: tag} after the existing filter and, if use_deny, the design / errata / templating deny list."""
    cats = cats if cats is not None else load_deny()
    out = {}
    for t in tags:
        if PT.drop_reason(t):
            continue
        if use_deny and deny_category(t["slug"], cats):
            continue
        out[t["id"]] = t
    return out


def card_tags(fn):
    out = collections.defaultdict(set)
    for tid, t in fn.items():
        for g in t["taggings"]:
            out[g["oracle_id"]].add(tid)
    return out


def groups(cards, ct):
    G = collections.defaultdict(set)
    for o in cards:
        for t in ct.get(o, ()):
            G[t].add(o)
    return G


def main():
    new = PT.load(PT.NEW)
    cats = load_deny()
    unread = set(json.load(io.open(os.path.join(BUILD, "tag_probe_cards.json"), encoding="utf-8"))["unread"])
    base, after = functional(new, cats, False), functional(new, cats, True)
    res = {"snapshot": json.load(io.open(PT.NEW.replace(".json", ".meta.json"), encoding="utf-8"))["updated_at"], "cards": len(unread)}
    denied = [base[t] for t in base if t not in after]
    bycat = collections.Counter(deny_category(t["slug"], cats) for t in denied)
    res["tags"] = {"all": len(new), "functional_before_deny_list": len(base), "denied_by_the_deny_list": len(denied), "functional_after": len(after), "denied_by_category": dict(bycat)}
    for lab, fn in (("before", base), ("after", after)):
        ct = card_tags(fn)
        G = groups(unread, ct)
        keep = {t for t, v in G.items() if GROUP_MIN <= len(v) <= GROUP_MAX}
        reach = {o for o in unread if any(t in keep for t in ct.get(o, ()))}
        gp = sorted(sum(1 for t in ct.get(o, ()) if t in keep) for o in reach)
        res[lab] = {"tags_with_a_card_among_the_1300": len(G), "groups_of_5_or_more": sum(1 for v in G.values() if len(v) >= 5), "groups_of_5_to_100": len(keep), "groups_over_100": sum(1 for v in G.values() if len(v) > 100),
                    "groups_under_5": sum(1 for v in G.values() if len(v) < 5), "cards_reached_by_a_group_of_5_to_100": len(reach), "pct": round(100.0 * len(reach) / len(unread), 1),
                    "groups_per_reached_card": {"median": gp[len(gp) // 2], "mean": round(sum(gp) / len(gp), 1), "max": gp[-1]}, "cards_with_any_functional_tag": sum(1 for o in unread if ct.get(o))}
        if lab == "before":
            reach_b = reach
        else:
            reach_a = reach
    res["coverage_cost"] = {"cards_that_lose_every_group": len(reach_b - reach_a), "cards_gained": len(reach_a - reach_b), "net": len(reach_a) - len(reach_b)}
    # the denied tags that held a group of 5 or more among the 1,300, by category and size
    ctb = card_tags(base)
    Gb = groups(unread, ctb)
    res["denied_groups_of_5_or_more"] = {c: sorted(((len(Gb[t["id"]]), t["slug"]) for t in denied if deny_category(t["slug"], cats) == c and len(Gb.get(t["id"], ())) >= 5), reverse=True) for c in cats}
    with io.open(os.path.join(BUILD, "tag_layer_filter.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"snapshot": res["snapshot"], "functional_tag_ids": sorted(after), "denied": sorted([[t["id"], t["slug"], deny_category(t["slug"], cats)] for t in denied], key=lambda x: x[0])}, ensure_ascii=False, separators=(",", ":")))
    with io.open(os.path.join(BUILD, "tag_layer_filter_report.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "denied_groups_of_5_or_more"}, indent=1))
    print({c: len(v) for c, v in res["denied_groups_of_5_or_more"].items()})


if __name__ == "__main__":
    main()
