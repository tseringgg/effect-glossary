/* Shared card rendering + browsing facets.
 *
 * Extracted from card-explorer.html so the browse page renders cards with the
 * SAME code rather than a second, drifting copy: one escaper, one chunk
 * loader, one parsed-structure detail view, one row builder, one filter
 * predicate. card-explorer.html injects its dev-only extras (cluster cell,
 * cluster box) through the `opts` hooks instead of forking the renderer.
 *
 * Plain script, one global `CV` -- no modules, so it loads the same way under
 * src/serve.py as the pages themselves.
 */
const CV = (() => {

const esc = s => String(s == null ? "" : s)
  .replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// highlight the nodes that mean "parser could not represent this"
const hl = s => esc(s).replace(/&quot;(Unimplemented|GenericEffect)&quot;/g,
  '<span class="gapnode">&quot;$1&quot;</span>');

// ---- lazy chunk loader ----------------------------------------------------
// build/index.json holds only search text + interned facet ids; the parsed
// structure is sharded into 64 chunks and fetched on expand. Cached per chunk,
// so a page loads each one at most once however many cards are expanded.
const CHUNKS = new Map();
async function chunk(n) {
  if (!CHUNKS.has(n)) {
    CHUNKS.set(n, fetch(`../build/chunks/${n}.json`).then(r => r.json()));
  }
  return CHUNKS.get(n);
}
// Structure that does not live in build/chunks/ (the recovered-card overlay,
// shipped inside build/placements.json) is seeded under its own chunk name.
function seedChunk(n, data) { CHUNKS.set(n, Promise.resolve(data)); }

// ---- browsing facets -----------------------------------------------------
// Values come off the index rows that are already loaded (`col`, `mv`, `cty`,
// built by src/build_index.py from the snapshot's own mana_cost /
// color_override / card_type fields). Nothing here re-derives card data.

const COLOURS = [
  { k: "W", name: "White" }, { k: "U", name: "Blue" }, { k: "B", name: "Black" },
  { k: "R", name: "Red" },   { k: "G", name: "Green" },
];
const COLOUR_NAME = Object.fromEntries(COLOURS.map(c => [c.k, c.name]));

// A face with no mana cost is a distinct state, never mana value 0 -- back
// faces, tokens and most lands have no castable cost at all. The filter says
// so rather than padding the 0 bucket with them.
const NO_COST = "—";

function mvLabel(r) { return r.mv == null ? NO_COST : String(r.mv); }

function colourLabel(r) {
  if (!r.col) return "Colourless";
  return r.col.split("").map(k => COLOUR_NAME[k]).join("/");
}

// Compact mana-cost-ish chip for a row: colour letters + mana value.
function costChip(r) {
  const cols = r.col ? r.col.split("").map(k =>
    `<span class="pip p-${k}" title="${COLOUR_NAME[k]}">${k}</span>`).join("") : "";
  const mv = r.mv == null
    ? `<span class="pip p-none" title="this face has no mana cost (back face, token, or land)">${NO_COST}</span>`
    : `<span class="mv" title="mana value ${r.mv}">${r.mv}</span>`;
  return `<span class="cost">${cols}${!r.col ? `<span class="pip p-C" title="Colourless">C</span>` : ""}${mv}</span>`;
}

// ---- filter state --------------------------------------------------------
// One shape, one predicate, shared by "cards in this leaf" and "cards across
// this whole branch" -- the filters do not care which set they are narrowing.

function newFilter() {
  return {
    q: "",
    colours: new Set(),      // W U B R G, and "C" for colourless
    colourMode: "any",       // any | only  (only = exactly this colour set)
    types: new Set(),        // core types, e.g. Creature
    mvMin: null, mvMax: null,
    mvNoCost: true,          // include no-cost faces when no range is set
  };
}

function filterActive(f) {
  return !!(f.q || f.colours.size || f.types.size ||
            f.mvMin != null || f.mvMax != null || !f.mvNoCost);
}

function match(r, f) {
  if (f.q) {
    const s = r._s || (r._s = (r.name + "\n" + r.text).toLowerCase());
    if (!s.includes(f.q)) return false;
  }
  if (f.colours.size) {
    const have = new Set(r.col ? r.col.split("") : ["C"]);
    if (f.colourMode === "only") {
      if (have.size !== f.colours.size) return false;
      for (const k of have) if (!f.colours.has(k)) return false;
    } else {
      let hit = false;
      for (const k of f.colours) if (have.has(k)) { hit = true; break; }
      if (!hit) return false;
    }
  }
  if (f.types.size) {
    const cty = r.cty || [];
    let hit = false;
    for (const t of cty) if (f.types.has(t)) { hit = true; break; }
    if (!hit) return false;
  }
  if (r.mv == null) {
    // A face with no mana cost has no mana value, so it cannot satisfy a range:
    // once one is set it drops out, and the control says how many that is.
    // Leaving them in would show 0-cost lands under "mana value 2 to 4".
    if (f.mvMin != null || f.mvMax != null) return false;
    if (!f.mvNoCost) return false;
  } else {
    if (f.mvMin != null && r.mv < f.mvMin) return false;
    if (f.mvMax != null && r.mv > f.mvMax) return false;
  }
  return true;
}

// Option counts over a given card set, so every control shows what it would
// actually yield here rather than corpus-wide totals.
function tally(rows) {
  const col = new Map(), typ = new Map(), mv = new Map();
  let noCost = 0;
  for (const r of rows) {
    if (r.col) { for (const k of r.col.split("")) col.set(k, (col.get(k) || 0) + 1); }
    else col.set("C", (col.get("C") || 0) + 1);
    for (const t of (r.cty || [])) typ.set(t, (typ.get(t) || 0) + 1);
    if (r.mv == null) noCost++;
    else mv.set(r.mv, (mv.get(r.mv) || 0) + 1);
  }
  return { col, typ, mv, noCost, n: rows.length };
}

// ---- what the parser matched, inside the card's own text -----------------
// build/match_spans.json holds, per entry, the character range of each
// ability's TOP-LEVEL effect: phase.rs's own `description` for the ability,
// located in the oracle text, then narrowed by src/effect_span.py past the
// cost or trigger condition and before any chained sub-effect. That is the
// part the clustering matched -- it reads `node.effect` and never walks
// sub-abilities -- so "Destroy target creature." is marked on Angrath's Fury
// and the damage and tutor that follow it on the same line are not.
//
// These are THEIR attributions, narrowed; we do not have their regexes, so
// this is not a capture group. 90.6% of abilities are located; the rest carry
// no description (6.3%) or name something that is not card text (3.1%, e.g.
// a Saga's "Chapter 1"). Those are counted, never approximated.
let SPANS = null, SPAN_EFFECTS = [], SPANS_ON = true;

function setSpans(doc) {
  SPANS = doc ? doc.spans : null;
  SPAN_EFFECTS = doc ? (doc.effects || []) : [];
}
function setHighlight(on) { SPANS_ON = !!on; }
function hasSpans() { return !!SPANS; }

// text -> HTML with the matched clauses wrapped. Falls back to plain escaped
// text whenever spans are unavailable or switched off, so the column always
// renders the same words either way.
function markText(id, text) {
  if (!text) return "";
  const sp = SPANS_ON && SPANS ? SPANS[id] : null;
  if (!sp || !sp.length) return esc(text);
  let out = "", pos = 0;
  for (const [start, end, ei] of sp) {
    if (start < pos || start >= text.length) continue;
    out += esc(text.slice(pos, start));
    const eff = SPAN_EFFECTS[ei] || "?";
    out += `<mark class="mt" title="matched as ${esc(eff)} — this ability's top-level effect, the part the clustering read">` +
           esc(text.slice(start, end)) + `</mark>`;
    pos = end;
  }
  return out + esc(text.slice(pos));
}

// The per-node breakdown, for the expanded detail: every clause the parser
// attributed, and every node it attributed nothing to.
function matchedClausesHTML(d) {
  const rows = [];
  let noDesc = 0;
  for (const bucket of ["abilities", "triggers", "static_abilities", "replacements"]) {
    (d[bucket] || []).forEach((node, i) => {
      const desc = node.description;
      if (!desc) { noDesc++; return; }
      const eff = bucket === "abilities" ? (node.effect || {}).type
                : bucket === "static_abilities" ? tagOf(node.mode)
                : ((node.execute || {}).effect || {}).type;
      rows.push(`<div class="mcrow"><span class="mcb">${bucket}[${i}]</span>` +
        `<span class="mce">${esc(eff || "—")}</span>` +
        `<span class="mct">${esc(desc)}</span></div>`);
    });
  }
  if (!rows.length && !noDesc) return "";
  return `<div class="mcbox"><b class="hdr">Abilities the parser matched</b>` +
    `<div class="note">phase.rs's own <code>description</code> per ability — the ` +
    `whole ability, cost and condition and chained sub-effects included. The ` +
    `highlight in the oracle text marks only the named top-level effect within ` +
    `it, which is the part the clustering matched.</div>` + rows.join("") +
    (noDesc ? `<div class="note"><b>${noDesc} node${noDesc > 1 ? "s" : ""} carr${noDesc > 1 ? "y" : "ies"} ` +
      `no description at all</b> — nothing to attribute, so nothing is highlighted ` +
      `for ${noDesc > 1 ? "them" : "it"}.</div>` : "") + `</div>`;
}

// mode arrives either as a bare string or externally tagged, same as upstream
function tagOf(v) {
  if (typeof v === "string") return v;
  if (v && typeof v === "object") return Object.keys(v)[0];
  return null;
}

// ---- card images ---------------------------------------------------------
// build/card_images.json (src/build_images.py) maps our oracle ids onto
// Scryfall card ids, so a URL can be built without storing 33,618 full
// strings. Images load from Scryfall's own CDN, lazily and only in the image
// view -- the ONLY thing in these pages that reaches outside the machine.
// 99.4% of oracle ids have one; every miss is an Alchemy "A-" card, which is
// digital-only and absent from the export they publish.
let IMG = null;

function setImages(doc) { IMG = doc || null; }
function hasImages() { return !!IMG; }

// r is an index row; its id is "<oracle id>" or "<oracle id>/<face>".
function imageURL(r, size) {
  if (!IMG) return null;
  const bits = String(r.id).split("/");
  const rec = IMG.cards[bits[0]];
  if (!rec) return null;
  const [cid, ts, hasBack] = rec;
  const face = (bits.length > 1 && +bits[1] > 0 && hasBack) ? "back" : "front";
  return IMG.template
    .replace("{size}", size || "normal").replace("{face}", face)
    .replace("{a}", cid[0]).replace("{b}", cid[1])
    .replace("{id}", cid).replace("{ts}", ts);
}

// ---- card row ------------------------------------------------------------
// The row shape card-explorer.html has always used. `opts.extra(r)` appends
// dev-only markup (the cluster button) inside the quality cell; `opts.cost`
// adds the colour/mana-value chip the browse page leads with.

function rowHTML(r, opts = {}) {
  const extra = opts.extra ? opts.extra(r) : "";
  return `<td><button data-id="${esc(r.id)}" data-ch="${r.ch}" title="show parsed structure">+</button></td>` +
    `<td class="nm">${esc(r.name)}` +
      (opts.cost ? `<br>${costChip(r)}` : "") +
      (r.layout ? `<br><span class="oid">layout: ${esc(r.layout)}</span>` : "") +
      `<br><span class="oid">${esc(r.id)}</span>` +
      (r.group ? `<br><span class="oid">multi-face group</span>` : "") +
    `</td>` +
    `<td><span class="badge b-${r.q}">${r.q}</span>` +
      (r.gaps ? `<br><span class="oid">${r.gaps} gap node${r.gaps > 1 ? "s" : ""}</span>` : "") +
      (r.warn ? `<br><span class="oid">${r.warn} warning${r.warn > 1 ? "s" : ""}</span>` : "") +
      (r.sg ? `<br><span class="oid" style="color:#7a4bbd">${r.sg} unmodelled</span>` : "") +
      (r.corr ? `<br><span class="badge" style="color:var(--corr);border-color:var(--corr)">⚠ ${r.corr} correction${r.corr > 1 ? "s" : ""}</span>` : "") +
      extra +
    `</td>` +
    `<td class="txt">${markText(r.id, r.text) || '<span class="empty">(no oracle text)</span>'}</td>` +
    `<td>${esc(r.type)}</td>`;
}

// ---- parsed-structure detail --------------------------------------------
// Verbatim the detail view card-explorer.html shipped. `opts.prefix(r)` is
// where the explorer injects its cluster box; the browse page passes a branch
// /leaf provenance box through the same hook.

function detailHTML(d, r, opts = {}) {
  if (!d) return `<span class="empty">structure missing from chunk ${r.ch}</span>`;
  let h = opts.prefix ? opts.prefix(r) : "";
  h += matchedClausesHTML(d);

  if (d._corrections && d._corrections.length) {
    h += `<div class="corrbox"><b class="hdr">⚠ ${d._corrections.length} correction${d._corrections.length > 1 ? "s" : ""}
      on file for this card — confirmed by hand, missed by every phase.rs signal above.</b>` +
      d._corrections.map(c => `
        <div class="corritem">
          <b>${esc(c.name)}</b> <span class="kindtag">${esc(c.kind)}</span>
          <span class="kindtag">${esc(c.severity)}</span>
          <span class="oid">added ${esc(c.added)} · field: ${esc(c.field)}</span>
          <div style="margin:4px 0">${esc(c.issue)}</div>
          <div class="note"><b>oracle text (evidence):</b></div>
          <pre>${esc(c.evidence.oracle_text)}</pre>
          <div class="note"><b>upstream snippet as parsed (evidence, byte-for-byte from the snapshot):</b></div>
          <pre>${esc(JSON.stringify(c.evidence.upstream_snippet, null, 1))}</pre>
          ${c.patch ? `<div class="note"><b>patch applied:</b></div><pre>${esc(JSON.stringify(c.patch, null, 1))}</pre>`
                    : `<div class="note"><b>no patch applied</b> — ${esc(c.note || "")}</div>`}
        </div>`).join("") +
      `</div>`;
  }

  if (d.parse_warnings && d.parse_warnings.length) {
    h += `<div class="warnbox"><b>parse_warnings (${d.parse_warnings.length})</b> — upstream
      flagged these itself:<pre>${esc(JSON.stringify(d.parse_warnings, null, 1))}</pre></div>`;
  } else {
    h += `<div class="nowarn"><b>No parse_warnings on this entry — that is not a
      verification.</b> This field is known to stay empty while real clauses are dropped
      (see header). Read the structure below against the oracle text yourself.</div>`;
  }

  for (const [k, label] of [["abilities", "abilities"], ["triggers", "triggers"],
        ["static_abilities", "static_abilities"], ["replacements", "replacements"]]) {
    const v = d[k] || [];
    h += `<div class="bucket"><h4>${label} <span class="oid">(${v.length})</span></h4>` +
         (v.length ? `<pre>${hl(JSON.stringify(v, null, 1))}</pre>`
                   : `<span class="empty">none</span>`) + `</div>`;
  }

  const extra = {};
  for (const k of ["modal", "additional_cost", "casting_restrictions", "casting_options",
                   "solve_condition", "strive_cost", "keywords", "mana_cost", "card_type",
                   "power", "toughness", "loyalty", "defense", "layout", "printings",
                   "legalities", "scryfall_oracle_id", "_export_key"]) {
    if (d[k] !== null && d[k] !== undefined &&
        !(Array.isArray(d[k]) && !d[k].length) &&
        !(typeof d[k] === "object" && !Array.isArray(d[k]) && !Object.keys(d[k]).length)) {
      extra[k] = d[k];
    }
  }
  h += `<div class="bucket"><h4>other fields</h4><pre>${esc(JSON.stringify(extra, null, 1))}</pre></div>`;
  return h;
}

// Expand/collapse a row into its parsed structure. `opts.wire(td)` gets the
// detail cell so a page can hook up whatever links it injected via `prefix`.
async function toggleDetail(btn, r, tr, opts = {}) {
  if (tr.nextSibling && tr.nextSibling.classList?.contains("det")) {
    tr.nextSibling.remove(); btn.textContent = "+"; return;
  }
  btn.textContent = "…";
  const data = (await chunk(r.ch))[r.id];
  btn.textContent = "−";
  const det = document.createElement("tr");
  det.className = "det";
  const td = document.createElement("td");
  td.colSpan = 5;
  td.innerHTML = detailHTML(data, r, opts);
  det.appendChild(td);
  tr.after(det);
  if (opts.wire) opts.wire(td);
}

return { esc, hl, chunk, seedChunk, COLOURS, COLOUR_NAME, NO_COST, mvLabel, colourLabel,
         costChip, newFilter, filterActive, match, tally, rowHTML, detailHTML,
         toggleDetail, setSpans, setHighlight, hasSpans, markText,
         setImages, hasImages, imageURL };
})();
