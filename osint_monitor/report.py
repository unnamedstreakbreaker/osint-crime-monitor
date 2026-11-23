"""Render the daily intelligence brief as a single self-contained HTML file."""
from __future__ import annotations

import html
from datetime import datetime, timedelta

from .fetcher import NewsItem
from .config import DISPLAY_TZ

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
@media(max-width:700px){.kpis{grid-template-columns:repeat(2,1fr)}main,header{padding-left:16px;padding-right:16px}}
"""


def _pct(t) -> str:
    if t['previous'] == 0:
        return 'new' if t['current'] else '—'
    return f"{'+' if t['change'] > 0 else ''}{t['change'] * 100:.0f}%"


def e(s) -> str:
    return html.escape(str(s), quote=True)


def _item_card(lead: NewsItem, dupes: list[NewsItem]) -> str:
    color = SEV_COLOR[lead.severity]
    tags = "".join(f'<span class="tag">{e(c)}</span>' for c in lead.categories)
    where = ", ".join(lead.districts) or lead.state
    summary = lead.llm_summary or lead.summary[:260]
    also = ""
    if dupes:
        srcs = sorted({d.source for d in dupes if d.source != lead.source})
        if srcs:
            also = f'<div class="also">Also reported by: {e(", ".join(srcs[:6]))}</div>'
    return f"""<div class="item" style="border-left-color:{color}">
<h3><a href="{e(lead.link)}" target="_blank" rel="noopener">{e(lead.title)}</a></h3>
<div class="meta"><span class="sev" style="color:{color}">{SEV_LABEL[lead.severity]}</span>
 · {e(where)} · {e(lead.source)} · {local(lead.published):%d %b %H:%M} IST</div>
<div>{tags}</div>
{f'<p class="summary">{e(summary)}</p>' if summary else ''}{also}
</div>"""


def render(*, items: list[NewsItem], clusters: dict[str, list[NewsItem]], trends, hotspots,
           emerging, now: datetime, hours: int, demo: bool) -> str:
    recent_start = now - timedelta(hours=hours)
    recent = [cl for cl in clusters.values()
              if cl[0].categories and cl[0].published >= recent_start]
    recent.sort(key=lambda cl: (-cl[0].severity, -len(cl), -cl[0].published.timestamp()))

    n_articles = sum(1 for i in items if i.published >= recent_start)
    n_incidents = len(recent)
    n_high = sum(1 for cl in recent if cl[0].severity >= 4)
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

    cards = "".join(_item_card(cl[0], cl[1:]) for cl in recent[:40]) or \
        '<p class="meta">No categorised incidents in this window.</p>'

    banner = ('<div class="banner"><b>DEMO MODE</b> — headlines below are synthetic sample data, '
              'not real incidents.</div>') if demo else ""

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="900">
<title>Open-Source Crime &amp; Threat Brief — {local(now):%d %b %Y}</title><style>{CSS}</style></head><body>
<header><h1>Open-Source Crime &amp; Threat Brief</h1>
<p>Andhra Pradesh &amp; Telangana · generated {local(now):%d %b %Y, %H:%M} IST · last {hours}h of public news</p></header>
{banner}
<main>
<div class="kpis">
<div class="kpi"><b>{n_articles}</b><span>articles scanned</span></div>
<div class="kpi"><b>{n_incidents}</b><span>distinct incidents</span></div>
<div class="kpi"><b>{n_high}</b><span>high / critical</span></div>
<div class="kpi"><b>{n_spikes}</b><span>category spikes (7d)</span></div>
</div>

<h2>Trends — last 7 days vs previous 7</h2>
<table><tr><th>Category</th><th>State</th><th class=num>This week</th><th class=num>Last week</th><th class=num>Change</th></tr>
{trend_rows}</table>

<h2>District hotspots — last 7 days</h2>
<table><tr><th>District / Commissionerate</th><th class=num>Incidents</th><th>Top categories</th></tr>
{hot_rows}</table>

<h2>Modus operandi watch</h2>
<div>{emerging_html}</div>

<h2>Incidents — last {hours}h (highest severity first)</h2>
{cards}
</main>
<footer>Updates every hour · <a href="incidents.json">incidents.json</a><br>Compiled automatically from public news sources. Unverified — corroborate before acting.
Severity is a keyword-based estimate, not an assessment.</footer>
</body></html>"""
