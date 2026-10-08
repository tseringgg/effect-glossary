#!/usr/bin/env python3
"""Seeded samples for signature-taxonomy PROBE 2 (coherence 30 leaves, placement 40 abilities).

    python src/sample2_signature_probe.py   # -> build/signature_probe2_handcheck.json

Rule fixed before any result was looked at. Seed 20261007. Variant RF5 (rarest-field-first backoff, minimum 5,
literal counts). Leaf strata by retained-field level: finest = level 5, mid = levels 3 and 4, coarsest = level 2.
Within a stratum the leaves (sorted by signature) are shuffled with random.Random("<seed>-coh-<stratum>") and read
in that order; a leaf holding fewer than 8 abilities directly is skipped (and listed) and the next one is taken.
Flagged-generic leaves are in the draw (they are leaves); the flag is shown. 8 abilities per leaf: members sorted
by (card, bucket, index), shuffled with random.Random("<seed>-abil-<signature>"), first 8.

Placement sample: abilities placed by RF5 in an unflagged leaf of >= 5 abilities whose card is noise, or whose
ability the ledger says is unplaced today. Sorted by (card, bucket, index); random.Random("<seed>-place").sample(40).
"""
import collections
import io
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze2_signature_probe as an  # noqa: E402
import probe2_signature_taxonomy as p2  # noqa: E402

SEED = an.SEED
KEY = "RF5"


def main():
    R = an.jl("signature_probe2_leaves.json")["rows"]
    idx = {r["id"]: r for r in an.jl("index.json")["rows"]}
    mem, flags = an.tables(R, KEY)
    full = lambda r: p2.sigstr(r["f"], set(p2.CANON))   # noqa: E731

    def card_text(r):
        t = (idx.get(r["face"]) or {}).get("text") or ""
        return t.replace("\n", " / ")[:260]

    strata = {"finest": lambda lf: lf[0] == 5, "mid": lambda lf: lf[0] in (3, 4), "coarsest": lambda lf: lf[0] == 2}
    coh = []
    skips = {}
    for band, pred in strata.items():
        leaves = sorted(lf for lf in mem if pred(lf))
        random.Random("%d-coh-%s" % (SEED, band)).shuffle(leaves)
        skipped, taken = [], []
        for lf in leaves:
            if len(taken) == 10:
                break
            if len(mem[lf]) < 8:
                skipped.append({"level": lf[0], "sig": lf[1], "n": len(mem[lf])})
                continue
            taken.append(lf)
        skips[band] = skipped
        for lf in taken:
            js = sorted(mem[lf], key=lambda j: (R[j]["oid"], R[j]["b"], R[j]["i"]))
            random.Random("%d-abil-%s" % (SEED, lf[1])).shuffle(js)
            ab = []
            for j in js[:8]:
                r = R[j]
                t = r["text"].strip()
                ab.append({"name": r["name"], "text": t[:260] if t else "(no text)  [card: " + card_text(r) + "]",
                           "full_sig": full(r)})
            coh.append({"band": band, "level": lf[0], "sig": lf[1], "n": len(mem[lf]),
                        "flagged": flags.get(lf, []), "abilities": ab,
                        "skipped_before_this_band_filled": len(skipped)})
    cand = sorted((j for j, r in enumerate(R)
                   if an.lv(r, KEY) and len(mem[an.lv(r, KEY)]) >= 5 and an.lv(r, KEY) not in flags
                   and (r["state"] == "unplaced" or r["status"] == "noise")),
                  key=lambda j: (R[j]["oid"], R[j]["b"], R[j]["i"]))
    pick = random.Random("%d-place" % SEED).sample(cand, 40)
    pl = []
    for j in pick:
        r = R[j]
        lf = an.lv(r, KEY)
        others = [R[x]["name"] + ": " + (R[x]["text"] or "")[:80] for x in sorted(mem[lf])[:400:80] if x != j][:4]
        pl.append({"name": r["name"], "b": r["b"], "i": r["i"], "text": r["text"].strip()[:260] or "(no text)",
                   "card_text": card_text(r), "today": [r["state"], r["status"]], "full_sig": full(r),
                   "level": lf[0], "leaf": lf[1], "leaf_n": len(mem[lf]), "leaf_peers": others})
    doc = {"v": 1, "seed": SEED, "variant": KEY,
           "population_for_placement_sample": len(cand), "coherence": coh, "placement": pl,
           "skipped_leaves_under_8": skips}
    with io.open(os.path.join(an.BUILD, "signature_probe2_handcheck.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True))
    print(len(coh), len(pl), "candidates", len(cand))
    print({b: sum(1 for c in coh if c["band"] == b) for b in strata})
    print("skipped per band:", {b: max((c["skipped_before_this_band_filled"] for c in coh if c["band"] == b), default=0) for b in strata})


if __name__ == "__main__":
    main()
