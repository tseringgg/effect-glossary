#!/usr/bin/env python3
"""Verify MODAL_ABILITIES (reports/config.js): the "Abilities" block in the large card view. Headless Edge over the DevTools protocol on exported folders served by a plain static server (GET only).

    python src/test_modal_abilities.py [--skip-perf] [--reads OUT.json] [--keep]

Independent of the page's own code: every block the page draws is compared with one re-derived here from the ability-page files (build/ability_pages/p/*.json, written by src/build_ability_pages.py and
read here as JSON), the card text (build/ability_taxonomy_cards.json), the face texts (build/faces/faces.json, matched by TEXT, not by the "pf" order the exporter uses) and the keyword facet
(build/keyword_facet.json). Not independent: build/ability_pages/cards.json is written by src/build_ability_cards.py from the same page files and the same parse (the ledger counts of "more abilities not on a page"
and "part of the text was not read" come from that parse, so they are checked for form, not for truth), and the 40 modals are written by --reads for a person to read: whether an entry is right is a judgment,
the seed is fixed before anything is computed. Clicks are DOM click() calls: no touch, no other browser. corrections/ and archive/ are hashed before and after; nothing here writes to them
(exports go to dist.ma_*/, removed at the end).
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
import test_tester_filters as F           # noqa: E402

check = T.check
SEED_40 = 20271104                        # fixed before any modal was computed
BEFORE = os.path.join(HERE, "src", "testdata", "before_modal_abilities")
OLD_BROAD = os.path.join(HERE, "src", "testdata", "before_broad_narrowing")
DIRS = {k: os.path.join(HERE, "dist.ma_" + k) for k in ("a", "b", "off", "old")}
CARDS_JSON = os.path.join(HERE, "build", "ability_pages", "cards.json")
B = os.path.join(HERE, "build")
KINDS = [("trig", "Triggered"), ("act", "Activated"), ("stat", "Static"), ("repl", "Replacement")]
NOTE = {1: "This spell’s effect is not an ability type. Ability pages cover triggered, activated, static and replacement abilities.",
        2: "The parser read this card’s abilities, but none is a kind that has an ability page yet.",
        3: "No abilities the parser could read.", 4: "Keyword abilities only. They have no ability page."}


def J(*p):
    with open(os.path.join(B, *p), encoding="utf-8") as fh:
        return json.load(fh)


def jx(c, expr):
    return json.loads(c.js("JSON.stringify(" + expr + ")"))


def files_of(root):
    return {os.path.relpath(p, root).replace("\\", "/"): T.sha(p) for p in T.walk(root)}


_NEW_OFF = []


def new_off():
    """A config.js with PERSIST_FILTERS and COLOUR_IDENTITY off (src/test_persist_identity.py tests them); this file tests the Abilities block."""
    if not _NEW_OFF:
        f = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
        f.write(re.sub(r"\b(PERSIST_FILTERS|COLOUR_IDENTITY|SEARCH_FIXES)\s*:\s*true", r"\1: false", open(os.path.join(HERE, "reports", "config.js"), encoding="utf-8").read())); f.close()
        _NEW_OFF.append(f.name)
    return _NEW_OFF[0]


def export_to(out, cfg=None):
    cmd = [sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--out", os.path.relpath(out, HERE)] + (["--config", cfg or new_off()])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    return r.returncode, r.stdout + r.stderr


def run_py(*args):
    return subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", args[0])] + list(args[1:]), capture_output=True, text=True, encoding="utf-8", cwd=HERE)


class Ref:
    """What the block should hold, from the page files, the card text, the face texts and the keyword facet."""
    def __init__(self):
        self.cards = J("ability_taxonomy_cards.json")["cards"]
        self.oids = list(self.cards)
        self.ci = {o: i for i, o in enumerate(self.oids)}
        idx = J("ability_pages", "index.json")
        self.pages = [(g[0], g[1]) for g in idx["groups"]]
        self.ent = {}                                   # card index -> [(page key, line, x)]
        for key, name in self.pages:
            d = J("ability_pages", "p", key[3:] + ".json")
            x = d.get("x") or {}
            for n in range(len(d["r"]) // 2):
                self.ent.setdefault(d["r"][2 * n], []).append((key, d["r"][2 * n + 1], x.get(str(n))))
        self.pname = dict(self.pages)
        self.faces = J("faces", "faces.json")["cards"]
        kf = J("keyword_facet.json")["keywords"]
        self.kw = {}                                    # oid -> [(key, display)]
        for k, v in kf.items():
            for o in v["c"]:
                self.kw.setdefault(o, []).append((k, v["d"]))
        self.kw_sorted = {o: sorted(v) for o, v in self.kw.items()}

    def face_of_line(self, oid, line):
        """0/1 by matching the segment's TEXT with the face texts; None where the text does not decide it."""
        fl = self.faces.get(oid)
        if not fl:
            return 0
        t = self.cards[oid]["t"].split("\n")
        seg = 0
        for l in t[:line]:
            if l.strip() == "//":
                seg += 1
        segs = self.cards[oid]["t"].split("\n//\n")
        if len(segs) != 2 or len(fl["f"]) != 2:
            return fl.get("pf", 0)                      # one-part card: checked separately against the text of the first part
        m = [j for j in range(2) if fl["f"][j]["t"] == segs[seg]]
        return m[0] if len(m) == 1 and [j for j in range(2) if fl["f"][j]["t"] == segs[1 - seg]] != m else None

    def block(self, oid, face):
        """Expected rows for a card and a face (None = no flip): [(kind label, [([chip names], [lines], more)])], keyword chips."""
        ci = self.ci[oid]
        lines = self.cards[oid]["t"].split("\n")
        by = {}
        for key, l, x in sorted(self.ent.get(ci, []), key=lambda e: (e[0], e[1], e[2] or "")):
            if face is not None and self.face_of_line(oid, l if l >= 0 else 0) not in (face, None):
                continue
            b = by.setdefault(key, {"first": 1e9, "ls": []})
            t = lines[l] if l >= 0 else x
            if t and t not in b["ls"]:
                b["ls"].append(t)
            if l >= 0:
                b["first"] = min(b["first"], l)
        order = [k for k, _ in self.pages]
        out = []
        for kind, label in KINDS:
            ks = sorted((k for k in by if k[3:].split(".")[0] == kind), key=lambda k: (by[k]["first"], order.index(k)))
            if not ks:
                continue
            groups = {}
            for k in ks:
                groups.setdefault("\n".join(by[k]["ls"]), []).append(k)
            out.append((label, [([(k, self.pname[k]) for k in g], by[g[0]]["ls"][:3], max(0, len(by[g[0]]["ls"]) - 3)) for g in groups.values()]))
        return out, [("yk:" + k, d) for k, d in self.kw_sorted.get(oid, [])]


