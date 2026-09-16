# Findings (first run, uncontrolled)

> **Fourth run, after the slang gloss cap (2026-09-07).** The e5 diagnostic
> traced the mana-dork weakness to a compound query: the slang layer appended
> both the mana-dork gloss and the `ramp` gloss, and the ramp half is about
> lands. That layer now caps injection at one gloss per matched span. Re-running
> this cluster, effect-level improves on all six cards (7.50 -> 6.17) and the
> baseline improves more on average (9.00 -> 6.50) but almost entirely via one
> card. By cluster mean the mana-dork verdict softens **WIN -> TIE**; per card
> effect-level goes from 2 wins to 4 wins with a median gain of 2 places. See
> `mana_dork_recheck.md`. Board wipe and clone are unaffected -- their queries
> did not change.
>
> **The cap is NOT ported.** It lives in `development/semantic-search/mtg-search-v0`,
> which is not the current project. It is not live in the real system until
> someone copies it across.
>
> **Third run, 30 cards.** The sample was widened from 17 to 30 (six targets per
> cluster instead of 3/3/1). All three verdicts held: effect-level wins mana dork
> and board wipe, ties clone. Two qualifications the wider sample exposed. The
> mana-dork win is carried almost entirely by one card and only two of the three
> embedders support it, so treat it as weak. The clone tie became *more*
> trustworthy, since at 17 cards it was a ceiling artifact with both pipelines
> pinned at rank 1. See `grid.md`.
>
> **Superseded in part by `grid.md`.** This document reports the first run, in
> which neither confound was controlled. A second, controlled run translates the
> queries out of MTG jargon and strips the card's own name from the baseline,
> and the headline below **reverses**: effect-level then wins the mana-dork and
> board-wipe clusters and ties clone. Sections 1 and 3 to 6 stand as written.
> Section 2 is the confound, now measured directly rather than inferred.
> Read `grid.md` for the current verdict.
>
> Every rank quoted in the body below is from the original 17-card corpus and no
> longer matches the regenerated `results.md`, which now runs at 30. The
> mechanisms the sections describe are unchanged; only the numbers are historic.

Read alongside `results.md` (full rank tables) and `ablation-cardname.md`.

## Headline

Under the raw jargon queries and a baseline that keeps its card names,
effect-level search did **not** produce a net retrieval improvement on this
sample. It fixed the density failure in the specific places where that failure
is mechanically identifiable, and it lost more ground elsewhere for a reason
that has nothing to do with density: it discards the card name.

Both halves of that sentence turned out to be confounds rather than properties
of effect-level search, which is what the controlled run then established.

Mean rank of the cards each query should find (lower is better):

| Query | Effect-level | Baseline |
|---|---|---|
| a mana dork | 4.0 | 4.7 |
| a board wipe | 9.3 | 3.3 |
| a clone effect | 1.0 | 1.0 |
| a creature that taps for mana | 3.7 | 3.3 |
| destroy all creatures | 1.7 | 2.0 |
| copy a creature | 1.0 | 1.0 |

## 1. The density failure is real, and effect-level search does fix it

Three independent pieces of evidence, all from the tables rather than from the
fused number moving:

**Identical text, different ranks.** Llanowar Elves and Elvish Mystic have
byte-identical oracle text. The whole-card baseline ranks them **9th and 4th**
for "a mana dork" and **6th and 3rd** for "a creature that taps for mana". A
five-place and a three-place split between two cards that do exactly the same
thing, produced entirely by the name, type line and cost wrapped around the
text. The effect-level pipeline ties them at 5 in both cases, which is the
only defensible answer.

**The reported burial reproduces, partly.** Llanowar Elves, whose entire text
is `{T}: Add {G}`, ranks **9th of 17** for "a mana dork" in the baseline,
below Ponder (8th), Giant Growth (7th) and Divination (6th), none of which
make mana. Effect-level lifts it to 5th. Note the caveat: Elvish Mystic, same
text, was already 4th, so on this 17-card sample the burial is name-dependent
rather than a uniform property of terse cards.

**Type-line bleed disappears.** For "copy a creature" the baseline ranks
Elvish Mystic **2nd** and Llanowar Elves **3rd**, behind only Clone, because
`Creature - Elf Druid` in the type line lexically matches "creature". This is
the density failure exactly: irrelevant repeated terms from concatenated
metadata outrank meaning. Effect-level drops both to 9th.

## 2. Effect-level search loses on jargon queries, and the cause is the card name

"a board wipe" is the worst result in the run: the three wipes land at 8th,
8th and 12th under effect-level against 5th, 2nd and 3rd in the baseline.

The ablation isolates why. Stripping the card name from the baseline document:

| | Wrath of God | Damnation | Day of Judgment |
|---|---|---|---|
| full document | 5 | 2 | 3 |
| name removed | 9 | 7 | 3 |

and for "a clone effect", Clone falls from **1st to 4th** when its name is
removed. The baseline's apparent win on the clone query is largely the literal
string "Clone" in the card name matching "clone" in the query. It is not
evidence that whole-card embedding understands the effect.

The effect-level pipeline throws the card name away by construction, since
effects are deduplicated across cards and so cannot carry a name. Against
jargon queries, where the models have no semantic handle at all, that name
string was carrying most of the baseline's signal. This is a structural cost of
effect-level search, separate from and larger than the density benefit it buys.

## 3. Whether the query is in-vocabulary dominates everything else

The per-embedder columns make this unmissable, and it is the single strongest
effect in the run.

On **paraphrase** queries the three models agree tightly. For "destroy all
creatures" every model independently puts the three wipes at the top under both
pipelines. On **jargon** queries they collapse into mutual noise. For "a board
wipe" under effect-level, bge ranks Nykthos 1st and the two Elves 2nd, while e5
ranks Lightning Bolt 1st. Neither model knows the term, so the fused ranking is
an average of two unrelated noise signals.

Moving the same intent from jargon to plain English is worth far more than
changing the document unit: the wipes go from 8/8/12 to 2/2/1 under
effect-level purely by rephrasing the query. No document-unit change in this
experiment produced a swing of that size.

## 4. TF-IDF contributes nothing on two of the three primary queries

For "a board wipe" and "a clone effect" the query shares no vocabulary with any
authored effect, so TF-IDF scores every document zero. Because ties share a
rank, all-tied TF-IDF gives every document rank 1 and its identical
1/(60+1) contribution cancels out of the fusion. Those runs are effectively
two-model, not three.

This surfaced as a genuine bug first. Before stop words were removed, the only
matching token in "a board wipe" was the article "a", and TF-IDF returned an
identical, confident-looking bogus ranking for both "a board wipe" and "a clone
effect", with Giant Growth on top for a board-wipe query. Two fixes were
needed: English stop words in the vectorizer, and standard competition ranking
so that tied documents share a rank instead of being ordered arbitrarily.
Without the second fix a zero-signal embedder hands RRF a full ordering built
out of nothing. Only the per-embedder breakdown made either visible.

## 5. MAX aggregation gives multi-effect cards extra lottery tickets

A card is exactly as findable as its single best-matching effect, so a card
with more effects gets more chances to match anything.

Nykthos, Shrine to Nyx reaches **2nd for "a clone effect"** on the strength of
its long devotion ability, and Doubling Season reaches 2nd on the same query
via its *counters*-doubling effect rather than its token effect. Both are cards
with two indexed effects; every single-effect card gets one draw.

This is the seam `aggregate.py` exists for. A SUM variant would spread a card's
score across all its effects instead of letting the best one carry it, which
would change these two results specifically. It is deliberately not implemented.

## 6. The no-fallback rule costs real coverage, and buys some precision

Ponder and Divination are absent from every effect-level result, because their
only effects are unauthored. The cost is total: no query can reach them.

There is a visible upside in the same tables. The baseline ranks Divination
**4th** and Ponder **7th** for "a board wipe", putting a card-draw spell above
Wrath of God at 5th. The effect-level pipeline never emits that false positive,
though only because it cannot emit those cards at all. This is coverage traded
for precision, not precision earned.

## Caveats

- 17 cards. Rank differences of one or two places are not meaningful at this
  size.
- The three clusters share one corpus, so each cluster's controls are the other
  clusters' distractors. Intended, but it means "rank 9 of 17" is not
  comparable to a rank in a real corpus of thousands.
- Effect-level documents are hand-authored plain English while baseline
  documents are raw oracle text. Wording and document unit are therefore
  confounded: some of the effect-level behaviour is the rewording, not the
  splitting. Separating them would need a third arm with unreworded effect
  chunks.
- `plain_text` never contains the query strings, by authoring discipline. A
  less careful authoring pass would have made effect-level look much better and
  meant nothing.

## What this suggests next

1. Re-run on a corpus large enough for burial to be common, since the density
   failure is what motivated this and it only half-reproduced at 17 cards.
2. Attach the card name, type line or both to the effect document, or restore
   them at aggregation time. The name ablation says this is where the largest
   recoverable loss is.
3. Add the unreworded-effect-chunks arm to separate rewording from splitting.
4. Handle jargon at the query end, not the document end. Every result here is
   dominated by whether the query is in-vocabulary, and none of the three
   embedders knows MTG slang.
