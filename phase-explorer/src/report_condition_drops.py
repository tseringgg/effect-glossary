#!/usr/bin/env python3
"""Turn build/condition_drops.json into reports/condition-drops.md.

Counting conventions (same discipline as the gap-closing rounds):
  cards       distinct oracle ids with >= 1 flagged item in that shape
  silent      the card shows fully clean by every existing signal
              (index quality clean, 0 soft gaps, 0 corrections)
  sole-cause  silent cards whose EVERY flagged item is in this shape, i.e.
              fixing this shape alone would clear the card of detected drops
  sole-shape  same, but visible-gap cards are allowed
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect_condition_drops as D  # noqa: E402

HERE = D.HERE


def main():
    hits = json.load(open(os.path.join(HERE, "build", "condition_drops.json"), encoding="utf-8"))
    by_card = collections.defaultdict(list)
    for h in hits:
        by_card[h["oid"]].append(h)
    silent = {o for o, hs in by_card.items() if not any(h["card_visible"] for h in hs)}

    def stats(sel):
        cards = {h["oid"] for h in sel}
        sole = sole_shape = 0
        for o in cards:
            allsel = by_card[o]
            ids = {id(h) for h in sel}
            if all(id(h) in ids for h in allsel):
                sole_shape += 1
                if o in silent:
                    sole += 1
        return dict(items=len(sel), cards=len(cards), silent=len(cards & silent),
                    sole=sole, sole_shape=sole_shape)

    out = []
    w = out.append
    n_cards = len(by_card)
    w("# Silent condition drops -- corpus-wide sizing\n")
    w("Detection and sizing only (KNOWN_LIMITATIONS.md section 4). Detector: "
      "`src/detect_condition_drops.py`; classifier: `src/size_condition_drops.py`; "
      "raw hits: `build/condition_drops.json`.\n")
    w("## Headline\n")
    tierA = sum(h["tier"] == "A" for h in hits)
    w("| measure | value |\n|---|---:|")
    w(f"| flagged items | **{len(hits):,}** (tier A {tierA:,}, tier B {len(hits) - tierA:,}) |")
    w(f"| distinct cards (oracle ids) | **{n_cards:,}** |")
    w(f"| ...of which fully `clean` by every existing signal (invisible) | **{len(silent):,}** |")
    w(f"| ...of which already carry a visible gap/flag elsewhere | {n_cards - len(silent):,} |")
    alch = {o for o, hs in by_card.items() if all(h["alchemy"] for h in hs)}
    rec = {o for o, hs in by_card.items() if any(h["recovered"] for h in hs)}
    w(f"| cards that are Alchemy `A-` rebalances only | {len(alch):,} |")
    w(f"| cards from the collision-recovered overlay | {len(rec):,} |")
    w(f"| cards excluding `A-` | {n_cards - len(alch):,} (silent {len(silent - alch):,}) |")
    w("")
    w("By bucket (items): " + ", ".join(
        f"{b} {c:,}" for b, c in collections.Counter(h["bucket"] for h in hits).most_common()) + "\n")

    shapes = collections.defaultdict(list)
    for h in hits:
        shapes[h["shape"]].append(h)
    w("## Sub-shapes, ranked by cards\n")
    w("| rank | sub-shape | items | cards | silent cards | sole-cause (silent) | sole-shape |")
    w("|---:|---|---:|---:|---:|---:|---:|")
    ranked = sorted(shapes.items(), key=lambda kv: (-stats(kv[1])["cards"], kv[0]))
    for r, (s, sel) in enumerate(ranked, 1):
        st = stats(sel)
        w(f"| {r} | {s} | {st['items']:,} | {st['cards']:,} | {st['silent']:,} | "
          f"{st['sole']:,} | {st['sole_shape']:,} |")
    w("")
    w("## Sub-shape detail\n")
    for s, sel in ranked:
        w(f"### {s}\n")
        subs = collections.defaultdict(list)
        for h in sel:
            subs[h["sub"]].append(h)
        w("| variant | items | cards | silent cards | sole-cause |")
        w("|---|---:|---:|---:|---:|")
        for sub, ss in sorted(subs.items(), key=lambda kv: -len({h['oid'] for h in kv[1]})):
            st = stats(ss)
            w(f"| {sub} | {st['items']:,} | {st['cards']:,} | {st['silent']:,} | {st['sole']:,} |")
        ex = sorted({(h["name"]) for h in sel if h["oid"] in silent and not h["alchemy"]})[:6]
        w("\nExamples (silent): " + ", ".join(ex) + "\n")
    strict = {o for o in silent if not any(h["card_soft"] for h in by_card[o])}
    w("## Validation against the original 50-card spot-check\n")
    base = json.load(open(os.path.join(HERE, "..", "cond_sample.json"), encoding="latin-1"))
    hk = {(h["oid"], h["bucket"], h["idx"]): h for h in hits}
    got = [hk[(o, b, i)] for o, n, b, i in base if (o, b, i) in hk]
    w(f"The 50 sampled items (`cond_sample.json`): detector flags **{len(got)}** and clears "
      f"**{50 - len(got)}**; section 4 recorded 28 real / 22 false positive. Of the {len(got)} "
      f"flagged, **{sum(not h['card_visible'] for h in got)} silent** (card shows `clean`) and "
      f"**{sum(h['card_visible'] for h in got)} with a visible gap elsewhere** "
      f"(section 4: 20 / 8).\n")
    w(f"Stricter silent (also no soft-gap/unmodelled node, no correction): {len(strict):,} cards.\n")
    # ---- round-1 resolution log: the same detector, before vs after the overlay --------
    import size_condition_drops as S
    ovl = json.load(open(os.path.join(HERE, "data", "overlay", "unrecognized-restriction-fix.json"),
                         encoding="utf-8"))
    def nested_stats(without):
        uni, idx = S.load_universe(without=without)
        hs = []
        for key, e in uni.items():
            for h in D.detect_entry(e):
                shape, _ = S.classify(h, e[h["bucket"]][h["idx"]])
                ir = idx.get(key)
                vis = (ir["q"] != "clean") if ir else D.entry_has_gap(e)
                hs.append((e.get("scryfall_oracle_id"), shape, vis))
        per = collections.defaultdict(list)
        for oid, shape, vis in hs:
            per[oid].append((shape, vis))
        nw = {o for o, v in per.items() if any(s == "nested-wrapper" for s, _ in v)}
        silent_nw = {o for o in nw if not any(vis for _, vis in per[o])}
        sole = {o for o in silent_nw if all(s == "nested-wrapper" for s, _ in per[o])}
        return dict(items=sum(s == "nested-wrapper" for _, s, _ in hs), cards=len(nw),
                    silent=len(silent_nw), sole=len(sole), total_items=len(hs), total_cards=len(per)), nw
    before, nw_before = nested_stats(("unrecognized-restriction-fix",))
    after, nw_after = nested_stats(())
    still = sorted(o for o in nw_before if o in {h["oid"] for h in hits})
    w("## Round 1 -- nested-wrapper: a VISIBILITY fix, not a resolution\n")
    w("`parse_restriction_condition` returns `None` for any restriction text outside its closed "
      "vocabulary and the engine evaluates `None` as permissive-true; the `RequiresCondition` wrapper was "
      "built regardless, so the condition text was discarded. The fix (overlay "
      "`data/overlay/unrecognized-restriction-fix.json`, new `ParsedCondition::Unrecognized { text }`, "
      "evaluated `true` exactly like the `None` it replaces) keeps the real text. **Zero cards are newly "
      "parsed**; nothing about gameplay evaluation changes.\n")
    w("| nested-wrapper, same detector | before | after |\n|---|---:|---:|")
    w(f"| flagged items | {before['items']} | {after['items']} |")
    w(f"| cards | {before['cards']} | {after['cards']} |")
    w(f"| silent cards (`clean` label) | {before['silent']} | {after['silent']} |")
    w(f"| sole-cause silent cards | {before['sole']} | {after['sole']} |")
    w(f"| whole corpus, flagged items | {before['total_items']} | {after['total_items']} |")
    w(f"| whole corpus, flagged cards | {before['total_cards']} | {after['total_cards']} |\n")
    m = ovl["meta"]
    w(f"The overlay carries **{m['fixed']} cards / {sum(m['diff_census'].values())} condition nodes** "
      f"({m['diff_census']['activation']} activation, {m['diff_census']['casting_restriction']} casting "
      f"restriction, {m['diff_census']['casting_option']} casting option -- the last two are call sites of the "
      f"same function found during implementation; the sizing's 79 covered only the activation ones the "
      f"detector could see). The gate compared {m['gate']['compared']:,} entries against the snapshot with "
      f"the two earlier parser-fix overlays applied: {m['gate']['identical'] + m['gate']['identical_after_april_metadata']:,} "
      f"byte-identical, {m['gate']['different']} rerun-flagged, of which {m['rerun_artifacts_identical_after_regeneration']} "
      f"were metadata-restoration artifacts identical after regeneration and {m['fixed']} cards carry the change. "
      f"Every shipped difference is `null/absent -> {{type: Unrecognized, text}}` at exactly those nodes.\n")
    w("Residuals, stated plainly: (1) the 77 cards here are the 79 of the sizing round minus Gate to the "
      "Afterlife and Isolated Watchtower, whose first unsatisfied clause is a separate body clause (\"if you "
      "search your library this way\", \"if a basic land card is revealed this way\") and are now classified "
      "by it -- they were never only a wrapper problem. (2) After the fix, 74 of the 77 stop flagging at all; "
      "3 keep a separate, real drop that the null wrapper had been hiding from the classifier: Izzet Generatorium "
      "and Ojer Taq (embedded replacement) and Sarevok's Tome (\"...instead\"). (3) To make that visible the "
      "detector now lets a restriction sentence back only its own `only if` clause (family RESTR) instead of "
      "masking every other clause of the ability; on identical data that unmasks 2 items elsewhere "
      "(2,936 -> 2,938), and the 50-card baseline is unchanged (28 flagged / 22 cleared, 20 silent / 8 visible).\n")
    w("Worklist for round B (real phrase parsers): `reports/restriction-condition-worklist.md`.\n")
    # ---- round B1 log: timing clause split out of compound activation restrictions -----
    import restriction_worklist as W
    tp = os.path.join(HERE, "data", "overlay", "activation-timing-split-fix.json")
    if os.path.exists(tp):
        tdoc = json.load(open(tp, encoding="utf-8"))
        tm = tdoc["meta"]
        timing_names = {"AsSorcery", "DuringYourTurn", "DuringYourUpkeep", "DuringCombat",
                        "OnlyOnceEachTurn", "OnlyOnce"}
        complete, residual = [], []
        for faces in tdoc["cards"].values():
            for f in faces:
                for a in f["abilities"]:
                    rs_ = a.get("activation_restrictions") or []
                    if any(r["type"] in timing_names for r in rs_):
                        conds = [r for r in rs_ if r["type"] == "RequiresCondition"]
                        (residual if conds else complete).append(f["name"])
        left = [r for r in W.rows() if r[0] == "activation" and W.re.match(r"(?:during|before) ", r[3])]
        w("## Round B1 -- timing clause split out of compound activation restrictions\n")
        w("Round 1 left every unparsed \"Activate only ...\" sentence as one `Unrecognized` string. For "
          "compound sentences (\"as a sorcery and only if ...\", \"during your upkeep and only if ...\", "
          "\"once each turn and only if ...\") the leading clause is a phrase the parser already knows. "
          "The generic `activate only ` branch now splits on ` and only ` / `, and only ` / `, only `, "
          "emits `AsSorcery`, `DuringYourTurn`, `DuringYourUpkeep`, `DuringCombat`, `OnlyOnceEachTurn`, "
          "`OnlyOnce` for exact matches, and keeps every other piece verbatim as `Unrecognized` (the "
          "remainder is deliberately NOT run through the condition parser; see below). A sentence with no "
          "recognised timing piece is left exactly as it was.\n")
        w("| of the 40 timing-prefix blobs found after round 1 | cards |\n|---|---:|")
        w(f"| timing extracted, nothing left over (fully resolved) | {len(complete)} |")
        w(f"| timing extracted, `Unrecognized` remainder kept | {len(residual)} |")
        w(f"| unchanged: timing phrase with no equivalent variant yet | {len(left) - 1} |")
        w(f"| **total** | {len(complete) + len(residual) + len(left) - 1} |\n")
        w("(Grizzled Wolverine is in the second row and also keeps a leftover \"during the declare "
          "blockers step\" piece, which is why the worklist counts "
          f"{len(left)} timing-phrase texts still unrecognized.)\n")
        w(f"**This one changes gameplay.** The engine enforces those timing variants; the `Unrecognized` "
          f"remainder is still permissive. Engine tests parse the real Oracle text and run it through the "
          f"activation gate: Cabal Inquisitor is refused in Upkeep, Beginning of Combat, Declare Blockers and "
          f"End steps and during the opponent's main phase and allowed in its owner's main phase; an "
          f"upkeep-only ability is refused outside the upkeep; `OnlyOnceEachTurn` blocks a second activation; "
          f"\"once and only during your turn\" enforces both halves (4,479 engine tests pass).\n")
        w(f"Gate: {tm['gate']['compared']:,} entries compared against the snapshot with the three earlier "
          f"parser-fix overlays applied. {tm['gate']['identical']:,} byte-identical in generator key order, "
          f"{tm['gate']['identical_after_april_metadata']} after restoring the April metadata, "
          f"{tm['gate']['identical_overlay_face_canonical']} earlier-overlay faces identical under a canonical "
          f"(sorted-key) comparison, and exactly {tm['gate']['different']} different -- the declared set of "
          f"{tm['declared_targets']} cards, computed beforehand by an independent re-implementation of the "
          f"split rule. Every difference is an `activation_restrictions` list that was one `Unrecognized` "
          f"blob and is now a lossless split (each piece's text occurs in the old blob), plus "
          f"`sorcery_speed: false -> true` on the 6 `AsSorcery` abilities. The comparison itself was audited: "
          f"two comparators agree, the compared bytes are hashed on both sides, and a planted one-field "
          f"mutation is detected. (That audit also corrected round 1's account: the \"59 metadata-restoration "
          f"artifacts\" were earlier-overlay faces whose bytes differ only in key order, not in content.)\n")
        w("Detector: flagged items 2,861 / cards 2,785 before and after, as expected -- an extracted timing "
          "restriction is not a condition drop, and the remainder is still represented.\n")
        w("Two findings that shaped the scope. (1) Live-checking showed that sending remainders through the "
          "existing condition parser gives two cards a wrong, now-enforced meaning (Urza's Fun House's "
          "three-land clause and Goblin Ski Patrol's \"snow Mountain\" each become one made-up subtype that "
          "nothing can satisfy, so the abilities would become unusable); remainders therefore stay "
          "`Unrecognized`. (2) Seven remainders do parse correctly with the existing parser (Cabal "
          "Inquisitor's seven graveyard cards, Chronatog Totem, Gutterbones, Kuldotha Phoenix, Coffin "
          "Puppets, ...) and are a cheap later win once the misparses are fixed.\n")
    w("## Reach limits (what this detector cannot see)\n")
    w("- Only conditions written as `if` in an item's own `description` (49,017 items). "
      "`as long as`, `unless`, `only during` and similar are not examined.")
    w("- Items with no `description` are read through modal `mode_descriptions` when aligned; "
      "otherwise skipped (about 3,000 abilities, mostly keyword-generated).")
    w("- Card-level fields (`casting_restrictions`, `casting_options`, `additional_cost`) are not "
      "searched, and a whole oracle line missing from every item is invisible here: 272 entries "
      "(222 `clean`) have more `if` clauses in the oracle text than in all item descriptions "
      "(mostly Cast-only-if / alternative-cost / Saga / Raid lines). Unaudited, not counted above.")
    w("- Tier A needs a clause family with zero evidence; tier B (89 items) is a family with "
      "fewer condition nodes than clauses. Two different conditions where only one is dropped and "
      "the surviving node is of the same family can still be missed.")
    w("- Sub-shape is assigned by text pattern on the first unsatisfied clause; boundaries "
      "(compound vs sequential, filter-targeting) are heuristic.\n")
    open(os.path.join(HERE, "reports", "condition-drops.md"), "w", encoding="utf-8").write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
