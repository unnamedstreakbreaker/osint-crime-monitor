"""Render the brief as a tile dashboard: each tile opens its full view in a pop-up."""
from __future__ import annotations

import html
import json
from datetime import datetime, timedelta

from . import charts
from .config import DISPLAY_TZ, REPO
from .fetcher import NewsItem
from .explain import predictions, EVIDENCE_RULE, city_insights, city_facts, fmt_rupees, TERM_LABEL
from . import i18n
from .i18n import news
from . import config
from urllib.parse import urlparse, parse_qs

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(DISPLAY_TZ)
except Exception:  # tzdata missing on some Windows installs
    from datetime import timezone as _tz
    _TZ = _tz(timedelta(hours=5, minutes=30))


_LANG = "en"


def L(en: str, te: str) -> str:
    """Pick the string for the page being rendered."""
    return te if _LANG == "te" else en


def local(dt: datetime) -> datetime:
    return dt.astimezone(_TZ)


SEV_LABEL = {5: "Critical", 4: "High", 3: "Elevated", 2: "Moderate", 1: "Low", 0: "Info"}
SEV_COLOR = {5: "#b3261e", 4: "#d9531e", 3: "#c98a00", 2: "#4a7bb7", 1: "#6b7a8f", 0: "#9aa4b2"}

# Line icons (24px, stroke = currentColor)
ICONS = {
    "pulse": '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "swap": '<path d="M7 4v16M3 8l4-4 4 4M17 20V4M13 16l4 4 4-4"/>',
    "hook": '<path d="M12 3v10a4 4 0 1 1-4-4"/><path d="M12 3l3 3"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "download": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    "offline": '<path d="M2 8.5a15 15 0 0 1 4-2.6M22 8.5A15 15 0 0 0 10 5.1M5 12.5a10 10 0 0 1 3-1.9M19 12.5a10 10 0 0 0-4.6-2.4M8.5 16a5 5 0 0 1 7 0M12 20h.01M3 3l18 18"/>',
    "share": '<path d="M12 3v12M8 7l4-4 4 4M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
}


def icon(name: str, size: int = 22) -> str:
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