DOM_JS = """(()=>{const b=document.querySelector('.tbox .mabl');if(!b)return null;const rows=[];let kind=null;
for(const n of b.querySelector('.mabody').children){
 if(n.classList.contains('makind')){kind=n.textContent;continue}
 if(n.classList.contains('manote')){rows.push({note:n.textContent});continue}
 if(n.classList.contains('maent'))rows.push({kind:kind,chips:[...n.querySelectorAll('.chip')].map(c=>({k:c.dataset.go,n:c.textContent,t:c.title||'',h:Math.round(c.getBoundingClientRect().height)})),lines:[...n.querySelectorAll('.maln')].map(x=>x.textContent),more:(n.querySelector('.mamore')||{textContent:''}).textContent})}
const sum=b.querySelector('.masum'),h3=b.querySelector('h3');
return {folded:b.classList.contains('folded'),h3:h3.textContent,sumShown:getComputedStyle(sum).display!=='none',sum:sum.textContent,bodyShown:getComputedStyle(b.querySelector('.mabody')).display!=='none',rows:rows}})()"""


def dom_block(c):
    return jx(c, DOM_JS)


def norm_dom(d):
    """DOM rows -> (kind label, [(chips[(key, name)], lines, more)]), keyword chips, notes."""
    kinds, kw, notes = [], [], []
    for r in d["rows"]:
        if "note" in r:
            notes.append(r["note"]); continue
        if r["kind"] == "Keyword abilities":
            kw += [(x["k"], x["n"]) for x in r["chips"]]; continue
        m = re.match(r"\+(\d+) more", r["more"] or "")
        item = ([(x["k"], x["n"]) for x in r["chips"]], r["lines"], int(m.group(1)) if m else 0)
        if kinds and kinds[-1][0] == r["kind"]:
            kinds[-1][1].append(item)
        else:
            kinds.append((r["kind"], [item]))
    return kinds, kw, notes


def open_card(c, oid, wait_block=True, faced=False):
    c.js("showCardPage(%s)" % json.dumps(oid))
    if wait_block:
        c.wait("!!document.querySelector('.tbox .mabl')", 30)
    else:
        c.pump(1.2)
    if faced:
        c.wait("!!document.querySelector('.tbox .flipbtn[data-face]')", 30); c.pump(0.4)


def close_modal(c):
    c.js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))"); c.pump(0.15)


def click(c, sel):
    return c.js("(()=>{const e=document.querySelector(%s);if(!e)return false;e.click();return true})()" % json.dumps(sel))


def expect_equal(R, oid, d, face):
    """DOM block against the re-derived one; returns a list of differences."""
    rows, kw = R.block(oid, face)
    kinds, dkw, notes = norm_dom(d)
    bad = []
    if [(l, [([k for k, _ in ch], ls, mo) for ch, ls, mo in items]) for l, items in rows] != [(l, [([k for k, _ in ch], ls, mo) for ch, ls, mo in items]) for l, items in kinds]:
        bad.append("entries")
    if [n for _, n in [(k, n) for k, n in dkw]] != [n for _, n in kw] or [k for k, _ in dkw] != [k for k, _ in kw]:
        bad.append("keywords")
    return bad


