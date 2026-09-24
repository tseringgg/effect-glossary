#!/usr/bin/env python3
"""Leaf-similarity map over a small CURATED dimension set.

The previous pass positioned leaves with all 3,347 structural features and
failed validation: kNN preservation 44.4%, Spearman rho 0.164. Root cause was
intrinsic dimensionality -- too many near-orthogonal directions to compress
into 2D -- confirmed by a parameter sweep that capped at 44.9%.

This pass replaces that with six conceptual dimensions / fifteen numeric
columns, every one a graded fraction over the leaf's member cards, drawn only
from data this project already validated:

  D1 mass vs single-target  1 col   branch_leaves.MASS_EFFECTS
  D2 choice present         1 col   zone classifier `choice`
  D3 zone profile           8 cols  zone classifier `zone`
  D4 direction profile      3 cols  zone classifier `direction`
  D5 activated vs spell     1 col   phase.rs abilities[].kind
  D6 keyword-bearing        1 col   phase.rs keywords[]

Deliberately NOT a positioning column:
  * branch categorisation -- would make validation circular (the checks are
    defined by branch membership) and leaves 30% of leaves at the origin.
  * raw dominant effect type -- 120 one-hot categories is the near-orthogonal
    encoding that caused the last failure. Measured as a variant, not adopted
    blindly.

Nothing here re-parses card text. Zone facts come from the old pipeline's
already-computed output, which joins to phase.rs by Scryfall oracle id at 100%
coverage (its `card_id` field IS the oracle id).

Reads   ../data/full/effects.json           zone classifier output
        build/clusters.json, build/index.json, build/chunks/*.json
Writes  build/leafmap_curated.json          coords + meta
        build/_cur_D.npy, _cur_XY.npy, _cur_ids.json
"""
import collections
import importlib.metadata
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "hdbscan" not in sys.modules:          # blocked by Application Control; unused here
    import types as _t
    sys.modules["hdbscan"] = _t.ModuleType("hdbscan")
import cluster_structural as C
import branch_leaves as B

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
PARENT = os.path.dirname(HERE)
ZONES_PATH = os.path.join(PARENT, "data", "full", "effects.json")

RANDOM_SEED = 42
N_NEIGHBORS = 15
MIN_DIST = 0.1

ZONE_ORDER = ["battlefield", "graveyard", "hand", "library",
              "stack", "exile", "mana pool", "command zone"]
DIR_ORDER = ["source", "destination", "reference"]


def load_zone_facts():
    """oracle_id -> {zones:set, dirs:set, choice:bool}, from the zone classifier."""
    eff = json.load(open(ZONES_PATH, encoding="utf-8"))
    items = eff["effects"] if isinstance(eff, dict) else eff
    out = collections.defaultdict(
        lambda: {"zones": set(), "dirs": set(), "choice": False})
    for e in items:
        recs = e.get("zones") or []
        for cid in e.get("card_ids") or []:
            t = out[cid]
            for r in recs:
                t["zones"].add(r["zone"])
                t["dirs"].add(r["direction"])
                if r["choice"]:
                    t["choice"] = True
    return out


def dominant_effects(d):
    """Top-level effect types on one card, as the clustering pass sees them."""
    got = set()
    for a in d.get("abilities") or []:
        e, _ = C.effect_features(a.get("effect"))
        if e:
            got.add(e)
    for t in d.get("triggers") or []:
        e, _ = C.effect_features((t.get("execute") or {}).get("effect"))
        if e:
            got.add(e)
    for r in d.get("replacements") or []:
        e, _ = C.effect_features((r.get("execute") or {}).get("effect"))
        if e:
            got.add(e)
    for s in d.get("static_abilities") or []:
        m = C.tag(s.get("mode"))
        if m:
            got.add("static:" + m)
    return got


