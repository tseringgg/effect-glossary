#!/usr/bin/env python3
"""Tester-facing layer: "Not yet organized" groups + the "Find a card" lookup.

    python src/build_ledger.py          # (twice, around build_placements.py, as always)
    python src/build_keyword_layer.py
    python src/build_unorganized.py     # -> build/unorganized.json, unorganized_cards.json, lookup.json

DISPLAY ONLY. This reads the ledger and the placement / keyword layers and writes three NEW
files. It changes no status, no placement, no threshold and no frozen file. The plain-language
wording a tester sees lives here (and in reports/findcard.js) and nowhere upstream.

  build/unorganized.json        boot file (a few KB): groups, counts, one-line explanations,
                                the reconciliation line.
  build/unorganized_cards.json  lazy: per group, the cards with their gap text / suggestion.
  build/lookup.json             lazy: one entry for EVERY oracle id in the ledger universe
                                (38,921), so "Find a card" works for cards, tokens, art cards
                                and planes alike.

Group rule. Every in-scope card the ledger leaves unplaced goes to exactly one group, by the
stage it stopped at. Collision-recovered cards are not a group of their own: they are parsed
cards and fold into the group for their stage, carrying a plain "recovered" tag.
"""
import collections
import io
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ledger as BL  # noqa: E402  gap_fragments only; its main() is not run

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")

# ---------------------------------------------------------------- tester-facing wording
TITLE = "Not yet organized"
INTRO = ("Cards the tool has not put in a group yet. This is about the tool, not the card: "
         "open a group to see why each card is here.")
GROUPS = [
    (1, "Parsed, but with a gap",
     "The parser read most of this card but could not understand part of its text (shown next "
     "to the card). We don't group cards on a partial reading, because it could put them in "
     "the wrong place."),
    (2, "Parsed, no close group found",
     "The parser read this card fully, but it doesn't closely resemble any existing group. The "
     "nearest group is shown as a suggestion with how close it is. The card has not been "
     "placed there."),
    (3, "No effect to group",
     "The parser read this card fully, but its rules change how other things happen (for "
     "example “prevent all combat damage”, or “if X would happen, do Y instead”) "
     "or only add a cost, rather than doing something themselves. Grouping compares what "
     "cards do, so there is nothing to compare."),
    (4, "Not parsed yet",
     "The parser produced nothing usable for this card's rules text, so there is nothing to "
     "group it on."),
    (5, "Known parse mistake",
     "We checked this card by hand and the parser got part of it wrong, for example reading a "
     "cost as free. It is held back until that is fixed."),
    (6, "No rules text: newer cards",
     "These cards have no rules text. The “No abilities” group above was built before "
     "they were released, so they are not in it yet."),
]
# display words for the nearest-group suggestion (group 2). Display only: no placement
# threshold is involved.
CLOSE, LOOSE = 0.70, 0.50

OOS_TEXT = {
    "art_series": "an art card: artwork only, with no rules",
    "token": "a token: a game piece that cards create, not a card",
    "double_faced_token": "a two-sided token: a game piece that cards create, not a card",
    "emblem": "an emblem: a game marker that cards create, not a card",
    "memorabilia": "a collector or memorabilia item, not a card used in normal play",
    "box": "a box or counter item from a product, not a card",
    "planar": "a plane (Planechase): played from its own deck; not covered yet",
    "scheme": "a scheme (Archenemy): played from its own deck; not covered yet",
    "vanguard": "a Vanguard avatar: played from its own deck; not covered yet",
    "unlisted": "listed by Scryfall but not in the card list this tool is built from",
}


def oos_code(reason):
    if reason.startswith("deferred_card_type:"):
        return reason.split(":", 1)[1]
    r = reason.split(":", 1)[1]
    if r == "front_card":
        return "memorabilia"
    if r in OOS_TEXT:
        return r
    if r.endswith("/token"):
        return "token"
    if r.endswith("/box"):
        return "box"
    return "unlisted"


# ---------------------------------------------------------------- name folding
SPECIAL = {"æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ß": "ss",
           "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L",
           "þ": "th", "Þ": "Th", "ð": "d", "Ð": "D"}


def fold_char(c):
    if c in SPECIAL:
        return SPECIAL[c]
    d = unicodedata.normalize("NFKD", c)
    return "".join(x for x in d if not unicodedata.combining(x))


