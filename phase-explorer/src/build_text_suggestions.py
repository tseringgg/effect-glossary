#!/usr/bin/env python3
"""Text suggestions for the hand-placement panel and the batch view. NEW FILES ONLY (build/text_sug/*, reports/text-suggestions.md). Suggestions are labelled suggestions; nothing is ever placed from them.

    python src/build_text_suggestions.py     # about 4 minutes; run build_manual_layer.py and build_manual_suggestions.py first

TEXT_SUGGESTIONS = False writes nothing and removes this script's own outputs, so the build directory is exactly the build without this layer.

What it does. Every group offered for hand placement gets a text profile: the rules lines of its members (the card's own lines for replacement, community-tag and hand-placed members). A card is split into lines; each line is compared
(TF-IDF over words and word pairs, reminder text and the card's own name removed) with every member line of every group. A group's score for a card is z(best weighted line similarity) + z(similarity vote of the 25 nearest member lines /
group size ** 0.25), the best over the card's lines; the card is removed from its own profile (leave-one-card-out). Source weights: precise leaf / replacement block / hand-group rule / batch-accepted placement 1.0, tentative / loose /
sibling 0.6, community-tag group 0.5, a single hand placement 1.5. The raw score is turned into a 0-1 confidence by isotonic calibration on 6,000 precisely placed cards (seed 20261111): the share of times the group was one of the
card's real groups at that raw score. That share counts only the card's real leaves, so it understates the truth for a card with several valid homes.
Keyword cards whose text is only reminder text are compared with the reminder kept, and keyword blocks named after the card's keywords are added (source kw). The 346 cards with no text get nothing: they sit in the "No abilities" block.
Merge (queue cards, the 5,593 u/t/a/m cards): the existing engine's rows (build/manual_suggestions.json) and the text rows, by group id. A group both found keeps the existing score (text adds the label and a reason, never score), a group only text found takes
the calibrated confidence; ranked by score, then number of sources; top 5 kept (7 stored). On three held-out samples (6,000 cards each) a +0.10 bonus for text agreeing cost top-1 (95.4 to 88.3 on cards the current engine handles), so there is none.
Text-only (and kw-only) rows are labelled low confidence on the page and are never pre-ticked in the batch view.

ENGINE_V2 (suggestions only; no leaf, threshold or figure changes; the first row at or above 0.90 of every card is unchanged, so what is ticked is unchanged):
  C1 keyword mapping: a keyword block is also offered through the keyword's variants (Hexproof from -> Hexproof), the "X: other combinations" block, the pair block of two keywords the card has, and the landwalk block for the land of
     the card's own keyword line (Snow swampwalk -> Swampwalk; the generic "Landwalk: other land types" row goes when the land is known). A keyword counts only if it opens a line of the card's text (not when an effect merely names it).
  C2 evergreen keyword rows (flying, haste, deathtouch, menace, ...) score 0.30 instead of 0.60; other keyword rows stay at 0.60; mapped rows score 0.25-0.35, so they never outrank a row with real evidence.
  C3 a hand-group rule row that would not be shown (its group is not among the first 5 clusters of near-duplicates) takes the fifth place.
  C4 (the page, reports/manualedit.js clusterRows): groups whose names are near-duplicates (token overlap >= 0.7) share one row that shows its best 2 groups and "+N similar"; meta.json carries engine_v2 for the page.

Outputs (build/text_sug/): meta.json, queue.json (merged rows with their reasons, same row shape as manual_suggestions.json), c/<xx>.json (rows for every other card, compact, by the first two characters of the oracle id),
l/<n>.json (the member lines those rows quote).
"""
import collections
import io
import json
import math
import os
import random
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as M

TEXT_SUGGESTIONS = True
ENGINE_V2 = True        # keyword mapping and demotion, near-duplicate clusters and a slot for a rule row (see below). Off: the files are byte-identical to the build before ENGINE_V2
HERE = M.HERE
BUILD = os.path.join(HERE, "build")
OUTDIR = os.environ.get("TEXT_SUG_OUT") or os.path.join(BUILD, "text_sug")          # the env override is for the tests only
OUT_MD = os.path.join(HERE, "reports", "text-suggestions.md")
if os.environ.get("TEXT_SUG_OUT"):
    OUT_MD = os.path.join(os.environ["TEXT_SUG_OUT"], "text-suggestions.md")
TOP, STORE = 5, 7
K, CAL_N, CAL_SEED = 25, 6000, 20261111
KW_SCORE = 0.60
MIN_GROUP = 5
REMINDER_CAP = 0.25


def bucket(nt):
    return 0 if nt <= 3 else 1 if nt <= 6 else 2
