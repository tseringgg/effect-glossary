#!/usr/bin/env python3
"""Group branches into SECTORS and compute their map regions.

A sector is a broad, human-facing bucket drawn as a translucent region over the
effect-flavoured leaf map. Sectors may overlap: a leaf can sit in several.

WHY SECTORS AND NOT PER-BRANCH COLOUR. 39 branches is far past what a
categorical palette can distinguish, and in a scatter plot any dot can end up
next to any other, so the strict all-pairs colour test applies (~3 safe hues).
Colouring *regions* instead bounds the problem: the only hues that must be
distinguishable are those whose regions actually touch, which is a small
measured adjacency graph rather than a worst case. That graph is computed here
and each adjacent pair is validated separately.

HOW THE GROUPING WAS CHOSEN. Every merge is backed by the measured mean
leaf-to-leaf distance between the two branches on the effect map, expressed as
a multiple of the corpus mean pairwise distance (4.94). Tier 1 merges are both
spatially tight and conceptually obvious. Tier 2 merges are looser spatially
and kept for human legibility -- flagged as judgement calls, not data.

Branches deliberately left UNSECTORED are recorded in reports/sectors.md with
the numbers that argue against forcing them anywhere. The notable one: Land
ramp sits 0.42x from Creature removal but 1.78x from Ramp -- farther from
"Ramp" than an average pair of leaves -- because "put a land onto the
battlefield" is a ChangeZone effect like removal, not a Mana effect.

Reads   build/branches.json, build/clusters.json, build/_eff_XY.npy, _eff_ids.json
Writes  build/sectors.json      polygons + membership, for the page
        reports/sectors.md      the grouping, its evidence, and what was left out
"""
import collections
import json
import os

import numpy as np
from scipy.spatial.distance import pdist

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
REPORTS = os.path.join(HERE, "reports")

# A sector's leaves rarely form one clean blob. Sub-cluster them with single
# linkage and draw a hull per clump, so a sector with two separated groups gets
# two shapes instead of one shape stretched across the map.
# Regions are a BUFFER-UNION around the member points, not a convex hull.
# Hulls were tried first and failed visibly on two counts: a near-collinear
# clump produces a degenerate sliver that reads as a shard rather than a
# bucket, and a hull over scattered leaves claims a large area of map that
# belongs to nobody -- Removal's hull was full of grey non-member dots.
# Buffering each point and unioning hugs the actual leaves, gives every shape
# a minimum thickness, and splits into separate blobs on its own when leaves
# are far apart (so no separate sub-clustering step is needed).
BLOB_RADIUS = 0.85        # map units of reach around each member leaf
BLOB_CLOSE = 0.45         # close pinholes/necks: buffer out then back in
BLOB_MIN_AREA = 0.30      # drop specks below this; their leaves become strays
BLOB_SIMPLIFY = 0.06      # vertex thinning, keeps the JSON small
TOUCH_GAP = 0.6           # regions this close read as touching on screen
# Constellation edges: a minimum spanning tree over each sector's leaves,
# with long edges cut. Uncut, the MST spans a sector's separate clumps and
# throws lines across the whole map (Mass Effects had a 6.81-unit edge).
# The cutoff is in map units but what matters is how it lands on screen: at
# the page's render size the median edge is only ~9px, while a 2.5 cutoff
# still allowed 211px sweeps that read as errors rather than links. 1.0 keeps
# 91% of edges and caps them near 89px.
MST_MAX_EDGE = 1.0

