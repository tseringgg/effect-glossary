/* Group search for the main search box: names, aliases and short descriptions of GROUPS (never the text of cards).
 *
 * Pure logic, no DOM, ES5 only: browse.html loads this file, and src/test_group_search.py runs the very same file in a JS engine against the real build/group_search/index.json.
 *
 *   var idx = GroupSearch.build(doc);                                   // doc = build/group_search/index.json
 *   var r = GroupSearch.search(idx, "board wipe", {allow: fn, words: obj|null});
 *     r.groups   [{e, key, tier, why, via, fit, note, dym}]            ranked; name and alias matches first, then description matches
 *     r.family   same shape, groups that matched only by their family/kind (the page collapses them under one row)
 *     r.dym      null, or {from, to}: the query was corrected ("did you mean")
 *     r.needWords true when a typed word could not be judged without the real-word list: load words.txt, then search again with {words: ...}
 *
 * Ranking. Tiers (lower is better): 0 exact name . 1 exact HAND alias (in the alias file's order) . 2 name starts with the query . 3 every query word is a word of the name . 3.5 all but one of 3 or more query
 * words are words of the name ("most words") . 4 partial hand alias, or a tag's own slug . 4.5 a DRAFTED alias, only when its exact words are typed (flagged "suggested alias", below every name match and every hand alias)
 * . 5 description. Family/kind matches are listed apart (tier 6). Inside a tier: log10(size + 1) minus 0.3 for an auto-generated name, then checked layers before unchecked ones, then name.
 * A typed word that is a real word (the word list), or a word/prefix of our own group vocabulary, is taken literally and never corrected. Only a word in neither, with fewer than 3 name/alias matches, is corrected.
 *
 * An entry is [gid, key, name, path, layer, size, auto, description, description_is_draft, twin_key, slug]; layer: l leaf, k keyword block, r replacement block, t tentative, o loose, c community tag, h hand group, y keyword filter,
 * m a MERGED PAGE (src/build_merged_groups.py: display-only; its row has two more columns: the other names the page answers to, i.e. its members' names and its aliases, and its members' ids; its key is its first member's key).
 */
