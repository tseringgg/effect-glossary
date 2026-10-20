#!/usr/bin/env python3
"""Checks for the "Possible matches" tab's data and logic (no browser): build/suggested_cards from src/build_suggested_cards.py and reports/suggested.js.

    python src/test_suggested_cards.py        (needs dukpy; builds only into temporary folders (SUGGESTED_OUT) and uses temporary corrections files)

Covered: the flag off writes nothing; two builds with the flag on are byte-identical; the stored rows are exactly the first 5 rows of each card (re-derived here from the raw suggestion files with separate code), with the same
score and sources, never below 0.50, never a member, sorted by score then popularity; the per-step counts in meta.json; the community-tag lens (carriers of the tag that are not in the group); the source files are
byte-identical before and after; the JavaScript (suggested.js) agrees with an independent Python implementation on real data with and without hand edits, at every floor, with and without already-placed cards; every
group's page key maps back to its id; an Add of a suggested pair through the existing write path (on a temporary copy) counts exactly as the resolver counts it and moves none of the six figures or the reconciliation,
and an undo removes it; the real corrections files are hashed before and after.
"""
import collections
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

import dukpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as MC

HERE = MC.HERE
BUILD = os.path.join(HERE, "build")
REAL = os.path.join(HERE, "corrections", "manual_placements.json")
FAILS = []


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" - " + str(detail)[:300]) if detail else ""))
    if not ok:
        FAILS.append(name)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def tree(d):
    m = {}
    for dd, ds, fs in os.walk(d):
        for f in fs:
            p = os.path.join(dd, f)
            m[os.path.relpath(p, d).replace(os.sep, "/")] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return m


def build(out, force):
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); import build_suggested_cards as S; S.main(force=%s)" % force], cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, SUGGESTED_OUT=out, PYTHONIOENCODING="utf-8"))
    return r.returncode, r.stdout + r.stderr


def jl(*p):
    with open(os.path.join(BUILD, *p), encoding="utf-8") as fh:
        return json.load(fh)


def py_visible(idx, res, qrows, prows, floor, inc, keep):
    C = idx["cards"]
    out, hid_h, hid_n = [], 0, 0
    for rows, placed in ((qrows, False), (prows, True)):
        if placed and not inc:
            continue
        for r in rows:
            if r[0] not in C or r[1] < floor - 1e-9:
                continue
            if r[0] in keep:
                out.append(r)
            elif r[0] in res["marked"]:
                hid_n += 1
            elif r[0] in res["adds"]:
                hid_h += 1
            else:
                out.append(r)
    out.sort(key=lambda r: (-r[1], C[r[0]][4] if C[r[0]][4] is not None else 10 ** 9, C[r[0]][0], r[0]))
    return [r[0] for r in out], hid_h, hid_n