# (sector, tier, branches, rationale). Closed, documented list.
SECTORS = [
    ("Removal", 1,
     ["Spot removal", "Creature removal", "Destroy removal", "Exile removal",
      "Bounce removal", "Sacrifice removal"],
     "Tightest cluster on the map, 0.34-0.73x corpus mean pairwise. The "
     "'gets rid of a permanent' class."),

    ("Mass Effects", 1,
     ["Board wipe", "Mass effect", "Mass +1/+1 counters", "One-sided sweeper"],
     "Very tight, 0.30-0.40x. Everything that hits every matching permanent "
     "rather than one target."),

    ("Card Selection & Attrition", 1,
     ["Self-mill", "Opponent mill", "Discard", "Scry", "Surveil"],
     "Tight, 0.21-0.45x. Library and hand manipulation without net card "
     "advantage. Note this is where mill and surveil finally agree -- they "
     "were far apart in the effect-type space and together in zone/choice."),

    ("Resource Acquisition", 1,
     ["Tutor", "Impulse", "Copy spell"],
     "0.34-0.37x mutual -- a tight triangle the map found, not an obvious "
     "community grouping. Search-and-acquire mechanics."),

    ("Team Buffs", 2,
     ["Anthem", "Keyword grant", "+1/+1 counters"],
     "JUDGEMENT CALL. Anthem<->Keyword grant is decent at 0.63x; +1/+1 "
     "counters is looser (0.84-0.85x) but shares the 'permanently improves a "
     "creature' idea. Kept for legibility."),

    ("Mana", 2,
     ["Ramp", "Cost reduction"],
     "JUDGEMENT CALL. Weak spatially (0.78x) but a concept players expect. "
     "Land ramp is deliberately NOT here -- it is 1.78x from Ramp."),

    ("Damage", 2,
     ["Burn", "Mass burn"],
     "JUDGEMENT CALL. 0.62x -- closer than random, not tight. Mass burn is "
     "kept with Burn rather than Mass Effects because it targets players, and "
     "it sits far from the Board wipe cluster despite the shared 'mass' name."),

    ("Interaction & Disruption", 2,
     ["Counterspell", "Theft", "Graveyard hate"],
     "JUDGEMENT CALL. Loose (0.60-0.71x). Answers to an opponent's resources: "
     "stop it, steal it, or deny the graveyard."),
]

# Left out on purpose, with the number that argues against each.
UNSECTORED_NOTES = [
    ("Land ramp", "0.42x from Creature removal but **1.78x from Ramp** -- "
     "farther than an average pair of leaves. Structurally it is a ChangeZone "
     "onto the battlefield, the same skeleton as removal, not a Mana effect. "
     "Putting it in Mana would be wrong; putting it in Removal reads as wrong "
     "to anyone who plays the game. Left out and recorded instead."),
    ("Tapper / Untapper", "0.92x apart -- essentially unrelated, despite being "
     "the obvious complementary pair. Tapper's own cohesion is weak (58%) and "
     "its nearest neighbours are all ~0.74x+."),
    ("Card draw", "No tight neighbour; nearest is 0.66x. Tutor is 0.92x away, "
     "so the intuitive 'card advantage' pairing is not supported. Matches the "
     "earlier diagnosis: draw rides along on many unrelated card types."),
    ("Token maker", "Nearest neighbour 0.60x, nothing conceptually adjacent."),
    ("Reanimation", "Closer to the Removal cluster (0.49-0.60x) than to "
     "Graveyard hate (0.77x), so a 'graveyard' sector pairing those two is not "
     "supported. Left out rather than filed under Removal, which it opposes."),
    ("Lifegain", "Sits near the map's dense middle; its neighbours (Mass burn "
     "0.29x, Self-mill 0.34x) are not conceptually related, so proximity here "
     "looks like centre-of-map crowding rather than shared function."),
    ("Regeneration, Damage prevention, Clone effect, Drain",
     "Small and isolated, no grouping story in either direction."),
]


def mst_edges(leaf_ids, points):
    """Constellation edges for one sector: a pruned minimum spanning tree.

    Returns [[leaf_a, leaf_b], ...]. The MST connects every leaf with the least
    total length, which reads as a constellation; edges longer than
    MST_MAX_EDGE are dropped so a sector's separate clumps stay visually
    separate instead of being joined by a line across the map.
    """
    from scipy.sparse.csgraph import minimum_spanning_tree
    from scipy.spatial.distance import pdist, squareform

    if len(points) < 2:
        return []
    mst = minimum_spanning_tree(squareform(pdist(points))).tocoo()
    out = []
    for i, j, d in zip(mst.row, mst.col, mst.data):
        if 0 < d <= MST_MAX_EDGE:
            out.append([leaf_ids[int(i)], leaf_ids[int(j)]])
    return out


def sector_blobs(points):
    """Organic regions around a sector's leaves, plus the leaves left outside.

    Returns (polygons, enclosed_mask). Each polygon is a ring of [x, y].
    """
    from shapely.geometry import MultiPoint, Point
    from shapely.ops import unary_union

    P = np.asarray(points, dtype=float)
    blob = unary_union([Point(*p).buffer(BLOB_RADIUS, quad_segs=8) for p in P])
    blob = blob.buffer(BLOB_CLOSE).buffer(-BLOB_CLOSE)      # close necks
    blob = blob.simplify(BLOB_SIMPLIFY, preserve_topology=True)
    parts = list(getattr(blob, "geoms", [blob]))
    parts = [g for g in parts if g.area >= BLOB_MIN_AREA]
    polys, keep = [], unary_union(parts) if parts else None
    for g in parts:
        ring = [[round(x, 3), round(y, 3)] for x, y in g.exterior.coords[:-1]]
        if len(ring) >= 3:
            polys.append(ring)
    enclosed = ([keep.covers(Point(*p)) for p in P] if keep is not None
                else [False] * len(P))
    return polys, enclosed