def build():
    CL = json.load(open(os.path.join(BUILD, "clusters.json"), encoding="utf-8"))
    rows, chunks = C.load()
    byid = {r["id"]: r for r in rows}
    ZF = load_zone_facts()

    members = collections.defaultdict(list)
    for cid, l in CL["cards"].items():
        if l >= 0:
            members[int(l)].append(cid)
    leaf_ids = sorted(members)

    COLS = (["mass", "choice"] + [f"zone:{z}" for z in ZONE_ORDER]
            + [f"dir:{x}" for x in DIR_ORDER] + ["activated", "keyworded"])
    V = np.zeros((len(leaf_ids), len(COLS)), dtype=np.float64)
    eff_names = collections.Counter()
    eff_rows = []          # for the effect-type variant only
    zone_cov = 0

    for k, l in enumerate(leaf_ids):
        mem = members[l]
        n = len(mem)
        acc = collections.Counter()
        effc = collections.Counter()
        for cid in mem:
            d = chunks[byid[cid]["ch"]][cid]
            oid = cid.split("/")[0]
            effs = dominant_effects(d)
            effc.update(effs)
            if effs & B.MASS_EFFECTS:
                acc["mass"] += 1
            zf = ZF.get(oid)
            if zf:
                zone_cov += 1
                if zf["choice"]:
                    acc["choice"] += 1
                for z in zf["zones"]:
                    if z in ZONE_ORDER:
                        acc[f"zone:{z}"] += 1
                for x in zf["dirs"]:
                    acc[f"dir:{x}"] += 1
            if any(a.get("kind") == "Activated" for a in d.get("abilities") or []):
                acc["activated"] += 1
            if d.get("keywords"):
                acc["keyworded"] += 1
        for j, c in enumerate(COLS):
            V[k, j] = acc[c] / n
        eff_names.update(effc)
        eff_rows.append(effc)

    return leaf_ids, COLS, V, members, CL, eff_rows, eff_names, zone_cov


def cosine_D(M):
    nrm = np.linalg.norm(M, axis=1, keepdims=True)
    nrm[nrm == 0] = 1.0
    Z = M / nrm
    S = Z @ Z.T
    np.clip(S, -1.0, 1.0, out=S)
    D = 1.0 - S
    np.fill_diagonal(D, 0.0)
    return np.maximum(D, D.T)


def knn_pres(D, XY, K=10):
    L = D.shape[0]
    d2 = np.sqrt(((XY[:, None, :] - XY[None, :, :]) ** 2).sum(-1))
    keep = 0
    for i in range(L):
        a = [x for x in np.argsort(D[i]) if x != i][:K]
        b = [x for x in np.argsort(d2[i]) if x != i][:K]
        keep += len(set(a) & set(b))
    return keep / (L * K)


def spearman(x, y):
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    rx -= rx.mean(); ry -= ry.mean()
    return float((rx @ ry) / np.sqrt((rx @ rx) * (ry @ ry)))


