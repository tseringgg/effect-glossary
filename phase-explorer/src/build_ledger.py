#!/usr/bin/env python3
"""Coverage ledger: one row per oracle id in the card universe, one status each.

Reads   data/AtomicCards.json.gz              universe (in scope)
        data/scryfall-oracle-cards.jsonl.gz   out-of-scope objects (tokens,
                                              art series, emblems, ...)
        data/scryfall-default-cards.jsonl.gz  first-printing dates
        data/card-data.json                   the phase.rs snapshot (read-only;
                                              face-name key ownership only)
        build/index.json, build/meta.json     per-face quality flags
        build/clusters.json                   leaf membership
        build/chunks/*.json                   gap fragments, as evidence
        corrections/corrections.json          flag names, as evidence
Writes  build/ledger.json                     rows + checks + gap causes
        reports/coverage-ledger.md            the same, readable

UNIVERSE. MTGJSON AtomicCards (the collision diff's reference, and the input
format phase.rs's generator consumes) supplies every in-scope oracle id: all
33,834 ids in the snapshot are in it, while Scryfall's oracle export cannot
place 216 of them (Alchemy "A-" cards). The oracle ids Scryfall knows and
AtomicCards does not are exactly the object types that are not cards --
tokens, art series, emblems, front cards -- so they are added as explicit
`out_of_scope` rows with Scryfall's own layout and set type as the reason,
rather than being left out of the count.

STATUS. A snapshot card's faces each go through the clustering pass's own
filter chain (cluster_structural.py) in its order:

    quality != clean  -> vanilla | unparsed | partial
    unmodelled node   -> unmodelled_node
    correction flag   -> corrections_flagged
    no top-level feature -> no_extractable_effect
    otherwise         -> noise | clustered

A card with two faces can stop at different stages. The card takes the
FURTHEST stage any face reached (a double-faced card whose front is in a leaf
is placed, even if its back is partial); every face's own stage stays in the
row's evidence, and the number of such mixed cards is reported so the rule's
effect is visible rather than implied.

Everything is sorted and written with sorted keys: two runs give identical
bytes, and the build checks that.
"""
import collections
import gzip
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
BUILD = os.path.join(HERE, "build")
REPORTS = os.path.join(HERE, "reports")

STATUSES = ("clustered", "noise", "no_extractable_effect", "corrections_flagged",
            "unmodelled_node", "partial", "unparsed", "vanilla",
            "missing_from_export", "out_of_scope")
# Furthest stage first: the order a face moves through the clustering pass.
STAGE_ORDER = STATUSES[:8]

BUCKETS = ("abilities", "triggers", "static_abilities", "replacements")

# Cards upstream excludes on purpose (crates/engine/src/database/removed_cards.rs,
# phase-rs/phase). Checked so such a card would get its own reason; none of the
# seven is absent from the snapshot, so this currently matches nothing.
# Real cards, but not deck cards: played from their own decks. Carved out as a
# later, separate pass (like vanilla), so they don't dilute coverage numbers.
DEFERRED_LAYOUTS = ("planar", "scheme", "vanguard")

REMOVED_BY_UPSTREAM = {"invoke prejudice", "cleanse", "stone-throwing devils",
                       "pradesh gypsies", "jihad", "imprison", "crusade"}


def jsonl(path):
    for line in gzip.open(path, "rt", encoding="utf-8"):
        line = line.strip().rstrip(",")
        if line and line not in ("[", "]"):
            yield json.loads(line)


# ------------------------------------------------------------- gap evidence

def norm_fragment(text, name):
    """Group fragments that differ only in card name or numbers."""
    t = text or ""
    # Longest name first, in a fixed order: iterating the set directly let
    # "Raddic" replace before "Raddic, Tal Zealot" on some runs and not others
    # (set order is hash-randomised per process), so one fragment normalised
    # two ways and the build was not reproducible.
    for n in sorted({name, name.split(",")[0]} - {""}, key=lambda s: (-len(s), s)):
        t = t.replace(n, "~")
    t = re.sub(r"\d+", "N", t.lower())
    t = re.sub(r"\s+", " ", t).strip(" .,;:")
    return t


