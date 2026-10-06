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
import io
import json
import os
import re
import sys
import hashlib
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corrections as corrections_mod

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
GAP_TAGS = {"Unimplemented"}

# GenericEffect is not itself a gap tag: it's phase.rs's real, CR-cited
# mechanism for transient continuous grants (temporary keyword/ability/P-T/
# type/color changes -- CR 113.3, 604.1, 611.2b, 702), executed at resolution
# by game/effects/effect.rs::resolve(), not a parser punt. It only carries
# zero information when its own `static_abilities` list is empty -- verified
# against the 2026-04-20 snapshot: every non-empty case uses a fully-typed
# `ContinuousModification`/`StaticMode` variant (no catch-all "Unknown" exists
# in either enum), so an empty list is the only way nothing was captured.
#
# Even then, it's not a gap when the enclosing AbilityDefinition carries a
# populated `modal` + `mode_abilities` pair: the real content is modal-encoded
# ("choose one -- * mode A * mode B"), and `effect` is just the placeholder
# every AbilityDefinition requires -- it isn't meant to carry anything here.
# 281 of the 312 empty-GenericEffect nodes in the snapshot have this shape
# (verified against real oracle text on several: Tax Collector, Cleanup Crew,
# Ertai Resurrected, Yotian Courier -- modal/mode_abilities fully and
# correctly structured in every case); the other 31 have no modal sibling at
# all and are genuine gaps.
def generic_effect_is_gap(node, parent=None):
    if node.get("static_abilities"):
        return False
    if parent is not None and parent.get("modal") and parent.get("mode_abilities"):
        return False
    return True

# A second, weaker class of gap that GAP_TAGS does not catch: an enum slot the
# parser left unmodelled rather than an effect it failed to build. A trigger or
# static `mode` arrives as an externally tagged dict (`{"Unknown": "<raw text>"}`)
# instead of a bare string, or a condition comes back `Unrecognized`. 1,696
# entries with zero GAP_TAGS nodes carry one of these, so treating GAP_TAGS as
# the whole story would report them as fully parsed. Tracked separately so the
# clean/partial/unparsed axis keeps the meaning it was specified with.
SOFT_TAGS = {"Unrecognized"}


# ---- browsing facets: colour, mana value, core types ----------------------
# These three are what a player filters a card list by, and all three come out
# of fields the snapshot already carries -- no extra input, no second pass.
#
# Colour: `color_override` when present, else the colours named in the mana
# cost's shards. The override is the snapshot's colour-indicator/devoid field
# and it is authoritative where it disagrees with the cost: 3,202 entries carry
# one, 541 of those differ from their cost (a back face with no cost but a
# colour indicator, or a devoid card with coloured pips that is colourless).
# Reading the cost alone would mis-colour every one of them.
#
# Mana value: generic + one per shard, with two exceptions that would otherwise
# be wrong -- `X` counts 0 (as it does on the stack) and a `Two<Colour>` hybrid
# pip counts 2. A face with no mana cost at all (back faces, tokens, most
# lands) gets `None`, NOT 0: 2,168 entries have no cost, and folding them into
# "mana value 0" would silently pad that bucket with cards that cannot be cast.
COLOUR_OF = {"White": "W", "Blue": "U", "Black": "B", "Red": "R", "Green": "G"}


def shard_weight(shard):
    if shard == "X":
        return 0
    return 2 if shard.startswith("Two") else 1


def browse_facets(entry):
    """-> (colours string e.g. "WU" / "" for colourless, mana value or None)."""
    mc = entry.get("mana_cost") or {}
    shards = mc.get("shards") or []
    generic = mc.get("generic") or 0

    override = entry.get("color_override")
    if override is not None:
        cols = {COLOUR_OF[c] for c in override if c in COLOUR_OF}
    else:
        cols = set()
        for shard in shards:
            for name, letter in COLOUR_OF.items():
                if name in shard:
                    cols.add(letter)

    mv = None
    if shards or generic:
        mv = generic + sum(shard_weight(s) for s in shards)
    return "".join(c for c in "WUBRG" if c in cols), mv


