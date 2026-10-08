#!/usr/bin/env python3
"""Per-item silent-condition-drop detector (KNOWN_LIMITATIONS.md §4).

DETECTION ONLY. Reads data/card-data.json; never touches the parser or any
build output the explorer serves. Writes build/condition_drops.json only with
--write.

An *item* is one entry of abilities[] / triggers[] / static_abilities[] /
replacements[]. Its `description` is the oracle text it was parsed from. For
each item the detector asks:

  TEXT   which conditional "if" clauses does the text contain, once reminder
         text, quoted (granted) text and non-condition idioms ("if able",
         "even if", the leading "if X would" of a
         replacement) are removed? Each clause gets a FAMILY:
            DO    "if you do / they don't / the player does ..."
            FLIP  "if you win / lose the flip"
            GEN   everything else
  FIELD  is a condition represented in the item's subtree, per bucket:
            condition (abilities, statics, replacements, and -- the bug of
               the sizing round -- the nested `execute` chain of triggers),
            trigger `constraint`, `activation_restrictions` (recursing into
               RequiresCondition.data.condition), `conditions[]`,
            FlipCoin win_effect/lose_effect, damage_modification /
               combat_scope / unless_filter, else_ability.
         Delayed-trigger shaping conditions (AtNextPhase, WheneverEvent ...)
         and timing-only constraints (OncePerTurn ...) are NOT evidence of an
         English "if". A wrapper whose inner condition is null
         (RequiresCondition{condition:null}) is NOT evidence either.

Each family's clauses must be backed by evidence of that family:
  tier A  a family has clauses but ZERO evidence              -> drop
  tier B  a family has some evidence but fewer nodes than
          clauses (a partial drop; e.g. 2 "if"s, 1 condition)  -> reported
          separately, never mixed into the tier-A headline.
An FlipCoin whose follow-up effects sit outside win_effect/lose_effect is the
separate STRUCT check (branch-structural drop).
"""
import argparse
import collections
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUCKETS = ("abilities", "triggers", "static_abilities", "replacements")

# ---------------------------------------------------------------- text side

REMINDER = re.compile(r"\([^()]*\)")
QUOTED = re.compile(r"[\"“][^\"”]*[\"”]")
IF_RE = re.compile(r"\bif\b", re.I)
NONCOND = [
    (re.compile(r"\bif able\b", re.I), "if_able"),            # CR 508.1a / 509.1c
    (re.compile(r"\bif possible\b", re.I), "if_possible"),
    (re.compile(r"\b(?:even|as) if\b", re.I), "even_if/as_if"),
]
DO_RE = re.compile(
    r"^if (?:you|they|he or she|that player|the player|each player|a player|"
    r"that creature's controller|its controller|its owner|that opponent|an opponent|"
    r"the opponent|that permanent's controller|one or more players|no one|nobody|"
    r"[a-z]+ player) (?:do|does|did|don't|doesn't|didn't|do not|does not|did not|"
    r"can't|cannot|can)\b(?=\s*(?:[,.;:]|$|so\b|instead\b|then\b|that way\b))", re.I)
FLIP_RE = re.compile(
    r"^if (?:you|they|that player|he or she|[a-z]+ player|it) "
    r"(?:win|lose|wins|loses|won|lost)\b", re.I)


def clean_text(t):
    return REMINDER.sub(" ", t or "")


