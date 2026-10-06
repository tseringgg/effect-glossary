#!/usr/bin/env python3
"""Part 1a, second pass: how many of the partial/unmodelled cards that would place survive a
SAME-LINE test. An ability is dropped when a gap fragment of the card sits in the same rules-text
line as the ability's own text (so the ability is a partial reading of that line, as in Spark
Double, where the copy clause was lost and the leftover clauses still looked clean).
Reads only; prints and writes build/partial_ability_probe2.json (new file).
"""
import collections
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap      # noqa: E402
import ability_rules as ar      # noqa: E402
import build_ledger as BL       # noqa: E402

CONT = {"it", "that", "the", "this", "its", "they", "those", "~", "then", "instead", "otherwise", "unless", "if",
        "them", "he", "she", "his", "her", "their", "and", "or", "also", "except", "where", "for", "at", "x", "a", "an", "choose"}


def sq(s):
    return re.sub(r"[^a-z]+", "", re.sub(r"\d+", "", (s or "").lower().replace("~", "")))


def fam(kind, cat):
    if kind == "Unimplemented":
        return "Unimplemented:" + cat.split(":", 1)[1]
    return "GenericEffect[?]" if kind == "GenericEffect" else cat


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sp = ap.Space()
    rules = ar.Rules(sp)
    R = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    rec_chunk = P["recovered"]["chunk"]
    flagged_items = collections.defaultdict(set)
    flagged_cards = set()
    for h in ap.jl("condition_drops.json"):
        flagged_cards.add(h["oid"])
        flagged_items[h["oid"]].add((h["bucket"], h["idx"]))
    faces_of = collections.defaultdict(list)
    for r in sp.rows:
        faces_of[r["id"].split("/")[0]].append(r["id"])
    for fid in sorted(rec_chunk):
        faces_of[fid.split("/")[0]].append(fid)
    entry_of = lambda fid: sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]
    pop = sorted(o for o, r in R.items() if r["status"] in ("partial", "unmodelled_node")
                 or r["placement"].get("reason") == "recovered_partial")
    flat = []
    for oid in pop:
        for fid in faces_of[oid]:
            e = entry_of(fid)
            its = ap.ability_items(e)
            modal = ar.is_modal(e, its)
            lines = [sq(re.sub(r"\([^)]*\)", "", ln)) for ln in (e.get("oracle_text") or "").split("\n")]
            card_frags = BL.gap_fragments(e, e.get("name") or "")
            fsq = [(fam(k, c), sq(t)) for k, c, t in card_frags]
            for b, i, it, t in its:
                gaps = BL.gap_fragments({b: [it]}, e.get("name") or "")
                flat.append({"oid": oid, "face": fid, "b": b, "i": i, "item": it, "modal": modal, "lines": lines,
                             "fsq": fsq, "tk": [k for k in sorted(t) if k in sp.vocab], "gaps": gaps})
    leaves, scores = ar.score_items(sp, [x["tk"] for x in flat])
    st = collections.Counter()
    by_card = collections.defaultdict(list)
    for x, l, s in zip(flat, leaves, scores):
        x["leaf"], x["score"] = (l, s) if x["tk"] else (None, None)
        size = int(sp.leaf_size[l]) if x["tk"] else 0
        text = ar.text_of(x["item"])
        base = ar.base_class(len(x["tk"]), size, x["score"] or 0.0)
        ok = (base == "specific" and not x["modal"] and (x["b"], x["i"]) not in flagged_items.get(x["oid"], ())
              and ar.has_text(text) and not x["gaps"]
              and rules.blind_spot(x["b"], x["item"], x["tk"], x["leaf"], text) is None)
        x["ok"] = ok
        x["text"] = text
        if not ok:
            continue
        d = sq(text)
        my_lines = [ln for ln in x["lines"] if ln and (d[:40] in ln or ln in d)]
        same = [f for f, t in x["fsq"] if t and any((t[:25] in ln) or (ln[:25] in t) for ln in my_lines)]
        x["same_line_gaps"] = same
        x["cont"] = [f for f, t in x["fsq"] if f.startswith("Unimplemented:") and f.split(":", 1)[1] in CONT]
        by_card[x["oid"]].append(x)
    cards = sorted(by_card)
    out = {"cards_clear_first_rule": len(cards)}
    keep = {o: [x for x in by_card[o] if not x["same_line_gaps"]] for o in cards}
    out["cards_after_same_line_test"] = sum(1 for o in cards if keep[o])
    out["abilities_dropped_by_same_line"] = sum(1 for o in cards for x in by_card[o] if x["same_line_gaps"])
    keep2 = {o: [x for x in keep[o] if not x["cont"]] for o in cards}
    out["cards_after_also_no_continuation_fragment_anywhere"] = sum(1 for o in cards if keep2[o])
    fam_cnt = collections.Counter()
    for o in cards:
        if keep[o]:
            for g in sorted({f for x in keep[o] for f, _ in x["fsq"]}):
                fam_cnt[g] += 1
    out["gap_families_after_same_line_test"] = dict(fam_cnt.most_common(25))
    out["dropped_same_line_by_family"] = dict(collections.Counter(f for o in cards for x in by_card[o] for f in set(x["same_line_gaps"])).most_common(25))
    out["abilities_per_card_after"] = dict(sorted(collections.Counter(len(keep[o]) for o in cards if keep[o]).items()))
    out["cards_2plus_leaves_after"] = sum(1 for o in cards if len({x["leaf"] for x in keep[o]}) > 1)
    out["by_status_after"] = dict(collections.Counter(R[o]["status"] if keep[o] else None for o in cards if keep[o]))
    out["_keep"] = {o: [(x["b"], x["i"], x["leaf"], round(x["score"], 4)) for x in keep[o]] for o in cards if keep[o]}
    with io.open(os.path.join(ap.BUILD, "partial_ability_probe2.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    print(json.dumps({k: v for k, v in out.items() if k != "_keep"}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