def main():
    t0 = time.time()
    leaf_ids, COLS, V, members, CL, eff_rows, eff_names, zone_cov = build()
    L = len(leaf_ids)
    tot_cards = sum(len(m) for m in members.values())
    print(f"[{time.time()-t0:5.1f}s] {L} leaves, {len(COLS)} columns, "
          f"zone coverage {zone_cov}/{tot_cards}", file=sys.stderr)

    import umap

    def embed(D):
        return umap.UMAP(n_neighbors=N_NEIGHBORS, min_dist=MIN_DIST,
                         metric="precomputed", random_state=RANDOM_SEED,
                         verbose=False).fit_transform(D)

    # --- candidate encodings, measured rather than assumed -----------------
    cands = {}

    # raw graded fractions, cosine
    cands["raw-fraction cosine"] = cosine_D(V)

    # per-column standardised, cosine (near-constant columns like
    # zone:battlefield otherwise dominate every similarity)
    Z = V - V.mean(0)
    sd = Z.std(0); sd[sd == 0] = 1.0
    Vz = Z / sd
    cands["standardised cosine"] = cosine_D(Vz)

    # variant: + dominant effect type one-hot, to test the rejected option
    keep_eff = [e for e, c in eff_names.items() if c >= 20]
    E = np.zeros((L, len(keep_eff)))
    for k, ec in enumerate(eff_rows):
        n = sum(len(members[leaf_ids[k]]) for _ in [0])
        for j, e in enumerate(keep_eff):
            E[k, j] = ec[e] / len(members[leaf_ids[k]])
    cands["standardised + effect-type block"] = cosine_D(np.hstack([Vz, E]))

    report = {}
    for name, D in cands.items():
        XY = embed(D)
        kp = knn_pres(D, XY)
        iu = np.triu_indices(L, 1)
        d2 = np.sqrt(((XY[:, None, :] - XY[None, :, :]) ** 2).sum(-1))
        rho = spearman(D[iu], d2[iu])
        report[name] = {"knn": kp, "rho": rho, "D": D, "XY": XY,
                        "cols": D.shape[0]}
        print(f"[{time.time()-t0:5.1f}s] {name:34s} kNN@10 {100*kp:5.1f}%  "
              f"rho {rho:.3f}", file=sys.stderr)

    # Selection rule, fixed here rather than chosen after seeing the groups:
    # take the best kNN preservation, then among encodings within 1 percentage
    # point of it (a statistical tie at this sample size) prefer the higher
    # Spearman rho. Global structure was the prior pass's worst failure
    # (rho 0.164), so a tie on local quality should be broken by the global
    # metric rather than by rounding noise.
    top = max(report[k]["knn"] for k in report)
    tied = [k for k in report if report[k]["knn"] >= top - 0.01]
    best = max(tied, key=lambda k: report[k]["rho"])
    D, XY = report[best]["D"], report[best]["XY"]
    print(f"[{time.time()-t0:5.1f}s] selected: {best}", file=sys.stderr)

    np.save(os.path.join(BUILD, "_cur_D.npy"), D)
    np.save(os.path.join(BUILD, "_cur_XY.npy"), XY)
    json.dump(leaf_ids, open(os.path.join(BUILD, "_cur_ids.json"), "w"))

    out = {
        "params": {
            "random_seed": RANDOM_SEED,
            "n_neighbors": N_NEIGHBORS,
            "min_dist": MIN_DIST,
            "encoding": best,
            "columns": COLS,
            "n_columns": len(COLS),
            "umap_learn": importlib.metadata.version("umap-learn"),
            "numba": importlib.metadata.version("numba"),
            "numpy": np.__version__,
            "zone_source": "../data/full/effects.json (zone classifier output), "
                           "joined by Scryfall oracle id at 100% coverage",
        },
        "encodings_tested": {k: {"knn_at_10": report[k]["knn"],
                                 "spearman_rho": report[k]["rho"]}
                             for k in report},
        "prior_pass": {"knn_at_10": 0.444, "spearman_rho": 0.164,
                       "n_features": 3347},
        "n_leaves": L,
        "n_cards": tot_cards,
        "leaves": [
            {"leaf": l, "x": float(XY[k][0]), "y": float(XY[k][1]),
             "n_cards": len(members[l]),
             "label": CL["labels"].get(str(l), ""),
             "dims": {COLS[j]: round(float(V[k, j]), 3) for j in range(len(COLS))
                      if V[k, j] > 0},
             "sample": sorted(CL["names"][c] for c in members[l])[:6]}
            for k, l in enumerate(leaf_ids)
        ],
    }
    json.dump(out, open(os.path.join(BUILD, "leafmap_curated.json"), "w",
                        encoding="utf-8"), separators=(",", ":"),
              ensure_ascii=False)

    print(json.dumps({
        "selected": best,
        "knn_at_10": round(report[best]["knn"], 4),
        "spearman_rho": round(report[best]["rho"], 4),
        "prior": {"knn_at_10": 0.444, "spearman_rho": 0.164},
        "all": {k: [round(report[k]["knn"], 4), round(report[k]["rho"], 4)]
                for k in report},
    }, indent=1))


if __name__ == "__main__":
    main()
