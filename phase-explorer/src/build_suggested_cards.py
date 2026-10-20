#!/usr/bin/env python3
"""Reverse index of suggestions, for the "Possible matches" tab of a group page. NEW FILES ONLY (build/suggested_cards/*, reports/suggested-cards.md). Suggestions only: nothing is placed, no figure changes.

    python src/build_suggested_cards.py     # a few seconds; run build_manual_layer.py, build_manual_suggestions.py and build_text_suggestions.py first

SUGGESTED_CARDS_VIEW = True (the default) builds the files; False writes nothing and removes this script's own outputs, so the page draws no tab and the build directory is exactly the build without this layer.

What it does. It inverts the suggestion rows the page already shows for a card (the first 5 rows of build/text_sug/queue.json for the pile, tentative, annotation and tag cards; the first 5 of build/text_sug/c/<xx>.json for every
other card; nothing is re-scored and no row is changed) into one list per group: the cards that have the group in their top 5 and are not already shown in it. Not shown in it = the card holds the group in no source (precise, broad, keyword,
replacement, tentative, annotation, tag, loose, sibling), is not a rule match of a hand-defined group, and has no hand add in it (the page also hides, live, cards with a hand entry anywhere and cards marked "nothing fits").
Only rows scoring 0.50 or more are stored (the tab's slider goes from 0.50 to 0.90; the default is 0.70). A group's rows are split in two files by the card's state: the cards the tool has not placed precisely (state u, t, a, m: an Add
moves the hand line) and the cards already placed (an Add is recorded and counted nowhere); each file is sorted by score, then popularity (lower rank first, unranked last), then name.

TAG_LENS (community tag lens, tag groups only): for each community-tag group, the cards that carry the group's Scryfall tag (the tag layer's own filter) and are not in the group. No score: sorted by popularity. Same two files.
It was read before it was enabled (reports/suggested-cards.md).

Outputs (build/suggested_cards/): meta.json (counts per group and slider step; the page reads only this until a group is opened), g/<i>q.json and g/<i>p.json (rows [oid, score, sources, reason, line start, line length, member line]),
t/<i>q.json and t/<i>p.json (the lens: lists of oracle ids).
"""
import collections
import io
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as M

SUGGESTED_CARDS_VIEW = True
TAG_LENS = True
HERE = M.HERE
BUILD = os.path.join(HERE, "build")
OUTDIR = os.environ.get("SUGGESTED_OUT") or os.path.join(BUILD, "suggested_cards")          # the env override is for the tests only
OUT_MD = os.path.join(HERE, "reports", "suggested-cards.md")
if os.environ.get("SUGGESTED_OUT"):
    OUT_MD = os.path.join(os.environ["SUGGESTED_OUT"], "suggested-cards.md")
TOP = 5
STORE_FLOOR = 0.50
STEPS = [0.50, 0.60, 0.70, 0.80, 0.90]
QUEUE_STATES = ("u", "t", "a", "m")
LABEL = "Suggested cards. Not members. Not counted in any figure."
LENS_LABEL = "Cards that carry this group's community tag and are not in the group. A tag is a hint, not a placement. Not counted in any figure."


def jl(n):
    with io.open(os.path.join(BUILD, n), encoding="utf-8") as fh:
        return json.load(fh)


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def step_counts(scores):
    return [sum(1 for s in scores if s >= st - 1e-9) for st in STEPS]


def stored_rows(C, G, tmeta):
    """-> {oid: [row, ...]} the first TOP stored rows of every card, in the shape [gid, score, sources, reason, (line start, length, member line id)]"""
    import glob
    rows = {}
    q = jl(os.path.join("text_sug", "queue.json"))["cards"]
    for o, r in q.items():
        rows[o] = r[:TOP]
    for fn in sorted(glob.glob(os.path.join(BUILD, "text_sug", "c", "*.json"))):
        with io.open(fn, encoding="utf-8") as fh:
            sh = json.load(fh)
        for o, rr in sh.items():
            out = []
            for r in rr[:TOP]:
                gid = tmeta["groups"][r[0]]
                if r[2] < 0:
                    out.append([gid, r[1] / 1000.0, "kw", r[5]])
                else:
                    out.append([gid, r[1] / 1000.0, "text", "", r[2], r[3], r[4]])
            rows[o] = out
    return rows


