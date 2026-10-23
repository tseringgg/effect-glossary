#!/usr/bin/env python3
"""Tests for the display-only merged group pages that need no browser:  python src/test_merged_groups.py     (needs `pip install dukpy` and the build files)

Independent of the generator: every error the build must raise, on temporary files; the union of a page re-derived from the SOURCE files (the members file, the tag file) and compared with the build's; the layout rule
(a card shown once, in the highest-trust section) run by reports/mergepage.js in a JS engine against a separate Python version, on random sections and on the real pages; two builds byte-identical; the flag off (every
other file byte-identical, the outputs removed); no group id, count or placement file moved (the build files the six figures come from are hashed before and after); the search index (a merged page in place of its members,
aliases that pointed at a member now pointing at the page); the protected corrections files hashed before and after (this test writes only to temporary copies). NOT independent: the choice of pages (mine and yours).
"""
import hashlib
import io
import json
import os
import random
import subprocess
import sys
import tempfile

import dukpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as M
import build_merged_groups as BM
import build_group_search as B

HERE = M.HERE
BUILD = os.path.join(HERE, "build")
CORR = os.path.join(HERE, "corrections")
PROTECTED = [os.path.join(CORR, n) for n in ("manual_placements.json", "manual_placements.json.bak", "hand_groups.json", "hand_groups.json.bak", "group_aliases.json", "group_descriptions.json", "group_aliases_drafted.json", "merged_groups.json")]
FIGURE_FILES = ["manual_index.json", "ability_taxonomy.json", "tentative_placements.json", "tag_placements.json", "loose_groups.json", "annotation_placements.json", "ability_taxonomy_members.json", "hand_group_hits.json"]
RESULTS = []


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)[:300]) if detail else ""))


def jl(n):
    with io.open(os.path.join(BUILD, n), encoding="utf-8") as fh:
        return json.load(fh)


