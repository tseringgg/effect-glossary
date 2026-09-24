#!/usr/bin/env python3
"""UMAP layout of the 591 structural leaves -- EXPLORATORY VALIDATION ONLY.

This is a checkpoint, not a feature. It answers one question: are the 2D
positions trustworthy enough to build anything on top of? No branch colouring,
no integration into the main page.

Feature space is NOT new. Card vectors are built by importing
cluster_structural.card_features and running the identical IDF weighting and
L2 normalisation over the identical card population, so the IDF weights are
byte-for-byte the ones the clustering pass used. A leaf vector is then the
centroid of its member card vectors, re-normalised -- the only added step, and
it introduces no new tokens.

Reads   build/clusters.json, build/index.json, build/chunks/*.json
Writes  build/leafmap.json                 coords + per-leaf meta for the page
        reports/leafmap-validation.md      the validation report

Reproducibility: RANDOM_SEED below is passed as UMAP's random_state, which the
library honours by forcing single-threaded execution (it warns about this) --
so repeated runs give identical coordinates. Library versions are recorded in
the output and the report.
"""
import collections
import importlib.metadata
import json
import os
import sys
import time

import numpy as np
import scipy.sparse as sp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# cluster_structural imports hdbscan at module level, and this machine's
# Application Control policy now blocks hdbscan's compiled _hdbscan_tree DLL.
# We need none of it: only the feature-extraction helpers, and the leaves are
# read from build/clusters.json as already computed (re-clustering is out of
# scope for this pass anyway). Stubbing the name keeps us on the identical
# feature code rather than copying it, which is what "same feature space"
# has to mean.
if "hdbscan" not in sys.modules:
    import types as _types
    sys.modules["hdbscan"] = _types.ModuleType("hdbscan")
import cluster_structural as C

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
REPORTS = os.path.join(HERE, "reports")

RANDOM_SEED = 42        # fixed and reported, as in the clustering pass
N_NEIGHBORS = 15        # umap-learn default
MIN_DIST = 0.1          # umap-learn default
N_COMPONENTS = 2

# Known cases, by Scryfall oracle id (never by face name -- see
# KNOWN_LIMITATIONS.md section 1). Ids confirmed against Scryfall.
PROBE_CARDS = {
    "Murder": "938b4e2c-88d9-4637-bc00-e228920c9a78",
    "Doom Blade": "59e7f2ae-4535-4191-98be-3e65b6b2befa",
    "Terror": "b81f041d-98db-4408-9472-c483e4a502bc",
    "Swords to Plowshares": "b1544f21-7e98-461b-aed5-e748b0168c52",
    "Wrath of God": "34515b16-c9a4-4f98-8c77-416a7a523407",
    "Blasphemous Act": "7a2484a9-04fd-41a0-8224-610c1c07ed10",
    "Memory Sluice": "a30b659e-ae2b-4736-9b4f-a9805905bf75",
    "Deadly Visit": "04a3bb42-0464-4638-a6ac-d5f412c222cc",
    "Raucous Theater": "04e5e84f-8fd4-43ab-8f9d-5b24646f7ae5",
    "Llanowar Elves": "68954295-54e3-4303-a6bc-fc4547a4e3a3",
    "Mulldrifter": "9ff8b1df-37c4-4b3a-a3e0-2d0bb2ec6c07",
}