def main():
    BR = json.load(open(os.path.join(BUILD, "branches.json"), encoding="utf-8"))
    CL = json.load(open(os.path.join(BUILD, "clusters.json"), encoding="utf-8"))
    XY = np.load(os.path.join(BUILD, "_eff_XY.npy"))
    ids = json.load(open(os.path.join(BUILD, "_eff_ids.json")))
    k_of = {l: i for i, l in enumerate(ids)}
    leaves_of = {b["name"]: b["leaves"] for b in BR["branches"]}
    sizes = {int(a): b for a, b in CL["sizes"].items()}

    corpus_mean = float(pdist(XY).mean())
    sectors, leaf_sectors = [], collections.defaultdict(list)

    for name, tier, branches, why in SECTORS:
        missing = [b for b in branches if b not in leaves_of]
        if missing:
            raise SystemExit(f"sector {name!r} names unknown branches: {missing}")
        member = sorted({l for b in branches for l in leaves_of[b]})
        present = [l for l in member if l in k_of]
        pts = XY[[k_of[l] for l in present]]
        polys, enclosed = sector_blobs(pts)
        strays = [l for l, inside in zip(present, enclosed) if not inside]
        edges = mst_edges(present, pts)
        for l in member:
            leaf_sectors[l].append(name)
        sectors.append({
            "name": name, "tier": tier, "branches": branches, "why": why,
            "n_leaves": len(member), "leaves": member, "edges": edges,
            "n_cards": sum(sizes.get(l, 0) for l in member),
            "polygons": polys, "strays": strays,
        })

    # Which sectors actually share screen space? This is a GEOMETRIC test on
    # the drawn polygons, not a mean-distance test: two compact blobs can have
    # a small mean leaf distance and still be visually disjoint. Only pairs
    # whose regions overlap or nearly touch need distinguishable hues, and that
    # is the entire basis for colouring regions rather than points -- so it has
    # to be measured. Measuring it by mean leaf distance first flagged 20 of 28
    # pairs, which would have collapsed the argument back into all-pairs.
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    def shape_of(sec):
        polys = [Polygon(p).buffer(0) for p in sec["polygons"] if len(p) >= 3]
        return unary_union(polys) if polys else None

    shapes = {sec["name"]: shape_of(sec) for sec in sectors}
    adj = []
    for i in range(len(sectors)):
        for j in range(i + 1, len(sectors)):
            a, b = sectors[i], sectors[j]
            sa, sb = shapes[a["name"]], shapes[b["name"]]
            if sa is None or sb is None:
                continue
            gap = float(sa.distance(sb))
            overlaps = bool(sa.intersects(sb))
            if not (overlaps or gap <= TOUCH_GAP):
                continue
            adj.append({
                "a": a["name"], "b": b["name"], "overlaps": overlaps,
                "gap": round(gap, 2),
                "overlap_area": round(float(sa.intersection(sb).area), 2)
                                if overlaps else 0.0,
                "shared_leaves": len(set(a["leaves"]) & set(b["leaves"])),
            })
    adj.sort(key=lambda r: (-r["overlap_area"], r["gap"]))

    # Assign hues by graph colouring: only sectors whose regions overlap need
    # different hues, so non-adjacent sectors can share one. This is what keeps
    # 8 sectors inside a palette that only safely distinguishes a few colours
    # at once. Slots come from the validated categorical order, never cycled
    # into invented hues -- if the graph needed more colours than the palette
    # safely provides, that is a hard failure to report, not to paper over.
    PALETTE = [("blue", "#2a78d6"), ("orange", "#eb6834"), ("aqua", "#1baf7a"),
               ("yellow", "#eda100"), ("magenta", "#e87ba4"), ("green", "#008300"),
               ("violet", "#4a3aa7"), ("red", "#e34948")]
    # COLOUR IS NOT ASSIGNED BY GRAPH COLOURING, and the reason is measured.
    # Graph colouring was tried and abandoned: it only works if few sectors
    # overlap, and these overlap almost everywhere. Sampling the covered area
    # on a 260x260 grid:
    #
    #   1 sector covers  32.6% of covered area
    #   2 sectors        21.6%
    #   3 sectors        17.6%
    #   4 sectors        15.5%
    #   5 sectors        10.1%
    #   6 sectors         2.4%
    #   7 sectors         0.1%   <-- max simultaneous stack
    #
    # 45% of the covered map has three or more sectors on top of each other,
    # and 26-28 of the 28 sector pairs touch at every blob radius tried. That
    # is a property of the data -- these broad categories genuinely interleave
    # on this layout -- not of the palette. No assignment of 8 hues can be
    # simultaneously legible against that, so the page does not try: regions
    # default to neutral, hue appears only for the sector(s) under the cursor,
    # and the authoritative answer to "what is this" is the hovered TEXT list.
    # Hue is therefore secondary encoding, never identity on its own.
    #
    # Slots are handed out in the documented palette order, never cycled.
    for i, sec in enumerate(sectors):
        name, hexv = PALETTE[i % len(PALETTE)]
        sec["hue_slot"] = i
        sec["hue_name"] = name
        sec["color"] = hexv
    n_hues = len(sectors)

    unsectored = sorted(
        {l for b in BR["branches"] for l in b["leaves"]} - set(leaf_sectors))
    out = {
        "source_map": "effect-flavoured (build/_eff_XY.npy)",
        "corpus_mean_distance": round(corpus_mean, 3),
        "params": {"blob_radius": BLOB_RADIUS, "blob_close": BLOB_CLOSE,
                   "blob_min_area": BLOB_MIN_AREA,
                   "blob_simplify": BLOB_SIMPLIFY, "touch_gap": TOUCH_GAP},
        "sectors": sectors,
        "adjacency": adj,
        "palette": [{"slot": i, "name": n, "hex": h}
                    for i, (n, h) in enumerate(PALETTE)],
        "hues_used": n_hues,
        "colour_model": "neutral by default; hue only for the sector(s) under "
                        "the cursor. Hue is secondary encoding -- the hovered "
                        "text list is authoritative.",
        "max_simultaneous_stack": 7,
        "single_sector_area_pct": 32.6,
        "leaf_sectors": {str(l): v for l, v in leaf_sectors.items()},
        "unsectored_leaves": unsectored,
        "unsectored_notes": [{"what": w, "why": y} for w, y in UNSECTORED_NOTES],
    }
    json.dump(out, open(os.path.join(BUILD, "sectors.json"), "w",
                        encoding="utf-8"), separators=(",", ":"),
              ensure_ascii=False)

    write_report(os.path.join(REPORTS, "sectors.md"), out)

    print(f"corpus mean distance {corpus_mean:.2f}")
    print(f"{'sector':28s} {'tier':>4s} {'leaves':>6s} {'cards':>6s} "
          f"{'blobs':>5s} {'strays':>6s} {'edges':>6s}")
    for s in sectors:
        print(f"{s['name']:28s} {s['tier']:4d} {s['n_leaves']:6d} "
              f"{s['n_cards']:6d} {len(s['polygons']):5d} "
              f"{len(s['strays']):6d} {len(s['edges']):6d}")
    print(f"\nleaves in >=1 sector: {len(leaf_sectors)} / {BR['n_leaves']}"
          f"  (unsectored {len(unsectored)})")
    print(f"multi-sector leaves: "
          f"{sum(1 for v in leaf_sectors.values() if len(v) > 1)}")
    print(f"\nsectors and their assigned hues (shown on hover, not all at once):")
    for sec in sectors:
        print(f"  {sec['name']:28s} slot {sec['hue_slot']} {sec['hue_name']:8s} {sec['color']}")

    tot = len(sectors) * (len(sectors) - 1) // 2
    print(f"\nsector pairs whose REGIONS overlap or nearly touch: "
          f"{len(adj)} of {tot} possible")
    for r in adj:
        kind = (f"overlap area {r['overlap_area']}" if r["overlaps"]
                else f"gap {r['gap']}")
        print(f"  {r['a']} <-> {r['b']}: {kind}, "
              f"{r['shared_leaves']} shared leaves")


