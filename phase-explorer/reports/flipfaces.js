/* Tester mode, feature FLIP_FACES (reports/config.js): both faces of a two-faced card.
 * Loaded by reports/tester.js only when the flag is on, and only in tester mode. Presentation only: it changes no group, id, placement, suggestion or figure.
 *
 * Data: build/faces/faces.json (written by src/build_type_groups.py from the MTGJSON file; 861 cards: transform, modal, adventure, split, aftermath, flip, prepare), fetched the first time a card opens,
 * a search is made or a group page is shown. Nothing is sent anywhere.
 *
 *   The large card view has a "Flip" control. It opens on the FIRST face of the card (the page's own record is the back face for about half of the transform and modal cards while the picture is always
 *   the front, so the two could disagree). Transform and modal cards have a picture for each face, and Flip swaps picture, name, cost, type line and text. Adventure, split, aftermath, flip and
 *   prepare cards have one picture holding both halves, so Flip there swaps the text only ("other half").
 *   Search: a name search also finds a card by the name of its other face (40 such names could not be found before), and a result found that way says so.
 *   Filters (testerfilters.js): colour and type read both faces; a card shown only because of its other face says which.
 */
"use strict";
(function () {
  const $ = id => document.getElementById(id);
  let DATA = null, PROM = null;
  const fnv = oids => {                                           // same checksum as src/build_type_groups.py
    let h = 2166136261, i, j, s;
    for (i = 0; i < oids.length; i++) { s = oids[i]; if (i) { h ^= 10; h = Math.imul(h, 16777619) >>> 0; } for (j = 0; j < s.length; j++) { h ^= s.charCodeAt(j); h = Math.imul(h, 16777619) >>> 0; } }
    return ("00000000" + h.toString(16)).slice(-8);
  };
  function load() {
    if (!PROM) PROM = (async () => {
      await needCards();
      const d = await J("faces/faces.json");
      if (d.sig !== fnv(Object.keys(CARDS))) throw new Error("faces.json was built for another card list");
      DATA = d;
      if (window.TF) { try { TF.invalidate(); TF.refresh(); } catch (e) { /* no list is open */ } }
      return d;
    })().catch(e => { PROM = null; if (window.console) console.warn("flipfaces: " + e.message); return null; });
    return PROM;
  }
  const get = oid => (DATA ? DATA.cards[oid] || null : null);
  const norm = s => (window.LIDX && LIDX.norm ? LIDX.norm(s) : String(s).toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/ +/g, " ").trim());
  const hasBack = oid => !!(IMGDOC && IMGDOC.cards[oid] && IMGDOC.cards[oid][2]);

  // ---------------------------------------------------------------- the card view
  const HALF = { adventure: "adventure half", split: "other half", aftermath: "other half", flip: "flipped half", prepare: "other half" };
  function faceHTML(oid, fl, i) {
    const f = fl.f[i];
    return { name: f.n, cost: f.mc ? `<span class="cost" title="mana cost">${esc(f.mc)}</span>` : `<span class="cost" title="no mana cost">no cost</span>`, ty: f.ty, text: f.t };
  }
  async function attach(oid, modal) {
    const box = modal.querySelector(".tbox");
    await load();
    const fl = get(oid);
    if (!fl || !box || !box.isConnected) return;                  // not a two-faced card, or the dialog was closed / changed meanwhile
    const both = hasBack(oid), word = both ? "back" : (HALF[fl.l] || "other half");
    let cur = 0;
    const big = box.querySelector(".tbig"), info = box.querySelector(".tinfo");
    if (!big || !info) return;
    big.insertAdjacentHTML("afterbegin", `<div class="flipbar"><button type="button" class="flipbtn" data-flip="1" aria-label="Flip card"><span aria-hidden="true">⟲</span> Flip</button><span class="flipst" aria-live="polite"></span></div>`);
    const btn = big.querySelector(".flipbtn"), st = big.querySelector(".flipst");
    const paint = () => {
      const f = faceHTML(oid, fl, cur), img = big.querySelector("img");
      const h2 = info.querySelector("h2"), tsrc = info.querySelector(".tsrc"), orc = info.querySelector(".toracle");
      if (h2) h2.textContent = f.name;
      if (tsrc) tsrc.innerHTML = `${f.cost} ${esc(f.ty)}`;
      if (orc) orc.textContent = f.text;
      if (both && img) { const u = imageURL(oid, "large"); if (u) { img.src = cur ? u.replace("/front/", "/back/") : u; img.alt = f.name; } }
      st.textContent = both ? (cur ? "Back face" : "Front face") : (cur ? "Showing the " + word : "Showing the first half") + ". One picture shows both halves.";
      btn.setAttribute("data-face", String(cur));
      btn.title = both ? "Show the " + (cur ? "front" : "back") + " face: " + fl.f[1 - cur].n : "Show the other half: " + fl.f[1 - cur].n;
    };
    btn.addEventListener("click", () => { cur = 1 - cur; paint(); });
    const full = info.querySelector("h2");
    if (full && !info.querySelector(".fullname")) full.insertAdjacentHTML("afterend", `<div class="tsrc fullname">${esc(CARDS[oid].n === fl.f[0].n || CARDS[oid].n === fl.f[1].n ? fl.f.map(x => x.n).join(" // ") : CARDS[oid].n)}</div>`);
    paint();
  }

  // ---------------------------------------------------------------- search: either face's name
  async function supplement(q) {
    const out = $("findres"); if (!out || !q.trim()) return;
    await load(); if (!DATA) return;
    const nq = norm(q); if (nq.length < 3) return;
    const have = new Set([...out.querySelectorAll("[data-go]")].map(e => e.dataset.go.replace(/^(pin|c):/, "")));
    const words = nq.split(" ");
    const hits = [];
    for (const [oid, fl] of Object.entries(DATA.cards)) {
      if (!CARDS[oid]) continue;
      for (let i = 0; i < 2; i++) {
        const fnm = norm(fl.f[i].n);
        if (fnm === nq || fnm.indexOf(nq) === 0 || words.every(w => fnm.split(" ").some(x => x.indexOf(w) === 0))) { hits.push({ oid: oid, i: i, rank: fnm === nq ? 0 : fnm.indexOf(nq) === 0 ? 1 : 2, name: fl.f[i].n }); break; }
      }
    }
    hits.sort((a, b) => a.rank - b.rank || (CARDS[a.oid].n < CARDS[b.oid].n ? -1 : 1));
    // a result already listed gets its note; a card the name search could not find is added
    const rows = [...out.querySelectorAll(".fr[data-go]")];
    for (const h of hits) {
      const fl = get(h.oid), why = `matched: ${h.i === fl.pf ? "" : "other face "}“${h.name}”`;
      const row = rows.find(r => r.dataset.go.replace(/^(pin|c):/, "") === h.oid);
      if (row) { if (h.i !== fl.pf && !row.querySelector(".flipwhy")) row.insertAdjacentHTML("beforeend", ` <span class="sub flipwhy">${esc(why)}</span>`); continue; }
    }
    const add = hits.filter(h => !have.has(h.oid)).slice(0, 6);
    if (!add.length) return;
    const host = out.querySelector("#gs-cards") || out;
    const html = add.map(h => `<div class="fr" tabindex="0" data-nav data-go="${PINON ? "pin:" : "c:"}${esc(h.oid)}"><span class="nm">${esc(CARDS[h.oid].n)}</span> <span class="sub flipwhy">matched: other face “${esc(h.name)}”</span></div>`).join("");
    const none = host.querySelector(".gs-none"); if (none) none.remove();
    const nolist = out.querySelector(":scope > .sub");
    if (host === out && nolist && /No card or group matches/.test(nolist.textContent)) nolist.remove();
    host.insertAdjacentHTML("beforeend", html);
  }
  const _find = find;
  find = async function (q) { await _find(q); try { await supplement(q); } catch (e) { if (window.console) console.warn("flipfaces search: " + e.message); } };

  // ---------------------------------------------------------------- lists: load the faces when the first group page opens; a card shown for its other face says so
  const _setList = setList;
  setList = function (head, items, opts) { _setList(head, items, opts); if (!PROM) load(); };
  function decorate() {
    if (!window.TF || !TF.faceNote || !DATA) return;
    for (const el of document.querySelectorAll("#list [data-oid]")) {
      if (el.dataset.fn === "1") continue;
      el.dataset.fn = "1";
      const note = TF.faceNote(el.dataset.oid);
      if (!note) continue;
      if (el.classList.contains("tile")) el.insertAdjacentHTML("afterbegin", `<div class="tvia fnote2">${esc(note)}</div>`);
      else { const top = el.querySelector(".top"); if (top) top.insertAdjacentHTML("afterend", `<div class="sub tgvia">${esc(note)}</div>`); }
    }
  }
  const _renderList = renderList;
  renderList = function () { _renderList(); try { decorate(); } catch (e) { /* the list is as it was */ } };

  window.FL = { enabled: true, on: () => true, load: load, get: get, attach: attach, loaded: () => !!DATA };
})();
