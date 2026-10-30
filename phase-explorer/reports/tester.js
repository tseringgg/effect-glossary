/* Tester mode for reports/browse.html: a presentation layer over the same data. Written into the page (document.write) only when ?dev=1 is absent, so ?dev=1 is the page exactly as it always was.
 *
 * It does not change a leaf, a group, an id, a placement, a suggestion, a count or a figure: it re-lays the page out (top bar, left column, drawer, card modal), trims headers and labels, hides the editing
 * and logging UI, and replaces the few things that need a server: no POST and no endpoint ping is ever made; hand placements come from build/hand_view.json (card id and group id only, written by
 * src/export_static.py), never from corrections/. Global names (TAX, MI, show, find, renderTree ...) are browse.html's own: its classic script shares one global scope with this file.
 */
"use strict";
(function () {
  const CFG = { feedbackUrl: "", prefill: "clipboard", titleParam: "title", bodyParam: "body", TESTER_FILTERS: false, TYPE_GROUPS: false, FLIP_FACES: false, DEFAULT_POPULARITY: false, ACTIVE_GROUP_HIGHLIGHT: false, QUERY_MATCH_BLOCK: false, ABILITY_TYPE_PAGES: false, ABILITY_TYPE_FILTERS: false, MODAL_ABILITIES: false };
  const $ = id => document.getElementById(id);
  const mobile = () => window.matchMedia("(max-width: 800px)").matches;
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  document.body.classList.add("tester");
  document.title = "LogicVoid’s Deck Doctor";
  try { const l = document.createElement("link"); l.rel = "icon"; l.href = "data:,"; document.head.appendChild(l); } catch (e) { /* ignore */ }

  // ---------------------------------------------------------------- defaults: every switch at today's default (on); nothing remembered from an earlier dev session
  SHOWT = true; SHOWA = true; SHOWTAG = true; SHOWSIB = true; SHOWBATCH = false; SHOWH = true; HIDE = true;
  SCFLOOR = 0.70; SCINC = false; SCTAB = "members"; VIEW = "images";
  for (const [id, v] of [["hidenopic", HIDE], ["showtent", SHOWT], ["showann", SHOWA], ["showtag", SHOWTAG], ["showsib", SHOWSIB], ["showbatch", SHOWBATCH], ["showhand", SHOWH]]) $(id).checked = v;
  for (const k of Object.keys(UNSAVED)) delete UNSAVED[k];
  BUNSAVED = null;

  // ---------------------------------------------------------------- shell: top bar, left column (search, results, tree), footer, drawer
  const nav = document.querySelector("nav"), Q = $("q"), FR = $("findres"), TREE = $("tree"), PANEL = $("panel");
  const tbar = el("div", "tbar",
    `<button class="menu" id="tmenu" type="button" aria-label="Find and browse" aria-expanded="false" aria-controls="tnav">☰ <span>Find</span></button>` +
    `<span class="brand">LogicVoid’s Deck Doctor</span><span class="sp"></span>` +
    `<button class="tlink hide-m" id="thow" type="button">How this works</button><a id="trep" data-report="page" target="_blank" rel="noopener noreferrer" href="#">Report a problem</a>`);
  document.body.insertBefore(tbar, document.body.firstChild);
  const sbox = el("div", "sbox", `<label for="q" class="sr-only">Search cards and groups</label>`);
  Q.placeholder = "Search a card or a group, e.g. “board wipe”";
  sbox.appendChild(Q);
  const clr = el("button", "sclr", "×"); clr.type = "button"; clr.setAttribute("aria-label", "Clear the search"); clr.hidden = true;
  sbox.appendChild(clr);
  nav.id = "tnav";
  nav.insertBefore(sbox, nav.firstChild);
  sbox.after(FR);
  const treewrap = el("div"); treewrap.id = "treewrap";
  const treebar = el("button", "treebar", `<span>Browse all groups</span><span id="treearrow">▾</span>`); treebar.type = "button"; treebar.setAttribute("aria-expanded", "true");
  nav.appendChild(treewrap); treewrap.appendChild(treebar); treewrap.appendChild(TREE);
  const scrim = el("div", "tscrim"); document.body.appendChild(scrim);
  const tfoot = el("footer", "tfoot",
    `Card data and images from <a href="https://scryfall.com" target="_blank" rel="noopener noreferrer">Scryfall</a>. Magic: The Gathering card names, text and art are property of Wizards of the Coast. ` +
    `This site is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC. ` +
    `<button class="tlink" type="button" data-how="1">How this works and credits</button> · <a data-report="page" target="_blank" rel="noopener noreferrer" href="#">Report a problem</a>`);
  $("foot").after(tfoot);
  const modal = el("div", "tmodal"); modal.hidden = true; modal.setAttribute("role", "dialog"); modal.setAttribute("aria-modal", "true"); document.body.appendChild(modal);
  const toast = el("div", "ttoast"); toast.hidden = true; toast.setAttribute("role", "status"); document.body.appendChild(toast);

  let TREEOPEN = true, SEARCHING = false;
  function applyTree() { treewrap.classList.toggle("folded", !TREEOPEN); treebar.setAttribute("aria-expanded", TREEOPEN ? "true" : "false"); $("treearrow").textContent = TREEOPEN ? "▾" : "▸"; }
  treebar.addEventListener("click", () => { TREEOPEN = !TREEOPEN; applyTree(); });
  Q.addEventListener("input", () => {
    const now = Q.value.trim() !== "";
    clr.hidden = !now;
    if (now !== SEARCHING) { SEARCHING = now; TREEOPEN = !now; applyTree(); }
  });
  clr.addEventListener("click", () => { Q.value = ""; Q.dispatchEvent(new Event("input", { bubbles: true })); Q.focus(); });
  function drawer(open) {
    document.body.classList.toggle("drawer-open", open);
    $("tmenu").setAttribute("aria-expanded", open ? "true" : "false");
    if (open) Q.focus();
  }
  $("tmenu").addEventListener("click", () => drawer(!document.body.classList.contains("drawer-open")));
  scrim.addEventListener("click", () => drawer(false));
  window.addEventListener("resize", () => { if (!mobile()) drawer(false); });

  // ---------------------------------------------------------------- dialogs (card, how this works, report copy fallback)
  let MODALFOR = null;
  function openModal(html, narrow) {
    modal.innerHTML = `<div class="tbox${narrow ? " narrow" : ""}"><button class="tclose" type="button" aria-label="Close">×</button>${html}</div>`;
    modal.hidden = false;
    const c = modal.querySelector(".tclose"); if (c) c.focus();
  }
  function closeModal() { modal.hidden = true; modal.innerHTML = ""; MODALFOR = null; }
  modal.addEventListener("click", e => {
    if (e.target === modal || e.target.closest(".tclose")) { closeModal(); return; }
    const how = e.target.closest("[data-how]"); if (how) { showHow(); return; }
    const go = e.target.closest("[data-go]");
    if (go) {
      const oid = MODALFOR; closeModal();
      if (oid && PINON && !/^(ab|yk):/.test(go.dataset.go)) { PINNEXT = oid; SCWANT = { k: go.dataset.go, tab: "members" }; }       // an ability or keyword page (feature MODAL_ABILITIES) has no pin and no tab: nothing is left set for a later page
      show(go.dataset.go);
    }
  });
  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    if (!modal.hidden) { closeModal(); return; }
    if (document.body.classList.contains("drawer-open") && document.activeElement !== Q) drawer(false);
    else if (document.body.classList.contains("drawer-open")) drawer(false);
  });
  let toastTimer = null;
  function say(t) { toast.textContent = t; toast.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { toast.hidden = true; }, 5000); }

  // ---------------------------------------------------------------- Report a problem
  let TCUR = { k: "", name: "" };
  function reportText(src) {
    const L = ["Problem report"];
    const card = src.card || "", group = src.group != null ? src.group : TCUR.name;
    L.push("Card: " + (card || "(none)")); L.push("Group: " + (group || "(none)"));
    const q = src.q != null ? src.q : Q.value.trim();
    if (q) L.push("Searched for: " + q);
    L.push("Page: " + location.href); L.push("What looks wrong: ");
    return L.join("\n");
  }
  function execCopy(text) {
    try {
      const t = el("textarea"); t.value = text; t.setAttribute("readonly", ""); t.style.cssText = "position:fixed;left:-9999px;top:0";
      document.body.appendChild(t); t.select(); const ok = document.execCommand && document.execCommand("copy"); t.remove(); return !!ok;
    } catch (e) { return false; }
  }
  async function copyReport(text) {
    try { await navigator.clipboard.writeText(text); say("Report copied. Paste it into the feedback channel."); return true; } catch (e) { /* fall through */ }
    if (execCopy(text)) { say("Report copied. Paste it into the feedback channel."); return true; }
    const keep = MODALFOR;
    openModal(`<div class="tinfo"><h2>Copy this report</h2><p>It could not be copied for you. Select the text, copy it, and paste it into the feedback channel.</p><textarea id="treptext" readonly></textarea></div>`, true);
    MODALFOR = keep;
    const ta = $("treptext"); ta.value = text; ta.focus(); ta.select();
    return false;
  }
  document.addEventListener("click", e => {
    const a = e.target.closest("[data-report]");
    if (!a) return;
    const kind = a.dataset.report, src = {};
    if (kind === "card") { const c = CARDS && CARDS[a.dataset.oid]; src.card = c ? c.n : ""; }
    if (kind === "miss") { src.q = a.dataset.q; src.card = ""; src.group = ""; }
    const text = reportText(src);
    if (!CFG.feedbackUrl) { e.preventDefault(); copyReport(text); return; }
    if (CFG.prefill === "query") {
      const u = CFG.feedbackUrl + (CFG.feedbackUrl.indexOf("?") >= 0 ? "&" : "?") + encodeURIComponent(CFG.titleParam) + "=" + encodeURIComponent("Problem: " + (src.card || (src.group != null ? src.group : TCUR.name) || "report")) + "&" + encodeURIComponent(CFG.bodyParam) + "=" + encodeURIComponent(text);
      a.href = u; return;
    }
    a.href = CFG.feedbackUrl;
    copyReport(text);
  });
  $("thow").addEventListener("click", () => showHow());
  document.addEventListener("click", e => { const h = e.target.closest("[data-how]"); if (h && !modal.contains(h)) showHow(); });

  // ---------------------------------------------------------------- how this works (the honest quality note; every figure is read from the page's own data)
  function showHow() {
    const t = TAX ? TAX.totals : null, pct = o => (o ? String(o[1] != null ? o[1] : o.pct) + "%" : "");
    const p1 = v => Number(v).toFixed(1) + "%";
    let a = t ? p1(t.headline.pct) : "", b = "", rows = "";
    if (t) {
      const fig = (v, why) => `<tr><td><b>${p1(v)}</b></td><td>${why}</td></tr>`;
      rows += fig(t.headline.pct, `of ${t.in_scope.toLocaleString("en-US")} cards are in a group the tool has checked.`);
      rows += fig(t.with_broad.pct, "also counting groups broader than their names say.");
      if (TENT && TENT.meta.headline) rows += fig(TENT.meta.headline.with_tentative[1], "also counting best-guess groups.");
      if (ANN && ANN.meta.headline) { rows += fig(ANN.meta.headline.with_annotation[1], "also counting cards with a part of their text we could not read."); rows += fig(ANN.meta.headline.with_gap_stratum[1], "also counting cards where another part of the card was not read."); }
      if (TAGS && TAGS.meta.headline) { b = p1(TAGS.meta.headline.with_tag[1]); rows += fig(TAGS.meta.headline.with_tag[1], "also counting cards grouped only by a Scryfall tag (not checked against the card text)."); }
    }
    openModal(`<div class="tinfo"><h2>How this works</h2>` +
      `<p>Cards are grouped by what their abilities do. An open-source rules parser (phase.rs) that is still being built reads the card text. Most cards are read correctly. Some are not, and this site shows where.</p>` +
      (t ? `<p>Roughly <b>${a}</b> of cards are in a group the tool has checked.${b ? ` Counting the groups marked “grouped loosely” it is roughly <b>${b}</b>.` : ""} The rest are under “Cards not grouped yet”, and each one says why.</p>` : "") +
      `<p>A group marked “grouped loosely” is a best guess from what the card does, not checked card by card. Group names can be imprecise: the cards inside a group are right more often than its label. The card’s own text is always the source of truth.</p>` +
      `<p>“Might also fit” lists cards the tool suggests for a group but has not put in it.</p>` +
      (rows ? `<h3>The exact figures</h3><table class="fig"><tbody>${rows}</tbody></table>` : "") +
      `<h3>Credits</h3><p>Card data, tags and images: <a href="https://scryfall.com" target="_blank" rel="noopener noreferrer">Scryfall</a>. Rules parsing: phase.rs. Magic: The Gathering card names, text and art are property of Wizards of the Coast. This site is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.</p>` +
      `<p>Something wrong? <a data-report="page" target="_blank" rel="noopener noreferrer" href="#">Report a problem</a>. This site does not record what you search for.</p></div>`);
  }

  // ---------------------------------------------------------------- config.js (feedback link)
  function applyConfig() {
    const hide = !CFG.feedbackUrl;
    for (const a of document.querySelectorAll("a[data-report]")) { if (!CFG.feedbackUrl) continue; a.href = CFG.feedbackUrl; }
    void hide;
  }
  const loadConfig = () => new Promise(res => {
    const s = document.createElement("script"); s.src = "config.js";
    s.onload = () => {
      try { Object.assign(CFG, window.APP_CONFIG || {}); } catch (e) { /* defaults */ }
      applyConfig();
      // feature TESTER_FILTERS: the filter and sort bar and "Narrow by group" (reports/testerfilters.js, .css); off: nothing is requested
      // features TYPE_GROUPS (typegroups.js, .css), FLIP_FACES (flipfaces.js, .css), ABILITY_TYPE_PAGES and MODAL_ABILITIES (modalabilities.js, .css) load after it, one after the other; each off: nothing is requested. NARROW_NO_CUT and COLOUR_MODES live in testerfilters.js.
      const extras = () => {
        const chain = ["TYPE_GROUPS", "FLIP_FACES", "ABILITY_TYPE_PAGES", "MODAL_ABILITIES"].filter(n => CFG[n] === true).map(n => n === "TYPE_GROUPS" ? "typegroups" : n === "FLIP_FACES" ? "flipfaces" : n === "MODAL_ABILITIES" ? "modalabilities" : "abilitypages");
        const next = () => {
          const n = chain.shift();
          if (!n) { res(); return; }
          const l = document.createElement("link"); l.rel = "stylesheet"; l.href = n + ".css"; document.head.appendChild(l);
          const f = document.createElement("script"); f.src = n + ".js"; f.onload = next; f.onerror = next; document.head.appendChild(f);
        };
        next();
      };
      if (!CFG.TESTER_FILTERS) { extras(); return; }
      const l = document.createElement("link"); l.rel = "stylesheet"; l.href = "testerfilters.css"; document.head.appendChild(l);
      const f = document.createElement("script"); f.src = "testerfilters.js"; f.onload = () => extras(); f.onerror = () => extras(); document.head.appendChild(f);
    };
    s.onerror = () => res();
    document.head.appendChild(s);
  });

  // ---------------------------------------------------------------- hand placements: build/hand_view.json (card id and group id only); no endpoint, no corrections file
  loadManual = async function () {
    try { MI = await J("manual_index.json"); } catch (e) { MI = null; return; }
    MDOC = emptyDoc();
    try {
      const hv = await J("hand_view.json"), ensure = oid => MDOC.edits[oid] || (MDOC.edits[oid] = { name: MI.cards[oid] ? MI.cards[oid][0] : "", groups: {} });
      for (const [oid, gids] of Object.entries(hv.adds || {})) for (const g of gids) ensure(oid).groups[g] = { action: "add" };
      for (const [oid, gids] of Object.entries(hv.removes || {})) for (const g of gids) ensure(oid).groups[g] = { action: "remove" };
      for (const oid of hv.nofit || []) ensure(oid).groups[Manual.NOFIT] = { action: "nofit" };
    } catch (e) { /* no hand placements on file */ }
    MENDPOINT = false;
    recomputeHand();
    await loadSC();
  };
  header = function () { /* the coverage block and the dev lines are not part of the tester page */ };
  needFlags = async function () { FLAGTRIED = true; };                       // card_flags.json feeds only the "Left out" list, which testers do not see
  let KFWANT = false;
  const needKFacReal = needKFac;
  needKFac = function () { return KFWANT ? needKFacReal() : Promise.resolve(); };      // the keyword facet is read when a keyword page is opened
  setMode = function () { MODE = "abilities"; };
  gsPost = function () { /* nothing is ever sent */ };
  gsBoot = async function () {
    try { const m = await J("group_search/meta.json"); GSON = !!(m && m.enabled); } catch (e) { GSON = false; }
    GSLOGOK = false;
  };
  mergedBadgeFor = function () { return ""; };
  leafLabel = function (l) { return esc(l.name); };
  tileHTML = function (x) {
    const oid = itemOid(x), c = CARDS[oid] || { n: oid }, url = imageURL(oid, "normal");
    return `<div class="tile" tabindex="0" role="button" data-oid="${esc(oid)}" data-ab="">` + (url ?
      `<img loading="lazy" src="${esc(url)}" alt="${esc(c.n)}" title="${esc(c.n)}"><div class="tname">${esc(c.n)}</div>` :
      `<div class="noimg"><b>${esc(c.n)}</b><div>no picture for this card</div></div>`) + `</div>`;
  };
  viewBarHTML = function () {
    if (!LIST.some(x => itemOid(x)) && !HIDDEN) return "";
    return `<div class="viewbar">View: <button class="vbtn${VIEW === "images" ? " on" : ""}" data-view="images">Images</button><button class="vbtn${VIEW === "text" ? " on" : ""}" data-view="text">Text</button>` +
      (HIDDEN ? ` <span class="sub" id="hiddennote">${fmt(HIDDEN)} card${HIDDEN === 1 ? " has" : "s have"} no picture and ${HIDDEN === 1 ? "is" : "are"} not shown.</span>` : "") + `<span class="sub" id="viewnote"></span></div>`;
  };
  viewNote = function () { const e = $("viewnote"); if (e) e.textContent = VIEW === "images" ? "Pictures load from Scryfall." : ""; };
  handRows = function (gid, have) {
    if (!handOn() || !CARDS) return [];
    const oids = Object.keys(MRESV.adds).filter(o => MRESV.adds[o][gid] && !have.has(o) && CARDS[o]).sort((a, b) => CARDS[a].n < CARDS[b].n ? -1 : 1);
    if (!oids.length) return [];
    return [`<div class="subhead">Added by hand (${fmt(oids.length)}), not in the count above</div>`].concat(oids.map(o => ({ oid: o, extra: "", html: cardHTML(o, null, null, gid) })), [`<div class="subhead">Others in this group</div>`]);
  };
  sibRows = function (lid) {
    if (!sibOn() || !CARDS || !SIB.groups[lid]) return [];
    const rows = SIB.groups[lid].m.filter(r => CARDS[r[0]]);
    if (!rows.length) return [];
    return [`<div class="subhead">Also here, grouped loosely (${fmt(rows.length)})</div>`].concat(rows.map(r => ({ oid: r[0], extra: "", html: cardHTML(r[0], null, null) })), [`<div class="subhead">Checked members of this group</div>`]);
  };
  sectionHead = function (m, si, own, above) {
    const tag = m.layer === "tag";
    return `<div class="subhead msec" id="msec-${si}" data-gid="${esc(m.gid)}"><span class="mname">${esc(memberName(m))}</span> <span class="sub">${fmt(own)} card${own === 1 ? "" : "s"}${above ? ` · ${fmt(above)} also shown above` : ""}</span> ` +
      `<span class="lnk" data-go="${esc(m.key)}" data-alone="1">open on its own</span>${tag ? `<div class="tloosenote">${LOOSE_NOTE}</div>` : ""}</div>`;
  };

  // ---------------------------------------------------------------- the tree
  const LOOSE_NOTE = "Grouped loosely: a best guess from what the card does, not checked card by card.";
  let TLASTSEL = null;
  renderTree = function () {
    if (selected !== TLASTSEL) {
      TLASTSEL = selected;
      if (selected) {
        if (/^(tf|tg|af|ag|lf|lg|ct|CT|LG):/.test(selected)) open.add("GL:");
        if (/^(u|UR):/.test(selected)) open.add("NG:");
        if (/^(Y|yk):/.test(selected)) open.add("Y:");
        if (window.TG && TG.owns(selected)) TG.reveal(selected, open);                    // feature TYPE_GROUPS
        if (window.AP && AP.owns(selected)) AP.reveal(selected, open);                    // feature ABILITY_TYPE_PAGES
      }
    }
    const h = [], t = TAX.totals;
    h.push(`<div class="blk">What abilities do</div>`);
    for (const f of TAX.families) {
      const fk = "f:" + f.key;
      h.push(row("l1", fk, esc(f.name), famN(f), { kids: true }));
      if (!open.has(fk)) continue;
      for (const nd of f.nodes) {
        const nk = "n:" + nd.id;
        h.push(row("l2", nk, esc(nd.name), nodeN(nd), { kids: true }));
        if (!open.has(nk)) continue;
        for (const lid of nd.leaves) h.push(row("l3", "l:" + lid, esc(TAX.leaves[lid].name), leafN(lid)));
        if (nd.rolled.length) h.push(row("l3", "r:" + nd.id, `Other: ${esc(nd.name).toLowerCase()}`, nd.rolled.reduce((a, lid) => a + leafN(lid), 0)));
      }
    }
    const kb = TAX.blocks.keyword, rb = TAX.blocks.replacement, nb = TAX.blocks.no_abilities;
    h.push(`<div class="blk">Grouped by rule</div>`);
    h.push(row("l1", "K", esc(kb.name), blockN(kb, TAX.totals.views.keyword_block), { kids: true }));
    if (open.has("K")) for (const br of kb.branches) {
      const bk = "kb:" + br.name;
      h.push(row("l2", bk, esc(br.name), branchN(kb, br), { kids: true }));
      if (open.has(bk)) for (const lid of br.leaves) h.push(row("l3", "kl:" + lid, esc(kb.leaves[lid].name), blkLeafN(kb, lid)));
    }
    h.push(row("l1", "G", esc(rb.name), blockN(rb, TAX.totals.views.replacement_group), { kids: true }));
    if (open.has("G")) for (const br of rb.branches) {
      const bk = "gb:" + br.name;
      h.push(row("l2", bk, esc(br.name), branchN(rb, br), { kids: true }));
      if (open.has(bk)) for (const lid of br.leaves) h.push(row("l3", "gl:" + lid, esc(rb.leaves[lid].name), blkLeafN(rb, lid)));
    }
    h.push(row("l1", "V", esc(nb.name), counting() ? nvis(nb.cards) : nb.cards.length));
    // grouped loosely: tentative groups, groups held for an unread condition, community tags, loose groups by effect
    if (tentOn() || annOn() || LOOSE || tagOn()) {
      h.push(row("l1", "GL:", "Grouped loosely", null, { kids: true }));
      if (open.has("GL:")) {
        if (tentOn()) { h.push(`<div class="blk sub2">Best-guess groups</div>`); for (const f of TAX.families) { const tf = TENT.families.find(x => x.key === f.key); if (!tf) continue; const tk = "tf:" + f.key; h.push(row("l2", tk, esc(f.name), tfN(tf), { kids: true })); if (open.has(tk)) for (const gid of tf.groups) h.push(row("l3", "tg:" + gid, esc(TENT.groups[gid].short), tgN(TENT.groups[gid]))); } }
        if (annOn()) { h.push(`<div class="blk sub2">Cards with a part we could not read</div>`); for (const f of TAX.families) { const af = ANN.families.find(x => x.key === f.key); if (!af) continue; const ak = "af:" + f.key; h.push(row("l2", ak, esc(f.name), afN(af), { kids: true })); if (open.has(ak)) for (const k of af.groups) h.push(row("l3", "ag:" + k, esc(ANN.groups[k].name), agN(ANN.groups[k]))); } }
        if (LOOSE) { h.push(`<div class="blk sub2">By effect (unchecked)</div>`); for (const f of LOOSE.families) { const fk = "lf:" + f.key; h.push(row("l2", fk, esc(f.name), lfN(f), { kids: true })); if (open.has(fk)) for (const gid of f.groups) h.push(row("l3", "lg:" + gid, esc(LOOSE.groups[gid].short), lgN(LOOSE.groups[gid]))); } }
        if (UNREAD && tagOn()) { h.push(`<div class="blk sub2">By Scryfall tag</div>`); h.push(row("l2", "CT:", "Scryfall tag groups", ctAllN(), { kids: true })); if (open.has("CT:")) for (const gid of TAGS.order) h.push(row("l3", "ct:" + gid, esc(TAGS.groups[gid].name), tgcN(TAGS.groups[gid]))); }
      }
    }
    h.push(`<div class="blk">By keyword</div>`);
    h.push(row("l1", "Y:", "Cards with a keyword", KFAC ? KFAC.meta.cards_with_a_keyword : null, { kids: true }));
    if (KFAC && open.has("Y:")) for (const n of kwOrder()) h.push(row("l2", "yk:" + n, esc(KFAC.keywords[n].d), KFAC.keywords[n].n));
    if (window.TG && TG.enabled) for (const x of TG.treeRows(row, open, renderTree)) h.push(x);        // feature TYPE_GROUPS: "Card types"
    if (window.AP && AP.enabled) for (const x of AP.treeRows(row, open, renderTree)) h.push(x);        // feature ABILITY_TYPE_PAGES: "Ability types"
    if (HG &&Object.keys(HG.groups).length) {
      h.push(`<div class="blk">Extra groups</div>`);
      for (const slug of Object.keys(HG.groups)) { const g = HG.groups[slug]; if (g.retired) continue; h.push(row("l1", "hg:" + slug, esc(g.name), g.cards)); }
    }
    const nOrg = t.not_yet_organized - (tentOn() ? TENT.meta.cards : 0) - (annOn() ? annCounts().c + annCounts().g : 0) - (tagOn() ? TAGS.meta.cards : 0) - handPileN();
    h.push(row("l1 sep", "NG:", "Cards not grouped yet", nOrg, { kids: true }));
    if (open.has("NG:")) {
      for (const g of TAX.unorganized) h.push(row("l2", "u:" + g.id, esc(g.name), UNORG ? unorgN(UNORG.find(x => x.id === g.id) || g) : g.cards));
      if (UNREAD) h.push(row("l2", "UR:", "Cards we couldn't read yet", unreadN()));
    }
    TREE.innerHTML = h.join("");
  };
  TREE.addEventListener("click", e => {                      // the two folders that are not pages
    const r = e.target.closest(".row"); if (!r) return;
    const k = r.dataset.k;
    if (k === "GL:" || k === "NG:" || (window.TG && TG.isFolder(k)) || (window.AP && AP.isFolder(k))) { e.stopImmediatePropagation(); if (open.has(k)) open.delete(k); else open.add(k); renderTree(); }
  }, true);

  // ---------------------------------------------------------------- group headers: name, one line, card count; one plain note for every group that is not a checked one
  const GKEYS = new Map();
  async function descOf(k) {
    try {
      await gsLoad();
      if (!GKEYS.size) for (const e of GSIDX.entries) if (!GKEYS.has(e.key)) GKEYS.set(e.key, e);
      const e = GKEYS.get(k); return e && e.desc ? e.desc : "";
    } catch (err) { return ""; }
  }
  async function headFor(k) {
    if (window.TG && TG.owns(k)) return TG.head(k);                                      // feature TYPE_GROUPS
    if (window.AP && AP.owns(k)) return AP.head(k);                                      // feature ABILITY_TYPE_PAGES
    const i = k.indexOf(":"), kind = k.slice(0, i), id = k.slice(i + 1);
    let name = "", count = null, noun = "cards", path = "", desc = "", loose = false;
    const famName = key => { const f = TAX.families.find(x => x.key === key); return f ? f.name : ""; };
    if (MERGED && MERGED.redirects[k] && k !== ALONEKEY) {
      const pg = MERGED.pageBy[MERGED.redirects[k]]; name = pg.name; desc = pg.description || ""; count = mergedUnion(pg);
      loose = pg.members.some(m => m.layer === "tag");
      return { name: name, html: headHTML(name, count, noun, "", desc, loose) };
    }
    if (kind === "l") { const l = TAX.leaves[id]; name = l.name; count = leafN(id); path = leafPath(id); loose = !!(l.flags.length || (l.notes && l.notes.length)); desc = await descOf(k); }
    else if (kind === "tg" && TENT && TENT.groups[id]) { const g = TENT.groups[id], fam = TENT.families.find(x => x.groups.includes(id)); name = g.name; count = tgN(g); path = fam ? fam.name : ""; loose = true; desc = await descOf(k); }
    else if (kind === "lg" && LOOSE && LOOSE.groups[id]) { const g = LOOSE.groups[id], fam = LOOSE.families.find(x => x.groups.includes(id)); name = g.name; count = lgN(g); path = fam ? fam.name : ""; loose = true; desc = await descOf(k); }
    else if (kind === "ct" && TAGS && TAGS.groups[id]) { const g = TAGS.groups[id]; name = g.name; count = tgcN(g); path = "Scryfall tag"; loose = true; desc = await descOf(k); }
    else if (kind === "ag" && ANN && ANN.groups[id]) { const g = ANN.groups[id]; name = g.name; count = agN(g); path = famName(g.fam); loose = true; desc = "Cards with a condition the tool did not read, shown in the group they would belong in if the condition were ignored."; }
    else if (kind === "kl") { const l = TAX.blocks.keyword.leaves[id]; name = l.name; count = blkLeafN(TAX.blocks.keyword, id); path = "Keyword abilities"; desc = await descOf(k); }
    else if (kind === "gl") { const l = TAX.blocks.replacement.leaves[id]; name = l.name; count = blkLeafN(TAX.blocks.replacement, id); path = TAX.blocks.replacement.name; desc = await descOf(k); }
    else if (kind === "hg" && HG && HG.groups[id]) { const g = HG.groups[id]; name = g.name; count = g.cards; noun = "possible cards"; path = "Made by hand"; loose = true; desc = await descOf(k); }
    else if (kind === "V") { name = "No abilities"; count = counting() ? nvis(TAX.blocks.no_abilities.cards) : TAX.blocks.no_abilities.cards.length; desc = "Cards with no rules text."; }
    else if (kind === "u" && UNORG) { const g = UNORG.find(x => String(x.id) === id); if (!g) return null; name = "Not grouped yet: " + g.name; count = unorgN(g); desc = g.explain || ""; }
    else if (kind === "yk" && KFAC && KFAC.keywords[id]) { const kw = KFAC.keywords[id]; name = "Keyword: " + kw.d; count = kw.n; desc = "Cards that carry this keyword, wherever they are grouped."; }
    else if (kind === "r") { const nd = NODES[id]; if (!nd) return null; name = "Other: " + nd.name.toLowerCase(); count = nd.rolled.reduce((a, lid) => a + leafN(lid), 0); path = NODE_FAM[id]; desc = "Small groups shown together."; }
    else return null;
    return { name: name, html: headHTML(name, count, noun, path, desc, loose) };
  }
  function headHTML(name, count, noun, path, desc, loose) {
    return `<div class="thead">${path ? `<div class="crumb">${esc(path)}</div>` : ""}<h1>${esc(name)}</h1>${desc ? `<p class="tdesc">${esc(desc)}</p>` : ""}${count != null ? `<div class="tcnt">${fmt(count)} ${esc(noun)}</div>` : ""}${loose ? `<div class="tloosenote">${LOOSE_NOTE}</div>` : ""}</div>`;
  }
  const LISTKINDS = /^(l|tg|lg|ct|ag|kl|gl|hg|V|u|yk|r|ty|ab):/;
  const _show = show;
  let KEEPDRAWER = false;
  show = async function (k) {
    if (!k) return;
    const keepDrawer = KEEPDRAWER;
    if (/^(C|Q|QB):/.test(k)) return;                          // the Cards and To place views are not part of the tester page
    if (k.startsWith("c:")) { await openCard(k.slice(2)); return; }
    if (/^(Y|yk):/.test(k)) KFWANT = true;
    PANEL.classList.add("tpend");
    try { await (window.TG && TG.owns(k) ? TG.show(k) : window.AP && AP.owns(k) ? AP.show(k) : _show(k)); } finally { PANEL.classList.remove("tpend"); }
    if (selected !== k && !(MERGED && MERGED.redirects[k])) return;
    let meta = null;
    if (LISTKINDS.test(k) || (MERGED && MERGED.redirects[k])) { try { meta = await headFor(k); } catch (e) { meta = null; } }
    if (meta) {
      let n = PANEL.firstElementChild; const rm = [];
      while (n && !(n.id === "sctabs" || n.id === "pinwrap" || n.id === "list" || n.id === "morewrap" || n.id === "suggsec" || n.classList.contains("viewbar") || n.classList.contains("mchips"))) { rm.push(n); n = n.nextElementSibling; }
      for (const x of rm) x.remove();
      PANEL.insertAdjacentHTML("afterbegin", meta.html);
      TCUR = { k: k, name: meta.name };
    } else {
      const h2 = PANEL.querySelector("h2"); TCUR = { k: k, name: h2 ? h2.textContent.trim() : "" };
    }
    if (mobile() && !keepDrawer) drawer(false);
  };
  // a folder that opens in the tree must not close the drawer
  TREE.addEventListener("click", () => { KEEPDRAWER = true; setTimeout(() => { KEEPDRAWER = false; }, 0); }, true);

  // ---------------------------------------------------------------- card: a large image with its oracle text, in a modal over the page
  function groupsOf(oid) {
    const c = MI && MI.cards[oid]; if (!c) return [];
    const out = [], seen = new Set(), adds = (MRESV && MRESV.adds[oid]) || {}, rem = (MRESV && MRESV.removes[oid]) || {}, order = "PRKBTSMLA";
    const list = c[3].slice().sort((a, b) => order.indexOf(a[1]) - order.indexOf(b[1]));
    for (const [gid, src] of list) {
      if (seen.has(gid) || rem[gid]) continue;
      const g = MI.groups[gid]; if (!g || !g[4]) continue;
      seen.add(gid); out.push({ gid: gid, key: Manual.goKey(gid), name: g[0], loose: "BTAMLS".indexOf(src) >= 0 });
    }
    for (const gid of Object.keys(adds)) { if (seen.has(gid) || !MI.groups[gid]) continue; seen.add(gid); out.push({ gid: gid, key: Manual.goKey(gid), name: MI.groups[gid][0], loose: true }); }
    return out.filter(g => g.key);
  }
  async function openCard(oid) {
    await needCards(); await needManual();
    const c = CARDS && CARDS[oid];
    if (!c) { say("That card is not in this tool."); return; }
    const url = imageURL(oid, "large"), gs = groupsOf(oid), st = MI && MI.cards[oid] ? MI.cards[oid][1] : "";
    const img = url ? `<img src="${esc(url)}" alt="${esc(c.n)}">` : `<div class="noimg"><b>${esc(c.n)}</b><div>no picture for this card</div></div>`;
    const chips = gs.length ? gs.map(g => `<span class="lnk chip${g.loose ? " lo" : ""}" data-go="${esc(g.key)}">${esc(g.name)}</span>`).join(" ") + (gs.some(g => g.loose) ? `<div class="tsrc">Dashed: grouped loosely.</div>` : "")
      : `<div class="tsrc">${st === "v" ? "This card has no rules text." : "Not grouped yet."}</div>`;
    openModal(`<div class="tbig">${img}</div><div class="tinfo"><h2>${esc(c.n)}</h2><div class="tsrc">${costHTML(c)} ${esc(c.ty)}</div><div class="toracle">${esc(c.t)}</div>` +
      `<h3>In these groups</h3><div>${chips}</div><p style="margin-top:12px"><a data-report="card" data-oid="${esc(oid)}" target="_blank" rel="noopener noreferrer" href="${esc(CFG.feedbackUrl || "#")}">Report a problem with this card</a></p></div>`);
    MODALFOR = oid;
    if (window.FL) FL.attach(oid, modal);                       // feature FLIP_FACES
    if (window.MA) MA.attach(oid, modal);                       // feature MODAL_ABILITIES
  }
  showCardPage = function (oid) { return openCard(oid); };
  PANEL.addEventListener("click", e => {                      // a tile or a card row opens the modal; its chips and links still do what they did
    const tl = e.target.closest(".tile");
    if (tl) { e.stopImmediatePropagation(); openCard(tl.dataset.oid); return; }
    const top = e.target.closest(".card .top");
    if (top && !e.target.closest("[data-go]")) { e.stopImmediatePropagation(); openCard(top.parentElement.dataset.oid); }
  }, true);
  PANEL.addEventListener("keydown", e => { if ((e.key === "Enter" || e.key === " ") && e.target.classList && e.target.classList.contains("tile")) { e.preventDefault(); e.target.click(); } });

  // ---------------------------------------------------------------- "Might also fit" (the possible-matches tab): the same lists and order, without the slider, the scores, the tick and Add
  scRowHTML = function (oid, r, placed, lens) {
    const S = SCCUR, c = MI.cards[oid], ccard = CARDS && CARDS[oid] ? costHTML(CARDS[oid]) : "";
    return `<div class="sgrow" data-oid="${esc(oid)}"><span class="lnk nm" data-go="c:${esc(oid)}">${esc(c[0])}</span> ${ccard}<div class="why">${esc(lens ? S.lensWhy : scWhy(r))}</div></div>`;
  };
  scRender = function () {
    const S = SCCUR, box = $("suggsec");
    if (!S || !box || !MRESV) return;
    const e = SC.groups[S.gid], l = SC.lens[S.gid], plain = {};
    let h = scPickerHTML(), shownRows = [], rowsA = [], rowsB = [];
    if (e) {
      const vis = Suggested.visible(MI, MRESV, S.gid, S.q, S.p, { floor: SCFLOOR, includePlaced: SCINC, keep: S.keep });
      rowsA = vis.rows.filter(r => visible(r.oid));
      for (const r of rowsA) plain[r.oid] = 1;
    }
    if (l) {
      S.lensWhy = `the card has the Scryfall tag “${l[3]}”, which this group is built from; a tag is a hint, not a check`;
      rowsB = Suggested.lens(MI, MRESV, S.lq, S.lp, { includePlaced: SCINC, keep: S.keep, skip: plain }).rows.filter(r => visible(r.oid));
    }
    // feature TESTER_FILTERS: the filter and sort bar and the narrowing row act on these rows as well
    const TFX = window.TF && TF.enabled ? TF.sugg(rowsA, rowsB) : null;
    if (TFX) { rowsA = TFX.A; rowsB = TFX.B; h += TFX.bar; }
    if (e) {
      const shown = rowsA.slice(0, S.nS);
      shownRows = shown.map(r => r.row);
      h += `<h3>Cards that might also fit</h3><div class="sub">The tool suggests these for this group but has not put them in it. Suggested, not checked.</div>` +
        `<div class="sub">${fmt(rowsA.length)} card${rowsA.length === 1 ? "" : "s"}${rowsA.length > shown.length ? `, showing the first ${fmt(shown.length)}` : ""}.</div>`;
      h += shown.length ? shown.map(r => scRowHTML(r.oid, r.row, r.placed, false)).join("") : `<div class="sub">No suggested card for this group${TFX && TF.state().k ? " with these filters" : ""}.</div>`;
      if (rowsA.length > shown.length) h += `<div class="more"><button data-sact="more" data-w="S">Show ${Math.min(SC.per_view, rowsA.length - shown.length)} more (${fmt(rowsA.length - shown.length)} left)</button></div>`;
    } else if (!l) h += `<div class="sub">No suggested card for this group.</div>`;
    if (l) {
      const lshown = rowsB.slice(0, S.nL);
      h += `<h3 class="sgsub">Cards with the Scryfall tag “${esc(l[3])}”</h3><div class="sub">Cards with this tag that are not in the group. A tag is a hint, not a check.</div>` +
        `<div class="sub">${fmt(rowsB.length)} card${rowsB.length === 1 ? "" : "s"}${rowsB.length > lshown.length ? `, showing the first ${fmt(lshown.length)}` : ""}, most popular first.</div>`;
      h += lshown.length ? lshown.map(r => scRowHTML(r.oid, null, r.placed, true)).join("") : `<div class="sub">No other card carries this tag.</div>`;
      if (rowsB.length > lshown.length) h += `<div class="more"><button data-sact="more" data-w="L">Show ${Math.min(SC.per_view, rowsB.length - lshown.length)} more (${fmt(rowsB.length - lshown.length)} left)</button></div>`;
    }
    box.innerHTML = h;
    const tb = document.querySelector('#sctabs button[data-sctab="matches"]');
    if (tb) tb.textContent = scTabLabel();
    scNeedWhy(shownRows);
  };

  // ---------------------------------------------------------------- search results: a card shows the groups it is in, a group shows name, count, one line and why it matched; no logging, no "Didn't find it?" POST
  const looseGroup = e => e.layer === "t" || e.layer === "o" || e.layer === "c" || e.layer === "h" || (e.layer === "l" && !!TAX.leaves[e.gid.slice(5)] && TAX.leaves[e.gid.slice(5)].flags.length > 0);
  // ---------------------------------------------------------------- feature SEARCH_FIXES (reports/config.js): search ranking and layout fixes. Off: none of this code runs and groupsearch.js is called exactly as before.
  // A hand-defined group's row says how many cards are placed in it by hand (its count is the rule matches, which are suggestions); a memberless one ranks after groups that have members unless the query is its
  // name or alias; a longer word that only begins with a typed whole word ranks after whole-word matches; descriptions that are one member's quoted card line sit in one collapsed row; a long list is two or
  // three headed blocks of 10 with an honest count. Presentation and ranking only: no group, id, placement, count or figure changes, and nothing new is fetched.
  const SFX = () => CFG.SEARCH_FIXES === true;
  let HPN = null;                                                                            // hand group id -> cards placed in it by hand (the same count as the group page's Members list), rebuilt for each search
  const handPlacedN = e => {
    if (!HPN) {
      HPN = {};
      if (handOn() && MRESV && MRESV.adds && MI) for (const o of Object.keys(MRESV.adds)) { if (!MI.cards[o]) continue; for (const g of Object.keys(MRESV.adds[o])) if (MRESV.adds[o][g]) HPN[g] = (HPN[g] || 0) + 1; }
    }
    return HPN[e.gid] || 0;
  };
  gsRow = function (r) {
    const e = r.e, n = gsCount(r), noun = e.layer === "h" ? "possible cards" : "cards";
    const why = r.dym ? `did you mean “${esc(r.dym)}”` : r.why === "alias" ? (r.drafted ? `suggested alias “${esc(r.via)}”` : `via “${esc(r.via)}”`) : r.why === "most" ? "matched: most of your words" : r.why === "slug" ? "matched: tag name" : r.why === "description" ? "matched: description" : r.why === "family" ? "matched: family" : "";
    return `<a class="gr" data-nav data-go="${esc(r.key)}" href="#${esc(encodeURIComponent(r.key))}"${r.note && r.why === "alias" ? ` title="${esc(r.note)}"` : ""}>` +
      `<span class="gc">${fmt(n)} ${noun}${SFX() && e.layer === "h" ? `, ${fmt(handPlacedN(e))} placed by hand` : ""}</span><span class="gn">${esc(e.name)}</span>` +
      (e.desc ? `<span class="gd" title="${esc(e.desc)}">${esc(e.desc)}</span>` : "") +
      (why ? `<span class="gm">${why}</span>` : "") +
      (looseGroup(e) ? `<span class="tl">Grouped loosely</span>` : "") +
      (r.why === "alias" && r.fit === "partial" && r.note ? `<span class="gl">Note: ${esc(r.note)}</span>` : "") + `</a>`;
  };
  gsMissHTML = function (q) {
    if (LIDX.norm(q).length < 2 || !CFG.feedbackUrl) return "";
    return `<div class="gs-miss"><a class="gs-btn" data-report="miss" data-q="${esc(q)}" target="_blank" rel="noopener noreferrer" href="${esc(CFG.feedbackUrl)}">Can’t find it? Tell us what you were looking for</a></div>`;
  };
  function cardAnswer(en, a) {
    if (en[3] === "o") return `<span class="sub">${esc(a.text)}</span>`;
    const gs = groupsOf(en[0]);
    if (gs.length) return `<span class="sub">In: ${gs.slice(0, 3).map(g => `<span class="lnk chip" data-go="${esc(g.key)}">${esc(g.name)}</span>`).join(" ")}${gs.length > 3 ? ` +${gs.length - 3} more` : ""}</span>`;
    return `<span class="sub">${en[3] === "v" ? "No rules text." : "Not grouped yet."}</span>`;
  }
  find = async function (q) {
    const out = FR;
    if (!q.trim()) { out.innerHTML = ""; gsPending = null; return; }
    const seq = ++FINDSEQ;
    if (!LOOK) { out.innerHTML = `<div class="sub">Loading the card list…</div>`; await needLookup(); }
    await needManual();
    const ctx = answerCtx(), r = AbilityFind.search(LIDX, q, 12);
    const rows = r.matches.map(en => {
      const a = AbilityFind.describe(LIDX, en, ctx);
      return `<div class="fr"${PINON && en[3] !== "o" ? ` tabindex="0" data-nav data-go="pin:${esc(en[0])}"` : (en[3] !== "o" ? ` tabindex="0" data-nav data-go="c:${esc(en[0])}"` : "")}><span class="nm">${esc(a.name)}</span>${a.others.length ? ` <span class="sub">(${a.others.map(esc).join(" / ")})</span>` : ""}${cardAnswer(en, a)}</div>`;
    });
    try {
      await gsLoad(); await needLoose();
      const so = { allow: gsAllow, words: GSWORDS };
      if (SFX()) { HPN = null; so.fixes = true; so.placed = handPlacedN; }
      let res = GroupSearch.search(GSIDX, q, so);
      if (res.needWords) { await gsWords(); so.words = GSWORDS; res = GroupSearch.search(GSIDX, q, so); }
      if (seq !== FINDSEQ) return;
      if (!r.total && !res.groups.length && !res.family.length && !(res.example && res.example.length)) out.innerHTML = `<div class="sub">No card or group matches “${esc(q)}”. Try a card name, or a common term such as “board wipe”.</div>` + gsMissHTML(q);
      else out.innerHTML = gsSection(q, rows, r.total, res);
    } catch (err) {
      out.innerHTML = (r.total ? "" : `<div class="sub">No card matches.</div>`) + rows.join("") + (r.total > 12 ? `<div class="sub">${fmt(r.total)} matches; showing 12.</div>` : "");
    }
  };

  // SEARCH_FIXES: the results layout. Up to 10 groups (and no example-line row) is today's markup; more is two or three headed blocks (Named, Contains the word, Related) of 10 with "Show 10 more" up to 30 each.
  const _gsSectionBase = gsSection;
  gsSection = function (q, cardRows, cardTotal, res) {
    const ex = res.example || [], nG = res.groups.length;
    if (!SFX() || (nG <= 10 && !ex.length)) return _gsSectionBase(q, cardRows, cardTotal, res);
    let h = `<div class="gs-jump" id="gs-jump"><a href="#" data-gsjump="gs-cards">Cards (${fmt(cardTotal)})</a> · <a href="#" data-gsjump="gs-groups">Groups (${fmt(nG)}${res.family.length ? " + " + fmt(res.family.length) + " by family" : ""}${ex.length ? " + " + fmt(ex.length) + " in an example line" : ""})</a></div>`;
    h += `<div id="gs-cards"><h3 class="gs-h">Cards</h3>` + (cardTotal ? gsMore(cardRows, GSCARDS_FIRST, "cards") + (cardTotal > 12 ? `<div class="sub">${fmt(cardTotal)} cards match; showing 12.</div>` : "") : `<div class="sub gs-none">No card name matches.</div>`) + `</div>`;
    h += `<div id="gs-groups"><h3 class="gs-h">Groups</h3>`;
    if (res.dym) h += `<div class="sub gs-dym">Nothing matched “${esc(res.dym.from)}” as typed. Did you mean “${esc(res.dym.to)}”? Those groups are listed with that label.</div>`;
    if (!nG) h += `<div class="sub gs-none">No group matches “${esc(q)}”.</div>`;
    else if (nG <= 10) h += gsMore(res.groups.map(gsRow), GSFIRST, "groups");
    else {
      h += `<div class="sub">${fmt(nG)} groups match.</div>`;
      for (const [id, label, f] of [["named", "Named", t => t <= 2], ["contains", "Contains the word", t => t > 2 && t < 4], ["related", "Related", t => t >= 4]]) {
        const list = res.groups.filter(g => f(g.tier));
        if (!list.length) continue;
        const rows = list.slice(0, GSCAP).map(gsRow);
        h += `<p class="subhead" data-gsb="${id}">${label} (${fmt(list.length)})</p>` + rows.slice(0, 10).join("") + rows.slice(10).map(x => x.replace(/^<(a|div) /, `<$1 hidden data-gsfx="${id}" `)).join("") +
          (rows.length > 10 ? `<button class="gs-btn" data-nav data-gsfxmore="${id}">Show ${Math.min(10, rows.length - 10)} more</button>` : "") +
          (list.length > GSCAP ? `<div class="sub">${fmt(list.length)} in this block; at most ${GSCAP} can be shown.</div>` : "");
      }
    }
    if (res.family.length) h += `<div class="gs-fam"><button class="gs-btn gs-famb" data-nav data-gsfam aria-expanded="false">${fmt(res.family.length)} more group${res.family.length === 1 ? "" : "s"} matched only by family or kind ▸</button><div class="gs-famlist" hidden>${res.family.slice(0, GSCAP).map(gsRow).join("")}${res.family.length > GSCAP ? `<div class="sub">showing ${GSCAP} of ${fmt(res.family.length)}</div>` : ""}</div></div>`;
    if (ex.length) h += `<div class="gs-fam"><button class="gs-btn gs-famb" data-nav data-gsfam aria-expanded="false">${fmt(ex.length)} more group${ex.length === 1 ? "" : "s"} matched only in an example card line ▸</button><div class="gs-famlist" hidden>${ex.slice(0, GSCAP).map(gsRow).join("").replace(/matched: description/g, "matched: an example card line")}${ex.length > GSCAP ? `<div class="sub">showing ${GSCAP} of ${fmt(ex.length)}</div>` : ""}</div></div>`;
    return h + gsMissHTML(q, nG, cardTotal) + `</div><div class="sr-only" aria-live="polite" id="gs-live">${nG} group${nG === 1 ? "" : "s"}, ${cardTotal} card${cardTotal === 1 ? "" : "s"}</div>`;
  };
  FR.addEventListener("click", e => {
    const b = e.target.closest("[data-gsfxmore]");
    if (!b) return;
    const hid = [...FR.querySelectorAll(`[data-gsfx="${b.dataset.gsfxmore}"][hidden]`)];
    for (const el of hid.slice(0, 10)) el.hidden = false;
    if (hid.length > 10) b.textContent = `Show ${Math.min(10, hid.length - 10)} more`;
    else { b.remove(); if (hid[0]) hid[0].focus(); }
  });

  // ---------------------------------------------------------------- landing
  function landing() {
    PANEL.innerHTML = `<div class="landing"><h1>Find Magic cards by what they do</h1>` +
      `<p>Search for a card or for an effect, or browse the groups in the left column. Each group holds cards whose abilities do the same kind of thing: removal, ramp, card draw and so on.</p>` +
      `<div class="exs" id="exs"><button class="ex" type="button" data-q="board wipe">board wipe</button><button class="ex" type="button" data-q="ramp">ramp</button><button class="ex" type="button" data-q="lifegain">lifegain</button><button class="ex" type="button" data-q="Wrath of God">Wrath of God</button></div>` +
      `<p class="sub">Some groups are a best guess and are marked “grouped loosely”. <button class="tlink" type="button" data-how="1" style="color:var(--accent);background:none;border:0;padding:0;cursor:pointer;text-decoration:underline;font:inherit">How this works</button></p></div>`;
  }
  landing();
  PANEL.addEventListener("click", e => {
    const ex = e.target.closest(".ex");
    if (ex) { Q.value = ex.dataset.q; Q.dispatchEvent(new Event("input", { bubbles: true })); if (mobile()) drawer(true); else Q.focus(); }
    const how = e.target.closest("[data-how]"); if (how) showHow();
  });

  applyTree();
  // ---------------------------------------------------------------- features ACTIVE_GROUP_HIGHLIGHT, DEFAULT_POPULARITY (the rank wait; the sort itself is in testerfilters.js) and QUERY_MATCH_BLOCK (reports/config.js)
  // Presentation only: no group, id, placement, suggestion, count or figure changes, nothing is fetched that was not fetched before, and each flag off means none of this code runs.
  // ACTIVE_GROUP_HIGHLIGHT: the open group is marked (class "cur", aria-current) in the search results and the tree, tied to the open group's id (a merged page's id for any of its groups), never to focus or hover.
  // QUERY_MATCH_BLOCK: a group opened from a search row that matched by its DESCRIPTION shows, above its list, the cards whose own ability line (the line the page shows under the card) has the query's words, most popular first.
  //   The query lives in memory only: the address never carries it, so a deep link, a reload or another way of opening the group shows no block. Matching: stop words dropped, each word by stem, in order, within the number of typed words + 3.
  function initDeckFlags() {
    const HL = CFG.ACTIVE_GROUP_HIGHLIGHT === true, POPF = CFG.DEFAULT_POPULARITY === true && CFG.TESTER_FILTERS === true, QMF = CFG.QUERY_MATCH_BLOCK === true;
    if (!HL && !POPF && !QMF) return;
    const st = document.createElement("style");
    st.textContent =
      (HL ? ".gr.cur{box-shadow:inset 4px 0 0 var(--accent);border-color:var(--accent);background:var(--sel)}.gr.cur .gn::after,#tree .row.cur>span:first-child::after{content:\" \\25CF open\";font-size:11px;font-weight:600;color:var(--accent)}" +
        "#tree .row.cur{box-shadow:inset 4px 0 0 var(--accent);background:var(--sel);font-weight:600}" : "") +
      (QMF ? ".qm{border:1px solid var(--accent);border-radius:8px;background:var(--panel);padding:8px 10px;margin:10px 0}.qm .qt{font-weight:700}.qm .qt b{color:var(--accent)}.qm .qs{color:var(--muted);font-size:12.5px;margin:2px 0 6px}" +
        ".qr{display:flex;gap:10px;padding:5px 0;border-top:1px solid var(--line);align-items:baseline}.qr .nm{font-weight:600;min-width:150px}.qr .ln{flex:1;min-width:0;overflow-wrap:anywhere}" +
        ".qm mark{background:#fff0a8;color:#1d1d1b;border-radius:2px;padding:0 1px}.qr .src{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:9px;padding:0 6px;white-space:nowrap}" +
        ".qm .qb{font:inherit;border:1px solid var(--line);background:var(--chip);color:var(--fg);border-radius:6px;padding:5px 10px;cursor:pointer;margin-top:4px}.qnone{color:var(--muted);font-size:13px;margin:8px 0}" +
        "@media (max-width:800px){.qr{flex-wrap:wrap}.qr .nm{min-width:0;width:100%}.qm .qb{min-height:44px}}" : "");
    document.head.appendChild(st);
    const canon = k => (k && MERGED && MERGED.redirects && MERGED.redirects[k] && k !== ALONEKEY) ? "P:" + MERGED.redirects[k] : k;
    function mark() {
      const cur = selected ? canon(selected) : null;
      for (const e of document.querySelectorAll("#findres .gr[data-go], #tree .row[data-k]")) {
        const on = !!cur && canon(e.dataset.go || e.dataset.k) === cur;
        e.classList.toggle("cur", on);
        if (on) e.setAttribute("aria-current", "true"); else e.removeAttribute("aria-current");
      }
    }
    if (HL) {
      const mo = new MutationObserver(mark);
      mo.observe(TREE, { childList: true }); mo.observe(FR, { childList: true });
      mark();
    }
    let QM = null, PEND = null, QSEQ = 0;
    if (QMF) {
      const _row = gsRow;
      gsRow = function (r) { return _row(r).replace('<a class="gr"', `<a class="gr" data-why="${esc(r.why)}" data-gid="${esc(r.e.gid)}" data-layer="${esc(r.e.layer)}"`); };
      const _sec = gsSection;
      let RESQ = "";                                              // the query the results on screen were made for (gsSection is called with it)
      gsSection = function (q, ...rest) { RESQ = String(q).trim(); return _sec(q, ...rest); };
      FR.addEventListener("click", e => {
        const g = e.target.closest(".gr[data-go]");
        PEND = g && g.dataset.why === "description" && RESQ ? { q: RESQ, key: g.dataset.go, gid: g.dataset.gid, layer: g.dataset.layer, n: 10 } : null;
      }, true);
      SCHIDE.push("#qmwrap");
    }
    const _show = show;
    show = async function (k) {
      if (POPF) await needManual();                                                      // the rank is in manual_index.json: the first sort waits for the file the page loads anyway
      if (QMF) {
        if (PEND) { QM = canon(k) === canon(PEND.key) ? PEND : null; PEND = null; }
        else if (QM && canon(k) !== canon(QM.key)) QM = null;
        if (PINNEXT) QM = null;
      }
      const r = await _show(k);
      if (HL) mark();
      if (QMF) renderQM().catch(() => { /* the block is a convenience */ });
      return r;
    };
    // ---- the block
    const STOP = new Set("a an the of to and or for in on at by with from your you it its that this is are be as".split(" "));
    const norm = x => String(x).toLowerCase().replace(/['’]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
    function stem(w) {
      const n = w.length;
      if (n > 4 && /ies$/.test(w)) return w.slice(0, -3) + "y";
      if (n > 4 && /(ss|x|z|ch|sh)es$/.test(w)) return w.slice(0, -2);
      if (n > 3 && /s$/.test(w) && !/(ss|us|is)$/.test(w)) return w.slice(0, -1);
      return w;
    }
    function variants(w) { const s = stem(w), v = [s]; if (s.length > 5 && /ing$/.test(s)) v.push(s.slice(0, -3)); else if (s.length > 4 && /ed$/.test(s)) v.push(s.slice(0, -2)); return v; }
    function parse(q) {
      const words = norm(q).split(" ").filter(Boolean);
      let core = words.filter(w => !STOP.has(w)); if (!core.length) core = words;
      return { k: words.length, terms: core.map(w => ({ w: w, v: variants(w) })) };
    }
    // the ranges of the words of the best (shortest) in-order match of the query's words in a line, or null
    function matchLine(line, qp) {
      if (!line || !qp.terms.length) return null;
      const toks = [], re = /[A-Za-z0-9’']+/g;
      let m;
      while ((m = re.exec(line))) { const w = m[0].toLowerCase().replace(/['’]/g, "").replace(/[^a-z0-9]/g, ""); if (w) toks.push({ w: w, st: stem(w), s: m.index, e: m.index + m[0].length }); }
      const hit = (t, term) => t.w === term.w || term.v.indexOf(t.st) >= 0;
      let best = null;
      for (let i = 0; i < toks.length; i++) {
        if (!hit(toks[i], qp.terms[0])) continue;
        const pos = [i];
        let at = i;
        for (let j = 1; j < qp.terms.length; j++) {
          let f = -1;
          for (let x = at + 1; x < toks.length; x++) if (hit(toks[x], qp.terms[j])) { f = x; break; }
          if (f < 0) { pos.length = 0; break; }
          pos.push(f); at = f;
        }
        if (!pos.length) continue;
        const span = pos[pos.length - 1] - i + 1;
        if (span <= qp.k + 3 && (!best || span < best.span)) best = { span: span, pos: pos };
      }
      return best ? best.pos.map(x => [toks[x].s, toks[x].e]) : null;
    }
    const unesc = x => x.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&amp;/g, "&");
    function lineOf(it) {                                       // the line the page shows under the card, or ""
      if (typeof it === "string") return "";
      if (Array.isArray(it)) { const c = CARDS[it[0]], a = it[1] != null && c && c.ab[it[1]]; return a ? a[0] || "" : ""; }
      const m = /<span class="why">([\s\S]*?)<\/span>/.exec(it.html || "");
      return m ? unesc(m[1]) : "";
    }
    function collect(items, qm) {                               // [{oid, line}] one per card, in list order; supported = some card had a line
      const seen = new Set(), out = [], member = qm.layer !== "m" && MERGED && MERGED.by_gid && MERGED.by_gid[qm.gid] ? qm.gid : "";
      let sec = "", supported = false;
      for (const it of items) {
        if (typeof it === "string") { const g = /data-gid="([^"]*)"/.exec(it); if (g && it.indexOf('id="msec-') >= 0) sec = unesc(g[1]); continue; }
        if (member && sec !== member) continue;
        const o = itemOid(it);
        if (!o || seen.has(o)) continue;
        seen.add(o);
        const line = lineOf(it);
        if (line) { supported = true; out.push({ oid: o, line: line }); }
      }
      return { rows: out, supported: supported };
    }
    const rankOf = o => { const m = MI && MI.cards && MI.cards[o]; return m && m[4] != null ? m[4] : null; };
    const nameOf = o => CARDS[o].n.toLowerCase();
    function snippet(line, rg) {
      let a = 0, b = line.length;
      if (line.length > 220) { a = Math.max(0, rg[0][0] - 60); b = Math.min(line.length, Math.max(a + 220, rg[rg.length - 1][1])); }
      let h = a > 0 ? "…" : "", at = a;
      for (const [s, e] of rg) { h += esc(line.slice(at, s)) + "<mark>" + esc(line.slice(s, e)) + "</mark>"; at = e; }
      return h + esc(line.slice(at, b)) + (b < line.length ? "…" : "");
    }
    async function renderQM() {
      const old = $("qmwrap"); if (old) old.remove();
      if (!QM || PINCUR || !selected || canon(selected) !== canon(QM.key)) return;
      const my = ++QSEQ;
      await needManual();
      const again = $("qmwrap"); if (again) again.remove();
      if (my !== QSEQ || !QM || PINCUR || canon(selected) !== canon(QM.key) || !CARDS || !MI) return;
      const vb = $("panel").querySelector(".viewbar"); if (!vb) return;
      const qp = parse(QM.q), tf = window.TF && TF.enabled;
      const all = collect(tf ? TF.items() : LIST, QM);
      if (!all.supported) return;                              // this page shows no ability line under its cards: nothing to match, and nothing to claim
      const full = all.rows.map(x => { const rg = matchLine(x.line, qp); return rg ? { oid: x.oid, line: x.line, rg: rg } : null; }).filter(Boolean);
      const shownSet = new Set((tf ? TF.shownItems() : LIST).map(it => (typeof it === "string" ? null : itemOid(it))).filter(Boolean));
      const rows = full.filter(x => shownSet.has(x.oid));
      rows.sort((x, y) => { const a = rankOf(x.oid), b = rankOf(y.oid); return (a == null) - (b == null) || (a || 0) - (b || 0) || (nameOf(x.oid) < nameOf(y.oid) ? -1 : nameOf(x.oid) > nameOf(y.oid) ? 1 : 0) || (x.oid < y.oid ? -1 : 1); });
      const box = el("div", "qm");
      box.id = "qmwrap";
      const q = esc(QM.q), n = rows.length, plural = (c, w) => c + " " + w + (c === 1 ? "" : "s");
      if (!full.length) {
        box.className = "qnone";
        box.textContent = "Your words (“" + QM.q + "”) are in this group’s description, but no card’s own text has them together.";
      } else if (!n) {
        box.innerHTML = `<div class="qt">These cards matched your query: <b>${q}</b></div><div class="qs">None of the ${plural(full.length, "matching card")} is left after your filters.</div>`;
      } else {
        const cap = Math.min(QM.n, 20, n), shown = rows.slice(0, cap);
        let h = `<div class="qt">These cards matched your query: <b>${q}</b></div><div class="qs">Cards in this group whose own text has your words, most popular first. ${plural(n, "card")} match${n === 1 ? "es" : ""}${n !== full.length ? ` with your filters (${full.length} without)` : ""}.</div>`;
        for (const x of shown) h += `<div class="qr"><span class="nm lnk" data-go="c:${esc(x.oid)}">${esc(CARDS[x.oid].n)}</span><span class="ln">${snippet(x.line, x.rg)}</span><span class="src">ability line</span></div>`;
        if (cap < n && cap < 20) h += `<button type="button" class="qb" data-qm="more">Show more (${plural(Math.min(20, n) - cap, "more card")})</button>`;
        else if (n > cap) h += `<div class="qs">${plural(n - cap, "more card")} match; they are in the list below.</div>`;
        box.innerHTML = h;
        const b = box.querySelector("[data-qm=more]");
        if (b) b.addEventListener("click", () => { QM.n = Math.min(20, QM.n + 10); renderQM(); });
      }
      const tabs = $("sctabs");
      vb.parentNode.insertBefore(box, tabs && tabs.parentNode === vb.parentNode ? tabs : vb);
      if (SCCUR && SCCUR.tab === "matches") box.classList.add("sc-off");
    }
    window.QMB_REFRESH = () => { if (QM) renderQM().catch(() => { /* the block is a convenience */ }); };
    window.QMB = { state: () => (QM ? { q: QM.q, key: QM.key, n: QM.n } : null), match: (line, q) => matchLine(line, parse(q)) };
  }
  loadConfig().then(() => { try { initDeckFlags(); } catch (e) { if (window.console) console.error("deck flags", e); } window.__testerGo(); });
})();
