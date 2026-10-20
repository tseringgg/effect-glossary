#!/usr/bin/env python3
"""Headless Edge pass for the "Possible matches" tab (DevTools protocol), against a TEMP corrections file served in place of the real one and a TEMP build of build/suggested_cards served in place of the real one.
The real corrections files are hashed before and after; the test aborts if its corrections path is the real one.

    python src/test_suggested_browser.py        (same needs as src/test_text_browser.py; builds the layer into a temporary folder)

Covered: flag off (the files answer 404): no tab on any group page, one request for the meta file and no more, a remembered "matches" tab ignored; flag on: no page toggle exists, a group with possible matches has two tabs
("Cards in this group" by default, "Possible matches (N)" with N from the meta file), a group with none (and no community-tag block) has no tab, a community-tag group with a tag block but no suggestions has the tab; a group's own
tab is unchanged by switching and never lists a possible match; the group's files are requested only when the tab is opened; the tab's contents (heading, "suggestion" badge, the wording, floor 0.70, already-placed unticked, at most 25
rows, sorted, no member, a reason on every row); the biggest group paging 25 at a time; the floor slider and the count in the tab label; the already-placed tick; Add and Undo (saved in the temp file, counted as the resolver counts,
the six figures unchanged, "Placed here by hand" on the group's own tab after the group is reopened); the community-tag block on a tag group; the tab remembered per browser (also across a reload); a pasted link to the tab and
to the group's own tab; the tab at 390 px (no sideways scroll, touch-size); Find a card does not describe a suggestion as a placement; the page-load cost with and without the files. Clicks are DOM click() calls: no touch, no other browser.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_manual_browser as TB
import manual_common as MC

REAL = os.path.join(MC.HERE, "corrections", "manual_placements.json")
SUGDIR = os.path.join(tempfile.mkdtemp(prefix="sugg_build_"), "suggested_cards")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


class WithSug(TB.Real):                                       # the temporary build stands in for build/suggested_cards
    def translate_path(self, path):
        p = path.split("?")[0]
        if p.startswith("/build/suggested_cards/"):
            return os.path.join(SUGDIR, p[len("/build/suggested_cards/"):].replace("/", os.sep))
        return super().translate_path(path)


class NoSug(TB.Real):                                         # the flag off: the files do not exist
    def do_GET(self):
        if self.path.split("?")[0].startswith("/build/suggested_cards/"):
            self.send_error(404)
            return
        super().do_GET()


def main():
    cor = ("manual_placements.json", "manual_placements.json.bak", "hand_groups.json", "hand_groups.json.bak")
    real_before = tuple(sha(os.path.join(MC.HERE, "corrections", n)) for n in cor)
    assert os.path.abspath(TB.DOC) != os.path.abspath(REAL)
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); import build_suggested_cards as S; S.main(force=True)"], cwd=MC.HERE, capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, SUGGESTED_OUT=SUGDIR, PYTHONIOENCODING="utf-8"))
    assert r.returncode == 0, r.stderr
    meta = json.load(open(os.path.join(SUGDIR, "meta.json"), encoding="utf-8"))
    idx = MC.load_index()
    C, G = idx["cards"], idx["groups"]
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))
        print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)[:300]) if detail else ""))
    q70 = lambda g: meta["groups"][g][1][2] if g in meta["groups"] else 0
    p70 = lambda g: meta["groups"][g][2][2] if g in meta["groups"] else 0
    leaves = [g for g in sorted(meta["groups"]) if g.startswith("leaf:")]
    small = next(g for g in leaves if 3 <= q70(g) <= 8 and p70(g) == 0 and g not in meta["lens"])
    big = max(leaves, key=lambda g: q70(g))
    mixed = next(g for g in leaves if q70(g) >= 2 and 1 <= p70(g) <= 20)
    tagg = next(g for g in sorted(meta["lens"]) if meta["lens"][g][1] >= 40 and meta["lens"][g][2] >= 1 and q70(g) >= 1)
    lens_only = next((g for g in sorted(meta["lens"]) if q70(g) == 0), None)
    none_leaf = next(g for g, v in sorted(G.items()) if g.startswith("leaf:") and v[4] and v[1] >= 5 and q70(g) == 0 and g not in meta["lens"])
    key = lambda g: "l:" + g[5:] if g.startswith("leaf:") else "ct:" + g[4:]
    srvA = TB.Quiet(("127.0.0.1", TB.PORT_A), WithSug)
    srvB = TB.Quiet(("127.0.0.1", TB.PORT_B), NoSug)
    for s_ in (srvA, srvB):
        threading.Thread(target=s_.serve_forever, daemon=True).start()
    edge = subprocess.Popen([TB.EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + tempfile.mkdtemp(), "--remote-debugging-port=%d" % TB.PORT_CDP, "--remote-allow-origins=*",
                             "--window-size=1400,1000", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % TB.PORT_CDP))
                break
            except Exception:
                time.sleep(0.5)
        c = TB.CDP(next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"])
        c.call("Page.enable")
        READY = "document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null && typeof SC !== 'undefined' && !document.getElementById('showhandlab').hidden && !!KFAC && !!HG && !!SIB"

        def load(port, storage=None, frag="", clear=True):
            c.call("Page.navigate", url="about:blank")
            time.sleep(0.4)
            if clear or storage:
                c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % port)
                c.wait("document.readyState === 'complete'", 60)
                c.js(("localStorage.clear(); " if clear else "") + "".join("localStorage.setItem('%s','%s'); " % kv for kv in (storage or {}).items()))
                c.call("Page.navigate", url="about:blank")
                time.sleep(0.3)
            t0 = time.time()
            c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html%s" % (port, frag))
            ok = c.wait(READY, 240)
            return ok, time.time() - t0
        figs = lambda: c.js("[...document.querySelectorAll('#cov > div:not(.basis)')].map(d => d.innerText).join('|')")
        reqs = lambda pat: c.js("performance.getEntriesByType('resource').filter(r => r.name.includes('%s')).length" % pat)
        bytes_ = lambda pat: c.js("performance.getEntriesByType('resource').filter(r => r.name.includes('%s')).reduce((a, r) => a + (r.encodedBodySize || r.transferSize || 0), 0)" % pat)
        tabbar = lambda: c.js("!!document.getElementById('sctabs')")
        tablabel = lambda: c.js("(document.querySelector('#sctabs button[data-sctab=matches]') || {}).textContent || ''")
        active = lambda: c.js("document.querySelector('#sctabs button.on') ? document.querySelector('#sctabs button.on').dataset.sctab : ''")
        listshown = lambda: c.js("!!document.getElementById('list') && getComputedStyle(document.getElementById('list')).display !== 'none'")
        secshown = lambda: c.js("!!document.getElementById('suggsec') && getComputedStyle(document.getElementById('suggsec')).display !== 'none'")
        sel_is = lambda k: c.wait("selected === '%s'" % k, 60)

        def open_group(g, wait_tab=True):
            c.js("show('%s')" % key(g))
            c.wait("selected === '%s' && !!document.getElementById('list')" % key(g), 120)
            time.sleep(0.6)

        def wait_sec():
            return c.wait("!!document.getElementById('suggsec') && !document.getElementById('suggsec').innerText.startsWith('Loading')", 120)
        rows = lambda: c.js("[...document.querySelectorAll('#suggsec .sgrow')].map(e => ({oid: e.dataset.oid, score: e.querySelector('.score') ? parseFloat(e.querySelector('.score').innerText) : null, why: e.querySelector('.why').innerText, add: !!e.querySelector('[data-sact=add]'), "
                            "txt: e.innerText, name: e.querySelector('.nm').innerText}))")
        sectxt = lambda: c.js("document.getElementById('suggsec') ? document.getElementById('suggsec').innerText : ''")
        click_tab = lambda t: c.js("document.querySelector('#sctabs button[data-sctab=%s]').click()" % t)

        # ---------------------------------------------------------------- flag off
        ok, boot_off = load(TB.PORT_B, {"groupTab": "matches"})
        check("0 flag off: the page boots (%.1f s to a ready tree)" % boot_off, ok)
        open_group(small)
        check("0 flag off: no tab on a group page, whatever tab was remembered", c.js("SC") is None and tabbar() is False and c.js("!document.getElementById('suggsec')") is True and listshown() is True)
        check("0 flag off: the only request for these files is the one meta file (%d), and no group file" % reqs("suggested_cards/"), reqs("suggested_cards/") <= 1 and reqs("suggested_cards/g/") == 0 and reqs("suggested_cards/t/") == 0)
        req_off = c.js("performance.getEntriesByType('resource').length")
        # ---------------------------------------------------------------- flag on: page load and the tab bar
        ok, boot_on = load(TB.PORT_A)
        check("1 flag on: the page boots (%.1f s against %.1f s with the flag off)" % (boot_on, boot_off), ok)
        mb = bytes_("suggested_cards/meta.json")
        check("1 page load: the only added request is meta.json (%.0f KB); no group file is read at boot (%d requests more than flag off)" % (mb / 1024.0, c.js("performance.getEntriesByType('resource').length") - req_off),
              reqs("suggested_cards/") == 1 and reqs("suggested_cards/g/") == 0 and reqs("suggested_cards/t/") == 0 and mb < 200 * 1024, (mb, reqs("suggested_cards/")))
        check("1 there is no 'Also show suggested cards' toggle on the page", c.js("!document.getElementById('showsugg') && !document.getElementById('showsugglab') && !document.body.innerText.includes('Also show suggested cards')") is True)
        figs0 = figs()
        check("1 the six figures are shown", figs0.count("Basis:") == 6, figs0.count("Basis:"))
        open_group(small)
        check("1 a group with possible matches has two tabs; the group's own cards are the default (%s)" % tablabel(), tabbar() and active() == "members" and listshown() and not secshown() and tablabel() == "Possible matches (%d)" % q70(small) and
              c.js("document.querySelector('#sctabs button[data-sctab=members]').textContent") == "Cards in this group", (tablabel(), q70(small)))
        check("1 the tab bar is drawn from the meta file alone: no group file requested yet", reqs("suggested_cards/g/") == 0 and reqs("suggested_cards/t/") == 0)
        list_before = c.js("document.getElementById('list').innerHTML")
        open_group(none_leaf)
        check("2 a group with no possible match and no community-tag block (%s) has no tab" % G[none_leaf][0][:30], tabbar() is False and listshown())
        if lens_only:
            open_group(lens_only)
            check("2 a community-tag group with a tag block but no suggestion (%s) still has the tab, labelled (0)" % G[lens_only][0][:30], tabbar() and tablabel() == "Possible matches (0)", tablabel())
        # ---------------------------------------------------------------- switching
        open_group(small)
        click_tab("matches")
        ok = wait_sec()
        t = sectxt()
        rs = rows()
        check("3 the tab shows the section: heading, 'suggestion' badge, and the wording 'Suggested cards. Not members. Not counted in any figure.'", ok and "Suggested cards" in t and c.js("!!document.querySelector('#suggsec .b-sugg')") and "Not members. Not counted in any figure." in t, t[:160])
        check("3 the group's own list is hidden, not changed", not listshown() and secshown() and active() == "matches" and c.js("document.getElementById('list').innerHTML") == list_before)
        check("3 the floor starts at 0.70 and 'include already-placed cards' is unticked", c.js("document.querySelector('#suggsec [data-sctl=floor]').value") == "0.7" and c.js("document.querySelector('#suggsec [data-sctl=inc]').checked") is False)
        scores = [x["score"] for x in rs]
        members = {o for o, cc in C.items() if any(x[0] == small for x in cc[3])}
        check("3 %d rows, all at 0.70 or more, sorted by score, none a member, each with a reason and an Add button, none an already-placed card" % len(rs),
              1 <= len(rs) <= 25 and all(s >= 0.7 - 1e-9 for s in scores) and scores == sorted(scores, reverse=True) and not [x for x in rs if x["oid"] in members] and all(x["why"] and x["add"] for x in rs)
              and all(C[x["oid"]][1] in "utam" for x in rs), (len(rs), scores[:5]))
        click_tab("members")
        check("3 back on the group's own tab: the list is shown and unchanged, and no possible match is in it", listshown() and not secshown() and c.js("document.getElementById('list').innerHTML") == list_before
              and not (set(x["oid"] for x in rs) & set(c.js("[...document.querySelectorAll('#list .card')].map(e => e.dataset.oid)"))))
        # ---------------------------------------------------------------- the biggest group: the files load when the tab opens, 25 at a time
        open_group(big)
        r0, b0 = reqs("suggested_cards/g/"), bytes_("suggested_cards/g/")
        check("4 biggest group (%s, %d at 0.70): own tab first, label %s, no group file read yet" % (G[big][0][:30], q70(big), tablabel()), tabbar() and active() == "members" and tablabel() == "Possible matches (%d)" % q70(big) and reqs("suggested_cards/g/") == r0)
        t0 = time.time(); click_tab("matches"); wait_sec()
        dt = time.time() - t0
        nb = bytes_("suggested_cards/g/") - b0
        check("4 opening the tab reads the group's file (%.0f KB, %.1f s) and shows 25 rows" % (nb / 1024.0, dt), len(rows()) == 25 and nb > 0 and nb < 400 * 1024 and reqs("suggested_cards/g/") > r0, (len(rows()), nb))
        c.js("document.querySelector('#suggsec [data-sact=more]').click()")
        c.wait("document.querySelectorAll('#suggsec .sgrow').length === 50", 30)
        sc50 = [x["score"] for x in rows()]
        check("4 'Show 25 more' adds 25 (50 shown) and keeps the order; the page says how many there are", len(sc50) == 50 and sc50 == sorted(sc50, reverse=True) and "showing the first 50" in sectxt())
        # ---------------------------------------------------------------- the floor and the label
        n_of = lambda: int(c.js("(/(\\d[\\d,]*) cards? at ([0-9.]+) or higher/.exec(document.getElementById('suggsec').innerText) || [0,'-1'])[1].replace(/,/g, '')"))
        setfloor = lambda v: c.js("(function () { var e = document.querySelector('#suggsec [data-sctl=floor]'); e.value = '%s'; e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); })()" % v)
        nn70 = n_of()
        setfloor("0.9")
        n90, lab90, r90 = n_of(), tablabel(), rows()
        setfloor("0.5")
        n50, lab50 = n_of(), tablabel()
        check("5 the floor slider: %d at 0.90 <= %d at 0.70 <= %d at 0.50; the tab label follows (%s, %s)" % (n90, nn70, n50, lab90, lab50), n90 <= nn70 <= n50 and n90 < n50 and all(x["score"] >= 0.9 - 1e-9 for x in r90)
              and lab90 == "Possible matches (%d)" % meta["groups"][big][1][4] and lab50 == "Possible matches (%d)" % meta["groups"][big][1][0], (n90, nn70, n50))
        setfloor("0.7")
        # ---------------------------------------------------------------- already-placed cards
        open_group(mixed)
        click_tab("matches"); wait_sec()
        n_before, lab_before = len(rows()), tablabel()
        hid_note = "already-placed" in sectxt()
        c.js("document.querySelector('#suggsec [data-sctl=inc]').click()")
        c.wait("document.querySelector('#suggsec [data-sctl=inc]').checked", 20)
        time.sleep(1.5)
        rs = rows()
        check("6 'include already-placed cards' (%s): the hidden-count note comes first (%s); ticking adds placed cards (%d -> %d rows) that say an Add is recorded and counted nowhere; the label counts them (%s -> %s)" % (G[mixed][0][:30], hid_note, n_before, len(rs), lab_before, tablabel()),
              hid_note and len(rs) > n_before and any("counted nowhere" in x["txt"] for x in rs) and all(("counted nowhere" in x["txt"]) == (C[x["oid"]][1] not in "utam") for x in rs) and tablabel() != lab_before, (n_before, len(rs)))
        c.js("document.querySelector('#suggsec [data-sctl=inc]').click()")
        time.sleep(0.5)
        check("6 unticking hides them again", len(rows()) == n_before and tablabel() == lab_before)
        # ---------------------------------------------------------------- Add and Undo
        open_group(small)
        click_tab("matches"); wait_sec()
        rs = rows()
        first = rs[0]
        c.js("document.querySelector('#suggsec .sgrow[data-oid=\"%s\"] [data-sact=add]').click()" % first["oid"])
        c.wait("Object.keys(MDOC.edits).length === 1 && /saved/.test(LASTMSG)", 30)
        time.sleep(0.5)
        d = TB.doc()
        entry = d["edits"].get(first["oid"], {}).get("groups", {}).get(small)
        check("7 Add from the tab: saved in the temporary file for this card and group, as a single placement (no batch field)", entry and entry["action"] == "add" and "batch" not in entry and len(d["edits"]) == 1, entry)
        rowtxt = c.js("document.querySelector('#suggsec .sgrow[data-oid=\"%s\"]').innerText" % first["oid"])
        check("7 the row turns into 'added by hand' with an Undo button (it stays in place)", "added by hand" in rowtxt and c.js("!!document.querySelector('#suggsec .sgrow[data-oid=\"%s\"] [data-sact=undo]')" % first["oid"]), rowtxt[:80])
        st = C[first["oid"]][1]
        cnt = c.js("MRES.counts")
        want = {"u": cnt["placed_by_hand_new"] == 1, "t": cnt["confirmed_by_hand"] == 1, "a": cnt["confirmed_by_hand"] == 1, "m": cnt["confirmed_by_hand"] == 1}[st]
        check("7 counted on the hand line only, as the resolver counts it (state %s)" % st, want, cnt)
        check("7 the six figures are unchanged by it", figs() == figs0, (figs()[:100], figs0[:100]))
        click_tab("members")
        check("7 the group's own tab does not list the added card until the group is reopened (members and counts unchanged)", c.js("document.getElementById('list').innerHTML") == list_before)
        click_tab("matches")
        c.js("document.querySelector('#suggsec .sgrow[data-oid=\"%s\"] [data-sact=undo]').click()" % first["oid"])
        c.wait("Object.keys(MDOC.edits).length === 0", 30)
        time.sleep(0.5)
        check("7 Undo removes the edit from the temporary file and the row offers Add again", not TB.doc()["edits"] and c.js("!!document.querySelector('#suggsec .sgrow[data-oid=\"%s\"] [data-sact=add]')" % first["oid"]))
        c.js("document.querySelector('#suggsec .sgrow[data-oid=\"%s\"] [data-sact=add]').click()" % first["oid"])
        c.wait("Object.keys(MDOC.edits).length === 1", 30)
        open_group(small)
        wait_sec()
        click_tab("members")
        check("7 reopening the group: the added card is under 'Placed here by hand' on the group's own tab, and no longer a possible match", first["oid"] not in [x["oid"] for x in rows()] and c.js("document.getElementById('list').innerText.includes('Placed here by hand')"))
        c.js("sendEdit({oid: '%s', group: '%s', action: 'clear', note: ''}, true)" % (first["oid"], small))
        c.wait("Object.keys(MDOC.edits).length === 0", 30)
        # ---------------------------------------------------------------- the community-tag block
        open_group(tagg)
        click_tab("matches"); wait_sec()
        t = sectxt()
        slug = meta["lens"][tagg][3]
        lr = c.js("[...document.querySelectorAll('#suggsec .sgrow')].map(e => ({oid: e.dataset.oid, score: !!e.querySelector('.score'), txt: e.innerText}))")
        heads = c.js("[...document.querySelectorAll('#suggsec h3')].map(h => h.innerText)")
        check("8 tag group: a 'Community tag' block names the tag (%s) and says a tag is a hint, not a placement, not counted" % slug, any(("Community tag: " + slug) in h for h in heads) and "not a placement" in t and "Not counted in any figure" in t, heads)
        lens_rows = [x for x in lr if not x["score"]]
        check("8 tag group: tag rows carry no score and say they carry the tag; no card is in both blocks", len(lens_rows) >= 1 and all("community tag" in x["txt"] for x in lens_rows) and len({x["oid"] for x in lr}) == len(lr), (len(lens_rows), len(lr)))
        lo = lens_rows[0]["oid"]
        c.js("document.querySelector('#suggsec .sgrow[data-oid=\"%s\"] [data-sact=add]').click()" % lo)
        c.wait("Object.keys(MDOC.edits).length === 1", 30)
        e2 = TB.doc()["edits"].get(lo, {}).get("groups", {}).get(tagg)
        check("8 Add from the tag block is the same single placement into the tag group", e2 and e2["action"] == "add" and "batch" not in e2, e2)
        c.js("document.querySelector('#suggsec .sgrow[data-oid=\"%s\"] [data-sact=undo]').click()" % lo)
        c.wait("Object.keys(MDOC.edits).length === 0", 30)
        check("8 Undo from the tag block removes it", not TB.doc()["edits"])
        # ---------------------------------------------------------------- Find a card
        c.js("document.getElementById('q').value=''")
        c.js("document.getElementById('q').focus()")
        c.type(C[first["oid"]][0])
        c.wait("document.getElementById('findres').innerText.length > 20", 90)
        fr = c.js("document.getElementById('findres').innerText")
        check("9 Find a card does not mention possible matches or describe one as a placement (%s: no 'Placed by hand', the group %r is not named)" % (C[first["oid"]][0], G[small][0][:30]),
              "Placed by hand" not in fr and G[small][0] not in fr and "ossible match" not in fr, fr[:160].replace(chr(10), " "))
        # ---------------------------------------------------------------- tab memory
        load(TB.PORT_A)
        open_group(small)
        check("10 fresh browser: the group's own tab is the default", active() == "members")
        click_tab("matches"); wait_sec()
        check("10 choosing the tab stores it per browser (localStorage groupTab)", c.js("localStorage.getItem('groupTab')") == "matches")
        open_group(big)
        wait_sec()
        check("10 another group with possible matches opens on the tab", active() == "matches" and secshown() and not listshown())
        open_group(none_leaf)
        check("10 a group with no possible match opens on its own cards, whatever is remembered", tabbar() is False and listshown())
        load(TB.PORT_A, clear=False)
        open_group(small)
        wait_sec()
        check("10 the choice survives a reload of the page", active() == "matches" and secshown())
        click_tab("members")
        check("10 switching back to the group's own cards is remembered too", c.js("localStorage.getItem('groupTab')") == "members" and listshown())
        # ---------------------------------------------------------------- deep links
        gk = key(small)
        load(TB.PORT_A, {"groupTab": "members"}, "#" + gk.replace(":", "%3A") + "&tab=matches")
        wait_sec()
        check("11 a pasted link to the tab (#%s&tab=matches) opens it, although the remembered tab is the group's own" % gk, sel_is(gk) and active() == "matches" and secshown() and not listshown(), c.js("location.hash"))
        check("11 the address keeps the tab while it is open", c.js("location.hash").endswith("&tab=matches"), c.js("location.hash"))
        click_tab("members")
        check("11 switching to the group's own cards drops the tab from the address", "&tab=" not in c.js("location.hash") and listshown(), c.js("location.hash"))
        load(TB.PORT_A, {"groupTab": "matches"}, "#" + gk.replace(":", "%3A") + "&tab=members")
        time.sleep(1.0)
        check("11 a link with &tab=members opens the group's own cards, although the remembered tab is the other one", sel_is(gk) and active() == "members" and listshown(), c.js("location.hash"))
        load(TB.PORT_A, {"groupTab": "members"}, "#" + gk.replace(":", "%3A"))
        time.sleep(1.0)
        check("11 a plain link (no tab) opens the remembered tab (the group's own cards here)", sel_is(gk) and active() == "members" and listshown())
        # ---------------------------------------------------------------- 390 px
        load(TB.PORT_A, {"groupTab": "matches"})
        c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
        open_group(mixed)
        wait_sec()
        time.sleep(1.0)
        geo = c.js("({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, btn: Math.min.apply(null, [...document.querySelectorAll('#suggsec button, #sctabs button')].map(b => b.getBoundingClientRect().height)), "
                   "rng: document.querySelector('#suggsec [data-sctl=floor]').getBoundingClientRect().height, tabs: document.getElementById('sctabs').getBoundingClientRect().width})")
        check("12 390 px: no sideways scroll", geo["sw"] <= geo["cw"] + 1, geo)
        check("12 390 px: tabs, buttons and the slider are touch-size (44 px)", geo["btn"] >= 43 and geo["rng"] >= 43, geo)
        if TB.SHOTS:
            import base64
            open(os.path.join(TB.SHOTS, "possible_matches_390.png"), "wb").write(base64.b64decode(c.call("Page.captureScreenshot", format="png")["data"]))
        c.call("Emulation.clearDeviceMetricsOverride")
    finally:
        edge.terminate()
    real_after = tuple(sha(os.path.join(MC.HERE, "corrections", n)) for n in cor)
    check("13 the real corrections files (manual_placements.json, hand_groups.json and their backups) are byte-identical before and after", real_before == real_after)
    bad = [r for r in results if not r[1]]
    print("\n%d checks, %d failed" % (len(results), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
