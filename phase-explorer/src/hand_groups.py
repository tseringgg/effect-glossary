#!/usr/bin/env python3
"""Hand-defined groups: the file format, its validation and the rule evaluator. Shared by src/build_hand_groups.py, src/build_manual_layer.py, the suggestions build and the tests.

corrections/hand_groups.json (hand-edited; no endpoint writes it):

  {"version": 1, "groups": {"<slug>": {"name": "...", "note": "...", "created": "2026-10-15", "retired": false,
      "rules": [{"id": "r1", "type": "text", "any": ["phrase", ...], "not": ["phrase", ...], "confidence": 0.7},
                {"id": "r2", "type": "keyword", "keyword": "Mutate", "confidence": 0.6},
                {"id": "r3", "type": "tag", "tag": "alternate-win-condition", "confidence": 0.4}]}}}

* Group id = "hand:" + slug. The slug is chosen once, never derived from the name, the rules, the members or the build, and never reused. A rename changes only `name`. To remove a group set
  "retired": true (a tombstone): it leaves the search and gets no suggestions, but its id still resolves, so no hand placement into it is orphaned. Deleting the entry orphans those placements (reported).
* A rule only ever SUGGESTS. No rule places a card; a member is a person's Add click (corrections/manual_placements.json, group id hand:<slug>).
* text rule: literal phrases (no regular expressions, so a rule cannot hang the build). The card's oracle text is folded (lower case, curly apostrophes straight, spaces collapsed) and cut into sentences
  (at line breaks and at ". "). A phrase of `any` matches a sentence that contains it; the match is void if that same sentence contains a phrase of `not`. A card matches if any sentence matches, and the
  rule keeps that sentence (as written on the card; a window of 200 characters around the match if the sentence is longer) as the reason. keyword rule: the parser's keyword name (case and spaces ignored). tag rule: a Scryfall community-tag slug.
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(HERE, "corrections", "hand_groups.json")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$")
RULE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,20}$")
TYPES = ("text", "keyword", "tag")
MAX_PHRASES, MAX_PHRASE_LEN, MAX_RULES = 40, 120, 20


def fold(s):
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("−", "-").lower()
    return " ".join(s.split())


def norm_kw(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def validate(doc):
    """-> list of problems (empty if the file is valid). Never raises."""
    bad = []
    if not isinstance(doc, dict) or not isinstance(doc.get("groups"), dict):
        return ["the file needs a 'groups' object"]
    names = {}
    for slug, g in doc["groups"].items():
        w = "group %r: " % slug
        if not SLUG.match(slug):
            bad.append(w + "the slug must match [a-z0-9][a-z0-9-]{2,40}")
            continue
        if not isinstance(g, dict) or not isinstance(g.get("name"), str) or not g["name"].strip():
            bad.append(w + "needs a name")
            continue
        if g["name"] in names:
            bad.append(w + "the name is also used by %r" % names[g["name"]])
        names[g["name"]] = slug
        if not isinstance(g.get("retired", False), bool):
            bad.append(w + "'retired' must be true or false")
        rules = g.get("rules", [])
        if not isinstance(rules, list) or len(rules) > MAX_RULES:
            bad.append(w + "'rules' must be a list of at most %d rules" % MAX_RULES)
            continue
        ids = set()
        for r in rules:
            if not isinstance(r, dict) or r.get("type") not in TYPES:
                bad.append(w + "a rule needs type text | keyword | tag")
                continue
            rid = r.get("id")
            if not isinstance(rid, str) or not RULE_ID.match(rid) or rid in ids:
                bad.append(w + "rule ids must be unique and match [a-z0-9][a-z0-9_-]*")
            ids.add(rid)
            c = r.get("confidence", 0.6)
            if not isinstance(c, (int, float)) or isinstance(c, bool) or not 0 < c <= 1:
                bad.append(w + "rule %s: confidence must be a number above 0 and at most 1" % rid)
            if r["type"] == "text":
                for k in ("any", "not"):
                    v = r.get(k, [] if k == "not" else None)
                    if not isinstance(v, list) or (k == "any" and not v) or len(v) > MAX_PHRASES or not all(isinstance(x, str) and 2 <= len(x) <= MAX_PHRASE_LEN for x in v):
                        bad.append(w + "rule %s: '%s' must be a list (any: not empty) of phrases of 2 to %d characters" % (rid, k, MAX_PHRASE_LEN))
            elif r["type"] == "keyword":
                if not isinstance(r.get("keyword"), str) or not norm_kw(r["keyword"]):
                    bad.append(w + "rule %s: needs a keyword" % rid)
            else:
                if not isinstance(r.get("tag"), str) or not r["tag"].strip():
                    bad.append(w + "rule %s: needs a tag slug" % rid)
    return bad


def load(path=None):
    path = path or PATH
    if not os.path.exists(path):
        return {"version": 1, "groups": {}}
    with io.open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    bad = validate(doc)
    if bad:
        raise ValueError("corrections/hand_groups.json is invalid:\n  " + "\n  ".join(bad))
    return doc


def sentences(text):
    """[(as written, folded)] for each sentence of an oracle text (cut at line breaks and at '. ')."""
    out = []
    for line in (text or "").split("\n"):
        parts = re.split(r"(?<=[.!?\]\)])\s+(?=[A-Z\"\(\[{•—−+\-0-9])", line) if line.strip() else []
        for p in parts:
            p = p.strip()
            if p:
                out.append((p, fold(p)))
    return out


def match_text(rule, text):
    """-> the sentence (as written on the card) that satisfies the rule, or None."""
    anyf = [fold(x) for x in rule["any"]]
    notf = [fold(x) for x in rule.get("not", [])]
    for orig, f in sentences(text):
        hit = [a for a in anyf if a in f]
        if hit and not any(n in f for n in notf):
            if len(orig) <= 200:
                return orig
            pos = orig.replace("’", "'").replace("‘", "'").lower().find(hit[0])         # a long sentence: a window around the match, so the reason shows it
            start = max(0, pos - 80) if pos >= 0 else 0
            return ("…" if start else "") + orig[start:start + 200]
    return None


def evaluate(doc, texts, keywords, tags):
    """texts {oid: oracle text}; keywords {parser keyword name: set(oid)}; tags {tag slug: set(oid)}.
    -> {slug: {"retired": bool, "hits": {oid: [[rule id, reason], ...]}}} for every group (a retired group is evaluated too; the build decides what to do with it)."""
    kwn = {norm_kw(k): v for k, v in keywords.items()}
    out = {}
    for slug in sorted(doc["groups"]):
        g = doc["groups"][slug]
        hits = {}
        for r in g.get("rules", []):
            rid = r["id"]
            if r["type"] == "text":
                for oid in sorted(texts):
                    s = match_text(r, texts[oid])
                    if s:
                        hits.setdefault(oid, []).append([rid, s])
            elif r["type"] == "keyword":
                for oid in sorted(kwn.get(norm_kw(r["keyword"]), ())):
                    hits.setdefault(oid, []).append([rid, "carries the keyword %s" % r["keyword"]])
            else:
                for oid in sorted(tags.get(r["tag"], ())):
                    hits.setdefault(oid, []).append([rid, "carries the community tag %s" % r["tag"]])
        out[slug] = {"retired": bool(g.get("retired")), "hits": hits}
    return out
