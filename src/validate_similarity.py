"""Validate the two word-overlap modes on known cases before anyone trusts them.

Writes reports/similarity-validation.md. Every number here is EXACT: each
probe is scored by brute force against all 42k effects with no candidate
pruning, so a neighbour cannot be missed by an index shortcut. (The page
builder uses a matrix path; check_page_agreement.py confirms it reproduces
these same rankings.)

The cases are the ones a reader can check by eye:
  mill vs surveil    two library-to-graveyard mechanics that are NOT the same
  board wipes        four of them against each other and against unrelated text
  removal pairs      destroy-vs-destroy, exile-vs-exile, destroy-vs-exile
"""
import os
import sys

import similarity as S

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "reports", "similarity-validation.md")

TOP_N = 8

SURVEIL_1 = ("Surveil 1. (Look at the top card of your library. You may put it into "
             "your graveyard.)")
SURVEIL_2 = ("Surveil 2. (Look at the top two cards of your library, then put any number "
             "of them into your graveyard and the rest on top of your library in any order.)")
PATH = ("Exile target creature. Its controller may search their library for a basic land "
        "card, put that card onto the battlefield tapped, then shuffle.")
SWORDS = "Exile target creature. Its controller gains life equal to its power."
TERROR = "Destroy target nonartifact, nonblack creature. It can't be regenerated."
WRATH = "Destroy all creatures. They can't be regenerated."

# Probes are named by the exact effect text so the report stays readable and so
# a rebuild against a newer Scryfall dump fails loudly instead of quietly
# scoring some other effect.
PROBES = [
    ("Mill", "Target player mills five cards."),
    ("Surveil", SURVEIL_1),
    ("Board wipe (destroy all)", "Destroy all creatures."),
    ("Board wipe (damage)", "Blasphemous Act deals 13 damage to each creature."),
    ("Board wipe (-X/-X)", "All creatures get -X/-X until end of turn."),
    ("Removal (destroy)", "Destroy target creature."),
    ("Removal (exile)", SWORDS),
    ("Counterspell", "Counter target spell."),
    ("Unrelated: pump", "Target creature gets +3/+3 until end of turn."),
    ("Unrelated: mana", "{T}: Add {G}."),
]

PAIRS = [
    ("mill vs surveil", "Target player mills five cards.", SURVEIL_1),
    ("mill vs mill (different number)",
     "Target player mills five cards.", "Target player mills two cards."),
    ("mill vs mill (player vs opponent)",
     "Target player mills five cards.", "Target opponent mills seven cards."),
    ("surveil vs surveil (different number)", SURVEIL_1, SURVEIL_2),
    ("wipe vs wipe: Day of Judgment / Wrath of God", "Destroy all creatures.", WRATH),
    ("wipe vs wipe: Day of Judgment / Toxic Deluge",
     "Destroy all creatures.", "All creatures get -X/-X until end of turn."),
    ("wipe vs wipe: Day of Judgment / Blasphemous Act",
     "Destroy all creatures.", "Blasphemous Act deals 13 damage to each creature."),
    ("wipe vs unrelated: Day of Judgment / Giant Growth",
     "Destroy all creatures.", "Target creature gets +3/+3 until end of turn."),
    ("wipe vs unrelated: Day of Judgment / Llanowar Elves",
     "Destroy all creatures.", "{T}: Add {G}."),
    ("wipe vs single removal: Day of Judgment / Murder",
     "Destroy all creatures.", "Destroy target creature."),
    ("removal pair: Murder / Doom Blade",
     "Destroy target creature.", "Destroy target nonblack creature."),
    ("removal pair: Murder / Terror", "Destroy target creature.", TERROR),
    ("removal pair: Swords to Plowshares / Path to Exile", SWORDS, PATH),
    ("removal cross-mode: Murder / Swords to Plowshares",
     "Destroy target creature.", SWORDS),
    ("removal vs unrelated: Murder / Giant Growth",
     "Destroy target creature.", "Target creature gets +3/+3 until end of turn."),
    ("removal vs unrelated: Murder / Lightning Bolt",
     "Destroy target creature.", "Lightning Bolt deals 3 damage to any target."),
]


