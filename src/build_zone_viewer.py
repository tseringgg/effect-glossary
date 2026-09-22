"""Build reports/zone-labels.html: a flat, filterable table of every glossary
effect and its current zone labels.

A sanity-check tool for the classifier, not the exploration UI: one row per
effect, no grouping. Labels are read from data/effects.yaml (what is actually
stored); rule evidence and plain-only flags are recomputed by classify_zones so
each label can be traced to the rule that fired. If the stored labels disagree
with a fresh classification, the page says so at the top -- a stale glossary
must not look trustworthy.
"""
import html
import os

import classify_zones as cz
import glossary

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, os.pardir, "reports", "zone-labels.html")

CSS = """
:root {
  --paper: #EDF1EF; --surface: #FAFCFB; --surface-2: #E3EAE7;
  --ink: #141A19; --ink-soft: #4A5754; --ink-faint: #7B8783;
  --rule: #C8D3CE; --rule-soft: #DCE4E1;
  --accent: #1F6F5C; --accent-wash: #DCEAE5;
  --warn: #A8434A; --warn-wash: #F4E1E2;
  --z-library: #3F6FB0; --z-hand: #8A5CB0; --z-battlefield: #2F8A5C;
  --z-graveyard: #6B6B6B; --z-exile: #B07A2F; --z-stack: #B04F7A;
  --z-command: #5C8AB0; --z-mana: #2F9AA8;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #0E1413; --surface: #161D1B; --surface-2: #1E2725;
    --ink: #DFE7E3; --ink-soft: #A3B0AC; --ink-faint: #74827E;
    --rule: #2C3936; --rule-soft: #222D2B;
    --accent: #5CC3A4; --accent-wash: #16302A;
    --warn: #E0868C; --warn-wash: #3A1F22;
    --z-library: #7FA8E0; --z-hand: #BC95E0; --z-battlefield: #6FCB98;
    --z-graveyard: #A8A8A8; --z-exile: #E0B06F; --z-stack: #E08AB0;
    --z-command: #95BCE0; --z-mana: #6FD0DC;
  }
}
:root[data-theme="dark"] {
  --paper: #0E1413; --surface: #161D1B; --surface-2: #1E2725;
  --ink: #DFE7E3; --ink-soft: #A3B0AC; --ink-faint: #74827E;
  --rule: #2C3936; --rule-soft: #222D2B;
  --accent: #5CC3A4; --accent-wash: #16302A;
  --warn: #E0868C; --warn-wash: #3A1F22;
  --z-library: #7FA8E0; --z-hand: #BC95E0; --z-battlefield: #6FCB98;
  --z-graveyard: #A8A8A8; --z-exile: #E0B06F; --z-stack: #E08AB0;
  --z-command: #95BCE0; --z-mana: #6FD0DC;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1400px; margin: 0 auto; padding: 24px 20px 48px; }
h1 { font-size: 20px; margin: 0 0 4px; }
.lede { color: var(--ink-soft); margin: 0 0 16px; }
.stale { background: var(--warn-wash); color: var(--warn); border: 1px solid var(--warn);
  padding: 10px 12px; border-radius: 6px; margin: 0 0 16px; }
.counts { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 6px; margin: 0 0 16px; }
.controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
  position: sticky; top: 0; z-index: 2; background: var(--paper); padding: 10px 0; }
.controls select, .controls input { font: inherit; color: var(--ink); background: var(--surface);
  border: 1px solid var(--rule); border-radius: 6px; padding: 6px 8px; }
.controls input { min-width: 240px; }
#shown { color: var(--ink-soft); margin-left: auto; font-variant-numeric: tabular-nums; }
.wrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--rule); border-radius: 8px; }
table { border-collapse: collapse; width: 100%; min-width: 1000px; }
th, td { text-align: left; vertical-align: top; padding: 9px 10px; border-bottom: 1px solid var(--rule-soft); }
th { background: var(--surface-2); font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
  color: var(--ink-soft); cursor: pointer; user-select: none; white-space: nowrap; position: sticky; top: 0; }
th[aria-sort="ascending"]::after { content: " \\25B2"; }
th[aria-sort="descending"]::after { content: " \\25BC"; }
tr:last-child td { border-bottom: 0; }
td.id { font-family: ui-monospace, Consolas, monospace; font-size: 12px; white-space: nowrap; }
td.id .cards { font-family: system-ui, sans-serif; color: var(--ink-faint); white-space: normal; margin-top: 4px; }
td.raw { width: 28%; }
td.plain { width: 26%; color: var(--ink-soft); }
.none { color: var(--ink-faint); font-style: italic; }
.chips { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 4px; }
.chip { display: inline-block; font-size: 12px; padding: 1px 7px; border-radius: 999px;
  border: 1px solid var(--rule); border-left: 4px solid var(--zc, var(--rule)); background: var(--surface);
  white-space: nowrap; }
.chip.sub { font-weight: 600; background: var(--accent-wash); }
.chip.empty { border-left-color: var(--rule); color: var(--ink-faint); font-style: italic; }
.chip b { font-weight: 600; margin-left: 4px; font-variant-numeric: tabular-nums; }
.chip .cm, li .cm { color: var(--warn); font-weight: 700; margin-left: 3px; }
details { margin-top: 6px; font-size: 12px; color: var(--ink-soft); }
details summary { cursor: pointer; color: var(--ink-faint); }
details ul { margin: 4px 0 0; padding-left: 16px; }
.flag { color: var(--warn); font-size: 12px; margin-bottom: 4px; }
.flag .st { font-weight: 600; }
"""

