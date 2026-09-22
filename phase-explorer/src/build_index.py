#!/usr/bin/env python3
"""Build the browsable index over phase.rs's card-data.json snapshot.

Reads   data/card-data.json          (read-only upstream input)
Writes  build/index.json             light rows: search text + interned facet ids
        build/facets.json            facet vocabularies, derived from the data
        build/chunks/<n>.json        full parsed structure, fetched lazily
        build/meta.json              snapshot provenance + quality totals

Nothing here mutates the upstream file. Facet vocabularies are derived at build
time on purpose: phase.rs's parser is actively improving and any hardcoded list
of effect/condition variants would silently drift out of date.
"""
import json
import os
import hashlib
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "data", "card-data.json")
BUILD = os.path.join(HERE, "build")
CHUNKS = os.path.join(BUILD, "chunks")
N_CHUNKS = 64

BUCKETS = ("abilities", "triggers", "static_abilities", "replacements")

# Slot-aware vocabularies. The same tag name means different things depending on
# which key it hangs off -- `Fixed` is a quantity in `amount`/`count` but a cost
# in `cost`, and `Cost` is both a cost node and a mana-cost node. Flattening all
# `type` fields into one filter axis would conflate them, so every axis below is
# keyed by the *slot* the node was found in.
SLOTS = {
    "effect": {"effect"},
    "target": {"target", "valid_card", "valid_target", "valid_source", "affected"},
    "quantity": {"amount", "count", "qty", "power", "toughness", "value"},
    "cost": {"cost", "unless_payment", "unless_pay"},
    "condition": {"condition", "constraint", "solve_condition"},
}
SLOT_OF = {key: axis for axis, keys in SLOTS.items() for key in keys}

# Tags that mean "the parser could not represent this". These drive the
# clean/partial split.
GAP_TAGS = {"Unimplemented", "GenericEffect"}

# A second, weaker class of gap that GAP_TAGS does not catch: an enum slot the
# parser left unmodelled rather than an effect it failed to build. A trigger or
# static `mode` arrives as an externally tagged dict (`{"Unknown": "<raw text>"}`)
# instead of a bare string, or a condition comes back `Unrecognized`. 1,696
# entries with zero GAP_TAGS nodes carry one of these, so treating GAP_TAGS as
# the whole story would report them as fully parsed. Tracked separately so the
# clean/partial/unparsed axis keeps the meaning it was specified with.
SOFT_TAGS = {"Unrecognized"}