STOP = set("the a an of to and or you your that this it is in on for with as at if then from by be its their they them his her any each other another".split()) - {"each", "other", "another", "any"}
SRC_W = {"leaf": 1.0, "rp": 1.0, "hand": 1.0, "batch": 1.0, "tent": 0.6, "loose": 0.6, "sib": 0.6, "tag": 0.5, "single": 1.5}
LABEL = ("Text suggestion, not a placement: found by comparing the card's lines with the rules lines of each group's members. Low confidence when text is the only source; never pre-ticked.")


def jl(n):
    with io.open(os.path.join(BUILD, n), encoding="utf-8") as fh:
        return json.load(fh)


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


# ------------------------------------------------------------------ text handling
def name_variants(name):
    v = {name.lower(), name.split(",")[0].lower(), name.split(" // ")[0].lower()}
    return sorted((x for x in v if len(x) >= 3), key=len, reverse=True)


def norm(text, name="", keep_reminder=False):
    s = (text or "").replace("’", "'").replace("−", "-")
    if not keep_reminder:
        s = re.sub(r"\([^)]*\)", " ", s)
    s = s.lower()
    for v in name_variants(name):
        s = s.replace(v, " ~ ")
    s = re.sub(r"\{([^}]*)\}", lambda m: " m" + re.sub(r"[^a-z0-9]", "", m.group(1).lower()) + " ", s)
    return re.sub(r"\d+", "n", s)


def tokens(s):
    return [w for w in re.findall(r"[a-z~]+", s) if w not in STOP]


def analyze(s):
    t = tokens(s)
    return t + [a + "_" + b for a, b in zip(t, t[1:])]


def split_lines(text, name="", keep_reminder=False, min_tokens=2):
    """the query lines of a card: oracle-text lines, long lines cut at sentence ends, an ability-word or chapter prefix kept off."""
    out = []
    for ln in (text or "").split("\n"):
        ln = re.sub(r"^\s*(?:[IVX]+(?:,\s*[IVX]+)*|\[[^\]]*\]|[•\-])\s*(?:—|-|:)?\s*", "", ln.strip())
        ln = re.sub(r"^[A-Z][A-Za-z' ]{2,30} — ", "", ln)
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"(\[{])", ln) if len(ln) > 90 else [ln]
        for p in parts:
            p = p.strip()
            if len(tokens(norm(p, name, keep_reminder))) >= min_tokens:
                out.append(p)
    return out


def card_lines(c):
    """(lines, kind): the usable lines, or, when reminder text was all there is, the lines with reminder kept (kind 'reminder')"""
    ls = split_lines(c["t"], c["n"])
    if ls:
        return ls, "text"
    ls = split_lines(c["t"], c["n"], True, 1)
    return ls, "reminder"


# ------------------------------------------------------------------ tf-idf (numpy / scipy only)
class Tfidf:
    def __init__(self, docs, min_df=2):
        import numpy as np
        df = collections.Counter()
        toks = [analyze(d) for d in docs]
        for t in toks:
            df.update(set(t))
        self.vocab = {t: i for i, t in enumerate(sorted(t for t, c in df.items() if c >= min_df))}
        n = float(len(docs))
        self.idf = np.array([math.log((1 + n) / (1 + df[t])) + 1 for t in sorted(self.vocab, key=self.vocab.get)], dtype=np.float32)

    def transform(self, docs):
        import numpy as np
        import scipy.sparse as sp
        ind, ptr, val = [], [0], []
        for d in docs:
            cnt = collections.Counter(self.vocab[t] for t in analyze(d) if t in self.vocab)
            row = sorted(cnt.items())
            v = np.array([(1 + math.log(c)) * self.idf[i] for i, c in row], dtype=np.float32)
            nrm = float(np.sqrt((v * v).sum()))
            if nrm > 0:
                v = v / nrm
            ind += [i for i, c in row]
            val += list(v)
            ptr.append(len(ind))
        return sp.csr_matrix((np.array(val, dtype=np.float32), np.array(ind, dtype=np.int32), np.array(ptr)), shape=(len(docs), len(self.vocab)), dtype=np.float32)


