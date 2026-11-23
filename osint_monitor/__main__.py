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
from .classifier import classify, enrich_with_llm
from .demo import sample_items
from .fetcher import fetch_all
from .store import Store


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="osint_monitor", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="use synthetic sample data (no network)")
    ap.add_argument("--hours", type=int, default=24, help="incident window for the brief (default 24)")
    ap.add_argument("--db", default=None, help="SQLite path (default from OSINT_DB)")
    ap.add_argument("--out", default=None, help="output HTML path")
    ap.add_argument("--json", action="store_true", help="also export incidents as JSON")
    ap.add_argument("--json-out", default=None, help="path for the JSON export (implies --json)")
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
    clusters = analysis.cluster(items)
    store.upsert(items)  # persist cluster ids

    trends = analysis.category_trends(items, now)
    hotspots = analysis.district_hotspots(items, now)
    emerging = analysis.emerging_terms(items, now)

    page = report.render(items=items, clusters=clusters, trends=trends, hotspots=hotspots,
                         emerging=emerging, now=now, hours=args.hours, demo=args.demo)
    os.makedirs(config.REPORT_DIR, exist_ok=True)
    out = args.out or os.path.join(config.REPORT_DIR,
                                   f"brief_{now:%Y%m%d}{'_demo' if args.demo else ''}.html")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"Brief written to {out}")

    if args.json or args.json_out:
        jpath = args.json_out or out.rsplit(".", 1)[0] + ".json"
        os.makedirs(os.path.dirname(jpath) or ".", exist_ok=True)
        recent = [cl for cl in clusters.values() if cl[0].categories
                  and cl[0].published >= now - timedelta(hours=args.hours)]
        with open(jpath, "w", encoding="utf-8") as fh:
            json.dump([{
                "title": cl[0].title, "link": cl[0].link, "published": cl[0].published.isoformat(),
                "categories": cl[0].categories, "state": cl[0].state, "districts": cl[0].districts,
                "severity": cl[0].severity, "summary": cl[0].llm_summary or cl[0].summary,
                "sources": sorted({c.source for c in cl}),
            } for cl in recent], fh, indent=2, ensure_ascii=False)
        print(f"JSON written to {jpath}")

    spikes = [t for t in trends if t["spike"]]
    if spikes:
        print("Spikes:", "; ".join(f"{t['category']} ({t['state']}) {t['previous']}→{t['current']}" for t in spikes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
