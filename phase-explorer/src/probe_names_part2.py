#!/usr/bin/env python3
"""Part 2 prototype: signature-derived names (names_v2) against today's names. Measurement only; writes build/ability_taxonomy_names_part2.json.

    python src/probe_names_part2.py
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
import names_v2 as N  # noqa: E402
import probe_names_part1 as P1  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
TP = ("scope:TriggeringPlayer", "triggering player")
DROPPED = ["obj", "ctrl", "quant", "props", "kw", "dur", "cond", "wrap", "chain", "tok"]


def run(patch_flag=False):
    orig = B.extra_flags
    if patch_flag:
        def ef(ftype, ret):
            out = orig(ftype, ret)
            if ftype in ("Draw", "GainLife") and ret.get("who") in TP:
                out.append("who draws or gains life is not recorded for 'that player'")
            return out
        B.extra_flags = ef
    B.dump = lambda *a, **k: None
    FL = "who draws or gains life is not recorded for 'that player'"
    B.FLAG_SHORT.setdefault(FL, "who draws isn't reliably recorded (“that player” is usually you in the text)")
    B.FLAG_NOTE.setdefault(FL, "For abilities that affect “that player”, the parse does not record whether that is you or another player, so this group is broader than it looks.")
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            S = B.main()
    finally:
        B.extra_flags = orig
    return S


def headline(S):
    c = collections.Counter(v[0] for v in S["view"].values())
    h = c["placed"] + c["keyword_block"] + c["no_abilities"] + c["replacement_group"]
    return h, h + c["broad_only"], c


def scan_names(pairs, vocab, allow=True):
    if allow:
        P1.ALLOW.update(N.TEMPLATE_VOCAB)
    else:
        P1.ALLOW.difference_update(N.TEMPLATE_VOCAB)
    scan = P1.defect_scan(pairs, vocab)
    soft = ("disambiguation suffix ('(variant)', '#2')", "longer than 110 characters", "stacked parentheses")
    hard = {n.split("  [")[0] for k, ns in scan.items() if k not in soft for _, n in ns}
    return {"hard": len(hard), "by_cat": {k: len({n.split("  [")[0] for _, n in v}) for k, v in scan.items() if k not in soft},
            "examples": {k: [x[1] for x in v[:6]] for k, v in scan.items() if k not in soft}}


STEMS = {"untap": r"untap", "attack": r"attack", "block": r"block", "counter": r"counter", "exile": r"exile|exiling|airbend", "destroy": r"destroy",
         "sacrifice": r"sacrifice", "draw": r"draw", "discard": r"discard", "mill": r"mill|top .{0,30}graveyard", "return": r"return|owner's hand|into .{0,15}hand|onto the battlefield",
         "search": r"search", "create": r"create|token|investigate|treasure|food|clue|blood|map|incubate|amass|populate|connive|proliferate|manifest|conjure|learn|goad|support|bolster|adapt",
         "lose": r"lose|loses|pay|isn't", "deal": r"deal|damage", "copy": r"cop(?:y|ies)", "regenerate": r"regenerate", "transform": r"transform",
         "reveal": r"reveal", "shuffle": r"shuffle", "cast": r"cast|play|without paying", "scry": r"scry", "surveil": r"surveil", "tap": r"tap",
         "double": r"double", "gain": r"gain|get|has|have|with|becomes?|in addition|class|level|lifelink|trample|flying", "pump": r"get|\+", "put": r"put|place|add|get|enters? with|counter|distribute|move|return|exile|onto|into|earthbend|bolster|adapt|support",
         "mana": r"mana|\{[wubrgc0-9x]\}", "counters": r"counter|earthbend|bolster|adapt|support|level|enters with", "look": r"look|reveal", "play": r"play|cast|land", "must": r"must|have to|if able|able to block|do so",
         "become": r"become|is changed|changes|change|has base|base power|copy|isn't|is a|prepared|earthbend", "enters": r"enter", "fight": r"fight", "prevent": r"prevent", "attach": r"attach|equip|aura",
         "change": r"chang|becomes?|set|control|gain control|exchange", "remove": r"remove|loses?|isn't", "choose": r"choose|chosen", "pay": r"pay|cost", "move": r"move|put|return|exile|onto|into|sacrifice|destroy|enter|airbend|search|reveal"}
NEG = [("can't", r"can't|cannot"), ("doesn't", r"doesn't|don't|does not|do not"), ("isn't", r"isn't|aren't|is not|are not"), ("must", r"must|has to|have to|if able|able to block|do so"),
       ("may", r"\bmay\b|\bcan\b")]


def norm(t):
    return (t or "").lower().replace("’", "'").replace("‘", "'")


def claims(S, Lm, key):
    """Every leaf: does the name state something its members' text doesn't say? (a) each verb stem in the name must appear in at least half of
    the members' text; (b) a negation or modal in the name needs the same word in at least half; (c) \"can't X\" / \"doesn't X\" needs that exact
    phrase (can't~cannot, doesn't~don't) in at least half of the members' text. A hit is blocking."""
    A, members, leaf_info = S["A"], S["members"], S["leaf_info"]
    hits = {}
    for lf, li in leaf_info.items():
        nm = norm(Lm[li["id"]][key])
        texts = [norm(A[j]["text"]) for j in members[lf]]
        texts = [t for t in texts if t.strip()]              # members with no ability text cannot be checked
        n = len(texts)
        if not n or n < 0.5 * len(members[lf]):
            continue
        bad = []
        words = set(re.findall(r"[a-z']+", nm))
        for w, rx in STEMS.items():
            if w == "counter" and "counters" in words:
                continue                                   # "put counters on" is the counters stem, not countering a spell
            if w == "put" and "counters" in words:
                continue
            if w in words or (w + "s") in words or (w + "es") in words or (w[:-1] + "ies") in words:
                share = sum(1 for t in texts if re.search(rx, t)) / n
                if share < 0.5:
                    bad.append("'%s' in %d%% of texts" % (w, round(100 * share)))
        for w, rx in NEG:
            if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", nm):
                share = sum(1 for t in texts if re.search(rx, t)) / n
                if share < 0.5:
                    bad.append("'%s' in %d%% of texts" % (w, round(100 * share)))
        for neg, vb in re.findall(r"(can't|doesn't) ([a-z]+)", nm):
            if vb == "be":
                continue                                   # "can't be cast" is "can't cast": the verb after 'be' is not checked
            rx = (r"can't|cannot" if neg == "can't" else r"doesn't|don't|does not|do not")
            share = sum(1 for t in texts if re.search("(?:" + rx + r")(?: [a-z]+){0,3} " + vb, t)) / n
            if share < 0.5:
                bad.append("'%s %s' in %d%% of texts" % (neg, vb, round(100 * share)))
        if bad:
            hits[li["id"]] = bad
    return hits


def coverage(Lm):
    by_node = collections.defaultdict(list)
    for lid, l in Lm.items():
        by_node[l["node"]].append(lid)
    out = {}
    for lid, l in Lm.items():
        if l["n"] < 10:
            continue
        ft, ret = P1.ret_of(l["sig"])
        sib = [P1.ret_of(Lm[s]["sig"])[1] for s in by_node[l["node"]] if s != lid]
        miss = []
        for f in P1.FIELDS:
            v = ret.get(f, "")
            if not v or (f, v) in P1.DEFAULT_SKIP:
                continue
            if sib and {s.get(f, "") for s in sib} == {v}:
                continue
            if not P1.mention(f, v, l["name"], ft) and not P1.implied(ft, ret, f, v, l["name"]):
                miss.append("%s=%s" % (f, v))
        if miss:
            out[lid] = miss
    return out


def minority(S, Lm, key):
    """Leaves of 10+ with a >=10% minority that differs on a dropped field the name nonetheless states (by the part-1 mention test)."""
    A, members, leaf_info = S["A"], S["members"], S["leaf_info"]
    res = {}
    for lf, li in leaf_info.items():
        if li["n"] < 10:
            continue
        ret, ft, nm = li["ret"], li["ftype"], Lm[li["id"]][key]
        mem = [A[j] for j in members[lf]]
        bad = []
        for f in DROPPED:
            if ret.get(f):
                continue
            cnt = collections.Counter((a["f"].get(f, "") if a["f"].get(f, "") != "-" else "") for a in mem)
            val, c = cnt.most_common(1)[0]
            if not val:
                continue
            share_min = 1 - c / len(mem)
            says_varies = ({"obj": "object", "ctrl": "controller", "quant": "number", "props": "restriction", "chain": "follow-up", "dur": "duration"}.get(f, f) + " varies") in nm
            if share_min >= 0.10 and P1.mention(f, val, nm, ft) and not says_varies:
                bad.append("%s=%s (%.0f%% differ)" % (f, val, 100 * share_min))
        # a/an asserts one object when quant was dropped and 10%+ are plural/all
        if not ret.get("quant"):
            q = collections.Counter(a["f"].get("quant", "") for a in mem)
            plural = sum(v for k, v in q.items() if k in ("all", "multi", "each"))
            if re.search(r"\b(a|an|A|An) (?!condition|cost)", nm) and plural / len(mem) >= 0.10 and ft not in ("static:Continuous",):
                bad.append("quant: name says 'a/an', %.0f%% are all/several/each" % (100 * plural / len(mem)))
        if bad:
            res[li["id"]] = bad
    return res


ANY_WORDING = True
DIS_ORDER = ["chain", "obj", "ctrl", "props", "kw", "dur", "who", "tok", "cond", "wrap", "recip", "frm", "to", "ctr", "mods", "sign", "quant"]
LABEL = {"obj": "object", "ctrl": "controller", "quant": "number", "props": "restriction", "chain": "follow-up", "dur": "duration"}


def _word(f, v):
    if not v or v == "-":
        return LABEL.get(f, f) + " varies"
    return N.GUARD_W.get(f, lambda x: x)(v).strip()


def disambiguate(Lm):
    """Names that still collide inside a node: add the fewest fields, in a fixed priority order, until every name in the group is different.
    A field a twin retains and this leaf does not is worded '<field> varies' (the group does not separate it)."""
    by = collections.defaultdict(list)
    for lid, l in Lm.items():
        by[(l["node"], l["new"])].append(lid)
    for (nd, nm), ids in by.items():
        if len(ids) < 2:
            continue
        rets = {i: P1.ret_of(Lm[i]["sig"])[1] for i in ids}
        diff = [f for f in DIS_ORDER if len({rets[i].get(f, "") for i in ids}) > 1]
        chosen = []

        def build(chosen):
            out = {}
            for i in ids:
                ws = []
                for g in chosen:
                    v = rets[i].get(g, "")
                    w = _word(g, v)
                    if v and w.lower().rstrip("s") in nm.lower():
                        continue                             # the name already states it; the twin that lacks it says "varies"
                    ws.append(w)
                out[i] = nm + (" (" + "; ".join(ws) + ")" if ws else "")
            return out
        for f in diff:
            chosen.append(f)
            names = build(chosen)
            if len(set(names.values())) == len(ids):
                break
        else:
            names = build(chosen)
        for i in ids:
            Lm[i]["new"] = names[i]


def main():
    S = run(False)
    leaf_info, A, members = S["leaf_info"], S["A"], S["members"]
    Lm = {}
    node_rets = collections.defaultdict(list)
    for lf, li in leaf_info.items():
        node_rets[li["node"]].append((li["id"], li["ret"]))
    for lf, li in leaf_info.items():
        buckets = collections.Counter(A[j]["b"] for j in members[lf])
        sibs = [r for i, r in node_rets[li["node"]] if i != li["id"]]
        new = N.name_leaf_final(li["ftype"], li["ret"], buckets, sibs)
        today = li["auto_name"] + ((" — " + "; ".join(B.FLAG_SHORT[f] for f in li["flags"])) if li["flags"] else "")
        Lm[li["id"]] = {"old": today, "new": new, "n": li["n"], "sig": lf[1], "node": li["node"], "flags": li["flags"], "level": li["level"]}
    disambiguate(Lm)
    corr = json.load(io.open(os.path.join(HERE, "corrections", "ability_taxonomy_names.json"), encoding="utf-8")).get("leaves", {})
    for lid, l in Lm.items():
        if l["sig"] in corr:
            l["new"] = corr[l["sig"]]["name"]
            l["corrected"] = True
    by = collections.defaultdict(list)
    for lid, l in Lm.items():
        by[(l["node"], l["new"])].append(lid)
    coll = {k: v for k, v in by.items() if len(v) > 1}
    vocab = set()
    cards = json.load(io.open(os.path.join(BUILD, "ability_taxonomy_cards.json"), encoding="utf-8"))["cards"]
    for c in cards.values():
        for w in re.findall(r"[A-Za-z][a-z']{2,}", c["t"] or ""):
            vocab.add(w.lower())
    old_scan = scan_names([("leaf", l["old"]) for l in Lm.values()], vocab)
    new_scan = scan_names([("leaf", l["new"]) for l in Lm.values()], vocab)
    new_scan_noallow = scan_names([("leaf", l["new"]) for l in Lm.values()], vocab, allow=False)
    scan_names([], vocab)                               # restore the allow-list
    cov_old = coverage({k: dict(v, name=v["old"]) for k, v in Lm.items()})
    cov_new = coverage({k: dict(v, name=v["new"]) for k, v in Lm.items()})
    mo, mn = minority(S, Lm, "old"), minority(S, Lm, "new")
    cl_old, cl_new = claims(S, Lm, "old"), claims(S, Lm, "new")
    n10 = sum(1 for l in Lm.values() if l["n"] >= 10)
    changed = [k for k, l in Lm.items() if l["old"] != l["new"]]
    base_h, base_wb, base_c = headline(S)
    S2 = run(True)
    h2, wb2, c2 = headline(S2)
    tp_leaves = [(l["id"], l["n"], l["name"]) for l in S2["leaf_info"].values()
                 if l["ftype"] in ("Draw", "GainLife") and l["ret"].get("who") in TP]
    pre_flag = {l["id"] for l in leaf_info.values() if l["flags"]}
    newly = [(i, n, nm) for i, n, nm in tp_leaves if i not in pre_flag]
    res = {"leaves": len(Lm), "leaves_10plus": n10, "renamed": len(changed),
           "collisions": {"%s | %s" % (k[0], k[1]): len(v) for k, v in coll.items()},
           "defects_old": old_scan["hard"], "defects_new": new_scan["hard"], "defects_new_without_allowlist": new_scan_noallow["hard"], "allow_list": sorted(N.TEMPLATE_VOCAB), "defects_new_cat": new_scan["by_cat"],
           "defects_new_examples": new_scan["examples"],
           "coverage_omit_old": len(cov_old), "coverage_omit_new": len(cov_new),
           "coverage_new_detail": {Lm[k]["new"]: v for k, v in cov_new.items()},
           "claims_old": len(cl_old), "claims_new": len(cl_new), "claims_new_detail": {Lm[k]["new"]: v for k, v in cl_new.items()},
           "claims_old_detail": {Lm[k]["old"]: v for k, v in cl_old.items()},
           "minority_old": len(mo), "minority_new": len(mn), "minority_new_detail": {Lm[k]["new"]: v for k, v in mn.items()},
           "that_player": {"leaves_newly_flagged": len(newly), "abilities_newly_flagged": sum(n for _, n, _ in newly),
                           "detail": sorted(newly, key=lambda x: -x[1]),
                           "headline_before": [base_h, round(100 * base_h / 34864, 1)],
                           "with_broad_before": [base_wb, round(100 * base_wb / 34864, 1)],
                           "headline_after": [h2, round(100 * h2 / 34864, 1)],
                           "with_broad_after": [wb2, round(100 * wb2 / 34864, 1)],
                           "views_after": dict(c2)}}
    out = dict(res)
    known = []
    def find(pred, label):
        for lid, l in sorted(Lm.items(), key=lambda kv: -kv[1]["n"]):
            if pred(l):
                known.append((label, lid))
                return
    find(lambda l: "IsCommander" in l["sig"], "commander restriction dropped")
    find(lambda l: l["sig"].endswith("frm=Hand · to=Exile · obj=Card · ctrl=You · quant=one"), "alternative cost read as exile")
    find(lambda l: "frm=Graveyard · to=Battlefield · who=scope:All" in l["sig"], "each player not stated")
    find(lambda l: "who=triggering player" in l["sig"] and "ftype=Draw" in l["sig"] or "who=scope:TriggeringPlayer" in l["sig"] and "ftype=Draw" in l["sig"], "that player draws")
    find(lambda l: "ftype=GainLife" in l["sig"] and "TriggeringPlayer" in l["sig"], "that player gains life")
    find(lambda l: "MustBeBlocked" in l["sig"] and "obj=self" in l["sig"], "lure")
    find(lambda l: l["sig"].endswith("ftype=GainLife · who=controller · dur=UntilEndOfTurn"), "gain life until end of turn")
    find(lambda l: "CantBeBlockedExceptBy" in l["sig"] and "GenericEffect" in l["sig"], "garbled 'cant be blocked except by'")
    kid = {i for _, i in known}
    pool = sorted([i for i, l in Lm.items() if l["n"] >= 10 and l["old"] != l["new"] and i not in kid])
    table30 = [{"why": w, "id": i} for w, i in known] + [{"why": "id order", "id": i} for i in pool[:30 - len(known)]]
    for r in table30:
        l = Lm[r["id"]]
        r["flag_text"] = "; ".join(B.FLAG_SHORT[f] for f in l["flags"] if f in B.FLAG_SHORT)
        if re.search(r"ftype=(Draw|GainLife) · who=(scope:TriggeringPlayer|triggering player)", l["sig"]) and not r["flag_text"]:
            r["flag_text"] = B.FLAG_SHORT["who draws or gains life is not recorded for 'that player'"] + "  [NEW FLAG]"
        r.update({"old": l["old"], "new": l["new"], "n": l["n"], "sig": l["sig"].split(" · ", 1)[1][:140], "flags": l["flags"]})
    out["table30"] = table30
    out["table_all"] = sorted([{"id": k, "old": l["old"], "new": l["new"], "n": l["n"], "sig": l["sig"].split(" · ", 1)[1][:150]}
                               for k, l in Lm.items() if l["old"] != l["new"]], key=lambda x: -x["n"])
    with io.open(os.path.join(BUILD, "ability_taxonomy_names_part2.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print(json.dumps({k: v for k, v in res.items() if k != "that_player"}, indent=1, ensure_ascii=False)[:7000])
    print(json.dumps({k: v for k, v in res["that_player"].items() if k != "detail"}, indent=1))
    for e in res["that_player"]["detail"]:
        print("  ", e[1], e[2][:80])


if __name__ == "__main__":
    main()
