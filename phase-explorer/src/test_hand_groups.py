#!/usr/bin/env python3
"""Tests for hand-defined groups: the rule evaluator (src/hand_groups.py), the build (src/build_hand_groups.py), the seeded win/lose group on the real cards, and the endpoint rules for hand:<slug> ids.

    python src/test_hand_groups.py

Synthetic cases first (folding, sentence-level 'not', keyword and tag rules, literal phrases, validation, retirement, determinism, the flag), then the real data (the 107 text hits read by hand on 2026-10-15, the poison
reminder, the two cards the narrower patterns missed), then the endpoint (POST /api/manual logic against a copy of the index with an extra retired group; a TEMP corrections file only).
"""
import copy
import hashlib
import io
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hand_groups as H
import manual_common as MC
import build_hand_groups as BH

HERE = H.HERE
FAILS = []
REAL_CORR = os.path.join(HERE, "corrections", "manual_placements.json")


def check(name, ok, detail=""):
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" - " + str(detail)) if detail else ""))
    if not ok:
        FAILS.append(name)


def jl(n):
    return json.load(io.open(os.path.join(HERE, "build", n), encoding="utf-8"))


def grp(rules, name="Test group", **kw):
    return dict({"name": name, "rules": rules}, **kw)


def main():
    real_hash = hashlib.sha256(open(REAL_CORR, "rb").read()).hexdigest() if os.path.exists(REAL_CORR) else None
    T = {"text": {"any": ["loses the game", "lose the game"], "not": ["poison counters"]}}
    r1 = dict(id="r1", type="text", confidence=0.7, **T["text"])
    # ---- folding and sentences
    check("curly apostrophes and capitals are folded", H.match_text({"any": ["can't win the game"]}, "You Can’t Win the Game.") is not None)
    check("a phrase matches only inside one sentence's text (no match across a full stop)", H.match_text({"any": ["lose. the game"]}, "You lose. The game ends.") is None)
    check("the poison reminder alone does not match", H.match_text(r1, "(A player with ten or more poison counters loses the game.)") is None)
    s = H.match_text(r1, "Flying\nIf you don't, you lose the game. (A player with ten or more poison counters loses the game.)")
    check("a card with a real sentence and the reminder matches on the real sentence", s == "If you don't, you lose the game.", s)
    check("'not' is per sentence: a real sentence elsewhere still matches", H.match_text(r1, "Infect (A player with ten or more poison counters loses the game.)\nWhen this dies, target player loses the game.") == "When this dies, target player loses the game.")
    check("the snippet is the sentence as written on the card (capitals kept), at most 200 characters", len(H.match_text({"any": ["x"]}, "X" * 500) or "") == 200 and H.match_text({"any": ["win the game"]}, "You WIN the game.") == "You WIN the game.")
    check("phrases are literal: regular-expression characters mean nothing", H.match_text({"any": ["a.*b"]}, "axxb") is None and H.match_text({"any": ["a.*b"]}, "a.*b") is not None)
    big = "word " * 200000 + "you lose the game."
    import time
    t0 = time.time()
    H.match_text(r1, big)
    check("a very long text is evaluated in well under a second (no pattern can hang it)", time.time() - t0 < 2.0, "%.2fs" % (time.time() - t0))
    # ---- keyword, tag, several rules
    doc = {"version": 1, "groups": {"mixed": grp([dict(id="t", type="text", any=["exile the top card"], confidence=0.5), dict(id="k", type="keyword", keyword="First Strike", confidence=0.6), dict(id="g", type="tag", tag="some-tag", confidence=0.4)])}}
    check("a valid document has no problems", H.validate(doc) == [], H.validate(doc))
    ev = H.evaluate(doc, {"a": "Exile the top card of your library.", "b": "Flying", "c": ""}, {"FirstStrike": {"b", "c"}, "Flying": {"a"}}, {"some-tag": {"a", "c"}})["mixed"]["hits"]
    check("keyword names ignore case and spaces; text, keyword and tag rules each hit", set(ev) == {"a", "b", "c"} and [h[0] for h in ev["a"]] == ["t", "g"] and [h[0] for h in ev["b"]] == ["k"] and [h[0] for h in ev["c"]] == ["k", "g"], ev)
    check("a hit records its reason", ev["b"][0][1] == "carries the keyword First Strike" and ev["a"][1][1] == "carries the community tag some-tag")
    # ---- validation
    bad = {"groups": {"Bad_Slug": grp([r1]), "ok-one": grp([r1], name="A"), "ok-two": grp([r1], name="A"), "short": grp([r1]), "no-rules-ok": {"name": "B"}, "bad-conf": grp([dict(r1, confidence=0)], name="C"),
                      "bad-conf2": grp([dict(r1, confidence=1.5)], name="C2"), "bool-conf": grp([dict(r1, confidence=True)], name="C3"), "dup-id": grp([r1, r1], name="D"), "empty-any": grp([dict(id="x", type="text", any=[])], name="E"),
                      "long-phrase": grp([dict(id="x", type="text", any=["y" * 200])], name="F"), "bad-type": grp([dict(id="x", type="regex", any=["a"])], name="G"), "no-name": {"rules": []},
                      "retired-str": grp([r1], name="H", retired="yes"), "no-kw": grp([dict(id="x", type="keyword")], name="I"), "no-tag": grp([dict(id="x", type="tag", tag="")], name="J"),
                      "many": grp([dict(id="r%d" % i, type="keyword", keyword="k") for i in range(25)], name="K")}}
    probs = H.validate(bad)
    for needle in ("Bad_Slug", "same", "%r" % "short", "bad-conf", "bool-conf", "dup-id", "empty-any", "long-phrase", "bad-type", "no-name", "retired-str", "no-kw", "no-tag", "many"):
        pass
    want = ["'Bad_Slug'", "also used by", "'bad-conf'", "'bad-conf2'", "'bool-conf'", "'dup-id'", "'empty-any'", "'long-phrase'", "'bad-type'", "'no-name'", "'retired-str'", "'no-kw'", "'no-tag'", "'many'"]
    miss = [w for w in want if not any(w in p for p in probs)]
    check("every kind of invalid group or rule is reported, with the group named", not miss, miss)
    check("a document without a groups object, and a non-object, are invalid", H.validate({}) and H.validate([1]) and H.validate({"groups": []}))
    check("an invalid file stops the load with every problem listed (never silently skipped)", _load_raises(bad))
    # ---- retirement, determinism, flag (on temp outputs)
    tmp = tempfile.mkdtemp(prefix="handgroups_")
    path = os.path.join(tmp, "hand_groups.json")
    texts = jl("ability_taxonomy_cards.json")["cards"]
    src = {"version": 1, "groups": {"live-group": grp([r1], name="Live", created="2026-10-15"), "dead-group": grp([r1], name="Dead", retired=True)}}
    json.dump(src, open(path, "w"))
    H.PATH = path
    BH.OUT, BH.OUT_MD = os.path.join(tmp, "hits.json"), os.path.join(tmp, "g.md")
    BH.main()
    h1 = open(BH.OUT, "rb").read()
    out = json.loads(h1)["groups"]
    check("a retired group is kept (its id still resolves) but has no suggestions", out["dead-group"]["retired"] and out["dead-group"]["cards"] == 0 and out["live-group"]["cards"] > 50, (out["dead-group"]["cards"], out["live-group"]["cards"]))
    BH.main()
    check("two builds in a row are byte-identical", open(BH.OUT, "rb").read() == h1)
    BH.HAND_GROUPS = False
    BH.main()
    check("flag off: both outputs removed", not os.path.exists(BH.OUT) and not os.path.exists(BH.OUT_MD))
    BH.HAND_GROUPS = True
    json.dump({"version": 1, "groups": {"mutate-test": {"name": "X", "rules": [dict(id="a", type="keyword", keyword="Mutate", confidence=0.5)]}}}, open(path, "w"))
    BH.main()
    kh = json.loads(open(BH.OUT, "rb").read())["groups"]["mutate-test"]
    check("a keyword rule reads the keyword facet (Mutate: 34 cards)", kh["cards"] == 34, kh["cards"])
    # ---- the real seeded group
    H.PATH = os.path.join(HERE, "corrections", "hand_groups.json")
    real = jl("hand_group_hits.json")["groups"]["wins-or-loses-the-game"]
    hits = real["hits"]
    idx = jl("manual_index.json")["cards"]
    name = lambda o: idx[o][0]
    check("the seeded group exists, is active, and has 107 text matches", not real["retired"] and real["cards"] == 107 == len(hits), real["cards"])
    check("every hit's reason is the card's own sentence and holds one of the phrases", all(any(p in H.fold(h[1]) for p in ("win the game", "wins the game", "lose the game", "loses the game", "the game is a draw")) for hs in hits.values() for h in hs))
    check("no hit is a poison reminder", not any("poison counters" in H.fold(h[1]) for hs in hits.values() for h in hs))
    poison_only = [o for o, c in texts.items() if "poison counters loses the game" in (c["t"] or "") and o not in hits]
    check("the 15 cards whose only match is the poison reminder are all excluded", len(poison_only) == 15, len(poison_only))
    got = {name(o) for o in hits}
    check("the two cards the narrower patterns missed are in (Celestial Convergence, Divine Intervention)", {"Celestial Convergence", "Divine Intervention"} <= got)
    check("the two weak 'has lost the game' references are out (Hot Pursuit, Rampant Frogantua)", not ({"Hot Pursuit", "Rampant Frogantua"} & got))
    check("the known true cards are in (Platinum Angel, Laboratory Maniac, Door to Nothingness, Slaughter Pact, Lich)", {"Platinum Angel", "Laboratory Maniac", "Door to Nothingness", "Slaughter Pact", "Lich"} <= got)
    check("the group's rule words and note are recorded for the page", real["rules"][0]["words"].startswith("the card text has a sentence with") and "poison" in real["rules"][0]["words"] and "107" in real["note"])
    # ---- suggestions are only suggestions
    S = jl("manual_suggestions.json")["cards"]
    ruled = {o: [r for r in rs if r[0] == "hand:wins-or-loses-the-game"] for o, rs in S.items()}
    ruled = {o: r[0] for o, r in ruled.items() if r}
    check("rule suggestions exist for pile and soft cards, scored by the rule and labelled as the rule", len(ruled) > 20 and all("rule" in r[2].split("+") and "your hand-defined group" in r[3] for r in ruled.values()), len(ruled))
    check("a card that is not in the pile or soft layers gets no suggestion", all(idx[o][1] in "utam" for o in ruled))
    check("the real hand-placement file is not touched by the build or this test", (hashlib.sha256(open(REAL_CORR, "rb").read()).hexdigest() if os.path.exists(REAL_CORR) else None) == real_hash)
    code = open(os.path.join(HERE, "src", "build_hand_groups.py"), encoding="utf-8").read()
    check("the rule build cannot place a card (no import of the placement writer, one new data file)", "manual_common" not in code and "apply_edit" not in code and code.count("io.open(OUT,") == 1)
    # ---- the endpoint, hand layer
    ix = jl("manual_index.json")
    ix2 = copy.deepcopy(ix)
    ix2["groups"]["hand:old-group"] = ["Old group", 0, "Hand-defined groups › retired", "hand", 0]
    pile = next(o for o, c in sorted(ix["cards"].items()) if c[1] == "u")
    MC.CORR = os.path.join(tmp, "manual.json")

    def post(body):
        try:
            return 200, MC.apply_edit(body, index=ix2, path=MC.CORR)
        except MC.ApiError as e:
            return e.status, e.msg
    s, j = post({"oid": pile, "group": "hand:wins-or-loses-the-game", "action": "add", "note": "reads right"})
    e = MC.load_doc(MC.CORR)["edits"].get(pile, {}).get("groups", {}).get("hand:wins-or-loses-the-game", {})
    check("endpoint: an add to an active hand-defined group is accepted and keeps the group's name", s == 200 and e.get("group_name") == "Wins, loses or draws the game, or stops it" and e["source_at_edit"]["status"] == "unorganized", (s, j if s != 200 else ""))
    s, j = post({"oid": pile, "group": "hand:old-group", "action": "add"})
    check("endpoint: an add to a retired hand-defined group is refused (422)", s == 422 and "retired" in j, (s, j))
    s, j = post({"oid": pile, "group": "hand:no-such-group", "action": "add"})
    check("endpoint: an add to an unknown hand-defined group is refused (422)", s == 422, (s, j))
    s, j = post({"oid": pile, "group": "hand:Bad_Slug", "action": "add"})
    check("endpoint: a malformed hand slug is refused (422: not in the inventory)", s == 422, (s, j))
    s, j = post({"oid": pile, "group": "hand:wins-or-loses-the-game", "action": "clear"})
    check("endpoint: undo of a hand-group placement works", s == 200 and pile not in MC.load_doc(MC.CORR)["edits"], (s, j))
    doc = {"edits": {pile: {"name": "x", "groups": {"hand:old-group": {"action": "add", "date": "d", "note": "", "group_name": "Old group"}, "hand:deleted-for-real": {"action": "add", "date": "d", "note": "", "group_name": "Gone"}}}}, "history": [], "revision": 1}
    res = MC.resolve(ix2, doc)
    check("a retired hand-defined group is not an orphan; one deleted from the file is", [o["group"] for o in res["orphans"]] == ["hand:deleted-for-real"] and res["counts"]["placed_by_hand_new"] == 1, res["counts"])
    check("hand-group placements count on the existing 'placed by hand' line only (reconciliation still sums)", res["reconciliation"]["sum"] == 38921)
    print("\n%d failure(s)" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


def _load_raises(bad):
    p = os.path.join(tempfile.mkdtemp(), "g.json")
    json.dump(bad, open(p, "w"))
    try:
        H.load(p)
    except ValueError as e:
        return "Bad_Slug" in str(e) and "bad-conf" in str(e)
    return False


if __name__ == "__main__":
    main()
