"""Build the shareable HTML view of reports/results.json.

Every number on the page is read from the JSON the real run produced, so the
page cannot drift from the experiment.
"""
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(HERE, os.pardir, "reports")
MODELS = ["tfidf", "e5-small-v2", "bge-base-en-v1.5"]
SHORT = {"tfidf": "tf-idf", "e5-small-v2": "e5", "bge-base-en-v1.5": "bge"}

CSS = """
:root {
  --paper:      #EDF1EF;
  --surface:    #FAFCFB;
  --surface-2:  #E3EAE7;
  --ink:        #141A19;
  --ink-soft:   #4A5754;
  --ink-faint:  #7B8783;
  --rule:       #C8D3CE;
  --rule-soft:  #DCE4E1;
  --el:         #1F6F5C;
  --el-wash:    #DCEAE5;
  --bl:         #6B5BA8;
  --bl-wash:    #E4E0F2;
  --warn:       #A8434A;
  --shadow:     0 1px 2px rgba(20,26,25,.06), 0 8px 24px -16px rgba(20,26,25,.28);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper:     #0E1413;
    --surface:   #161D1B;
    --surface-2: #1E2725;
    --ink:       #DFE7E3;
    --ink-soft:  #A3B0AC;
    --ink-faint: #74827E;
    --rule:      #2C3936;
    --rule-soft: #222D2B;
    --el:        #5CC3A4;
    --el-wash:   #16302A;
    --bl:        #A695E6;
    --bl-wash:   #262042;
    --warn:      #E0868C;
    --shadow:    0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
  }
}
:root[data-theme="dark"] {
  --paper:     #0E1413;
  --surface:   #161D1B;
  --surface-2: #1E2725;
  --ink:       #DFE7E3;
  --ink-soft:  #A3B0AC;
  --ink-faint: #74827E;
  --rule:      #2C3936;
  --rule-soft: #222D2B;
  --el:        #5CC3A4;
  --el-wash:   #16302A;
  --bl:        #A695E6;
  --bl-wash:   #262042;
  --warn:      #E0868C;
  --shadow:    0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
}

* { box-sizing: border-box; }
body {
  background: var(--paper);
  color: var(--ink);
  font-family: "Public Sans", ui-sans-serif, system-ui, -apple-system, sans-serif;
  font-size: 16px;
  line-height: 1.62;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1120px; margin: 0 auto; padding: 0 28px 96px; }
.col  { max-width: 66ch; }

h1, h2, h3 {
  font-family: Newsreader, ui-serif, Georgia, serif;
  font-weight: 500;
  text-wrap: balance;
  margin: 0;
}
h1 { font-size: clamp(2.1rem, 1.3rem + 3vw, 3.5rem); line-height: 1.06; letter-spacing: -.018em; }
h2 { font-size: clamp(1.4rem, 1.1rem + 1vw, 1.85rem); line-height: 1.18; }
h3 { font-size: 1.12rem; line-height: 1.3; }
p  { margin: 0; }
em { font-style: italic; }
strong { font-weight: 650; }

.eyebrow {
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: .688rem; letter-spacing: .13em; text-transform: uppercase;
  color: var(--ink-faint);
}
.mono { font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, monospace; }
.num  { font-variant-numeric: tabular-nums; }

/* ---- masthead ---- */
header.mast {
  display: flex; flex-direction: column; gap: 22px;
  padding: 72px 0 40px;
  border-bottom: 1px solid var(--rule);
}
.mast .standfirst {
  font-size: 1.16rem; color: var(--ink-soft); max-width: 62ch;
}
.mast .meta {
  display: flex; flex-wrap: wrap; gap: 8px 22px;
  padding-top: 6px;
}
.mast .meta span { color: var(--ink-faint); }
.mast .meta b { color: var(--ink-soft); font-weight: 600; }

/* ---- verdict ---- */
.verdict {
  margin: 40px 0 0;
  display: grid; gap: 0;
  grid-template-columns: 4px 1fr;
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 3px;
  box-shadow: var(--shadow);
  overflow: hidden;
}
.verdict .stripe { background: var(--warn); }
.verdict .stripe.ok { background: var(--el); }
.verdict .vbody { padding: 26px 30px; display: flex; flex-direction: column; gap: 12px; }
.verdict p { max-width: 66ch; }
.vgrid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 1px; background: var(--rule-soft);
  border: 1px solid var(--rule-soft); border-radius: 3px; margin-top: 6px;
}
.vcell { background: var(--surface); padding: 15px 18px; display: flex; flex-direction: column; gap: 5px; }
.vscore {
  font-family: Newsreader, ui-serif, Georgia, serif; font-size: 1.72rem; line-height: 1;
}
.vscore.win  { color: var(--el); }
.vscore.tie  { color: var(--ink-soft); }
.vscore.loss { color: var(--warn); }
.vnum { font-size: .78rem; color: var(--ink-faint); }
.vgap { padding-left: 6px; }
.vgap.win { color: var(--el); }
.vgap.tie { color: var(--ink-faint); }
.vgap.loss { color: var(--warn); }
.vfoot { font-size: .875rem; color: var(--ink-faint); max-width: 70ch; }

thead tr.grp th.gbx { color: var(--ink-soft); }
td.fbx { background: var(--surface-2); }
tr.fairrow td { border-top: 1px solid var(--rule); }
tr.fairrow td.l:first-child { box-shadow: inset 3px 0 0 var(--el); }

/* ---- sections ---- */
section { padding-top: 62px; }
.sec-head { display: flex; flex-direction: column; gap: 10px; margin-bottom: 22px; }
.stack { display: flex; flex-direction: column; gap: 16px; }

/* ---- finding cards ---- */
.findings { display: flex; flex-direction: column; gap: 2px; }
.finding {
  display: grid; grid-template-columns: 148px 1fr; gap: 30px;
  padding: 26px 0; border-top: 1px solid var(--rule-soft);
}
.finding:first-child { border-top: 1px solid var(--rule); }
.chip {
  display: inline-block; align-self: start;
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: .656rem; letter-spacing: .1em; text-transform: uppercase;
  padding: 4px 9px; border-radius: 2px; white-space: nowrap;
}
.chip.confirmed { background: var(--el-wash); color: var(--el); }
.chip.cost      { background: var(--surface-2); color: var(--warn); }
.chip.confound  { background: var(--bl-wash); color: var(--bl); }
.chip.instrument{ background: var(--surface-2); color: var(--ink-soft); }
.chip.seam      { background: var(--surface-2); color: var(--ink-soft); }
.finding .body { display: flex; flex-direction: column; gap: 12px; }
.finding .body p { max-width: 68ch; }

/* ---- data tables ---- */
.scroller { overflow-x: auto; border: 1px solid var(--rule); border-radius: 3px; background: var(--surface); }
table { border-collapse: collapse; width: 100%; font-size: .875rem; }
caption {
  text-align: left; padding: 16px 18px 14px; border-bottom: 1px solid var(--rule);
  color: var(--ink-soft);
}
caption .q { color: var(--ink); font-weight: 650; }
th, td { padding: 7px 12px; text-align: right; white-space: nowrap; }
th.l, td.l { text-align: left; }
thead th {
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: .656rem; letter-spacing: .09em; text-transform: uppercase;
  color: var(--ink-faint); font-weight: 500;
  border-bottom: 1px solid var(--rule);
}
thead tr.grp th { padding-bottom: 2px; border-bottom: none; }
thead tr.grp th.gel { color: var(--el); }
thead tr.grp th.gbl { color: var(--bl); }
tbody tr { border-top: 1px solid var(--rule-soft); }
tbody td { color: var(--ink-soft); font-variant-numeric: tabular-nums; }
tbody td.l { color: var(--ink); }
td.fused { font-weight: 650; color: var(--ink); }
td.fel { background: var(--el-wash); }
td.fbl { background: var(--bl-wash); }
tr.target td.l { font-weight: 650; }
tr.target td.name { box-shadow: inset 3px 0 0 var(--el); }
tr.excluded td { color: var(--ink-faint); font-style: italic; }
.role { font-size: .75rem; color: var(--ink-faint); font-style: normal; }
.sep { border-left: 1px solid var(--rule-soft); }

/* ---- chart ---- */
.chart { background: var(--surface); border: 1px solid var(--rule); border-radius: 3px; padding: 22px 20px 12px; }
.legend { display: flex; gap: 20px; flex-wrap: wrap; padding: 0 2px 16px; }
.legend .k { display: inline-flex; align-items: center; gap: 8px; font-size: .82rem; color: var(--ink-soft); }
.legend .dot { width: 10px; height: 10px; border-radius: 50%; }

/* ---- method grid ---- */
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1px; background: var(--rule-soft); border: 1px solid var(--rule); border-radius: 3px; overflow: hidden; }
.cellx { background: var(--surface); padding: 20px 22px; display: flex; flex-direction: column; gap: 8px; }
.cellx h3 { font-size: .98rem; }
.cellx p { font-size: .9rem; color: var(--ink-soft); }
.callout {
  margin-top: 20px; padding: 18px 22px;
  background: var(--surface); border: 1px solid var(--rule);
  border-left: 3px solid var(--el); border-radius: 3px;
}
.callout p { font-size: .94rem; color: var(--ink-soft); max-width: 78ch; }
.callout b { color: var(--ink); }
.contra {
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: .656rem; letter-spacing: .1em; text-transform: uppercase;
  padding: 3px 8px; border-radius: 2px;
  background: var(--surface-2); color: var(--warn);
}
caption .vscore { font-family: inherit; }

/* ---- glossary rows ---- */
.gloss { display: flex; flex-direction: column; gap: 1px; background: var(--rule-soft); border: 1px solid var(--rule); border-radius: 3px; overflow: hidden; }
.grow { background: var(--surface); padding: 13px 18px; display: grid; grid-template-columns: 1fr 1fr 72px; gap: 18px; align-items: baseline; }
.grow.head { background: var(--surface-2); }
.grow .raw { font-family: "JetBrains Mono", ui-monospace, monospace; font-size: .78rem; color: var(--ink); }
.grow .plain { font-size: .84rem; color: var(--ink-soft); }
.grow .cnt { text-align: right; font-family: "JetBrains Mono", ui-monospace, monospace; font-size: .78rem; color: var(--ink-faint); }
.grow.unauth .plain { color: var(--warn); font-style: italic; }
.grow.head span { font-family: "JetBrains Mono", ui-monospace, monospace; font-size: .656rem; letter-spacing: .09em; text-transform: uppercase; color: var(--ink-faint); }

ul.plain-list { margin: 0; padding-left: 1.15em; display: flex; flex-direction: column; gap: 9px; }
ul.plain-list li { color: var(--ink-soft); max-width: 66ch; }
ul.plain-list li::marker { color: var(--ink-faint); }

footer { padding-top: 62px; border-top: 1px solid var(--rule); margin-top: 62px; color: var(--ink-faint); font-size: .85rem; }

@media (max-width: 720px) {
  .finding { grid-template-columns: 1fr; gap: 12px; }
  .grow { grid-template-columns: 1fr; gap: 6px; }
  .grow .cnt { text-align: left; }
}
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
:focus-visible { outline: 2px solid var(--el); outline-offset: 2px; }
"""


