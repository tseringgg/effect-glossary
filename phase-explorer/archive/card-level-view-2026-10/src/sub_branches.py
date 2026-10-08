#!/usr/bin/env python3
"""Type-specific sub-branches: a CARD-level drill-down under a parent branch.

WHAT THIS ADDS, AND WHY IT IS NEW
---------------------------------
Two things this repo did not have before:

  1. A parent/child layer. The Burn/Land-ramp round is sometimes remembered as
     a "sub-branch split", but it was not: it rescoped BURN_EFFECTS and added
     "Mass burn" as a FLAT SIBLING branch. Nothing in the model had a parent.
  2. Card-level assignment. Every branch record carries `leaves`, and cards
     inherit their leaf wholesale. A leaf could never be divided.

Leaf 44 is why both are needed. It holds 513 cards -- mana dorks, mana rocks and
mana lands -- merged into ONE leaf because the clustering was type-blind. No
leaf-level rule can separate them, because the split runs *through* the leaf.

So a sub-branch assigns CARDS, not leaves, and one leaf's cards routinely land
in several sub-branches. That is the point, not a defect.

WHAT IT DOES NOT DO
-------------------
Nothing is re-clustered and no leaf is altered. The parent branch keeps its full
card set and stays browsable exactly as before -- sub-branches are an ADDITIVE
drill-down. Leaf 44 is still a 513-card type-mixed leaf afterwards, and the
leaf-level audit still reports it as such. What changes is that its cards are
now reachable through containers that are type-pure. See `verify` below: the
proof of the split is measured on the sub-branches, not on the leaves.

MULTI-TYPE CARDS
----------------
An Artifact Creature that taps for mana is genuinely both a dork and a rock, so
it is assigned to BOTH sub-branches. Branch assignment has always been
many-to-many, and sub-branch card counts therefore sum to more than the parent,
exactly as branch counts already sum to more than the corpus.

Reads   build/type_audit.json, build/branches.json, build/clusters.json, chunks
Writes  build/sub_branches.json     merged into branches.json by branch_leaves.py
        reports/sub-branches.md
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "hdbscan" not in sys.modules:
    import types as _types
    sys.modules["hdbscan"] = _types.ModuleType("hdbscan")
import cluster_structural as C

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
REPORTS = os.path.join(HERE, "reports")

PERMANENT = {"Artifact", "Creature", "Enchantment", "Land", "Planeswalker",
             "Battle", "Kindred", "Tribal"}
SPELL = "Spell"

# A type earns its own sub-branch at either bar. Two bars rather than one so a
# small parent is not left unsplit on the share test, and a huge parent does not
# sprout a sub-branch for six stray cards on the count test.
MIN_SUB_SHARE = 0.10
MIN_SUB_CARDS = 20
# Below which a type is folded into "other types" -- kept so every card in the
# parent stays reachable through the drill-down, rather than quietly vanishing.
OTHER = "other types"

# Sourced vocabulary for (parent, type) pairs that already have a real MTG term.
# Everything else gets a generated "Parent (Type)" name, flagged auto-named on
# exactly the same footing as the auto-named branches.
SOURCED = {
    ("Ramp", "Creature"): "Mana dork",
    ("Ramp", "Artifact"): "Mana rock",
    ("Ramp", "Land"): "Land ramp",
}

# Scope guard, enforced in code rather than trusted to the caller: only tier A,
# only inside a real branch. Tier B and auto-named / Unique-effect leaves are
# explicitly out of this pass.
TIER = "A"
STATE = "Real branch"


def card_types(d):
    ct = set((d.get("card_type") or {}).get("core_types") or [])
    perm = ct & PERMANENT
    return perm if perm else {SPELL}


def main():
    TA = json.load(open(os.path.join(BUILD, "type_audit.json"), encoding="utf-8"))
    BR = json.load(open(os.path.join(BUILD, "branches.json"), encoding="utf-8"))
    CL = json.load(open(os.path.join(BUILD, "clusters.json"), encoding="utf-8"))
    rows, chunks = C.load()
    byid = {r["id"]: r for r in rows}

    members = collections.defaultdict(list)
    for cid, l in CL["cards"].items():
        if l >= 0:
            members[int(l)].append(cid)

    in_scope = [f for f in TA["findings"]
                if f["tier"] == TIER and f["state"] == STATE]
    parents = collections.OrderedDict()
    for f in sorted(in_scope, key=lambda x: -x["n_cards"]):
        for b in f["branches"]:
            parents.setdefault(b, []).append(f["leaf"])

    bymeta = {b["name"]: b for b in BR["branches"]}
    # exposure BEFORE, measured the way the audit measures it
    before = {}
    for p, lv in parents.items():
        tc = bymeta[p]["n_cards"]
        hc = sum(f["n_cards"] for f in in_scope if p in f["branches"])
        before[p] = {"branch_cards": tc, "het_cards": hc,
                     "share": round(hc / tc, 4) if tc else 0.0,
                     "tierA_leaves": sorted(set(lv))}

    subs, skipped = [], []
    for p, trigger_leaves in parents.items():
        leaves = bymeta[p]["leaves"]
        cards = [c for l in leaves for c in members[l]]
        n = len(cards)
        by_type = collections.defaultdict(list)
        for cid in cards:
            for t in card_types(chunks[byid[cid]["ch"]][cid]):
                by_type[t].append(cid)

        keep = {t: cs for t, cs in by_type.items()
                if len(cs) >= MIN_SUB_CARDS or len(cs) / n >= MIN_SUB_SHARE}
        if len(keep) < 2:
            skipped.append({"parent": p, "why": "fewer than two type groups "
                            "clear the bar; a drill-down would add nothing",
                            "distribution": {t: len(cs) for t, cs in
                                             sorted(by_type.items(),
                                                    key=lambda kv: -len(kv[1]))}})
            continue

        # every card stays reachable: whatever missed the bar lands in `other`
        kept_cards = {c for cs in keep.values() for c in cs}
        leftover = [c for c in cards if c not in kept_cards]
        if leftover:
            keep[OTHER] = leftover

        for t, cs in sorted(keep.items(), key=lambda kv: -len(kv[1])):
            name = SOURCED.get((p, t)) or (
                f"{p} ({t})" if t != OTHER else f"{p} (other types)")
            lv = sorted({CL["cards"][c] for c in cs})
            subs.append({
                "parent": p, "type": t, "name": name,
                "sourced": (p, t) in SOURCED,
                "auto_named": (p, t) not in SOURCED,
                "n_cards": len(cs),
                "share_of_parent": round(len(cs) / n, 4),
                "leaves_touched": lv,
                "n_leaves_touched": len(lv),
                "cards": sorted(cs),
                "sample": sorted(CL["names"][c] for c in cs)[:8],
            })

    # ---- the proof: is each sub-branch type-pure? -------------------------
    verify = []
    for s in subs:
        cnt = collections.Counter()
        for cid in s["cards"]:
            for t in card_types(chunks[byid[cid]["ch"]][cid]):
                cnt[t] += 1
        n = s["n_cards"]
        own = cnt.get(s["type"], 0) / n if s["type"] != OTHER else None
        verify.append({
            "name": s["name"], "parent": s["parent"], "type": s["type"],
            "n_cards": n,
            "own_type_share": None if own is None else round(own, 4),
            "type_pure": None if own is None else own >= 0.999,
        })

    split_parents = sorted({s["parent"] for s in subs})
    after = {}
    for p in parents:
        if p in split_parents:
            bad = [v for v in verify
                   if v["parent"] == p and v["type_pure"] is False]
            after[p] = {"sub_branches": len([s for s in subs if s["parent"] == p]),
                        "impure_sub_branches": len(bad),
                        "share": 0.0 if not bad else None}
        else:
            after[p] = {"sub_branches": 0, "impure_sub_branches": None,
                        "share": before[p]["share"]}

    out = {
        "scope": {"tier": TIER, "state": STATE,
                  "min_sub_share": MIN_SUB_SHARE, "min_sub_cards": MIN_SUB_CARDS},
        "n_parents_in_scope": len(parents),
        "n_parents_split": len(split_parents),
        "n_sub_branches": len(subs),
        "n_cards_in_sub_branches": sum(s["n_cards"] for s in subs),
        "parents_split": split_parents,
        "skipped": skipped,
        "before": before,
        "after": after,
        "verify": verify,
        "sub_branches": subs,
    }
    with open(os.path.join(BUILD, "sub_branches.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"), ensure_ascii=False)

    write_report(os.path.join(REPORTS, "sub-branches.md"), out)

    impure = [v for v in verify if v["type_pure"] is False]
    print(json.dumps({
        "parents_in_scope": len(parents),
        "parents_split": len(split_parents),
        "parents_skipped": len(skipped),
        "sub_branches_created": len(subs),
        "cards_placed": sum(s["n_cards"] for s in subs),
        "sub_branches_type_pure": len([v for v in verify if v["type_pure"]]),
        "sub_branches_impure": len(impure),
    }, indent=1))


def write_report(path, out):
    L = []
    A = L.append
    S = out["sub_branches"]
    A("# Type sub-branches -- a card-level drill-down")
    A("")
    A(f"{out['n_sub_branches']} sub-branches under {out['n_parents_split']} "
      f"parent branches, placing {out['n_cards_in_sub_branches']:,} card slots. "
      f"Generated by `src/sub_branches.py`.")
    A("")
    A("## What is new here")
    A("")
    A("Two mechanisms this repo did not previously have:")
    A("")
    A("- **A parent/child layer.** The Burn/Land-ramp round is easy to remember "
      "as a sub-branch split, but it was not one: it rescoped `BURN_EFFECTS` and "
      "added *Mass burn* as a flat sibling. Nothing had a parent until now.")
    A("- **Card-level assignment.** Every branch record carries `leaves`, and "
      "cards inherited their leaf wholesale. A leaf could not be divided.")
    A("")
    A("Leaf 44 forced both. Its 513 cards are mana dorks, rocks and lands merged "
      "into one leaf by type-blind clustering, so the split runs *through* the "
      "leaf and no leaf-level rule can reach it.")
    A("")
    A("The parent keeps its full card set and stays browsable unchanged. "
      "Sub-branches are **additive**.")
    A("")
    A("Multi-type cards are assigned to **every** matching sub-branch -- an "
      "Artifact Creature that taps for mana really is both a dork and a rock -- "
      "so sub-branch counts sum to more than the parent, exactly as branch "
      "counts already sum to more than the corpus.")
    A("")

    A("## Ramp, Burn and Tutor")
    A("")
    for p in ("Ramp", "Burn", "Tutor"):
        rows = [s for s in S if s["parent"] == p]
        if not rows:
            sk = next((k for k in out["skipped"] if k["parent"] == p), None)
            A(f"**{p}** -- not split: {sk['why'] if sk else 'not in scope'}.")
            A("")
            continue
        A(f"### {p}")
        A("")
        A("| sub-branch | type | cards | share of parent | leaves touched | name |")
        A("|---|---|---|---|---|---|")
        for s in rows:
            A(f"| **{s['name']}** | {s['type']} | {s['n_cards']:,} | "
              f"{s['share_of_parent']:.0%} | {s['n_leaves_touched']} | "
              f"{'sourced' if s['sourced'] else '`AUTO`'} |")
        A("")
        A(f"Sample from the largest: "
          f"{', '.join(rows[0]['sample'][:6])}.")
        A("")

    A("## All sub-branches")
    A("")
    A("| parent | sub-branch | type | cards | share | leaves | name |")
    A("|---|---|---|---|---|---|---|")
    for s in S:
        A(f"| {s['parent']} | {s['name']} | {s['type']} | {s['n_cards']:,} | "
          f"{s['share_of_parent']:.0%} | {s['n_leaves_touched']} | "
          f"{'sourced' if s['sourced'] else 'auto'} |")
    A("")

    if out["skipped"]:
        A("## Parents left unsplit")
        A("")
        A("In scope, but a drill-down would have added nothing.")
        A("")
        A("| parent | why | distribution |")
        A("|---|---|---|")
        for k in out["skipped"]:
            d = " ".join(f"{t} {n}" for t, n in list(k["distribution"].items())[:4])
            A(f"| {k['parent']} | {k['why']} | {d} |")
        A("")

    A("## Proof: are the sub-branches type-pure?")
    A("")
    A("Creating sub-branches is not evidence that they worked. Each one is "
      "measured for the share of its cards actually carrying its type. A "
      "type-specific sub-branch must be at 100%.")
    A("")
    pure = [v for v in out["verify"] if v["type_pure"]]
    impure = [v for v in out["verify"] if v["type_pure"] is False]
    resid = [v for v in out["verify"] if v["type_pure"] is None]
    A(f"- type-pure at 100%: **{len(pure)} of {len(pure)+len(impure)}** typed "
      f"sub-branches")
    A(f"- impure: **{len(impure)}**")
    A(f"- residual *other types* buckets (mixed by definition, so not measured): "
      f"{len(resid)}")
    A("")
    if impure:
        A("| sub-branch | own-type share |")
        A("|---|---|")
        for v in impure:
            A(f"| {v['name']} | {v['own_type_share']:.1%} |")
        A("")

    A("## Before and after")
    A("")
    A("**Read this carefully.** Two different things are being measured, and "
      "only one of them changes.")
    A("")
    A("| parent | leaf-level exposure before | leaf-level after | sub-branch-level after |")
    A("|---|---|---|---|")
    for p, b in sorted(out["before"].items(), key=lambda kv: -kv[1]["share"]):
        a = out["after"][p]
        sb = ("no split" if not a["sub_branches"]
              else ("0%" if a["share"] == 0.0 else "impure"))
        A(f"| {p} | {b['share']:.0%} | {b['share']:.0%} (unchanged) | {sb} |")
    A("")
    A("**Leaf-level exposure does not move, and cannot.** Nothing was "
      "re-clustered, so leaf 44 is still 513 cards at Creature 44% / Land 30% / "
      "Artifact 28%, and the leaf audit still reports it. Any claim that Ramp's "
      "exposure 'dropped to 0%' would be measuring a different thing and calling "
      "it the same name.")
    A("")
    A("**What genuinely changed** is that those cards are now reachable through "
      "containers that are type-pure. The mixing still exists one layer down, in "
      "the leaves; it is no longer what you browse. Removing it at the leaf layer "
      "needs re-clustering with card type in the feature set, which would "
      "invalidate every leaf id, branch, map and sector -- still not done here.")
    A("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


if __name__ == "__main__":
    main()