# ------------------------------------------------------------------ the profiles
class Profiles:
    def __init__(self, cards, idx, G, query_cards):
        import numpy as np
        self.np = np
        lines = []                                                    # (gid, oid, text, weight, kind)

        def add(gid, o, t, w):
            if gid in G and G[gid][4] and G[gid][1] >= MIN_GROUP and t and t.strip():
                lines.append((gid, o, t.strip(), w))
        mem, tax = jl("ability_taxonomy_members.json")["leaves"], jl("ability_taxonomy.json")
        for lid in sorted(tax["leaves"]):
            have = set()
            for o, i in mem.get(lid, []):
                try:
                    t = cards[o]["ab"][i][0]
                except Exception:
                    t = ""
                if t and t.strip():
                    add("leaf:" + lid, o, t, SRC_W["leaf"])
                    have.add(o)
            for o, i in mem.get(lid, []):                              # members with no rules line: the card's lines that are not another member line of the same card
                if o in have:
                    continue
                own = {norm(a[0], cards[o]["n"]) for a in cards[o]["ab"] if a[0]}
                for ln in split_lines(cards[o]["t"], cards[o]["n"]):
                    if norm(ln, cards[o]["n"]) not in own:
                        add("leaf:" + lid, o, ln, SRC_W["leaf"])
        tent, loose = jl("tentative_placements.json"), jl("loose_groups.json")
        for gid, g in sorted(tent["groups"].items()):
            for r in g["m"]:
                add("tent:" + gid, r[0], r[1], SRC_W["tent"])
        for gid, g in sorted(loose["groups"].items()):
            if gid in tent["groups"] or g["kind"] != "group":
                continue
            for r in g["m"]:
                add("loose:" + gid, r[0], r[1], SRC_W["loose"])
        for gid, g in sorted(jl("tag_placements.json")["groups"].items()):
            for o in g["m"]:
                for ln in split_lines(cards[o]["t"], cards[o]["n"]):
                    add("tag:" + gid, o, ln, SRC_W["tag"])
        for lid, l in sorted(tax["blocks"]["replacement"]["leaves"].items()):
            for o in l["cards"]:
                for ln in split_lines(cards[o]["t"], cards[o]["n"]):
                    add("rp:" + lid, o, ln, SRC_W["rp"])
        hp = os.path.join(BUILD, "hand_group_hits.json")
        if os.path.exists(hp):
            for slug, g in sorted(jl("hand_group_hits.json")["groups"].items()):
                if g.get("retired"):
                    continue
                for o, hs in sorted(g["hits"].items()):
                    for rid, sent in hs:
                        add("hand:" + slug, o, sent, SRC_W["hand"])
        sp_ = os.path.join(BUILD, "sibling_placements.json")
        if os.path.exists(sp_):
            for lid, g in sorted(jl("sibling_placements.json")["groups"].items()):
                for r in g["m"]:
                    add("leaf:" + lid, r[0], r[1], SRC_W["sib"])
        self.n_hand = 0
        doc = M.load_doc() if os.path.exists(M.CORR) else None
        if doc:
            for oid, e in sorted(doc["edits"].items()):
                if oid not in cards:
                    continue
                for gid, g in sorted(e["groups"].items()):
                    if g["action"] != "add":
                        continue
                    w = SRC_W["batch"] if g.get("batch") else SRC_W["single"]
                    self.n_hand += 1
                    for ln in split_lines(cards[oid]["t"], cards[oid]["n"]):
                        add(gid, oid, ln, w)
        lines.sort(key=lambda x: x[0])                                 # the sort is stable: a group's lines stay in the order they were added
        self.lines = lines
        gids = [l[0] for l in lines]
        self.uniq = sorted(set(gids))
        gi = {g: i for i, g in enumerate(self.uniq)}
        self.gi = gi
        self.col_g = np.array([gi[g] for g in gids])
        self.starts = np.array([i for i in range(len(lines)) if i == 0 or gids[i] != gids[i - 1]])
        self.w = np.array([l[3] for l in lines], dtype=np.float32)
        cols = collections.defaultdict(list)
        for j, l in enumerate(lines):
            cols[l[1]].append(j)
        self.cols_of = {o: np.array(v) for o, v in cols.items()}
        mn = [norm(l[2], cards[l[1]]["n"]) for l in lines]
        qn = []
        for o in query_cards:
            ls, kind = card_lines(cards[o])
            qn += [norm(ln, cards[o]["n"], kind == "reminder") for ln in ls]
        self.vec = Tfidf(mn + qn)
        self.MT = self.vec.transform(mn).T.tocsc()
        self.size = np.array([max(G[g][1], 1) for g in self.uniq], dtype=np.float32)
        self.offered = np.array([bool(G[g][4]) for g in self.uniq])
        self.cards = cards

    def score(self, queries, owners, exclude):
        """queries: normalised query lines; owners: oid per line; exclude: {oid: set(gid)} groups never offered for that card.
        -> per line the top STORE groups [(group index, score, member column, similarity)]"""
        np = self.np
        Q = self.vec.transform(queries).tocsr()
        res = []
        z = lambda x: (x - x.mean()) / (x.std() + 1e-9)
        n_g = len(self.uniq)
        for a in range(0, Q.shape[0], 256):
            sim = (Q[a:a + 256] @ self.MT).toarray() * self.w[None, :]
            for r in range(sim.shape[0]):
                c = self.cols_of.get(owners[a + r])
                if c is not None:
                    sim[r, c] = -1
            mx = np.maximum.reduceat(sim, self.starts, axis=1)
            tp = np.argpartition(sim, -K, axis=1)[:, -K:]
            ts = np.take_along_axis(sim, tp, axis=1)
            for r in range(sim.shape[0]):
                v = np.zeros(n_g, dtype=np.float32)
                np.add.at(v, self.col_g[tp[r]], np.maximum(ts[r], 0) ** 2)
                sc = z(mx[r]) + z(v / (self.size ** 0.25))
                sc = np.where(self.offered, sc, -1e9)
                for g in exclude.get(owners[a + r], ()):
                    j = self.gi.get(g)
                    if j is not None:
                        sc[j] = -1e9
                top = np.lexsort((np.arange(n_g), -sc))[:STORE]
                row = []
                for g in top:
                    if sc[g] <= -1e8:
                        continue
                    s0 = self.starts[g]
                    s1 = self.starts[g + 1] if g + 1 < len(self.starts) else len(self.lines)
                    j = int(s0 + np.argmax(sim[r, s0:s1]))
                    row.append((int(g), float(sc[g]), j, float(sim[r, j])))
                res.append(row)
        return res