CSS = """
:root{--navy:#13233f;--navy2:#1d3358;--brass:#b8913a;--brass-soft:#f3ead3;--page:#edf0f4;--tile:#fff;
--ink:#1b2433;--ink2:#55606f;--line:#d9dee5;--soft:#f5f7fa;
--display:"Barlow Condensed","Noto Sans Telugu","Arial Narrow",system-ui,sans-serif;--body:"Barlow","Noto Sans Telugu",system-ui,-apple-system,"Segoe UI",sans-serif}
html[lang=te] body{line-height:1.6}html[lang=te] .glance{grid-template-columns:128px 1fr}html[lang=te] .tile h2,html[lang=te] .dlg-hd h2,html[lang=te] .title h1{letter-spacing:0}
.actions{margin-left:auto;display:flex;align-items:center;gap:10px;flex:none}
.install{display:inline-flex;align-items:center;gap:6px;background:var(--brass);color:var(--navy);border:0;border-radius:999px;
 padding:7px 14px;font-weight:600;font-size:14.5px;cursor:pointer}
.install[hidden]{display:none}
.offline{display:flex;align-items:center;justify-content:center;gap:8px;background:#fff4e5;color:#7a4b00;font-size:14px;padding:8px 16px}
.offline[hidden]{display:none}
.ioshint{position:fixed;left:12px;right:12px;bottom:calc(12px + env(safe-area-inset-bottom));z-index:40;display:flex;align-items:center;gap:10px;
 background:var(--navy);color:#fff;border:1px solid var(--brass);border-radius:12px;padding:12px 14px;font-size:14.5px;box-shadow:0 10px 30px rgba(10,20,40,.35)}
.ioshint .ic{color:var(--brass);flex:none}.ioshint[hidden]{display:none}
.x2{margin-left:auto;background:transparent;border:0;color:#fff;cursor:pointer;padding:6px;flex:none}
html{-webkit-tap-highlight-color:transparent}
.board{padding-top:max(22px,env(safe-area-inset-top))}
.app .board{padding-top:max(14px,env(safe-area-inset-top))}
footer{padding-bottom:max(30px,env(safe-area-inset-bottom))}
.lang{display:inline-flex;border:1px solid #3a5480;border-radius:999px;overflow:hidden;flex:none}

.lang a{color:#dfe6f1;text-decoration:none;padding:6px 14px;font-size:14.5px}
.lang a.on{background:var(--brass);color:var(--navy);font-weight:600}
.lang a:not(.on):hover{background:#2c4369}
*{box-sizing:border-box}
body{margin:0;font:16px/1.5 var(--body);background:var(--page);color:var(--ink)}
a{color:inherit}
button{font:inherit;color:inherit}
:focus-visible{outline:3px solid var(--brass);outline-offset:2px}

/* header: the duty board */
.board{background:var(--navy);color:#fff;padding:22px 32px 26px}
.board-in{max-width:1240px;margin:0 auto}
.top{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.emblem{width:46px;height:46px;border-radius:50%;border:2px solid var(--brass);display:grid;place-items:center;color:var(--brass);flex:none}
.title{flex:1;min-width:0}
.title h1{font:600 30px/1.05 var(--display);margin:0;letter-spacing:.2px}
.title p{margin:2px 0 0;color:#b9c3d3;font-size:14px}
.cities{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.city{display:inline-flex;align-items:baseline;gap:6px;border:1px solid #3a5480;border-radius:999px;padding:6px 14px;
 color:#dfe6f1;text-decoration:none;font-size:14.5px}
.city.on{background:var(--brass);border-color:var(--brass);color:var(--navy);font-weight:600}
a.city:not(.on):hover{border-color:var(--brass)}
.city.soon{opacity:.6;cursor:not-allowed}.city small{font-size:12px}
.counters{display:grid;grid-template-columns:repeat(4,1fr);margin-top:22px;border-top:1px solid #2c4369}
.counter{padding:14px 18px 0 0}
.counter+.counter{padding-left:18px;border-left:1px solid #2c4369}
.counter b{display:block;font:600 44px/1 var(--display);font-variant-numeric:tabular-nums}
.counter span{color:#b9c3d3;font-size:14px}
.counter.alert b{color:#ffb4a8}
.banner{background:#fff4e5;color:#7a4b00;font-size:14px;padding:8px 32px;text-align:center}

/* prediction cards */
.preds{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.pred{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px;display:flex;flex-direction:column;gap:10px}
.pred-top{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:start}
.pred h4{margin:0;font:600 22px/1.15 var(--display)}
.pred .what{margin:2px 0 0;color:var(--ink2);font-size:14.5px}
.pred .count{text-align:right;font:600 34px/1 var(--display);color:var(--navy)}
.pred .count small{display:block;font:400 12.5px var(--body);color:var(--ink2);margin-top:3px}
.chance{display:flex;align-items:center;gap:8px;font-size:14px}
.chance s{flex:1;max-width:220px;height:8px;border-radius:4px;background:var(--line);overflow:hidden;text-decoration:none}
.chance s b{display:block;height:100%;background:#2a78d6;border-radius:4px}
.pred dl{margin:0;display:grid;grid-template-columns:62px 1fr;gap:6px 10px;font-size:14.5px}
.pred dt{font-weight:600;color:var(--navy)}.pred dd{margin:0}
.pred ul{margin:0;padding-left:18px}.pred li{margin:2px 0}
.ev{border-top:1px solid #e8ecf1;padding-top:8px;font-size:13.5px}
.ev a{display:block;color:var(--ink);text-decoration:none;padding:3px 0}.ev a:hover{text-decoration:underline}
.ev a span{color:var(--ink2)}
.howto{background:var(--brass-soft);border:1px solid #e6d6ad;border-radius:10px;padding:12px 16px;font-size:14.5px;margin-bottom:16px}
.howto p{margin:0 0 4px}.howto p:last-child{margin:0}
@media(max-width:800px){.preds{grid-template-columns:1fr}}

.grade{display:inline-block;font-size:12.5px;font-weight:600;border-radius:999px;padding:2px 10px;margin-top:6px}
.g-Strong{background:#dff3e4;color:#0b5a26}.g-Moderate{background:#e5eefb;color:#1d4f91}.g-Limited{background:#eceef1;color:#55606f}
.evline{font-size:13.5px;color:var(--ink2)}
.ev summary{cursor:pointer;font-weight:600;color:var(--navy)}
.ev a em{font-style:normal;color:var(--ink2)}
.record{background:#fff;border:1px solid var(--line);border-left:5px solid var(--navy);border-radius:10px;padding:12px 16px;margin-bottom:12px}
.record b.big{font:600 26px/1 var(--display);color:var(--navy);margin-right:6px}
.record p{margin:4px 0 0;font-size:14.5px}
.hit{color:#0b5a26;font-weight:600}.miss{color:#b3261e;font-weight:600}
details.method{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 16px;margin-bottom:16px;font-size:14.5px}
details.method summary{cursor:pointer;font-weight:600;color:var(--navy)}
details.method h5{margin:12px 0 4px;font-size:14.5px}
details.method ul,details.method ol{margin:0;padding-left:20px}
details.early{margin-top:8px}details.early>summary{cursor:pointer;font:600 18px var(--display);color:var(--ink2)}

.brief{background:var(--navy);color:#fff;border-radius:12px;padding:16px 20px;margin-bottom:14px}
.brief h3{margin:0 0 8px!important;color:#fff;font:600 22px/1.1 var(--display)}
.brief ul{margin:0;padding-left:20px}.brief li{margin:5px 0;font-size:15px;line-height:1.45}
.glance{margin:0;display:grid;grid-template-columns:96px 1fr;border:1px solid #e8ecf1;border-radius:8px;overflow:hidden;font-size:14.5px}
.glance dt,.glance dd{padding:6px 10px;border-bottom:1px solid #eef1f5;margin:0}
.glance dt{background:var(--soft);font-weight:600;color:var(--ink2);font-size:13.5px}
.glance dt:nth-last-of-type(1),.glance dd:last-child{border-bottom:0}
.insight{background:var(--brass-soft);border-left:4px solid var(--brass);border-radius:6px;padding:8px 12px;font-weight:500;font-size:15px;margin:0}
.focus{font-size:14px;margin:0}.focus b{color:var(--navy)}
details.whyd summary{cursor:pointer;font-weight:600;color:var(--navy);font-size:14.5px}
details.whyd ul{margin:6px 0 0;padding-left:18px;font-size:14px}

/* tile grid */
main{max-width:1240px;margin:0 auto;padding:26px 32px 50px}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);grid-auto-rows:minmax(170px,auto);gap:16px}
.tile{position:relative;background:var(--tile);border:1px solid var(--line);border-radius:12px;padding:18px 20px 16px;
 text-align:left;cursor:pointer;display:flex;flex-direction:column;gap:10px;min-width:0;transition:border-color .15s,box-shadow .15s}
.tile:hover{border-color:var(--brass);box-shadow:0 6px 22px rgba(19,35,63,.10)}
.tile .hd{display:flex;align-items:center;gap:10px}
.tile .hd .ic{color:var(--brass);flex:none}
.tile h2{font:600 22px/1.1 var(--display);margin:0}
.tile .more{margin-left:auto;font-size:13px;color:var(--ink2);white-space:nowrap}
.tile .lead{font:600 34px/1 var(--display);font-variant-numeric:tabular-nums}
.tile .lead small{font:400 15px var(--body);color:var(--ink2);margin-left:6px}
.tile p{margin:0;color:var(--ink2);font-size:14.5px}
.t-trends{grid-column:span 2;grid-row:span 2;background:var(--navy2);color:#fff;border-color:var(--navy2)}
.t-trends p,.t-trends .more{color:#c4cede}.t-trends .lead small{color:#c4cede}
.t-trends:hover{border-color:var(--brass)}
.t-trends .chartwrap{background:#fcfcfb;border-radius:8px;padding:10px 10px 4px}
.t-trends .flat{color:#dfe6f1}.t-trends .up{color:#ffb4a8}.t-trends .down{color:#9be29b}
.catstrip{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:auto;padding-top:6px}
.catstrip div{border-top:2px solid var(--brass);padding-top:6px;font-size:13.5px;color:#c4cede}
.catstrip b{display:block;font:600 24px/1.1 var(--display);color:#fff}
.t-incidents{grid-row:span 2}
.heads{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
.heads li{display:grid;grid-template-columns:10px 1fr;gap:10px;font-size:14.5px;line-height:1.35}
.heads i{width:10px;height:10px;border-radius:50%;margin-top:5px}
.heads span{display:block;color:var(--ink2);font-size:13px;margin-top:2px}
.bars{display:flex;flex-direction:column;gap:7px;font-size:14px}
.bars div{display:grid;grid-template-columns:1fr 40px;column-gap:8px;row-gap:3px;align-items:center}
.bars em{grid-column:1/-1}
.bars em{font-style:normal;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px}
.bars s{display:block;height:8px;border-radius:4px;background:var(--line);text-decoration:none;overflow:hidden}
.bars s b{display:block;height:100%;background:#2a78d6;border-radius:4px}
.bars code{font:inherit;font-variant-numeric:tabular-nums;text-align:right;color:var(--ink2)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip-s{background:var(--soft);border:1px solid var(--line);border-radius:999px;padding:2px 10px;font-size:13.5px}
.chip-s.hot{border-color:var(--brass);background:var(--brass-soft)}
.pill{display:inline-block;font-size:12.5px;border-radius:999px;padding:1px 10px;background:#2c4369;color:#dfe6f1}
.empty-t{color:var(--ink2);font-size:14px}

/* pop-up */
dialog{border:0;padding:0;border-radius:16px;width:min(1080px,94vw);max-height:90vh;background:var(--page);color:var(--ink);
 box-shadow:0 30px 80px rgba(10,20,40,.35)}
dialog::backdrop{background:rgba(13,24,43,.55);backdrop-filter:blur(3px)}
dialog[open]{animation:pop .18s ease-out}
@keyframes pop{from{opacity:0;transform:translateY(10px) scale(.985)}to{opacity:1;transform:none}}
.dlg-hd{position:sticky;top:0;z-index:6;display:flex;align-items:center;gap:12px;background:var(--navy);color:#fff;padding:14px 18px 14px 22px}
.dlg-hd .ic{color:var(--brass)}
.dlg-hd h2{font:600 26px/1.1 var(--display);margin:0}
.dlg-hd p{margin:0;color:#b9c3d3;font-size:13.5px}
.x{margin-left:auto;width:40px;height:40px;border-radius:50%;border:1px solid #3a5480;background:transparent;color:#fff;
 display:grid;place-items:center;cursor:pointer;flex:none}
.x:hover{background:#2c4369}
.dlg-bd{padding:20px 22px 26px;overflow:auto;max-height:calc(90vh - 70px)}
.dlg-bd h3{font:600 20px/1.2 var(--display);margin:22px 0 10px}
.dlg-bd h3:first-child{margin-top:0}
@media (prefers-reduced-motion:reduce){dialog[open]{animation:none}.tile{transition:none}}

/* tables & incidents (inside pop-ups) */
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid #e8ecf1;font-size:14.5px;vertical-align:top}
th{background:var(--soft);font-weight:600;font-size:13.5px;color:var(--ink2)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.meta{color:var(--ink2);font-size:13.5px}
.spike{display:inline-block;background:#b3261e;color:#fff;border-radius:4px;padding:0 6px;font-size:12px;margin-left:6px}
.new{display:inline-block;background:var(--navy);color:#fff;border-radius:4px;padding:0 6px;font-size:12px;margin-left:6px}
.item{background:#fff;border:1px solid var(--line);border-left:5px solid;border-radius:10px;padding:12px 16px;margin-bottom:10px}
.item h4{margin:0 0 4px;font-size:16px;line-height:1.35}.item h4 a{text-decoration:none}.item h4 a:hover{text-decoration:underline}
.item .meta span+span::before{content:"";display:inline-block;width:4px;height:4px;border-radius:50%;background:#9aa4b2;margin:0 8px 2px}
.sev{font-weight:600}.summary{margin:6px 0 0;font-size:14.5px}
.tag{display:inline-block;background:var(--soft);border:1px solid #e3e7ec;border-radius:4px;padding:0 6px;margin:4px 4px 0 0;font-size:12.5px}
.also{font-size:13px;color:var(--ink2);margin-top:4px}
.filters{position:sticky;top:0;z-index:5;background:var(--page);padding:4px 0 12px;margin-bottom:6px;border-bottom:1px solid var(--line)}
.frow{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.filters select,.filters input{font:inherit;font-size:14.5px;padding:7px 9px;border:1px solid #c9d1db;border-radius:8px;background:#fff;color:var(--ink)}
.filters input{flex:1;min-width:170px}
.chip{border:1px solid #c9d1db;background:#fff;border-radius:999px;padding:5px 14px;cursor:pointer;font-size:14px}
.chip.on{background:var(--navy);color:#fff;border-color:var(--navy)}
.shown{color:var(--ink2);font-size:14px;margin-left:auto}
.hidden{display:none!important}
footer{color:var(--ink2);font-size:13px;text-align:center;padding:8px 20px 30px}

@media(max-width:1000px){.tiles{grid-template-columns:repeat(2,1fr)}.t-trends{grid-column:span 2;grid-row:span 1}}
@media(max-width:640px){
 .board{padding:18px 16px 20px}main{padding:18px 16px 40px}
 .tiles{grid-template-columns:1fr}.t-trends,.t-incidents{grid-column:auto;grid-row:auto}
 .counters{grid-template-columns:repeat(2,1fr)}.counter:nth-child(3){border-left:0;padding-left:0}
 .counter b{font-size:36px}
 dialog{width:100vw;max-width:100vw;max-height:100dvh;height:100dvh;border-radius:0}.dlg-bd{max-height:calc(100dvh - 70px)}
}
"""
CSS += charts.CSS
CSS += """
/* phone layout: last so it wins over the base rules */
@media(max-width:640px){
 .top{display:grid;grid-template-columns:auto 1fr;align-items:center;gap:10px 12px}
 .emblem{width:38px;height:38px;grid-row:1}.emblem .ic{width:20px;height:20px}
 .actions{grid-column:2;grid-row:1;justify-self:end}
 .title{grid-column:1/-1;grid-row:2}
 .title h1{font-size:27px}.title p{font-size:13.5px;margin-top:4px}
 .install span{display:none}.install{padding:8px}
 .cities{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;margin:14px -16px 0;padding:0 16px}
 .cities::-webkit-scrollbar{display:none}.city{flex:none}
 .tile{padding:16px}.tile:active{transform:scale(.99)}
 .filters{position:static}
 .filters .frow{display:grid;grid-template-columns:1fr 1fr;gap:8px}
 .filters .frow .chip{text-align:center}
 .filters select,.filters input{width:100%;min-width:0}
 .filters input,.shown{grid-column:1/-1}.shown{margin-left:0}
 .dlg-hd{padding-top:max(14px,env(safe-area-inset-top))}
 .dlg-hd h2{font-size:23px}.dlg-hd p{font-size:13px}
 .dlg-bd{padding:16px 14px 30px}
 .dlg-bd table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}
 .pred{padding:14px}.pred h4{font-size:20px}.pred .count{font-size:30px}
 .glance{grid-template-columns:86px 1fr}
 .brief{padding:14px 16px}.brief li{font-size:14.5px}
}
"""


