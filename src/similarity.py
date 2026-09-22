"""Word-overlap similarity over the deduped effect glossary.

Two modes, both fully deterministic -- no model, no embedding, no curated
MTG-term list:

  raw       plain Jaccard over the token SETS: |A & B| / |A | B|.
  weighted  cosine between the effects' IDF-weighted token vectors.

The point of the pair is the contrast. Raw overlap treats "target" and
"creature" exactly like "surveil": every shared token counts 1. Weighted
overlap gets its vocabulary from the corpus itself -- idf = log(N / df) is
near zero for a token that shows up in a third of all effects and large for
one that shows up in forty, so the distinctive MTG terms float to the top
without anybody writing them down.

Vectors are SET-based (binary presence x idf), not tf-idf: an effect that says
"creature" three times is not three times more about creatures, and Jaccard is
set-based too, so the two modes stay comparable.
"""
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
FULL = os.path.join(HERE, os.pardir, "data", "full")
EFFECTS_PATH = os.path.join(FULL, "effects.json")
CARDS_PATH = os.path.join(FULL, "cards.jsonl")

# Ordinary English filler ONLY. Deliberately no MTG vocabulary: "target",
# "creature", "player", "card" and friends are exactly what the IDF weights
# are supposed to discount on their own, so stopwording them by hand would
# hide the result we are trying to measure.
STOPWORDS = frozenset("""
a an the this that these those there here
and or but if then than as so
of to in into on onto from with at for by up down out off over under
is are was were be been being am
it its they them their he she his her him
do does did done
have has had
will would shall should may might must can could
each other another same
""".split())

# Reminder text restates a keyword's rules in words the effect itself never
# chose. Two unrelated cards that both have deathtouch would otherwise share a
# dozen tokens of boilerplate, so the parenthetical comes out before tokenizing.
_REMINDER = re.compile(r"\([^()]*\)")

# Kept whole, in this order: mana/tab symbols ({T}, {2}, {G/W}), stat and
# counter deltas (+1/+1, -1/-1, 3/3), words (with internal apostrophes and
# hyphens), bare numbers.
_TOKEN = re.compile(r"\{[^}]{1,12}\}|[+-]?\d+/[+-]?\d+|[a-z]+(?:['\u2019-][a-z]+)*|\d+")


def tokenize(text, drop_reminders=True):
    """Return the ordered token list for one effect's raw_text."""
    t = text.lower()
    if drop_reminders:
        t = _REMINDER.sub(" ", t)
    t = t.replace("\u2014", " ").replace("\u2019", "'")
    return [w for w in _TOKEN.findall(t) if w not in STOPWORDS]


def token_set(text, **kw):
    return frozenset(tokenize(text, **kw))


