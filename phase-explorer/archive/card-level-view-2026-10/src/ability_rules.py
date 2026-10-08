#!/usr/bin/env python3
"""The promotion rule for ability-level placement, as a library.

Used by src/build_ability_layer.py (which places cards and writes the ability ledger) and by
nothing else. Reads only; every number comes from the clustering's own space (ability_probe.Space).

A card in "Parsed, no close group found" is placed in a leaf when ONE of its abilities matches
that leaf closely and the match survives every check below. One ability's score never depends on
the others: the checks are per ability.

  scored       the ability has tokens in the clustering's vocabulary
  >= 0.90      cosine of the ability's own vector against the best leaf centroid
  specific     >= 3 tokens and the leaf has <= 300 clustered cards
               (1 token or a leaf of >= 500 is "generic leaf"; the rest "in between")
  has text     the ability has rules text to show (keyword-generated equip/cycling and Saga
               chapters whose text is only "Chapter N" do not)
  not flagged  the condition-drop detector did not flag the card or the item
  not modal    modes are separate ability items, so a modal spell is never scored per ability
  token blind spot, three independent checks, ALL must pass:
    type       the effect is not one of EXCLUDED_TYPES. The tokens cannot see zone origin or
               destination, counter type or player scope, and these effect types are the ones
               whose meaning lives there. An item carrying a player_scope is excluded too.
    wording    every zone / player-scope / counter-type term in the ability's text appears in at
               least BLIND_SHARE of the leaf's member cards' text
    structure  the effect node's own scalar fields (counter_type, origin, destination, ...) and
               its sub-ability chain length match what the leaf's members with the same tokens
               carry (>= 2 identical-token members, >= MIN_SHARE of them agreeing)
"""
import collections
import re

import numpy as np

import ability_probe as ap

THRESHOLD = 0.90
MIN_TOKENS = 3
MAX_LEAF = 300
GENERIC_LEAF = 500
BLIND_SHARE = 0.20
MIN_SHARE = 0.15

EXCLUDED_TYPES = frozenset([
    "ChangeZone", "ChangeZoneAll", "Bounce", "Discard", "Counter", "PutCounter", "PutCounterAll",
    "RemoveCounter", "MoveCounters", "MultiplyCounter", "GivePlayerCounter"])

ZONE_TERMS = ["graveyard", "exile", "library", "battlefield", "hand"]
PLAYER_TERMS = ["opponent", "each player", "target player", "that player"]
COUNTER_RE = re.compile(r"([+-]\d+/[+-]\d+|[a-z]+) counters?\b")
COUNTER_STOP = {"a", "an", "the", "that", "those", "any", "each", "one", "more", "of", "this", "target", "no",
                "all", "other", "another", "its", "their", "your", "two", "three", "x", "not",
                "to", "and", "or", "you", "it", "spell", "can't", "cannot", "unless", "then", "if"}


def terms_in(text):
    """The token-blind terms an ability's text mentions: zones, player scope, counter type."""
    t = (text or "").lower()
    out = set()
    for z in ZONE_TERMS:
        if re.search(r"\b" + z, t):
            out.add("zone:" + z)
    for p in PLAYER_TERMS:
        if re.search(r"\b" + p, t):
            out.add("player:" + p)
    for m in COUNTER_RE.finditer(t):
        k = m.group(1)
        if k not in COUNTER_STOP and k != "+1/+1":
            out.add("counter:" + k)
    return out


def effect_node(bucket, item):
    if bucket == "abilities":
        return item.get("effect")
    if bucket in ("triggers", "replacements"):
        return (item.get("execute") or {}).get("effect")
    return None


def exec_node(bucket, item):
    if bucket == "abilities":
        return item
    if bucket in ("triggers", "replacements"):
        return item.get("execute") or {}
    return {}


def effect_type(bucket, item):
    eff = effect_node(bucket, item)
    return eff.get("type") if isinstance(eff, dict) else None


def chain_len(bucket, item):
    node = exec_node(bucket, item)
    n = 0
    while isinstance(node, dict) and node.get("sub_ability"):
        n += 1
        node = node["sub_ability"]
    return min(n, 2)


