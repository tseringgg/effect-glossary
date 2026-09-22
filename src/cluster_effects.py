"""First HDBSCAN pass over the deduped effect glossary, raw overlap only.

Distance is 1 - raw Jaccard (similarity.py's `raw` mode -- unweighted, no IDF,
same tokenizer and card-name masking as the rest of the tool). No custom
clustering math: HDBSCAN does the clustering -- density-based, no
predetermined cluster count, explicit noise label -1. Standard,
scikit-learn-compatible library, not hand-rolled.

Library note: `sklearn.cluster.HDBSCAN` (1.9.0, tried first) was dropped for
the standalone `hdbscan` package instead. Its metric="precomputed" sparse
path has a real bug at this scale -- reproduced on a 10,000-effect slice of
this exact data (MemoryError inside its own _tree.pyx bfs_from_hierarchy),
confirmed NOT an artifact of the padding below (still happens with zero added
edges, just the natural KNN graph), and confirmed NOT a general sparse-vs-dense
issue (the identical distances as a dense array cluster correctly in 7s). The
standalone `hdbscan` package -- the original reference implementation
sklearn's port is based on, itself scikit-learn-compatible (BaseEstimator,
.fit_predict, .labels_) -- handles the identical sparse matrix correctly.

Why this isn't just "build the distance matrix and call .fit()" in the first
place: HDBSCAN(metric="precomputed") on a DENSE array upcasts to float64
internally regardless of input dtype, so a full 42,445 x 42,445 matrix needs
~14.4 GB -- more than this machine has (17 GB total, ~6 GB free). The
alternative both implementations accept is a SPARSE precomputed distance
matrix, but that path carries two hard requirements (checked in sklearn's
source, sklearn/cluster/_hdbscan/hdbscan.py `_brute_mst`, and enforced the
same way by the standalone package) and raises rather than warns:

  1. every row must have at least `min_samples` stored entries
  2. the whole graph must be a single connected component

A plain top-K nearest-neighbour graph -- cheap to compute, ~45s via the same
chunked sparse matmul trick build_similarity_page.py uses -- satisfies
neither in general. Measured on this corpus at K=25: 52 effects share not
even one token with any other effect (genuinely isolated under raw overlap --
not a bug, just the honest result for maximally idiosyncratic wording), and
the K=25 graph over the remaining effects splits into 62 connected
components: one giant one (42,184 of 42,259 non-empty effects) plus ~60 tiny
islands of 2-24.

_bridge_and_pad below adds the minimum extra edges needed to make the sparse
structure legal, using values that are honest rather than invented: a small
fixed pool of "anchor" effects -- nodes that already have a full K=25 real
neighbour list, so by construction they sit inside the giant component -- get
connected to any node that still needs more stored entries or still needs a
route into the giant component. The edge weight is the ACTUAL raw-Jaccard
distance to that anchor (computed directly from the token sets), which is
almost always 1.0 for these pairs -- not a placeholder, simply the true
distance for two effects that share nothing, made explicit instead of left as
an absent sparse entry. The 52 zero-real-neighbour effects, and the 186
zero-token effects already documented in similarity-validation.md, are never
padded into looking connected: they are excluded from the HDBSCAN input
outright and reported as noise directly, for the same reason raw overlap
already treats them as scoring 0 against everything.
"""
import collections
import json
import os
import re
import time

import hdbscan
import numpy as np
import scipy.sparse as sp
import scipy.sparse.csgraph as csgraph

import similarity as S

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(HERE, os.pardir, "reports")
FULL = os.path.join(HERE, os.pardir, "data", "full")
CLUSTERS_PATH = os.path.join(FULL, "clusters.json")
REPORT_PATH = os.path.join(REPORTS, "clustering.md")

K = 25                  # neighbours per row in the KNN graph fed to HDBSCAN
MIN_CLUSTER_SIZE = 5    # sklearn default; scope guard says don't tune yet
ANCHOR_POOL = 15        # candidate "well-connected hub" nodes for padding
EPS = 1e-9              # floor so a real distance-0 edge (identical token
                        # sets) is never mistaken for a missing sparse entry


