#!/usr/bin/env python3
"""Narrow an ability's matched clause down to the effect the clustering matched.

phase.rs records one `description` per ability: the whole ability, cost and
trigger condition and every chained sub-effect included. For Angrath's Fury
that is four sentences -- destroy, deal damage, search, shuffle -- recorded as
one span. The clustering, though, matches on the TOP-LEVEL effect only
(cluster_structural.effect_features reads `node.effect`; sub_ability chains are
not walked). So what was actually matched is "Destroy target creature." and
nothing after it.

This module cuts a located description down to that part. It never rewrites
text; it only chooses a [start, end) range inside the words already there.

Three cuts, in order:

  1. The non-effect PREFIX. An activated ability's cost ("{2}, {T}, Sacrifice
     this artifact:") and a trigger's condition ("Whenever you cast an instant,
     sorcery, or artifact spell,") plus any intervening "if ..." clause. These
     are structural positions in Oracle templating, found by punctuation at
     quote/paren depth 0 -- not by vocabulary.

  2. Trailing RESTRICTION sentences: "Activate only ...", "This ability
     triggers only ...". Fixed Oracle templates about when, not what.

  3. SUB-EFFECTS, only when the parsed chain has more than one link. The text
     is split into clauses (sentences, ", then", ", and", ", " at depth 0) and
     walked in order; the top-level effect owns the first clause and every
     clause after it until one reads as a *different* effect in the chain.
     Over-splitting is harmless: a clause that reads as nothing in particular
     ("reveal it", "It can't be regenerated.") stays with the effect before it.

What "reads as" an effect is LEARNED from the corpus, not hand-listed: for
every effect type, the words most over-represented in unambiguous clauses of
that type (single-link chains, no cost, no condition) versus all others, by
smoothed log-odds. Those words are only used to find boundaries; nothing
learned here is ever displayed.

When a cut cannot be made confidently, the text is left as it was -- a wider
highlight is a smaller error than cutting away the matched effect.
"""
import collections
import math
import re

WORD = re.compile(r"[a-z][a-z'\-]+")

# Words that carry no effect information in any Oracle clause. Small, generic,
# and only used to keep the learned anchors from latching onto grammar.
STOP = frozenset("""
a an the of to and or it its this that those these their them they you your
each any all up for from on in into onto with at as by if then than one two
three four five six x may can target card cards creature creatures player
players opponent opponents control controls under his her until turn end
""".split())

# A clause that introduces the NEXT one rather than doing anything itself:
# "If you do", "When you do", or a bare duration ("Until end of turn,").
# It belongs with the effect that follows it.
LEAD_IN = re.compile(
    r"^((if|when) (you|they|that player|he or she|its controller) "
    r"(do|don't|does|doesn't|did|didn't|can't|cannot)\b.*"
    r"|until (end of turn|your next turn|the end of (your|the) next turn)"
    r"|this turn|for as long as .*"
    r"|(then )?(if|unless) .*)$", re.I)

RESTRICTION = re.compile(
    r"^(activate only|activate this ability only|this ability triggers only|"
    r"any player may activate|spend only)", re.I)


# ---------------------------------------------------------------- scanning

def depth0_positions(text, pattern):
    """Start offsets of `pattern` matches that sit outside quotes and parens."""
    out, quote, paren = [], False, 0
    marks = {m.start(): m for m in re.finditer(pattern, text)}
    for i, ch in enumerate(text):
        if i in marks and not quote and paren == 0:
            out.append(marks[i])
        if ch == '"':
            quote = not quote
        elif ch == "(" and not quote:
            paren += 1
        elif ch == ")" and not quote and paren:
            paren -= 1
    return out


def skip_space(text, i):
    while i < len(text) and text[i] in " \n":
        i += 1
    return i


# ------------------------------------------------------------ 1. the prefix

def cost_end(text):
    """Offset just past an activated ability's cost ("...: "), or 0."""
    ms = depth0_positions(text, r": ")
    return skip_space(text, ms[0].end()) if ms else 0


def mask_name(text, name):
    """Blank out a card's own name where it contains a comma.

    "Whenever Ambergris, Agent of Tyranny attacks, ..." -- the first comma is
    part of the name, not the end of the condition. Replacing the name with a
    same-length run of letters keeps every offset valid for the original text.
    """
    if name and ", " in name:
        text = text.replace(name, "x" * len(name))
    return text