EVERGREEN = {"deathtouch", "defender", "doublestrike", "firststrike", "flash", "flying", "haste", "hexproof", "indestructible", "lifelink", "menace", "reach", "trample", "vigilance"}
KW_VARIANT = {"HexproofFrom": "Hexproof", "TrampleOverPlaneswalkers": "Trample", "Megamorph": "Morph"}
KW_SCORES = {"evergreen": 0.30, "variant": 0.30, "pair": 0.32, "landwalk": 0.35, "other": 0.25}
_NRM = lambda x: "".join(ch for ch in x.lower() if ch.isalnum())
_LAND = {"island": "kw:Landwalk|Island", "swamp": "kw:Landwalk|Swamp", "forest": "kw:Landwalk|Forest", "mountain": "kw:Landwalk|Mountain"}


def kw_blocks(G):
    ok = lambda g, v: v[3] == "kw" and v[4]
    exact = {_NRM(g[3:].replace("+", "")): g for g, v in G.items() if ok(g, v) and not g.startswith(("kw:other:", "kw:Landwalk|", "kw:rare"))}
    other = {g[9:]: g for g, v in G.items() if ok(g, v) and g.startswith("kw:other:")}
    pairs = {tuple(sorted(g[3:].split("+"))): g for g, v in G.items() if ok(g, v) and "+" in g and not g.startswith("kw:other")}
    return exact, other, pairs


def keyword_line(text, k, known):
    """is the keyword on a keyword line of the card's text: a line that opens with it, or a comma list that opens with a keyword? (Odric names flying and first strike inside an effect: not a keyword line)"""
    n = _NRM(k)
    for ln in (text or "").split("\n"):
        parts = [_NRM(p) for p in re.split(r"[,;]", re.sub(r"\(.*?\)", "", ln))]
        if parts and (_NRM(ln).startswith(n) or (parts[0] in known and n in parts)):
            return True
    return False


def kw_candidates_v2(text, names, held, G, blocks, known):
    """-> {group id: (score, reason)} for one card"""
    exact, other, pairs = blocks
    out = {}
    ks = set(names)
    for k in sorted(ks):
        n = _NRM(k)
        if k == "Landwalk" or not keyword_line(text, k, known):
            continue
        if n in exact:
            g = exact[n]
            ev = all(_NRM(x) in EVERGREEN for x in g[3:].split("+"))
            out[g] = (KW_SCORES["evergreen"] if ev else 0.60, "the card carries the keyword %s (keyword block, exact name)" % k)
        elif k in KW_VARIANT and _NRM(KW_VARIANT[k]) in exact:
            out[exact[_NRM(KW_VARIANT[k])]] = (KW_SCORES["variant"], "the card carries %s, a variant of this block's keyword" % k)
        elif k in other:
            out[other[k]] = (KW_SCORES["other"], "the card carries %s; this block holds it together with other keywords" % k)
    if len(ks) >= 2:
        for pr, g in pairs.items():
            if set(pr) <= ks and all(keyword_line(text, x, known) for x in pr):
                out[g] = (max(out.get(g, (0,))[0], KW_SCORES["pair"]), "the card carries %s and %s, which have a block together" % pr)
    land = None
    for ln in (text or "").split("\n"):
        for m in re.finditer(r"^(?:snow )?(island|swamp|forest|mountain|plains)walk\b|,\s*(island|swamp|forest|mountain|plains)walk\b", ln.strip().lower()):
            w = m.group(1) or m.group(2)
            g = _LAND.get(w, "kw:Landwalk")
            if g in G:
                out[g] = (KW_SCORES["landwalk"], "its keyword line gives it %swalk" % w)
                land = g
    if land and land != "kw:Landwalk":
        out.pop("kw:Landwalk", None)                                     # the generic "other land types" block was the wrong home
    return {g: v for g, v in out.items() if g not in held}


