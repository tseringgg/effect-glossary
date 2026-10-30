#!/usr/bin/env python3
"""Part 2 (stats, coverage, reads) and Part 3 (popular cards) of the browse-group probe. READ ONLY; writes build/browse_groups_probe_results.json and build/browse_groups_reads_sheet.json (new files).

    python src/probe_browse_checks.py

Seeds, fixed here before anything was computed:  READ_SEED 20261030 (the 30 browse groups read), CARD_SEED 20261031 (the 40 popular cards read).
The 30 browse groups are drawn from the browse groups with 2 or more member fine groups and at least 5 cards (a one-member browse group tests no merge); the count of the others is reported apart.
The 40 expected browse groups and their text patterns are written below, before any result was looked at; the text patterns are MY heuristics (not the site's data), so a "miss" is a lead to read, not a verdict.
"""
import collections
import gzip
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browse_probe_data as P

READ_SEED = 20261030
CARD_SEED = 20261031

# concept id: (label, regex over a browse group's name + aliases, regex over a card's oracle text, optional type-line regex)
EXPECTED = [
    ("draw", "Draw cards", r"\bdraw|card advantage|cantrip|card draw", r"\bdraws? (a|an|two|three|four|five|x|that many|\w+) cards?\b", None),
    ("removal", "Removal", r"removal|\bdestroy\b|\bexile\b|spot", r"\b(destroy|exile) target (creature|permanent|nonland|artifact|enchantment|planeswalker|attacking|tapped)", None),
    ("ramp", "Ramp", r"\bramp\b|mana rock|mana dork|add mana|search your library for a (basic )?land|land ramp", r"search your library for (a|up to \w+) (basic )?land|put a land card from your hand onto the battlefield", None),
    ("counterspell", "Counterspell", r"counterspell|counter a spell|counter spell|counter target|counters? (a|any) spell|can't be countered", r"counter target (spell|activated|triggered|noncreature|creature|instant|\w+ spell)", None),
    ("boardwipe", "Board wipe", r"board wipe|wrath|sweeper|destroy all|destroys everything|all creatures", r"\b(destroy|exile) all (creatures|nonland|permanents|artifacts|enchantments|lands)|each creature .* deals? damage to", None),
    ("sacoutlet", "Sacrifice outlet", r"sacrifice outlet|sac outlet|lets you sacrifice|sacrifice", r"(^|\n|: |, )sacrifice (a|an|another|two|three)[^:\n.]*:", None),
    ("tutor", "Tutor", r"tutor|search", r"search your library for (a|an|up to|two|three)\b(?! basic land)(?!.* land card)", None),
    ("recursion", "Recursion / reanimation", r"reanimat|recurs|return.*from (a|your) graveyard|regrowth", r"return (target|up to|a|an|all|each)[^.]*\bcards?\b[^.]*from (your|a|their|target player's) graveyard", None),
    ("blink", "Blink / flicker", r"blink|flicker|exiles? .*(and|then) return", r"exile (target|another|up to|a|each)[^.]*\.?[^.]*return (it|that card|them|those cards)[^.]*to the battlefield", None),
    ("mill", "Mill", r"\bmill|mills cards|puts cards from your library", r"\bmills?\b|put the top \w+ cards? of (your|their|target player's|its owner's) library into", None),
    ("lifegain", "Lifegain", r"lifegain|gain life|gains life", r"you gain \w+ life|gains? \d+ life|gain life equal|gain that much life", None),
    ("manadork", "Mana dork", r"mana dork|mana creature|creature that makes mana|creature.*taps? for mana", r"\{t\}: add \{", r"creature"),
    ("landdenial", "Land denial", r"land denial|destroy a land|destroy all lands|destroy.*land", r"destroy target land|destroy all lands|destroy each land|destroy target nonbasic land", None),
    ("anthem", "Anthem", r"anthem|your whole team|creatures you control get|raises the power of your", r"(other )?creatures you control get \+\d+/\+\d+|creatures you control have", None),
    ("tokens", "Tokens", r"token", r"\bcreates? (a|an|\w+|x) .*tokens?\b", None),
    ("stax", "Stax", r"\bstax\b|spells cost more|can't be cast|doesn't untap|spells can't", r"spells (your opponents|opponents) cast cost|players can't cast|(don't|doesn't) untap during|cost \{\d\} more to cast", None),
    ("burn", "Burn", r"\bburn\b|deal damage to any target|deal damage to (a|target) (player|creature)", r"deals? \d+ damage to (any target|target (player|opponent|creature or player)|each opponent|each player)", None),
    ("bounce", "Bounce", r"bounce|to its owner'?s hand|return to hand", r"return (target|up to|each|all)[^.]*(to|into) (its|their) owner'?s hand", None),
    ("discard", "Discard / hand disruption", r"discard|hand disruption|reveals? (their|a|his) hand", r"(target (player|opponent)|each opponent|each player) discards", None),
    ("costred", "Cost reduction", r"cost reduc|cost less|spells cost|makes spells cost", r"cost \{\d\} less|costs? \{\d\} less|cost less to cast", None),
    ("extraturn", "Extra turn", r"extra turn|take an extra", r"extra turn", None),
    ("clone", "Clone / copy a permanent", r"clone|becomes a copy|token copy|copy a (creature|permanent)|copies creature", r"(becomes? a copy of|create a token that's a copy of|enter(s)? as a copy of)", None),
    ("steal", "Gain control (steal)", r"steal|gain control|threaten|changes control", r"gain control of target|gains? control of (target|all|each)", None),
    ("gyhate", "Graveyard hate", r"graveyard hate|exile (a card |cards )?from (a|your|target player's) graveyard", r"exile (target player's graveyard|all cards from (all|each) graveyards?|target card from a graveyard|all graveyards|a card from a graveyard)", None),
    ("wheel", "Wheel", r"wheel|each player discards.*draws", r"each player (discards|shuffles) (their|his or her) hand[^.]*(draws|then draws)", None),
    ("manarock", "Mana rock", r"mana rock|add colorless mana", r"\{t\}: add", r"artifact"),
    ("fixing", "Mana fixing", r"fixing|any color|mana filter|add mana", r"add (one|two|three) mana of any (one )?color|add \{[wubrg]\}[^.]*or \{[wubrg]\}", None),
    ("tapper", "Tapper", r"tapper|tap a creature|taps? (a|target) creature|freeze", r"\{t\}: tap target (creature|artifact|land|permanent)|tap target creature", None),
    ("fog", "Fog / damage prevention", r"fog|prevent|damage prevention|protects you", r"prevent all (combat )?damage|prevent the next \w+ damage", None),
    ("proliferate", "Proliferate", r"proliferate", r"\bproliferate\b", None),
    ("p1p1", "+1/+1 counters", r"\+1/\+1 counter|counters on", r"\+1/\+1 counters?", None),
    ("equipment", "Equipment", r"equipment|attach|equipped", r"\bequip\b|equipped creature", None),
    ("evasion", "Evasion", r"evasion|can't be blocked|flying|unblockable|menace", r"can't be blocked|\bflying\b|\bmenace\b|\bfear\b|\bintimidate\b|\bshadow\b", None),
    ("protection", "Protection / hexproof", r"hexproof|protect|indestructible|protection|shroud", r"\bhexproof\b|\bindestructible\b|gains? protection|\bshroud\b|can't be countered", None),
    ("trick", "Combat trick / pump", r"combat trick|\bpump\b|gets \+n/\+n until|firebreathing|giant growth", r"gets? \+\d+/\+\d+ until end of turn", None),
    ("drain", "Drain", r"\bdrain\b|each opponent loses life", r"(each|target) opponent loses \w+ life|target (player|opponent) loses \w+ life", None),
    ("copyspell", "Copy a spell", r"copy spell|copies spell|copy a spell|copies an instant|copy", r"copy target (instant|sorcery|spell|activated)|copy (that|it|target) spell|casts? a copy", None),
    ("artifactrem", "Artifact / enchantment removal", r"artifact removal|disenchant|naturalize|destroy an artifact|destroy an enchantment|enchantment removal", r"(destroy|exile) target (artifact|enchantment)", None),
    ("pillowfort", "Pillowfort", r"pillowfort|stops creatures from attacking|can't attack|prevent attack", r"creatures can't attack you|can't attack you or", None),
    ("treasure", "Treasure / Food / Clue tokens", r"treasure|food|clue|blood", r"\b(treasure|food|clue|blood) tokens?\b", None),
]
assert len(EXPECTED) == 40, len(EXPECTED)


