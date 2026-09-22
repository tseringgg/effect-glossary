# Effect-level search experiment

Standalone experiment. No shared code with any other codebase.

**Question under test.** Whole-card embedding has a *density* failure: a short,
correct card can lose to a longer, only-tangentially-related card, because
embedders respond to how many times a matching term is repeated in a document.
The hypothesis is that splitting each card into individual effects,
deduplicating them, rewording them in plain language, searching at the effect
level, and aggregating matches back to parent cards removes that failure --
a terse card's one effect then competes against another card's one effect
rather than a short whole card competing against a long whole card.

**Not under test here.** Category confusion (clone vs token-doubler) is a
separate mechanism -- weighted term relationships -- validated elsewhere. No
term-relationship weighting is implemented in this repo. No corpus-wide
extraction: the sample is hand-picked.

## Layout

    src/fetch_cards.py        hand-picked 17-card sample, fetched from Scryfall
    src/extract_effects.py    deterministic structural splitting
    src/glossary.py           dedup + YAML glossary read/write
    src/author_plain_text.py  the hand-authored plain_text, with its discipline
    src/classify_zones.py     deterministic zone labels (battlefield sub-tags)
    src/build_zone_viewer.py  flat HTML table of every effect and its zones
    src/ingest_bulk.py        full Scryfall oracle_cards bulk ingest -> data/full/
    src/build_full_glossary.py  extract/dedupe/zone-label the full corpus
    src/build_zone_review.py  paginated full-corpus zone review page
    src/embedders.py          TF-IDF / e5-small-v2 / bge-base-en-v1.5 + RRF
    src/aggregate.py          effect -> card aggregation (MAX; SUM seam)
    src/search.py             effect-level pipeline
    src/baseline.py           whole-card baseline
    src/report.py             the comparison report
    src/ablation_cardname.py  card-name ablation on the baseline

    data/cards.json                 fetched sample
    data/effects.pre-authoring.yaml glossary snapshot before any plain_text
    data/effects.yaml               the live, human-editable glossary
    reports/results.md              main results
    reports/ablation-cardname.md    ablation results
    reports/zone-labels.html        zone-label sanity-check viewer
    data/full/                      full-corpus cards, effects.json, stats (NOT used by search)
    reports/zone-review.html        full-corpus review page (+ zone-review.data.js)
    reports/zone-distribution-full.md  full-corpus zone distribution
    reports/similarity.html         raw vs IDF-weighted comparison page (+ .data.js)
    reports/similarity-validation.md  similarity validation on known cases

Full-corpus zone labelling runs separately with `./run_zone_corpus.sh`, and
word-overlap similarity with `./run_similarity.sh`.
Run everything with `./run_all.sh`, or each script individually from `src/`.
Set `EFFECT_GLOSSARY_STUB=1` to swap in deterministic offline embedders for
fast iteration; validation runs use the real models.

## Design decisions worth knowing

**Extraction is structural only.** Line breaks, modal lead-ins and bullets.
Nothing sentence-level or semantic: Wrath of God's "Destroy all creatures.
They can't be regenerated." stays one chunk. Keyword abilities are exploded
into their own entries, so Birds of Paradise yields `Flying` separately from
its mana ability.

**Dedup is exact-match on normalized text** (lowercased, whitespace collapsed,
mana symbols case-normalized). 22 extractions collapse to 18 unique effects.
`effect_id` is a hash of the normalized text, so it is stable across rebuilds
and hand-authored `plain_text` stays attached to the right entry.

**No fallback, by design.** Only entries with a non-empty `plain_text` are
embedded. An effect with no `plain_text` is not in the index and there is no
raw-text fallback, so a card whose every effect is unauthored is unreachable.
Ponder and Divination are in that state deliberately.

**Aggregation is MAX** and lives alone in `aggregate.py`. A SUM variant would
replace `aggregate_max` and nothing else; no caller inspects effect scores
directly.

