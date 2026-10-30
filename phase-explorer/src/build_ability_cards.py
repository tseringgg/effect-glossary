#!/usr/bin/env python3
"""Card -> ability-page entries for the card modal: build/ability_pages/cards.json (feature MODAL_ABILITIES in reports/config.js).

    python src/build_ability_cards.py [--check]

Deterministic and read-only on everything but its own output. It reads the ability pages that src/build_ability_pages.py wrote (build/ability_pages/index.json and p/*.json: the cards and
lines on each page are exactly the pages' own, never a second opinion), build/ability_taxonomy_cards.json and _ledger.json, build/index.json + chunks/*.json + placements.json (the parsed
faces, to count abilities and find Unimplemented parts), build/faces/faces.json and build/keyword_facet.json. It writes only build/ability_pages/cards.json (sorted keys, no timestamps).
Nothing under corrections/ or archive/ is opened.

The file is a FILTER AND A LOOKUP, never a placement: it is in no group, no count, no figure, and changes no leaf, group, id, suggestion, page or page membership.

  {v, sig, pages:[[key, name]...], kw:[[key, display]...], x:[[card index, page no, wording]...], d:[...]}
  sig    the same checksum as ability_pages/index.json (the card indexes mean the key order of ability_taxonomy_cards.json)
  pages  every ability page, in the order of ability_pages/index.json; an entry names its page by place in this list
  kw     the parser's keywords (build/keyword_facet.json), by place; "yk:" + key is the existing keyword page
  x      the parser's wording for an entry whose line was not found in the card's text (line = 0 in the entry)
  d      a flat list, one record per card that has anything to show, in card order: card gap (index minus the previous record's), a header, the entries, the keyword places.
         header = st | miss << 4 | k << 8 | n << 12   (k keywords, n entries)
         st: bits 0-2 = why a card with no entry has none (0 it has entries or nothing to say, 1 an instant or sorcery whose effect is not an ability type, 2 the parser read its abilities but
             none is a kind that has a page, 3 something in it was not read, 4 keyword abilities only); bit 3 (8) = part of its text was not read (an Unimplemented node in an ability, or a gap)
         miss: abilities (not keyword abilities, not spell effects) of the card that are on no page
         entry = page no | (line + 1) << 6 | face << 13   (line + 1 = 0: no line found, the wording is in x)
         face: 0 or 1, the place of the face the line is on in build/faces/faces.json (0 for a one-faced card); a transform/modal/adventure card's record holds both faces in "t", split on "//",
               and the first part is the face faces.json calls "pf" (checked against the text of the faces: 820 of 823 agree, 3 share wording and keep the pf order)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_ability_pages as BA          # noqa: E402

BUILD = BA.BUILD
OUT = os.path.join(BUILD, "ability_pages", "cards.json")
SEP = "//"


def segments(t):
    """Index of the part ("//" splits the faces) of the text each line is in."""
    seg, out = 0, []
    for l in (t or "").split("\n"):
        if l.strip() == SEP:
            seg += 1
            out.append(-1)
        else:
            out.append(seg)
    return out


def face_of_segment(card, fl, stats):
    """segment number -> place in faces.json. The first part is face pf; verified against the text where the text identifies it."""
    if not fl:
        return lambda s: 0
    f, pf = fl["f"], fl.get("pf", 0)
    segs = (card.get("t") or "").split("\n//\n")
    order = [pf, 1 - pf]
    if len(segs) == 2 and len(f) == 2:
        texts = [x["t"] for x in f]
        by_text = [[j for j in range(2) if texts[j] == s] for s in segs]
        if all(len(m) == 1 for m in by_text):
            stats["text_unique"] += 1
            if [m[0] for m in by_text] != order:
                stats["pf_rule_disagrees"] += 1
                order = [m[0] for m in by_text]
        else:
            stats["ambiguous_by_text"] += 1               # the faces share wording or differ only in keyword order: the pf order stands
    else:
        stats["one_part"] += 1                            # an aftermath, prepare or split card whose second half is not in "t": every line is on the first part
    return lambda s: order[s] if 0 <= s < len(order) else order[0]


def build():
    idx = BA.J("ability_pages/index.json")
    cards = BA.J("ability_taxonomy_cards.json")["cards"]
    oids = list(cards)
    if idx["sig"] != BA.sig_of(oids):
        raise SystemExit("ability_pages was built for another card list: run src/build_ability_pages.py first")
    pages = [[g[0], g[1]] for g in idx["groups"]]
    pno = {g[0]: i for i, g in enumerate(idx["groups"])}
    faces = BA.J("faces/faces.json")["cards"]
    kwf = BA.J("keyword_facet.json")["keywords"]
    kws = sorted(kwf)
    cidx = {o: i for i, o in enumerate(oids)}
    kw_of = {}
    for j, k in enumerate(kws):
        for o in kwf[k]["c"]:
            if o in cidx:
                kw_of.setdefault(cidx[o], []).append(j)
    # entries: exactly the pages' own
    ent, xs = {}, []
    for key, i in pno.items():
        d = BA.J("ability_pages/p/" + BA.fname(key))
        x = d.get("x") or {}
        for n in range(len(d["r"]) // 2):
            c, l = d["r"][2 * n], d["r"][2 * n + 1]
            ent.setdefault(c, []).append((i, l, x.get(str(n))))
    # the ledger and the parse: abilities with no page, Unimplemented parts, why a card has no entry
    led = BA.J("ability_taxonomy_ledger.json")["rows"]
    idxrows = {r["id"]: r for r in BA.J("index.json")["rows"]}
    rec = BA.J("placements.json")["recovered"]["chunk"]
    chunks = {}

    def face(fid):
        if fid in idxrows:
            c = idxrows[fid]["ch"]
            if c not in chunks:
                chunks[c] = BA.J("chunks/%d.json" % c)
            return chunks[c].get(fid) or {}
        return rec.get(fid) or {}
    by_kind = {}
    for k, name, kind, rule, al, fn in BA.PAGES:
        by_kind.setdefault(kind, []).append(fn)
    kind_of = {v: k for k, v in BA.BUCKET.items()}
    per = {}
    for r in led:
        o, fid, b, i, mode = r[0], r[1], r[2], r[3], r[4]
        if mode is not None or o not in cidx:
            continue
        it = (face(fid).get(b) or [])[i]
        p = per.setdefault(o, {"real": 0, "hit": 0, "kw": 0, "spell": 0, "un": False})
        if BA.has_unimpl(it):
            p["un"] = True
        if b == "abilities" and it.get("kind") == "Activated" and not BA.desc(it):
            p["kw"] += 1
            continue
        if b == "abilities" and it.get("kind") == "Spell":
            p["spell"] += 1
            continue
        p["real"] += 1
        for fn in by_kind[kind_of[b]]:
            try:
                if fn(it):
                    p["hit"] += 1
                    break
            except Exception:
                pass
    stats = {"text_unique": 0, "pf_rule_disagrees": 0, "ambiguous_by_text": 0, "one_part": 0}
    d, prev = [], 0
    n_rec = 0
    for ci, o in enumerate(oids):
        c = cards[o]
        txt = (c.get("t") or "").strip()
        p = per.get(o) or {"real": 0, "hit": 0, "kw": 0, "spell": 0, "un": False}
        es = sorted(ent.get(ci, []), key=lambda e: (e[0], e[1], e[2] or ""))
        ks = kw_of.get(ci, [])
        st = 0
        if txt and not es:
            if not (p["real"] or p["kw"] or p["spell"]):
                st = 4 if ks else 3
            elif p["un"]:
                st = 3
            elif p["real"]:
                st = 2
            elif p["spell"]:
                st = 1 if re.search(r"(?:^|[ -])(?:Instant|Sorcery)(?:$| )", c.get("ty") or "") else 2         # an Attraction's Visit or a Saga's chapter is a spell-kind ability on a card that is not a spell
            else:
                st = 4
        if p["un"] or c.get("g"):
            st |= 8
        miss = max(0, p["real"] - p["hit"]) if es else 0
        if not (es or ks or st):
            continue
        fl = faces.get(o)
        fseg = face_of_segment(c, fl, stats) if fl else (lambda s: 0)
        segs = segments(c.get("t"))
        assert miss < 16 and len(ks) < 16 and len(es) < 16 and len(pages) <= 64, "a packed field is too small"
        d += [ci - prev, st | miss << 4 | len(ks) << 8 | len(es) << 12]
        prev = ci
        for pn, l, x in es:
            line = l if l >= 0 else -1
            f = fseg(segs[l]) if 0 <= l < len(segs) and segs[l] >= 0 else 0
            if l < 0:
                f = fseg(0)
                if x:
                    xs.append([ci, pn, x])
            assert line + 1 < 128
            d.append(pn | (line + 1) << 6 | f << 13)
        d += ks
        n_rec += 1
    doc = {"v": 1, "sig": idx["sig"], "pages": pages, "kw": [[k, kwf[k]["d"]] for k in kws], "x": xs, "d": d}
    return doc, stats, n_rec


def dumps(doc):
    return (json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def outputs():
    doc, stats, n = build()
    return {"ability_pages/cards.json": dumps(doc)}, stats, n


def write():
    outs, stats, n = outputs()
    data = outs["ability_pages/cards.json"]
    if not os.path.exists(OUT) or open(OUT, "rb").read() != data:      # an unchanged file is not rewritten
        with open(OUT, "wb") as fh:
            fh.write(data)
    return outs, stats, n


def main():
    if "--check" in sys.argv:
        outs, stats, n = outputs()
        data = outs["ability_pages/cards.json"]
        ok = os.path.exists(OUT) and open(OUT, "rb").read() == data
        print("ability_pages/cards.json %s" % ("up to date" if ok else "differs"))
        sys.exit(0 if ok else 1)
    outs, stats, n = write()
    print("wrote build/ability_pages/cards.json: %s bytes, %d card records; faces %s" % (format(len(outs["ability_pages/cards.json"]), ","), n, stats))


if __name__ == "__main__":
    main()
