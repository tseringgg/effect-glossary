"""Apply the "can be your commander" parser fix as an overlay.

    python src/apply_commander_eligibility_overlay.py

Unlike the AddKeyword round (a fix to our own gap classification), this is a
real parser fix in the local phase-rs v0.1.15 checkout: the oracle-text line
dispatcher in `crates/engine/src/parser/oracle.rs` now recognizes the bare,
literal sentence "<name> can be your commander." and drops it instead of
falling through to the `Unimplemented` placeholder -- the fact itself was
already captured independently by `CardFace::brawl_commander` and
`deck_validation::{is_commander_eligible, is_brawl_commander_eligible}` (both
verified live, before this fix, against real synthesized data), so nothing
about commander legality changes; only the structured ability tree does.

card-data.json is never read for writing and never modified. The corrected
parse for the affected cards is written to a separate overlay.

Generator: phase-rs/phase `oracle-gen` at tag v0.1.15 (commit 930172dab041,
2026-04-20 -- the release the export was built from, PLUS the local, narrow
one-line-dispatch fix described above), toolchain pinned by that tag's
rust-toolchain.toml (nightly-2026-04-19). Path via PHASE_ORACLE_GEN.

Target selection: every face in the current snapshot carrying an
`Unimplemented` node with `name == "unknown"` and `description` exactly equal
to "<that face's name> can be your commander." -- the identical literal
criterion the Rust fix matches on, so a mismatch between what Python expects
and what the fixed binary actually changed aborts the run instead of silently
shipping something else.

Hard gate before anything is written: the fixed binary is run over the full
current AtomicCards and EVERY entry outside the target set must come out
byte-identical to the live snapshot (parse fields only; legalities/printings/
rulings are excluded, same as recover_dropped.py's gate). Entries that differ
are re-run with the April MTGJSON metadata the snapshot implies, same two-pass
discipline as recover_dropped.py. Any difference outside the target set, or
any target-set card that does NOT change, aborts the run -- this is a
deliberately inverted gate from recover_dropped.py's (which asserts zero
differences): here we assert differences exactly where expected and nowhere
else.

Each target card is then regenerated on its own, from a one-card AtomicCards
file holding only that oracle id's faces, matching recover_dropped.py's
isolation discipline.

Output: data/overlay/commander-eligibility-fix.json
    {"meta": {...provenance, gate result, target list...},
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
OUT = os.path.join(DATA, "overlay", "commander-eligibility-fix.json")
GEN = os.environ.get("PHASE_ORACLE_GEN",
                     r"C:\source\phase-rs\phase-v0.1.15\target\debug\oracle-gen.exe")
GEN_COMMIT = "930172dab041798b02d0f7e2b18371b900405569 + local fix (oracle.rs can-be-your-commander dispatch)"

META_FIELDS = ("legalities", "printings", "rulings")      # copied from the input file
INPUT_FIELDS = ("name", "mana_cost", "card_type", "power", "toughness", "loyalty",
                "defense", "oracle_text", "flavor_name", "layout")
BUCKETS = ("abilities", "triggers", "static_abilities", "replacements")


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
    name = k if isinstance(k, str) else next(iter(k))
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).capitalize()


def has_commander_sentence(node, name):
    """Walk a face's four ability buckets for the exact Unimplemented node this fix targets.

    The engine's self-reference normalizer (normalize_self_refs_for_static,
    which the Rust fix matches against) recognizes a card's full name AND its
    short name (e.g. "Svega" for "Svega, the Unconventional") as the same
    self-reference -- some cards' own rules text uses the short form. Checked
    against both, same convention build_ledger.py's norm_fragment() uses.
    """
    names = {name, name.split(",")[0]} - {""}
    target_descs = {f"{n} can be your commander." for n in names}

    def walk(n):
        if isinstance(n, dict):
            if (n.get("type") == "Unimplemented" and n.get("name") == "unknown"
                    and n.get("description") in target_descs):
                return True
            return any(walk(v) for v in n.values())
        if isinstance(n, list):
            return any(walk(v) for v in n)
        return False

    return any(walk(node.get(b)) for b in BUCKETS)


def gate(snapshot, atomic, tmp, targets):
    """Like recover_dropped.gate, but asserts differences fall EXACTLY on `targets`."""
    sys.stderr.write("gate: generating the full current AtomicCards\n")
    control = run_gen(atomic["meta"], atomic["data"], tmp)
    tally = {"identical": 0, "identical_after_april_metadata": 0,
              "unexpected_different": 0, "target_unchanged": 0,
              "excluded_inputs_changed": 0, "excluded_key_reassigned": 0, "excluded_absent": 0}
    differ = []
    for k, s in snapshot.items():
        s, c = one(s), control.get(k)
        oid = s.get("scryfall_oracle_id")
        if c is None:
            tally["excluded_absent"] += 1
        elif one(c).get("scryfall_oracle_id") != oid:
            tally["excluded_key_reassigned"] += 1
        elif any(s.get(f) != one(c).get(f) for f in INPUT_FIELDS):
            tally["excluded_inputs_changed"] += 1
        elif parse_part(s) == parse_part(one(c)):
            tally["identical"] += 1
            if oid in targets:
                tally["target_unchanged"] += 1
        else:
            differ.append(k)

    unexpected = []
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
            s = one(snapshot[k])
            oid = s.get("scryfall_oracle_id")
            if k in rerun and parse_part(s) == parse_part(one(rerun[k])):
                tally["identical_after_april_metadata"] += 1
                if oid in targets:
                    tally["target_unchanged"] += 1
            elif oid in targets:
                pass  # expected: this is one of our targets, genuinely different
            else:
                tally["unexpected_different"] += 1
                unexpected.append(k)
                sys.stderr.write(f"gate: UNEXPECTED difference outside target set: {k}\n")

    realized_targets = {one(snapshot[k]).get("scryfall_oracle_id")
                         for k in differ if one(snapshot[k]).get("scryfall_oracle_id") in targets}
    tally["targets_expected"] = len(targets)
    tally["targets_realized"] = len(realized_targets)
    tally["compared"] = sum(tally[k] for k in
                             ("identical", "identical_after_april_metadata", "unexpected_different"))
    tally["passed"] = (tally["unexpected_different"] == 0
                       and tally["target_unchanged"] == 0
                       and realized_targets == targets)
    return tally, unexpected


def main():
    snapshot = json.load(io.open(os.path.join(DATA, "card-data.json"), encoding="utf-8"))
    atomic = json.load(gzip.open(os.path.join(DATA, "AtomicCards.json.gz"), "rt", encoding="utf-8"))

    targets = set()
    target_keys = {}
    for k, e in snapshot.items():
        e = one(e)
        if has_commander_sentence(e, e.get("name") or ""):
            oid = e.get("scryfall_oracle_id")
            targets.add(oid)
            target_keys.setdefault(oid, []).append(k)

    print(f"target selection: {len(targets)} oracle ids, {sum(len(v) for v in target_keys.values())} faces")

    with tempfile.TemporaryDirectory() as tmp:
        g, unexpected = gate(snapshot, atomic, tmp, targets)
        print("gate:", json.dumps(g))
        if not g["passed"]:
            sys.exit("gate FAILED -- see unexpected differences above; nothing written")

        faces_of = {}
        for full, faces in atomic["data"].items():
            for f in faces:
                oid = (f.get("identifiers") or {}).get("scryfallOracleId")
                if oid in targets:
                    faces_of.setdefault(oid, {}).setdefault(full, []).append(f)

        cards, failed = {}, {}
        for oid in sorted(targets):
            out = run_gen(atomic["meta"], faces_of.get(oid, {}), tmp)
            got = [e for e in out.values() if one(e).get("scryfall_oracle_id") == oid]
            if got:
                order = [f.get("faceName") or f["name"] for fs in faces_of[oid].values() for f in fs]
                got.sort(key=lambda e: order.index(one(e)["name"]) if one(e)["name"] in order else 99)
                cards[oid] = [one(e) for e in got]
                # These cards already exist in the (frozen, 2026-04-20-dated)
                # snapshot. The isolated regen derives legalities/printings/
                # rulings from TODAY's AtomicCards, which can disagree with
                # what the snapshot itself recorded (format legality changes,
                # new printings, ...) -- restore the snapshot's own values so
                # these fields stay internally consistent with every other
                # entry in the build, same discipline as recover_dropped.py
                # documents for META_FIELDS, just preserving instead of
                # accepting today's values (there's a frozen original to
                # preserve here; recover_dropped's cards have none).
                orig_keys = sorted(target_keys[oid])
                for face in cards[oid]:
                    face_key = face["name"].lower()
                    src_key = face_key if face_key in orig_keys else orig_keys[0]
                    orig = one(snapshot[src_key])
                    for f in META_FIELDS:
                        if f in orig:
                            face[f] = orig[f]
                        else:
                            face.pop(f, None)
                # Re-confirm, in this isolated single-card regen, that the
                # targeted sentence is actually gone and nothing else moved.
                for face in cards[oid]:
                    if has_commander_sentence(face, face.get("name") or ""):
                        failed[oid] = "isolated regen still has the Unimplemented node"
            else:
                failed[oid] = "generator produced no entry"

    if failed:
        sys.exit(f"isolated regeneration mismatch for {len(failed)} card(s): {failed}; nothing written")

    doc = {
        "meta": {
            "what": "cards whose '<name> can be your commander.' sentence now parses to nothing "
                    "(dropped, not structured) instead of an Unimplemented placeholder -- the fact "
                    "itself was already captured independently via CardFace.brawl_commander and "
                    "deck_validation::{is_commander_eligible,is_brawl_commander_eligible}",
            "generator": "phase-rs/phase oracle-gen v0.1.15 + local fix",
            "generator_commit": GEN_COMMIT,
            "toolchain": "nightly-2026-04-19 (x86_64-pc-windows-gnu)",
            "fix_location": "crates/engine/src/parser/oracle.rs, parse_oracle_text main line loop",
            "gate": g,
            "targets": len(targets),
            "fixed": len(cards),
            "failed": failed,
        },
        "cards": cards,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print(f"fixed {len(cards)}/{len(targets)} -> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