def jgz(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


def card_text(o):
    if o.get("card_faces") and not o.get("oracle_text"):
        return "\n".join(f.get("oracle_text", "") for f in o["card_faces"])
    return o.get("oracle_text", "")


def card_types(o):
    if o.get("type_line"):
        return o["type_line"]
    return " // ".join(f.get("type_line", "") for f in o.get("card_faces", []))


def main():
    D = P.Data()
    draft = P.jl(os.path.join(P.BUILD, "browse_groups_draft.json"))
    BG, F2B = draft["groups"], draft["fine_to_bg"]
    res = {}
    # ----------------------------------------------------------------- 2.2 statistics
    cards_per = {b: v["cards"] for b, v in BG.items()}
    mem_per = {b: len(v["members"]) for b, v in BG.items()}
    primary_per = {b: sum(1 for m in v["members"] if m["role"] == "primary") for b, v in BG.items()}
    nonempty = [b for b in BG if cards_per[b] > 0]

    def hist(vals, edges):
        out = collections.OrderedDict()
        for lo, hi in zip(edges, edges[1:] + [10 ** 9]):
            out["%d-%s" % (lo, hi - 1 if hi < 10 ** 9 else "")] = sum(1 for x in vals if lo <= x < hi)
        return out
    res["n_bg"] = len(BG)
    res["n_nonempty"] = len(nonempty)
    res["n_empty"] = len(BG) - len(nonempty)
    res["empty_names"] = [BG[b]["name"] for b in BG if cards_per[b] == 0]
    res["members_hist"] = hist([mem_per[b] for b in BG], [1, 2, 3, 6, 11, 21, 41])
    res["cards_hist"] = hist([cards_per[b] for b in nonempty], [1, 5, 10, 20, 50, 100, 300, 1000])
    res["cards_ge"] = {str(t): sum(1 for b in nonempty if cards_per[b] >= t) for t in (5, 10, 15, 20, 30, 50, 100)}
    res["singletons"] = sum(1 for b in BG if mem_per[b] == 1)
    ms = sorted(mem_per.values())
    res["members_median"] = ms[len(ms) // 2]
    res["members_mean"] = round(sum(ms) / len(ms), 2)
    res["members_max"] = ms[-1]
    top = sorted(BG, key=lambda b: -cards_per[b])[:40]
    res["top40"] = [{"id": b, "name": BG[b]["name"], "members": mem_per[b], "cards": cards_per[b], "topic": BG[b]["topic"], "bases": BG[b]["bases"]} for b in top]
    res["oversize"] = [{"id": b, "name": BG[b]["name"], "members": mem_per[b], "cards": cards_per[b]} for b in sorted(BG, key=lambda b: -mem_per[b]) if mem_per[b] >= 30]
    res["by_confidence"] = dict(collections.Counter(v["confidence"] for v in F2B.values()))
    res["by_basis"] = dict(collections.Counter(v["basis"] for v in F2B.values()))
    res["by_layer_conf"] = {L: dict(collections.Counter(v["confidence"] for g, v in F2B.items() if P.layer_of(g) == L)) for L in sorted({P.layer_of(g) for g in F2B})}
    res["two_bg"] = sum(1 for v in F2B.values() if len(v["bg"]) == 2)
    res["two_bg_basis"] = dict(collections.Counter(v["basis"] for v in F2B.values() if len(v["bg"]) == 2))
    # does not map cleanly
    unclean = []
    for g, v in sorted(F2B.items()):
        why = []
        if v["basis"].startswith("family fallback"):
            why.append("no rule reached it: parked in the family's 'Other' browse group")
        if v["confidence"] == "low" and not why:
            why.append("low: " + ("; ".join(v["notes"]) or v["basis"]))
        if v["overlap_hint"] and v["confidence"] != "high":
            why.append("overlap hint: %.0f%% of its cards are in '%s'" % (v["overlap_hint"]["overlap"] * 100, BG[v["overlap_hint"]["bg"]]["name"]))
        if D.size(g) == 0:
            why.append("no cards today (a hand-defined group nobody has placed into yet)")
        if why:
            unclean.append({"id": g, "name": D.name(g), "layer": P.layer_of(g), "cards": D.size(g), "bg": BG[v["bg"][0]]["name"], "basis": v["basis"], "confidence": v["confidence"], "why": why})
    res["unclean"] = unclean
    res["unclean_by_reason"] = {
        "family fallback": sum(1 for u in unclean if any(w.startswith("no rule reached") for w in u["why"])),
        "low (not fallback)": sum(1 for u in unclean if any(w.startswith("low:") for w in u["why"])),
        "overlap hint, medium/low": sum(1 for u in unclean if any(w.startswith("overlap hint") for w in u["why"])),
        "empty hand-defined": sum(1 for u in unclean if any(w.startswith("no cards") for w in u["why"]))}
    # ----------------------------------------------------------------- 2.3 coverage
    today, after = {}, {}
    offered = set(D.fine)
    notoffered = set(D.groups_all) - offered
    card_gs = collections.defaultdict(set)
    for g, ms_ in D.members.items():
        for oid in ms_:
            card_gs[oid].add(g)
    with_today = {oid for oid, gs in card_gs.items() if gs & offered}
    only_notoffered = {oid for oid, gs in card_gs.items() if gs and not (gs & offered)}
    lost = [oid for oid in with_today if not any(F2B.get(g) for g in card_gs[oid] & offered)]
    res["coverage"] = {"cards_total": len(D.cards), "cards_with_an_offered_group": len(with_today), "cards_with_a_browse_group": len(with_today) - len(lost), "cards_that_lose_all": len(lost),
                       "cards_only_in_not_offered_groups": len(only_notoffered), "not_offered_groups": sorted(D.name(g) for g in notoffered)[:30]}
    # cards whose only browse groups are low confidence / fallback
    only_low = [oid for oid in with_today if all(F2B[g]["confidence"] == "low" for g in card_gs[oid] & offered)]
    only_fb = [oid for oid in with_today if all(F2B[g]["basis"].startswith("family fallback") for g in card_gs[oid] & offered)]
    res["coverage"]["cards_whose_browse_groups_are_all_low"] = len(only_low)
    res["coverage"]["cards_only_in_a_family_fallback_group"] = len(only_fb)
    per_card_bg = {oid: sorted({b for g in card_gs[oid] & offered for b in F2B[g]["bg"]}) for oid in with_today}
    res["coverage"]["browse_groups_per_card"] = {"median": sorted(len(v) for v in per_card_bg.values())[len(per_card_bg) // 2], "mean": round(sum(len(v) for v in per_card_bg.values()) / len(per_card_bg), 2), "max": max(len(v) for v in per_card_bg.values()),
                                                  "fine_per_card_mean": round(sum(len(card_gs[o] & offered) for o in with_today) / len(with_today), 2)}
    # ----------------------------------------------------------------- 2.4 reads sheet (30 browse groups)
    rng = random.Random(READ_SEED)
    pool = sorted(b for b in BG if mem_per[b] >= 2 and cards_per[b] >= 5)
    pick = rng.sample(pool, 30)
    sheet = []
    for b in pick:
        v = BG[b]
        cs = sorted(set().union(*[D.members.get(m["id"], set()) for m in v["members"]]))
        samp = rng.sample(cs, min(5, len(cs)))
        sheet.append({"id": b, "name": v["name"], "cards": cards_per[b], "members": [[m["id"], m["role"], D.name(m["id"]), P.layer_of(m["id"]), D.size(m["id"]), F2B[m["id"]]["basis"], F2B[m["id"]]["confidence"]] for m in v["members"]],
                      "sample": [D.cards[o]["name"] for o in samp]})
    res["read_pool"] = len(pool)
    res["read_ids"] = pick
    with open(os.path.join(P.BUILD, "browse_groups_reads_sheet.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(sheet, fh, ensure_ascii=False, indent=1)
    # ----------------------------------------------------------------- 2.5 the 50 most popular groups, and the 40 expected browse groups
    pop = sorted(D.fine, key=lambda g: -D.size(g))[:50]
    res["top50_groups"] = [{"id": g, "name": D.name(g), "layer": P.layer_of(g), "cards": D.size(g), "bg": [BG[b]["name"] for b in F2B[g]["bg"]], "bg_members": mem_per[F2B[g]["bg"][0]],
                            "basis": F2B[g]["basis"], "confidence": F2B[g]["confidence"]} for g in pop]
    exp = []
    for cid, label, bgre, txtre, tl in EXPECTED:
        rx = re.compile(bgre, re.I)
        hits = []
        for b, v in BG.items():
            hay = v["name"] + " | " + " | ".join(v["aliases"])
            if rx.search(hay) and cards_per[b] > 0:
                hits.append(b)
        hits.sort(key=lambda b: -cards_per[b])
        exp.append({"id": cid, "label": label, "n_match": len(hits), "matches": [[b, BG[b]["name"], cards_per[b], mem_per[b]] for b in hits[:8]]})
    res["expected"] = exp
    # ----------------------------------------------------------------- Part 3: the 500 most popular cards
    ranked = sorted((c["rank"], oid) for oid, c in D.cards.items() if c["rank"] is not None)
    top500 = [oid for _, oid in ranked[:500]]
    oracle = {}
    top500set = set(top500)
    for o in jgz(os.path.join(P.HERE, "data", "scryfall-oracle-cards.jsonl.gz")):
        if o["oracle_id"] in top500set:
            oracle[o["oracle_id"]] = o
    rows = []
    miss_counter = collections.Counter()
    for oid in top500:
        o = oracle.get(oid, {})
        txt = card_text(o).lower().replace(o.get("name", "~").lower(), "~")
        tl = card_types(o).lower()
        gs = sorted(card_gs[oid] & offered)
        bgs = sorted({b for g in gs for b in F2B[g]["bg"]})
        bg_hay = {b: (BG[b]["name"] + " | " + " | ".join(BG[b]["aliases"])) for b in bgs}
        fine_hay = {g: D.name(g) + " | " + D.desc.get(g, "") for g in gs}
        need = []
        for cid, label, bgre, txtre, tre in EXPECTED:
            if tre and not re.search(tre, tl):
                continue
            if re.search(txtre, txt, re.I | re.M):
                have = [b for b in bgs if re.search(bgre, bg_hay[b], re.I)]
                need.append({"concept": cid, "present": bool(have)})
        rows.append({"oid": oid, "name": D.cards[oid]["name"], "rank": D.cards[oid]["rank"], "fine": [[g, D.name(g), F2B[g]["bg"]] for g in gs], "bg": bgs, "expected": need, "text": card_text(o)})
        for n in need:
            if not n["present"]:
                miss_counter[n["concept"]] += 1
    res["top500_n"] = len(rows)
    res["top500_no_fine_group"] = sum(1 for r in rows if not r["fine"])
    res["top500_with_expected"] = sum(1 for r in rows if r["expected"])
    res["top500_cards_missing_expected"] = sum(1 for r in rows if any(not n["present"] for n in r["expected"]))
    res["top500_expected_pairs"] = sum(len(r["expected"]) for r in rows)
    res["top500_missing_pairs"] = sum(1 for r in rows for n in r["expected"] if not n["present"])
    res["top500_missing_by_concept"] = dict(miss_counter.most_common())
    res["top500_bg_per_card_mean"] = round(sum(len(r["bg"]) for r in rows) / len(rows), 2)
    res["top500_fine_per_card_mean"] = round(sum(len(r["fine"]) for r in rows) / len(rows), 2)
    # 40 read
    rng2 = random.Random(CARD_SEED)
    rd = rng2.sample(range(len(rows)), 40)
    res["card_read_idx"] = rd
    with open(os.path.join(P.BUILD, "browse_groups_cards_sheet.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump([{**{k: rows[i][k] for k in ("oid", "name", "rank", "text", "expected")}, "fine": [[g, n, [BG[b]["name"] for b in bb]] for g, n, bb in rows[i]["fine"]], "bg": [BG[b]["name"] for b in rows[i]["bg"]]} for i in rd], fh, ensure_ascii=False, indent=1)
    # misses list (all) for fix classification
    miss_rows = []
    for r in rows:
        for n in r["expected"]:
            if n["present"]:
                continue
            cid = n["concept"]
            exp_ = next(e for e in EXPECTED if e[0] == cid)
            bgre = re.compile(exp_[2], re.I)
            concept_exists = any(bgre.search(v["name"] + " | " + " | ".join(v["aliases"])) and cards_per[b] > 0 for b, v in BG.items())
            fine_related = [g for g, nm, bb in r["fine"] if bgre.search(nm + " | " + D.desc.get(g, ""))]
            fix = "missing browse group" if not concept_exists else ("mapping change" if fine_related else "hand placement")
            miss_rows.append({"card": r["name"], "rank": r["rank"], "concept": cid, "fix": fix, "related_fine": [D.name(g) for g in fine_related][:3]})
    res["top500_misses"] = miss_rows
    res["top500_fix_counts"] = dict(collections.Counter(m["fix"] for m in miss_rows))
    with open(os.path.join(P.BUILD, "browse_groups_probe_results.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print("wrote results; bg", res["n_bg"], "nonempty", res["n_nonempty"], "unclean", len(unclean), "lost", len(lost))
    return res


if __name__ == "__main__":
    main()
