/* Merged group pages: the one piece of logic that decides which card is shown where. Pure, no DOM, ES5: browse.html loads this file and src/test_merged_groups.py runs the very same file in a JS engine and compares it with an
 * independent Python version.
 *
 *   var lay = MergePage.layout([{gid, oids: [oid...], removed: {oid: 1}}, ...]);      // sections in trust order (precise, tentative, tag, loose, also here)
 *   lay.sections[i].show     the oids to show in section i, in their order: a card is shown ONCE, in the highest-trust section that holds it
 *   lay.sections[i].hidden   how many of the section's cards are shown in a section above (the page says "k also shown above")
 *   lay.also[oid]            the gids of the LATER sections that also hold the card (the "also in" mark on the card where it is shown)
 *   lay.where[oid]           the gid of the section where the card is shown
 *   lay.union                the number of different cards shown: a DISPLAY figure (a card in two groups counted once); no group's own count changes
 * A card removed by hand from a section keeps its struck-through row in that section and is neither hidden by nor hides another section's row.
 */
var MergePage = (function () {
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  function layout(sections) {
    var out = { sections: [], also: {}, where: {}, union: 0 }, i, j, s, oid, sec, seen;
    for (i = 0; i < sections.length; i++) {
      s = sections[i]; sec = { gid: s.gid, show: [], hidden: 0 }; seen = {};
      for (j = 0; j < s.oids.length; j++) {
        oid = s.oids[j];
        if (has(seen, oid)) continue;                         // a card listed twice in one section is one card
        seen[oid] = 1;
        if (s.removed && has(s.removed, oid)) { sec.show.push(oid); continue; }
        if (has(out.where, oid)) {
          sec.hidden++;
          (out.also[oid] = out.also[oid] || []).push(s.gid);
          continue;
        }
        out.where[oid] = s.gid; out.union++;
        sec.show.push(oid);
      }
      out.sections.push(sec);
    }
    return out;
  }
  return { layout: layout };
})();

if (typeof module !== "undefined") module.exports = MergePage;