JS = """
(function () {
  var tbody = document.querySelector('tbody');
  var rows = Array.prototype.slice.call(tbody.rows);
  var zoneSel = document.getElementById('zone');
  var q = document.getElementById('q');
  var shown = document.getElementById('shown');

  function readHash() {
    var p = new URLSearchParams(location.hash.slice(1));
    zoneSel.value = p.get('zone') || '';
    if (zoneSel.value !== (p.get('zone') || '')) zoneSel.value = '';
    q.value = p.get('q') || '';
  }
  function writeHash() {
    var p = new URLSearchParams();
    if (zoneSel.value) p.set('zone', zoneSel.value);
    if (q.value) p.set('q', q.value);
    var h = p.toString();
    history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
  }
  function apply() {
    var z = zoneSel.value, needle = q.value.trim().toLowerCase(), n = 0;
    rows.forEach(function (r) {
      var zones = r.dataset.zones ? r.dataset.zones.split('|') : [];
      var ok = true;
      if (z === '__none__') ok = zones.length === 0;
      else if (z === '__flag__') ok = r.dataset.flags === '1';
      else if (z === '__choice__') ok = r.dataset.choice === '1';
      else if (z) ok = zones.indexOf(z) !== -1;
      if (ok && needle) ok = r.dataset.text.indexOf(needle) !== -1;
      r.hidden = !ok;
      if (ok) n++;
    });
    shown.textContent = 'showing ' + n + ' of ' + rows.length;
  }
  zoneSel.addEventListener('change', function () { writeHash(); apply(); });
  q.addEventListener('input', function () { writeHash(); apply(); });
  window.addEventListener('hashchange', function () { readHash(); apply(); });

  document.querySelectorAll('th[data-key]').forEach(function (th) {
    th.addEventListener('click', function () {
      var dir = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
      document.querySelectorAll('th').forEach(function (h) { h.removeAttribute('aria-sort'); });
      th.setAttribute('aria-sort', dir);
      var key = th.dataset.key, sign = dir === 'ascending' ? 1 : -1;
      rows.sort(function (a, b) {
        var x = a.dataset[key], y = b.dataset[key];
        var nx = Number(x), ny = Number(y);
        var c = (!isNaN(nx) && !isNaN(ny) && x !== '' && y !== '') ? nx - ny : x.localeCompare(y);
        return c * sign || Number(a.dataset.order) - Number(b.dataset.order);
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    });
  });

  readHash();
  apply();
})();
"""

ZONE_COLOR = {
    "library": "--z-library", "hand": "--z-hand", "battlefield": "--z-battlefield",
    "graveyard": "--z-graveyard", "exile": "--z-exile", "stack": "--z-stack",
    "command zone": "--z-command", "mana pool": "--z-mana",
}


def esc(s):
    return html.escape(s or "", quote=True)


def tag_of(record):
    return "%s:%s" % (record["zone"], record["direction"])


def chip(tag, count=None, choice_count=None):
    parent = tag.split(":")[0]
    n = "<b>%d</b>" % count if count is not None else ""
    mark = ' <span class="cm">&#9670;%d</span>' % choice_count if choice_count else ""
    return '<span class="chip" style="--zc: var(%s)">%s%s%s</span>' % (ZONE_COLOR[parent], esc(tag), n, mark)


def record_chip(record):
    mark = '<span class="cm">&#9670;</span>' if record["choice"] else ""
    return '<span class="chip" style="--zc: var(%s)">%s%s</span>' % (
        ZONE_COLOR[record["zone"]], esc(tag_of(record)), mark)


