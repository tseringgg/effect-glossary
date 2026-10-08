#!/usr/bin/env python3
"""Join the snapshot's oracle ids to Scryfall card images.

Reads   build/index.json                      our entries, keyed by oracle id
        data/scryfall-oracle-cards.jsonl.gz   Scryfall bulk export (downloaded
                                              here, kept compressed)
Writes  build/card_images.json            oracle id -> what is needed to build
                                          an image URL

    python src/build_images.py            # download if missing, then join
    python src/build_images.py --refresh  # re-download even if present

Why bulk and not the API: Scryfall asks that programs use the bulk exports
rather than issuing tens of thousands of card requests, and `oracle_cards` is
one entry per oracle id -- exactly our key -- at ~25 MB. The download lands in
data/ beside the other gitignored reference files and is only re-fetched when
asked.

Nothing here contacts Scryfall at page-view time; the pages only load images
from their CDN, which is what that CDN is for.

Image URLs are stored as a template plus per-card parts rather than as ~34,000
full strings, which keeps the output near 1 MB and lets the page choose a size.
The template is VERIFIED against Scryfall's own `image_uris` during the join --
if their URL shape ever changes, this run fails loudly instead of writing a
file full of 404s.
"""
import collections
import io
import json
import gzip
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
DATA = os.path.join(HERE, "data")
BULK = os.path.join(DATA, "scryfall-oracle-cards.jsonl.gz")

UA = "phase-explorer/0.1 (local dev tool; read-only consumer)"
TEMPLATE = "https://cards.scryfall.io/{size}/{face}/{a}/{b}/{id}.jpg?{ts}"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    return urllib.request.urlopen(req, timeout=120)


def download():
    sys.stderr.write("fetching Scryfall bulk manifest" + chr(10))
    with get("https://api.scryfall.com/bulk-data") as fh:
        manifest = json.load(fh)
    entry = next(b for b in manifest["data"] if b["type"] == "oracle_cards")
    # They serve gzipped JSONL now; the older `download_uri` (a plain JSON
    # array) is gone, so read one object per line and never hold the whole
    # export in memory.
    uri = entry.get("jsonl_download_uri") or entry.get("download_uri")
    if not uri:
        sys.exit("bulk manifest has no download uri: " + repr(sorted(entry)))
    updated = entry.get("updated_at", "")
    size = entry.get("compressed_size") or entry.get("size") or 0
    sys.stderr.write(f"downloading oracle_cards ({size/1e6:.1f} MB){chr(10)}")
    os.makedirs(DATA, exist_ok=True)
    tmp = BULK + ".tmp"
    with get(uri) as src, io.open(tmp, "wb") as dst:
        while True:
            chunk = src.read(1 << 20)
            if not chunk:
                break
            dst.write(chunk)
            sys.stderr.write(".")
    sys.stderr.write(chr(10))
    os.replace(tmp, BULK)
    return updated


def parts(url):
    """Split a Scryfall image URL into the bits the template needs, or None."""
    # https://cards.scryfall.io/normal/front/9/3/<id>.jpg?1712354367
    try:
        head, ts = url.split("?", 1)
        bits = head.split("/")
        size, face, a, b, fname = bits[3], bits[4], bits[5], bits[6], bits[7]
        cid = fname[:-4]
        return size, face, a, b, cid, ts
    except Exception:
        return None


def face_images(card):
    """{face_name: image url} for a card, front first."""
    out = {}
    if card.get("image_uris"):
        out["front"] = card["image_uris"].get("normal")
    for i, f in enumerate(card.get("card_faces") or []):
        iu = f.get("image_uris") or {}
        if iu.get("normal"):
            out["front" if i == 0 else "back"] = iu["normal"]
    return {k: v for k, v in out.items() if v}


def main():
    if "--refresh" in sys.argv or not os.path.exists(BULK):
        updated = download()
    else:
        updated = "(existing file)"
        sys.stderr.write("using existing " + BULK + chr(10))

    index = json.load(io.open(os.path.join(BUILD, "index.json"), encoding="utf-8"))
    ours = {}
    for r in index["rows"]:
        oid = r["id"].split("/")[0]
        ours.setdefault(oid, r["name"])

    sys.stderr.write("reading bulk export" + chr(10))
    cards, stat = {}, collections.Counter()
    template_ok, template_bad = 0, []
    n_bulk = 0
    for line in gzip.open(BULK, "rt", encoding="utf-8"):
        line = line.strip().rstrip(",")
        if not line or line in ("[", "]"):
            continue
        card = json.loads(line)
        n_bulk += 1
        oid = card.get("oracle_id")
        if not oid or oid not in ours or oid in cards:
            continue
        imgs = face_images(card)
        if not imgs:
            stat["in bulk but no image"] += 1
            continue
        p = parts(imgs["front"])
        if not p:
            stat["unparseable image url"] += 1
            continue
        size, face, a, b, cid, ts = p
        # Self-check: rebuild their URL from our template and compare.
        rebuilt = TEMPLATE.format(size=size, face=face, a=a, b=b, id=cid, ts=ts)
        if rebuilt == imgs["front"]:
            template_ok += 1
        elif len(template_bad) < 5:
            template_bad.append((imgs["front"], rebuilt))
        cards[oid] = [cid, ts, 1 if "back" in imgs else 0]

    if template_bad:
        print("URL template no longer matches Scryfall's own image_uris:")
        for real, mine in template_bad:
            print("  theirs:", real)
            print("  ours:  ", mine)
        sys.exit("refusing to write a file of URLs that may not resolve")

    missing = [(oid, nm) for oid, nm in ours.items() if oid not in cards]
    alchemy = [nm for _, nm in missing if nm.startswith("A-")]

    doc = {
        "source": "https://api.scryfall.com/bulk-data (oracle_cards)",
        "bulk_updated_at": updated,
        "template": TEMPLATE,
        "note": ("cards[oracle_id] = [scryfall card id, timestamp, has_back]. "
                 "Build a URL with template.format(size=..., face='front'|'back', "
                 "a=id[0], b=id[1], id=id, ts=ts). Sizes Scryfall serves: "
                 "small, normal, large, art_crop, border_crop."),
        "n_bulk_cards": n_bulk,
        "n_ours": len(ours),
        "n_matched": len(cards),
        "n_missing": len(missing),
        "n_missing_alchemy": len(alchemy),
        "missing_note": ("every unmatched id is an Alchemy 'A-' rebalanced card. "
                         "Those are digital-only and are not in the oracle_cards "
                         "export; the larger default_cards export carries them if "
                         "they are ever wanted."),
        "missing_sample": [nm for _, nm in missing[:40]],
        "cards": cards,
    }
    with io.open(os.path.join(BUILD, "card_images.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))

    pct = 100 * len(cards) / len(ours) if ours else 0
    print("build/card_images.json")
    print(f"  {n_bulk:,} cards in the bulk export")
    print(f"  template verified against {template_ok:,} of Scryfall's own URLs")
    print(f"  {len(cards):,} of {len(ours):,} oracle ids matched ({pct:.1f}%)")
    print(f"  {len(missing):,} unmatched, of which {len(alchemy):,} are "
          f"Alchemy 'A-' entries")
    for k, v in stat.most_common():
        print(f"  {v:,} {k}")
    if missing:
        print("  first unmatched:", ", ".join(nm for _, nm in missing[:6]))


if __name__ == "__main__":
    main()
