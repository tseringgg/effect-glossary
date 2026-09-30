#!/usr/bin/env python3
"""Placement layer: puts cards the clustering pass left without a leaf
somewhere browsable, WITHOUT touching anything the clustering produced.

    python src/build_ledger.py         # statuses (this script reads them)
    python src/recover_dropped.py      # data/overlay/recovered-cards.json
    python src/build_placements.py     # -> build/placements.json
    python src/build_ledger.py         # again: annotates each row's placement

Three placement methods, recorded per face:
  clustered     the HDBSCAN leaf, as in build/clusters.json (not written here)
  proximity     nearest leaf centroid by cosine, for `noise` cards and for
                recovered cards whose parse is clean -- only at or above FLOOR
  vanilla_rule  `vanilla` cards (no oracle text) -> the "No abilities" branch

What is protected. Centroids are computed from clustered members only and
proximity cards never feed back into them, so leaf centroids, cohesion,
leaf/branch/sector counts, both maps and clusters.json are unchanged: this
script writes one new file and reads everything else. Browse shows the layer
as a separately counted, separately marked addition.

Feature space. Rebuilt exactly as src/cluster_structural.py built it: the same
card_features(), vocabulary in the same insertion order over the same 23,558
clustered+noise cards, binary presence x IDF over those cards, L2-normalised.
A recovered card's features outside that vocabulary are dropped (the space is
fixed); a card left with no feature at all scores 0 and is not placed.
Checked on every run: vocabulary size == clusters.n_features and every
clustered card's nearest centroid is its own leaf for >= 99.5% of them.

Below FLOOR a card is not placed; it goes to the review queue in this file
with its best leaf and score, so the call is visible rather than guessed.
"""
import collections
import io
import json
import os
import sys

import numpy as np
import scipy.sparse as sp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_index as bi            # noqa: E402  scan/classify/facets, as the index used
import cluster_structural as cs     # noqa: E402  card_features, as the clustering used

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
OVERLAY = os.path.join(HERE, "data", "overlay", "recovered-cards.json")
OUT = os.path.join(BUILD, "placements.json")

# Approved 2026-09-28. Clustered members score >= 0.80 against their own leaf
# centroid 96.6% of the time; noise between 0.70 and 0.80 is dominated by
# two-effect cards matching one effect at ~1/sqrt(2).
FLOOR = 0.80
VANILLA_BRANCH = "No abilities"
RECOVERED_CHUNK = "recovered"      # pseudo-chunk name browse seeds its cache with


def face_row(entry, eid, key, n_faces, oid):
    """An index row for a recovered face, built the way build_index.py builds one."""
    found = {axis: set() for axis in bi.SLOTS}
    gaps, soft = [], []
    for bucket in bi.BUCKETS:
        bi.scan(entry.get(bucket), bucket, found, gaps, soft)
    for t in entry.get("triggers") or []:
        mode = t.get("mode")
        if isinstance(mode, dict) and "Unknown" in mode:
            soft.append("trigger_mode")
    ct = entry.get("card_type") or {}
    typeline = " ".join(filter(None, [
        " ".join(ct.get("supertypes") or []),
        " ".join(ct.get("core_types") or []),
        ("- " + " ".join(ct.get("subtypes"))) if ct.get("subtypes") else "",
    ])).strip()
    col, mv = bi.browse_facets(entry)
    return {
        "id": eid, "key": key, "name": entry.get("name") or key,
        "text": entry.get("oracle_text") or "", "q": bi.classify(entry, gaps),
        "type": typeline, "col": col, "mv": mv, "cty": ct.get("core_types") or [],
        "layout": entry.get("layout"), "warn": len(entry.get("parse_warnings") or []),
        "gaps": len(gaps), "sg": len(soft), "corr": 0,
        "group": oid if n_faces > 1 else None, "ch": RECOVERED_CHUNK, "recovered": True,
    }