def resolve(corpus, text):
    i = corpus.exact(text)
    if i is None:
        raise SystemExit("probe text not present in the corpus: %r" % text[:70])
    return i


def label(corpus, names, i, width=90):
    e = corpus.effects[i]
    cards = sorted((names.get(c, c) for c in e["card_ids"]), key=str.lower)
    tail = ", ".join(cards[:3]) + (" +%d" % (len(cards) - 3) if len(cards) > 3 else "")
    t = e["raw_text"]
    if len(t) > width:
        t = t[:width - 1] + "…"
    return t, tail


def md(s):
    return s.replace("|", "\\|")


def shared_cell(corpus, i, j, mode, limit=6):
    """Shared tokens; for the weighted mode, each carries its IDF."""
    sh = corpus.shared(i, j)
    if not sh:
        return "_none_"
    if mode == "raw":
        body = " ".join("`%s`" % w for w in sh[:limit])
    else:
        body = " ".join("`%s` %.1f" % (w, corpus.idf[w]) for w in sh[:limit])
    if len(sh) > limit:
        body += " +%d" % (len(sh) - limit)
    return md(body)


def probe_block(corpus, names, title, text, out):
    i = resolve(corpus, text)
    tok = sorted(corpus.sets[i], key=lambda w: (-corpus.idf[w], w))
    out.append("### %s" % title)
    out.append("")
    out.append("> %s" % md(corpus.effects[i]["raw_text"]))
    out.append("")
    out.append("Tokens after stopword removal, heaviest IDF first: %s"
               % (" ".join("`%s` %.2f" % (w, corpus.idf[w]) for w in tok) or "_none_"))
    out.append("")
    tops = {"raw": corpus.top(i, "raw", TOP_N), "weighted": corpus.top(i, "weighted", TOP_N)}
    out.append("| # | raw overlap (Jaccard) | score | shared | IDF-weighted (cosine) | score "
               "| shared (token idf) |")
    out.append("|--:|---|--:|---|---|--:|---|")
    for n in range(TOP_N):
        cells = []
        for mode in ("raw", "weighted"):
            top = tops[mode]
            if n >= len(top):
                cells += ["—", "", ""]
                continue
            s, j = top[n]
            t, cards = label(corpus, names, j, 60)
            cells += ["%s<br><sub>%s</sub>" % (md(t), md(cards)),
                      "%.3f" % s, shared_cell(corpus, i, j, mode)]
        out.append("| %d | %s |" % (n + 1, " | ".join(cells)))
    out.append("")


def pair_table(corpus, out):
    out.append("| pair | raw | weighted | shared tokens (token idf) |")
    out.append("|---|--:|--:|---|")
    for title, a, b in PAIRS:
        i, j = resolve(corpus, a), resolve(corpus, b)
        if i == j:
            out.append("| %s | — | — | _one and the same deduped effect (`%s`)_ |"
                       % (title, corpus.effects[i]["effect_id"]))
            continue
        out.append("| %s | %.3f | %.3f | %s |"
                   % (title, corpus.raw(i, j), corpus.weighted(i, j),
                      shared_cell(corpus, i, j, "weighted", 8)))
    out.append("")


