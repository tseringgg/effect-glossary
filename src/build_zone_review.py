"""Build the full-corpus zone review page.

    reports/zone-review.html      the page (static, open directly from disk)
    reports/zone-review.data.js   the data, loaded by <script src> -- works on
                                  file:// where fetch() of a .json would not

A flat audit table over data/full/effects.json: filter by one or more zones
(any / all), text search across raw_text, plain_text and card names, sort, and
paginate. Not the exploration UI -- no grouping, no map.

Rule evidence is recomputed here with classify_zones (raw_text only, as in
build_full_glossary.py), so every label can be traced to the rule that fired.
If the stored zones disagree with a fresh classification -- classify_zones.py
edited without rebuilding -- the page says so at the top.
"""
import datetime
import html
import json
import os

import classify_zones as cz

HERE = os.path.dirname(os.path.abspath(__file__))
FULL = os.path.join(HERE, os.pardir, "data", "full")
REPORTS = os.path.join(HERE, os.pardir, "reports")
HTML_PATH = os.path.join(REPORTS, "zone-review.html")
DATA_PATH = os.path.join(REPORTS, "zone-review.data.js")

CSS = """
:root {
  --paper: #EDF1EF; --surface: #FAFCFB; --surface-2: #E3EAE7;
  --ink: #141A19; --ink-soft: #4A5754; --ink-faint: #7B8783;
  --rule: #C8D3CE; --rule-soft: #DCE4E1;
  --accent: #1F6F5C; --accent-wash: #DCEAE5; --on-accent: #FFFFFF;
  --warn: #A8434A; --warn-wash: #F4E1E2; --mark: #F3E3A6;
  --z-library: #3F6FB0; --z-hand: #8A5CB0; --z-battlefield: #2F8A5C;
  --z-graveyard: #6B6B6B; --z-exile: #B07A2F; --z-stack: #B04F7A;
  --z-command: #5C8AB0; --z-mana: #2F9AA8; --z-none: #9AA5A1;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #0E1413; --surface: #161D1B; --surface-2: #1E2725;
    --ink: #DFE7E3; --ink-soft: #A3B0AC; --ink-faint: #74827E;
    --rule: #2C3936; --rule-soft: #222D2B;
    --accent: #5CC3A4; --accent-wash: #16302A; --on-accent: #0E1413;
    --warn: #E0868C; --warn-wash: #3A1F22; --mark: #5A4A14;
    --z-library: #7FA8E0; --z-hand: #BC95E0; --z-battlefield: #6FCB98;
    --z-graveyard: #A8A8A8; --z-exile: #E0B06F; --z-stack: #E08AB0;
    --z-command: #95BCE0; --z-mana: #6FD0DC; --z-none: #6B7874;
  }
}
:root[data-theme="dark"] {
  --paper: #0E1413; --surface: #161D1B; --surface-2: #1E2725;
  --ink: #DFE7E3; --ink-soft: #A3B0AC; --ink-faint: #74827E;
  --rule: #2C3936; --rule-soft: #222D2B;
  --accent: #5CC3A4; --accent-wash: #16302A; --on-accent: #0E1413;
  --warn: #E0868C; --warn-wash: #3A1F22; --mark: #5A4A14;
  --z-library: #7FA8E0; --z-hand: #BC95E0; --z-battlefield: #6FCB98;
  --z-graveyard: #A8A8A8; --z-exile: #E0B06F; --z-stack: #E08AB0;
  --z-command: #95BCE0; --z-mana: #6FD0DC; --z-none: #6B7874;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1500px; margin: 0 auto; padding: 24px 20px 48px; }
h1 { font-size: 20px; margin: 0 0 4px; }
.lede { color: var(--ink-soft); margin: 0 0 14px; }
.stale, .error { background: var(--warn-wash); color: var(--warn); border: 1px solid var(--warn);
  padding: 10px 12px; border-radius: 6px; margin: 0 0 14px; }
.panel { position: sticky; top: 0; z-index: 3; background: var(--paper); padding: 10px 0 8px;
  border-bottom: 1px solid var(--rule); margin-bottom: 10px; }
.zonebar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 8px; }
.zbtn { font: inherit; font-size: 12px; cursor: pointer; padding: 3px 9px; border-radius: 999px;
  border: 1px solid var(--rule); border-left: 4px solid var(--zc); background: var(--surface); color: var(--ink); }
.zbtn .n { color: var(--ink-faint); margin-left: 5px; font-variant-numeric: tabular-nums; }
.zbtn.sub { font-weight: 600; }
.zbtn[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: var(--on-accent); }
.zbtn[aria-pressed="true"] .n { color: inherit; opacity: .8; }
.row2 { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.row2 input[type=search] { font: inherit; min-width: 320px; flex: 1 1 320px; max-width: 520px; color: var(--ink);
  background: var(--surface); border: 1px solid var(--rule); border-radius: 6px; padding: 6px 9px; }
.row2 select, .pager button, .pager input, .linkbtn { font: inherit; color: var(--ink); background: var(--surface);
  border: 1px solid var(--rule); border-radius: 6px; padding: 5px 8px; }
.seg { display: inline-flex; border: 1px solid var(--rule); border-radius: 6px; overflow: hidden; }
.seg label { padding: 5px 9px; cursor: pointer; background: var(--surface); font-size: 13px; }
.seg input { position: absolute; opacity: 0; pointer-events: none; }
.seg input:checked + span { font-weight: 600; color: var(--accent); }
.seg input:focus-visible + span { outline: 2px solid var(--accent); outline-offset: 2px; }
.muted { color: var(--ink-soft); }
.pager { display: flex; align-items: center; gap: 6px; margin: 8px 0; flex-wrap: wrap; }
.pager input { width: 64px; text-align: right; }
.pager .status { margin-left: auto; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
.wrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--rule); border-radius: 8px; }
table { border-collapse: collapse; width: 100%; min-width: 1100px; }
th, td { text-align: left; vertical-align: top; padding: 8px 10px; border-bottom: 1px solid var(--rule-soft); }
th { background: var(--surface-2); font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
  color: var(--ink-soft); white-space: nowrap; }
tr:last-child td { border-bottom: 0; }
td.id { font-family: ui-monospace, Consolas, monospace; font-size: 12px; white-space: nowrap; color: var(--ink-soft); }
td.raw { width: 34%; white-space: pre-line; }
td.plain { width: 16%; color: var(--ink-soft); }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.cards { width: 20%; font-size: 13px; }
.none { color: var(--ink-faint); }
.chips { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 4px; }
.chip { font-size: 12px; padding: 1px 7px; border-radius: 999px; border: 1px solid var(--rule);
  border-left: 4px solid var(--zc); background: var(--surface); white-space: nowrap; }
.chip.sub { font-weight: 600; background: var(--accent-wash); }
.chip.empty { font-style: italic; color: var(--ink-faint); }
details { margin-top: 5px; font-size: 12px; color: var(--ink-soft); }
details summary { cursor: pointer; color: var(--ink-faint); }
details ul { margin: 3px 0 0; padding-left: 16px; }
.linkbtn { font-size: 12px; padding: 1px 6px; margin-left: 4px; cursor: pointer; }
mark { background: var(--mark); color: inherit; border-radius: 2px; }
.empty-state { padding: 28px; text-align: center; color: var(--ink-soft); }
"""

