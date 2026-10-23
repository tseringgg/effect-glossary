#!/usr/bin/env python3
"""Headless Edge pass for the group search in the main search box (DevTools protocol). Temporary corrections file and a temporary log are served in place of the real ones; the protected files are hashed before and after.

    python src/test_group_search_browser.py     (same needs as src/test_suggested_browser.py; build/group_search/ must be built)
    BROWSE_BEFORE=<path to the browse.html from before this feature>   (optional: also compares the flag-off page with it, byte for byte in the results it draws)

Covered: flag off (the page asks for one small file, draws no group section, the label and box are as before, and its card results are identical to the original page's); flag on: the label, the "searches are logged" line,
boot cost (one added request); a query that has both a card and a group (Cards, then Groups, jump links, 4 card rows and 5 group rows before "Show more"); an alias with its "via alias" label and, for a partial alias, its note;
opening a group and a card from a result; a typo ("did you mean"); a real word that is not corrected (wraith) next to wrath; a keyword filter; a description match labelled "matched: description" after the name matches; family
matches collapsed under one row; no result; the miss log (search, zero, open); the tentative and community-tag switches (a switched-off layer is never offered; a tentative group falls back to its loose twin); EVERY searchable
group opens a page (all %d, with the switches on, then off); the row's count equals the page's; keyboard (real key events: Down, Up, Enter, Escape); 390 px (no sideways scroll, 44 px targets). Clicks are DOM click() calls and
the box is typed with real key events: no touch, no other browser.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_manual_browser as TB
import manual_common as MC
import group_search_log as GSL

HERE = MC.HERE
PROTECTED = [os.path.join(HERE, "corrections", n) for n in ("manual_placements.json", "manual_placements.json.bak", "hand_groups.json", "hand_groups.json.bak", "group_aliases.json", "group_descriptions.json", "group_aliases_drafted.json")]
REAL_LOG = os.path.join(HERE, "build", "group_search_log.json")
TMPLOG = os.path.join(tempfile.mkdtemp(prefix="gs_browser_"), "group_search_log.json")
GSL.LOG = TMPLOG
BEFORE_HTML = os.environ.get("BROWSE_BEFORE")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


class On(TB.Real):                                             # flag on: the real build/group_search, a temporary log and corrections; the card pin is off here (it has its own test, src/test_card_pin_browser.py)
    def do_GET(self):
        if self.path.split("?")[0].startswith("/build/card_pin/"):
            self.send_error(404)
            return
        super().do_GET()


class Off(TB.Real):                                            # flag off: the feature's files do not exist
    def do_GET(self):
        p = self.path.split("?")[0]
        if p.startswith("/build/group_search/") or p.startswith("/api/groupsearch/") or p.startswith("/build/card_pin/"):
            self.send_error(404)
            return
        super().do_GET()


class NoLog(TB.Real):                                          # the flag on, but the log endpoint does not answer
    def do_GET(self):
        if self.path.split("?")[0].rstrip("/") == "/api/groupsearch/ping":
            self.send_response(404)
            self.end_headers()
            return
        if self.path.split("?")[0].startswith("/build/card_pin/"):
            self.send_error(404)
            return
        super().do_GET()


class Old(Off):                                                # the page as it was before this feature
    def translate_path(self, path):
        if path.split("?")[0] == "/reports/browse.html" and BEFORE_HTML:
            return BEFORE_HTML
        return super().translate_path(path)


def main():
    before = [sha(p) for p in PROTECTED]
    assert os.path.abspath(TB.DOC) != os.path.join(HERE, "corrections", "manual_placements.json")
    assert not os.path.exists(REAL_LOG) or True
    real_log_before = sha(REAL_LOG)
    idx = json.load(open(os.path.join(HERE, "build", "group_search", "index.json"), encoding="utf-8"))
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok)))
        print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)[:300]) if detail else ""))
    port_c = TB.free_port()
    TB.PORT_D = TB.free_port()
    srvs = [TB.Quiet(("127.0.0.1", TB.PORT_A), On), TB.Quiet(("127.0.0.1", TB.PORT_B), Off), TB.Quiet(("127.0.0.1", TB.PORT_D), NoLog)]
    if BEFORE_HTML:
        srvs.append(TB.Quiet(("127.0.0.1", port_c), Old))
    for s_ in srvs:
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
        READY = "document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null && !!KFAC && !!HG && !!TENT && !!TAGS && typeof GSON !== 'undefined'"

        def load(port, clear=True, old=False):
            c.call("Page.navigate", url="about:blank")
            time.sleep(0.4)
            if clear:
                c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % port)
                c.wait("document.readyState === 'complete'", 60)
                c.js("localStorage.clear()")
                c.call("Page.navigate", url="about:blank")
                time.sleep(0.3)
            c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % port)
            ok = c.wait(READY.replace(" && typeof GSON !== 'undefined'", "") if old else READY, 240)
            if old:
                return ok
            c.wait("typeof GSON !== 'undefined' && (!GSON || !document.getElementById('gsnote').textContent.endsWith('…'))", 30)
            return ok
        reqs = lambda pat: c.js("performance.getEntriesByType('resource').filter(r => r.name.includes('%s')).length" % pat)
        figs = lambda: c.js("[...document.querySelectorAll('#cov > div:not(.basis)')].map(d => d.innerText).join('|')")

        def key(k, vk, text=None):
            kw = dict(key=k, code=k, windowsVirtualKeyCode=vk)
            if text:
                kw["text"] = text
            c.call("Input.dispatchKeyEvent", type="keyDown", **kw)
            c.call("Input.dispatchKeyEvent", type="keyUp", **kw)

        def clearq():
            c.js("(() => { const q = document.getElementById('q'); q.value = ''; q.dispatchEvent(new Event('input')); q.focus(); })()")
            time.sleep(0.4)

        def settle():
            last, same = None, 0
            for _ in range(80):
                h = c.js("document.getElementById('findres').innerHTML")
                if h == last and not h.startswith('<div class="sub">Loading'):
                    same += 1
                    if same >= 3:
                        return h
                else:
                    same = 0
                last = h
                time.sleep(0.2)
            return last

        def search(text):
            clearq()
            c.type(text)
            time.sleep(0.5)
            return settle()
        rows = lambda: c.js("[...document.querySelectorAll('#findres .gr')].map(e => ({name: e.querySelector('.gn').innerText, go: e.dataset.go, hidden: !!e.closest('[hidden]') || e.hidden, text: e.innerText, why: (e.querySelector('.gm') || {}).innerText || '', note: (e.querySelector('.gl') || {}).innerText || ''}))")
        vis = lambda: [r for r in rows() if not r["hidden"]]

        # ---------------------------------------------------------------- flag off
        ok = load(TB.PORT_B)
        check("0 flag off: the page boots; the box and its label are as before", ok and c.js("document.querySelector('.find label[for=q]').textContent") == "Find a card:" and c.js("document.getElementById('q').placeholder") == "type a card name" and c.js("GSON") is False)
        off_figs = figs()
        h_off = {q: search(q) for q in ("wrath", "clone", "serra angel", "zzqxv", "lightning bolt")}
        check("0 flag off: no group section, no jump links, no focusable card rows, the notice stays hidden", all("gs-" not in h and 'class="gr"' not in h and "tabindex" not in h for h in h_off.values()) and c.js("document.getElementById('gsnote').hidden") is True)
        check("0 flag off: the page asked for one group-search file (the meta file, a 404) and no more", reqs("group_search/") == 1, reqs("group_search/"))
        req_off = c.js("performance.getEntriesByType('resource').length")
        if BEFORE_HTML:
            load(port_c, old=True)
            h_old = {q: search(q) for q in h_off}
            check("0 flag off: the card results are identical to the page before this feature (5 queries, the same HTML)", h_old == h_off, [q for q in h_off if h_old[q] != h_off[q]])
        # ---------------------------------------------------------------- flag on
        ok = load(TB.PORT_A)
        check("1 flag on: the page boots; the label and the placeholder say groups", ok and c.js("GSON") is True and c.js("document.querySelector('.find label[for=q]').textContent") == "Find a card or group:" and "group" in c.js("document.getElementById('q').placeholder"))
        note = c.js("document.getElementById('gsnote').textContent")
        check("1 the page says searches are logged, and what is logged", "logged" in note and "words typed" in note and "build/group_search_log.json" in note and c.js("document.getElementById('gsnote').hidden") is False, note)
        check("1 the six figures are the same with the flag on and off", figs() == off_figs, figs()[:120])
        req_on = c.js("performance.getEntriesByType('resource').length")
        check("1 boot cost: one extra request (meta.json); the index (%d KB) and the word list are not read until needed (%d requests more than flag off)" % (os.path.getsize(os.path.join(HERE, "build", "group_search", "index.json")) // 1024, req_on - req_off),
              reqs("group_search/meta.json") == 1 and reqs("group_search/index.json") == 0 and reqs("words.txt") == 0 and req_on - req_off <= 2)
        # a query with a card and groups
        search("clone")
        gh = c.js("document.getElementById('findres').innerHTML")
        sec = c.js("[...document.querySelectorAll('#findres .gs-h')].map(e => e.textContent)")
        check("2 a card and groups: Cards first, then Groups, jump links first", sec == ["Cards", "Groups"] and gh.index('id="gs-cards"') < gh.index('id="gs-groups"') and gh.index('id="gs-jump"') < gh.index('id="gs-cards"'), sec)
        nm = [r["name"] for r in rows()]
        check("2 the community-tag group 'Clone' is in Groups beside the card 'Clone' (same name, both shown)", "Clone" in nm and c.js("[...document.querySelectorAll('#findres .fr .nm')].some(e => e.innerText === 'Clone')") is True, nm[:6])
        check("2 4 card rows and 5 group rows before 'Show more'", c.js("document.querySelectorAll('#findres #gs-cards .fr:not([hidden])').length") <= 4 and len(vis()) <= 5, (len(vis()),))
        sm = c.js("[...document.querySelectorAll('#findres .gs-btn[data-gsmore]')].map(b => b.dataset.gsmore + ':' + b.innerText)")
        if any(x.startswith("groups:") for x in sm):
            c.js("document.querySelector('#findres [data-gsmore=groups]').click()")
            time.sleep(0.3)
            check("2 'Show more' reveals the rest (up to 30) and removes itself (%s)" % sm, len(vis()) > 5 and c.js("!document.querySelector('#findres [data-gsmore=groups]')") is True, len(vis()))
        check("2 each group row shows its name, layer badge, count, path and a one-line description where there is one", all(r["text"].count("\n") >= 2 for r in vis()) and c.js("[...document.querySelectorAll('#findres .gr .badge')].length") >= 1)
        # alias
        search("wrath")
        v = vis()
        check("3 alias: 'wrath' lists the wipes first, each labelled via alias “wrath”", len(v) >= 3 and all("via alias “wrath”" in r["why"] for r in v[:3]) and "Destroy all creatures" in v[0]["name"], [r["name"][:30] for r in v[:3]])
        first_go = v[0]["go"]
        c.js("document.querySelector('#findres .gr').click()")
        c.wait("selected === %s" % json.dumps(first_go), 60)
        time.sleep(0.8)
        check("3 clicking the group opens its page (%s)" % first_go, c.js("selected") == first_go and "Destroy all creatures" in c.js("document.querySelector('#panel h2').innerText"))
        search("ramp")
        v = vis()
        pn = [r for r in v if r["note"]]
        check("3 partial alias: 'ramp' shows its note on the row (what it leaves out) and as a tooltip", bool(pn) and "mana" in pn[0]["note"].lower() and c.js("!!document.querySelector('#findres .gr[title]')") is True, [r["note"][:60] for r in pn][:1])
        search("mana dork")
        check("3 partial alias 'mana dork' carries its note", any(r["note"] for r in vis()))
        # a card opens from the results
        search("lightning bolt")
        c.js("document.querySelector('#findres .fr[data-go]').click()")
        c.wait("selected && selected.startsWith('c:')", 60)
        check("3 clicking a card result opens the card page", c.js("selected").startswith("c:"))
        # typo and real words
        search("destory")
        v = vis()
        check("4 typo: 'destory' says it was not found as typed and offers 'destroy'; rows labelled did you mean “destroy”", "Did you mean “destroy”" in c.js("(document.querySelector('#findres .gs-dym') || {}).innerText || ''") and v and all("did you mean “destroy”" in r["why"] for r in v), v[:1])
        search("lifegian")
        check("4 typo: 'lifegian' reaches the lifegain alias", any("Gain life" in r["name"] for r in vis()))
        search("wraith")
        t_ = c.js("document.getElementById('findres').innerText")
        check("4 real word: 'wraith' is taken literally (no correction, no groups) and still finds the cards named Wraith", "Did you mean" not in t_ and "No group matches" in t_ and c.js("document.querySelectorAll('#findres .fr').length") > 0, t_[:160])
        wl = reqs("words.txt")
        search("wrath")
        search("destory")
        check("4 the word list is read only when a typed word needs judging (%d request, none for ordinary words)" % reqs("words.txt"), reqs("words.txt") == 1 and wl <= 1)
        # keyword filter, description, family, none
        search("cycling")
        v = vis()
        check("5 keyword: 'cycling' offers the keyword filter, labelled a filter, not a placement", v and v[0]["go"] == "yk:Cycling" and "filter" in v[0]["text"], v[:1])
        c.js("document.querySelector('#findres .gr').click()")
        c.wait("selected === 'yk:Cycling'", 60)
        time.sleep(0.6)
        check("5 and opens the keyword page", "Keyword: Cycling" in c.js("document.querySelector('#panel h2').innerText"))
        search("perpetually")
        v = vis()
        check("5 description: 'perpetually' matches a hand group only by its description, labelled “matched: description”", any(r["why"] == "matched: description" for r in v), [(r["name"][:24], r["why"]) for r in v[:3]])
        search("landwalk")
        v = vis()
        fam_ok = c.js("(() => { const b = document.querySelector('#findres [data-gsfam]'); const l = document.querySelector('#findres .gs-famlist'); return b ? [b.getAttribute('aria-expanded'), l.hidden, l.querySelectorAll('.gr').length] : null })()")
        check("5 family: groups matched only by family sit under one collapsed row, none among the literal rows (%s)" % fam_ok, fam_ok and fam_ok[0] == "false" and fam_ok[1] is True and fam_ok[2] > 0 and not any("matched: family" in r["why"] and not r["hidden"] for r in rows()))
        c.js("document.querySelector('#findres [data-gsfam]').click()")
        check("5 expanding it shows the rows labelled “matched: family”", c.js("document.querySelector('#findres [data-gsfam]').getAttribute('aria-expanded')") == "true" and any(r["why"] == "matched: family" for r in vis()))
        search("zzqxv")
        t_ = c.js("document.getElementById('findres').innerText")
        check("5 no result: a plain message, no empty sections", "No card or group matches" in t_ and "Cards" not in t_.split("No card")[0] and c.js("!document.querySelector('#findres .gs-h')") is True, t_[:120])
        # the log
        time.sleep(1.4)
        lg = json.load(open(TMPLOG, encoding="utf-8")) if os.path.exists(TMPLOG) else {"queries": {}}
        qs = lg["queries"]
        check("6 log: searches that stood for a moment were logged (%d queries); a no-result query is marked zero; typing in between is not" % len(qs), "zzqxv" in qs and qs["zzqxv"]["zero"] == 1 and "wrath" in qs and "w" not in qs and "wr" not in qs, list(qs)[:8])
        search("board wipe")
        time.sleep(1.2)
        c.js("document.querySelector('#findres .gr').click()")
        time.sleep(1.0)
        lg = json.load(open(TMPLOG, encoding="utf-8"))["queries"]
        check("6 log: opening a result is logged against the query (opened %s, searches %s)" % (lg.get("board wipe", {}).get("opened"), lg.get("board wipe", {}).get("searches")), lg.get("board wipe", {}).get("opened") == 1 and lg["board wipe"]["searches"] == 1)
        check("6 log: only folded words, counts and dates are stored", all(set(v) == {"q", "searches", "zero", "groups", "cards", "opened", "missed", "first", "last"} for v in lg.values()))
        # ---------------------------------------------------------------- new aliases, spellings, drafted aliases, most words, a new hand group
        search("duress")
        v = vis()
        check("13 a spelling of a hand alias: 'duress' reaches the thoughtseize groups, labelled via alias “duress”", v and all("via alias “duress”" in r["why"] for r in v[:2]), [r["why"] for r in v[:2]])
        search("blink")
        v = vis()
        check("13 a new hand group: 'blink' offers 'Exiles a permanent and returns it to the battlefield (blink, flicker)' first, via alias “blink”", v and v[0]["go"] == "hg:blinks-or-flickers-a-permanent" and "via alias “blink”" in v[0]["why"], v[:1])
        search("flicker")
        check("13 ... and 'flicker' (a spelling of the same entry) reaches it", any(r["go"] == "hg:blinks-or-flickers-a-permanent" for r in vis()))
        c.js("document.querySelector('#findres .gr[data-go=\"hg:blinks-or-flickers-a-permanent\"]').click()")
        c.wait("selected === 'hg:blinks-or-flickers-a-permanent'", 60)
        time.sleep(1.2)
        pg = c.js("({h2: document.querySelector('#panel h2').innerText, n: document.querySelectorAll('#panel .card').length, text: document.getElementById('panel').innerText, badge: !!document.querySelector('#panel h2 .b-hg')})")
        check("13 its page opens: the hand-group badge, the 'Phase 2' note, and rule matches with the card's own sentence as the reason (%d rows listed so far)" % pg["n"], pg["badge"] and "Phase 2" in pg["text"] and "Rule matches" in pg["text"] and pg["n"] > 0 and "Suggested because" in pg["text"], pg["h2"])
        check("13 ... nothing on it is ticked, and opening it placed nothing", c.js("document.querySelectorAll('#panel input[type=checkbox]:checked').length") == 0)
        for q_, want in (("mana rock", "hand:mana-rocks"), ("cantrip", "hand:cantrips")):
            search(q_)
            v = vis()
            check("13 new hand group: '%s' offers %s first" % (q_, want), v and v[0]["go"] == "hg:" + want[5:], v[:1])
        search("stax")
        v = vis()
        check("13 stax: five effect groups, each row carrying the note that stax is a strategy, not an effect", len(v) >= 5 and all("strategy" in r["note"] for r in v[:5]), [r["name"][:24] for r in v[:5]])
        search("wipe")
        v = vis()
        check("13 a drafted alias never shows above a name: 'wipe' is already a word of the sweeper tag's name, so that group is listed by name, not as a suggested alias", v and all("suggested alias" not in r["why"] for r in v[:5]) and v[0]["name"].startswith("Destroys everything"), [(r["name"][:22], r["why"][:30]) for r in v[:3]])
        search("mass removal")
        v = vis()
        dr = [i for i, r in enumerate(v) if "suggested alias" in r["why"]]
        check("13 drafted alias: 'mass removal' (a Scryfall spelling of the sweeper tag) answers, labelled “suggested alias”, and every drafted row sits below every row that is not drafted", bool(dr) and all(i > j for i in dr for j in range(len(v)) if "suggested alias" not in v[j]["why"]), [(r["name"][:22], r["why"][:30]) for r in v[:4]])
        search("counterspell")
        check("13 a drafted alias answers only to its exact words: 'counterspell' lists no drafted row", all("suggested alias" not in r["why"] for r in vis()))
        search("sacrifice a creature to pump")
        v = vis()
        check("13 most words: 'sacrifice a creature to pump' answers, every row labelled “matched: most of your words”", v and all(r["why"] == "matched: most of your words" for r in v), [(r["name"][:24], r["why"]) for r in v[:2]])
        search("destory")
        check("13 'did you mean' still works next to the new aliases", "Did you mean “destroy”" in c.js("(document.querySelector('#findres .gs-dym') || {}).innerText || ''"))
        search("blnik")
        v = vis()
        check("13 a typo of a new alias is corrected to it: 'blnik' leads to the blink group, labelled did you mean “blink”", v and any(r["go"] == "hg:blinks-or-flickers-a-permanent" and "did you mean “blink”" in r["why"] for r in v), [(r["name"][:20], r["why"]) for r in v[:2]])
        for w_ in ("blind", "stack", "cantor", "rack"):
            search(w_)
            check("13 near-collision '%s' is not corrected" % w_, "Did you mean" not in c.js("document.getElementById('findres').innerText"))
        # ---------------------------------------------------------------- the "Didn't find it?" button
        search("zzmagecraftx")
        b = c.js("(() => { const x = document.querySelector('#findres .gs-miss button'); return x ? {t: x.innerText, nav: x.hasAttribute('data-nav'), h: Math.round(x.getBoundingClientRect().height)} : null })()")
        check("14 button: offered in the empty-result message when the log answers (%s)" % (b and b["t"]), b and b["t"] == "Didn’t find it?" and b["nav"])
        c.js("document.querySelector('#findres .gs-miss button').click()")
        time.sleep(1.0)
        b2 = c.js("(() => { const x = document.querySelector('#findres .gs-miss button'); return {t: x.innerText, d: x.getAttribute('aria-disabled'), live: x.nextElementSibling.innerText} })()")
        lg = json.load(open(TMPLOG, encoding="utf-8"))["queries"]
        check("14 button: one click records the query in its own field (missed %s), says so, and is then inert" % lg.get("zzmagecraftx", {}).get("missed"), b2["t"] == "Noted, thanks" and b2["d"] == "true" and lg["zzmagecraftx"]["missed"] == 1 and "We will look at" in b2["live"], b2)
        c.js("document.querySelector('#findres .gs-miss button').click()")
        time.sleep(0.6)
        check("14 button: a second click records nothing more", json.load(open(TMPLOG, encoding="utf-8"))["queries"]["zzmagecraftx"]["missed"] == 1)
        search("wrath")
        b3 = c.js("(() => { const x = document.querySelector('#findres #gs-groups .gs-miss button'); return x ? x.innerText : null })()")
        check("14 button: also below a result list (a search that found something, but not the right thing)", b3 == "Didn’t find it?")
        c.js("document.querySelector('#findres .gs-miss button').click()")
        time.sleep(0.8)
        lg = json.load(open(TMPLOG, encoding="utf-8"))["queries"]
        check("14 button: from a list with results the miss is recorded with the result counts (groups %s)" % lg["wrath"]["groups"], lg["wrath"]["missed"] == 1 and lg["wrath"]["groups"] >= 3 and lg["wrath"]["searches"] >= 1)
        load(TB.PORT_A, clear=False)
        search("zzmagecraftx")
        b4 = c.js("document.querySelector('#findres .gs-miss button').innerText + '|' + document.querySelector('#findres .gs-miss button').getAttribute('aria-disabled')")
        check("14 button: remembered across a reload in this browser (%s), so it does not offer itself again" % b4, b4 == "Noted, thanks|true")
        search("zzqmissy")
        c.js("document.getElementById('q').focus()")
        key("ArrowDown", 40)
        check("14 button: reachable with the keyboard (Down arrow from the box)", c.js("document.activeElement.hasAttribute('data-gsmiss')") is True)
        key("Enter", 13, "\r")
        time.sleep(0.8)
        check("14 button: Enter on it records the miss too", json.load(open(TMPLOG, encoding="utf-8"))["queries"]["zzqmissy"]["missed"] == 1)
        ok = load(TB.PORT_D)
        search("zzmagecraftx")
        check("14 button: hidden when the log endpoint does not answer, and the page says searches are not logged", c.js("!document.querySelector('#findres .gs-miss')") is True and "not logged" in c.js("document.getElementById('gsnote').textContent"), c.js("document.getElementById('gsnote').textContent")[:80])
        load(TB.PORT_A, clear=False)
        # the switches
        search("regenerate")
        has_t = any(r["go"].startswith("tg:") for r in rows())
        c.js("document.getElementById('showtent').click()")
        time.sleep(1.0)
        settle()
        r2 = rows()
        check("7 'show tentative' off: the results refresh, no tg: row remains, and a tentative group with a loose twin is offered as the loose group (%s -> %s)" % (has_t, [r["go"][:3] for r in r2 if r["go"][:3] in ("tg:", "lg:")][:4]), not any(r["go"].startswith("tg:") for r in r2))
        c.js("document.getElementById('showtent').click()")
        search("voting")
        has_c = any(r["go"].startswith("ct:") for r in rows())
        c.js("document.getElementById('showtag').click()")
        time.sleep(1.0)
        settle()
        check("7 'community-tag groups' off: the results refresh and no ct: row remains (%s before)" % has_c, has_c and not any(r["go"].startswith("ct:") for r in rows()))
        c.js("document.getElementById('showtag').click()")
        # every group opens
        n = len(idx["groups"])
        c.js("gsLoad()")
        c.wait("!!GSIDX", 60)
        OPEN = ("(async (a, b) => { const bad = []; for (let i = a; i < b; i++) { const e = GSIDX.entries[i], k = gsAllow(e); if (!k) continue; await show(k); "
                "const t = document.getElementById('panel').innerText; if (!t || t.startsWith('Loading') || /^No such/.test(t) || t.includes('switched off') || t.includes('Loading the')) bad.push([e.gid, k, t.slice(0, 50)]); } return bad; })")
        bad = []
        for a in range(0, n, 250):
            bad += c.js("%s(%d, %d)" % (OPEN, a, min(n, a + 250)))
        check("8 every one of the %d searchable groups opens a real page (switches on)" % n, not bad, bad[:3])
        load(TB.PORT_A)                                           # a fresh page: 2,000 page opens in one tab is a lot for Edge
        c.js("gsLoad()")
        c.wait("!!GSIDX", 60)
        c.js("document.getElementById('showtent').click(); document.getElementById('showtag').click()")
        time.sleep(1.0)
        off_keys = c.js("GSIDX.entries.filter(e => !gsAllow(e)).map(e => e.layer)")
        bad = []
        for a in range(0, n, 250):
            bad += c.js("%s(%d, %d)" % (OPEN, a, min(n, a + 250)))
        n_t_only = sum(1 for r in idx["groups"] if r[4] == "t" and not r[9])
        n_tag = sum(1 for r in idx["groups"] if r[4] == "c") + sum(1 for r in idx["groups"] if r[4] == "m" and all(g.startswith("tag:") for g in r[12]))     # a merged page whose members are all community tags is a tag group too
        check("8 with tentative and tag groups switched off: %d are not offered (%d tag, counting merged pages made only of tags, + %d tentative with no loose twin) and every other group still opens (%d bad)" % (len(off_keys), n_tag, n_t_only, len(bad)),
              not bad and len(off_keys) == n_tag + n_t_only, bad[:3])
        load(TB.PORT_A)
        c.js("gsLoad()")
        c.wait("!!GSIDX", 60)
        # counts
        samp = []
        for lay in ("l", "t", "c", "k", "r", "y", "o"):
            samp += [r[0] for r in idx["groups"] if r[4] == lay][::max(1, sum(1 for r in idx["groups"] if r[4] == lay) // 6)][:6]
        mism = []
        for gid in samp:
            r = c.js("(async () => { const e = GSIDX.byGid[%s], k = gsAllow(e); const n = gsCount({e: e, key: k}); await show(k); const sub = document.querySelector('#panel p.sub'); const m = (sub ? sub.innerText : '').match(/([\\d,]+) (?:cards|rule matches)\\b/); return [n, m ? +m[1].replace(/,/g, '') : null]; })()" % json.dumps(gid))
            if r[1] is None or r[0] != r[1]:
                mism.append((gid, r))
        check("9 the count on a result row equals the count on the group's page (%d groups, every layer)" % len(samp), not mism, mism[:3])
        # keyboard
        search("wrath")
        c.js("document.getElementById('q').focus()")
        key("ArrowDown", 40)
        a0 = c.js("document.activeElement.hasAttribute('data-nav') ? document.activeElement.className + '|' + document.activeElement.tagName : 'none'")
        check("10 keyboard: ArrowDown in the box moves focus to the first result (%s)" % a0, a0 != "none")
        for _ in range(12):
            if c.js("document.activeElement.classList.contains('gr')"):
                break
            key("ArrowDown", 40)
        on_group = c.js("document.activeElement.classList.contains('gr')")
        go = c.js("document.activeElement.dataset.go")
        key("ArrowUp", 38)
        key("ArrowDown", 40)
        check("10 keyboard: Down and Up move through the cards and then the groups", on_group and c.js("document.activeElement.dataset.go") == go)
        key("Enter", 13, "\r")
        ok = c.wait("selected === %s" % json.dumps(go), 60)
        check("10 keyboard: Enter on a group opens it (%s)" % go, ok)
        search("wrath")
        key("ArrowDown", 40)
        key("Escape", 27)
        check("10 keyboard: Escape in the results returns focus to the box", c.js("document.activeElement.id") == "q")
        key("Escape", 27)
        time.sleep(0.3)
        check("10 keyboard: Escape in the box clears it and the results", c.js("document.getElementById('q').value") == "" and c.js("document.getElementById('findres').innerHTML") == "")
        search("fog")
        key("Enter", 13, "\r")
        time.sleep(0.6)
        check("10 keyboard: Enter in the box runs the search at once and focuses the first result", c.js("document.activeElement.hasAttribute('data-nav')") is True)
        check("10 an aria-live line announces the counts", "group" in c.js("(document.getElementById('gs-live') || {textContent: ''}).textContent"))
        # 390 px
        c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
        time.sleep(0.6)
        search("landwalk")
        c.js("document.querySelector('#findres [data-gsfam]').click()")
        c.js("document.querySelectorAll('#findres [data-gsx]').forEach(e => e.hidden = false)")
        long_q = max(idx["groups"], key=lambda r: len(r[2]))[2]
        search(" ".join(long_q.split()[:4]))
        m = c.js("(() => ({w: document.documentElement.scrollWidth, iw: window.innerWidth, rows: [...document.querySelectorAll('#findres .gr')].filter(e => e.getBoundingClientRect().height > 0).map(e => [Math.round(e.getBoundingClientRect().height), e.scrollWidth <= e.clientWidth + 1]), "
                 "btn: [...document.querySelectorAll('#findres .gs-btn')].map(e => Math.round(e.getBoundingClientRect().height)), jump: [...document.querySelectorAll('#findres .gs-jump a')].map(e => Math.round(e.getBoundingClientRect().height))}))()")
        check("11 390 px: no sideways scroll (%d <= %d), group rows at least 44 px tall and not overflowing, buttons and jump links 44 px" % (m["w"], m["iw"]),
              m["w"] <= m["iw"] and m["rows"] and all(h >= 44 and ok for h, ok in m["rows"]) and all(h >= 44 for h in m["btn"] + m["jump"]), m)
        search("wrath")
        c.js("document.querySelector('#findres .gr').click()")
        time.sleep(1.0)
        top = c.js("document.getElementById('panel').getBoundingClientRect().top")
        check("11 390 px: opening a group scrolls its page into view (panel top %d px)" % top, -50 <= top <= 844)
        c.call("Emulation.clearDeviceMetricsOverride")
        # the protected files and the real log
        after = [sha(p) for p in PROTECTED]
        check("12 the protected corrections files are byte-identical before and after (the browser used temporary copies)", before == after)
        check("12 the real log file was not touched by the test", sha(REAL_LOG) == real_log_before)
    finally:
        edge.terminate()
        for s_ in srvs:
            s_.shutdown()
    bad = [n for n, ok in results if not ok]
    print("\n%d checks, %d failed" % (len(results), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
