"""Inline SVG charts (no JS libraries) for the trends & outlook section."""
from __future__ import annotations

import html
import math

# Reference palette (validated: blue/orange pass CVD + contrast on #fcfcfb)
ACTUAL = "#2a78d6"
FORECAST = "#eb6834"
PARTIAL = "#c3c2b7"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASE, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"

CSS = """
.viz{background:#fcfcfb;border:1px solid rgba(11,11,11,.10);border-radius:8px;padding:14px 16px 10px;margin-bottom:14px}
.viz h3{margin:0;font-size:15px;color:#0b0b0b}.viz .sub{margin:2px 0 8px;font-size:12.5px;color:#52514e}
.viz svg{display:block;width:100%;height:auto;overflow:visible}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12.5px;color:#52514e;margin:4px 0 2px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-2px}
.sm{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.sm .viz{margin:0;padding:10px 12px 6px}.sm h3{font-size:13.5px}
.sm .num{font-size:12px;color:#52514e;margin:2px 0 4px}
.up{color:#b3261e;font-weight:600}.down{color:#006300;font-weight:600}.flat{color:#52514e}
.ptrack{display:inline-block;width:90px;height:8px;background:#e1e0d9;border-radius:4px;vertical-align:middle;margin-right:6px;overflow:hidden}
.ptrack b{display:block;height:100%;background:#2a78d6;border-radius:4px}
.conf{display:inline-block;font-size:12px;border-radius:4px;padding:1px 8px;background:#eef1f5;color:#52514e}
.note{font-size:12.5px;color:#52514e;margin:6px 0 14px}
details.dt{margin-top:6px;font-size:13px}details.dt summary{cursor:pointer;color:#52514e}
details.dt table{margin-top:6px}
#viztip{position:fixed;pointer-events:none;z-index:50;background:#0b0b0b;color:#fff;font-size:12.5px;
 padding:6px 9px;border-radius:6px;white-space:pre;opacity:0;transition:opacity .08s;box-shadow:0 2px 8px rgba(0,0,0,.2)}
.hit{fill:transparent;cursor:default}.hit:hover+.bar,.bar:hover{filter:brightness(.88)}
.scroll{overflow-x:auto}
@media(max-width:700px){.sm{grid-template-columns:repeat(2,1fr)}.scroll svg{min-width:700px}}
"""

TIP_JS = """
(function(){const t=document.createElement('div');t.id='viztip';document.body.appendChild(t);
document.addEventListener('mousemove',e=>{const el=e.target.closest('[data-tip]');
if(!el){t.style.opacity=0;return}
const host=el.closest('dialog')||document.body;if(t.parentNode!==host)host.appendChild(t);
t.textContent=el.dataset.tip;t.style.opacity=1;
const x=Math.min(e.clientX+14,innerWidth-t.offsetWidth-8);t.style.left=x+'px';t.style.top=(e.clientY+14)+'px';});})();
"""

TEXTURE = f"""<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
<rect width="6" height="6" fill="{FORECAST}" fill-opacity=".28"/><line x1="0" y1="0" x2="0" y2="6" stroke="{FORECAST}" stroke-width="2.2"/></pattern></defs>"""


def e(s) -> str:
    return html.escape(str(s), quote=True)


def _bar(x, y, w, h, fill, tip):
    """Bar anchored to the baseline with 4px rounded top corners."""
    if h <= 0:
        return ""
    r = min(4, w / 2, h)
    d = (f"M{x:.1f},{y + h:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}"
         f"H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{y + h:.1f}Z")
    return f'<path class="bar" d="{d}" fill="{fill}" data-tip="{e(tip)}"/>'


def _nice_max(v: float) -> float:
    if v <= 4:
        return 4
    mag = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * mag:
            return m * mag
    return 10 * mag