var GroupSearch = (function () {
  var STOP = {}, LAYER_RANK = { l: 0, k: 1, r: 1, m: 1, t: 2, o: 3, c: 4, h: 5, y: 6 }, i;
  var stops = "a an the of to and or for in on at by with from your you it its that this is are be as".split(" ");
  for (i = 0; i < stops.length; i++) STOP[stops[i]] = 1;
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }

  function norm(s) {
    s = String(s).toLowerCase().replace(/['’]/g, "").replace(/[^a-z0-9]+/g, " ");
    return s.replace(/^ +/, "").replace(/ +$/, "");
  }
  function stem(w) {
    var n = w.length;
    if (n > 4 && /ies$/.test(w)) return w.slice(0, -3) + "y";
    if (n > 4 && /(ss|x|z|ch|sh)es$/.test(w)) return w.slice(0, -2);
    if (n > 3 && /s$/.test(w) && !/(ss|us|is)$/.test(w)) return w.slice(0, -1);
    return w;
  }
  // a typed word: its stem, and the stem without -ing / -ed ("sacrificing", "destroyed")
  function variants(w) {
    var s = stem(w), v = [s];
    if (s.length > 5 && /ing$/.test(s)) v.push(s.slice(0, -3));
    else if (s.length > 4 && /ed$/.test(s)) v.push(s.slice(0, -2));
    return v;
  }
  function stems(str) {
    var t = norm(str), out = [], k;
    if (!t) return out;
    t = t.split(" ");
    for (k = 0; k < t.length; k++) out.push(stem(t[k]));
    return out;
  }
  function tokMatch(vs, w, prefix) {
    var k;
    for (k = 0; k < vs.length; k++) {
      if (w === vs[k]) return true;
      if (prefix && vs[k].length >= 3 && w.indexOf(vs[k]) === 0) return true;
    }
    return false;
  }
  // every token (a variants array) matches some word of ws
  function allMatch(ws, qv, exactOnly) {
    var a, b, ok;
    if (!ws.length || !qv.length) return false;
    for (a = 0; a < qv.length; a++) {
      ok = false;
      for (b = 0; b < ws.length; b++) if (tokMatch(qv[a], ws[b], !exactOnly)) { ok = true; break; }
      if (!ok) return false;
    }
    return true;
  }
  // the words of ws start with the tokens, in order: all but the last exactly, the last as a prefix
  function startsWith(ws, qv) {
    var a;
    if (ws.length < qv.length) return false;
    for (a = 0; a < qv.length; a++) if (!tokMatch(qv[a], ws[a], a === qv.length - 1)) return false;
    return true;
  }
  function dl(a, b, k) {                               // optimal string alignment distance (a transposition counts 1); k+1 when it exceeds k
    var la = a.length, lb = b.length, d = [], x, y, c, best;
    if (Math.abs(la - lb) > k) return k + 1;
    for (x = 0; x <= la; x++) { d.push([]); for (y = 0; y <= lb; y++) d[x].push(0); }
    for (x = 0; x <= la; x++) d[x][0] = x;
    for (y = 0; y <= lb; y++) d[0][y] = y;
    for (x = 1; x <= la; x++) {
      best = k + 1;
      for (y = 1; y <= lb; y++) {
        c = a.charAt(x - 1) === b.charAt(y - 1) ? 0 : 1;
        d[x][y] = Math.min(d[x - 1][y] + 1, d[x][y - 1] + 1, d[x - 1][y - 1] + c);
        if (x > 1 && y > 1 && a.charAt(x - 1) === b.charAt(y - 2) && a.charAt(x - 2) === b.charAt(y - 1)) d[x][y] = Math.min(d[x][y], d[x - 2][y - 2] + 1);
        if (d[x][y] < best) best = d[x][y];
      }
      if (best > k) return k + 1;
    }
    return d[la][lb];
  }
  function r6(x) { return Math.round(x * 1000000) / 1000000; }

  function build(doc) {
    var idx = { entries: [], byGid: {}, aliases: [], aliasByKey: {}, gw: {}, gwList: [], gwCount: {} }, g, e, a, k, p, words, w, ph;
    function addWords(str) {
      var t = norm(str), parts, q;
      if (!t) return;
      parts = t.split(" ");
      for (q = 0; q < parts.length; q++) {
        w = parts[q];
        if (w.length < 3) continue;
        idx.gw[stem(w)] = 1;
        if (!has(idx.gwCount, w)) { idx.gwCount[w] = 0; idx.gwList.push(w); }
        idx.gwCount[w]++;
      }
    }
    for (k = 0; k < doc.groups.length; k++) {
      g = doc.groups[k];
      e = { i: k, gid: g[0], key: g[1], name: g[2], path: g[3], layer: g[4], size: g[5], auto: g[6], desc: g[7], descDraft: g[8], twin: g[9], slug: g[10] };
      e.ns = stems(e.name); e.nkey = e.ns.join(" ");
      e.extras = g[11] || []; e.members = g[12] || [];
      e.vars = [{ ns: e.ns, nkey: e.nkey, ckey: "" }];                            // the names the entry answers to: its own and (a merged page) its members' names and aliases
      e.ckey = stems(e.name.replace(/ \u2014 .*$/, "").replace(/ \([^)]*\)/g, "")).join(" ");          // the name without its qualifiers ("— who draws isn't recorded", "(restriction varies)")
      e.vars[0].ckey = e.ckey;
      for (p = 0; p < e.extras.length; p++) {
        words = stems(e.extras[p]);
        e.vars.push({ ns: words, nkey: words.join(" "), ckey: stems(e.extras[p].replace(/ — .*$/, "").replace(/ \([^)]*\)/g, "")).join(" ") });
      }
      e.alts = e.slug ? stems(e.slug) : []; e.altkey = e.alts.join(" ");
      e.ps = stems(e.path);
      words = stems(e.desc); e.ds = [];
      for (p = 0; p < words.length; p++) if (!STOP[words[p]] && words[p].length >= 2) e.ds.push(words[p]);
      e.score = r6(Math.log(e.size + 1) / Math.LN10 - (e.auto ? 0.3 : 0));
      idx.entries.push(e);
      idx.byGid[e.gid] = e;
      addWords(e.name); addWords(e.slug);
    }
    for (ph in doc.aliases) {
      if (!has(doc.aliases, ph)) continue;
      a = doc.aliases[ph];
      a = { k: ph, p: a.p, stems: stems(a.p), gids: a.g, fit: a.fit, note: a.note, s: a.s || "hand" };
      a.key = a.stems.join(" ");
      idx.aliases.push(a);
      idx.aliasByKey[a.key] = a;
      addWords(a.p);
    }
    idx.gwList.sort();
    return idx;
  }

  function cmp(a, b) {
    if (a.tier !== b.tier) return a.tier - b.tier;
    if (a.tier === 1 && a.order !== b.order) return a.order - b.order;
    if (a.e.score !== b.e.score) return b.e.score - a.e.score;
    if (LAYER_RANK[a.e.layer] !== LAYER_RANK[b.e.layer]) return LAYER_RANK[a.e.layer] - LAYER_RANK[b.e.layer];
    if (a.e.name !== b.e.name) return a.e.name < b.e.name ? -1 : 1;
    return a.e.gid < b.e.gid ? -1 : a.e.gid > b.e.gid ? 1 : 0;
  }

  // the literal search for a list of folded tokens
  function literal(idx, toks, allow) {
    var qstems = [], qall = [], core = [], qcore = [], best = {}, fam = {}, k, e, a, g, n, t, key, gid, cand, out = [], famOut = [];
    for (k = 0; k < toks.length; k++) { qstems.push(stem(toks[k])); qall.push(variants(toks[k])); if (!STOP[toks[k]]) { core.push(toks[k]); qcore.push(variants(toks[k])); } }
    if (!core.length) { core = toks; qcore = qall; }
    var qkey = qstems.join(" ");
    function offer(en, tier, why, via, order, fit, note, drafted) {
      var cur = best[en.gid];
      if (!cur || tier < cur.tier || (tier === cur.tier && tier === 1 && order < cur.order)) best[en.gid] = { e: en, tier: tier, why: why, via: via || "", order: order || 0, fit: fit || "", note: note || "", drafted: !!drafted };
    }
    if (has(idx.aliasByKey, qkey)) {
      a = idx.aliasByKey[qkey];
      for (n = 0; n < a.gids.length; n++) if (has(idx.byGid, a.gids[n])) offer(idx.byGid[a.gids[n]], a.s === "drafted" ? 4.5 : 1, "alias", a.p, n, a.fit, a.note, a.s === "drafted");
    }
    for (k = 0; k < idx.entries.length; k++) {
      e = idx.entries[k];
      if (anyVar(e, function (v) { return v.nkey === qkey || v.ckey === qkey; })) offer(e, 0, "name");
      else if (e.altkey && e.altkey === qkey) offer(e, 1, "slug", "", 50);
      else if (anyVar(e, function (v) { return startsWith(v.ns, qall); })) offer(e, 2, "name");
      else if (anyVar(e, function (v) { return allMatch(v.ns, qcore); })) offer(e, 3, "name");
      else if (core.length >= 3 && anyVar(e, function (v) { return countMatch(v.ns, qcore) >= core.length - 1; })) offer(e, 3.5, "most");
      else if (e.alts.length && allMatch(e.alts, qcore)) offer(e, 4, "slug");
      else if (e.ds.length && allMatch(e.ds, qcore, true) && maxLen(core) >= 3) offer(e, 5, "description");
      else if (allMatch(e.ps, qcore)) fam[e.gid] = { e: e, tier: 6, why: "family", via: "", order: 0, fit: "", note: "" };
    }
    for (k = 0; k < idx.aliases.length; k++) {
      a = idx.aliases[k];
      if (a.key !== qkey && a.s !== "drafted" && allMatch(a.stems, qcore)) {          // a drafted alias answers only to its exact words ("hate counterspell" must not answer "counterspell")
        for (n = 0; n < a.gids.length; n++) if (has(idx.byGid, a.gids[n])) offer(idx.byGid[a.gids[n]], 4, "alias", a.p, 0, a.fit, a.note, false);
      }
    }
    for (gid in best) if (has(best, gid)) {
      cand = best[gid];
      key = allow ? allow(cand.e) : cand.e.key;
      if (key) { cand.key = key; out.push(cand); }
    }
    for (gid in fam) if (has(fam, gid) && !has(best, gid)) {
      cand = fam[gid];
      key = allow ? allow(cand.e) : cand.e.key;
      if (key) { cand.key = key; famOut.push(cand); }
    }
    out.sort(cmp); famOut.sort(cmp);
    return { groups: out, family: famOut };
  }
  function countMatch(ws, qv) {
    var a, b, n = 0;
    for (a = 0; a < qv.length; a++) {
      for (b = 0; b < ws.length; b++) if (tokMatch(qv[a], ws[b], true)) { n++; break; }
    }
    return n;
  }
  function anyVar(e, fn) { var i; for (i = 0; i < e.vars.length; i++) if (fn(e.vars[i])) return true; return false; }
  function maxLen(a) { var m = 0, k; for (k = 0; k < a.length; k++) if (a[k].length > m) m = a[k].length; return m; }

  // is the word one of ours (a stem of a group word) or the start of one?
  function known(idx, t) {
    var vs = variants(t), k, w;
    for (k = 0; k < vs.length; k++) if (has(idx.gw, vs[k])) return true;
    if (t.length >= 3) for (k = 0; k < idx.gwList.length; k++) { w = idx.gwList[k]; if (w.indexOf(t) === 0) return true; }
    return false;
  }
  function real(words, t) {
    var vs = variants(t), k;
    if (has(words, t)) return true;
    for (k = 0; k < vs.length; k++) if (has(words, vs[k])) return true;
    return false;
  }
  function nearest(idx, t) {
    var kmax = t.length <= 7 ? 1 : 2, best = null, bd = 99, k, w, d, c0 = t.charAt(0), c1 = t.charAt(1);
    for (k = 0; k < idx.gwList.length; k++) {
      w = idx.gwList[k];
      if (Math.abs(w.length - t.length) > kmax) continue;
      if (w.charAt(0) !== c0 && !(w.charAt(0) === c1 && w.charAt(1) === c0)) continue;
      d = dl(t, w, kmax);
      if (d > kmax) continue;
      if (d < bd || (d === bd && idx.gwCount[w] > idx.gwCount[best])) { best = w; bd = d; }
    }
    return best;
  }

  function search(idx, query, opts) {
    opts = opts || {};
    var q = norm(query), toks, r, out, nName = 0, k, t, need = false, changed = false, corrected, best, r2, seen = {}, extra = [];
    out = { query: q, groups: [], family: [], dym: null, needWords: false, nameCount: 0 };
    if (q.length < 2) return out;
    toks = q.split(" ");
    r = literal(idx, toks, opts.allow);
    for (k = 0; k < r.groups.length; k++) if (r.groups[k].tier <= 4.5) nName++;
    out.groups = r.groups; out.family = r.family; out.nameCount = nName;
    if (nName < 3) {
      corrected = toks.slice();
      for (k = 0; k < toks.length; k++) {
        t = toks[k];
        if (t.length < 4 || STOP[t] || /[0-9]/.test(t) || known(idx, t)) continue;
        if (!opts.words) { need = true; continue; }
        if (real(opts.words, t)) continue;
        best = nearest(idx, t);
        if (best) { corrected[k] = best; changed = true; }
      }
      out.needWords = need && !opts.words;
      if (changed) {
        r2 = literal(idx, corrected, opts.allow);
        for (k = 0; k < r.groups.length; k++) seen[r.groups[k].e.gid] = 1;
        for (k = 0; k < r2.groups.length; k++) {
          if (r2.groups[k].tier <= 4.5 && !has(seen, r2.groups[k].e.gid)) { r2.groups[k].dym = corrected.join(" "); extra.push(r2.groups[k]); }
        }
        if (extra.length) {
          out.groups = r.groups.concat(extra);
          out.dym = { from: q, to: corrected.join(" ") };
          out.family = r.family;
        }
      }
    }
    return out;
  }

  return { build: build, search: search, norm: norm, stem: stem, variants: variants, dl: dl, known: known, real: real, nearest: nearest, LAYER_RANK: LAYER_RANK };
})();

if (typeof module !== "undefined") module.exports = GroupSearch;