def build_binary_matrix(corpus, indices, vocab, col):
    indptr, cols = [0], []
    for i in indices:
        cols.extend(sorted(col[w] for w in corpus.sets[i]))
        indptr.append(len(cols))
    cols = np.array(cols, dtype=np.int32)
    indptr = np.array(indptr, dtype=np.int64)
    shape = (len(indices), len(vocab))
    return sp.csr_matrix((np.ones(len(cols), dtype=np.float32), cols, indptr), shape=shape)


def knn_jaccard(binary, k=K, chunk=512, progress=None):
    """Top-k real (jaccard > 0) neighbours per row, chunked sparse matmul --
    same approach as build_similarity_page.rank_all, raw mode only (no IDF
    matrix needed here, per scope). Returns adj: list[dict[col -> jaccard]]."""
    n = binary.shape[0]
    sizes = binary.getnnz(axis=1).astype(np.float32)
    bt = binary.T.tocsr()
    adj = [dict() for _ in range(n)]
    for start in range(0, n, chunk):
        stop = min(start + chunk, n)
        rows = np.arange(start, stop)
        inter = (binary[start:stop] @ bt).toarray()
        union = sizes[rows][:, None] + sizes[None, :] - inter
        np.maximum(union, 1.0, out=union)
        jac = inter / union
        jac[rows - start, rows] = -1.0
        pool = min(jac.shape[1], max(k * 4, 64))
        cand = np.argpartition(-jac, pool - 1, axis=1)[:, :pool]
        vals = np.take_along_axis(jac, cand, axis=1)
        order = np.lexsort((cand, -vals), axis=1)
        top_idx = np.take_along_axis(cand, order, axis=1)[:, :k]
        top_val = np.take_along_axis(vals, order, axis=1)[:, :k]
        for r in range(stop - start):
            real = top_val[r] > 0
            for c, v in zip(top_idx[r][real], top_val[r][real]):
                adj[start + r][int(c)] = float(v)
        if progress:
            progress(stop, n)
    return adj


def _symmetrize(adj):
    """Union both directions -- jaccard(i,j) == jaccard(j,i) always, so this
    never creates a conflicting value, only fills in a missing direction."""
    for i, nbrs in enumerate(adj):
        for j, v in list(nbrs.items()):
            adj[j].setdefault(i, v)
    return adj


def _jaccard(a, b):
    if not a and not b:
        return 0.0
    u = len(a | b)
    return len(a & b) / u if u else 0.0


def bridge_and_pad(adj, sets, min_samples, pool_size=ANCHOR_POOL):
    """Make the sparse structure legal for HDBSCAN: every row >= min_samples
    stored entries, whole graph one connected component. Mutates `adj` in
    place. Returns (anchors, n_components_before, n_rows_touched)."""
    n = len(adj)
    degree = np.array([len(a) for a in adj])

    # Anchors: nodes that already have a full K-neighbour list, in index
    # order for determinism -- exactly the "generic, well connected" effects,
    # which by construction sit inside whichever component is largest.
    anchors = [i for i in range(n) if degree[i] >= K][:pool_size]
    if not anchors:
        raise RuntimeError("no fully-connected anchor candidates -- K too small")

    rows_a = np.repeat(np.arange(n), degree)
    cols_a = np.array([c for a in adj for c in a], dtype=np.int64)
    vals_a = np.array([v for a in adj for v in a.values()], dtype=np.float64)
    graph = sp.coo_matrix((1.0 - vals_a, (rows_a, cols_a)), shape=(n, n)).tocsr()
    n_components, labels = csgraph.connected_components(graph, directed=False)
    anchor_component = labels[anchors[0]]
    assert all(labels[a] == anchor_component for a in anchors), (
        "anchor pool split across components -- raise ANCHOR_POOL or K")

    touched = 0
    for i in range(n):
        needs_bridge = labels[i] != anchor_component
        needs_degree = degree[i] < min_samples
        if not (needs_bridge or needs_degree):
            continue
        touched += 1
        want = max(1 if needs_bridge else 0, min_samples - degree[i])
        added = 0
        for a in anchors:
            if added >= want:
                break
            if a in adj[i] or a == i:
                continue
            v = _jaccard(sets[i], sets[a])  # true distance, honest even when 0
            adj[i][a] = v
            adj[a].setdefault(i, v)
            added += 1
    return anchors, n_components, touched


