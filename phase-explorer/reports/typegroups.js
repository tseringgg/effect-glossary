/* Tester mode, feature TYPE_GROUPS (reports/config.js): a page for every card type, supertype and subtype that 5 or more cards have ("Card types" in the left column, and in the search box).
 * Loaded by reports/tester.js only when the flag is on, and only in tester mode. These pages are FILTERS AND PAGES, never placements: no group, no count, no figure, no suggestion changes.
 *
 * Data: build/type_groups/index.json (names, kinds, sizes: read when the "Card types" folder opens or at the first search) and build/type_groups/members.json (card indexes: read when a type page
 * opens or a subtype is chosen in the filter bar), both written by src/build_type_groups.py from the MTGJSON file. A card is on a page if ANY of its faces has the word; a card that is there only
 * through a face the page does not list says "via other face". Page keys are "ty:t.creature", "ty:s.legendary", "ty:u.saga": the word itself, so a count never moves one.
 *
 * Nothing here is sent anywhere. Search: the entries are added to the group search index at the first search (an exact name outranks every alias, so "equipment" and "siege" open the type page first).
 * Narrowing: type pages are not offered as "Narrow by group" chips (the Type and Subtype rows of the filter bar do that job).
 */
"use strict";
(function () {
  const $ = id => document.getElementById(id);
  const DOMAINS = [["creature", "Creature types"], ["spell", "Spell types"], ["artifact", "Artifact types"], ["enchantment", "Enchantment types"], ["land", "Land types"], ["planeswalker", "Planeswalker types"], ["battle", "Battle types"]];
  const DOMAIN_NAME = Object.fromEntries(DOMAINS);
  const TOP_CREATURE = 40;                                       // creature types listed in the tree before "More creature types"
  const CORE = ["Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Land", "Planeswalker", "Battle", "Kindred"];
  let DOC = null, BY = {}, PIDX = null, PMEM = null, TMEM = null, ORDER = null;
  const SETS = {}, VIA = {};
  const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

  function loadIndex() {
    if (!PIDX) PIDX = J("type_groups/index.json").then(d => {
      DOC = d; BY = {};
      for (const g of d.groups) BY[g[0]] = { key: g[0], name: g[1], kind: g[2], domain: g[3], n: g[4], al: g[5] };
      return d;
    }).catch(e => { PIDX = null; throw e; });
    return PIDX;
  }
  function fnv(oids) {                                            // the same checksum as src/build_type_groups.py: the indexes in members.json mean these cards
    let h = 2166136261, i, j, s;
    for (i = 0; i < oids.length; i++) {
      s = oids[i];
      if (i) { h ^= 10; h = Math.imul(h, 16777619) >>> 0; }
      for (j = 0; j < s.length; j++) { h ^= s.charCodeAt(j); h = Math.imul(h, 16777619) >>> 0; }
    }
    return ("00000000" + h.toString(16)).slice(-8);
  }
  function loadMembers() {
    if (!PMEM) PMEM = (async () => {
      await loadIndex(); await needCards();
      const m = await J("type_groups/members.json");
      ORDER = Object.keys(CARDS);
      if (m.sig !== DOC.sig || fnv(ORDER) !== DOC.sig) throw new Error("type_groups: members.json was built for another card list");
      TMEM = m;
      return m;
    })().catch(e => { PMEM = null; throw e; });
    return PMEM;
  }
  function setOf(key) {
    let s = SETS[key];
    if (!s) { s = SETS[key] = new Set(); for (const i of (TMEM.m[key] || [])) s.add(ORDER[i]); }
    return s;
  }
  const has = (key, oid) => !!TMEM && setOf(key).has(oid);
  const name = key => (BY[key] ? BY[key].name : key);
  const owns = k => /^ty:[tsu]\./.test(String(k));
  const domainLabel = g => g.kind === "t" ? "Types" : g.kind === "s" ? "Supertypes" : (DOMAIN_NAME[g.domain] || "Subtypes");

  // ---------------------------------------------------------------- the filter bar's "Subtype" select (testerfilters.js)
  function options(exclude) {
    const grp = (label, gs) => gs.length ? `<optgroup label="${esc(label)}">` + gs.map(g => `<option value="${esc(g.key)}">${esc(g.name)}</option>`).join("") + `</optgroup>` : "";
    const all = Object.values(BY).filter(g => !exclude.has(g.key)), byName = (a, b) => cmp(a.name.toLowerCase(), b.name.toLowerCase()) || cmp(a.name, b.name);
    let h = grp("Supertypes", all.filter(g => g.kind === "s").sort(byName));
    h += grp("Other types", all.filter(g => g.kind === "t" && CORE.indexOf(g.name) < 0).sort(byName));
    for (const [d, label] of DOMAINS) h += grp(label, all.filter(g => g.kind === "u" && g.domain === d).sort(byName));
    return h;
  }

  // ---------------------------------------------------------------- the tree: "Card types" after "By keyword"
  function isFolder(k) { return k === "TY:" || /^TYd:/.test(k) || k === "TYm:creature"; }
  function creatureOrder() {
    const cs = Object.values(BY).filter(g => g.kind === "u" && g.domain === "creature");
    const top = cs.slice().sort((a, b) => b.n - a.n || cmp(a.name, b.name)).slice(0, TOP_CREATURE);
    const topSet = new Set(top.map(g => g.key));
    return { top: top.sort((a, b) => b.n - a.n || cmp(a.name, b.name)), more: cs.filter(g => !topSet.has(g.key)).sort((a, b) => cmp(a.name.toLowerCase(), b.name.toLowerCase()) || cmp(a.name, b.name)) };
  }
  function reveal(k, open) {
    if (!owns(k)) return;
    open.add("TY:");
    const g = BY[k];
    if (g && g.kind === "u") {
      open.add("TYd:" + g.domain);
      if (g.domain === "creature" && creatureOrder().more.some(x => x.key === k)) open.add("TYm:creature");
    }
  }
  function treeRows(row, open, rerender) {
    const h = [];
    h.push(`<div class="blk">By card type</div>`);
    h.push(row("l1", "TY:", "Card types", null, { kids: true }));
    if (!open.has("TY:")) return h;
    if (!DOC) { loadIndex().then(rerender).catch(() => {}); h.push(`<div class="blk sub2">Loading…</div>`); return h; }
    h.push(`<div class="blk sub2">Filters, not placements</div>`);
    const lst = (kind) => Object.values(BY).filter(g => g.kind === kind);
    for (const g of lst("t")) h.push(row("l2", g.key, esc(g.name), g.n));
    for (const g of lst("s")) h.push(row("l2", g.key, esc(g.name), g.n));
    for (const [d, label] of DOMAINS) {
      const gs = Object.values(BY).filter(g => g.kind === "u" && g.domain === d);
      if (!gs.length) continue;
      const fk = "TYd:" + d;
      h.push(row("l2", fk, esc(label), null, { kids: true }));
      if (!open.has(fk)) continue;
      if (d === "creature") {
        const co = creatureOrder();
        for (const g of co.top) h.push(row("l3", g.key, esc(g.name), g.n));
        if (co.more.length) {
          h.push(row("l3", "TYm:creature", `More creature types (${co.more.length})`, null, { kids: true }));
          if (open.has("TYm:creature")) for (const g of co.more) h.push(row("l3", g.key, esc(g.name), g.n));
        }
      } else for (const g of gs.sort((a, b) => b.n - a.n || cmp(a.name, b.name))) h.push(row("l3", g.key, esc(g.name), g.n));
    }
    return h;
  }

  // ---------------------------------------------------------------- the page
  const byName = (a, b) => { const x = CARDS[a].n.toLowerCase(), y = CARDS[b].n.toLowerCase(); return cmp(x, y) || cmp(CARDS[a].n, CARDS[b].n) || cmp(a, b); };
  async function show(k) {
    if (typeof ALONEKEY !== "undefined" && ALONEKEY) ALONEKEY = null;
    PINNEXT = null; PINCUR = null;
    selected = k; CURCARD = null; renderTree();
    location.hash = encodeURIComponent(k);
    const P = $("panel");
    try { await loadIndex(); await needCards(); await needManual(); await loadMembers(); }
    catch (e) { P.innerHTML = `<p class="explain">The type pages could not be loaded (${esc(String(e.message || e))}).</p>`; return; }
    if (selected !== k) return;
    reveal(k, open); renderTree();                                 // the folder it sits in opens now that the index is here
    const g = BY[k];
    if (!g) { P.innerHTML = `<p class="explain">There is no such card type page.</p>`; return; }
    const via = new Set();
    const viaIdx = new Set(TMEM.o[k] || []);
    const oids = (TMEM.m[k] || []).filter(i => CARDS[ORDER[i]]).map(i => { const o = ORDER[i]; if (viaIdx.has(i)) via.add(o); return o; }).sort(byName);
    VIA.cur = k; VIA.set = via;
    const extra = `<div class="sub tgvia">On this page through its other face.</div>`;
    setList("", oids.map(o => via.has(o) ? { oid: o, extra: extra, html: cardHTML(o, null, null).replace(`<div class="det" hidden>`, extra + `<div class="det" hidden>`) } : { oid: o, extra: "", html: cardHTML(o, null, null) }));
    await scAfter(k);
  }
  function head(k) {
    const g = BY[k]; if (!g) return null;
    const o = TMEM && TMEM.o[k] ? TMEM.o[k].length : 0;
    const what = g.kind === "u" ? `Every card with ${g.name} as a subtype.` : `Every card with ${g.name} on its type line.`;
    let note = `A filter and a page, not a placement: it is in no group and changes no count. A card is here if either of its faces has ${esc(g.name)}.`;
    if (o) note += ` ${fmt(o)} ${o === 1 ? "card is" : "cards are"} here only through the other face and say${o === 1 ? "s" : ""} so.`;
    if (g.kind === "u" && g.domain === "creature" && DOC && DOC.changelings) note += ` Changelings (${fmt(DOC.changelings)}) are creatures of every type but do not say so on their type line, so they are not listed.`;
    return { name: g.name, html: `<div class="thead"><div class="crumb">Card types › ${esc(domainLabel(g))}</div><h1>${esc(g.name)}</h1><p class="tdesc">${esc(what)}</p><div class="tcnt">${fmt(g.n)} cards</div><div class="tgnote">${note}</div></div>` };
  }

  // a tile in the picture view says it too
  const _tile = tileHTML;
  tileHTML = function (x) {
    let h = _tile(x);
    if (selected && VIA.cur === selected && VIA.set && VIA.set.has(itemOid(x))) h = h.replace(`<div class="tname">`, `<div class="tvia">via other face</div><div class="tname">`).replace(`<div class="noimg"><b>`, `<div class="noimg"><div class="tvia">via other face</div><b>`);
    return h;
  };

  // ---------------------------------------------------------------- search: the type pages join the group search index when it is built
  const _gsLoad = gsLoad;
  gsLoad = async function () {
    if (GSIDX) return;
    try {
      const [doc, td] = await Promise.all([J("group_search/index.json"), loadIndex()]);
      const groups = doc.groups.slice(), aliases = Object.assign({}, doc.aliases);
      for (const g of td.groups) {
        const gid = "typepage:" + g[0].slice(3);
        groups.push([gid, g[0], g[1], "", "ty", g[4], 0, "", 0, "", ""]);
        for (const a of g[5]) if (!aliases[a]) aliases[a] = { p: a, g: [gid], fit: "", note: "", s: "hand" };
      }
      GroupSearch.LAYER_RANK.ty = 5.5;
      const idx = GroupSearch.build({ v: doc.v, groups: groups, aliases: aliases });
      for (const e of idx.entries) if (e.layer === "ty") { const g = BY[e.key]; e.desc = (g.kind === "t" ? "Card type" : g.kind === "s" ? "Supertype" : (DOMAIN_NAME[g.domain] || "Subtypes").replace(/s$/, "")) + " · a filter, not a placement"; }
      GSIDX = idx;
    } catch (err) { await _gsLoad(); }
  };

  window.TG = { enabled: true, owns: owns, isFolder: isFolder, reveal: reveal, treeRows: treeRows, show: show, head: head, loadIndex: loadIndex, loadMembers: loadMembers, ready: () => !!DOC, has: has, name: name, options: options,
    groups: () => Object.values(BY), members: k => (TMEM ? setOf(k) : new Set()), loaded: () => !!TMEM };
})();
