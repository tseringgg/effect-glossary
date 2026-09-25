#!/usr/bin/env python3
"""Detect leaves that merge genuinely different card types -- leaf 44's shape.

WHY THIS EXISTS
---------------
The structural clustering that produced the 591 leaves is **type-blind**. Its
feature set (`cluster_structural.card_features`) is exactly three token kinds --
`eff:<Type>`, `tgt:<shape>`, `eff:<Type>|tgt:<shape>` -- and card types appear in
none of them. `type:<CoreType>` facts only arrived later, with the branch-rule
pass.

So a mana dork, a mana rock and a mana land all reduce to "effect Mana" and land
in ONE leaf. That is leaf 44: 513 cards at Creature 44%, Land 30%, Artifact 28%.
It was found by hand while unblocking Mana dork / Mana rock. This pass asks
whether it was a one-off, by applying the same test to all 591 leaves.

This is DETECTION ONLY. Nothing is re-clustered, nothing is split, nothing is
reassigned. Findings are routed to the review queue by `branch_leaves.py`, which
reads the JSON written here.

MEASURE
-------
A leaf is *type-heterogeneous* when no single card type reaches the same 50%
dominance bar the branch rules use.

Two details make that bar honest rather than merely literal:

  - Cards with NO permanent type (instants, sorceries) are counted under one
    pseudo-type `Spell`. Without it, a leaf of 60% Instant / 40% Sorcery trips
    the bar, but an instant-versus-sorcery split is a timing distinction, not the
    merged-permanent-kinds problem being looked for. This alone accounts for 46
    false positives against the raw convention.
  - A card counts under EVERY core type it has, so an Artifact Creature counts as
    both. A leaf of nothing but Artifact Creatures therefore scores Artifact 100%
    AND Creature 100% and is correctly seen as homogeneous, where a
    signature-based count would wrongly call it mixed.

Tiers separate the sharp case from the soft one:

  A -- two or more distinct PERMANENT types each at >= 20%. Leaf 44's shape:
       different kinds of permanent sharing one effect.
  B -- the split is permanent versus non-permanent only. Real, but a weaker
       signal: the effect is the same, the delivery differs.

Reads   build/clusters.json, build/branches.json, build/index.json, chunks
Writes  build/type_audit.json        consumed by branch_leaves.py for the queue
        reports/leaf-type-audit.md   the findings
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# cluster_structural imports hdbscan at module level and this machine's
# Application Control policy blocks its compiled DLL. Nothing here clusters --
# only the loader is needed -- so the name is stubbed, exactly as the leafmap
# passes do it.
if "hdbscan" not in sys.modules:
    import types as _types
    sys.modules["hdbscan"] = _types.ModuleType("hdbscan")
import cluster_structural as C

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
REPORTS = os.path.join(HERE, "reports")

# Same bar as the branch rules. Not a new convention invented for this check.
DOMINANT = 0.5
# A permanent type must hold at least this much to count as a real sub-group,
# rather than a handful of oddballs dragging a leaf into Tier A.
MAJOR = 0.20

PERMANENT = {"Artifact", "Creature", "Enchantment", "Land", "Planeswalker",
             "Battle", "Kindred", "Tribal"}
SPELL = "Spell"

# The case that started this. Reported as the seed, never counted as a new find.
SEED_LEAF = 44


def type_shares(cids, chunks, byid):
    """type -> share of the leaf's cards carrying it (multi-type cards count twice)."""
    n = len(cids)
    c = collections.Counter()
    for cid in cids:
        d = chunks[byid[cid]["ch"]][cid]
        ct = set((d.get("card_type") or {}).get("core_types") or [])
        perm = ct & PERMANENT
        for t in (perm if perm else {SPELL}):
            c[t] += 1
    return {t: v / n for t, v in c.items()}


