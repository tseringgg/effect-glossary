#!/usr/bin/env python3
"""The "that player" leaves: abilities whose parsed player is the TRIGGERING player. Measurement only.

    python src/probe_that_player.py   # -> build/ability_taxonomy_that_player.json

For each ability whose signature says the triggering player (who = scope:TriggeringPlayer or "triggering player"):
  trigger names another player   the trigger's own structure (everything but its effect) mentions an opponent
  text subject                   "other" (that player / they / each opponent / ...) or "you" or unclear, read from the rules text
and, per effect type, how often each reading holds. The text is used only to MEASURE the field, never to place anything.
"""
import collections
import contextlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ability_taxonomy as B  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
VERB = {"Draw": r"draws?", "GainLife": r"gains?", "LoseLife": r"loses?", "Discard": r"discards?", "Mill": r"mills?",
        "GivePlayerCounter": r"gets?", "RevealHand": r"reveals?", "DealDamage": r"deals?", "Scry": r"scr(?:y|ies)", "Surveil": r"surveils?",
        "Sacrifice": r"sacrifices?", "Tap": r"taps?", "Untap": r"untaps?", "ExileTop": r"exiles?", "Token": r"creates?"}
OTHER = r"(that player|that creature's controller|its controller|their controller|that permanent's controller|they|each opponent|target opponent|an opponent|defending player|target player|each player|its owner|that spell's controller)"


def classify(text, ft):
    """Who is the subject of the effect's verb? Looks at the words directly before the first use of the verb."""
    v = VERB.get(ft)
    t = (text or "").replace("\n", " ")
    if not v or len(t) < 12:
        return "unclear"
    for m in re.finditer(r"\b" + v + r"\b", t, re.I):
        pre = t[max(0, m.start() - 26):m.start()]
        if re.search(r"\byou(?: may| then| also| can| each time)?\s*$", pre, re.I):
            return "you"
        if re.search(OTHER + r"(?: may| then| also| each time)?\s*$", pre, re.I):
            return "other"
        if re.search(r"(?:^|[,\u2014:\]\)]\s*|\.\s+|then\s+|may\s+)$", pre, re.I):
            return "you"                      # imperative: "draw a card" -- the controller
    return "unclear"


def main():
    sink = io.StringIO()
    B.dump = lambda *a, **k: None
    with contextlib.redirect_stdout(sink):
        S = B.main()
    A = S["A"]
    n_by = collections.defaultdict(collections.Counter)
    leaves = collections.Counter()
    leaf_ft = {}
    for j, a in enumerate(A):
        f = a["f"]
        if not f.get("usable") or a.get("pre"):
            continue
        if not (f["who"] in ("scope:TriggeringPlayer", "triggering player")):
            continue
        ft = f["ftype"]
        it = a["item"]
        struct = None
        if a["b"] == "triggers":
            trig = {k: v for k, v in it.items() if k not in ("execute", "description")}
            s = json.dumps(trig)
            struct = "opponent" if re.search(r"Opponent", s) else "no other player named"
        else:
            struct = "not a trigger"
        sub = classify(a["text"], ft)
        c = n_by[ft]
        c["n"] += 1
        c["structure:" + struct] += 1
        c["text:" + sub] += 1
        c["text:%s|structure:%s" % (sub, struct)] += 1
        asg = a.get("asg")
        if asg and asg[0] != "x":
            leaves[(ft, asg[1])] += 1
    out = {"by_effect_type": {ft: dict(c) for ft, c in sorted(n_by.items(), key=lambda kv: -kv[1]["n"])}}
    tot = collections.Counter()
    for c in n_by.values():
        for k, v in c.items():
            tot[k] += v
    out["all"] = dict(tot)
    L = S["tax"]["leaves"]
    lst = []
    for lid, l in L.items():
        if "who=scope:TriggeringPlayer" in l["sig"] or "who=triggering player" in l["sig"]:
            lst.append({"name": l["name"], "abilities": l["abilities"], "sig": l["sig"].split(" · ", 1)[1][:90], "visible": l["visible"], "flagged": bool(l["flags"])})
    out["leaves"] = sorted(lst, key=lambda x: -x["abilities"])
    trust = {}
    for ft, c in n_by.items():
        n = c["n"]
        o, y = c["text:other"], c["text:you"]
        trust[ft] = {"n": n, "text_says_other": o, "text_says_you": y, "unclear": c["text:unclear"],
                     "share_other_of_readable": round(o / (o + y), 2) if (o + y) else None}
    out["trust_by_effect_type"] = trust
    with io.open(os.path.join(BUILD, "ability_taxonomy_that_player.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print(json.dumps({"all": out["all"], "trust": trust}, indent=1))
    for e in out["leaves"]:
        print(e["abilities"], e["name"][:70], "| visible" if e["visible"] else "", "| FLAGGED" if e["flagged"] else "", "|", e["sig"][:60])


if __name__ == "__main__":
    main()
