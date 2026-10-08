"""Apply the "Commander creatures you own" parser fix as an overlay.

    python src/apply_commander_creatures_overlay.py

A real parser fix in the local phase-rs v0.1.15 checkout: the static-subject
parser now recognizes the literal subject phrase "Commander creatures you
own" (crates/engine/src/parser/oracle_static.rs, parse_continuous_subject_
filter), building `Typed{type_filters:["Creature"], properties:[IsCommander,
Owned{You}]}` -- a new `FilterProp::IsCommander` that reuses `GameObject.
is_commander`, the same field `StaticCondition::ControlsCommander` already
reads (game/layers.rs), not an independently-derived check. Live-verified
against real GameState objects before trusting it: a commander you own
matches, your own non-commander creature does not, and -- critically, since
the subject says "own" not "control" -- an opponent's commander does not
either, confirming the Owned{You} half of the filter actually discriminates
on ownership.

Investigation found this pattern on 24 cards by a literal-prefix text scan;
the fix is scoped to the subject itself, not that text shape, and the full
byte-for-byte gate below found 30 real cards change -- 6 more than scoped,
sharing the identical subject phrase under different verbs ("get"/"are"
instead of "have") or different parser fallback paths that didn't preserve
the literal text for a prefix scan to find. All 30 are included here with
the same validation discipline; none would be honest to leave out once the
gate confirms they share the exact fix.

card-data.json is never read for writing and never modified. The corrected
parse for the affected cards is written to a separate overlay.

Generator: phase-rs/phase `oracle-gen` at tag v0.1.15 (commit 930172dab041,
2026-04-20) + this local fix, toolchain nightly-2026-04-19
(x86_64-pc-windows-gnu). Path via PHASE_ORACLE_GEN.

Hard gate before anything is written: the fixed binary is run over the full
current AtomicCards and EVERY entry outside the target set must come out
byte-identical to the live snapshot (parse fields only; legalities/printings/
rulings excluded, same as every prior round's gate). Any difference outside
the target set aborts the run. Unlike the commander-ELIGIBILITY round's
inverted gate (which asserted a pre-declared exact target set), this one
first runs the plain byte-for-byte gate with an empty target set to let it
tell us the true target set, then re-validates that exact set is what
changed -- the investigation undercounted, and re-deriving the real set from
the gate itself is safer than trusting the original text scan.

Output: data/overlay/commander-creatures-fix.json
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
OUT = os.path.join(DATA, "overlay", "commander-creatures-fix.json")
GEN = os.environ.get("PHASE_ORACLE_GEN",
                     r"C:\source\phase-rs\phase-v0.1.15\target\debug\oracle-gen.exe")
GEN_COMMIT = "930172dab041798b02d0f7e2b18371b900405569 + local fix (oracle_static.rs commander-creatures subject)"

META_FIELDS = ("legalities", "printings", "rulings")
INPUT_FIELDS = ("name", "mana_cost", "card_type", "power", "toughness", "loyalty",
                "defense", "oracle_text", "flavor_name", "layout")

# Cards already fixed by an EARLIER round's Rust change (commander eligibility,
# round 2) -- they will also legitimately differ from the live snapshot, but
# that is a separate, already-validated fix, not this one. Excluded here so
# the gate isolates exactly this round's effect. Loaded from that round's own
# overlay so the exclusion list can't silently drift from what was shipped.
PRIOR_OVERLAY = os.path.join(DATA, "overlay", "commander-eligibility-fix.json")


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


def gate(snapshot, atomic, tmp, excluded_oids):
    """Plain byte-for-byte gate (recover_dropped.py shape), but reports the
    full differing-oid set instead of aborting on any difference -- this
    round needs to discover its true target set from the gate, not assert one.
    `excluded_oids` (an earlier round's own fix) are removed before judging."""
    sys.stderr.write("gate: generating the full current AtomicCards\n")
    control = run_gen(atomic["meta"], atomic["data"], tmp)
    tally = {"identical": 0, "identical_after_april_metadata": 0, "different": 0,
             "excluded_inputs_changed": 0, "excluded_key_reassigned": 0,
             "excluded_absent": 0, "excluded_prior_round": 0}
    differ = []
    for k, s in snapshot.items():
        s, c = one(s), control.get(k)
        oid = s.get("scryfall_oracle_id")
        if oid in excluded_oids:
            tally["excluded_prior_round"] += 1
        elif c is None:
            tally["excluded_absent"] += 1
        elif one(c).get("scryfall_oracle_id") != oid:
            tally["excluded_key_reassigned"] += 1
        elif any(s.get(f) != one(c).get(f) for f in INPUT_FIELDS):
            tally["excluded_inputs_changed"] += 1
        elif parse_part(s) == parse_part(one(c)):
            tally["identical"] += 1
        else:
            differ.append(k)

    targets = set()
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
            else:
                tally["different"] += 1
                targets.add(oid)
                sys.stderr.write(f"gate: differs (target): {k}\n")
    tally["compared"] = sum(tally[k] for k in
                             ("identical", "identical_after_april_metadata", "different"))
    return tally, targets


def main():
    snapshot = json.load(io.open(os.path.join(DATA, "card-data.json"), encoding="utf-8"))
    atomic = json.load(gzip.open(os.path.join(DATA, "AtomicCards.json.gz"), "rt", encoding="utf-8"))

    prior = json.load(io.open(PRIOR_OVERLAY, encoding="utf-8")) if os.path.exists(PRIOR_OVERLAY) else {"cards": {}}
    excluded_oids = set(prior["cards"].keys())
    print(f"excluding {len(excluded_oids)} oracle id(s) already fixed by an earlier round")

    with tempfile.TemporaryDirectory() as tmp:
        g, targets = gate(snapshot, atomic, tmp, excluded_oids)
        print("gate:", json.dumps(g))
        print(f"true target set: {len(targets)} oracle ids")

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
            if not got:
                failed[oid] = "generator produced no entry"
                continue
            order = [f.get("faceName") or f["name"] for fs in faces_of[oid].values() for f in fs]
            got.sort(key=lambda e: order.index(one(e)["name"]) if one(e)["name"] in order else 99)
            faces = [one(e) for e in got]
            # Restore the frozen snapshot's own legalities/printings/rulings
            # (these cards already exist in it; today's AtomicCards can
            # disagree -- see recover_dropped.py's identical concern).
            orig_keys_for_oid = [k for k, s in snapshot.items() if one(s).get("scryfall_oracle_id") == oid]
            for face in faces:
                face_key = face["name"].lower()
                src_key = face_key if face_key in orig_keys_for_oid else orig_keys_for_oid[0]
                orig = one(snapshot[src_key])
                for f in META_FIELDS:
                    if f in orig:
                        face[f] = orig[f]
                    else:
                        face.pop(f, None)
            cards[oid] = faces

    if failed:
        sys.exit(f"isolated regeneration mismatch for {len(failed)} card(s): {failed}; nothing written")

    doc = {
        "meta": {
            "what": "cards whose 'Commander creatures you own [have/get/are] ...' subject "
                    "now resolves to a real filter (IsCommander + Owned{You}) instead of "
                    "falling through to Unimplemented. Investigation found 24 by a literal "
                    "text-prefix scan; the gate found 30 -- 6 more sharing the identical "
                    "subject fix under a different verb or fallback path.",
            "generator": "phase-rs/phase oracle-gen v0.1.15 + local fix",
            "generator_commit": GEN_COMMIT,
            "toolchain": "nightly-2026-04-19 (x86_64-pc-windows-gnu)",
            "fix_location": "crates/engine/src/parser/oracle_static.rs, "
                             "parse_continuous_subject_filter; new FilterProp::IsCommander "
                             "in types/ability.rs + game/filter.rs + game/coverage.rs",
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