**Authoring discipline.** The literal query strings -- "mana dork", "board
wipe", "clone effect" -- are never written into any `plain_text`. Planting the
query in the document would guarantee a win by string echo and would say
nothing about density. Distractors are authored as carefully as targets, so
effect-level search is not winning by having only the right answers indexed.

**Similarity is two word-overlap modes, nothing learned.** `similarity.py`
scores any two effects by raw Jaccard over token sets and by cosine over
IDF-weighted token vectors, with `idf = log(total_effects / effects_containing_token)`.
The stopword list is ordinary English filler only -- no MTG vocabulary is
stopworded, because the whole question is whether IDF discounts `target` and
`creature` on its own. It does: they sit at 1.26 and 0.68 while `surveil` and
`mill` sit at 5.53 and 4.95.

Both modes are exact over all 42k effects with no candidate pruning, and
`check_page_agreement.py` re-derives a sample by brute force so the page's
matrix path cannot drift from the validation report's Python one.

**Card-name masking is on by default, in both modes.** A card that names
itself in its own rules text ("Blasphemous Act deals 13 damage...") got a
weighted vector dominated by a token that is maximally distinctive (nobody
else is named that) and says nothing about the effect: unmasked, 17.9% of
effects echo their own name, and for 8.6% of the whole corpus that name
carries over half the vector's mass. Masking is restricted to effects with
exactly one card, and only that card's own name -- never any other card
sharing the same effect. That restriction is load-bearing, not cosmetic: Wizards'
Un-set joke cards are deliberately named after game terms, and one of them,
Spell Counter, is among the 52 cards sharing `Counter target spell.` Masking
by "any sharing card's name" would strip `counter` from every one of those 52,
joke card or not. Singleton-only sidesteps it -- a word that common is never
used by only one card, so it's never a masking candidate. Struck-through in
the comparison page when it applies; the measurement, the Spell Counter
anecdote, and the one known failure mode it introduces (a card *named after*
the exact restriction its own ability applies, e.g. Rend Spirit's `Destroy
target Spirit.`) are all in `reports/similarity-validation.md` §1.

Neither mode is trustworthy by itself, and `reports/similarity-validation.md`
says where each breaks. The short version: weighted wins wherever a rare
mechanic word carries the meaning, raw wins wherever the weighted mode's own
victory condition (low IDF on a common noun) discounts the very word that
says what the spell hits, e.g. `creature` in `Destroy target creature.`

**Clustering is a first pass, raw overlap only, HDBSCAN.** `cluster_effects.py`
runs `hdbscan.HDBSCAN` (metric=precomputed) over 1 - raw Jaccard distance --
unweighted, no IDF, per the scope decision for this slice. No predetermined
cluster count, explicit noise label. Library note: sklearn's own newer
`sklearn.cluster.HDBSCAN` (1.3+) was tried first and dropped -- its sparse
precomputed path corrupts on this data at corpus scale (a real bug, reproduced
and isolated on a 10k-effect slice; see the module docstring). The standalone
`hdbscan` package it's a port of does not have this problem.

678 clusters, 77.5% of the corpus noise/unclustered (not tuned down -- this is
the first honest number, not a target). No cluster holds more than 0.62% of
the corpus. Validated against the same known cases as the similarity work:
mill and surveil land in different clusters (correct), the destroy-based
board wipes cluster together (38 members) separately from the -X/-X wipes (7
members), single-target removal clusters separately from both (65 members) --
but Blasphemous Act itself lands as noise (its masked token set is too generic
and too small to form a dense neighbourhood), and the mill cluster quietly
contains three `draws` effects pulled in by the shared "target player ___
cards" template. The largest cluster mixes at least 8 unrelated costed
keywords (Kicker, Equip, Flashback, Cycling, Morph, Madness, Unearth, Sneak)
that share nothing but cost-number tokens once reminder text is stripped --
flagged automatically (`largest_cluster_diversity`) rather than found by eye.
Full writeup, all four validation groups, and five sampled clusters shown in
full (not cherry-picked) are in `reports/clustering.md`. Cluster membership is
also viewable per-effect in `reports/similarity.html`'s cluster panel.