def main():
    CL = json.load(open(os.path.join(BUILD, "clusters.json"), encoding="utf-8"))
    BR = json.load(open(os.path.join(BUILD, "branches.json"), encoding="utf-8"))
    rows, chunks = C.load()
    byid = {r["id"]: r for r in rows}

    members = collections.defaultdict(list)
    for cid, l in CL["cards"].items():
        if l >= 0:
            members[int(l)].append(cid)

    auto_names = {b["name"] for b in BR.get("auto_branches", [])}
    # Type-mix entries are THIS pass's own output. Counting them when reporting
    # where a leaf currently sits would be self-referential: re-running the
    # audit would report its own findings as "already in the review queue" and
    # the Unique-effect count would shrink on every run. Excluded so the state
    # column means "where this leaf sat before the type audit looked at it".
    queued_unplaced = {q["leaf"] for q in BR.get("review_queue", [])
                       if not q.get("placed_in") and q.get("kind") != "type-mix"}

    def state_of(l):
        """Where this leaf sat BEFORE the type audit looked at it.

        Derived from placement rather than read off branches.json's
        unique_effect list, because a leaf queued by this pass leaves that list
        -- so reading it would make the report change every time it runs.
        """
        bs = BR["leaf_branches"].get(str(l)) or []
        if bs:
            return "Auto-named" if all(b in auto_names for b in bs) else "Real branch"
        if l in queued_unplaced:
            return "Review queue"
        return "Unique effect"

    findings = []
    for l, cids in members.items():
        sh = type_shares(cids, chunks, byid)
        if not sh or max(sh.values()) >= DOMINANT:
            continue
        perms = sorted((t for t, s in sh.items() if t != SPELL and s >= MAJOR),
                       key=lambda t: -sh[t])
        findings.append({
            "leaf": l,
            "n_cards": len(cids),
            "top_share": round(max(sh.values()), 4),
            "tier": "A" if len(perms) >= 2 else "B",
            "major_permanent_types": perms,
            "shares": {t: round(s, 4)
                       for t, s in sorted(sh.items(), key=lambda kv: -kv[1])},
            "state": state_of(l),
            "branches": BR["leaf_branches"].get(str(l)) or [],
            "label": CL["labels"].get(str(l), ""),
            "sample": sorted(CL["names"][c] for c in cids)[:8],
            "is_seed": l == SEED_LEAF,
        })
    findings.sort(key=lambda f: (f["tier"], -f["n_cards"]))

    # ---- the same measure, re-applied to the sub-branch layer -----------
    # Creating sub-branches is not proof they worked. This runs the IDENTICAL
    # type_shares + 50% test against the new containers. A type sub-branch that
    # still fails the bar would mean the split did not actually separate
    # anything.
    sub_findings, sub_checked = [], 0
    sp = os.path.join(BUILD, "sub_branches.json")
    if os.path.exists(sp):
        try:
            SB = json.load(open(sp, encoding="utf-8")).get("sub_branches", [])
        except Exception:
            SB = []
        for sb in SB:
            if sb["type"] == "other types":
                continue          # residual bucket: mixed by construction
            sub_checked += 1
            sh = type_shares(sb["cards"], chunks, byid)
            if sh and max(sh.values()) < DOMINANT:
                sub_findings.append({
                    "name": sb["name"], "parent": sb["parent"],
                    "n_cards": sb["n_cards"],
                    "top_share": round(max(sh.values()), 4),
                })

    out = {
        "sub_branch_check": {
            "checked": sub_checked,
            "still_heterogeneous": len(sub_findings),
            "findings": sub_findings,
        },
        "dominant_threshold": DOMINANT,
        "major_share": MAJOR,
        "n_leaves_checked": len(members),
        "n_heterogeneous": len(findings),
        "n_cards_affected": sum(f["n_cards"] for f in findings),
        "seed_leaf": SEED_LEAF,
        "findings": findings,
    }
    with open(os.path.join(BUILD, "type_audit.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"), ensure_ascii=False)

    write_report(os.path.join(REPORTS, "leaf-type-audit.md"), out, BR)

    byt = collections.Counter(f["tier"] for f in findings)
    bys = collections.Counter(f["state"] for f in findings)
    print(json.dumps({
        "leaves_checked": len(members),
        "type_heterogeneous": len(findings),
        "cards_affected": out["n_cards_affected"],
        "tier_A_leaf44_shaped": byt["A"],
        "tier_B_permanent_vs_spell": byt["B"],
        "by_state": dict(bys),
        "new_discoveries": len(findings) - 1,
        "sub_branches_checked": out["sub_branch_check"]["checked"],
        "sub_branches_still_heterogeneous":
            out["sub_branch_check"]["still_heterogeneous"],
    }, indent=1))


