/* Tester mode, feature ABILITY_TYPE_PAGES (reports/config.js): pages for the kinds of ability a card has ("Ability types" in the left column, and in the search box): triggered abilities by
 * trigger, activated abilities by cost, static and replacement abilities by kind. Loaded by reports/tester.js only when the flag is on, and only in tester mode.
 * These pages are FILTERS AND PAGES, never placements: no group, no count, no figure, no suggestion changes.
 *
 * Data: build/ability_pages/index.json (names, kinds, sizes, aliases: read when the "Ability types" folder opens or at the first search) and one small file per page,
 * build/ability_pages/p/<page>.json (card indexes and the index of the card's own rules line for each ability: read when a page opens or when the filter bar chooses it), both written by
 * src/build_ability_pages.py. Membership is by ability: a card is on a page once for each of its abilities that the page's rule accepts, and the row shows that ability's line.
 * Page keys are "ab:trig.enters", "ab:act.sacrifice", ...: named, so a count never moves one.
 *
 * Nothing here is sent anywhere. Search: the pages are added to the group search index at the first search (existing aliases keep their groups; these pages are added to them).
 * Narrowing: ability pages are not offered as "Narrow by group" chips (the Trigger, Cost and Kind rows of the filter bar do that job, feature ABILITY_TYPE_FILTERS).
 */