def build_leaf_vectors():
    """(leaf_ids, leaf_matrix, members, card_rows) in the clustering feature space."""
    CL = json.load(open(os.path.join(BUILD, "clusters.json"), encoding="utf-8"))
    rows, chunks = C.load()
    byid = {r["id"]: r for r in rows}

    # Reproduce the clustering pass's card population and filter exactly.
    keep = [r for r in rows
            if r["q"] == "clean" and not r["sg"] and not r.get("corr")]
    feats, kept = [], []
    for r in keep:
        f = C.card_features(chunks[r["ch"]][r["id"]])
        if f:
            feats.append(f)
            kept.append(r)

    vocab = {}
    for f in feats:
        for k in f:
            vocab.setdefault(k, len(vocab))
    indptr, indices = [0], []
    for f in feats:
        indices.extend(vocab[k] for k in f)
        indptr.append(len(indices))
    n, v = len(feats), len(vocab)
    X = sp.csr_matrix((np.ones(len(indices), dtype=np.float32), indices, indptr),
                      shape=(n, v))
    df = np.asarray((X > 0).sum(axis=0)).ravel()
    idf = np.log((1.0 + n) / (1.0 + df)).astype(np.float32) + 1.0
    X = X.multiply(idf).tocsr()
    norms = np.sqrt(X.multiply(X).sum(axis=1)).A.ravel()
    norms[norms == 0] = 1.0
    X = sp.diags(1.0 / norms).dot(X).tocsr().astype(np.float32)

    pos = {kept[i]["id"]: i for i in range(n)}
    members = collections.defaultdict(list)
    for cid, l in CL["cards"].items():
        if l >= 0 and cid in pos:
            members[int(l)].append(cid)

    leaf_ids = sorted(members)
    M = np.zeros((len(leaf_ids), v), dtype=np.float32)
    for k, l in enumerate(leaf_ids):
        idx = [pos[c] for c in members[l]]
        cen = np.asarray(X[idx].mean(axis=0)).ravel()
        nrm = np.linalg.norm(cen)
        M[k] = cen / (nrm if nrm else 1.0)
    return leaf_ids, M, members, byid, CL, n, v


def main():
    t0 = time.time()
    leaf_ids, M, members, byid, CL, n_cards, n_feat = build_leaf_vectors()
    L = len(leaf_ids)
    print(f"[{time.time()-t0:5.1f}s] {L} leaves, {n_feat} features, "
          f"from {n_cards} cards", file=sys.stderr)

    # --- full dense pairwise cosine distance (591x591, no approximation) ---
    S = M @ M.T
    np.clip(S, -1.0, 1.0, out=S)
    D = (1.0 - S).astype(np.float64)
    np.fill_diagonal(D, 0.0)
    D = np.maximum(D, D.T)
    print(f"[{time.time()-t0:5.1f}s] distance matrix {D.shape}, "
          f"mean {D[np.triu_indices(L,1)].mean():.4f}", file=sys.stderr)

    import umap
    reducer = umap.UMAP(
        n_neighbors=N_NEIGHBORS, min_dist=MIN_DIST, n_components=N_COMPONENTS,
        metric="precomputed", random_state=RANDOM_SEED, verbose=False,
    )
    XY = reducer.fit_transform(D)
    print(f"[{time.time()-t0:5.1f}s] UMAP done", file=sys.stderr)

    idx_of = {l: k for k, l in enumerate(leaf_ids)}
    out = {
        "params": {
            "random_seed": RANDOM_SEED,
            "n_neighbors": N_NEIGHBORS,
            "min_dist": MIN_DIST,
            "n_components": N_COMPONENTS,
            "metric": "precomputed cosine on IDF-weighted leaf centroids",
            "umap_learn": importlib.metadata.version("umap-learn"),
            "numba": importlib.metadata.version("numba"),
            "numpy": np.__version__,
            "note": "random_state forces single-threaded UMAP, so runs are "
                    "bit-identical; the library warns about this by design",
        },
        "n_leaves": L,
        "n_features": n_feat,
        "n_cards": n_cards,
        "leaves": [
            {
                "leaf": l,
                "x": float(XY[idx_of[l]][0]),
                "y": float(XY[idx_of[l]][1]),
                "n_cards": len(members[l]),
                "label": CL["labels"].get(str(l), ""),
                "sample": sorted(CL["names"][c] for c in members[l])[:6],
            }
            for l in leaf_ids
        ],
    }
    with open(os.path.join(BUILD, "leafmap.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"), ensure_ascii=False)

    np.save(os.path.join(BUILD, "_leaf_D.npy"), D)
    np.save(os.path.join(BUILD, "_leaf_XY.npy"), XY)
    with open(os.path.join(BUILD, "_leaf_ids.json"), "w") as fh:
        json.dump(leaf_ids, fh)

    print(json.dumps({"leaves": L, "features": n_feat,
                      "seed": RANDOM_SEED,
                      "umap": out["params"]["umap_learn"]}, indent=1))


if __name__ == "__main__":
    main()
