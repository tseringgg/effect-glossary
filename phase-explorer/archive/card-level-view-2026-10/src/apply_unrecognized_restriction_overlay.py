"""Apply the "keep unparsed restriction text" parser change as an overlay.

    python src/apply_unrecognized_restriction_overlay.py

A VISIBILITY fix in the local phase-rs v0.1.15 checkout, not a resolution.
`parse_restriction_condition` returns `None` for any "Activate only if ..." /
"Cast this spell only if ..." / "You may ... if ..." text outside its closed
vocabulary, and every storing call site wrapped that `None` into
`RequiresCondition { condition: None }` (or left a casting option's
`condition` unset). The engine evaluates `None` as permissive-true, so the
condition was silently discarded (KNOWN_LIMITATIONS.md section 4,
"nested-wrapper").

The fix adds `ParsedCondition::Unrecognized { text }` (same precedent as
`StaticCondition::Unrecognized` / `ReplacementCondition::Unrecognized`), kept
permissive (`true`) so gameplay is unchanged, and a storing-form helper
`parse_restriction_condition_or_unrecognized`. The `Option`-returning
`parse_restriction_condition` is untouched, because three casting-option
callers use its `None` as control flow. No card is newly PARSED by this; every
affected card moves from an invisible null to a visible `Unrecognized` node
carrying the real condition text.

Changed files (crates/engine/src): types/ability.rs (variant),
parser/oracle_condition.rs (helper + tests), game/restrictions.rs
(`Unrecognized => true`), parser/oracle.rs (5 activation sites),
parser/oracle_casting.rs (3 casting-option sites + 2 casting-restriction sites).

card-data.json is never read for writing and never modified.

GATE. The binary is run over the full current AtomicCards. The base for every
comparison is the snapshot WITH the earlier rounds' parser-fix overlays
(commander eligibility, commander creatures) already applied -- those rounds
changed the same binary, so the honest question is "does this round change
anything beyond its own scope". Every entry whose inputs are unchanged must
come out byte-identical to that base (parse fields only; legalities/
printings/rulings excluded, MTGJSON-April metadata restored for the differing
ones exactly as in recover_dropped.py), EXCEPT the entries the change targets.
For every differing entry the diff is then walked field by field and must
consist ONLY of `condition: null -> {type: Unrecognized, text}` at an
activation_restrictions[].data, casting_restrictions[].data or
casting_options[] node. Any other difference aborts and nothing is written.

Output: data/overlay/unrecognized-restriction-fix.json
    {"meta": {...provenance, gate result, diff census...},
     "cards": {oracle_id: [face entry, ...]}}   # entries as in card-data.json
"""
import collections
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
OUT = os.path.join(DATA, "overlay", "unrecognized-restriction-fix.json")
GEN = os.environ.get("PHASE_ORACLE_GEN",
                     r"C:\source\phase-rs\phase-v0.1.15\target\debug\oracle-gen.exe")
GEN_COMMIT = ("930172dab041798b02d0f7e2b18371b900405569 + local fix "
              "(ParsedCondition::Unrecognized for unparsed restriction text)")
PRIOR_OVERLAYS = [os.path.join(DATA, "overlay", n) for n in
                  ("commander-eligibility-fix.json", "commander-creatures-fix.json")]

META_FIELDS = ("legalities", "printings", "rulings")
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
    name = k if isinstance(k, str) else next(iter(k))
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).capitalize()


def apply_prior(snapshot):
    """snapshot with the earlier rounds' fixed faces substituted in."""
    base = dict(snapshot)
    n = 0
    for path in PRIOR_OVERLAYS:
        doc = json.load(io.open(path, encoding="utf-8"))
        for faces in doc["cards"].values():
            for face in faces:
                base[face["name"].lower()] = face
                n += 1
    return base, n


# ---- diff census -----------------------------------------------------------