def tag_name(v):
    """Normalise an enum value that may be a bare string or externally tagged."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and len(v) == 1:
        return next(iter(v))
    if v is None:
        return None
    return json.dumps(v, separators=(",", ":"))[:60]


def scan(node, slot, found, gaps, soft, parent=None):
    """Walk a parsed subtree, recording (axis, tag) pairs by slot.

    List items inherit the slot of the key that owned the list, so
    `properties: [{type: Another}]` is attributed to the target axis.
    `parent` is the nearest enclosing dict (an AbilityDefinition, typically),
    passed down so a GenericEffect node can check its own siblings.
    """
    if isinstance(node, dict):
        tag = node.get("type")
        if isinstance(tag, str):
            axis = SLOT_OF.get(slot)
            if axis:
                found[axis].add(tag)
            if tag in GAP_TAGS:
                gaps.append(tag)
            elif tag == "GenericEffect" and generic_effect_is_gap(node, parent):
                gaps.append(tag)
            if tag in SOFT_TAGS:
                soft.append(tag)
        for k, v in node.items():
            scan(v, k, found, gaps, soft, node)
    elif isinstance(node, list):
        for v in node:
            scan(v, slot, found, gaps, soft, parent)


def _squash(s):
    return re.sub(r"[\s\-]+", "", s.lower())


def parsed_elsewhere(entry):
    """Whether a face with empty ability buckets is in fact fully parsed.

    Ported from build_ledger.py's reason-labelling helper of the same name --
    the logic is identical and already validated there (see its own
    docstring); this just makes it feed `classify()` directly instead of
    only annotating a `q` value classify() already decided without it.

    `keywords` and `additional_cost` both hold real structure outside the
    four ability buckets: a card whose whole text is "Flying" (Storm Crow)
    or "As an additional cost to cast this spell, ..." parses completely,
    just not into abilities/triggers/static_abilities/replacements.

    Returns True when every oracle-text line is one of the card's OWN parsed
    keywords or an additional cost its own parse holds. Judged per line
    against the card's own parse, never a keyword list of ours: reminder
    text is dropped, a keyword line must open with one of its keywords, and
    a plain comma list ("Flying, first strike") must open with one in every
    item. A keyword the parser DROPPED (Echo, Reinforce, Morph on some
    cards) is absent from `keywords`, so that line fails and this correctly
    returns False -- the face stays `unparsed` for a real, separate reason.
    """
    names = set()
    for k in entry.get("keywords") or []:
        if isinstance(k, str):
            names.add(_squash(re.sub(r"([a-z])([A-Z])", r"\1 \2", k)))
        elif isinstance(k, dict) and k:
            key, val = next(iter(k.items()))
            names.add(_squash(re.sub(r"([a-z])([A-Z])", r"\1 \2", key)))
            if isinstance(val, str):
                names.add(_squash(val))
    lines = [re.sub(r"\([^)]*\)", "", ln).strip() for ln in (entry.get("oracle_text") or "").split("\n")]
    lines = [ln for ln in lines if ln]
    if not lines:
        return False

    def opens(seg):
        s = _squash(seg)
        return any(s.startswith(n) for n in names)

    def keyword_line(ln):
        if not names or not opens(ln):
            return False
        costed = "—" in ln or "{" in ln
        return costed or all(opens(p) for p in re.split(r",\s*|;\s*", ln) if p.strip())

    for ln in lines:
        if keyword_line(ln):
            continue
        if entry.get("additional_cost") and ln.lower().startswith("as an additional cost"):
            continue
        return False
    return True


def classify(entry, gaps):
    """clean | partial | unparsed | vanilla

    `vanilla` is a fourth category the brief did not name: 360 entries have no
    oracle_text at all, so they are neither `unparsed` (which means "has text
    but no structure") nor meaningfully `clean`. Forcing them into either would
    misreport coverage, so they get their own bucket.

    "No structure" means none of the four ability buckets AND no equivalent
    structure in `keywords`/`additional_cost` either (parsed_elsewhere) -- a
    keyword-only or additional-cost-only card is fully parsed, just not into
    those four buckets.
    """
    has_struct = any(entry.get(b) for b in BUCKETS) or parsed_elsewhere(entry)
    text = entry.get("oracle_text")
    if not text:
        return "vanilla"
    if not has_struct:
        return "unparsed"
    if gaps:
        return "partial"
    return "clean"


# Validated local parser fixes, applied on top of card-data.json at our own
# build time -- never written back to their file, never run through their
# engine for anything but generating these entries. Unlike corrections.json
# (hand-asserted substitutions we can't validate because we don't run their
# engine) these ARE real output from running phase-rs's own generator, built
# from the local v0.1.15 checkout with a narrow, gate-verified fix; unlike
# recovered-cards.json (cards ADDED back after being dropped by a face-name
# collision) these REPLACE an existing entry. Each file's own `meta` records
# the fix and its control-set gate result -- see src/apply_*_overlay.py.
PARSER_FIX_OVERLAYS = [
    os.path.join(HERE, "data", "overlay", "commander-eligibility-fix.json"),
    os.path.join(HERE, "data", "overlay", "commander-creatures-fix.json"),
    # visibility fix: unparsed restriction text kept as ParsedCondition::Unrecognized
    os.path.join(HERE, "data", "overlay", "unrecognized-restriction-fix.json"),
    # round B1: timing clause split out of compound "Activate only ..." (enforced by the engine)
    os.path.join(HERE, "data", "overlay", "activation-timing-split-fix.json"),
]


def apply_parser_fix_overlays(raw):
    applied = 0
    for path in PARSER_FIX_OVERLAYS:
        if not os.path.exists(path):
            continue
        doc = json.load(io.open(path, encoding="utf-8"))
        for faces in doc["cards"].values():
            for face in faces:
                key = face["name"].lower()
                if key not in raw:
                    raise KeyError(f"parser-fix overlay {path}: no raw entry for {key!r}")
                raw[key] = face
                applied += 1
    return applied


def main():
    with open(SRC, encoding="utf-8") as fh:
        raw = json.load(fh)

    n_fixed = apply_parser_fix_overlays(raw)
    if n_fixed:
        sys.stderr.write(f"applied {n_fixed} face(s) from parser-fix overlays\n")

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

    corrections_by_oid = corrections_mod.load()

    rows = []
    vocab = {axis: Counter() for axis in SLOTS}
    for extra in ("trigger_mode", "static_mode", "replacement_event", "keyword"):
        vocab[extra] = Counter()
    quality_totals = Counter()
    soft_totals = Counter()
    correction_totals = Counter()
    chunk_data = defaultdict(dict)
    faces_per_group = Counter()

    for oid, keys in sorted(by_oid.items()):
        faces_per_group[len(keys)] += 1
        for face_pos, key in enumerate(keys):
            # Apply our hand-maintained overlay (corrections/corrections.json)
            # before anything downstream sees this record. `flag`-kind
            # corrections leave the structure untouched and are only carried
            # forward for display; `patch`-kind corrections mutate a deep
            # copy. Either way `applied` is non-empty only for the handful of
            # cards we have evidence-based findings for.
            entry, applied = corrections_mod.apply(raw[key], oid, corrections_by_oid)
            for c in applied:
                correction_totals[c["kind"]] += 1
            # Stable per-face id. Suffixed only when an oracle_id covers
            # several faces, so single-face ids stay readable.
            eid = oid if len(keys) == 1 else f"{oid}/{face_pos}"

            found = {axis: set() for axis in SLOTS}
            gaps = []
            soft = []
            for bucket in BUCKETS:
                scan(entry.get(bucket), bucket, found, gaps, soft)
            # Card-level casting fields carry the same `Unrecognized` condition node
            # (ParsedCondition::Unrecognized, unrecognized-restriction-fix overlay).
            # Only the soft-gap signal is read from them: no facet axis values and no
            # GAP_TAGS, so nothing else about the index row can move.
            for extra in ("casting_restrictions", "casting_options"):
                scan(entry.get(extra), extra, {a: set() for a in SLOTS}, [], soft)

            # A trigger `mode` arriving as {"Unknown": "<raw text>"} means the
            # parser did not model that trigger at all. Static `mode` and
            # replacement `event` also arrive as externally-tagged dicts, but
            # those encode legitimate data-carrying variants (e.g.
            # {"ReduceCost": {...}}), not gaps -- a prior build counted every
            # dict-valued mode/event as a soft gap and over-reported 2,244
            # affected entries (1,696 of them "clean") when the true figure,
            # restricted to actual {"Unknown": ...} trigger modes plus
            # Unrecognized conditions, is 1,288 (887 "clean"). Verified by
            # cross-checking a flagged "clean" card (Blasphemous Act) whose
            # only dict-valued mode was a legitimate {"ReduceCost": {...}}.
            for t in entry.get("triggers") or []:
                mode = t.get("mode")
                if isinstance(mode, dict) and "Unknown" in mode:
                    soft.append("trigger_mode")

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

            colours, mana_value = browse_facets(entry)

            rows.append({
                "id": eid,
                "key": key,
                "name": entry.get("name") or key,
                "text": entry.get("oracle_text") or "",
                "q": quality,
                "type": typeline,
                "col": colours,              # "WU", or "" for colourless
                "mv": mana_value,            # null when the face has no cost
                "cty": ct.get("core_types") or [],
                "layout": entry.get("layout"),
                "warn": len(entry.get("parse_warnings") or []),
                "gaps": len(gaps),
                "sg": len(soft),
                "corr": len(applied),
                "group": oid if len(keys) > 1 else None,
                "ch": chunk,
                "f": found,  # interned below
            })

            chunk_payload = {
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
            if applied:
                # Our own findings, kept distinct from upstream's parse_warnings
                # (see corrections/SCHEMA.md) -- never merged into that list.
                chunk_payload["_corrections"] = applied
            chunk_data[chunk][eid] = chunk_payload

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
        "corrections_file": "corrections/corrections.json",
        "corrections_loaded": sum(len(v) for v in corrections_by_oid.values()),
        "corrections_applied_by_kind": dict(correction_totals),
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
