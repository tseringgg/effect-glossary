/* Shared branch treemap.
 *
 * Extracted verbatim from card-explorer.html so browse.html can offer the same
 * overview without a second copy of the layout, the colour decisions or the
 * accessibility work. Squarified treemap (Bruls/Huizing/van Wijk). Branches
 * only -- leaves are never nested inside; the tree is where leaves live.
 *
 * Colour carries the branch's VOCABULARY SOURCE, not its identity -- 38
 * regions is far past the 8-slot cap for categorical hues, and identity is
 * carried by the label instead. Three source slots, fixed order, taken from the
 * validated default palette; validated at pairs=all (any two regions can end up
 * adjacent in a treemap) -- worst CVD dE 9.2, worst normal-vision dE 24.0, both
 * clear. A fourth slot was rejected: it hard-fails the normal-vision floor
 * (yellow<->orange dE 13.7), which is why the two `slang` variants share one
 * slot. Unique effect is deliberately NOT a fourth hue: it is a state, so it
 * gets neutral ink plus a hatch, readable in greyscale and for any colour
 * vision.
 *
 * BM.render(hostEl, {BR, CLU, capEl, legendEl, tipEl, onPick})
 */
const BM = (() => {
const esc = CV.esc;

function worst(row, side) {
  const s = row.reduce((a, b) => a + b, 0);
  const mx = Math.max(...row), mn = Math.min(...row);
  return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn));
}

function squarify(items, X, Y, W, H) {
  const total = items.reduce((s, i) => s + i.value, 0) || 1;
  const scale = (W * H) / total;
  const areas = items.map(i => i.value * scale);
  const out = [];
  let x = X, y = Y, w = W, h = H, i = 0;
  while (i < areas.length) {
    const side = Math.min(w, h);
    let row = [areas[i]], idx = [i], j = i + 1;
    while (j < areas.length) {
      const cand = row.concat([areas[j]]);
      if (worst(cand, side) <= worst(row, side)) { row = cand; idx.push(j); j++; }
      else break;
    }
    const sum = row.reduce((a, b) => a + b, 0);
    if (w >= h) {
      const sw = sum / h;
      let cy = y;
      row.forEach((a, k) => {
        const rh = a / sw;
        out.push({ item: items[idx[k]], x, y: cy, w: sw, h: rh });
        cy += rh;
      });
      x += sw; w -= sw;
    } else {
      const sh = sum / w;
      let cx = x;
      row.forEach((a, k) => {
        const rw = a / sh;
        out.push({ item: items[idx[k]], x: cx, y, w: rw, h: sh });
        cx += rw;
      });
      y += sh; h -= sh;
    }
    i = j;
  }
  return out;
}

// Two `slang` variants are merged into one source slot on purpose -- see the
// four-slot note above.
function srcSlot(source) {
  if (source === "curated") return "curated";
  if (source && source.indexOf("slang") === 0) return "slang";
  return "otag";
}
const SRC_COLOR = { curated: "var(--src-curated)", otag: "var(--src-otag)",
                    slang: "var(--src-slang)" };
const SRC_HEX = { curated: "#2a78d6", otag: "#eb6834", slang: "#1baf7a" };
const UNBR_HEX = "#6b6a66";
const SRC_LABEL = { curated: "curated glossary.yaml", otag: "Scryfall otag",
                    slang: "slang glossary" };

