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
    check("the page has 'closest group' / 'also fits' suggestion links (the last bullet of the note)", sug,
          "" if sug else "the main view has none (they exist only in the archived card-level view); drop or reword that bullet")
    print("NOTE  the note says 'constructed-legal'; the build's denominator is the card set after leaving out non-cards and cards not meant for constructed play (%s cards). It is not a legality test: "
          "it still holds, for example, cards of sets that have not released yet." % format(t["in_scope"], ","))
    sys.exit(0 if all(out) else 1)


if __name__ == "__main__":
    main()