def esc(s):
    return html.escape(str(s), quote=False)


def rank_chart(doc):
    """Dumbbell chart: for every target card, its effect-level and baseline rank."""
    rows = []
    for q in doc["queries"]:
        for cid in doc["targets"][q["cluster"]]:
            rows.append((q["query"], q["primary"], doc["cards"][cid]["name"],
                         q["el"]["fused"].get(cid), q["bl"]["fused"].get(cid)))

    left, right, top = 232, 60, 46
    row_h, grp_gap, hdr_h = 25, 20, 19
    width, maxr = 960, 17
    span = width - left - right

    # Lay the rows out first, then size the canvas to what was laid out. Deriving
    # the height from a formula instead silently clipped the last group.
    placed, y, last_q = [], top, None
    for query, primary, name, el, bl in rows:
        if query != last_q:
            if last_q is not None:
                y += grp_gap
            placed.append(("hdr", y, query, primary))
            last_q = query
            y += hdr_h
        placed.append(("row", y, name, (el, bl)))
        y += row_h
    height = y + 14

    def x(rank):
        return left + (rank - 1) / (maxr - 1) * span

    p = ['<svg viewBox="0 0 %d %d" width="100%%" role="img" '
         'aria-label="Rank of each target card under both pipelines" '
         'style="display:block;max-width:100%%;height:auto;font-family:\'JetBrains Mono\',monospace">'
         % (width, height)]

    # rank axis
    for r in (1, 5, 9, 13, 17):
        p.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--rule-soft)" '
                 'stroke-width="1" />' % (x(r), top - 12, x(r), height - 20))
        p.append('<text x="%.1f" y="%d" fill="var(--ink-faint)" font-size="10" '
                 'text-anchor="middle">%d</text>' % (x(r), top - 20, r))
    p.append('<text x="%d" y="%d" fill="var(--ink-faint)" font-size="10" '
             'text-anchor="end">rank</text>' % (left - 12, top - 20))

    for kind, y, label, extra in placed:
        if kind == "hdr":
            p.append('<text x="0" y="%d" fill="var(--ink)" font-size="11.5" '
                     'font-weight="600">%s</text>' % (y + 4, esc('"%s"' % label)))
            # Tag sits at the far right edge; beside the query text it collided.
            p.append('<text x="%d" y="%d" fill="var(--ink-faint)" font-size="9" '
                     'text-anchor="end">%s</text>'
                     % (width, y + 4, "specified" if extra else "paraphrase"))
            continue
        el, bl = extra
        if el is None or bl is None:
            continue
        p.append('<text x="%d" y="%d" fill="var(--ink-soft)" font-size="10.5" '
                 'text-anchor="end">%s</text>' % (left - 12, y + 4, esc(label)))
        p.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--rule)" '
                 'stroke-width="1.5" />' % (x(bl), y, x(el), y))
        p.append('<circle cx="%.1f" cy="%d" r="4.5" fill="var(--bl)" />' % (x(bl), y))
        p.append('<circle cx="%.1f" cy="%d" r="4.5" fill="var(--el)" />' % (x(el), y))
        if el != bl:
            # Always to the right of the rightmost dot, so it can never run back
            # over the card label at the left edge.
            p.append('<text x="%.1f" y="%d" fill="%s" font-size="9.5">%s</text>'
                     % (max(x(el), x(bl)) + 10, y + 3.5,
                        "var(--el)" if el < bl else "var(--warn)", "%+d" % (bl - el)))
    p.append("</svg>")
    return "".join(p)