def _pct(t) -> str:
    if t.get("baseline") is False:
        return '<span class="meta">building baseline</span>'
    if t['previous'] == 0:
        return 'new' if t['current'] else '—'
    return f"{'+' if t['change'] > 0 else ''}{t['change'] * 100:.0f}%"


def e(s) -> str:
    return html.escape(str(s), quote=True)


def _term(t: str) -> str:
    return i18n.term(TERM_LABEL.get(t, t)) if _LANG == "te" else t


def _name(key) -> str:
    if isinstance(key, str):
        return key
    return L(" in ".join(key), f"{key[1]}లో {i18n.cat(key[0])}")


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
        f"<tr><td>{e(_name(r['key']))}</td><td class=num>{r['last7']}</td>"
        f"<td class=num>~{r['expected']:.1f} <span class=meta>({r['low']}–{r['high']})</span></td>"
        f"<td><span class=ptrack><b style=\"width:{r['p_any'] * 100:.0f}%\"></b></span>{r['p_any'] * 100:.0f}%</td>"
        f"<td>{_arrow(r)}</td></tr>" for r in rows)
    return (f"<table><tr><th>{label}</th><th class=num>Last 7 days</th><th class=num>Expected next 7 (range)</th>"
            f"<th>Chance of at least one</th><th>Trend</th></tr>{body}</table>")


def _bars(rows, value, label=lambda r: r["key"], fmt=lambda v: f"{v:.0f}") -> str:
    if not rows:
        return ""
    top = max(value(r) for r in rows) or 1
    return '<div class="bars">' + "".join(
        f'<div><em>{e(_name(label(r)))}</em><s><b style="width:{value(r) / top * 100:.0f}%"></b></s>'
        f'<code>{fmt(value(r))}</code></div>' for r in rows) + "</div>"