def row(order, entry, evidence, flags):
    records = entry.get("zones") or []
    tags = [tag_of(r) for r in records]
    if records:
        chips = "".join(record_chip(r) for r in records)
    else:
        chips = '<span class="chip empty">no zones</span>'
    ev_items = "".join(
        "<li><b>%s</b>%s: %s</li>" % (
            esc(tag), ' <span class="cm">&#9670; choice</span>' if choice else "",
            esc(", ".join("%s:%s" % h for h in evidence.get(tag, []))))
        for tag, choice in zip(tags, (r["choice"] for r in records)))
    ev = ("<details><summary>rules fired</summary><ul>%s</ul></details>" % ev_items) if ev_items else ""
    flag_html = "".join(
        '<div class="flag">%s &mdash; plain_text only, NOT applied (%s)</div>'
        % (esc(tag), esc(", ".join("%s:%s" % f for f in fired)))
        for tag, _applied, fired in flags) or '<span class="none">&mdash;</span>'
    plain = entry.get("plain_text") or ""
    text_blob = " ".join([entry["effect_id"], entry["raw_text"], plain, " ".join(tags)]).lower()
    return (
        '<tr data-order="{o}" data-id="{id}" data-raw="{raw}" data-plain="{plain_key}" '
        'data-zonecount="{zc}" data-zonekey="{zk}" data-flagcount="{fc}" '
        'data-zones="{zones}" data-flags="{hasflag}" data-choice="{haschoice}" data-text="{text}">'
        '<td class="id">{id}<div class="cards">{cards}</div></td>'
        '<td class="raw">{raw}</td>'
        '<td class="plain">{plain_cell}</td>'
        '<td><div class="chips">{chips}</div>{ev}</td>'
        '<td>{flags}</td></tr>'
    ).format(
        o=order, id=esc(entry["effect_id"]), raw=esc(entry["raw_text"]),
        plain_key=esc(plain),
        plain_cell=esc(plain) if plain else '<span class="none">unauthored</span>',
        zc=len({r["zone"] for r in records}), zk=esc(" ".join(tags)), fc=len(flags),
        zones=esc("|".join(tags)), hasflag="1" if flags else "0",
        haschoice="1" if any(r["choice"] for r in records) else "0", text=esc(text_blob),
        cards=esc(", ".join(entry.get("card_ids") or [])),
        chips=chips, ev=ev, flags=flag_html,
    )


def build(entries):
    stale, body = [], []
    all_records = []  # (evidence, flags) per entry, recomputed fresh, raw_text only
    for i, e in enumerate(entries):
        zones, evidence, flags = cz.classify(e.get("raw_text", ""), e.get("plain_text", ""))
        if zones != (e.get("zones") or []):
            stale.append(e["effect_id"])
        all_records.append(zones)
        body.append(row(i, e, evidence, flags))

    tags_seen = sorted({tag_of(r) for zones in all_records for r in zones},
                       key=lambda t: (cz.ZONES.index(t.split(":")[0]), cz.DIRECTIONS.index(t.split(":")[1])))
    counts = "".join(
        chip(t,
            sum(1 for zones in all_records if any(tag_of(r) == t for r in zones)),
            sum(1 for zones in all_records if any(tag_of(r) == t and r["choice"] for r in zones)))
        for t in tags_seen)
    n_empty = sum(1 for zones in all_records if not zones)
    n_flag = sum(1 for e in entries if cz.classify(e.get("raw_text", ""), e.get("plain_text", ""))[2])
    n_choice = sum(1 for zones in all_records if any(r["choice"] for r in zones))

    options = ['<option value="">all effects</option>']
    options += ['<option value="%s">%s</option>' % (esc(t), esc(t)) for t in tags_seen]
    options += ['<option value="__none__">(no zones)</option>',
                '<option value="__choice__">(has a choice)</option>',
                '<option value="__flag__">(has plain-only flag)</option>']

    stale_html = ""
    if stale:
        stale_html = ('<div class="stale"><b>Stored labels are stale.</b> %d effect(s) in '
                      'data/effects.yaml disagree with the current rules (%s). Re-run '
                      '<code>python classify_zones.py</code>.</div>' % (len(stale), esc(", ".join(stale))))

    return """<title>Zone Labels</title>
<style>{css}</style>
<main>
<h1>Zone labels</h1>
<p class="lede">{n} effects from data/effects.yaml &middot; {empty} with no zones &middot; {choice} with a
player choice ({cm}) &middot; {flag} with plain-only flags. Each tag is zone:direction, classified on
raw_text only.</p>
{stale}
<div class="counts">{counts}</div>
<div class="controls">
  <label>Zone <select id="zone">{options}</select></label>
  <input id="q" type="search" placeholder="Filter by text, id, or zone&hellip;">
  <span id="shown"></span>
</div>
<div class="wrap"><table>
<thead><tr>
  <th data-key="id">effect_id</th>
  <th data-key="raw">raw_text</th>
  <th data-key="plain">plain_text</th>
  <th data-key="zonecount">zones</th>
  <th data-key="flagcount">flags</th>
</tr></thead>
<tbody>
{rows}
</tbody></table></div>
</main>
<script>{js}</script>
""".format(css=CSS, n=len(entries), empty=n_empty, choice=n_choice, cm="&#9670;", flag=n_flag,
           stale=stale_html, counts=counts, options="".join(options), rows="\n".join(body), js=JS)


def main():
    entries = glossary.load_glossary()
    page = build(entries)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write("<!doctype html>\n<meta charset=\"utf-8\">\n"
                 "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n")
        fh.write(page)
    print("%d effects -> %s" % (len(entries), os.path.normpath(OUT_PATH)))


if __name__ == "__main__":
    main()
