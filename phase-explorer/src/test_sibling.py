#!/usr/bin/env python3
"""Tests for the sibling-of-leaf rule (build/sibling_placements.json, src/build_sibling.py). About three minutes (it re-runs the taxonomy in memory twice).

    python src/test_sibling.py

An independent re-derivation of the rule from the parser's abilities (compared with the file), the 27 abilities that were read before the build, that every placement is exact / unflagged / held for a backoff reason / on a
card that is not placed, that no card changes bucket and no figure moves, reversibility through the edit panel's endpoint (a recorded removal), determinism and the flag.
"""
import collections
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as MC

HERE = MC.HERE
B = os.path.join(HERE, "build")
FAILS = []
READ = {"Coat of Arms", "Worldly Tutor", "Ashiok, Nightmare Weaver", "Aku Djinn", "Faerie Macabre", "Mortify", "Merfolk Spy", "Silverquill Lecturer", "Sylvan Tutor", "Aven Windreader", "Vodalian Illusionist", "Memnarch",
        "Share the Spoils", "Clear the Land", "Evelyn, the Covetous", "Discordant Spirit", "Broadside Bombardiers", "Maralen, Fae Ascendant", "Grimoire Thief", "Venerated Loxodon", "Night of Souls' Betrayal", "Dream Tides",
        "Wicker Picker", "Putrefy", "Summoner's Egg", "Agent of Treachery", "Myr Mindservant"}


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" - " + str(detail)) if detail else ""))
    if not ok:
        FAILS.append(name)


def jl(n):
    return json.load(io.open(os.path.join(B, n), encoding="utf-8"))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run(code):
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); " + code], cwd=HERE, capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1"))
    return r.stdout + r.stderr