def generic_signature(node):
    """GenericEffect wraps granted statics; its identity is what it grants."""
    parts = []
    for s in node.get("static_abilities") or []:
        mode = s.get("mode")
        mode = mode if isinstance(mode, str) else (next(iter(mode)) if isinstance(mode, dict) and mode else "?")
        mods = sorted({m.get("type") if isinstance(m, dict) else str(m)
                       for m in (s.get("modifications") or [])} - {None})
        parts.append(mode + ("(" + ",".join(mods) + ")" if mods else ""))
    return "GenericEffect[" + "|".join(parts or ["?"]) + "]"


def gap_fragments(card, name):
    """Every gap and unmodelled node in a parsed face, as (kind, category, text)."""
    out = []

    def walk(n):
        if isinstance(n, dict):
            t = n.get("type")
            if t == "Unimplemented":
                out.append(("Unimplemented", "Unimplemented:" + str(n.get("name")),
                            norm_fragment(n.get("description"), name)))
            elif t == "GenericEffect":
                sig = generic_signature(n)
                out.append(("GenericEffect", sig, sig))
            elif t == "Unrecognized":
                out.append(("unmodelled", "Unrecognized condition",
                            norm_fragment(n.get("text"), name)))
            mode = n.get("mode")
            if isinstance(mode, dict) and "Unknown" in mode:
                out.append(("unmodelled", "Unknown trigger mode",
                            norm_fragment(mode.get("Unknown"), name)))
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    for b in BUCKETS:
        walk(card.get(b))
    return out


def _squash(s):
    return re.sub(r"[\s\-]+", "", s.lower())


def parsed_elsewhere(card):
    """Why an `unparsed` face's text is in fact parsed, or None.

    `unparsed` means "has text but nothing in the four ability buckets". Two
    other fields hold parsed text too, so a card can be fully modelled and
    still land there:

      * `keywords` -- a card whose whole text is "Flying" (Storm Crow);
      * `additional_cost` -- "As an additional cost to cast this spell, ...".

    Returns "keywords_only" when every line is one of the card's OWN parsed
    keywords, "parsed_outside_ability_buckets" when every line is a keyword or
    an additional cost the parse holds, else None. Judged per line against the
    card's own parse, never a keyword list of ours: reminder text is dropped,
    a keyword line must open with one of its keywords, and a plain comma list
    ("Flying, first strike") must open with one in every item. A keyword with
    a string payload counts by its payload too, since {"Landwalk": "Swamp"} is
    printed "Swampwalk". A keyword the parser DROPPED (Echo, Reinforce, Morph
    on some cards) is absent from `keywords`, so that line fails and the face
    correctly stays `text_without_structure`.
    """
    names = set()
    for k in card.get("keywords") or []:
        if isinstance(k, str):
            names.add(_squash(re.sub(r"([a-z])([A-Z])", r"\1 \2", k)))
        elif isinstance(k, dict) and k:
            key, val = next(iter(k.items()))
            names.add(_squash(re.sub(r"([a-z])([A-Z])", r"\1 \2", key)))
            if isinstance(val, str):
                names.add(_squash(val))
    lines = [re.sub(r"\([^)]*\)", "", ln).strip() for ln in (card.get("oracle_text") or "").split("\n")]
    lines = [ln for ln in lines if ln]
    if not lines:
        return None

    def opens(seg):
        s = _squash(seg)
        return any(s.startswith(n) for n in names)

    def keyword_line(ln):
        if not names or not opens(ln):
            return False
        costed = "—" in ln or "{" in ln
        return costed or all(opens(p) for p in re.split(r",\s*|;\s*", ln) if p.strip())

    kinds = set()
    for ln in lines:
        if keyword_line(ln):
            kinds.add("keyword")
        elif card.get("additional_cost") and ln.lower().startswith("as an additional cost"):
            kinds.add("additional_cost")
        else:
            return None
    return "keywords_only" if kinds == {"keyword"} else "parsed_outside_ability_buckets"


# ------------------------------------------------------------------- build

