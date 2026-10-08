#!/usr/bin/env python3
"""Archive the card-level view (browse / ledger / card-explorer pages and everything they read).

    python src/archive_card_level_view.py [archive/card-level-view-2026-10]

COPIES only; nothing live is moved, changed or deleted, and no generator is touched. The archive mirrors
the live layout (reports/, build/, corrections/, data/overlay/, src/) so the archived pages' relative
fetches ("../build/...") work when the archive directory is served as the root.

Byte identity. Every archived file is a byte copy of today's file, with ONE exception: the four HTML pages
get a banner inserted right after <body>. For those, the manifest records both hashes and the check is that
removing the exact banner string reproduces the live file's hash. MANIFEST.sha256 lists, per file:
  <sha256 of the live file before>  <sha256 of the live file after>  <sha256 of the archived file>  <kind>  <path>
"""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else os.path.join("archive", "card-level-view-2026-10"))

BANNER = (b'<div id="archived-view-banner" style="margin:0;padding:10px 16px;background:#7a1f1f;color:#fff;'
          b'font:600 14px/1.3 system-ui,sans-serif;text-align:center">'
          b'Archived card-level view. Numbers here do not match the current view.</div>')
PAGES = ["reports/browse.html", "reports/ledger.html", "reports/card-explorer.html", "reports/review-queue.html"]

REPORTS = ["cardview.js", "branchmap.js", "findcard.js", "branches.md", "sectors.md", "leaf-type-audit.md",
           "coverage-ledger.md", "leaf-phrases.md", "sub-branches.md", "clustering-structural.md"]
# every build/ file the pages (browse, ledger, card-explorer, review-queue, cardview.js, findcard.js) fetch, plus
# ability_ledger.json (read by build_ledger.py) and condition_drops.json (read by the ability layers)
BUILD = ["unorganized.json", "unorganized_cards.json", "lookup.json", "placements.json", "partial_ability_layer.json",
         "signature_layer.json", "keyword_layer.json", "ability_layer.json", "also_fits.json", "index.json",
         "clusters.json", "branches.json", "sectors.json", "type_audit.json", "leaf_phrases.json", "match_spans.json",
         "meta.json", "card_images.json", "facets.json", "collisions.json", "ledger.json", "ability_ledger.json",
         "condition_drops.json"]
DOCS = ["README.md", "KNOWN_LIMITATIONS.md", "SCHEMA.md", "DECISIONS.md", "PROVENANCE.md", "NAME_COLLISIONS.md"]
# generators of the old view; probe / archive scripts of the new work are not part of it
NOT_OLD = {"probe_signature_taxonomy.py", "analyze_signature_probe.py", "probe2_signature_taxonomy.py",
           "analyze2_signature_probe.py", "sample2_signature_probe.py", "archive_card_level_view.py",
           "build_ability_taxonomy.py"}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    if os.path.exists(DEST):
        sys.exit("archive exists; refusing to overwrite: " + DEST)
    files = [("reports/" + f, "copy") for f in REPORTS] + [(p, "page") for p in PAGES]
    files += [("build/" + f, "copy") for f in BUILD]
    files += [("build/chunks/" + f, "copy") for f in sorted(os.listdir(os.path.join(HERE, "build", "chunks")))]
    files += [("corrections/" + f, "copy") for f in sorted(os.listdir(os.path.join(HERE, "corrections")))]
    files += [("data/overlay/" + f, "copy") for f in sorted(os.listdir(os.path.join(HERE, "data", "overlay")))]
    files += [("src/" + f, "copy") for f in sorted(os.listdir(os.path.join(HERE, "src")))
              if f.endswith(".py") and f not in NOT_OLD]
    files += [("docs/" + f, "doc:" + f) for f in DOCS]
    before = {}
    for rel, kind in files:
        src = os.path.join(HERE, rel if not kind.startswith("doc:") else kind[4:])
        before[rel] = sha(src)
    rows = []
    for rel, kind in files:
        src = os.path.join(HERE, rel if not kind.startswith("doc:") else kind[4:])
        dst = os.path.join(DEST, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if kind == "page":
            b = open(src, "rb").read()
            assert b.count(b"<body>") == 1
            out = b.replace(b"<body>", b"<body>" + BANNER, 1)
            with open(dst, "wb") as fh:
                fh.write(out)
            # banner removal must reproduce the live file exactly
            assert sha_bytes(open(dst, "rb").read().replace(BANNER, b"", 1)) == before[rel]
        else:
            shutil.copyfile(src, dst)
        rows.append((rel, kind))
    manifest, bad = [], []
    for rel, kind in rows:
        src = os.path.join(HERE, rel if not kind.startswith("doc:") else kind[4:])
        after = sha(src)
        arch = sha(os.path.join(DEST, rel))
        k = "page+banner" if kind == "page" else "identical"
        if kind == "page":
            stripped = sha_bytes(open(os.path.join(DEST, rel), "rb").read().replace(BANNER, b"", 1))
            ok = before[rel] == after == stripped
        else:
            ok = before[rel] == after == arch
        if not ok:
            bad.append(rel)
        manifest.append("%s  %s  %s  %s  %s" % (before[rel], after, arch, k, rel))
    with open(os.path.join(DEST, "MANIFEST.sha256"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# live-before  live-after  archived  kind  path\n" + "\n".join(manifest) + "\n")
    print("files", len(manifest), "mismatches", bad)
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
