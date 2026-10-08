"""Add the cards released after the April snapshot as a separate, oracle-id-keyed overlay.

    python src/add_new_release_cards.py

Approach A of the snapshot refresh (additive overlay). The pinned generator -- phase-rs
`oracle-gen` v0.1.15 plus the four local, gate-verified parser changes already shipped as
overlays -- is run on ONLY the cards that are in the current MTGJSON AtomicCards but neither in
the April snapshot nor in the collision-recovered overlay. Existing cards are not regenerated
and not touched; card-data.json is never read for writing.

Two MTGJSON files, on purpose:
  data/AtomicCards.json.gz            2026-09-21, the ledger's universe and this round's GATE
                                      control set (unchanged since earlier rounds)
  data/AtomicCards-20261003.json.gz   the SOURCE of the new cards only
Swapping the newer file in as the universe would have removed 216 snapshot cards (Alchemy "A-"
rebalances MTGJSON dropped) and edited the Oracle text of 56 existing ones, i.e. changed existing
cards. It is therefore used only to read the new cards.

GATE (nothing is written unless it passes). The pinned binary is run over the full
2026-09-21 AtomicCards; every entry whose inputs are unchanged must be byte-identical to the
base (snapshot with all four earlier parser-fix overlays applied; earlier-overlay faces are
compared canonically because they were saved with sorted keys). Zero differences are allowed,
because this round changes no parser code. The comparison is audited as in the previous round:
two comparators, hashes of the compared bytes, and a planted one-field mutation that must be
detected.

GENERATION. One oracle id per run, so no face-name collision can drop a card (the new data has
`joven and chandler`, `artist alley` and `boltwave` colliding with existing snapshot keys, and
five keys shared by two new cards). Every card must come back with exactly the faces MTGJSON
lists for it. Collisions are reported, not "resolved".

Output: data/overlay/new-release-cards.json   {"meta": {...}, "cards": {oracle_id: [face, ...]}}
"""
import collections
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(DATA, "overlay", "new-release-cards.json")
SOURCE = os.path.join(DATA, "AtomicCards-20261003.json.gz")
GEN = os.environ.get("PHASE_ORACLE_GEN",
                     r"C:\source\phase-rs\phase-v0.1.15\target\debug\oracle-gen.exe")
GEN_COMMIT = ("930172dab041798b02d0f7e2b18371b900405569 + local fixes (commander eligibility, "
              "commander creatures, Unrecognized restriction, activation timing split)")
PRIOR_OVERLAYS = [os.path.join(DATA, "overlay", n) for n in
                  ("commander-eligibility-fix.json", "commander-creatures-fix.json",
                   "unrecognized-restriction-fix.json", "activation-timing-split-fix.json")]
RECOVERED = os.path.join(DATA, "overlay", "recovered-cards.json")
DEFERRED_LAYOUTS = ("planar", "scheme", "vanguard")      # out of scope in the ledger

META_FIELDS = ("legalities", "printings", "rulings")
INPUT_FIELDS = ("name", "mana_cost", "card_type", "power", "toughness", "loyalty",
                "defense", "oracle_text", "flavor_name", "layout")


def one(e):
    return e[0] if isinstance(e, list) else e


def strip_meta(e):
    return {k: v for k, v in e.items() if k not in META_FIELDS}


def parse_part(e):
    return json.dumps(strip_meta(e), ensure_ascii=False)


def canon_part(e):
    return json.dumps(strip_meta(e), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def run_gen(atomic_meta, data, tmp):
    path = os.path.join(tmp, "atomic.json")
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump({"meta": atomic_meta, "data": data}, fh, ensure_ascii=False)
    out = subprocess.run([GEN, "--mtgjson", path], capture_output=True, check=True).stdout
    return json.loads(out)


def mtgjson_keyword(k):
    name = k if isinstance(k, str) else next(iter(k))
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).capitalize()


def oid_of(f):
    return (f.get("identifiers") or {}).get("scryfallOracleId")


def face_key(f):
    return (f.get("faceName") or f["name"]).lower()


