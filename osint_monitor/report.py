"""Render the daily intelligence brief as a single self-contained HTML file."""
from __future__ import annotations

import html
import json
from datetime import datetime, timedelta

from .fetcher import NewsItem
from . import charts
from .config import DISPLAY_TZ, REFRESH_URL, REPO

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(DISPLAY_TZ)
except Exception:  # tzdata missing on some Windows installs
    from datetime import timezone as _tz
    _TZ = _tz(timedelta(hours=5, minutes=30))


def local(dt: datetime) -> datetime:
    return dt.astimezone(_TZ)

SEV_LABEL = {5: "Critical", 4: "High", 3: "Elevated", 2: "Moderate", 1: "Low", 0: "Info"}
SEV_COLOR = {5: "#b3261e", 4: "#d9531e", 3: "#c98a00", 2: "#4a7bb7", 1: "#6b7a8f", 0: "#9aa4b2"}

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--muted:#5d6b7c;--line:#e3e7ec;--accent:#1f3a5f}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--accent);color:#fff;padding:22px 32px}
header h1{margin:0;font-size:22px}header p{margin:4px 0 0;opacity:.85;font-size:13px}
.banner{background:#fff4e5;border-bottom:1px solid #f0d9b5;padding:8px 32px;font-size:13px;color:#7a4b00}
main{max-width:1100px;margin:0 auto;padding:24px 32px 60px}
h2{font-size:17px;margin:32px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--line)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px}
.kpi b{display:block;font-size:26px}.kpi span{color:var(--muted);font-size:13px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);font-size:14px;vertical-align:top}
th{background:#eef1f5;font-weight:600;font-size:13px;color:var(--muted)}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.up{color:#b3261e;font-weight:600}.down{color:#2e7d32}
.spike{display:inline-block;background:#b3261e;color:#fff;border-radius:4px;padding:0 6px;font-size:11px;margin-left:6px}
.new{display:inline-block;background:#1f3a5f;color:#fff;border-radius:4px;padding:0 6px;font-size:11px;margin-left:6px}
.item{background:var(--card);border:1px solid var(--line);border-left:5px solid;border-radius:8px;padding:12px 16px;margin-bottom:10px}
.item h3{margin:0 0 4px;font-size:15px}.item h3 a{color:var(--ink);text-decoration:none}.item h3 a:hover{text-decoration:underline}
.meta{color:var(--muted);font-size:12.5px}.tag{display:inline-block;background:#eef1f5;border-radius:4px;padding:0 6px;margin:2px 4px 0 0;font-size:12px}
.sev{font-weight:600}.summary{margin:6px 0 0;font-size:14px}
.also{font-size:12.5px;color:var(--muted);margin-top:4px}
footer{color:var(--muted);font-size:12px;text-align:center;padding:20px}
.filters{position:sticky;top:0;z-index:5;background:var(--bg);padding:12px 0 10px;border-bottom:1px solid var(--line);margin-bottom:14px}
.frow{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.filters select,.filters input{font:inherit;font-size:14px;padding:6px 8px;border:1px solid #cfd6de;border-radius:6px;background:#fff;color:var(--ink)}
.filters input{flex:1;min-width:160px}
.chip{font:inherit;font-size:13px;border:1px solid #cfd6de;background:#fff;border-radius:999px;padding:4px 12px;cursor:pointer;color:var(--ink)}
.chip.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.shown{color:var(--muted);font-size:13px;margin-left:auto}
.hdr{display:flex;align-items:flex-start;gap:16px;justify-content:space-between;flex-wrap:wrap}
.refresh{font:inherit;font-size:14px;font-weight:600;background:#fff;color:var(--accent);border:0;border-radius:6px;padding:8px 14px;cursor:pointer}
.refresh:disabled{opacity:.7;cursor:progress}
#rstatus{font-size:12.5px;margin-top:6px;opacity:.9;max-width:420px;text-align:right}
.hidden{display:none!important}"""
CSS += charts.CSS
CSS += """
@media(max-width:700px){.kpis{grid-template-columns:repeat(2,1fr)}main,header{padding-left:16px;padding-right:16px}}
"""


def _pct(t) -> str:
    if t.get("baseline") is False:
        return '<span class="meta">building baseline</span>'
    if t['previous'] == 0:
        return 'new' if t['current'] else '—'
    return f"{'+' if t['change'] > 0 else ''}{t['change'] * 100:.0f}%"


def e(s) -> str:
    return html.escape(str(s), quote=True)


def _item_card(lead: NewsItem, dupes: list[NewsItem]) -> str:
    color = SEV_COLOR[lead.severity]
    tags = "".join(f'<span class="tag">{e(c)}</span>' for c in lead.categories)
    where = ", ".join(lead.areas + [d for d in lead.districts]) or lead.state
    summary = lead.llm_summary or lead.summary[:260]
    also = ""
    if dupes:
        srcs = sorted({d.source for d in dupes if d.source != lead.source})
        if srcs:
            also = f'<div class="also">Also reported by: {e(", ".join(srcs[:6]))}</div>'
    search = " ".join([lead.title, summary, where] + lead.categories).lower()
    return f"""<div class="item" style="border-left-color:{color}"
 data-ts="{int(lead.published.timestamp())}" data-sev="{lead.severity}"
 data-state="{e(lead.state)}" data-districts="{e('|'.join(lead.districts))}"
 data-areas="{e('|'.join(lead.areas))}" data-cats="{e('|'.join(lead.categories))}"
 data-q="{e(search)}">
<h3><a href="{e(lead.link)}" target="_blank" rel="noopener">{e(lead.title)}</a></h3>
<div class="meta"><span class="sev" style="color:{color}">{SEV_LABEL[lead.severity]}</span>
 · {e(where)} · {e(lead.source)} · {local(lead.published):%d %b %H:%M} IST</div>
<div>{tags}</div>
{f'<p class="summary">{e(summary)}</p>' if summary else ''}{also}
</div>"""


_JS = r"""
const CFG = __CFG__;
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const cards = $$('#list .item');
const F = {win: $('#f-win'), state: $('#f-state'), district: $('#f-district'), area: $('#f-area'),
           cat: $('#f-cat'), sev: $('#f-sev'), q: $('#f-q')};

function uniq(attr) {
  const c = {};
  cards.forEach(el => (el.dataset[attr] || '').split('|').filter(Boolean).forEach(v => c[v] = (c[v] || 0) + 1));
  return Object.entries(c).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}
function fill(sel, attr, label) {
  sel.innerHTML = `<option value="">${label}</option>` +
    uniq(attr).map(([v, n]) => `<option value="${v.replace(/"/g, '&quot;')}">${v} (${n})</option>`).join('');
}
fill(F.state, 'state', 'All states'); fill(F.district, 'districts', 'All districts');
fill(F.area, 'areas', 'All Vizag areas'); fill(F.cat, 'cats', 'All categories');

function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  for (const [k, el] of Object.entries(F)) if (p.has(k)) el.value = p.get(k);
}
function writeHash() {
  const p = new URLSearchParams();
  for (const [k, el] of Object.entries(F)) if (el.value && !(k === 'sev' && el.value === '0') && !(k === 'win' && el.value === String(CFG.defaultWin))) p.set(k, el.value);
  history.replaceState(null, '', p.toString() ? '#' + p : location.pathname);
}
function apply() {
  const now = Date.now() / 1000, win = +F.win.value * 3600, q = F.q.value.trim().toLowerCase();
  let shown = 0, high = 0;
  cards.forEach(el => {
    const d = el.dataset;
    const ok = (now - +d.ts <= win)
      && (!F.state.value || d.state.split(' / ').includes(F.state.value) || d.state === F.state.value)
      && (!F.district.value || d.districts.split('|').includes(F.district.value))
      && (!F.area.value || d.areas.split('|').includes(F.area.value))
      && (!F.cat.value || d.cats.split('|').includes(F.cat.value))
      && (+d.sev >= +F.sev.value)
      && (!q || d.q.includes(q));
    el.classList.toggle('hidden', !ok);
    if (ok) { shown++; if (+d.sev >= 4) high++; }
  });
  $('#k-inc').textContent = shown; $('#k-high').textContent = high;
  $('#shown').textContent = `${shown} of ${cards.length} incidents`;
  $('#empty').classList.toggle('hidden', shown > 0);
  $('#chip-vizag').classList.toggle('on', F.district.value === 'Visakhapatnam');
  $('#chip-all').classList.toggle('on', !F.district.value && !F.area.value && !F.state.value && !F.cat.value && !q && F.sev.value === '0');
  writeHash();
}
Object.values(F).forEach(el => el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', apply));
F.area.addEventListener('change', () => { if (F.area.value) F.district.value = 'Visakhapatnam'; apply(); });
$('#chip-vizag').onclick = () => { F.district.value = F.district.value === 'Visakhapatnam' ? '' : 'Visakhapatnam'; if (!F.district.value) F.area.value = ''; apply(); };
$('#chip-all').onclick = () => { ['state', 'district', 'area', 'cat', 'q'].forEach(k => F[k].value = ''); F.sev.value = '0'; apply(); };
readHash(); apply();

// ---- refresh -------------------------------------------------------------
const btn = $('#refresh'), st = $('#rstatus');
async function latest() {
  try { const r = await fetch('status.json?t=' + Date.now(), {cache: 'no-store'}); return (await r.json()).generated_at || 0; }
  catch (e) { return 0; }
}
let polling = null;
function poll(maxMin) {
  clearInterval(polling);
  const until = Date.now() + maxMin * 60000;
  polling = setInterval(async () => {
    if (await latest() > CFG.generatedAt) { st.textContent = 'New news arrived. Reloading…'; location.reload(); }
    else if (Date.now() > until) { clearInterval(polling); btn.disabled = false; btn.textContent = '↻ Refresh now';
      st.textContent = 'Still running on GitHub. This page will update on its next check.'; }
  }, 15000);
}
btn.onclick = async () => {
  btn.disabled = true; btn.textContent = 'Refreshing…';
  if (CFG.refreshUrl) {
    try {
      const r = await fetch(CFG.refreshUrl, {method: 'POST'});
      const j = await r.json();
      st.textContent = j.message || 'Fetching the latest news (about 2–3 minutes)…';
    } catch (e) { st.textContent = 'Could not reach the refresh service. Try again in a minute.'; btn.disabled = false; btn.textContent = '↻ Refresh now'; return; }
  } else {
    window.open(CFG.actionsUrl, '_blank', 'noopener');
    st.textContent = 'On the GitHub page that opened, click "Run workflow". This page reloads by itself when the new news is ready (about 2–3 minutes).';
  }
  poll(8);
};
// background check every 5 minutes; reload quietly if a newer brief exists
setInterval(async () => { if (!polling && await latest() > CFG.generatedAt) location.reload(); }, 300000);
"""


def _arrow(p) -> str:
    if p["direction"] == "up":
        return f'<span class="up">▲ rising ({p["trend"]:.1f}x)</span>'
    if p["direction"] == "down":
        return f'<span class="down">▼ easing ({p["trend"]:.1f}x)</span>'
    return '<span class="flat">● steady</span>'


def _outlook_table(rows, label, empty) -> str:
    if not rows:
        return f'<p class="meta">{empty}</p>'
    body = "".join(
        f"<tr><td>{e(r['key'] if isinstance(r['key'], str) else ' in '.join(r['key']))}</td>"
        f"<td class=num>{r['last7']}</td>"
        f"<td class=num>~{r['expected']:.1f} <span class=meta>({r['low']}–{r['high']})</span></td>"
        f"<td><span class=ptrack><b style=\"width:{r['p_any'] * 100:.0f}%\"></b></span>{r['p_any'] * 100:.0f}%</td>"
        f"<td>{_arrow(r)}</td></tr>" for r in rows)
    return (f"<table><tr><th>{label}</th><th class=num>Last 7 days</th><th class=num>Expected next 7 (range)</th>"
            f"<th>Chance of ≥1</th><th>Trend</th></tr>{body}</table>")


def _outlook_section(o) -> str:
    if o is None:
        return ""
    hist = o.daily_total()
    fc = o.forecast_days()
    main = charts.daily_chart(hist, fc)
    total = o.project(o.total)
    data_rows = "".join(f"<tr><td>{d:%a %d %b}</td><td class=num>{c}</td><td>{'incomplete' if p else ''}</td></tr>"
                        for d, c, p in hist) + "".join(
        f"<tr><td>{d:%a %d %b}</td><td class=num>~{ex:.1f} ({lo}–{hi})</td><td>outlook</td></tr>" for d, ex, lo, hi in fc)

    recent = [h for h in hist if h[0] >= o.today - __import__("datetime").timedelta(days=13)]
    small = []
    for r in o.category_rows(top=8):
        cat = r["key"]
        svg = charts.daily_chart([(d, o.by_cat[cat].get(d, 0), p) for d, _, p in recent],
                                 o.forecast_days(o.by_cat[cat]), width=240, height=90, compact=True)
        small.append(f'<div class="viz"><h3>{e(cat)}</h3><div class="num">{r["last7"]} last 7 days · '
                     f'next 7: ~{r["expected"]:.1f} · {_arrow(r)}</div>{svg}</div>')

    conf_text = {"Low": "only a few days of monitoring so far, so treat the outlook as a rough guide",
                 "Medium": "a couple of weeks of history; rates are usable, trends still settling",
                 "High": "3+ weeks of history"}[o.conf]
    return f"""
<h2>Trends &amp; 7-day outlook</h2>
<p class="note">Outlook confidence: <span class="conf">{o.conf}</span>: {conf_text}
({o.n_reliable} reliable day{'s' if o.n_reliable != 1 else ''}; Medium from 7, High from 21).
The outlook estimates how many <b>news-reported</b> incidents to expect, from recent daily rates and their trend.
It is a planning aid for where attention may be needed, not a prediction of specific crimes.</p>

<div class="viz"><h3>Crime &amp; security incidents per day: AP &amp; Telangana</h3>
<p class="sub">Last 30 days and next 7 days · next week expected ~{total['expected']:.0f} incidents
(likely {total['low']}–{total['high']}) · {_arrow(total)}</p>
{charts.LEGEND}<div class="scroll">{main}</div>
<details class="dt"><summary>Show data table</summary><table><tr><th>Day</th><th class=num>Incidents</th><th>Note</th></tr>{data_rows}</table></details>
</div>

<h3 style="font-size:15px;margin:18px 0 8px">By category: last 14 days and next 7</h3>
<div class="sm">{''.join(small) or '<p class="meta">Not enough data yet.</p>'}</div>

<h3 style="font-size:15px;margin:22px 0 8px">Watchlist: most likely next week (category × district)</h3>
{_outlook_table(o.watchlist(), "Category in district", "Not enough district-level history yet.")}

<h3 style="font-size:15px;margin:22px 0 8px">District outlook</h3>
{_outlook_table(o.district_rows(), "District / Commissionerate", "Not enough district-level history yet.")}

<h3 style="font-size:15px;margin:22px 0 8px">Vizag areas outlook</h3>
{_outlook_table(o.area_rows(), "Vizag area", "No Vizag area-level incidents in the last 30 days yet.")}
"""


def render(*, items: list[NewsItem], clusters: dict[str, list[NewsItem]], trends, hotspots,
           emerging, now: datetime, hours: int, demo: bool, outlook=None) -> str:
    week_start = now - timedelta(days=7)
    incidents = [cl for cl in clusters.values()
                 if cl[0].categories and cl[0].published >= week_start]
    incidents.sort(key=lambda cl: (-cl[0].severity, -len(cl), -cl[0].published.timestamp()))
    incidents = incidents[:500]

    recent_start = now - timedelta(hours=24)
    n_articles = sum(1 for i in items if i.published >= recent_start)
    n_spikes = sum(1 for t in trends if t["spike"])

    trend_rows = "".join(
        f"<tr><td>{e(t['category'])}{'<span class=spike>SPIKE</span>' if t['spike'] else ''}</td>"
        f"<td>{e(t['state'])}</td><td class=num>{t['current']}</td><td class=num>{t['previous']}</td>"
        f"<td class='num {'up' if t['change'] > 0 else 'down' if t['change'] < 0 else ''}'>"
        f"{_pct(t)}</td></tr>"
        for t in trends[:15]) or "<tr><td colspan=5>Not enough history yet.</td></tr>"

    hot_rows = "".join(
        f"<tr><td>{e(h['district'])}</td><td class=num>{h['total']}</td>"
        f"<td>{e(', '.join(f'{c} ({n})' for c, n in h['by_category']))}</td></tr>"
        for h in hotspots) or "<tr><td colspan=3>No district-tagged incidents.</td></tr>"

    emerging_html = "".join(
        f'<span class="tag">{e(t["term"])} · {t["count"]}{"<span class=new>NEW</span>" if t["new"] else ""}</span>'
        for t in emerging) or '<span class="meta">None detected this week.</span>'

    cards = "".join(_item_card(cl[0], cl[1:]) for cl in incidents)

    banner = ('<div class="banner"><b>DEMO MODE</b>: headlines below are synthetic sample data, '
              'not real incidents.</div>') if demo else ""

    win_opts = "".join(f'<option value="{h}"{" selected" if h == hours else ""}>{lbl}</option>'
                       for h, lbl in ((6, "Last 6 hours"), (24, "Last 24 hours"),
                                      (72, "Last 3 days"), (168, "Last 7 days")))
    if hours not in (6, 24, 72, 168):
        win_opts += f'<option value="{hours}" selected>Last {hours} hours</option>'
    sev_opts = "".join(f'<option value="{v}">{lbl}</option>' for v, lbl in
                       ((0, "Any severity"), (3, "Elevated +"), (4, "High +"), (5, "Critical only")))

    cfg = json.dumps({
        "refreshUrl": REFRESH_URL,
        "actionsUrl": f"https://github.com/{REPO}/actions/workflows/hourly.yml",
        "generatedAt": int(now.timestamp()),
        "defaultWin": hours,
    })

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Open-Source Crime &amp; Threat Brief, {local(now):%d %b %Y}</title><style>{CSS}</style></head><body>
<header><div class="hdr"><div><h1>Open-Source Crime &amp; Threat Brief</h1>
<p>Andhra Pradesh &amp; Telangana · last updated {local(now):%d %b %Y, %H:%M} IST · updates hourly</p></div>
<div style="text-align:right"><button class="refresh" id="refresh">↻ Refresh now</button><div id="rstatus"></div></div></div></header>
{banner}
<main>
<div class="kpis">
<div class="kpi"><b>{n_articles}</b><span>articles scanned (24h)</span></div>
<div class="kpi"><b id="k-inc">0</b><span>incidents shown</span></div>
<div class="kpi"><b id="k-high">0</b><span>high / critical shown</span></div>
<div class="kpi"><b>{n_spikes}</b><span>category spikes (7d)</span></div>
</div>

{_outlook_section(outlook)}

<h2>Incidents</h2>
<div class="filters">
<div class="frow" style="margin-bottom:8px">
<button class="chip" id="chip-all">All</button>
<button class="chip" id="chip-vizag">Vizag only</button>
<select id="f-win" aria-label="Time window">{win_opts}</select>
<select id="f-sev" aria-label="Severity">{sev_opts}</select>
<span class="shown" id="shown"></span>
</div>
<div class="frow">
<select id="f-state" aria-label="State"></select>
<select id="f-district" aria-label="District"></select>
<select id="f-area" aria-label="Vizag area"></select>
<select id="f-cat" aria-label="Category"></select>
<input id="f-q" type="search" placeholder="Search (e.g. ganja, digital arrest)" aria-label="Search">
</div>
</div>
<div id="list">{cards}</div>
<p class="meta hidden" id="empty">No incidents match these filters. Try a longer time window.</p>

<h2>Trends: last 7 days vs previous 7</h2>
<table><tr><th>Category</th><th>State</th><th class=num>This week</th><th class=num>Last week</th><th class=num>Change</th></tr>
{trend_rows}</table>

<h2>District hotspots: last 7 days</h2>
<table><tr><th>District / Commissionerate</th><th class=num>Incidents</th><th>Top categories</th></tr>
{hot_rows}</table>

<h2>Modus operandi watch</h2>
<div>{emerging_html}</div>
</main>
<footer>Updates every hour · <a href="incidents.json">incidents.json</a><br>Compiled automatically from public news sources. Unverified: corroborate before acting.
Severity is a keyword-based estimate, not an assessment.</footer>
<script>{_JS.replace("__CFG__", cfg)}</script>
<script>{charts.TIP_JS}</script>
</body></html>"""