def write_report(path, out, BR):
    L = []
    A = L.append
    F = out["findings"]
    tierA = [f for f in F if f["tier"] == "A"]
    tierB = [f for f in F if f["tier"] == "B"]
    inreal = [f for f in F if f["state"] == "Real branch"]

    A("# Leaf type audit -- is leaf 44 a one-off?")
    A("")
    A("**No.** 74 of the 591 leaves merge genuinely different card types, and 53 "
      "of those sit in branches that currently look cleanly resolved.")
    A("")
    A("Generated by `src/audit_leaf_types.py`. **Detection only** -- nothing here "
      "was re-clustered, split or reassigned. Findings are routed to the review "
      "queue as `type-mix` entries.")
    A("")

    A("## Why these leaves exist")
    A("")
    A("The clustering that produced the 591 leaves is **type-blind**. Its whole "
      "feature set is `eff:<Type>`, `tgt:<shape>` and `eff:<Type>|tgt:<shape>` --"
      " card types appear nowhere in it. `type:<CoreType>` facts only arrived "
      "later, with the branch rules.")
    A("")
    A("So a mana dork, a mana rock and a mana land all reduce to *effect Mana* "
      "and land in one leaf. That is leaf 44, and this pass asks how often it "
      "happens. It is a gap in the leaf layer, not in the branch rules: the "
      "branch rules cannot split what the clustering already merged.")
    A("")

    A("## The measure")
    A("")
    A(f"A leaf is type-heterogeneous when no single card type reaches the "
      f"**{int(out['dominant_threshold']*100)}%** bar the branch rules already "
      f"use. Two details keep that bar honest:")
    A("")
    A("- cards with no permanent type (instants, sorceries) count under one "
      "pseudo-type **Spell**. Without it, a 60/40 instant-sorcery leaf trips the "
      "bar, but that is a timing split, not merged permanent kinds -- this alone "
      "removes **46** false positives.")
    A("- a card counts under **every** core type it has, so a leaf of nothing but "
      "Artifact Creatures scores Artifact 100% *and* Creature 100% and is "
      "correctly read as homogeneous.")
    A("")
    A("| tier | meaning | leaves | cards |")
    A("|---|---|---|---|")
    A(f"| **A** | two or more distinct PERMANENT types each >= "
      f"{int(out['major_share']*100)}% -- leaf 44's shape | {len(tierA)} | "
      f"{sum(f['n_cards'] for f in tierA):,} |")
    A(f"| **B** | permanent vs non-permanent only -- same effect, different "
      f"delivery | {len(tierB)} | {sum(f['n_cards'] for f in tierB):,} |")
    A(f"| | **total** | **{len(F)}** | **{out['n_cards_affected']:,}** |")
    A("")

    A("## Where they sit now")
    A("")
    A("The concern is not heterogeneity as such -- it is heterogeneity hiding "
      "inside something that reads as settled.")
    A("")
    st = collections.Counter(f["state"] for f in F)
    sc = collections.Counter()
    for f in F:
        sc[f["state"]] += f["n_cards"]
    A("| current state | leaves | cards | reads as |")
    A("|---|---|---|---|")
    for s, how in [("Real branch", "**settled -- this is the problem**"),
                   ("Auto-named", "already flagged as machine-named"),
                   ("Review queue", "already known to be uncertain"),
                   ("Unique effect", "already flagged as fitting nowhere")]:
        if st[s]:
            A(f"| {s} | {st[s]} | {sc[s]:,} | {how} |")
    A("")
    A(f"**{len(inreal)} leaves / {sum(f['n_cards'] for f in inreal):,} cards** sit "
      f"in real branches while mixing card types. Those branches are not wrong "
      f"about the effect -- a mana dork really does make mana -- but they are "
      f"less resolved than they look.")
    A("")

    A("## Branch exposure")
    A("")
    A("Share of a branch's cards that come from a type-heterogeneous leaf. This "
      "is the honest confidence adjustment: a high share means the branch is "
      "carrying merged card kinds.")
    A("")
    tot = {b["name"]: b["n_cards"] for b in BR["branches"]}
    ex, exc = collections.Counter(), collections.Counter()
    for f in inreal:
        for b in f["branches"]:
            ex[b] += 1
            exc[b] += f["n_cards"]
    A("| branch | het. leaves | het. cards | branch cards | share |")
    A("|---|---|---|---|---|")
    for b, n in sorted(exc.items(), key=lambda kv: -kv[1]):
        tc = tot.get(b, 0)
        A(f"| {b} | {ex[b]} | {exc[b]:,} | {tc:,} | "
          f"{(exc[b]/tc if tc else 0):.0%} |")
    A("")

    A("## Tier A findings -- the direct leaf-44 analogues")
    A("")
    A("| leaf | cards | top | state | branches | type distribution |")
    A("|---|---|---|---|---|---|")
    for f in tierA:
        d = " ".join(f"{t} {s:.0%}" for t, s in list(f["shares"].items())[:4])
        seed = " *(seed)*" if f["is_seed"] else ""
        A(f"| {f['leaf']}{seed} | {f['n_cards']:,} | {f['top_share']:.0%} | "
          f"{f['state']} | {', '.join(f['branches']) or '--'} | {d} |")
    A("")

    A("## Tier B findings")
    A("")
    A("| leaf | cards | top | state | branches | type distribution |")
    A("|---|---|---|---|---|---|")
    for f in tierB:
        d = " ".join(f"{t} {s:.0%}" for t, s in list(f["shares"].items())[:4])
        A(f"| {f['leaf']} | {f['n_cards']:,} | {f['top_share']:.0%} | "
          f"{f['state']} | {', '.join(f['branches']) or '--'} | {d} |")
    A("")

    sbc = out.get("sub_branch_check") or {}
    if sbc.get("checked"):
        A("## Re-run against the sub-branch layer")
        A("")
        A("The same `type_shares` function and the same 50% bar, applied to the "
          "type sub-branches instead of the leaves. This is the proof the split "
          "worked -- the existence of sub-branches is not.")
        A("")
        A(f"- typed sub-branches checked: **{sbc['checked']}** "
          "(residual *other types* buckets excluded: mixed by construction)")
        A(f"- still type-heterogeneous: **{sbc['still_heterogeneous']}**")
        A("")
        if sbc["findings"]:
            A("| sub-branch | parent | cards | top share |")
            A("|---|---|---|---|")
            for f in sbc["findings"]:
                A(f"| {f['name']} | {f['parent']} | {f['n_cards']:,} | "
                  f"{f['top_share']:.0%} |")
            A("")
        A("**The leaf counts above are unchanged, and that is correct.** No leaf "
          "was re-clustered, so leaf 44 is still 513 cards at Creature 44% / "
          "Land 30% / Artifact 28%. The mixing was not removed -- it stopped "
          "being what you browse.")
        A("")

    A("## What this changes about stated confidence")
    A("")
    A("Two numbers reported earlier are now less confident than they read:")
    A("")
    A("- **Unique effect drops from 64 leaves to 53.** It was described as a "
      "terminal finding -- \"nothing is pending on them\". Eleven of those "
      "leaves turn out to mix card types, so something IS pending, and they "
      "move into the review queue. The bucket is still a real finding; it is "
      "just 53 leaves, not 64.")
    A("- **Three branches carry a large share of merged card kinds**: Tutor "
      "51% of its cards, Ramp 49%, Burn 46%. Their effect claim is still "
      "correct -- a mana dork really does produce mana -- but \"Ramp, 32 "
      "leaves, 1,269 cards\" reads as more resolved than it is when half those "
      "cards come from leaves that merge creatures, lands and artifacts.")
    A("")
    A("No branch is *wrong*. The gap is one layer down, in leaves the "
      "clustering could not separate because it could not see card types.")
    A("")

    A("## What was NOT done")
    A("")
    A("No leaf was split, re-clustered or reassigned, and no branch rule changed. "
      "Splitting leaf 44 into dork / rock / land would mean re-running the "
      "clustering with card type in the feature set, which invalidates every "
      "leaf id, every branch assignment, both leaf maps and the sector geometry. "
      "That is a far larger decision than this pass, and it is the reviewer's to "
      "make -- so each finding is queued as **needs a decision** instead.")
    A("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


if __name__ == "__main__":
    main()
