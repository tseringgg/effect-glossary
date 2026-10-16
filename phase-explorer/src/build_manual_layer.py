#!/usr/bin/env python3
"""The "placed by hand" layer: the group inventory, the card index and the resolved hand placements. NEW FILES ONLY.

    python src/build_manual_layer.py     # -> build/manual_index.json, build/manual_layer.json, build/manual_ids_seen.json, reports/manual-placements.md   (seconds)

Reads the generated layers (lookup, taxonomy, tentative, loose, annotation, tag, remaining_cards) and corrections/manual_placements.json. Changes none of them: no leaf, no leaf formation,
no threshold, no parser, no figure. The six figures (73.3 / 83.1 / 89.5 / 92.3 / 92.8 / 96.0) are generated elsewhere and are never touched by a hand edit.

MANUAL_PLACEMENTS = False writes nothing and removes this script's own outputs, so the build directory is exactly the build without this layer.

Groups offered for hand placement (group id = layer:id): leaf (1,245), tent (177), loose (the 48 plain loose groups that are not tentative), tag (312), kw (the keyword block), rp (the replacement
block). Not offered: the loose catch-alls and "less common effects" buckets (a Miscellaneous bucket by hand), annotation groups (they are views of a leaf or tentative group).
Counting (decided with the owner): a pile card placed by hand leaves the pile and counts as "placed by hand"; a soft-placed card (tentative, annotation, tag) that is confirmed by hand stays in
its figure and is reported as a sub-count; a precisely placed card takes edits that count nowhere; "nothing fits" is a separate count.
"""
import collections
import gzip
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as M

MANUAL_PLACEMENTS = True
BATCH_ACTIONS = True            # batch place / confirm / reject / undo (POST /api/manual/batch, the batch view). Off: no `batch` field in the index, no batch counts, no fallback file: every output is byte-identical to the build without batch actions
HERE = M.HERE
BUILD = os.path.join(HERE, "build")
OUT_INDEX = os.path.join(BUILD, "manual_index.json")
OUT_LAYER = os.path.join(BUILD, "manual_layer.json")
OUT_SEEN = os.path.join(BUILD, "manual_ids_seen.json")
OUT_MD = os.path.join(HERE, "reports", "manual-placements.md")
if os.environ.get("MANUAL_BUILD_OUT"):                                  # tests only: write the four outputs somewhere else
    _o = os.environ["MANUAL_BUILD_OUT"]
    OUT_INDEX, OUT_LAYER, OUT_SEEN, OUT_MD = (os.path.join(_o, n) for n in ("manual_index.json", "manual_layer.json", "manual_ids_seen.json", "manual-placements.md"))
SRC_ORDER = "PBKRTAMLS"


def jl(n):
    with io.open(os.path.join(BUILD, n), encoding="utf-8") as fh:
        return json.load(fh)


def dump(path, obj):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def ranks():
    p = os.path.join(HERE, "data", "scryfall-oracle-cards.jsonl.gz")
    out = {}
    if not os.path.exists(p):
        return out
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            if o.get("edhrec_rank") is not None:
                out[o["oracle_id"]] = o["edhrec_rank"]
    return out


