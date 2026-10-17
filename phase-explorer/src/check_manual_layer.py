#!/usr/bin/env python3
"""Checks for the hand-placement layer: hashes, the flag, reconciliation, identical builds.

    python src/check_manual_layer.py snapshot FILE      # hash every file under the project (not __pycache__, not .git) -> FILE   (run BEFORE any change)
    python src/check_manual_layer.py verify FILE        # compare with a snapshot: only the files this work was allowed to change may differ; nothing may be missing
    python src/check_manual_layer.py flag               # MANUAL_PLACEMENTS off reproduces the build without the layer byte-for-byte; on adds only the new files; two builds are identical
    python src/check_manual_layer.py reconcile          # the corrections file (if any) resolves against the build to a reconciliation that sums to the universe

Frozen = everything that existed in the snapshot except the files listed in ALLOWED (the files this change edits on purpose). The archive, build/, data/ and corrections/ files that existed must be identical.
"""
import hashlib
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as MC

HERE = MC.HERE
NEW_BUILD = ("manual_index.json", "manual_layer.json", "manual_ids_seen.json", "manual_suggestions.json", "keyword_facet.json", "hand_group_hits.json", "sibling_placements.json", "sibling_ledger.json", "manual_fallback.json")
NEW_REPORTS = ("manual-placements.md", "hand-groups.md")
ALLOWED = {"src/test_manual_browser.py", "reports/abilityfind.js", "src/test_abilityfind.py", "src/serve.py", "src/check_manual_layer.py", "src/manual_common.py", "src/build_manual_layer.py", "src/build_manual_suggestions.py", "src/manual_batch.py", "src/test_batch_browser.py", "src/test_batch_logic.py", "corrections/hand_groups.json", "src/build_text_suggestions.py", "src/test_hand_group_browser.py", "src/test_text_suggestions.py", "src/test_text_browser.py", "reports/manualedit.js", "src/serve.py", "reports/browse.html", "reports/abilityfind.js", "src/test_abilityfind.py", "TESTER_NOTE.md", "KNOWN_LIMITATIONS.md", "README.md", "src/check_tester_note.py"}


def manifest():
    m = {}
    for d, ds, fs in os.walk(HERE):
        ds[:] = [x for x in ds if x not in ("__pycache__", ".git", "node_modules")]
        for f in fs:
            p = os.path.join(d, f)
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for b in iter(lambda: fh.read(1 << 20), b""):
                    h.update(b)
            m[os.path.relpath(p, HERE).replace(os.sep, "/")] = h.hexdigest()
    return m


def is_new(rel):
    return (is_text(rel) or (rel.startswith("build/") and rel[6:] in NEW_BUILD) or (rel.startswith("reports/") and rel[8:] in NEW_REPORTS) or rel in ("corrections/hand_groups.json", "corrections/hand_groups.json.bak")
            or rel in ("src/manual_common.py", "src/build_manual_layer.py", "src/build_manual_suggestions.py", "reports/manualedit.js", "src/check_manual_layer.py", "src/test_manual_endpoint.py", "src/test_manual_logic.py",
                       "src/test_manual_browser.py", "src/test_manual_find.py", "src/build_keyword_facet.py", "src/hand_groups.py", "src/build_hand_groups.py", "src/build_sibling.py", "src/test_keyword_facet.py",
                       "src/test_hand_groups.py", "src/test_sibling.py", "src/test_features_browser.py", "src/manual_batch.py", "src/test_batch_endpoint.py", "src/test_batch_logic.py", "src/test_batch_browser.py", "src/test_batch_find.py", "src/build_text_suggestions.py", "src/test_text_suggestions.py", "src/test_text_browser.py", "src/test_hand_group_browser.py", "reports/text-suggestions.md"))


def is_text(rel):
    return rel.startswith("build/text_sug/") or rel == "reports/text-suggestions.md"


