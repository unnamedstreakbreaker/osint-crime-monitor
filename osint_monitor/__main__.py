"""CLI entry point.

    python -m osint_monitor              # fetch live feeds, build today's brief
    python -m osint_monitor --demo       # offline run on synthetic sample data
    python -m osint_monitor --hours 48   # widen the incident window
    python -m osint_monitor --json       # also write the incidents as JSON
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone

from . import analysis, config, report
from .classifier import classify, enrich_with_llm, locate
from .demo import sample_items
from .forecast import Outlook
from .explain import predictions, all_for_log, track_record
from .fetcher import fetch_all
from .store import Store


def write_pwa(out_dir: str, now) -> None:
    """Icons, per-language web app manifests and the versioned service worker."""
    import shutil
    static = os.path.join(os.path.dirname(__file__), "static")
    for f in os.listdir(static):
        if f.endswith(".png"):
            shutil.copyfile(os.path.join(static, f), os.path.join(out_dir, f))
    with open(os.path.join(static, "sw.js"), encoding="utf-8") as fh:
        sw = fh.read().replace("__VERSION__", now.strftime("%Y%m%d%H%M"))
    with open(os.path.join(out_dir, "sw.js"), "w", encoding="utf-8") as fh:
        fh.write(sw)
    city = config.CITIES[config.DEFAULT_CITY]
    icons = [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
             {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
             {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]
    for lang, fname, name, short, desc, start in (
        ("en", "manifest.webmanifest", f"{city['name']} Crime and Threat Board", f"{city['name']} Crime Board",
         f"Crime and security incidents in and around {city['full']}, from public news, with a 7-day outlook.", "./index.html"),
        ("te", "manifest.te.webmanifest", "విశాఖ నేర, ముప్పు పర్యవేక్షణ బోర్డు", "విశాఖ నేర బోర్డు",
         "విశాఖపట్నం, పరిసర ప్రాంతాల్లో నేర ఘటనలు, 7 రోజుల అంచనాతో.", "./te.html")):
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as fh:
            json.dump({"name": name, "short_name": short, "description": desc, "lang": lang,
                       "id": start, "start_url": start, "scope": "./", "display": "standalone",
                       "background_color": "#13233f", "theme_color": "#13233f", "icons": icons},
                      fh, ensure_ascii=False, indent=2)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="osint_monitor", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="use synthetic sample data (no network)")
    ap.add_argument("--hours", type=int, default=24, help="incident window for the brief (default 24)")
    ap.add_argument("--db", default=None, help="SQLite path (default from OSINT_DB)")
    ap.add_argument("--out", default=None, help="output HTML path")
    ap.add_argument("--json", action="store_true", help="also export incidents as JSON")
    ap.add_argument("--json-out", default=None, help="path for the JSON export (implies --json)")
    ap.add_argument("--city", default=None, help="(unused for now) all enabled cities are built")
    ap.add_argument("--no-llm", action="store_true", help="skip Claude enrichment even if a key is set")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    db_path = args.db or (":memory:" if args.demo else config.DB_PATH)
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    store = Store(db_path)

    print("Collecting items…")
    raw = sample_items(now) if args.demo else fetch_all(config.FEEDS)
    # keep two weeks so trends have a baseline
    raw = [i for i in raw if i.published >= now - timedelta(days=14)]
    print(f"  {len(raw)} items within 14 days")

    known = store.known_ids()
    for it in raw:
        classify(it)

    use_llm = bool(config.ANTHROPIC_API_KEY) and not args.no_llm
    if use_llm:
        fresh = [i for i in raw if i.categories and i.item_id not in known]
        print(f"Enriching {len(fresh)} new items with {config.LLM_MODEL}…")
        for it in fresh:
            enrich_with_llm(it)

    new = store.upsert(raw)
    print(f"  {new} new items stored")

    items = store.since(now - timedelta(days=14))
    # re-apply the current rules to history so keyword fixes take effect retroactively
    for it in items:
        if use_llm and it.llm_summary:
            locate(it)
        else:
            classify(it)
    clusters = analysis.cluster(items)
    store.upsert(items)  # persist cluster ids

    tz = report._TZ
    started = store.tracking_start() or now
    if args.demo:  # pretend monitoring has run for 10 days so the demo shows a full outlook
        started = now - timedelta(days=10)
    start_day, today = started.astimezone(tz).date(), now.astimezone(tz).date()
    baseline_ok = (now - started) >= timedelta(days=14)

    # Statewide outlook: every prediction is logged so the track record can't be cherry-picked
    outlook_all = Outlook(clusters, start_day, today, tz)
    log_rows = all_for_log(outlook_all)

    os.makedirs(config.REPORT_DIR, exist_ok=True)
    out = args.out or os.path.join(config.REPORT_DIR,
                                   f"brief_{now:%Y%m%d}{'_demo' if args.demo else ''}.html")
    out_dir = os.path.dirname(out) or "."
    os.makedirs(out_dir, exist_ok=True)

    default_out = None
    for key, city in config.CITIES.items():
        if not city["enabled"]:
            continue
        cdists = set(city["districts"])
        c_clusters = {cid: cl for cid, cl in clusters.items() if set(cl[0].districts) & cdists}
        c_items = [it for cl in c_clusters.values() for it in cl]
        trends = analysis.category_trends(c_items, now)
        if not baseline_ok:  # last week wasn't monitored yet, so "spikes" would be artefacts
            for t in trends:
                t["spike"] = False
                t["baseline"] = False
        hotspots = analysis.district_hotspots(c_items, now)
        emerging = analysis.emerging_terms(c_items, now)
        outlook = Outlook(c_clusters, start_day, today, tz)
        log_rows.append({"category": "*", "district": f"city:{key}", **outlook.project(outlook.total), "evidence": ""})
        record = track_record(store, outlook, districts=cdists, city=key)

        weekly_rep = None
        if not args.demo:
            from .weekly import build as build_weekly
            weekly_rep = build_weekly(db_path, key, now)
        for lang in ("en", "te"):
            page = report.render(record=record, items=c_items, clusters=c_clusters, trends=trends, hotspots=hotspots,
                                 emerging=emerging, now=now, hours=args.hours, demo=args.demo, outlook=outlook,
                                 city_key=key, lang=lang, weekly=weekly_rep)
            if key == config.DEFAULT_CITY:
                path = out if lang == "en" else os.path.join(out_dir, "te.html")
            else:
                path = os.path.join(out_dir, f"{key}{'.te' if lang == 'te' else ''}.html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(page)
        print(f"{city['name']}: {sum(1 for cl in c_clusters.values() if cl[0].categories)} incidents in 14 days -> {path}")
        if key != config.DEFAULT_CITY:
            continue
        default_out = (c_clusters, outlook, record)
        if weekly_rep:
            with open(os.path.join(out_dir, "weekly.json"), "w", encoding="utf-8") as fh:
                json.dump(weekly_rep, fh, indent=2, ensure_ascii=False)

        def _rows(rows):
            return [{"name": r["key"] if isinstance(r["key"], str) else " in ".join(r["key"]),
                     "last_7_days": r["last7"], "expected_next_7": round(r["expected"], 2),
                     "range": [r["low"], r["high"]], "chance_any": round(r["p_any"], 3),
                     "trend": round(r["trend"], 2)} for r in rows]
        with open(os.path.join(out_dir, "outlook.json"), "w", encoding="utf-8") as fh:
            json.dump({"generated_at": now.isoformat(), "city": city["name"], "districts": city["districts"],
                       "confidence": outlook.conf, "reliable_days": outlook.n_reliable,
                       "total": _rows([{"key": "All incidents", **outlook.project(outlook.total)}])[0],
                       "categories": _rows(outlook.category_rows()), "by_district": _rows(outlook.district_rows()),
                       "areas": _rows(outlook.area_rows()), "watchlist": _rows(outlook.watchlist()),
                       "predictions": predictions(outlook, 8),
                       "track_record": {k: v for k, v in record.items() if k != "first_check"}
                                       | {"first_check": str(record["first_check"] or "")}},
                      fh, indent=2, ensure_ascii=False)

    write_pwa(out_dir, now)

    if not args.demo:
        store.log_predictions(today, log_rows)
    clusters = default_out[0] if default_out else clusters
    with open(os.path.join(os.path.dirname(out) or ".", "status.json"), "w") as fh:
        json.dump({"generated_at": int(now.timestamp()), "items": len(items)}, fh)

    if args.json or args.json_out:
        jpath = args.json_out or out.rsplit(".", 1)[0] + ".json"
        os.makedirs(os.path.dirname(jpath) or ".", exist_ok=True)
        recent = [cl for cl in clusters.values() if cl[0].categories
                  and cl[0].published >= now - timedelta(hours=args.hours)]
        with open(jpath, "w", encoding="utf-8") as fh:
            json.dump([{
                "title": cl[0].title, "link": cl[0].link, "published": cl[0].published.isoformat(),
                "categories": cl[0].categories, "state": cl[0].state, "districts": cl[0].districts,
                "areas": cl[0].areas,
                "severity": cl[0].severity, "summary": cl[0].llm_summary or cl[0].summary,
                "sources": sorted({c.source for c in cl}),
            } for cl in recent], fh, indent=2, ensure_ascii=False)
        print(f"JSON written to {jpath}")

    spikes = [t for t in trends if t["spike"]]  # empty until 14 days of monitoring
    if spikes:
        print("Spikes:", "; ".join(f"{t['category']} ({t['state']}) {t['previous']}→{t['current']}" for t in spikes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
