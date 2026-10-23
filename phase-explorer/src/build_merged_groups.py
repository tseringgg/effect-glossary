#!/usr/bin/env python3
"""Display-only merged group pages. NEW FILES ONLY: build/merged_groups/ (meta.json, index.json) and build/merged_slugs_seen.json. Reads corrections/merged_groups.json (edited by hand; nothing here ever writes it).
Nothing is placed, and no group id, placement, count or figure changes: a page only SHOWS 2 to 8 groups together. The number a page shows is a display figure (a card in two members counted once); every group keeps
its own count, its own id and its own placements.

    python src/build_merged_groups.py        # seconds; run build_manual_layer.py first, then this, then build_group_search.py (the search reads this index)

MERGED_GROUPS = True builds the files; False writes nothing and removes this script's own outputs, so the page merges nothing and the build directory is exactly the build without this layer.

The file (corrections/merged_groups.json): {"v": 1, "pages": {"<slug>": {"name", "description", "members": [group ids], "aliases": [...], "member_notes": {id: note}, "basis", "created", "retired"}}}.
The FIRST member listed is the page's key and must be the highest in trust order (precise, tentative, tag, loose; then the largest); the other members' keys redirect to the page. A slug is chosen once and never reused:
retire a page with "retired": true (it stays in the file); deleting an entry is an error on the next build (build/merged_slugs_seen.json remembers every slug).
Errors (nothing is written): an unknown or not-offered group, a member that disappeared, a group in two pages, a layer other than leaf or community tag (version 1), fewer than 2 or more than 8 members, a first member that is not
the highest in trust, a duplicate or badly formed slug, a page name used twice or equal to the full name of a group that is not a member, an alias used by two pages, a removed slug. Warnings: a page name equal to the display
name of a group that is not a member, a member that is not the largest of its class, a description missing.
"""
import io
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as M
import build_group_search as B

MERGED_GROUPS = True
HERE = M.HERE
BUILD = os.path.join(HERE, "build")
OUTDIR = os.environ.get("MERGED_BUILD_OUT") or os.path.join(BUILD, "merged_groups")                 # the env overrides are for the tests only
FILE = os.environ.get("MERGED_FILE") or os.path.join(HERE, "corrections", "merged_groups.json")
LEDGER = os.environ.get("MERGED_LEDGER") or os.path.join(BUILD, "merged_slugs_seen.json")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$")
V1_LAYERS = ("leaf", "tag")
TRUST = {"leaf": 0, "kw": 0, "rp": 0, "tent": 1, "tag": 2, "loose": 3, "hand": 4}
MIN_MEMBERS, MAX_MEMBERS = 2, 8