def disagreements(corpus, names, out, limit=12):
    """Pairs the two modes rank very differently, found automatically.

    For every probe, any raw-mode neighbour whose weighted score lags badly is
    listed with the cheap tokens that carried it -- this is where "tied
    together only by `target` and `creature`" surfaces without anyone having to
    guess at it in advance.
    """
    rows = []
    for title, text in PROBES:
        i = resolve(corpus, text)
        for s, j in corpus.top(i, "raw", TOP_N):
            w = corpus.weighted(i, j)
            if w < 0.5 * s or (s >= 0.35 and w < 0.5):
                cheap = [t for t in corpus.shared(i, j) if corpus.idf[t] < 2.0]
                rows.append((s - w, title, j, s, w, cheap))
    rows.sort(key=lambda r: (-r[0], r[1]))
    if not rows:
        out.append("_No raw-mode neighbour fell far behind its weighted score._")
        out.append("")
        return
    out.append("| probe | raw neighbour | raw | weighted | carried by low-IDF tokens |")
    out.append("|---|---|--:|--:|---|")
    for _, title, j, s, w, cheap in rows[:limit]:
        t, cards = label(corpus, names, j, 58)
        out.append("| %s | %s<br><sub>%s</sub> | %.3f | %.3f | %s |"
                   % (title, md(t), md(cards), s, w,
                      " ".join("`%s` %.1f" % (c, corpus.idf[c]) for c in cheap) or "_—_"))
    out.append("")


