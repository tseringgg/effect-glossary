"""Ingest Scryfall's full Oracle card corpus from the bulk-data API.

Source: the `oracle_cards` bulk file -- one record per Oracle ID, i.e. one per
distinct card, not one per printing. Printings share oracle text, so they would
only inflate occurrence counts without adding a single new effect.

FORMAT NOTE. The bulk-data API exposes `jsonl_download_uri` (gzipped JSON
Lines). The older `download_uri` (plain JSON array) is gone. This script
requires `jsonl_download_uri` and fails loudly if it is missing rather than
guessing at a format -- parsing a JSON array as JSONL would fail in confusing
ways, or worse, half-succeed.

Output goes under data/full/, deliberately separate from data/cards.json and
data/effects.yaml: those feed the 30-card search experiment, which this
corpus must not disturb.

Normalized record shape matches fetch_cards.py (what extract_effects /
glossary.build expect), keyed by oracle_id:

    card_id, name, mana_cost, type_line, oracle_text, layout, scryfall_id

Multi-face cards (transform, modal DFC, split, adventure, flip...) carry their
rules text per face in `card_faces`, with no top-level oracle_text. Those face
texts are joined with a newline, which extraction already treats as an effect
boundary -- so each face's abilities become chunks, with no extraction change.

    python ingest_bulk.py            # use cached download if present
    python ingest_bulk.py --refresh  # re-query bulk-data and re-download
"""
import gzip
import json
import os
import sys
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FULL = os.path.join(HERE, os.pardir, "data", "full")
CARDS_PATH = os.path.join(FULL, "cards.jsonl")
MANIFEST_PATH = os.path.join(FULL, "ingest_manifest.json")

BULK_INDEX = "https://api.scryfall.com/bulk-data"
BULK_TYPE = "oracle_cards"
HEADERS = {"User-Agent": "effect-glossary-experiment/0.1", "Accept": "application/json"}


def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60)


def bulk_entry():
    with _get(BULK_INDEX) as resp:
        index = json.load(resp)
    for entry in index.get("data", []):
        if entry.get("type") == BULK_TYPE:
            if "jsonl_download_uri" not in entry:
                raise SystemExit(
                    "Scryfall bulk-data entry %r has no jsonl_download_uri; keys are %s. "
                    "The API format changed again -- check the docs before adapting."
                    % (BULK_TYPE, sorted(entry)))
            return entry
    raise SystemExit("No %r entry in %s" % (BULK_TYPE, BULK_INDEX))


def download(entry, refresh=False):
    """Download the gzipped JSONL once; reuse the cached file afterwards."""
    os.makedirs(FULL, exist_ok=True)
    uri = entry["jsonl_download_uri"]
    path = os.path.join(FULL, os.path.basename(uri))
    if os.path.exists(path) and not refresh:
        print("cached: %s" % path)
        return path
    tmp = path + ".part"
    print("downloading %s (%.1f MB compressed)" % (uri, entry.get("compressed_size", 0) / 1e6))
    with _get(uri) as resp, open(tmp, "wb") as fh:
        while True:
            block = resp.read(1 << 20)
            if not block:
                break
            fh.write(block)
    os.replace(tmp, path)
    return path


def latest_cached():
    if not os.path.isdir(FULL):
        return None
    names = sorted(n for n in os.listdir(FULL) if n.startswith("oracle-cards-") and n.endswith(".jsonl.gz"))
    return os.path.join(FULL, names[-1]) if names else None


def oracle_text_of(card):
    if card.get("oracle_text"):
        return card["oracle_text"]
    faces = card.get("card_faces") or []
    return "\n".join(f["oracle_text"] for f in faces if f.get("oracle_text"))


def normalize(card):
    faces = card.get("card_faces") or []
    return {
        "card_id": card["oracle_id"] if card.get("oracle_id") else faces[0]["oracle_id"],
        "name": card["name"],
        "mana_cost": card.get("mana_cost") or " // ".join(f.get("mana_cost", "") for f in faces),
        "type_line": card.get("type_line") or " // ".join(f.get("type_line", "") for f in faces),
        "oracle_text": oracle_text_of(card),
        "layout": card.get("layout", ""),
        "scryfall_id": card.get("id"),
    }


def main(refresh=False):
    if refresh or not latest_cached():
        entry = bulk_entry()
        raw_path = download(entry, refresh=refresh)
        source = {"uri": entry["jsonl_download_uri"], "updated_at": entry.get("updated_at")}
    else:
        raw_path = latest_cached()
        print("cached: %s (pass --refresh to re-download)" % raw_path)
        source = {"uri": os.path.basename(raw_path), "updated_at": None}
        # Keep the provenance recorded when this exact file was downloaded.
        if os.path.exists(MANIFEST_PATH):
            with open(MANIFEST_PATH, encoding="utf-8") as fh:
                previous = json.load(fh)
            if previous.get("raw_file") == os.path.basename(raw_path):
                source = previous.get("source", source)

    layouts, faces_joined, empty = Counter(), 0, 0
    seen = set()
    with gzip.open(raw_path, "rt", encoding="utf-8") as src, \
            open(CARDS_PATH, "w", encoding="utf-8") as out:
        for line in src:
            line = line.strip()
            if not line:
                continue
            card = json.loads(line)
            rec = normalize(card)
            if rec["card_id"] in seen:
                raise SystemExit("duplicate oracle_id in oracle_cards: %s" % rec["card_id"])
            seen.add(rec["card_id"])
            layouts[rec["layout"]] += 1
            if not rec["oracle_text"]:
                empty += 1
            elif not card.get("oracle_text") and card.get("card_faces"):
                faces_joined += 1
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    manifest = {
        "bulk_type": BULK_TYPE, "source": source, "raw_file": os.path.basename(raw_path),
        "cards": len(seen), "cards_without_oracle_text": empty,
        "cards_with_joined_faces": faces_joined, "layouts": dict(layouts.most_common()),
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print("%d cards -> %s (%d with no oracle text, %d multi-face joined)"
          % (len(seen), CARDS_PATH, empty, faces_joined))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
