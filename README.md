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

Full-corpus zone labelling runs separately with `./run_zone_corpus.sh`.
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
