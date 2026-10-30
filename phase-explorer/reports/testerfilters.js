/* Tester mode, feature TESTER_FILTERS (reports/config.js): a filter and sort bar on group pages (colour, type, mana value, sort) and a "Narrow by group" row.
 * Loaded by reports/tester.js only when the flag is on, and only in tester mode. Presentation only: it reads facts the page already holds (CARDS: name, type line, colour, mana value) and the group
 * memberships the group pages themselves list (members, sibling, tentative, loose, tag, keyword and replacement files, hand placements), and changes no group, id, placement, suggestion or figure.
 * Nothing is fetched: every number is computed in the page (flag-gated extras below fetch their own lazy files through typegroups.js / flipfaces.js).
 *
 * Flags (reports/config.js; each absent or false means the rules in the first block below, exactly):
 *   NARROW_NO_CUT  the "Narrow by group" chips drop the 3-card minimum: a chip needs 2 shared cards; a "Show single-card groups" link adds the 1-card chips. Order: shared count, then the smaller group,
 *                  then name. Chips that pick exactly the same cards on this list are folded into the first. 12 shown, "Show more" adds 12 up to 60. The row is shown (with its count in the folded 390 px
 *                  line) even when it has no chip. The 90% cap, the zero-count hiding and the near-twin rules are unchanged.
 *   COLOUR_MODES   colour match: "Any of these" (default, today's rule), "Includes all", "Only these", "Not these". The colourless and multicolour chips are extra conditions in the last three.
 *   TYPE_GROUPS    (typegroups.js) adds a "Subtype" row: a card passes if any face has the chosen type, supertype or subtype (OR inside the row). Type pages themselves are never offered as chips.
 *   FLIP_FACES     (flipfaces.js) colour and type read both faces of a two-faced card (the union); a card shown only because of its other face says so.
 *   BROAD_NARROWING  (needs NARROW_NO_CUT; data: build/buckets/map.json, written by src/build_buckets.py) the first level of "Narrow by group" is 15 topics (Card draw, Counters, ...), each with a dropdown of its
 *                  specific groups. A topic is a set of groups, a group may be in several; a card is in a topic if it is in any group of it (not the page's own group or a near-twin of it; groups of one card count).
 *                  Topics are filters, never placements. Inside a topic: any of the chosen groups; across topics: all. Groups with no topic are reached with "Show all groups" (today's flat chips).
 *   DEFAULT_POPULARITY  the sort has a fourth choice, "Most popular first" (Scryfall's EDHREC rank, read from MI.cards[oid][4] in manual_index.json: lower is more popular; unranked last; ties by name, then id), which is the
 *                  default for the cards on a group page; "Best match" is relabelled "Default order". "Might also fit" keeps its own score order unless a sort was chosen. A chosen sort is remembered (localStorage "sortPref").
 *   PERSIST_FILTERS  colour, colour match, type and mana value are kept when another group opens (sessionStorage "filterState": this tab only, gone when it closes); sort stays in localStorage "sortPref".
 *                  Narrowing, Subtype and Trigger / Cost / Kind start empty on every group. A line over the bar names the kept filters with "Clear all"; a group with nothing left says so and what dropping each filter
 *                  would show; a pinned card the kept filters hide stays in its pinned row with a note naming the filters. Filters are views, never placements.
 *   COLOUR_IDENTITY  a "Based on" switch (Card colour | Colour identity, default Colour identity, remembered in localStorage "colourBasis"). Identity is Scryfall's color_identity, read from
 *                  build/colour_identity/cards.json (src/build_colour_identity.py), requested once when this file loads; the four colour modes then apply to the card's identity instead of its colour.
 *                  The 15 cards Scryfall's file lacks use their card colour. Needs TESTER_FILTERS (all modes need COLOUR_MODES as well; without it only "Any of these").
 *
 * Rules (src/test_tester_static.py re-derives them in Python and compares):
 *   filter: AND across kinds (colour, type, mana value), OR inside a kind. Colour is the card's colour, not its colour identity (unless COLOUR_IDENTITY is on and "Colour identity" is chosen). Facts are those of the face the page lists (a split card: its first half).
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
  const FLG = window.APP_CONFIG || {};
  const NNC = FLG.NARROW_NO_CUT === true, CMODES = FLG.COLOUR_MODES === true, TGON = FLG.TYPE_GROUPS === true, ABON = FLG.ABILITY_TYPE_PAGES === true && FLG.ABILITY_TYPE_FILTERS === true;
  const POP = FLG.DEFAULT_POPULARITY === true;
  const BKON = FLG.BROAD_NARROWING === true && NNC;
  const PERSIST = FLG.PERSIST_FILTERS === true, CIDON = FLG.COLOUR_IDENTITY === true;
  if (PERSIST || CIDON) {
    const st = document.createElement("style");
    st.textContent = ".fkept{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;padding:6px 10px;border-left:3px solid var(--accent);border-radius:0 6px 6px 0;background:var(--sel);font-size:13px}.fkept .flink{margin-left:auto}" +
      ".fempty{border:1px dashed var(--line);border-radius:8px;padding:12px;font-size:14px}.cbseg{display:inline-flex;gap:6px}@media (max-width:800px){.cbseg{width:100%}.cbseg .fch{flex:1;justify-content:center;min-height:44px}.fkept .flink{min-height:44px}}";
    document.head.appendChild(st);
  }
  if (BKON) {
    const st = document.createElement("style");
    st.textContent = ".nsub{display:flex;flex-direction:column;gap:6px;padding:6px 8px;border-left:3px solid var(--accent);border-radius:0 6px 6px 0;background:var(--sel)}.fnote.nl{margin-left:0}@media (max-width:800px){.nsub .fsel{width:100%}}";
    document.head.appendChild(st);
  }
  if (CMODES) {                                                                              // the match-mode rules live here, so testerfilters.css is the file it always was
    const st = document.createElement("style");
    st.textContent = ".cmsel{display:none}.fpip[aria-disabled=true]{cursor:not-allowed}@media (max-width:800px){.cmseg{display:none}.cmsel{display:block}}";
    document.head.appendChild(st);
  }
  const CMODE_NAMES = [["any", "Any of these"], ["all", "Includes all"], ["only", "Only these"], ["exactly", "Exactly these"], ["not", "Not these"]];
  const DEFMODE = CMODES ? "only" : "any";                                                    // COLOUR_MODES: "Only these" is the mode a page opens with
  const typesOf = ty => String(ty).split(" - ")[0].split(" ").filter(t => TYPES.indexOf(t) >= 0);

  // ---------------------------------------------------------------- facts (from CARDS, which the page already holds)
  const FACTS = new Map();
  function factsOf(oid) {
    let f = FACTS.get(oid);
    if (f) return f;
    const c = CARDS[oid] || { n: "", ty: "", col: "", mv: null };
    f = { nm: c.n.toLowerCase(), mv: c.mv == null ? null : c.mv, col: c.col || "", ts: typesOf(c.ty), oid: oid };
    const fl = window.FL && FL.on() ? FL.get(oid) : null;                 // FLIP_FACES: a two-faced card is read from both faces (colours and types are the union)
    if (fl) {
      let col = "", ts = new Set(f.ts);
      for (const x of fl.f) { col += x.c; for (const t of typesOf(x.ty)) ts.add(t); }
      f.col = "WUBRG".split("").filter(x => col.indexOf(x) >= 0).join(""); f.ts = TYPES.filter(t => ts.has(t));
    }
    f.mvb = f.mv == null ? "none" : f.mv >= 6 ? "6+" : String(f.mv);
    FACTS.set(oid, f);
    return f;
  }
  const colMatch = (f, c) => c === "C" ? f.col === "" : c === "M" ? f.col.length >= 2 : f.col.indexOf(c) >= 0;
  // COLOUR_IDENTITY: the colours the filter reads. BASIS "identity" reads Scryfall's colour identity (build/colour_identity/cards.json); until that file is here, or if it failed, the card colour.
  const A32 = "0123456789abcdefghijklmnopqrstuv", MASKS = [];
  for (let m = 0; m < 32; m++) MASKS.push("WUBRG".split("").filter((l, i) => m >> i & 1).join(""));
  function prefBasis() { try { const v = localStorage.getItem("colourBasis"); return v === "card" || v === "identity" ? v : "identity"; } catch (e) { return "identity"; } }
  let BASIS = CIDON ? prefBasis() : "card", CIDOC = null, CIFAIL = false, CIIDX = null, CIP = null;
  function ciLoad() {
    if (!CIDON || CIP) return;
    CIP = (async () => {
      const [d] = await Promise.all([J("colour_identity/cards.json"), needCards()]);
      const keys = Object.keys(CARDS);
      if (d.v !== 1 || d.sig !== fnv(keys) || d.i.length !== keys.length) throw new Error("colour_identity: built for another card list");
      CIIDX = new Map(); keys.forEach((k, i) => CIIDX.set(k, A32.indexOf(d.i.charAt(i))));
      CIDOC = d;
      FACTS.clear();
      if (BASIS === "identity") { try { refresh(); } catch (e) { /* no list is open */ } }
    })().catch(e => { CIFAIL = true; if (window.console) console.error("colour_identity", e); try { refresh(); } catch (er) { /* no list is open */ } });
  }
  const idOn = () => CIDON && BASIS === "identity" && !!CIDOC;
  const colourOf = f => (idOn() ? MASKS[CIIDX.get(f.oid)] : f.col);
  const colM = (f, c) => colMatch({ col: colourOf(f) }, c);
  // colour match in the four modes; "any" is the rule the page always had. X = the card's colours, L = chosen colour letters, c / m = the colourless / multicolour chips.
  function colOk(col, cols, mode) {
    if (!cols.size) return true;
    if (!CMODES || mode === "any") { for (const c of cols) if (colMatch({ col: col }, c)) return true; return false; }
    const L = [...cols].filter(x => x !== "C" && x !== "M"), c = cols.has("C"), m = cols.has("M"), n = col.length;
    if (mode === "all") { for (const l of L) if (col.indexOf(l) < 0) return false; return !(c && n) && !(m && n < 2); }
    if (mode === "only") {
      if (n === 0) return c;
      if (m && !L.length) return n >= 2;
      for (const ch of col) if (L.indexOf(ch) < 0) return false;
      return !(m && n < 2);
    }
    if (mode === "exactly") {                                                                 // the card's colours are exactly the chosen letters (colourless: none, no letters)
      if (c) return n === 0 && !L.length;
      if (!L.length) return n >= 2;                                                           // only the multicolour chip is on
      return n === L.length && L.every(l => col.indexOf(l) >= 0) && !(m && n < 2);
    }
    for (const l of L) if (col.indexOf(l) >= 0) return false;                                 // "not"
    return !(c && n === 0) && !(m && n >= 2);
  }

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
  // DEFAULT_POPULARITY: ST.sort is null until the viewer chooses one (then it is remembered); the cards list then defaults to "pop", the suggestion list to "best" (its score order)
  const PREFS = ["pop", "best", "mv", "name"];
  function prefSort() { try { const v = localStorage.getItem("sortPref"); return PREFS.indexOf(v) >= 0 ? v : null; } catch (e) { return null; } }
  const sortMode = ctx => (POP ? ST.sort || (ctx === "sugg" ? "best" : "pop") : ST.sort);
  const rankOf = oid => { const m = typeof MI !== "undefined" && MI && MI.cards && MI.cards[oid]; return m && m[4] != null ? m[4] : null; };
  const popCmp = (x, y) => { const a = rankOf(x), b = rankOf(y); return (a == null) - (b == null) || (a || 0) - (b || 0) || cmp(factsOf(x).nm, factsOf(y).nm) || cmp(x, y); };
  // PERSIST_FILTERS: colour, colour match, type and mana value live in sessionStorage "filterState" (this tab only); a page that cannot store keeps them in PMEM for as long as the page lives
  let PMEM = null;
  function loadP() {
    let d = PMEM;
    try { const s = sessionStorage.getItem("filterState"); if (s) d = JSON.parse(s); } catch (e) { /* storage unavailable or damaged: PMEM */ }
    if (!d || typeof d !== "object") return null;
    const arr = (a, ok) => (Array.isArray(a) ? a.filter(x => typeof x === "string" && ok.indexOf(x) >= 0) : []);
    const cols = arr(d.c, COLS.map(x => x[0])), types = arr(d.t, TYPES), mvs = arr(d.v, MVS.map(x => x[0]));
    let mode = CMODE_NAMES.some(x => x[0] === d.m) && CMODES ? d.m : DEFMODE;
    if (mode === "only") { const i = cols.indexOf("M"); if (i >= 0) cols.splice(i, 1); }
    return { cols: cols, types: types, mvs: mvs, mode: mode };
  }
  function saveP() {
    if (!PERSIST) return;
    const d = { c: [...ST.cols], m: ST.cmode, t: [...ST.types], v: [...ST.mvs] };
    PMEM = d;
    try { if (d.c.length || d.t.length || d.v.length) sessionStorage.setItem("filterState", JSON.stringify(d)); else sessionStorage.removeItem("filterState"); } catch (e) { /* kept in PMEM */ }
    ST.kept = ST.kept && !!(d.c.length || d.t.length || d.v.length);
  }
  const fresh = () => {
    const s = { k: null, cols: new Set(), cmode: DEFMODE, types: new Set(), subs: new Set(), ab: { trig: new Set(), cost: new Set(), kind: new Set() }, mvs: new Set(), sort: POP ? prefSort() : "best", nar: [], bk: new Map(), bshow: false, nshow: 12, single: false, open: false, nopen: false, kept: false };
    if (PERSIST) { const p = loadP(); if (p && (p.cols.length || p.types.length || p.mvs.length)) { s.cols = new Set(p.cols); s.types = new Set(p.types); s.mvs = new Set(p.mvs); s.cmode = p.mode; s.kept = true; } }
    return s;
  };
  let ST = fresh();
  const abN = () => ST.ab.trig.size + ST.ab.cost.size + ST.ab.kind.size;
  const active = () => ST.cols.size || ST.types.size || ST.subs.size || abN() || ST.mvs.size || ST.nar.length || ST.bk.size;
  const abOk = oid => { for (const r of ["trig", "cost", "kind"]) if (ST.ab[r].size) { let ok = false; for (const k of ST.ab[r]) if (AP.has(k, oid)) { ok = true; break; } if (!ok) return false; } return true; };
  const subOk = (oid, subs) => { for (const k of subs) if (TG.has(k, oid)) return true; return false; };
  function pass(f, skip) {
    if (skip !== "col" && ST.cols.size && !colOk(colourOf(f), ST.cols, ST.cmode)) return false;
    if (skip !== "type" && ST.types.size) { let ok = false; for (const t of ST.types) if (f.ts.indexOf(t) >= 0) { ok = true; break; } if (!ok) return false; }
    if (skip !== "sub" && ST.subs.size && !subOk(f.oid, ST.subs)) return false;
    if (ABON && skip !== "ab" && abN() && !abOk(f.oid)) return false;
    if (skip !== "mv" && ST.mvs.size && !ST.mvs.has(f.mvb)) return false;
    return true;
  }
  function inAllNarrow(oid, idx, skipTopic) {
    for (const k of ST.nar) { const m = idx.mem.get(k); if (!m || !m.has(oid)) return false; }
    if (BKON && ST.bk.size) for (const [b, specs] of ST.bk) {
      if (b === skipTopic) continue;
      if (specs.length) { let ok = false; for (const k of specs) { const m = idx.mem.get(k); if (m && m.has(oid)) { ok = true; break; } } if (!ok) return false; }
      else if (!bkSet(b).has(oid)) return false;
    }
    return true;
  }

  // ---------------------------------------------------------------- BROAD_NARROWING: topics (build/buckets/map.json, src/build_buckets.py)
  let BKDOC = null, BKP = null, BKFAIL = false, BKMASK = null, BKCTX = { full: [], key: "" };
  const BKM2 = new Map(), BKC = { sig: "", sets: null };
  function fnv(items) {                                                                         // the same checksum as src/build_buckets.py
    let h = 2166136261;
    for (let i = 0; i < items.length; i++) {
      if (i) { h ^= 10; h = Math.imul(h, 16777619) >>> 0; }
      const s = items[i];
      for (let j = 0; j < s.length; j++) { h ^= s.charCodeAt(j); h = Math.imul(h, 16777619) >>> 0; }
    }
    return ("00000000" + h.toString(16)).slice(-8);
  }
  function bkLoad() {
    if (!BKON || BKP || BKFAIL || typeof MI === "undefined" || !MI) return;
    BKP = J("buckets/map.json").then(d => {
      const keys = Object.keys(MI.groups);
      if (d.v !== 1 || d.sig !== fnv(keys) || d.m.length !== keys.length) throw new Error("buckets: built for another group list");
      BKMASK = new Map(); keys.forEach((k, i) => { if (d.m[i]) BKMASK.set(k, d.m[i]); });
      BKDOC = d;
      try { barOnly(); } catch (e) { /* page changed */ }                                       // no topic is on yet, so the card list stays as it is: only the bar is drawn again
    }).catch(e => { BKFAIL = true; BKP = null; if (window.console) console.error("buckets", e); });
  }
  function bkMask(k) {
    if (!BKMASK) return 0;
    let m = BKM2.get(k);
    if (m != null) return m;
    m = 0;
    if (k.startsWith("P:")) { const pg = MERGED && MERGED.pageBy[k.slice(2)]; if (pg) for (const x of pg.members) m |= BKMASK.get(x.gid) || 0; }
    else m = BKMASK.get(k) || 0;
    BKM2.set(k, m);
    return m;
  }
  // the cards of every topic: those in any group of it, not the page's own groups and not near-twins of the page (a group with one card counts)
  function bkSet(b) {
    const tag = IDXSIG + "|" + BKCTX.key + "|" + BKCTX.full.length + "|" + (BKDOC ? 1 : 0);          // IDXSIG is the signature of the index built last; buildIndex() itself is not called per card
    if (BKC.sig !== tag || !BKC.sets) {
      const idx = buildIndex(), own = ownKeys(BKCTX.key).own, tw = twinKeys(BKCTX.full, BKCTX.key, idx), sets = [];
      for (let i = 0; i < 15; i++) sets.push(new Set());
      if (BKDOC) for (const [k, mem] of idx.mem) {
        if (own.has(k) || tw.has(k)) continue;
        const m = bkMask(k); if (!m) continue;
        for (let i = 0; i < 15; i++) if (m >> i & 1) for (const o of mem) sets[i].add(o);
      }
      BKC.sig = IDXSIG + "|" + BKCTX.key + "|" + BKCTX.full.length + "|" + (BKDOC ? 1 : 0); BKC.sets = sets;
    }
    return BKC.sets[b];
  }
  const uniq = oids => { const s = new Set(), out = []; for (const o of oids) if (!s.has(o)) { s.add(o); out.push(o); } return out; };

  // ---------------------------------------------------------------- narrowing chips for a list of cards
  const PAGEINFO = { k: "", n: -1, twins: null };
  // NARROW_NO_CUT: a chip whose name only restates the page's ("Mill cards" on "Library › Mill cards, by you", "Attach to a creature" on "Attach to a creature you control"): every word of the shorter name
  // (plurals folded, 2 words or more) is in the longer one. "Create Treasure tokens" on "Create Food tokens" is not a restatement.
  const fold = s => new Set([...s].map(w => w.replace(/s$/, "")));
  function restates(a, b) {
    const x = fold(a), y = fold(b), [s, l] = x.size <= y.size ? [x, y] : [y, x];
    if (s.size < 2) return false;
    for (const w of s) if (!l.has(w)) return false;
    return true;
  }
  function twinKeys(pageOids, key, idx) {
    if (PAGEINFO.k === key && PAGEINFO.n === pageOids.length && PAGEINFO.sig === IDXSIG) return PAGEINFO.twins;
    const o = ownKeys(key), cnt = new Map(), twins = new Set(), ownNK = o.names.concat([...o.own].map(k => idx.name.get(k)).filter(Boolean)).map(nameKey);
    for (const oid of pageOids) { const a = idx.of.get(oid); if (a) for (const k of a) cnt.set(k, (cnt.get(k) || 0) + 1); }
    for (const [k, n] of cnt) {
      const nk = idx.nk.get(k); let tw = false;
      for (const a of ownNK) if (jac(nk, a) >= 0.7 || (NNC && restates(nk, a))) { tw = true; break; }
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
    const floor = NNC ? 1 : 3;                                                                  // NARROW_NO_CUT: every chip with a shared card is a candidate; the floor of 2 is applied below, after folding
    for (const [k, n] of cnt) { if (n < floor || n * 10 >= N * 9 || twins.has(k) || sel.has(k)) continue; cand.push({ key: k, n: n, label: clean(idx.name.get(k)), loose: idx.loose.get(k), size: idx.mem.get(k).size }); }
    if (NNC) cand.sort((a, b) => b.n - a.n || a.size - b.size || cmp(a.label, b.label) || cmp(a.key, b.key));
    else cand.sort((a, b) => b.n - a.n || cmp(a.label, b.label) || cmp(a.key, b.key));
    const kept = [], sigs = new Set();
    let sigOf = null;
    if (NNC) {                                                                                  // the cards of this list each chip would keep, in list order: equal text = the same choice
      const by = new Map(); for (const c of cand) by.set(c.key, []);
      for (const oid of list) { const a = idx.of.get(oid); if (a) for (const k of a) { const l = by.get(k); if (l) l.push(oid); } }
      sigOf = k => by.get(k).join("|");
    }
    for (const c of cand) {
      let dup = false;
      if (NNC) { const sg = sigOf(c.key); if (sigs.has(sg)) continue; }
      for (const d of kept) { if (jac(idx.nk.get(c.key), idx.nk.get(d.key)) >= 0.7) { dup = true; break; } const A = idx.mem.get(c.key), B = idx.mem.get(d.key); if (Math.min(A.size, B.size) * 10 < Math.max(A.size, B.size) * 8) continue; let i = 0; for (const x of A) if (B.has(x)) i++; if (i / (A.size + B.size - i) >= 0.8) { dup = true; break; } }
      if (!dup) { kept.push(c); if (NNC) sigs.add(sigOf(c.key)); }
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
        const sm = sortMode("list");
        const s = sm === "best" ? sec : sm === "pop" ? sec.slice().sort((x, y) => popCmp(oidOf(x), oidOf(y))) : sec.slice().sort((x, y) => { const p = factsOf(oidOf(x)), q = factsOf(oidOf(y)); return sm === "name" ? cmp(p.nm, q.nm) || cmp(oidOf(x), oidOf(y)) : (p.mv == null) - (q.mv == null) || (p.mv || 0) - (q.mv || 0) || cmp(p.nm, q.nm) || cmp(oidOf(x), oidOf(y)); });
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
      if (pass(f, "col")) for (const [c] of COLS) if (colM(f, c)) cc[c]++;
      if (pass(f, "type")) for (const t of f.ts) tc[t]++;
      if (pass(f, "mv")) mc[f.mvb]++;
    }
    return { cc: cc, tc: tc, mc: mc };
  }
  const colName = c => COLS.find(x => x[0] === c)[1];
  function summary(idx) {
    const p = [];
    if (CIDON && ST.cols.size && idOn()) p.push("Identity");
    for (const c of ST.cols) p.push(colName(c));
    if (CMODES && ST.cols.size && ST.cmode !== DEFMODE) p.push(CMODE_NAMES.find(x => x[0] === ST.cmode)[1]);
    for (const t of ST.types) p.push(t);
    for (const k of ST.subs) p.push(TG.name(k));
    if (ABON && window.AP) for (const r of ["trig", "cost", "kind"]) for (const k of ST.ab[r]) p.push(AP.name(k));
    for (const m of ST.mvs) p.push(m === "none" ? "No cost" : "MV " + m);
    if (BKON && BKDOC) for (const [b, specs] of ST.bk) p.push(BKDOC.b[b][1] + (specs.length ? " (" + specs.length + ")" : ""));
    if (ST.nar.length) p.push(ST.nar.length + " group" + (ST.nar.length > 1 ? "s" : ""));
    return p.join(" · ");
  }
  // PERSIST_FILTERS: the filters that are kept from group to group, in words
  function keptText() {
    const p = [];
    if (ST.cols.size) p.push((CIDON ? (idOn() ? "Colour identity" : "Card colour") + " · " : "") + (CMODES ? CMODE_NAMES.find(x => x[0] === ST.cmode)[1] + ": " : "") + [...ST.cols].map(colName).join(", "));
    for (const t of ST.types) p.push(t);
    for (const m of ST.mvs) p.push(m === "none" ? "No cost" : "MV " + m);
    return p.join(" · ");
  }
  const keptN = () => ST.cols.size + ST.types.size + ST.mvs.size;
  // how many of the page's cards would show if one kind of filter were dropped (an empty list names the ones that help)
  function dropCounts(fullOids, idx) {
    const kinds = [["Colour", "col", ST.cols.size], ["Type", "type", ST.types.size], ["Subtype", "sub", ST.subs.size], ["Trigger, cost or kind", "ab", abN()], ["Mana value", "mv", ST.mvs.size], ["Narrowing", "nar", ST.nar.length + ST.bk.size]], out = [];
    for (const [name, skip, on] of kinds) {
      if (!on) continue;
      let n = 0;
      for (const o of fullOids) if (skip === "nar" ? pass(factsOf(o), null) : pass(factsOf(o), skip) && inAllNarrow(o, idx)) n++;
      if (n) out.push([name, n]);
    }
    return out.sort((a, b) => b[1] - a[1]);
  }
  function keptHTML() {
    if (!PERSIST || !ST.kept || !keptN()) return "";
    return `<div class="fkept" data-kept="1"><span>Filters kept from the last group:</span><b>${esc2(keptText())}</b><button type="button" class="flink" data-f="clear">Clear all</button></div>`;
  }
  function emptyHTML(fullOids, shown, ctx, idx) {
    if (!PERSIST || shown || !fullOids.length || !active() || (ctx && ctx.sugg)) return "";
    const dc = dropCounts(fullOids, idx);
    return `<div class="fempty" data-empty="1"><b>No cards match these filters.</b> ${fmt(fullOids.length)} card${fullOids.length === 1 ? " is" : "s are"} in this group.` +
      (dc.length ? ` Without ${dc.slice(0, 3).map(([n, c]) => `<u>${esc2(n.toLowerCase())}</u> it would show ${fmt(c)}`).join("; without ")}.` : "") + ` <button type="button" class="flink" data-f="clear">Clear all filters</button></div>`;
  }
  const BASIS_MODE_NOTE = { any: "Any of these: the identity has at least one of the chosen colours.", all: "Includes all: the identity has every chosen colour.", only: "Only these: the identity is inside the chosen colours. Colourless cards need ◇ on as well.", exactly: "Exactly these: the identity is the chosen colours and no others.", not: "Not these: the identity has none of the chosen colours." };
  function basisHTML() {
    const b = (v, n) => `<button type="button" role="radio" class="fch cm${BASIS === v ? " on" : ""}" data-f="basis" data-v="${v}" aria-checked="${BASIS === v}">${n}</button>`;
    const note = CIFAIL ? "Colour identity could not be loaded, so the card’s own colour is used." : BASIS === "identity" ? "Colour identity: the colours in the cost and rules text, as Commander counts them. A Forest is green." + (CMODES && ST.cols.size ? " " + BASIS_MODE_NOTE[ST.cmode] : "") : "Card colour, not colour identity. A Forest is colourless.";
    return `<div class="frow"><span class="flab">Based on</span><div class="fgrp cbseg" role="radiogroup" aria-label="Colour based on">${b("card", "Card colour")}${b("identity", "Colour identity")}</div></div><div class="fnote" data-basis-note="1">${note}</div>`;
  }
  function modeOptions() { return CMODE_NAMES.map(([v, n]) => `<option value="${v}"${ST.cmode === v ? " selected" : ""}>${n}</option>`).join(""); }
  function subRow() {
    if (!(TGON && window.TG && TG.enabled)) return "";
    if (!TG.ready()) { TG.loadIndex().then(() => { try { refresh(); } catch (e) { /* page changed */ } }); return ""; }
    const chips = [...ST.subs].map(k => `<button type="button" class="fch on x" data-f="subx" data-v="${esc2(k)}" title="Remove: ${esc2(TG.name(k))}">${esc2(TG.name(k))}</button>`).join("");
    return `<div class="frow"><span class="flab">Subtype</span><div class="fgrp">${chips}<select class="fsel" data-f="sub" aria-label="Add a subtype or supertype"><option value="">Add a subtype or supertype…</option>${TG.options(ST.subs)}</select></div></div>` +
      `<div class="fnote">Any of the chosen. A card counts if either face has it.</div>`;
  }
  function abRows() {
    if (!(ABON && window.AP && AP.enabled)) return "";
    if (!AP.ready()) { AP.loadIndex().then(() => { try { refresh(); } catch (e) { /* page changed */ } }); return ""; }
    const lab = { trig: "Add a trigger…", cost: "Add a cost…", kind: "Add a static or replacement kind…" };
    return AP.rows.map(([r, label]) => {
      const chips = [...ST.ab[r]].map(k => `<button type="button" class="fch on x" data-f="abx" data-r="${r}" data-v="${esc2(k)}" title="Remove: ${esc2(AP.name(k))}">${esc2(AP.name(k))}</button>`).join("");
      return `<div class="frow"><span class="flab">${label}</span><div class="fgrp">${chips}<select class="fsel" data-f="ab" data-r="${r}" aria-label="${lab[r]}"><option value="">${lab[r]}</option>${AP.options(r, ST.ab[r])}</select></div></div>`;
    }).join("") + `<div class="fnote">Trigger, Cost and Kind: any of the chosen inside a row, all rows together. Cards the parser couldn’t read aren’t included.</div>`;
  }
  function popSortHTML(ctx) {
    const cur = sortMode(ctx && ctx.sugg ? "sugg" : "list"), o = [["pop", "Most popular first"], ["best", "Default order"], ["mv", "Mana value"], ["name", "Name"]];
    return `<select class="fsel" data-f="sort" aria-label="Sort">${o.map(([v, n]) => `<option value="${v}"${cur === v ? " selected" : ""}>${n}</option>`).join("")}</select>` +
      `<div class="fnote" data-pop-note="1">Popularity is each card’s EDHREC rank (how often it is played in Commander decks, from Scryfall). Cards with no rank come last.</div>`;
  }
  function barHTML(fullOids, shown, ctx) {
    const idx = buildIndex(), fc = facetCounts(fullOids, idx);
    const mOff = CMODES && ST.cmode === "only";
    const pipHTML = COLS.map(([c, n]) => {
      const off = mOff && c === "M";
      return `<button type="button" class="fpip p${c}${ST.cols.has(c) ? " on" : ""}${(!fc.cc[c] && !ST.cols.has(c)) || off ? " dim" : ""}" data-f="col" data-v="${c}" aria-pressed="${ST.cols.has(c)}"${off ? ' aria-disabled="true"' : ""} aria-label="${n}, ${fc.cc[c]} cards" ` +
        `title="${off ? "Multicolour can’t be combined with Only these. Pick the colours instead, for example W and U for white-blue cards." : `${n} (${fc.cc[c]})`}">${c === "C" ? "◇" : c}</button>`;
    }).join("");
    const modeHTML = CMODES ? `<div class="frow cmrow"><span class="flab">Match</span><div class="fgrp cmseg" role="radiogroup" aria-label="Colour match">` +
      CMODE_NAMES.map(([v, n]) => `<button type="button" role="radio" class="fch cm${ST.cmode === v ? " on" : ""}" data-f="cmode" data-v="${v}" aria-checked="${ST.cmode === v}">${n}</button>`).join("") +
      `</div><select class="fsel cmsel" data-f="cmodesel" aria-label="Colour match">${modeOptions()}</select></div>` : "";
    const typeHTML = TYPES.filter(t => fullOids.some(o => factsOf(o).ts.indexOf(t) >= 0) || ST.types.has(t)).map(t => `<button type="button" class="fch${ST.types.has(t) ? " on" : ""}${!fc.tc[t] && !ST.types.has(t) ? " dim" : ""}" data-f="type" data-v="${t}" aria-pressed="${ST.types.has(t)}">${t} <b>${fmt(fc.tc[t])}</b></button>`).join("");
    const mvHTML = MVS.map(([m, n]) => `<button type="button" class="fch${ST.mvs.has(m) ? " on" : ""}${!fc.mc[m] && !ST.mvs.has(m) ? " dim" : ""}" data-f="mv" data-v="${m}" aria-pressed="${ST.mvs.has(m)}">${n} <b>${fmt(fc.mc[m])}</b></button>`).join("");
    const sortHTML = POP ? popSortHTML(ctx) : `<select class="fsel" data-f="sort" aria-label="Sort"><option value="best"${ST.sort === "best" ? " selected" : ""}>Best match</option><option value="mv"${ST.sort === "mv" ? " selected" : ""}>Mana value</option><option value="name"${ST.sort === "name" ? " selected" : ""}>Name</option></select>`;
    const status = `Showing <b>${fmt(shown)}</b> of ${fmt(fullOids.length)}`;
    const sm = summary(idx);
    const nr = narrowHTML(ctx.list, fullOids, ctx.key, idx);
    const nline = BKON && BKDOC ? `${nr.count} topic${nr.count === 1 ? "" : "s"}${ST.nar.length + ST.bk.size ? " · " + (ST.nar.length + ST.bk.size) + " on" : ""}` :
      NNC ? `${nr.count} group${nr.count === 1 ? "" : "s"}${ST.nar.length ? " · " + ST.nar.length + " on" : ""}` : (ST.nar.length ? ST.nar.length + " on" : "none on");
    return `<div class="fwrap" data-open="${ST.open ? 1 : 0}" data-nopen="${ST.nopen ? 1 : 0}">` + keptHTML() +
      `<button type="button" class="fsum" data-f="fold" aria-expanded="${ST.open}"><span>Filter and sort</span><span class="fpills">${esc2(sm) || "none on"}</span><span>${status}</span><span aria-hidden="true">${ST.open ? "▾" : "▸"}</span></button>` +
      `<div class="fbar"><div class="frow"><span class="flab">Colour</span><div class="fgrp">${pipHTML}</div></div>${CIDON ? basisHTML() : ""}${modeHTML}${CIDON ? "" : `<div class="fnote">Card colour, not colour identity</div>`}` +
      `<div class="frow"><span class="flab">Type</span><div class="fgrp">${typeHTML}</div></div>` + subRow() + abRows() +
      `<div class="frow"><span class="flab">Mana value</span><div class="fgrp">${mvHTML}</div></div>` +
      `<div class="frow"><span class="flab">Sort</span>${sortHTML}</div>` +
      `<div class="fstat"><span>${status}</span>${active() ? `<button type="button" class="flink" data-f="clear">${PERSIST ? "Clear all" : "Clear filters"}</button>` : ""}</div></div>` +
      (nr.html ? `<button type="button" class="fsum" data-f="nfold" aria-expanded="${ST.nopen}"><span>Narrow by group</span><span class="fpills">${nline}</span><span aria-hidden="true">${ST.nopen ? "▾" : "▸"}</span></button>` + nr.html : "") + emptyHTML(fullOids, shown, ctx, idx) + `</div>`;
  }
  // the chips for the list as it stands: with NARROW_NO_CUT the floor is 2 (1 with "Show single-card groups"), at most 60; otherwise the rule the page always had
  function chipSet(list, pageOids, key) {
    const all = chipsFor(list, pageOids, key);
    if (!NNC) return { all: all, vis: all, singles: 0 };
    const main = all.filter(c => c.n >= 2);
    return { all: all, vis: (ST.single ? all : main).slice(0, 60), total: (ST.single ? all : main).length, singles: all.length - main.length };
  }
  // BROAD_NARROWING: the topic chips, a dropdown of specific groups under each chosen topic, and "Show all groups" for the flat chips
  function topicsHTML(list, pageOids, key, idx) {
    const cs = chipSet(list, pageOids, key), N = list.length, names = BKDOC.b;
    const rows = [];
    for (let b = 0; b < names.length; b++) {
      const on = ST.bk.has(b);
      let n = 0;
      if (on) n = N; else { const set = bkSet(b); for (const o of list) if (set.has(o)) n++; }
      if (!on && (n === 0 || n * 10 >= N * 9)) continue;
      rows.push({ b: b, n: n, on: on });
    }
    rows.sort((x, y) => y.n - x.n || x.b - y.b);
    const chH = rows.map(r => `<button type="button" class="fch${r.on ? " on x" : ""}" data-f="bk" data-v="${r.b}" aria-pressed="${r.on}" title="${esc2(names[r.b][2])} ${fmt(r.n)} cards are in any group of this topic, including groups with one card; this is not the sum of the groups listed.">${esc2(names[r.b][1])} <b>${fmt(r.n)}</b></button>`).join("");
    let subs = "";
    for (const [b, specs] of ST.bk) {
      const skipList = pageOids.filter(o => pass(factsOf(o), null) && inAllNarrow(o, idx, b));
      const any = skipList.filter(o => bkSet(b).has(o)).length;
      const cand = chipsFor(skipList, pageOids, key).filter(c => (bkMask(c.key) >> b & 1) && specs.indexOf(c.key) < 0);
      const main = cand.filter(c => c.n >= 2), singles = cand.length - main.length, vis = ST.single ? cand : main;
      const opt = c => `<option value="${esc2(c.key)}">${c.loose ? "\u25cc " : ""}${esc2(c.label)} (${fmt(c.n)})</option>`;
      const chk = vis.filter(c => !c.loose).map(opt).join(""), lo = vis.filter(c => c.loose).map(opt).join("");
      const chosen = specs.map(k => `<button type="button" class="fch on x${idx.loose.get(k) ? " lo" : ""}" data-f="bksx" data-b="${b}" data-v="${esc2(k)}" title="Remove: ${esc2(idx.name.get(k))}">${esc2(clean(idx.name.get(k)))}</button>`).join("");
      subs += `<div class="nsub" data-topic="${b}"><div class="frow"><span class="flab">${esc2(names[b][1])}</span>${chosen}</div>` +
        `<div class="fnote nl">${specs.length ? "Any of the chosen groups." : `Any group in it: ${fmt(any)} cards, counting groups with one card.`}</div>` +
        `<div class="fgrp"><select class="fsel" data-f="bks" data-b="${b}" aria-label="Add a specific group in ${esc2(names[b][1])}"><option value="">Add a specific group…</option>` +
        (chk ? `<optgroup label="Checked groups">${chk}</optgroup>` : "") + (lo ? `<optgroup label="Grouped loosely (not checked)">${lo}</optgroup>` : "") + `</select>` +
        (singles || ST.single ? `<button type="button" class="flink" data-f="single">${ST.single ? "Hide single-card groups" : `Show single-card groups (${fmt(singles)})`}</button>` : "") + `</div></div>`;
    }
    const none2 = cs.all.filter(c => !bkMask(c.key) && c.n >= 2).length, none1 = cs.all.filter(c => !bkMask(c.key) && c.n < 2).length;
    const noneT = none2 || none1 ? `${fmt(none2)} group${none2 === 1 ? "" : "s"} here fit${none2 === 1 ? "s" : ""} no topic${none1 ? ` (${fmt(none1)} more with one card)` : ""}.` : "";
    const selH = ST.nar.map(k => `<button type="button" class="fch on x${idx.loose.get(k) ? " lo" : ""}" data-f="narx" data-v="${esc2(k)}" title="Remove: ${esc2(idx.name.get(k))}">${esc2(clean(idx.name.get(k)))}</button>`).join("");
    let flat = "";
    if (ST.bshow) {
      const chips = cs.vis, shown = chips.slice(0, ST.nshow);
      const fh = shown.map(c => `<button type="button" class="fch${c.loose ? " lo" : ""}" data-f="nar" data-v="${esc2(c.key)}" title="${esc2(idx.name.get(c.key))}">${esc2(c.label)} <b>${fmt(c.n)}</b></button>`).join("");
      const more = chips.length > shown.length ? `<button type="button" class="flink" data-f="nmore">Show more (${shown.length} of ${chips.length} shown)</button>` : "";
      const single = cs.singles || ST.single ? `<button type="button" class="flink" data-f="single">${ST.single ? "Hide single-card groups" : `Show single-card groups (${fmt(cs.singles)})`}</button>` : "";
      flat = `<div class="frow"><span class="flab">All groups</span></div><div class="fgrp">${fh}${more}${single}</div><div class="fnote nl">Every group, as before. Picking several here keeps only cards that are in all of them. Counts are for the cards showing now. Dashed means grouped loosely.</div>`;
    }
    return { count: rows.length, html: `<div class="nrow"><div class="frow"><span class="flab">Narrow by group</span>${selH}${ST.nar.length || ST.bk.size ? `<button type="button" class="flink" data-f="nclear">Clear</button>` : ""}</div>` +
      `<div class="fgrp">${chH}</div>${subs}` +
      `<div class="fnote nl">A topic is a set of groups, and a group can be in several. The number is how many of these cards are in any group of it. Topics together: a card must be in all of them. Groups inside one topic: any of them.</div>` +
      `<div class="fstat"><span class="fnote nl">${noneT}</span><button type="button" class="flink" data-f="bkall">${ST.bshow ? "Hide all groups" : "Show all groups"}</button></div>${flat}</div>` };
  }
  function narrowHTML(list, pageOids, key, idx) {
    if (BKON) { bkLoad(); if (BKDOC) return topicsHTML(list, pageOids, key, idx); }
    const cs = chipSet(list, pageOids, key), chips = cs.vis;
    if (!chips.length && !ST.nar.length && !(NNC && cs.singles)) { if (!NNC) return { html: "", count: 0 }; }
    const selH = ST.nar.map(k => `<button type="button" class="fch on x${idx.loose.get(k) ? " lo" : ""}" data-f="narx" data-v="${esc2(k)}" title="Remove: ${esc2(idx.name.get(k))}">${esc2(clean(idx.name.get(k)))}</button>`).join("");
    const shown = chips.slice(0, ST.nshow);
    const chH = shown.map(c => `<button type="button" class="fch${c.loose ? " lo" : ""}" data-f="nar" data-v="${esc2(c.key)}" title="${esc2(idx.name.get(c.key))}">${esc2(c.label)} <b>${fmt(c.n)}</b></button>`).join("");
    const more = chips.length > shown.length ? `<button type="button" class="flink" data-f="nmore">Show more (${shown.length} of ${chips.length} shown)</button>` : "";
    let note = "Counts are for the cards showing now. Dashed means grouped loosely.";
    if (NNC) {
      if (!chips.length) note = "No other group has 2 or more of these cards. " + note;
      if (cs.total > 60) note += ` Showing the 60 groups with the most cards of ${fmt(cs.total)}.`;
    }
    const single = NNC && (cs.singles || ST.single) ? `<button type="button" class="flink" data-f="single">${ST.single ? "Hide single-card groups" : `Show single-card groups (${fmt(cs.singles)})`}</button>` : "";
    return { count: NNC ? cs.total : chips.length, html: `<div class="nrow"><div class="frow"><span class="flab">Narrow by group</span>${selH}${ST.nar.length ? `<button type="button" class="flink" data-f="nclear">Clear</button>` : ""}</div>` +
      `<div class="fgrp">${chH}${more}${single}</div><div class="fnote">${note}</div></div>` };
  }

  // ---------------------------------------------------------------- the members list
  let FULL = [], LISTKEY = "";
  function renderBarInto(host, fullOids, shown, list, key) { host.innerHTML = barHTML(fullOids, shown, { list: list, key: key }); }
  function applyList() {
    const P = $("panel"), host = $("fwrap");
    if (!host) return;
    const fullOids = uniq(FULL.map(oidOf).filter(o => o != null));
    const idx = buildIndex();
    BKCTX = { full: fullOids, key: LISTKEY };
    const items = filterItems(FULL);
    const list = uniq(items.map(oidOf).filter(o => o != null));
    LIST = items; LISTN = 0;
    const el = $("list");
    if (el) { el.innerHTML = ""; renderList(); }
    renderBarInto(host, fullOids, list.length, list, LISTKEY);
    pinNote(list);
    if (typeof window.QMB_REFRESH === "function") window.QMB_REFRESH();                       // feature QUERY_MATCH_BLOCK: the block follows the filters
    void P; void idx;
  }
  function barOnly() {
    if (SCCUR && SCCUR.tab === "matches") { scRender(); return; }
    const host = $("fwrap");
    if (!host) return;
    const fullOids = uniq(FULL.map(oidOf).filter(o => o != null)), list = uniq(LIST.map(oidOf).filter(o => o != null));
    BKCTX = { full: fullOids, key: LISTKEY };
    renderBarInto(host, fullOids, list.length, list, LISTKEY);
  }
  function pinNote(list) {
    const w = $("pinwrap"); if (!w) return;
    const old = w.querySelector(".pinfilt"); if (old) old.remove();
    if (PINCUR && active() && !list.includes(PINCUR) && FULL.some(x => oidOf(x) === PINCUR)) w.insertAdjacentHTML("beforeend", PERSIST ? `<div class="sub pinfilt">Hidden by your filters (${esc2(keptText() || summary(buildIndex()))}). <button type="button" class="flink" data-f="clear">Clear all filters</button></div>` : `<div class="sub pinfilt">Hidden by your filters. <button type="button" class="flink" data-f="clear">Clear filters</button></div>`);
  }
  const _setList = setList;
  setList = function (head, items, opts) {
    if (BKON) bkLoad();                                                                        // ask for the topic map before the card pictures start to download
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
    BKCTX = { full: all, key: key };
    const keepA = rowsA.filter(r => pass(factsOf(r.oid), null) && inAllNarrow(r.oid, idx)), keepB = rowsB.filter(r => pass(factsOf(r.oid), null) && inAllNarrow(r.oid, idx));
    const sm = sortMode("sugg");
    const ord = rows => sm === "best" ? rows : sm === "pop" ? rows.slice().sort((x, y) => popCmp(x.oid, y.oid)) : rows.slice().sort((x, y) => { const p = factsOf(x.oid), q = factsOf(y.oid); return sm === "name" ? cmp(p.nm, q.nm) || cmp(x.oid, y.oid) : (p.mv == null) - (q.mv == null) || (p.mv || 0) - (q.mv || 0) || cmp(p.nm, q.nm) || cmp(x.oid, y.oid); });
    const A = ord(keepA), B = ord(keepB), shownList = uniq(A.map(r => r.oid).concat(B.map(r => r.oid)));
    SUGLIST = all;
    return { A: A, B: B, bar: `<div id="fwrap2">` + barHTML(all, shownList.length, { list: shownList, key: key, sugg: true }) + `</div>` };
  }

  // ---------------------------------------------------------------- events
  function refresh() {
    saveP();
    if (SCCUR && SCCUR.tab === "matches") { scRender(); return; }
    applyList();
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-f]");
    if (!b || !$("panel").contains(b)) return;
    const f = b.dataset.f, v = b.dataset.v;
    if (b.getAttribute("aria-disabled") === "true") { e.stopPropagation(); return; }           // the multicolour chip under "Only these"
    if (f === "col" || f === "type" || f === "mv") { const s = f === "col" ? ST.cols : f === "type" ? ST.types : ST.mvs; if (s.has(v)) s.delete(v); else s.add(v); }
    else if (f === "cmode") { ST.cmode = v; if (v === "only") ST.cols.delete("M"); }
    else if (f === "basis" && CIDON) { BASIS = v === "card" ? "card" : "identity"; try { localStorage.setItem("colourBasis", BASIS); } catch (err) { /* storage unavailable: the choice lasts for this page only */ } }
    else if (f === "subx") ST.subs.delete(v);
    else if (f === "abx") { for (const r of ["trig", "cost", "kind"]) ST.ab[r].delete(v); }
    else if (f === "single") { ST.single = !ST.single; }
    else if (f === "nar") { if (!ST.nar.includes(v)) ST.nar.push(v); }
    else if (f === "narx") ST.nar = ST.nar.filter(k => k !== v);
    else if (f === "nclear") { ST.nar = []; ST.bk.clear(); }
    else if (f === "bk") { const t = Number(v); if (ST.bk.has(t)) ST.bk.delete(t); else ST.bk.set(t, []); }
    else if (f === "bksx") { const t = Number(b.dataset.b), a = ST.bk.get(t); if (a) ST.bk.set(t, a.filter(k => k !== v)); }
    else if (f === "bkall") ST.bshow = !ST.bshow;
    else if (f === "nmore") ST.nshow = Math.min(NNC ? 60 : 1e9, ST.nshow + 12);
    else if (f === "clear") { ST.cols.clear(); ST.types.clear(); ST.subs.clear(); for (const r of ["trig", "cost", "kind"]) ST.ab[r].clear(); ST.mvs.clear(); ST.nar = []; ST.bk.clear(); ST.cmode = DEFMODE; ST.kept = false; }
    else if (f === "fold") ST.open = !ST.open;
    else if (f === "nfold") ST.nopen = !ST.nopen;
    else return;
    e.stopPropagation();
    refresh();
  }, true);
  document.addEventListener("change", e => {
    const s = e.target.closest && e.target.closest("select[data-f]");
    if (!s || !$("panel").contains(s)) return;
    if (s.dataset.f === "sort") { ST.sort = s.value; if (POP) { try { localStorage.setItem("sortPref", s.value); } catch (err) { /* storage unavailable: the choice lasts for this page only */ } } refresh(); }
    else if (s.dataset.f === "cmodesel") { ST.cmode = s.value; if (s.value === "only") ST.cols.delete("M"); refresh(); }
    else if (s.dataset.f === "ab" && ABON) { const v = s.value, r = s.dataset.r; if (v && ST.ab[r]) AP.loadPages([v]).then(() => { ST.ab[r].add(v); refresh(); }); }
    else if (s.dataset.f === "bks" && BKON) { const v = s.value, t = Number(s.dataset.b), a = ST.bk.get(t); if (v && a && a.indexOf(v) < 0) { a.push(v); refresh(); } }
    else if (s.dataset.f === "sub") { const v = s.value; if (v) TG.loadMembers().then(() => { ST.subs.add(v); refresh(); }); }
  }, true);
  const _scSetTab = scSetTab;
  scSetTab = async function (tab) { await _scSetTab(tab); if (tab === "members") { try { applyList(); } catch (e) { /* no bar on this page */ } } };

  // PERSIST_FILTERS: a card opened by a search or a link is pinned after the list is drawn; if the kept filters hide it, it stays in its pinned row and the note names the filters
  // (browse.html's own "not listed in this group any more" note is for a card removed from the group, which this is not)
  if (PERSIST && typeof pinAfter === "function") {
    const _pinAfter = pinAfter;
    pinAfter = async function (k, oid) {
      await _pinAfter(k, oid);
      try {
        if (PINCUR && active() && FULL.some(x => oidOf(x) === PINCUR)) {
          const list = uniq(LIST.map(oidOf).filter(o => o != null));
          if (!list.includes(PINCUR)) { const n = document.querySelector("#pinwrap .pinnote"); if (n) n.remove(); pinNote(list); }
        }
      } catch (e) { if (window.console) console.error("filters", e); }
    };
  }
  if (CIDON) ciLoad();

  window.TF = { enabled: true, sugg: sugg, items: () => FULL.slice(), shownItems: () => LIST.slice(), refresh: refresh, state: () => ST, full: () => uniq(FULL.map(oidOf).filter(o => o != null)), shown: () => uniq(LIST.map(oidOf).filter(o => o != null)),
    chips: () => { const idx = buildIndex(), full = uniq(FULL.map(oidOf).filter(o => o != null)); return chipSet(uniq(LIST.map(oidOf).filter(o => o != null)), full, LISTKEY).vis.map(c => ({ key: c.key, label: c.label, n: c.n, name: idx.name.get(c.key), loose: c.loose })); },
    chipsAll: () => { const idx = buildIndex(), full = uniq(FULL.map(oidOf).filter(o => o != null)); return chipsFor(uniq(LIST.map(oidOf).filter(o => o != null)), full, LISTKEY).map(c => ({ key: c.key, label: c.label, n: c.n, size: c.size, name: idx.name.get(c.key) })); },
    topics: () => (BKDOC ? { doc: BKDOC, mask: bkMask, set: bkSet, state: () => [...ST.bk].map(([b, a]) => [b, a.slice()]) } : null),
    members: key => buildIndex().mem.get(key) || new Set(), reset: () => { ST = fresh(); ST.k = selected; },
    colOk: colOk, facts: oid => { const f = factsOf(oid); return { col: f.col, id: idOn() ? colourOf(f) : null, ts: f.ts.slice(), mv: f.mv }; },
    basis: () => (idOn() ? "identity" : "card"), identityState: () => ({ on: CIDON, basis: BASIS, loaded: !!CIDOC, failed: CIFAIL }), kept: () => keptText(), saved: () => PMEM,
    invalidate: () => { FACTS.clear(); },                                              // FLIP_FACES: the faces arrived after the first facts were read
    // FLIP_FACES: which face is the reason a card is in the list now: "" (the face the page lists passes, or no filter is on), or a note naming the other face
    faceNote: oid => {
      if (!(window.FL && FL.on()) || !(ST.cols.size || ST.types.size)) return "";
      const fl = FL.get(oid); if (!fl) return "";
      const ok = (col, ty) => (!ST.cols.size || idOn() || colOk(col, ST.cols, ST.cmode)) && (!ST.types.size || typesOf(ty).some(t => ST.types.has(t)));
      if (ok(fl.f[fl.pf].c, fl.f[fl.pf].ty)) return "";
      for (let i = 0; i < fl.f.length; i++) if (i !== fl.pf && ok(fl.f[i].c, fl.f[i].ty)) return "matched on its other face: " + fl.f[i].n;
      return "matched across both faces";
    } };
})();
