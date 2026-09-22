"""Prove the page's matrix ranking is the brute-force ranking.

build_similarity_page.py ranks 42k x 42k with chunked sparse matmuls; the
validation report ranks by an O(n) Python loop. They are supposed to be the
same function. This re-derives a random sample of effects the slow way and
compares, so "exact, no candidate pruning" is a checked claim rather than a
comment in a docstring.

A neighbour is allowed to differ from brute force ONLY where it ties the
brute-force neighbour's score to within float32 precision -- a tie the pool
boundary in _topk may order either way. Anything else is a real disagreement
and fails the run.

    python check_page_agreement.py [sample_size]
"""
import random
import sys

import build_similarity_page as B
import similarity as S

TOL = 2e-6


def main(sample=120, seed=7):
    corpus = S.load_corpus()
    binary, weighted, vocab, idf = B.matrices(corpus)
    raw_nb, wtd_nb = B.rank_all(binary, weighted)

    rng = random.Random(seed)
    picks = rng.sample(range(corpus.n), min(sample, corpus.n))
    # The validation probes are checked every run, not just when the sampler
    # happens to land on them.
    import validate_similarity as V
    picks += [V.resolve(corpus, text) for _, text in V.PROBES]

    checked = exact = tied = 0
    bad = []
    for i in picks:
        for mode, table in (("raw", raw_nb), ("weighted", wtd_nb)):
            truth = corpus.top(i, mode, B.TOP_N)
            got = list(table[i])
            for rank, j in enumerate(got):
                checked += 1
                want_score, want_j = truth[rank] if rank < len(truth) else (0.0, None)
                if j == want_j:
                    exact += 1
                elif abs(corpus.score(mode, i, int(j)) - want_score) <= TOL:
                    tied += 1
                else:
                    bad.append((i, mode, rank, int(j), want_j,
                                corpus.score(mode, i, int(j)), want_score))

    print("%d effects x 2 modes x top-%d = %d neighbours checked against brute force"
          % (len(picks), B.TOP_N, checked))
    print("  identical:      %d (%.2f%%)" % (exact, 100.0 * exact / checked))
    print("  score-tied swap: %d" % tied)
    print("  disagreements:   %d" % len(bad))
    for row in bad[:10]:
        print("    effect %d %s rank %d: got %s (%.6f), brute force %s (%.6f)" % row)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 120))
