#!/usr/bin/env python3
"""Proposals for display-only merged group pages. PROPOSALS ONLY: writes build/merged_proposals.json (and, with --sheet, build/merged_read_sheet.txt); it never writes corrections/merged_groups.json. Nothing here changes a group id,
a placement, a count or a figure. The merge file is edited by hand.

    python src/propose_merged_groups.py            # seconds; reads the build files and reports/merged_reads.json (my marks: merge / don't merge / needs your decision, with the reason)
    python src/propose_merged_groups.py --sheet    # also writes the read sheet: every proposal's members with 3 sample cards each (seed 20263501, fixed before the proposals were computed)

MERGED_GROUPS = True writes the files; False writes nothing and removes them.

Inputs. (1) NAME-TWIN FAMILIES: groups whose names are the same once the qualifiers are removed (text in parentheses, and the text after an em dash): 73 families, 168 groups. Each qualifier is classed as a parser limit
(the parse lost a detail: "object varies", "follow-up varies", "what it applies to isn't recorded"), as a possible change of meaning (who controls it, a duration, a zone, the kind of object) or as unclear. A family whose
qualifiers are all parser limits is "limit only"; one with a meaning qualifier is "meaning"; the rest "unclear". (2) THREE HAND-CONFIRMED PAIRS from the overlap read of 2026-10-21. Left out by rule: overlap-only pairs, equipment and
aura grant groups ("Equipped creature ...", "Enchanted creature ...", "Attach ..."), a family with a hand-defined member that has hand placements, and the keyword filters.
"""
import collections
import io
import json
import os
import random
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as M
import build_group_search as B

MERGED_GROUPS = True
HERE = M.HERE
BUILD = os.path.join(HERE, "build")
OUT = os.environ.get("MERGED_OUT") or os.path.join(BUILD, "merged_proposals.json")                 # the env override is for the tests only
SHEET = os.path.join(os.path.dirname(OUT), "merged_read_sheet.txt")
READS = os.path.join(HERE, "reports", "merged_reads.json")
SEED = 20263501
TRUST = {"leaf": 0, "kw": 0, "rp": 0, "tent": 1, "tag": 2, "loose": 3, "hand": 4}
SECTION = {0: "precise", 1: "tentative", 2: "tag", 3: "loose", 4: "also here"}
EXCLUDE_NAMES = ("Equipped creature", "Enchanted creature", "Attach")
# qualifiers: the parse lost a detail (a parser limit) / a difference a player may care about (meaning)
LIMIT = ("object varies", "restriction varies", "number varies", "follow-up varies", "isn't recorded", "isn’t recorded", "any target", "targeted", "several", "then move a chosen card", "the parse says", "reliably recorded", "excluding some kind")
MEANING = ("you control", "an opponent controls", "ability duration", "to the hand", "to the graveyard", "to the battlefield", "mana value", "artifact creature", "permanent;")
HAND_PAIRS = [
    {"slug": "copies-instants-and-sorceries", "name": "Copies an instant or a sorcery", "members": ["tag:300f5a3d-01c5-43a7-b1f4-847afe5bf961", "tag:3fd34377-67d3-44fc-9db2-2de7fe13edd6"],
     "description": "Cards that copy an instant spell or a sorcery spell. The community tags \"Copies sorcery\" and \"Copies instant\" hold the same 11 cards.", "basis": "hand-confirmed near-duplicate (11 of 11 cards in common)"},
    {"slug": "draw-engines", "name": "Draw engine: draws a card again and again", "members": ["tag:0e87cf9c-591e-4f2a-b4fd-675021f120ae", "tag:524845ed-ea82-4a60-8b54-8a38ab06a503"],
     "description": "Cards that draw more cards over and over. \"Draws a card again and again with no other cost\" is all of its 31 cards inside \"Draw engine\" (36).", "basis": "hand-confirmed near-duplicate (31 of 31 inside 36)"},
    {"slug": "raises-power-of-your-creatures", "name": "Raises the power of your creatures", "members": ["tag:e7f7559f-5ddd-4262-90ad-04f2ea2a735b", "tag:0454fcef-0118-4f10-b9d7-c071845bfbd4"],
     "description": "Cards that raise the power of all your creatures, or of a type. \"Gives your whole team +N/+N\" is 10 cards, all inside \"Raises the power of your creatures\" (13).", "basis": "hand-confirmed sub-group (10 of 10 inside 13)"},
]