def main():
    rows, chunks = cs.load()
    clusters = json.load(io.open(os.path.join(BUILD, "clusters.json"), encoding="utf-8"))
    ledger = json.load(io.open(os.path.join(BUILD, "ledger.json"), encoding="utf-8"))["rows"]
    lab = clusters["cards"]

    # ---- the clustering's feature space, rebuilt
    order = [r["id"] for r in rows if r["id"] in lab]
    feats = {i: cs.card_features(chunks[r["ch"]][i]) for r in rows for i in [r["id"]] if i in lab}
    vocab = {}
    for i in order:
        for k in feats[i]:
            vocab.setdefault(k, len(vocab))
    assert len(vocab) == clusters["n_features"] and len(order) == clusters["n_cards"], \
        "feature space does not match build/clusters.json -- rerun the clustering inputs"
    n = len(order)

    def encode(feature_lists):
        indptr, indices = [0], []
        for fl in feature_lists:
            indices.extend(vocab[k] for k in fl if k in vocab)
            indptr.append(len(indices))
        return sp.csr_matrix((np.ones(len(indices), np.float32), indices, indptr),
                             shape=(len(feature_lists), len(vocab)))

    X = encode([feats[i] for i in order])
    df = np.asarray((X > 0).sum(axis=0)).ravel()
    idf = np.log((1.0 + n) / (1.0 + df)).astype(np.float32) + 1.0

    def weigh(M):
        M = M.multiply(idf).tocsr()
        norms = np.sqrt(M.multiply(M).sum(axis=1)).A.ravel()
        norms[norms == 0] = 1.0
        return sp.diags(1.0 / norms).dot(M).tocsr()

    X = weigh(X)
    labels = np.array([lab[i] for i in order])
    leaves = sorted(set(labels.tolist()) - {-1})
    C = np.zeros((len(leaves), len(vocab)), np.float32)
    for j, l in enumerate(leaves):
        C[j] = np.asarray(X[labels == l].mean(axis=0)).ravel()
    C /= np.linalg.norm(C, axis=1, keepdims=True)

    S_all = np.asarray(X @ C.T)
    member = labels != -1
    own = np.array([S_all[k, leaves.index(labels[k])] for k in np.where(member)[0]])
    self_nearest = float(np.mean([leaves[j] == labels[k] for k, j in
                                  zip(np.where(member)[0], S_all[member].argmax(axis=1))]))
    assert self_nearest >= 0.995, f"centroids do not reproduce the leaves ({self_nearest:.3f})"

    # ---- candidates: noise cards' noise faces, recovered clean faces
    cand = []    # (face id, oracle id, source, feature list)
    for r in rows:
        oid = r["id"].split("/")[0]
        if lab.get(r["id"]) == -1 and ledger.get(oid, {}).get("status") == "noise":
            cand.append((r["id"], oid, "noise", feats[r["id"]]))

    overlay = json.load(io.open(OVERLAY, encoding="utf-8")) if os.path.exists(OVERLAY) else {"cards": {}}
    rec_rows, rec_chunk, rec_stage = [], {}, {}
    for oid, faces in sorted(overlay["cards"].items()):
        stages = []
        for pos, e in enumerate(faces):
            eid = oid if len(faces) == 1 else f"{oid}/{pos}"
            row = face_row(e, eid, e.get("name", "").lower(), len(faces), oid)
            rec_rows.append(row)
            rec_chunk[eid] = {**e, "_export_key": None, "_recovered": True}
            f = cs.card_features(e) if row["q"] == "clean" and not row["sg"] else []
            stage = (row["q"] if row["q"] != "clean" else
                     "unmodelled_node" if row["sg"] else
                     "clean" if f else "no_extractable_effect")
            stages.append({"id": eid, "name": row["name"], "quality": row["q"], "stage": stage,
                           "gap_nodes": row["gaps"], "unmodelled": row["sg"],
                           "unseen_features": sorted(k for k in f if k not in vocab)})
            if stage == "clean":
                cand.append((eid, oid, "recovered", f))
        rec_stage[oid] = stages

    Y = weigh(encode([c[3] for c in cand]))
    S = np.asarray(Y @ C.T)
    best = S.argmax(axis=1)
    score = S.max(axis=1)

    faces, review = {}, []
    for (eid, oid, src, _), j, s in zip(cand, best, score):
        rec = {"card": oid, "source": src, "best_leaf": int(leaves[j]), "similarity": round(float(s), 4)}
        if s >= FLOOR:
            faces[eid] = {**rec, "method": "proximity", "leaf": int(leaves[j])}
        else:
            review.append({"face": eid, **rec, "reason": "below_similarity_floor"})

    vanilla = sorted(r["id"] for r in rows
                     if r["q"] == "vanilla" and ledger.get(r["id"].split("/")[0], {}).get("status") == "vanilla")
    for eid in vanilla:
        faces[eid] = {"card": eid.split("/")[0], "source": "vanilla", "method": "vanilla_rule",
                      "branch": VANILLA_BRANCH}

    q = [0, 1, 5, 10, 25, 50, 75, 90, 95, 99, 100]
    pct = lambda a: {str(p): round(float(v), 4) for p, v in zip(q, np.percentile(a, q))} if len(a) else {}
    by_src = collections.defaultdict(list)
    for (eid, _, src, _), s in zip(cand, score):
        by_src[src].append(float(s))
    hist = lambda a: [int(x) for x in np.histogram(a, bins=20, range=(0, 1))[0]]

    doc = {
        "meta": {
            "floor": FLOOR,
            "vanilla_branch": VANILLA_BRANCH,
            "feature_space": {"n_features": len(vocab), "n_cards": n,
                              "clustered_nearest_is_own_leaf": round(self_nearest, 4)},
            "similarity": {
                "clustered_members_to_own_centroid": {"percentiles": pct(own), "hist20": hist(own)},
                **{f"{src}_best_centroid": {"n": len(v), "percentiles": pct(v), "hist20": hist(v),
                                            "at_or_above_floor": sum(x >= FLOOR for x in v)}
                   for src, v in sorted(by_src.items())},
            },
            "counts": dict(collections.Counter(
                f["method"] + ":" + f["source"] for f in faces.values())),
            "review_queue": len(review),
            "protected": "centroids from clustered members only; clusters.json, branches.json, "
                         "sectors.json and the maps are read, never written",
        },
        "faces": dict(sorted(faces.items())),
        "review_queue": sorted(review, key=lambda x: (-x["similarity"], x["face"])),
        "recovered": {"rows": rec_rows, "chunk": rec_chunk, "stages": rec_stage},
    }
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print(json.dumps(doc["meta"], indent=1))


if __name__ == "__main__":
    main()