def condition_end(text, name=""):
    """Offset just past a trigger/replacement condition, or 0.

    The condition ends at the first depth-0 comma that is not a list comma.
    "Whenever you cast an instant, sorcery, or artifact spell, draw a card." has
    three commas; the first two separate list items, which is visible from
    what follows them -- the next segment begins with "or"/"and", or the one
    after that does. The card's own name is masked first, since a name can
    carry a comma of its own.
    """
    text = mask_name(text, name)
    if not re.match(r"(when|whenever|at|if|as)\b", text, re.I):
        return 0
    commas = [m.start() for m in depth0_positions(text, r", ")]
    stop = sentence_end(text)
    commas = [c for c in commas if c < stop]
    for k, c in enumerate(commas):
        nxt = text[c + 2:(commas[k + 1] if k + 1 < len(commas) else stop)]
        after = (text[commas[k + 1] + 2:] if k + 1 < len(commas) else "")
        if re.match(r"(or|and)\b", nxt):
            continue
        if after and re.match(r"(or|and)\b", after) and len(nxt.split()) <= 4:
            continue
        end = skip_space(text, c + 2)
        # an intervening "if ...," clause is still condition, not effect
        if re.match(r"if\b", text[end:], re.I):
            inner = condition_end(text[end:])
            if inner:
                end += inner
        return end
    return 0


def sentence_end(text, start=0):
    ms = [m for m in depth0_positions(text, r"\.(\s|$)") if m.start() >= start]
    return ms[0].start() + 1 if ms else len(text)


# ------------------------------------------------------- 2. the restriction

def trim_restrictions(text, start, end):
    """Drop trailing "Activate only..." style sentences from [start, end)."""
    while True:
        body = text[start:end].rstrip()
        cuts = [m.start() for m in depth0_positions(body, r"\.\s+")]
        if not cuts:
            return start, start + len(body)
        last = skip_space(body, cuts[-1] + 1)
        if RESTRICTION.match(body[last:]):
            end = start + cuts[-1] + 1
            continue
        return start, start + len(body)


# ------------------------------------------------------ 3. the sub-effects

def clauses(text, start, end):
    """[(s, e)] clause ranges inside [start, end), split at depth 0."""
    seg = text[start:end]
    cuts = sorted({m.start() for m in depth0_positions(
        seg, r"(\.\s+|;\s+|, then |, and | and (?!/)|\band then\b|, (?=[a-z]))")})
    out, prev = [], 0
    for c in cuts:
        m = re.match(r"(\.\s+|;\s+|, then |, and | and |and then |, )", seg[c:])
        if not m:
            continue
        if c > prev:
            out.append((start + prev, start + c + (1 if seg[c] == "." else 0)))
        prev = c + m.end()
    if prev < len(seg):
        out.append((start + prev, end))
    return [(s, e) for s, e in out if text[s:e].strip()]


def score(anchors, effect, clause_text):
    table = anchors.get(effect)
    if not table:
        return 0.0
    return sum(table.get(w, 0.0) for w in set(WORD.findall(clause_text.lower())))


def chain_effects(bucket, node, effect_of):
    """Effect types in the node's sub-ability chain, top-level first."""
    cur = (node if bucket == "abilities"
           else (node.get("execute") or {}) if bucket in ("triggers", "replacements")
           else None)
    out = []
    while cur:
        et = effect_of(cur.get("effect"))
        if et:
            out.append(et)
        cur = cur.get("sub_ability")
    return out


# ------------------------------------------------------------- the entry