def build_distance_matrix(adj):
    n = len(adj)
    degree = np.array([len(a) for a in adj])
    rows = np.repeat(np.arange(n), degree)
    cols = np.array([c for a in adj for c in a], dtype=np.int64)
    vals = np.array([v for a in adj for v in a.values()], dtype=np.float64)
    # Floored at EPS, not 0.0: the standalone hdbscan package's sparse path
    # treats a stored value of exactly 0.0 as a MISSING entry, not a real
    # "these are identical" edge (confirmed by its own error message: "less
    # than min_samples neighbors" fired on a graph where every row already
    # had >= min_samples stored entries, until this floor was added). Two
    # different deduped effects with identical raw Jaccard=1.0 (same token
    # set) are common enough in this corpus to hit this. EPS is far below the
    # smallest real gap between distinct Jaccard values, so it changes no
    # ordering -- it only keeps a genuine zero-distance edge from vanishing.
    dist = np.maximum(1.0 - vals, EPS)
    X = sp.coo_matrix((dist, (rows, cols)), shape=(n, n)).tocsr()
    # X must be exactly symmetric -- it is, by construction (_symmetrize and
    # bridge_and_pad always write both directions with the identical value),
    # but sort/dedupe indices for a clean CSR.
    X.sort_indices()
    return X


def cluster(progress=None):
    """Returns (labels, kept_indices, excluded) all aligned to corpus order.
    labels[i] is -1 for noise/excluded, else a 0-based cluster id.
    excluded is {index: reason} for effects never handed to HDBSCAN at all."""
    corpus = S.load_corpus()
    n = corpus.n
    excluded = {i: "no tokens (empty after stopwords/masking)"
                for i, s in enumerate(corpus.sets) if not s}
    kept = [i for i in range(n) if i not in excluded]

    vocab = sorted(corpus.df)
    col = {w: k for k, w in enumerate(vocab)}
    binary = build_binary_matrix(corpus, kept, vocab, col)
    adj = knn_jaccard(binary, progress=progress)
    adj = _symmetrize(adj)

    isolated = [k for k, a in enumerate(adj) if not a]
    for k in isolated:
        excluded[kept[k]] = "0 effects share even one token with it (raw Jaccard 0 to the whole corpus)"
    keep2 = [k for k in range(len(kept)) if k not in set(isolated)]
    remap = {old: new for new, old in enumerate(keep2)}
    adj2 = [adj[k] for k in keep2]
    adj2 = [{remap[c]: v for c, v in a.items()} for a in adj2]
    sets2 = [corpus.sets[kept[k]] for k in keep2]

    min_samples = MIN_CLUSTER_SIZE
    anchors, n_components_before, touched = bridge_and_pad(adj2, sets2, min_samples)
    X = build_distance_matrix(adj2)

    t0 = time.time()
    # sklearn.cluster.HDBSCAN (1.9.0) was tried first -- it corrupts on this
    # exact sparse-precomputed input at >~10k points (MemoryError inside its
    # own _tree.pyx bfs_from_hierarchy; reproduced on a 10k-effect slice, and
    # confirmed NOT a padding artifact -- it happens even with zero added
    # edges, just the natural KNN graph). The standalone `hdbscan` package
    # (the original reference implementation this port is based on, still
    # scikit-learn-compatible: BaseEstimator, .fit_predict, .labels_) handles
    # the identical matrix correctly. Using that instead.
    model = hdbscan.HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE, min_samples=min_samples,
                             metric="precomputed")
    sub_labels = model.fit_predict(X)
    fit_seconds = time.time() - t0

    labels = np.full(n, -1, dtype=np.int64)
    for new, old_k in enumerate(keep2):
        labels[kept[old_k]] = sub_labels[new]

    meta = {
        "n_effects": n, "n_excluded": len(excluded), "n_clustered_input": len(keep2),
        "k": K, "min_cluster_size": MIN_CLUSTER_SIZE, "min_samples": min_samples,
        "n_components_before_bridging": n_components_before,
        "n_anchors": len(anchors), "n_rows_bridged_or_padded": touched,
        "fit_seconds": fit_seconds,
    }
    return labels, excluded, meta, corpus


