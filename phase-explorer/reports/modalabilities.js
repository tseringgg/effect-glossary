/* Tester mode, feature MODAL_ABILITIES (reports/config.js): an "Abilities" block in the large card view, under "In these groups". It lists the ability pages the card is on (triggered, activated, static,
 * replacement) as chips, each with the card's own line beneath, and the card's keyword abilities as chips to the existing keyword pages. Loaded by reports/tester.js only when the flag is on, and only in
 * tester mode; needs ABILITY_TYPE_PAGES (a chip opens an ability page). FLIP_FACES is optional: with it the block follows the Flip control.
 * The block is FILTERS AND LINKS, never placements: it is in no group, no count, no figure, and changes no leaf, group, id, suggestion or page.
 *
 * Data: build/ability_pages/cards.json (written by src/build_ability_cards.py; its format is described there), read the first time a card opens, never at first load. Nothing is sent anywhere.
 * A chip carries data-go="ab:..." (or "yk:..."), so the modal's own click handler closes the card and opens the page, exactly as a group chip does.
 */
"use strict";
(function () {
  const KINDS = [["trig", "Triggered"], ["act", "Activated"], ["stat", "Static"], ["repl", "Replacement"]];
  const NOTE = {
    1: "This spell’s effect is not an ability type. Ability pages cover triggered, activated, static and replacement abilities.",
    2: "The parser read this card’s abilities, but none is a kind that has an ability page yet.",
    3: "No abilities the parser could read.",
    4: "Keyword abilities only. They have no ability page."
  };
  let DOC = null, PROM = null, ORDER = null, REC = null, XS = null;
  let FOLD = null;                                                // the person's choice on a narrow screen: true = folded; null = not chosen (folded when narrow)
  const narrow = () => window.matchMedia("(max-width: 500px)").matches;

  function fnv(oids) {                                            // the same checksum as src/build_ability_pages.py
    let h = 2166136261, i, j, s;
    for (i = 0; i < oids.length; i++) {
      s = oids[i];
      if (i) { h ^= 10; h = Math.imul(h, 16777619) >>> 0; }
      for (j = 0; j < s.length; j++) { h ^= s.charCodeAt(j); h = Math.imul(h, 16777619) >>> 0; }
    }
    return ("00000000" + h.toString(16)).slice(-8);
  }
  function load() {
    if (!PROM) PROM = (async () => {
      await needCards();
      const d = await J("ability_pages/cards.json");
      ORDER = Object.keys(CARDS);
      if (d.sig !== fnv(ORDER)) throw new Error("modalabilities: built for another card list");
      REC = new Map(); XS = new Map();
      for (const x of d.x) { const k = x[0] + ":" + x[1]; if (!XS.has(k)) XS.set(k, []); XS.get(k).push(x[2]); }
      let ci = 0;
      for (let i = 0; i < d.d.length;) {
        ci += d.d[i]; const h = d.d[i + 1], n = h >> 12, k = (h >> 8) & 15;
        const es = [], ks = [];
        for (let e = 0; e < n; e++) { const v = d.d[i + 2 + e]; es.push({ p: v & 63, l: ((v >> 6) & 127) - 1, f: v >> 13 }); }
        for (let e = 0; e < k; e++) ks.push(d.d[i + 2 + n + e]);
        REC.set(ci, { st: h & 15, miss: (h >> 4) & 15, es: es, ks: ks });
        i += 2 + n + k;
      }
      DOC = d;
      return d;
    })().catch(e => { PROM = null; if (window.console) console.warn(e.message); return null; });
    return PROM;
  }

  // ---------------------------------------------------------------- what to show for a card and a face
  function entries(oid, face) {                                   // [{ p: page no, ls: [line text...] }] for the face (face null: every face)
    const ci = ORDER.indexOf(oid), r = ci >= 0 ? REC.get(ci) : null;
    if (!r) return { r: null, rows: [] };
    const lines = (CARDS[oid].t || "").split("\n"), by = new Map();
    for (const e of r.es) {
      if (face != null && e.f !== face) continue;
      const xs = e.l < 0 ? (XS.get(ci + ":" + e.p) || []) : [lines[e.l]];
      if (!by.has(e.p)) by.set(e.p, { p: e.p, first: e.l < 0 ? 1e9 : e.l, ls: [] });
      const b = by.get(e.p);
      for (const t of xs) if (t && b.ls.indexOf(t) < 0) b.ls.push(t);
      if (e.l >= 0 && e.l < b.first) b.first = e.l;
    }
    return { r: r, rows: [...by.values()] };
  }
  function blockHTML(oid, face) {
    const c = CARDS[oid]; if (!c) return "";
    const hasText = (c.t || "").trim() !== "";
    const { r, rows } = entries(oid, face), P = DOC.pages;
    const all = r ? r.es.length : 0;
    const body = [];
    let npages = 0;
    for (const [kind, label] of KINDS) {
      const ks = rows.filter(x => P[x.p][0].slice(3).split(".")[0] === kind).sort((a, b) => a.first - b.first || a.p - b.p);
      if (!ks.length) continue;
      npages += ks.length;
      const groups = new Map();                                   // pages that show exactly the same lines sit together over one copy of them
      for (const x of ks) { const g = x.ls.join("\n"); if (!groups.has(g)) groups.set(g, []); groups.get(g).push(x); }
      body.push(`<div class="makind">${label}</div>`);
      for (const xs of groups.values()) {
        const ls = xs[0].ls, shown = ls.slice(0, 3), more = ls.length - shown.length;
        const chips = xs.map(x => {
          const others = xs.filter(y => y !== x).map(y => P[y.p][1]);
          const tip = ls.length ? (others.length ? `Same line as ${others.join(" and ")}: ${ls[0]}` : ls[0]) : "";
          return `<span class="lnk chip ab" data-go="${esc(P[x.p][0])}" tabindex="0" role="link"${tip ? ` title="${esc(tip)}"` : ""}>${esc(P[x.p][1])}</span>`;
        }).join(" ");
        body.push(`<div class="maent">${chips}${shown.map(t => `<div class="maln">${esc(t)}</div>`).join("")}${more > 0 ? `<div class="mamore">+${more} more matching abilit${more === 1 ? "y" : "ies"}</div>` : ""}</div>`);
      }
    }
    if (r && r.ks.length) {
      body.push(`<div class="makind">Keyword abilities</div><div class="maent">` + r.ks.map(k => `<span class="lnk chip kw" data-go="yk:${esc(DOC.kw[k][0])}" tabindex="0" role="link">${esc(DOC.kw[k][1])}</span>`).join(" ") + `</div>`);
    }
    if (!npages) {
      if (all && face != null) body.unshift(`<div class="manote">No ability pages on this face.</div>`);
      else if (r && NOTE[r.st & 7]) body.unshift(`<div class="manote">${NOTE[r.st & 7]}</div>`);
      else if (hasText && !(r && r.ks.length)) body.unshift(`<div class="manote">${NOTE[3]}</div>`);
    }
    if (r && r.miss) body.push(`<div class="manote">${r.miss === 1 ? "1 more ability of this card is not on any ability page." : r.miss + " more abilities of this card are not on any ability page."}</div>`);
    if (r && (r.st & 8)) body.push(`<div class="manote">Part of this card’s text was not read by the parser, so some of its abilities may be missing.</div>`);
    if (!body.length) return "";
    const where = face != null ? ` · ${face ? "back face" : "front face"}` : "";
    const fold = FOLD === null ? narrow() : FOLD;
    const sum = npages ? `${npages} ability page${npages === 1 ? "" : "s"}` : r && r.ks.length ? `${r.ks.length} keyword${r.ks.length === 1 ? "" : "s"}` : "none";
    return `<div class="mabl${fold ? " folded" : ""}" data-ma="1"><h3>Abilities<span class="macount">${esc(where)}${npages || (r && r.ks.length) ? " · " + esc(sum) : ""}</span></h3>` +
      `<button type="button" class="masum" data-ma-fold="1" aria-expanded="${fold ? "false" : "true"}"><b>Abilities${npages ? " · " + npages : ""}</b><span class="mapv">${esc(where.replace(/^ · /, ""))}</span><span aria-hidden="true">${fold ? "▸" : "▾"}</span></button>` +
      `<div class="mabody">${body.join("")}</div></div>`;
  }

  // ---------------------------------------------------------------- the modal
  function curFace(oid, modal) {                                  // null: the card is not two-faced (or the Flip control is off); else 0 or 1
    const fl = window.FL && FL.get ? FL.get(oid) : null;
    if (!fl) return null;
    const b = modal.querySelector(".flipbtn[data-face]");
    return b ? Number(b.getAttribute("data-face")) || 0 : 0;
  }
  function paint(oid, modal) {
    const box = modal.querySelector(".tinfo");
    if (!box || !box.isConnected || !REC) return;
    const rep = box.querySelector("a[data-report]");
    if (rep && rep.dataset.oid !== oid) return;                   // the dialog now shows another card
    const old = box.querySelector(".mabl"); if (old) old.remove();
    const html = blockHTML(oid, curFace(oid, modal));
    if (!html) return;
    const anchor = rep ? rep.parentElement : null;
    if (anchor) anchor.insertAdjacentHTML("beforebegin", html); else box.insertAdjacentHTML("beforeend", html);
  }
  async function attach(oid, modal) {
    const d = await load();
    if (!d || modal.hidden || !modal.querySelector(".tinfo")) return;
    if (window.FL && FL.load) { try { await FL.load(); } catch (e) { /* the block shows every face */ } }
    if (modal.hidden || !modal.querySelector(".tinfo") || modal.querySelector("h2") == null) return;
    paint(oid, modal);
    const box = modal.querySelector(".tbox");
    if (box && window.MutationObserver) {                         // the Flip control sets data-face on its button when it paints: the block follows
      const mo = new MutationObserver(() => { if (modal.hidden) { mo.disconnect(); return; } paint(oid, modal); });
      mo.observe(box, { subtree: true, attributes: true, attributeFilter: ["data-face"] });
    }
  }
  document.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest("[data-ma-fold]");
    if (!b) return;
    const blk = b.closest(".mabl"); if (!blk) return;
    FOLD = !blk.classList.contains("folded");
    blk.classList.toggle("folded", FOLD);
    b.setAttribute("aria-expanded", FOLD ? "false" : "true");
    b.lastElementChild.textContent = FOLD ? "▸" : "▾";
  });
  document.addEventListener("keydown", e => {
    if ((e.key === "Enter" || e.key === " ") && e.target.classList && e.target.classList.contains("chip") && e.target.closest(".mabl")) { e.preventDefault(); e.target.click(); }
  });

  window.MA = { enabled: true, attach: attach, load: load, blockHTML: blockHTML };
})();