def norm(s, fold):
    out = []
    for c in s:
        if ord(c) > 127:
            c = fold.get(c, "")
        out.append(c)
    t = "".join(out).lower().replace("//", " ")
    t = re.sub(r"[^a-z0-9 ]+", "", t)
    return re.sub(r" +", " ", t).strip()


# ---------------------------------------------------------------- gap text
GAP_PREFIX = re.compile(r"^[a-z ]*?(?:candidate|matched)[a-z ]*? failed [a-z ]+ parser: ")


def clean_gaps(frags):
    out, seen = [], set()
    for kind, cat, text in frags:
        text = GAP_PREFIX.sub("", text or "").strip()
        if kind == "unmodelled" and cat == "Unrecognized condition":
            k = "cond"
        elif kind == "unmodelled" and cat == "Unknown trigger mode":
            k = "trigger"
        elif kind == "GenericEffect":
            k = "effect"
        else:
            k = "unread"
        if (k, text) not in seen and text:
            seen.add((k, text))
            out.append([k, text])
    return out


def walk_unrecognized(node, out):
    if isinstance(node, dict):
        if node.get("type") == "Unrecognized" and isinstance(node.get("text"), str):
            out.append(["cond", node["text"]])
        for v in node.values():
            walk_unrecognized(v, out)
    elif isinstance(node, list):
        for v in node:
            walk_unrecognized(v, out)