def main():
    sib = jl("sibling_placements.json")
    idx = jl("manual_index.json")
    C, G = idx["cards"], idx["groups"]
    m = sib["meta"]
    tax = jl("ability_taxonomy.json")
    check("27 abilities on 27 cards in 20 groups (21 tentative cards, 6 pile cards)", (m["abilities"], m["cards"], m["groups"], m["cards_by_state"]) == (27, 27, 20, {"tentative": 21, "unorganized": 6}), (m["abilities"], m["cards"], m["groups"], m["cards_by_state"]))
    names = {C[o][0] for o in sib["by_card"]}
    check("they are exactly the 27 abilities read before the build (seed 20261080)", names == READ, sorted(names ^ READ))
    check("the read is recorded: 24 correct, 2 loose, 1 wrong, bar no more than 2 wrong", m["read"] == {"seed": 20261080, "abilities": 27, "correct": 24, "loose": 2, "wrong": 1, "bar": "no more than 2 wrong"})
    check("the placement is labelled tentative, not checked and counted in no figure", "Tentative placement (sibling)" in m["label"] and "Not checked" in m["label"] and "not counted in any figure" in m["label"] and m["method"] == "sibling_tentative")
    # independent re-derivation
    argv, sys.argv = sys.argv, sys.argv[:1]
    import build_ability_taxonomy as BT
    BT.dump = lambda *a, **k: None
    with contextlib.redirect_stdout(io.StringIO()):
        S = BT.main()
    sys.argv = argv
    CAN = ["sign", "recip", "frm", "to", "ctr", "who", "mods", "obj", "ctrl", "quant", "props", "kw", "dur", "cond", "wrap", "chain", "tok"]
    leafsig = collections.defaultdict(list)
    for lid, l in S["tax"]["leaves"].items():
        d = dict(p.split("=", 1) for p in l["sig"].split(" · "))
        leafsig[(d["fam"], d["ftype"], frozenset("%s=%s" % (k, v) for k, v in d.items() if k not in ("fam", "ftype") and v not in ("", "-")))].append(lid)
    got = set()
    for a in S["A"]:
        o = a["oid"]
        if o not in C or C[o][1] not in ("u", "t", "a", "m") or a["state"] != "unplaced" or a["pre"] or not a["f"].get("usable"):
            continue
        if a["reason"] not in ("rare_object", "rare_verb_parameter", "rare_effect_type", "below_minimum_size"):
            continue
        f = a["f"]
        ls = [l for l in leafsig.get((f["fam"], f["ftype"], frozenset("%s=%s" % (k, f[k]) for k in CAN if f.get(k) not in ("", "-", None))), []) if not S["tax"]["leaves"][l]["flags"]]
        if len(ls) == 1:
            got.add((o, ls[0]))
    have = {(o, l) for o, ls in sib["by_card"].items() for l in ls}
    check("the file equals an independent re-derivation of the rule from the parser's abilities", got == have, (len(got), len(have)))
    check("every group is an existing, unflagged leaf of 5 or more cards", all(l in tax["leaves"] and not tax["leaves"][l]["flags"] and tax["leaves"][l]["cards"] >= 5 for l in sib["groups"]))
    check("every card is one that is not precisely placed (pile, tentative, annotation or tag)", all(C[o][1] in ("u", "t", "a", "m") for o in sib["by_card"]))
    check("no card is a member of the leaf it is placed in (they are held out of it)", all(not any(x[0] == "leaf:" + l and x[1] in "PB" for x in C[o][3]) for o, ls in sib["by_card"].items() for l in ls))
    check("every placement is a source ('S') in the card index, and nothing else changed", all(any(x == ["leaf:" + l, "S"] for x in C[o][3]) for o, ls in sib["by_card"].items() for l in ls) and sum(1 for c in C.values() for x in c[3] if x[1] == "S") == 27)
    states = collections.Counter(c[1] for c in C.values())
    check("no card changed bucket: tentative 2,093 / annotation 960 / tag 1,205 / pile 1,335 / placed 27,590 / not cards 5,738", (states["t"], states["a"], states["m"], states["u"], sum(states[k] for k in "pbkgv"), states["o"]) == (2093, 960, 1205, 1335, 27590, 5738),
          dict(states))
    figs = tax["totals"]
    check("the first two figures are as generated (24,336 = 73.3%, 27,590 = 83.1%)", (figs["headline"]["cards"], figs["headline"]["pct"], figs["with_broad"]["cards"], figs["with_broad"]["pct"]) == (24336, 73.3, 27590, 83.1))
    # reversibility through the endpoint logic (temp file)
    o = next(o for o in sib["by_card"] if C[o][1] == "u")
    gid = "leaf:" + sib["by_card"][o][0]
    MC.CORR = os.path.join(tempfile.mkdtemp(prefix="sibling_"), "m.json")
    j = MC.apply_edit({"oid": o, "group": gid, "action": "remove", "note": "not right"}, index=idx, path=MC.CORR)
    res = MC.resolve(idx, MC.load_doc(MC.CORR))
    check("a sibling placement can be removed: recorded, shown, no generated count changes", j["ok"] and res["counts"]["removals_recorded"] == 1 and res["reconciliation"]["unorganized"] == 1335 and res["reconciliation"]["sum"] == 38921, res["counts"]["removals_recorded"])
    MC.apply_edit({"oid": o, "group": gid, "action": "clear"}, index=idx, path=MC.CORR)
    check("and the removal can be undone", not MC.load_doc(MC.CORR)["edits"])
    page = open(os.path.join(HERE, "reports", "browse.html"), encoding="utf-8").read()
    check("the page has its own switch, its own badge and the 'counted in no figure' wording", all(x in page for x in ("showsib", "Show sibling placements", "b-sib", "counted in no figure")))
    # determinism and the flag (the file on disk was built before this test: a rebuild must reproduce it)
    guard = ["build/ability_taxonomy.json", "build/ability_taxonomy_lookup.json", "build/tentative_placements.json", "build/annotation_placements.json", "build/tag_placements.json", "build/loose_groups.json"]
    before = {g: sha(os.path.join(HERE, g)) for g in guard}
    h1 = (sha(os.path.join(B, "sibling_placements.json")), sha(os.path.join(B, "sibling_ledger.json")))
    run("import build_sibling as S; S.main()")
    h2 = (sha(os.path.join(B, "sibling_placements.json")), sha(os.path.join(B, "sibling_ledger.json")))
    check("a rebuild is byte-identical (placements and ledger)", h1 == h2)
    check("the six-figure layers are byte-identical around the build", all(sha(os.path.join(HERE, g)) == before[g] for g in guard))
    run("import build_sibling as S; S.SIBLING_RULE = False; S.main()")
    check("flag off: the file is removed (its ledger stays only if left from a build: removed too)", not os.path.exists(os.path.join(B, "sibling_placements.json")))
    run("import build_sibling as S; S.main()")
    check("flag on again: the identical files come back", (sha(os.path.join(B, "sibling_placements.json")), sha(os.path.join(B, "sibling_ledger.json"))) == h1)
    print("\n%d failure(s)" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