def main():
    skip_perf = "--skip-perf" in sys.argv
    reads_out = sys.argv[sys.argv.index("--reads") + 1] if "--reads" in sys.argv else os.path.join(tempfile.gettempdir(), "modal40_reads.json")
    before = dict(T.protected())
    for d in DIRS.values():
        shutil.rmtree(d, ignore_errors=True)

    # ------------------------------------------------------------ 1. the data file
    r1 = run_py("build_ability_cards.py"); h1 = T.sha(CARDS_JSON)
    r2 = run_py("build_ability_cards.py"); h2 = T.sha(CARDS_JSON)
    check("build_ability_cards.py runs twice and writes the same bytes (%s bytes)" % format(os.path.getsize(CARDS_JSON), ","), r1.returncode == 0 and r2.returncode == 0 and h1 == h2, r1.stdout + r1.stderr)
    check("--check agrees with the file on disk", run_py("build_ability_cards.py", "--check").returncode == 0)
    raw = open(CARDS_JSON, "rb").read()
    doc = json.loads(raw)
    R = Ref()
    check("cards.json: version 1, same sig as ability_pages/index.json, %d pages" % len(doc["pages"]), doc["v"] == 1 and doc["sig"] == J("ability_pages", "index.json")["sig"] and [p[0] for p in doc["pages"]] == [p[0] for p in R.pages])
    check("cards.json holds no card ids, no group ids and no paths", not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-|leaf:|tag:|corrections|archive", raw.decode("utf-8")))
    # decode independently of the page
    rec, ci = {}, 0
    d = doc["d"]
    i = 0
    while i < len(d):
        ci += d[i]; h = d[i + 1]; n = h >> 12; k = (h >> 8) & 15
        rec[ci] = {"st": h & 15, "miss": (h >> 4) & 15, "es": [((v & 63), ((v >> 6) & 127) - 1, v >> 13) for v in d[i + 2:i + 2 + n]], "ks": d[i + 2 + n:i + 2 + n + k]}
        i += 2 + n + k
    pk = [p[0] for p in doc["pages"]]
    got = {(c, pk[p], l) for c, r in rec.items() for p, l, f in r["es"]}
    want = {(c, k, l) for c, es in R.ent.items() for k, l, x in es}
    check("every (card, page, line) of the 42 page files is in cards.json and nothing else (%d entries)" % len(want), got == want, (len(got - want), len(want - got)))
    check("cards with an entry: %d (the page files' own count)" % len(R.ent), len({c for c, r in rec.items() if r["es"]}) == len(R.ent))
    kwd = {(R.oids[c], doc["kw"][j][0]) for c, r in rec.items() for j in r["ks"]}
    kwf = {(o, k) for o, v in R.kw.items() for k, _ in v}
    check("keywords: every (card, keyword) of the keyword facet is in cards.json and nothing else (%d)" % len(kwf), kwd == kwf)
    # faces: entry face against the face text
    bad_face, nfaced, amb, onepart = [], 0, 0, 0
    onepart_bad = []
    for c, r in rec.items():
        o = R.oids[c]
        if o not in R.faces:
            if any(f for _, _, f in r["es"]):
                bad_face.append(o)
            continue
        nfaced += 1
        segs = R.cards[o]["t"].split("\n//\n")
        fl = R.faces[o]
        if len(segs) == 1:
            onepart += 1
            if segs[0] != fl["f"][fl.get("pf", 0)]["t"] and not fl["f"][fl.get("pf", 0)]["t"].startswith(segs[0][:40]):
                onepart_bad.append(o)
        for p, l, f in r["es"]:
            if l < 0:
                continue
            w = R.face_of_line(o, l)
            if w is None:
                amb += 1
            elif w != f:
                bad_face.append(o)
    check("faces: each entry's face matches the face whose TEXT holds its line (%d two-faced cards with a record; %d entries on the 3 look-alike cards left to the pf order)" % (nfaced, amb), not bad_face, bad_face[:3])
    print("one-part cards whose text is not that of the face pf names:", [R.cards[o]["n"] for o in onepart_bad])
    check("faces: the one-part cards (%d: aftermath, prepare, split) have their text on the face the pf order names (all but %d: %s, whose text in faces.json is another card's)" % (onepart, len(onepart_bad), [R.cards[o]["n"] for o in onepart_bad]), onepart >= 30 and len(onepart_bad) <= 1, onepart_bad[:3])

    def two_unique(o):
        segs = R.cards[o]["t"].split("\n//\n")
        return all(len([j for j in range(2) if R.faces[o]["f"][j]["t"] == s]) == 1 for s in segs)
    ambiguous = [o for o in R.faces if o in R.cards and len(R.cards[o]["t"].split("\n//\n")) == 2 and len(R.faces[o]["f"]) == 2 and not two_unique(o)]
    print("the look-alike two-faced cards:", [R.cards[o]["n"] for o in ambiguous])
    check("the 3 two-faced cards whose faces the text cannot tell apart: %s (the exporter keeps the pf order for them)" % [R.cards[o]["n"] for o in ambiguous], len(ambiguous) == 3, len(ambiguous))

    # ------------------------------------------------------------ 2. exports
    rc, out = export_to(DIRS["a"]); rc2, out2 = export_to(DIRS["b"])
    check("exports with the flag on succeed (twice)", rc == 0 and rc2 == 0, (out + out2)[-300:])
    fa, fb = files_of(DIRS["a"]), files_of(DIRS["b"])
    check("two flag-on exports: every file byte-identical (%d files)" % len(fa), fa == fb)
    for need in ("build/ability_pages/cards.json", "reports/modalabilities.js", "reports/modalabilities.css"):
        check("flag on: %s is exported and is the source file" % need, need in fa and fa[need] == T.sha(os.path.join(HERE, need.replace("build/", "build/").replace("reports/", "reports/"))))
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--check", "--config", new_off(), "--out", os.path.relpath(DIRS["a"], HERE)], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    check("whitelist check passes on the flag-on export", r.returncode == 0, r.stdout + r.stderr)
    for plant in ("build/ability_pages/cards.json.bak", "build/ability_pages/extra.json", "build/ability_pages/p/notes.txt", "corrections/group_aliases.json"):
        p = os.path.join(DIRS["a"], *plant.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write("{}")
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--check", "--config", new_off(), "--out", os.path.relpath(DIRS["a"], HERE)], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
        check("planted %s is refused" % plant, r.returncode != 0)
        os.remove(p)
        if plant.startswith("corrections"):
            shutil.rmtree(os.path.dirname(p))
    cfg_txt = open(os.path.join(HERE, "reports", "config.js"), encoding="utf-8").read()
    f = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    f.write(re.sub(r"\b(MODAL_ABILITIES|PERSIST_FILTERS|COLOUR_IDENTITY|SEARCH_FIXES)\s*:\s*true", r"\1: false", cfg_txt)); f.close()
    rc, out = export_to(DIRS["off"], f.name)
    check("export with the flag off succeeds", rc == 0, out[-300:])
    offf = files_of(DIRS["off"])
    base = json.load(open(os.path.join(BEFORE, "manifest.json"), encoding="utf-8"))
    basef = {x["path"]: x["sha256"] for x in base["files"]}
    check("flag off: the same file list as the export made before this work (%d files)" % len(basef), set(offf) - {"manifest.json"} == set(basef), sorted(set(offf) ^ set(basef))[:4])
    diff = [k for k in basef if offf.get(k) != basef[k]]
    check("flag off: every file is byte-identical to that export except config.js, tester.js (the flag and its hook), groupsearch.js (SEARCH_FIXES; src/test_search_fixes.py proves its flag-off behaviour) and testerfilters.js (it gained PERSIST_FILTERS and COLOUR_IDENTITY after that export was made; src/test_persist_identity.py checks it against its own baseline)", sorted(diff) == ["reports/config.js", "reports/groupsearch.js", "reports/tester.js", "reports/testerfilters.js"], diff[:6])
    check("flag off: no modalabilities file and no cards.json is exported or listed", not [k for k in offf if "modalabilities" in k or k.endswith("ability_pages/cards.json")] and not [x for x in json.load(open(os.path.join(DIRS["off"], "manifest.json")))["files"] if "modalabilities" in x["path"] or x["path"].endswith("ability_pages/cards.json")])
    shutil.copytree(DIRS["off"], DIRS["old"])
    shutil.copyfile(os.path.join(BEFORE, "tester.js"), os.path.join(DIRS["old"], "reports", "tester.js"))
    shutil.copyfile(os.path.join(BEFORE, "config.js"), os.path.join(DIRS["old"], "reports", "config.js"))

    # ------------------------------------------------------------ 3. flag off against the old scripts: same modals, same requests
    byname = {}
    for o, c in R.cards.items():
        byname.setdefault(c["n"], o)
    EX = {n: byname[n] for n in ("Thalia's Lieutenant", "Starved Rusalka", "Sorin Markov", "Bonesplitter", "Lightning Bolt", "Ulvenwald Abomination", "Grizzly Bears")}

    def drive(root):
        s = T.Session(root, "/reports/browse.html", 1280); c = s.c
        try:
            check("[%s] page boots" % os.path.basename(root), c.wait(F.READY, 300)); c.pump(1)
            snaps = []
            for n, o in EX.items():
                c.js("showCardPage(%s)" % json.dumps(o)); c.pump(1.0)
                snaps.append(c.js("document.querySelector('.tbox').innerHTML"))
                close_modal(c)
            urls = sorted({r["url"].replace(s.base(), "") for r in s.net()})
            return snaps, urls, s.console(), c.js("!!document.querySelector('.mabl')")
        finally:
            s.close()
    sn, un, cn, mn = drive(DIRS["off"]); so, uo, co, mo = drive(DIRS["old"])
    check("flag off: the new tester.js and the old one draw the same card view for 7 cards (a two-faced one too: %d snapshots)" % len(sn), sn == so and all(len(x) > 100 for x in sn) and not mn)
    check("flag off: the same requests (%d) and no console errors" % len(un), un == uo and not cn and not co, (set(un) ^ set(uo), cn[:2]))
    check("flag off: no request for modalabilities or cards.json", not [u for u in un if "modalabilities" in u or "cards.json" in u and "ability_pages" in u])

    # ------------------------------------------------------------ 4. flag on, 1280 px
    s = T.Session(DIRS["a"], "/reports/browse.html", 1280); c = s.c
    reads = []
    try:
        check("page boots", c.wait(F.READY, 300) and c.js("typeof MA!=='undefined' && MA.enabled===true"));
        c.pump(1)
        boot = [r["url"].replace(s.base(), "") for r in s.net()]
        check("first load: no request for cards.json (it waits for the first card)", not [u for u in boot if "ability_pages/cards.json" in u], [u for u in boot if "ability_pages" in u])
        check("first load: the only new requests are modalabilities.js and .css", sorted(u for u in boot if "modalabilities" in u) == ["/reports/modalabilities.css", "/reports/modalabilities.js"], [u for u in boot if "modalab" in u])
        mark = s.mark()
        # examples
        def pick(pred, label):
            for o in R.oids:
                if R.ci[o] in R.ent and pred(o):
                    return o
        repl = [o for o in sorted(R.oids, key=lambda o: R.cards[o]["n"]) if R.ci[o] in R.ent and any(k.startswith("ab:repl") for k, _, _ in R.ent[R.ci[o]]) and all(k.startswith("ab:repl") for k, _, _ in R.ent[R.ci[o]])][0]
        st4 = [o for o in sorted(R.oids, key=lambda o: R.cards[o]["n"]) if rec.get(R.ci[o], {}).get("st") == 4 and not R.ent.get(R.ci[o]) and R.cards[o]["t"].strip()][0]
        st3 = [o for o in sorted(R.oids, key=lambda o: R.cards[o]["n"]) if (rec.get(R.ci[o], {}).get("st", 0) & 7) == 3 and not R.ent.get(R.ci[o])][0]
        st2 = [o for o in sorted(R.oids, key=lambda o: R.cards[o]["n"]) if (rec.get(R.ci[o], {}).get("st", 0) & 7) == 2 and not R.ent.get(R.ci[o])][0]
        cases = [("a trigger card", EX["Thalia's Lieutenant"]), ("an activated card", EX["Starved Rusalka"]), ("a planeswalker", EX["Sorin Markov"]), ("a static card (Equipment)", EX["Bonesplitter"]),
                 ("a replacement card", repl)]
        for label, o in cases:
            open_card(c, o); d = dom_block(c)
            bad = expect_equal(R, o, d, None)
            check("%s (%s): the block matches the one re-derived from the page files" % (label, R.cards[o]["n"]), d is not None and not bad, bad)
            reads.append({"card": R.cards[o]["n"], "label": label})
            if label == "a trigger card":
                check("trigger card: Triggered, two chips, each over its own line, as in the page files", norm_dom(d)[0][0][0] == "Triggered" and len(norm_dom(d)[0][0][1]) == 2)
                check("the block sits under 'In these groups' and above 'Report a problem'", c.js("(()=>{const i=document.querySelector('.tinfo');const h=[...i.querySelectorAll('h3')].map(x=>x.textContent.split('·')[0].trim());const r=i.querySelector('a[data-report]').parentElement;const m=i.querySelector('.mabl');return h[0]==='In these groups'&&h[1]==='Abilities'&&m.nextElementSibling===r})()"))
            if label == "a planeswalker":
                check("planeswalker: one Loyalty chip over three lines", [len(ch) for ch, ls, mo in norm_dom(d)[0][0][1]] == [1] and len(norm_dom(d)[0][0][1][0][1]) == 3)
            close_modal(c)
        # no entries: each wording
        for label, o, want in (("an instant (Lightning Bolt)", EX["Lightning Bolt"], NOTE[1]), ("keyword abilities only (%s)" % R.cards[st4]["n"], st4, NOTE[4]), ("not read (%s)" % R.cards[st3]["n"], st3, NOTE[3]), ("read, no page (%s)" % R.cards[st2]["n"], st2, NOTE[2])):
            open_card(c, o); d = dom_block(c)
            notes = norm_dom(d)[2] if d else []
            check("no entries, %s: the note reads '%s…'" % (label, want[:40]), d is not None and want in notes and not norm_dom(d)[0], notes)
            close_modal(c)
        ft = byname["Fortune Teller"]
        open_card(c, ft); dft = dom_block(c)
        check("a non-spell with a spell-kind ability (Fortune Teller, an Attraction) is not told it is a spell", dft is not None and NOTE[1] not in norm_dom(dft)[2] and NOTE[2] in norm_dom(dft)[2], norm_dom(dft)[2] if dft else None)
        close_modal(c)
        open_card(c, EX["Grizzly Bears"], wait_block=False)
        check("a card with no rules text: no Abilities block (the groups line already says so)", dom_block(c) is None and "no rules text" in c.js("document.querySelector('.tinfo').textContent"))
        close_modal(c)
        # two-faced with Flip
        o = EX["Ulvenwald Abomination"]
        open_card(c, o, faced=True)
        d0 = dom_block(c); name0 = c.js("document.querySelector('.tinfo h2').textContent")
        check("two-faced: opens on the first face (%s) and the block names it" % name0, name0 == "Ulvenwald Captive" and "front face" in d0["h3"], (name0, d0["h3"]))
        check("two-faced, front face: entries match the ones whose lines are on the front face's text", not expect_equal(R, o, d0, 0))
        click(c, ".flipbtn"); c.pump(0.6)
        d1 = dom_block(c)
        check("two-faced after Flip: the block follows to the back face (%s)" % c.js("document.querySelector('.tinfo h2').textContent"), "back face" in d1["h3"] and not expect_equal(R, o, d1, 1), d1["h3"])
        n0, n1 = norm_dom(d0)[0], norm_dom(d1)[0]
        check("two-faced: the two faces show different entries (front %s, back %s)" % ([[x[0][0][1] for x in it] for _, it in n0], [[x[0][0][1] for x in it] for _, it in n1]), n0 != n1)
        click(c, ".flipbtn"); c.pump(0.6)
        check("two-faced: Flip back restores the front block", norm_dom(dom_block(c)) == norm_dom(d0))
        close_modal(c)
        # adventure / one-part card: second half has no entries
        one = [x for x in R.faces if x in R.cards and len(R.cards[x]["t"].split("\n//\n")) == 1 and R.ci[x] in R.ent][0]
        open_card(c, one, faced=True)
        dd = dom_block(c); click(c, ".flipbtn"); c.pump(0.6); d2 = dom_block(c)
        check("a one-part two-faced card (%s): entries on the first half; the other half says there are none" % R.cards[one]["n"], dd and norm_dom(dd)[0] and d2 and not norm_dom(d2)[0] and "No ability pages on this face." in norm_dom(d2)[2], norm_dom(d2)[2] if d2 else None)
        close_modal(c)
        # chip click opens the page
        o = EX["Thalia's Lieutenant"]
        open_card(c, o)
        key = c.js("document.querySelector('.mabl .chip.ab').dataset.go")
        line = c.js("document.querySelector('.mabl .maent .maln').textContent")
        click(c, ".mabl .chip.ab"); c.wait("!document.getElementById('panel').classList.contains('tpend') && selected==%s && typeof TF!=='undefined' && document.querySelector('#list [data-oid]')!==null" % json.dumps(key), 60); c.pump(0.6)
        check("chip click: the modal closes and the page %s opens with the card on it (and the page head says so)" % key, c.js("document.querySelector('.tmodal').hidden===true && selected==%s && AP.pageOids(%s).indexOf(%s)>=0 && /ETB|Enters the battlefield/.test(document.getElementById('panel').textContent)" % (json.dumps(key), json.dumps(key), json.dumps(o))))
        check("chip click on an ability page: no pin and no tab are left set (PINNEXT, SCWANT: %s, %s)" % (jx(c, "PINNEXT"), jx(c, "SCWANT")), jx(c, "PINNEXT") is None and jx(c, "SCWANT") is None)
        # a stale SCWANT (set by hand, as the modal's handler used to leave it) does no harm
        c.js("SCWANT={k:%s,tab:'matches'}" % json.dumps(key))
        mark2 = s.mark()
        dk = R_REF().pages["draw-cards"]["key"]
        c.js("show(%s)" % json.dumps(dk)); c.wait("!document.getElementById('panel').classList.contains('tpend') && typeof TF!=='undefined' && TF.full().length>0", 60); c.pump(1.0)
        check("stale SCWANT: another group page opens on its usual tab (SCCUR tab: %s) and is not pushed to 'matches'" % jx(c, "SCCUR&&SCCUR.tab"), jx(c, "SCCUR") is None or c.js("SCCUR.tab") == "members")
        c.js("SCWANT={k:%s,tab:'matches'}" % json.dumps(key))
        c.js("show(%s)" % json.dumps(key)); c.wait("selected==%s && !document.getElementById('panel').classList.contains('tpend')" % json.dumps(key), 60); c.pump(0.8)
        check("stale SCWANT: opening the ability page itself shows the page with no tab bar and no error", c.js("!document.getElementById('sctabs') && selected==%s && AP.pageOids(%s).length>100" % (json.dumps(key), json.dumps(key))) and not s.console(mark2), s.console(mark2)[:2])
        # keyword chip
        kwcard = [x for x in R.oids if R.ci[x] in R.ent and R.kw.get(x)][0]
        open_card(c, kwcard)
        kkey = c.js("(document.querySelector('.mabl .chip.kw')||{dataset:{}}).dataset.go")
        click(c, ".mabl .chip.kw"); c.wait("selected==%s && !document.getElementById('panel').classList.contains('tpend')" % json.dumps(kkey), 60); c.pump(0.6)
        check("keyword chip %s opens the existing keyword page" % kkey, kkey.startswith("yk:") and c.js("selected==%s && /Keyword/.test(document.getElementById('panel').textContent)" % json.dumps(kkey)))
        reqs = s.net(mark)
        fails = [r for r in reqs if r["failed"] or (r["status"] and r["status"] >= 400)]
        check("no failed request (%d requests since boot)" % len(reqs), not fails, fails[:3])
        posts = [r for r in reqs if r["method"] != "GET"]
        check("only GET requests", not posts)
        check("cards.json was requested once, at the first card", len([r for r in reqs if r["url"].endswith("/ability_pages/cards.json")]) == 1)
        check("no console errors on desktop", not s.console(), s.console()[:3])
        # 40 modals
        rnd = random.Random(SEED_40)
        pickd = rnd.sample(R.oids, 40)
        nbad, shown, none = [], 0, 0
        for o in pickd:
            faced = o in R.faces
            open_card(c, o, wait_block=False, faced=faced)
            c.pump(0.5)
            d = dom_block(c)
            face = None
            if faced:
                face = int(c.js("Number(document.querySelector('.flipbtn[data-face]').getAttribute('data-face'))"))
            if d is None:
                rows, kw = R.block(o, face)
                if rows or kw or R.cards[o]["t"].strip():
                    nbad.append((R.cards[o]["n"], "no block drawn"))
                none += 1
            else:
                shown += 1
                bad = expect_equal(R, o, d, face)
                if bad:
                    nbad.append((R.cards[o]["n"], bad))
            kinds, kw, notes = norm_dom(d) if d else ([], [], [])
            reads.append({"card": R.cards[o]["n"], "type": R.cards[o]["ty"], "text": R.cards[o]["t"], "face": face, "entries": [(l, [([n for _, n in ch], ls, mo) for ch, ls, mo in it]) for l, it in kinds], "keywords": [n for _, n in kw], "notes": notes,
                          "h3": d["h3"] if d else None})
            close_modal(c)
        check("40 modals (seed %d): the block drawn equals the one re-derived from the page files in every one (%d with a block, %d without)" % (SEED_40, shown, none), not nbad, nbad[:3])
        check("no console errors after the 40 modals", not s.console(), s.console()[:3])
    finally:
        s.close()
    with open(reads_out, "w", encoding="utf-8") as fh:
        json.dump(reads, fh, ensure_ascii=False, indent=1)
    print("wrote", reads_out)

    # ------------------------------------------------------------ 5. 390 px
    s = T.Session(DIRS["a"], "/reports/browse.html", 390); c = s.c
    try:
        check("390 px: page boots", c.wait(F.READY, 300)); c.pump(1)
        o = EX["Thalia's Lieutenant"]
        open_card(c, o); c.pump(0.4)
        d = dom_block(c)
        check("390 px: folded by default, the summary row shows the count ('%s') and the body is hidden" % d["sum"], d["folded"] and d["sumShown"] and not d["bodyShown"] and "Abilities" in d["sum"] and "2" in d["sum"], d)
        check("390 px: the desktop heading is not shown twice", not c.js("getComputedStyle(document.querySelector('.mabl h3')).display!=='none'"))
        click(c, ".masum"); c.pump(0.3)
        d = dom_block(c)
        check("390 px: a tap on the summary opens the body (chips shown, aria-expanded true)", not d["folded"] and d["bodyShown"] and c.js("document.querySelector('.masum').getAttribute('aria-expanded')") == "true")
        check("390 px: chips are at least 40 px tall (%s)" % [x["h"] for r in d["rows"] if "chips" in r for x in r["chips"]], all(x["h"] >= 40 for r in d["rows"] if "chips" in r for x in r["chips"]))
        check("390 px: nothing scrolls sideways (page and card view)", c.js("document.documentElement.scrollWidth<=window.innerWidth && (()=>{const b=document.querySelector('.tbox');return b.scrollWidth<=b.clientWidth+1})()"))
        click(c, ".masum"); c.pump(0.2)
        check("390 px: a second tap folds it again", dom_block(c)["folded"])
        close_modal(c)
        open_card(c, EX["Sorin Markov"]); c.pump(0.3)
        check("390 px: a new card opens folded again after the person folded it", dom_block(c)["folded"])
        click(c, ".masum"); c.pump(0.2); close_modal(c)
        open_card(c, EX["Thalia's Lieutenant"]); c.pump(0.3)
        check("390 px: a block the person opened stays open for the next card", not dom_block(c)["folded"])
        check("390 px: no console errors", not s.console(), s.console()[:3])
    finally:
        s.close()

    # ------------------------------------------------------------ 6. first load and timing (flag off against flag on, 4x CPU, 9 Mbps / 170 ms, 390 px)
    perf = {}
    if not skip_perf:
        for label, root in (("flag off", DIRS["off"]), ("flag on", DIRS["a"])):
            runs = []
            for _ in range(3):
                s = T.Session(root, "/reports/browse.html", 390, gz=True, throttle=(9000, 170), cpu=4); c = s.c
                try:
                    t0 = time.time()
                    ok = c.wait(F.READY, 900); t_ready = time.time() - t0
                    c.pump(1)
                    boot = [r for r in s.net() if r["url"].startswith(s.base())]
                    m = s.mark()
                    c.js("window.__t0=performance.now();window.__tb=null;new MutationObserver(()=>{if(!window.__tb&&document.querySelector('.tbox .mabl'))window.__tb=performance.now()}).observe(document.body,{subtree:true,childList:true});window.__tc=null;showCardPage(%s).then(()=>{window.__tc=performance.now()})" % json.dumps(EX["Thalia's Lieutenant"]))
                    c.wait("window.__tc!==null" + (" && window.__tb!==null" if root == DIRS["a"] else ""), 900)
                    c.pump(0.5)
                    modal_ms = round(jx(c, "__tc-__t0")); block_ms = round(jx(c, "__tb-__t0")) if root == DIRS["a"] else None
                    second_ms = None
                    if root == DIRS["a"]:
                        close_modal(c)
                        c.js("window.__tb=null;window.__t0=performance.now();showCardPage(%s)" % json.dumps(EX["Sorin Markov"]))
                        c.wait("window.__tb!==null", 900); second_ms = round(jx(c, "__tb-__t0"))
                    runs.append({"ready_s": round(t_ready, 2), "boot_requests": len(boot), "boot_bytes": sum(r["bytes"] or 0 for r in boot), "modal_ms": modal_ms, "first_block_ms": block_ms, "second_block_ms": second_ms,
                                 "later_requests": sorted(r["url"].replace(s.base(), "") for r in s.net(m) if r["url"].startswith(s.base()) and "/card" not in r["url"].split("/")[-1][:0]), "ok": ok})
                finally:
                    s.close()
            perf[label] = runs
            print(label, runs)
        a, b_ = perf["flag on"], perf["flag off"]
        med = lambda L, k: sorted(x[k] for x in L)[len(L) // 2]
        check("first load: boot requests with the flag on are the flag-off ones plus modalabilities.js and .css (%d vs %d)" % (a[0]["boot_requests"], b_[0]["boot_requests"]), a[0]["boot_requests"] == b_[0]["boot_requests"] + 2)
        extra = set(a[0]["later_requests"]) - set(b_[0]["later_requests"])
        check("opening the first card asks for one file more with the flag on: build/ability_pages/cards.json", {u for u in extra if u.endswith(".json")} == {"/build/ability_pages/cards.json"}, sorted(extra))
        print("median ready_s off/on: %s / %s; boot bytes off/on: %s / %s; first card: view %s ms (off) / %s ms (on), block after %s ms; second card block after %s ms" % (
            med(b_, "ready_s"), med(a, "ready_s"), med(b_, "boot_bytes"), med(a, "boot_bytes"), med(b_, "modal_ms"), med(a, "modal_ms"), med(a, "first_block_ms"), med(a, "second_block_ms")))

    # ------------------------------------------------------------ 7. nothing changed that must not change
    after = dict(T.protected())
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    check("corrections/, archive/, the shared scripts and the top-level build files are byte-identical to before (%d hashed)" % len(before), not changed, changed[:4])
    T.test_figures()
    if "--keep" not in sys.argv:
        for dd in DIRS.values():
            shutil.rmtree(dd, ignore_errors=True)
    bad = [n for n, ok, _ in T.RESULTS if not ok]
    print("\n%d checks, %d failed" % (len(T.RESULTS), len(bad)))
    for n in bad:
        print("FAILED:", n)
    sys.exit(1 if bad else 0)


_R = []


def R_REF():
    if not _R:
        import tester_filters_ref as REF
        _R.append(REF.Ref())
    return _R[0]


if __name__ == "__main__":
    main()