def _pred_card(p) -> str:
    arrow = {"up": ' <span class="up">▲ rising</span>', "down": ' <span class="down">▼ easing</span>'}.get(p["direction"], "")
    chance = (f'<div class="chance"><s><b style="width:{p["chance"] * 100:.0f}%"></b></s>'
              f'At least one: {e(p["chance_text"])}{arrow}</div>') if p["show_chance"] else ""
    ev = "".join(
        f'<a href="{e(x["link"])}" target="_blank" rel="noopener">{news(e(x["title"][:120]))} '
        f'<span>({e(x["place"])}, {news(e(x["source"]))}, {x["when"]})</span>'
        + (f' <em>{L("also", "ఇవి కూడా:")} {news(e(", ".join(x["also"][:3])))}</em>' if x["also"] else "") + "</a>" for x in p["evidence"])
    none = L("Not stated in reports", "నివేదికల్లో పేర్కొనలేదు")
    rows = [("Crime type", p.get("category_label", p["category"])),
            ("Where", p["where_short"]),
            ("Expected", L(f"About {p['expected']:.0f} in the next 7 days (likely {p['low']}–{p['high']}); {p['n7']} in the last 7 days",
                           f"వచ్చే 7 రోజుల్లో సుమారు {p['expected']:.0f} (పరిధి {p['low']}–{p['high']}); గత 7 రోజుల్లో {p['n7']}")),
            ("Who", p.get("victims_label") or (", ".join(p["victims"]).capitalize() if p["victims"] else none)),
            ("Method", p.get("methods_label") or (", ".join(p["methods"]).capitalize() if p["methods"] else none))]
    if p["losses_n"]:
        rows.append(("Money lost", p.get("losses_label") or f"{fmt_rupees(p['losses_total'])} across {p['losses_n']} case{'s' if p['losses_n'] != 1 else ''}"))
    rows.append(("Evidence", f"{p.get('evidence_grade_label', p['evidence_grade'])}: {p['evidence_text']}"))
    glance = "".join(f"<dt>{k}</dt><dd>{e(v)}</dd>" for k, v in rows)
    n_ev = len(p["evidence"])
    ev_sum = L(f'All {n_ev} incident{"s" if n_ev != 1 else ""} this is based on', f"ఈ అంచనాకు ఆధారమైన {n_ev} ఘటనలు")
    return f"""<article class="pred">
<div class="pred-top"><div><h4>{e(p["headline"])}</h4>
<span class="grade g-{p["evidence_grade"]}">Evidence: {p["evidence_grade"]}</span>{arrow}</div>
<div class="count">~{p["expected"]:.0f}<small>expected next 7 days</small></div></div>
<p class="insight">{e(p["insight"])}</p>
<dl class="glance">{glance}</dl>
{chance}
{f'<p class="focus"><b>Suggested focus:</b> {e(p["focus"])}.</p>' if p["focus"] else ''}
<details class="whyd"><summary>Why this is predicted</summary><ul>{"".join(f"<li>{e(w)}</li>" for w in p["why"])}</ul></details>
{f'<details class="ev"><summary>{ev_sum}</summary>{ev}</details>' if ev else ''}
</article>"""


def _sources_list() -> str:
    out = []
    for name, url in config.FEEDS.items():
        if "news.google.com" in url:
            q = parse_qs(urlparse(url).query).get("q", [""])[0]
            out.append(f"Google News search: “{e(q)}”")
        elif "thehindu" in url:
            sec = url.split("/news/")[1].split("/feeder")[0].split("/")[-1].replace("-", " ").title()
            out.append(f"The Hindu, {e(sec)} section")
        else:
            out.append(e(name))
    return "".join(f"<li>{x}</li>" for x in out)


def _record_html(r, conf) -> str:
    if not r or r["n"] == 0:
        fc = r["first_check"] if r else None
        when = f"{fc.day} {fc:%b}" if fc else "one week after the first prediction"
        return (f'<div class="record"><b>Track record: starts {when}.</b>'
                f'<p>Every day, every prediction (not only the ones shown here) is saved before the week happens. '
                f'From {when}, each one is checked against the incidents actually reported, and the hit rate appears here, good or bad.</p></div>')
    pct = r["hits"] / r["n"] * 100
    grades = ", ".join(f'{g}: {v["hits"]} of {v["n"]}' for g, v in r["by_grade"].items())
    rows = "".join(
        f'<tr><td>{x["made_on"]}</td><td>{e(x["category"])} in {e(x["district"])}</td><td>{x["evidence"]}</td>'
        f'<td class=num>~{x["expected"]:.0f} ({x["low"]}–{x["high"]})</td><td class=num>{x["actual"]}</td>'
        f'<td class="{"hit" if x["hit"] else "miss"}">{"Inside range" if x["hit"] else "Outside range"}</td></tr>'
        for x in r["recent"])
    return (f'<div class="record"><b class="big">{r["hits"]} of {r["n"]}</b> past predictions ({pct:.0f}%) landed inside their stated range.'
            f'<p>By evidence grade: {e(grades)}. A well-calibrated range should be right about 80% of the time.</p>'
            f'<details class="dt"><summary>Show the latest checked predictions</summary><table><tr><th>Made on</th><th>Prediction</th>'
            f'<th>Evidence</th><th class=num>Predicted</th><th class=num>Actual</th><th>Result</th></tr>{rows}</table></details></div>')


def _item_card(lead: NewsItem, dupes: list[NewsItem]) -> str:
    color = SEV_COLOR[lead.severity]
    tags = "".join(f'<span class="tag">{e(c)}</span>' for c in lead.categories)
    where = ", ".join(lead.areas + lead.districts) or lead.state
    summary = lead.llm_summary or lead.summary[:260]
    also = ""
    if dupes:
        srcs = sorted({d.source for d in dupes if d.source != lead.source})
        if srcs:
            also = f'<div class="also">Also reported by {news(e(", ".join(srcs[:6])))}</div>'
    search = " ".join([lead.title, summary, where] + lead.categories).lower()
    return f"""<article class="item" style="border-left-color:{color}"
 data-ts="{int(lead.published.timestamp())}" data-sev="{lead.severity}"
 data-state="{e(lead.state)}" data-districts="{e('|'.join(lead.districts))}"
 data-areas="{e('|'.join(lead.areas))}" data-cats="{e('|'.join(lead.categories))}" data-q="{news(e(search))}">
<h4><a href="{e(lead.link)}" target="_blank" rel="noopener">{news(e(lead.title))}</a></h4>
<div class="meta"><span class="sev" style="color:{color}">{SEV_LABEL[lead.severity]}</span><span>{e(where)}</span>
<span>{news(e(lead.source))}</span><span>{local(lead.published):%d %b, %H:%M} IST</span></div>
<div>{tags}</div>
{f'<p class="summary">{news(e(summary))}</p>' if summary else ''}{also}
</article>"""


def _dialog(key, ic, title, sub, body) -> str:
    return f"""<dialog id="d-{key}" aria-labelledby="h-{key}">
<div class="dlg-hd">{icon(ic, 26)}<div><h2 id="h-{key}">{title}</h2><p>{sub}</p></div>
<button class="x" data-close aria-label="Close">{icon("close", 20)}</button></div>
<div class="dlg-bd">{body}</div></dialog>"""


def _tile(key, ic, title, body, cls="", more="") -> str:
    return (f'<div class="tile {cls}" role="button" tabindex="0" data-open="{key}" aria-haspopup="dialog" aria-label="{e(title)}: {e(more or 'open')}">'
            f'<div class="hd">{icon(ic)}<h2>{title}</h2>{f'<span class="more">{more}</span>' if more else ''}</div>{body}</div>')


