#!/usr/bin/env python3
"""Candidate promotion rule: effect-PARAMETER agreement with the leaf's members (investigation).

The tokens are blind to counter type, zone origin/destination, player scope and chain length. This
checks the ability's real effect node against the leaf's members instead of reading words:

  signature = the effect node's scalar string fields (counter_type, origin, destination, player,
              duration, ... everything except `type`) + the length of its sub_ability chain
  agree     = among the leaf's member items with the SAME token set, the ability's signature
              appears for at least MIN_SHARE of them (and at least 2 items)

Writes build/ability_param_rule_probe.json (new file); prints the findings.
"""
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_probe as ap  # noqa: E402

BUILD = ap.BUILD
MIN_SHARE = 0.15


def effect_node(bucket, item):
    if bucket == "abilities":
        return item.get("effect")
    if bucket in ("triggers", "replacements"):
        return (item.get("execute") or {}).get("effect")
    return None


def chain_len(bucket, item):
    node = item if bucket == "abilities" else (item.get("execute") or {})
    n = 0
    while isinstance(node, dict) and node.get("sub_ability"):
        n += 1
        node = node["sub_ability"]
    return min(n, 2)


def signature(bucket, item):
    eff = effect_node(bucket, item)
    if bucket == "static_abilities":
        m = item.get("mode")
        return ("static", json.dumps(m, sort_keys=True)[:60] if isinstance(m, dict) else str(m), 0)
    if not isinstance(eff, dict):
        return ("none", "", chain_len(bucket, item))
    fields = tuple(sorted((k, v) for k, v in eff.items() if isinstance(v, str) and k != "type"))
    return (eff.get("type"), fields, chain_len(bucket, item))


def main():
    sp = ap.Space()
    L = ap.jl("ledger.json")["rows"]
    P = ap.jl("placements.json")
    also = ap.jl("also_fits.json")["cards"]
    rec_chunk = P["recovered"]["chunk"]

    def entry_of(fid):
        return sp.chunks[sp.byid[fid]["ch"]][fid] if fid in sp.byid else rec_chunk[fid]

    # per leaf: Counter[(frozenset(tokens), signature)] over all member items
    dist = collections.defaultdict(collections.Counter)
    tot = collections.defaultdict(collections.Counter)
    for fid, l in sp.lab.items():
        if l < 0 or fid not in sp.byid:
            continue
        e = sp.chunks[sp.byid[fid]["ch"]][fid]
        for b, i, it, t in ap.ability_items(e):
            tk = frozenset(k for k in t if k in sp.vocab)
            if tk:
                dist[l][(tk, signature(b, it))] += 1
                tot[l][tk] += 1

    def agrees(b, it, tk, leaf):
        tk = frozenset(tk)
        n = tot[leaf].get(tk, 0)
        if n < 2:
            return None                    # the leaf has too few identical-token items to judge
        k = dist[leaf].get((tk, signature(b, it)), 0)
        return k >= 2 and k / n >= MIN_SHARE

    res = collections.Counter()
    fails = []
    for oid, c in also.items():
        e = entry_of(c["f"])
        items = ap.ability_items(e)
        for m in c["m"]:
            b, i = m["b"], m["i"]
            it = next(x for bb, ii, x, _ in items if bb == b and ii == i)
            tk = [k for k in sorted(next(t for bb, ii, _, t in items if bb == b and ii == i)) if k in sp.vocab]
            a = agrees(b, it, tk, m["l"])
            res["links"] += 1
            res["agree" if a else "unknown_too_few_identical" if a is None else "disagree"] += 1
            if a is False and len(fails) < 400:
                fails.append([L[oid]["name"], m["t"][:100], m["l"], list(signature(b, it))[:3] if False else str(signature(b, it))[:110]])
    out = {"min_share": MIN_SHARE, "links": dict(res), "disagree_examples": fails[:40]}

    known = [("Spitting Dilophosaurus", "put a -1/-1"), ("Bandit's Talent", "each opponent discards"),
             ("Dogged Detective", "return this card from your graveyard"),
             ("Gollum the Abandoned", "return this card from your graveyard"),
             ("Helvault", "return all cards exiled"), ("Relic of Progenitus", "exiles a card from their graveyard"),
             ("Biotransference", "you lose 1 life and create")]
    kn = []
    for name, frag in known:
        oid = next((o for o, r in L.items() if r["name"] == name and r["placement"].get("reason") == "below_similarity_floor"), None)
        done = False
        for m in (also.get(oid) or {"m": []})["m"]:
            if frag.lower() in m["t"].lower():
                e = entry_of(also[oid]["f"])
                items = ap.ability_items(e)
                it = next(x for bb, ii, x, _ in items if bb == m["b"] and ii == m["i"])
                tk = [k for k in sorted(next(t for bb, ii, _, t in items if bb == m["b"] and ii == m["i"])) if k in sp.vocab]
                a = agrees(m["b"], it, tk, m["l"])
                kn.append({"card": name, "agrees": a, "caught": a is False, "signature": str(signature(m["b"], it))[:120]})
                done = True
        if not done:
            kn.append({"card": name, "in_links": False})
    out["known_misses"] = kn
    with io.open(os.path.join(BUILD, "ability_param_rule_probe.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    print(json.dumps({k: v for k, v in out.items() if k != "disagree_examples"}, indent=1, ensure_ascii=False))
    for f in out["disagree_examples"][:40]:
        print(f)


if __name__ == "__main__":
    main()
