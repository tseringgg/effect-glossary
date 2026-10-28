#!/usr/bin/env python3
"""Verify the four newer tester features, each behind a flag in reports/config.js: TYPE_GROUPS (type and subtype pages), NARROW_NO_CUT (the "Narrow by group" row without the 3-card cut), COLOUR_MODES
(Any / Includes all / Only these / Not these) and FLIP_FACES (a flip control, either face searchable). Headless Edge over the DevTools protocol on exported dist folders served by a plain static server (GET only).

    python src/test_tester_features.py [--skip-perf] [--reads OUT.json]

Run src/test_tester_static.py and src/test_tester_filters.py as well: they now export with the four flags OFF and test the page as it was (their checks are unchanged).

What is checked, and what is independent of the page's own code:
  * the data files (src/build_type_groups.py): built twice, same bytes; every type page's members re-derived from the Scryfall oracle file (a different source and parser from the MTGJSON file the build reads);
  * exports: with the flags on, twice, byte-identical; with the flags off, the same file list as before the features and every file but tester.js, testerfilters.js, config.js and the manifest byte-identical to the
    manifest saved in src/testdata/before_features/; and the flags-off page, run beside the pre-feature scripts (saved there), draws the same DOM and makes the same requests after the same steps;
  * type pages: 30 pages drawn with seed %(SEED_T)d, fixed before anything is computed; bar: more than 3 wrong cards among a page's first 20 fails (a "wrong card" is one the Scryfall type lines do not give the page's word);
  * narrowing: chips and counts against src/tester_filters_ref.py (a Python re-implementation); 30 narrowed lists drawn with seed %(SEED_N)d; bar: more than 5 of 30 not sensible fails (sensible is mechanical:
    the result is exactly page AND chip, it has 2 or more cards and under 90%% of the list, and the chip is not a name-twin of the page). My own reading of those 30 lists is NOT independent (--reads writes them);
  * colour modes: 10 selections x 4 modes over all 33,183 cards against counts worked out before the build (scratchpad col1.py) and against a Python set implementation;
  * flip: a transform, a modal and an adventure card; both faces' name, cost, type and text against the MTGJSON text; the picture URL (front/back);
  * 390 px, no failed request, no console error, nothing sent; first-load size and time at 1x and 4x CPU, flags off against flags on.
Clicks are DOM click() calls and the search box is typed with key events: no touch, no other browser. Protected files (corrections/ incl. backups, archive/, the shared JS, serve.py, top-level build files) are
hashed before and after; nothing here writes to them. Exports go to dist.feat/, dist.feat2/, dist.off/, dist.old/, which are removed; dist/ is left as the flags-on export at the end.
"""
import gzip
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_tester_static as T            # noqa: E402
import tester_filters_ref as REF          # noqa: E402

check = T.check
SEED_T, SEED_N, SEED_S = 20263401, 20263402, 20263403          # fixed here, before any list is computed
__doc__ = __doc__ % {"SEED_T": SEED_T, "SEED_N": SEED_N}
BEFORE = os.path.join(HERE, "src", "testdata", "before_features")
READY = ("document.body.classList.contains('tester') && typeof HG !== 'undefined' && !!HG && !!SIB && !!SC && !!MI && !!CARDS && !!UNORG && !!LOOSE && !!TENT && !!TAGS && !!ANN && GSON === true && PINON === true && !!MERGED"
         " && typeof TF !== 'undefined'")
NL = "String.fromCharCode(10)"
DIRS = {k: os.path.join(HERE, "dist." + k) for k in ("feat", "feat2", "off", "offp", "old")}
ST_TWO = {"transform", "modal_dfc", "adventure", "split", "flip", "prepare"}
# colour-mode counts over all 33,183 cards, worked out before the build by a separate script (Part 1 of the work): selection -> (any, all, only, not)
COLOUR_TABLE = {"W+U": (13177, 704, 10218, 20006), "C": (4121, 4121, 4121, 29062), "M": (4575, 4575, 4575, 28608), "W": (7020, 7020, 5002, 26163), "W+M": (9577, 2018, 0, 23606),
                "C+W": (11141, 0, 9123, 22042), "G+R": (13111, 652, 10141, 20072), "W+U+B": (18921, 145, 15951, 14262), "U+B+R": (18848, 159, 15923, 14335), "W+U+B+R+G": (29062, 59, 29062, 4121)}


def jx(c, expr):
    return json.loads(c.js("JSON.stringify(" + expr + ")"))


def wait_page(c, key, secs=90):
    c.js("show(%s)" % json.dumps(key))
    return c.wait("!document.getElementById('panel').classList.contains('tpend') && !!document.querySelector('#list [data-oid]') && !!document.getElementById('fwrap') && TF.full().length > 0", secs)


def wait_plain(c, key, secs=90):
    c.js("show(%s)" % json.dumps(key))
    return c.wait("selected===%s && !document.getElementById('panel').classList.contains('tpend') && (!!document.querySelector('#list [data-oid]') || !!document.querySelector('.explain'))" % json.dumps(key), secs)


def boot(root, width=1280, **kw):
    s = T.Session(root, "/reports/browse.html", width, **kw)
    ok = s.c.wait(READY, 300)
    s.c.pump(1.5)
    return s, ok


def cleanup():
    for d in DIRS.values():
        shutil.rmtree(d, ignore_errors=True)


