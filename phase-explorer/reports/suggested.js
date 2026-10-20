/* Suggested cards on a group page: the pure logic. No DOM, ES5 only: browse.html loads this file and src/test_suggested_cards.py runs the very same file in a JS engine against an independent Python implementation.
 *
 *   Suggested.visible(index, res, gid, queueRows, placedRows, opts)   // opts: {floor, includePlaced, keep}  -> {rows: [{oid, row, placed}], hidden: {handled, nofit}, below: n}
 *   Suggested.lens(index, res, oidsQueue, oidsPlaced, opts)           // opts: {includePlaced, keep, skip}   -> {rows: [{oid, placed}], hidden: {handled, nofit}}
 *   Suggested.count(meta, gid, floor, includePlaced)                  // the stored count before the live hand entries are taken out
 *
 * Suggestions only: nothing here places a card. A card is hidden, live, when it has a hand entry anywhere (it is "handled"; a hand add in this very group is already in the group's "Placed here by hand" block) or is marked
 * "nothing fits". A card added from the section in this view (opts.keep) stays in place, so it can be undone. Sort: score, then popularity (lower rank first, unranked last), then name, then id.
 */
var Suggested = (function () {
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  var NONE = 1e9;
  function pop(index, oid) { var p = index.cards[oid][4]; return p == null ? NONE : p; }
  function isQueue(index, oid) { var s = index.cards[oid][1]; return s === "u" || s === "t" || s === "a" || s === "m"; }
  function stepIdx(meta, floor) {
    var i, best = 0;
    for (i = 0; i < meta.steps.length; i++) if (meta.steps[i] <= floor + 1e-9) best = i;
    return best;
  }
  function count(meta, gid, floor, includePlaced) {
    if (!has(meta.groups, gid)) return 0;
    var g = meta.groups[gid], i = stepIdx(meta, floor);
    return g[1][i] + (includePlaced ? g[2][i] : 0);
  }
  function lensCount(meta, gid, includePlaced) {
    if (!meta.lens || !has(meta.lens, gid)) return 0;
    var g = meta.lens[gid];
    return g[1] + (includePlaced ? g[2] : 0);
  }
  function entryState(res, oid, keep) {
    if (keep && has(keep, oid)) return "keep";
    if (has(res.marks, oid)) return "nofit";
    if (has(res.adds, oid)) return "handled";
    return "";
  }
  function cmpRows(index) {
    return function (a, b) {
      if (a.row[1] !== b.row[1]) return b.row[1] - a.row[1];
      var pa = pop(index, a.oid), pb = pop(index, b.oid);
      if (pa !== pb) return pa - pb;
      var na = index.cards[a.oid][0], nb = index.cards[b.oid][0];
      if (na !== nb) return na < nb ? -1 : 1;
      return a.oid < b.oid ? -1 : a.oid > b.oid ? 1 : 0;
    };
  }
  function visible(index, res, gid, queueRows, placedRows, opts) {
    var floor = opts.floor, out = [], hidden = { handled: 0, nofit: 0 }, below = 0, lists = [[queueRows || [], false]], k, i, r, st;
    if (opts.includePlaced) lists.push([placedRows || [], true]);
    for (k = 0; k < lists.length; k++) {
      for (i = 0; i < lists[k][0].length; i++) {
        r = lists[k][0][i];
        if (!has(index.cards, r[0])) continue;
        if (r[1] < floor - 1e-9) { below++; continue; }
        st = entryState(res, r[0], opts.keep);
        if (st === "nofit") { hidden.nofit++; continue; }
        if (st === "handled") { hidden.handled++; continue; }
        out.push({ oid: r[0], row: r, placed: lists[k][1] });
      }
    }
    out.sort(cmpRows(index));
    return { rows: out, hidden: hidden, below: below };
  }
  function lens(index, res, queueOids, placedOids, opts) {
    var out = [], hidden = { handled: 0, nofit: 0 }, lists = [[queueOids || [], false]], k, i, o, st;
    if (opts.includePlaced) lists.push([placedOids || [], true]);
    for (k = 0; k < lists.length; k++) {
      for (i = 0; i < lists[k][0].length; i++) {
        o = lists[k][0][i];
        if (!has(index.cards, o)) continue;
        if (opts.skip && has(opts.skip, o)) continue;
        st = entryState(res, o, opts.keep);
        if (st === "nofit") { hidden.nofit++; continue; }
        if (st === "handled") { hidden.handled++; continue; }
        out.push({ oid: o, placed: lists[k][1] });
      }
    }
    out.sort(function (a, b) {
      var pa = pop(index, a.oid), pb = pop(index, b.oid);
      if (pa !== pb) return pa - pb;
      var na = index.cards[a.oid][0], nb = index.cards[b.oid][0];
      if (na !== nb) return na < nb ? -1 : 1;
      return a.oid < b.oid ? -1 : a.oid > b.oid ? 1 : 0;
    });
    return { rows: out, hidden: hidden };
  }
  // the key the page uses for a group, back to the group id (the inverse of Manual.goKey; tentative / loose share the "lg:" page)
  function gidOfKey(key, isTentative) {
    var i = key.indexOf(":"), kind = key.slice(0, i), id = key.slice(i + 1);
    if (kind === "l") return "leaf:" + id;
    if (kind === "tg") return "tent:" + id;
    if (kind === "lg") return (isTentative ? "tent:" : "loose:") + id;
    if (kind === "ct") return "tag:" + id;
    if (kind === "kl") return id;
    if (kind === "gl") return "rp:" + id;
    if (kind === "hg") return "hand:" + id;
    return "";
  }
  return { visible: visible, lens: lens, count: count, lensCount: lensCount, stepIdx: stepIdx, gidOfKey: gidOfKey };
})();

if (typeof module !== "undefined") module.exports = Suggested;
