#!/usr/bin/env python3
"""Per-ability scoring PROBE -- investigation only. Places nothing, changes nothing.

    python src/ability_probe.py          # -> build/ability_probe.json (new file; measurements)

Question: do cards left in "Parsed, no close group found" score 0.70-0.80 because ONE effect
matches a leaf and a second effect dilutes the blended vector (1/sqrt(2) ~= 0.707 for a
two-effect card with one perfect match)? If so, scoring each ability on its own would give
near-1.0 matches.

Nothing here invents a feature space. It rebuilds, exactly as src/build_placements.py does, the
clustering's vocabulary (insertion order over the clustered+noise cards), binary presence x IDF
(idf = ln((1+n)/(1+df)) + 1, over the same n cards), L2 normalisation, and the leaf centroids
(mean of the clustered members' vectors, L2-normalised). A per-ability vector uses
card_features()'s token scheme restricted to ONE item of abilities / triggers / replacements /
static_abilities, then the identical weighting. Scores are cosine against every leaf centroid.

Reads only. Writes only build/ability_probe.json (and, from report_ability_probe.py,
reports/ability-placement-probe.md).
"""
import collections
import io
import json
import os
import sys
import types

import numpy as np
import scipy.sparse as sp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "hdbscan" not in sys.modules:           # nothing here clusters; only the loader/features are used
    sys.modules["hdbscan"] = types.ModuleType("hdbscan")
import cluster_structural as cs  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
BUCKETS = ("abilities", "triggers", "static_abilities", "replacements")


def jl(name):
    return json.load(io.open(os.path.join(BUILD, name), encoding="utf-8"))


def item_tokens(bucket, item):
    """card_features() restricted to one item. Same tokens, same rules."""
    feats = set()

    def add(et, ts):
        if not et:
            return
        feats.add(f"eff:{et}")
        if ts:
            feats.add(f"eff:{et}|tgt:{ts}")
            feats.add(f"tgt:{ts}")

    if bucket == "abilities":
        add(*cs.effect_features(item.get("effect")))
    elif bucket in ("triggers", "replacements"):
        add(*cs.effect_features((item.get("execute") or {}).get("effect")))
    elif bucket == "static_abilities":
        m = cs.tag(item.get("mode"))
        if m:
            add(f"static:{m}", cs.target_shape(item.get("affected")))
    return feats


def ability_items(entry):
    """[(bucket, idx, item, tokens)] in bucket order, as card_features walks them."""
    out = []
    for b in BUCKETS:
        for i, it in enumerate(entry.get(b) or []):
            out.append((b, i, it, item_tokens(b, it)))
    return out


class Space:
    """The clustering's feature space, rebuilt as build_placements.py rebuilds it."""

    def __init__(self):
        self.rows, self.chunks = cs.load()
        self.clusters = jl("clusters.json")
        self.lab = self.clusters["cards"]
        self.byid = {r["id"]: r for r in self.rows}
        order = [r["id"] for r in self.rows if r["id"] in self.lab]
        self.feats = {i: cs.card_features(self.chunks[self.byid[i]["ch"]][i]) for i in order}
        self.vocab = {}
        for i in order:
            for k in self.feats[i]:
                self.vocab.setdefault(k, len(self.vocab))
        assert len(self.vocab) == self.clusters["n_features"] and len(order) == self.clusters["n_cards"]
        self.order = order
        n = len(order)
        X = self.encode([self.feats[i] for i in order])
        df = np.asarray((X > 0).sum(axis=0)).ravel()
        self.df = df
        self.idf = np.log((1.0 + n) / (1.0 + df)).astype(np.float32) + 1.0
        self.X = self.weigh(X)
        self.labels = np.array([self.lab[i] for i in order])
        self.leaves = sorted(set(self.labels.tolist()) - {-1})
        self.leaf_index = {l: j for j, l in enumerate(self.leaves)}
        C = np.zeros((len(self.leaves), len(self.vocab)), np.float32)
        for j, l in enumerate(self.leaves):
            C[j] = np.asarray(self.X[self.labels == l].mean(axis=0)).ravel()
        C /= np.linalg.norm(C, axis=1, keepdims=True)
        self.C = C
        self.leaf_size = collections.Counter(self.labels[self.labels != -1].tolist())
        self.inv_vocab = {v: k for k, v in self.vocab.items()}

    def encode(self, token_lists):
        indptr, indices = [0], []
        for fl in token_lists:
            indices.extend(self.vocab[k] for k in fl if k in self.vocab)
            indptr.append(len(indices))
        return sp.csr_matrix((np.ones(len(indices), np.float32), indices, indptr),
                             shape=(len(token_lists), len(self.vocab)))

    def weigh(self, M):
        M = M.multiply(self.idf).tocsr()
        norms = np.sqrt(M.multiply(M).sum(axis=1)).A.ravel()
        norms[norms == 0] = 1.0
        return sp.diags(1.0 / norms).dot(M).tocsr()

    def score(self, token_lists):
        """cosine of each token set against every leaf centroid -> (best_leaf, best_score, S)."""
        Y = self.weigh(self.encode(token_lists))
        S = np.asarray(Y @ self.C.T)
        j = S.argmax(axis=1)
        return np.array([self.leaves[x] for x in j]), S.max(axis=1), S

    def unseen(self, tokens):
        return [t for t in tokens if t not in self.vocab]


if __name__ == "__main__":
    print("library module; see report_ability_probe.py")
