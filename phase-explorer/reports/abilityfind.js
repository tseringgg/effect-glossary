/* "Find a card" for the per-ability view: name search over build/ability_taxonomy_lookup.json and the
 * plain-language answer for a card.
 *
 * Pure logic, no DOM, ES5 only: browse.html loads this file, and src/test_abilityfind.py runs the very
 * same file in a JS engine against the real data files. Everything a tester reads in the answer is
 * written here (plus group wording and leaf names in build/ability_taxonomy.json).
 * The archived card-level view keeps its own findcard.js.
 *
 *   var idx = AbilityFind.build(lookup);
 *   var res = AbilityFind.search(idx, "serra angel", 40);   // {total, matches:[entry...]}
 *   var ans = AbilityFind.describe(idx, entry, ctx);         // {text, kind, leaves, ...}
 *
 * An entry is [oracle_id, name, otherFaceNames[], code, extra, nFaces, tags]:
 *   l placed by its abilities (extra: [leaf id...])     b in groups broader than they look only (extra: [leaf id...])
 *   k keyword block (extra: keyword leaf id)            g replacement group (extra: replacement leaf id)
 *   v no rules text                                     u not yet organized (extra: group id)
 *   o not a card in this tool (extra: [reason, setType, set])
 */
var AbilityFind = (function () {
  function makeNorm(fold) {
    return function (s) {
      var out = "", i, c, f;
      s = String(s);
      for (i = 0; i < s.length; i++) {
        c = s.charAt(i);
        if (s.charCodeAt(i) > 127) {
          f = fold[c];
          c = f === undefined ? "" : f;
        }
        out += c;
      }
      out = out.toLowerCase().split("//").join(" ");
      out = out.replace(/[^a-z0-9 ]+/g, "").replace(/ +/g, " ");
      return out.replace(/^ /, "").replace(/ $/, "");
    };
  }

  function build(lookup) {
    var norm = makeNorm(lookup.fold), keys = [], exact = {}, i, j, names, k, nk;
    for (i = 0; i < lookup.entries.length; i++) {
      names = [lookup.entries[i][1]].concat(lookup.entries[i][2]);
      nk = [];
      for (j = 0; j < names.length; j++) {
        k = norm(names[j]);
        nk.push(k);
        if (!Object.prototype.hasOwnProperty.call(exact, k)) exact[k] = [];
        if (exact[k].indexOf(i) < 0) exact[k].push(i);
      }
      keys.push(nk);
    }
    return { lookup: lookup, norm: norm, keys: keys, exact: exact };
  }

  // Real cards before entries that are not cards; inside each half the closest name match first.
  function search(idx, query, limit) {
    var q = idx.norm(query), hits = [], seen = {}, i, j, nk, rank, ex;
    if (!q) return { total: 0, matches: [] };
    function add(n, r) {
      if (Object.prototype.hasOwnProperty.call(seen, n)) {
        if (r < hits[seen[n]].rank) hits[seen[n]].rank = r;
        return;
      }
      seen[n] = hits.length;
      hits.push({ i: n, rank: r });
    }
    ex = Object.prototype.hasOwnProperty.call(idx.exact, q) ? idx.exact[q] : [];
    for (i = 0; i < ex.length; i++) add(ex[i], 0);
    for (i = 0; i < idx.keys.length; i++) {
      nk = idx.keys[i];
      for (j = 0; j < nk.length; j++) {
        if (nk[j].indexOf(q) === 0) rank = 1;
        else if (nk[j].indexOf(" " + q) >= 0) rank = 2;
        else if (nk[j].indexOf(q) >= 0) rank = 3;
        else continue;
        add(i, rank);
      }
    }
    // "A // B": a double-faced or split card is stored under one face name, so also look up each side by its exact name (a lower rank than a
    // match on the whole string; entries that are not cards always sort after real cards)
    if (String(query).indexOf("//") >= 0) {
      var parts = String(query).split("//"), p, exs;
      for (j = 0; j < parts.length; j++) {
        p = idx.norm(parts[j]);
        if (p && Object.prototype.hasOwnProperty.call(idx.exact, p)) {
          exs = idx.exact[p];
          for (i = 0; i < exs.length; i++) add(exs[i], 4);
        }
      }
    }
    var E = idx.lookup.entries;
    hits.sort(function (a, b) {
      var ea = E[a.i], eb = E[b.i];
      var oa = ea[3] === "o" ? 1 : 0, ob = eb[3] === "o" ? 1 : 0;
      if (oa !== ob) return oa - ob;
      if (a.rank !== b.rank) return a.rank - b.rank;
      if (ea[1].length !== eb[1].length) return ea[1].length - eb[1].length;
      if (ea[1] !== eb[1]) return ea[1] < eb[1] ? -1 : 1;
      return ea[0] < eb[0] ? -1 : ea[0] > eb[0] ? 1 : 0;
    });
    var out = [];
    for (i = 0; i < hits.length && i < (limit || 40); i++) out.push(E[hits[i].i]);
    return { total: hits.length, matches: out };
  }

  function exact(idx, query) {
    var q = idx.norm(query), ex, out = [], i;
    ex = Object.prototype.hasOwnProperty.call(idx.exact, q) ? idx.exact[q] : [];
    for (i = 0; i < ex.length; i++) out.push(idx.lookup.entries[ex[i]]);
    return out;
  }

  function quoteList(ids, ctx, max) {
    var out = [], i;
    for (i = 0; i < ids.length && i < max; i++) out.push("“" + ctx.leafName(ids[i]) + "” (" + ctx.leafPath(ids[i]) + ")");
    var s = out.join("; ");
    if (ids.length > max) s += "; and " + (ids.length - max) + " more";
    return s;
  }

  /* ctx (from build/ability_taxonomy.json, supplied by the page or the test):
   *   leafName(id)  leafPath(id) -> "Family › node"   leafNote(id) -> plain note for a broad group
   *   kwLeaf(id) -> {name}   sgLeaf(id) -> {name}   sgBlock -> block name   group(id) -> {name, explain} */
  function describe(idx, entry, ctx) {
    var code = entry[3], x = entry[4], tags = entry[6] || "", res, g, n;
    res = { oid: entry[0], name: entry[1], others: entry[2], code: code,
            recovered: tags.indexOf("r") >= 0, isNew: tags.indexOf("n") >= 0,
            kind: "", text: "", leaves: [], group: null, reason: null };
    if (code === "l") {
      n = x.length;
      res.kind = "placed"; res.leaves = x;
      res.text = "Grouped by what its abilities do. It is in " + (n === 1 ? "one group: " : n + " groups: ") +
        quoteList(x, ctx, 6) + ".";
    } else if (code === "b") {
      res.kind = "broad"; res.leaves = x;
      res.text = "Only in a group broader than it looks: " + quoteList(x, ctx, 3) + ". " + ctx.leafNote(x[0]) +
        " Cards like this are not counted in the main coverage figure.";
    } else if (code === "k") {
      res.kind = "keyword"; res.leaf = x;
      res.text = "In Keyword abilities › " + ctx.kwLeaf(x).name + ". Its rules text is only keywords, so it is grouped by an exact match on them.";
    } else if (code === "g") {
      res.kind = "replacement"; res.leaf = x;
      res.text = "In " + ctx.sgBlock + " › " + ctx.sgLeaf(x).name + ". Grouped by an exact match on its replacement effect or cost.";
    } else if (code === "v") {
      res.kind = "norules";
      res.text = "In “No abilities”: this card has no rules text.";
    } else if (code === "u") {
      g = ctx.group(x);
      res.kind = "unorganized"; res.group = x;
      res.text = "Not yet organized: “" + g.name + "”. " + g.explain;
    } else {
      res.kind = "notcard"; res.reason = x[0];
      res.text = "Not a card in this tool: " + (idx.lookup.oos[x[0]] || idx.lookup.oos.unlisted) + ".";
    }
    if (res.recovered) res.text += " (Recovered card: the original data had dropped it by mistake; it was regenerated and is read like any other card.)";
    return res;
  }

  return { build: build, search: search, exact: exact, describe: describe, makeNorm: makeNorm };
})();

if (typeof module !== "undefined") module.exports = AbilityFind;
