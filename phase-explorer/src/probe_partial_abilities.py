#!/usr/bin/env python3
"""Part 1a investigation: ability-level placement for partial and unmodelled cards. Reads only;
writes build/partial_ability_probe.json (new file) and prints the findings.

    python src/probe_partial_abilities.py

For every card in "Parsed, but with a gap" (partial, unmodelled_node, recovered_partial) it applies
the first version's promotion rule to each ability (src/ability_rules.py) plus two conditions that
only matter on gap cards: the ability is not flagged by the condition-drop detector, and its item
holds no Unimplemented / GenericEffect[?] / Unrecognized / unknown-trigger-mode node anywhere.
"""
import collections
import io
import json
import os
import re
import sys

HERE_SRC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE_SRC)
import ability_probe as ap      # noqa: E402
import ability_rules as ar      # noqa: E402
import build_ledger as BL       # noqa: E402

BUILD = ap.BUILD


def fam(kind, cat):
    if kind == "Unimplemented":
        return "Unimplemented:" + cat.split(":", 1)[1]
    if kind == "GenericEffect":
        return "GenericEffect[?]"
    return cat                                   # "Unrecognized condition" / "Unknown trigger mode"


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sp = ap.Space()
    rules = ar.Rules(sp)
    R = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    rec_chunk = P["recovered"]["chunk"]
    flagged_cards, flagged_items = set(), collections.defaultdict(set)
    for h in ap.jl("condition_drops.json"):
        flagged_cards.add(h["oid"])
        flagged_items[h["oid"]].add((h["bucket"], h["idx"]))

    faces_of = collections.defaultdict(list)
    for r in sp.rows:
        faces_of[r["id"].split("/")[0]].append(r["id"])
    for fid in sorted(rec_chunk):
        faces_of[fid.split("/")[0]].append(fid)

    def entry_of(fid):
        return sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]

    pop = sorted(o for o, r in R.items() if r["status"] in ("partial", "unmodelled_node")
                 or r["placement"].get("reason") == "recovered_partial")
    flat = []
    for oid in pop:
        for fid in faces_of[oid]:
            e = entry_of(fid)
            its = ap.ability_items(e)
            modal = ar.is_modal(e, its)
            for b, i, it, t in its:
                gaps = BL.gap_fragments({b: [it]}, e.get("name") or "")
                flat.append({"oid": oid, "face": fid, "b": b, "i": i, "item": it, "modal": modal,
                             "tk": [k for k in sorted(t) if k in sp.vocab], "gaps": sorted({fam(k, c) for k, c, _ in gaps})})
    leaves, scores = ar.score_items(sp, [x["tk"] for x in flat])
    for x, l, s in zip(flat, leaves, scores):
        x["leaf"], x["score"] = (l, s) if x["tk"] else (None, None)
        x["size"] = int(sp.leaf_size[l]) if x["tk"] else 0
        x["text"] = ar.text_of(x["item"])
        base = ar.base_class(len(x["tk"]), x["size"], x["score"] or 0.0)
        why = None
        if base == "no_tokens":
            r_ = "no_tokens"
        elif (x["b"], x["i"]) in flagged_items.get(x["oid"], ()):
            r_ = "flagged_item"
        elif x["modal"]:
            r_ = "modal"
        elif base != "specific":
            r_ = base
        elif not ar.has_text(x["text"]):
            r_ = "no_text"
        else:
            why = rules.blind_spot(x["b"], x["item"], x["tk"], x["leaf"], x["text"])
            r_ = "token_blind_spot" if why else ("item_gap" if x["gaps"] else "eligible")
        x["reason"], x["why"] = r_, why

    by = collections.defaultdict(list)
    for x in flat:
        by[x["oid"]].append(x)
    out = {"population": len(pop), "by_status": dict(collections.Counter(
        R[o]["status"] if R[o]["status"] in ("partial", "unmodelled_node") else "recovered_partial" for o in pop))}
    out["ability_items"] = len(flat)
    out["item_reasons"] = dict(collections.Counter(x["reason"] for x in flat).most_common())
    elig_cards = [o for o in pop if any(x["reason"] == "eligible" for x in by[o])]
    out["cards_with_eligible_ability"] = len(elig_cards)
    out["abilities_per_card"] = dict(sorted(collections.Counter(
        sum(1 for x in by[o] if x["reason"] == "eligible") for o in elig_cards).items()))
    out["eligible_in_flagged_card_but_unflagged_item"] = sum(1 for o in elig_cards if o in flagged_cards)
    # distinct leaves among eligible abilities, per card
    out["cards_with_eligible_in_2plus_leaves"] = sum(
        1 for o in elig_cards if len({x["leaf"] for x in by[o] if x["reason"] == "eligible"}) > 1)
    # items that clear everything except the item-gap condition
    out["blocked_only_by_item_gap"] = sum(1 for x in flat if x["reason"] == "item_gap")

    # gap families on the cards that would place: the card's gaps (all items) and whether the gap sits in a
    # sibling item of the same face
    fam_cards = collections.Counter()
    fam_kind = collections.defaultdict(set)
    for o in elig_cards:
        card_fams = set()
        for fid in faces_of[o]:
            e = entry_of(fid)
            for k, c, _ in BL.gap_fragments(e, e.get("name") or ""):
                card_fams.add(fam(k, c))
        for f_ in card_fams:
            fam_cards[f_] += 1
    out["gap_families_on_placing_cards"] = dict(fam_cards.most_common(60))
    out["gap_families_total_cards"] = len(fam_cards)

    # oracle-text lines no item accounts for (a lost effect with no gap node)
    def uncovered(o):
        lost = 0
        for fid in faces_of[o]:
            e = entry_of(fid)
            descs = []
            for b in ap.BUCKETS:
                for it in e.get(b) or []:
                    descs.append(norm(it.get("description")))
            kws = {norm(re.sub(r"([a-z])([A-Z])", r"\1 \2", k if isinstance(k, str) else next(iter(k)))) for k in (e.get("keywords") or [])}
            for ln in (e.get("oracle_text") or "").split("\n"):
                ln = re.sub(r"\([^)]*\)", "", ln).strip()
                n = norm(ln)
                if not n or any(n.startswith(k) for k in kws if k):
                    continue
                if not any(d and (d in n or n in d) for d in descs):
                    lost += 1
        return lost
    unc = {o: uncovered(o) for o in elig_cards}
    out["placing_cards_with_an_uncovered_text_line"] = sum(1 for v in unc.values() if v)
    out["placing_cards_all_text_covered"] = sum(1 for v in unc.values() if not v)

    # card-level conditions the first version used: also exclude cards flagged anywhere / modal faces
    out["placing_cards_not_flagged_anywhere"] = sum(1 for o in elig_cards if o not in flagged_cards)

    # ---- named cards
    names = ["Spark Double", "Master Chef", "Toxic Deluge", "Tax Collector", "Jeska, Thornprince", "Thrice Reborn", "Channel"]
    def find(n):
        return [o for o, r in R.items() if r["name"].lower().startswith(n.lower())]
    named = {}
    for n in names:
        for o in find(n)[:1]:
            named[n] = o
    out["named_lookup"] = {n: (R[o]["status"], R[o]["placement"].get("reason")) for n, o in named.items()}
    out["named_missing"] = [n for n in names if n not in named]
    out["_uncovered"] = unc
    out["_elig_cards"] = elig_cards
    with io.open(os.path.join(BUILD, "partial_ability_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({k: v for k, v in out.items() if not k.startswith("_")}, ensure_ascii=False,
                            sort_keys=True, separators=(",", ":")))
    print(json.dumps({k: v for k, v in out.items() if not k.startswith("_")}, indent=1, ensure_ascii=False))
    # stash the detail for the sampling script
    import pickle
    with open(os.path.join(os.environ.get("SCRATCH", "."), "partial_flat.pkl"), "wb") as fh:
        pickle.dump({"flat": [{k: v for k, v in x.items() if k != "item"} for x in flat], "elig": elig_cards,
                     "unc": unc, "names": named}, fh)


if __name__ == "__main__":
    main()
