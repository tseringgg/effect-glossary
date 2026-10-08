#!/usr/bin/env python3
"""First structural clustering pass over phase.rs's parsed card data.

Clusters CARDS on (effect type + target/filter shape) -- structural fields
already present in the data. No word overlap, no embeddings, no zone tagging:
this is a fresh pass on the new schema, not a port of the earlier experiment.

Reads   build/index.json, build/chunks/*.json   (quality flags + parsed structure)
Writes  build/clusters.json                     card -> cluster, for the explorer
        reports/clustering-structural.md        the human-readable report

Scope for this pass (deliberately narrow, see reports/clustering-structural.md):
  * clean parses only -- partial/unparsed/unmodelled/corrected entries excluded
  * top-level effects only -- sub_ability chains are NOT walked (that is
    full-tree similarity, explicitly out of scope here)
  * effect type + target/filter shape only -- no quantities, costs, conditions
"""
import collections
import json
import os
import sys
import time

import hdbscan
import importlib.metadata
import numpy as np
import scipy.sparse as sp
import scipy.sparse.csgraph as csgraph

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
REPORTS = os.path.join(HERE, "reports")

MIN_CLUSTER_SIZE = 5   # matches the earlier experiment's setting; not tuned here
MIN_SAMPLES = 5
K = 25                 # neighbours per row in the KNN graph, as before
EPS = 1e-9             # floor so an identical-signature pair (true distance 0)
                       # is never read as a missing sparse entry
CATCH_ALL_LIMIT = 0.25  # reject any run whose largest cluster exceeds this

# The standing validation set, by Scryfall oracle id so a face-name collision
# can never silently swap a card underneath us (KNOWN_LIMITATIONS.md §1).
# Ids confirmed against Scryfall's /cards/collection endpoint.
VALIDATION = [
    ("mill", [("Memory Sluice", "a30b659e-ae2b-4736-9b4f-a9805905bf75"),
              ("Seedship Broodtender", "15c994b9-901a-46d6-804b-24560a14a481")]),
    ("surveil", [("Deadly Visit", "04a3bb42-0464-4638-a6ac-d5f412c222cc"),
                 ("Raucous Theater", "04e5e84f-8fd4-43ab-8f9d-5b24646f7ae5")]),
    ("board wipe", [("Wrath of God", "34515b16-c9a4-4f98-8c77-416a7a523407"),
                    ("Damnation", "d57a8f0b-7989-4db5-8756-6f2690097252"),
                    ("Day of Judgment", "d057289d-5e28-43d5-8ff3-4a1bc723477d"),
                    ("Toxic Deluge", "afaef788-34d1-460b-b884-9d7ae6ddeb18"),
                    ("Blasphemous Act", "7a2484a9-04fd-41a0-8224-610c1c07ed10")]),
    ("single-target removal", [("Murder", "938b4e2c-88d9-4637-bc00-e228920c9a78"),
                               ("Doom Blade", "59e7f2ae-4535-4191-98be-3e65b6b2befa"),
                               ("Swords to Plowshares", "b1544f21-7e98-461b-aed5-e748b0168c52"),
                               ("Terror", "b81f041d-98db-4408-9472-c483e4a502bc")]),
]

# Noise rate of the earlier raw word-overlap pass, for direct comparison.
# NOTE: that run clustered 42,445 deduplicated effect *strings*; this one
# clusters 23,558 *cards*. Different units -- see the report.
PRIOR_WORD_OVERLAP_NOISE_PCT = 77.5


def knn_graph(X, k, t0):
    """Top-k cosine similarities per row, computed in row blocks.

    X is L2-normalised, so X @ X.T is cosine similarity directly. The full
    product is never materialised: 23.5k^2 would be 2.2 GB, and most of it is
    structural zeros between cards sharing no feature at all.
    """
    n = X.shape[0]
    rows, cols, vals = [], [], []
    block = 512
    for start in range(0, n, block):
        stop = min(start + block, n)
        S = (X[start:stop] @ X.T).toarray()
        for i in range(stop - start):
            S[i, start + i] = -1.0  # drop self
        take = min(k, S.shape[1] - 1)
        idx = np.argpartition(-S, take - 1, axis=1)[:, :take]
        for i in range(stop - start):
            sim = S[i, idx[i]]
            keep = sim > 0
            if not keep.any():
                continue
            rows.extend([start + i] * int(keep.sum()))
            cols.extend(idx[i][keep].tolist())
            vals.extend(sim[keep].tolist())
        if start % 8192 == 0:
            print(f"[{time.time()-t0:5.1f}s]   knn {start}/{n}", file=sys.stderr)
    return sp.csr_matrix((np.asarray(vals, dtype=np.float64),
                          (np.asarray(rows), np.asarray(cols))), shape=(n, n))