JS = r"""
(function () {
  'use strict';
  var D = window.ZONE_REVIEW;
  if (!D) { document.getElementById('load-error').hidden = false; return; }

  var TAGS = D.tags, N = D.effects.length, NONE = -1;
  var $ = function (id) { return document.getElementById(id); };

  // ---- precompute ----
  var hay = new Array(N), topCount = new Array(N);
  for (var i = 0; i < N; i++) {
    var e = D.effects[i];
    var names = e[4].map(function (c) { return D.cards[c]; }).join('\n');
    hay[i] = (e[1] + '\n' + (D.plain[i] || '') + '\n' + names + '\n' + e[0]).toLowerCase();
    var m = e[3] & D.topMask, k = 0;
    while (m) { k += m & 1; m >>>= 1; }
    topCount[i] = k;
  }
  var orders = {};
  function order(key) {
    if (orders[key]) return orders[key];
    var idx = new Array(N);
    for (var i = 0; i < N; i++) idx[i] = i;
    var raw = function (i) { return D.effects[i][1].toLowerCase(); };
    var cmp = {
      'occ-desc': function (a, b) { return D.effects[b][2] - D.effects[a][2] || a - b; },
      'occ-asc': function (a, b) { return D.effects[a][2] - D.effects[b][2] || a - b; },
      'zones-desc': function (a, b) { return topCount[b] - topCount[a] || D.effects[b][2] - D.effects[a][2] || a - b; },
      'raw-az': function (a, b) { var x = raw(a), y = raw(b); return x < y ? -1 : x > y ? 1 : a - b; }
    }[key];
    idx.sort(cmp);
    return (orders[key] = idx);
  }

  // ---- state <-> hash ----
  var S = { sel: new Set(), mode: 'any', q: '', sort: 'occ-desc', page: 1, size: 100 };
  var expanded = new Set();
  function readHash() {
    var p = new URLSearchParams(location.hash.slice(1));
    S.sel = new Set();
    (p.get('zones') || '').split(',').forEach(function (t) {
      if (t === 'none') S.sel.add(NONE);
      else if (TAGS.indexOf(t) !== -1) S.sel.add(TAGS.indexOf(t));
    });
    S.mode = p.get('mode') === 'all' ? 'all' : 'any';
    S.q = p.get('q') || '';
    S.sort = ['occ-desc', 'occ-asc', 'zones-desc', 'raw-az'].indexOf(p.get('sort')) !== -1 ? p.get('sort') : 'occ-desc';
    S.size = [50, 100, 250].indexOf(+p.get('size')) !== -1 ? +p.get('size') : 100;
    S.page = Math.max(1, parseInt(p.get('page'), 10) || 1);
  }
  function writeHash() {
    var p = new URLSearchParams();
    if (S.sel.size) p.set('zones', Array.from(S.sel).map(function (t) { return t === NONE ? 'none' : TAGS[t]; }).join(','));
    if (S.mode !== 'any') p.set('mode', S.mode);
    if (S.q) p.set('q', S.q);
    if (S.sort !== 'occ-desc') p.set('sort', S.sort);
    if (S.size !== 100) p.set('size', S.size);
    if (S.page > 1) p.set('page', S.page);
    var h = p.toString();
    history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
  }

  // ---- filter ----
  var result = [], counts = [];
  function run() {
    var needle = S.q.trim().toLowerCase();
    var sel = Array.from(S.sel), all = S.mode === 'all';
    counts = new Array(TAGS.length + 1).fill(0);
    result = [];
    var ord = order(S.sort);
    for (var j = 0; j < N; j++) {
      var i = ord[j];
      if (needle && hay[i].indexOf(needle) === -1) continue;
      var m = D.effects[i][3];
      if (m === 0) counts[TAGS.length]++;
      else for (var t = 0; t < TAGS.length; t++) if (m & (1 << t)) counts[t]++;
      if (sel.length) {
        var hits = 0;
        for (var s = 0; s < sel.length; s++) {
          if (sel[s] === NONE ? m === 0 : (m & (1 << sel[s])) !== 0) hits++;
        }
        if (all ? hits !== sel.length : hits === 0) continue;
      }
      result.push(i);
    }
  }

  // ---- render ----
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function highlight(text, needle) {
    if (!needle) return esc(text);
    var low = text.toLowerCase(), out = '', from = 0, at;
    while ((at = low.indexOf(needle, from)) !== -1) {
      out += esc(text.slice(from, at)) + '<mark>' + esc(text.slice(at, at + needle.length)) + '</mark>';
      from = at + needle.length;
    }
    return out + esc(text.slice(from));
  }
  function zoneColor(tag) { return 'var(' + D.colors[tag.split(':')[0]] + ')'; }
  function chip(tag) {
    return '<span class="chip' + (tag.indexOf(':') !== -1 ? ' sub' : '') + '" style="--zc:' + zoneColor(tag) + '">' + esc(tag) + '</span>';
  }

  function renderZoneBar() {
    var html = TAGS.map(function (tag, t) {
      return '<button type="button" class="zbtn' + (tag.indexOf(':') !== -1 ? ' sub' : '') + '" data-tag="' + t +
        '" aria-pressed="' + S.sel.has(t) + '" style="--zc:' + zoneColor(tag) + '">' + esc(tag) +
        '<span class="n">' + counts[t].toLocaleString() + '</span></button>';
    }).join('');
    html += '<button type="button" class="zbtn" data-tag="' + NONE + '" aria-pressed="' + S.sel.has(NONE) +
      '" style="--zc:var(--z-none)">no zones<span class="n">' + counts[TAGS.length].toLocaleString() + '</span></button>';
    $('zonebar').innerHTML = html;
  }

  function renderPager(el, pages) {
    var from = result.length ? (S.page - 1) * S.size + 1 : 0, to = Math.min(result.length, S.page * S.size);
    el.innerHTML =
      '<button type="button" data-go="prev"' + (S.page <= 1 ? ' disabled' : '') + '>&larr; Prev</button>' +
      '<span class="muted">Page</span> <input type="number" min="1" max="' + pages + '" value="' + S.page + '" data-go="to" aria-label="Page number">' +
      '<span class="muted">of ' + pages.toLocaleString() + '</span>' +
      '<button type="button" data-go="next"' + (S.page >= pages ? ' disabled' : '') + '>Next &rarr;</button>' +
      '<span class="status">' + from.toLocaleString() + '&ndash;' + to.toLocaleString() + ' of ' +
      result.length.toLocaleString() + ' effects</span>';
  }

  function renderRows() {
    var needle = S.q.trim().toLowerCase();
    var pages = Math.max(1, Math.ceil(result.length / S.size));
    if (S.page > pages) S.page = pages;
    renderPager($('pager-top'), pages);
    renderPager($('pager-bottom'), pages);
    var slice = result.slice((S.page - 1) * S.size, S.page * S.size);
    if (!slice.length) {
      $('rows').innerHTML = '<tr><td colspan="6" class="empty-state">No effects match these filters.</td></tr>';
      return;
    }
    $('rows').innerHTML = slice.map(function (i) {
      var e = D.effects[i], m = e[3];
      var zones = TAGS.filter(function (_, t) { return m & (1 << t); });
      var chips = zones.length ? zones.map(chip).join('') : '<span class="chip empty" style="--zc:var(--z-none)">no zones</span>';
      var ev = {};
      e[5].forEach(function (r) { var p = D.rules[r].split('|'); (ev[p[0]] = ev[p[0]] || []).push(p[1]); });
      var evHtml = zones.length ? '<details><summary>rules fired</summary><ul>' + zones.map(function (z) {
        return '<li><b>' + esc(z) + '</b>: ' + esc((ev[z] || []).join(', ')) + '</li>';
      }).join('') + '</ul></details>' : '';
      var cards = e[4], shown = expanded.has(i) ? cards : cards.slice(0, 6);
      var names = shown.map(function (c) { return highlight(D.cards[c], needle); }).join(' &middot; ');
      var more = cards.length > 6
        ? '<button type="button" class="linkbtn" data-more="' + i + '">' + (expanded.has(i) ? 'less' : '+' + (cards.length - 6).toLocaleString() + ' more') + '</button>'
        : '';
      var plain = D.plain[i];
      return '<tr>' +
        '<td class="id">' + esc(e[0]) + '</td>' +
        '<td class="raw">' + highlight(e[1], needle) + '</td>' +
        '<td class="plain">' + (plain ? highlight(plain, needle) : '<span class="none">&mdash;</span>') + '</td>' +
        '<td><div class="chips">' + chips + '</div>' + evHtml + '</td>' +
        '<td class="num">' + e[2].toLocaleString() + '</td>' +
        '<td class="cards">' + names + more + '</td>' +
        '</tr>';
    }).join('');
  }

  function update(resetPage) {
    if (resetPage) S.page = 1;
    run();
    renderZoneBar();
    renderRows();
    writeHash();
  }

  // ---- events ----
  $('zonebar').addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-tag]');
    if (!b) return;
    var t = +b.dataset.tag;
    S.sel.has(t) ? S.sel.delete(t) : S.sel.add(t);
    update(true);
  });
  var timer;
  $('q').addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(function () { S.q = $('q').value; update(true); }, 150);
  });
  document.querySelectorAll('input[name=mode]').forEach(function (r) {
    r.addEventListener('change', function () { S.mode = r.value; update(true); });
  });
  $('sort').addEventListener('change', function () { S.sort = $('sort').value; update(true); });
  $('size').addEventListener('change', function () { S.size = +$('size').value; update(true); });
  $('clear').addEventListener('click', function () {
    S.sel = new Set(); S.q = ''; S.mode = 'any'; $('q').value = '';
    document.querySelector('input[name=mode][value=any]').checked = true;
    update(true);
  });
  function onPager(ev) {
    var b = ev.target.closest('[data-go]');
    if (!b || b.tagName === 'INPUT') return;
    S.page += b.dataset.go === 'next' ? 1 : -1;
    renderRows(); writeHash();
    $('table-top').scrollIntoView({ block: 'start' });
  }
  function onPageInput(ev) {
    if (!ev.target.matches('input[data-go=to]')) return;
    var v = parseInt(ev.target.value, 10);
    if (v >= 1) { S.page = v; renderRows(); writeHash(); }
  }
  ['pager-top', 'pager-bottom'].forEach(function (id) {
    $(id).addEventListener('click', onPager);
    $(id).addEventListener('change', onPageInput);
  });
  $('rows').addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-more]');
    if (!b) return;
    var i = +b.dataset.more;
    expanded.has(i) ? expanded.delete(i) : expanded.add(i);
    renderRows();
  });
  window.addEventListener('hashchange', function () { readHash(); syncControls(); update(false); });

  function syncControls() {
    $('q').value = S.q;
    $('sort').value = S.sort;
    $('size').value = String(S.size);
    document.querySelector('input[name=mode][value=' + S.mode + ']').checked = true;
  }

  readHash();
  syncControls();
  update(false);
  document.body.dataset.ready = '1';
})();
"""