"use strict";
(function () {
  const $ = id => document.getElementById(id);
  const KINDS = [["trig", "Triggered abilities"], ["act", "Activated abilities"], ["stat", "Static abilities"], ["repl", "Replacement effects"]];
  const KIND_NAME = Object.fromEntries(KINDS);
  const ROWS = [["trig", "Trigger", ["trig"]], ["cost", "Cost", ["act"]], ["kind", "Kind", ["stat", "repl"]]];
  let DOC = null, BY = {}, PIDX = null, ORDER = null;
  const PAGES = {};
  let CUR = null;                                                // the page on show: its key and the lines for the picture view
  const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

  function loadIndex() {
    if (!PIDX) PIDX = J("ability_pages/index.json").then(d => {
      DOC = d; BY = {};
      for (const g of d.groups) BY[g[0]] = { key: g[0], name: g[1], kind: g[2], n: g[3], items: g[4], partly: g[5], al: g[6], rule: g[7] };
      return d;
    }).catch(e => { PIDX = null; throw e; });
    return PIDX;
  }
  function fnv(oids) {                                            // the same checksum as src/build_ability_pages.py: the indexes in a page file mean these cards
    let h = 2166136261, i, j, s;
    for (i = 0; i < oids.length; i++) {
      s = oids[i];
      if (i) { h ^= 10; h = Math.imul(h, 16777619) >>> 0; }
      for (j = 0; j < s.length; j++) { h ^= s.charCodeAt(j); h = Math.imul(h, 16777619) >>> 0; }
    }
    return ("00000000" + h.toString(16)).slice(-8);
  }
  function loadPage(key) {
    if (!PAGES[key]) PAGES[key] = (async () => {
      await loadIndex(); await needCards();
      if (!BY[key]) throw new Error("no such ability page");
      const d = await J("ability_pages/p/" + key.slice(3) + ".json");
      if (!ORDER) ORDER = Object.keys(CARDS);
      if (d.sig !== DOC.sig || fnv(ORDER) !== DOC.sig) throw new Error("ability_pages: built for another card list");
      const oids = [], lines = new Map(), x = d.x || {};
      for (let n = 0; n < d.r.length / 2; n++) {
        const o = ORDER[d.r[2 * n]], li = d.r[2 * n + 1];
        if (!CARDS[o]) continue;
        let t = li >= 0 ? (CARDS[o].t || "").split("\n")[li] : x[String(n)];
        if (!lines.has(o)) { lines.set(o, []); oids.push(o); }
        if (t && lines.get(o).indexOf(t) < 0) lines.get(o).push(t);
      }
      return { oids: oids, lines: lines, set: new Set(oids) };
    })().catch(e => { delete PAGES[key]; throw e; });
    return PAGES[key];
  }
  const done = {};
  function remember(key) { return loadPage(key).then(p => { done[key] = p; return p; }); }
  const has = (key, oid) => !!done[key] && done[key].set.has(oid);
  const name = key => (BY[key] ? BY[key].name : key);
  const owns = k => /^ab:(trig|act|stat|repl)\./.test(String(k));

  // ---------------------------------------------------------------- the filter bar's Trigger / Cost / Kind rows (testerfilters.js, feature ABILITY_TYPE_FILTERS)
  function keysOf(row) {
    const kinds = (ROWS.find(r => r[0] === row) || [0, 0, []])[2];
    return Object.values(BY).filter(g => kinds.indexOf(g.kind) >= 0);
  }
  function options(row, exclude) {
    const grp = (label, gs) => gs.length ? `<optgroup label="${esc(label)}">` + gs.map(g => `<option value="${esc(g.key)}">${esc(g.name)}</option>`).join("") + `</optgroup>` : "";
    const all = keysOf(row).filter(g => !exclude.has(g.key));
    if (row === "kind") return grp("Static", all.filter(g => g.kind === "stat")) + grp("Replacement", all.filter(g => g.kind === "repl"));
    return all.map(g => `<option value="${esc(g.key)}">${esc(g.name)}</option>`).join("");
  }

  // ---------------------------------------------------------------- the tree: "Ability types" after "Card types"
  const isFolder = k => k === "AB:" || /^ABd:/.test(k);
  function reveal(k, open) {
    if (!owns(k)) return;
    open.add("AB:"); open.add("ABd:" + k.slice(3).split(".")[0]);
  }
  function treeRows(row, open, rerender) {
    const h = [];
    h.push(`<div class="blk">By ability type</div>`);
    h.push(row("l1", "AB:", "Ability types", null, { kids: true }));
    if (!open.has("AB:")) return h;
    if (!DOC) { loadIndex().then(rerender).catch(() => {}); h.push(`<div class="blk sub2">Loading…</div>`); return h; }
    h.push(`<div class="blk sub2">Filters, not placements</div>`);
    for (const [kind, label] of KINDS) {
      const fk = "ABd:" + kind;
      h.push(row("l2", fk, esc(label), null, { kids: true }));
      if (!open.has(fk)) continue;
      for (const g of Object.values(BY).filter(g => g.kind === kind)) h.push(row("l3", g.key, esc(g.name), g.n));
    }
    return h;
  }

  // ---------------------------------------------------------------- the page
  const byName = (a, b) => { const x = CARDS[a].n.toLowerCase(), y = CARDS[b].n.toLowerCase(); return cmp(x, y) || cmp(CARDS[a].n, CARDS[b].n) || cmp(a, b); };
  function lineHTML(lines) {
    if (!lines || !lines.length) return "";
    const shown = lines.slice(0, 3), more = lines.length - shown.length;
    return shown.map(t => `<div class="ab apline"><span class="why">${esc(t)}</span></div>`).join("") + (more > 0 ? `<div class="sub apmore">+${more} more matching abilit${more === 1 ? "y" : "ies"}</div>` : "");
  }
  async function show(k) {
    if (typeof ALONEKEY !== "undefined" && ALONEKEY) ALONEKEY = null;
    PINNEXT = null; PINCUR = null;
    selected = k; CURCARD = null; renderTree();
    location.hash = encodeURIComponent(k);
    const P = $("panel");
    let pg;
    try { await loadIndex(); await needCards(); await needManual(); pg = await remember(k); }
    catch (e) { P.innerHTML = `<p class="explain">The ability pages could not be loaded (${esc(String(e.message || e))}).</p>`; return; }
    if (selected !== k) return;
    reveal(k, open); renderTree();
    const g = BY[k];
    if (!g) { P.innerHTML = `<p class="explain">There is no such ability page.</p>`; return; }
    const oids = pg.oids.slice().sort(byName);
    CUR = { key: k, pg: pg };
    setList("", oids.map(o => ({ oid: o, html: cardHTML(o, null, null).replace(`<div class="det" hidden>`, lineHTML(pg.lines.get(o)) + `<div class="det" hidden>`) })));
    await scAfter(k);
  }
  // a tile in the picture view shows the first matching line under the name
  const _tile = tileHTML;
  tileHTML = function (x) {
    let h = _tile(x);
    if (CUR && selected === CUR.key) {
      const t = CUR.pg.lines.get(itemOid(x));
      if (t && t.length) h = h.replace(/<\/div>$/, `<div class="aptile" title="${esc(t.join(" / "))}">${esc(t[0])}</div></div>`);
    }
    return h;
  };
  function head(k) {
    const g = BY[k]; if (!g) return null;
    let note = `A filter and a page, not a placement: it is in no group and changes no count. Cards the parser couldn’t read aren’t included.`;
    if (g.partly) note += ` ${fmt(g.partly)} of the ${fmt(g.items)} abilities here are only partly read: the part that sets them apart is understood, something else in them was not.`;
    if (g.kind === "act") note += ` Keyword abilities such as Equip and cycling are not on the cost pages.`;
    const what = g.n === g.items ? "" : ` ${fmt(g.items)} abilities on ${fmt(g.n)} cards; a card with more than one is listed once, with each line.`;
    return { name: g.name, html: `<div class="thead"><div class="crumb">Ability types › ${esc(KIND_NAME[g.kind])}</div><h1>${esc(g.name)}</h1><p class="tdesc">${esc(g.rule)}${esc(what)}</p><div class="tcnt">${fmt(g.n)} cards</div><div class="tgnote">${note}</div></div>` };
  }

  // ---------------------------------------------------------------- search: the pages join the group search index when it is built
  const _gsLoad = gsLoad;
  gsLoad = async function () {
    if (GSIDX) return;
    let ai = null;
    try { ai = await loadIndex(); } catch (err) { ai = null; }
    const ob = GroupSearch.build;
    if (ai) GroupSearch.build = function (doc) {
      const groups = doc.groups.slice(), aliases = Object.assign({}, doc.aliases);
      for (const g of ai.groups) {
        const gid = "abpage:" + g[0].slice(3);
        groups.push([gid, g[0], g[1], "", "ab", g[3], 0, "", 0, "", ""]);
        for (const a of g[6]) {
          if (aliases[a]) { if (aliases[a].g.indexOf(gid) < 0) aliases[a] = Object.assign({}, aliases[a], { g: aliases[a].g.concat([gid]) }); }
          else aliases[a] = { p: a, g: [gid], fit: "", note: "", s: "hand" };
        }
      }
      GroupSearch.LAYER_RANK.ab = 5.6;
      return ob.call(GroupSearch, Object.assign({}, doc, { groups: groups, aliases: aliases }));
    };
    try { await _gsLoad(); } finally { GroupSearch.build = ob; }
    if (GSIDX && ai) for (const e of GSIDX.entries) if (e.layer === "ab" && BY[e.key]) e.desc = "Ability type · a filter, not a placement. " + BY[e.key].rule;
  };

  window.AP = { enabled: true, owns: owns, isFolder: isFolder, reveal: reveal, treeRows: treeRows, show: show, head: head, loadIndex: loadIndex, ready: () => !!DOC, has: has, name: name, options: options,
    keysOf: keysOf, loadPages: keys => Promise.all(keys.map(remember)), rows: ROWS.map(r => [r[0], r[1]]), pageOids: key => (done[key] ? done[key].oids.slice() : []), loaded: key => !!done[key] };
})();