def main():
    meta = json.load(io.open(os.path.join(BUILD, "meta.json"), encoding="utf-8"))
    snapshot_date = meta["snapshot_last_modified"][:10]
    index = json.load(io.open(os.path.join(BUILD, "index.json"), encoding="utf-8"))
    clusters = json.load(io.open(os.path.join(BUILD, "clusters.json"), encoding="utf-8"))
    leaf_of = clusters["cards"]
    try:
        corr_names = {c["oracle_id"]: c.get("name") for c in json.load(io.open(
            os.path.join(HERE, "corrections", "corrections.json"), encoding="utf-8"))}
    except Exception:
        corr_names = {}

    # ---- universe
    sys.stderr.write("reading AtomicCards" + chr(10))
    atomic = json.load(gzip.open(os.path.join(DATA, "AtomicCards.json.gz"), "rt", encoding="utf-8"))
    at_meta = atomic.get("meta", {})
    at_card = {}
    for full, faces in atomic["data"].items():
        for f in faces:
            oid = (f.get("identifiers") or {}).get("scryfallOracleId")
            if not oid:
                continue
            c = at_card.setdefault(oid, {"name": full, "faces": [], "layout": f.get("layout"),
                                         "type": f.get("type")})
            c["faces"].append(f.get("faceName") or f.get("name"))
            c.setdefault("layouts", set()).add(f.get("layout"))

    sys.stderr.write("reading Scryfall oracle + default exports" + chr(10))
    sf_card = {}
    for c in jsonl(os.path.join(DATA, "scryfall-oracle-cards.jsonl.gz")):
        if c.get("oracle_id"):
            sf_card[c["oracle_id"]] = {"name": c.get("name"), "layout": c.get("layout"),
                                       "set_type": c.get("set_type"), "set": c.get("set")}
    first = {}
    for c in jsonl(os.path.join(DATA, "scryfall-default-cards.jsonl.gz")):
        oid = c.get("oracle_id") or ((c.get("card_faces") or [{}])[0].get("oracle_id"))
        d = c.get("released_at")
        if oid and d and (oid not in first or (d, c.get("set")) < first[oid]):
            first[oid] = (d, c.get("set"))

    universe = set(at_card) | set(sf_card)

    # ---- snapshot: faces from the index, key ownership from the raw export
    faces_of = collections.defaultdict(list)
    for r in index["rows"]:
        faces_of[r["id"].split("/")[0]].append(r)
    sys.stderr.write("reading snapshot key ownership" + chr(10))
    raw = json.load(io.open(os.path.join(DATA, "card-data.json"), encoding="utf-8"))
    key_owner = {}
    for k, e in raw.items():
        e = e[0] if isinstance(e, list) else e
        key_owner[k] = {"oracle_id": e.get("scryfall_oracle_id"), "name": e.get("name"),
                        "layout": e.get("layout")}
    del raw

    # ---- chunk evidence, only for faces that stopped on a gap
    need = collections.defaultdict(list)
    for oid, fs in faces_of.items():
        for r in fs:
            if r["q"] in ("partial", "unparsed") or r["sg"]:
                need[r["ch"]].append(r["id"])
    frags = {}
    warn = {}
    kw_only = {}   # face id -> how its text is parsed outside the ability buckets
    for ch in sorted(need):
        blob = json.load(io.open(os.path.join(BUILD, "chunks", str(ch) + ".json"), encoding="utf-8"))
        for fid in need[ch]:
            card = blob.get(fid) or {}
            frags[fid] = gap_fragments(card, card.get("name") or "")
            warn[fid] = card.get("parse_warnings") or []
            elsewhere = parsed_elsewhere(card)
            if elsewhere:
                kw_only[fid] = elsewhere

    def face_stage(r):
        if r["q"] == "vanilla":
            return "vanilla"
        if r["q"] == "unparsed":
            return "unparsed"
        if r["q"] == "partial":
            return "partial"
        if r["sg"]:
            return "unmodelled_node"
        if r.get("corr"):
            return "corrections_flagged"
        if r["id"] not in leaf_of:
            return "no_extractable_effect"
        return "noise" if leaf_of[r["id"]] < 0 else "clustered"

    rows = {}
    faces_lost = {}
    face_tally = collections.Counter()
    mixed = collections.Counter()
    for oid in sorted(universe):
        if oid in faces_of:
            fs = sorted(faces_of[oid], key=lambda r: r["id"])
            stages = [(face_stage(r), r) for r in fs]
            for s, _ in stages:
                face_tally[s] += 1
            best = min(stages, key=lambda x: STAGE_ORDER.index(x[0]))
            status, r = best
            if len({s for s, _ in stages}) > 1:
                mixed["/".join(sorted({s for s, _ in stages}))] += 1
            ev = {"faces": [{"id": x["id"], "name": x["name"], "stage": s, "quality": x["q"],
                             "gap_nodes": x["gaps"], "unmodelled": x["sg"],
                             "corrections": x.get("corr", 0),
                             "leaf": leaf_of.get(x["id"])} for s, x in stages]}
            if status == "clustered":
                reason = "leaf"
                ev["leaf"] = leaf_of[r["id"]]
            elif status == "noise":
                reason = "hdbscan_noise"
            elif status == "no_extractable_effect":
                reason = "no_top_level_effect_or_static"
            elif status == "corrections_flagged":
                reason = "hand_confirmed_defect"
                ev["correction"] = corr_names.get(oid)
            elif status == "unmodelled_node":
                kinds = sorted({c for f in fs for _, c, _ in
                                [x for x in frags.get(f["id"], []) if x[0] == "unmodelled"]})
                reason = "+".join(k.replace(" ", "_").lower() for k in kinds) or "unmodelled_node"
            elif status == "partial":
                kinds = sorted({k for f in fs for k, _, _ in frags.get(f["id"], []) if k != "unmodelled"})
                reason = "+".join(kinds) or "gap_node"
            elif status == "unparsed":
                # Keyword-only text is parsed -- into `keywords`, not the four
                # ability buckets `unparsed` is judged on. Same status (the
                # pipeline's), different reason, so the two never get confused.
                got = {kw_only.get(f["id"]) for f in fs if face_stage(f) == "unparsed"}
                reason = ("text_without_structure" if None in got
                          else "parsed_outside_ability_buckets" if "parsed_outside_ability_buckets" in got
                          else "keywords_only")
            else:
                reason = "no_oracle_text"
            if status in ("partial", "unparsed", "unmodelled_node"):
                ev["fragments"] = sorted({(k, c, t) for f in fs for k, c, t in frags.get(f["id"], [])})[:24]
                ev["parse_warnings"] = sorted({w if isinstance(w, str) else json.dumps(w, sort_keys=True)
                                               for f in fs for w in warn.get(f["id"], [])})[:8]
            name = fs[0]["name"]
            # Present, but a face lost its key to another card (e.g. the
            # prepare back face "Demonic Tutor" of Emeritus of Woe). Recorded,
            # not recovered: adding a face would change an existing card.
            have = {x["key"] for x in fs}
            lost = [{"face": f, "key": f.lower(), "winner_oracle_id": key_owner[f.lower()]["oracle_id"],
                     "winner_name": key_owner[f.lower()]["name"]}
                    for f in at_card.get(oid, {}).get("faces", [])
                    if f.lower() not in have and f.lower() in key_owner
                    and key_owner[f.lower()]["oracle_id"] != oid]
            if lost:
                ev["faces_lost_to_collision"] = lost
                faces_lost[oid] = len(lost)
        elif oid in at_card:
            status = "missing_from_export"
            c = at_card[oid]
            name = c["name"]
            fp = first.get(oid)
            keys = sorted({x.lower() for x in c["faces"]} | {name.lower()})
            won = [{"key": k, "winner_oracle_id": key_owner[k]["oracle_id"],
                    "winner_name": key_owner[k]["name"], "winner_layout": key_owner[k]["layout"]}
                   for k in keys if k in key_owner and key_owner[k]["oracle_id"] != oid]
            ev = {"first_printing": {"date": fp[0], "set": fp[1]} if fp else None,
                  "atomic_layout": c["layout"], "type": c["type"], "keys_checked": keys}
            if won:
                ev["collisions"] = won
            if fp and fp[0] > snapshot_date:
                reason = "released_after_snapshot"
            elif name.lower() in REMOVED_BY_UPSTREAM:
                reason = "removed_by_upstream_policy"
            elif won:
                reason = "collision_dropped"
            else:
                reason = "absent_unexplained"
        else:
            status = "out_of_scope"
            c = sf_card[oid]
            name = c["name"]
            reason = "not_a_card:" + (c["layout"] or "?") + (
                "" if c["layout"] in ("token", "art_series", "emblem", "double_faced_token", "front_card")
                else "/" + (c["set_type"] or "?"))
            ev = {"scryfall_layout": c["layout"], "scryfall_set_type": c["set_type"],
                  "scryfall_set": c["set"], "not_in": "MTGJSON AtomicCards"}
        deferred = sorted(set(DEFERRED_LAYOUTS) & at_card.get(oid, {}).get("layouts", set()))
        if deferred:
            # Pipeline stage stays in the evidence; faces still count toward
            # the reconciliation checks, which are about the pipeline.
            ev = {"pipeline_status": status, "pipeline_reason": reason, **ev}
            status, reason = "out_of_scope", "deferred_card_type:" + deferred[0]
        rows[oid] = {"status": status, "reason": reason, "name": name, "evidence": ev}

    placement = place(rows)

    # ---- checks: computed, not asserted
    sets = {s: {o for o, r in rows.items() if r["status"] == s} for s in STATUSES}
    pair = {f"{a}&{b}": len(sets[a] & sets[b])
            for i, a in enumerate(STATUSES) for b in STATUSES[i + 1:]}
    union = set().union(*sets.values())
    counts = {s: len(sets[s]) for s in STATUSES}
    q_meta = meta["quality"]
    steps = clusters["filter_steps"]
    recon = {
        "faces vanilla == meta.quality.vanilla": (face_tally["vanilla"], q_meta["vanilla"]),
        "faces unparsed == meta.quality.unparsed": (face_tally["unparsed"], q_meta["unparsed"]),
        "faces partial == meta.quality.partial": (face_tally["partial"], q_meta["partial"]),
        "faces clean-stage total == meta.quality.clean": (
            sum(face_tally[s] for s in STAGE_ORDER[:5]), q_meta["clean"]),
        "faces past unmodelled filter == clusters.filter_steps": (
            sum(face_tally[s] for s in STAGE_ORDER[:4]), steps["  minus unmodelled-node entries"]),
        "faces past corrections filter == clusters.filter_steps": (
            sum(face_tally[s] for s in STAGE_ORDER[:3]), steps["  minus corrections-flagged entries"]),
        "faces clustered+noise == clusters.n_cards": (
            face_tally["clustered"] + face_tally["noise"], clusters["n_cards"]),
        "snapshot oracle ids covered by universe": (len(set(faces_of) & universe), len(faces_of)),
    }
    checks = {
        "universe": len(universe),
        "sum_of_statuses": sum(counts.values()),
        "sum_equals_universe": sum(counts.values()) == len(universe),
        "union_equals_universe": union == universe,
        "pairwise_intersections": pair,
        "all_pairwise_zero": all(v == 0 for v in pair.values()),
        "reconciliation": {k: {"ledger": a, "independent": b, "ok": a == b} for k, (a, b) in recon.items()},
        "mixed_face_cards": dict(sorted(mixed.items())),
        "present_cards_with_faces_lost_to_collision": len(faces_lost),
        "placement": placement,
    }

    # ---- gap causes: what to fix next in the parser
    def rank(statuses, kinds):
        cat_cards, frag_cards = collections.Counter(), collections.Counter()
        cat_sole, frag_sole = collections.Counter(), collections.Counter()
        frag_cat, examples = {}, collections.defaultdict(list)
        for oid, r in rows.items():
            if r["status"] not in statuses:
                continue
            fr = [x for x in r["evidence"].get("fragments", []) if x[0] in kinds]
            cats = {c for _, c, _ in fr}
            texts = {(c, t) for _, c, t in fr}
            for c in cats:
                cat_cards[c] += 1
            for c, t in texts:
                frag_cards[t] += 1
                frag_cat[t] = c
                if len(examples[t]) < 4:
                    examples[t].append(r["name"])
            if len(cats) == 1:
                cat_sole[next(iter(cats))] += 1
            if len(texts) == 1:
                frag_sole[next(iter(texts))[1]] += 1
        key = lambda kv: (-kv[1], kv[0])
        return {
            "by_category": [{"category": c, "cards": n, "sole_cause": cat_sole[c]}
                            for c, n in sorted(cat_cards.items(), key=key)[:60]],
            "by_fragment": [{"fragment": t, "category": frag_cat[t], "cards": n,
                             "sole_cause": frag_sole[t], "examples": examples[t]}
                            for t, n in sorted(frag_cards.items(), key=key)[:150]],
        }

    # Unparsed cards carry no fragment -- nothing was structured -- so the only
    # handle on WHY is the text itself: which clause the card opens with.
    unparsed_reason = collections.Counter()
    opener, opener_ex = collections.Counter(), collections.defaultdict(list)
    for oid, r in rows.items():
        if r["status"] != "unparsed":
            continue
        unparsed_reason[r["reason"]] += 1
        if r["reason"] != "text_without_structure":
            continue
        text = next((f["text"] for f in faces_of[oid] if f["q"] == "unparsed"), "")
        first = re.sub(r"\([^)]*\)", "", text).strip().split("\n")[0]
        head = " ".join(norm_fragment(first, r["name"]).replace("—", " — ").split()[:3])
        opener[head] += 1
        if len(opener_ex[head]) < 4:
            opener_ex[head].append(r["name"])
    gap_causes = {
        "partial": rank({"partial"}, {"Unimplemented", "GenericEffect"}),
        "unmodelled": rank({"partial", "unmodelled_node"}, {"unmodelled"}),
        "unparsed_by_reason": [{"reason": k, "cards": v}
                               for k, v in sorted(unparsed_reason.items(), key=lambda kv: (-kv[1], kv[0]))],
        "unparsed_by_opening": [{"opening": k, "cards": v, "examples": opener_ex[k]}
                                for k, v in sorted(opener.items(), key=lambda kv: (-kv[1], kv[0]))[:40]],
    }

    reasons = collections.Counter((r["status"], r["reason"]) for r in rows.values())
    doc = {
        "meta": {
            "snapshot_date": snapshot_date,
            "snapshot_etag": meta.get("snapshot_etag"),
            "universe_source": "MTGJSON AtomicCards " + at_meta.get("version", "?"),
            "out_of_scope_source": "Scryfall oracle_cards ids absent from AtomicCards (not cards), "
                                   "plus planar/scheme/vanguard layouts (deferred to a separate pass)",
            "first_printing_source": "Scryfall default_cards, earliest released_at per oracle id",
            "status_rule": "furthest clustering-pass stage reached by any face",
            "statuses": list(STATUSES),
        },
        "counts": counts,
        "reasons": [{"status": s, "reason": r, "cards": n}
                    for (s, r), n in sorted(reasons.items(), key=lambda kv: (STATUSES.index(kv[0][0]), -kv[1], kv[0][1]))],
        "checks": checks,
        "gap_causes": gap_causes,
        "rows": rows,
    }
    blob = json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()
    with open(os.path.join(BUILD, "ledger.json"), "wb") as fh:
        fh.write(blob)

    write_report(doc, digest)
    print(f"build/ledger.json  sha256 {digest[:16]}  ({len(blob)/1e6:.1f} MB)")
    print(f"universe {len(universe):,} | sum of statuses {sum(counts.values()):,} | "
          f"pairwise all zero: {checks['all_pairwise_zero']} | union == universe: {checks['union_equals_universe']}")
    for s in STATUSES:
        print(f"  {counts[s]:>7,}  {s}")
    bad = [k for k, v in checks["reconciliation"].items() if not v["ok"]]
    print("reconciliation:", "all ok" if not bad else "MISMATCH " + ", ".join(bad))