def qualifiers(name):
    return [q.strip() for q in re.findall(r"\(([^)]*)\)", name)] + [q.strip() for q in re.findall(r"—\s*(.*)$", name)]


def core(name):
    return re.sub(r"\s*\([^)]*\)", "", re.sub(r"\s+—.*$", "", name)).strip()


def kind(q):
    if any(m in q for m in MEANING):
        return "meaning"
    if any(l in q for l in LIMIT):
        return "limit"
    return "unclear"


def family_class(names):
    ks = {kind(q) for n in names for q in qualifiers(n)}
    if "meaning" in ks:
        return "meaning"
    if "unclear" in ks:
        return "unclear"
    return "limit"


def sample_lines(groups_members):
    """gid -> {oid: rules line} for the leaf, tentative and loose groups (the card's own line in that group); other layers have no line."""
    cards = B.jl(os.path.join(BUILD, "ability_taxonomy_cards.json"))["cards"]
    mem = B.jl(os.path.join(BUILD, "ability_taxonomy_members.json"))["leaves"]
    tent = B.jl(os.path.join(BUILD, "tentative_placements.json"))["groups"]
    loose = B.jl(os.path.join(BUILD, "loose_groups.json"))["groups"]
    out = {}
    for gid in groups_members:
        layer, _, i = gid.partition(":")
        d = {}
        if layer == "leaf":
            for oid, ai in mem.get(i, []):
                c = cards.get(oid)
                if c and ai is not None and ai < len(c["ab"]):
                    d[oid] = c["ab"][ai][0]
        elif layer == "tent":
            d = {r[0]: r[1] for r in tent[i]["m"]}
        elif layer == "loose":
            d = {r[0]: r[1] for r in loose[i]["m"]}
        out[gid] = d
    return out, cards


