/* "Find a card": name search over build/lookup.json and the plain-language answer for a card.
 *
 * Pure logic, no DOM, ES5 only: browse.html loads this file, and src/test_findcard.py runs the
 * very same file in a JS engine against the real data files. Everything a tester reads in the
 * answer is written here (plus the group wording in build/unorganized.json); nothing is derived
 * from a status name. See src/build_unorganized.py.
 *
 *   var idx = FindCard.build(lookup);                       // once, after lookup.json loads
 *   var res = FindCard.search(idx, "serra angel", 40);      // {total, matches:[entry...]}
 *   var ans = FindCard.describe(idx, entry, ctx);           // {text, kind, faces, ...}
 *
 * An entry is [oracle_id, name, otherFaceNames[], code, extra, nFaces, tags]:
 *   code c clustered (extra: leaf)           p placed by closeness (extra: [leaf, similarity])
 *        k keyword rule (extra: kw leaf id)  v no-rules-text group (extra: branch name)
 *        u not yet organized (extra: group)  o not a card in this tool (extra: [reason, setType, set])
 */
var FindCard = (function () {
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

  // Real cards are listed before everything that is not a card in this tool; inside each
  // half the closest name match comes first.
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

  // Exact normalized-name matches only (any face name): O(1), used for the exhaustive check.
  function exact(idx, query) {
    var q = idx.norm(query), ex, out = [], i;
    ex = Object.prototype.hasOwnProperty.call(idx.exact, q) ? idx.exact[q] : [];
    for (i = 0; i < ex.length; i++) out.push(idx.lookup.entries[ex[i]]);
    return out;
  }

  function faceIds(entry) {
    var oid = entry[0], n = entry[5], out = [], i;
    if (entry[3] === "o") return out;
    if (n <= 1) return [oid];
    for (i = 0; i < n; i++) out.push(oid + "/" + i);
    return out;
  }

  function branchList(list) {
    return list && list.length ? " Branch" + (list.length > 1 ? "es" : "") + ": " + list.join(", ") + "." : "";
  }

  function strength(sim, words) {
    return sim >= words.close ? "close" : sim >= words.loose ? "loose" : "weak";
  }

  /* ctx (supplied by the page, or by the test from the same data files):
   *   leafLabel(leaf) -> short text      leafBranches(leaf) -> [branch names]
   *   kwLeaf(id) -> {name, branches}     group(id) -> {name, explain}
   *   words -> {close, loose}            */
  function describe(idx, entry, ctx) {
    var code = entry[3], x = entry[4], tags = entry[6] || "", res, g, lab, br, kl;
    res = { oid: entry[0], name: entry[1], others: entry[2], code: code, faces: faceIds(entry),
            recovered: tags.indexOf("r") >= 0, isNew: tags.indexOf("n") >= 0,
            kind: "", text: "", group: null, leaf: null, reason: null };
    if (code === "c") {
      lab = ctx.leafLabel(x); br = ctx.leafBranches(x);
      res.kind = "grouped"; res.leaf = x;
      res.text = "In the grouped tree: “" + lab + "” (leaf " + x + ")." + branchList(br);
    } else if (code === "p") {
      lab = ctx.leafLabel(x[0]);
      res.kind = "nearby"; res.leaf = x[0];
      res.text = "Placed by closeness, not clustered: its nearest group is “" + lab + "” (leaf " + x[0] +
        "), similarity " + x[1].toFixed(2) + ". It is shown there as “nearby”." + branchList(ctx.leafBranches(x[0]));
    } else if (code === "a") {
      lab = ctx.leafLabel(x[0]); br = ctx.leafBranches(x[0]);
      res.kind = "grouped"; res.leaf = x[0];
      res.text = "In the grouped tree: “" + lab + "” (leaf " + x[0] + "), placed through its ability “" + x[1].replace(/\.$/, "") + "”." + branchList(br);
    } else if (code === "g") {
      kl = ctx.sgLeaf(x);
      res.kind = "signature"; res.leaf = x;
      res.text = "In " + ctx.sgBlock + " › " + kl.name + ". Placed by an exact match on its replacement-effect signature, not by clustering." +
        branchList(kl.branches);
    } else if (code === "k") {
      kl = ctx.kwLeaf(x);
      res.kind = "keyword"; res.leaf = x;
      res.text = "In Keyword abilities › " + kl.name + ". Placed by an exact match on its keywords, not by clustering." +
        branchList(kl.branches);
    } else if (code === "v") {
      res.kind = "norules";
      res.text = "In “" + x + "”: this card has no rules text.";
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

  return { build: build, search: search, exact: exact, describe: describe, strength: strength, faceIds: faceIds,
           makeNorm: makeNorm };
})();

if (typeof module !== "undefined") module.exports = FindCard;
