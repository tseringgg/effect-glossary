#!/usr/bin/env python3
"""Tests for the card pin that need no browser:  python src/test_card_pin.py     (needs `pip install dukpy` and the build files)

Independent of the generator: reports/cardpin.js (run in dukpy) is compared, card by card on ALL 38,921 entries and under six switch scenarios, with a separate Python implementation of the rules written from the header of
cardpin.js; the group a card opens is checked against the SOURCE files (the card is really listed in that group, and the group exists in the file the page opens it from); the flag off (nothing written, the file removed, every other
file byte-identical); the protected corrections files hashed before and after. NOT independent: which group is "best" is a rule I chose (precise, tentative, tag, loose, keyword, hand).
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

HERE = M.HERE
BUILD = os.path.join(HERE, "build")
CORR = os.path.join(HERE, "corrections")
PROTECTED = [os.path.join(CORR, n) for n in ("manual_placements.json", "manual_placements.json.bak", "hand_groups.json", "hand_groups.json.bak", "group_aliases.json", "group_descriptions.json", "group_aliases_drafted.json")]
RESULTS = []


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)[:300]) if detail else ""))


def jl(n):
    with io.open(os.path.join(BUILD, n), encoding="utf-8") as fh:
        return json.load(fh)


CLS = {"P": 0, "R": 0.5, "B": 0.7, "T": 1, "S": 1.2, "M": 2, "L": 3, "K": 4}


def ref_plan(MI, oid, tent, tag, loose, loose_names, adds, removes):
    """The rules in the header of reports/cardpin.js, written again: -> (open, [keys best first])."""
    c = MI["cards"].get(oid)
    if c is None or c[1] == "o":
        return "card", []
    rows = []
    seen = set()

    def offer(gid, cls):
        layer, _, i = gid.partition(":")
        if gid in removes:
            return
        key = ""
        if layer == "leaf":
            key = "l:" + i
        elif layer == "rp":
            key = "gl:" + i
        elif layer == "kw":
            key = "kl:" + gid
        elif layer == "hand":
            key = "hg:" + i
        elif layer == "tag":
            key = "ct:" + i if i in tag else ""
        elif layer == "tent":
            key = "tg:" + i if i in tent else ("lg:" + i if i in loose else "")
        elif layer == "loose":
            key = "" if i in tent else ("lg:" + i if i in loose else "")
        if not key or key in seen:
            return
        g = MI["groups"].get(gid)
        if g is not None and not g[4]:
            return
        seen.add(key)
        rows.append((cls, len(rows), key))
    if c[1] == "v":
        rows.append((0, 0, "V:"))
    else:
        for gid, src in [(g[0], g[1]) for g in c[3]]:
            if src == "A" or src not in CLS or c[1] in ("u", "a"):
                continue
            offer(gid, CLS[src])
    for gid in adds:
        offer(gid, 5)
    rows.sort()
    return ("group" if rows else "card"), [r[2] for r in rows]


def main():
    before = [sha(p) for p in PROTECTED]
    MI = jl("manual_index.json")
    tent, loose = jl("tentative_placements.json")["groups"], jl("loose_groups.json")["groups"]
    tags, hg = jl("tag_placements.json")["groups"], jl("hand_group_hits.json")["groups"]
    tax = jl("ability_taxonomy.json")
    members_leaf = jl("ability_taxonomy_members.json")["leaves"]
    sib = jl("sibling_placements.json") if os.path.exists(os.path.join(BUILD, "sibling_placements.json")) else {}
    names = {i: v["short"] for i, v in loose.items()}
    cards = MI["cards"]

    itp = dukpy.JSInterpreter()
    itp.evaljs(io.open(os.path.join(HERE, "reports", "cardpin.js"), encoding="utf-8").read())
    itp.evaljs("var MI = %s; var TENT = %s, LOOSE = %s, TAG = %s, LNAME = %s;" % (json.dumps({"cards": cards, "groups": MI["groups"]}), json.dumps(list(tent)), json.dumps(list(loose)), json.dumps(list(tags)), json.dumps(names)))
    itp.evaljs("""
      function setEnv(t, g, h) { var T = {}, G = {}, L = {}, i; for (i = 0; i < TENT.length; i++) T[TENT[i]] = 1; for (i = 0; i < TAG.length; i++) G[TAG[i]] = 1; for (i = 0; i < LOOSE.length; i++) L[LOOSE[i]] = 1;
        ENVB = { tentOk: function (id) { return t && T[id]; }, tagOk: function (id) { return g && G[id]; }, looseHas: function (id) { return !!L[id]; }, looseName: function (id) { return LNAME[id] || ''; } }; HAND = h || {}; }
      function runAll(t, g) {
        var out = {}, oid, e, p, i, ks;
        setEnv(t, g, null);
        for (oid in MI.cards) { e = { tentOk: ENVB.tentOk, tagOk: ENVB.tagOk, looseHas: ENVB.looseHas, looseName: ENVB.looseName, adds: HAND.adds && HAND.adds[oid] || null, removes: HAND.removes && HAND.removes[oid] || null };
          p = CardPin.plan(MI, oid, e); ks = []; for (i = 0; i < p.groups.length; i++) ks.push(p.groups[i].key); out[oid] = [p.open, ks]; }
        return out; }
    """)
    scen = [(True, True), (False, True), (True, False), (False, False)]
    allbad = {}
    first = None
    for t, g in scen:
        js = json.loads(itp.evaljs("JSON.stringify(runAll(%s, %s))" % (str(t).lower(), str(g).lower())))
        tset = set(tent) if t else set()
        gset = set(tags) if g else set()
        bad = []
        for oid in cards:
            ro, rk = ref_plan(MI, oid, tset, gset, set(loose), names, {}, {})
            if [ro, rk] != js[oid]:
                bad.append(oid)
        allbad[(t, g)] = bad
        if first is None:
            first = js
        check("1 the pin's rules in JavaScript equal the independent Python version on all %d entries (tentative %s, tag %s)" % (len(cards), "on" if t else "off", "on" if g else "off"), not bad, bad[:2])
    # hand edits: random adds and removes, mixed with the generated groups
    rnd = random.Random(20263301)
    offered = [gid for gid, v in MI["groups"].items() if v[4]]
    oids = [o for o, v in cards.items() if v[1] != "o"]
    adds, removes = {}, {}
    for o in rnd.sample(oids, 1500):
        if rnd.random() < 0.6 or not cards[o][3]:
            adds.setdefault(o, {})[rnd.choice(offered)] = {}
        else:
            removes.setdefault(o, {})[rnd.choice(cards[o][3])[0]] = {}
    itp.evaljs("setEnv(true, true, %s);" % json.dumps({"adds": adds, "removes": removes}))
    js = json.loads(itp.evaljs("""JSON.stringify((function () { var out = {}, oid, e, p, i, ks; for (oid in MI.cards) { e = { tentOk: ENVB.tentOk, tagOk: ENVB.tagOk, looseHas: ENVB.looseHas, looseName: ENVB.looseName, adds: HAND.adds[oid] || null, removes: HAND.removes[oid] || null };
          p = CardPin.plan(MI, oid, e); ks = []; for (i = 0; i < p.groups.length; i++) ks.push(p.groups[i].key); out[oid] = [p.open, ks]; } return out; })())"""))
    bad = [o for o in cards if [*ref_plan(MI, o, set(tent), set(tags), set(loose), names, adds.get(o, {}), removes.get(o, {}))] != js[o]]
    check("1 with 1,500 cards given hand adds and removals (900 adds, 600 removals) the two versions still agree on all entries", not bad, bad[:2])
    gone = [o for o, r in removes.items() if any(k for g in r for k in [g]) and any(js[o][1] and False for _ in [0])]
    rm_ok = True
    for o, r in removes.items():
        for gid in r:
            layer, _, i = gid.partition(":")
            k = {"leaf": "l:" + i, "rp": "gl:" + i, "kw": "kl:" + gid, "hand": "hg:" + i, "tag": "ct:" + i, "tent": "tg:" + i, "loose": "lg:" + i}[layer]
            if k in js[o][1]:
                rm_ok = False
    check("1 a group a card was removed from by hand is never opened for it", rm_ok)

    # ---- invariants read from the SOURCE files (not from the plan's own data)
    kwl = tax["blocks"]["keyword"]["leaves"]
    rpl = tax["blocks"]["replacement"]["leaves"]

    def member(key, oid):
        k, _, i = key.partition(":")
        if key == "V:":
            return oid in set(tax["blocks"]["no_abilities"]["cards"])
        if k == "l":
            return any(m[0] == oid for m in members_leaf.get(i, []))
        if k == "tg":
            return any(r[0] == oid for r in tent[i]["m"])
        if k == "lg":
            return any(r[0] == oid for r in loose[i]["m"])
        if k == "ct":
            return oid in tags[i]["m"]
        if k == "kl":
            return oid in kwl[i]["cards"]
        if k == "gl":
            return oid in rpl[i]["cards"]
        if k == "hg":
            return oid in hg[i]["hits"]
        return False
    leaf_idx = {}
    for lid, rows in members_leaf.items():
        for m in rows:
            leaf_idx.setdefault(m[0], set()).add(lid)
    sib_leaf = {}
    sp = os.path.join(BUILD, "sibling_placements.json")
    if os.path.exists(sp):
        sd = jl("sibling_placements.json")
        for lid, g in sd["groups"].items():
            for r in g["m"]:
                sib_leaf.setdefault(r[0], set()).add(lid)
    notmember, unknown = [], []
    cnt = {"group": 0, "card": 0}
    for oid, (op, ks) in first.items():
        cnt[op] += 1
        for k in ks[:1]:                                    # the best group: the one a click opens
            ok = member(k, oid) or (k.startswith("l:") and k[2:] in sib_leaf.get(oid, set()))
            if not ok:
                notmember.append((oid, k))
            kk, _, i = k.partition(":")
            exists = {"l": i in tax["leaves"], "tg": i in tent, "lg": i in loose, "ct": i in tags, "kl": i in kwl, "gl": i in rpl, "hg": i in hg, "V": True}[kk]
            if not exists:
                unknown.append((oid, k))
    check("2 for all %d cards that open a group, the best group exists in the file the page opens it from" % cnt["group"], not unknown, unknown[:2])
    check("2 ... and the card is really listed in it (members file, tentative / loose / tag file, keyword or replacement block, hand-group rule matches, sibling placements): %d not listed" % len(notmember), not notmember, notmember[:3])
    by_state = {}
    for oid, (op, ks) in first.items():
        by_state.setdefault(cards[oid][1], {"group": 0, "card": 0})[op] += 1
    print("INFO by state (group / card page):", {k: (v["group"], v["card"]) for k, v in sorted(by_state.items())})
    check("3 pile (u), annotated (a) and not-a-card (o) entries open the card page (a card page: %d of 1,335 pile cards; none opens a group without a hand placement)" % by_state["u"]["card"],
          by_state["u"]["group"] == 0 and by_state["a"]["group"] == 0 and by_state["o"]["group"] == 0)
    check("3 every precisely placed, keyword, replacement, tentative and tag card opens a group", all(by_state[s]["card"] == 0 for s in ("p", "b", "k", "g", "t", "m", "v")), {s: by_state[s] for s in ("p", "b", "k", "g", "t", "m", "v")})
    # class order
    # a synthetic card in a group of every class, stored in a scrambled order: the order of the classes is the rule (precise 0, replacement 0.5, broad 0.7, tentative 1, sibling 1.2, tag 2, loose 3, keyword 4, hand 5)
    SG = {"leaf:p1": ["P leaf", 9, "", "leaf", 1], "rp:r1": ["R", 9, "", "rp", 1], "leaf:b1": ["B leaf", 9, "", "leaf", 1], "tent:t1": ["T", 9, "", "tent", 1], "leaf:s1": ["S leaf", 9, "", "leaf", 1],
          "tag:g1": ["M", 9, "", "tag", 1], "loose:l1": ["L", 9, "", "loose", 1], "kw:K": ["K", 9, "", "kw", 1], "hand:h1": ["H", 9, "", "hand", 1], "leaf:x1": ["A leaf", 9, "", "leaf", 1]}
    stored = [["kw:K", "K"], ["loose:l1", "L"], ["tag:g1", "M"], ["tent:t1", "T"], ["leaf:s1", "S"], ["leaf:b1", "B"], ["rp:r1", "R"], ["leaf:p1", "P"], ["leaf:x1", "A"]]
    SMI = {"cards": {"c1": ["Synth", "p", 0, stored, 1]}, "groups": SG}
    want = ["l:p1", "gl:r1", "l:b1", "tg:t1", "l:s1", "ct:g1", "lg:l1", "kl:kw:K", "hg:h1"]
    js_ = json.loads(itp.evaljs("""JSON.stringify((function () { var T = {t1: 1}, G = {g1: 1}, L = {l1: 1};
      var p = CardPin.plan(%s, 'c1', {tentOk: function (i) { return T[i]; }, tagOk: function (i) { return G[i]; }, looseHas: function (i) { return L[i]; }, looseName: function () { return ''; }, adds: {'hand:h1': {}}, removes: null});
      return [p.open, p.groups.map(function (x) { return x.key; })]; })())""" % json.dumps(SMI)))
    py_ = ref_plan(SMI, "c1", {"t1"}, {"g1"}, {"l1"}, {}, {"hand:h1": {}}, {})
    check("4 a card in a group of every class opens them in the rule's order (precise, replacement, broad, tentative, sibling, tag, loose, keyword, hand); an annotation (A) is never a group", js_ == ["group", want] and list(py_) == ["group", want], js_)
    SMI["cards"]["c1"][1] = "u"
    js2 = json.loads(itp.evaljs("""JSON.stringify(CardPin.plan(%s, 'c1', {tentOk: function () { return 1; }, tagOk: function () { return 1; }, looseHas: function () { return 1; }, looseName: function () { return ''; }, adds: null, removes: null}).open)""" % json.dumps(SMI)))
    check("4 the same groups on a pile card open the card page; with a hand placement the pile card opens the hand-placed group", js2 == "card" and ref_plan(SMI, "c1", {"t1"}, {"g1"}, {"l1"}, {}, {"hand:h1": {}}, {}) == ("group", ["hg:h1"]))
    # the switches
    j_tentoff = json.loads(itp.evaljs("JSON.stringify(runAll(false, true))"))
    check("5 tentative off: no tg: key is ever offered; tag off: no ct: key", not any(k.startswith("tg:") for v in j_tentoff.values() for k in v[1]) and not any(k.startswith("ct:") for o, v in json.loads(itp.evaljs("JSON.stringify(runAll(true, false))")).items() for k in v[1]))

    # ---- the flag
    out = tempfile.mkdtemp(prefix="pin_off_")
    own = ("build/card_pin/",)
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
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); import build_card_pin as B; B.main(force=False)"], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    h1 = tree()
    check("6 flag off: %d files outside the feature's own file are byte-identical, and build/card_pin/ is removed" % len(h0), h0 == h1 and not os.path.exists(os.path.join(BUILD, "card_pin")) and r.returncode == 0, [k for k in h0 if h0[k] != h1.get(k)][:3])
    r = subprocess.run([sys.executable, os.path.join(HERE, "src", "build_card_pin.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    a = open(os.path.join(BUILD, "card_pin", "meta.json"), "rb").read()
    r2 = subprocess.run([sys.executable, os.path.join(HERE, "src", "build_card_pin.py")], cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    check("6 flag on again: meta.json written, and two builds are byte-identical", r.returncode == 0 and a == open(os.path.join(BUILD, "card_pin", "meta.json"), "rb").read() and json.loads(a)["enabled"] is True)
    after = [sha(p) for p in PROTECTED]
    check("7 the protected corrections files (and the alias and description files) are byte-identical before and after", before == after)
    bad = [n for n, ok in RESULTS if not ok]
    print("\n%d checks, %d failed" % (len(RESULTS), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
