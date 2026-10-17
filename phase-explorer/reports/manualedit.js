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
    var batchOn = !!index.batch, isb = function (o) { var g, any = true; for (g in adds[o]) if (has(adds[o], g) && !adds[o][g].batch) any = false; return any; };
    var nr = 0; for (oid in removes) if (has(removes, oid)) nr += keys(removes[oid]).length;
    var na = 0; for (oid in adds) if (has(adds, oid)) na += keys(adds[oid]).length;
    var bx = {};
    if (batchOn) {
      var pb = 0, cb = 0, brm = 0, nb = 0, nu = 0, t, g2, bk;
      for (i = 0; i < n.length; i++) if (isb(n[i])) pb++;
      for (t in conf) if (has(conf, t)) for (i = 0; i < conf[t].length; i++) if (isb(conf[t][i])) cb++;
      for (oid in removes) if (has(removes, oid)) for (g2 in removes[oid]) if (has(removes[oid], g2) && removes[oid][g2].batch) brm++;
      for (bk in (doc && doc.batches) || {}) if (has(doc.batches, bk)) { nb++; if (doc.batches[bk].undone) nu++; }
      bx = { placed_by_hand_batch: pb, confirmed_by_hand_batch: cb, batch_removals: brm, batches: nb, batches_undone: nu };
    }
    var cnts = {
      counts: { placed_by_hand_new: n.length, confirmed_by_hand: conf.t.length + conf.a.length + conf.m.length,
                confirmed_by_hand_of_which: { tentative: conf.t.length, annotation: conf.a.length, tag: conf.m.length },
                precise_cards_with_edits_not_counted: prec.length, marked_nothing_fits: marked.length, removals_recorded: nr, adds: na,
                orphans: orphans.length, renamed: renamed.length, stale_removals: stale.length },
      reconciliation: rec, hand_new: n, confirmed: conf, precise_edits: prec, marked: keys(marks), orphans: orphans, renamed: renamed, stale: stale,
      adds: adds, removes: removes, marks: marks
    };
    for (var bkk in bx) if (has(bx, bkk)) cnts.counts[bkk] = bx[bkk];
    return cnts;
  }

  // ------------------------------------------------------------ the batch view (pure logic; the page only draws it)
  // saga boilerplate: true of every Saga and says nothing about the card, so a batch never offers it as the card's home
  function isBoilerplate(row, name) {
    return /“(?:Saga ETB lore counter|Chapter \d+)”/.test(row[3] || "") || name === "Put lore counters on this permanent";
  }
  // text suggestions (build/text_sug, TEXT_SUGGESTIONS): a row whose every source is "text" or "kw" is low confidence and is never ticked for you, whatever its score
  function isTextOnly(src) {
    var p = String(src).split("+"), i;
    for (i = 0; i < p.length; i++) if (p[i] !== "text" && p[i] !== "kw") return false;
    return p.length > 0 && p[0] !== "";
  }
  // a row led only by text, keyword name or a hand-group rule is never ticked for you, whatever its score: none of them was part of what the 0.90 threshold was checked on
  function neverTick(src) {
    var p = String(src).split("+"), i;
    for (i = 0; i < p.length; i++) if (p[i] !== "text" && p[i] !== "kw" && p[i] !== "rule") return false;
    return p.length > 0 && p[0] !== "";
  }
  // ENGINE_V2 near-duplicate groups: names with the same words (token overlap of at least 0.7, parentheses and anything after a dash left out) share one row in the panel.
  // First fit, in row order; the same function is in src/build_text_suggestions.py (cluster_rows) and a test compares them on every queue card.
  var STOPN = { a: 1, an: 1, the: 1, of: 1, to: 1, or: 1, and: 1, it: 1, its: 1, "this": 1, "that": 1, his: 1, her: 1, their: 1, "from": 1, "in": 1, on: 1, "for": 1, "with": 1, you: 1, your: 1 };
  function nameKey(name) {
    var n = String(name).toLowerCase().replace(/\(.*?\)/g, "").replace(/\u2014.*$/, "").replace(/[^a-z0-9\/ +\-]/g, " "), t = n.split(/\s+/), k = {}, c = 0, i;
    for (i = 0; i < t.length; i++) if (t[i] && !has(STOPN, t[i]) && !has(k, t[i])) { k[t[i]] = 1; c++; }
    return { k: k, n: c };
  }
  function nearKeys(a, b) {
    var inter = 0, x;
    if (!a.n || !b.n) return false;
    for (x in a.k) if (has(a.k, x) && has(b.k, x)) inter++;
    return inter / (a.n + b.n - inter) >= 0.7;
  }
  function clusterRows(index, rows) {
    var cl = [], keys = [], i, j, k, hit;
    for (i = 0; i < rows.length; i++) {
      k = nameKey(index.groups[rows[i][0]][0]); hit = -1;
      for (j = 0; j < cl.length; j++) if (nearKeys(k, keys[j])) { hit = j; break; }
      if (hit < 0) { cl.push([rows[i]]); keys.push(k); } else cl[hit].push(rows[i]);
    }
    return cl;
  }
  // the usable suggestions of one card: not already added by hand, not held precisely, not boilerplate (when asked)
  function usableSuggestions(index, sugg, res, oid, skip) {
    var rows = (sugg && sugg[oid]) || [], out = [], i, r, c = index.cards[oid], j, held, adds = (res.adds && res.adds[oid]) || {};
    for (i = 0; i < rows.length && out.length < 5; i++) {
      r = rows[i];
      if (!has(index.groups, r[0]) || has(adds, r[0])) continue;
      held = false;
      for (j = 0; j < c[3].length; j++) if (c[3][j][0] === r[0] && PRECISE_SRC.indexOf(c[3][j][1]) >= 0) held = true;
      if (held || (skip && isBoilerplate(r, index.groups[r[0]][0]))) continue;
      out.push(r);
    }
    return out;
  }
  // order = oracle ids in queue order. -> {rows: [{oid, items, tier: 'tick'|'review'}], handled: [{oid, items, what}], nosug: [oid], below: n}
  // a row is 'tick' when its top suggestion scores at least `thr` and 'review' (shown unticked) between `floor` and `thr`; a card with any hand entry is never a row, only `handled`.
  function batchRows(index, sugg, res, order, thr, skip, floor) {
    floor = floor == null ? 0.70 : floor;
    var rows = [], handled = [], nosug = [], below = 0, i, oid, list, has_ = function (o) { return has(res.adds, o) || has(res.removes, o) || has(res.marks, o); }, what;
    for (i = 0; i < order.length; i++) {
      oid = order[i];
      if (!has(index.cards, oid) || index.cards[oid][1] === "o") continue;
      list = usableSuggestions(index, sugg, res, oid, skip);
      if (has_(oid)) {
        what = [];
        if (has(res.adds, oid)) what.push(keys(res.adds[oid]).length + " hand add" + (keys(res.adds[oid]).length > 1 ? "s" : ""));
        if (has(res.removes, oid)) what.push("a removal");
        if (has(res.marks, oid)) what.push("marked nothing fits");
        handled.push({ oid: oid, items: list, what: what.join(", ") });
      } else if (!list.length) nosug.push(oid);
      else if (list[0][1] >= thr - 1e-9 && !neverTick(list[0][2])) rows.push({ oid: oid, items: list, tier: "tick" });
      else if (list[0][1] >= floor - 1e-9) rows.push({ oid: oid, items: list, tier: "review" });
      else below++;
    }
    return { rows: rows, handled: handled, nosug: nosug, below: below };
  }
  // a batch id the server accepts: b-YYYYMMDD-HHMMSS-xxxx
  function newBatchId(d, rnd) {
    function p(n, w) { n = String(n); while (n.length < w) n = "0" + n; return n; }
    var r = "", al = "abcdefghijklmnopqrstuvwxyz0123456789", i;
    for (i = 0; i < 4; i++) r += al.charAt(Math.floor(rnd() * 36));
    return "b-" + d.getFullYear() + p(d.getMonth() + 1, 2) + p(d.getDate(), 2) + "-" + p(d.getHours(), 2) + p(d.getMinutes(), 2) + p(d.getSeconds(), 2) + "-" + r;
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

  return { resolve: resolve, done: done, isBoilerplate: isBoilerplate, isTextOnly: isTextOnly, neverTick: neverTick, clusterRows: clusterRows, usableSuggestions: usableSuggestions, batchRows: batchRows, newBatchId: newBatchId, search: search, goKey: goKey, norm: norm, NOFIT: NOFIT, PRECISE_SRC: PRECISE_SRC, SRC_WORD: SRC_WORD, LAYER_WORD: LAYER_WORD, STATE_WORD: STATE_WORD };
})();

if (typeof module !== "undefined") module.exports = Manual;