def build_index():
    tax, lookup = jl("ability_taxonomy.json"), jl("ability_taxonomy_lookup.json")
    tent, loose, ann, tag, rem = jl("tentative_placements.json"), jl("loose_groups.json"), jl("annotation_placements.json"), jl("tag_placements.json"), jl("remaining_cards.json")
    rank = ranks()
    G = {}                                                         # gid -> [name, size, path, layer, offered]
    node_of = {}
    for f in tax["families"]:
        for nd in f["nodes"]:
            for lid in nd["leaves"] + nd["rolled"]:
                node_of[lid] = (f["name"], nd["name"])
    for lid, l in tax["leaves"].items():
        fam, nd = node_of.get(lid, ("", ""))
        G["leaf:" + lid] = [l["name"], l["cards"], fam + " › " + nd, "leaf", 1]
    tfam = {gid: f["name"] for f in tent["families"] for gid in f["groups"]}
    for gid, g in tent["groups"].items():
        G["tent:" + gid] = [g["name"], g["cards"], "Tentative groups › " + tfam.get(gid, g["fam"]), "tent", 1]
    for gid, g in loose["groups"].items():
        if gid in tent["groups"]:
            continue
        G["loose:" + gid] = [g["name"], g["cards"], "Loosely grouped" + ("" if g["kind"] == "group" else " (" + g["kind"] + ", not offered)"), "loose", 1 if g["kind"] == "group" else 0]
    for tid, g in tag["groups"].items():
        G["tag:" + tid] = [g["name"], g["cards"], "Community tag", "tag", 1]
    for blk, pre, label in (("keyword", "kw:", "Keyword abilities"), ("replacement", "rp:", "Replacement groups")):
        b = tax["blocks"][blk]
        brn = {lid: br["name"] for br in b["branches"] for lid in br["leaves"]}
        for lid, l in b["leaves"].items():
            G[(lid if pre == "kw:" else pre + lid)] = [l["name"], l["n"], label + " › " + brn.get(lid, ""), "kw" if pre == "kw:" else "rp", 1]
    import hand_groups as HG
    import build_hand_groups as BHG
    if BHG.HAND_GROUPS:
        hdoc = HG.load()
        hp = os.path.join(BUILD, "hand_group_hits.json")
        hits = jl("hand_group_hits.json")["groups"] if os.path.exists(hp) else {}
        for slug, g in hdoc["groups"].items():                  # a retired group stays in the inventory (not offered), so a hand placement into it is never an orphan
            G["hand:" + slug] = [g["name"], hits.get(slug, {}).get("cards", 0), "Hand-defined groups › " + ("retired" if g.get("retired") else "rule matches"), "hand", 0 if g.get("retired") else 1]
    for gid in G:
        assert gid.split(":", 1)[0] in M.LAYERS, gid
    tfull = set(tent["by_card"])
    ann_cs = {}
    for g in ann["groups"].values():
        for r in g["m"]:
            if ann_cs.get(r[0]) != "c":
                ann_cs[r[0]] = r[6]
    cond_new = {o for o, s in ann_cs.items() if s == "c" and o not in tfull}
    tag_cards = set(tag["by_card"])
    import build_sibling as BS
    sib = jl("sibling_placements.json") if BS.SIBLING_RULE and os.path.exists(os.path.join(BUILD, "sibling_placements.json")) else {"by_card": {}}
    prim = rem["primary"]
    gap = {o for o, s in ann_cs.items() if s == "g" and o not in tfull}
    broad_leaf = {lid for lid, l in tax["leaves"].items() if l["flags"]}
    cards = {}
    for e in lookup["entries"]:
        oid, name, code, x = e[0], e[1], e[3], e[4]
        gens = {}

        def put(gid, src):
            if gid in G and (gid not in gens or SRC_ORDER.index(src) < SRC_ORDER.index(gens[gid])):
                gens[gid] = src
        if code in ("l", "b"):
            for lid in x:
                put("leaf:" + lid, "B" if lid in broad_leaf else "P")
        elif code == "k":
            put(x, "K")
        elif code == "g":
            put("rp:" + x, "R")
        state, cause = {"l": "p", "b": "b", "k": "k", "g": "g", "v": "v", "o": "o"}.get(code, "u"), 0
        if code == "u":
            oid_ = oid
            for gid in tent["by_card"].get(oid_, ()):
                put("tent:" + gid, "T")
            for k in ann["by_card"].get(oid_, ()):
                put(("leaf:" if k[0] == "l" else "tent:") + k[2:], "A")
            for gid in tag["by_card"].get(oid_, ()):
                put("tag:" + gid, "M")
            for gid in loose["by_card"].get(oid_, ()):
                put(("tent:" if gid in tent["groups"] else "loose:") + gid, "L")
            for lid in sib["by_card"].get(oid_, ()):              # the sibling rule's tentative placement (a source, not a state: no bucket moves)
                put("leaf:" + lid, "S")
            if oid_ in tfull:
                state = "t"
            elif oid_ in cond_new:
                state = "a"
            elif oid_ in tag_cards:
                state = "m"
            else:
                state = "u"
            cause = 7 if oid_ in gap else (prim.get(oid_) or 0)
        cards[oid] = [name, state, cause, sorted([g, s] for g, s in gens.items()), rank.get(oid)]
    return dict({"v": 1, "enabled": True, "groups": G, "cards": cards,
            "causes": {str(k): v for k, v in M.CAUSE_TEXT.items()}, "layers": {"leaf": "leaf", "tent": "tentative group", "loose": "loose group", "tag": "community-tag group", "kw": "keyword group", "rp": "replacement group", "hand": "hand-defined group"}}, **({"batch": True} if BATCH_ACTIONS else {}))


