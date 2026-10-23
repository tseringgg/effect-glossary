/* Card pin: a card result opens the card IN ITS GROUP (the card pinned at the top of the group's page) instead of the card page.
 *
 * Pure logic, no DOM, ES5 only: browse.html loads this file, and src/test_card_pin.py runs the very same file in a JS engine against the real build/manual_index.json and compares it, card by card, with a separate Python
 * implementation.
 *
 *   var p = CardPin.plan(MI, oid, env);
 *   p.open      "group" (open p.best with the card pinned) | "card" (open the card page: a pile card, or a card with no group the page can open)
 *   p.best      {gid, key, cls, name, layer, src}   the group to open
 *   p.groups    every group the card is in that the page can open now, best first (p.best is the first)
 *
 * Which group is best (the class, lower first): a precise placement (a leaf, 0; a replacement group, 0.5; a group broader than it looks, 0.7), then a tentative one (1; a sibling placement 1.2), a community-tag
 * group (2), a loose group (3), a keyword block (4), and last a group the card was placed in by hand (5). Inside a class, the card's own order (the order its groups are stored in, which follows its rules text).
 * A pile card (not yet organized) and an annotated card are not in a group: they open the card page, unless they were placed by hand. A card with no rules text is in "No abilities" (key "V:").
 * A group the page would not open now is never offered: tentative groups only while "show tentative" is on (otherwise the loose twin, if there is one), tag groups only while the tag switch is on, hand edits only while
 * "Show hand edits" is on. A group the card was removed from by hand is skipped.
 *
 * env: {tentOk(id), tagOk(id), looseHas(id), looseName(id), adds: {gid: edit}|null, removes: {gid: edit}|null}   (adds / removes are the card's hand edits when hand edits are on, else null)
 */
var CardPin = (function () {
  var CLS = { P: 0, R: 0.5, B: 0.7, T: 1, S: 1.2, M: 2, L: 3, K: 4 };
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }

  function plan(MI, oid, env) {
    var c = has(MI.cards, oid) ? MI.cards[oid] : null, out = { open: "card", best: null, groups: [], state: c ? c[1] : "" }, rows = [], seen = {}, i, g, src, cls, key, gid, id, layer, name, adds, removes, a;
    if (!c || c[1] === "o") return out;
    adds = env.adds || {}; removes = env.removes || {};
    function add(gid, cls, src) {
      var layer = gid.slice(0, gid.indexOf(":")), id = gid.slice(gid.indexOf(":") + 1), key = "", name = "";
      if (has(removes, gid)) return;
      if (layer === "leaf") { key = "l:" + id; }
      else if (layer === "rp") { key = "gl:" + id; }
      else if (layer === "kw") { key = "kl:" + gid; }
      else if (layer === "hand") { key = "hg:" + id; }
      else if (layer === "tag") { key = env.tagOk(id) ? "ct:" + id : ""; }
      else if (layer === "tent") { key = env.tentOk(id) ? "tg:" + id : (env.looseHas(id) ? "lg:" + id : ""); }
      else if (layer === "loose") { key = env.tentOk(id) ? "" : (env.looseHas(id) ? "lg:" + id : ""); }       // a promoted loose group is shown as its tentative group while that is on
      if (!key || has(seen, key)) return;
      if (has(MI.groups, gid)) name = MI.groups[gid][0]; else if (layer === "loose" || layer === "tent") name = env.looseName(id) || gid;
      if (layer === "loose" && has(MI.groups, gid) && !MI.groups[gid][4]) return;                              // a catch-all or a "less common" bucket is never opened for a card
      if (has(MI.groups, gid) && !MI.groups[gid][4]) return;                                                   // not a group the page offers
      seen[key] = 1;
      rows.push({ gid: gid, key: key, cls: cls, name: name, layer: layer, src: src, n: rows.length });
    }
    if (c[1] === "v") {
      rows.push({ gid: "none:V", key: "V:", cls: 0, name: "No abilities", layer: "none", src: "V", n: 0 });
    } else {
      for (i = 0; i < c[3].length; i++) {
        gid = c[3][i][0]; src = c[3][i][1];
        if (src === "A" || !has(CLS, src)) continue;                                                           // an annotation is a view of a group, not a membership
        if (c[1] === "u" || c[1] === "a") continue;                                                            // a pile or annotated card: only a hand placement counts
        add(gid, CLS[src], src);
      }
    }
    for (gid in adds) if (has(adds, gid)) add(gid, 5, "H");
    rows.sort(function (x, y) { return x.cls !== y.cls ? x.cls - y.cls : x.n - y.n; });
    out.groups = rows;
    if (rows.length) { out.open = "group"; out.best = rows[0]; }
    return out;
  }
  return { plan: plan, CLS: CLS };
})();

if (typeof module !== "undefined") module.exports = CardPin;