def load():
    with open(os.path.join(FULL, "effects.json"), encoding="utf-8") as fh:
        effects = json.load(fh)["effects"]
    with open(os.path.join(FULL, "cards.jsonl"), encoding="utf-8") as fh:
        names = {c["card_id"]: c["name"] for c in map(json.loads, fh)}
    manifest = {}
    mpath = os.path.join(FULL, "ingest_manifest.json")
    if os.path.exists(mpath):
        with open(mpath, encoding="utf-8") as fh:
            manifest = json.load(fh)
    return effects, names, manifest


def build_data(effects, names):
    tag_bit = {t: i for i, t in enumerate(cz.ALL_TAGS)}
    card_index, card_names = {}, []
    rule_index, rules = {}, []
    rows, plain, stale = [], {}, []

    for n, e in enumerate(effects):
        zones, evidence, _ = cz.classify(e["raw_text"], "")
        if zones != e["zones"]:
            stale.append(e["effect_id"])
        mask = 0
        for t in e["zones"]:
            mask |= 1 << tag_bit[t]
        refs = []
        for cid in e["card_ids"]:
            if cid not in card_index:
                card_index[cid] = len(card_names)
                card_names.append(names.get(cid, cid))
            refs.append(card_index[cid])
        refs.sort(key=lambda r: card_names[r].lower())
        rule_refs = []
        for tag in zones:
            for _, label, _ in evidence[tag]:
                key = "%s|%s" % (tag, label)
                if key not in rule_index:
                    rule_index[key] = len(rules)
                    rules.append(key)
                rule_refs.append(rule_index[key])
        rows.append([e["effect_id"], e["raw_text"], e["occurrence_count"], mask, refs, rule_refs])
        if e.get("plain_text"):
            plain[n] = e["plain_text"]

    top_mask = 0
    for z in cz.ZONES:
        top_mask |= 1 << tag_bit[z]
    colors = {"library": "--z-library", "hand": "--z-hand", "battlefield": "--z-battlefield",
              "graveyard": "--z-graveyard", "exile": "--z-exile", "stack": "--z-stack",
              "command zone": "--z-command", "mana pool": "--z-mana"}
    data = {"tags": cz.ALL_TAGS, "topMask": top_mask, "colors": colors, "rules": rules,
            "cards": card_names, "plain": plain, "effects": rows}
    return data, stale