def inventory_counts(idx):
    c = collections.Counter(g[3] for g in idx["groups"].values() if g[4])
    return dict(sorted(c.items()))


def main():
    if not MANUAL_PLACEMENTS:
        for p in (OUT_INDEX, OUT_LAYER, OUT_SEEN, OUT_MD, os.path.join(BUILD, "manual_suggestions.json"), os.path.join(BUILD, "manual_fallback.json")):
            if os.path.exists(p):
                os.remove(p)
        print("MANUAL_PLACEMENTS is off: nothing written; this script's own outputs removed")
        return
    idx = build_index()
    doc = M.load_doc()
    res = M.resolve(idx, doc)
    seen = json.load(io.open(OUT_SEEN, encoding="utf-8")) if os.path.exists(OUT_SEEN) else {"groups": {}}
    gone = sorted(g for g in seen["groups"] if g not in idx["groups"])
    renamed_ids = sorted(g for g, n in seen["groups"].items() if g in idx["groups"] and idx["groups"][g][0] != n)
    new_seen = {"groups": {g: idx["groups"][g][0] if g in idx["groups"] else seen["groups"][g] for g in sorted(set(seen["groups"]) | set(idx["groups"]))}}
    inv = inventory_counts(idx)
    layer = {"v": 1, "enabled": True, "counts": res["counts"], "reconciliation": res["reconciliation"], "inventory_offered": inv, "inventory_offered_total": sum(inv.values()),
             "orphans": res["orphans"], "renamed": res["renamed"], "stale_removals": res["stale"], "by_reason": res["by_reason"],
             "hand_new": res["hand_new"], "confirmed": res["confirmed"], "precise_edits": res["precise_edits"], "marked": res["marked"],
             "ids": {"seen_before_and_missing_now": gone, "renamed_since_first_seen": renamed_ids},
             "revision": doc.get("revision", 0)}
    assert res["reconciliation"]["sum"] == len(idx["cards"]), res["reconciliation"]
    dump(OUT_INDEX, idx)
    dump(OUT_LAYER, layer)
    dump(OUT_SEEN, new_seen)
    write_report(idx, res, inv, gone, renamed_ids)
    c, r = res["counts"], res["reconciliation"]
    print("groups offered", sum(inv.values()), inv)
    print("hand: newly placed", c["placed_by_hand_new"], "| confirmed", c["confirmed_by_hand"], c["confirmed_by_hand_of_which"], "| precise cards with edits (not counted)", c["precise_cards_with_edits_not_counted"],
          "| marked nothing fits", c["marked_nothing_fits"], "| removals recorded", c["removals_recorded"])
    print("reconciliation", r)
    print("ORPHANED EDITS: %d | renamed groups: %d | stale removals: %d | ids seen before and missing now: %d" % (c["orphans"], c["renamed"], c["stale_removals"], len(gone)))
    for o in res["orphans"]:
        print("  ORPHAN", o)