_JS = r"""
const CFG = __CFG__;
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
let cards = $$('#list .item');
const F = {win: $('#f-win'), state: $('#f-state'), district: $('#f-district'), area: $('#f-area'),
           cat: $('#f-cat'), sev: $('#f-sev'), q: $('#f-q')};
let openTile = '';

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
fill(F.area, 'areas', 'All localities'); fill(F.cat, 'cats', 'All categories');

function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  for (const [k, el] of Object.entries(F)) if (p.has(k)) el.value = p.get(k);
  return p.get('tile') || '';
}
function writeHash() {
  const p = new URLSearchParams();
  if (openTile) p.set('tile', openTile);
  if (openTile === 'incidents')
    for (const [k, el] of Object.entries(F)) if (el.value && !(k === 'sev' && el.value === '0') && !(k === 'win' && el.value === String(CFG.defaultWin))) p.set(k, el.value);
  history.replaceState(null, '', p.toString() ? '#' + p : location.pathname + location.search);
}
function apply() {
  const now = Date.now() / 1000, win = +F.win.value * 3600, q = F.q.value.trim().toLowerCase();
  let shown = 0;
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
    if (ok) shown++;
  });
  $('#shown').textContent = `${shown} of ${cards.length} incidents`;
  $('#empty').classList.toggle('hidden', shown > 0);
  $('#chip-vizag').classList.toggle('on', F.district.value === CFG.core);
  $('#chip-all').classList.toggle('on', !F.district.value && !F.area.value && !F.state.value && !F.cat.value && !q && F.sev.value === '0');
  writeHash();
}
Object.values(F).forEach(el => el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', apply));
F.area.addEventListener('change', () => { if (F.area.value) F.district.value = CFG.core; apply(); });
$('#chip-vizag').onclick = () => { F.district.value = F.district.value === CFG.core ? '' : CFG.core; if (!F.district.value) F.area.value = ''; apply(); };
$('#chip-all').onclick = () => { ['state', 'district', 'area', 'cat', 'q'].forEach(k => F[k].value = ''); F.sev.value = '0'; apply(); };

// ---- tiles & pop-ups ------------------------------------------------------
let opener = null;
function openDialog(key, preset) {
  const d = $('#d-' + key); if (!d) return;
  if (preset) {
    ['state', 'district', 'area', 'cat', 'q'].forEach(k => F[k].value = ''); F.sev.value = '0'; F.win.value = String(CFG.defaultWin);
    Object.entries(preset).forEach(([k, v]) => F[k].value = v);
    apply();
  }
  $$('dialog[open]').forEach(x => x.close());
  openTile = key; d.showModal(); d.querySelector('.dlg-bd').scrollTop = 0;
  document.body.style.overflow = 'hidden'; writeHash();
}
$$('[data-open]').forEach(t => {
  const go = () => { opener = t; openDialog(t.dataset.open, t.dataset.preset ? JSON.parse(t.dataset.preset) : (t.dataset.open === 'incidents' ? {} : null)); };
  t.addEventListener('click', go);
  t.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); go(); } });
});
$$('dialog').forEach(d => {
  d.addEventListener('close', () => { document.body.style.overflow = ''; openTile = ''; writeHash(); if (opener) opener.focus(); });
  d.addEventListener('click', ev => { if (ev.target === d) d.close(); });   // click outside the box
  d.querySelector('[data-close]').addEventListener('click', () => d.close());
});
const start = readHash(); apply();
if (start) openDialog(start, null);
// language toggle: keep the open pop-up and filters, remember the choice
$$('.lang a').forEach(a => a.addEventListener('click', () => {
  try { localStorage.setItem('lang', a.dataset.lang); } catch (e) {}
  a.href = a.getAttribute('href') + location.hash;
}));
try {
  const want = localStorage.getItem('lang');
  if (want && want !== document.documentElement.lang) {
    const a = document.querySelector('.lang a[data-lang="' + want + '"]');
    if (a) location.replace(a.getAttribute('href') + location.hash);
  }
} catch (e) {}
addEventListener('hashchange', () => { const t = readHash(); apply(); if (t && t !== openTile) openDialog(t, null); });

"""


_RELOAD_JS = r"""
// reload quietly when the hourly job publishes a newer brief (never while a pop-up is open)
setInterval(async () => {
  if (document.querySelector('dialog[open]')) return;
  try {
    const r = await fetch('status.json?t=' + Date.now(), {cache: 'no-store'});
    if (((await r.json()).generated_at || 0) > CFG.generatedAt) location.reload();
  } catch (e) {}
}, 300000);
"""


def render(*, items: list[NewsItem], clusters: dict[str, list[NewsItem]], trends, hotspots,
           emerging, now: datetime, hours: int, demo: bool, outlook=None, record=None,
           city_key: str = config.DEFAULT_CITY, lang: str = "en") -> str:
    global _LANG
    _LANG = lang
    try:
        return i18n.translate_page(_render(**locals_for_render(locals())), lang)
    finally:
        _LANG = "en"


def locals_for_render(ns):
    return {k: ns[k] for k in ("items", "clusters", "trends", "hotspots", "emerging", "now", "hours", "demo",
                               "outlook", "record", "city_key")}


_PWA_JS = r"""
// ---- app (PWA): offline support, install button, iPhone hint ----------------
if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
}
const off = $('#offline');
const netState = () => { off.hidden = navigator.onLine; };
addEventListener('online', netState); addEventListener('offline', netState); netState();

let deferred = null;
const inst = $('#install');
addEventListener('beforeinstallprompt', ev => { ev.preventDefault(); deferred = ev; inst.hidden = false; });
inst.addEventListener('click', async () => { if (!deferred) return; deferred.prompt(); await deferred.userChoice; deferred = null; inst.hidden = true; });
addEventListener('appinstalled', () => { inst.hidden = true; });

const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
const ios = /iphone|ipad|ipod/i.test(navigator.userAgent) && !/crios|fxios/i.test(navigator.userAgent);
let hintSeen = false; try { hintSeen = localStorage.getItem('ioshint') === '1'; } catch (e) {}
if (ios && !standalone && !hintSeen) $('#ioshint').hidden = false;
$('#ioshint-x').addEventListener('click', () => { $('#ioshint').hidden = true; try { localStorage.setItem('ioshint', '1'); } catch (e) {} });
if (standalone) document.documentElement.classList.add('app');
"""