_STOPN = set("a an the of to or and it its this that his her their from in on for with you your".split())


def name_key(name):
    n = re.sub(r"\(.*?\)", "", name.lower())
    n = re.sub(r"—.*$", "", n)
    n = re.sub(r"[^a-z0-9/ +\-]", " ", n)
    return frozenset(w for w in n.split() if w not in _STOPN)


def near(a, b, th=0.7):
    return bool(a and b) and len(a & b) / float(len(a | b)) >= th


def cluster_rows(rows, G):
    """first-fit clusters of near-duplicate group names, in row order -> list of lists of rows (reports/manualedit.js clusterRows does the same)"""
    cl = []
    for r in rows:
        k = name_key(G[r[0]][0])
        for c in cl:
            if near(k, name_key(G[c[0][0]][0])):
                c.append(r)
                break
        else:
            cl.append([r])
    return cl


def slot_rule_row(rows, G, shown=5):
    """C3: a rule row whose group is not in the first `shown` clusters takes the last of them"""
    cl = cluster_rows(rows, G)
    missing = [r for c in cl[shown:] for r in c if "rule" in r[2].split("+")]
    if not missing:
        return rows
    r = max(missing, key=lambda x: x[1])
    rest = [x for x in rows if x is not r]
    cl = cluster_rows(rest, G)
    at = rest.index(cl[shown - 1][0]) if len(cl) >= shown else len(rest)     # just before the head of the fifth cluster: the order of every other row is kept
    return rest[:at] + [r] + rest[at:]



def pav(x, y):
    """isotonic (non-decreasing) fit of y on x: -> (breakpoints, values)"""
    import numpy as np
    o = np.argsort(x, kind="stable")
    xs, ys = np.asarray(x)[o], np.asarray(y, dtype=float)[o]
    blocks = [[ys[i], 1.0, xs[i], xs[i]] for i in range(len(ys))]       # value, weight, x first, x last
    out = []
    for b in blocks:
        out.append(b)
        while len(out) > 1 and out[-2][0] >= out[-1][0]:
            b2 = out.pop()
            b1 = out.pop()
            w = b1[1] + b2[1]
            out.append([(b1[0] * b1[1] + b2[0] * b2[1]) / w, w, b1[2], b2[3]])
    px, py = [], []
    for v, w, x0, x1 in out:
        px += [x0, x1]
        py += [v, v]
    return px, py