class Corpus(object):
    """Token sets + IDF weights for one list of glossary effects.

    `effects` is the list straight out of data/full/effects.json -- reused
    as-is, nothing re-extracted.
    """

    def __init__(self, effects, drop_reminders=True, names=None, mask_own_name=True):
        self.effects = effects
        self.n = len(effects)
        raw_sets = [token_set(e["raw_text"], drop_reminders=drop_reminders) for e in effects]

        # Card-name masking, ON by default: a card's own name is not content,
        # it is identity, and IDF cannot tell the difference -- "Blasphemous
        # Act" is the rarest thing in the corpus precisely because no other
        # card is named that, which makes `blasphemous`/`act` look maximally
        # DISTINCTIVE when they are actually maximally UNINFORMATIVE about
        # what the effect does.
        #
        # Restricted to effects with exactly one card_id (singletons). A word
        # is masked only when it is that ONE card's own name -- never because
        # some other card sharing the same effect happens to be named that.
        # Widening this to "any card that uses this effect" is a real trap:
        # Un-set joke cards are deliberately named after game terms (Spell
        # Counter, Creature Guy, Destroy the Evidence, Kill! Destroy!, Exile),
        # and a shared effect like "Counter target spell." has ~50 cards
        # behind it -- one joke card in that list would strip `counter` from
        # every real counterspell. Singleton-only sidesteps that: a word this
        # common is never used by only one card, so it is never a masking
        # candidate in the first place. See reports/similarity-validation.md
        # for the measurement that justified this restriction.
        self.own_name_tokens = [frozenset()] * self.n
        if mask_own_name and names:
            for i, e in enumerate(effects):
                if len(e["card_ids"]) != 1:
                    continue
                nt = token_set(names.get(e["card_ids"][0], ""), drop_reminders=False)
                hit = raw_sets[i] & nt
                if hit:
                    self.own_name_tokens[i] = hit
                    raw_sets[i] = raw_sets[i] - hit

        self.sets = raw_sets
        self.df = {}
        for s in self.sets:
            for w in s:
                self.df[w] = self.df.get(w, 0) + 1
        # idf = log(total_effects / effects_containing_token). A token in every
        # single effect lands on exactly 0.0 and stops counting, which is the
        # correct answer for it.
        self.idf = {w: math.log(self.n / d) for w, d in self.df.items()}
        self.norm = [self._norm(s) for s in self.sets]
        self.by_id = {e["effect_id"]: i for i, e in enumerate(effects)}

    def _norm(self, s):
        return math.sqrt(sum(self.idf[w] ** 2 for w in s))

    # -- the two similarity functions -------------------------------------

    def raw(self, i, j):
        """Plain Jaccard: shared tokens / union of tokens, unweighted."""
        a, b = self.sets[i], self.sets[j]
        if not a and not b:
            return 0.0
        return len(a & b) / len(a | b)

    def weighted(self, i, j):
        """Cosine between the two IDF-weighted token vectors."""
        na, nb = self.norm[i], self.norm[j]
        if na == 0.0 or nb == 0.0:
            return 0.0
        shared = self.sets[i] & self.sets[j]
        return sum(self.idf[w] ** 2 for w in shared) / (na * nb)

    def score(self, mode, i, j):
        return self.raw(i, j) if mode == "raw" else self.weighted(i, j)

    # -- explanation -------------------------------------------------------

    def shared(self, i, j):
        """Shared tokens, heaviest IDF first -- the WHY behind a score."""
        return sorted(self.sets[i] & self.sets[j], key=lambda w: (-self.idf[w], w))

    def contribution(self, i, j):
        """Per-token share of the weighted cosine, as fractions summing to 1."""
        shared = self.sets[i] & self.sets[j]
        total = sum(self.idf[w] ** 2 for w in shared)
        if total == 0.0:
            return {w: 0.0 for w in shared}
        return {w: self.idf[w] ** 2 / total for w in shared}

    # -- ranking -----------------------------------------------------------

    def top(self, i, mode, k=10, min_score=0.0):
        """Exact brute-force top-k against the WHOLE corpus, no pruning.

        O(n) per query with no candidate cutoff, so nothing can be missed --
        this is what the validation report uses, and what makes its numbers
        answerable. The page builder has its own pruned index for the
        all-effects precompute; this one is the ground truth it is checked
        against.
        """
        score = self.raw if mode == "raw" else self.weighted
        out = []
        for j in range(self.n):
            if j == i:
                continue
            s = score(i, j)
            if s > min_score:
                out.append((s, j))
        # Ties break on corpus position, which is fixed by the glossary file --
        # the same rule the page builder's matrix path uses, so the two are
        # comparable neighbour-for-neighbour.
        out.sort(key=lambda p: (-p[0], p[1]))
        return out[:k]

    # -- lookup helpers ----------------------------------------------------

    def find(self, needle, limit=None):
        """Indices of effects whose raw_text contains `needle` (case-folded)."""
        n = needle.lower()
        hits = [i for i, e in enumerate(self.effects) if n in e["raw_text"].lower()]
        return hits[:limit] if limit else hits

    def exact(self, text):
        """Index of the effect whose raw_text is exactly `text`, else None."""
        for i, e in enumerate(self.effects):
            if e["raw_text"] == text:
                return i
        return None


def load_effects(path=EFFECTS_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["effects"]


def load_card_names(path=CARDS_PATH):
    with open(path, encoding="utf-8") as fh:
        return {c["card_id"]: c["name"] for c in map(json.loads, fh)}


def load_corpus(mask_own_name=True, **kw):
    """Load effects (+ card names, needed for the default name mask) and
    build a Corpus. Pass mask_own_name=False to see the unmasked baseline."""
    names = load_card_names() if mask_own_name else None
    return Corpus(load_effects(), names=names, mask_own_name=mask_own_name, **kw)