def page(n_effects, n_cards, manifest, stale):
    esc = html.escape
    src = manifest.get("source", {})
    stale_html = ""
    if stale:
        stale_html = ('<div class="stale"><b>Stored labels are stale.</b> %d effects in data/full/effects.json '
                      'disagree with the current classify_zones.py rules (first: %s). Re-run '
                      '<code>python build_full_glossary.py</code>.</div>' % (len(stale), esc(", ".join(stale[:5]))))
    generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zone Review</title>
<style>{css}</style>
<main>
<h1>Zone review</h1>
<p class="lede">{n_effects} unique effects from {n_cards} cards &middot; Scryfall oracle_cards {updated}
&middot; zones classified on raw_text only &middot; page generated {generated}</p>
{stale}
<div id="load-error" class="error" hidden><b>Data failed to load.</b> zone-review.data.js must sit next to this page.
Re-run <code>python build_zone_review.py</code>.</div>
<div class="panel">
  <div class="zonebar" id="zonebar" aria-label="Filter by zone"></div>
  <div class="row2">
    <input id="q" type="search" placeholder="Search raw_text, plain_text, card names, effect_id&hellip;" aria-label="Search">
    <span class="seg" role="radiogroup" aria-label="Zone match mode">
      <label><input type="radio" name="mode" value="any" checked><span>any selected</span></label>
      <label><input type="radio" name="mode" value="all"><span>all selected</span></label>
    </span>
    <label class="muted">Sort <select id="sort">
      <option value="occ-desc">most cards first</option>
      <option value="occ-asc">fewest cards first</option>
      <option value="zones-desc">most zones first</option>
      <option value="raw-az">raw_text A&ndash;Z</option>
    </select></label>
    <label class="muted">Rows <select id="size"><option>50</option><option selected>100</option><option>250</option></select></label>
    <button type="button" id="clear" class="linkbtn">Clear filters</button>
  </div>
