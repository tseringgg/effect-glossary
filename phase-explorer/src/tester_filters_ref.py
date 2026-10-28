#!/usr/bin/env python3
"""An independent Python implementation of the tester site's "Narrow by group" rules and filter facts (reports/testerfilters.js), used by src/test_tester_static.py to compare the page's chips and counts.

It reads the same build files the group pages are made from (members, tentative, loose, tag, keyword and replacement files, sibling placements, build/hand_view.json) and never looks at the JavaScript.

Rules (the header of reports/testerfilters.js states them): a chip is a group that is offered in build/manual_index.json with at least 3 of the list's cards and fewer than 90% of them; not one of the page's own
groups; not a near-twin of the page (name words Jaccard >= 0.7, or whole card sets Jaccard >= 0.8); not a near-twin of a chip already kept; the member groups of a merged page are one chip (its union).
"""
import json
import os
import re
import collections

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(HERE, "build")
STOPN = set("a an the of to or and it its this that his her their from in on for with you your".split())
TYPES = ["Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Land", "Planeswalker", "Battle", "Kindred"]


def name_key(n):
    n = re.sub(r"\(.*?\)", "", n.lower())
    n = re.sub("\u2014.*$", "", n)
    n = re.sub(r"[^a-z0-9/ +\-]", " ", n)
    return {t for t in n.split() if t and t not in STOPN}


def clean(n):
    return re.sub("\\s*\u2014.*$", "", re.sub(r"\s*\(.*?\)", "", n)).strip()


def jac(a, b):
    if not a or not b:
        return 0.0
    i = len(a & b)
    return i / (len(a) + len(b) - i)


def _j(name):
    return json.load(open(os.path.join(B, name), encoding="utf-8"))


