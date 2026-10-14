#!/usr/bin/env python3
"""Part 1 (b)-(d) probe (read-only): extract the unread condition text from each candidate's ability text, scan for cost/effect verb sharing, count inversion words.
Reads build/annotation_probe.json; writes build/annotation_extract.json. Changes nothing else."""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
KW = re.compile(r"\b(unless|otherwise|instead|if you do|if you don't|if you didn't|if you can't|if you can|this way|only if|as long as|if|while|only during|during)\b", re.I)
STRONG = re.compile(r"\b(unless|otherwise|instead|only if|as long as|if|while|only during)\b", re.I)
DEP = re.compile(r"^(if you (do|did|don't|didn't|can't|can|do not)|when you do|if it (doesn't|didn't))\b", re.I)
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z~\"{(])")
INV = {"if you don't": r"\bif you (don't|do not|didn't|can't|cannot)\b", "unless": r"\bunless\b", "instead": r"\binstead\b", "otherwise": r"\botherwise\b", "if you do": r"\bif you (do|did|can)\b", "this way": r"\bthis way\b"}


def sentences(t):
    return [s.strip() for s in SENT.split(t) if s.strip()]


def extract(text, clauses):
    """-> (kind, clause). kind: clean (a clause that starts at the condition word), sentence (the whole sentence, clause not separable), none."""
    ss = sentences(text)
    # prefer the sentence containing the detector's first clause words
    pick = None
    for cl in clauses:
        frag = re.sub(r"\s+", " ", cl)[:40].lower()
        for s in ss:
            if frag and frag in s.lower():
                pick = s
                break
        if pick:
            break
    strong = lambda s: STRONG.search(s)
    cands = [pick] if pick and strong(pick) else []
    cands += [s for s in ss if s not in cands and strong(s)]
    cands += [s for s in ss if s not in cands and KW.search(s)]
    for s in cands:
        if not KW.search(s):
            continue
        low = s
        # leading "If X, B." / "Unless X, B." / "As long as X, B."
        m = re.match(r"^(If|Unless|As long as|Only if|While|During)\b([^,]{3,140}),", low)
        if m:
            return "clean", (m.group(1) + m.group(2)).strip()
        m = re.search(r"\b(instead|otherwise)\b", low, re.I)
        if m and re.match(r"^(Otherwise|If)\b", low):
            return "sentence", low
        m = re.search(r"(^|,\s+|;\s+|\s+)(then if|unless|only if|if|as long as|while|only during)\b(.{3,})$", low, re.I)
        if m:
            body = (m.group(2) + m.group(3)).strip(" ,.;")
            body = re.sub(r"^then ", "", body, flags=re.I)
            if m.group(1).startswith((",", ";")) or m.group(2).lower() == "then if":
                body = re.split(r",\s", body, maxsplit=1)[0]   # intervening "if X, Y": the condition ends at the comma
            if len(body) <= 160:
                return "clean", body
        if len(low) <= 260:
            return "sentence", low
    return "none", ""


def finish(full, kind, clause):
    """Make the clause readable on its own. -> (text, how). how: '' (clause as found), 'lead-in' (the sentence before an 'if you do' clause), 'branch' (the 'Otherwise' / 'if you don't' sentence that follows is added),
    'whole sentence' (an 'instead' or 'otherwise' sits in the clause's own sentence, so the whole sentence is shown)."""
    if kind != "clean":
        return clause, ""
    ss = sentences(full)
    key = clause[-40:]
    idx = None
    for j, sn in enumerate(ss):
        if key in sn:
            idx = j
    if idx is None:
        return clause, ""
    sn = ss[idx]
    how, text = "", clause
    if DEP.match(clause):
        lo = idx
        while lo > 0 and DEP.match(ss[lo]):
            lo -= 1
        hi = idx
        while hi + 1 < len(ss) and DEP.match(ss[hi + 1]):
            hi += 1
        text, how = " ".join(ss[lo:hi + 1]), "lead-in"
        if len(text) > 400:
            text = " ".join(ss[max(lo, idx - 1):idx + 1])
    elif re.search(r"\b(instead|otherwise)\b", sn, re.I):
        text, how = sn, "whole sentence"
    nxt = ss[idx + 1] if idx + 1 < len(ss) else ""
    if nxt and re.match(r"^(Otherwise|If not)\b", nxt) and len(sn) + len(nxt) <= 400:
        text, how = (sn if how == "" else text) + " " + nxt, "branch"
    return text, how


def full_text(r, card):
    """The item's text is cut at about 160 characters; the full ability is the oracle line it starts."""
    def norm(t):
        return re.sub(r"\s+", " ", t)
    key = norm(r["text"])[:40]
    name = card.get("n", "")
    for line in card.get("t", "").split(chr(10)):
        l = norm(line)
        for cand in (l, l.replace(name, "~")):
            i = cand.find(key)
            if i >= 0:
                return cand[i:], True
    return norm(r["text"]), False


def verb_of(leaf):
    n = leaf.split(" › ", 1)[-1].split(" \u2014 ")[-1].strip().lower()
    w = re.sub(r"[^a-z' ]", "", n).split()
    return w[0] if w else ""


STEM = lambda w: re.sub(r"(ing|ed|es|s|e)$", "", w)


def main():
    d = json.load(io.open(os.path.join(BUILD, "annotation_probe.json"), encoding="utf-8"))
    cards = json.load(io.open(os.path.join(BUILD, "ability_taxonomy_cards.json"), encoding="utf-8"))["cards"]
    rows = [r for r in d["rows"] if r["route"] != "none"]
    out = []
    for r in rows:
        full, got = full_text(r, cards[r["oid"]])
        kind, clause = extract(full, r["clauses"])
        clause, branch = finish(full, kind, clause)
        r = dict(r, ext_kind=kind, ext=clause, branch=branch, full=full, full_found=got)
        low = full.lower()
        r["inv"] = [k for k, p in INV.items() if re.search(p, low)]
        out.append(r)
    c = collections.Counter(r["ext_kind"] for r in out)
    print("extraction", dict(c))
    by = collections.defaultdict(collections.Counter)
    for r in out:
        by[r["shape"]][r["ext_kind"]] += 1
    for s, v in sorted(by.items()):
        print("%-28s %s" % (s, dict(v)))
    ic = collections.Counter()
    for r in out:
        for k in r["inv"]:
            ic[k] += 1
    print("inversion words (abilities)", dict(ic), " any:", sum(1 for r in out if r["inv"]))
    json.dump(out, io.open(os.path.join(BUILD, "annotation_extract.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False)


if __name__ == "__main__":
    main()