// Label ink is picked per fill, not fixed to white: white on the aqua slot is
// only 2.82:1 and on orange 3.20:1, both under the 4.5:1 text floor. Choosing
// whichever of near-black / white scores higher puts every label >= 4.4:1.
function relLum(hex) {
  const v = [1, 3, 5].map(i => {
    const c = parseInt(hex.substr(i, 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
}
function inkFor(hex) {
  const L = relLum(hex);
  return ((1.05) / (L + 0.05)) >= ((L + 0.05) / 0.05) ? "#ffffff" : "#111111";
}

function render(host, o) {
  const { BR, CLU } = o;
  if (!BR || !CLU || !host) return;
  const uniq = BR.unique_effect || [];
  const uniqCards = uniq.reduce((a, u) => a + u.n_cards, 0);

  const items = BR.branches.filter(b => b.n_leaves).map(b => ({
    key: b.name + (b.auto_named ? " · auto" : ""),
    name: b.name,
    value: b.n_cards, leaves: b.n_leaves, src: srcSlot(b.source),
    rule: b.rule, otags: b.otags, unbr: false, auto: !!b.auto_named,
  }));
  items.push({ key: "Unique effect", name: "Unique effect", value: uniqCards,
               leaves: uniq.length, src: null, unbr: true,
               rule: "structure shared with no other leaf" });
  items.sort((a, b) => b.value - a.value);
  const grand = items.reduce((s, i) => s + i.value, 0);

  if (o.capEl) o.capEl.innerHTML =
    `Regions are <b>branches only</b> — no leaves nested inside; click one to open it ` +
    `in the tree. Area is <b>card count</b>, not leaf count: card count reflects how much ` +
    `of the corpus a branch actually covers, whereas leaf count only reflects how finely ` +
    `that branch happened to split during clustering. ` +
    `<b>Areas do not sum to the corpus</b> — branch assignment is many-to-many, so a card ` +
    `in 3 branches is counted 3 times (${grand.toLocaleString()} region-cards over ` +
    `${CLU.n_cards.toLocaleString()} clustered cards). ` +
    `Colour carries the branch's <b>vocabulary source</b>, not its identity.`;

  const W = host.clientWidth || 1200, H = host.clientHeight || 520;
  const laid = squarify(items, 0, 0, W, H);
  const GAP = 2;   // 2px surface gap between fills

  let h = "";
  const small = [];
  for (const r of laid) {
    const it = r.item;
    const w = Math.max(0, r.w - GAP), hh = Math.max(0, r.h - GAP);
    const bg = it.unbr ? "var(--unbr-ink)" : SRC_COLOR[it.src];
    const ink = inkFor(it.unbr ? UNBR_HEX : SRC_HEX[it.src]);
    // Adaptive labelling: full label, name only, or nothing + tooltip. Never
    // cram unreadable text into a tiny box.
    let inner = "";
    if (w >= 62 && hh >= 30) {
      inner = `<span class="tmn">${esc(it.key)}</span>` +
              `<span class="tmc">${it.value.toLocaleString()} cards · ${it.leaves} leaves</span>`;
    } else if (w >= 40 && hh >= 15) {
      inner = `<span class="tmn">${esc(it.key)}</span>`;
    } else {
      small.push(it.key);
    }
    // A narrow-but-tall box can take a MULTI-WORD name on two lines instead of
    // ellipsising it. Single words are left to ellipsis: breaking "Surveil"
    // into "Survei/l" is harder to read than "Surve...", and the tooltip
    // carries the full name either way.
    const wrap = inner && hh >= 28 && w < 9 * it.key.length
                 && it.key.indexOf(" ") > 0 ? " wrap" : "";
    h += `<div class="tmcell${it.unbr ? " unbr" : ""}${it.auto ? " auto" : ""}${wrap}" data-b="${esc(it.key)}" ` +
         `style="left:${r.x}px;top:${r.y}px;width:${w}px;height:${hh}px;` +
         `background-color:${bg};color:${ink}">${inner}</div>`;
  }
  host.innerHTML = h;

  if (o.legendEl) {
    o.legendEl.innerHTML = Object.keys(SRC_COLOR).map(k =>
      `<span><span class="sw" style="background:${SRC_COLOR[k]}"></span>${SRC_LABEL[k]}</span>`).join("")
      + `<span><span class="sw unbr" style="background:var(--unbr-ink);` +
        `background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.4) 0 3px,rgba(255,255,255,0) 3px 6px)"></span>` +
        `Unique effect (shared with no other leaf)</span>`
      + `<span><span class="sw autosw" style="background-color:var(--src-otag)"></span>` +
        `auto-named (machine-generated, any source colour)</span>`
      + (small.length ? `<span style="color:var(--mut)">too small to label (hover, or use the tree): `
          + small.map(esc).join(", ") + `</span>` : "");
  }

  // hover tooltip -- required for the smallest regions, useful for all
  const tip = o.tipEl;
  host.querySelectorAll(".tmcell").forEach(el => {
    const it = laid.find(r => r.item.key === el.dataset.b).item;
    if (tip) {
      el.onmousemove = ev => {
        tip.style.display = "block";
        tip.style.left = Math.min(ev.clientX + 14, innerWidth - 350) + "px";
        tip.style.top = (ev.clientY + 16) + "px";
        tip.innerHTML = `<b>${esc(it.key)}</b><br>` +
          `${it.value.toLocaleString()} cards · ${it.leaves} leaves · ` +
          `${(100 * it.value / grand).toFixed(1)}% of region area<br>` +
          (it.unbr ? "" : `source: ${esc(it.src)}${it.otags && it.otags.length
              ? " · " + it.otags.map(esc).join(", ") : ""}<br>`) +
          `<span style="opacity:.8">${esc(it.rule)}</span><br>` +
          `<span style="opacity:.8">${o.pickHint || "click to open in the tree"}</span>`;
      };
      el.onmouseleave = () => { tip.style.display = "none"; };
    }
    el.onclick = () => {
      if (tip) tip.style.display = "none";
      if (o.onPick) o.onPick(it.name);
    };
  });
}

return { render, srcSlot, SRC_COLOR, SRC_HEX, SRC_LABEL, inkFor, squarify };
})();