class Ref:
    def __init__(self, hand_view_path=None):
        self.MI = _j("manual_index.json")
        self.C = _j("ability_taxonomy_cards.json")["cards"]
        self.TAX = _j("ability_taxonomy.json")
        self.MG = _j("merged_groups/index.json")
        self.img = _j("card_images.json")["cards"]
        tent, loose, tags, sib = _j("tentative_placements.json"), _j("loose_groups.json"), _j("tag_placements.json"), _j("sibling_placements.json")
        members = _j("ability_taxonomy_members.json")["leaves"]
        hv = json.load(open(hand_view_path or os.path.join(HERE, "dist", "build", "hand_view.json"), encoding="utf-8"))
        G = self.MI["groups"]
        self.G = G
        self.tent_ids = set(tent["groups"])
        by_gid = self.MG["by_gid"]

        def key_of(gid):
            return "P:" + by_gid[gid] if gid in by_gid else gid
        mem = collections.defaultdict(set)

        def add(gid, oid):
            if oid in self.C and gid in G and G[gid][4]:
                mem[key_of(gid)].add(oid)
        for lid, rows in members.items():
            for r in rows:
                add("leaf:" + lid, r[0])
        for lid, g in sib["groups"].items():
            for r in g["m"]:
                add("leaf:" + lid, r[0])
        for i, g in tent["groups"].items():
            for r in g["m"]:
                add("tent:" + i, r[0])
        for i, g in loose["groups"].items():
            for r in g["m"]:
                add("loose:" + i, r[0])
        for i, g in tags["groups"].items():
            for o in g["m"]:
                add("tag:" + i, o)
        for gid, l in self.TAX["blocks"]["keyword"]["leaves"].items():
            for o in l["cards"]:
                add(gid, o)
        for i, l in self.TAX["blocks"]["replacement"]["leaves"].items():
            for o in l["cards"]:
                add("rp:" + i, o)
        for oid, gids in hv["adds"].items():
            for g in gids:
                add(g, oid)
        for oid, gids in hv["removes"].items():
            for g in gids:
                if g not in by_gid and key_of(g) in mem:
                    mem[key_of(g)].discard(oid)
        self.mem = dict(mem)
        self.pages = {p["slug"]: p for p in self.MG["pages"]}
        self.name, self.nk, self.loose = {}, {}, {}
        for k in self.mem:
            if k.startswith("P:"):
                pg = self.pages[k[2:]]
                self.name[k] = pg["name"]
                self.loose[k] = any(m["layer"] == "tag" for m in pg["members"])
            else:
                self.name[k] = G[k][0]
                layer = G[k][3]
                self.loose[k] = layer in ("tent", "loose", "tag") or (layer == "leaf" and bool(self.TAX["leaves"].get(k[5:]) and self.TAX["leaves"][k[5:]]["flags"]))
            self.nk[k] = name_key(self.name[k])
        self.of = collections.defaultdict(list)
        for k, s in self.mem.items():
            for o in s:
                self.of[o].append(k)

    def visible(self, oid):
        return oid in self.img

    def own(self, page_key):
        """The page's own groups (and the chip key of a merged page) and the names it answers to."""
        red = self.MG["redirects"].get(page_key)
        if red:
            pg = self.pages[red]
            return {m["gid"] for m in pg["members"]} | {"P:" + pg["slug"]}, [pg["name"]] + [m["name"] for m in pg["members"]]
        kind, _, i = page_key.partition(":")
        gid = {"l": "leaf:" + i, "tg": "tent:" + i, "ct": "tag:" + i, "kl": i, "gl": "rp:" + i, "hg": "hand:" + i}.get(kind)
        if kind == "lg":
            gid = ("tent:" if i in self.tent_ids else "loose:") + i
        if not gid:
            return set(), []
        k = "P:" + self.MG["by_gid"][gid] if gid in self.MG["by_gid"] else gid
        return {gid, k}, []

    def chips(self, lst, page_oids, page_key, selected=()):
        own, names = self.own(page_key)
        own_nk = [name_key(n) for n in names] + [self.nk[k] for k in own if k in self.nk]
        pset = set(page_oids)
        cnt_page = collections.Counter()
        for o in pset:
            for k in self.of.get(o, ()):
                cnt_page[k] += 1
        twins = set()
        for k, n in cnt_page.items():
            if any(jac(self.nk[k], a) >= 0.7 for a in own_nk) or n / (len(pset) + len(self.mem[k]) - n) >= 0.8:
                twins.add(k)
        cnt = collections.Counter()
        for o in lst:
            for k in self.of.get(o, ()):
                if k not in own:
                    cnt[k] += 1
        N = len(lst)
        cand = [(k, n) for k, n in cnt.items() if n >= 3 and n * 10 < N * 9 and k not in twins and k not in selected]
        cand.sort(key=lambda x: (-x[1], clean(self.name[x[0]]), x[0]))
        kept = []
        for k, n in cand:
            dup = False
            for d, _ in kept:
                A, Bs = self.mem[k], self.mem[d]
                if jac(self.nk[k], self.nk[d]) >= 0.7 or len(A & Bs) / len(A | Bs) >= 0.8:
                    dup = True
                    break
            if not dup:
                kept.append((k, n))
        return [(k, clean(self.name[k]), n) for k, n in kept]

    # facts, the same rule as the page: type words of the front type line, colour, mana value
    def facts(self, oid):
        c = self.C[oid]
        return {"mv": c["mv"], "col": c["col"], "ts": [t for t in c["ty"].split(" - ")[0].split() if t in TYPES]}


def mvb(mv):
    return "none" if mv is None else "6+" if mv >= 6 else str(mv)


def col_match(f, c):
    return f["col"] == "" if c == "C" else len(f["col"]) >= 2 if c == "M" else c in f["col"]


