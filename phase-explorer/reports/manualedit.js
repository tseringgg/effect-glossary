/* Hand placements: the pure logic behind the edit panel. No DOM, ES5 only: browse.html loads this file and src/test_manual_logic.py runs the very same file in a JS engine
 * and compares it with the Python resolver (src/manual_common.py) on the real data.
 *
 *   var res = Manual.resolve(index, doc);      // index = build/manual_index.json, doc = corrections/manual_placements.json
 *   Manual.search(index, "destroy artifact", 12, excludeSet);
 *   Manual.goKey("leaf:a123")                  // the page's key for opening that group
 *
 * Counting (decided with the owner): a pile card ('u') with a valid hand add leaves the pile and is "placed by hand"; a soft-placed card (t, a, m) with a valid add is "confirmed by hand" and
 * stays in its own figure; a precisely placed card's edits count nowhere; 'nothing fits' is a separate count and never a placement. Removals are recorded and shown and change no count.
 */
var Manual = (function () {
  var NOFIT = "none:fits";
  var PRECISE_SRC = "PBKR";
  var PRECISE_STATES = { p: 1, b: 1, k: 1, g: 1, v: 1 };
  var SRC_WORD = { P: "precise", B: "broad", K: "keyword", R: "replacement", T: "tentative", A: "annotation", M: "tag", L: "loose", S: "sibling" };
  var LAYER_WORD = { leaf: "leaf", tent: "tentative group", loose: "loose group", tag: "community-tag group", kw: "keyword group", rp: "replacement group", hand: "hand-defined group" };
  var STATE_WORD = { p: "placed", b: "placed (broad groups only)", k: "keyword block", g: "replacement group", v: "no abilities", t: "tentative", a: "annotation", m: "community tag", u: "not yet organized", o: "not a card" };

  function keys(o) { var k = [], x; for (x in o) if (Object.prototype.hasOwnProperty.call(o, x)) k.push(x); k.sort(); return k; }
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }

  function resolve(index, doc) {
    var cards = index.cards, groups = index.groups, edits = (doc && doc.edits) || {};
    var adds = {}, removes = {}, marks = {}, orphans = [], renamed = [], stale = [];
    var oids = keys(edits), i, j, oid, e, c, gids, gid, g, gi, act, held, k;
    for (i = 0; i < oids.length; i++) {
      oid = oids[i]; e = edits[oid]; c = has(cards, oid) ? cards[oid] : null; gids = keys(e.groups);
      for (j = 0; j < gids.length; j++) {
        gid = gids[j]; g = e.groups[gid]; act = g.action;
        if (c === null) { orphans.push({ oid: oid, group: gid, action: act }); continue; }
        if (act === "nofit") { marks[oid] = g; continue; }
        if (!has(groups, gid)) { orphans.push({ oid: oid, group: gid, action: act }); continue; }
        gi = groups[gid];
        if (g.group_name && g.group_name !== gi[0]) renamed.push({ oid: oid, group: gid, was: g.group_name, now: gi[0] });
        if (act === "add") { (adds[oid] = adds[oid] || {})[gid] = g; }
        else {
          held = false;
          for (k = 0; k < c[3].length; k++) if (c[3][k][0] === gid) held = true;
          if (!held) stale.push({ oid: oid, group: gid });
          (removes[oid] = removes[oid] || {})[gid] = g;
        }
      }
    }
    for (oid in marks) if (has(marks, oid) && has(adds, oid)) delete marks[oid];
    var n = [], conf = { t: [], a: [], m: [] }, prec = [], addOids = keys(adds);
    for (i = 0; i < addOids.length; i++) {
      oid = addOids[i]; var s = cards[oid][1];
      if (s === "u") n.push(oid); else if (s === "t" || s === "a" || s === "m") conf[s].push(oid); else if (PRECISE_STATES[s]) prec.push(oid);
    }
    var cnt = {}, st;
    for (oid in cards) if (has(cards, oid)) { st = cards[oid][1]; cnt[st] = (cnt[st] || 0) + 1; }
    var placed = 0; for (st in PRECISE_STATES) placed += cnt[st] || 0;
    var rec = { placed: placed, tentative: cnt.t || 0, annotation: cnt.a || 0, tag: cnt.m || 0, hand: n.length, unorganized: (cnt.u || 0) - n.length, not_cards: cnt.o || 0 };
    rec.sum = rec.placed + rec.tentative + rec.annotation + rec.tag + rec.hand + rec.unorganized + rec.not_cards;
    var marked = keys(marks).filter(function (o) { return cards[o][1] !== "o"; });
    var nr = 0; for (oid in removes) if (has(removes, oid)) nr += keys(removes[oid]).length;
    var na = 0; for (oid in adds) if (has(adds, oid)) na += keys(adds[oid]).length;
    return {
      counts: { placed_by_hand_new: n.length, confirmed_by_hand: conf.t.length + conf.a.length + conf.m.length,
                confirmed_by_hand_of_which: { tentative: conf.t.length, annotation: conf.a.length, tag: conf.m.length },
                precise_cards_with_edits_not_counted: prec.length, marked_nothing_fits: marked.length, removals_recorded: nr, adds: na,
                orphans: orphans.length, renamed: renamed.length, stale_removals: stale.length },
      reconciliation: rec, hand_new: n, confirmed: conf, precise_edits: prec, marked: keys(marks), orphans: orphans, renamed: renamed, stale: stale,
      adds: adds, removes: removes, marks: marks
    };
  }

  // is this card finished for the work queue: placed by hand (any valid add) or marked 'nothing fits'
  function done(res, oid) { return has(res.adds, oid) || has(res.marks, oid); }

  function norm(s) { return String(s).toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/ +/g, " ").replace(/^ /, "").replace(/ $/, ""); }

  // group search over names (and the family path); only groups offered for hand placement
  function search(index, query, limit, exclude) {
    var q = norm(query), toks = q ? q.split(" ") : [], out = [], gid, g, hay, nm, r, t, ok;
    if (!toks.length) return [];
    for (gid in index.groups) {
      if (!has(index.groups, gid)) continue;
      g = index.groups[gid];
      if (!g[4] || (exclude && has(exclude, gid))) continue;
      nm = norm(g[0]); hay = nm + " " + norm(g[2]); ok = true;
      for (t = 0; t < toks.length; t++) if (hay.indexOf(toks[t]) < 0) { ok = false; break; }
      if (!ok) continue;
      r = nm.indexOf(q) === 0 ? 0 : (" " + nm).indexOf(" " + q) >= 0 ? 1 : nm.indexOf(toks[0]) === 0 ? 2 : 3;
      out.push({ gid: gid, rank: r, name: g[0], size: g[1], path: g[2], layer: g[3] });
    }
    out.sort(function (a, b) {
      if (a.rank !== b.rank) return a.rank - b.rank;
      if (a.name.length !== b.name.length) return a.name.length - b.name.length;
      if (a.name !== b.name) return a.name < b.name ? -1 : 1;
      return a.gid < b.gid ? -1 : a.gid > b.gid ? 1 : 0;
    });
    return out.slice(0, limit || 12);
  }

  // the page's key for opening a group
  function goKey(gid) {
    var i = gid.indexOf(":"), layer = gid.slice(0, i), id = gid.slice(i + 1);
    if (layer === "leaf") return "l:" + id;
    if (layer === "tent") return "tg:" + id;
    if (layer === "loose") return "lg:" + id;
    if (layer === "tag") return "ct:" + id;
    if (layer === "kw") return "kl:" + gid;
    if (layer === "rp") return "gl:" + id;
    if (layer === "hand") return "hg:" + id;
    return "";
  }

  return { resolve: resolve, done: done, search: search, goKey: goKey, norm: norm, NOFIT: NOFIT, PRECISE_SRC: PRECISE_SRC, SRC_WORD: SRC_WORD, LAYER_WORD: LAYER_WORD, STATE_WORD: STATE_WORD };
})();

if (typeof module !== "undefined") module.exports = Manual;