def run(args, env=None):
    r = subprocess.run([sys.executable] + args, cwd=HERE, capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8", **(env or {})))
    return r.returncode, r.stdout + r.stderr


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fails = []

    def check(name, ok, detail=""):
        print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" - " + str(detail)) if detail else ""))
        if not ok:
            fails.append(name)
    if cmd == "snapshot":
        m = manifest()
        json.dump(m, open(sys.argv[2], "w"), indent=0, sort_keys=True)
        print("snapshot of %d files -> %s" % (len(m), sys.argv[2]))
        return
    if cmd == "verify":
        before, now = json.load(open(sys.argv[2])), manifest()
        changed = sorted(k for k in before if k in now and before[k] != now[k])
        missing = sorted(k for k in before if k not in now)
        added = sorted(k for k in now if k not in before)
        regen = [k for k in changed if is_new(k) and k.startswith(("build/", "reports/manual-", "reports/hand-", "reports/text-"))]       # this work's own generated files, rebuilt on purpose
        bad = [k for k in changed if k not in ALLOWED and k not in regen]
        check("every file that existed before still exists (%d files)" % len(before), not missing, missing[:5])
        check("no frozen file changed (archive, build, data, corrections, every other source file)", not bad, bad[:10])
        print("   edited on purpose (%d): %s" % (len(changed) - len(regen), ", ".join(k for k in changed if k not in regen)))
        print("   regenerated (this work's own build files, %d): %s" % (len(regen), ", ".join(regen)))
        unexpected = [k for k in added if not is_new(k)]
        check("every added file is one of the new hand-placement files", not unexpected, unexpected[:10])
        print("   added (%d): %s" % (len(added), ", ".join(added)))
        real = "corrections/manual_placements.json"
        if real in before:
            check("the real hand-placement file (your edits) is byte-identical", before[real] == now.get(real) and before.get(real + ".bak") == now.get(real + ".bak"))
        arch = [k for k in before if k.startswith("archive/")]
        check("the archive is byte-identical (%d files)" % len(arch), all(before[k] == now.get(k) for k in arch))
        check("reports/findcard.js is byte-identical", before["reports/findcard.js"] == now["reports/findcard.js"])
        for k in ("build/ability_taxonomy.json", "build/ability_taxonomy_lookup.json", "build/tentative_placements.json", "build/annotation_placements.json", "build/tag_placements.json", "build/loose_groups.json"):
            check("generated file byte-identical: " + k, before[k] == now[k])
    elif cmd == "flag":
        base = {k: v for k, v in manifest().items() if not is_new(k) and not k.startswith("corrections/manual_placements")}
        layers = [("manual layer", "build_manual_layer", "MANUAL_PLACEMENTS", "src/build_manual_layer.py"), ("hand groups", "build_hand_groups", "HAND_GROUPS", "src/build_hand_groups.py"),
                  ("keyword facet", "build_keyword_facet", "KEYWORD_FACET", "src/build_keyword_facet.py")]
        sug_before = manifest().get("build/manual_suggestions.json")
        for label, mod, flag, script in layers:
            rc, out = run(["-c", "import sys; sys.path.insert(0, 'src'); import %s as B; B.%s = False; B.main()" % (mod, flag)])
            print("   %s flag off: %s" % (label, out.strip().splitlines()[-1] if out.strip() else rc))
        off = manifest()
        gone = [k for k in off if k.startswith("build/manual_") or k in ("build/keyword_facet.json", "build/hand_group_hits.json", "reports/manual-placements.md", "reports/hand-groups.md")]
        check("flags off: no file of these layers is left in build/ or reports/", not gone, gone)
        check("flags off: every other file is byte-identical to the build without them", all(off.get(k) == v for k, v in base.items()) and not [k for k in off if k not in base and not is_new(k) and not k.startswith("corrections/manual_placements")])
        for label, mod, flag, script in [layers[2], layers[1], layers[0]]:             # facet first (the hand groups read it), the manual layer last
            rc, out = run([script])
            check("flag on: %s builds" % label, rc == 0, out.strip().splitlines()[-1][:90] if out.strip() else "")
        on = manifest()
        check("flags on: existing files unchanged (only this work's files added)", all(on.get(k) == v for k, v in base.items()))
        names = [k for k in on if k in ["build/" + n for n in ("keyword_facet.json", "hand_group_hits.json", "manual_index.json", "manual_layer.json", "manual_ids_seen.json")] or k in ("reports/manual-placements.md", "reports/hand-groups.md")]
        run(["src/build_keyword_facet.py"]); run(["src/build_hand_groups.py"]); run(["src/build_manual_layer.py"])
        run(["src/build_manual_suggestions.py"])
        on2 = manifest()
        check("the suggestions file (rebuilt after the flags came back on) is byte-identical to the one before", on2.get("build/manual_suggestions.json") == sug_before)
        check("a second build of each is byte-identical (%d files: facet, hand-group hits and report, manual index / layer / ids / report)" % len(names), all(on[k] == on2[k] for k in names), [k for k in names if on[k] != on2[k]])
    elif cmd == "batchflag":
        # python src/check_manual_layer.py batchflag BEFORE.json : BATCH_ACTIONS off must leave every output byte-identical to the build before batch actions existed (BEFORE.json = a snapshot from then)
        before = json.load(open(sys.argv[2]))
        keys = ["build/manual_index.json", "build/manual_layer.json", "build/manual_ids_seen.json", "reports/manual-placements.md", "build/manual_suggestions.json"]
        on = manifest()
        rc, out = run(["-c", "import sys; sys.path.insert(0, 'src'); import build_manual_layer as L; L.BATCH_ACTIONS = False; L.main(); import build_manual_suggestions as S; S.main()"])
        print("   flag off:", out.strip().splitlines()[-1][:100] if out.strip() else rc)
        off = manifest()
        check("flag off: the manual index, layer, ids, report and suggestions are byte-identical to the build before batch actions", all(off.get(k) == before.get(k) for k in keys), [k for k in keys if off.get(k) != before.get(k)])
        check("flag off: no fallback file", "build/manual_fallback.json" not in off)
        check("flag off: every other file (all that existed before) is byte-identical to before", all(off.get(k) == v for k, v in before.items() if not is_new(k) and not k.startswith("corrections/manual_placements") and k not in ALLOWED and k != "reports/manualedit.js"),
              [k for k, v in before.items() if off.get(k) != v and not is_new(k) and k not in ALLOWED][:5])
        check("flag off: the real corrections file and its backup are byte-identical", all(off.get(k) == before.get(k) for k in ("corrections/manual_placements.json", "corrections/manual_placements.json.bak")))
        rc, out = run(["-c", "import sys; sys.path.insert(0, 'src'); import build_manual_layer as L; L.main(); import build_manual_suggestions as S; S.main()"])
        on2 = manifest()
        check("flag on again: the files with batch fields come back byte-identical to the build before the flag was turned off", all(on2.get(k) == on.get(k) for k in keys + ["build/manual_fallback.json"]), [k for k in keys + ["build/manual_fallback.json"] if on2.get(k) != on.get(k)])
        rc, out = run(["-c", "import sys; sys.path.insert(0, 'src'); import build_manual_layer as L; L.main(); import build_manual_suggestions as S; S.main()"])
        on3 = manifest()
        check("two builds in a row with the flag on are byte-identical (index, layer, ids, report, suggestions, fallback)", all(on3.get(k) == on2.get(k) for k in keys + ["build/manual_fallback.json"]))
    elif cmd == "textflag":
        # python src/check_manual_layer.py textflag BEFORE.json : TEXT_SUGGESTIONS off must leave every other file byte-identical to BEFORE.json (a snapshot from before text suggestions existed); on again, two builds are identical
        before = json.load(open(sys.argv[2]))
        on = manifest()
        rc, out = run(["-c", "import sys; sys.path.insert(0, 'src'); import build_text_suggestions as T; T.TEXT_SUGGESTIONS = False; T.main()"])
        print("   flag off:", out.strip().splitlines()[-1][:100] if out.strip() else rc)
        off = manifest()
        check("flag off: no text-suggestion file is left (build/text_sug, reports/text-suggestions.md)", not [k for k in off if is_text(k)], [k for k in off if is_text(k)][:3])
        frozen = {k: v for k, v in before.items() if not is_new(k) and k not in ALLOWED and k != "reports/manualedit.js"}
        check("flag off: every file of the snapshot that this work may not edit is byte-identical (%d files)" % len(frozen), all(off.get(k) == v for k, v in frozen.items()), [k for k, v in frozen.items() if off.get(k) != v][:5])
        keep = [k for k in before if k.startswith("build/") and not is_text(k)]
        check("flag off: the other generated files are byte-identical (%d build files)" % len(keep), all(off.get(k) == before[k] for k in keep), [k for k in keep if off.get(k) != before[k]][:5])
        check("flag off: the real corrections file and its backup are byte-identical", all(off.get(k) == before.get(k) for k in ("corrections/manual_placements.json", "corrections/manual_placements.json.bak")))
        check("flag off: no file was added outside the new-file list", not [k for k in off if k not in before and not is_new(k)])
        rc, out = run(["src/build_text_suggestions.py"])
        on2 = manifest()
        tk = sorted(k for k in on2 if is_text(k))
        check("flag on again: %d text-suggestion files come back byte-identical to the build before the flag was turned off" % len(tk), bool(tk) and all(on2.get(k) == on.get(k) for k in tk) and sorted(k for k in on if is_text(k)) == tk)
        rc, out = run(["src/build_text_suggestions.py"])
        on3 = manifest()
        check("two builds in a row are byte-identical (%d files)" % len(tk), all(on3.get(k) == on2.get(k) for k in tk))
    elif cmd == "enginev2":
        # python src/check_manual_layer.py enginev2 BEFORE.json : BEFORE.json = a snapshot taken before ENGINE_V2 existed. Builds go to temporary directories (TEXT_SUG_OUT), never over the real build/text_sug.
        # ENGINE_V2 off must reproduce the pre-V2 text files byte for byte; on, two builds are identical, match the real build/text_sug, and keep every row at 0.70 or more and the first row at 0.90 or more of every card.
        import tempfile
        before = json.load(open(sys.argv[2]))
        tmp = tempfile.mkdtemp(prefix="enginev2_")

        def build(flag, name):
            out = os.path.join(tmp, name)
            rc, text = run(["-c", "import sys; sys.path.insert(0, 'src'); import build_text_suggestions as T; T.ENGINE_V2 = %s; T.main()" % flag], env={"TEXT_SUG_OUT": out})
            return out, rc

        def tree(d):
            m = {}
            for dd, ds, fs in os.walk(d):
                for f in fs:
                    pth = os.path.join(dd, f)
                    m[os.path.relpath(pth, d).replace(os.sep, "/")] = hashlib.sha256(open(pth, "rb").read()).hexdigest()
            return m
        off, rc0 = build(False, "off")
        t_off = tree(off)
        want = {k[len("build/text_sug/"):]: v for k, v in before.items() if k.startswith("build/text_sug/")}
        want["text-suggestions.md"] = before.get("reports/text-suggestions.md")
        check("ENGINE_V2 off: the build reproduces the %d text-suggestion files from before ENGINE_V2 byte for byte" % len(want), rc0 == 0 and t_off == want, [k for k in set(want) | set(t_off) if want.get(k) != t_off.get(k)][:5])
        on1, rc1 = build(True, "on1")
        on2, rc2 = build(True, "on2")
        t1, t2 = tree(on1), tree(on2)
        check("ENGINE_V2 on: two builds are byte-identical (%d files)" % len(t1), rc1 == 0 and rc2 == 0 and t1 == t2, [k for k in set(t1) | set(t2) if t1.get(k) != t2.get(k)][:5])
        real = tree(os.path.join(HERE, "build", "text_sug"))
        real["text-suggestions.md"] = hashlib.sha256(open(os.path.join(HERE, "reports", "text-suggestions.md"), "rb").read()).hexdigest()
        check("ENGINE_V2 on: the build equals the files in build/text_sug", t1 == real, [k for k in set(t1) | set(real) if t1.get(k) != real.get(k)][:5])
        qa = json.load(io.open(os.path.join(off, "queue.json"), encoding="utf-8"))["cards"]
        qb = json.load(io.open(os.path.join(on1, "queue.json"), encoding="utf-8"))["cards"]
        first = lambda rows, th: next((r[0] for r in rows if r[1] >= th), None)
        check("ENGINE_V2: the first row at or above 0.90 is the same for all %d queue cards (what is ticked is unchanged)" % len(qa), all(first(qa[o], 0.9) == first(qb[o], 0.9) for o in qa))
        check("ENGINE_V2: the rows at or above 0.70 are the same set for every queue card (the batch view's review band is unchanged)", all({r[0] for r in qa[o] if r[1] >= 0.7} == {r[0] for r in qb[o] if r[1] >= 0.7} for o in qa))
        gone = [r[1] for o in qa for r in qa[o] if r[2] != "kw" and r[0] not in {x[0] for x in qb[o]}]
        check("ENGINE_V2: a row that leaves the stored 7 is a keyword row or scores below 0.30 (%d rows leave)" % len(gone), all(x < 0.30 for x in gone), max(gone) if gone else 0)
    elif cmd == "reconcile":
        idx = MC.load_index()
        doc = MC.load_doc()
        res = MC.resolve(idx, doc)
        r = res["reconciliation"]
        check("reconciliation sums to the universe", r["sum"] == len(idx["cards"]) == 38921, r)
        check("the generated parts equal the six-figure basis (27,590 / 2,093 / 960 / 1,205 / 5,738)", (r["placed"], r["tentative"], r["annotation"], r["tag"], r["not_cards"]) == (27590, 2093, 960, 1205, 5738))
        print("   counts:", res["counts"])
    else:
        print(__doc__)
        sys.exit(2)
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
