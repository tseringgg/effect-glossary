#!/usr/bin/env python3
"""Writes the review sheet (build/browse_groups_review.md) and the probe report (reports/browse-groups-probe.md) from the probe's JSON files. READ ONLY on corrections/ and every existing file.

    python src/probe_browse_clutter.py && python src/probe_browse_draft.py && python src/probe_browse_checks.py && python src/probe_browse_report.py
"""
import collections
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browse_probe_data as P

OUT_REVIEW = os.path.join(P.BUILD, "browse_groups_review.md")
OUT_REPORT = os.path.join(P.HERE, "reports", "browse-groups-probe.md")


def fmt(n):
    return "{:,}".format(n)


def pct(a, b):
    return "%.0f%%" % (100.0 * a / b) if b else "n/a"


def review(D, draft, res):
    BG, F2B = draft["groups"], draft["fine_to_bg"]
    bids = D.bucket_names
    by_topic = collections.OrderedDict((t, []) for t in bids + ["(no topic)"])
    for b, v in BG.items():
        t = v["topic"][0] if v["topic"] else "(no topic)"
        by_topic[t].append(b)
    rank = {oid: c["rank"] for oid, c in D.cards.items()}
    L = []
    L.append("# Browse groups: review sheet (DRAFT, read-only probe output)\n")
    L.append("Written by `src/probe_browse_report.py` from `build/browse_groups_draft.json`. Nothing here is read by the site and nothing is in `corrections/`. Mark each section, then the marks become `corrections/browse_groups.json`.\n")
    L.append("**How to mark.** Each section has one line of boxes: *keep* (name, description and members are right), *rename* (write the name), *merge into* (write the other section's id), *split* (say how), *drop*. A member line ends `basis/confidence`: `high` = a hand merge, a name twin or a good alias; `medium` = a partial alias, tag slug, taxonomy node or name words; `low` = no word of its name is in the browse group's name, or no rule reached it (parked in an `Other:` group). `+2nd` = this fine group is also in a second browse group (at most two). `variant of` / `overlap hint` is a lead from card overlap, never a mapping.\n")
    L.append("**Descriptions and aliases are drafts.** A description is the first existing one-line description among the members (many were auto-written from the most popular members' lines, often starting “Example:”); an alias is one a member already answers to, plus the alias-file words. Both need a hand pass. A topic is the bucket(s) most of the members sit in; 148 browse groups sit in no topic (the bucket map left them out), which is a mapping gap to decide.\n")
    n_ne = sum(1 for v in BG.values() if v["cards"] > 0)
    L.append("**Counts.** %s browse groups (%s with at least one card, %s empty because their only member is a hand-defined group nobody has placed into). Sorted by topic, then by cards, largest first. Sections with `Other:` in the name are parking places, not ideas: split them or find homes.\n" % (fmt(len(BG)), fmt(n_ne), fmt(len(BG) - n_ne)))
    L.append("| Topic | Browse groups | Cards in them (sum, with repeats) |\n|---|---:|---:|")
    for t, bs in by_topic.items():
        if bs:
            L.append("| %s | %d | %s |" % (t, len(bs), fmt(sum(BG[b]["cards"] for b in bs))))
    L.append("")
    for t, bs in by_topic.items():
        if not bs:
            continue
        bs.sort(key=lambda b: (-BG[b]["cards"], BG[b]["name"]))
        L.append("\n---\n\n## Topic: %s (%d browse groups)\n" % (t, len(bs)))
        for b in bs:
            v = BG[b]
            mem = v["members"]
            confs = collections.Counter(F2B[m["id"]]["confidence"] for m in mem if m["role"] == "primary")
            basis = collections.Counter(F2B[m["id"]]["basis"] for m in mem if m["role"] == "primary")
            cs = set()
            for m in mem:
                cs |= D.members.get(m["id"], set())
            samp = sorted(cs, key=lambda o: (rank.get(o) is None, rank.get(o) or 0, D.cards[o]["name"]))[:5]
            L.append("### %s · %s" % (b, v["name"]))
            L.append("**%s cards · %d fine group%s** · basis: %s · confidence: %s" % (fmt(v["cards"]), len(mem), "" if len(mem) == 1 else "s", ", ".join("%s (%d)" % (k, n) for k, n in basis.most_common(3)), ", ".join("%s %d" % (k, confs[k]) for k in ("high", "medium", "low") if confs[k])))
            if v["cards"] == 0:
                L.append("**EMPTY today:** every member is a hand-defined group with no placements. It would open an empty page.")
            L.append("- Description: %s" % (v["description"] or "(none: write one line)"))
            L.append("- Aliases: %s" % (", ".join(v["aliases"]) or "(none)"))
            L.append("- Topic: %s" % ", ".join(v["topic"] or ["(none)"]))
            L.append("- Decision: [ ] keep  [ ] rename → ______  [ ] merge into ______  [ ] split  [ ] drop")
            L.append("- Sample cards (most popular): %s" % (", ".join(D.cards[o]["name"] for o in samp) or "(none)"))
            L.append("- Member fine groups:")
            for m in mem:
                g = m["id"]
                f = F2B[g]
                extra = ""
                if m["role"] == "second":
                    extra += " · **2nd browse group** (primary: %s)" % BG[f["bg"][0]]["name"]
                elif len(f["bg"]) == 2:
                    extra += " · +2nd: %s" % BG[f["bg"][1]]["name"]
                if f.get("overlap_hint"):
                    extra += " · overlap hint: %.0f%% of its cards are in “%s”" % (f["overlap_hint"]["overlap"] * 100, BG[f["overlap_hint"]["bg"]]["name"])
                for n in f["notes"]:
                    extra += " · %s" % n
                L.append("  - `%s` %s · %s cards · %s/%s%s" % (P.layer_of(g), D.name(g).replace("|", "/")[:110], fmt(D.size(g)), f["basis"], f["confidence"], extra))
            L.append("")
    with open(OUT_REVIEW, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L))
    return len(L)


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def report(D, draft, res, cl, reads):
    BG, F2B = draft["groups"], draft["fine_to_bg"]
    R = []
    a = R.append
    rows = cl["searches"]
    nz = [r for r in rows if r["results"] > 0]
    tot = sum(r["results"] for r in nz)
    resn = [r["results"] for r in rows]
    nc = [r for r in nz if r["q"] != "creature"]
    tot_nc = sum(r["results"] for r in nc)
    a("# Browse groups: probe report (read-only)\n")
    a("Written for: the project owner, who will review the draft mapping and decide whether to build the browse-group level. Nothing was built, committed or changed; every new file is listed at the end. Dates: 2026-10-29/30.\n")
    a("**Verdict in one paragraph.** The design is workable, but not as a pure rule pass. The read-only rules (merged pages, name twins, aliases, tag slugs, keywords, taxonomy nodes) place all 1,942 fine groups and lose no card, and 27 of 30 browse groups I read were right (0 wrong, 3 loose, under the bar of 6). But the rules give %s browse groups, not 150 to 300 (%s have at least one card; %s have 20 or more cards), and 25 of the 40 browse groups a deckbuilder would expect come out split across 2 to 6 browse groups that are one idea (Burn / Deal damage, Counterspell / Counter a spell, Tutor in four places). Those splits are merge decisions only you can make. Plan on about 250 browse groups in the tree (the head) plus a search-only tail, and on roughly 8 to 16 hours of review for a first pass (an estimate, section 5).\n" % (fmt(res["n_bg"]), fmt(res["n_nonempty"]), res["cards_ge"]["20"]))

    # ---------------------------------------------------------------- 1
    a("---\n\n## 1. Clutter today (measured; nothing changed)\n")
    a("**Search set.** Seed 20261029, fixed in `src/probe_browse_clutter.py` before anything was computed: your 7 examples (dragon, draw cards, board wipe, recursion, land denial, sacrifice, tutor) + 43 drawn from three pools I wrote down first (24 mechanics, 30 slang terms, 13 card types). The real `reports/groupsearch.js` ran against the real `build/group_search/index.json` with the page's defaults (tentative and community-tag groups on). *Near-twin* = same core name (qualifiers, “Family ›” prefix and “less common kinds” removed), or 70% card overlap. Overlap is reported two ways because the brief does not say which: the overlap coefficient |A∩B|/min(|A|,|B|) (a small group inside a big one counts) and the strict Jaccard.\n")
    a("| | all 50 searches | without “creature” (1,027 results) |\n|---|---:|---:|")
    a("| group results returned | %s | %s |" % (fmt(tot), fmt(tot_nc)))
    a("| median / mean / max per search | %s / %.1f / %s | |" % (st.median(resn), st.mean(resn), fmt(max(resn))))
    a("| searches with 0 results | %d (recursion, fetch land, overrun) | |" % sum(1 for x in resn if x == 0))
    a("| searches with 10 or more results | %d | |" % sum(1 for x in resn if x >= 10))
    a("| results that are a near-twin of another result, same core name | %s (%s) | %s |" % (sum(r["twin_results_core"] for r in nz), pct(sum(r["twin_results_core"] for r in nz), tot), sum(r["twin_results_core"] for r in nc)))
    a("| … core name or overlap coefficient ≥ 70%% | %s (%s) | %s (%s) |" % (sum(r["twin_results_overlap"] for r in nz), pct(sum(r["twin_results_overlap"] for r in nz), tot), sum(r["twin_results_overlap"] for r in nc), pct(sum(r["twin_results_overlap"] for r in nc), tot_nc)))
    a("| … core name or strict Jaccard ≥ 70%% | %s (%s) | %s |" % (sum(r["twin_results_strict"] for r in nz), pct(sum(r["twin_results_strict"] for r in nz), tot), sum(r["twin_results_strict"] for r in nc)))
    a("| distinct ideas after collapsing twins (core or overlap) | %s of %s | %s of %s |" % (fmt(sum(r["ideas"] for r in nz)), fmt(tot), fmt(sum(r["ideas"] for r in nc)), fmt(tot_nc)))
    a("| searches that show at least one twin pair | %d of %d with results (core name), %d (with overlap) | |" % (sum(1 for r in nz if r["twin_results_core"]), len(nz), sum(1 for r in nz if r["twin_results_overlap"])))
    a("")
    a("**What this says.** Collapsing twins removes %s of %s results (%s), not most of them. The clutter is mainly *breadth*: a generic word returns many different ideas (creature 1,027, artifact 152, sacrifice 81, draw cards 64, enchantment 59; the page shows 30). The twins show up where you would expect (“Surveil” three times, “Flash” twice, “Counter a spell” as a merged page and again as its member, “Destroy an artifact” as leaf and loose group) and in 21 of 47 searches with results. Three other defects the reads found, which the browse level does not fix on its own: (1) **hand-defined groups with 0 cards are returned first** (blink, cantrip, mana rock: the first click lands on an empty page); (2) description matches pull in unrelated groups (“zombie” returns “Sacrifice a creature”); (3) keyword prefixes (“flash” returns Flashback).\n" % (fmt(tot - sum(r["ideas"] for r in nz)), fmt(tot), pct(tot - sum(r["ideas"] for r in nz), tot)))
    a("**Top 10 read for 10 searches** (drawn with the same generator after the 50: %s). My reading of each:\n" % ", ".join(cl["reads"]))
    for q in cl["reads"]:
        a("- *%s*: %s" % (q, reads["top10"][q]))
    a("")
    a("**Groups by layer** (measured). The page offers %s fine groups. %s of them are hashed ids that can change on a rebuild (leaf, tentative, loose); %s have stable ids.\n" % (fmt(cl["fine_groups"]), fmt(cl["layers"]["leaf"] + cl["layers"]["tent"] + cl["layers"]["loose"]), fmt(cl["layers"]["tag"] + cl["layers"]["kw"] + cl["layers"]["rp"] + cl["layers"]["hand"])))
    lay = cl["layers"]
    sh = cl["share_by_layer"]
    a(table([[L, fmt(lay[L]), fmt(sh.get(L, 0)), pct(sh.get(L, 0), lay[L])] for L in ("leaf", "tent", "loose", "tag", "kw", "rp", "hand")] + [["**all**", fmt(cl["fine_groups"]), fmt(cl["groups_sharing_core"]), pct(cl["groups_sharing_core"], cl["fine_groups"])]], ["layer", "fine groups", "share a core name with another group", "share"]))
    a("\n%d core-name families hold those %d groups; %d of the families span more than one layer (a leaf and its tentative or loose twin). Not groups for this probe: 172 keyword-filter pages (`yk:`, shown in search as group rows), 13 merged pages (display only), the type pages and the 42 ability-type pages (filters). The 25 offered=0 groups (loose “less common effects” buckets, retired hand groups) are outside the mapping; %d cards are only in those (see 2.4).\n" % (cl["core_families"], cl["groups_sharing_core"], cl["families_spanning_layers"], res["coverage"]["cards_only_in_not_offered_groups"]))
    a("Largest families: " + "; ".join("“%s” ×%d" % (c, n) for n, c in cl["largest_families"][:8]) + ".\n")

    # ---------------------------------------------------------------- 2
    a("---\n\n## 2. The draft mapping (measured, then read)\n")
    a("`src/probe_browse_draft.py` → `build/browse_groups_draft.json`. Deterministic; no hand assignment. Rules in the order you gave, with one addition I had to make (marked): 1 merged pages → 2 name-twin families → 3 aliases (alias group lists that overlap ≥ 50% are one concept) → 4 tag slug roots → 5 keyword blocks (a two-keyword block is in both keywords: the structural second mapping) → **6 the existing taxonomy node (family › node) as the “broad bucket” refinement**: the 15 topics alone are far too coarse to be browse groups, so a leaf goes to its node, and a tentative or loose group goes to the node of the leaf whose name shares most words with it → 7 hand-defined groups no rule reaches become their own browse group. Card overlap never assigns; it only records a lead (`overlap_hint`) when 70% of a group's cards sit in another browse group. Two small rules I added after the first run showed the problem: concepts with the same display name merge (the name-twin rule applied to concepts), and a named artifact token (Treasure, Food, Clue ...) is its own browse group because the Tokens node held 125 fine groups.\n")
    a("### 2.1 Numbers\n")
    a("- **Browse groups: %s** (%s with cards, %s empty hand-defined, listed in the review sheet). With ≥ 5 cards: %s; ≥ 10: %s; ≥ 20: %s; ≥ 50: %s; ≥ 100: %s." % (fmt(res["n_bg"]), fmt(res["n_nonempty"]), res["n_empty"], res["cards_ge"]["5"], res["cards_ge"]["10"], res["cards_ge"]["20"], res["cards_ge"]["50"], res["cards_ge"]["100"]))
    a("- **Size, in fine groups per browse group:** median %d, mean %.1f, max %d. %s" % (res["members_median"], res["members_mean"], res["members_max"], "; ".join("%s: %d" % (k, v) for k, v in res["members_hist"].items())))
    a("- **Size, in cards (non-empty):** %s" % "; ".join("%s: %d" % (k, v) for k, v in res["cards_hist"].items()))
    a("- **Singletons (one fine group): %d** (%s of all browse groups). By what their one fine group came from (basis / layer): %s. They are mostly legitimate ideas (Egg, Coin flip, Initiative, Megamorph), not merge failures." % (res["singletons"], pct(res["singletons"], res["n_bg"]), ", ".join("%s %d" % (k, v) for k, v in collections.Counter(F2B[v["members"][0]["id"]]["basis"].split(" + ")[0] + " / " + P.layer_of(v["members"][0]["id"]) for v in BG.values() if len(v["members"]) == 1).most_common(8))))
    a("- **Confidence of the %s fine-group mappings:** high %s, medium %s, low %s." % (fmt(len(F2B)), fmt(res["by_confidence"].get("high", 0)), fmt(res["by_confidence"].get("medium", 0)), fmt(res["by_confidence"].get("low", 0))))
    a("  By basis: " + "; ".join("%s %s" % (k, fmt(v)) for k, v in sorted(res["by_basis"].items(), key=lambda kv: -kv[1])) + ".")
    a("  By layer (high/medium/low): " + "; ".join("%s %s/%s/%s" % (L, v.get("high", 0), v.get("medium", 0), v.get("low", 0)) for L, v in res["by_layer_conf"].items()) + ".")
    a("  Confidence is the rule's, not a verdict: **medium** includes the 999 leaves placed by taxonomy node, whose names I only spot-read. The overlap hint is not in the confidence.")
    a("- **Fine groups in two browse groups: %d** (%s). The brief allows at most two and the rules make a second mapping only for a keyword pair (Flying + Haste) or when an alias names a second concept (Destroy an artifact or enchantment: Artifact removal and Disenchant)." % (res["two_bg"], ", ".join("%s %d" % (k, v) for k, v in res["two_bg_basis"].items())))
    a("")
    a("### 2.2 The 40 biggest browse groups (by cards)\n")
    a(table([[i + 1, t["id"], t["name"], fmt(t["cards"]), t["members"], "; ".join(t["topic"])] for i, t in enumerate(res["top40"])], ["#", "id", "name", "cards", "fine groups", "topics"]))
    a("\nNine browse groups have 30 or more fine groups (%s). Those are the “one idea, many variants” case the design wants (Create tokens with 115 variants, Put +1/+1 counters 49, Destroy 43), except that “Exile” (48) mixes removal with blink and “Has a keyword” (54) and “Gains a keyword” (44) are parser-shaped, not choices a deckbuilder makes. \n" % ", ".join("%s %d" % (o["name"], o["members"]) for o in res["oversize"]))
    a("### 2.3 Fine groups that do not map cleanly\n")
    ub = res["unclean_by_reason"]
    a("%d fine groups carry at least one flag (the full list is in the table below and in the draft file's `fine_to_bg` with its notes). By reason (a group can have more than one): **%d parked in an `Other: <family>` group** (no rule reached them; these are the loose and tentative groups with “less common kinds”-style names, 7 parking browse groups: `Other: Pump and grant abilities` 28, `Other: Continuous effects (static)` 23, …); **%d low** (the name shares no word with its browse group); **%d with an overlap hint** (70%% of its cards sit in a different browse group, and the mapping is not high); **%d empty hand-defined groups** (no placed cards). Only the first is a mapping failure. The “low” ones are flags to read (most are fine: “Creatures you control have haste” under “Has a keyword” is right, “Enters tapped” under “Tap” is not); the hint and the empty cases are leads.\n" % (len(res["unclean"]), ub["family fallback"], ub["low (not fallback)"], ub["overlap hint, medium/low"], ub["empty hand-defined"]))
    shown = [u for u in res["unclean"] if any(w.startswith("no rule reached") or w.startswith("low:") for w in u["why"])]
    a("Parked or low (%d):\n" % len(shown))
    a(table([[u["layer"], u["name"][:70].replace("|", "/"), u["cards"], u["bg"][:40], "; ".join(w[:90] for w in u["why"])] for u in shown], ["layer", "fine group", "cards", "now in", "why"]))
    a("\nOverlap-hint and empty cases are listed per group in `build/browse_groups_draft.json` (`overlap_hint`) and inside each section of the review sheet.\n")
    a("### 2.4 Does every card keep a browse group?\n")
    c = res["coverage"]
    a("Yes, by construction and by check: %s cards have at least one offered fine group today; %s keep at least one browse group; **%d lose all**. %s cards are only in the 25 non-offered groups (the “less common effects” buckets): they have no fine group today either, so the browse level does not change them. Browse groups per card: median %d, mean %.2f (fine groups per card: %.2f). Weaker: %s cards would have only low-confidence browse groups and %s only a parked `Other:` group, so they are covered on paper and badly placed.\n" % (fmt(c["cards_with_an_offered_group"]), fmt(c["cards_with_a_browse_group"]), c["cards_that_lose_all"], fmt(c["cards_only_in_not_offered_groups"]), c["browse_groups_per_card"]["median"], c["browse_groups_per_card"]["mean"], c["browse_groups_per_card"]["fine_per_card_mean"], fmt(c["cards_whose_browse_groups_are_all_low"]), fmt(c["cards_only_in_a_family_fallback_group"])))
    a("*This check is mechanical and independent of my reading, but it is nearly trivial: the mapping is total, so no card can lose a group. Hand placements (%d) were included as members.*\n" % D.hand_adds)
    a("### 2.5 Group-level read: 30 browse groups\n")
    a("Seed 20261030, fixed in `src/probe_browse_checks.py` before the draft was computed. Drawn from the %d browse groups with two or more fine groups and at least 5 cards (a one-member browse group tests no merge). I read the member names and 5 sample cards of each (`build/browse_groups_reads_sheet.json`).\n" % res["read_pool"])
    sheet = json.load(open(os.path.join(P.BUILD, "browse_groups_reads_sheet.json"), encoding="utf-8"))
    marks = collections.Counter(reads["groups"][str(i)][0] for i in range(1, 31))
    a("**Result: right %d, loose %d, wrong %d.** Not right: %d (the bar is more than 6, so the rule passes this check)." % (marks["right"], marks["loose"], marks["wrong"], marks["loose"] + marks["wrong"]))
    a("")
    a(table([[i + 1, s["id"], s["name"][:55], len(s["members"]), reads["groups"][str(i + 1)][0], reads["groups"][str(i + 1)][1]] for i, s in enumerate(sheet)], ["#", "id", "browse group", "fine groups", "mark", "note"]))
    a("\n**Caveats, plainly.** (1) I wrote the rules and I did the reading: not independent. (2) The sample is multi-member groups only; it contains none of the nine oversize groups or the `Other:` parking groups. A supplementary look at those: `Other:` ×7 are junk drawers by design (wrong as browse groups); “Tap” holds “Enters tapped” (wrong); “Exile” mixes removal and blink; “Tutor” holds the basic-land searches that “Ramp” also holds; “Mana rock” holds “Add colorless mana”, which includes lands; “Firebreathing” is one 613-card group named after a niche slang. Counting those as not right, the honest figure is “the multi-member middle is sound; the very large and the parked groups need hand work”. (3) Names: about 15 of the 30 have jargon or slang names (Jump, Cda, Time walk, Theft) that the alias-derived naming chose; naming is a review task, not a mapping failure.\n")
    a("### 2.6 The 50 most popular groups, and the 40 browse groups a deckbuilder would expect\n")
    a("**Top 50 fine groups by card count** (all 50 map; %s). My quick read: 44 sensible, 5 loose (the “Firebreathing” name for the +N/+N pump; “Add colorless mana” under Mana rock includes lands; two aura pumps under “Gets +N/+N (Continuous effects)”; team pump split between Anthem and “Gets +N/+N (Pump)”), 1 wrong (“Enters tapped” under “Tap”).\n" % ", ".join("%s %d" % (k, v) for k, v in collections.Counter(g["confidence"] for g in res["top50_groups"]).items()))
    a(table([[i + 1, g["layer"], g["name"][:50].replace("|", "/"), fmt(g["cards"]), " + ".join(x[:28] for x in g["bg"]), g["bg_members"], g["basis"], g["confidence"]] for i, g in enumerate(res["top50_groups"])], ["#", "layer", "fine group", "cards", "browse group", "its size", "basis", "conf."]))
    a("")
    ex = res["expected"]
    cnt = collections.Counter(reads["expected40"][e["id"]][0] for e in ex)
    a("**The 40 expected browse groups** (list written in `src/probe_browse_checks.py` before the draft). **%d exist as one clear browse group, %d are split across 2 to 6 browse groups that are one idea, %d is effectively missing** (Blink: only an empty hand-defined group). Two of the “exist” ones need a better name or a fix: Extra turn is named “Time walk”; Mana rock contains lands.\n" % (cnt["exists"], cnt["split"], cnt["missing"]))
    a(table([[e["label"], reads["expected40"][e["id"]][0], reads["expected40"][e["id"]][1]] for e in ex], ["expected", "status", "what exists (my read)"]))
    a("\nThe split pattern is the same every time: a hand alias or tag carries the deckbuilder's word (Burn, Counterspell, Lifegain, Copy spell, Tutor), while the taxonomy node carries the parser's (Deal damage, Counter a spell, Gain life, Copy a spell, Search your library). Name-twin and alias rules do not join them because the names differ. About 25 pairs or clusters; each is one line in the mapping file once you decide.\n")

    # ---------------------------------------------------------------- 3
    a("---\n\n## 3. Popular cards\n")
    a("Top 500 cards by `edhrec_rank` (the rank in `manual_index.json`; seed for the read 20261031). All 500 have at least one fine group and therefore a browse group; they average %.2f fine groups and %.2f browse groups each.\n" % (res["top500_fine_per_card_mean"], res["top500_bg_per_card_mean"]))
    a("**Automatic check (my text patterns, not the site's data).** For each card I matched its oracle text against 40 expected-concept patterns (concepts and text patterns written before the run; the browse-group name patterns were tightened once after the first run showed false matches, such as “counter” matching “+1/+1 counters”) and asked whether the card has a browse group whose name or aliases fit the concept. %d of the 500 cards trigger at least one pattern (%d card/concept pairs). **%d of those cards (%s of the 500) miss an expected browse group** (%d pairs). By what would fix it: %s. The patterns are generous in some places and strict in others, so read this as a lead, not a score." % (res["top500_with_expected"], res["top500_expected_pairs"], res["top500_cards_missing_expected"], pct(res["top500_cards_missing_expected"], 500), res["top500_missing_pairs"], ", ".join("%s %d" % (k, v) for k, v in res["top500_fix_counts"].items())))
    a("Misses by concept: " + ", ".join("%s %d" % (k, v) for k, v in list(res["top500_missing_by_concept"].items())[:14]) + ". The biggest: draw (41, mostly cards that draw as a side effect: Mind Stone, Skullclamp, The One Ring), mana rock (23, signets and talismans whose mana is colored), protection (20), tokens (19, e.g. cards that give an opponent a token), fixing (14; dual lands in my 40-card read).\n")
    cards = json.load(open(os.path.join(P.BUILD, "browse_groups_cards_sheet.json"), encoding="utf-8"))
    miss = [i for i in range(1, 41) if reads["cards"][str(i)][2] != "ok"]
    fixc = collections.Counter(reads["cards"][str(i)][2] for i in miss)
    a("**Hand read: 40 cards, seed 20261031**, against the card text. **%d of 40 miss an expected browse group (%s)**: %s. (Plus some wrong inclusions: Demolition Field and Karplusan Forest, both lands, sit in “Mana rock”; “Enters tapped” cards sit in “Tap”.) The fix is a mapping change when the card's ability is in a group that maps to the wrong or a sibling browse group, a hand placement when no group holds the ability at all, and a new browse group only for Doubling Season (no doubler group exists).\n" % (len(miss), pct(len(miss), 40), ", ".join("%s %d" % (k, v) for k, v in fixc.items())))
    a(table([[i, reads["cards"][str(i)][0], reads["cards"][str(i)][1] or "-", reads["cards"][str(i)][2], reads["cards"][str(i)][3], " | ".join(cards[i - 1]["bg"])[:70]] for i in range(1, 41)], ["#", "card", "expected, missing", "fix", "note", "its browse groups"]))
    a("\nThe 40-card read is the real measure: 16 of 40 (40%) is a lot for the 500 most popular cards. Split by cause: 8 cards need a hand placement (an ability sits in no group at all, so the browse level cannot help; these are today's coverage gaps seen through popular cards); 7 are mapping decisions in the browse level (sibling groups: Tutor, Ramp, Artifact removal, Pillowfort, and three dual lands as Fixing); 1 needs a new browse group (doublers).\n")

    # ---------------------------------------------------------------- 4
    a("---\n\n## 4. The file, the validation, and what happens to the features (proposal only, nothing built)\n")
    a("### 4.1 `corrections/browse_groups.json`\n")
    a("```json\n{\n  \"_about\": \"Browse groups: the curated level over the fine groups. Hand-edited. ids are never reused or derived; to stop using a group set retired.\",\n  \"v\": 1,\n  \"next_id\": 312,\n  \"groups\": {\n    \"bg:b023\": {\n      \"name\": \"Spot removal\",\n      \"description\": \"Destroys or exiles one target creature or permanent.\",\n      \"aliases\": [\"removal\", \"kill spell\"],\n      \"topic\": [\"removal\"],\n      \"members\": [\n        {\"id\": \"leaf:a205bd3cf5\", \"name\": \"Destroy a creature (restriction varies)\", \"sig\": \"fam=Destroy · ftype=Destroy · obj=Creature\", \"role\": \"primary\"},\n        {\"id\": \"tag:3fb7e4fd-5304-4120-b7c4-8a89f70ad3f0\", \"name\": \"Spot removal\", \"role\": \"primary\"}\n      ],\n      \"basis\": \"alias; merged page destroy-a-creature\",\n      \"created\": \"2026-10-30\",\n      \"retired\": false\n    }\n  }\n}\n```\n")
    a("- **Ids.** `bg:` plus a short opaque slug (`b023`), taken from `next_id`, never derived from the name or the members, never reused. The draft's ids (`bg:b001` …) are provisional in size order; they freeze when you first import the file. (Readable slugs like `bg:board-wipe` are easier to read in a URL; the brief says never derive them, so I used opaque ones. Your call.) Renaming changes only `name`.")
    a("- **Topic** is the bucket id (`removal`, `draw` …) from `build/buckets/map.json`, one or two. It is a starting point for browsing, not a constraint.")
    a("- **Members** are fine-group ids with the last-seen `name` (and the leaf `sig`), so a vanished hashed id can be found again. `role` is `primary` (exactly one) or `second` (at most one).")
    a("- **Build-time validation** (an error stops the build, like the alias file): every member id exists among the offered fine groups, or resolves by the re-key rule below; a fine group is in at most two non-retired browse groups, as `primary` in exactly one; **no orphans**: every offered fine group with at least one card is a member of some non-retired browse group (a new group appearing after a rebuild is listed as an orphan, so it cannot silently vanish from the site); names are unique after case and space folding; ids are unique and an entry is never deleted (retire it); topic ids are among the 15; a browse group with no cards is allowed only when marked `empty_ok`; at most 12 aliases and no alias that is another browse group's name (warning).")
    a("- **Hashed ids that change on rebuild.** Measured now: %s of the %s fine groups have hashed ids (leaf, tentative, loose); the other %s (tag, keyword, replacement, hand) never change. Of the hashed ones, %s have a unique (layer, name) and **all 1,245 leaves have a unique signature**; all 225 tentative and loose groups have a unique name. The alias file records that about 34 of 1,273 leaf ids changed in one rebuild. So the build resolves a missing member by (1) the same layer and exact name if unique, (2) the leaf signature if unique, (3) otherwise an **error** that prints the candidates ranked by card overlap. It never repoints silently; a small `--rekey` tool (not built) would rewrite the file after you accept the printed pairs. That is the same approach as the alias file's “a rename is reported at build”." % (fmt(1470), fmt(1942), fmt(472), fmt(1436)))
    a("")
    a("### 4.2 Review sheet\n\n`build/browse_groups_review.md`: one section per browse group, sorted by topic then size, with name, description, aliases, topic, members (name, layer, size, basis/confidence), 5 sample cards (the most popular in the group), and a line of boxes to mark. Nothing is in `corrections/`.\n")
    a("### 4.3 How the site would read it, and what happens to each feature\n")
    a(table([
        ["Group search (`groupsearch.js`)", "stays, re-pointed", "Indexes browse groups (name, aliases, description) and, below the name tier, the **variants' names** (“treasure”, “plains”, “zombie” still find their browse group, shown as “matched variant: Create Treasure tokens”). Fine groups stop being rows. This is needed: otherwise hiding variants removes every narrow search. The empty-page problem goes away if empty browse groups are not indexed."],
        ["`group_aliases.json` and `group_descriptions.json`", "fold in", "Each alias id resolves to its browse group at build; later the aliases move into the browse group's own list. The fine-group descriptions stay as tooltips on the variants."],
        ["Left tree (“By family”)", "replaced", "Topic (15) → browse groups. The 28-family taxonomy tree stays reachable as a developer view only."],
        ["“Might also fit” (suggestions)", "stays at the fine level, shown at the browse level", "The suggestion engine, batch actions and hand placement still work on fine groups (placement is the precise act). A browse-group page lists suggestions for any variant, each naming the variant it would go into. Open decision: the edit panel's “place in …” picker must choose a variant."],
        ["“Narrow by group” chips", "stays, one level up", "The 15 topics stay as the first row. The second row becomes browse-group chips (counts as today, twin folding no longer needed). Variants are a third, optional row inside a browse group, **off by default**."],
        ["Merged pages (`mergepage.js`, 13 pages)", "folds in, retired", "Each page is already one browse group (rule 1). Its section-per-member display becomes the variant list. `merged_groups.json` is superseded once every page is a browse group (it is read once for the import and kept, not deleted, per its own rule)."],
        ["Twin folding in narrowing and the “+N similar groups” block", "retired for browse groups", "Redundant once twins share a browse group. The block can stay in the edit panel for fine groups."],
        ["Tentative, loose and community-tag layers and their badges", "stay as variants", "A variant keeps its “not checked” badge. A browse group shows how many of its cards come from checked variants only. The switches at the top still hide unchecked variants."],
        ["Type pages, ability-type pages, keyword facet, colour/type/MV filters, card pin, topic buckets", "unchanged", "Filters and pages, not groups; not in the mapping."],
        ["The six figures", "unchanged", "The browse level is a display layer over placements; no placement, leaf or count changes."],
    ], ["feature", "fate", "how"]))
    a("")

    # ---------------------------------------------------------------- recommendation
    a("---\n\n## 5. Recommendation\n")
    sing = res["singletons"]
    ne = res["n_nonempty"]
    mid = sum(1 for b, v in BG.items() if v["cards"] > 0 and 2 <= len(v["members"]) <= 5)
    big = sum(1 for b, v in BG.items() if v["cards"] > 0 and len(v["members"]) >= 6)
    sing_ne = sum(1 for b, v in BG.items() if v["cards"] > 0 and len(v["members"]) == 1)
    hours_lo = (sing_ne * 15 + mid * 45 + big * 150 + 40 * 120 + 100 * 30) / 3600.0
    hours_hi = (sing_ne * 30 + mid * 90 + big * 240 + 60 * 180 + 150 * 45) / 3600.0
    a("**Is the design workable?** Yes. Every fine group maps, no card loses a group, the multi-member browse groups read as sound (27/30), and the browse level fits the data: the hierarchy exists already (topic → taxonomy node → leaf) and the hand aliases are a seed list of the right concepts. Nothing in the draft says it cannot work. What it does *not* show is that a rule pass can make the curated set by itself.\n")
    a("**How many browse groups.** The rules produce %s (%s non-empty). Merging the ~25 split concepts above (roughly 40 to 60 browse groups fold into others) gives about 480 to 520. 150 to 300 is reachable only as the **tree**, not as the whole set: %s browse groups have 20 or more cards now, about 250 after the merges. My recommendation: **about 250 in the tree and main search (cards ≥ 20 or an alias/hand-picked concept), and the 200-odd smaller ones (Egg, Coin flip, rare keywords) kept as search-only “more” entries under their topic**, not folded into catch-alls: a catch-all is exactly the “Other:” parking the read marked wrong. If you want a hard 300 cap, the cost is losing niche ideas from the tree.\n" % (fmt(res["n_bg"]), fmt(ne), res["cards_ge"]["20"]))
    a("**Review effort (estimate).** Counts are measured; the minutes are my assumptions. %d single-member browse groups at 15–30 s, %d of 2–5 members at 45–90 s, %d of 6+ members at 2.5–4 min, ~40 concept merges at 2–3 min, ~100 renames and ~150 descriptions at 30–45 s each → **about %.0f to %.0f hours for a first pass**, plus a few hours of follow-up hand placements for the popular-card misses. A shorter first pass over only the %s browse groups with 20+ cards (the tree) is roughly a third of that.\n" % (sing_ne, mid, big, hours_lo, hours_hi, res["cards_ge"]["20"]))
    a("**Where you will need to make judgment calls** (I did not, and the file records each as a choice):\n")
    for t in ["Which split concepts are one idea (Burn vs Deal damage to any target; Counterspell vs Counter a spell with restrictions; Lifegain vs Gain life; Tutor vs Search your library; Reanimate vs Return from a graveyard onto the battlefield). Some are the same, some are real choices (reanimate vs regrowth; burn vs fight).",
              "Whether a very large group is one browse group or several: Create tokens (115 variants), Exile (removal vs blink), Destroy, Deal damage, “Has a keyword” / “Gains a keyword” (parser-shaped, not a deckbuilder's choice).",
              "Whether dual lands are “Fixing”, and whether “Mana rock” means any artifact that makes mana or only colorless ones (the alias currently puts lands in it).",
              "Whether keywords are browse groups (106 keyword blocks make about 50) when a keyword filter already exists; and whether a keyword pair is in two browse groups.",
              "Whether the 116 community-tag singletons (Egg, Coin flip, Utility land, Attack trigger) are browse groups, tail entries, or variants of something.",
              "Names and descriptions: about 15 of 30 names I read were slang or parser phrases. Plain names are the review's main work.",
              "What to do with hand-defined groups that have no placements (35 empty browse groups): hide until placed, or place first.",
              "Opaque or readable ids; and whether the placement picker in the edit panel chooses a variant or a browse group."]:
        a("- " + t)
    a("\n**What is measured, what is estimated, what is independent.**\n")
    a(table([
        ["Search counts, twins, ideas, layer counts, shared core names", "measured by script", "yes (the real search code and data); the 70% overlap definition is mine"],
        ["Draft sizes, confidence, bases, two-group count, unclean list, card coverage", "measured by script", "yes for the numbers; the rules and the confidence labels are my design"],
        ["30 browse groups read, 10 top-10 reads, 50 popular groups, 40 expected groups, 40 popular cards read", "my judgment", "**no**: I wrote the rules and did the reading. The sample seeds were fixed first, so the choice of what to read is not tuned, but the marks are mine"],
        ["Top-500 automatic miss count", "measured", "partly: text patterns are mine and written before the run; browse-group matching is by name and alias regexes, so it is generous in places"],
        ["Number of browse groups after merging, tree size, review hours", "estimate", "no"],
        ["Hashed-id re-key figures (1,470 hashed, 1,436 unique names, 1,245 unique signatures)", "measured", "yes"],
    ], ["what", "kind", "independent?"]))
    a("\n**What would make the next round better.** Join concepts across the alias and node sides with one extra rule (a node of ≤ 25 fine groups whose headline group is in an alias absorbs the node), which I expect to remove 15 to 20 of the 25 splits; give every alias concept a plain canonical name; stop the tag-slug root `land` from joining the “land” alias. I did not do these here because the brief asks for a probe of the rules as specified.\n")
    a("---\n\n## Files this probe wrote (all new; nothing else changed)\n")
    for f in ["src/browse_probe_data.py, src/probe_browse_clutter.py, src/probe_browse_draft.py, src/probe_browse_checks.py, src/probe_browse_report.py (the probe, read-only on every input)",
              "build/browse_groups_clutter.json, build/browse_groups_draft.json, build/browse_groups_probe_results.json, build/browse_groups_reads_sheet.json, build/browse_groups_cards_sheet.json",
              "build/browse_groups_review.md (the review sheet)", "reports/browse-groups-probe.md (this file), reports/browse-groups-reads.json (my readings)"]:
        a("- " + f)
    a("\nAppendix: the 50 searches.\n")
    a(table([[r["q"], r["results"], r["twin_results_core"], r["twin_results_overlap"], r["twin_results_strict"], r["ideas"]] for r in rows], ["search", "results", "twins (core name)", "twins (core or overlap coeff.)", "twins (core or Jaccard)", "distinct ideas"]))
    with open(OUT_REPORT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(R) + "\n")


def main():
    D = P.Data()
    draft = P.jl(os.path.join(P.BUILD, "browse_groups_draft.json"))
    res = P.jl(os.path.join(P.BUILD, "browse_groups_probe_results.json"))
    cl = P.jl(os.path.join(P.BUILD, "browse_groups_clutter.json"))
    reads = P.jl(os.path.join(P.HERE, "reports", "browse-groups-reads.json"))
    n = review(D, draft, res)
    report(D, draft, res, cl, reads)
    print("review lines", n, "->", OUT_REVIEW)
    print("report ->", OUT_REPORT)


if __name__ == "__main__":
    main()
