"""Weekly scorecard: did last week's predictions come true?

The week runs Wednesday to Tuesday. Predictions saved on a Tuesday cover the
next seven days and are scored the following Wednesday, once the week is over.

    python -m osint_monitor.weekly            # print the latest scorecard (markdown)
    python -m osint_monitor.weekly --json     # same, as JSON
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from . import analysis, config
from .classifier import classify
from .explain import fmt_rupees, predictions
from .forecast import Outlook
from .store import Store

CYCLE_WEEKDAY = 1      # predictions made on Tuesday are the weekly ones


def _latest_cycle(store: Store, today: date):
    """Most recent Tuesday whose 7-day window has fully ended, and the first one ever."""
    days = [date.fromisoformat(r[0]) for r in store.conn.execute(
        "SELECT DISTINCT made_on FROM predictions_log ORDER BY made_on")]
    weekly = [d for d in days if d.weekday() == CYCLE_WEEKDAY]
    due = [d for d in weekly if d + timedelta(days=7) < today]
    first_due = (weekly[0] + timedelta(days=8)) if weekly else None
    return (due[-1] if due else None), first_due, due


def _score_rows(store, made_on: date, o_all: Outlook, o_city: Outlook, city_key: str, cdists: set):
    rows = store.conn.execute(
        "SELECT category, district, expected, low, high, evidence, window_start, window_end "
        "FROM predictions_log WHERE made_on = ?", (made_on.isoformat(),)).fetchall()
    out = []
    for cat, dist, exp, low, high, grade, ws, we in rows:
        ws, we = date.fromisoformat(ws), date.fromisoformat(we)
        if cat == "*":
            if dist == f"city:{city_key}":
                series, name, scope = o_city.total, "All incidents", "city"
            elif dist == "*":
                series, name, scope = o_all.total, "All incidents, AP and Telangana", "state"
            else:
                continue
        else:
            series = o_all.by_cat_district.get((cat, dist), {})
            name, scope = f"{cat} in {dist}", "city" if dist in cdists else "state"
        span = (we - ws).days + 1
        actual = sum(series.get(ws + timedelta(days=i), 0) for i in range(span))
        naive = sum(series.get(ws - timedelta(days=7) + timedelta(days=i), 0) for i in range(span))  # "same as last week"
        verdict = "inside" if low <= actual <= high else ("above" if actual > high else "below")
        out.append({"name": name, "category": cat, "district": dist, "scope": scope, "evidence": grade or "",
                    "expected": exp, "low": low, "high": high, "actual": actual, "verdict": verdict, "naive": naive,
                    "trivial": verdict == "inside" and low == 0 and actual == 0,
                    "window": [ws.isoformat(), we.isoformat()]})
    return out


def build(db_path: str, city_key: str = config.DEFAULT_CITY, now: datetime | None = None) -> dict:
    from .report import _TZ as tz
    now = now or datetime.now(timezone.utc)
    store = Store(db_path)
    today = now.astimezone(tz).date()
    city = config.CITIES[city_key]
    cdists = set(city["districts"])
    made_on, first_due, all_due = _latest_cycle(store, today)
    rep = {"city": city["name"], "generated": now.isoformat(), "made_on": made_on.isoformat() if made_on else None,
           "first_scorecard": first_due.isoformat() if first_due else None}

    items = store.since(now - timedelta(days=30))
    for it in items:
        classify(it)
    clusters = analysis.cluster(items)
    started = (store.tracking_start() or now).astimezone(tz).date()
    o_all = Outlook(clusters, started, today, tz)
    c_clusters = {k: v for k, v in clusters.items() if set(v[0].districts) & cdists}
    o_city = Outlook(c_clusters, started, today, tz)

    # next week's outlook for the city (always available)
    rep["next_week"] = [{"name": p["headline"], "expected": round(p["expected"], 1), "range": [p["low"], p["high"]],
                         "evidence": p["evidence_grade"], "where": p["where_short"], "insight": p["insight"]}
                        for p in predictions(o_city, 4)]
    if not made_on:
        return rep

    rows = _score_rows(store, made_on, o_all, o_city, city_key, cdists)
    city_rows = [r for r in rows if r["scope"] == "city"]
    state_rows = [r for r in rows if r["scope"] == "state"]

    def summary(rs):
        graded = [r for r in rs if r["category"] != "*"]
        by = {}
        for g in ("Strong", "Moderate", "Limited"):
            gs = [r for r in graded if r["evidence"] == g]
            if gs:
                by[g] = [sum(r["verdict"] == "inside" for r in gs), len(gs)]
        n = len(graded) or 1
        return {"inside": sum(r["verdict"] == "inside" for r in graded), "n": len(graded), "by_grade": by,
                "trivial": sum(r["trivial"] for r in graded),
                "error_model": round(sum(abs(r["actual"] - r["expected"]) for r in graded) / n, 2),
                "error_naive": round(sum(abs(r["actual"] - r["naive"]) for r in graded) / n, 2),
                "expected_total": round(sum(r["expected"] for r in graded), 1),
                "actual_total": sum(r["actual"] for r in graded)}

    if not rows:
        return rep
    ws, we = date.fromisoformat(rows[0]["window"][0]), date.fromisoformat(rows[0]["window"][1])
    rep.update({
        "window": [ws.isoformat(), we.isoformat()],
        "city_rows": sorted(city_rows, key=lambda r: (r["category"] != "*", -r["expected"])),
        "state_total": next((r for r in state_rows if r["category"] == "*"), None),
        "city_summary": summary(city_rows),
        "state_summary": summary(state_rows),
        "misses": sorted([r for r in rows if r["verdict"] != "inside" and r["category"] != "*"],
                         key=lambda r: -abs(r["actual"] - r["expected"]))[:6],
    })

    # what actually happened in the city that week, and how it compares with the week before
    def week_counts(start):
        cnt, heads = Counter(), []
        for cl in c_clusters.values():
            lead = cl[0]
            d = lead.published.astimezone(tz).date()
            if lead.categories and start <= d < start + timedelta(days=7):
                cnt[lead.categories[0]] += 1
                heads.append((lead.severity, d, lead.title, lead.link))
        return cnt, sorted(heads, key=lambda h: (-h[0], h[1]))
    this_c, heads = week_counts(ws)
    prev_c, _ = week_counts(ws - timedelta(days=7))
    rep["happened"] = {"total": sum(this_c.values()), "previous_total": sum(prev_c.values()),
                       "by_category": [[c, n, prev_c.get(c, 0)] for c, n in this_c.most_common()],
                       "top": [{"title": t, "link": l, "date": d.isoformat()} for _, d, t, l in heads[:5]]}

    # running score: every weekly cycle so far
    hist = []
    for m in all_due:
        rs = [r for r in _score_rows(store, m, o_all, o_city, city_key, cdists) if r["category"] != "*"]
        hist.append({"made_on": m.isoformat(), "inside": sum(r["verdict"] == "inside" for r in rs), "n": len(rs),
                     "city_inside": sum(r["verdict"] == "inside" for r in rs if r["scope"] == "city"),
                     "city_n": sum(1 for r in rs if r["scope"] == "city")})
    rep["history"] = hist
    return rep


def _d(s: str) -> str:
    d = date.fromisoformat(s)
    return f"{d.day} {d:%b}"


def markdown(rep: dict) -> str:
    """Short text summary, e.g. for a weekly message."""
    city = rep["city"]
    if not rep["made_on"]:
        lines = [f"**{city} weekly scorecard:** the first week of predictions is still running. "
                 f"First scorecard on {_d(rep['first_scorecard'])}." if rep["first_scorecard"] else
                 f"**{city} weekly scorecard:** no predictions saved yet."]
    else:
        cs, ss = rep["city_summary"], rep["state_summary"]
        w = f"{_d(rep['window'][0])}–{_d(rep['window'][1])}"
        lines = [f"**{city} weekly scorecard, {w}** (predictions made {_d(rep['made_on'])})", ""]
        tot = next((r for r in rep["city_rows"] if r["category"] == "*"), None)
        if tot:
            lines.append(f"- {city} total: predicted ~{tot['expected']:.0f} ({tot['low']}–{tot['high']}), "
                         f"actual **{tot['actual']}**: {'inside range' if tot['verdict'] == 'inside' else tot['verdict'] + ' range'}")
        if cs["n"]:
            lines.append(f"- {city} predictions inside their range: **{cs['inside']} of {cs['n']}** "
                         f"(expected {cs['expected_total']:.0f} incidents in total, {cs['actual_total']} happened)")
        if cs["trivial"]:
            lines.append(f"  ({cs['trivial']} of those were 'nothing happened' with a range starting at 0, an easy hit)")
        if cs["n"]:
            better = cs["error_model"] < cs["error_naive"]
            lines.append(f"- Accuracy vs a simple guess: off by {cs['error_model']:.1f} incidents per prediction on average; "
                         f"repeating last week's count would have been off by {cs['error_naive']:.1f} "
                         f"({'our predictions did better' if better else 'the simple guess did as well or better'})")
        if ss["n"]:
            lines.append(f"- Rest of AP and Telangana: {ss['inside']} of {ss['n']} inside range; "
                         f"off by {ss['error_model']:.1f} on average vs {ss['error_naive']:.1f} for the simple guess")
        by = {**{k: v for k, v in cs["by_grade"].items()}}
        if by:
            lines.append("- By evidence: " + ", ".join(f"{g} {a}/{b}" for g, (a, b) in by.items()))
        if rep["misses"]:
            lines.append("- Biggest misses: " + "; ".join(
                f"{m['name']} (predicted ~{m['expected']:.0f}, actual {m['actual']}, {m['verdict']})" for m in rep["misses"][:3]))
        h = rep["happened"]
        lines.append(f"- What happened in {city}: {h['total']} incidents (previous week {h['previous_total']}); "
                     + ", ".join(f"{c.lower()} {n}" for c, n, _ in h["by_category"][:4]))
        if len(rep["history"]) > 1:
            a = sum(x["inside"] for x in rep["history"]); b = sum(x["n"] for x in rep["history"])
            lines.append(f"- Running score over {len(rep['history'])} weeks: {a} of {b} inside range ({a / b * 100:.0f}%)")
    if rep["next_week"]:
        lines += ["", "**Next 7 days:** " + "; ".join(f"{p['name']} ~{p['expected']:.0f} ({p['evidence'].lower()} evidence)"
                                                      for p in rep["next_week"][:3])]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="osint_monitor.weekly")
    ap.add_argument("--db", default=os.environ.get("OSINT_DB", config.DB_PATH))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = build(args.db)
    print(json.dumps(rep, indent=2, ensure_ascii=False) if args.json else markdown(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