def main(force=None):
    on = SUGGESTED_CARDS_VIEW if force is None else force
    import build_manual_layer as BML
    ready = on and BML.MANUAL_PLACEMENTS and os.path.exists(os.path.join(BUILD, "text_sug", "queue.json"))
    if not ready:
        if os.path.isdir(OUTDIR) and not os.environ.get("SUGGESTED_OUT"):
            shutil.rmtree(OUTDIR)
        if os.path.exists(OUT_MD) and not os.environ.get("SUGGESTED_OUT"):
            os.remove(OUT_MD)
        print("SUGGESTED_CARDS_VIEW is off (or the text suggestions are not built): nothing written")
        return
    t0 = time.time()
    ix = jl("manual_index.json")
    G, C = ix["groups"], ix["cards"]
    tmeta = jl(os.path.join("text_sug", "meta.json"))
    rows = stored_rows(C, G, tmeta)
    members = collections.defaultdict(set)
    for o, c in C.items():
        for g in c[3]:
            members[g[0]].add(o)
    hp = os.path.join(BUILD, "hand_group_hits.json")
    if os.path.exists(hp):
        for slug, g in jl("hand_group_hits.json")["groups"].items():
            members["hand:" + slug] |= set(g["hits"])
    pop = lambda o: (C[o][4] if C[o][4] is not None else 10 ** 9)
    key = lambda o, s: (-s, pop(o), C[o][0], o)

    # ---- the suggestions
    per = collections.defaultdict(lambda: ([], []))                       # gid -> (queue rows, placed rows)
    n_pairs = 0
    for o in sorted(rows):
        c = C.get(o)
        if c is None or c[1] == "o":
            continue
        for r in rows[o]:
            gid, sc = r[0], round(float(r[1]), 3)
            g = G.get(gid)
            if g is None or not g[4] or sc < STORE_FLOOR - 1e-9 or o in members[gid]:
                continue
            per[gid][0 if c[1] in QUEUE_STATES else 1].append([o, sc] + list(r[2:]))
            n_pairs += 1
    gids = sorted(per)
    meta_groups, stats = {}, []
    for i, gid in enumerate(gids):
        q, p = per[gid]
        for lst, tag in ((q, "q"), (p, "p")):
            lst.sort(key=lambda r: key(r[0], r[1]))
            if lst:
                dump(os.path.join(OUTDIR, "g", "%d%s.json" % (i, tag)), lst)
        meta_groups[gid] = [i, step_counts([r[1] for r in q]), step_counts([r[1] for r in p])]
        stats.append((len(q) + len(p), gid))

    # ---- the community-tag lens
    lens, n_lens = {}, 0
    if TAG_LENS:
        import tag_layer_filter as F
        import probe_tags as PT
        tags = jl("tag_placements.json")
        fn = F.functional(PT.load(PT.NEW))
        ct = F.card_tags(fn)
        by_group = collections.defaultdict(list)
        for o in sorted(ct):
            c = C.get(o)
            if c is None or c[1] == "o":
                continue
            for t in ct[o]:
                gid = "tag:" + t
                if t in tags["groups"] and gid in G and G[gid][4] and o not in members[gid]:
                    by_group[gid].append(o)
        for j, gid in enumerate(sorted(by_group)):
            os_ = sorted(by_group[gid], key=lambda o: (pop(o), C[o][0], o))
            q = [o for o in os_ if C[o][1] in QUEUE_STATES]
            p = [o for o in os_ if C[o][1] not in QUEUE_STATES]
            for lst, tag in ((q, "q"), (p, "p")):
                if lst:
                    dump(os.path.join(OUTDIR, "t", "%d%s.json" % (j, tag)), lst)
            lens[gid] = [j, len(q), len(p), fn[gid[4:]]["slug"]]
            n_lens += len(os_)
    meta = {"v": 1, "label": LABEL, "lens_label": LENS_LABEL, "store_floor": STORE_FLOOR, "steps": STEPS, "default_floor": 0.70, "per_view": 25, "groups": meta_groups, "lens": lens,
            "top": TOP, "pairs": n_pairs}
    dump(os.path.join(OUTDIR, "meta.json"), meta)
    write_report(meta, stats, G, n_lens)
    tot = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(OUTDIR) for f in fs)
    print("suggested cards: %d groups with suggestions, %d pairs; %d tag groups with a lens, %d pairs; %.1f MB in %d files, %.1fs" % (len(gids), n_pairs, len(lens), n_lens, tot / 1048576.0,
          sum(len(fs) for _, _, fs in os.walk(OUTDIR)), time.time() - t0))


def write_report(meta, stats, G, n_lens):
    big = sorted(stats, key=lambda x: (-x[0], x[1]))[:15]
    L = ["# Suggested cards (generated; do not edit)", "",
         "Built by `python src/build_suggested_cards.py` (flag SUGGESTED_CARDS_VIEW, default off). Suggestions only: nothing is placed from them and no figure changes.", "",
         "- %d (card, group) pairs stored at %.2f or more, in %d groups; %d tag groups have a community-tag lens (%d pairs)." % (meta["pairs"], STORE_FLOOR, len(meta["groups"]), len(meta["lens"]), n_lens),
         "- Slider steps %s; default %.2f; %d rows per view." % (", ".join("%.2f" % s for s in STEPS), meta["default_floor"], meta["per_view"]), "",
         "## The 15 largest groups (pairs stored)", ""]
    for n, gid in big:
        L.append("- %s (%s): %d" % (G[gid][0], gid, n))
    with io.open(OUT_MD, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