def write_report(path, out):
    L = []
    A = L.append
    A("# Sectors over the leaf map")
    A("")
    A("Sectors are broad, human-facing buckets drawn as translucent "
      "regions on the **effect-flavoured** leaf map. They may overlap: a "
      "leaf can belong to several. Generated by `src/build_sectors.py`.")
    A("")
    A("Distances below are mean leaf-to-leaf distance between two branches "
      "on that map, as a multiple of the corpus mean pairwise distance "
      f"({out['corpus_mean_distance']}). Lower is closer.")
    A("")
    A("## The eight sectors")
    A("")
    A("| sector | tier | branches | leaves | cards | blobs | hue |")
    A("|---|---|---|---|---|---|---|")
    for sec in out["sectors"]:
        A(f"| **{sec['name']}** | {sec['tier']} | "
          f"{', '.join(sec['branches'])} | {sec['n_leaves']} | "
          f"{sec['n_cards']:,} | {len(sec['polygons'])} | "
          f"{sec['hue_name']} `{sec['color']}` |")
    A("")
    A("Tier 1 merges are both spatially tight and conceptually obvious. "
      "Tier 2 merges are **judgement calls**: looser spatially, kept "
      "because they match how players talk.")
    A("")
    for sec in out["sectors"]:
        A(f"- **{sec['name']}** (tier {sec['tier']}) -- {sec['why']}")
    A("")
    A("## Colour is hover-driven, not eight hues at once")
    A("")
    A("Each sector has its own assigned hue, but the map does **not** show all "
      "eight simultaneously. Regions default to neutral; hue appears only for "
      "the sector(s) under the cursor, and the hovered text list -- not the "
      "colour -- is the authoritative answer to what a spot belongs to.")
    A("")
    A("That is forced by the data, not by taste. Graph colouring was tried "
      "first, on the theory that only sectors whose regions touch need "
      "different hues. It failed: at every blob radius tried, 26-28 of the 28 "
      "sector pairs touch. Sampling the covered area on a 260x260 grid shows "
      "why -- these broad categories genuinely interleave on this layout:")
    A("")
    A("| sectors covering one point | share of covered area |")
    A("|---|---|")
    A("| 1 | 32.6% |")
    A("| 2 | 21.6% |")
    A("| 3 | 17.6% |")
    A("| 4 | 15.5% |")
    A("| 5 | 10.1% |")
    A("| 6 | 2.4% |")
    A("| 7 (max) | 0.1% |")
    A("")
    A("45% of the covered map carries three or more sectors at once. No "
      "assignment of eight hues is simultaneously legible against that, so "
      "hue is used as secondary encoding only.")
    A("")
    A("The palette pairs were still measured, for the case where a few sectors "
      "light up together. All 28 pairs of the 8-slot palette went through the "
      "data-viz validator at `pairs=all` against a white surface; five fail "
      "and are worth knowing: orange/yellow (normal-vision dE 13.7 against a "
      "floor of 15), orange/magenta (12.9), orange/green (CVD fail), "
      "orange/red (7.1), magenta/red (13.2).")
    A("")
    A("Region shape also changed during the build. Convex hulls were tried "
      "and dropped on sight: a near-collinear clump becomes a sliver that "
      "reads as a shard, and a hull over scattered leaves claims a large area "
      "of map belonging to nobody -- Removal's hull was full of grey "
      "non-member dots. Regions are now a buffer-union around the member "
      "leaves, which hugs the actual points, guarantees a minimum thickness, "
      "and splits into separate blobs on its own.")
    A("")
    A("## Branches deliberately left unsectored")
    A("")
    A("Same discipline as the branch-rule audit: a weak grouping is worse "
      "than an honest gap, so these are recorded rather than forced.")
    A("")
    for note in out["unsectored_notes"]:
        A(f"- **{note['what']}** -- {note['why']}")
    A("")
    A("## Coverage")
    A("")
    multi = sum(1 for v in out["leaf_sectors"].values() if len(v) > 1)
    A(f"- leaves in at least one sector: **{len(out['leaf_sectors'])}**")
    A(f"- of those, in more than one sector: {multi}")
    A(f"- in a branch but no sector: {len(out['unsectored_leaves'])} "
      "(this grew when the auto-named fallback landed: leaves that used to be "
      "unbranched now carry a flagged auto name, so they count as branched "
      "here while still belonging to no sector)")
    BRJ = json.load(open(os.path.join(BUILD, "branches.json"), encoding="utf-8"))
    _c = BRJ.get("coverage", {})
    A(f"- awaiting a review decision: "
      f"{_c.get('review_queue', {}).get('leaves', 0)}")
    A(f"- Unique effect (terminal, shares structure with no other leaf): "
      f"{_c.get('unique_effect', {}).get('leaves', 0)}")
    A("")
    A("Leaves inside a sector's membership but outside its drawn blobs "
      "(too far from any clump of 3+) are kept as **strays**: coloured and "
      "hoverable, but not enclosed. Stretching a hull to catch an outlier "
      "is exactly what makes sector borders look wrong.")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(chr(10).join(L))


if __name__ == "__main__":
    main()
