/* Tester mode, feature TESTER_FILTERS (reports/config.js): a filter and sort bar on group pages (colour, type, mana value, sort) and a "Narrow by group" row.
 * Loaded by reports/tester.js only when the flag is on, and only in tester mode. Presentation only: it reads facts the page already holds (CARDS: name, type line, colour, mana value) and the group
 * memberships the group pages themselves list (members, sibling, tentative, loose, tag, keyword and replacement files, hand placements), and changes no group, id, placement, suggestion or figure.
 * Nothing is fetched: every number is computed in the page.
 *
 * Rules (src/test_tester_static.py re-derives them in Python and compares):
 *   filter: AND across kinds (colour, type, mana value), OR inside a kind. Colour is the card's colour, not its colour identity. Facts are those of the face the page lists (a split card: its first half).
 *   mana value: 0..5, 6+, and "No cost / unknown" (none recorded: lands, free spells the data cannot tell from no cost, some back faces). X counts as 0.
 *   narrowing: a chip is a group (offered in the edit index) with at least 3 of the list's cards, fewer than 90% of them; not one of the page's own groups; not a near-twin of the page (name words with
 *   Jaccard >= 0.7, or card sets with Jaccard >= 0.8), not a near-twin of a chip already kept; the member groups of a merged page are one chip (its union). Counts are recomputed on the filtered list.
 */