def main():
    real_before = (sha(REAL), sha(REAL + ".bak"), sha(os.path.join(HERE, "corrections", "hand_groups.json")), sha(os.path.join(HERE, "corrections", "hand_groups.json.bak")))
    src_files = glob.glob(os.path.join(BUILD, "text_sug", "**", "*.json"), recursive=True) + [os.path.join(BUILD, n) for n in ("manual_index.json", "manual_suggestions.json", "tag_placements.json", "hand_group_hits.json")]
    src_before = {f: sha(f) for f in src_files}
    tmp = tempfile.mkdtemp(prefix="suggested_")
    idx = MC.load_index()
    C, G = idx["cards"], idx["groups"]

    # ---- the flag
    off = os.path.join(tmp, "off")
    rc, out = build(off, False)
    check("flag off: nothing is written (no folder, no report)", rc == 0 and not os.path.exists(off) and "nothing written" in out, out.strip()[-120:])
    check("flag on by default in the script (False writes nothing)", "SUGGESTED_CARDS_VIEW = True" in open(os.path.join(HERE, "src", "build_suggested_cards.py"), encoding="utf-8").read())
    # ---- on: two identical builds
    a, b = os.path.join(tmp, "a"), os.path.join(tmp, "b")
    rc1, o1 = build(a, True)
    rc2, o2 = build(b, True)
    ta, tb = tree(a), tree(b)
    check("flag on: two builds in a row are byte-identical (%d files)" % len(ta), rc1 == 0 and rc2 == 0 and ta == tb and len(ta) > 100, (rc1, rc2, o1.strip()[-200:]))
    meta = json.load(open(os.path.join(a, "meta.json"), encoding="utf-8"))
    realdir = os.path.join(BUILD, "suggested_cards")
    if os.path.isdir(realdir):
        tr = tree(realdir)
        ta2 = {k: v for k, v in ta.items() if k != "suggested-cards.md"}
        check("the generated build/suggested_cards is byte-identical to a fresh build (%d files)" % len(tr), tr == ta2, [k for k in set(tr) | set(ta2) if tr.get(k) != ta2.get(k)][:3])
    else:
        check("build/suggested_cards has been generated (SUGGESTED_CARDS_VIEW is True)", False)
    gi = {v[0]: g for g, v in meta["groups"].items()}
    li = {v[0]: g for g, v in meta["lens"].items()}

    # ---- re-derive the expected pairs from the raw suggestion files, separate code
    tm = jl("text_sug", "meta.json")
    raw = {}
    for o, rr in jl("text_sug", "queue.json")["cards"].items():
        raw[o] = [(r[0], r[1], r[2], r[3], r[4:7]) for r in rr[:5]]
    for fn in glob.glob(os.path.join(BUILD, "text_sug", "c", "*.json")):
        for o, rr in json.load(open(fn, encoding="utf-8")).items():
            raw[o] = [(tm["groups"][r[0]], r[1] / 1000.0, "kw" if r[2] < 0 else "text", r[5] if r[2] < 0 else "", [] if r[2] < 0 else r[2:5]) for r in rr[:5]]
    mem = collections.defaultdict(set)
    for o, c in C.items():
        for g in c[3]:
            mem[g[0]].add(o)
    for slug, g in jl("hand_group_hits.json")["groups"].items():
        mem["hand:" + slug] |= set(g["hits"])
    exp = {}
    for o, rows in raw.items():
        if C[o][1] == "o":
            continue
        for gid, sc, srcs, why, ref in rows:
            if gid in G and G[gid][4] and round(sc, 3) >= 0.5 - 1e-9 and o not in mem[gid]:
                exp[(o, gid)] = (round(sc, 3), srcs)
    got, bad_order, below, member_hits, wrong_class = {}, 0, 0, 0, 0
    for i, gid in gi.items():
        for tag, queue in (("q", True), ("p", False)):
            fn = os.path.join(a, "g", "%d%s.json" % (i, tag))
            if not os.path.exists(fn):
                continue
            rows = json.load(open(fn, encoding="utf-8"))
            keys = [(-r[1], C[r[0]][4] if C[r[0]][4] is not None else 10 ** 9, C[r[0]][0], r[0]) for r in rows]
            bad_order += keys != sorted(keys)
            for r in rows:
                got[(r[0], gid)] = (r[1], r[2])
                below += r[1] < 0.5 - 1e-9
                member_hits += r[0] in mem[gid]
                wrong_class += (C[r[0]][1] in "utam") != queue
    check("the stored pairs are exactly the expected pairs (%d), with the same scores and sources" % len(exp), got == exp, (len(got), len(exp), [k for k in exp if got.get(k) != exp[k]][:2]))
    check("no stored row is below 0.50, a member of its group, or in the wrong state file; every file is sorted by score, popularity, name", below == 0 and member_hits == 0 and wrong_class == 0 and bad_order == 0, (below, member_hits, wrong_class, bad_order))
    cnt_ok = True
    for gid, (i, qc, pc) in meta["groups"].items():
        for lst, counts in ((exp_rows(got, gid, C, True), qc), (exp_rows(got, gid, C, False), pc)):
            cnt_ok = cnt_ok and counts == [sum(1 for s in lst if s >= st - 1e-9) for st in meta["steps"]]
    check("meta.json counts per slider step (queue cards and already-placed cards) equal the counts from the files", cnt_ok)
    check("no pair is stored for a group that is not offered for hand placement", all(G[g][4] for _, g in got))
    # ---- the lens
    import tag_layer_filter as F
    import probe_tags as PT
    fn_ = F.functional(PT.load(PT.NEW))
    ct = F.card_tags(fn_)
    tagp = jl("tag_placements.json")["groups"]
    lens_exp = collections.defaultdict(set)
    for o, ts in ct.items():
        if o in C and C[o][1] != "o":
            for t in ts:
                gid = "tag:" + t
                if t in tagp and gid in G and G[gid][4] and o not in mem[gid]:
                    lens_exp[gid].add(o)
    lens_got = collections.defaultdict(set)
    sorted_ok, class_ok = True, True
    for j, gid in li.items():
        for tag, queue in (("q", True), ("p", False)):
            p_ = os.path.join(a, "t", "%d%s.json" % (j, tag))
            if os.path.exists(p_):
                oids = json.load(open(p_, encoding="utf-8"))
                lens_got[gid] |= set(oids)
                ks = [(C[o][4] if C[o][4] is not None else 10 ** 9, C[o][0], o) for o in oids]
                sorted_ok = sorted_ok and ks == sorted(ks)
                class_ok = class_ok and all((C[o][1] in "utam") == queue for o in oids)
    check("the community-tag lens holds exactly the cards that carry a group's tag and are not in the group (%d groups, %d pairs), sorted by popularity" % (len(lens_exp), sum(map(len, lens_exp.values()))),
          lens_got == lens_exp and sorted_ok and class_ok and set(meta["lens"]) == set(lens_exp), (len(lens_got), len(lens_exp)))
    check("the lens slug in meta.json is the tag's slug", all(v[3] == fn_[g[4:]]["slug"] for g, v in meta["lens"].items()))

    # ---- JS = Python
    src = open(os.path.join(HERE, "reports", "manualedit.js"), encoding="utf-8").read() + "\n" + open(os.path.join(HERE, "reports", "suggested.js"), encoding="utf-8").read()
    pile = [o for o, c in sorted(C.items()) if c[1] == "u"]
    placed = [o for o, c in sorted(C.items()) if c[1] == "p"]

    def entry(action, gid, name):
        return {"action": action, "date": "2026-10-17T10:00:00", "note": "", "group_name": name, "source_at_edit": {"status": "unorganized", "reason": {"code": 2, "text": "x"}}}
    big = sorted(meta["groups"], key=lambda g: -(meta["groups"][g][1][0] + meta["groups"][g][2][0]))[:6]
    small = [g for g in sorted(meta["groups"]) if 0 < meta["groups"][g][1][2] <= 5][:6]
    tagg = sorted(meta["lens"])[:5]
    gsel = big + small + tagg
    # edits on cards that really are suggested for the selected groups: a hand add in the group, a hand add elsewhere, a nothing-fits mark
    docs = {"no edits": {"edits": {}, "history": [], "revision": 0}}
    ed = {}
    for g in big[:2]:
        i = meta["groups"][g][0]
        rows = json.load(open(os.path.join(a, "g", "%dq.json" % i), encoding="utf-8"))
        o1, o2, o3 = rows[0][0], rows[1][0], rows[2][0]
        ed[o1] = {"name": C[o1][0], "groups": {g: entry("add", g, G[g][0])}}
        ed[o2] = {"name": C[o2][0], "groups": {MC.NOFIT: entry("nofit", MC.NOFIT, "")}}
        other = next(x for x in sorted(G) if G[x][4] and x != g and not any(h[0] == x for h in C[o3][3]))
        ed[o3] = {"name": C[o3][0], "groups": {other: entry("add", other, G[other][0])}}
    docs["some edits"] = {"edits": ed, "history": [], "revision": 3}
    ok_all, n_cases, mism = True, 0, []
    for label, doc in docs.items():
        res = MC.resolve(idx, doc)
        jres = dukpy.evaljs([src, "Manual.resolve(dukpy.index, dukpy.doc)"], index=idx, doc=doc)
        for gid in gsel:
            q = json.load(open(os.path.join(a, "g", "%dq.json" % meta["groups"][gid][0]), encoding="utf-8")) if gid in meta["groups"] and meta["groups"][gid][1][0] else []
            p = json.load(open(os.path.join(a, "g", "%dp.json" % meta["groups"][gid][0]), encoding="utf-8")) if gid in meta["groups"] and meta["groups"][gid][2][0] else []
            keeps = [{}, {ed_o: 1 for ed_o in list(ed)[:1]}]
            cases = [(fl, inc, kp) for fl in (0.5, 0.7, 0.9) for inc in (False, True) for kp in keeps]
            js = dukpy.evaljs([src, "var out = []; for (var i = 0; i < dukpy.cases.length; i++) { var c = dukpy.cases[i]; var v = Suggested.visible(dukpy.index, dukpy.res, dukpy.gid, dukpy.q, dukpy.p, {floor: c[0], includePlaced: c[1], keep: c[2]}); "
                              "out.push([v.rows.map(function (r) { return r.oid; }), v.hidden.handled, v.hidden.nofit]); } out"], index=idx, res=jres, gid=gid, q=q, p=p, cases=[list(c) for c in cases])
            for c, j in zip(cases, js):
                n_cases += 1
                pv = py_visible(idx, res, q, p, c[0], c[1], c[2])
                if [j[0], j[1], j[2]] != [pv[0], pv[1], pv[2]]:
                    ok_all = False
                    mism.append((label, gid, c[:2], len(j[0]), len(pv[0])))
        # the lens
        for gid in tagg:
            j_ = meta["lens"][gid][0]
            lq = json.load(open(os.path.join(a, "t", "%dq.json" % j_), encoding="utf-8")) if meta["lens"][gid][1] else []
            lp = json.load(open(os.path.join(a, "t", "%dp.json" % j_), encoding="utf-8")) if meta["lens"][gid][2] else []
            for inc in (False, True):
                skip = {o: 1 for o in lq[:3]}
                js = dukpy.evaljs([src, "Suggested.lens(dukpy.index, dukpy.res, dukpy.q, dukpy.p, {includePlaced: dukpy.inc, keep: {}, skip: dukpy.skip})"], index=idx, res=jres, q=lq, p=lp, inc=inc, skip=skip)
                n_cases += 1
                want = [o for o in (lq + (lp if inc else [])) if o not in skip and o not in res["marked"] and o not in res["adds"]]
                want.sort(key=lambda o: (C[o][4] if C[o][4] is not None else 10 ** 9, C[o][0], o))
                if [r["oid"] for r in js["rows"]] != want:
                    ok_all = False
                    mism.append((label, gid, "lens", inc))
    check("suggested.js agrees with the independent Python implementation (%d cases: 2 edit sets, 17 groups, 3 floors, with and without already-placed cards, with and without a kept row, and the lens)" % n_cases, ok_all, mism[:3])
    gk = dukpy.evaljs([src, "var o = {}; for (var i = 0; i < dukpy.gids.length; i++) { var g = dukpy.gids[i]; var k = Manual.goKey(g); o[g] = Suggested.gidOfKey(k, g.indexOf('tent:') === 0); } o"], gids=[g for g in G if G[g][4]])
    check("every offered group's page key maps back to its id (%d groups)" % len(gk), all(k == v for k, v in gk.items()), [k for k, v in gk.items() if k != v][:3])

    # ---- Add / undo through the existing write path, on a temporary copy
    tdoc = os.path.join(tmp, "m.json")
    MC.CORR = tdoc
    base = MC.resolve(idx, MC.empty_doc())["reconciliation"]
    pairs = {}
    for st, label in (("u", "pile"), ("t", "tentative"), ("p", "placed")):
        for gid in sorted(meta["groups"]):
            i = meta["groups"][gid][0]
            fq = os.path.join(a, "g", "%d%s.json" % (i, "p" if st == "p" else "q"))
            if os.path.exists(fq):
                for r in json.load(open(fq, encoding="utf-8")):
                    if C[r[0]][1] == st and r[1] >= 0.7:
                        pairs[label] = (r[0], gid)
                        break
            if label in pairs:
                break
    check("a suggested pair was found for a pile, a tentative and a placed card", len(pairs) == 3, pairs)
    for label, (o, gid) in pairs.items():
        r = MC.apply_edit({"oid": o, "group": gid, "action": "add", "note": ""}, index=idx, path=tdoc)
        doc = MC.load_doc(tdoc)
        res = MC.resolve(idx, doc)
        c = res["counts"]
        want = {"pile": ("placed_by_hand_new", 1), "tentative": ("confirmed_by_hand", 1), "placed": ("precise_cards_with_edits_not_counted", 1)}[label]
        rec = res["reconciliation"]
        check("Add of a suggested %s card (%s) is counted as the resolver counts it (%s +1) and the reconciliation still sums to 38,921" % (label, C[o][0], want[0]), r["changed"] and c[want[0]] == want[1] and rec["sum"] == 38921, (c, rec))
        if label == "pile":
            check("the pile add moves the hand line only: placed/tentative/annotation/tag unchanged, unorganized falls by 1", all(rec[k] == base[k] for k in ("placed", "tentative", "annotation", "tag", "not_cards")) and rec["hand"] == 1 and rec["unorganized"] == base["unorganized"] - 1, rec)
        MC.apply_edit({"oid": o, "group": gid, "action": "clear"}, index=idx, path=tdoc)
        check("undo (clear) of the %s add removes the edit" % label, not MC.load_doc(tdoc)["edits"])
    # ---- nothing else moved
    src_after = {f: sha(f) for f in src_files}
    check("the source files this layer reads are byte-identical before and after (%d files)" % len(src_files), src_before == src_after)
    real_after = (sha(REAL), sha(REAL + ".bak"), sha(os.path.join(HERE, "corrections", "hand_groups.json")), sha(os.path.join(HERE, "corrections", "hand_groups.json.bak")))
    check("the real corrections files (manual_placements.json, hand_groups.json and their backups) are byte-identical before and after", real_before == real_after)
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d failed" % len(FAILS) if FAILS else "\nall passed")
    return 1 if FAILS else 0


def exp_rows(got, gid, C, queue):
    return [sc for (o, g), (sc, _) in got.items() if g == gid and ((C[o][1] in "utam") == queue)]


if __name__ == "__main__":
    sys.exit(main())