UNPLACED_BY_STATUS = {
    # Pipeline stages that need their own placement rule -- deliberately not
    # placed yet, and kept visible here with the reason.
    "partial": "awaiting_rule:partial", "unparsed": "awaiting_rule:unparsed",
    "unmodelled_node": "awaiting_rule:unmodelled_node",
    "corrections_flagged": "awaiting_rule:corrections_flagged",
    "no_extractable_effect": "no_feature_to_compare",
    "missing_from_export": "not_in_snapshot", "out_of_scope": "out_of_scope",
}


def place(rows):
    """Annotate each row with how (or why not) it is placed in the tree.

    Reads build/placements.json (src/build_placements.py), which itself reads
    this file's statuses -- so run ledger -> placements -> ledger. Placement
    never feeds back into status. Without the file only `clustered` is placed.
    """
    path = os.path.join(BUILD, "placements.json")
    P = json.load(io.open(path, encoding="utf-8")) if os.path.exists(path) else None
    by_card, review, stages = collections.defaultdict(list), {}, {}
    if P:
        for fid, f in P["faces"].items():
            by_card[f["card"]].append({"face": fid, **{k: v for k, v in f.items() if k != "card"}})
        for x in P["review_queue"]:
            if x["card"] not in review or x["similarity"] > review[x["card"]]["similarity"]:
                review[x["card"]] = x
        stages = P["recovered"]["stages"]
    tally, unplaced = collections.Counter(), collections.Counter()
    for oid, r in rows.items():
        if oid in stages:
            r["evidence"]["recovered"] = {"overlay": "data/overlay/recovered-cards.json",
                                          "faces": stages[oid]}
        placed = by_card.get(oid)
        if r["status"] == "clustered":
            pl = {"method": "clustered", "leaf": r["evidence"]["leaf"]}
        elif placed:
            # A card placed through several faces keeps its best-scoring one
            # here; every placed face is listed in build/placements.json.
            b = max(placed, key=lambda x: (x.get("similarity", 2), x["face"]))
            pl = {k: v for k, v in b.items() if k in ("method", "leaf", "similarity", "branch", "source", "face")}
        else:
            if oid in review:
                reason = "below_similarity_floor"
            elif oid in stages:
                reason = "recovered_" + min((f["stage"] for f in stages[oid]),
                                            key=lambda x: STAGE_ORDER.index(x) if x in STAGE_ORDER else -1)
            elif r["status"] == "noise":
                reason = "below_similarity_floor" if P else "no_placement_layer"
            else:
                reason = UNPLACED_BY_STATUS.get(r["status"], r["status"])
            pl = {"method": "unplaced", "reason": reason}
            if oid in review:
                pl.update(best_leaf=review[oid]["best_leaf"], similarity=review[oid]["similarity"])
            unplaced[reason] += 1
        r["placement"] = pl
        tally[pl["method"]] += 1
    n = len(rows)
    in_scope = n - sum(1 for r in rows.values() if r["status"] == "out_of_scope")
    placed_n = n - tally["unplaced"]
    return {
        "floor": P["meta"]["floor"] if P else None,
        "by_method": dict(sorted(tally.items())),
        "unplaced_by_reason": dict(sorted(unplaced.items(), key=lambda kv: (-kv[1], kv[0]))),
        "placed": placed_n, "universe": n, "in_scope": in_scope,
        "placed_share_of_universe": round(placed_n / n, 4),
        "placed_share_of_in_scope": round(placed_n / in_scope, 4),
        "sum_check": sum(tally.values()) == n,
    }