def daily_chart(history, forecast, *, width=1036, height=240, tz_label="IST", compact=False):
    """history: [(date, count, partial)], forecast: [(date, expected, lo, hi)]."""
    pad_l, pad_r, pad_t, pad_b = (26, 6, 8, 20) if compact else (36, 10, 14, 34)
    n = len(history) + len(forecast)
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    slot = plot_w / n
    gap = 2
    bw = max(1.5, slot - gap)
    ymax = _nice_max(max([c for _, c, _ in history] + [hi for *_, hi in forecast] + [1]))
    y = lambda v: pad_t + plot_h - v / ymax * plot_h
    out = [f'<svg viewBox="0 0 {width} {height}" role="img">', TEXTURE]

    ticks = 2 if compact else 4
    for i in range(ticks + 1):
        v = ymax * i / ticks
        yy = y(v)
        out.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}" '
                   f'stroke="{BASE if i == 0 else GRID}" stroke-width="1"/>')
        lab = f"{v:.0f}" if v == int(v) else f"{v:.1f}"
        out.append(f'<text x="{pad_l - 6}" y="{yy + 4:.1f}" text-anchor="end" font-size="{10 if compact else 11}" fill="{MUTED}">{lab}</text>')

    # partial-history band
    n_partial = sum(1 for *_, p in history if p)
    if n_partial and not compact:
        bx = pad_l + n_partial * slot
        out.append(f'<rect x="{pad_l}" y="{pad_t}" width="{bx - pad_l:.1f}" height="{plot_h}" fill="#f1f0ec"/>')
        out.append(f'<text x="{pad_l + 6}" y="{pad_t + 13}" font-size="11" fill="{INK2}">Before monitoring: incomplete</text>')
    # forecast band label
    fx = pad_l + len(history) * slot
    if not compact:
        out.append(f'<line x1="{fx - gap / 2:.1f}" x2="{fx - gap / 2:.1f}" y1="{pad_t}" y2="{pad_t + plot_h}" stroke="{BASE}"/>')
        out.append(f'<text x="{fx + 4:.1f}" y="{pad_t + 13}" font-size="11" fill="{INK2}">Next 7 days (outlook)</text>')

    for i, (d, c, partial) in enumerate(history):
        x = pad_l + i * slot + gap / 2
        tip = f"{d:%a %d %b}\n{c} incident{'s' if c != 1 else ''}" + ("\n(before monitoring began: incomplete)" if partial else "")
        out.append(_bar(x, y(c), bw, pad_t + plot_h - y(c), PARTIAL if partial else ACTUAL, tip))
        out.append(f'<rect class="hit" x="{x:.1f}" y="{pad_t}" width="{bw:.1f}" height="{plot_h}" data-tip="{e(tip)}"/>')
    for j, (d, ex, lo, hi) in enumerate(forecast):
        i = len(history) + j
        x = pad_l + i * slot + gap / 2
        tip = f"{d:%a %d %b} (outlook)\nexpected ~{ex:.1f}\nlikely range {lo}–{hi}"
        out.append(_bar(x, y(ex), bw, pad_t + plot_h - y(ex), "url(#hatch)", tip))
        cx = x + bw / 2
        out.append(f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(hi):.1f}" y2="{y(lo):.1f}" stroke="{FORECAST}" stroke-width="2"/>')
        out.append(f'<rect class="hit" x="{x:.1f}" y="{pad_t}" width="{bw:.1f}" height="{plot_h}" data-tip="{e(tip)}"/>')

    # x labels: weekly from the start, plus Today and the last outlook day, never colliding
    all_days = [d for d, *_ in history] + [d for d, *_ in forecast]
    today_i, last_i = len(history) - 1, n - 1
    if compact:
        marks = [0, today_i]
    else:
        keep = {today_i, last_i}
        marks = sorted(keep | {i for i in range(0, n, 7)
                               if all(abs(i - k) * slot >= 46 for k in keep)})
    for i in marks:
        lab = "Today" if i == today_i else f"{all_days[i]:%d %b}"
        anchor = "end" if i == last_i else "start" if i == 0 else "middle"
        xpos = pad_l + (i + (1 if i == last_i else 0 if i == 0 else .5)) * slot
        out.append(f'<text x="{xpos:.1f}" y="{height - (6 if compact else 12)}" text-anchor="{anchor}" '
                   f'font-size="{10 if compact else 11}" fill="{MUTED}">{lab}</text>')
    out.append("</svg>")
    return "".join(out)


LEGEND = (f'<div class="legend"><span><i style="background:{ACTUAL}"></i>Incidents per day</span>'
          f'<span><i style="background:{PARTIAL}"></i>Before monitoring (incomplete)</span>'
          f'<span><i style="background:{FORECAST};background:repeating-linear-gradient(45deg,{FORECAST} 0 2px,#fbd9cb 2px 5px)"></i>'
          f'Outlook (expected, with likely range)</span></div>')
