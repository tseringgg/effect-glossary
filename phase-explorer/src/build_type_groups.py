#!/usr/bin/env python3
"""Type and subtype pages, and the two faces of two-faced cards: build/type_groups/*.json and build/faces/faces.json.

    python src/build_type_groups.py [--check]

Deterministic and read-only on everything but its own output: it reads the tracked MTGJSON file data/AtomicCards-20261003.json.gz (structured types, subtypes, supertypes, face names, colours, mana cost,
text, layout) and build/ability_taxonomy_cards.json (which cards are in scope and the page's face for each); it writes only build/type_groups/ and build/faces/. Same inputs, same bytes (sorted keys, no
timestamps). src/export_static.py runs it when the flag TYPE_GROUPS or FLIP_FACES is on (reports/config.js) and then copies the files like any other build file.

Type pages are FILTERS AND PAGES, never placements: they are in no group, no count, no figure. A card is on the page of every type, supertype and subtype that ANY of its faces has ("Saga" on a back face
counts); a card that is on a page only through a face the page does not list is also in "o" (shown as "via other face"). A word gets a page when 5 or more cards have it.

  build/type_groups/index.json    {v, sig, n, groups:[[key, name, kind, domain, count, aliases[]]...]}   key "ty:t.creature" (type), "ty:s.legendary" (supertype), "ty:u.saga" (subtype): the word, lowercased, anything
                                  that is not a letter or digit becomes "-". Stable: a count never changes a key. kind t/s/u. domain: for subtypes, where the word is used (creature, artifact, enchantment, land, planeswalker, spell, battle).
  build/type_groups/members.json  {v, sig, m:{key:[card index...]}, o:{key:[card index...]}}   an index is the card's place in the key order of build/ability_taxonomy_cards.json ("sig" checks it is the same file);
                                  o is the part of m that is on the page only through another face.
  build/faces/faces.json          {v, sig, cards:{oracle id:{l: layout, pf: index of the face the page lists, f:[{n, mc, ty, t, c}...]}}}   both faces of the 861 cards that have two (transform, modal, adventure,
                                  split, aftermath, flip, prepare); c is the face's colour; ty uses " - " like the page's own type line.
"""
import gzip
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
ATOMIC = os.path.join(HERE, "data", "AtomicCards-20261003.json.gz")
CARDS = os.path.join(BUILD, "ability_taxonomy_cards.json")
TYPES = ["Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Land", "Planeswalker", "Battle", "Kindred", "Conspiracy", "Stickers", "Dungeon", "Phenomenon", "Plane", "Scheme", "Vanguard"]
SUPERS = ["Legendary", "Snow", "World", "Basic"]
MIN_CARDS = 5
TWO_FACED = {"transform", "modal_dfc", "adventure", "split", "aftermath", "flip", "prepare"}
IRREGULAR = {"Elf": ["elves"], "Wolf": ["wolves"], "Dwarf": ["dwarves"], "Werewolf": ["werewolves"], "Fungus": ["fungi"], "Cyclops": ["cyclopes"], "Homunculus": ["homunculi"], "Mouse": ["mice"],
             "Octopus": ["octopuses", "octopi"], "Sphinx": ["sphinxes"], "Wolverine": [], "Lich": ["liches"], "Harpy": ["harpies"], "Zombie": [], "Ox": ["oxen"], "Kindred": ["tribal"], "Nautilus": ["nautiluses", "nautili"]}
DOMAIN_OF = {"Creature": "creature", "Kindred": "creature", "Planeswalker": "planeswalker", "Land": "land", "Artifact": "artifact", "Enchantment": "enchantment", "Instant": "spell", "Sorcery": "spell", "Battle": "battle"}
DOMAIN_ORDER = ["creature", "spell", "artifact", "enchantment", "land", "planeswalker", "battle"]
LAYOUT_NAME = {"modal_dfc": "modal"}


def slug(w):
    return re.sub(r"[^a-z0-9]+", "-", w.lower()).strip("-")


def sort_key(w):
    return (w.lower(), w)


def load_cards():
    with open(CARDS, encoding="utf-8") as fh:
        return json.load(fh)["cards"]


def load_atomic():
    """oracle id -> list of face records (deduplicated, in side order)."""
    with gzip.open(ATOMIC, "rt", encoding="utf-8") as fh:
        data = json.load(fh)["data"]
    by = {}
    for name in sorted(data):
        for f in data[name]:
            oid = (f.get("identifiers") or {}).get("scryfallOracleId")
            if not oid:
                continue
            lst = by.setdefault(oid, [])
            key = (f.get("faceName") or f.get("name"), f.get("side"))
            if any((x.get("faceName") or x.get("name"), x.get("side")) == key for x in lst):
                continue
            lst.append(f)
    for oid, lst in by.items():
        lst.sort(key=lambda f: (f.get("side") or "a"))
    return by


def sig_of(oids):
    """FNV-1a (32 bit) of the ids joined by newlines: the page recomputes it from Object.keys(CARDS) to be sure the indexes mean the same cards."""
    h = 2166136261
    for b in "\n".join(oids).encode("utf-8"):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return "%08x" % h