def main(force=None, sheet=None):
    on = MERGED_GROUPS if force is None else force
    if not on:
        for p in (OUT, SHEET):
            if os.path.exists(p) and not os.environ.get("MERGED_OUT"):
                os.remove(p)
        print("MERGED_GROUPS is off: nothing written")
        return 0
    sheet = ("--sheet" in sys.argv) if sheet is None else sheet
    groups = [e for e in B.load_groups() if e["layer"] != "yk"]
    by = {e["gid"]: e for e in groups}
    mem = B.group_members(groups)
    mem = {g: m for g, m in mem.items() if g in by}
    mi = B.jl(os.path.join(BUILD, "manual_index.json"))
    rank = {o: v[4] for o, v in mi["cards"].items()}
    cname = {o: v[0] for o, v in mi["cards"].items()}
    try:
        placed_hand = set()
        doc = json.load(io.open(os.path.join(HERE, "corrections", "manual_placements.json"), encoding="utf-8"))
        for e in doc.get("edits", {}).values():
            for g, x in e["groups"].items():
                if g.startswith("hand:") and x.get("action") == "add":
                    placed_hand.add(g)
    except (IOError, ValueError):
        placed_hand = set()
    reads = json.load(io.open(READS, encoding="utf-8")) if os.path.exists(READS) else {}
    desc = {}
    d = B.read_json_or(B.DESCS, {})
    for part in ("drafts", "edits"):
        for gid, v in (d.get(part) or {}).items():
            desc[gid] = v["text"]
    # ---- name-twin families
    fam = collections.defaultdict(list)
    for e in groups:
        fam[core(e["full"]).lower()].append(e["gid"])                                  # the manual index's names (a tentative or loose group carries its family: "Tokens > Create tokens")
    fam = {k: sorted(v) for k, v in fam.items() if len(v) > 1}
    short = collections.defaultdict(list)
    for e in groups:
        short[core(e["name"]).lower()].append(e["gid"])
    short_only = {k: v for k, v in short.items() if len(v) > 1 and k not in fam and not any(set(v) <= set(m) for m in fam.values())}
    pages, excluded = [], []
    for key, ms in sorted(fam.items()):
        names = [by[g]["full"] for g in ms]
        cls = family_class(names)
        why_out = None
        if any(n.startswith(EXCLUDE_NAMES) for n in names):
            why_out = "equipment or aura grant group"
        elif any(g.startswith("hand:") and g in placed_hand for g in ms):
            why_out = "a member is a hand-defined group with hand placements"
        if why_out:
            excluded.append({"family": key, "members": ms, "reason": why_out, "class": cls})
            continue
        big = max(ms, key=lambda g: (by[g]["size"], g))
        nm = core(by[big]["full"])
        quals = sorted({q for n in names for q in qualifiers(n)})
        pages.append({"slug": "twin-" + re.sub(r"[^a-z0-9]+", "-", key)[:34].strip("-") + "-" + big.split(":")[1][:4], "family": key, "kind": "name-twins", "class": cls, "members": ms, "name": nm,
                      "description": "%s. One effect, kept as %d groups in the build because of what the parser could or could not record (%s); the page shows them together." % (nm, len(ms), "; ".join(quals) if quals else "details the group name does not show"),
                      "aliases": sorted({by[g]["full"] for g in ms} | {by[g]["name"] for g in ms}), "basis": "name-twins: the same name once the qualifiers are removed"})
    for h in HAND_PAIRS:
        pages.append({"slug": h["slug"], "family": h["slug"], "kind": "hand-confirmed", "class": "hand-confirmed", "members": h["members"], "name": h["name"], "description": h["description"],
                      "aliases": sorted({by[g]["name"] for g in h["members"]}), "basis": h["basis"]})
    # ---- numbers per page
    seen_in = collections.defaultdict(list)
    for p in pages:
        for g in p["members"]:
            seen_in[g].append(p["slug"])
        p["members"] = sorted(p["members"], key=lambda g: (TRUST[by[g]["layer"]], -by[g]["size"], g))          # trust order: the first member is the page's key
        p["per_group"] = {g: len(mem[g]) for g in p["members"]}
        un = set().union(*[mem[g] for g in p["members"]])
        p["union"] = len(un)
        p["in_two_members"] = sum(1 for o in un if sum(1 for g in p["members"] if o in mem[g]) > 1)
        secs = collections.OrderedDict()
        for g in sorted(p["members"], key=lambda g: (TRUST[by[g]["layer"]], -by[g]["size"], g)):
            secs.setdefault(SECTION[TRUST[by[g]["layer"]]], []).append(g)
        p["sections"] = secs
        r = reads.get(p["family"]) or {}
        p["mark"], p["reason"] = r.get("mark", "unread"), r.get("why", "")
    clash = {g: v for g, v in seen_in.items() if len(v) > 1}
    out = {"v": 1, "seed": SEED, "pages": pages, "excluded": excluded,
           "short_name_collisions_not_proposed": {k: v for k, v in sorted(short_only.items())},
           "summary": {"name_twin_families": len(fam), "short_name_collisions_not_proposed": len(short_only), "name_twin_groups": sum(len(v) for v in fam.values()), "excluded_families": len(excluded), "proposed_pages": len(pages),
                       "by_class": dict(collections.Counter(p["class"] for p in pages)), "by_mark": dict(collections.Counter(p["mark"] for p in pages)),
                       "groups_covered": len(seen_in), "groups_in_two_pages": clash}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    print("proposals: %d pages (%d name-twin families after %d excluded, 3 hand-confirmed pairs), %d groups covered, %d groups in two pages; by class %s; by mark %s" % (
        len(pages), len(pages) - 3, len(excluded), len(seen_in), len(clash), out["summary"]["by_class"], out["summary"]["by_mark"]))
    if sheet:
        lines, cards = sample_lines({g for p in pages for g in p["members"]})
        rnd = random.Random(SEED)
        L = []
        for p in sorted(pages, key=lambda p: p["family"]):
            L.append("== %s [%s, %s] %s" % (p["family"], p["kind"], p["class"], p["slug"]))
            for g in sorted(p["members"]):
                ms = sorted(mem[g])
                pick = rnd.sample(ms, 3) if len(ms) > 3 else ms
                s = []
                for o in pick:
                    ln = lines[g].get(o, "")
                    s.append("%s%s" % (cname.get(o, o), (" “" + re.sub(r"\s+", " ", ln)[:80] + "”") if ln else ""))
                L.append("   %-24s %5d  %s\n        e.g. %s" % (g, len(ms), by[g]["name"][:120], "  |  ".join(s)))
        with io.open(SHEET, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(L) + "\n")
        print("read sheet: %s" % SHEET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