def cond_clauses(text, bucket):
    """[(family, snippet)] for each conditional 'if' left after exclusions."""
    t = QUOTED.sub(" ", clean_text(text))
    for rx, _tag in NONCOND:
        t = rx.sub(" ", t)
    if bucket == "replacements":
        # the leading "If X would Y" IS the replacement event, not a condition
        t = re.sub(r"\bif\b[^,.]*?\b(?:would|tapped for mana)\b", " ", t, flags=re.I)
    out = []
    for m in IF_RE.finditer(t):
        tail = t[m.start(): m.start() + 80]
        # the sentence holding this "if" (split on ". " / newline / "; ")
        a = max(t.rfind(". ", 0, m.start()), t.rfind("\n", 0, m.start()),
                t.rfind("; ", 0, m.start()))
        # RESTR: an "if" inside an "...only if ..." restriction sentence (including a
        # second "or if" inside it); it is backed by activation_restrictions, not by
        # the ability body's own conditions.
        fam = ("DO" if DO_RE.match(tail) else "FLIP" if FLIP_RE.match(tail)
               else "RESTR" if re.search(r"\bonly\b", t[a + 1 if a >= 0 else 0: m.start()], re.I)
               else "GEN")
        b = [x for x in (t.find(". ", m.end()), t.find("\n", m.end())) if x >= 0]
        sent = t[a + 1 if a >= 0 else 0: min(b) + 1 if b else len(t)].strip()
        out.append({"fam": fam, "snip": t[max(0, m.start() - 25): m.end() + 45].strip(),
                    "sent": sent, "pos": m.start() - (a + 1 if a >= 0 else 0),
                    "tail": t[m.start(): min(b) + 1 if b else len(t)]})
    return out


# --------------------------------------------------------------- field side

TIMING_ONLY = {"AsSorcery", "AsInstant", "OnlyOnceEachTurn", "OnlyOnce",
               "MaxTimesEachTurn", "OncePerTurn", "OncePerGame",
               "OnlyDuringYourTurn", "OnlyDuringOpponentsTurn",
               "OnlyDuringYourMainPhase", "DuringYourTurn", "DuringYourUpkeep",
               "NthSpellThisTurn", "NthDrawThisTurn",
               "BeforeAttackersDeclared", "BeforeCombatDamage", "DuringCombat"}
DELAYED = {"AtNextPhase", "AtNextPhaseForPlayer", "WheneverEvent", "WhenNextEvent",
           "WhenDies", "WhenDiesOrExiled", "WhenLeavesPlayFiltered",
           "WhenEntersBattlefield"}
DO_TYPES = {"IfYouDo", "WhenYouDo", "IfAPlayerDoes"}
STRUCT_FIELDS = {"damage_modification": "GEN", "combat_scope": "GEN",
                 "unless_filter": "GEN"}


def is_gap(node):
    return (isinstance(node, dict)
            and node.get("type") in ("Unimplemented", "Unrecognized"))


class Evidence:
    __slots__ = ("fam", "kinds", "gap", "empty_wrappers", "wild")

    def __init__(self):
        self.fam = collections.Counter()
        self.kinds = collections.Counter()
        self.gap = False
        self.empty_wrappers = 0
        self.wild = 0            # else_ability / Unrecognized: backs any family

    def add(self, fam, kind):
        self.fam[fam] += 1
        self.kinds[kind] += 1


def scan(node, ev):
    if isinstance(node, list):
        for x in node:
            scan(x, ev)
        return
    if not isinstance(node, dict):
        return
    if is_gap(node):
        ev.gap = True
    for k, v in node.items():
        if k == "condition":
            if isinstance(v, dict):
                t = v.get("type")
                if is_gap(v):                      # visible, present, unmodelled
                    ev.gap = True
                    ev.wild += 1
                    ev.kinds["condition:Unrecognized"] += 1
                elif t in DO_TYPES:
                    ev.add("DO", "condition:" + t)
                elif t in DELAYED:
                    ev.kinds["delayed:" + t] += 1  # not evidence of an "if"
                else:
                    ev.add("GEN", "condition:" + str(t))
            elif v is not None:
                ev.add("GEN", "condition:scalar")
            continue                               # do not double-count inner nodes
        if k == "conditions" and v:
            ev.add("GEN", "conditions[]")
        elif k == "constraint" and isinstance(v, dict):
            if v.get("type") not in TIMING_ONLY:
                ev.add("GEN", "constraint:" + str(v.get("type")))
        elif k == "activation_restrictions" and v:
            for r in v:
                t = r.get("type") if isinstance(r, dict) else None
                if t == "RequiresCondition":
                    data = r.get("data")
                    inner = data.get("condition") if isinstance(data, dict) else None
                    if inner is not None:
                        # A parsed OR an Unrecognized (text-preserving) condition: the
                        # restriction sentence is represented. It backs only the
                        # "only if" clause (family RESTR) -- it must not mask another
                        # dropped clause in the same ability.
                        ev.add("RESTR", "restriction:RequiresCondition:" +
                               str(inner.get("type") if isinstance(inner, dict) else "?"))
                        if is_gap(inner):
                            ev.gap = True
                    else:
                        ev.empty_wrappers += 1
                elif t not in TIMING_ONLY:
                    ev.add("RESTR", "restriction:" + str(t))
            continue                                # the restriction nodes are accounted for
        elif k == "decline" and v:                  # Optional replacement mode:
            ev.add("DO", "field:decline")          # "you may X. If you don't, Y"
        elif k in ("win_effect", "lose_effect") and v:
            ev.add("FLIP", "field:" + k)
        elif k == "else_ability" and v:
            ev.wild += 1
            ev.kinds["field:else_ability"] += 1
        elif k in STRUCT_FIELDS and v not in (None, [], {}, False):
            ev.add(STRUCT_FIELDS[k], "field:" + k)
        if isinstance(v, (dict, list)):
            scan(v, ev)