# ---------------------------------------------------------------- feature NARROW_NO_CUT and COLOUR_MODES (reports/testerfilters.js); read by src/test_tester_features.py
def restates(a, b):
    """NARROW_NO_CUT: every word of the shorter name (plurals folded, 2 words or more) is in the longer one: the chip only restates the page ("Mill cards" on "Library > Mill cards, by you")."""
    fa, fb = {re.sub("s$", "", w) for w in a}, {re.sub("s$", "", w) for w in b}
    sm, lg = (fa, fb) if len(fa) <= len(fb) else (fb, fa)
    return len(sm) >= 2 and sm <= lg


def chips_all_nnc(ref, lst, page_oids, page_key, selected=()):
    """Every candidate chip for the list under NARROW_NO_CUT, before the floor: shared count >= 1, fewer than 90% of the list, not a twin of the page (name words Jaccard >= 0.7, or one name only restates the other, or card sets Jaccard >= 0.8), not selected. Order: shared count (high first), then the
    smaller group, then name, then key. A chip that picks exactly the same cards of this list as one already kept is folded into it; near-twins of a kept chip (name words or card sets, Jaccard 0.7 / 0.8) too.
    Returns [(key, label, n, group size)]."""
    own, names = ref.own(page_key)
    own_nk = [name_key(n) for n in names] + [ref.nk[k] for k in own if k in ref.nk]
    pset = set(page_oids)
    cnt_page = collections.Counter()
    for o in pset:
        for k in ref.of.get(o, ()):
            cnt_page[k] += 1
    twins = {k for k, n in cnt_page.items() if any(jac(ref.nk[k], a) >= 0.7 or restates(ref.nk[k], a) for a in own_nk) or n / (len(pset) + len(ref.mem[k]) - n) >= 0.8}
    cnt = collections.Counter()
    for o in lst:
        for k in ref.of.get(o, ()):
            if k not in own:
                cnt[k] += 1
    N = len(lst)
    cand = [(k, n) for k, n in cnt.items() if n >= 1 and n * 10 < N * 9 and k not in twins and k not in selected]
    cand.sort(key=lambda x: (-x[1], len(ref.mem[x[0]]), clean(ref.name[x[0]]), x[0]))
    kept, sigs = [], set()
    lset = set(lst)
    for k, n in cand:
        sig = frozenset(ref.mem[k] & lset)
        if sig in sigs:
            continue
        if any(jac(ref.nk[k], ref.nk[d]) >= 0.7 or len(ref.mem[k] & ref.mem[d]) / len(ref.mem[k] | ref.mem[d]) >= 0.8 for d, _ in kept):
            continue
        kept.append((k, n)); sigs.add(sig)
    return [(k, clean(ref.name[k]), n, len(ref.mem[k])) for k, n in kept]


def chips_nnc(ref, lst, page_oids, page_key, selected=(), single=False, cap=60):
    """The chips the page shows with NARROW_NO_CUT: floor 2 (1 with the single-card link), at most 60. Also the number of 1-card chips and the total before the cap."""
    allc = chips_all_nnc(ref, lst, page_oids, page_key, selected)
    main = [c for c in allc if c[2] >= 2]
    vis = allc if single else main
    return [(k, l, n) for k, l, n, _ in vis[:cap]], len(allc) - len(main), len(vis)


def col_ok(col, cols, mode):
    """COLOUR_MODES, written from the sets: X = the card's colours, S = chosen colour letters, c / m = the colourless and multicolour chips."""
    if not cols:
        return True
    X, S = set(col), {x for x in cols if x in "WUBRG"}
    c, m = "C" in cols, "M" in cols
    if mode == "any":
        return bool(X & S) or (c and not X) or (m and len(X) >= 2)
    if mode == "all":
        return S <= X and (not c or not X) and (not m or len(X) >= 2)
    if mode == "only":
        if not X:
            return c
        if m and not S:
            return len(X) >= 2
        return X <= S and (not m or len(X) >= 2)
    if mode == "exactly":
        if c:
            return not X and not S
        if not S:
            return len(X) >= 2
        return X == S and (not m or len(X) >= 2)
    return not (X & S) and (not c or bool(X)) and (not m or len(X) < 2)