# -- reporting --------------------------------------------------------------

def summarize(labels, excluded, meta, corpus, out):
    counts = collections.Counter(l for l in labels if l >= 0)
    n_noise_alg = int((labels == -1).sum()) - len(excluded)
    out.append("## Cluster summary")
    out.append("")
    out.append("- %s effects total" % "{:,}".format(meta["n_effects"]))
    out.append("- %s excluded before clustering (0 tokens, or 0 shared tokens with anything): "
               "not fed to HDBSCAN, reported as noise directly" % "{:,}".format(meta["n_excluded"]))
    out.append("- %s effects handed to HDBSCAN" % "{:,}".format(meta["n_clustered_input"]))
    out.append("- **%s clusters found**" % "{:,}".format(len(counts)))
    out.append("- **%s effects labeled noise by HDBSCAN itself** (%.1f%% of the input; %.1f%% "
               "of the whole corpus)"
               % ("{:,}".format(n_noise_alg), 100.0 * n_noise_alg / meta["n_clustered_input"],
                  100.0 * n_noise_alg / meta["n_effects"]))
    out.append("- **%.1f%% of the whole corpus is noise/unclustered** (excluded + HDBSCAN noise "
               "combined: %s of %s)"
               % (100.0 * (labels == -1).sum() / meta["n_effects"],
                  "{:,}".format(int((labels == -1).sum())), "{:,}".format(meta["n_effects"])))
    out.append("- KNN graph: K=%d, %d connected components before bridging (1 giant + %d small "
               "islands), %d rows needed bridging/degree padding via %d anchor effects"
               % (meta["k"], meta["n_components_before_bridging"],
                  meta["n_components_before_bridging"] - 1,
                  meta["n_rows_bridged_or_padded"], meta["n_anchors"]))
    out.append("- HDBSCAN fit: %.0fs (min_cluster_size=%d, min_samples=%d, metric=precomputed)"
               % (meta["fit_seconds"], meta["min_cluster_size"], meta["min_samples"]))
    out.append("")
    sizes = sorted(counts.values(), reverse=True)
    out.append("Size distribution (top 15 largest, then a histogram of the rest):")
    out.append("")
    out.append("| cluster rank | size | % of corpus |")
    out.append("|--:|--:|--:|")
    for rank, sz in enumerate(sizes[:15], 1):
        out.append("| %d | %d | %.2f%% |" % (rank, sz, 100.0 * sz / meta["n_effects"]))
    out.append("")
    biggest = sizes[0] if sizes else 0
    flag = ("**Flagged: the largest cluster holds %.1f%% of the corpus** -- large enough to "
            "check by hand (see sample below) for whether the algorithm is discriminating or "
            "just lumping generic short effects together." % (100.0 * biggest / meta["n_effects"])
            if biggest / meta["n_effects"] > 0.02 else
            "No cluster holds more than 2% of the corpus -- no single-cluster collapse.")
    out.append(flag)
    out.append("")
    hist = collections.Counter()
    for sz in sizes:
        if sz < 10:
            hist[str(sz)] += 1
        elif sz < 25:
            hist["10-24"] += 1
        elif sz < 50:
            hist["25-49"] += 1
        elif sz < 100:
            hist["50-99"] += 1
        else:
            hist["100+"] += 1
    out.append("| bucket | # clusters |")
    out.append("|---|--:|")
    for k in sorted(hist, key=lambda k: (len(k) > 2, k)):
        out.append("| %s | %d |" % (k, hist[k]))
    out.append("")