def tag_name(v):
    """Normalise an enum value that may be a bare string or externally tagged."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and len(v) == 1:
        return next(iter(v))
    if v is None:
        return None
    return json.dumps(v, separators=(",", ":"))[:60]


def scan(node, slot, found, gaps, soft):
    """Walk a parsed subtree, recording (axis, tag) pairs by slot.

    List items inherit the slot of the key that owned the list, so
    `properties: [{type: Another}]` is attributed to the target axis.
    """
    if isinstance(node, dict):
        tag = node.get("type")
        if isinstance(tag, str):
            axis = SLOT_OF.get(slot)
            if axis:
                found[axis].add(tag)
            if tag in GAP_TAGS:
                gaps.append(tag)
            if tag in SOFT_TAGS:
                soft.append(tag)
        for k, v in node.items():
            scan(v, k, found, gaps, soft)
    elif isinstance(node, list):
        for v in node:
            scan(v, slot, found, gaps, soft)


def classify(entry, gaps):
    """clean | partial | unparsed | vanilla

    `vanilla` is a fourth category the brief did not name: 360 entries have no
    oracle_text at all, so they are neither `unparsed` (which means "has text
    but no structure") nor meaningfully `clean`. Forcing them into either would
    misreport coverage, so they get their own bucket.
    """
    has_struct = any(entry.get(b) for b in BUCKETS)
    text = entry.get("oracle_text")
    if not text:
        return "vanilla"
    if not has_struct:
        return "unparsed"
    if gaps:
        return "partial"
    return "clean"


def main():
    with open(SRC, encoding="utf-8") as fh:
        raw = json.load(fh)

    os.makedirs(CHUNKS, exist_ok=True)

    # --- internal identity: oracle_id, not face name -----------------------
    # The upstream file is keyed by lowercased face name. We re-key by
    # scryfall_oracle_id so that identity does not depend on a colliding
    # namespace. Two wrinkles the data forces us to handle:
    #   * multi-face cards share one oracle_id across their faces (34,645 keys
    #     vs 33,834 distinct ids), so an id maps to a *group* of faces;
    #   * some entries carry no oracle_id at all.
    by_oid = defaultdict(list)
    for key in sorted(raw):
        oid = raw[key].get("scryfall_oracle_id")
        by_oid[oid if oid else "noid:" + key].append(key)

    rows = []
    vocab = {axis: Counter() for axis in SLOTS}
    for extra in ("trigger_mode", "static_mode", "replacement_event", "keyword"):
        vocab[extra] = Counter()
    quality_totals = Counter()
    soft_totals = Counter()
    chunk_data = defaultdict(dict)
    faces_per_group = Counter()

    for oid, keys in sorted(by_oid.items()):
        faces_per_group[len(keys)] += 1
        for face_pos, key in enumerate(keys):
            entry = raw[key]
            # Stable per-face id. Suffixed only when an oracle_id covers
            # several faces, so single-face ids stay readable.
            eid = oid if len(keys) == 1 else f"{oid}/{face_pos}"

            found = {axis: set() for axis in SLOTS}
            gaps = []
            soft = []
            for bucket in BUCKETS:
                scan(entry.get(bucket), bucket, found, gaps, soft)

            # An externally tagged dict in an enum slot means the parser did not
            # model that mode/event and stashed the raw text instead.
            for t in entry.get("triggers") or []:
                if isinstance(t.get("mode"), dict):
                    soft.append("trigger_mode")
            for s in entry.get("static_abilities") or []:
                if isinstance(s.get("mode"), dict):
                    soft.append("static_mode")
            for rp in entry.get("replacements") or []:
                if isinstance(rp.get("event"), dict):
                    soft.append("replacement_event")

            trig = {tag_name(t.get("mode")) for t in entry.get("triggers") or []}
            stat = {tag_name(s.get("mode")) for s in entry.get("static_abilities") or []}
            repl = {tag_name(r.get("event")) for r in entry.get("replacements") or []}
            kws = set()
            for k in entry.get("keywords") or []:
                n = tag_name(k)
                if n:
                    kws.add(n)

            found["trigger_mode"] = {x for x in trig if x}
            found["static_mode"] = {x for x in stat if x}
            found["replacement_event"] = {x for x in repl if x}
            found["keyword"] = kws

            for axis, vals in found.items():
                vocab[axis].update(vals)

            quality = classify(entry, gaps)
            quality_totals[quality] += 1
            if soft:
                soft_totals[quality] += 1

            chunk = int(hashlib.md5(eid.encode()).hexdigest(), 16) % N_CHUNKS
            ct = entry.get("card_type") or {}
            typeline = " ".join(
                filter(None, [
                    " ".join(ct.get("supertypes") or []),
                    " ".join(ct.get("core_types") or []),
                    ("- " + " ".join(ct.get("subtypes"))) if ct.get("subtypes") else "",
                ])
            ).strip()

            rows.append({
                "id": eid,
                "key": key,
                "name": entry.get("name") or key,
                "text": entry.get("oracle_text") or "",
                "q": quality,
                "type": typeline,
                "layout": entry.get("layout"),
                "warn": len(entry.get("parse_warnings") or []),
                "gaps": len(gaps),
                "sg": len(soft),
                "group": oid if len(keys) > 1 else None,
                "ch": chunk,
                "f": found,  # interned below
            })

            chunk_data[chunk][eid] = {
                "name": entry.get("name"),
                "mana_cost": entry.get("mana_cost"),
                "card_type": entry.get("card_type"),
                "power": entry.get("power"),
                "toughness": entry.get("toughness"),
                "loyalty": entry.get("loyalty"),
                "defense": entry.get("defense"),
                "oracle_text": entry.get("oracle_text"),
                "keywords": entry.get("keywords"),
                "abilities": entry.get("abilities"),
                "triggers": entry.get("triggers"),
                "static_abilities": entry.get("static_abilities"),
                "replacements": entry.get("replacements"),
                "modal": entry.get("modal"),
                "additional_cost": entry.get("additional_cost"),
                "casting_restrictions": entry.get("casting_restrictions"),
                "casting_options": entry.get("casting_options"),
                "solve_condition": entry.get("solve_condition"),
                "strive_cost": entry.get("strive_cost"),
                "parse_warnings": entry.get("parse_warnings"),
                "layout": entry.get("layout"),
                "legalities": entry.get("legalities"),
                "printings": entry.get("printings"),
                "scryfall_oracle_id": entry.get("scryfall_oracle_id"),
                "_export_key": key,
            }

    # --- intern facet strings so index.json stays small --------------------
    axes = sorted(vocab)
    order = {axis: sorted(vocab[axis]) for axis in axes}
    idx = {axis: {v: i for i, v in enumerate(order[axis])} for axis in axes}
    for r in rows:
        r["f"] = {a: sorted(idx[a][v] for v in r["f"].get(a, ())) for a in axes}

    rows.sort(key=lambda r: r["name"].lower())

    with open(os.path.join(BUILD, "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"rows": rows}, fh, separators=(",", ":"), ensure_ascii=False)

    with open(os.path.join(BUILD, "facets.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {a: [{"v": v, "n": vocab[a][v]} for v in order[a]] for a in axes},
            fh, separators=(",", ":"), ensure_ascii=False)

    for chunk, payload in chunk_data.items():
        with open(os.path.join(CHUNKS, f"{chunk}.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)

    st = os.stat(SRC)
    meta = {
        "source_url": "https://data.phase-rs.dev/card-data.json",
        "snapshot_last_modified": "2026-04-20T20:53:36Z",
        "snapshot_etag": "835ec8094e883fa623b65ea7e841bb9e",
        "fetched": "2026-09-21",
        "source_bytes": st.st_size,
        "entries": len(rows),
        "distinct_oracle_ids": len(by_oid),
        "quality": dict(quality_totals),
        "soft_gaps_by_quality": dict(soft_totals),
        "soft_gap_entries": sum(soft_totals.values()),
        "n_chunks": N_CHUNKS,
        "axis_sizes": {a: len(order[a]) for a in axes},
        "faces_per_oracle_id": dict(faces_per_group),
    }
    with open(os.path.join(BUILD, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)

    print(json.dumps(meta, indent=1))
    for a in axes:
        print(f"  axis {a:20s} {len(order[a]):5d} values")


if __name__ == "__main__":
    main()