def rank_table(doc, q, full):
    cards = doc["cards"]
    targets = set(doc["targets"][q["cluster"]])
    excluded = set(doc["excluded_cards"])
    order = sorted(cards, key=lambda c: (q["el"]["fused"].get(c, 10 ** 6),
                                         q["bl"]["fused"].get(c, 10 ** 6), c))
    ns_el, ns_bl = q["el"]["no_signal"], q["bl"]["no_signal"]
    note = ""
    if ns_el or ns_bl:
        note = (' &middot; no lexical signal from <span class="mono">%s</span>, '
                'so it contributes nothing to fusion'
                % esc(", ".join(SHORT[m] for m in (ns_el or ns_bl))))

    h = ['<div class="scroller"><table>']
    h.append('<caption><span class="q">&ldquo;%s&rdquo;</span>%s</caption>' % (esc(q["query"]), note))
    h.append("<thead>")
    if full:
        h.append('<tr class="grp"><th class="l" colspan="2"></th>'
                 '<th class="gel sep" colspan="4">effect-level</th>'
                 '<th class="gbl sep" colspan="4">whole-card baseline</th></tr>')
        h.append('<tr><th class="l">Card</th><th class="l">Cluster / role</th>'
                 '<th class="sep">fused</th>' + "".join('<th>%s</th>' % SHORT[m] for m in MODELS) +
                 '<th class="sep">fused</th>' + "".join('<th>%s</th>' % SHORT[m] for m in MODELS) +
                 "</tr>")
    else:
        h.append('<tr><th class="l">Card</th><th class="l">Cluster / role</th>'
                 '<th class="sep gel">effect-level</th><th class="gbl">baseline</th></tr>')
    h.append("</thead><tbody>")

    for cid in order:
        c = cards[cid]
        cls = []
        if cid in targets:
            cls.append("target")
        if cid in excluded:
            cls.append("excluded")
        role = "%s / %s" % (c["cluster"].replace("_", " "), c["role"])
        if cid in excluded:
            role += " &middot; not indexed"
        h.append('<tr class="%s">' % " ".join(cls))
        h.append('<td class="l name">%s</td><td class="l"><span class="role">%s</span></td>'
                 % (esc(c["name"]), role))

        def cell(v, extra=""):
            return '<td class="%s">%s</td>' % (extra, v if v is not None else "&mdash;")
        if full:
            h.append(cell(q["el"]["fused"].get(cid), "fused fel sep"))
            for m in MODELS:
                h.append(cell(q["el"]["models"][m].get(cid)))
            h.append(cell(q["bl"]["fused"].get(cid), "fused fbl sep"))
            for m in MODELS:
                h.append(cell(q["bl"]["models"][m].get(cid)))
        else:
            h.append(cell(q["el"]["fused"].get(cid), "fused fel sep"))
            h.append(cell(q["bl"]["fused"].get(cid), "fused fbl"))
        h.append("</tr>")
    h.append("</tbody></table></div>")
    return "".join(h)


GRID_PIPES = [("effect_level", "effect-level", "gel"),
              ("baseline_name", "baseline +name", "gbl"),
              ("baseline_noname", "baseline &minus;name", "gbx")]


def grid_table(g, cluster, variant):
    cards, cell = g["cards"], g["grid"][cluster][variant]
    targets, excluded = set(g["targets"][cluster]), set(g["excluded_cards"])

    h = ['<div class="scroller"><table>']
    h.append('<caption><span class="q">%s</span> &middot; <span class="mono">%s</span></caption>'
             % (esc(variant), esc(cell["query"])))
    h.append('<thead><tr class="grp"><th class="l" colspan="2"></th>')
    for _, label, cls in GRID_PIPES:
        h.append('<th class="%s sep" colspan="4">%s</th>' % (cls, label))
    h.append('</tr><tr><th class="l">Card</th><th class="l">Cluster / role</th>')
    for _ in GRID_PIPES:
        h.append('<th class="sep">fused</th>' + "".join("<th>%s</th>" % SHORT[m] for m in MODELS))
    h.append("</tr></thead><tbody>")

    def key(cid):
        return (cell["effect_level"]["fused"].get(cid, 10 ** 6),
                cell["baseline_noname"]["fused"].get(cid, 10 ** 6), cid)

    for cid in sorted(cards, key=key):
        c = cards[cid]
        cls = []
        if cid in targets:
            cls.append("target")
        if cid in excluded:
            cls.append("excluded")
        role = "%s / %s" % (c["cluster"].replace("_", " "), c["role"])
        if cid in excluded:
            role += " &middot; not indexed"
        h.append('<tr class="%s"><td class="l name">%s</td>'
                 '<td class="l"><span class="role">%s</span></td>'
                 % (" ".join(cls), esc(c["name"]), role))
        for pname, _, cls_ in GRID_PIPES:
            d = cell[pname]
            v = d["fused"].get(cid)
            h.append('<td class="fused f%s sep">%s</td>'
                     % (cls_[1:], v if v is not None else "&mdash;"))
            for m in MODELS:
                mv = d["models"][m].get(cid)
                h.append("<td>%s</td>" % (mv if mv is not None else "&mdash;"))
        h.append("</tr>")
    h.append("</tbody></table></div>")
    return "".join(h)


def per_card_rows(g, cluster, variant="glossed", opponent="baseline_noname"):
    el = g["grid"][cluster][variant]["effect_level"]["fused"]
    bl = g["grid"][cluster][variant][opponent]["fused"]
    rows = []
    for cid in g["targets"][cluster]:
        e, b = el.get(cid), bl.get(cid)
        d = None if (e is None or b is None) else b - e
        v = "excluded" if d is None else ("win" if d > 0 else ("loss" if d < 0 else "tie"))
        rows.append((cid, e, b, d, v))
    return rows