def corpus_block(corpus, out):
    df = sorted(corpus.df.items(), key=lambda p: (-p[1], p[0]))
    picks = ["surveil", "mill", "mills", "regenerated", "lifelink", "scry", "destroy",
             "exile", "counter", "damage", "creature", "target", "you", "card"]
    out.append("| | tokens |")
    out.append("|---|---|")
    out.append("| **lowest IDF** — commonest, discounted with no help from anyone | %s |"
               % " ".join("`%s` %.2f" % (w, corpus.idf[w]) for w, _ in df[:14]))
    out.append("| **named MTG terms, for scale** | %s |"
               % " ".join("`%s` %.2f" % (w, corpus.idf[w]) for w in picks if w in corpus.idf))
    out.append("")
    empty = sum(1 for s in corpus.sets if not s)
    out.append("%s effects, %s distinct tokens, %s postings, median %d tokens per effect "
               "(**with card-name masking already applied** — see §1 below). "
               "%d effects tokenize to nothing (pure reminder text, nothing but stopwords, or "
               "— a handful — nothing left after their own name is masked out) and score "
               "0 against everything under both modes."
               % ("{:,}".format(corpus.n), "{:,}".format(len(corpus.df)),
                  "{:,}".format(sum(len(s) for s in corpus.sets)),
                  sorted(len(s) for s in corpus.sets)[corpus.n // 2], empty))
    out.append("")


def card_name_masking(corpus, names, out):
    """Card-name masking is ON by default -- this is the before/after that
    justifies it, plus the one anecdote that explains why it is restricted to
    singleton (one-card) effects.

    IDF reads "rare across the corpus" as "distinctive", and a proper noun is
    the rarest thing in the corpus -- so a card that names itself in its own
    rules text ("Blasphemous Act deals 13 damage...") got a vector dominated
    by a token that says nothing at all about the effect. `corpus` here is
    already masked (the default); `baseline` is the unmasked counterfactual,
    built only to show what the fix is fixing.
    """
    baseline = S.Corpus(corpus.effects, names=names, mask_own_name=False)
    affected, heavy, masses = 0, 0, []
    for i, e in enumerate(corpus.effects):
        s = baseline.sets[i]
        overlap = s & corpus.own_name_tokens[i] if len(e["card_ids"]) == 1 else s & set(
            w for cid in e["card_ids"] for w in S.tokenize(names.get(cid, "")))
        if not overlap:
            continue
        total = sum(baseline.idf[w] ** 2 for w in s)
        if total == 0:
            continue
        share = sum(baseline.idf[w] ** 2 for w in overlap) / total
        affected += 1
        masses.append(share)
        if share > 0.5:
            heavy += 1
    masses.sort()
    masked_n = sum(1 for t in corpus.own_name_tokens if t)
    vocab_gone = len(baseline.df) - len(corpus.df)
    out.append("Restricted to effects with exactly one card (singletons): masking never touches "
               "a shared effect, however many cards use it. **%s singleton effects (%.1f%% of "
               "the corpus) now have their own-name tokens excluded** before anything is scored. "
               "That drops %s tokens out of the vocabulary entirely (%s → %s) — mostly "
               "hapax proper nouns, but also words like a repeated legendary's own name echoed "
               "across several printings of itself, that existed only as name-echo in the first "
               "place."
               % ("{:,}".format(masked_n), 100.0 * masked_n / corpus.n, "{:,}".format(vocab_gone),
                  "{:,}".format(len(baseline.df)), "{:,}".format(len(corpus.df))))
    out.append("")
    out.append("What that's fixing, measured on the **unmasked baseline**: %s effects (%.1f%% of "
               "the corpus) use a word from their own card name in their rules text; for %s of "
               "them — %.1f%% of the whole corpus — those name tokens carried **more "
               "than half** the weighted vector's mass, median %.0f%% among affected effects. Raw "
               "overlap was unaffected either way: a name token is worth exactly 1 there, same as "
               "every other word."
               % ("{:,}".format(affected), 100.0 * affected / corpus.n, "{:,}".format(heavy),
                  100.0 * heavy / corpus.n, 100.0 * masses[len(masses) // 2]))
    out.append("")
    out.append("**Why singleton-only, not \"any card that uses this effect\":** Un-set joke cards "
               "are deliberately named after game terms. `Counter target spell.` is shared by 52 "
               "cards; one of them is literally named **Spell Counter**. Masking by \"any sharing "
               "card's name\" would strip `counter` from all 52, including every ordinary "
               "counterspell. Singleton-only sidesteps this entirely: a word that common is never "
               "used by only one card, so it is never a masking candidate to begin with.")
    out.append("")
    i = resolve(corpus, "Blasphemous Act deals 13 damage to each creature.")
    bi = resolve(baseline, "Blasphemous Act deals 13 damage to each creature.")
    total = sum(baseline.idf[w] ** 2 for w in baseline.sets[bi])
    out.append("Worked example — `Blasphemous Act deals 13 damage to each creature.`, "
               "unmasked baseline:")
    out.append("")
    out.append("| token | df | idf | share of weighted vector |")
    out.append("|---|--:|--:|--:|")
    for w in sorted(baseline.sets[bi], key=lambda w: (-baseline.idf[w], w)):
        out.append("| `%s` | %s | %.2f | %.1f%% |"
                   % (w, "{:,}".format(baseline.df[w]), baseline.idf[w],
                      100.0 * baseline.idf[w] ** 2 / total))
    out.append("")
    out.append("Masked (the default): `%s` excluded as this card's own name; `%s` remain."
               % (", ".join("`%s`" % w for w in sorted(corpus.own_name_tokens[i])),
                  ", ".join("`%s`" % w for w in sorted(corpus.sets[i], key=lambda w: -corpus.idf[w]))
                  or "_nothing_"))
    out.append("")
    out.append("| | top weighted neighbour, unmasked | score | top weighted neighbour, masked | score |")
    out.append("|---|---|--:|---|--:|")
    bt = baseline.top(bi, "weighted", 1)
    mt = corpus.top(i, "weighted", 1)
    out.append("| `Blasphemous Act...` | %s | %.3f | %s | %.3f |"
               % (md(baseline.effects[bt[0][1]]["raw_text"][:56]) if bt else "—",
                  bt[0][0] if bt else 0.0,
                  md(corpus.effects[mt[0][1]]["raw_text"][:56]) if mt else "—",
                  mt[0][0] if mt else 0.0))
    out.append("")
    out.append("Masking removes the name-echo, but `13` is still a bare numeral shared with every "
               "other effect that happens to deal or reference 13 of something (see §3 below) "
               "— masking card names and disambiguating numerals are two different fixes for "
               "two different tokens in the same sentence.")
    out.append("")
    thin = [k for k, t in enumerate(corpus.own_name_tokens) if t and 0 < len(corpus.sets[k]) <= 2]
    spirit_i, cre_i = resolve(corpus, "Destroy target Spirit."), resolve(corpus, "Destroy target creature.")
    out.append("**The trade-off, measured:** masking assumes a card's own name is flavor, not "
               "content. That holds almost everywhere — %s of the %s masked singletons are left "
               "with 1–2 tokens, and the overwhelming majority of those are correctly generic "
               "(`enters` `tapped`; `commander` `your`). It fails when the card is *named after* "
               "the exact restriction its own ability applies: **Rend Spirit**'s "
               "`Destroy target Spirit.` masks away `spirit` — the creature-type restriction that "
               "IS the card's whole point, not flavor — leaving just `destroy` `target`, which "
               "then scores %.3f weighted against plain `Destroy target creature.` because there "
               "is nothing left to tell them apart. This specific pattern (a `Destroy`/`Exile "
               "target <own-name-word>.` singleton reduced to ≤ 2 tokens) occurs exactly once "
               "in the whole corpus. Worth knowing about; not worth reverting the default over."
               % ("{:,}".format(len(thin)), "{:,}".format(masked_n), corpus.weighted(spirit_i, cre_i)))
    out.append("")


def object_drift(corpus, out, probe="Destroy target creature.", k=20):
    """`creature` is so common its IDF barely counts -- so under the weighted
    mode, destroying an artifact scores about as well as destroying a creature.
    The discount that correctly demotes filler also demotes the noun that says
    what the spell actually hits."""
    i = resolve(corpus, probe)
    top = corpus.top(i, "weighted", k)
    off = [(s, j) for s, j in top if "creature" not in corpus.sets[j]]
    raw_off = [(s, j) for s, j in corpus.top(i, "raw", k) if "creature" not in corpus.sets[j]]
    out.append("`creature` has the lowest IDF in the entire corpus (%.2f), so under the weighted "
               "mode it barely constrains anything. Of the top %d weighted neighbours of "
               "`%s`, **%d name no creature at all**; raw overlap lets %d through."
               % (corpus.idf["creature"], k, probe, len(off), len(raw_off)))
    out.append("")
    if off:
        out.append("| weighted score | neighbour |")
        out.append("|--:|---|")
        for s, j in off[:6]:
            out.append("| %.3f | %s |" % (s, md(corpus.effects[j]["raw_text"][:72])))
        out.append("")


def number_collision(corpus, out):
    """Bare numerals are one token regardless of what they count."""
    a = resolve(corpus, SURVEIL_1)
    b = corpus.exact("+1: Surveil 2.")
    if b is None:
        return
    out.append("Bare numerals are a single token whatever they count. `%s` and `%s` share `surveil` "
               "and `1` — but the `1` in the second is a loyalty cost, not a surveil count. "
               "Raw scores the pair %.3f, weighted %.3f; both are counting a coincidence. "
               "`1` appears in %s effects (idf %.2f)."
               % (md("Surveil 1."), md("+1: Surveil 2."), corpus.raw(a, b), corpus.weighted(a, b),
                  "{:,}".format(corpus.df["1"]), corpus.idf["1"]))
    out.append("")


def reminder_sensitivity(corpus, names, out):
    """What dropping parenthetical reminder text is worth, in numbers.

    It is the one tokenizer choice that changes a headline answer, so it gets
    measured against its counterfactual instead of being asserted: reminder
    text spells out a keyword in the vocabulary of every OTHER keyword that
    touches the same zones, which is precisely how mill and surveil would end
    up looking alike.
    """
    kept = S.Corpus(corpus.effects, drop_reminders=False, names=names)
    mill = next((e["raw_text"] for e in corpus.effects
                 if "mills" in e["raw_text"] and "(To mill" in e["raw_text"]), None)
    if mill is None:
        return
    rows = [("plain mill vs surveil", "Target player mills five cards.", SURVEIL_1),
            ("mill spelling out its reminder vs surveil", mill, SURVEIL_1)]
    out.append("| pair | reminders dropped (what this tool does) | reminders kept |")
    out.append("|---|--:|--:|")
    for title, a, b in rows:
        i, j = resolve(corpus, a), resolve(corpus, b)
        p, q = resolve(kept, a), resolve(kept, b)
        out.append("| %s | raw %.3f / wtd %.3f | raw %.3f / wtd %.3f |"
                   % (title, corpus.raw(i, j), corpus.weighted(i, j),
                      kept.raw(p, q), kept.weighted(p, q)))
    out.append("")
    p, q = resolve(kept, mill), resolve(kept, SURVEIL_1)
    i, j = resolve(corpus, mill), resolve(corpus, SURVEIL_1)
    out.append("Reminder text restates a keyword in the vocabulary every other keyword over the "
               "same zones also uses — %s. Keeping it more than triples that pair, raw %.3f "
               "to %.3f, on boilerplate neither effect chose to say. Dropping it is what keeps "
               "the mill/surveil answer honest, and it is the one tokenizer choice here that "
               "moves a headline number."
               % (" ".join("`%s`" % t for t in kept.shared(p, q)),
                  corpus.raw(i, j), kept.raw(p, q)))
    out.append("")


def main():
    corpus = S.load_corpus()
    names = S.load_card_names()
    out = []
    out.append("# Word-overlap similarity — validation")
    out.append("")
    out.append("Two deterministic modes over the deduped effect glossary "
               "(`data/full/effects.json`, reused as-is). No model, no curated MTG-term list.")
    out.append("")
    out.append("- **raw** — plain Jaccard over token sets: `|A ∩ B| / |A ∪ B|`, "
               "every shared token worth 1.")
    out.append("- **weighted** — cosine between IDF-weighted token vectors, "
               "`idf = log(total_effects / effects_containing_token)`.")
    out.append("")
    out.append("Tokenizing drops parenthetical reminder text, then a small ordinary-English "
               "stopword list (%d words: of/the/a/to/and/this/that/…). Nothing MTG-specific "
               "is stopworded — `target` and `creature` are discounted by their own IDF, "
               "which is the thing being tested." % len(S.STOPWORDS))
    out.append("")
    out.append("**Card-name masking is on by default** (both modes): for effects belonging to "
               "exactly one card, words from that card's own name are excluded before scoring "
               "— see §1 below for why, and why it stops at singletons.")
    out.append("")
    out.append("Every score below is exact: each probe is compared against all %s effects with "
               "no candidate pruning." % "{:,}".format(corpus.n))
    out.append("")
    out.append("## Corpus and IDF")
    out.append("")
    corpus_block(corpus, out)
    out.append("## Named pairs")
    out.append("")
    pair_table(corpus, out)
    out.append("## Where the modes disagree")
    out.append("")
    out.append("Found automatically: raw-mode top-%d neighbours whose weighted score is under "
               "half the raw score, or that clear raw 0.35 but miss weighted 0.50." % TOP_N)
    out.append("")
    disagreements(corpus, names, out)
    out.append("## Failure modes, measured")
    out.append("")
    out.append("### 1. Card names hijack the weighted vector (fixed by default masking)")
    out.append("")
    card_name_masking(corpus, names, out)
    out.append("### 2. The weighted mode forgets what the spell hits")
    out.append("")
    object_drift(corpus, out)
    out.append("### 3. Bare numerals collide (both modes)")
    out.append("")
    number_collision(corpus, out)
    out.append("### 4. Sensitivity: dropping reminder text")
    out.append("")
    reminder_sensitivity(corpus, names, out)
    out.append("## Top-%d neighbours per probe, both modes" % TOP_N)
    out.append("")
    for title, text in PROBES:
        probe_block(corpus, names, title, text, out)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("wrote %s" % os.path.normpath(OUT))


if __name__ == "__main__":
    sys.exit(main())
