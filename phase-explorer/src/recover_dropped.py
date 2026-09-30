"""Recover the cards phase.rs's export dropped to face-name collisions.

    python src/recover_dropped.py

The snapshot (data/card-data.json) is keyed by lowercased face name, so when a
Strixhaven `prepare` face is also called "Lightning Bolt" one of the two cards
is silently overwritten. This script regenerates ONLY those losers, with the
same generator that built the snapshot, and writes them to a separate overlay.
card-data.json is never read for writing and never modified.

Generator: phase-rs/phase `oracle-gen` at tag v0.1.15 (commit 930172dab041,
2026-04-20 -- the release the export was built from), toolchain pinned by that
tag's rust-toolchain.toml (nightly-2026-04-19). Path via PHASE_ORACLE_GEN.

Hard gate before anything is written: the same binary is run over the full
current AtomicCards and every snapshot entry whose parse inputs are unchanged
must come out byte-identical (parse fields; legalities/printings/rulings are
copied from whichever AtomicCards is fed in, so they are excluded). Entries
that differ are re-run with the April MTGJSON metadata the snapshot implies
(keyword list, colours, one card per name) and must then match too. Any
remaining difference aborts the run.

Each loser is then generated on its own, from a one-card AtomicCards file
holding only that oracle id's faces, so it cannot collide with anything.

Output: data/overlay/recovered-cards.json
    {"meta": {...provenance, gate result...},
     "cards": {oracle_id: [face entry, ...]}}   # entries as in card-data.json
"""
import gzip
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(DATA, "overlay", "recovered-cards.json")
GEN = os.environ.get("PHASE_ORACLE_GEN",
                     r"C:\source\phase-rs\phase-v0.1.15\target\tool\oracle-gen.exe")
GEN_COMMIT = "930172dab041798b02d0f7e2b18371b900405569"

META_FIELDS = ("legalities", "printings", "rulings")      # copied from the input file
INPUT_FIELDS = ("name", "mana_cost", "card_type", "power", "toughness", "loyalty",
                "defense", "oracle_text", "flavor_name", "layout")


def one(e):
    return e[0] if isinstance(e, list) else e


def parse_part(e):
    return json.dumps({k: v for k, v in e.items() if k not in META_FIELDS}, ensure_ascii=False)


def run_gen(atomic_meta, data, tmp):
    path = os.path.join(tmp, "atomic.json")
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump({"meta": atomic_meta, "data": data}, fh, ensure_ascii=False)
    out = subprocess.run([GEN, "--mtgjson", path], capture_output=True, check=True).stdout
    return json.loads(out)


def mtgjson_keyword(k):
    """Engine keyword ("FirstStrike" / {"Backup": 2}) -> MTGJSON spelling."""
    name = k if isinstance(k, str) else next(iter(k))
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).capitalize()


def gate(snapshot, atomic, tmp):
    sys.stderr.write("gate: generating the full current AtomicCards\n")
    control = run_gen(atomic["meta"], atomic["data"], tmp)
    tally = {"identical": 0, "identical_after_april_metadata": 0, "different": 0,
             "excluded_inputs_changed": 0, "excluded_key_reassigned": 0, "excluded_absent": 0}
    differ = []
    for k, s in snapshot.items():
        s, c = one(s), control.get(k)
        if c is None:
            tally["excluded_absent"] += 1
        elif one(c).get("scryfall_oracle_id") != s.get("scryfall_oracle_id"):
            tally["excluded_key_reassigned"] += 1
        elif any(s.get(f) != one(c).get(f) for f in INPUT_FIELDS):
            tally["excluded_inputs_changed"] += 1
        elif parse_part(s) == parse_part(one(c)):
            tally["identical"] += 1
        else:
            differ.append(k)

    # Re-run the differing entries with the MTGJSON metadata the snapshot
    # implies. MTGJSON has edited its keyword lists and colours since April,
    # and now files two different cards under "Joven and Chandler" -- all
    # inputs to the generator, none of them the parser.
    if differ:
        by_face = {}
        for full, faces in atomic["data"].items():
            for f in faces:
                by_face.setdefault((f.get("faceName") or f["name"]).lower(), (full, []))[1].append(f)
        data = {}
        for k in differ:
            s = one(snapshot[k])
            full, faces = by_face[k]
            faces = [f for f in atomic["data"][full]
                     if (f.get("identifiers") or {}).get("scryfallOracleId") == s["scryfall_oracle_id"]]
            restored = []
            for f in faces:
                f = dict(f)
                if (f.get("faceName") or f["name"]).lower() == k:
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
            if k in rerun and parse_part(one(snapshot[k])) == parse_part(one(rerun[k])):
                tally["identical_after_april_metadata"] += 1
            else:
                tally["different"] += 1
                sys.stderr.write(f"gate: still differs: {k}\n")
    tally["compared"] = tally["identical"] + tally["identical_after_april_metadata"] + tally["different"]
    tally["passed"] = tally["different"] == 0
    return tally


def main():
    snapshot = json.load(io.open(os.path.join(DATA, "card-data.json"), encoding="utf-8"))
    atomic = json.load(gzip.open(os.path.join(DATA, "AtomicCards.json.gz"), "rt", encoding="utf-8"))
    ledger = json.load(io.open(os.path.join(BUILD, "ledger.json"), encoding="utf-8"))
    targets = sorted(o for o, r in ledger["rows"].items()
                     if r["status"] == "missing_from_export" and r["reason"] == "collision_dropped")

    with tempfile.TemporaryDirectory() as tmp:
        g = gate(snapshot, atomic, tmp)
        print("gate:", json.dumps(g))
        if not g["passed"]:
            sys.exit("gate FAILED -- parser output does not match the snapshot; nothing written")

        faces_of = {}
        for full, faces in atomic["data"].items():
            for f in faces:
                oid = (f.get("identifiers") or {}).get("scryfallOracleId")
                if oid in targets:
                    faces_of.setdefault(oid, {}).setdefault(full, []).append(f)
        cards, failed = {}, {}
        for oid in targets:
            out = run_gen(atomic["meta"], faces_of.get(oid, {}), tmp)
            got = [e for e in out.values() if one(e).get("scryfall_oracle_id") == oid]
            if got:
                # face order as the generator emits it for the card (front first)
                order = [f.get("faceName") or f["name"] for fs in faces_of[oid].values() for f in fs]
                got.sort(key=lambda e: order.index(one(e)["name"]) if one(e)["name"] in order else 99)
                cards[oid] = [one(e) for e in got]
            else:
                failed[oid] = "generator produced no entry"

    doc = {
        "meta": {
            "what": "cards dropped from the snapshot by face-name collisions, regenerated one at a time",
            "generator": "phase-rs/phase oracle-gen v0.1.15",
            "generator_commit": GEN_COMMIT,
            "toolchain": "nightly-2026-04-19 (x86_64-pc-windows-gnu)",
            "input": "MTGJSON AtomicCards " + atomic["meta"].get("version", "?") +
                     " (legalities/printings/rulings/keyword metadata are from this file, not April's)",
            "gate": g,
            "targets": len(targets),
            "recovered": len(cards),
            "failed": failed,
        },
        "cards": cards,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print(f"recovered {len(cards)}/{len(targets)} -> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