# Which key on an effect node carries its target/filter, in priority order.
# An effect has at most one of these in practice; first match wins.
TARGET_KEYS = ("target", "filter", "valid_card", "affected", "valid_target")


def tag(v):
    """Normalise a value that may be a bare string or an externally tagged dict."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and len(v) == 1:
        return next(iter(v))
    if v is None:
        return None
    return json.dumps(v, separators=(",", ":"))[:40]


def shape_tag(v):
    """Tag one element of a type_filters / properties list.

    These are not plain strings. `type_filters` mixes bare strings with
    negations like {"Non": "Artifact"}, and `properties` holds multi-key nodes
    like {"type": "NotColor", "color": "Black"}. Collapsing either to a single
    key loses the discriminating half -- "Non" alone cannot tell a nonartifact
    filter from a nonland one -- so the scalar payload is folded into the tag.
    """
    if isinstance(v, str):
        return v
    if not isinstance(v, dict):
        return None
    if "type" in v:
        rest = [str(x) for k, x in sorted(v.items())
                if k != "type" and isinstance(x, (str, int, float, bool))]
        return v["type"] + (":" + ",".join(rest) if rest else "")
    if len(v) == 1:
        k, x = next(iter(v.items()))
        return f"{k}:{x}" if isinstance(x, (str, int, float, bool)) else k
    return json.dumps(v, separators=(",", ":"))[:40]


def target_shape(node):
    """Structural signature of a target/filter node.

    Captures what the node *selects*, not the values it carries: the node
    type, and for `Typed` the sorted type filters, the controller scope, and
    the sorted property tags. Terror's type_filters holds a dict
    ({"Non": "Artifact"}) alongside plain strings, so every element goes
    through `shape_tag`.
    """
    if not isinstance(node, dict):
        return None
    t = node.get("type")
    if t != "Typed":
        return t
    tf = sorted(x for x in (shape_tag(f) for f in node.get("type_filters") or []) if x)
    props = sorted(x for x in (shape_tag(p) for p in node.get("properties") or []) if x)
    ctrl = node.get("controller") or "Any"
    return f"Typed[{','.join(tf)}]@{ctrl}" + (f"{{{','.join(props)}}}" if props else "")


def effect_features(eff):
    """(effect_type, target_shape) for one top-level effect node."""
    if not isinstance(eff, dict):
        return None, None
    et = eff.get("type")
    if not isinstance(et, str):
        return None, None
    for k in TARGET_KEYS:
        if k in eff:
            return et, target_shape(eff[k])
    return et, None


def card_features(d):
    """Multi-resolution feature tokens for one card.

    Three token kinds per ability, so that cards agreeing at one resolution
    still overlap when they differ at another:

      eff:<Type>                 -- the effect alone
      eff:<Type>|tgt:<shape>     -- the effect bound to what it selects
      tgt:<shape>                -- what is selected, alone

    The bare `tgt:` token is high-frequency (Typed[Creature]@Any appears on
    ~17k cards) and would swamp a raw cosine, but IDF weighting downweights it
    automatically rather than us hand-dropping it -- so "target/filter shape"
    stays a real half of the feature rather than being subordinate to effect
    type.

    Bucket of origin is deliberately NOT part of the token: Memory Sluice mills
    from `abilities` and Seedship Broodtender mills from `triggers`, and
    tagging the bucket would split them on a distinction that is about when the
    effect fires, not what it does.
    """
    feats = collections.Counter()

    def add(et, ts):
        if not et:
            return
        feats[f"eff:{et}"] += 1
        if ts:
            feats[f"eff:{et}|tgt:{ts}"] += 1
            feats[f"tgt:{ts}"] += 1

    for a in d.get("abilities") or []:
        add(*effect_features(a.get("effect")))
    for t in d.get("triggers") or []:
        add(*effect_features((t.get("execute") or {}).get("effect")))
    for r in d.get("replacements") or []:
        add(*effect_features((r.get("execute") or {}).get("effect")))
    # Statics carry no `effect` node at all -- their discriminator is `mode`,
    # and `affected` is their target/filter. Mapped onto the same feature
    # space rather than dropped, so purely-static cards are still clusterable.
    for s in d.get("static_abilities") or []:
        m = tag(s.get("mode"))
        if m:
            add(f"static:{m}", target_shape(s.get("affected")))
    return feats


def cluster_label(members, feats, top=3):
    """Describe a cluster by the feature tokens most of its members share."""
    c = collections.Counter()
    for i in members:
        for k in feats[i]:
            c[k] += 1
    n = len(members)
    parts = [f"{k} ({100*v//n}%)" for k, v in c.most_common(top) if v / n >= 0.5]
    return " · ".join(parts) if parts else "(no shared token above 50%)"


def write_report(path, steps, params, selection, labels, kept, feats, n):
    sizes = collections.Counter(int(x) for x in labels)
    noise = sizes.pop(-1, 0)
    order = sizes.most_common()
    vals = [v for _, v in order]
    members = collections.defaultdict(list)
    for i, l in enumerate(labels):
        members[int(l)].append(i)
    by_oid = {}
    for i, r in enumerate(kept):
        by_oid.setdefault(r["id"].split("/")[0], i)

    n_val_total = sum(len(c) for _, c in VALIDATION)
    n_val_clustered = sum(
        1 for _, cards in VALIDATION for _, oid in cards
        if by_oid.get(oid) is not None and int(labels[by_oid[oid]]) >= 0)

    L = []
    A = L.append
    A("# Structural clustering, first pass\n")
    A("Clusters **cards** on (effect type + target/filter shape), the structural "
      "fields already in phase.rs's parse. Not word overlap, not embeddings, and "
      "not a port of the earlier experiment -- a fresh pass on the new schema.\n")
    A("Generated by `src/cluster_structural.py`.\n")

    A("## Scope\n")
    A("| | |")
    A("|---|---|")
    for k, v in params.items():
        A(f"| {k} | `{v}` |")
    A("")
    A("Deliberately excluded from this pass: sub-`sub_ability` chains (that is "
      "full-tree similarity), quantities, costs, conditions, durations. Only the "
      "top-level effect node of each ability and the target/filter it carries.\n")

    A("## Input filter\n")
    A("Clean parses only. A card with incomplete structure would cluster on what "
      "survived the parse rather than on what the card does, and would do it "
      "silently.\n")
    A("| step | entries |")
    A("|---|---|")
    for k, v in steps.items():
        A(f"| {k} | {v:,} |")
    A("")
    A("The corrections filter is what keeps **Toxic Deluge** out of this pass: it "
      "is labelled `clean` by every phase.rs signal, but `corrections.json` "
      "records its \"pay X life\" cost parsing to `Fixed 0` "
      "(KNOWN_LIMITATIONS.md §4), so its structure is known-unreliable.\n")

    A("## Result\n")
    A(f"- **{len(sizes):,} clusters** over **{n:,} cards**")
    A(f"- **{noise:,} noise ({100.0*noise/n:.1f}%)** -- HDBSCAN is density-based and "
      "leaves a card unclustered rather than forcing it somewhere")
    A(f"- largest cluster **{vals[0]:,} cards ({100.0*vals[0]/n:.1f}% of the corpus)**")
    A(f"- median cluster {vals[len(vals)//2]}, mean {sum(vals)/len(vals):.1f}\n")

    A("### Catch-all check\n")
    A(f"The largest cluster holds {100.0*vals[0]/n:.1f}% of the corpus, well under the "
      f"{100*CATCH_ALL_LIMIT:.0f}% limit this pass rejects at. No catch-all.\n")
    A("Size distribution:\n")
    A("| bucket | clusters |")
    A("|---|---|")
    buckets = collections.Counter()
    for v in vals:
        b = ("5-9" if v < 10 else "10-24" if v < 25 else "25-49" if v < 50 else
             "50-99" if v < 100 else "100-249" if v < 250 else
             "250-499" if v < 500 else "500+")
        buckets[b] += 1
    for b in ("5-9", "10-24", "25-49", "50-99", "100-249", "250-499", "500+"):
        if buckets[b]:
            A(f"| {b} | {buckets[b]} |")
    A("")

    A("### Noise vs the earlier word-overlap pass\n")
    A("| pass | unit | noise |")
    A("|---|---|---|")
    A(f"| raw word overlap (earlier) | deduped effect strings (42,445) | "
      f"**{PRIOR_WORD_OVERLAP_NOISE_PCT}%** |")
    A(f"| structural (this pass) | cards ({n:,}) | **{100.0*noise/n:.1f}%** |")
    A("")
    A("The units differ -- the earlier pass clustered deduplicated effect *strings*, "
      "this one clusters *cards* -- so this is not a like-for-like ratio and should "
      "not be read as one. What is comparable is the qualitative outcome: under word "
      "overlap **every card in the validation set came back noise**, so the earlier "
      "pass produced no usable grouping for any card we track. This pass places "
      f"{n_val_clustered} of {n_val_total} of them in a cluster.\n")
    A("Selection method comparison (both were run; the lower-noise one wins, "
      "provided it passes the catch-all check -- a rule fixed before looking at "
      "where the validation cards landed):\n")
    A("| method | clusters | noise | largest |")
    A("|---|---|---|---|")
    for m, r in selection.items():
        A(f"| {m}{' **(selected)**' if m == params['cluster_selection_method'] else ''} "
          f"| {r['clusters']} | {100.0*r['noise']/n:.1f}% | {r['largest']} |")
    A("")

    A("## Validation against the standing test set\n")
    A("| group | card | cluster | cluster size |")
    A("|---|---|---|---|")
    assign = {}
    for g, cards in VALIDATION:
        for nm, oid in cards:
            i = by_oid.get(oid)
            if i is None:
                assign[nm] = None
                A(f"| {g} | {nm} | *excluded by input filter* | — |")
                continue
            cl = int(labels[i])
            assign[nm] = cl
            A(f"| {g} | {nm} | {'**noise**' if cl < 0 else cl} | "
              f"{len(members[cl]) if cl >= 0 else '—'} |")
    A("")
    for g, cards in VALIDATION:
        cls = [assign[nm] for nm, _ in cards if assign.get(nm) is not None]
        real = sorted({c for c in cls if c >= 0})
        nz = sum(1 for c in cls if c == -1)
        A(f"- **{g}**: " +
          (f"all clustered members in cluster {real[0]}" if len(real) == 1
           else f"split across clusters {real}") +
          (f"; {nz} noise" if nz else ""))
    A("")
    bw = {assign[nm] for nm, _ in VALIDATION[2][1] if (assign.get(nm) or -1) >= 0}
    st = {assign[nm] for nm, _ in VALIDATION[3][1] if (assign.get(nm) or -1) >= 0}
    ml = {assign[nm] for nm, _ in VALIDATION[0][1] if (assign.get(nm) or -1) >= 0}
    sv = {assign[nm] for nm, _ in VALIDATION[1][1] if (assign.get(nm) or -1) >= 0}
    A(f"- **board wipes vs single-target removal**: {sorted(bw)} vs {sorted(st)} — "
      f"{'**separated**, no shared cluster' if not (bw & st) else f'OVERLAP {sorted(bw & st)}'}")
    A(f"- **mill vs surveil**: {sorted(ml)} vs {sorted(sv)} — "
      f"{'**separated**, no shared cluster' if not (ml & sv) else f'OVERLAP {sorted(ml & sv)}'}\n")

    val_clusters = {c for c in assign.values() if c is not None and c >= 0}
    A("### What the validation clusters actually contain\n")
    for cl in sorted(val_clusters):
        who = [nm for nm, c in assign.items() if c == cl]
        mem = sorted(kept[i]["name"] for i in members[cl])
        A(f"**cluster {cl}** ({len(mem)} cards) — contains {', '.join(who)}  ")
        A(f"`{cluster_label(members[cl], feats)}`  ")
        A("> " + ", ".join(mem[:18]) + (f" … +{len(mem)-18} more" if len(mem) > 18 else ""))
        A("")

    A("## Sample clusters (not validation cases)\n")
    A("Picked across the size range, skipping any cluster a validation card is in, "
      "so these are cards we are not specifically tracking.\n")
    picks, seen = [], set()
    for cl, sz in order:
        if cl in val_clusters or sz < 6:
            continue
        band = ("large" if sz >= 200 else "medium" if sz >= 40 else "small")
        if band in seen:
            continue
        seen.add(band)
        picks.append(cl)
        if len(picks) >= 3:
            break
    for cl, _ in order:
        if len(picks) >= 5:
            break
        if cl not in val_clusters and cl not in picks and 8 <= len(members[cl]) <= 120:
            picks.append(cl)
    for cl in picks:
        mem = sorted(kept[i]["name"] for i in members[cl])
        A(f"**cluster {cl}** ({len(mem)} cards)  ")
        A(f"`{cluster_label(members[cl], feats)}`  ")
        A("> " + ", ".join(mem[:20]) + (f" … +{len(mem)-20} more" if len(mem) > 20 else ""))
        A("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


def load():
    rows = json.load(open(os.path.join(BUILD, "index.json"), encoding="utf-8"))["rows"]
    chunks = {}
    for n in range(64):
        p = os.path.join(BUILD, "chunks", f"{n}.json")
        if os.path.exists(p):
            chunks[n] = json.load(open(p, encoding="utf-8"))
    return rows, chunks


def main():
    t0 = time.time()
    rows, chunks = load()
    total = len(rows)

    # --- filter to trustworthy structure only ------------------------------
    steps = collections.OrderedDict()
    steps["all entries"] = total
    keep = [r for r in rows if r["q"] == "clean"]
    steps["quality == clean"] = len(keep)
    keep = [r for r in keep if not r["sg"]]
    steps["  minus unmodelled-node entries"] = len(keep)
    keep = [r for r in keep if not r.get("corr")]
    steps["  minus corrections-flagged entries"] = len(keep)

    feats, kept = [], []
    for r in keep:
        f = card_features(chunks[r["ch"]][r["id"]])
        if f:
            feats.append(f)
            kept.append(r)
    steps["  minus entries with no extractable feature"] = len(kept)

    # --- encode: binary presence, IDF-weighted, L2-normalised --------------
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

    n_sigs = len({tuple(sorted(f)) for f in feats})
    print(f"[{time.time()-t0:5.1f}s] {n} cards, {v} features, "
          f"{n_sigs} distinct signatures", file=sys.stderr)

    # --- sparse KNN graph over all cards -----------------------------------
    # Every card is clustered individually rather than deduplicating to
    # distinct signatures first. HDBSCAN is density-based, and collapsing a
    # signature shared by 3,000 cards down to one point destroys exactly the
    # density it clusters on -- an earlier attempt here did that and produced
    # a single cluster holding 87% of the corpus. A K-nearest-neighbour graph
    # keeps all n points while staying far inside memory, and matches the
    # approach the earlier word-overlap experiment used.
    S_knn = knn_graph(X, K, t0)

    # Sparse precomputed HDBSCAN treats a missing entry as unreachable, so the
    # stored distances must satisfy three things (the earlier experiment hit
    # all three): symmetry, at least `min_samples` stored entries per row, and
    # a non-zero floor -- thousands of cards here share a byte-identical
    # signature, and a true 0.0 distance stored explicitly is indistinguishable
    # from "not stored" in a sparse matrix.
    D = S_knn.tocoo()
    dist = np.maximum(1.0 - D.data, EPS)
    D = sp.csr_matrix((dist, (D.row, D.col)), shape=S_knn.shape, dtype=np.float64)
    D = D.maximum(D.T)
    D.setdiag(0.0)
    D.eliminate_zeros()
    degree = np.diff(D.indptr)
    thin = int((degree < MIN_SAMPLES).sum())
    print(f"[{time.time()-t0:5.1f}s] KNN graph: {D.nnz} edges, "
          f"min degree {degree.min()}, rows below min_samples: {thin}",
          file=sys.stderr)

    # A KNN graph is not connected -- cards sharing no feature with their
    # neighbours form islands, and this one has 8 components plus rows holding
    # fewer than min_samples edges. Both are refused by sparse-precomputed
    # HDBSCAN. `max_dist` is the library's own answer: any pair absent from the
    # graph is treated as sitting at that distance. 1.0 is not a padding
    # constant here, it is the true upper bound of cosine distance on
    # non-negative vectors -- two cards sharing no feature really are maximally
    # dissimilar -- so nothing is invented, unlike bridging islands with
    # synthetic short edges.
    # The library rejects a disconnected matrix before it ever reads max_dist,
    # so both are needed: cluster each component separately, and inside a
    # component let max_dist cover rows holding fewer than min_samples edges.
    n_comp, comp = csgraph.connected_components(D, directed=False)
    comp_sizes = collections.Counter(comp.tolist())
    degree = np.diff(D.indptr)
    print(f"[{time.time()-t0:5.1f}s] {n_comp} components (largest "
          f"{max(comp_sizes.values())}), min degree {degree.min()}",
          file=sys.stderr)

    results = {}
    for method in ("eom", "leaf"):
        lab = np.full(n, -1, dtype=int)
        nxt = 0
        for c, size in comp_sizes.most_common():
            if size < MIN_CLUSTER_SIZE:
                continue  # too small to hold a cluster: stays noise
            idx = np.flatnonzero(comp == c)
            part = hdbscan.HDBSCAN(
                min_cluster_size=MIN_CLUSTER_SIZE,
                min_samples=MIN_SAMPLES,
                metric="precomputed",
                cluster_selection_method=method,
                max_dist=1.0,
            ).fit_predict(D[idx][:, idx].tocsr())
            hit = part >= 0
            if hit.any():
                lab[idx[hit]] = part[hit] + nxt
                nxt += int(part.max()) + 1
        sizes = collections.Counter(int(x) for x in lab)
        noise = sizes.pop(-1, 0)
        biggest = max(sizes.values()) if sizes else 0
        results[method] = (lab, len(sizes), noise, biggest)
        print(f"[{time.time()-t0:5.1f}s] {method}: {len(sizes)} clusters, "
              f"noise {100.0*noise/n:.1f}%, largest {biggest} "
              f"({100.0*biggest/n:.1f}%)", file=sys.stderr)

    # Selection rule, fixed in advance so this is not picked by how the
    # validation cards happen to land: reject any configuration whose largest
    # cluster exceeds CATCH_ALL_LIMIT of the corpus (that is the catch-all
    # failure, not a cluster), then prefer lower noise.
    ok = [m for m, (_, _, _, big) in results.items()
          if big <= CATCH_ALL_LIMIT * n]
    if not ok:
        raise SystemExit(
            "both selection methods produced a catch-all cluster; "
            "the feature space needs rethinking before tuning further")
    method = min(ok, key=lambda m: results[m][2])
    labels, n_clusters, noise, biggest = results[method]
    print(f"[{time.time()-t0:5.1f}s] selected cluster_selection_method={method}",
          file=sys.stderr)

    out = {
        "params": {
            "min_cluster_size": MIN_CLUSTER_SIZE,
            "min_samples": MIN_SAMPLES,
            "k_neighbours": K,
            "metric": "cosine on IDF-weighted binary features, sparse KNN precomputed",
            "cluster_selection_method": method,
            "library": f"hdbscan {importlib.metadata.version('hdbscan')}",
            "unit": "card",
            "scope": "clean parses only; top-level effects only; no sub_ability walk",
        },
        "selection": {m: {"clusters": r[1], "noise": int(r[2]), "largest": int(r[3])}
                      for m, r in results.items()},
        "filter_steps": steps,
        "n_cards": n,
        "n_features": v,
        "n_signatures": n_sigs,
        "cards": {kept[i]["id"]: int(labels[i]) for i in range(n)},
        "names": {kept[i]["id"]: kept[i]["name"] for i in range(n)},
    }
    # Per-cluster labels, so the explorer can say what a cluster *is* rather
    # than only showing a number.
    grouped = collections.defaultdict(list)
    for i, l in enumerate(labels):
        if l >= 0:
            grouped[int(l)].append(i)
    out["labels"] = {str(c): cluster_label(m, feats) for c, m in grouped.items()}
    out["sizes"] = {str(c): len(m) for c, m in grouped.items()}
    with open(os.path.join(BUILD, "clusters.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"), ensure_ascii=False)

    os.makedirs(REPORTS, exist_ok=True)
    write_report(os.path.join(REPORTS, "clustering-structural.md"),
                 steps, out["params"], out["selection"], labels, kept, feats, n)

    sizes = collections.Counter(int(x) for x in labels)
    noise = sizes.pop(-1, 0)
    print(json.dumps({
        "cards_clustered": n,
        "clusters": len(sizes),
        "noise": noise,
        "noise_pct": round(100.0 * noise / n, 1),
        "largest": sizes.most_common(8),
    }, indent=1))


if __name__ == "__main__":
    main()
