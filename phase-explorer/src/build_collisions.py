#!/usr/bin/env python3
"""Detect cards silently dropped from card-data.json by face-name key collision.

phase.rs's export is a JSON object keyed by lowercased *face* name. JSON object
keys are unique, so by the time we hold the file the loser of any collision is
simply absent -- it cannot be recovered from the snapshot alone. To name both
sides we reproduce the export's keying against MTGJSON AtomicCards and look for
face-name keys that MTGJSON covers with more than one distinct oracle id.

We only consider names where MTGJSON *itself* holds several oracle ids, then
ask which one survived in the snapshot. MTGJSON is newer than the snapshot, so
an id losing a key is one of three things, and only the first is a dropped card:
  card_dropped            no face of the card is in the snapshot (a real loss)
  face_lost_card_present  the card survives under another face's key -- e.g.
                          Emeritus of Woe keeps its front face; only its
                          prepare face "Demonic Tutor" lost to the classic card
  released_after_snapshot first printed after the snapshot date, so it never
                          competed (needs data/scryfall-default-cards.jsonl.gz)
Each id is counted once even when it loses several keys. An earlier version
summed losers per key, which double-counted those ids and included the other
two classes: it reported 80 where 63 cards were actually dropped.

Reads   data/card-data.json, data/AtomicCards.json.gz,
        data/scryfall-default-cards.jsonl.gz (optional, for first-printing dates)
Writes  NAME_COLLISIONS.md, build/collisions.json
"""
import gzip
import json
import os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT_DATE = "2026-04-20"
CLASS_TEXT = {
    "card_dropped": "card dropped — no face of it is in the snapshot",
    "face_lost_card_present": "only this face lost; the card is in the snapshot under another face",
    "released_after_snapshot": "first printed after the snapshot — never competed",
}


def first_printings():
    """oracle id -> earliest Scryfall released_at, or {} without the file."""
    path = os.path.join(HERE, "data", "scryfall-default-cards.jsonl.gz")
    first = {}
    if not os.path.exists(path):
        return first
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip().rstrip(",")
            if not line.startswith("{"):
                continue
            c = json.loads(line)
            oid = c.get("oracle_id") or ((c.get("card_faces") or [{}])[0].get("oracle_id"))
            d = c.get("released_at")
            if oid and d and (oid not in first or d < first[oid]):
                first[oid] = d
    return first


