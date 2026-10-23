#!/usr/bin/env python3
"""Check TESTER_NOTE.md against the current build. Reads files only; changes nothing.

    python src/check_tester_note.py

Each claim of the note that can be tested is tested; a FAIL means the note (or the page) needs an edit before it goes to testers.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def main():
    note = io.open(os.path.join(HERE, "TESTER_NOTE.md"), encoding="utf-8").read()
    tax, cards, lookup = jl("ability_taxonomy.json"), jl("ability_taxonomy_cards.json")["cards"], jl("ability_taxonomy_lookup.json")
    page = io.open(os.path.join(HERE, "reports", "browse.html"), encoding="utf-8").read()
    t = tax["totals"]
    out = []

    def check(name, ok, detail=""):
        out.append(ok)
        print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (" - " + detail) if detail else ""))
    m = re.search(r"About (\d+)% of constructed-legal cards are in a group, and about (\d+)% counting the broad ones", note)
    check("the note gives the two percentages", bool(m))
    if m:
        check("the precise percentage matches the build", round(t["headline"]["pct"]) == int(m.group(1)), "note %s%%, build %s%%" % (m.group(1), t["headline"]["pct"]))
        check("the with-broad percentage matches the build", round(t["with_broad"]["pct"]) == int(m.group(2)), "note %s%%, build %s%%" % (m.group(2), t["with_broad"]["pct"]))
    check("every not-yet-organized group has an explanation (\"each one says why\")", all(g.get("explain") for g in tax["unorganized"]), "%d groups" % len(tax["unorganized"]))
    check("Find a card has a left-out answer for the excluded kinds",
          all(k in lookup["oos"] for k in ("silver_border", "acorn_stamp", "playtest_card", "joke_or_test_set", "memorabilia")))
    check("some placed cards show the part that was not read on the card page", sum(1 for c in cards.values() if c.get("g")) > 0 and "did not read part of this card" in page,
          "%d cards carry an unread part" % sum(1 for c in cards.values() if c.get("g")))
    check("some groups are marked as broader than they look", any(l["flags"] for l in tax["leaves"].values()) and "broad" in page)
    vanilla = set(tax["blocks"]["no_abilities"]["cards"])
    notext = [o for o, c in cards.items() if not c.get("t")]
    check("every card has oracle text in the data, except the no-rules-text cards", all(o in vanilla for o in notext),
          "%d cards without text, all in the 'No abilities' block" % len(notext) if all(o in vanilla for o in notext) else "%d without text and not in 'No abilities'" % sum(1 for o in notext if o not in vanilla))
    snap = tax["meta"]["rules"]["snapshot"]
    check("the snapshot predates 'since April' (cards released since are in the overlay)", "2026-04" in snap, snap[:80])
    sug = ("closest group" in page.lower()) or ("also fits" in page.lower())
    promises = ("closest group" in note.lower()) or ("also fits" in note.lower()) or ("suggestion link" in note.lower())
    check("the note promises no 'closest group' / 'also fits' suggestion links unless the page has them", (not promises) or sug,
          "the page has none (they exist only in the archived card-level view); the note's bullet was removed on 2026-10-12" if not sug else "")
    tm, am = jl("tentative_placements.json")["meta"], jl("annotation_placements.json")["meta"]
    mt = re.search(r"about ([\d,]+) cards; about (\d+)% of the card set counting them", note)
    check("the note's tentative line matches the build (cards and percentage)", bool(mt) and round(float(tm["headline"]["with_tentative"][1])) == int(mt.group(2)) and abs(int(mt.group(1).replace(",", "")) - tm["cards"]) <= 100,
          "build %s cards, %s%%" % (tm["cards"], tm["headline"]["with_tentative"][1]))
    ma = re.search(r"Condition annotations.*?about ([\d,]+) more cards.*?about (\d+)% of the card set counting them", note, re.S)
    check("the note's condition-annotation line matches the build (cards and percentage)", bool(ma) and round(float(am["headline"]["with_annotation"][1])) == int(ma.group(2)) and abs(int(ma.group(1).replace(",", "")) - am["condition_cards_new"]) <= 100,
          "build %s new cards, %s%%" % (am["condition_cards_new"], am["headline"]["with_annotation"][1]))
    tgm = jl("tag_placements.json")["meta"]
    mg = re.search(r"about ([\d,]+) of the 1,300.*?about (\d+)% of the card set", note, re.S)
    check("the note's community-tag line matches the build (cards and percentage)", bool(mg) and round(float(tgm["headline"]["with_tag"][1])) == int(mg.group(2)) and abs(int(mg.group(1).replace(",", "")) - tgm["cards"]) <= 100,
          "build %s cards, %s%%" % (tgm["cards"], tgm["headline"]["with_tag"][1]))
    check("the page has the community-tag switch, the badge and the agreed wording", all(x in page for x in ("showtag", "Show community-tag groups", "b-tag", "Not checked against the card's parsed text", "Tag snapshot")) or all(x in page for x in ("showtag", "Show community-tag groups", "b-tag", "tagSnap")))
    check("the page has the annotation switch, the badge and the agreed wording", all(x in page for x in ("showann", "Show condition annotations", "b-ann", "did not read")))
    check("the note's hand-placement line matches the page (switch, badge, own line)", "placed by hand" in note and "Show hand edits" in note and all(x in page for x in ("showhand", "Show hand edits", "b-hand", "placed by hand")))
    check("the note's keyword-facet, hand-group and sibling lines match the page (filter wording, badges, switch)", all(x in note for x in ("By keyword", "narrower than Scryfall", "hand group", "Show sibling placements")) and all(x in page for x in ("cf-kw", "By keyword", "filter, not a placement", "b-hg", "showsib", "Show sibling placements")))
    check("the note's batch-actions line matches the page (switch, batch view, review, undo, all or nothing)", all(x in note for x in ("Batch view", "Batch review", "Undo this batch", "Show batch actions", "all or nothing")) and all(x in page for x in ("showbatch", "Show batch actions", "Batch view", "breview", "Undo this batch", "Nothing is placed until you press Accept")))
    sg = io.open(os.path.join(HERE, "src", "build_suggested_cards.py"), encoding="utf-8").read()
    check("the note's possible-matches line matches the page (tab, count, wording, floor, tick) and the build script (flag, label)", all(x in note for x in ("Possible matches", "counted in no figure", "never appear on the group's own tab", "0.70", "already-placed"))
          and all(x in page for x in ("sctabs", "Possible matches (", "include already-placed cards", "b-sugg", "groupTab")) and "SUGGESTED_CARDS_VIEW = True" in sg and "Suggested cards. Not members. Not counted in any figure." in sg)
    gs = io.open(os.path.join(HERE, "src", "build_group_search.py"), encoding="utf-8").read()
    check("the note's group-search line matches the page (label, sections, labels, log line) and the build script (flag, no card text)", all(x in note for x in ("Find a card or group", "Cards and then Groups", "alias", "matched: description", "matched: family", "did you mean", "never the text of cards", "logged on this computer", "Didn't find it?", "suggested aliases", "matched: most of your words"))
          and all(x in page for x in ("Find a card or group", "matched: description", "matched: family", "did you mean", "Searches in this box are logged", "gs-jump", "groupsearch.js", "Didn’t find it?", "suggested alias", "matched: most of your words")) and "GROUP_SEARCH = True" in gs)
    cp = io.open(os.path.join(HERE, "src", "build_card_pin.py"), encoding="utf-8").read()
    check("the note's card-pin line matches the page (pinned row, chips, highlight, address) and the build script (flag)", all(x in note for x in ("You searched for this card", "Also in", "card page", "pasted link"))
          and all(x in page for x in ("You searched for this card", "pinwrap", "pinhit", "&card=", "cardpin.js")) and "CARD_PIN = True" in cp)
    mg = io.open(os.path.join(HERE, "src", "build_merged_groups.py"), encoding="utf-8").read()
    check("the note's merged-page line matches the page (badge, display figure, open on its own) and the build script (flag)", all(x in note for x in ("merged page", "display figure", "open on its own"))
          and all(x in page for x in ("merged page", "display figure", "open on its own", "mergepage.js")) and "MERGED_GROUPS = True" in mg)
    print("NOTE  the note says 'constructed-legal'; the build's denominator is the card set after leaving out non-cards and cards not meant for constructed play (%s cards). It is not a legality test: "
          "it still holds, for example, cards of sets that have not released yet." % format(t["in_scope"], ","))
    sys.exit(0 if all(out) else 1)


if __name__ == "__main__":
    main()