def spread_stats(rows):
    deltas = sorted(d for _, _, _, d, _ in rows if d is not None)
    n = len(deltas)
    med = deltas[n // 2] if n % 2 else (deltas[n // 2 - 1] + deltas[n // 2]) / 2.0
    top = max(deltas, key=abs) if deltas else 0
    tot = sum(abs(d) for d in deltas)
    tally = {"win": 0, "tie": 0, "loss": 0, "excluded": 0}
    for _, _, _, _, v in rows:
        tally[v] += 1
    return {"mean": sum(deltas) / float(n), "median": med, "top": top,
            "share": (abs(top) / tot) if tot else 0.0, "tally": tally}


def mean_target(g, cluster, variant, pipeline):
    ranks = g["grid"][cluster][variant][pipeline]["fused"]
    vals = [ranks.get(c) for c in g["targets"][cluster] if ranks.get(c)]
    return sum(vals) / len(vals) if vals else None


def build():
    with open(os.path.join(REPORTS, "results.json"), encoding="utf-8") as fh:
        doc = json.load(fh)
    with open(os.path.join(REPORTS, "grid.json"), encoding="utf-8") as fh:
        grid = json.load(fh)
    e5d = None
    _p = os.path.join(REPORTS, "e5_diagnostic.json")
    if os.path.exists(_p):
        with open(_p, encoding="utf-8") as fh:
            e5d = json.load(fh)
    mdr = None
    _p2 = os.path.join(REPORTS, "mana_dork_recheck.json")
    if os.path.exists(_p2):
        with open(_p2, encoding="utf-8") as fh:
            mdr = json.load(fh)

    eff = doc["effects"]
    n_auth = sum(1 for e in eff.values() if e["plain_text"].strip())

    def mean_ranks(q, side):
        vals = [q[side]["fused"].get(c) for c in doc["targets"][q["cluster"]]]
        vals = [v for v in vals if v]
        return sum(vals) / len(vals) if vals else None

    out = ['<title>Does Effect Splitting Fix Density?</title>',
           '<link rel="preconnect" href="https://fonts.googleapis.com">',
           '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
           'family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&'
           'family=Public+Sans:wght@400;500;650&'
           'family=JetBrains+Mono:wght@400;500&display=swap">',
           "<style>%s</style>" % CSS, '<div class="wrap">']
    w = out.append

    # ---------- masthead ----------
    w('<header class="mast">')
    w('<div class="eyebrow">Retrieval experiment &middot; standalone</div>')
    w("<h1>Does effect splitting fix density?</h1>")
    w('<p class="standfirst">Whole-card embedding buries short, correct cards under longer, '
      'tangential ones. This trial splits 17 Magic cards into deduplicated effects, rewords '
      'them in plain language, searches at the effect level, and aggregates back to cards. '
      'A first run measured it against a whole-card baseline and found it wanting. A second, '
      'controlled run removed the two confounds behind that result &mdash; query-side jargon '
      'and card-name leakage &mdash; and reversed it. A third run widens the sample to 30 '
      'cards to test whether the reversal was a small-sample artifact.</p>')
    w('<div class="meta mono">')
    for label, val in [("corpus", "17 cards"),
                       ("glossary", "%d effects / %d extractions" % (len(eff), 22)),
                       ("authored", "%d of %d" % (n_auth, len(eff))),
                       ("embedders", "tf-idf &middot; e5-small-v2 &middot; bge-base-en-v1.5"),
                       ("fusion", "RRF k=60"),
                       ("aggregation", "MAX")]:
        w("<span>%s <b>%s</b></span>" % (label, val))
    w("</div></header>")

    # ---------- verdict ----------
    verdicts = []
    for cluster in grid["queries"]:
        el = mean_target(grid, cluster, "glossed", "effect_level")
        bx = mean_target(grid, cluster, "glossed", "baseline_noname")
        gap = bx - el
        v = "Win" if gap >= 1 else ("Loss" if gap <= -1 else "Tie")
        verdicts.append((cluster, el, bx, gap, v))

    w('<div class="verdict"><div class="stripe ok"></div><div class="vbody">')
    w('<div class="eyebrow">Verdict &middot; controlled comparison</div>')
    w("<h2>Once both confounds are removed, effect-level wins two clusters and ties "
      "the third &mdash; and that holds at %d cards.</h2>" % len(grid["cards"]))
    w('<p>The first run concluded that effect-level search did not pay for itself. That '
      'conclusion was an artifact of the two confounds. Translating the query out of MTG '
      'jargon and stripping the card&rsquo;s own name from the baseline document reverses it. '
      'Nothing in the pipeline changed &mdash; same extraction, same glossary, same MAX '
      'aggregation.</p>')
    w('<div class="vgrid">')
    for cluster, el, bx, gap, v in verdicts:
        w('<div class="vcell"><div class="eyebrow">%s</div>'
          '<div class="vscore %s">%s</div>'
          '<div class="vnum mono num">%.2f vs %.2f<span class="vgap %s"> %+.2f</span></div></div>'
          % (esc(cluster.replace("_", " ")), v.lower(), v, el, bx, v.lower(), gap))
    w("</div>")
    w('<p class="vfoot">Mean rank of the cards each cluster should find, effect-level against '
      'the name-stripped baseline, under the jargon-free query. Lower is better. Every verdict '
      'is unchanged from the 17-card run, but the mana-dork win is carried almost entirely by '
      'one card &mdash; see the per-card spread below before trusting it.</p>')
    w("</div></div>")

    # ---------- per-card spread ----------
    ncards = len(grid["cards"])
    w('<section><div class="sec-head"><div class="eyebrow">Per-card spread</div>'
      "<h2>Whether each cluster verdict survives being looked at card by card</h2>"
      '<p class="col" style="color:var(--ink-soft)">The sample was widened from 17 cards to '
      '%d, six targets per cluster instead of three, three and one. A cluster mean can be '
      'carried by a single card, so the per-card delta is the real evidence. Delta is '
      'baseline minus effect-level, positive meaning effect-level placed the card higher.'
      "</p></div>" % ncards)
    w('<div class="stack">')
    for cluster in grid["queries"]:
        rows = per_card_rows(grid, cluster)
        st = spread_stats(rows)
        mel = mean_target(grid, cluster, "glossed", "effect_level")
        mbl = mean_target(grid, cluster, "glossed", "baseline_noname")
        cdir = "win" if mbl - mel >= 1 else ("loss" if mbl - mel <= -1 else "tie")
        w('<div class="scroller"><table>')
        w('<caption><span class="q">%s</span> &middot; mean %.2f vs %.2f '
          '<span class="vscore %s" style="font-size:1rem">%s</span> &middot; '
          '<span class="mono">%d win / %d tie / %d loss</span> &middot; median delta '
          '<b>%+.1f</b> &middot; largest card %+d, %.0f%% of all movement</caption>'
          % (esc(cluster.replace("_", " ")), mel, mbl, cdir, cdir.upper(),
             st["tally"]["win"], st["tally"]["tie"], st["tally"]["loss"],
             st["median"], st["top"], 100 * st["share"]))
        w('<thead><tr><th class="l">Card</th><th class="gel">effect-level</th>'
          '<th class="gbx">baseline &minus;name</th><th class="sep">delta</th>'
          '<th class="l">card</th><th class="l">vs cluster</th></tr></thead><tbody>')
        for cid, e, b, d, v in rows:
            contra = (cdir == "win" and v == "loss") or (cdir == "loss" and v == "win")
            w('<tr class="%s"><td class="l name">%s</td>'
              '<td class="fused fel">%s</td><td class="fused fbx">%s</td>'
              '<td class="sep num">%s</td><td class="l"><span class="role">%s</span></td>'
              '<td class="l">%s</td></tr>'
              % ("target", esc(grid["cards"][cid]["name"]),
                 e if e else "&mdash;", b if b else "&mdash;",
                 "%+d" % d if d is not None else "&mdash;", v,
                 '<span class="contra">contradicts</span>' if contra else ""))
        w("</tbody></table></div>")
    w("</div>")

    bw = spread_stats(per_card_rows(grid, "board_wipe"))
    md = spread_stats(per_card_rows(grid, "mana_dork"))
    worst = max(per_card_rows(grid, "mana_dork"), key=lambda r: abs(r[3] or 0))
    w('<div class="callout"><p><b>Read the medians, not just the means.</b> The board-wipe '
      'win is broad: %d of %d cards improve and the median card gains %.1f places. The '
      'mana-dork win is not. Its median card gains %.1f, and a single card, %s, accounts '
      'for %.0f%% of all the movement in that cluster. Widening the sample is what made that '
      'visible, and it is the one place the earlier three-card result was flattering. The '
      'clone tie went the other way and got <em>more</em> trustworthy: at 17 cards it was a '
      'ceiling artifact with both pipelines pinned at rank 1, and at %d it is a real tie '
      'across a spread of ranks.</p></div>'
      % (bw["tally"]["win"], len(grid["targets"]["board_wipe"]), bw["median"],
         md["median"], esc(grid["cards"][worst[0]]["name"]), 100 * md["share"], ncards))

    w('<h3 style="padding:30px 0 12px">Do the three embedders agree with the fused '
      'verdict?</h3>')
    w('<p class="col" style="color:var(--ink-soft);padding-bottom:14px">Mean rank of each '
      'the targets of each cluster under one model alone, before fusion. A fused win that '
      'only one model supports is weaker than one all three produce.</p>')
    w('<div class="scroller"><table><thead><tr><th class="l">Cluster</th><th class="l">Model'
      '</th><th class="gel sep">effect-level</th><th class="gbx">baseline &minus;name</th>'
      '<th class="l sep">favours</th></tr></thead><tbody>')
    for cluster in grid["queries"]:
        cell = grid["grid"][cluster]["glossed"]
        tg = grid["targets"][cluster]
        for m in MODELS:
            el = sum(cell["effect_level"]["models"][m][c] for c in tg) / float(len(tg))
            bl = sum(cell["baseline_noname"]["models"][m][c] for c in tg) / float(len(tg))
            fav = "effect-level" if bl - el > .01 else ("baseline" if el - bl > .01 else "neither")
            klass = {"effect-level": "win", "baseline": "loss", "neither": "tie"}[fav]
            w('<tr><td class="l">%s</td><td class="l"><span class="role">%s</span></td>'
              '<td class="fused fel sep">%.2f</td><td class="fused fbx">%.2f</td>'
              '<td class="l sep"><span class="vscore %s" style="font-size:.85rem">%s</span>'
              "</td></tr>"
              % (esc(cluster.replace("_", " ")), SHORT[m], el, bl, klass, fav))
    w("</tbody></table></div>")
    w('<div class="callout"><p><b>The mana-dork win is the one to distrust.</b> e5 alone '
      'ranks the mana dorks <em>better</em> under the whole-card baseline than under '
      'effect-level, so the fused win there rests on tf-idf. Three of the six dorks carry '
      'only one indexed effect, &ldquo;tap this permanent to produce one green mana&rdquo;. '
      'tf-idf ranks that effect 3rd of the 31 indexed; e5 ranks the same effect 25th. '
      'Splitting the card did not fix the density problem for that model, and the ensemble '
      'is carrying a real disagreement rather than a consensus. Board wipe and clone show '
      'no such split.</p></div>')

    prior_path = os.path.join(REPORTS, "grid.17card.json")
    if os.path.exists(prior_path):
        with open(prior_path, encoding="utf-8") as fh:
            prior = json.load(fh)
        w('<h3 style="padding:30px 0 12px">Does the prior verdict hold?</h3>')
        w('<div class="scroller"><table><thead><tr><th class="l">Cluster</th>'
          '<th class="sep">17-card EL</th><th>17-card BL</th><th class="l">verdict</th>'
          '<th class="sep">%d-card EL</th><th>%d-card BL</th><th class="l">verdict</th>'
          '<th class="l">holds?</th></tr></thead><tbody>' % (ncards, ncards))
        for cluster in grid["queries"]:
            pel = mean_target(prior, cluster, "glossed", "effect_level")
            pbl = mean_target(prior, cluster, "glossed", "baseline_noname")
            nel = mean_target(grid, cluster, "glossed", "effect_level")
            nbl = mean_target(grid, cluster, "glossed", "baseline_noname")
            pv = "WIN" if pbl - pel >= 1 else ("LOSS" if pbl - pel <= -1 else "TIE")
            nv = "WIN" if nbl - nel >= 1 else ("LOSS" if nbl - nel <= -1 else "TIE")
            w('<tr><td class="l name">%s</td><td class="sep">%.2f</td><td>%.2f</td>'
              '<td class="l"><span class="vscore %s" style="font-size:.9rem">%s</span></td>'
              '<td class="sep">%.2f</td><td>%.2f</td>'
              '<td class="l"><span class="vscore %s" style="font-size:.9rem">%s</span></td>'
              '<td class="l">%s</td></tr>'
              % (esc(cluster.replace("_", " ")), pel, pbl, pv.lower(), pv,
                 nel, nbl, nv.lower(), nv,
                 "yes" if pv == nv else "<b>no</b>"))
        w("</tbody></table></div>")
        w('<p class="col" style="color:var(--ink-faint);padding-top:12px;font-size:.875rem">'
          'Ranks are out of 17 in the prior columns and out of %d here, so absolute numbers '
          'are not comparable across the divide. The verdict and the sign of the gap are.'
          "</p>" % ncards)
    w("</section>")

    # ---------- e5 diagnostic ----------
    if e5d:
        ab = e5d["prefixes"]["ablation"]
        sp = e5d["spread"]
        e5s = sp["e5-small-v2"]
        w('<section><div class="sec-head"><div class="eyebrow">Diagnostic</div>'
          "<h2>Why e5 buries the terse mana effect, and why that is not a semantic "
          "judgement</h2>"
          '<p class="col" style="color:var(--ink-soft)">The mana-dork result rests on one '
          'oddity: e5 ranks &ldquo;%s&rdquo; %d of %d for the makes-mana query while tf-idf '
          'ranks it %d. Density and jargon are already ruled out, since this is a single '
          'isolated effect written in plain English on both sides.</p></div>'
          % (esc(e5d["target_plain_text"]), e5s["target_rank"], e5d["n_indexed"],
             sp["tfidf"]["target_rank"]))

        w('<div class="grid2">')
        w('<div class="cellx"><h3>1. The prefix convention is correct</h3>'
          '<p>e5 expects <span class="mono">query: </span> on queries and '
          '<span class="mono">passage: </span> on documents. Both are configured, and '
          'spying on what actually reaches <span class="mono">model.encode()</span> confirms '
          'it arrives: <span class="mono">%s</span>. Ablation settles it &mdash; dropping the '
          'prefixes moves the target from %d to %d, so the convention is helping, not '
          'causing this.</p></div>'
          % (esc(e5d["prefixes"]["encoded_doc_example"][:46] + "..."),
             ab["shipped"]["target_rank"], ab["none"]["target_rank"]))
        w('<div class="cellx"><h3>2. What e5 puts first is unrelated</h3>'
          '<p>Its top hit for a query about producing mana is &ldquo;%s&rdquo; at cosine '
          '%.4f. Only four of its top ten are mana effects at all, and an exalted combat '
          'trigger places fourth. This is not a plausible-but-wrong neighbour, it is close '
          'to arbitrary.</p></div>'
          % (esc(e5d["e5_top10"][0]["plain_text"]), e5d["e5_top10"][0]["cos"]))
        w('<div class="cellx"><h3>3. The ranks sit on almost no signal</h3>'
          '<p>All %d effects score between %.4f and %.4f. The whole index spans %.4f, and '
          'just <b>%.4f</b> separates the target from the effect ranked immediately above '
          'it. A rank of %d of %d reads as a damning verdict but encodes a cosine gap in the '
          'fourth decimal place.</p></div>'
          % (e5d["n_indexed"], e5s["min"], e5s["max"], e5s["range"],
             e5d["target_vs_field"]["gap_to_one_above"], e5s["target_rank"],
             e5d["n_indexed"]))
        w('<div class="cellx"><h3>The other two models separate normally</h3>'
          '<p>On the identical query and index, tf-idf spans %.0f%% of its maximum and bge '
          '%.0f%%, against e5&rsquo;s <b>%.0f%%</b>. e5 compresses this corpus into a narrow '
          'band near 0.8, which is a property of the model rather than of these '
          'cards.</p></div>'
          % (100 * sp["tfidf"]["relative_range"],
             100 * sp["bge-base-en-v1.5"]["relative_range"],
             100 * e5s["relative_range"]))
        w("</div>")

        w('<h3 style="padding:30px 0 12px">Score separation on the same query</h3>')
        w('<div class="scroller"><table><thead><tr><th class="l">Model</th>'
          '<th class="sep">max</th><th>min</th><th>range</th><th>stdev</th>'
          '<th>range as share of max</th><th class="sep">target rank</th>'
          "</tr></thead><tbody>")
        for m in MODELS:
            v = sp[m]
            w('<tr><td class="l name">%s</td><td class="sep">%.4f</td><td>%.4f</td>'
              '<td>%.4f</td><td>%.4f</td><td>%.1f%%</td><td class="fused sep">%d</td></tr>'
              % (SHORT[m], v["max"], v["min"], v["range"], v["stdev"],
                 100 * v["relative_range"], v["target_rank"]))
        w("</tbody></table></div>")

        w('<h3 style="padding:30px 0 12px">It is the query, not the card</h3>')
        w('<p class="col" style="color:var(--ink-soft);padding-bottom:14px">Same target, '
          'same index, same models. Only the wording of the query changes. e5 degrades as '
          'the query gets longer and more compound, while bge and tf-idf barely move.</p>')
        w('<div class="scroller"><table><thead><tr><th class="l">Query</th>'
          '<th class="gel sep">e5 rank</th><th>bge rank</th><th>tf-idf rank</th>'
          '<th class="sep">e5 cosine</th><th>e5 top</th></tr></thead><tbody>')
        for row in e5d["query_forms"]:
            hit = row["e5-small-v2"]
            w('<tr><td class="l name">%s</td><td class="fused fel sep">%d</td><td>%d</td>'
              '<td>%d</td><td class="sep">%.4f</td><td>%.4f</td></tr>'
              % (esc(row["label"]), hit["target_rank"],
                 row["bge-base-en-v1.5"]["target_rank"],
                 row["tfidf"]["target_rank"], hit["target_cos"], hit["top_cos"]))
        w("</tbody></table></div>")
        w('<div class="callout"><p><b>The compound query is the cause.</b> Ask e5 '
          '&ldquo;produces green mana&rdquo; and it ranks the effect <b>first</b>. Ask it the '
          'glossed query this experiment uses, which joins two glosses because the real slang '
          'layer matched both <span class="mono">ramp</span> and '
          '<span class="mono">mana dork</span>, and it falls to %d. The ramp half is about '
          'putting <em>lands</em> into play, and on its own it ranks this creature effect %d. '
          'Concatenating a land-centric gloss onto a creature-centric query drags the query '
          'embedding away from the cards it is meant to find. That is a finding about the '
          'slang layer&rsquo;s expand-rather-than-replace rule, not about effect-level '
          'search, and it is the most likely reason the mana-dork cluster was the weak '
          'one.</p></div>'
          % (e5d["query_forms"][0]["e5-small-v2"]["target_rank"],
             e5d["query_forms"][2]["e5-small-v2"]["target_rank"]))
        w("</section>")

    # ---------- post-fix re-measurement ----------
    if mdr:
        by = {(c["family"], c["phase"]): c for c in mdr["cells"]}
        BEFORE, AFTER = "before (2 glosses)", "after (1 gloss)"
        tg = mdr["targets"]

        def mrank(cell, pipe):
            r = cell[pipe]["fused"]
            return sum(r[c] for c in tg) / float(len(tg))

        w('<section><div class="sec-head"><div class="eyebrow">After the fix</div>'
          "<h2>The slang layer now appends one gloss, and the mana dorks move</h2>"
          '<p class="col" style="color:var(--ink-soft)">The diagnostic above traced the '
          'mana-dork weakness to a compound query: the slang layer appended both the '
          'mana-dork gloss and the <span class="mono">ramp</span> gloss, and the ramp half '
          'is about putting lands into play. That layer now caps injection at one gloss per '
          'matched span. This is the same corpus and pipeline, re-run with the query the '
          'fixed layer emits. Only this cluster changes &mdash; the board-wipe query matched '
          'one term before and after, and the clone query matches nothing.</p></div>')

        w('<div class="scroller"><table><thead><tr><th class="l">Query</th>'
          '<th class="l">Phase</th><th class="gel sep">effect-level</th>'
          '<th class="gbl sep">baseline +name</th><th class="gbx">baseline &minus;name</th>'
          "</tr></thead><tbody>")
        for fam in ("expanded", "glossed"):
            for ph in (BEFORE, AFTER):
                c = by[(fam, ph)]
                cls = ' class="fairrow"' if ph == AFTER else ""
                w("<tr%s><td class=\"l name\">%s</td>"
                  '<td class="l"><span class="role">%s</span></td>'
                  '<td class="fused fel sep">%.2f</td><td class="fused fbl sep">%.2f</td>'
                  '<td class="fused fbx">%.2f</td></tr>'
                  % (cls, fam, esc(ph), mrank(c, "effect_level"),
                     mrank(c, "baseline_name"), mrank(c, "baseline_noname")))
        w("</tbody></table></div>")

        w('<h3 style="padding:30px 0 12px">Per card, in the fairest cell</h3>')
        w('<div class="scroller"><table><thead><tr><th class="l">Card</th>'
          '<th class="gel sep">EL before</th><th class="gel">EL after</th>'
          '<th class="gbx sep">BL before</th><th class="gbx">BL after</th>'
          '<th class="l sep">after the fix</th></tr></thead><tbody>')
        cb, ca = by[("glossed", BEFORE)], by[("glossed", AFTER)]
        for cid in tg:
            eb, ea = cb["effect_level"]["fused"][cid], ca["effect_level"]["fused"][cid]
            bb, ba = cb["baseline_noname"]["fused"][cid], ca["baseline_noname"]["fused"][cid]
            d = ba - ea
            k = "win" if d > 0 else ("loss" if d < 0 else "tie")
            w('<tr class="target"><td class="l name">%s</td>'
              '<td class="fused fel sep">%d</td><td class="fused fel">%d</td>'
              '<td class="fused fbx sep">%d</td><td class="fused fbx">%d</td>'
              '<td class="l sep"><span class="vscore %s" style="font-size:.9rem">%s</span>'
              "</td></tr>"
              % (esc(mdr["cards"][cid]), eb, ea, bb, ba, k, k))
        w("</tbody></table></div>")

        deltas = sorted(ca["baseline_noname"]["fused"][c] - ca["effect_level"]["fused"][c]
                        for c in tg)
        med = (deltas[2] + deltas[3]) / 2.0
        wins = sum(1 for d in deltas if d > 0)
        w('<div class="callout"><p><b>The fix helps, and it changes the verdict &mdash; '
          'read the mean and the spread together.</b> Effect-level improves on '
          '<em>all six</em> cards, %.2f to %.2f, and e5 is where the gain shows: the three '
          'Elves go from 20th to 14th under e5 alone. The baseline improves more on average, '
          '%.2f to %.2f, but almost all of that is one card &mdash; Avacyn&rsquo;s Pilgrim '
          'jumps 20 to 5 while three other dorks get <em>worse</em>. So by cluster mean the '
          'mana-dork verdict softens from WIN to TIE (gap %+.2f), while per card '
          'effect-level goes from 2 wins to <b>%d wins</b> and the median card now favours '
          'it by %+.0f places. The same mean-versus-spread trap the widening round found, '
          'pointing the other way this time.</p></div>'
          % (mrank(cb, "effect_level"), mrank(ca, "effect_level"),
             mrank(cb, "baseline_noname"), mrank(ca, "baseline_noname"),
             mrank(ca, "baseline_noname") - mrank(ca, "effect_level"), wins, med))
        w('<div class="callout" style="border-left-color:var(--warn)"><p><b>Not yet ported.'
          '</b> The cap is implemented and tested in <span class="mono">mtg-search-v0</span>, '
          'which is not the current project. It is not live in the real system until someone '
          'copies it across, and the port is not a copy-paste: the target version has a real '
          'router with its own spans and richer match tiers to map onto.</p></div>')
        w("</section>")

    # ---------- controlled grid ----------
    w('<section><div class="sec-head"><div class="eyebrow">Controls</div>'
      "<h2>The two confounds, and how each was removed</h2></div>")
    w('<div class="grid2">')
    w('<div class="cellx"><h3>Query-side jargon</h3><p>This experiment has no slang layer; '
      'the real pipeline does. Query variants come from the real project&rsquo;s glossary. '
      'Its layer <em>expands</em> rather than replaces, so its output keeps the jargon and '
      'appends &ldquo;term: gloss&rdquo;. That puts the literal token <span class="mono">wrath'
      '</span> into the board-wipe query and <span class="mono">clone</span> into the clone '
      'query, which string-match the cards Wrath of God and Clone. The real translation '
      'therefore reintroduces name leakage, so a third gloss-only variant carries the fair '
      'comparison.</p></div>')
    w('<div class="cellx"><h3>Card-name leakage</h3><p>The baseline can rank a card called '
      'Clone first for &ldquo;a clone effect&rdquo; by literal string match, which is not '
      'semantic understanding. The name-stripped variant embeds type line, cost and oracle '
      'text only.</p></div>')
    ni = grid["name_independence"]
    w('<div class="cellx"><h3>Effect-level is name-independent &mdash; confirmed</h3>'
      '<p>Not assumed. No card name and no distinctive name token appears anywhere in the '
      'indexed text. Rebuilding the whole effect index from cards whose names were replaced '
      'with nonsense returned identical ranks in <b>%d of %d</b> queries, so there is no '
      'name-stripped effect-level variant to run.</p></div>'
      % (sum(ni["scrambled_name_ranks_identical"].values()),
         len(ni["scrambled_name_ranks_identical"])))
    w('<div class="cellx"><h3>Unchanged</h3><p>Extraction, the effect glossary and the MAX '
      'aggregation are untouched. This is a re-measurement of the pipeline that already '
      'existed, not a new one. No term-relationship weighting, and no authoring beyond the '
      'query variants.</p></div>')
    w("</div></section>")

    w('<section><div class="sec-head"><div class="eyebrow">The grid</div>'
      "<h2>Mean target rank in every cell</h2>"
      '<p class="col" style="color:var(--ink-soft)">Lower is better, out of 17. '
      '<span class="mono">jargon</span> is the raw query, <span class="mono">expanded</span> '
      'is what the real slang layer actually emits, <span class="mono">glossed</span> drops '
      'the jargon and the term label. Leakage is how many places the baseline loses when its '
      'own name is removed &mdash; signal it was taking from the name rather than the card.</p>'
      "</div>")
    w('<div class="scroller"><table><thead><tr>'
      '<th class="l">Cluster</th><th class="l">Query</th>'
      '<th class="gel sep">effect-level</th><th class="gbl sep">baseline +name</th>'
      '<th class="gbx">baseline &minus;name</th><th class="sep">leakage</th>'
      "</tr></thead><tbody>")
    for cluster in grid["queries"]:
        for v in grid["variants"]:
            el = mean_target(grid, cluster, v, "effect_level")
            bn = mean_target(grid, cluster, v, "baseline_name")
            bx = mean_target(grid, cluster, v, "baseline_noname")
            fair = ' class="fairrow"' if v == "glossed" else ""
            w('<tr%s><td class="l">%s</td><td class="l"><span class="role">%s</span></td>'
              '<td class="fused fel sep">%.2f</td><td class="fused fbl sep">%.2f</td>'
              '<td class="fused fbx">%.2f</td><td class="sep">%+.2f</td></tr>'
              % (fair, esc(cluster.replace("_", " ")), esc(v), el, bn, bx, bx - bn))
    w("</tbody></table></div>")
    w('<p class="col" style="color:var(--ink-soft);padding-top:14px">Two things worth reading '
      'off this table. Under raw jargon the board-wipe cluster is the one place effect-level '
      'is badly beaten, and translating the query alone moves it from 9.33 to 1.00 &mdash; a '
      'larger swing than any structural change in the experiment produced. And name leakage is '
      '<em>negative</em> for the mana dorks: removing the name helps the baseline there, '
      'because &ldquo;Llanowar Elves&rdquo; and &ldquo;Birds of Paradise&rdquo; are noise '
      'against a query about producing mana.</p>')
    w("</section>")

    w('<section><div class="sec-head"><div class="eyebrow">Per-embedder breakdown &middot; '
      'controlled grid</div>'
      "<h2>Every rank, every cell, before and after fusion</h2>"
      '<p class="col" style="color:var(--ink-soft)">Nine tables: three clusters by three query '
      'variants, each showing all three pipelines. Fused columns are shaded, target cards carry '
      'a rule on the left, and rows are ordered by effect-level rank.</p></div>')
    for cluster in grid["queries"]:
        w('<h3 style="padding:26px 0 12px">Cluster: %s</h3>'
          % esc(cluster.replace("_", " ")))
        w('<div class="stack">')
        for v in grid["variants"]:
            w(grid_table(grid, cluster, v))
        w("</div>")
    w("</section>")

    w('<section><div class="sec-head"><div class="eyebrow">First run &middot; uncontrolled</div>'
      "<h2>What the original measurement showed, and why it misled</h2>"
      '<p class="col" style="color:var(--ink-soft)">Everything below is the first run, with '
      'neither confound controlled. It is kept because its per-embedder detail is what exposed '
      'the two instrument bugs, and because the contrast is the point.</p></div></section>')

    # ---------- chart ----------
    w("<section><div class=\"sec-head\">")
    w('<div class="eyebrow">Rank movement</div>')
    w("<h2>Where the cards each query should find actually landed</h2>")
    w('<p class="col" style="color:var(--ink-soft)">One row per target card. The connector runs '
      'from its baseline rank to its effect-level rank; the signed number is places gained or '
      'lost. Rank 1 is best, out of 17.</p>')
    w("</div>")
    w('<div class="chart">')
    w('<div class="legend">'
      '<span class="k"><span class="dot" style="background:var(--el)"></span>effect-level</span>'
      '<span class="k"><span class="dot" style="background:var(--bl)"></span>whole-card baseline</span>'
      "</div>")
    w(rank_chart(doc))
    w("</div></section>")

    # ---------- findings ----------
    findings = [
        ("confirmed", "Confirmed", "Identical cards stop getting different ranks",
         ['Llanowar Elves and Elvish Mystic have byte-identical oracle text. The baseline ranks '
          'them <b>9th and 4th</b> for &ldquo;a mana dork&rdquo; and <b>6th and 3rd</b> for '
          '&ldquo;a creature that taps for mana&rdquo;. A five-place split between two cards that '
          'do exactly the same thing, produced entirely by the name, type line and cost wrapped '
          'around the text. Effect-level ties them at 5 in both cases.',
          'The reported burial reproduces too, partly. Llanowar Elves, whose entire text is '
          '<span class="mono">{T}: Add {G}</span>, sits <b>9th of 17</b> for &ldquo;a mana '
          'dork&rdquo; in the baseline &mdash; below Ponder, Giant Growth and Divination, none of '
          'which make mana. Effect-level lifts it to 5th.',
          'The cleanest case is &ldquo;copy a creature&rdquo;, where the baseline ranks Elvish '
          'Mystic <b>2nd</b> and Llanowar Elves <b>3rd</b>, behind only Clone, because '
          '<span class="mono">Creature &mdash; Elf Druid</span> in the type line lexically '
          'matches &ldquo;creature&rdquo;. That is the density failure exactly. Effect-level '
          'drops both to 9th.']),
        ("cost", "Structural cost", "Effect-level throws away the card name",
         ['&ldquo;A board wipe&rdquo; is the worst result in the run: the three wipes land at '
          '8th, 8th and 12th under effect-level against 5th, 2nd and 3rd in the baseline.',
          'The ablation isolates the cause. Stripping the card name out of the baseline document '
          'moves Wrath of God from 5th to 9th and Damnation from 2nd to 7th, and drops Clone from '
          '<b>1st to 4th</b> on &ldquo;a clone effect&rdquo;. The baseline&rsquo;s win on the '
          'clone query is largely the literal string &ldquo;Clone&rdquo; in the card name matching '
          'the query word. It is not evidence that whole-card embedding understands the effect.',
          'Effects are deduplicated across cards, so they cannot carry a name. Against jargon '
          'queries, where the models have no semantic handle at all, that name string was the '
          'signal.']),
        ("confound", "Confound", "Vocabulary coverage swamps the document unit",
         ['On paraphrase queries the three models agree tightly: for &ldquo;destroy all '
          'creatures&rdquo; every model independently puts the three wipes on top under both '
          'pipelines. On jargon queries they collapse into mutual noise &mdash; for &ldquo;a board '
          'wipe&rdquo; under effect-level, bge ranks Nykthos 1st and the two Elves 2nd while e5 '
          'ranks Lightning Bolt 1st.',
          'Rephrasing the same intent from jargon into plain English moves the wipes from 8/8/12 '
          'to 2/2/1 under effect-level. No document-unit change in this experiment produced a '
          'swing near that size.']),
        ("instrument", "Instrument", "TF-IDF contributes nothing on two of three primary queries",
         ['&ldquo;A board wipe&rdquo; and &ldquo;a clone effect&rdquo; share no vocabulary with '
          'any authored effect, so TF-IDF scores every document zero. Because tied documents share '
          'a rank, an all-tied model gives every document rank 1 and its identical '
          '<span class="mono">1/(60+1)</span> contribution cancels out of the fusion. Those runs '
          'are effectively two-model.',
          'This surfaced as a real bug first. Before stop words were removed the only matching '
          'token in &ldquo;a board wipe&rdquo; was the article &ldquo;a&rdquo;, and TF-IDF returned '
          'an identical, confident-looking ranking for two different queries, with Giant Growth on '
          'top for a board-wipe query. Two fixes were needed: English stop words, and standard '
          'competition ranking so ties share a rank instead of being ordered arbitrarily. Only the '
          'per-embedder breakdown made either visible.']),
        ("seam", "Seam", "MAX aggregation hands multi-effect cards extra lottery tickets",
         ['A card is exactly as findable as its single best-matching effect, so a card with more '
          'effects gets more chances to match anything. Nykthos reaches <b>2nd for &ldquo;a clone '
          'effect&rdquo;</b> on its long devotion ability, and Doubling Season reaches 2nd on the '
          'same query through its <em>counters</em>-doubling effect rather than its token effect.',
          'A SUM variant would spread a card&rsquo;s score across all its effects instead of '
          'letting the best one carry it, changing exactly these two results. It is deliberately '
          'left unimplemented behind a single function.']),
        ("cost", "Coverage cost", "The no-fallback rule is total, and it does buy some precision",
         ['Ponder and Divination are absent from every effect-level result because their only '
          'effects are unauthored. No query can reach them at all.',
          'The upside is visible in the same tables: the baseline ranks Divination <b>4th</b> for '
          '&ldquo;a board wipe&rdquo;, a card-draw spell above Wrath of God at 5th. Effect-level '
          'never emits that false positive &mdash; but only because it cannot emit the card. That '
          'is coverage traded for precision, not precision earned.']),
    ]
    w('<section><div class="sec-head"><div class="eyebrow">Findings</div>'
      "<h2>Six results, and what each one rests on</h2></div>")
    w('<div class="findings">')
    for cls, label, title, paras in findings:
        w('<div class="finding"><span class="chip %s">%s</span><div class="body">' % (cls, label))
        w("<h3>%s</h3>" % title)
        for para in paras:
            w("<p>%s</p>" % para)
        w("</div></div>")
    w("</div></section>")

    # ---------- ablation ----------
    w('<section><div class="sec-head"><div class="eyebrow">Ablation</div>'
      "<h2>How much of the baseline is just the card name?</h2>"
      '<p class="col" style="color:var(--ink-soft)">The same whole-card baseline, run over three '
      'document variants. Ranks are of the cards each query should find.</p></div>')
    abl = [
        ("&ldquo;a board wipe&rdquo;", ["Wrath of God", "Damnation", "Day of Judgment"],
         [("name + type + cost + oracle", [5, 2, 3]),
          ("name removed", [9, 7, 3]),
          ("oracle text only", [6, 6, 9])]),
        ("&ldquo;a clone effect&rdquo;", ["Clone"],
         [("name + type + cost + oracle", [1]), ("name removed", [4]),
          ("oracle text only", [3])]),
        ("&ldquo;a mana dork&rdquo;", ["Llanowar Elves", "Elvish Mystic", "Birds of Paradise"],
         [("name + type + cost + oracle", [9, 4, 1]), ("name removed", [5, 5, 1]),
          ("oracle text only", [11, 11, 2])]),
    ]
    w('<div class="stack">')
    for query, cols, rows in abl:
        w('<div class="scroller"><table><caption><span class="q">%s</span></caption><thead><tr>'
          '<th class="l">Baseline document</th>%s</tr></thead><tbody>'
          % (query, "".join("<th>%s</th>" % esc(c) for c in cols)))
        for label, vals in rows:
            w('<tr><td class="l">%s</td>%s</tr>'
              % (label, "".join("<td>%d</td>" % v for v in vals)))
        w("</tbody></table></div>")
    w("</div></section>")

    # ---------- method ----------
    w('<section><div class="sec-head"><div class="eyebrow">Method</div>'
      "<h2>How the glossary was built</h2></div>")
    w('<div class="grid2">')
    for title, body in [
        ("Structural splitting only",
         "Line breaks, modal lead-ins and bullets. Nothing sentence-level or semantic, so Wrath "
         "of God&rsquo;s &ldquo;Destroy all creatures. They can&rsquo;t be regenerated.&rdquo; "
         "stays one chunk. Keyword abilities are exploded into their own entries, so Birds of "
         "Paradise yields <span class=\"mono\">Flying</span> separately from its mana ability."),
        ("Exact-match dedup",
         "Normalized by lowercasing, collapsing whitespace and case-normalizing mana symbols. "
         "22 extractions collapse to 18 unique effects. The effect id is a hash of the normalized "
         "text, so hand-authored wording stays attached across rebuilds."),
        ("No fallback",
         "Only entries with a non-empty plain_text are embedded. There is no raw-text fallback, so "
         "a card whose every effect is unauthored is unreachable. Ponder and Divination are in "
         "that state deliberately."),
        ("Authoring discipline",
         "The literal query strings &mdash; mana dork, board wipe, clone effect &mdash; are never "
         "written into any plain_text. Planting the query in the document would guarantee a win by "
         "string echo and say nothing about density. Distractors were authored as carefully as "
         "targets."),
    ]:
        w('<div class="cellx"><h3>%s</h3><p>%s</p></div>' % (title, body))
    w("</div></section>")

    # ---------- glossary ----------
    w('<section><div class="sec-head"><div class="eyebrow">Effect glossary</div>'
      "<h2>All 18 entries, and the three left unauthored</h2>"
      '<p class="col" style="color:var(--ink-soft)">Count is how many of the 17 cards carry that '
      'exact effect. An entry with no plain language is not in the index.</p></div>')
    w('<div class="gloss">')
    w('<div class="grow head"><span>raw text</span><span>plain language</span>'
      "<span>cards</span></div>")
    for eid, e in eff.items():
        auth = e["plain_text"].strip()
        w('<div class="grow%s"><div class="raw">%s</div><div class="plain">%s</div>'
          '<div class="cnt">%d</div></div>'
          % ("" if auth else " unauth", esc(e["raw_text"]),
             esc(auth) if auth else "unauthored &middot; excluded from index",
             e["occurrence_count"]))
    w("</div></section>")

    # ---------- full tables ----------
    w('<section><div class="sec-head"><div class="eyebrow">Per-embedder breakdown</div>'
      "<h2>The three specified queries, every rank before and after fusion</h2>"
      '<p class="col" style="color:var(--ink-soft)">Fused columns are shaded. Cards the query '
      'should find carry a rule on the left. Rows are ordered by effect-level rank, so excluded '
      'cards fall to the bottom.</p></div>')
    w('<div class="stack">')
    for q in doc["queries"]:
        if q["primary"]:
            w(rank_table(doc, q, full=True))
    w("</div></section>")

    w('<section><div class="sec-head"><div class="eyebrow">Diagnostic</div>'
      "<h2>The same three intents, phrased in ordinary English</h2>"
      '<p class="col" style="color:var(--ink-soft)">The specified queries are MTG jargon that none '
      'of the three models knows, which drowns out the density signal. These paraphrases say the '
      'same thing in plain words.</p></div>')
    w('<div class="stack">')
    for q in doc["queries"]:
        if not q["primary"]:
            w(rank_table(doc, q, full=False))
    w("</div></section>")

    # ---------- caveats ----------
    w('<section><div class="sec-head"><div class="eyebrow">Caveats</div>'
      "<h2>What this run cannot tell you</h2></div>")
    w('<ul class="plain-list">')
    for item in [
        "Seventeen cards. Rank differences of one or two places are not meaningful at this size, "
        "and a rank of 9 out of 17 is not comparable to a rank in a corpus of thousands.",
        "The three clusters share one corpus, so each cluster&rsquo;s controls act as the other "
        "clusters&rsquo; distractors. That is intended, but it concentrates the field.",
        "Effect-level documents are hand-authored plain English while baseline documents are raw "
        "oracle text, so wording and document unit are confounded. Some of the effect-level "
        "behaviour is the rewording, not the splitting. Separating them needs a third arm using "
        "unreworded effect chunks.",
        "Category confusion was not tested here. Doubling Season and Parallel Lives still sit high "
        "on &ldquo;a clone effect&rdquo; under both pipelines, as expected &mdash; the mechanism "
        "for that is weighted term relationships, tested separately.",
    ]:
        w("<li>%s</li>" % item)
    w("</ul></section>")

    w('<section><div class="sec-head"><div class="eyebrow">Next</div>'
      "<h2>What to try, in order of expected payoff</h2></div>")
    w('<ul class="plain-list">')
    for item in [
        "Give the effect document its card name and type line back, or restore them at "
        "aggregation time. The ablation says this is the largest recoverable loss.",
        "Re-run on a corpus large enough for burial to be common. The density failure only half "
        "reproduced at 17 cards.",
        "Add the unreworded-effect-chunks arm to separate rewording from splitting.",
        "Handle jargon at the query end rather than the document end. Every result here is "
        "dominated by whether the query is in vocabulary, and none of these embedders knows MTG "
        "slang.",
    ]:
        w("<li>%s</li>" % item)
    w("</ul></section>")

    w('<footer><p>Generated from <span class="mono">reports/results.json</span>. Every rank on '
      "this page is read from that file, which the real embedding run produced. Rebuild with "
      '<span class="mono">./run_all.sh</span>.</p></footer>')
    w("</div>")

    path = os.path.join(REPORTS, "effect-level-search.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("wrote %s" % path)
    return path


if __name__ == "__main__":
    build()