def main():
    import numpy as np
    import build_manual_layer as BML
    if not TEXT_SUGGESTIONS or not BML.MANUAL_PLACEMENTS:
        if os.path.isdir(OUTDIR) and not os.environ.get("TEXT_SUG_OUT"):
            shutil.rmtree(OUTDIR)
        if os.path.exists(OUT_MD) and not os.environ.get("TEXT_SUG_OUT"):
            os.remove(OUT_MD)
        print("TEXT_SUGGESTIONS is off: nothing written")
        return
    t0 = time.time()
    ix = jl("manual_index.json")
    G, C = ix["groups"], ix["cards"]
    cards = jl("ability_taxonomy_cards.json")["cards"]
    scope = sorted(o for o, c in C.items() if c[1] != "o" and o in cards)
    query_cards = [o for o in scope if (cards[o]["t"] or "").strip()]
    P = Profiles(cards, ix, G, query_cards)
    print("profiles: %d member lines, %d groups, vocabulary %d (%.0fs)" % (len(P.lines), len(P.uniq), len(P.vec.vocab), time.time() - t0), file=sys.stderr)

    # ---- calibration: precisely placed cards, the card removed from its own profile; a hit is a group that is one of the card's real leaves
    pop = []
    for o in scope:
        if C[o][1] in ("p", "b"):
            real = {"leaf:" + a[1] for a in cards[o]["ab"] if a[2] in ("p", "b") and a[1]}
            if real and (cards[o]["t"] or "").strip():
                pop.append((o, real))
    cal = random.Random(CAL_SEED).sample(pop, min(CAL_N, len(pop)))
    qs, ow = [], []
    for o, real in cal:
        for ln in split_lines(cards[o]["t"], cards[o]["n"]):
            qs.append(norm(ln, cards[o]["n"])); ow.append(o)
    rows = P.score(qs, ow, {})
    per = collections.defaultdict(dict)
    for q, o, r in zip(qs, ow, rows):
        nt = len(tokens(q))
        for g, sc, j, s in r:
            if sc > per[o].get(g, (-1e9, 0))[0]:
                per[o][g] = (sc, nt)
    xs, ys, bk, hit_at = [], [], [], []
    for o, real in cal:
        top = sorted(per[o].items(), key=lambda kv: (-kv[1][0], kv[0]))[:STORE]
        hit_at.append([any(P.uniq[g] in real for g, _ in top[:k]) for k in (1, 3, 5)])
        for g, (sc, nt) in top:
            xs.append(sc); ys.append(1.0 if P.uniq[g] in real else 0.0); bk.append(bucket(nt))
    held = np.array(hit_at).mean(axis=0) if hit_at else np.zeros(3)
    curves = {"all": pav(xs, ys)}
    for b in (0, 1, 2):
        sel = [i for i in range(len(xs)) if bk[i] == b]
        if len(sel) >= 1500:                                        # a bucket with too little data uses the overall curve
            curves[b] = pav([xs[i] for i in sel], [ys[i] for i in sel])

    def conf(raw, nt, kind):
        px, py = curves.get(bucket(nt), curves["all"])
        c = float(min(0.99, max(0.02, np.interp(raw, px, py))))
        return min(c, REMINDER_CAP) if kind == "reminder" else c                     # reminder-only cards have no calibration data: capped low
    px, py = curves["all"]
    print("calibration: %d cards, held-out top-1/3/5 %.1f / %.1f / %.1f (%.0fs)" % (len(cal), 100 * held[0], 100 * held[1], 100 * held[2], time.time() - t0), file=sys.stderr)

    # ---- every card in scope
    keyword = collections.defaultdict(list)
    kfp = os.path.join(BUILD, "keyword_facet.json")
    if os.path.exists(kfp):
        for k, v in jl("keyword_facet.json")["keywords"].items():
            for o in v["c"]:
                keyword[o].append(k)
    nrm = lambda x: "".join(ch for ch in x.lower() if ch.isalnum())
    kwg = {nrm(g[3:].replace("+", "")): g for g, v in G.items() if v[3] == "kw" and v[4]}
    blocks = kw_blocks(G)
    known = {nrm(k) for k in jl("keyword_facet.json")["keywords"]} if os.path.exists(kfp) else set()
    held_of = {o: {x[0] for x in C[o][3] if x[1] in M.PRECISE} for o in scope}
    qs, ow, qraw = [], [], []
    kind_of = {}
    for o in query_cards:
        ls, kind = card_lines(cards[o])
        kind_of[o] = kind
        for ln in ls:
            qs.append(norm(ln, cards[o]["n"], kind == "reminder")); ow.append(o); qraw.append(ln)
    rows = P.score(qs, ow, held_of)
    print("scored %d lines of %d cards (%.0fs)" % (len(qs), len(query_cards), time.time() - t0), file=sys.stderr)
    best = collections.defaultdict(dict)                                # oid -> gid -> (score, line index, member column, similarity)
    ntok = [len(tokens(q)) for q in qs]
    for i, (o, r) in enumerate(zip(ow, rows)):
        for g, sc, j, s in r:
            gid = P.uniq[g]
            if gid not in best[o] or sc > best[o][gid][0]:
                best[o][gid] = (sc, i, j, s)
    text_rows = {}
    for o in scope:
        cand = {}
        for gid, (sc, i, j, s) in best.get(o, {}).items():
            cand[gid] = {"raw": sc, "conf": conf(sc, ntok[i], kind_of[o]), "line": qraw[i], "m": j, "src": "text"}
        if ENGINE_V2:
            for g, (sc_, why_) in kw_candidates_v2(cards[o]["t"], keyword.get(o, ()), held_of[o], G, blocks, known).items():
                if g not in cand:
                    cand[g] = {"raw": -1e6, "conf": sc_, "line": None, "m": None, "src": "kw", "k": "", "why": why_}
        else:
            for k in sorted(keyword.get(o, ())):
                g = kwg.get(nrm(k))
                if g and g not in held_of[o] and g not in cand:
                    cand[g] = {"raw": -1e6, "conf": KW_SCORE, "line": None, "m": None, "src": "kw", "k": k}
        lst = sorted(cand.items(), key=lambda kv: (-kv[1]["conf"], -kv[1]["raw"], kv[0]))[:STORE]
        text_rows[o] = lst

    # ---- member line table: the lines the stored rows quote, grouped by group so that one card's rows touch few shards
    queue_ids = [o for o in scope if C[o][1] in ("u", "t", "a", "m")]
    qset = set(queue_ids)
    old = {}
    p_old = os.path.join(BUILD, "manual_suggestions.json")
    if os.path.exists(p_old):
        old = jl("manual_suggestions.json")["cards"]
    quoted = {e["m"] for o in scope for gid, e in text_rows[o] if e["m"] is not None}
    lid_of = {}
    table = []
    for j in sorted(quoted, key=lambda j: (P.lines[j][0], P.lines[j][2], cards[P.lines[j][1]]["n"], j)):
        lid_of[j] = len(table)
        table.append([" ".join(P.lines[j][2].split())[:110], cards[P.lines[j][1]]["n"]])
    glist = sorted({gid for o in scope for gid, e in text_rows[o]})
    gix = {g: i for i, g in enumerate(glist)}

    def ref(o, e):
        return [cards[o]["t"].find(e["line"]), len(e["line"]), lid_of[e["m"]]]

    # ---- merge for the queue cards: row = [group, score, sources, reason of the existing sources, (card line start, length, member line id)]
    queue, n_text_only_top = {}, 0
    rule_rows = collections.defaultdict(list)                              # hand-defined group rules (build/hand_group_hits.json): the existing engine keeps only its own top 5, so a 0.70 rule row can be cut before this merge
    if os.path.exists(os.path.join(BUILD, "hand_group_hits.json")):
        for slug, g in sorted(jl("hand_group_hits.json")["groups"].items()):
            if g.get("retired") or ("hand:" + slug) not in G or not G["hand:" + slug][4]:
                continue
            conf = {r["id"]: r["confidence"] for r in g["rules"]}
            for oid, hs in g["hits"].items():
                best = max(hs, key=lambda h: conf[h[0]])
                rule_rows[oid].append(("hand:" + slug, conf[best[0]], "your hand-defined group “%s” (rule %s) matches: “%s”" % (g["name"], best[0], best[1][:120])))
    for o in queue_ids:
        cand = {}
        for r in old.get(o, ()):
            cand[r[0]] = {"score": r[1], "src": r[2].split("+"), "why": r[3], "ref": None, "raw": -1e7}
        for gid, sc_, why_ in rule_rows.get(o, ()):
            c = cand.get(gid)
            if c is None:
                cand[gid] = {"score": sc_, "src": ["rule"], "why": why_, "ref": None, "raw": -1e7}
        for gid, e in text_rows[o]:
            why_kw = (e.get("why") or "the card carries the keyword %s (keyword block, exact name)" % e["k"]) if e["src"] == "kw" else ""
            c = cand.get(gid)
            if c is None:
                cand[gid] = {"score": e["conf"], "src": [e["src"]], "why": why_kw, "ref": ref(o, e) if e["m"] is not None else None, "raw": e["raw"]}
            else:
                # the existing engine's score is kept as it is: text that agrees changes the label and the reason, never the score, so the set of rows at or above 0.90 is the one the threshold was checked on
                # (a row found only by a hand-group rule has no such score: it takes the larger of the two)
                if set(c["src"]) <= {"rule"}:
                    c["score"] = max(c["score"], e["conf"])
                c["src"] = c["src"] + [e["src"]]
                c["why"] = (c["why"] + "; " + why_kw) if why_kw else c["why"]
                c["ref"] = ref(o, e) if e["m"] is not None else None
                c["raw"] = e["raw"]
        lst = sorted(cand.items(), key=lambda kv: (-round(kv[1]["score"], 3), -len(kv[1]["src"]), -kv[1]["raw"], kv[0]))[:STORE]
        queue[o] = [[gid, round(c["score"], 3), "+".join(sorted(set(c["src"]))), c["why"]] + (c["ref"] or []) for gid, c in lst]
        if ENGINE_V2:
            queue[o] = slot_rule_row(queue[o], G)
        if queue[o] and set(queue[o][0][2].split("+")) <= {"text", "kw"}:
            n_text_only_top += 1

    # ---- compact rows for every other card
    shards = collections.defaultdict(dict)
    for o in scope:
        if o in qset:
            continue
        r = []
        for gid, e in text_rows[o]:
            if e["src"] == "kw":
                r.append([gix[gid], int(round(e["conf"] * 1000)), -1, 0, 0, e["why"] if ENGINE_V2 else e["k"]])
            else:
                r.append([gix[gid], int(round(e["conf"] * 1000))] + ref(o, e))
        shards[o[:2]][o] = r
    # ---- write
    if os.path.isdir(OUTDIR):
        shutil.rmtree(OUTDIR)
    for k, v in shards.items():
        dump(os.path.join(OUTDIR, "c", k + ".json"), v)
    per_shard = 256
    for n in range(0, (len(table) + per_shard - 1) // per_shard):
        dump(os.path.join(OUTDIR, "l", "%d.json" % n), table[n * per_shard:(n + 1) * per_shard])
    dump(os.path.join(OUTDIR, "queue.json"), {"v": 1, "top": TOP, "label": LABEL, "cards": queue})
    cov = coverage(scope, C, cards, text_rows, queue, qset)
    meta = {"v": 1, "top": TOP, "store": STORE, "label": LABEL, "groups": glist, "line_shard": per_shard, "lines": len(table),
            "kw_score": KW_SCORE, "calibration": {"cards": len(cal), "seed": CAL_SEED, "top1": round(float(held[0]), 4), "top3": round(float(held[1]), 4), "top5": round(float(held[2]), 4),
                                                                                "curve": [[round(float(a), 2), round(float(b), 3)] for a, b in zip(px[::2][:: max(1, len(px[::2]) // 40)], py[::2][:: max(1, len(px[::2]) // 40)])]},
            "hand_members": P.n_hand, "coverage": cov}
    if ENGINE_V2:
        meta["engine_v2"] = {"cluster_threshold": 0.7, "inline": 2, "shown": 5, "keyword_scores": KW_SCORES}
    dump(os.path.join(OUTDIR, "meta.json"), meta)
    write_report(meta, P, queue, text_rows, n_text_only_top, scope, C, cards)
    tot = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(OUTDIR) for f in fs)
    print("text suggestions: %d cards, %d queue rows, %.1f MB in %d files, %.0fs" % (len(scope), len(queue), tot / 1048576.0, sum(len(fs) for _, _, fs in os.walk(OUTDIR)), time.time() - t0))
    print(json.dumps(cov, sort_keys=True))


def coverage(scope, C, cards, text_rows, queue, qset):
    out = collections.Counter()
    zero = collections.Counter()
    for o in scope:
        n = len(queue[o]) if o in qset else len(text_rows[o])
        has_text = bool((cards[o]["t"] or "").strip())
        out["cards"] += 1
        if n >= TOP:
            out["at_least_5"] += 1
        elif n > 0:
            out["1_to_4"] += 1
            zero["1-4 (state %s%s)" % (C[o][1], "" if has_text else ", no text")] += 1
        else:
            out["none"] += 1
            zero["none (state %s%s)" % (C[o][1], "" if has_text else ", no text")] += 1
    d = dict(out)
    d["not_5_by_cause"] = dict(zero)
    return d


def write_report(meta, P, queue, text_rows, n_top, scope, C, cards):
    cov = meta["coverage"]
    L = ["# Text suggestions (generated; do not edit)", "",
         "Built by `python src/build_text_suggestions.py` (flag TEXT_SUGGESTIONS). Suggestions only: nothing is placed from them, no figure changes, and text-only rows are never pre-ticked.", "",
         "- Profiles: %d member lines in %d groups; vocabulary %d terms. %d hand placements entered the profiles (a single hand placement weighs 1.5, a batch-accepted one 1.0)." % (len(P.lines), len(P.uniq), len(P.vec.vocab), meta["hand_members"]),
         "- Calibration: %d precisely placed cards (seed %d), the card left out of its own profile. Held-out, a real leaf of the card is in the text top 1 / 3 / 5 for %.1f%% / %.1f%% / %.1f%% of them." % (
             meta["calibration"]["cards"], meta["calibration"]["seed"], 100 * meta["calibration"]["top1"], 100 * meta["calibration"]["top3"], 100 * meta["calibration"]["top5"]),
         "- Coverage: %d cards in scope; %d have 5 or more suggestions, %d have 1 to 4, %d have none." % (cov["cards"], cov.get("at_least_5", 0), cov.get("1_to_4", 0), cov.get("none", 0)),
         "- Queue cards (not yet organized, tentative, annotation, tag) whose top row is text only: %d of %d." % (n_top, len(queue)), "",
         "## Cards with fewer than 5 suggestions, by cause", ""]
    for k, v in sorted(cov["not_5_by_cause"].items()):
        L.append("- %s: %d" % (k, v))
    with io.open(OUT_MD, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