def _render(*, items, clusters, trends, hotspots, emerging, now, hours, demo, outlook, record, city_key) -> str:
    city = config.CITIES[city_key]
    cname, core = city["name"], city["core"]
    around = [d for d in city["districts"] if d != core]
    region_text = (L(f"{city['full']} city and the surrounding {', '.join(around[:-1])} and {around[-1]} districts",
                     f"{city['full']} నగరం, పరిసర {', '.join(around)} జిల్లాలు")
                   if len(around) > 1 else city["full"])
    sfx = ".te.html" if _LANG == "te" else ".html"
    page_of = lambda k, lang: (("./" if lang == "en" else "te.html") if k == config.DEFAULT_CITY
                               else k + (".te.html" if lang == "te" else ".html"))
    city_nav = "".join(
        (f'<a class="city{" on" if k == city_key else ""}" href="{page_of(k, _LANG)}"'
         f'{" aria-current=\"page\"" if k == city_key else ""}>{e(c["name"])}</a>') if c["enabled"] else
        f'<span class="city soon" aria-disabled="true">{e(c["name"])} <small>coming soon</small></span>'
        for k, c in config.CITIES.items())
    week_start = now - timedelta(days=7)
    incidents = [cl for cl in clusters.values()
                 if cl[0].categories and cl[0].published >= week_start]
    incidents.sort(key=lambda cl: (-cl[0].severity, -len(cl), -cl[0].published.timestamp()))
    incidents = incidents[:500]
    day = [cl for cl in incidents if cl[0].published >= now - timedelta(hours=24)]
    vizag = [cl for cl in incidents if core in cl[0].districts]

    n_articles = sum(1 for i in items if i.published >= now - timedelta(hours=24))
    n_high = sum(1 for cl in day if cl[0].severity >= 4)
    total = outlook.project(outlook.total) if outlook else None

    # ---------------- pop-up bodies ----------------
    win_opts = "".join(f'<option value="{h}"{" selected" if h == hours else ""}>{lbl}</option>'
                       for h, lbl in ((6, "Last 6 hours"), (24, "Last 24 hours"),
                                      (72, "Last 3 days"), (168, "Last 7 days")))
    if hours not in (6, 24, 72, 168):
        win_opts += f'<option value="{hours}" selected>Last {hours} hours</option>'
    sev_opts = "".join(f'<option value="{v}">{lbl}</option>' for v, lbl in
                       ((0, "Any severity"), (3, "Elevated and above"), (4, "High and above"), (5, "Critical only")))
    incidents_body = f"""<div class="filters">
<div class="frow" style="margin-bottom:8px"><button class="chip" id="chip-all">All</button>
<button class="chip" id="chip-vizag">{e(core)} city only</button>
<select id="f-win" aria-label="Time window">{win_opts}</select>
<select id="f-sev" aria-label="Severity">{sev_opts}</select><span class="shown" id="shown"></span></div>
<div class="frow"><select id="f-state" aria-label="State" class="hidden"></select><select id="f-district" aria-label="District"></select>
<select id="f-area" aria-label="Locality"></select><select id="f-cat" aria-label="Category"></select>
<input id="f-q" type="search" placeholder="Search, e.g. ganja or digital arrest" aria-label="Search"></div></div>
<div id="list">{"".join(_item_card(cl[0], cl[1:]) for cl in incidents)}</div>
<p class="meta hidden" id="empty">No incidents match these filters. Try a longer time window.</p>"""

    trend_rows = "".join(
        f"<tr><td>{e(t['category'])}{'<span class=spike>Spike</span>' if t['spike'] else ''}</td>"
        f"<td class=num>{t['current']}</td><td class=num>{t['previous']}</td>"
        f"<td class='num {'up' if t['change'] > 0 else 'down' if t['change'] < 0 else ''}'>{_pct(t)}</td></tr>"
        for t in trends[:20]) or "<tr><td colspan=4>Not enough history yet.</td></tr>"
    weekly_body = (f"<table><tr><th>Category</th><th class=num>This week</th><th class=num>Last week</th>"
                   f"<th class=num>Change</th></tr>{trend_rows}</table>")

    hot_rows = "".join(
        f"<tr><td>{e(h['district'])}</td><td class=num>{h['total']}</td>"
        f"<td>{e(', '.join(f'{c} ({n})' for c, n in h['by_category']))}</td></tr>"
        for h in hotspots) or "<tr><td colspan=3>No district-tagged incidents yet.</td></tr>"
    districts_body = (f"<h3>Most incidents in the last 7 days</h3><table><tr><th>District / Commissionerate</th>"
                      f"<th class=num>Incidents</th><th>Top categories</th></tr>{hot_rows}</table>")

    scams_body = ("<p class='meta' style='margin-top:0'>Scam and crime techniques mentioned in the news this week. "
                  "<b>New</b> means not seen in the previous week.</p><div class='chips'>" + "".join(
        f'<span class="chip-s{" hot" if t["new"] else ""}">{e(_term(t["term"]))}: {t["count"]}{L(" (new)", " (కొత్తది)") if t["new"] else ""}</span>'
        for t in emerging) + "</div>") if emerging else "<p class='meta'>No known techniques mentioned this week.</p>"

    trends_body = watch_body = areas_body = ""
    if outlook:
        hist, fc = outlook.daily_total(), outlook.forecast_days()
        conf_text = {"Low": "Only a few days of monitoring so far, so treat the outlook as a rough guide.",
                     "Medium": "A couple of weeks of history. Rates are usable; trends are still settling.",
                     "High": "Three or more weeks of history."}[outlook.conf]
        data_rows = "".join(f"<tr><td>{d:%a %d %b}</td><td class=num>{c}</td><td>{'incomplete' if p else ''}</td></tr>"
                            for d, c, p in hist) + "".join(
            f"<tr><td>{d:%a %d %b}</td><td class=num>~{ex:.1f} ({lo}–{hi})</td><td>outlook</td></tr>" for d, ex, lo, hi in fc)
        recent = [h for h in hist if h[0] >= outlook.today - timedelta(days=13)]
        small = "".join(
            f'<div class="viz"><h3>{e(r["key"])}</h3><div class="num">{r["last7"]} in last 7 days, '
            f'~{r["expected"]:.1f} expected next 7 · {_arrow(r)}</div>'
            + charts.daily_chart([(d, outlook.by_cat[r["key"]].get(d, 0), p) for d, _, p in recent],
                                 outlook.forecast_days(outlook.by_cat[r["key"]]), width=240, height=90, compact=True)
            + "</div>" for r in outlook.category_rows(top=8))
        trends_body = f"""<p class="note" style="margin-top:0">Outlook confidence <span class="conf">{outlook.conf}</span>
{conf_text} {L(f"Based on {outlook.n_reliable} reliable day{'s' if outlook.n_reliable != 1 else ''}; Medium from 7, High from 21. The outlook estimates how many <b>news-reported</b> incidents to expect. It is a planning aid, not a prediction of specific crimes.",
 f"{outlook.n_reliable} విశ్వసనీయ రోజుల ఆధారంగా; 7 రోజుల తర్వాత మధ్యస్థం, 21 తర్వాత ఎక్కువ. ఈ అంచనా <b>వార్తల్లో నమోదయ్యే</b> ఘటనల సంఖ్యను మాత్రమే సూచిస్తుంది. ఇది ప్రణాళిక కోసం సహాయం మాత్రమే, నిర్దిష్ట నేరాల అంచనా కాదు.")}</p>
<div class="viz"><h3>Incidents per day in and around {e(cname)}</h3>
<p class="sub">Last 30 days and the next 7. Next week: about {total['expected']:.0f} incidents (likely {total['low']}–{total['high']}), {_arrow(total)}</p>
{charts.LEGEND}<div class="scroll">{charts.daily_chart(hist, fc)}</div>
<details class="dt"><summary>Show data table</summary><table><tr><th>Day</th><th class=num>Incidents</th><th>Note</th></tr>{data_rows}</table></details></div>
<h3>By category, last 14 days and next 7</h3><div class="sm">{small or '<p class="meta">Not enough data yet.</p>'}</div>"""
        allp = predictions(outlook, 8)
        insights = (i18n.te_city_insights(city_facts(outlook, allp, city)) if _LANG == "te"
                    else city_insights(outlook, allp, city))
        if _LANG == "te":
            allp = [i18n.te_prediction(p) for p in allp]
        watch_body = (f'<div class="brief"><h3>Key insights for {e(cname)}</h3><ul>'
                      + "".join(f"<li>{e(x)}</li>" for x in insights) + "</ul></div>"
                      + _record_html(record, outlook.conf)
                      + (f"""<details class="method"><summary>Method, sources and limits</summary>
<h5>ఏం అంచనా వేస్తున్నాం</h5><p>వచ్చే 7 రోజుల్లో ఒక జిల్లా నుంచి ఒక రకం నేరానికి సంబంధించి <b>వార్తల్లో ఎన్ని ఘటనలు నమోదవుతాయో</b>.
నిర్దిష్ట నేరాలు, వ్యక్తులు లేదా ప్రదేశాలు కాదు.</p>
<h5>మూలాలు</h5><ul>{_sources_list()}</ul>
<h5>పద్ధతి</h5><ol>
<li>ప్రతి గంటకు వార్తలు సేకరించి, స్థిరమైన కీవర్డ్ నియమాలతో (కోడ్‌లో ప్రచురించినవి) నేర రకం, ప్రదేశం గుర్తిస్తాం; ఒకే ఘటనపై వేర్వేరు సంస్థల వార్తలను ఒకటిగా కలుపుతాం.</li>
<li>ప్రతి నేర రకం, జిల్లాకు: ఇటీవలి రోజువారీ సగటు (కొత్త రోజులకు ఎక్కువ బరువు); చరిత్ర తక్కువగా ఉన్నప్పుడు జిల్లా దీర్ఘకాలిక వాటా వైపు సర్దుబాటు.</li>
<li>అంచనా = రోజువారీ సగటు x 7 (10+ రోజుల తర్వాత ధోరణితో గుణించి). పరిధి = ఆ అంచనాతో Poisson లెక్కలో 80% పరిధి.</li>
<li>ఆధారం: బలమైనది = 3+ వేర్వేరు సంస్థలు, 3+ వేర్వేరు రోజుల్లో 5+ ఘటనలు. మోస్తరు = 2+ సంస్థల నుంచి 3+ ఘటనలు. పరిమితం = అంతకంటే తక్కువ.</li>
<li>ప్రతి అంచనాను రోజూ సేవ్ చేసి, వారం తర్వాత ఫలితంతో పోలుస్తాం (పై ట్రాక్ రికార్డ్).</li>
<li>కనీసం ఒక ఘటన జరిగే అవకాశం శాతం 7 రోజుల పర్యవేక్షణ తర్వాత, ఆధారం మోస్తరు లేదా బలమైనది అయితేనే చూపిస్తాం.</li></ol>
<h5>పరిమితులు</h5><ul>
<li>పత్రికలు ప్రచురించినవే కనిపిస్తాయి. నివేదించని నేరాలు ఇక్కడ కనిపించవు.</li>
<li>పరిధి: {e(region_text)}. ప్రదేశం అంటే వార్తలో ఘటన జరిగినట్లు లేదా ప్రకటించినట్లు చెప్పిన చోటు.</li>
<li>పర్యవేక్షణ మొదలైంది {outlook.reliable_from + timedelta(days=2):%d %b %Y}; విశ్వసనీయత <b>{i18n.CONF_TE[outlook.conf]}</b> ({outlook.n_reliable} రోజులు). 7 రోజుల తర్వాత మధ్యస్థం, 21 తర్వాత ఎక్కువ.</li></ul>
<h5>ఎలా ధృవీకరించాలి</h5><p>ప్రతి కార్డులో దానికి ఆధారమైన ప్రతి ఘటన, అసలు వార్తల లింకులు, ఇతర సంస్థల వివరాలు ఉన్నాయి.</p>
</details>""" if _LANG == "te" else f"""<details class="method"><summary>Method, sources and limits</summary>
<h5>What is predicted</h5><p>How many incidents of a crime type will be <b>reported in the news</b> from a district in the next 7 days.
Not specific crimes, people or places.</p>
<h5>Sources</h5><ul>{_sources_list()}</ul>
<h5>Method</h5><ol>
<li>Stories are collected every hour, tagged by crime type and place with fixed keyword rules (published in the code), and duplicates of the same incident across outlets are merged.</li>
<li>For each crime type and district: the recent daily rate (newer days weigh more), pulled toward the district's long-run share while history is short.</li>
<li>Expected = daily rate x 7 (x trend once 10+ days exist). Range = the 80% band of a Poisson count with that expectation.</li>
<li>Evidence grade: {e(EVIDENCE_RULE)}</li>
<li>Every prediction is saved daily and scored a week later (track record above).</li>
<li>The chance of at least one incident is shown only once monitoring passes 7 days and the evidence is Moderate or Strong.</li></ol>
<h5>Limits</h5><ul>
<li>Only what the press reports. Unreported or under-reported crime is invisible here.</li>
<li>Covers {e(region_text)}. The place is where the story says it happened or was announced.</li>
<li>Monitoring started {outlook.reliable_from + timedelta(days=2):%d %b %Y}; confidence is <b>{outlook.conf}</b> ({outlook.n_reliable} days). Medium from 7 days, High from 21.</li></ul>
<h5>How to verify</h5><p>Each card lists every incident it is based on, with links to the original reports and other outlets that covered it.</p>
</details>""")
                      + f"<h3>Predictions for the next 7 days</h3>"
                      + "<p class='meta' style='margin-top:-4px'>Strongest evidence first. Limited means fewer than 3 incidents "
                        "or a single outlet: worth watching, not acting on alone.</p>"
                      + (f'<div class="preds">{"".join(_pred_card(p) for p in allp)}</div>' if allp
                         else f"<p class='meta'>No incidents in the last 30 days in and around {e(cname)} to base a prediction on.</p>")
                      + "<h3>All combinations at a glance</h3>"
                      + _outlook_table(outlook.watchlist(top=15), "Category in district", "Not enough district-level history yet.")
                      + "<h3>District outlook</h3>"
                      + _outlook_table(outlook.district_rows(top=15), "District / Commissionerate", "Not enough history yet."))
        areas_body = _outlook_table(outlook.area_rows(top=20), f"{cname} locality",
                                    f"No locality-level incidents in the last 30 days yet. Localities are picked up when a story names them, e.g. Gajuwaka or MVP Colony.")

    # ---------------- tiles ----------------
    if outlook:
        mini_hist = [h for h in outlook.daily_total() if h[0] >= outlook.today - timedelta(days=20)]
        t_trends = _tile("trends", "pulse", "Trends and outlook", f"""
<div class="lead">~{total['expected']:.0f}<small>incidents expected next 7 days (likely {total['low']}–{total['high']})</small></div>
<p>{_arrow(total)} &nbsp;<span class="pill">Confidence: {outlook.conf}</span></p>
<div class="chartwrap">{charts.daily_chart(mini_hist, outlook.forecast_days(), width=560, height=330)}</div>
<div class="catstrip">{"".join(f'<div><b>~{r["expected"]:.0f}</b>{e(r["key"])} next week</div>' for r in outlook.category_rows(top=3))}</div>""",
                         "t-trends", "Open charts")
        tp = predictions(outlook, 3)
        if _LANG == "te":
            tp = [i18n.te_prediction(p) for p in tp]
        t_watch = _tile("watch", "target", "Predictions",
                        ('<ul class="heads">' + "".join(
                            f'<li><i style="background:#2a78d6"></i><div><b>~{p["expected"]:.0f} {e(p.get("category_label") or p["category"].lower())}</b>'
                            f'<span>{e(p["where_short"])} · evidence {p["evidence_grade"].lower()}</span></div></li>'
                            for p in tp) + "</ul><p>Next 7 days. Open for insights: type, where, who, why.</p>")
                        if tp else '<p class="empty-t">Builds up as incidents come in.</p>')
        ar = outlook.area_rows(top=4)
        t_areas = _tile("areas", "grid", f"{cname} localities",
                        _bars(ar, lambda r: r["last7"] or r["expected"], fmt=lambda v: f"{v:.0f}") + "<p>Incidents in the last 7 days</p>"
                        if ar else '<p class="empty-t">No locality-level incidents yet this month.</p>')
    else:
        t_trends = t_watch = t_areas = ""

    heads = "".join(
        f'<li><i style="background:{SEV_COLOR[cl[0].severity]}"></i><div>{news(e(cl[0].title[:110]))}'
        f'<span>{e(", ".join(cl[0].areas + cl[0].districts) or cl[0].state)}, {local(cl[0].published):%H:%M}</span></div></li>'
        for cl in day[:5])
    t_inc = _tile("incidents", "list", "Live incidents",
                  f'<div class="lead">{len(day)}<small>in the last 24 hours</small></div>'
                  + (f'<ul class="heads">{heads}</ul>' if heads else '<p class="empty-t">No incidents in the last 24 hours.</p>'),
                  "t-incidents", "See all")

    vz_areas = {}
    for cl in vizag:
        for a in cl[0].areas:
            vz_areas[a] = vz_areas.get(a, 0) + 1
    vz_top = ", ".join(a for a, _ in sorted(vz_areas.items(), key=lambda kv: -kv[1])[:3])
    vz_latest = max(vizag, key=lambda cl: cl[0].published)[0].title[:90] if vizag else ""
    t_vizag = (f'<div class="tile" role="button" tabindex="0" aria-label="{e(core)} city: open" data-open="incidents" data-preset=\'{{"district":"{e(core)}","win":"168"}}\' aria-haspopup="dialog">'
               f'<div class="hd">{icon("pin")}<h2>{e(core)} city</h2></div>'
               f'<div class="lead">{len(vizag)}<small>incidents in 7 days</small></div>'
               + (f"<p>Latest: {news(e(vz_latest))}</p>" if vz_latest else f"<p>No incidents in {e(core)} city this week.</p>")
               + (f"<p>Areas: {e(vz_top)}</p>" if vz_top else "") + "</div>")

    t_dist = _tile("districts", "eye", f"In and around {cname}",
                   _bars(hotspots[:4], lambda h: h["total"], label=lambda h: h["district"]) + "<p>Incidents in the last 7 days</p>"
                   if hotspots else '<p class="empty-t">No incidents in the last 7 days.</p>')
    ups = sum(1 for t in trends if t.get("spike"))
    building = trends and trends[0].get("baseline") is False
    t_week = _tile("weekly", "swap", "Weekly changes",
                   ('<div class="lead">Building<small>baseline</small></div><p>Week-on-week changes and spike alerts start after 14 days of monitoring.</p>'
                    if building else f'<div class="lead">{ups}<small>spike{"s" if ups != 1 else ""} this week</small></div>'
                    '<p>This week against last week, by category and state</p>'))
    t_scams = _tile("scams", "hook", "Scam techniques",
                    ('<div class="chips">' + "".join(f'<span class="chip-s{" hot" if t["new"] else ""}">{e(_term(t["term"]))}</span>'
                                                     for t in emerging[:7]) + "</div><p>Mentioned in this week's news</p>")
                    if emerging else '<p class="empty-t">None mentioned this week.</p>')

    dialogs = "".join([
        _dialog("incidents", "list", "Incidents", "Deduplicated, highest severity first. Filters are saved in the page link.", incidents_body),
        _dialog("trends", "pulse", "Trends and 7-day outlook", "Incidents per day and what to expect next week", trends_body) if outlook else "",
        _dialog("watch", "target", "Predictions", "What is likely next week, why, and where", watch_body) if outlook else "",
        _dialog("areas", "grid", f"{cname} localities", "Locality-level incidents and next-week outlook", areas_body) if outlook else "",
        _dialog("districts", "eye", f"In and around {cname}", "Incidents by district, last 7 days", districts_body),
        _dialog("weekly", "swap", "Weekly changes", "This week against last week", weekly_body),
        _dialog("scams", "hook", "Scam techniques", "Modus operandi in this week's news", scams_body),
    ])

    banner = ('<div class="banner"><b>Demo mode.</b> The headlines below are made-up sample data, not real incidents.</div>'
              if demo else "")
    cfg = json.dumps({
        "actionsUrl": f"https://github.com/{REPO}/actions/workflows/hourly.yml",
        "generatedAt": int(now.timestamp()),
        "defaultWin": hours, "core": core,
    })
    spike_n = sum(1 for t in trends if t["spike"])

    return f"""<!DOCTYPE html><html lang="{_LANG}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#13233f">
<link rel="manifest" href="{'manifest.te.webmanifest' if _LANG == 'te' else 'manifest.webmanifest'}">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="{L(cname + ' Crime Board', 'విశాఖ నేర బోర్డు')}">
<title>{e(cname)} crime and threat board, {local(now):%d %b %Y}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@500;600&family=Noto+Sans+Telugu:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<header class="board"><div class="board-in">
<div class="top"><div class="emblem">{icon("eye", 24)}</div>
<div class="title"><h1>{e(cname)} crime and threat board</h1><p>{L(f"Incidents reported in {e(region_text)}, from public news. Updated {local(now):%d %b %Y, %H:%M} IST, every hour.",
 f"{e(region_text)}లో నమోదైన ఘటనలు, బహిరంగ వార్తల ఆధారంగా. చివరి అప్‌డేట్ {local(now):%d %b %Y, %H:%M} IST; ప్రతి గంటకు.")}</p></div>
<div class="actions"><button class="install" id="install" hidden>{icon("download", 18)}<span>Install app</span></button>
<nav class="lang" aria-label="Language"><a href="{page_of(city_key, 'en')}" data-lang="en"{' class="on" aria-current="true"' if _LANG == "en" else ''}>English</a><a href="{page_of(city_key, 'te')}" data-lang="te"{' class="on" aria-current="true"' if _LANG == "te" else ''}>తెలుగు</a></nav></div>
</div>
<nav class="cities" aria-label="City">{city_nav}</nav>
<div class="counters">
<div class="counter"><b>{n_articles}</b><span>news reports today</span></div>
<div class="counter"><b>{len(day)}</b><span>incidents in 24 hours</span></div>
<div class="counter{' alert' if n_high else ''}"><b>{n_high}</b><span>high or critical</span></div>
<div class="counter"><b>{len(incidents)}</b><span>incidents this week</span></div>
</div></div></header>
{banner}
<div class="offline" id="offline" hidden>{icon("offline", 18)}<span>You are offline. Showing data saved at {local(now):%d %b, %H:%M} IST.</span></div>
<main><div class="tiles">
{t_trends}{t_inc}{t_vizag}{t_watch}{t_dist}{t_areas}{t_week}{t_scams}
</div></main>
{dialogs}
<footer>Compiled automatically from public news. Unverified: corroborate before acting. Severity is a keyword-based estimate. News headlines are shown as published.
{f'{spike_n} category spike{"s" if spike_n != 1 else ""} this week. ' if spike_n else ''}Data: <a href="incidents.json">incidents.json</a>, <a href="outlook.json">outlook.json</a></footer>
<div class="ioshint" id="ioshint" hidden>{icon("share", 20)}<span>Install this app: tap Share, then Add to Home Screen.</span>
<button class="x2" id="ioshint-x" aria-label="Close">{icon("close", 16)}</button></div>
<script>{_JS.replace("__CFG__", cfg)}{_RELOAD_JS}{_PWA_JS}</script>
<script>{charts.TIP_JS}</script>
</body></html>"""