def export_to(out, config=None, features=True):
    cmd = [sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--out", os.path.relpath(out, HERE)] + (["--config", config] if config else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    return r.returncode, r.stdout + r.stderr


ABILITY_FLAGS = ("ABILITY_TYPE_PAGES", "ABILITY_TYPE_FILTERS")      # the ability-type pages and filters (src/test_ability_pages.py tests them); this file tests the page without them, as it was


def ability_off_config():
    """reports/config.js as it is, with only the two ability-type flags switched off (the 'flags on' arm of this file: its own flags on, the later ones off)."""
    import tempfile
    txt = open(os.path.join(HERE, "reports", "config.js"), encoding="utf-8").read()
    for f in ABILITY_FLAGS:
        txt = re.sub(r"\b%s\s*:\s*true" % f, "%s: false" % f, txt)
    t = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8"); t.write(txt); t.close()
    return t.name


def files_of(root):
    return {os.path.relpath(p, root).replace("\\", "/"): T.sha(p) for p in T.walk(root)}


# ---------------------------------------------------------------- the independent source for type membership: Scryfall's oracle file (the build reads MTGJSON)
SCRY_FACES = {}                                                # oracle id -> the two faces as Scryfall has them (name, mana cost, type line, text)


def scryfall_membership(cards):
    path = os.path.join(HERE, "data", "scryfall-oracle-cards.jsonl.gz")
    if not os.path.exists(path):
        return None
    faces_of = {}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            oid = r["oracle_id"]
            if oid in cards:
                fs = r.get("card_faces") if r.get("layout") in ST_TWO and r.get("card_faces") else None
                faces_of[oid] = [(f.get("name", ""), f.get("type_line", "")) for f in fs] if fs else [(r["name"], r["type_line"])]
                if fs and len(fs) == 2:
                    SCRY_FACES[oid] = [(f.get("name", ""), f.get("mana_cost", ""), f.get("type_line", ""), f.get("oracle_text", "")) for f in fs]
    info = {}
    for oid, fs in faces_of.items():
        n = cards[oid]["n"].lower()
        pf = next((i for i, f in enumerate(fs) if f[0].lower() == n), 0)
        per = []
        for name, tl in fs:
            left, _, right = tl.partition(" \u2014 ")
            lw = set(left.split())
            per.append((lw, " " + right + " "))
        info[oid] = (per, pf)
    return info


def expected_members(info, kind, word):
    """(all, via_other_face_only) for one page word, from Scryfall's type lines."""
    allm, via = set(), set()
    for oid, (per, pf) in info.items():
        hit = [(word in lw) if kind in "ts" else ((" " + word + " ") in right) for lw, right in per]
        if any(hit):
            allm.add(oid)
            if not hit[pf]:
                via.add(oid)
    return allm, via


def main():
    skip_perf = "--skip-perf" in sys.argv
    reads_out = sys.argv[sys.argv.index("--reads") + 1] if "--reads" in sys.argv else os.path.join(tempfile.gettempdir(), "features_narrow30_reads.json")
    before = T.protected()
    cleanup()
    cards = json.load(open(os.path.join(HERE, "build", "ability_taxonomy_cards.json"), encoding="utf-8"))["cards"]
    # ------------------------------------------------------------ 1. data files
    r1 = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "build_type_groups.py")], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    check("build_type_groups.py runs", r1.returncode == 0, r1.stdout + r1.stderr)
    h1 = {p: T.sha(os.path.join(HERE, "build", *p.split("/"))) for p in ("type_groups/index.json", "type_groups/members.json", "faces/faces.json")}
    r2 = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "build_type_groups.py"), "--check"], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    check("the three data files are reproducible: a second build gives the same bytes %s" % {k: v[:8] for k, v in h1.items()}, r2.returncode == 0, r2.stdout + r2.stderr)
    tg = json.load(open(os.path.join(HERE, "build", "type_groups", "index.json"), encoding="utf-8"))
    mem = json.load(open(os.path.join(HERE, "build", "type_groups", "members.json"), encoding="utf-8"))
    groups = {g[0]: g for g in tg["groups"]}
    check("%d type pages: 11 types, 4 supertypes, %d subtypes; each has 5 or more cards" % (len(groups), len([g for g in groups.values() if g[2] == "u"])), len(groups) == 321 and all(g[4] >= 5 for g in groups.values()) and sum(1 for g in groups.values() if g[2] == "t") == 11)
    check("keys are the word itself (stable): ty:t.creature, ty:s.legendary, ty:u.saga exist; no two words share a key", {"ty:t.creature", "ty:s.legendary", "ty:u.saga"} <= set(groups) and len(groups) == len({g[1:3].__repr__() for g in groups.values()}))
    info = scryfall_membership(cards)
    order = list(cards)
    if info is None:
        check("independent source (data/scryfall-oracle-cards.jsonl.gz) is present", False, "gitignored file missing: type membership could not be checked independently")
    else:
        bad, via_bad = [], []
        for key, g in groups.items():
            allm, via = expected_members(info, g[2], g[1])
            got = {order[i] for i in mem["m"][key]} & info.keys()                  # the 15 newest cards are not in Scryfall's oracle file: they cannot be compared
            gv = {order[i] for i in mem["o"].get(key, [])} & info.keys()
            if got != allm:
                bad.append((g[1], len(got), len(allm), sorted(cards[o]["n"] for o in (got ^ allm))[:3]))
            if gv != via:
                via_bad.append((g[1], len(gv), len(via)))
        check("all %d pages: exact membership equals the Scryfall type lines (any face)" % len(groups), len(bad) <= 3, bad[:6])
        check("all %d pages: 'via other face' sets equal the Scryfall derivation" % len(groups), len(via_bad) <= 3, via_bad[:6])
        T.NOTES.append("type membership vs Scryfall, over the %d cards both files have: %d of %d pages differ (%s); via-other-face: %d differ (%s)" % (len(info), len(bad), len(groups), bad[:4], len(via_bad), via_bad[:4]))
    check("members.json and index.json carry the same card-list checksum; every index is in range", mem["sig"] == tg["sig"] and all(max(v) < len(order) for v in mem["m"].values()))
    fc = json.load(open(os.path.join(HERE, "build", "faces", "faces.json"), encoding="utf-8"))
    check("faces.json: 861 two-faced cards, two faces each, sig matches", len(fc["cards"]) == 861 and all(len(v["f"]) == 2 for v in fc["cards"].values()) and fc["sig"] == tg["sig"], len(fc["cards"]))

    # ------------------------------------------------------------ 2. exports
    ab_off = ability_off_config()
    rc, out = export_to(DIRS["feat"], ab_off)
    check("export (flags on) succeeds", rc == 0, out[-300:])
    rc2, out2 = export_to(DIRS["feat2"], ab_off)
    check("export (flags on), again, succeeds", rc2 == 0, out2[-300:])
    a, b = files_of(DIRS["feat"]), files_of(DIRS["feat2"])
    check("two flags-on exports: every file byte-identical (%d files)" % len(a), a == b, [k for k in set(a) | set(b) if a.get(k) != b.get(k)][:4])
    shutil.rmtree(DIRS["feat2"])
    off_cfg = T.flags_off_config()
    rc3, out3 = export_to(DIRS["off"], off_cfg)
    check("export (flags off) succeeds", rc3 == 0, out3[-300:])
    base = {f["path"]: f["sha256"] for f in json.load(open(os.path.join(BEFORE, "dist_manifest_before.json"), encoding="utf-8"))["files"]}
    offf = files_of(DIRS["off"])
    base_all = dict(base); base_all["manifest.json"] = None
    check("flags off: the file list is exactly the one before the features (%d files)" % len(offf), set(offf) == set(base_all), sorted(set(offf) ^ set(base_all))[:5])
    differ = sorted(k for k in base if offf.get(k) != base[k])
    check("flags off: every file is byte-identical to the pre-feature export except tester.js, testerfilters.js and config.js %s" % differ, differ == ["reports/config.js", "reports/tester.js", "reports/testerfilters.js"], differ)
    new = sorted(set(a) - set(offf))
    exp_new = ["build/faces/faces.json", "build/type_groups/index.json", "build/type_groups/members.json", "reports/flipfaces.css", "reports/flipfaces.js", "reports/typegroups.css", "reports/typegroups.js"]
    check("flags on adds exactly the 7 whitelisted files %s" % new, new == exp_new, new)
    other = sorted(k for k in offf if k in a and offf[k] != a[k] and k != "manifest.json")
    check("flags on, against flags off, changes no existing file but config.js %s (the scripts are the same files)" % other, other == ["reports/config.js"], other)
    rcc = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--check", "--config", ab_off, "--out", os.path.relpath(DIRS["feat"], HERE)], capture_output=True, text=True, cwd=HERE)
    check("export_static.py --check passes on the flags-on export", rcc.returncode == 0, rcc.stdout + rcc.stderr)
    blob = " ".join(open(os.path.join(DIRS["feat"], "reports", n), encoding="utf-8").read() for n in ("typegroups.js", "flipfaces.js"))
    check("the new page files name no private path (corrections, backups, archive, manual_placements, /api/)", not re.search(r"corrections|backups|archive|manual_placements|/api/", blob))
    T.NOTES.append("flags-on adds %s" % new)
    # six figures in the flags-on data
    t = json.load(open(os.path.join(DIRS["feat"], "build", "ability_taxonomy.json"), encoding="utf-8"))["totals"]
    ten = json.load(open(os.path.join(DIRS["feat"], "build", "tentative_placements.json"), encoding="utf-8"))["meta"]["headline"]
    ann = json.load(open(os.path.join(DIRS["feat"], "build", "annotation_placements.json"), encoding="utf-8"))["meta"]["headline"]
    tag = json.load(open(os.path.join(DIRS["feat"], "build", "tag_placements.json"), encoding="utf-8"))["meta"]["headline"]
    got = [t["headline"]["pct"], t["with_broad"]["pct"], ten["with_tentative"][1], ann["with_annotation"][1], ann["with_gap_stratum"][1], tag["with_tag"][1]]
    check("the six figures are unchanged %s" % got, got == T.FIGURES)

    # ------------------------------------------------------------ 3. flags off: the page the same as before (current scripts vs the saved pre-feature scripts)
    # the pre-feature scripts predate the three popularity flags too, so both pages in this comparison run with those off (same config.js in both: only tester.js and testerfilters.js differ)
    shutil.copytree(DIRS["off"], DIRS["old"])
    shutil.copytree(DIRS["off"], DIRS["offp"])
    for n in ("tester.js", "testerfilters.js"):
        shutil.copyfile(os.path.join(BEFORE, n), os.path.join(DIRS["old"], "reports", n))
    for root in (DIRS["old"], DIRS["offp"]):
        with open(os.path.join(root, "reports", "config.js"), "w", encoding="utf-8", newline="") as fh:
            fh.write(T.flags_off_text(extra_off=("DEFAULT_POPULARITY", "ACTIVE_GROUP_HIGHLIGHT", "QUERY_MATCH_BLOCK")))
    runs = {}
    for label, root in (("now", DIRS["offp"]), ("before", DIRS["old"])):
        s, ok = boot(root)
        c = s.c
        try:
            check("flags off (%s scripts): page boots" % label, ok)
            ids = jx(c, "(()=>{const L=Object.entries(TAX.leaves).filter(([id,l])=>!l.flags.length&&memOids(id).length>25&&memOids(id).length<400);return [L[0][0],L[7][0]]})()")
            snaps = []
            snap = "(()=>{const g=id=>{const e=document.getElementById(id);return e?e.innerHTML:''};return [g('panel'),g('tree'),g('findres')].join('\\n=====\\n')})()"

            def take():
                c.pump(0.6)
                snaps.append(c.js(snap))
            wait_plain(c, "l:" + ids[0]); take()
            c.js("document.querySelector('[data-f=col][data-v=U]') && document.querySelector('[data-f=col][data-v=U]').click()"); take()
            c.js("document.querySelector('[data-f=col][data-v=B]') && document.querySelector('[data-f=col][data-v=B]').click()"); take()
            c.js("document.querySelector('[data-f=type][data-v=Creature]') && document.querySelector('[data-f=type][data-v=Creature]').click()"); take()
            c.js("document.querySelector('[data-f=clear]') && document.querySelector('[data-f=clear]').click()")
            wait_plain(c, "l:" + ids[1]); take()
            c.js("document.querySelector('[data-f=nar]') && document.querySelector('[data-f=nar]').click()"); take()
            c.js("document.querySelector('[data-f=nclear]') && document.querySelector('[data-f=nclear]').click()")
            dk = c.js("MERGED.pageBy['draw-cards'].key")
            wait_plain(c, dk); take()
            c.js("document.querySelector('[data-f=nmore]') && document.querySelector('[data-f=nmore]').click()"); take()
            c.js("document.querySelector('[data-f=nmore]') && document.querySelector('[data-f=nmore]').click()"); take()
            c.js("document.querySelector('#list .tile').click()"); c.wait("document.querySelector('.tmodal:not([hidden]) .toracle')", 60); c.pump(0.8)
            snaps.append(c.js("document.querySelector('.tmodal').innerHTML")); c.key("Escape"); c.pump(0.3)
            c.js("document.getElementById('q').focus()"); c.type("board wipe")
            c.wait("document.querySelectorAll('#findres .gr').length > 0", 90); c.pump(1.5); take()
            c.js("document.querySelector('.sclr').click()"); c.pump(0.4)
            c.js("document.querySelector('#tree .row[data-k^=\"f:\"]').click()"); take()
            reqs = sorted(r["url"].replace(s.base(), "") for r in s.net() if r["url"].startswith(s.base()))
            bad = [r for r in s.net() if r["url"].startswith(s.base()) and (r["failed"] or (r["status"] or 0) >= 400)]
            runs[label] = (snaps, reqs, bad, [x for x in s.console() if not re.search(r"cards\.scryfall\.io", x)])
        finally:
            s.close()
    sn, sb = runs["now"][0], runs["before"][0]
    check("flags off: the DOM after %d identical steps (page, tree, search, card dialog) is identical to the page with the pre-feature scripts" % len(sn), sn == sb, [i for i in range(min(len(sn), len(sb))) if sn[i] != sb[i]])
    check("flags off: the requests are identical to the pre-feature page (%d requests)" % len(runs["now"][1]), runs["now"][1] == runs["before"][1], sorted(set(runs["now"][1]) ^ set(runs["before"][1]))[:5])
    check("flags off: none of the new files is requested", not [r for r in runs["now"][1] if re.search(r"typegroups|flipfaces|type_groups|faces/", r)])
    check("flags off: no failed request, no console error", not runs["now"][2] and not runs["now"][3], (runs["now"][2][:2], runs["now"][3][:2]))

    # ------------------------------------------------------------ 4. flags on: type pages, search, tree
    R = REF.Ref(os.path.join(DIRS["feat"], "build", "hand_view.json"))
    s, ok = boot(DIRS["feat"])
    c = s.c
    wrong30 = []
    try:
        check("flags on: page boots with the four features loaded", ok and c.js("typeof TG==='object' && typeof FL==='object'"))
        names0 = [r["url"].replace(s.base(), "") for r in s.net()]
        check("flags on, boot: requests the 4 new page files and no data file of theirs (all lazy)", sum(1 for n in names0 if re.search(r"/(typegroups|flipfaces)\.(js|css)$", n)) == 4 and not [n for n in names0 if re.search(r"type_groups|faces/faces", n)], [n for n in names0 if re.search(r"type_groups|faces", n)])
        check("flags on, boot: no console error, no failed request", not s.console() and not [r for r in s.net() if r["failed"] or (r["status"] or 0) >= 400], s.console()[:3])
        # tree
        c.js("document.querySelector('#tree .row[data-k=\"TY:\"]').click()"); c.wait("document.querySelector('#tree .row[data-k=\"ty:t.creature\"]')", 60); c.pump(0.5)
        tr = jx(c, "[...document.querySelectorAll('#tree .row')].filter(r=>r.dataset.k.startsWith('ty:')||r.dataset.k.startsWith('TY')).map(r=>r.dataset.k)")
        check("tree: a 'Card types' row; opened it lists the 11 types and 4 supertypes, then the subtype folders", sum(1 for k in tr if k.startswith("ty:t.")) == 11 and sum(1 for k in tr if k.startswith("ty:s.")) == 4 and "TYd:creature" in tr and "TYd:spell" in tr, tr[:20])
        check("tree: the Card types row says it is a filter, not a placement", c.js("/Filters, not placements/.test(document.getElementById('tree').innerText)"))
        c.js("document.querySelector('#tree .row[data-k=\"TYd:creature\"]').click()"); c.pump(0.5)
        crow = jx(c, "[...document.querySelectorAll('#tree .row')].filter(r=>r.dataset.k.startsWith('ty:u.')).map(r=>[r.dataset.k, r.querySelector('.n').textContent])")
        ncre = len([g for g in groups.values() if g[2] == "u" and g[3] == "creature"])
        check("tree: creature types: the 40 largest by size first (Human first), then 'More creature types (%d)'" % (ncre - 40), len(crow) == 40 and crow[0][0] == "ty:u.human" and c.js("!!document.querySelector('#tree .row[data-k=\"TYm:creature\"]')") and ("(%d)" % (ncre - 40)) in c.js("document.querySelector('#tree .row[data-k=\"TYm:creature\"]').innerText"), (len(crow), crow[:2]))
        sizes = [int(n.replace(",", "")) for _, n in crow]
        check("tree: those 40 are sorted by size, largest first", sizes == sorted(sizes, reverse=True))
        c.js("document.querySelector('#tree .row[data-k=\"TYm:creature\"]').click()"); c.pump(0.5)
        more = jx(c, "[...document.querySelectorAll('#tree .row')].filter(r=>r.dataset.k.startsWith('ty:u.')).map(r=>r.querySelector('span').textContent.trim())")[40:]
        check("tree: the remaining creature types are A to Z", more == sorted(more, key=lambda x: (x.lower(), x)) and len(more) == ncre - 40, more[:4])

        # a type page
        def open_type(key):
            c.js("show(%s)" % json.dumps(key))
            return c.wait("selected===%s && !document.getElementById('panel').classList.contains('tpend') && !!document.querySelector('.thead h1') && !!document.querySelector('#list [data-oid]') && !!document.getElementById('fwrap')" % json.dumps(key), 120)
        check("type page Saga opens", open_type("ty:u.saga"))
        c.pump(1)
        sg = jx(c, "{h1:document.querySelector('.thead h1').textContent, cnt:document.querySelector('.tcnt').textContent, note:(document.querySelector('.tgnote')||{}).textContent, crumb:document.querySelector('.crumb').textContent, tiles:document.querySelectorAll('#list .tile').length, size:TG.members('ty:u.saga').size, shown:TF.shown().length, sel:selected, hash:location.hash, tabs:document.querySelectorAll('#sctabs').length, loose:document.querySelectorAll('.tloosenote').length}")
        check("Saga page: name, '230 cards', the 'filter and a page, not a placement' note, 'via other face' count", sg["h1"] == "Saga" and sg["cnt"] == "230 cards" and "not a placement" in sg["note"] and "26 cards are here only through the other face" in sg["note"], sg)
        check("Saga page: members are the 230 cards (all those with a picture shown), no tab bar, no 'grouped loosely' note, address carries the key", sg["size"] == 230 and sg["tabs"] == 0 and sg["loose"] == 0 and "ty%3Au.saga" in sg["hash"] or "ty:u.saga" in sg["hash"], sg)
        sagas = jx(c, "TG.members('ty:u.saga') && [...TG.members('ty:u.saga')]")
        check("Saga page: the member set is exactly the Saga pages' Atomic set (230)", len(sagas) == 230)
        c.js("document.querySelector('[data-view=text]').click()"); c.pump(0.8)
        via_oids = {order[i] for i in mem["o"]["ty:u.saga"]}
        rendered = jx(c, "[...document.querySelectorAll('#list .card')].map(e=>e.dataset.oid)")
        vias = c.js("document.querySelectorAll('#list .tgvia').length")
        check("Saga page (Text view): the 'via other face' rows are marked: %d of the %d rows shown, as the Scryfall derivation says" % (vias, len(rendered)), len(rendered) > 0 and vias == len(set(rendered) & via_oids), (vias, len(set(rendered) & via_oids)))
        c.js("document.querySelector('[data-view=images]').click()"); c.pump(0.5)
        fil = jx(c, "{bar:!!document.getElementById('fwrap'), sub:!!document.querySelector('select[data-f=sub]'), note:/Any of the chosen/.test(document.getElementById('fwrap').innerText)}")
        check("Saga page: the filter bar is there, with a Subtype select", fil["bar"] and fil["sub"] and fil["note"], fil)
        chips = jx(c, "TF.chipsAll().map(x=>x.key)")
        check("Saga page: no type page is offered as a narrowing chip", not [k for k in chips if k.startswith("ty:")] and "ty:" not in c.js("document.querySelector('.nrow') ? document.querySelector('.nrow').innerHTML : ''"))
        # the Subtype row: Legendary on the Saga page
        info_leg = None
        if info is not None:
            all_saga, _ = expected_members(info, "u", "Saga")
            all_leg, _ = expected_members(info, "s", "Legendary")
            exp = len(all_saga & all_leg)
            vis_saga = {o for o in all_saga if o in R.img}
            exp_vis = len(vis_saga & all_leg)
            c.js("(()=>{const s=document.querySelector('select[data-f=sub]'); s.value='ty:s.legendary'; s.dispatchEvent(new Event('change',{bubbles:true}))})()")
            c.wait("TF.state().subs.has('ty:s.legendary') && TF.shown().length<230", 90); c.pump(0.8)
            got_leg = c.js("TF.shown().length")
            check("Subtype row: Saga + Legendary shows %d (Scryfall: %d of the pictured Sagas)" % (got_leg, exp_vis), got_leg == exp_vis, (got_leg, exp_vis, exp))
            st = c.js("document.querySelector('.fbar .fstat span').textContent")
            check("Subtype row: the status line says 'Showing %d of ...'" % exp_vis, ("Showing %s" % format(exp_vis, ",")) in st, st)
            c.js("document.querySelector('[data-f=subx]').click()"); c.pump(0.5)
            check("Subtype row: removing the chip restores the list", c.js("TF.shown().length") == len(vis_saga) and c.js("TF.state().subs.size") == 0)
        # search
        def search(q):
            c.js("document.querySelector('.sclr').click()"); c.pump(0.3)
            c.js("document.getElementById('q').focus()"); c.type(q)
            c.wait("document.querySelectorAll('#findres .gr, #findres .fr').length > 0", 90); c.pump(1.2)
            return jx(c, "[...document.querySelectorAll('#findres .gr')].map(g=>[g.dataset.go, g.querySelector('.gn').textContent, (g.querySelector('.gd')||{}).textContent||''])")
        cases = [("saga", "ty:u.saga"), ("sagas", "ty:u.saga"), ("creature", "ty:t.creature"), ("creatures", "ty:t.creature"), ("elves", "ty:u.elf"), ("equipment", "ty:u.equipment"), ("siege", "ty:u.siege"), ("tribal", "ty:t.kindred"), ("legendary", "ty:s.legendary"), ("time lord", "ty:u.time-lord")]
        bad = []
        for q, key in cases:
            res = search(q)
            if not res or res[0][0] != key:
                bad.append((q, res[:2]))
        check("search: saga, sagas, creature, creatures, elves, equipment, siege, tribal, legendary, time lord each lead with their type page", not bad, bad[:3])
        res = search("saga")
        check("search 'saga': the row says 'Card type'/'Enchantment type' and 'a filter, not a placement' and shows the card count", "filter, not a placement" in res[0][2] and c.js("/230 cards/.test(document.querySelector('#findres .gr').innerText)"), res[0])
        res = search("human")
        check("search 'human': the Human type page is first, an existing group never loses its place below it", res[0][0] == "ty:u.human" and len(res) > 1)
        # a search that must still find what it found before: an existing group name keeps its own top result
        res = search("draw cards")
        check("search 'draw cards': the existing Draw cards page is still first, no type page above it", not res[0][0].startswith("ty:"), res[0])
        res = search("board wipe")
        check("search 'board wipe': no type page appears", not [r for r in res if r[0].startswith("ty:")], res[:3])
        c.js("document.querySelector('.sclr').click()"); c.pump(0.3)
        # the type page from a search click
        c.js("document.getElementById('q').focus()"); c.type("legendary")
        c.wait("document.querySelector('#findres .gr')", 60); c.pump(1)
        c.js("document.querySelector('#findres .gr').click()")
        check("search result opens the type page", c.wait("selected==='ty:s.legendary' && !!document.querySelector('.thead h1') && !!document.querySelector('#list [data-oid]')", 90))
        check("the opened type page's tree row is highlighted and the folder is open", c.js("!!document.querySelector('#tree .row.sel[data-k=\"ty:s.legendary\"]')"))
        c.js("document.querySelector('.sclr').click()"); c.pump(0.3)
        c.js("show('ty:nope.x')"); c.pump(1.2)
        check("an unknown type key shows a plain message (no error)", not [x for x in s.console() if "exception" in x], s.console()[:2])
        # top 20 on the Creature page
        T.NOTES.append("type pages opened in this session: Saga, Creature; searches typed: %d" % (len(cases) + 4))

        # -------------------------------------------------------- 30 type pages (seed fixed above, drawn before anything is computed)
        rng = random.Random(SEED_T)
        keys = sorted(groups)
        draw = rng.sample(keys, 30)
        for key in draw:
            ok = open_type(key); c.pump(0.6)
            g = groups[key]
            top = json.loads(c.js("JSON.stringify(TF.full().slice(0, 20))"))
            allm = None
            if info is not None:
                allm, _ = expected_members(info, g[2], g[1])
            wrong = [o for o in top if allm is not None and o not in allm]
            cnt = c.js("document.querySelector('.tcnt').textContent")
            full = json.loads(c.js("JSON.stringify(TF.full())"))
            miss = [o for o in full if allm is not None and o not in allm]
            wrong30.append((g[1], len(wrong), len(top), cnt, len(miss), ok))
        bad_pages = [w for w in wrong30 if w[1] > 3 or not w[5]]
        check("30 type pages (seed %d): none has more than 3 wrong cards among its first 20 (worst: %s)" % (SEED_T, max(wrong30, key=lambda w: w[1])[:3]), not bad_pages and len(wrong30) == 30, bad_pages[:3])
        check("30 type pages: every card listed is a member by the Scryfall type lines (total wrong over all lists: %d)" % sum(w[4] for w in wrong30), sum(w[4] for w in wrong30) == 0, [w for w in wrong30 if w[4]][:3])
        check("30 type pages: each header count equals the index count", all(w[3] == "%s cards" % format(groups[k][4], ",") for w, k in zip(wrong30, draw)), [w[3] for w in wrong30][:3])
        T.NOTES.append("30 type pages (seed %d): %s" % (SEED_T, ", ".join("%s(%d/%d wrong in top 20)" % (w[0], w[1], w[2]) for w in wrong30)))

        # -------------------------------------------------------- narrowing without the cut
        dk = c.js("MERGED.pageBy['draw-cards'].key")
        # five small pages, drawn with a fixed seed from the leaf pages of 4 to 10 cards that have a picture
        small = jx(c, "Object.keys(TAX.leaves).filter(id=>{const n=memOids(id).length;return n>=4&&n<=10}).sort()")
        rng = random.Random(SEED_S)
        pick = rng.sample(small, 12)
        bad, shown = [], []
        for lid in pick:
            pk = "l:" + lid
            if not wait_page(c, pk):
                continue
            c.pump(0.4)
            full = json.loads(c.js("JSON.stringify(TF.full())"))
            ref, singles, total = REF.chips_nnc(R, full, full, pk)
            got = [(x["key"], x["label"], x["n"]) for x in json.loads(c.js("JSON.stringify(TF.chips())"))]
            row = c.js("!!document.querySelector('.nrow')")
            shown.append((TAX_NAME(c, lid), len(got), singles, row))
            if got != ref or not row:
                bad.append((lid, len(got), len(ref), row))
            if len(shown) >= 5 and not bad:
                pass
        check("narrowing, %d small pages (seed %d): chips and counts equal the Python reference, the row is always there" % (len(shown), SEED_S), not bad and len(shown) >= 5, bad[:3])
        T.NOTES.append("small pages: %s" % shown[:6])
        # floor and the single-card link, on a small page that has both
        sp = None
        for lid in small:
            wait_page(c, "l:" + lid); full = json.loads(c.js("JSON.stringify(TF.full())"))
            _, singles, total = REF.chips_nnc(R, full, full, "l:" + lid)
            if singles >= 2 and total >= 1:
                sp = lid; break
        check("a small page with both 2-card chips and single-card groups was found", sp is not None)
        if sp:
            pk = "l:" + sp
            wait_page(c, pk); full = json.loads(c.js("JSON.stringify(TF.full())"))
            ref, singles, total = REF.chips_nnc(R, full, full, pk)
            ref1, _, total1 = REF.chips_nnc(R, full, full, pk, single=True)
            check("floor of 2: every chip shown has 2 or more shared cards", all(n >= 2 for _, _, n in [(x["key"], x["label"], x["n"]) for x in jx(c, "TF.chips()")]))
            lk = c.js("(()=>{const b=document.querySelector('[data-f=single]');return b?b.textContent:''})()")
            check("'Show single-card groups (%d)' link is offered" % singles, lk == "Show single-card groups (%d)" % singles, lk)
            c.js("document.querySelector('[data-f=single]').click()"); c.pump(0.6)
            got1 = [(x["key"], x["label"], x["n"]) for x in jx(c, "TF.chips()")]
            check("after the link: single-card chips are shown (%d chips), equal to the reference" % len(got1), got1 == ref1 and any(n == 1 for _, _, n in got1), (len(got1), len(ref1)))
            check("the link now offers to hide them", c.js("document.querySelector('[data-f=single]').textContent") == "Hide single-card groups")
            c.js("document.querySelector('[data-f=single]').click()"); c.pump(0.4)
        # the big page: order, 12 then Show more up to 60, zero-count hidden, folded duplicates
        wait_page(c, dk); c.pump(0.6)
        full = json.loads(c.js("JSON.stringify(TF.full())"))
        refd, singles_d, total_d = REF.chips_nnc(R, full, full, dk)
        gotd = [(x["key"], x["label"], x["n"]) for x in jx(c, "TF.chips()")]
        check("Draw cards: the chips (%d, capped at 60 of %d) equal the Python reference, in order" % (len(gotd), total_d), gotd == refd and len(gotd) == 60, (len(gotd), len(refd)))
        sizes = [len(R.mem[k]) for k, _, _ in gotd]
        keys_ = [(-n, sz, l.lower() if False else l, k) for (k, l, n), sz in zip(gotd, sizes)]
        check("Draw cards: ordered by shared count, then smaller group, then name", all(keys_[i] <= keys_[i + 1] for i in range(len(keys_) - 1)))
        shown_counts = [c.js("document.querySelectorAll('.nrow .fch[data-f=nar]').length")]
        for _ in range(5):
            c.js("(()=>{const b=document.querySelector('[data-f=nmore]'); if(b) b.click()})()"); c.pump(0.3)
            shown_counts.append(c.js("document.querySelectorAll('.nrow .fch[data-f=nar]').length"))
        check("Draw cards: 12 shown, 'Show more' adds 12 each time and stops at 60 %s" % shown_counts, shown_counts == [12, 24, 36, 48, 60, 60] and not c.js("!!document.querySelector('[data-f=nmore]')"), shown_counts)
        check("Draw cards: no chip with a zero count, none at or above 90%% of the list", all(0 < n and n * 10 < len(full) * 9 for _, _, n in gotd))
        sigs = {}
        for k, _, n in gotd:
            sg_ = frozenset(R.mem[k] & set(full))
            sigs.setdefault(sg_, []).append(k)
        check("Draw cards: no two chips pick exactly the same cards", all(len(v) == 1 for v in sigs.values()), [v for v in sigs.values() if len(v) > 1][:2])
        check("Draw cards: the note says only the 60 largest are shown", c.js("/Showing the 60 groups/.test(document.querySelector('.nrow').innerText)"), c.js("document.querySelector('.nrow .fnote').textContent"))
        # a chip narrows to exactly page AND chip
        c.js("document.querySelector('.nrow .fch[data-f=nar]').click()"); c.pump(0.8)
        k0, l0, n0 = refd[0]
        shown_ = json.loads(c.js("JSON.stringify(TF.shown())"))
        check("ticking the first chip keeps exactly page AND chip (%d cards)" % n0, sorted(shown_) == sorted(set(full) & R.mem[k0]) and len(shown_) == n0)
        c.js("document.querySelector('[data-f=nclear]').click()"); c.pump(0.4)

        # -------------------------------------------------------- 30 narrowed lists (seed fixed above). Draw 1: 60 (page, rank) pairs, as the earlier filter test does; it leaves fewer than 30 readable
        # lists, so draw 2 takes 100 pairs from the same seed. Both are read and reported; neither is dropped.
        elig = sorted(g for g, v in R.G.items() if v[4] and v[3] in ("leaf", "tent", "loose", "tag", "kw", "rp") and v[1] >= 15)
        all_reads = {}
        for label, npairs in (("draw1", 60), ("draw2", 100)):
            rng = random.Random(SEED_N)
            pairs = list(zip(rng.sample(elig, npairs), [rng.randint(1, 5) for _ in range(npairs)]))
            reads, notsens = [], []
            for gid, rank in pairs:
                if len(reads) >= 30:
                    break
                pk = page_key(R, gid)
                if not wait_page(c, pk, 60):
                    continue
                full = json.loads(c.js("JSON.stringify(TF.full())"))
                ref, _, _ = REF.chips_nnc(R, full, full, pk)
                if len(ref) < rank:
                    continue
                k, label_, n = ref[rank - 1]
                c.js("document.querySelectorAll('.nrow [data-f=nar]')[%d].click()" % (rank - 1)); c.pump(0.6)
                res = json.loads(c.js("JSON.stringify(TF.shown())"))
                pname = R.name.get(gid, R.G[gid][0] if gid in R.G else gid)
                sensible = sorted(res) == sorted(set(full) & R.mem[k]) and 2 <= len(res) < 0.9 * len(full) and not REF.restates(REF.name_key(R.name[k]), REF.name_key(pname)) and REF.jac(REF.name_key(R.name[k]), REF.name_key(pname)) < 0.7
                reads.append({"page": pname, "page_cards": len(full), "chip": label_, "rank": rank, "result": len(res), "sensible": sensible, "first": [cards[o]["n"] for o in res[:5]]})
                if not sensible:
                    notsens.append((pname, label_, len(res)))
                c.js("document.querySelector('[data-f=nclear]') && document.querySelector('[data-f=nclear]').click()")
            all_reads[label] = reads
            check("narrowed lists, %s (seed %d, %d pairs): %d read; mechanical bar: each is exactly page AND chip, 2+ cards, under 90%%, not a restatement of the page (not sensible: %d; more than 5 fails)" % (label, SEED_N, npairs, len(reads), len(notsens)),
                  len(reads) >= (25 if label == "draw1" else 30) and len(notsens) <= 5, notsens[:5])
        json.dump(all_reads, open(reads_out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        T.NOTES.append("narrowed lists written to %s (draw1 %d lists, draw2 %d lists)" % (reads_out, len(all_reads["draw1"]), len(all_reads["draw2"])))

        # -------------------------------------------------------- colour modes
        modes = ["any", "all", "only", "not"]
        cards_col = {o: v["col"] for o, v in cards.items()}
        got_tbl, py_bad, js_bad = {}, [], []
        res = json.loads(c.js("""(async () => {
          const T = %s, M = ['any','all','only','not'], out = {}, cols = Object.fromEntries(Object.entries(CARDS).map(([o,c]) => [o, c.col || '']));
          for (const [sel, row] of Object.entries(T)) { const S = new Set(sel.split('+')); out[sel] = M.map(m => { let n = 0; for (const o in cols) if (TF.colOk(cols[o], S, m)) n++; return n; }); }
          return JSON.stringify(out); })()""" % json.dumps(COLOUR_TABLE)))
        for sel, want in COLOUR_TABLE.items():
            pyc = [sum(1 for col in cards_col.values() if REF.col_ok(col, set(sel.split("+")), m)) for m in modes]
            if list(res[sel]) != list(want):
                js_bad.append((sel, res[sel], want))
            if pyc != list(want):
                py_bad.append((sel, pyc, want))
        check("colour modes: 10 selections x 4 modes over all %d cards: the page's rule equals the counts worked out before the build" % len(cards_col), not js_bad, js_bad[:2])
        check("colour modes: a Python set implementation gives the same 40 counts", not py_bad, py_bad[:2])
        wait_page(c, dk); c.pump(0.5)
        full = json.loads(c.js("JSON.stringify(TF.full())"))
        fcs = fc["cards"]
        ucol = lambda o: "".join(x for x in "WUBRG" if x in (fcs[o]["f"][0]["c"] + fcs[o]["f"][1]["c"])) if o in fcs else R.C[o]["col"]
        ui_bad = []
        for sel, want in list(COLOUR_TABLE.items())[:6]:
            for mi, m in enumerate(modes):
                c.js("document.querySelector('[data-f=clear]') && document.querySelector('[data-f=clear]').click()")
                c.js("document.querySelector('[data-f=cmode][data-v=%s]').click()" % m)
                for x in sel.split("+"):
                    c.js("document.querySelector('[data-f=col][data-v=%s]').click()" % x)
                exp = len([o for o in full if REF.col_ok(ucol(o), set(x for x in sel.split("+") if not (m == "only" and x == "M")), m)])
                got = c.js("TF.shown().length")
                if got != exp:
                    ui_bad.append((sel, m, got, exp))
        check("colour modes in the page: 6 selections x 4 modes on Draw cards show the independent count (Showing N of M)", not ui_bad, ui_bad[:3])
        c.js("document.querySelector('[data-f=clear]') && document.querySelector('[data-f=clear]').click()")
        check("the five modes are there, 'Only these' is the default and the line 'Card colour, not colour identity' stays", c.js("[...document.querySelectorAll('.cmseg [data-f=cmode]')].map(b=>b.textContent).join('|')") == "Any of these|Includes all|Only these|Exactly these|Not these" and c.js("document.querySelector('.cmseg .on').dataset.v") == "only" and c.js("/Card colour, not colour identity/.test(document.querySelector('.fbar').innerText)"))
        c.js("document.querySelector('[data-f=col][data-v=M]').click()"); c.js("document.querySelector('[data-f=cmode][data-v=only]').click()"); c.pump(0.4)
        mpip = jx(c, "{on:document.querySelector('[data-f=col][data-v=M]').classList.contains('on'), dis:document.querySelector('[data-f=col][data-v=M]').getAttribute('aria-disabled'), tip:document.querySelector('[data-f=col][data-v=M]').title}")
        check("Only these: switching to it clears Multicolour, greys it out (aria-disabled) and its tooltip says why", not mpip["on"] and mpip["dis"] == "true" and "Only these" in mpip["tip"], mpip)
        c.js("document.querySelector('[data-f=col][data-v=M]').click()"); c.pump(0.3)
        check("Only these: clicking the greyed Multicolour does nothing", not c.js("TF.state().cols.has('M')"))
        c.js("document.querySelector('[data-f=cmode][data-v=any]').click()"); c.pump(0.3)
        check("back to Any of these: Multicolour works again", c.js("document.querySelector('[data-f=col][data-v=M]').getAttribute('aria-disabled')") is None)
        c.js("document.querySelector('[data-f=clear]') && document.querySelector('[data-f=clear]').click()")
        T.NOTES.append("colour table checked: %s" % {k: v for k, v in list(COLOUR_TABLE.items())[:3]})

        # -------------------------------------------------------- flip
        faces = fc["cards"]
        trans = next(o for o, v in faces.items() if v["l"] == "transform" and v["pf"] == 1 and o in R.img and R.img[o][2])
        modal_ = next(o for o, v in faces.items() if v["l"] == "modal" and o in R.img and R.img[o][2])
        adv = next(o for o, v in faces.items() if v["l"] == "adventure" and o in R.img and not R.img[o][2])
        flip_res = {}
        for label, oid in (("transform (page lists the back face)", trans), ("modal", modal_), ("adventure", adv)):
            c.js("show('c:%s')" % oid)
            c.wait("document.querySelector('.tmodal:not([hidden]) .flipbtn')", 60); c.pump(0.8)
            v = faces[oid]
            f0, f1 = v["f"]
            get = "(()=>{const m=document.querySelector('.tmodal');return {h2:m.querySelector('h2').textContent, ty:m.querySelector('.tinfo .tsrc').textContent, text:m.querySelector('.toracle').textContent, img:(m.querySelector('img')||{}).src||'', st:m.querySelector('.flipst').textContent, btn:m.querySelector('.flipbtn').title}})()"
            a0 = jx(c, get)
            c.js("document.querySelector('.tmodal .flipbtn').click()"); c.pump(0.5)
            a1 = jx(c, get)
            c.js("document.querySelector('.tmodal .flipbtn').click()"); c.pump(0.5)
            a2 = jx(c, get)
            both = bool(R.img[oid][2])
            sf = SCRY_FACES.get(oid)
            sf_ok = sf is None or (sf[0][0] == a0["h2"] and sf[1][0] == a1["h2"] and sf[0][3] == a0["text"] and sf[1][3] == a1["text"] and sf[0][2].replace(" — ", " - ") in a0["ty"] and sf[1][2].replace(" — ", " - ") in a1["ty"] and sf[0][1] in a0["ty"] and sf[1][1] in a1["ty"] or (sf[1][1] == "" and sf[0][1] in a0["ty"]))
            if sf is None:
                T.NOTES.append("flip: Scryfall's text for %s not available, compared with the MTGJSON file only" % label)
            ok = (sf_ok and a0["h2"] == f0["n"] and a0["text"] == f0["t"] and f0["ty"] in a0["ty"] and a1["h2"] == f1["n"] and a1["text"] == f1["t"] and f1["ty"] in a1["ty"] and a2 == a0
                  and (("/front/" in a0["img"] and "/back/" in a1["img"] and "/front/" in a2["img"]) if both else (a0["img"] == a1["img"] and "/front/" in a0["img"])))
            flip_res[label] = (ok, a0["h2"], a1["h2"], a0["st"], a1["st"])
            check("flip, %s: opens on the first face (%s), Flip shows %s with its own cost, type and text, Flip again returns%s" % (label, f0["n"], f1["n"], ", picture front/back" if both else ", one picture, text only"), ok, (a0, a1))
            c.key("Escape"); c.pump(0.3)
        check("flip: the transform card whose page record is the back face now opens on the front face", faces[trans]["pf"] == 1 and flip_res["transform (page lists the back face)"][0])
        check("flip: a one-picture card says so", "One picture shows both halves" in flip_res["adventure"][3], flip_res["adventure"])
        c.js("show('c:%s')" % next(o for o in cards if o not in faces and o in R.img)); c.pump(1.2)
        check("flip: a one-faced card has no Flip control", not c.js("!!document.querySelector('.tmodal .flipbtn')"))
        c.key("Escape"); c.pump(0.3)
        # either face's name in the search; one of the names that could not be found before
        lk = json.load(open(os.path.join(HERE, "build", "ability_taxonomy_lookup.json"), encoding="utf-8"))
        known = {}
        for e in lk["entries"]:
            known[e[0]] = {x.lower() for x in [e[1]] + list(e[2])}
        missing = [(o, v["f"][i]["n"]) for o, v in faces.items() for i in range(2) if v["f"][i]["n"].lower() not in known.get(o, set()) and o in cards]
        check("faces.json finds the unfindable face names (%d two-faced cards have a face name the card search did not know)" % len(missing), len(missing) >= 20, len(missing))
        bad = []
        for o, nm in missing[:3]:
            c.js("document.querySelector('.sclr').click()"); c.pump(0.3)
            c.js("document.getElementById('q').focus()"); c.type(nm)
            c.wait("document.querySelectorAll('#findres .gr, #findres .fr').length > 0 && !/Loading/.test(document.getElementById('findres').innerText)", 60); c.pump(2.0)
            row = c.js("!![...document.querySelectorAll('#findres .fr')].find(r=>(r.dataset.go||'').endsWith('%s'))" % o)
            why = c.js("(([...document.querySelectorAll('#findres .flipwhy')].map(x=>x.textContent)).join(' '))")
            if not row or "matched" not in why:
                bad.append((nm, row, why))
        check("search by the name of a face the card search did not know finds the card and says which face matched", not bad, bad)
        o2 = next(o for o, v in faces.items() if v["l"] == "transform" and v["pf"] == 0 and o in R.img)
        nm2 = faces[o2]["f"][1]["n"]
        c.js("document.querySelector('.sclr').click()"); c.pump(0.3)
        c.js("document.getElementById('q').focus()"); c.type(nm2)
        c.wait("document.querySelectorAll('#findres .fr').length > 0", 60); c.pump(2.0)
        check("search by a back face's name lists the card, once, with 'matched: other face'", c.js("[...document.querySelectorAll('#findres .fr')].filter(r=>(r.dataset.go||'').endsWith('%s')).length" % o2) == 1 and "other face" in c.js("document.getElementById('findres').innerText"), c.js("document.getElementById('findres').innerText.slice(0,200)"))
        c.js("document.querySelector('.sclr').click()"); c.pump(0.3)
        # filters read both faces
        union_bad = []
        for o, v in list(faces.items())[:861]:
            if o not in cards:
                continue
            want = "".join(x for x in "WUBRG" if x in v["f"][0]["c"] + v["f"][1]["c"])
            got = c.js("TF.facts('%s').col" % o)
            if got != want:
                union_bad.append((cards[o]["n"], got, want))
        check("filters (either face): the colour the filters read for all 861 two-faced cards is the union of the two faces", not union_bad, union_bad[:3])
        zero_to_col = [o for o, v in faces.items() if cards.get(o, {}).get("col") == "" and (v["f"][0]["c"] + v["f"][1]["c"])]
        check("filters (either face): the cards the page called colourless although a face has colour (%d) are no longer colourless" % len(zero_to_col), len(zero_to_col) >= 20 and all(c.js("TF.facts('%s').col" % o) != "" for o in zero_to_col[:20]))
        # a card shown because of its other face says so
        found = None
        for pk in (dk, "l:" + (small[0] if small else "")):
            wait_page(c, pk)
            for col in "WUBRG":
                c.js("document.querySelector('[data-f=clear]') && document.querySelector('[data-f=clear]').click()")
                c.js("document.querySelector('[data-f=col][data-v=%s]').click()" % col); c.pump(0.4)
                notes = jx(c, "TF.shown().slice(0, 60).map(o=>[o, TF.faceNote(o)]).filter(x=>x[1])")
                if notes:
                    found = (pk, col, notes[0]); break
            if found:
                break
        check("filters (either face): a card shown only for its other face carries a note %s" % (found[2][1] if found else ""), bool(found) and found[2][1].startswith("matched on its other face") , found)
        if found:
            wait_page(c, found[0])
            c.js("document.querySelector('[data-f=clear]') && document.querySelector('[data-f=clear]').click()")
            c.js("document.querySelector('[data-f=col][data-v=%s]').click()" % found[1]); c.pump(1.0)
            check("filters (either face): the note is drawn on the card in the list", c.js("!![...document.querySelectorAll('#list .fnote2, #list .tgvia')].find(x=>/matched on its other face/.test(x.textContent))"))
            c.js("document.querySelector('[data-f=clear]') && document.querySelector('[data-f=clear]').click()")

        # -------------------------------------------------------- whole run on the desktop
        allnet = s.net()
        bad = [r for r in allnet if r["url"].startswith(s.base()) and (r["failed"] or (r["status"] or 0) >= 400)]
        check("whole desktop run: no failed same-origin request (%d requests)" % len(allnet), not bad, bad[:3])
        check("whole desktop run: no POST, no /api/, no corrections/ request", not [r for r in allnet if r["method"] != "GET" or "/api/" in r["url"] or "corrections" in r["url"]])
        ext = [r for r in allnet if not r["url"].startswith(s.base())]
        check("whole desktop run: the only outside requests are Scryfall images (%d)" % len(ext), all(r["url"].startswith("https://cards.scryfall.io/") for r in ext))
        con = [x for x in s.console() if not re.search(r"cards\.scryfall\.io", x)]
        check("whole desktop run: no console error or warning", not con, con[:3])
        check("the static server saw no non-GET request", not [x for x in s.log if x[0] != "GET"])
    finally:
        s.close()

    # ------------------------------------------------------------ 5. phone width
    s, ok = boot(DIRS["feat"], 390)
    c = s.c
    try:
        check("390 px: page boots", ok)
        c.js("show('ty:u.saga')"); c.wait("selected==='ty:u.saga' && !!document.getElementById('fwrap') && !!document.querySelector('#list [data-oid]')", 90); c.pump(1)
        ph = jx(c, "{sw:document.documentElement.scrollWidth, iw:innerWidth, bar:getComputedStyle(document.querySelector('.fbar')).display, nsum:(document.querySelector('[data-f=nfold]')||{}).textContent||'', nrow:document.querySelector('.nrow')?getComputedStyle(document.querySelector('.nrow')).display:'none', fsum:getComputedStyle(document.querySelector('[data-f=fold]')).display}")
        check("390 px, Saga page: no horizontal scroll; the filter bar is folded", ph["sw"] <= ph["iw"] and ph["bar"] == "none" and ph["fsum"] != "none", ph)
        check("390 px: 'Narrow by group' is folded but its row shows its count (%s)" % ph["nsum"].strip(), ph["nrow"] == "none" and re.search(r"Narrow by group\s*\d+ groups?", ph["nsum"]) is not None, ph)
        c.js("document.querySelector('[data-f=fold]').click()"); c.pump(0.4)
        mob = jx(c, "{seg:getComputedStyle(document.querySelector('.cmseg')).display, sel:getComputedStyle(document.querySelector('.cmsel')).display, selh:document.querySelector('.cmsel').getBoundingClientRect().height, pip:document.querySelector('.fpip').getBoundingClientRect().width, sw:document.documentElement.scrollWidth, iw:innerWidth}")
        check("390 px: the match mode is one select (44 px), the radio row is hidden, pips are 40 px, no horizontal scroll", mob["seg"] == "none" and mob["sel"] != "none" and mob["selh"] >= 43 and mob["pip"] >= 39 and mob["sw"] <= mob["iw"], mob)
        c.js("(()=>{const s=document.querySelector('.cmsel'); s.value='all'; s.dispatchEvent(new Event('change',{bubbles:true}))})()"); c.pump(0.3)
        c.js("document.querySelector('[data-f=col][data-v=W]').click()"); c.js("document.querySelector('[data-f=col][data-v=U]').click()"); c.pump(0.5)
        check("390 px: the select changes the mode (Includes all) and the folded line says it", c.js("TF.state().cmode") == "all" and "Includes all" in c.js("document.querySelector('[data-f=fold] .fpills').textContent"), c.js("document.querySelector('[data-f=fold] .fpills').textContent"))
        # flip at 390
        faces = fc["cards"]
        trans = next(o for o, v in faces.items() if v["l"] == "transform" and o in R.img and R.img[o][2])
        c.js("show('c:%s')" % trans); c.wait("document.querySelector('.tmodal:not([hidden]) .flipbtn')", 60); c.pump(0.8)
        fb = jx(c, "{r:document.querySelector('.flipbtn').getBoundingClientRect().toJSON(), iw:innerWidth, sw:document.documentElement.scrollWidth, mw:document.querySelector('.tbox').scrollWidth}")
        check("390 px: the Flip button is on screen, 40 px tall, the dialog does not scroll sideways", fb["r"]["right"] <= fb["iw"] and fb["r"]["left"] >= 0 and fb["r"]["height"] >= 39 and fb["sw"] <= fb["iw"], fb)
        c.key("Escape"); c.pump(0.3)
        bad = [r for r in s.net() if r["url"].startswith(s.base()) and (r["failed"] or (r["status"] or 0) >= 400)]
        con = [x for x in s.console() if not re.search(r"cards\.scryfall\.io", x)]
        check("390 px run: no failed request, no console error", not bad and not con, (bad[:2], con[:2]))
    finally:
        s.close()

    # ------------------------------------------------------------ 6. first load and timing, flags off against flags on
    perf = {}
    if not skip_perf:
        for label, root in (("off", DIRS["off"]), ("on", DIRS["feat"])):
            for cpu in (1, 4):
                runs_ = []
                for rep in range(3):
                    s = T.Session(root, "/reports/browse.html", 1280, gz=True, cpu=cpu)
                    c = s.c
                    try:
                        t0 = time.time()
                        c.wait(READY.replace(" && typeof TF !== 'undefined'", ""), 400)
                        tboot = time.time() - s.t0
                        c.pump(2)
                        net = [r for r in s.net() if r["url"].startswith(s.base())]
                        nbytes = sum(r["bytes"] or 0 for r in net)
                        dkk = c.js("MERGED.pageBy['draw-cards'].key")
                        a_ = c.js("performance.now()")
                        c.js("show(%s)" % json.dumps(dkk)); c.wait("selected===%s && !document.getElementById('panel').classList.contains('tpend') && !!document.querySelector('#list [data-oid]')" % json.dumps(dkk), 120)
                        topen = (c.js("performance.now()") - a_) / 1000
                        runs_.append((tboot, len(net), nbytes, topen))
                    finally:
                        s.close()
                perf[(label, cpu)] = tuple(statistics.median(x[i] for x in runs_) for i in range(4))
        for cpu in (1, 4):
            o, n = perf[("off", cpu)], perf[("on", cpu)]
            T.NOTES.append("first load at %dx CPU (median of 3, gzip server): flags off %.2f s to ready, %d requests, %s bytes on the wire; flags on %.2f s, %d requests, %s bytes; open Draw cards page: %.2f s off, %.2f s on" %
                           (cpu, o[0], o[1], format(int(o[2]), ","), n[0], n[1], format(int(n[2]), ","), o[3], n[3]))
        check("first load: flags on adds only the 4 small page files at boot (requests %d -> %d)" % (perf[("off", 1)][1], perf[("on", 1)][1]), perf[("on", 1)][1] - perf[("off", 1)][1] == 4)

    # ------------------------------------------------------------ done: protected files, cleanup
    after = T.protected()
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    check("protected files byte-identical before and after (%d hashed: corrections/ incl. backups, archive/, the shared JS, serve.py, top-level build files)" % len(before), not changed, changed[:5])
    cleanup()
    print("\n%d checks, %d failed" % (len(T.RESULTS), len([r for r in T.RESULTS if not r[1]])))
    for n in T.NOTES:
        print("NOTE", n)
    sys.exit(1 if any(not r[1] for r in T.RESULTS) else 0)


def TAX_NAME(c, lid):
    return c.js("TAX.leaves[%s].name" % json.dumps(lid))


def page_key(R, gid):
    if gid.startswith("P:"):
        return R.pages[gid[2:]]["key"]
    layer, _, i = gid.partition(":")
    return {"leaf": "l:" + i, "tent": "tg:" + i, "loose": "lg:" + i, "tag": "ct:" + i, "kw": "kl:" + gid, "rp": "gl:" + i}[layer]


if __name__ == "__main__":
    main()