def signature(bucket, item):
    """The effect node's scalar string fields (all but `type`) + sub-ability chain length (<= 2)."""
    if bucket == "static_abilities":
        # the mode's NAME only: a dict mode's payload (amounts, filters) is parameter detail the
        # token already summarises, and its key order differs between parser runs
        m = item.get("mode")
        return ("static", str(m) if not isinstance(m, dict) else ",".join(sorted(m)), 0)
    eff = effect_node(bucket, item)
    if not isinstance(eff, dict):
        return ("none", "", chain_len(bucket, item))
    fields = tuple(sorted((k, v) for k, v in eff.items() if isinstance(v, str) and k != "type"))
    return (eff.get("type"), fields, chain_len(bucket, item))


def has_player_scope(bucket, item):
    return bool(exec_node(bucket, item).get("player_scope"))


class Rules:
    """Per-leaf evidence from the clustered members, built once."""

    def __init__(self, sp):
        self.sp = sp
        members = collections.defaultdict(list)
        for fid, l in sp.lab.items():
            if l >= 0 and fid in sp.byid:
                members[l].append(fid)
        self.leaf_terms = {}
        self.dist = collections.defaultdict(collections.Counter)
        self.tot = collections.defaultdict(collections.Counter)
        for l in sorted(members):
            mem = members[l]
            c = collections.Counter()
            for fid in mem:
                e = sp.chunks[sp.byid[fid]["ch"]][fid]
                ts = set()
                for b in ap.BUCKETS:
                    for it in e.get(b) or []:
                        ts |= terms_in(it.get("description"))
                for t in ts:
                    c[t] += 1
                for b, i, it, t in ap.ability_items(e):
                    tk = frozenset(k for k in t if k in sp.vocab)
                    if tk:
                        self.dist[l][(tk, signature(b, it))] += 1
                        self.tot[l][tk] += 1
            self.leaf_terms[l] = {t: n / len(mem) for t, n in c.items()}

    def wording_hits(self, text, leaf):
        return sorted(t for t in terms_in(text) if self.leaf_terms.get(leaf, {}).get(t, 0.0) < BLIND_SHARE)

    def structure(self, bucket, item, tokens, leaf):
        """True / False, or None when the leaf has too few identical-token members to judge."""
        tk = frozenset(tokens)
        n = self.tot[leaf].get(tk, 0)
        if n < 2:
            return None
        k = self.dist[leaf].get((tk, signature(bucket, item)), 0)
        return k >= 2 and k / n >= MIN_SHARE

    def blind_spot(self, bucket, item, tokens, leaf, text):
        """None when the ability clears every blind-spot check, else the check that stopped it."""
        if effect_type(bucket, item) in EXCLUDED_TYPES:
            return "type"
        if has_player_scope(bucket, item):
            return "type"
        if self.wording_hits(text, leaf):
            return "wording"
        s = self.structure(bucket, item, tokens, leaf)
        if s is None:
            return "structure_unknown"
        if not s:
            return "structure"
        return None


def score_items(sp, token_lists, batch=4000):
    """(best leaf, best score) per token list, in batches. Empty token lists score 0."""
    leaves, scores = [], []
    for a in range(0, len(token_lists), batch):
        part = token_lists[a:a + batch]
        lf, sc, _ = sp.score(part)
        leaves.extend(int(x) for x in lf)
        scores.extend(float(x) for x in sc)
    return leaves, scores


def base_class(ntok, size, score):
    if not ntok:
        return "no_tokens"
    if score < THRESHOLD:
        return "below_0.90"
    if ntok == 1 or size >= GENERIC_LEAF:
        return "generic_leaf"
    if ntok < MIN_TOKENS or size > MAX_LEAF:
        return "in_between"
    return "specific"


def is_modal(entry, items):
    return bool(entry.get("modal")) or bool(entry.get("mode_abilities")) or any(
        it.get("modal") or it.get("mode_abilities") for _, _, it, _ in items)


def text_of(item):
    return (item.get("description") or "").strip()


def has_text(text):
    return bool(text) and not re.fullmatch(r"Chapter \d+", text)