def main():
    ledger = json.load(io.open(os.path.join(BUILD, "ledger.json"), encoding="utf-8"))
    R = ledger["rows"]
    P = json.load(io.open(os.path.join(BUILD, "placements.json"), encoding="utf-8"))
    KL = json.load(io.open(os.path.join(BUILD, "keyword_layer.json"), encoding="utf-8"))
    AL = json.load(io.open(os.path.join(BUILD, "ability_layer.json"), encoding="utf-8"))
    corr = {c["oracle_id"]: c for c in json.load(io.open(os.path.join(HERE, "corrections", "corrections.json"),
                                                         encoding="utf-8"))}
    idx = {r["id"]: r for r in json.load(io.open(os.path.join(BUILD, "index.json"), encoding="utf-8"))["rows"]}
    chunks = {}

    def entry(fid):
        if fid in idx:
            ch = idx[fid]["ch"]
            if ch not in chunks:
                chunks[ch] = json.load(io.open(os.path.join(BUILD, "chunks", str(ch) + ".json"), encoding="utf-8"))
            return chunks[ch].get(fid) or {}
        return P["recovered"]["chunk"].get(fid) or {}

    def face_ids(r):
        return [f["id"] for f in r["evidence"].get("faces", [])] or \
               [f["id"] for f in (r["evidence"].get("recovered") or {}).get("faces", [])]

    # ---- groups
    def group_of(r):
        st, rs = r["status"], r["placement"].get("reason")
        if rs == "below_similarity_floor":
            return 2
        if st in ("partial", "unmodelled_node") or rs == "recovered_partial":
            return 1
        if st == "no_extractable_effect" or rs == "recovered_no_extractable_effect":
            return 3
        if st == "unparsed":
            return 4
        if st == "corrections_flagged":
            return 5
        if st == "vanilla":
            return 6
        raise SystemExit("unplaced in-scope card with no group: %s %s %s" % (r["name"], st, rs))

    members = collections.defaultdict(list)
    n_total = n_placed = n_oos = 0
    for oid, r in sorted(R.items()):
        n_total += 1
        if r["status"] == "out_of_scope":
            n_oos += 1
        elif r["placement"]["method"] != "unplaced":
            n_placed += 1
        else:
            members[group_of(r)].append(oid)
    n_un = sum(len(v) for v in members.values())
    assert n_placed + n_un + n_oos == n_total, "placed + unplaced + out of scope != universe"

    cards = {}
    for gid, oids in members.items():
        lst = []
        for oid in sorted(oids, key=lambda o: (R[o]["name"].lower(), o)):
            r = R[oid]
            fids = face_ids(r)
            tag = ("recovered" if r["evidence"].get("recovered") else
                   "new" if r["evidence"].get("layer") == "new_release" else "")
            c = {"c": oid, "n": r["name"], "f": fids}
            if tag:
                c["t"] = tag
            if gid == 1:
                frags = r["evidence"].get("fragments")
                if not frags:
                    frags = []
                    for fid in fids:
                        e = entry(fid)
                        frags.extend(BL.gap_fragments(e, e.get("name") or ""))
                gaps = clean_gaps(frags)
                if not gaps:                     # e.g. an unrecognized condition on a casting option
                    extra = []
                    for fid in fids:
                        walk_unrecognized(entry(fid), extra)
                    gaps = clean_gaps([("unmodelled", "Unrecognized condition", t) for _, t in extra])
                if gaps:
                    c["g"] = gaps[:6]
                    if len(gaps) > 6:
                        c["gm"] = len(gaps) - 6
            elif gid == 2:
                c["s"] = [r["placement"]["best_leaf"], r["placement"]["similarity"]]
            elif gid == 5:
                cr = corr.get(oid)
                if cr:
                    c["note"] = re.split(r"(?<=[.!?])\s", cr["issue"].strip())[0][:220]
            lst.append(c)
        cards[gid] = lst

    def strength(s):
        return "close" if s >= CLOSE else "loose" if s >= LOOSE else "weak"

    groups = []
    for gid, name, explain in GROUPS:
        lst = cards[gid]
        g = {"id": gid, "name": name, "explain": explain, "cards": len(lst),
             "faces": sum(len(c["f"]) for c in lst),
             "recovered": sum(1 for c in lst if c.get("t") == "recovered"),
             "new": sum(1 for c in lst if c.get("t") == "new")}
        if gid == 2:
            g["strength"] = dict(collections.Counter(strength(c["s"][1]) for c in lst))
        if gid == 1:
            g["gap_kinds"] = dict(collections.Counter(c["g"][0][0] if c.get("g") else "none" for c in lst))
        groups.append(g)
    assert sum(g["cards"] for g in groups) == n_un
    unorg = {
        "v": 1, "title": TITLE, "intro": INTRO, "groups": groups,
        "strength_words": {"close": CLOSE, "loose": LOOSE},
        "totals": {"universe": n_total, "in_scope": n_total - n_oos, "organized": n_placed,
                   "not_yet_organized": n_un, "not_cards": n_oos},
        "reconciles": n_placed + n_un + n_oos == n_total and sum(g["cards"] for g in groups) == n_un,
    }

    # ---- lookup: every oracle id
    # every accented / ligature letter a tester might type, not only the ones in today's names
    fold = {chr(cp): fold_char(chr(cp)) for cp in range(0xC0, 0x250) if fold_char(chr(cp)).isascii()}
    for r in R.values():
        for nm in [r["name"]] + [f["name"] for f in r["evidence"].get("faces", [])]:
            for ch in nm:
                if ord(ch) > 127 and ch not in fold:
                    fold[ch] = fold_char(ch)
    group_of_oid = {c["c"]: gid for gid, lst in cards.items() for c in lst}
    entries = []
    for oid, r in sorted(R.items()):
        faces = [f["name"] for f in r["evidence"].get("faces", [])]
        others = sorted({n for n in faces if n != r["name"]})
        tags = ("r" if r["evidence"].get("recovered") else "") + ("n" if r["evidence"].get("layer") == "new_release" else "")
        nf = max(1, len(face_ids(r)))
        if r["status"] == "out_of_scope":
            ev = r["evidence"]
            entries.append([oid, r["name"], others, "o",
                            [oos_code(r["reason"]), ev.get("scryfall_set_type"), ev.get("scryfall_set")], 0, tags])
            continue
        pl = r["placement"]
        m = pl["method"]
        if m == "clustered":
            code, extra = "c", pl["leaf"]
        elif m == "proximity":
            code, extra = "p", [pl["leaf"], pl["similarity"]]
        elif m == "ability":
            code, extra = "a", [pl["leaf"], AL["cards"][oid]["placed"][0]["t"][:100]]
        elif m == "keyword_rule":
            code, extra = "k", pl["leaf"]
        elif m == "vanilla_rule":
            code, extra = "v", pl.get("branch")
        else:
            code, extra = "u", group_of_oid[oid]
        entries.append([oid, r["name"], others, code, extra, nf, tags])
    lookup = {"v": 1, "fold": fold, "oos": OOS_TEXT, "entries": entries}

    def dump(name, obj):
        with io.open(os.path.join(BUILD, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    dump("unorganized.json", unorg)
    dump("unorganized_cards.json", {"v": 1, "groups": {str(k): v for k, v in sorted(cards.items())}})
    dump("lookup.json", lookup)
    print(json.dumps({"universe": n_total, "organized": n_placed, "not_yet_organized": n_un,
                      "not_cards": n_oos, "reconciles": unorg["reconciles"],
                      "groups": [(g["id"], g["name"], g["cards"]) for g in groups],
                      "lookup_entries": len(entries), "fold_chars": len(fold)}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