def narrow(bucket, node, text, top, chain, anchors, name="", threshold=1.5):
    """[start, end) of the top-level effect inside a located clause `text`.

    Returns (start, end, how) where `how` names the cuts applied, for the
    build report. Never returns an empty range: if a cut would leave nothing,
    it is not made.
    """
    how = []
    start, end = 0, len(text)

    if bucket == "abilities" and node.get("kind") == "Activated":
        c = cost_end(text)
        if 0 < c < end:
            start, how = c, how + ["cost"]
    elif bucket in ("triggers", "replacements"):
        c = condition_end(text, name)
        if 0 < c < end:
            start, how = c, how + ["condition"]

    s2, e2 = trim_restrictions(text, start, end)
    if e2 < end and e2 > s2:
        end, how = e2, how + ["restriction"]

    subs = [e for e in chain[1:] if e != top]
    if subs:
        parts = clauses(text, start, end)
        if len(parts) > 1:
            # A leading duration ("Until end of turn,") is not the effect; the
            # effect is the clause after it, which is owned unconditionally.
            first = 0
            while (first + 1 < len(parts)
                   and LEAD_IN.match(text[parts[first][0]:parts[first][1]])):
                first += 1
            owned_end = parts[first][1]
            for k, (s, e) in enumerate(parts[first + 1:], start=first + 1):
                piece = text[s:e]
                # "If you do" / "When you do" introduces the NEXT clause; it
                # belongs to whatever effect follows it, not the one before.
                if LEAD_IN.match(piece) and k + 1 < len(parts):
                    nxt = text[parts[k + 1][0]:parts[k + 1][1]]
                    theirs = max(score(anchors, x, nxt) for x in subs)
                    if theirs > threshold and theirs > score(anchors, top, nxt):
                        break
                    continue
                mine = score(anchors, top, piece)
                theirs = max(score(anchors, x, piece) for x in subs)
                if theirs > threshold and theirs > mine:
                    break
                owned_end = e
            if owned_end < end:
                end, how = owned_end, how + ["sub-effect"]

        # Fallback when no clause read as a sub-effect -- typically because the
        # sub-effect is unmodelled (Unimplemented, GenericEffect) and so has no
        # learned words. If the text has exactly one sentence per link in the
        # chain, reading order is a reliable 1:1 alignment: the chain mirrors
        # the text, top-level effect first.
        if "sub-effect" not in how:
            seg = text[start:end]
            stops = [m.start() + 1 for m in depth0_positions(seg, r"\.\s+")]
            if stops and len(stops) + 1 == len(chain):
                end, how = start + stops[0], how + ["sub-effect"]

    # never hand back a range with trailing separators hanging off it
    while end > start and text[end - 1] in " ,;":
        end -= 1
    if end <= start:
        return 0, len(text), ["none"]
    return start, end, how or ["none"]


# ------------------------------------------------------------- learning

def learn_anchors(samples, min_support=5, min_share=0.03, top_k=25):
    """{effect: {word: log-odds}} from unambiguous single-effect clauses.

    `samples` is an iterable of (effect, clause_text, card_name). Counted once
    per clause. Two guards keep the anchors about the EFFECT rather than about
    particular cards:

      * the card's own name is removed first -- "Searing Spear deals 3 damage"
        would otherwise teach DealDamage the word "searing";
      * a word must appear in at least `min_share` of that effect's clauses
        (and `min_support` of them), so a word that is perfectly associated
        but rare ("thopter" for Token) cannot outrank the common one that
        actually marks the effect ("create").

    Among what survives, smoothed log-odds of appearing in this effect's
    clauses versus all others; positive associations only.
    """
    per, total = collections.defaultdict(collections.Counter), collections.Counter()
    n_eff, n_all = collections.Counter(), 0
    for effect, clause_text, name in samples:
        own = set(WORD.findall((name or "").lower()))
        words = set(WORD.findall(clause_text.lower())) - STOP - own
        per[effect].update(words)
        total.update(words)
        n_eff[effect] += 1
        n_all += 1

    anchors = {}
    for effect, counts in per.items():
        ne, no = n_eff[effect], n_all - n_eff[effect]
        if ne < min_support or no <= 0:
            continue
        floor = max(min_support, min_share * ne)
        scored = []
        for w, c in counts.items():
            if c < floor:
                continue
            p_in = (c + 0.5) / (ne + 1.0)
            p_out = (total[w] - c + 0.5) / (no + 1.0)
            lo = math.log(p_in / p_out)
            if lo > 0:
                scored.append((lo, w))
        # explicit tie-break on the word: never depend on dict order
        scored.sort(key=lambda x: (-x[0], x[1]))
        anchors[effect] = {w: round(lo, 3) for lo, w in scored[:top_k]}
    return anchors