def walk_diff(a, b, path, out):
    """Collect (path, a_value, b_value) for every leaf-level difference."""
    if type(a) != type(b):
        out.append((path, a, b))
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append((path + "/" + k, a.get(k, "<absent>"), b.get(k, "<absent>")))
            else:
                walk_diff(a[k], b[k], path + "/" + k, out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append((path, "<len %d>" % len(a), "<len %d>" % len(b)))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                walk_diff(x, y, "%s[%d]" % (path, i), out)
    elif a != b:
        out.append((path, a, b))


ALLOWED = [
    ("activation", re.compile(r"^/abilities\[\d+\]/activation_restrictions\[\d+\]/data/condition$")),
    ("casting_restriction", re.compile(r"^/casting_restrictions\[\d+\]/data/condition$")),
    ("casting_option", re.compile(r"^/casting_options\[\d+\]/condition$")),
]


def classify_diff(d):
    path, a, b = d
    ok = ((a is None or a == "<absent>") and isinstance(b, dict) and b.get("type") == "Unrecognized"
          and isinstance(b.get("text"), str) and b["text"])
    for name, rx in ALLOWED:
        if ok and rx.match(path):
            return name
    return None


def main():
    snapshot = json.load(io.open(os.path.join(DATA, "card-data.json"), encoding="utf-8"))
    atomic = json.load(gzip.open(os.path.join(DATA, "AtomicCards.json.gz"), "rt", encoding="utf-8"))
    base, n_prior = apply_prior(snapshot)
    print(f"base = snapshot + {n_prior} face(s) from earlier parser-fix overlays")

    with tempfile.TemporaryDirectory() as tmp:
        sys.stderr.write("gate: generating the full current AtomicCards\n")
        control = run_gen(atomic["meta"], atomic["data"], tmp)
        tally = {"identical": 0, "identical_after_april_metadata": 0, "different": 0,
                 "excluded_inputs_changed": 0, "excluded_key_reassigned": 0,
                 "excluded_absent": 0}
        differ = []
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
            else:
                differ.append(k)

        rerun, targets_keys = {}, []
        if differ:
            by_face = {}
            for full, faces in atomic["data"].items():
                for f in faces:
                    by_face.setdefault((f.get("faceName") or f["name"]).lower(), (full, []))[1].append(f)
            data = {}
            for k in differ:
                s = one(base[k])
                full, _ = by_face[k]
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
                if k in rerun and parse_part(one(base[k])) == parse_part(one(rerun[k])):
                    tally["identical_after_april_metadata"] += 1
                else:
                    tally["different"] += 1
                    targets_keys.append(k)
        tally["compared"] = (tally["identical"] + tally["identical_after_april_metadata"]
                             + tally["different"])
        print("gate:", json.dumps(tally))

        census = collections.Counter()
        unchanged = []
        offenders = []
        targets = {one(base[k]).get("scryfall_oracle_id") for k in targets_keys}
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
            keys_for_oid = [k for k, s in base.items() if one(s).get("scryfall_oracle_id") == oid]
            for face in faces:
                fk = face["name"].lower()
                orig = one(base[fk if fk in keys_for_oid else keys_for_oid[0]])
                for f in META_FIELDS:
                    if f in orig:
                        face[f] = orig[f]
                    else:
                        face.pop(f, None)
            # STRICT SCOPE CHECK on the bytes that will actually ship: every difference
            # between the base face and the final face must be an allowed
            # null/absent -> Unrecognized condition. (The in-batch rerun is only used
            # to find targets; its April-metadata restoration mangles hybrid colours,
            # e.g. Groundling Pouncer's color_override, so it is not trusted for bytes.)
            changed = False
            for face in faces:
                fk = face["name"].lower()
                diffs = []
                walk_diff({x: v for x, v in one(base[fk]).items() if x not in META_FIELDS},
                          {x: v for x, v in face.items() if x not in META_FIELDS}, "", diffs)
                for d in diffs:
                    changed = True
                    kind = classify_diff(d)
                    if kind:
                        census[kind] += 1
                    else:
                        offenders.append((fk, d))
            if not changed:
                # differed only in the rerun's April-metadata restoration (e.g. the earlier
                # rounds' own overlay faces); byte-identical to the base once regenerated
                unchanged.append(oid)
                continue
            cards[oid] = faces

    if offenders:
        for k, d in offenders[:20]:
            sys.stderr.write(f"UNEXPECTED DIFF {k}: {d}\n")
        sys.exit(f"{len(offenders)} difference(s) outside the declared scope; nothing written")
    if failed:
        sys.exit(f"isolated regeneration mismatch for {len(failed)} card(s): {failed}; nothing written")

    doc = {
        "meta": {
            "what": "cards whose unparsed 'Activate only if' / 'Cast this spell only if' / "
                    "casting-option 'if' text is now kept as ParsedCondition::Unrecognized "
                    "{text} instead of a silent null. Visibility fix: nothing is newly parsed "
                    "and gameplay evaluation is unchanged (Unrecognized evaluates true).",
            "generator": "phase-rs/phase oracle-gen v0.1.15 + local fix",
            "generator_commit": GEN_COMMIT,
            "toolchain": "nightly-2026-04-19 (x86_64-pc-windows-gnu)",
            "fix_location": "crates/engine/src: types/ability.rs (ParsedCondition::Unrecognized), "
                            "parser/oracle_condition.rs (parse_restriction_condition_or_unrecognized), "
                            "game/restrictions.rs, parser/oracle.rs, parser/oracle_casting.rs",
            "gate": tally,
            "diff_census": dict(census),
            "targets": len(targets),
            "rerun_artifacts_identical_after_regeneration": len(unchanged),
            "fixed": len(cards),
            "failed": failed,
        },
        "cards": cards,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print("rerun-flagged faces:", len(targets_keys), "of which unchanged after regeneration:", len(unchanged), "| diff census on shipped faces:", dict(census))
    print(f"fixed {len(cards)}/{len(targets)} -> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
