#!/usr/bin/env python3
"""Export the tester view of reports/browse.html as pure static files: dist/.

    python src/export_static.py [--out dist] [--require-feedback]
    python src/export_static.py --hand-view-only      # only (re)write build/hand_view.json, so the tester page also runs from the project tree
    python src/export_static.py --check [--out dist]  # re-verify an existing dist/ against the whitelist, change nothing

What goes in is a WHITELIST: the page, its scripts and stylesheet, config.js, the build data the tester page reads, and build/hand_view.json (written here). Nothing else can get in; a
file the page reads that is not classified below stops the export. The export is deterministic (no timestamps, sorted, byte-for-byte copies; two runs give the same manifest) and finishes by
checking dist/ against the whitelist and for anything private: no corrections/, backups, logs, archive, data/ or source files, and hand_view.json must hold card ids and group ids and nothing else.

Read-only on the project: corrections/manual_placements.json is read (and hashed before and after, so a change during the export stops it) to project build/hand_view.json; nothing in corrections/,
archive/ or any frozen file is opened for writing.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import zlib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
REPORTS = os.path.join(HERE, "reports")
CORR_PLACEMENTS = os.path.join(HERE, "corrections", "manual_placements.json")

BASE_PAGE_FILES = ["browse.html", "tester.js", "tester.css", "config.js", "abilityfind.js", "manualedit.js", "suggested.js", "groupsearch.js", "cardpin.js", "mergepage.js"]
FILTER_FILES = ["testerfilters.js", "testerfilters.css"]          # feature TESTER_FILTERS (reports/config.js): exported only while the flag is on
TYPE_FILES = ["typegroups.js", "typegroups.css"]                  # feature TYPE_GROUPS: type and subtype pages
TYPE_BUILD = ["type_groups/index.json", "type_groups/members.json"]   # the index is read at the first search / when the "Card types" folder opens, the members when a type page opens
FLIP_FILES = ["flipfaces.js", "flipfaces.css"]                    # feature FLIP_FACES: the flip control, either face searchable
FLIP_BUILD = ["faces/faces.json"]
AB_FILES = ["abilitypages.js", "abilitypages.css"]               # feature ABILITY_TYPE_PAGES: ability-type pages (ABILITY_TYPE_FILTERS changes only testerfilters.js and needs it)
AB_BUILD = ["ability_pages/index.json"]                          # the index is read when the "Ability types" folder opens / at the first search; the pages (ability_pages/p/*.json) when one opens
AB_LAZY = ("ability_pages/p", r"^[a-z0-9.\-]+\.json$")
# NARROW_NO_CUT and COLOUR_MODES change only reports/testerfilters.js (and need TESTER_FILTERS): they add no file
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports", "config.js")


def flag_on(path=None, name="TESTER_FILTERS"):
    m = re.search(r"\b" + name + r"\s*:\s*(true|false)", open(path or CONFIG_PATH, encoding="utf-8").read())
    return bool(m) and m.group(1) == "true"


def pages_for(path=None):
    """The page files, and the extra build files, that the flags in this config.js ask for (none of the new ones while every new flag is off)."""
    files, build = list(BASE_PAGE_FILES), []
    if flag_on(path):
        files += FILTER_FILES
    if flag_on(path, "TYPE_GROUPS"):
        files += TYPE_FILES; build += TYPE_BUILD
    if flag_on(path, "FLIP_FACES"):
        files += FLIP_FILES; build += FLIP_BUILD
    if flag_on(path, "ABILITY_TYPE_PAGES"):
        files += AB_FILES; build += AB_BUILD
    return files, build


PAGE_FILES, EXTRA_BUILD = pages_for()
SRC_OVERRIDE = {}                                  # --config: another file stands in for reports/config.js (tests)


def page_src(n):
    return SRC_OVERRIDE.get(n) or os.path.join(REPORTS, n)
CORE_BUILD_BASE = [
    "ability_taxonomy.json", "ability_taxonomy_cards.json", "ability_taxonomy_members.json", "ability_taxonomy_unorganized.json", "ability_taxonomy_lookup.json",
    "loose_groups.json", "loose_unread.json", "tentative_placements.json", "tag_placements.json", "annotation_placements.json",
    "keyword_facet.json", "hand_group_hits.json", "sibling_placements.json", "card_images.json", "manual_index.json",
    "suggested_cards/meta.json", "merged_groups/index.json", "card_pin/meta.json", "text_sug/meta.json",
    "group_search/meta.json", "group_search/index.json", "group_search/words.txt",
]
CORE_BUILD = CORE_BUILD_BASE + EXTRA_BUILD
LAZY_BASE = [                                    # (directory under build/, regex on the file name): read on demand by the tester page
    ("suggested_cards/g", r"^\d+q\.json$"), ("suggested_cards/t", r"^\d+q\.json$"), ("text_sug/l", r"^\d+\.json$"),
]
LAZY_RULES = LAZY_BASE + ([AB_LAZY] if flag_on(None, "ABILITY_TYPE_PAGES") else [])
GENERATED = ["build/hand_view.json", "index.html", "manifest.json"]
# read by the dev page only (editing, batch, queue, parse audit, the "Left out" list): never exported
DEV_ONLY_JSON = {"index.json", "manual_suggestions.json", "manual_fallback.json", "card_flags.json", "text_sug/queue.json"}
DEV_ONLY_PREFIX = ("chunks/", "text_sug/c/")
DEV_ONLY_FETCH = ("../corrections/manual_placements.json", "../api/manual/ping", "../api/manual", "../api/manual/batch", "../api/groupsearch/ping", "../api/groupsearch/log")
STATIC_FETCH_OK = ("../build/group_search/words.txt",)

FORBIDDEN_PARTS = {"corrections", "backups", "archive", "data", "src", "logs", "log", "__pycache__", ".git"}
FORBIDDEN_NAME = re.compile(r"(\.bak|\.tmp|\.log|\.lock|\.pyc|\.orig)$|group_search_log|manual_placements|branch_review|hand_groups\.json|group_aliases|group_descriptions|merged_groups\.json|tag_denylist|\.md$", re.I)
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
GID = re.compile(r"^[A-Za-z]+:\S+$")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def die(msg):
    sys.stderr.write("export_static: STOP: %s\n" % msg)
    sys.exit(1)


def hand_view():
    """The projection of the hand placements: card id and group id only. Fails if anything else would be written."""
    if not os.path.exists(CORR_PLACEMENTS):
        return {"adds": {}, "removes": {}, "nofit": []}
    before = sha(CORR_PLACEMENTS)
    with open(CORR_PLACEMENTS, encoding="utf-8") as fh:
        doc = json.load(fh)
    adds, removes, nofit = {}, {}, set()
    for oid, e in doc.get("edits", {}).items():
        for gid, g in e.get("groups", {}).items():
            act = g.get("action")
            if act == "add":
                adds.setdefault(oid, set()).add(gid)
            elif act == "remove":
                removes.setdefault(oid, set()).add(gid)
            elif act == "nofit":
                nofit.add(oid)
    out = {"adds": {o: sorted(v) for o, v in sorted(adds.items())}, "removes": {o: sorted(v) for o, v in sorted(removes.items())}, "nofit": sorted(nofit)}
    if sha(CORR_PLACEMENTS) != before:
        die("corrections/manual_placements.json changed while it was being read")
    check_hand_view(out)
    return out


def check_hand_view(d):
    if not isinstance(d, dict) or set(d) != {"adds", "removes", "nofit"}:
        die("hand_view.json must have exactly the keys adds, removes, nofit; found %s" % sorted(d) if isinstance(d, dict) else "not an object")
    for sect in ("adds", "removes"):
        if not isinstance(d[sect], dict):
            die("hand_view.%s is not an object" % sect)
        for oid, gids in d[sect].items():
            if not UUID.match(oid) or not isinstance(gids, list) or not gids:
                die("hand_view.%s: %r is not a card id with a list of group ids" % (sect, oid))
            for g in gids:
                if not isinstance(g, str) or not GID.match(g):
                    die("hand_view.%s[%s]: %r is not a group id" % (sect, oid, g))
    if not isinstance(d["nofit"], list) or not all(isinstance(o, str) and UUID.match(o) for o in d["nofit"]):
        die("hand_view.nofit must be a list of card ids")


def hand_view_bytes(d):
    return (json.dumps(d, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def classify_page_references():
    """Every file the page asks for must be classified (exported, or dev only); anything new stops the export."""
    src = open(os.path.join(REPORTS, "browse.html"), encoding="utf-8").read()
    names = set(re.findall(r'\bJ\("([^"]+)"\)', src))
    prefixes = set(re.findall(r'\bJ\("([^"]+/)"\s*\+', src))
    prefixes |= set(re.findall(r"\bJ\(`([^`$]+/)\$\{", src))
    unknown = []
    for n in sorted(names):
        if n in CORE_BUILD or n in DEV_ONLY_JSON or n == "hand_view.json":
            continue
        unknown.append(n)
    for p in sorted(prefixes):
        if p.startswith(DEV_ONLY_PREFIX) or any(r[0].startswith(p.rstrip("/")) for r in LAZY_RULES) or p in ("suggested_cards/", "text_sug/l/"):
            continue
        unknown.append(p + "*")
    fetches = set(re.findall(r'fetch\("([^"]+)"', src))
    for f in sorted(fetches):
        if f.endswith("/"):                         # the JSON loader's own prefix; its files are classified above
            continue
        if f.startswith("../build/") and f in STATIC_FETCH_OK:
            continue
        if f in DEV_ONLY_FETCH:
            continue
        unknown.append("fetch " + f)
    if unknown:
        die("browse.html reads files the export does not know how to classify: %s. Add each to CORE_BUILD, LAZY_RULES or the dev-only lists in src/export_static.py." % ", ".join(unknown))
    return names, prefixes


def plan():
    files = {}                                   # dist path -> (source path or None, kind)
    for n in PAGE_FILES:
        p = page_src(n)
        if not os.path.exists(p):
            die("missing %s" % p)
        files["reports/" + n] = (p, "page")
    for n in CORE_BUILD:
        p = os.path.join(BUILD, *n.split("/"))
        if not os.path.exists(p):
            die("missing build file %s: run the build steps in README.md first" % p)
        files["build/" + n] = (p, "data")
    for d, rx in LAZY_RULES:
        full = os.path.join(BUILD, *d.split("/"))
        if not os.path.isdir(full):
            die("missing build folder %s" % full)
        pat = re.compile(rx)
        for n in sorted(os.listdir(full)):
            if pat.match(n):
                files["build/%s/%s" % (d, n)] = (os.path.join(full, n), "lazy")
    for g in GENERATED:
        files[g] = (None, "generated")
    return files


def index_html():
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LogicVoid’s Deck Doctor</title>'
            '<link rel="icon" href="data:,"><meta http-equiv="refresh" content="0; url=reports/browse.html"></head>'
            '<body><p><a href="reports/browse.html">LogicVoid’s Deck Doctor</a></p></body></html>\n').encode("utf-8")


def allowed_paths():
    """The whitelist as a predicate over dist-relative paths (the manifest is written last)."""
    exact = {"reports/" + n for n in PAGE_FILES} | {"build/" + n for n in CORE_BUILD} | set(GENERATED)
    lazy = [(re.compile(r"^build/%s/%s" % (re.escape(d), rx[1:])), d) for d, rx in LAZY_RULES]
    def which(rel):
        if rel in exact:
            return "exact"
        for rx, d in lazy:
            if rx.match(rel):
                return "lazy:" + d
        return None
    return which


def clean_out(out):
    """Empty a previous export. A top-level .git (dist/ may be a repository that is published from) is never touched."""
    def onerr(fn, path, exc):
        os.chmod(path, 0o700); fn(path)
    for n in os.listdir(out):
        if n == ".git":
            continue
        p = os.path.join(out, n)
        if os.path.isdir(p):
            shutil.rmtree(p, onerror=onerr)
        else:
            os.remove(p)


def verify(out, strict_manifest=True):
    """Every file in dist/ is on the whitelist; nothing private; hand_view.json is ids only; the page is byte-identical to the source."""
    which = allowed_paths()
    found, counts, bad = [], {}, []
    for root, dirs, fs in os.walk(out):
        dirs.sort()
        if root == out and ".git" in dirs:
            dirs.remove(".git")                       # a repository around the export is not part of it
        for f in sorted(fs):
            rel = os.path.relpath(os.path.join(root, f), out).replace(os.sep, "/")
            found.append(rel)
            parts = rel.split("/")
            if any(p.lower() in FORBIDDEN_PARTS for p in parts[:-1]) or FORBIDDEN_NAME.search(parts[-1]):
                bad.append("private or unneeded path: " + rel)
            w = which(rel)
            if not w:
                bad.append("not on the whitelist: " + rel)
            else:
                counts[w] = counts.get(w, 0) + 1
    for rel in ["reports/" + n for n in PAGE_FILES] + ["build/" + n for n in CORE_BUILD] + GENERATED:
        if rel not in found:
            bad.append("whitelisted file missing: " + rel)
    for n in PAGE_FILES:
        a, b = os.path.join(out, "reports", n), page_src(n)
        if os.path.exists(a) and sha(a) != sha(b):
            bad.append("reports/%s differs from its source" % n)
    hv = os.path.join(out, "build", "hand_view.json")
    if os.path.exists(hv):
        raw = open(hv, "rb").read()
        try:
            d = json.loads(raw.decode("utf-8"))
            check_hand_view(d)
            if raw != hand_view_bytes(d):
                bad.append("build/hand_view.json is not in the canonical form")
        except SystemExit:
            raise
        except Exception as e:
            bad.append("build/hand_view.json unreadable: %s" % e)
    if bad:
        die("dist check failed:\n  " + "\n  ".join(bad))
    return found, counts


def size_report(files_info):
    cats = {}
    for rel, (n, g, kind) in files_info.items():
        c = cats.setdefault(kind, [0, 0, 0])
        c[0] += 1; c[1] += n; c[2] += g
    return {k: {"files": v[0], "bytes": v[1], "gzip6_bytes": v[2]} for k, v in sorted(cats.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--require-feedback", action="store_true", help="fail while config.js still holds the placeholder feedback link")
    ap.add_argument("--hand-view-only", action="store_true")
    ap.add_argument("--config", help="use this file as reports/config.js (tests: the flags off without editing the real file)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    global PAGE_FILES, EXTRA_BUILD, CORE_BUILD
    if a.config:
        SRC_OVERRIDE["config.js"] = os.path.abspath(a.config)
        PAGE_FILES, EXTRA_BUILD = pages_for(a.config)
        CORE_BUILD = CORE_BUILD_BASE + EXTRA_BUILD
        LAZY_RULES[:] = LAZY_BASE + ([AB_LAZY] if flag_on(a.config, "ABILITY_TYPE_PAGES") else [])
    out = a.out if os.path.isabs(a.out) else os.path.join(HERE, a.out)
    out = os.path.normpath(out)

    if a.hand_view_only:
        d = hand_view()
        with open(os.path.join(BUILD, "hand_view.json"), "wb") as fh:
            fh.write(hand_view_bytes(d))
        print("wrote build/hand_view.json: %d cards with adds, %d with removes, %d nothing-fits" % (len(d["adds"]), len(d["removes"]), len(d["nofit"])))
        return
    if a.check:
        found, counts = verify(out)
        print("dist check passed: %d files, all on the whitelist %s" % (len(found), counts))
        return

    classify_page_references()
    if EXTRA_BUILD and not a.check:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import build_type_groups                     # deterministic: the same MTGJSON file and card list give the same bytes; an unchanged file is not rewritten
        if flag_on(None if not a.config else a.config, "TYPE_GROUPS") or flag_on(None if not a.config else a.config, "FLIP_FACES"):
            build_type_groups.write()
        if flag_on(None if not a.config else a.config, "ABILITY_TYPE_PAGES"):
            import build_ability_pages                 # deterministic as well; writes only build/ability_pages/
            build_ability_pages.write()
    files = plan()
    cfg = open(page_src("config.js"), encoding="utf-8").read()
    placeholder = "REPLACE-ME" in cfg
    if placeholder and a.require_feedback:
        die("reports/config.js still holds the placeholder feedback link")
    if os.path.commonpath([out, HERE]) != HERE or out in (HERE, BUILD, REPORTS, os.path.join(HERE, "src"), os.path.join(HERE, "corrections"), os.path.join(HERE, "archive"), os.path.join(HERE, "data")):
        die("refusing to write to %s" % out)
    if os.path.exists(out):
        if [n for n in os.listdir(out) if n != ".git"] and not os.path.exists(os.path.join(out, "manifest.json")):
            die("%s exists, is not empty and is not a previous export (no manifest.json); not touching it" % out)
        clean_out(out)
    os.makedirs(out, exist_ok=True)

    hv = hand_view()
    hv_bytes = hand_view_bytes(hv)
    info = {}
    for rel in sorted(files):
        src, kind = files[rel]
        dst = os.path.join(out, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if rel == "manifest.json":
            continue
        if kind == "generated":
            data = hv_bytes if rel == "build/hand_view.json" else index_html()
            with open(dst, "wb") as fh:
                fh.write(data)
        else:
            shutil.copyfile(src, dst)
            data = open(dst, "rb").read()
        info[rel] = (len(data), len(zlib.compress(data, 6)), "page" if kind == "page" else "generated" if kind == "generated" else ("data:" + rel.split("/")[1] if kind == "lazy" else "data"))
    manifest = {
        "note": "Whitelist export of the tester view (src/export_static.py). Deterministic: no timestamps; sha256 of every file.",
        "hand_view": {"cards_with_adds": len(hv["adds"]), "adds": sum(len(v) for v in hv["adds"].values()), "cards_with_removes": len(hv["removes"]), "nothing_fits": len(hv["nofit"])},
        "feedback_placeholder_still_in_config_js": placeholder,
        "size_report": size_report(info),
        "total_bytes": sum(v[0] for v in info.values()),
        "total_gzip6_bytes": sum(v[1] for v in info.values()),
        "file_count": len(info) + 1,
        "files": [{"path": rel, "bytes": info[rel][0], "sha256": sha(os.path.join(out, *rel.split("/")))} for rel in sorted(info)],
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    found, counts = verify(out)
    print("exported %d files to %s: %.1f MB (about %.1f MB gzipped)" % (len(found), os.path.relpath(out, HERE), manifest["total_bytes"] / 1e6, manifest["total_gzip6_bytes"] / 1e6))
    for k, v in manifest["size_report"].items():
        print("  %-22s %5d files %12s bytes  gzip %11s" % (k, v["files"], format(v["bytes"], ","), format(v["gzip6_bytes"], ",")))
    print("whitelist check passed: %s" % counts)
    print("hand_view.json: %(cards_with_adds)d cards, %(adds)d placements, ids only" % manifest["hand_view"])
    if placeholder:
        print("WARNING: reports/config.js still holds the placeholder feedback link (https://discord.gg/REPLACE-ME); replace it before the site is shared (--require-feedback makes this fatal).")


if __name__ == "__main__":
    main()