def ref_layout(sections):
    """The rule in the header of reports/mergepage.js, written again."""
    where, also, out, union = {}, {}, [], 0
    for gid, oids, removed in sections:
        seen, show, hidden = set(), [], 0
        for o in oids:
            if o in seen:
                continue
            seen.add(o)
            if o in removed:
                show.append(o)
            elif o in where:
                hidden += 1
                also.setdefault(o, []).append(gid)
            else:
                where[o] = gid
                union += 1
                show.append(o)
        out.append((gid, show, hidden))
    return out, also, where, union


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    before = [sha(p) for p in PROTECTED]
    figs_before = {n: sha(os.path.join(BUILD, n)) for n in FIGURE_FILES}
    if not os.path.exists(os.path.join(BUILD, "merged_groups", "index.json")):
        print("build the merged pages first: python src/build_merged_groups.py")
        return 1
    idx = jl(os.path.join("merged_groups", "index.json"))
    doc = json.load(io.open(os.path.join(CORR, "merged_groups.json"), encoding="utf-8"))
    groups = [e for e in B.load_groups() if e["layer"] != "yk"]
    by = {e["gid"]: e for e in groups}
    mem = B.group_members(groups)
    mem = {g: mem.get(g, set()) for g in by}

    # ---------------------------------------------------------------- 1. the seeded file, the builds, the flag
    ledger_dir = tempfile.mkdtemp(prefix="mg_led_")
    t1, t2 = tempfile.mkdtemp(prefix="mg_a_"), tempfile.mkdtemp(prefix="mg_b_")
    for t in (t1, t2):
        r = subprocess.run([sys.executable, os.path.join(HERE, "src", "build_merged_groups.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                           env=dict(os.environ, MERGED_BUILD_OUT=t, MERGED_LEDGER=os.path.join(ledger_dir, "led.json")))
        assert r.returncode == 0, r.stdout + r.stderr
    same = sorted(os.listdir(t1)) == sorted(os.listdir(t2)) and all(sha(os.path.join(t1, n)) == sha(os.path.join(t2, n)) for n in os.listdir(t1))
    check("1 the file validates (%d pages, %d groups) and two builds into separate folders are byte-identical (%s)" % (len(idx["pages"]), len(idx["by_gid"]), ", ".join(sorted(os.listdir(t1)))), same)
    check("1 and equal to the build the page reads", all(sha(os.path.join(t1, n)) == sha(os.path.join(BUILD, "merged_groups", n)) for n in os.listdir(t1)))
    own = ("build/merged_groups/", "build/merged_slugs_seen.json", "build/group_search/", "reports/group-search.md", "build/group_search_log")
    def tree():
        h = {}
        for root, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for f in files:
                p = os.path.join(root, f)
                rel = os.path.relpath(p, HERE).replace("\\", "/")
                if not any(rel.startswith(s) for s in own):
                    h[rel] = sha(p)
        return h
    h0 = tree()
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); import build_merged_groups as B; B.main(force=False)"], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    h1 = tree()
    check("1 flag off: %d files outside the feature's own outputs are byte-identical and build/merged_groups/ is removed" % len(h0), h0 == h1 and not os.path.exists(os.path.join(BUILD, "merged_groups")) and r.returncode == 0, [k for k in h0 if h0[k] != h1.get(k)][:3])
    r = subprocess.run([sys.executable, os.path.join(HERE, "src", "build_merged_groups.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    check("1 flag on again: rebuilt identical to the first build", r.returncode == 0 and all(sha(os.path.join(t1, n)) == sha(os.path.join(BUILD, "merged_groups", n)) for n in os.listdir(t1)))

    # ---------------------------------------------------------------- 2. every error the build must raise (temporary files; the real file is never written)
    mt = tempfile.mkdtemp(prefix="mg_bad_")
    leafs = [e["gid"] for e in groups if e["layer"] == "leaf" and e["size"] >= 8][:30]
    tags = [e["gid"] for e in groups if e["layer"] == "tag"][:6]
    tent = next(e["gid"] for e in groups if e["layer"] == "tent")
    kw = next(e["gid"] for e in groups if e["layer"] == "kw")
    hand = next(e["gid"] for e in groups if e["layer"] == "hand")
    loose = next(e["gid"] for e in groups if e["layer"] == "loose")
    rp = next(e["gid"] for e in groups if e["layer"] == "rp")

    def pg(name, members, **kw_):
        d = {"name": name, "description": "d", "members": members, "aliases": [], "created": "2026-10-22", "retired": False}
        d.update(kw_)
        return d

    def errs_for(pages, ledger=()):
        pages_, errs, warns = BM.validate({"v": 1, "pages": pages}, groups, mem, list(ledger))
        return errs
    ok = errs_for({"fine-page": pg("Fine page", leafs[:2])})
    check("2 a good page has no error", not ok, ok)
    cases = {
        "an unknown group": ({"p-unknown": pg("Unknown", [leafs[0], "leaf:nope000000"])}, "not a group the page can open"),
        "a group in two pages": ({"p-one": pg("One page", leafs[:2]), "p-two": pg("Two page", [leafs[2], leafs[1]])}, "already in page"),
        "a tentative group (version 1)": ({"p-tent": pg("Tentative page", [leafs[0], tent])}, "version 1 merges leaf and community-tag"),
        "a keyword block": ({"p-kw": pg("Keyword page", [leafs[0], kw])}, "version 1 merges"),
        "a replacement block": ({"p-rp": pg("Replacement page", [leafs[0], rp])}, "version 1 merges"),
        "a hand-defined group": ({"p-hand": pg("Hand page", [leafs[0], hand])}, "version 1 merges"),
        "a loose group": ({"p-loose": pg("Loose page", [leafs[0], loose])}, "version 1 merges"),
        "a keyword filter": ({"p-yk": pg("Filter page", [leafs[0], "yk:Flying"])}, "not a group the page can open"),
        "one member": ({"p-solo": pg("Solo page", [leafs[0]])}, "different member ids"),
        "nine members": ({"p-nine": pg("Nine page", leafs[:9])}, "different member ids"),
        "the same member twice": ({"p-dup": pg("Dup page", [leafs[0], leafs[0]])}, "different member ids"),
        "a tag group first and a leaf second": ({"p-trust": pg("Trust page", [tags[0], leafs[0]])}, "highest in trust order"),
        "a bad slug": ({"Bad_Slug": pg("Bad slug page", leafs[:2])}, "slug must match"),
        "a page name used twice": ({"p-a": pg("Same name", leafs[:2]), "p-b": pg("same  NAME", leafs[2:4])}, "is also the name of page"),
        "a name equal to a group that is not a member": ({"p-full": pg(by[leafs[5]]["full"], leafs[:2])}, "full name of the group"),
        "an alias used by two pages": ({"p-c": pg("Cee page", leafs[:2], aliases=["shared term"]), "p-d": pg("Dee page", leafs[2:4], aliases=["Shared Term"])}, "also used by page"),
        "a member note for a group that is not a member": ({"p-note": pg("Note page", leafs[:2], member_notes={leafs[7]: "x"})}, "member_notes"),
    }
    for nm, (pages, want) in cases.items():
        e = errs_for(pages)
        check("2 error: %s" % nm, any(want in x for x in e), e[:2])
    e = errs_for({"p-keep": pg("Keep page", leafs[:2])}, ledger=["p-keep", "p-gone"])
    check("2 error: a slug removed from the file (a slug is never reused)", any("p-gone" in x and "never reused" in x for x in e), e)
    e = errs_for({"p-ret": pg("Retired", leafs[:2], retired=True), "p-new": pg("New page", leafs[:2])})
    check("2 a retired page frees its members (a tombstone, not a clash)", not e, e)
    # a build with a bad file exits non-zero and writes nothing (also for a proposal that includes another layer)
    bad = os.path.join(mt, "merged_groups.json")
    json.dump({"v": 1, "pages": {"p-tent": pg("Tentative page", [leafs[0], tent])}}, open(bad, "w"))
    out = tempfile.mkdtemp(prefix="mg_badout_")
    r = subprocess.run([sys.executable, os.path.join(HERE, "src", "build_merged_groups.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, MERGED_FILE=bad, MERGED_BUILD_OUT=out, MERGED_LEDGER=os.path.join(mt, "led.json")))
    check("2 a file that includes a tentative group fails the build (exit 1, an ERROR line, no index, no ledger written)", r.returncode == 1 and "ERROR" in r.stdout and not os.path.exists(os.path.join(out, "index.json")) and not os.path.exists(os.path.join(mt, "led.json")), r.stdout[-200:])
    # the warnings (a name equal to a displayed name; fold-alike terms) are warnings, not errors
    pages_, errs, warns = BM.validate(doc, groups, mem, [])
    check("2 the real file: no error, %d warnings (names equal to the displayed name of a tentative or loose twin, and the +N/+N and −N/−N pages that fold alike in the search)" % len(warns), not errs and len(pages_) == 13, errs[:2])

    # ---------------------------------------------------------------- 3. reconciliation: the build against the source files
    members_leaf = jl("ability_taxonomy_members.json")["leaves"]
    tagf = jl("tag_placements.json")["groups"]
    mi = jl("manual_index.json")
    bad = []
    for p in idx["pages"]:
        sets = []
        for m in p["members"]:
            kind, _, i = m["gid"].partition(":")
            s = {x[0] for x in members_leaf[i]} if kind == "leaf" else set(tagf[i]["m"])
            sets.append(s)
            if len(s) != m["size"] or mi["groups"][m["gid"]][1] != m["size"] or not mi["groups"][m["gid"]][4]:
                bad.append((p["slug"], m["gid"], "size/offered"))
        un = set().union(*sets)
        two = sum(1 for o in un if sum(1 for s in sets if o in s) > 1)
        if len(un) != p["union"] or two != p["in_two_members"]:
            bad.append((p["slug"], "union", len(un), p["union"]))
        if [m["gid"] for m in p["members"]] != doc["pages"][p["slug"]]["members"] or p["key"] != B.page_key(doc["pages"][p["slug"]]["members"][0]):
            bad.append((p["slug"], "members/key"))
    check("3 for all %d pages the union, the cards in two members, each member's size and the page key are re-derived from the members and tag files: %d differences" % (len(idx["pages"]), len(bad)), not bad, bad[:3])
    two_page = [(p["slug"], p["in_two_members"]) for p in idx["pages"] if p["in_two_members"]]
    check("3 cards that sit in two members exist and are counted once: %s" % two_page, any(n > 0 for _, n in two_page) and sum(p["union"] for p in idx["pages"]) < sum(m["size"] for p in idx["pages"] for m in p["members"]))
    ids_seen = [m["gid"] for p in idx["pages"] for m in p["members"]]
    check("3 no group is in two pages (%d member ids, all different) and every redirect key maps to its page" % len(ids_seen), len(ids_seen) == len(set(ids_seen)) and all(idx["redirects"][m["key"]] == p["slug"] for p in idx["pages"] for m in p["members"]))
    figs_after = {n: sha(os.path.join(BUILD, n)) for n in FIGURE_FILES}
    check("3 no group id, count or placement file moved: the %d build files the six figures and the hand counts come from are byte-identical before and after the builds in this test" % len(FIGURE_FILES), figs_before == figs_after, [n for n in FIGURE_FILES if figs_before[n] != figs_after[n]])

    # ---------------------------------------------------------------- 4. the layout rule: reports/mergepage.js against the Python version
    itp = dukpy.JSInterpreter()
    itp.evaljs(io.open(os.path.join(HERE, "reports", "mergepage.js"), encoding="utf-8").read())
    rnd = random.Random(20263601)
    bad = []
    for t in range(400):
        pool = ["c%d" % i for i in range(rnd.randint(3, 25))]
        secs = []
        for s in range(rnd.randint(1, 4)):
            oids = [rnd.choice(pool) for _ in range(rnd.randint(0, 20))]
            secs.append(("g%d" % s, oids, set(rnd.sample(oids, min(len(oids), rnd.randint(0, 3))))))
        js = json.loads(itp.evaljs("JSON.stringify(MergePage.layout(%s))" % json.dumps([{"gid": g, "oids": o, "removed": {x: 1 for x in r}} for g, o, r in secs])))
        out, also, where, union = ref_layout(secs)
        got = ([(s["gid"], s["show"], s["hidden"]) for s in js["sections"]], js["also"], js["where"], js["union"])
        if got != (out, also, where, union):
            bad.append(t)
    check("4 reports/mergepage.js equals the Python layout on 400 random section sets (duplicates inside a section, hand removals)", not bad, bad[:3])
    bad = []
    for p in idx["pages"]:
        secs = []
        for m in p["members"]:
            kind, _, i = m["gid"].partition(":")
            oids = [x[0] for x in members_leaf[i]] if kind == "leaf" else list(tagf[i]["m"])
            secs.append((m["gid"], oids, set()))
        js = json.loads(itp.evaljs("JSON.stringify(MergePage.layout(%s))" % json.dumps([{"gid": g, "oids": o, "removed": {}} for g, o, r in secs])))
        out, also, where, union = ref_layout(secs)
        shown = [o for s in js["sections"] for o in s["show"]]
        if js["union"] != union or union != p["union"] or len(shown) != len(set(shown)) or [(s["gid"], s["show"], s["hidden"]) for s in js["sections"]] != out:
            bad.append(p["slug"])
        # a card in two members is shown in the FIRST of them (highest trust, then the larger group) and the later section counts it as hidden
        for o, gs in also.items():
            if js["where"][o] != secs[0][0] and not any(o in s[1] for s in secs[:1]) and js["where"][o] == gs[0]:
                bad.append((p["slug"], o))
    check("4 on the %d real pages the card is shown exactly once, the page's union equals the build's, and the hidden counts add up (sum of shown = union)" % len(idx["pages"]), not bad, bad[:3])

    # ---------------------------------------------------------------- 5. the search index
    sx = jl(os.path.join("group_search", "index.json"))
    rows = {r[0]: r for r in sx["groups"]}
    member_ids = set(idx["by_gid"])
    check("5 the search index has no row for any of the %d member groups and one row for each of the %d pages" % (len(member_ids), len(idx["pages"])), not (member_ids & set(rows)) and all("page:" + p["slug"] in rows for p in idx["pages"]))
    pr = [rows["page:" + p["slug"]] for p in idx["pages"]]
    check("5 a page row: layer m, the page's key (its first member's), the union as its size, its own description, the members' names as other names, the member ids", all(r[4] == "m" and r[1] == p["key"] and r[5] == p["union"] and r[7] == p["description"] and r[8] == 0 and len(r) == 13 and r[12] == [m["gid"] for m in p["members"]] and
          set(m["full"] for m in p["members"]) <= set(r[11]) for r, p in zip(pr, idx["pages"])))
    others = [r for g, r in rows.items() if not g.startswith("page:")]
    check("5 every other row still has its 11 columns (nothing else about the index changed)", all(len(r) == 11 for r in others))
    stale = [(k, v["g"]) for k, v in sx["aliases"].items() if set(v["g"]) & member_ids]
    check("5 no alias points at a member any more: %d alias keys now point at a page (e.g. 'counterspell' -> %s)" % (sum(1 for v in sx["aliases"].values() if any(g.startswith("page:") for g in v["g"])), sx["aliases"]["counterspell"]["g"]), not stale and "page:counter-a-spell" in sx["aliases"]["counterspell"]["g"], stale[:2])
    check("5 an alias whose list held two members of one page lists the page once", all(len(v["g"]) == len(set(v["g"])) for v in sx["aliases"].values()))
    rep = io.open(os.path.join(HERE, "reports", "group-search.md"), encoding="utf-8").read()
    check("5 the build report names the merged pages, the aliases moved to a page and the member descriptions the page's own description shadows", "## Merged pages: 13" in rep and "shadowed" in rep and "now point at its page" in rep)

    # ---------------------------------------------------------------- 6. nothing protected moved
    after = [sha(p) for p in PROTECTED]
    check("6 the protected corrections files (and the alias, description and merge files) are byte-identical before and after", before == after)
    bad = [n for n, ok in RESULTS if not ok]
    print("\n%d checks, %d failed" % (len(RESULTS), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
