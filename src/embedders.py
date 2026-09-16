"""Three-model embedding ensemble fused with Reciprocal Rank Fusion.

Models: TF-IDF (sklearn), intfloat/e5-small-v2, BAAI/bge-base-en-v1.5.

Fusion is rank-based, NOT score averaging: the three models' similarity scores
are not on comparable scales.

    rrf_score(doc) = sum over embedders of 1 / (60 + rank_of_doc_in_that_embedder)

with 1-based ranks. Every embedder ranks every document, so every document
receives a contribution from all three.

Embedders are swappable: pass `stub=True` (or set EFFECT_GLOSSARY_STUB=1) to
use a deterministic offline embedder for fast iteration. Validation runs use
the real models.
"""
import os
import re

import numpy as np

RRF_K = 60


# --------------------------------------------------------------------------
# Embedder implementations
# --------------------------------------------------------------------------
class BaseEmbedder:
    name = "base"

    def index(self, texts):
        raise NotImplementedError

    def similarities(self, query):
        """Return a float array of similarity to each indexed doc, in order."""
        raise NotImplementedError


class TfidfEmbedder(BaseEmbedder):
    name = "tfidf"

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        # sublinear_tf dampens raw repetition a little; word 1-2 grams.
        self._vec = TfidfVectorizer(
            # stop_words is load-bearing: without it the leading "a" in queries like
            # "a board wipe" is the only matching token, so TF-IDF returns the same
            # bogus ranking for every such query.
            lowercase=True, ngram_range=(1, 2), sublinear_tf=True, stop_words="english",
            token_pattern=r"(?u)\b\w[\w'+/-]*\b",
        )
        self._mat = None

    def index(self, texts):
        self._mat = self._vec.fit_transform(texts)

    def similarities(self, query):
        from sklearn.metrics.pairwise import cosine_similarity
        qv = self._vec.transform([query])
        return cosine_similarity(qv, self._mat)[0]


class SentenceTransformerEmbedder(BaseEmbedder):
    """Wraps a sentence-transformers model, applying its documented prefixes."""

    def __init__(self, name, model_id, query_prefix="", doc_prefix=""):
        self.name = name
        self.model_id = model_id
        self.query_prefix = query_prefix
        self.doc_prefix = doc_prefix
        self._model = None
        self._emb = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_id)
        return self._model

    def index(self, texts):
        m = self._load()
        self._emb = m.encode(
            [self.doc_prefix + t for t in texts],
            normalize_embeddings=True, show_progress_bar=False,
        )

    def similarities(self, query):
        m = self._load()
        q = m.encode([self.query_prefix + query],
                     normalize_embeddings=True, show_progress_bar=False)[0]
        return self._emb @ q


class StubEmbedder(BaseEmbedder):
    """Deterministic offline stand-in: hashed bag-of-words cosine.

    Not a quality model -- only for wiring up the pipeline without downloading
    weights. `variant` shifts the hash so the three stubs disagree, which
    exercises the fusion path.
    """

    def __init__(self, name, variant=0, dims=512):
        self.name = name
        self.variant = variant
        self.dims = dims
        self._mat = None

    def _vec(self, text):
        v = np.zeros(self.dims, dtype=np.float32)
        for tok in re.findall(r"[a-z0-9']+", text.lower()):
            h = (hash((tok, self.variant)) % self.dims)
            v[h] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def index(self, texts):
        self._mat = np.vstack([self._vec(t) for t in texts])

    def similarities(self, query):
        return self._mat @ self._vec(query)


def build_embedders(stub=None):
    if stub is None:
        stub = os.environ.get("EFFECT_GLOSSARY_STUB") == "1"
    if stub:
        return [StubEmbedder("tfidf", 0),
                StubEmbedder("e5-small-v2", 1),
                StubEmbedder("bge-base-en-v1.5", 2)]
    return [
        TfidfEmbedder(),
        SentenceTransformerEmbedder(
            "e5-small-v2", "intfloat/e5-small-v2",
            query_prefix="query: ", doc_prefix="passage: ",
        ),
        SentenceTransformerEmbedder(
            "bge-base-en-v1.5", "BAAI/bge-base-en-v1.5",
            query_prefix="Represent this sentence for searching relevant passages: ",
        ),
    ]


# --------------------------------------------------------------------------
# Ensemble + RRF
# --------------------------------------------------------------------------
def ranks_from_scores(doc_ids, scores, tol=1e-9):
    """1-based STANDARD COMPETITION ranking by descending score: documents with
    equal scores share the smallest rank (1,1,3,...).

    Ties must share a rank. If they were instead broken arbitrarily, an
    embedder with no signal for a query -- TF-IDF whenever the query shares no
    vocabulary with any document -- would hand RRF a full, confident-looking
    ordering built out of nothing. With shared ranks, an all-tied embedder
    gives every document rank 1, contributing the same 1/(60+1) to each, so it
    cancels out of the fusion instead of steering it.
    """
    order = sorted(range(len(doc_ids)), key=lambda i: -float(scores[i]))
    ranks = {}
    prev = None
    cur = 0
    for pos, i in enumerate(order, start=1):
        s = float(scores[i])
        if prev is None or abs(s - prev) > tol:
            cur = pos
            prev = s
        ranks[doc_ids[i]] = cur
    return ranks


class Ensemble:
    """Indexes a set of (doc_id, text) pairs and answers queries with per-model
    ranks plus the RRF-fused ranking."""

    def __init__(self, embedders):
        self.embedders = embedders
        self.doc_ids = []

    def index(self, doc_ids, texts):
        self.doc_ids = list(doc_ids)
        for e in self.embedders:
            e.index(list(texts))

    def query(self, q):
        per_model = {}
        for e in self.embedders:
            sims = np.asarray(e.similarities(q), dtype=float)
            per_model[e.name] = {
                "scores": {d: float(s) for d, s in zip(self.doc_ids, sims)},
                "ranks": ranks_from_scores(self.doc_ids, sims),
            }

        fused = {}
        for d in self.doc_ids:
            fused[d] = sum(1.0 / (RRF_K + per_model[e.name]["ranks"][d])
                           for e in self.embedders)
        return {
            "per_model": per_model,
            "fused_scores": fused,
            "fused_ranks": ranks_from_scores(self.doc_ids,
                                             [fused[d] for d in self.doc_ids]),
        }