def cluster_members(labels, corpus, cid, limit=None):
    idx = [i for i in range(corpus.n) if labels[i] == cid]
    return idx[:limit] if limit else idx


def fmt_effect(corpus, i, width=90):
    t = corpus.effects[i]["raw_text"]
    return (t[:width - 1] + "…") if len(t) > width else t


def validation_cases(labels, corpus, out):
    out.append("## Validation: known cases")
    out.append("")
    groups = [
        ("Mill", ["Target player mills five cards.", "Target player mills two cards.",
                  "Target opponent mills seven cards."]),
        ("Surveil", ["Surveil 1. (Look at the top card of your library. You may put it into "
                     "your graveyard.)",
                     "Surveil 2. (Look at the top two cards of your library, then put any "
                     "number of them into your graveyard and the rest on top of your library "
                     "in any order.)"]),
        ("Board wipes", ["Destroy all creatures.", "Destroy all creatures. They can't be "
                         "regenerated.", "All creatures get -X/-X until end of turn.",
                         "Blasphemous Act deals 13 damage to each creature."]),
        ("Single-target removal", ["Destroy target creature.", "Destroy target nonblack "
                                   "creature.", "Exile target creature. Its controller gains "
                                   "life equal to its power."]),
    ]
    rows = []
    for title, texts in groups:
        for t in texts:
            i = corpus.exact(t)
            if i is None:
                rows.append((title, t, None, None))
                continue
            cid = int(labels[i])
            size = int((labels == cid).sum()) if cid >= 0 else None
            rows.append((title, t, cid, size))
    out.append("| group | effect | cluster | cluster size |")
    out.append("|---|---|--:|--:|")
    for title, t, cid, size in rows:
        cid_s = "noise (-1)" if cid == -1 else ("not found" if cid is None else str(cid))
        out.append("| %s | %s | %s | %s |" % (title, t.replace("|", "\\|")[:70], cid_s,
                                                size if size is not None else "—"))
    out.append("")

    def report_cluster(title, text, out):
        i = corpus.exact(text)
        if i is None or labels[i] < 0:
            return
        cid = int(labels[i])
        members = cluster_members(labels, corpus, cid)
        out.append("**%s** -- \"%s\" is in cluster %d (%d members):" % (title, text[:60], cid, len(members)))
        out.append("")
        for m in members[:40]:
            out.append("- %s" % fmt_effect(corpus, m, 100).replace("|", "\\|"))
        if len(members) > 40:
            out.append("- … and %d more" % (len(members) - 40))
        out.append("")

    out.append("### Full membership for the probe clusters")
    out.append("")
    seen = set()
    for title, texts in groups:
        for t in texts:
            i = corpus.exact(t)
            if i is None or labels[i] < 0:
                continue
            cid = int(labels[i])
            if cid in seen:
                continue
            seen.add(cid)
            report_cluster(title, t, out)


def sample_clusters(labels, corpus, out, picks=5):
    counts = collections.Counter(l for l in labels if l >= 0)
    sizes = sorted(counts.items(), key=lambda p: -p[1])
    n = len(sizes)
    if n == 0:
        return
    idxs = sorted(set(max(0, min(n - 1, round(x))) for x in
                      np.linspace(0, n - 1, min(picks, n))))
    out.append("## Sample clusters (varying sizes, not cherry-picked for validation)")
    out.append("")
    for rank in idxs:
        cid, size = sizes[rank]
        members = cluster_members(labels, corpus, cid)
        out.append("### Cluster %d -- %d effects (size rank %d of %d)" % (cid, size, rank + 1, n))
        out.append("")
        for m in members[:50]:
            out.append("- %s" % fmt_effect(corpus, m, 100).replace("|", "\\|"))
        if len(members) > 50:
            out.append("- … and %d more" % (len(members) - 50))
        out.append("")


