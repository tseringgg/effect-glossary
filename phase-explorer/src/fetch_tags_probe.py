#!/usr/bin/env python3
"""Fetch Scryfall's oracle-tag bulk data into a NEW file (data/oracle-tags-<updated_at date>.json plus a .meta.json sidecar). Read-only probe helper; the old snapshot in
development/versions/card_function_search_v0.2/data/ is never touched.

    python src/fetch_tags_probe.py

Same conventions as that project's scripts/fetch_oracle_tags.py: the small /bulk-data/oracle_tags index first, a descriptive User-Agent, the (gzip, one JSON object per line) file only when the
cached sidecar's updated_at differs from the index (Scryfall refreshes the bulk data about daily, so a second run on the same day downloads nothing).
"""
import gzip
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
UA = "deckdoctor-effect-glossary-tag-probe/0.1 (read-only investigation; contact: enderswift2@gmail.com)"
INDEX = "https://api.scryfall.com/bulk-data/oracle_tags"


def get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, application/gzip, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main():
    idx = json.loads(get(INDEX, 30).decode("utf-8"))
    upd = idx["updated_at"]
    day = upd[:10].replace("-", "")
    raw = os.path.join(DATA, "oracle-tags-%s.json" % day)
    meta = raw.replace(".json", ".meta.json")
    if os.path.exists(raw) and os.path.exists(meta) and json.load(io.open(meta, encoding="utf-8")).get("updated_at") == upd:
        print("cached, up to date:", raw)
        return
    uri = idx["jsonl_download_uri"]
    recs = [json.loads(l) for l in gzip.decompress(get(uri, 300)).splitlines() if l.strip()]
    with io.open(raw, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(recs))
    with io.open(meta, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"updated_at": upd, "jsonl_download_uri": uri, "records": len(recs)}))
    print("fetched %d tags, updated_at %s -> %s" % (len(recs), upd, raw))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                                   # a failed refetch is reported, never fatal: the old snapshot stays usable
        print("REFETCH FAILED:", e)
        sys.exit(2)