def write_report(doc, digest):
    c, ch = doc["counts"], doc["checks"]
    L = ["# Coverage ledger", "",
         "Generated by `src/build_ledger.py`. One row per oracle id in the card universe, "
         "exactly one status each. Snapshot: **" + doc["meta"]["snapshot_date"] + "**. "
         "Output sha256 `" + digest[:16] + "`.", "",
         "## Universe", "",
         f"- in scope: **{ch['universe'] - c['out_of_scope']:,}** oracle ids from "
         f"{doc['meta']['universe_source']}",
         f"- out of scope: **{c['out_of_scope']:,}** — {doc['meta']['out_of_scope_source']}",
         f"- total: **{ch['universe']:,}**", "",
         "## Statuses", "", "| status | cards |", "|---|---:|"]
    for s in doc["meta"]["statuses"]:
        L.append(f"| {s} | {c[s]:,} |")
    L += [f"| **sum** | **{ch['sum_of_statuses']:,}** |", "",
          f"Sum equals universe: **{ch['sum_equals_universe']}**. Union equals universe: "
          f"**{ch['union_equals_universe']}**. All {len(ch['pairwise_intersections'])} pairwise "
          f"intersections zero: **{ch['all_pairwise_zero']}**.", "",
          "### Reconciled against numbers computed by earlier passes", "",
          "| check | ledger | independent | ok |", "|---|---:|---:|---|"]
    for k, v in ch["reconciliation"].items():
        L.append(f"| {k} | {v['ledger']:,} | {v['independent']:,} | {'yes' if v['ok'] else '**NO**'} |")
    L += ["", "### Cards whose faces stopped at different stages", "",
          "The card takes the furthest stage; each face's own stage is in its evidence.", ""]
    for k, v in ch["mixed_face_cards"].items():
        L.append(f"- `{k}`: {v}")
    pl = ch["placement"]
    L += ["", "## Placement", "",
          "How each card reaches the browse tree. `clustered` is the HDBSCAN leaf; `proximity` is "
          f"the nearest leaf centroid at cosine >= {pl['floor']} (a separate, flagged layer — it "
          "changes no centroid, cohesion score, count or map); `vanilla_rule` is the "
          "\"No abilities\" branch. See `build/placements.json`.", "",
          "| placement | cards |", "|---|---:|"]
    for k, v in pl["by_method"].items():
        L.append(f"| {k} | {v:,} |")
    L += [f"| **sum** | **{sum(pl['by_method'].values()):,}** (= universe: {pl['sum_check']}) |", "",
          f"Placed: **{pl['placed']:,} / {pl['universe']:,}** universe "
          f"({pl['placed_share_of_universe']:.1%}); **{pl['placed']:,} / {pl['in_scope']:,}** "
          f"in scope ({pl['placed_share_of_in_scope']:.1%}).", "",
          "| unplaced reason | cards |", "|---|---:|"]
    for k, v in pl["unplaced_by_reason"].items():
        L.append(f"| `{k}` | {v:,} |")
    L += ["", "## Reasons", "", "| status | reason | cards |", "|---|---|---:|"]
    for r in doc["reasons"]:
        L.append(f"| {r['status']} | `{r['reason']}` | {r['cards']:,} |")
    g = doc["gap_causes"]
    L += ["", "## Gap causes — what to fix next in the parser", "",
          "`sole cause` = cards where this is the only gap on the card, i.e. the cards that fixing "
          "it alone would unblock.", "",
          "### Partial cards, by category", "", "| category | cards | sole cause |", "|---|---:|---:|"]
    for x in g["partial"]["by_category"][:30]:
        L.append(f"| `{x['category']}` | {x['cards']:,} | {x['sole_cause']:,} |")
    L += ["", "### Partial cards, by fragment", "", "| fragment | category | cards | sole cause |",
          "|---|---|---:|---:|"]
    for x in g["partial"]["by_fragment"][:40]:
        L.append(f"| {x['fragment'][:90]} | `{x['category'][:40]}` | {x['cards']:,} | {x['sole_cause']:,} |")
    L += ["", "### Unmodelled nodes (partial + unmodelled_node cards)", "",
          "| node | kind | cards | sole cause |", "|---|---|---:|---:|"]
    for x in g["unmodelled"]["by_fragment"][:25]:
        L.append(f"| {x['fragment'][:90]} | {x['category']} | {x['cards']:,} | {x['sole_cause']:,} |")
    L += ["", "### Unparsed cards", "",
          "`unparsed` means text with nothing in the four ability buckets. Keywords are parsed into "
          "a separate field, so a card whose whole text is `Flying` lands here although phase.rs "
          "modelled all of it — reason `keywords_only`. The rest carry no fragment at all, so they "
          "are grouped by the clause they open with.", "", "| reason | cards |", "|---|---:|"]
    for x in g["unparsed_by_reason"]:
        L.append(f"| `{x['reason']}` | {x['cards']:,} |")
    L += ["", "| opening clause (`text_without_structure`) | cards | examples |", "|---|---:|---|"]
    for x in g["unparsed_by_opening"][:25]:
        L.append(f"| {x['opening']} | {x['cards']:,} | {', '.join(x['examples'])} |")
    with io.open(os.path.join(REPORTS, "coverage-ledger.md"), "w", encoding="utf-8", newline=chr(10)) as fh:
        fh.write(chr(10).join(L) + chr(10))


if __name__ == "__main__":
    main()