def page_face(cards_n, faces):
    """Index of the face the page lists for this card."""
    if len(faces) == 1:
        return 0
    n = (cards_n or "").lower()
    for i, f in enumerate(faces):
        if (f.get("faceName") or "").lower() == n:
            return i
    return 0


def build():
    cards = load_cards()
    oids = list(cards)
    atomic = load_atomic()
    missing = [o for o in oids if o not in atomic]
    # a card Atomic does not have contributes no page membership (none today: Atomic covers all in-scope cards)
    # membership[(kind, word)] -> {idx: via_other_face_only}
    page_sets, any_sets, uses = {}, {}, {}
    changelings = set()
    for i, oid in enumerate(oids):
        faces = atomic.get(oid)
        if not faces:
            continue
        pf = page_face(cards[oid]["n"], faces)
        for fi, f in enumerate(faces):
            if "Changeling" in (f.get("keywords") or []) and "Creature" in (f.get("types") or []):
                changelings.add(i)
            types = [t for t in f.get("types") or [] if t in TYPES]
            supers = [s for s in f.get("supertypes") or [] if s in SUPERS]
            subs = [s for s in f.get("subtypes") or [] if s]
            words = [("t", t) for t in types] + [("s", s) for s in supers] + [("u", u) for u in subs]
            for w in words:
                any_sets.setdefault(w, set()).add(i)
                if fi == pf:
                    page_sets.setdefault(w, set()).add(i)
            if subs:
                vote = {DOMAIN_OF[t] for t in types if t in DOMAIN_OF}
                if "creature" in vote:
                    vote = {"creature"}
                for u in subs:
                    for dmn in vote:
                        uses.setdefault(u, {}).setdefault(dmn, 0)
                        uses[u][dmn] += 1
    keep = sorted((w for w, s in any_sets.items() if len(s) >= MIN_CARDS), key=lambda w: ("tsu".index(w[0]), TYPES.index(w[1]) if w[0] == "t" else SUPERS.index(w[1]) if w[0] == "s" else 0, sort_key(w[1])))
    groups, members, other, seen = [], {}, {}, {}
    for kind, word in keep:
        key = "ty:%s.%s" % (kind, slug(word))
        if key in seen:
            sys.stderr.write("build_type_groups: key collision %s: %r and %r\n" % (key, seen[key], word))
            sys.exit(1)
        seen[key] = word
        dmn = ""
        if kind == "u":
            v = uses.get(word, {})
            dmn = sorted(v, key=lambda d: (-v[d], DOMAIN_ORDER.index(d)))[0] if v else "creature"
        al = IRREGULAR.get(word, [])
        groups.append([key, word, kind, dmn, len(any_sets[(kind, word)]), sorted(al)])
        members[key] = sorted(any_sets[(kind, word)])
        other[key] = sorted(any_sets[(kind, word)] - page_sets.get((kind, word), set()))
    sig = sig_of(oids)
    index = {"v": 1, "sig": sig, "n": len(oids), "changelings": len(changelings), "groups": groups}
    mem = {"v": 1, "sig": sig, "m": members, "o": {k: v for k, v in other.items() if v}}
    # the faces of two-faced cards
    fc = {}
    for oid in oids:
        faces = atomic.get(oid)
        if not faces or len(faces) < 2 or faces[0].get("layout") not in TWO_FACED:
            continue
        fc[oid] = {"l": LAYOUT_NAME.get(faces[0]["layout"], faces[0]["layout"]), "pf": page_face(cards[oid]["n"], faces),
                   "f": [{"n": f.get("faceName") or f.get("name"), "mc": f.get("manaCost") or "", "ty": (f.get("type") or "").replace(" — ", " - "), "t": f.get("text") or "",
                          "c": "".join(c for c in "WUBRG" if c in (f.get("colors") or []))} for f in faces[:2]]}
    return index, mem, {"v": 1, "sig": sig, "cards": fc}, missing


def dumps(d):
    return (json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def outputs():
    index, mem, faces, missing = build()
    return {"type_groups/index.json": dumps(index), "type_groups/members.json": dumps(mem), "faces/faces.json": dumps(faces)}, missing, (index, mem, faces)


def write():
    outs, missing, _ = outputs()
    for rel, data in outs.items():
        p = os.path.join(BUILD, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not os.path.exists(p) or open(p, "rb").read() != data:      # an unchanged file is not rewritten
            with open(p, "wb") as fh:
                fh.write(data)
    return outs, missing


def main():
    if "--check" in sys.argv:
        outs, missing, _ = outputs()
        bad = [r for r, d in outs.items() if not os.path.exists(os.path.join(BUILD, *r.split("/"))) or open(os.path.join(BUILD, *r.split("/")), "rb").read() != d]
        print("type_groups/faces files %s" % ("up to date" if not bad else "differ: " + ", ".join(bad)))
        sys.exit(1 if bad else 0)
    outs, missing = write()
    print("wrote %s; %d in-scope cards not in the MTGJSON file" % (", ".join("build/%s (%s bytes)" % (r, format(len(d), ",")) for r, d in outs.items()), len(missing)))


if __name__ == "__main__":
    main()