_LEAD_WORD = re.compile(r"[a-zA-Z]+")


def largest_cluster_diversity(labels, corpus, out):
    """Automatic check on the single largest cluster: how many genuinely
    different ABILITIES does it hold, proxied by distinct leading words
    (stripping any "When this creature enters, " / "I — " lead-in first)?
    A raw-overlap cluster can be internally coherent even at moderate size (a
    templated wording family), or it can be a grab-bag stitched together by
    density chaining through short, generic shared tokens -- this is the
    difference between those two, measured rather than eyeballed."""
    counts = collections.Counter(l for l in labels if l >= 0)
    if not counts:
        return
    cid = counts.most_common(1)[0][0]
    members = cluster_members(labels, corpus, cid)
    leads = []
    for m in members:
        t = corpus.effects[m]["raw_text"]
        t = re.sub(r"^(when(ever)? [^,]+,\s*|[ivx]+\s*—\s*)", "", t, flags=re.I)
        w = _LEAD_WORD.search(t)
        leads.append(w.group(0).lower() if w else "?")
    tally = collections.Counter(leads)
    distinct = len(tally)
    out.append("## Automatic check: largest cluster's internal diversity")
    out.append("")
    out.append("Cluster %d (%d effects, the largest) breaks down by leading word (lead-ins like "
               "\"When this creature enters,\" stripped first) into **%d distinct leading words**: %s."
               % (cid, len(members), distinct,
                  ", ".join("`%s`×%d" % (w, n) for w, n in tally.most_common(12))))
    out.append("")
    if distinct >= max(3, len(members) // 20):
        out.append("**Flagged:** that many distinct lead words for one cluster suggests it is "
                   "several genuinely different effects/keywords chained together by shared "
                   "short, generic tokens (costs, reminder-adjacent words) rather than one "
                   "coherent family -- see the full membership above under \"Sample clusters\" "
                   "and judge for yourself.")
    else:
        out.append("Low diversity relative to size -- looks like one coherent templated family, "
                   "not a grab-bag.")
    out.append("")


def write_clusters_json(labels, corpus):
    by_cluster = collections.defaultdict(list)
    for i, l in enumerate(labels):
        if l >= 0:
            by_cluster[int(l)].append(corpus.effects[i]["effect_id"])
    data = {
        "effect_cluster": {corpus.effects[i]["effect_id"]: int(labels[i])
                            for i in range(corpus.n) if labels[i] >= 0},
        "clusters": {str(cid): members for cid, members in by_cluster.items()},
    }
    with open(CLUSTERS_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    return CLUSTERS_PATH


def main():
    def progress(done, total):
        print("\r  knn %d/%d" % (done, total), end="", flush=True)

    labels, excluded, meta, corpus = cluster(progress=progress)
    print()

    out = ["# Raw-overlap HDBSCAN clustering -- first pass", ""]
    out.append("`hdbscan.HDBSCAN` (the standard scikit-learn-compatible reference implementation; "
               "see the note at the top of `cluster_effects.py` for why sklearn's own newer port "
               "was dropped) over 1 - raw Jaccard distance (`similarity.py`'s `raw` mode: "
               "stopword-stripped tokens, card-name masking on, no IDF weighting). Parameters left "
               "at sensible defaults (`min_cluster_size=5`, `min_samples=min_cluster_size`) -- "
               "first honest pass, not tuned yet.")
    out.append("")
    summarize(labels, excluded, meta, corpus, out)
    validation_cases(labels, corpus, out)
    sample_clusters(labels, corpus, out)
    largest_cluster_diversity(labels, corpus, out)

    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    path = write_clusters_json(labels, corpus)
    print("wrote %s" % os.path.normpath(REPORT_PATH))
    print("wrote %s" % os.path.normpath(path))


if __name__ == "__main__":
    main()