</div>
<div id="table-top"></div>
<div class="pager" id="pager-top"></div>
<div class="wrap"><table>
<thead><tr><th>effect_id</th><th>raw_text</th><th>plain_text</th><th>zones</th><th>cards</th><th>card names</th></tr></thead>
<tbody id="rows"><tr><td colspan="6" class="empty-state">Loading&hellip;</td></tr></tbody>
</table></div>
<div class="pager" id="pager-bottom"></div>
</main>
<script src="zone-review.data.js" charset="utf-8"></script>
<script>{js}</script>
""".format(css=CSS, js=JS, n_effects="{:,}".format(n_effects), n_cards="{:,}".format(n_cards),
           updated=esc((src.get("updated_at") or manifest.get("raw_file") or "")[:10]),
           generated=generated, stale=stale_html)


def main():
    effects, names, manifest = load()
    data, stale = build_data(effects, names)
    with open(DATA_PATH, "w", encoding="utf-8") as fh:
        fh.write("window.ZONE_REVIEW=")
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")
    with open(HTML_PATH, "w", encoding="utf-8") as fh:
        fh.write(page(len(effects), len(data["cards"]), manifest, stale))
    print("%d effects, %d cards -> %s (%.1f MB data)%s" % (
        len(effects), len(data["cards"]), os.path.normpath(HTML_PATH),
        os.path.getsize(DATA_PATH) / 1e6, ("  STALE: %d" % len(stale)) if stale else ""))


if __name__ == "__main__":
    main()
