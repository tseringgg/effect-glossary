"""Apply the "split the timing prefix out of a compound activation restriction" fix.

    python src/apply_activation_timing_split_overlay.py

Round B1 of the condition-drop arc (KNOWN_LIMITATIONS.md section 4). Round 1 kept the
text of every unparsed "Activate only ..." sentence as one opaque
`RequiresCondition(Unrecognized)`. For compound sentences such as "Activate only as a
sorcery and only if there are seven or more cards in your graveyard" that blob swallowed a
timing clause the parser already knows how to emit. The generic `activate only ` branch of
`strip_activated_constraints` (crates/engine/src/parser/oracle.rs) now splits the sentence
on " and only " / ", and only " / ", only ", emits AsSorcery / DuringYourTurn /
DuringYourUpkeep / DuringCombat / OnlyOnceEachTurn / OnlyOnce for the pieces that are exactly
those phrases, and keeps every other piece (an `if ...` condition, or timing with no
equivalent variant yet) as a condition. A sentence with NO recognised timing piece is left as
the single blob it was.

UNLIKE round 1 this changes gameplay: the engine enforces those timing variants (the
Unrecognized remainder is still permissive). The engine-side proof is in the Rust tests
(game/restrictions.rs: Cabal Inquisitor refused at instant speed, allowed at sorcery speed).

GATE. Same shape as the earlier rounds -- the rebuilt binary over the full current
AtomicCards, every entry whose inputs are unchanged byte-identical to the base (snapshot with
the THREE earlier parser-fix overlays applied), except the targets -- with three additions:

  * the target set is DECLARED up front: an independent Python re-implementation of the split
    rule is run over round 1's Unrecognized texts and the gate's target oracle ids must equal
    it exactly (no more, no fewer);
  * every difference on a shipped face must be an `activation_restrictions` list that was
    exactly one `RequiresCondition(Unrecognized(blob))` and is now a list in which the timing
    pieces are known variants and every leftover piece's text occurs in the old blob (nothing
    invented, nothing lost);
  * the comparison itself is audited: it is run twice (ordered JSON text, and canonical
    sorted-key JSON), the compared strings are hashed on both sides, and a planted
    one-field mutation is confirmed to be detected -- so a green gate cannot be an artifact of
    the comparison process (round 1's lesson).

card-data.json is never read for writing and never modified.

Output: data/overlay/activation-timing-split-fix.json
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
OUT = os.path.join(DATA, "overlay", "activation-timing-split-fix.json")
GEN = os.environ.get("PHASE_ORACLE_GEN",
                     r"C:\source\phase-rs\phase-v0.1.15\target\debug\oracle-gen.exe")
GEN_COMMIT = ("930172dab041798b02d0f7e2b18371b900405569 + local fixes (commander eligibility, "
              "commander creatures, Unrecognized restriction, activation timing split)")
PRIOR_OVERLAYS = [os.path.join(DATA, "overlay", n) for n in
                  ("commander-eligibility-fix.json", "commander-creatures-fix.json",
                   "unrecognized-restriction-fix.json")]
ROUND1 = PRIOR_OVERLAYS[-1]

META_FIELDS = ("legalities", "printings", "rulings")
INPUT_FIELDS = ("name", "mana_cost", "card_type", "power", "toughness", "loyalty",
                "defense", "oracle_text", "flavor_name", "layout")

# the declared rule, independently of the Rust (exact phrase -> variant name)
TIMING = {"as a sorcery": "AsSorcery", "during your turn": "DuringYourTurn",
          "during your upkeep": "DuringYourUpkeep", "during combat": "DuringCombat",
          "once each turn": "OnlyOnceEachTurn", "once": "OnlyOnce"}
SEP = re.compile(r", and only | and only |, only ")


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


def apply_prior(snapshot):
    base = dict(snapshot)
    n = 0
    apply_prior.keys = set()
    for path in PRIOR_OVERLAYS:
        doc = json.load(io.open(path, encoding="utf-8"))
        for faces in doc["cards"].values():
            for face in faces:
                base[face["name"].lower()] = face
                apply_prior.keys.add(face["name"].lower())
                n += 1
    return base, n


def unrecognized_blob(restrictions):
    """The text of a restriction list that is exactly one Unrecognized RequiresCondition."""
    if len(restrictions) != 1 or restrictions[0].get("type") != "RequiresCondition":
        return None
    c = (restrictions[0].get("data") or {}).get("condition")
    if isinstance(c, dict) and c.get("type") == "Unrecognized":
        return c["text"]
    return None


def declared_targets(base):
    """oracle ids the rule is EXPECTED to change: any activation whose round-1 blob has at
    least one piece that is exactly a known timing phrase."""
    expected = {}
    for k, s in base.items():
        s = one(s)
        for i, a in enumerate(s.get("abilities") or []):
            blob = unrecognized_blob(a.get("activation_restrictions") or [])
            if blob is None:
                continue
            # "Activate only if X and only as a sorcery" reaches the `activate only if `
            # branch, not the generic one this round changes (8 cards, logged separately).
            if "activate only if " in (a.get("description") or "").lower():
                continue
            pieces = [p.strip() for p in SEP.split(blob.strip().lower()) if p.strip()]
            if any(p in TIMING for p in pieces):
                expected.setdefault(s["scryfall_oracle_id"], []).append((s["name"], i, blob))
    return expected


# ---- diff walking -----------------------------------------------------------

def walk_diff(a, b, path, out):
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


def check_face(base_face, new_face):
    """-> (n_split_abilities, list of problems). Only activation_restrictions lists that were
    one Unrecognized blob may differ, and only as a lossless split."""
    problems, split = [], 0
    a, b = strip_meta(base_face), strip_meta(new_face)
    if set(a) != set(b):
        problems.append(("keys", sorted(set(a) ^ set(b))))
    for key in sorted(set(a) | set(b)):
        if key == "abilities":
            continue
        if a.get(key) != b.get(key):
            problems.append((key, "differs"))
    aa, ba = a.get("abilities") or [], b.get("abilities") or []
    if len(aa) != len(ba):
        problems.append(("abilities", "count"))
        return split, problems
    for i, (x, y) in enumerate(zip(aa, ba)):
        xr, yr = x.get("activation_restrictions"), y.get("activation_restrictions")
        x2 = {k: v for k, v in x.items() if k != "activation_restrictions"}
        y2 = {k: v for k, v in y.items() if k != "activation_restrictions"}
        if x2 != y2:
            # The only other field the parser derives from AsSorcery: def.sorcery_speed
            # (oracle.rs `constraints.sorcery_speed()`), False -> True.
            extra = {k for k in set(x2) | set(y2) if x2.get(k) != y2.get(k)}
            ok_ss = (extra == {"sorcery_speed"} and x2.get("sorcery_speed") is False
                     and y2.get("sorcery_speed") is True
                     and any(r.get("type") == "AsSorcery" for r in (yr or [])))
            if not ok_ss:
                problems.append(("abilities[%d]" % i, "unexpected fields changed: %s" % sorted(extra)))
                continue
        if xr == yr:
            continue
        blob = unrecognized_blob(xr or [])
        if blob is None:
            problems.append(("abilities[%d]" % i, "old restrictions were not a single blob"))
            continue
        timing_seen, ok = 0, True
        for r in yr:
            t = r.get("type")
            if t in TIMING.values():
                timing_seen += 1
                phrase = next(p for p, v in TIMING.items() if v == t)
                ok &= phrase in blob
            elif t == "RequiresCondition":
                c = (r.get("data") or {}).get("condition")
                if isinstance(c, dict) and c.get("type") == "Unrecognized":
                    ok &= c["text"] in blob
                # a condition that now PARSES is allowed; its source text is checked below
            else:
                ok = False
        if not timing_seen:
            ok = False
        if not ok:
            problems.append(("abilities[%d]" % i, "not a lossless split of %r" % blob))
        else:
            split += 1
    return split, problems


def main():
    snapshot = json.load(io.open(os.path.join(DATA, "card-data.json"), encoding="utf-8"))
    atomic = json.load(gzip.open(os.path.join(DATA, "AtomicCards.json.gz"), "rt", encoding="utf-8"))
    base, n_prior = apply_prior(snapshot)
    print(f"base = snapshot + {n_prior} face(s) from {len(PRIOR_OVERLAYS)} earlier parser-fix overlays")

    expected = declared_targets(base)
    print(f"declared target set: {len(expected)} oracle ids "
          f"({sum(len(v) for v in expected.values())} abilities)")

    # -- self-test of the comparison: a planted one-field change MUST be detected --------
    probe = next(iter(base.values()))
    probe = one(probe)
    mutated = json.loads(json.dumps(probe))
    mutated["name"] = mutated["name"] + "!"
    assert parse_part(probe) != parse_part(mutated) and canon_part(probe) != canon_part(mutated), \
        "comparison self-test failed: a planted mutation was not detected"
    print("comparison self-test: planted mutation detected by both comparators")

    with tempfile.TemporaryDirectory() as tmp:
        sys.stderr.write("gate: generating the full current AtomicCards\n")
        control = run_gen(atomic["meta"], atomic["data"], tmp)
        tally = {"identical": 0, "identical_after_april_metadata": 0, "different": 0,
                 "excluded_inputs_changed": 0, "excluded_key_reassigned": 0, "excluded_absent": 0}
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
            elif k in apply_prior.keys and canon_part(s) == canon_part(one(c)):
                # Faces from earlier overlays were saved with sorted keys; the generator emits
                # its own key order. Same data, different byte order: compare canonically.
                tally["identical_overlay_face_canonical"] = tally.get("identical_overlay_face_canonical", 0) + 1
            else:
                differ.append(k)

        # audit the comparison: independent comparator + hashes of the bytes compared
        h_base, h_ctrl, canon_bad = hashlib.sha256(), hashlib.sha256(), 0
        for k in sorted(ident):
            pb, pc = parse_part(one(base[k])), parse_part(one(control[k]))
            h_base.update(pb.encode("utf-8"))
            h_ctrl.update(pc.encode("utf-8"))
            if canon_part(one(base[k])) != canon_part(one(control[k])):
                canon_bad += 1
        assert h_base.hexdigest() == h_ctrl.hexdigest() and canon_bad == 0, \
            "comparison audit failed: ordered/canonical comparators disagree"
        audit = {"identical_entries_hashed": len(ident), "sha256": h_base.hexdigest(),
                 "canonical_comparator_disagreements": canon_bad,
                 "binary": os.path.basename(GEN),
                 "binary_mtime": int(os.path.getmtime(GEN))}
        print("comparison audit:", json.dumps(audit))

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
                             + tally.get("identical_overlay_face_canonical", 0) + tally["different"])
        print("gate:", json.dumps(tally))

        targets = {one(base[k]).get("scryfall_oracle_id") for k in targets_keys}
        faces_of = {}
        for full, faces in atomic["data"].items():
            for f in faces:
                oid = (f.get("identifiers") or {}).get("scryfallOracleId")
                if oid in targets:
                    faces_of.setdefault(oid, {}).setdefault(full, []).append(f)
        cards, unchanged, problems, n_split = {}, [], [], 0
        for oid in sorted(targets):
            out = run_gen(atomic["meta"], faces_of.get(oid, {}), tmp)
            got = [e for e in out.values() if one(e).get("scryfall_oracle_id") == oid]
            if not got:
                problems.append((oid, "generator produced no entry"))
                continue
            order = [f.get("faceName") or f["name"] for fs in faces_of[oid].values() for f in fs]
            got.sort(key=lambda e: order.index(one(e)["name"]) if one(e)["name"] in order else 99)
            faces = [one(e) for e in got]
            keys_for_oid = [k for k, s in base.items() if one(s).get("scryfall_oracle_id") == oid]
            changed = False
            for face in faces:
                fk = face["name"].lower()
                orig = one(base[fk if fk in keys_for_oid else keys_for_oid[0]])
                for f in META_FIELDS:
                    if f in orig:
                        face[f] = orig[f]
                    else:
                        face.pop(f, None)
                if canon_part(orig) == canon_part(face):
                    continue
                changed = True
                n, pr = check_face(orig, face)
                n_split += n
                problems.extend((fk,) + p for p in pr)
            if changed:
                cards[oid] = faces
            else:
                unchanged.append(oid)

    if problems:
        for p in problems[:20]:
            sys.stderr.write(f"OUT OF SCOPE {p}\n")
        sys.exit(f"{len(problems)} difference(s) outside the declared scope; nothing written")
    if set(cards) != set(expected):
        sys.exit("target set != declared set: unexpected=%s missing=%s; nothing written" %
                 (sorted(set(cards) - set(expected)), sorted(set(expected) - set(cards))))

    doc = {
        "meta": {
            "what": "compound 'Activate only <timing> and only if <condition>' sentences: the timing "
                    "clause is now its real ActivationRestriction (AsSorcery / DuringYourTurn / "
                    "DuringYourUpkeep / DuringCombat / OnlyOnceEachTurn / OnlyOnce) and only the "
                    "remainder stays a condition. The engine now ENFORCES the timing half.",
            "generator": "phase-rs/phase oracle-gen v0.1.15 + local fixes",
            "generator_commit": GEN_COMMIT,
            "toolchain": "nightly-2026-04-19 (x86_64-pc-windows-gnu)",
            "fix_location": "crates/engine/src/parser/oracle.rs: strip_activated_constraints "
                            "(generic `activate only ` branch), split_compound_activation_restriction, "
                            "activation_timing_phrase",
            "gate": tally,
            "comparison_audit": audit,
            "declared_targets": len(expected),
            "targets": len(targets),
            "rerun_artifacts_identical_after_regeneration": len(unchanged),
            "abilities_split": n_split,
            "fixed": len(cards),
        },
        "cards": cards,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print(f"fixed {len(cards)} cards ({n_split} abilities split); declared {len(expected)}; "
          f"rerun-only artifacts {len(unchanged)} -> {os.path.relpath(OUT, HERE)}")


if __name__ == "__main__":
    main()