def main():
    with open(os.path.join(HERE, "data", "card-data.json"), encoding="utf-8") as fh:
        snap = json.load(fh)
    with gzip.open(os.path.join(HERE, "data", "AtomicCards.json.gz"), "rt", encoding="utf-8") as fh:
        mtg = json.load(fh)

    meta = mtg.get("meta", {})
    data = mtg["data"]

    # Reproduce the export's key namespace: every face contributes its own
    # face name, so a standalone card and a face of a multi-face card compete
    # for the same slot.
    ns = defaultdict(dict)  # face key -> {oracle_id: [descriptions]}
    for name, variants in data.items():
        for c in variants:
            face = c.get("faceName") or c.get("name")
            oid = (c.get("identifiers") or {}).get("scryfallOracleId")
            if not face or not oid:
                continue
            ns[face.lower()].setdefault(oid, []).append({
                "name": c.get("name"),
                "faceName": c.get("faceName"),
                "layout": c.get("layout"),
                "type": c.get("type"),
                "text": (c.get("text") or "").replace("\n", " ")[:160],
                "printings": c.get("printings") or [],
            })

    collisions = []
    for key, oids in sorted(ns.items()):
        if len(oids) < 2:
            continue
        present = snap.get(key)
        winner = present.get("scryfall_oracle_id") if present else None
        collisions.append({
            "key": key,
            "oids": oids,
            "winner": winner,
            "in_snapshot": present is not None,
        })

    # Split by whether the loss is observable in this snapshot.
    dropped_rows = []
    for c in collisions:
        if not c["in_snapshot"]:
            continue
        losers = [o for o in c["oids"] if o != c["winner"]]
        if losers:
            dropped_rows.append(c)

    # Classify each losing id once, however many keys it lost.
    in_snap = {(e[0] if isinstance(e, list) else e).get("scryfall_oracle_id") for e in snap.values()}
    first = first_printings()
    klass = {}
    for c in dropped_rows:
        for o in c["oids"]:
            if o == c["winner"] or o in klass:
                continue
            klass[o] = ("face_lost_card_present" if o in in_snap else
                        "released_after_snapshot" if first.get(o, "") > SNAPSHOT_DATE else
                        "card_dropped")
    by_class = Counter(klass.values())
    n_slots = sum(len([o for o in c["oids"] if o != c["winner"]]) for c in dropped_rows)

    lines = []
    lines.append("# Face-name key collisions\n")
    lines.append(
        "Generated by `src/build_collisions.py`. This is a permanent build artifact, "
        "regenerated whenever the snapshot is refreshed -- not a one-time check.\n")
    lines.append("## Why this file exists\n")
    lines.append(
        "`card-data.json` is a JSON object keyed by lowercased **face** name. Object keys "
        "are unique, so when two different cards share a face name only one survives the "
        "export and the other is **absent with no marker of any kind**. The loser cannot be "
        "recovered from the snapshot alone, which is why this report is built by comparing "
        "against MTGJSON AtomicCards.\n")
    lines.append(
        "The comparison only considers face-name keys that **MTGJSON itself** covers with "
        "more than one distinct Scryfall oracle id, then asks which of those ids survived in "
        "the snapshot. MTGJSON is newer than the snapshot, so a losing id is classified: only "
        "`card_dropped` is a card missing from the snapshot. `face_lost_card_present` cards are "
        "in the snapshot under another face's key, and `released_after_snapshot` cards never "
        "competed. Each id is counted once.\n")
    lines.append("## Sources\n")
    lines.append(f"- snapshot: `data/card-data.json`, Last-Modified 2026-04-20, {len(snap):,} entries")
    lines.append(f"- reference: MTGJSON AtomicCards v{meta.get('version','?')}, "
                 f"date {meta.get('date','?')}, {len(data):,} names, "
                 f"{len(ns):,} distinct face-name keys\n")
    lines.append("## Result\n")
    lines.append(f"- **{len(collisions)}** face-name keys are contested by 2+ oracle ids in MTGJSON")
    lines.append(f"- **{len(dropped_rows)}** of those keys are present in the snapshot holding "
                 f"one id while at least one other id was dropped")
    n_lost = by_class["card_dropped"]
    lines.append(f"- **{n_lost}** cards are missing from the snapshot as a result (`card_dropped`)")
    lines.append(f"- {by_class['face_lost_card_present']} more lost one face's key but are present "
                 f"under another face (`face_lost_card_present`)")
    lines.append(f"- {by_class['released_after_snapshot']} losing ids were first printed after "
                 f"{SNAPSHOT_DATE} and never competed (`released_after_snapshot`)")
    lines.append(f"- {n_slots} losing (key, id) slots in all. An earlier version of this report "
                 f"summed those per key and printed it as \"oracle ids missing\" (80): that "
                 f"double-counted ids losing several keys and included the other two classes.\n")
    lines.append(f"The {n_lost} dropped cards are regenerated, one at a time with the same parser "
                 "version, into `data/overlay/recovered-cards.json` by `src/recover_dropped.py`; "
                 "`card-data.json` itself is never modified.\n")

    if dropped_rows:
        lines.append("## Dropped cards\n")
        lines.append("For each contested key: `WON` is the entry the snapshot actually contains, "
                     "`DROPPED` is the id that lost this key, with its class.\n")
        for c in dropped_rows:
            lines.append(f"### `{c['key']}`\n")
            for oid, descs in sorted(c["oids"].items()):
                mark = "WON    " if oid == c["winner"] else "DROPPED"
                d = descs[0]
                face = f" (face of *{d['name']}*)" if d.get("faceName") else ""
                sets = ",".join(d["printings"][:8]) + ("..." if len(d["printings"]) > 8 else "")
                cls = f" — `{klass[oid]}`: {CLASS_TEXT[klass[oid]]}" if oid in klass else ""
                lines.append(f"- **{mark}** `{oid}`{face}{cls}")
                lines.append(f"  - type: {d.get('type')} | layout: {d.get('layout')} | printings: {len(d['printings'])} ({sets})")
                if d.get("text"):
                    lines.append(f"  - text: {d['text']}")
            lines.append("")

    unseen = [c for c in collisions if not c["in_snapshot"]]
    if unseen:
        lines.append("## Contested keys absent from the snapshot entirely\n")
        lines.append("Every id under these keys is missing. Most will simply postdate the "
                     "2026-04-20 snapshot rather than having collided.\n")
        for c in unseen:
            ids = ", ".join(f"`{o}`" for o in sorted(c["oids"]))
            lines.append(f"- `{c['key']}` -- {len(c['oids'])} ids: {ids}")
        lines.append("")

    path = os.path.join(HERE, "NAME_COLLISIONS.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    summary = {
        "contested_keys": len(collisions),
        "keys_with_a_drop": len(dropped_rows),
        "oracle_ids_dropped": n_lost,
        "losing_ids_by_class": dict(sorted(by_class.items())),
        "losing_key_slots": n_slots,
        "contested_keys_absent_entirely": len(unseen),
        "mtgjson_version": meta.get("version"),
        "mtgjson_date": meta.get("date"),
    }
    with open(os.path.join(HERE, "build", "collisions.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    print(json.dumps(summary, indent=1))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