def gate(snapshot, atomic, tmp):
    base, overlay_keys = dict(snapshot), set()
    for path in PRIOR_OVERLAYS:
        for faces in json.load(io.open(path, encoding="utf-8"))["cards"].values():
            for face in faces:
                base[face["name"].lower()] = face
                overlay_keys.add(face["name"].lower())
    probe = one(next(iter(base.values())))
    mutated = json.loads(json.dumps(probe))
    mutated["name"] += "!"
    assert parse_part(probe) != parse_part(mutated) and canon_part(probe) != canon_part(mutated), \
        "comparison self-test failed: a planted mutation was not detected"

    sys.stderr.write("gate: generating the full 2026-09-21 AtomicCards\n")
    control = run_gen(atomic["meta"], atomic["data"], tmp)
    tally = collections.Counter()
    differ, ident = [], []
    for k, s in base.items():
        s, c = one(s), control.get(k)
        if c is None:
            tally["excluded_absent"] += 1
        elif one(c).get("scryfall_oracle_id") != s.get("scryfall_oracle_id"):
            tally["excluded_key_reassigned"] += 1
        elif any(s.get(f) != one(c).get(f) for f in INPUT_FIELDS):
            tally["excluded_inputs_changed"] += 1
        elif parse_part(s) == parse_part(one(c)):
            tally["identical"] += 1
            ident.append(k)
        elif k in overlay_keys and canon_part(s) == canon_part(one(c)):
            tally["identical_overlay_face_canonical"] += 1
        else:
            differ.append(k)

    h_base, h_ctrl, canon_bad = hashlib.sha256(), hashlib.sha256(), 0
    for k in sorted(ident):
        pb, pc = parse_part(one(base[k])), parse_part(one(control[k]))
        h_base.update(pb.encode("utf-8"))
        h_ctrl.update(pc.encode("utf-8"))
        canon_bad += canon_part(one(base[k])) != canon_part(one(control[k]))
    assert h_base.hexdigest() == h_ctrl.hexdigest() and canon_bad == 0, \
        "comparison audit failed: ordered/canonical comparators disagree"
    audit = {"identical_entries_hashed": len(ident), "sha256": h_base.hexdigest(),
             "canonical_comparator_disagreements": canon_bad,
             "planted_mutation_detected": True, "binary": os.path.basename(GEN),
             "binary_mtime": int(os.path.getmtime(GEN))}

    if differ:                       # same April-metadata restoration as every earlier gate
        by_face = {}
        for full, faces in atomic["data"].items():
            for f in faces:
                by_face.setdefault(face_key(f), (full, []))[1].append(f)
        data = {}
        for k in differ:
            s = one(base[k])
            full, _ = by_face[k]
            restored = []
            for f in [f for f in atomic["data"][full] if oid_of(f) == s["scryfall_oracle_id"]]:
                f = dict(f)
                if face_key(f) == k:
                    april = [mtgjson_keyword(x) for x in s.get("keywords") or []]
                    f["keywords"] = april + [x for x in f.get("keywords") or []
                                             if x.split()[0].lower() not in {a.split()[0].lower() for a in april}
                                             and x not in ("Start your engines!",)]
                    if s.get("color_override") is None:
                        f["colors"] = sorted(set(re.findall(r"\{([WUBRG])\}", f.get("manaCost") or "")))
                restored.append(f)
            data[full] = restored
        rerun = run_gen(atomic["meta"], data, tmp)
        for k in differ:
            if k in rerun and (parse_part(one(base[k])) == parse_part(one(rerun[k]))
                               or (k in overlay_keys and canon_part(one(base[k])) == canon_part(one(rerun[k])))):
                tally["identical_after_april_metadata"] += 1
            else:
                tally["different"] += 1
                sys.stderr.write(f"gate: DIFFERENT: {k}\n")
    tally = dict(tally)
    tally.setdefault("different", 0)
    tally["compared"] = sum(tally.get(k, 0) for k in
                            ("identical", "identical_overlay_face_canonical",
                             "identical_after_april_metadata", "different"))
    return tally, audit, base