def validate(doc, groups, mem, ledger):
    """-> (pages [dict], errors, warnings). pages holds only the active (not retired) pages, in slug order."""
    by = {e["gid"]: e for e in groups}
    errs, warns, pages = [], [], []
    if not isinstance(doc, dict) or not isinstance(doc.get("pages"), dict):
        return [], ["the file needs a 'pages' object"], []
    seen_slugs = set(doc["pages"])
    for s in sorted(set(ledger) - seen_slugs):
        errs.append("page %r was removed from the file; a slug is never reused: put it back and set \"retired\": true" % s)
    owner, names, terms, folded = {}, {}, {}, {}
    ex = lambda s: " ".join(str(s).lower().split())                      # exact text, not the search folding (which drops punctuation: "+1/+1" and "−1/−1" fold alike)
    full_names = {ex(e["full"]): e["gid"] for e in groups}
    disp_names = {ex(e["name"]): e["gid"] for e in groups}
    members_all = set()
    for slug, p in sorted(doc["pages"].items()):
        w = "page %r: " % slug
        if not SLUG.match(slug):
            errs.append(w + "the slug must match [a-z0-9][a-z0-9-]{2,40}")
            continue
        if not isinstance(p, dict):
            errs.append(w + "must be an object")
            continue
        ms = p.get("members")
        if not isinstance(ms, list) or not all(isinstance(x, str) for x in ms) or not MIN_MEMBERS <= len(ms) <= MAX_MEMBERS or len(set(ms)) != len(ms):
            errs.append(w + "needs %d to %d different member ids" % (MIN_MEMBERS, MAX_MEMBERS))
            continue
        bad = False
        for g in ms:
            layer = g.split(":", 1)[0]
            if g not in by:
                errs.append(w + "%s is not a group the page can open (unknown, not offered, retired, or it disappeared from the build)" % g)
                bad = True
            elif layer not in V1_LAYERS:
                errs.append(w + "%s is a %s group; version 1 merges leaf and community-tag (tag:) groups only" % (g, layer))
                bad = True
        if bad:
            continue
        name = p.get("name")
        if not isinstance(name, str) or not name.strip():
            errs.append(w + "needs a name")
            continue
        if not p.get("retired"):
            for g in ms:
                if g in owner:
                    errs.append(w + "%s is already in page %r (a group is in at most one page)" % (g, owner[g]))
                owner.setdefault(g, slug)
            members_all.update(ms)
        trust = [TRUST[g.split(":", 1)[0]] for g in ms]
        if trust[0] != min(trust):
            errs.append(w + "the first member (the page's key) must be the highest in trust order (precise, tentative, tag, loose); %s is not" % ms[0])
        best = max((by[g]["size"] for g in ms if TRUST[g.split(":", 1)[0]] == trust[0]))
        if by[ms[0]]["size"] != best:
            warns.append(w + "the first member is not the largest of its class")
        if not str(p.get("description") or "").strip():
            warns.append(w + "has no description")
        elif len(str(p["description"])) > 200:
            errs.append(w + "the description is over 200 characters (the limit every group description follows)")
        nk = ex(name)
        if nk in names:
            errs.append(w + "the name %r is also the name of page %r" % (name, names[nk]))
        names[nk] = slug
        if not p.get("retired"):
            if nk in full_names and full_names[nk] not in ms:
                errs.append(w + "the name %r is the full name of the group %s, which is not a member" % (name, full_names[nk]))
            elif nk in disp_names and disp_names[nk] not in ms:
                warns.append(w + "the name %r is also the displayed name of the group %s, which is not a member" % (name, disp_names[nk]))
            for t in [name] + list(p.get("aliases") or []):
                k, e = B.norm(t), ex(t)
                if not k:
                    errs.append(w + "an alias is empty after folding")
                elif e in terms and terms[e] != slug:
                    errs.append(w + "the term %r is also used by page %r" % (t, terms[e]))
                elif k in folded and folded[k][0] != slug and folded[k][1] != e:
                    warns.append(w + "the term %r folds like %r of page %r in the search (the search drops signs such as + and −)" % (t, folded[k][1], folded[k][0]))
                terms.setdefault(e, slug)
                folded.setdefault(k, (slug, e))
        mn = p.get("member_notes") or {}
        if not isinstance(mn, dict) or any(g not in ms or not isinstance(v, str) for g, v in mn.items()):
            errs.append(w + "member_notes must map a member id to a text")
        if p.get("retired"):
            continue
        un = set().union(*[mem[g] for g in ms])
        pages.append({"slug": slug, "name": name.strip(), "description": str(p.get("description") or "").strip(), "aliases": [a for a in (p.get("aliases") or []) if isinstance(a, str)],
                      "basis": str(p.get("basis") or ""), "key": B.page_key(ms[0]), "union": len(un), "in_two_members": sum(1 for o in un if sum(1 for g in ms if o in mem[g]) > 1),
                      "members": [{"gid": g, "key": B.page_key(g), "layer": g.split(":", 1)[0], "name": by[g]["name"], "full": by[g]["full"], "size": by[g]["size"], "note": str(mn.get(g) or "")} for g in ms]})
    return pages, errs, warns


def main(force=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    on = MERGED_GROUPS if force is None else force
    if not on or not os.path.exists(os.path.join(BUILD, "manual_index.json")):
        if not os.environ.get("MERGED_BUILD_OUT") and os.path.isdir(OUTDIR):
            shutil.rmtree(OUTDIR)
        print("MERGED_GROUPS is off (or build/manual_index.json is missing): nothing written")
        return 0
    if not os.path.exists(FILE):
        if not os.environ.get("MERGED_BUILD_OUT") and os.path.isdir(OUTDIR):
            shutil.rmtree(OUTDIR)
        print("no corrections/merged_groups.json: nothing merged")
        return 0
    groups = [e for e in B.load_groups() if e["layer"] != "yk"]
    mem = B.group_members(groups)
    doc = json.load(io.open(FILE, encoding="utf-8"))
    ledger = json.load(io.open(LEDGER, encoding="utf-8")) if os.path.exists(LEDGER) else []
    pages, errs, warns = validate(doc, groups, {e["gid"]: mem.get(e["gid"], set()) for e in groups}, ledger)
    if errs:
        for m in errs:
            print("ERROR", m)
        print("merged pages NOT built: %d error(s)" % len(errs))
        return 1
    redirects = {m["key"]: p["slug"] for p in pages for m in p["members"]}
    by_gid = {m["gid"]: p["slug"] for p in pages for m in p["members"]}
    index = {"v": 1, "pages": pages, "redirects": redirects, "by_gid": by_gid}
    meta = {"v": 1, "enabled": True, "pages": len(pages), "groups": len(by_gid), "union_total": sum(p["union"] for p in pages)}
    B.dump(os.path.join(OUTDIR, "index.json"), index)
    B.dump(os.path.join(OUTDIR, "meta.json"), meta)
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with io.open(LEDGER, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(sorted(set(ledger) | set(doc["pages"])), indent=0))
    print("merged pages built: %d pages, %d groups, %d warnings" % (len(pages), len(by_gid), len(warns)))
    for w in warns:
        print("warning", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