def write_report(idx, res, inv, gone, renamed_ids):
    c, r = res["counts"], res["reconciliation"]
    L = ["# Hand placements", "",
         "Generated by `src/build_manual_layer.py` from `corrections/manual_placements.json` and the generated layers. Do not edit.", "",
         "## Counts", "",
         "| | cards |", "|---|---:|",
         "| placed by hand (pile cards the tool newly placed; own line, never added to the six figures) | %d |" % c["placed_by_hand_new"],
         "| confirmed by hand (soft-placed cards; they stay in their figure) | %d |" % c["confirmed_by_hand"],
         "| &nbsp;&nbsp;of which tentative / annotation / tag | %d / %d / %d |" % (c["confirmed_by_hand_of_which"]["tentative"], c["confirmed_by_hand_of_which"]["annotation"], c["confirmed_by_hand_of_which"]["tag"]),
         "| precisely placed cards with hand edits (counted nowhere) | %d |" % c["precise_cards_with_edits_not_counted"],
         "| marked: nothing fits (own count, not a placement) | %d |" % c["marked_nothing_fits"],
         "| removals recorded (change no generated count) | %d |" % c["removals_recorded"]] + (
        ["| &nbsp;&nbsp;placed by hand, in a batch (inside the placed-by-hand line) | %d |" % c["placed_by_hand_batch"], "| &nbsp;&nbsp;confirmed by hand, in a batch (inside the confirmed line) | %d |" % c["confirmed_by_hand_batch"],
         "| batches (undone) | %d (%d) |" % (c["batches"], c["batches_undone"])] if BATCH_ACTIONS else []) + [""] + [
         "## Reconciliation", "",
         "placed %s + tentative %s + annotation %s + tag %s + hand %s + unorganized %s + not cards %s = **%s** (universe %s)" % tuple(
             format(x, ",") for x in (r["placed"], r["tentative"], r["annotation"], r["tag"], r["hand"], r["unorganized"], r["not_cards"], r["sum"], len(idx["cards"]))), "",
         "The 160 gap-test cards sit inside unorganized, as in KNOWN_LIMITATIONS section 17.", "",
         "## Orphaned edits (%d)" % c["orphans"], ""]
    if res["orphans"]:
        L += ["| card | group | action | why |", "|---|---|---|---|"] + ["| %s | %s %s | %s | %s |" % (o["name"], o["group"], ("(" + o["group_name"] + ")") if o.get("group_name") else "", o["action"], o["why"]) for o in res["orphans"]]
    else:
        L.append("None.")
    L += ["", "## Groups renamed since the edit (%d)" % c["renamed"], ""]
    L += ["- %s: %s — was “%s”, now “%s”" % (x["name"], x["group"], x["was"], x["now"]) for x in res["renamed"]] or ["None."]
    L += ["", "## Removals that no longer apply (%d)" % c["stale_removals"], ""]
    L += ["- %s: %s" % (x["name"], x["group"]) for x in res["stale"]] or ["None."]
    L += ["", "## For phase 2 (parser work): hand-handled cards by the reason they were unplaced", "",
          "Keys are `hand:<cause>` (placed by hand) and `nofit:<cause>` (nothing fits). Causes: " + "; ".join("%s = %s" % (k, v.split(":")[0]) for k, v in sorted(M.CAUSE_TEXT.items())) + ".", ""]
    L += ["- `%s`: %d cards" % (k, len(v)) for k, v in res["by_reason"].items()] or ["None yet."]
    L += ["", "## Groups offered", "", "| layer | groups |", "|---|---:|"] + ["| %s | %d |" % (k, v) for k, v in inv.items()] + ["| **total** | **%d** |" % sum(inv.values()), "",
          "## Group ids", "", "Ids seen in an earlier build and missing now: %d. Renamed since first seen (id unchanged): %d." % (len(gone), len(renamed_ids))]
    L += ["", "Missing: " + ", ".join(gone[:50])] if gone else []
    with io.open(OUT_MD, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