def flip_struct(node, found):
    """FlipCoin with a win/lose branch AND a trailing sub_ability: whatever
    follows the branch runs unconditionally (branch-structural drop)."""
    if isinstance(node, list):
        for x in node:
            flip_struct(x, found)
    elif isinstance(node, dict):
        eff = node.get("effect")
        if (isinstance(eff, dict) and eff.get("type") == "FlipCoin"
                and (eff.get("win_effect") or eff.get("lose_effect"))
                and node.get("sub_ability")):
            found.append(node["sub_ability"])
        for v in node.values():
            if isinstance(v, (dict, list)):
                flip_struct(v, found)


def item_text(entry, bucket, idx, item):
    t = item.get("description")
    if t:
        return t
    if bucket == "abilities":
        md = (entry.get("modal") or {}).get("mode_descriptions") or []
        if md and len(md) == len(entry["abilities"]) and idx < len(md):
            return md[idx]
    return None


def detect_entry(entry):
    out = []
    for b in BUCKETS:
        for i, it in enumerate(entry.get(b) or []):
            txt = item_text(entry, b, i, it)
            if not txt:
                continue
            ev = Evidence()
            scan(it, ev)
            clauses = cond_clauses(txt, b)
            need = collections.Counter(c["fam"] for c in clauses if c["fam"] != "RESTR")
            # one restriction SENTENCE is one restriction node, however many "or if"s it has
            for sent in {c["sent"] for c in clauses if c["fam"] == "RESTR"}:
                need["RESTR"] += 1
            missing = [f for f in need if ev.fam[f] == 0 and not ev.wild]
            short = [f for f in need if 0 < ev.fam[f] < need[f]]
            fs = []
            flip_struct(it, fs)
            if fs:
                short = short + ["STRUCT"] if "STRUCT" not in short else short
            if not missing and not short:
                continue
            out.append({"bucket": b, "idx": i, "text": txt,
                        "tier": "A" if missing else "B",
                        "clauses": [c["snip"] for c in clauses], "clause_info": clauses,
                        "families": dict(need), "evidence": dict(ev.kinds),
                        "missing": missing, "short": short, "flip_struct": bool(fs),
                        "item_gap": ev.gap, "empty_wrapper": ev.empty_wrappers})
    return out


def load(recovered=False):
    d = json.load(open(os.path.join(HERE, "data", "card-data.json"), encoding="utf-8"))
    return d


def entry_has_gap(entry):
    ev = Evidence()
    for b in BUCKETS:
        scan(entry.get(b) or [], ev)
    return ev.gap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    d = load()
    hits = []
    for key, e in d.items():
        for h in detect_entry(e):
            h.update(name=e["name"], oid=e.get("scryfall_oracle_id"), key=key,
                     card_gap=entry_has_gap(e))
            hits.append(h)
    print(len(hits), "flagged items on", len({h["key"] for h in hits}), "entries")
    if a.write:
        json.dump(hits, open(os.path.join(HERE, "build", "condition_drops.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
