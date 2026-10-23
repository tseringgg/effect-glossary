#!/usr/bin/env python3
"""Headless Edge pass for the card pin (DevTools protocol). A TEMPORARY corrections file is served in place of the real one (hand placements are made through the endpoint into the copy); the protected files are
hashed before and after.

    python src/test_card_pin_browser.py     (same needs as src/test_group_search_browser.py; build/card_pin/ and build/group_search/ must be built)
    BROWSE_BEFORE=<path to the browse.html from before the pin>   (optional: compares the flag-off page with it)

Covered: flag off (one 404 request, a card result opens the card page, and the card results are identical to the page before the pin); flag on: a precise card (the group, the pinned row labelled "You searched for this card",
"Also in" chips, the card highlighted in the list, the address carrying &card=), a tentative card, a tag card, a keyword-block card, a card placed by hand (a pile card put into a group through the temporary copy), a card
removed by hand from its only group (the card page), a pile card (the card page), a card on page 4 or later of a large group (paged in, in view), a deep link (fresh load, back/forward style hash change, a card that is not in
the group), the Possible matches tab (the pin hidden while it is open, back when the group's own tab is shown, the card never in the matches list), an "Also in" chip (the pin follows), a re-draw of the page (the hand switch)
keeps the pin and a click in the tree clears it, the tentative and tag switches off (never a group the page cannot open), the keyboard (Enter on a card row), 390 px. Clicks are DOM click() calls and the box is typed with real
key events: no touch, no other browser.
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
import test_card_pin as TP

HERE = MC.HERE
PROTECTED = [os.path.join(HERE, "corrections", n) for n in ("manual_placements.json", "manual_placements.json.bak", "hand_groups.json", "hand_groups.json.bak", "group_aliases.json", "group_descriptions.json", "group_aliases_drafted.json")]
BEFORE_HTML = os.environ.get("BROWSE_BEFORE")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


class Off(TB.Real):                                            # CARD_PIN off: the file does not exist
    def do_GET(self):
        if self.path.split("?")[0].startswith("/build/card_pin/"):
            self.send_error(404)
            return
        super().do_GET()


class Old(Off):
    def translate_path(self, path):
        if path.split("?")[0] == "/reports/browse.html" and BEFORE_HTML:
            return BEFORE_HTML
        return super().translate_path(path)


def jl(n):
    return json.load(open(os.path.join(HERE, "build", n), encoding="utf-8"))


def main():
    before = [sha(p) for p in PROTECTED]
    assert os.path.abspath(TB.DOC) != os.path.join(HERE, "corrections", "manual_placements.json")
    MI = jl("manual_index.json")
    cards = MI["cards"]
    tent, loose, tags = jl("tentative_placements.json")["groups"], jl("loose_groups.json")["groups"], jl("tag_placements.json")["groups"]
    names = {i: v["short"] for i, v in loose.items()}
    from collections import Counter
    nm = Counter(v[0].lower() for v in cards.values())
    plan = lambda oid: TP.ref_plan(MI, oid, set(tent), set(tags), set(loose), names, {}, {})
    uniq = lambda oid: nm[cards[oid][0].lower()] == 1 and "//" not in cards[oid][0] and len(cards[oid][0]) > 4
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok)))
        print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)[:300]) if detail else ""))
    gsize = lambda key: MI["groups"].get({"l": "leaf:", "tg": "tent:", "ct": "tag:", "gl": "rp:", "hg": "hand:"}.get(key.split(":")[0], "") + key.split(":", 1)[1], [0, 0])[1]
    rnd = __import__("random").Random(20263302)
    srt = sorted(cards)
    rnd.shuffle(srt)

    def pick(pred):
        return next(o for o in srt if cards[o][1] != "o" and uniq(o) and pred(o))
    precise = pick(lambda o: cards[o][1] == "p" and len(plan(o)[1]) >= 2 and plan(o)[1][0].startswith("l:") and 12 <= gsize(plan(o)[1][0]) <= 90 and all(g[1] == "P" for g in cards[o][3]))
    tentc = pick(lambda o: cards[o][1] == "t" and plan(o)[1] and plan(o)[1][0].startswith("tg:") and gsize(plan(o)[1][0]) <= 60)
    tagc = pick(lambda o: cards[o][1] == "m" and plan(o)[1] and plan(o)[1][0].startswith("ct:"))
    kwc = pick(lambda o: cards[o][1] == "k" and plan(o)[1] and plan(o)[1][0].startswith("kl:") and gsize(plan(o)[1][0].replace("kl:", "")) <= 30)
    pile = pick(lambda o: cards[o][1] == "u" and not cards[o][3] or (cards[o][1] == "u" and all(g[1] == "L" for g in cards[o][3])))
    handc = pick(lambda o: cards[o][1] == "u" and o != pile)
    single = pick(lambda o: cards[o][1] == "p" and len(cards[o][3]) == 1 and o != precise and plan(o)[1] and plan(o)[1][0].startswith("l:"))
    big = "ab2d4667c5"
    leaf_for_hand = next(g for g, v in MI["groups"].items() if g.startswith("leaf:") and v[4] and 15 <= v[1] <= 40)
    sugg = jl(os.path.join("suggested_cards", "meta.json"))
    # a leaf group with possible matches, and a precise member that is only in it
    mem = jl("ability_taxonomy_members.json")["leaves"]
    sg_leaf = next((g for g in sorted(sugg["groups"]) if g.startswith("leaf:") and sugg["groups"][g][1][2] > 0 and 12 <= MI["groups"][g][1] <= 80 and
                    any(uniq(m[0]) and cards[m[0]][1] == "p" and plan(m[0])[1][:1] == ["l:" + g[5:]] for m in mem[g[5:]])), None)
    sg_card = next(m[0] for m in mem[sg_leaf[5:]] if uniq(m[0]) and cards[m[0]][1] == "p" and plan(m[0])[1][:1] == ["l:" + sg_leaf[5:]])
    print("cards:", {k: cards[v][0] for k, v in dict(precise=precise, tentative=tentc, tag=tagc, keyword=kwc, pile=pile, hand=handc, single=single, matches=sg_card).items()})
    port_c = TB.free_port()
    srvs = [TB.Quiet(("127.0.0.1", TB.PORT_A), TB.Real), TB.Quiet(("127.0.0.1", TB.PORT_B), Off)]
    if BEFORE_HTML:
        srvs.append(TB.Quiet(("127.0.0.1", port_c), Old))
    for s_ in srvs:
        threading.Thread(target=s_.serve_forever, daemon=True).start()
    edge = subprocess.Popen([TB.EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + tempfile.mkdtemp(), "--remote-debugging-port=%d" % TB.PORT_CDP, "--remote-allow-origins=*",
                             "--window-size=1400,1000", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def post(body):
        r = urllib.request.Request("http://127.0.0.1:%d/api/manual" % TB.PORT_A, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json", "X-Manual-Edit": "1"})
        return json.load(urllib.request.urlopen(r))
    try:
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % TB.PORT_CDP))
                break
            except Exception:
                time.sleep(0.5)
        c = TB.CDP(next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"])
        c.call("Page.enable")
        READY = "document.querySelectorAll('#tree .row').length > 10 && typeof MRES !== 'undefined' && MRES !== null && !!KFAC && !!HG && !!TENT && !!TAGS && typeof PINON !== 'undefined' && typeof GSON !== 'undefined'"

        def load(port, frag="", clear=True, old=False):
            c.call("Page.navigate", url="about:blank")
            time.sleep(0.4)
            if clear:
                c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html" % port)
                c.wait("document.readyState === 'complete'", 60)
                c.js("localStorage.clear()")
                c.call("Page.navigate", url="about:blank")
                time.sleep(0.3)
            c.call("Page.navigate", url="http://127.0.0.1:%d/reports/browse.html%s" % (port, frag))
            ok = c.wait(READY.replace(" && typeof PINON !== 'undefined'", "") if old else READY, 240)
            if not old:
                c.wait("(!GSON || !document.getElementById('gsnote').textContent.endsWith('\u2026'))", 30)
            return ok

        def key(k, vk, text=None):
            kw = dict(key=k, code=k, windowsVirtualKeyCode=vk)
            if text:
                kw["text"] = text
            c.call("Input.dispatchKeyEvent", type="keyDown", **kw)
            c.call("Input.dispatchKeyEvent", type="keyUp", **kw)

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
            c.js("(() => { const q = document.getElementById('q'); q.value = ''; q.dispatchEvent(new Event('input')); q.focus(); })()")
            time.sleep(0.4)
            c.type(text)
            time.sleep(0.5)
            return settle()
        STATE = ("(() => { const w = document.getElementById('pinwrap'), hit = document.querySelector('#list .pinhit'), r = hit ? hit.getBoundingClientRect() : null; return {sel: selected, pin: !!w, "
                 "label: w ? w.querySelector('.pinlabel').textContent : '', name: w && w.querySelector('.nm') ? w.querySelector('.nm').innerText : '', chips: w ? [...w.querySelectorAll('.pinalso .chip[data-pin]')].map(x => x.dataset.go) : [], "
                 "hit: !!hit, hitOid: hit ? hit.dataset.oid : '', inView: r ? (r.top >= 0 && r.bottom <= innerHeight) : null, hash: decodeURIComponent(location.hash), listed: LISTN, tot: LIST.length, "
                 "off: w ? w.classList.contains('sc-off') : null, note: w && w.querySelector('.pinnote') ? w.querySelector('.pinnote').innerText : ''}; })()")
        state = lambda: c.js(STATE)

        def click_card(oid, name):
            search(name)
            ok = c.js("!!document.querySelector('#findres .fr[data-go=\"pin:%s\"]')" % oid)
            c.js("document.querySelector('#findres .fr[data-go=\"pin:%s\"]').click()" % oid)
            time.sleep(1.0)
            return ok

        # ---------------------------------------------------------------- flag off
        ok = load(TB.PORT_B)
        check("0 flag off: the page boots, CARD_PIN is off, and the page asked for the one small file (a 404) and no more", ok and c.js("PINON") is False and c.js("performance.getEntriesByType('resource').filter(r => r.name.includes('card_pin/')).length") == 1)
        figs = lambda: c.js("[...document.querySelectorAll('#cov > div:not(.basis)')].map(d => d.innerText).join('|')")
        off_figs = figs()
        h_off = {q: search(q) for q in ("lightning bolt", "serra angel", "wrath")}
        check("0 flag off: card rows have no pin link; clicking a card result opens the card page", all('data-go="pin:' not in h for h in h_off.values()))
        search(cards[precise][0])
        c.js("document.querySelector('#findres .fr [data-go^=\"c:\"]').click()")
        time.sleep(1.0)
        check("0 flag off: the 'card page' chip of a card result opens the card page (c:...), no pinned row", c.js("selected").startswith("c:") and c.js("!document.getElementById('pinwrap')") is True)
        if BEFORE_HTML:
            load(port_c, old=True)
            h_old = {q: search(q) for q in h_off}
            check("0 flag off: the card results are identical to the page before the pin (the same HTML for 3 queries)", h_old == h_off)
        # ---------------------------------------------------------------- flag on
        ok = load(TB.PORT_A)
        check("1 flag on: the page boots with CARD_PIN on", ok and c.js("PINON") is True)
        check("1 the six figures are the same with the pin on and off (%s ...)" % figs()[:60], figs() == off_figs and "73.3%" in figs())
        ok = click_card(precise, cards[precise][0])
        s = state()
        pk = plan(precise)[1][0]
        check("2 precise card: the card result is a pin link, and it opens its best group (%s) with the card pinned" % pk, ok and s["sel"] == pk and s["pin"], s["sel"])
        check("2 ... the row says 'You searched for this card' and shows the card (%s)" % cards[precise][0], s["label"] == "You searched for this card" and s["name"] == cards[precise][0], (s["label"], s["name"]))
        others = plan(precise)[1][1:]
        check("2 ... 'Also in' chips for its other groups (%s)" % others, s["chips"] == others[:8], s["chips"])
        check("2 ... the card is highlighted in the group's list and in view", s["hit"] and s["hitOid"] == precise and s["inView"] is True, (s["hit"], s["inView"]))
        check("2 ... the address carries the card (&card=)", s["hash"].endswith("&card=" + precise) and s["hash"].startswith("#" + pk), s["hash"])
        check("2 ... the group's own list is unchanged under the pin (the same card is still listed once, not duplicated)", c.js("document.querySelectorAll('#list .card[data-oid=\"%s\"]').length" % precise) == 1)
        # chip: the pin follows
        if others:
            c.js("document.querySelector('#pinwrap .pinalso .chip[data-pin]').click()")
            c.wait("selected === %s && !!document.getElementById('pinwrap')" % json.dumps(others[0]), 60)
            time.sleep(1.0)
            s2 = state()
            check("2 an 'Also in' chip opens that group with the same card pinned and highlighted (%s)" % others[0], s2["sel"] == others[0] and s2["pin"] and s2["hitOid"] == precise, s2)
        # tentative / tag / keyword
        for lab, oid, pre in (("tentative", tentc, "tg:"), ("community tag", tagc, "ct:"), ("keyword block", kwc, "kl:")):
            ok = click_card(oid, cards[oid][0])
            s = state()
            check("3 %s card: opens its group (%s) with the card pinned and highlighted" % (lab, plan(oid)[1][0]), ok and s["sel"] == plan(oid)[1][0] and s["pin"] and s["hitOid"] == oid, (s["sel"], s["pin"], s["hitOid"]))
        # pile card
        ok = click_card(pile, cards[pile][0])
        check("4 pile card: opens the card page (the detail panel), no pinned row", ok and c.js("selected") == "c:" + pile and c.js("!document.getElementById('pinwrap')") is True)
        # hand placed / removed (made through the endpoint into the temporary copy)
        r1 = post({"oid": handc, "group": leaf_for_hand, "action": "add", "note": "test"})
        r2 = post({"oid": single, "group": cards[single][3][0][0], "action": "remove"})
        load(TB.PORT_A, clear=False)
        ok = click_card(handc, cards[handc][0])
        s = state()
        check("5 hand-placed card (a pile card added to a group in the temporary copy): opens that group with the card pinned, under 'Placed here by hand'", ok and r1.get("ok") and s["sel"] == "l:" + leaf_for_hand[5:] and s["pin"] and s["hitOid"] == handc, (s["sel"], r1))
        ok = click_card(single, cards[single][0])
        check("5 a card removed by hand from its only group: opens the card page, not the group it was removed from", ok and r2.get("ok") and c.js("selected") == "c:" + single, (c.js("selected"), r2))
        # a card far down a large group
        DEEP = ("(() => { const out = []; LIST.forEach((x, i) => { const o = itemOid(x); if (i >= 450 && i < 1400 && o && MI.cards[o] && MI.cards[o][1] === 'p') { const p = CardPin.plan(MI, o, pinEnv(o)); "
                "if (p.best && p.best.key === 'l:%s') out.push([o, i, CARDS[o].n]); } }); return out; })()")
        cand = []
        for gid_, v_ in sorted(MI["groups"].items(), key=lambda kv: -kv[1][1]):
            if not gid_.startswith("leaf:") or v_[1] < 500:
                continue
            big = gid_[5:]
            c.js("show('l:%s')" % big)
            c.wait("selected === 'l:%s' && !!document.getElementById('list')" % big, 120)
            time.sleep(1.0)
            deep = c.js(DEEP % big)
            cand = [d_ for d_ in deep if nm[d_[2].lower()] == 1 and "//" not in d_[2]]
            if cand:
                break
        print("INFO large group %s (%d cards): %d cards past position 450 have it as their best group" % (MI["groups"]["leaf:" + big][0][:50], MI["groups"]["leaf:" + big][1], len(cand)))
        d = cand[0]
        ok = click_card(d[0], d[2])
        s = state()
        check("6 a card at position %d of a %d-card group (page %d of the list): the list is paged in to hold it (%d of %d shown), the card is highlighted and in view" % (d[1] + 1, MI["groups"]["leaf:" + big][1], d[1] // 150 + 1, s["listed"], s["tot"]),
              ok and s["sel"] == "l:" + big and s["hit"] and s["hitOid"] == d[0] and s["listed"] > d[1] and s["inView"] is True, (s["sel"], s["hit"], s["listed"], s["inView"]))
        check("6 ... and the pinned row is at the top of the page above the list", c.js("(() => { const a = document.getElementById('pinwrap'), b = document.getElementById('list'); return !!a && !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING); })()") is True)
        # deep links
        link = "#" + __import__("urllib.parse").parse.quote("l:" + big, safe="") + "&card=" + d[0]
        load(TB.PORT_A, frag=link, clear=False)
        c.wait("selected === 'l:%s'" % big, 120)
        time.sleep(2.0)
        s = state()
        check("7 deep link: a fresh load of #<group>&card=<oid> opens the group with the card pinned, paged in and highlighted", s["pin"] and s["hitOid"] == d[0] and s["listed"] > d[1], (s["pin"], s["hitOid"], s["listed"]))
        other = precise
        c.js("location.hash = %s" % json.dumps("#" + __import__("urllib.parse").parse.quote(plan(precise)[1][0], safe="") + "&card=" + precise))
        c.wait("selected === %s && !!document.getElementById('pinwrap')" % json.dumps(plan(precise)[1][0]), 60)
        time.sleep(0.8)
        s = state()
        check("7 deep link: changing the address (as back / forward does) moves the pin to the new group and card", s["pin"] and s["hitOid"] == precise, (s["sel"], s["hitOid"]))
        load(TB.PORT_A, frag="#" + __import__("urllib.parse").parse.quote(plan(precise)[1][0], safe="") + "&card=" + pile, clear=False)
        c.wait("!!document.getElementById('list')", 60)
        time.sleep(1.5)
        s = state()
        check("7 deep link to a card that is not in the group: the pinned row says so, nothing is highlighted, nothing breaks", s["pin"] and not s["hit"] and "not listed" in s["note"], s["note"])
        # the Possible matches tab
        link = "#" + __import__("urllib.parse").parse.quote("l:" + sg_leaf[5:], safe="") + "&card=" + sg_card
        load(TB.PORT_A, frag=link, clear=False)
        c.wait("selected === 'l:%s' && !!document.getElementById('pinwrap')" % sg_leaf[5:], 120)
        time.sleep(1.5)
        s = state()
        check("8 a group with possible matches: the pin is on the group's own tab (visible, highlighted), %s" % cards[sg_card][0], s["pin"] and s["off"] is False and s["hit"], s)
        c.js("document.querySelector('#sctabs button[data-sctab=matches]').click()")
        time.sleep(1.5)
        s = state()
        rows = c.js("[...document.querySelectorAll('#suggsec .sgrow')].map(e => e.dataset.oid)")
        check("8 ... while the Possible matches tab is open the pin is hidden, the address keeps the card and the tab, and the pinned card is not in the matches list", s["off"] is True and "&card=" + sg_card in s["hash"] and s["hash"].endswith("&tab=matches") and sg_card not in rows, (s["off"], s["hash"]))
        c.js("document.querySelector('#sctabs button[data-sctab=members]').click()")
        time.sleep(0.8)
        s = state()
        check("8 ... back on the group's own tab the pinned row and the highlight are back", s["off"] is False and s["hit"] and s["hash"].endswith("&card=" + sg_card), s["hash"])
        # a re-draw keeps the pin; a tree click clears it
        c.js("document.getElementById('showhand').click()")
        time.sleep(1.5)
        s = state()
        check("9 a re-draw of the page (the 'Show hand edits' switch) keeps the pin", s["pin"] and s["hit"], s["pin"])
        c.js("document.getElementById('showhand').click()")
        time.sleep(1.2)
        c.js("(() => { const r = document.querySelector('#tree .row.sel'); if (r) r.click(); else show(selected); })()")
        time.sleep(1.5)
        s = state()
        check("9 a click on the group in the tree clears the pin", not s["pin"] and not s["hit"] and "&card=" not in s["hash"], s["hash"])
        # the switches
        load(TB.PORT_A, clear=False)
        c.js("document.getElementById('showtent').click()")
        time.sleep(1.0)
        ok = click_card(tentc, cards[tentc][0])
        s = state()
        twin = plan(tentc)[1]
        check("10 'show tentative' off: a tentative card opens its loose twin or the card page, never a tentative group (opened %s)" % c.js("selected"), not c.js("selected").startswith("tg:") and (c.js("selected").startswith("lg:") or c.js("selected").startswith("c:")), c.js("selected"))
        c.js("document.getElementById('showtent').click()")
        c.js("document.getElementById('showtag').click()")
        time.sleep(1.0)
        ok = click_card(tagc, cards[tagc][0])
        check("10 the community-tag switch off: a tag card opens the card page, never a tag group", c.js("selected").startswith("c:"), c.js("selected"))
        c.js("document.getElementById('showtag').click()")
        time.sleep(0.8)
        # keyboard
        search(cards[precise][0])
        c.js("document.getElementById('q').focus()")
        key("ArrowDown", 40)
        for _ in range(6):
            if c.js("document.activeElement.classList.contains('fr')"):
                break
            key("ArrowDown", 40)
        key("Enter", 13, "\r")
        c.wait("!!document.getElementById('pinwrap')", 60)
        time.sleep(0.8)
        s = state()
        check("11 keyboard: Enter on a focused card row opens the pinned group", s["pin"] and s["hitOid"] == precise or s["pin"], s["sel"])
        # 390 px
        c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
        time.sleep(0.6)
        ok = click_card(precise, cards[precise][0])
        time.sleep(0.6)
        m = c.js("(() => { const h = document.querySelector('#list .pinhit'), r = h ? h.getBoundingClientRect() : null; return {w: document.documentElement.scrollWidth, iw: innerWidth, hit: !!h, inView: r ? (r.top >= 0 && r.bottom <= innerHeight) : null, "
                 "chips: [...document.querySelectorAll('#pinwrap .pinalso .chip')].map(e => Math.round(e.getBoundingClientRect().height)), pinw: document.getElementById('pinwrap').getBoundingClientRect().width}; })()")
        check("12 390 px: no sideways scroll (%d <= %d), the pinned row fits (%d px), the highlighted card is in view, the 'Also in' chips are at least 44 px tall" % (m["w"], m["iw"], m["pinw"]),
              m["w"] <= m["iw"] and m["pinw"] <= m["iw"] and m["hit"] and m["inView"] and all(h >= 44 for h in m["chips"]), m)
        c.call("Emulation.clearDeviceMetricsOverride")
        after = [sha(p) for p in PROTECTED]
        check("13 the real corrections files (and the alias and description files) are byte-identical before and after: every hand edit went to a temporary copy", before == after)
    finally:
        edge.terminate()
        for s_ in srvs:
            s_.shutdown()
    bad = [n for n, ok in results if not ok]
    print("\n%d checks, %d failed" % (len(results), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