def main():
    snapshot = json.load(io.open(os.path.join(DATA, "card-data.json"), encoding="utf-8"))
    atomic_old = json.load(gzip.open(os.path.join(DATA, "AtomicCards.json.gz"), "rt", encoding="utf-8"))
    atomic_new = json.load(gzip.open(SOURCE, "rt", encoding="utf-8"))
    recovered = json.load(io.open(RECOVERED, encoding="utf-8"))["cards"]

    with tempfile.TemporaryDirectory() as tmp:
        g, audit, base = gate(snapshot, atomic_old, tmp)
        print("gate:", json.dumps(g))
        print("comparison audit:", json.dumps(audit))
        if g["different"]:
            sys.exit("gate FAILED -- the pinned binary no longer reproduces the existing cards; nothing written")

        have = {one(s).get("scryfall_oracle_id") for s in base.values()} | set(recovered)
        faces_of, layouts = {}, {}
        for full, faces in atomic_new["data"].items():
            for f in faces:
                oid = oid_of(f)
                if oid and oid not in have:
                    faces_of.setdefault(oid, {}).setdefault(full, []).append(f)
                    layouts.setdefault(oid, set()).add(f.get("layout"))
        deferred = sorted(o for o, ls in layouts.items() if ls & set(DEFERRED_LAYOUTS))
        targets = sorted(set(faces_of) - set(deferred))
        print(f"new oracle ids: {len(faces_of)} | deferred layouts (out of scope in the ledger): "
              f"{len(deferred)} | to generate: {len(targets)}")

        # ---- collision census over the new faces' lowercased keys (reported, not resolved)
        snap_keys = set(base) | {face["name"].lower() for fs in recovered.values() for face in fs}
        key_owners = collections.defaultdict(set)
        for oid in targets:
            for fs in faces_of[oid].values():
                for f in fs:
                    key_owners[face_key(f)].add(oid)
        vs_existing = sorted(k for k in key_owners if k in snap_keys)
        among_new = sorted(k for k, v in key_owners.items() if len(v) > 1)

        cards, failed = {}, {}
        for n, oid in enumerate(targets, 1):
            want = [f for fs in faces_of[oid].values() for f in fs]
            out = run_gen(atomic_new["meta"], faces_of[oid], tmp)
            got = [one(e) for e in out.values() if one(e).get("scryfall_oracle_id") == oid]
            order = [f.get("faceName") or f["name"] for f in want]
            got.sort(key=lambda e: order.index(e["name"]) if e["name"] in order else 99)
            if {e["name"] for e in got} != {f.get("faceName") or f["name"] for f in want}:
                failed[oid] = "faces returned %s, MTGJSON lists %s" % (
                    sorted(e["name"] for e in got), sorted(order))
                continue
            cards[oid] = got
            if n % 200 == 0:
                sys.stderr.write(f"generated {n}/{len(targets)}\n")

    if failed:
        for o, why in list(failed.items())[:20]:
            sys.stderr.write(f"FAILED {o}: {why}\n")
    doc = {
        "meta": {
            "what": "cards in MTGJSON AtomicCards 5.3.0+20261003 that are neither in the April "
                    "snapshot nor in the collision-recovered overlay, generated one oracle id at a time",
            "generator": "phase-rs/phase oracle-gen v0.1.15 + local fixes",
            "generator_commit": GEN_COMMIT,
            "toolchain": "nightly-2026-04-19 (x86_64-pc-windows-gnu)",
            "input": "MTGJSON AtomicCards " + atomic_new["meta"]["version"],
            "gate_control_input": "MTGJSON AtomicCards " + atomic_old["meta"]["version"],
            "gate": g,
            "comparison_audit": audit,
            "new_oracle_ids": len(faces_of),
            "deferred_layout_ids": deferred,
            "generated": len(cards),
            "faces": sum(len(v) for v in cards.values()),
            "failed": failed,
            "collisions": {"keys_colliding_with_an_existing_key": vs_existing,
                           "keys_shared_by_two_new_cards": among_new,
                           "cards_affected_if_keyed_by_face_name": len(
                               {o for k in vs_existing + among_new for o in key_owners[k]})},
        },
        "cards": cards,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print(f"generated {len(cards)}/{len(targets)} cards ({doc['meta']['faces']} faces), "
          f"{len(failed)} failed -> {os.path.relpath(OUT, HERE)}")
    print("collisions:", json.dumps(doc["meta"]["collisions"]))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