"use strict";
(function () {
  const $ = id => document.getElementById(id);
  const TYPES = ["Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Land", "Planeswalker", "Battle", "Kindred"];
  const COLS = [["W", "White"], ["U", "Blue"], ["B", "Black"], ["R", "Red"], ["G", "Green"], ["C", "Colourless"], ["M", "Multicolour"]];
  const MVS = [["0", "0"], ["1", "1"], ["2", "2"], ["3", "3"], ["4", "4"], ["5", "5"], ["6+", "6+"], ["none", "No cost / unknown"]];
  const STOPN = new Set("a an the of to or and it its this that his her their from in on for with you your".split(" "));
  const nameKey = n => new Set(String(n).toLowerCase().replace(/\(.*?\)/g, "").replace(/—.*$/, "").replace(/[^a-z0-9\/ +\-]/g, " ").split(/\s+/).filter(t => t && !STOPN.has(t)));
  const clean = n => String(n).replace(/\s*\(.*?\)/g, "").replace(/\s*—.*$/, "").trim();
  const jac = (a, b) => { if (!a.size || !b.size) return 0; let i = 0; for (const x of a) if (b.has(x)) i++; return i / (a.size + b.size - i); };
  const mobile = () => window.matchMedia("(max-width: 800px)").matches;
  const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

  // ---------------------------------------------------------------- facts (from CARDS, which the page already holds)
  const FACTS = new Map();
  function factsOf(oid) {
    let f = FACTS.get(oid);
    if (f) return f;
    const c = CARDS[oid] || { n: "", ty: "", col: "", mv: null };
    f = { nm: c.n.toLowerCase(), mv: c.mv == null ? null : c.mv, col: c.col || "", ts: c.ty.split(" - ")[0].split(" ").filter(t => TYPES.indexOf(t) >= 0) };
    f.mvb = f.mv == null ? "none" : f.mv >= 6 ? "6+" : String(f.mv);
    FACTS.set(oid, f);
    return f;
  }
  const colMatch = (f, c) => c === "C" ? f.col === "" : c === "M" ? f.col.length >= 2 : f.col.indexOf(c) >= 0;

  // ---------------------------------------------------------------- group membership, the way the group pages list it (built once, rebuilt if a source file arrives later)
  let IDX = null, IDXSIG = "";
  const sig = () => [!!MEM, !!CARDS, !!TENT, !!LOOSE, !!TAGS, !!SIB, !!MI, !!MRESV, MRESV ? Object.keys(MRESV.adds).length : 0].join();
  function chipKey(gid) { return MERGED && MERGED.by_gid && MERGED.by_gid[gid] ? "P:" + MERGED.by_gid[gid] : gid; }
  function buildIndex() {
    const s = sig();
    if (IDX && IDXSIG === s) return IDX;
    const mem = new Map(), offered = gid => !!(MI && MI.groups[gid] && MI.groups[gid][4]);
    const add = (gid, oid) => { if (!CARDS[oid] || !offered(gid)) return; const k = chipKey(gid); let m = mem.get(k); if (!m) mem.set(k, m = new Set()); m.add(oid); };
    for (const [lid, rows] of Object.entries(MEM)) for (const r of rows) add("leaf:" + lid, r[0]);
    if (SIB) for (const [lid, g] of Object.entries(SIB.groups)) for (const r of g.m) add("leaf:" + lid, r[0]);
    if (TENT) for (const [id, g] of Object.entries(TENT.groups)) for (const r of g.m) add("tent:" + id, r[0]);
    if (LOOSE) for (const [id, g] of Object.entries(LOOSE.groups)) for (const r of g.m) add("loose:" + id, r[0]);
    if (TAGS) for (const [id, g] of Object.entries(TAGS.groups)) for (const o of g.m) add("tag:" + id, o);
    for (const [gid, l] of Object.entries(TAX.blocks.keyword.leaves)) for (const o of l.cards) add(gid, o);
    for (const [id, l] of Object.entries(TAX.blocks.replacement.leaves)) for (const o of l.cards) add("rp:" + id, o);
    if (MRESV) {
      for (const [oid, gs] of Object.entries(MRESV.adds)) for (const gid of Object.keys(gs)) add(gid, oid);
      for (const [oid, gs] of Object.entries(MRESV.removes)) for (const gid of Object.keys(gs)) { const m = mem.get(chipKey(gid)); if (m && !(MERGED && MERGED.by_gid[gid])) m.delete(oid); }
    }
    const of = new Map(), name = new Map(), nk = new Map(), loose = new Map();
    for (const [k, set] of mem) {
      for (const o of set) { let a = of.get(o); if (!a) of.set(o, a = []); a.push(k); }
      if (k.startsWith("P:")) { const pg = MERGED.pageBy[k.slice(2)]; name.set(k, pg.name); loose.set(k, pg.members.some(m => m.layer === "tag")); }
      else {
        name.set(k, MI.groups[k][0]);
        const layer = MI.groups[k][3];
        loose.set(k, layer === "tent" || layer === "loose" || layer === "tag" || (layer === "leaf" && !!TAX.leaves[k.slice(5)] && TAX.leaves[k.slice(5)].flags.length > 0));
      }
      nk.set(k, nameKey(name.get(k)));
    }
    IDX = { mem: mem, of: of, name: name, nk: nk, loose: loose };
    IDXSIG = s;
    return IDX;
  }
  function ownKeys(key) {
    const own = new Set(), names = [];
    if (MERGED && MERGED.redirects && MERGED.redirects[key] && key !== ALONEKEY) { const pg = MERGED.pageBy[MERGED.redirects[key]]; for (const m of pg.members) own.add(m.gid); own.add("P:" + pg.slug); names.push(pg.name); for (const m of pg.members) names.push(m.name); }
    else { const gid = Suggested.gidOfKey(String(key), !!(TENT && TENT.groups && TENT.groups[String(key).slice(String(key).indexOf(":") + 1)])); if (gid) { own.add(gid); const k = chipKey(gid); own.add(k); } }
    return { own: own, names: names };
  }

  // ---------------------------------------------------------------- state: one per page (reset when another page opens)
  const fresh = () => ({ k: null, cols: new Set(), types: new Set(), mvs: new Set(), sort: "best", nar: [], nshow: 12, open: false, nopen: false });
  let ST = fresh();
  const active = () => ST.cols.size || ST.types.size || ST.mvs.size || ST.nar.length;
  function pass(f, skip) {
    if (skip !== "col" && ST.cols.size) { let ok = false; for (const c of ST.cols) if (colMatch(f, c)) { ok = true; break; } if (!ok) return false; }
    if (skip !== "type" && ST.types.size) { let ok = false; for (const t of ST.types) if (f.ts.indexOf(t) >= 0) { ok = true; break; } if (!ok) return false; }
    if (skip !== "mv" && ST.mvs.size && !ST.mvs.has(f.mvb)) return false;
    return true;
  }
  function inAllNarrow(oid, idx) { for (const k of ST.nar) { const m = idx.mem.get(k); if (!m || !m.has(oid)) return false; } return true; }
  const uniq = oids => { const s = new Set(), out = []; for (const o of oids) if (!s.has(o)) { s.add(o); out.push(o); } return out; };

  // ---------------------------------------------------------------- narrowing chips for a list of cards
  const PAGEINFO = { k: "", n: -1, twins: null };
  function twinKeys(pageOids, key, idx) {
    if (PAGEINFO.k === key && PAGEINFO.n === pageOids.length && PAGEINFO.sig === IDXSIG) return PAGEINFO.twins;
    const o = ownKeys(key), cnt = new Map(), twins = new Set(), ownNK = o.names.concat([...o.own].map(k => idx.name.get(k)).filter(Boolean)).map(nameKey);
    for (const oid of pageOids) { const a = idx.of.get(oid); if (a) for (const k of a) cnt.set(k, (cnt.get(k) || 0) + 1); }
    for (const [k, n] of cnt) {
      const nk = idx.nk.get(k); let tw = false;
      for (const a of ownNK) if (jac(nk, a) >= 0.7) { tw = true; break; }
      if (!tw) { const size = idx.mem.get(k).size; if (n / (pageOids.length + size - n) >= 0.8) tw = true; }
      if (tw) twins.add(k);
    }
    PAGEINFO.k = key; PAGEINFO.n = pageOids.length; PAGEINFO.sig = IDXSIG; PAGEINFO.twins = twins;
    return twins;
  }
  function chipsFor(list, pageOids, key) {
    const idx = buildIndex(), own = ownKeys(key).own, twins = twinKeys(pageOids, key, idx), cnt = new Map(), N = list.length;
    for (const oid of list) { const a = idx.of.get(oid); if (a) for (const k of a) if (!own.has(k)) cnt.set(k, (cnt.get(k) || 0) + 1); }
    const sel = new Set(ST.nar), cand = [];
    for (const [k, n] of cnt) { if (n < 3 || n * 10 >= N * 9 || twins.has(k) || sel.has(k)) continue; cand.push({ key: k, n: n, label: clean(idx.name.get(k)), loose: idx.loose.get(k) }); }
    cand.sort((a, b) => b.n - a.n || cmp(a.label, b.label) || cmp(a.key, b.key));
    const kept = [];
    for (const c of cand) {
      let dup = false;
      for (const d of kept) { if (jac(idx.nk.get(c.key), idx.nk.get(d.key)) >= 0.7) { dup = true; break; } const A = idx.mem.get(c.key), B = idx.mem.get(d.key); let i = 0; for (const x of A) if (B.has(x)) i++; if (i / (A.size + B.size - i) >= 0.8) { dup = true; break; } }
      if (!dup) kept.push(c);
    }
    return kept;
  }

  // ---------------------------------------------------------------- the list: filter, then sort inside each section
  function sortOids(oids) {
    if (ST.sort === "best") return oids;
    const a = oids.slice();
    if (ST.sort === "name") a.sort((x, y) => cmp(factsOf(x).nm, factsOf(y).nm) || cmp(x, y));
    else a.sort((x, y) => { const p = factsOf(x), q = factsOf(y); return (p.mv == null) - (q.mv == null) || (p.mv || 0) - (q.mv || 0) || cmp(p.nm, q.nm) || cmp(x, y); });
    return a;
  }
  const oidOf = it => (typeof it === "string" ? null : itemOid(it));
  // Headings are the page's own strings between cards (a merged page's section heads, "Added by hand", "Others in this group"). One is kept only when a card of its section is left.
  const isMsec = h => h.indexOf('id="msec-') >= 0, isCloser = h => /Others in this group|Checked members of this group/.test(h);
  function filterItems(full) {
    const idx = buildIndex(), out = [];
    let head = [], sec = [], subEmitted = false;
    const order = x => x;
    const flush = () => {
      if (sec.length) {
        for (const h of head) { out.push(h); subEmitted = isMsec(h) ? false : true; }
        const s = ST.sort === "best" ? sec : sec.slice().sort((x, y) => { const p = factsOf(oidOf(x)), q = factsOf(oidOf(y)); return ST.sort === "name" ? cmp(p.nm, q.nm) || cmp(oidOf(x), oidOf(y)) : (p.mv == null) - (q.mv == null) || (p.mv || 0) - (q.mv || 0) || cmp(p.nm, q.nm) || cmp(oidOf(x), oidOf(y)); });
        for (const x of s) out.push(order(x));
        head = []; sec = [];
      }
    };
    for (const it of full) {
      const o = oidOf(it);
      if (o == null) {
        flush();
        if (isCloser(it)) { while (head.length && !isMsec(head[head.length - 1])) head.pop(); if (subEmitted) head.push(it); continue; }
        if (head.length && (!isMsec(head[head.length - 1]) || isMsec(it))) head.pop();
        head.push(it);
        continue;
      }
      if (pass(factsOf(o), null) && inAllNarrow(o, idx)) sec.push(it);
    }
    flush();
    return out;
  }

  // ---------------------------------------------------------------- the bar
  const esc2 = esc;
  function facetCounts(list, idx) {
    const cc = {}, tc = {}, mc = {};
    for (const [c] of COLS) cc[c] = 0; for (const t of TYPES) tc[t] = 0; for (const [m] of MVS) mc[m] = 0;
    for (const oid of list) {
      const f = factsOf(oid);
      if (!inAllNarrow(oid, idx)) continue;
      if (pass(f, "col")) for (const [c] of COLS) if (colMatch(f, c)) cc[c]++;
      if (pass(f, "type")) for (const t of f.ts) tc[t]++;
      if (pass(f, "mv")) mc[f.mvb]++;
    }
    return { cc: cc, tc: tc, mc: mc };
  }
  const colName = c => COLS.find(x => x[0] === c)[1];
  function summary(idx) {
    const p = [];
    for (const c of ST.cols) p.push(colName(c));
    for (const t of ST.types) p.push(t);
    for (const m of ST.mvs) p.push(m === "none" ? "No cost" : "MV " + m);
    if (ST.nar.length) p.push(ST.nar.length + " group" + (ST.nar.length > 1 ? "s" : ""));
    return p.join(" · ");
  }
  function barHTML(fullOids, shown, ctx) {
    const idx = buildIndex(), fc = facetCounts(fullOids, idx);
    const pipHTML = COLS.map(([c, n]) => `<button type="button" class="fpip p${c}${ST.cols.has(c) ? " on" : ""}${!fc.cc[c] && !ST.cols.has(c) ? " dim" : ""}" data-f="col" data-v="${c}" aria-pressed="${ST.cols.has(c)}" aria-label="${n}, ${fc.cc[c]} cards" title="${n} (${fc.cc[c]})">${c === "C" ? "◇" : c}</button>`).join("");
    const typeHTML = TYPES.filter(t => fullOids.some(o => factsOf(o).ts.indexOf(t) >= 0) || ST.types.has(t)).map(t => `<button type="button" class="fch${ST.types.has(t) ? " on" : ""}${!fc.tc[t] && !ST.types.has(t) ? " dim" : ""}" data-f="type" data-v="${t}" aria-pressed="${ST.types.has(t)}">${t} <b>${fmt(fc.tc[t])}</b></button>`).join("");
    const mvHTML = MVS.map(([m, n]) => `<button type="button" class="fch${ST.mvs.has(m) ? " on" : ""}${!fc.mc[m] && !ST.mvs.has(m) ? " dim" : ""}" data-f="mv" data-v="${m}" aria-pressed="${ST.mvs.has(m)}">${n} <b>${fmt(fc.mc[m])}</b></button>`).join("");
    const sortHTML = `<select class="fsel" data-f="sort" aria-label="Sort"><option value="best"${ST.sort === "best" ? " selected" : ""}>Best match</option><option value="mv"${ST.sort === "mv" ? " selected" : ""}>Mana value</option><option value="name"${ST.sort === "name" ? " selected" : ""}>Name</option></select>`;
    const status = `Showing <b>${fmt(shown)}</b> of ${fmt(fullOids.length)}`;
    const sm = summary(idx);
    const nrow = narrowHTML(ctx.list, fullOids, ctx.key, idx);
    return `<div class="fwrap" data-open="${ST.open ? 1 : 0}" data-nopen="${ST.nopen ? 1 : 0}">` +
      `<button type="button" class="fsum" data-f="fold" aria-expanded="${ST.open}"><span>Filter and sort</span><span class="fpills">${esc2(sm) || "none on"}</span><span>${status}</span><span aria-hidden="true">${ST.open ? "▾" : "▸"}</span></button>` +
      `<div class="fbar"><div class="frow"><span class="flab">Colour</span><div class="fgrp">${pipHTML}</div></div><div class="fnote">Card colour, not colour identity</div>` +
      `<div class="frow"><span class="flab">Type</span><div class="fgrp">${typeHTML}</div></div>` +
      `<div class="frow"><span class="flab">Mana value</span><div class="fgrp">${mvHTML}</div></div>` +
      `<div class="frow"><span class="flab">Sort</span>${sortHTML}</div>` +
      `<div class="fstat"><span>${status}</span>${active() ? `<button type="button" class="flink" data-f="clear">Clear filters</button>` : ""}</div></div>` +
      (nrow ? `<button type="button" class="fsum" data-f="nfold" aria-expanded="${ST.nopen}"><span>Narrow by group</span><span class="fpills">${ST.nar.length ? ST.nar.length + " on" : "none on"}</span><span aria-hidden="true">${ST.nopen ? "▾" : "▸"}</span></button>` + nrow : "") + `</div>`;
  }
  function narrowHTML(list, pageOids, key, idx) {
    const chips = chipsFor(list, pageOids, key);
    if (!chips.length && !ST.nar.length) return "";
    const selH = ST.nar.map(k => `<button type="button" class="fch on x${idx.loose.get(k) ? " lo" : ""}" data-f="narx" data-v="${esc2(k)}" title="Remove: ${esc2(idx.name.get(k))}">${esc2(clean(idx.name.get(k)))}</button>`).join("");
    const shown = chips.slice(0, ST.nshow);
    const chH = shown.map(c => `<button type="button" class="fch${c.loose ? " lo" : ""}" data-f="nar" data-v="${esc2(c.key)}" title="${esc2(idx.name.get(c.key))}">${esc2(c.label)} <b>${fmt(c.n)}</b></button>`).join("");
    const more = chips.length > shown.length ? `<button type="button" class="flink" data-f="nmore">Show more (${shown.length} of ${chips.length} shown)</button>` : "";
    return `<div class="nrow"><div class="frow"><span class="flab">Narrow by group</span>${selH}${ST.nar.length ? `<button type="button" class="flink" data-f="nclear">Clear</button>` : ""}</div>` +
      `<div class="fgrp">${chH}${more}</div><div class="fnote">Counts are for the cards showing now. Dashed means grouped loosely.</div></div>`;
  }

  // ---------------------------------------------------------------- the members list
  let FULL = [], LISTKEY = "";
  function renderBarInto(host, fullOids, shown, list, key) { host.innerHTML = barHTML(fullOids, shown, { list: list, key: key }); }
  function applyList() {
    const P = $("panel"), host = $("fwrap");
    if (!host) return;
    const fullOids = uniq(FULL.map(oidOf).filter(o => o != null));
    const idx = buildIndex();
    const items = filterItems(FULL);
    const list = uniq(items.map(oidOf).filter(o => o != null));
    LIST = items; LISTN = 0;
    const el = $("list");
    if (el) { el.innerHTML = ""; renderList(); }
    renderBarInto(host, fullOids, list.length, list, LISTKEY);
    pinNote(list);
    void P; void idx;
  }
  function pinNote(list) {
    const w = $("pinwrap"); if (!w) return;
    const old = w.querySelector(".pinfilt"); if (old) old.remove();
    if (PINCUR && active() && !list.includes(PINCUR) && FULL.some(x => oidOf(x) === PINCUR)) w.insertAdjacentHTML("beforeend", `<div class="sub pinfilt">Hidden by your filters. <button type="button" class="flink" data-f="clear">Clear filters</button></div>`);
  }
  const _setList = setList;
  setList = function (head, items, opts) {
    _setList(head, items, opts);
    try {
      const P = $("panel"), vb = P.querySelector(".viewbar"), old = $("fwrap");
      if (old) old.remove();
      if (!vb || !LIST.some(x => oidOf(x) != null) || !CARDS) return;
      if (ST.k !== selected) { ST = fresh(); ST.k = selected; }
      FULL = LIST.slice(); LISTKEY = selected;
      const host = document.createElement("div"); host.id = "fwrap"; vb.after(host);
      applyList();
    } catch (e) { if (window.console) console.error("filters", e); }
  };
  if (Array.isArray(SCHIDE)) SCHIDE.push("#fwrap");

  // ---------------------------------------------------------------- "Might also fit": the same bar over the suggestion rows
  let SUGLIST = [];
  function sugg(rowsA, rowsB) {
    const key = selected;
    if (ST.k !== key) { ST = fresh(); ST.k = key; }
    const idx = buildIndex(), all = uniq(rowsA.map(r => r.oid).concat(rowsB.map(r => r.oid)));
    const keepA = rowsA.filter(r => pass(factsOf(r.oid), null) && inAllNarrow(r.oid, idx)), keepB = rowsB.filter(r => pass(factsOf(r.oid), null) && inAllNarrow(r.oid, idx));
    const ord = rows => ST.sort === "best" ? rows : rows.slice().sort((x, y) => { const p = factsOf(x.oid), q = factsOf(y.oid); return ST.sort === "name" ? cmp(p.nm, q.nm) || cmp(x.oid, y.oid) : (p.mv == null) - (q.mv == null) || (p.mv || 0) - (q.mv || 0) || cmp(p.nm, q.nm) || cmp(x.oid, y.oid); });
    const A = ord(keepA), B = ord(keepB), shownList = uniq(A.map(r => r.oid).concat(B.map(r => r.oid)));
    SUGLIST = all;
    return { A: A, B: B, bar: `<div id="fwrap2">` + barHTML(all, shownList.length, { list: shownList, key: key }) + `</div>` };
  }

  // ---------------------------------------------------------------- events
  function refresh() {
    if (SCCUR && SCCUR.tab === "matches") { scRender(); return; }
    applyList();
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-f]");
    if (!b || !$("panel").contains(b)) return;
    const f = b.dataset.f, v = b.dataset.v;
    if (f === "col" || f === "type" || f === "mv") { const s = f === "col" ? ST.cols : f === "type" ? ST.types : ST.mvs; if (s.has(v)) s.delete(v); else s.add(v); }
    else if (f === "nar") { if (!ST.nar.includes(v)) ST.nar.push(v); }
    else if (f === "narx") ST.nar = ST.nar.filter(k => k !== v);
    else if (f === "nclear") ST.nar = [];
    else if (f === "nmore") ST.nshow += 12;
    else if (f === "clear") { ST.cols.clear(); ST.types.clear(); ST.mvs.clear(); ST.nar = []; }
    else if (f === "fold") ST.open = !ST.open;
    else if (f === "nfold") ST.nopen = !ST.nopen;
    else return;
    e.stopPropagation();
    refresh();
  }, true);
  document.addEventListener("change", e => {
    const s = e.target.closest && e.target.closest("select[data-f=sort]");
    if (!s || !$("panel").contains(s)) return;
    ST.sort = s.value; refresh();
  }, true);
  const _scSetTab = scSetTab;
  scSetTab = async function (tab) { await _scSetTab(tab); if (tab === "members") { try { applyList(); } catch (e) { /* no bar on this page */ } } };

  window.TF = { enabled: true, sugg: sugg, refresh: refresh, state: () => ST, full: () => uniq(FULL.map(oidOf).filter(o => o != null)), shown: () => uniq(LIST.map(oidOf).filter(o => o != null)),
    chips: () => { const idx = buildIndex(), full = uniq(FULL.map(oidOf).filter(o => o != null)); return chipsFor(uniq(LIST.map(oidOf).filter(o => o != null)), full, LISTKEY).map(c => ({ key: c.key, label: c.label, n: c.n, name: idx.name.get(c.key), loose: c.loose })); },
    members: key => buildIndex().mem.get(key) || new Set(), reset: () => { ST = fresh(); ST.k = selected; } };
})();
