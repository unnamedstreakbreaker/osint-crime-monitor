"""SQLite storage so trends can be computed across days of runs."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from .fetcher import NewsItem, strip_source

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    item_id      TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    link         TEXT,
    summary      TEXT,
    published    TEXT NOT NULL,
    source       TEXT,
    feed         TEXT,
    categories   TEXT,
    state        TEXT,
    districts    TEXT,
    severity     INTEGER,
    matched      TEXT,
    llm_summary  TEXT,
    cluster_id   TEXT,
    first_seen   TEXT NOT NULL,
    areas        TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_published ON items(published);
CREATE TABLE IF NOT EXISTS predictions_log (
    made_on      TEXT NOT NULL,   -- IST date the prediction was made
    category     TEXT NOT NULL,
    district     TEXT NOT NULL,   -- '*' = all of AP & Telangana
    expected     REAL NOT NULL,
    low          INTEGER NOT NULL,
    high         INTEGER NOT NULL,
    evidence     TEXT,
    window_start TEXT NOT NULL,   -- first day predicted (made_on + 1)
    window_end   TEXT NOT NULL,   -- last day predicted (made_on + 7)
    PRIMARY KEY (made_on, category, district)
);
"""


def _source_label(src: str) -> str:
    return "The Hindu" if src.startswith("thehindu") else src


class Store:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(items)")}
        if "areas" not in cols:  # migrate databases created before sub-areas existed
            self.conn.execute("ALTER TABLE items ADD COLUMN areas TEXT")
            self.conn.commit()

    def upsert(self, items: list[NewsItem]) -> int:
        """Insert new items; returns how many were new."""
        now = datetime.now(timezone.utc).isoformat()
        existing = self.known_ids()
        new = sum(1 for it in items if it.item_id not in existing)
        for it in items:
            self.conn.execute(
                """INSERT INTO items (item_id,title,link,summary,published,source,feed,categories,
                   state,districts,severity,matched,llm_summary,cluster_id,first_seen,areas)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(item_id) DO UPDATE SET
                     categories=excluded.categories, state=excluded.state,
                     districts=excluded.districts, areas=excluded.areas, severity=excluded.severity,
                     matched=excluded.matched, cluster_id=excluded.cluster_id,
                     llm_summary=COALESCE(NULLIF(excluded.llm_summary,''), items.llm_summary)""",
                (it.item_id, it.title, it.link, it.summary, it.published.isoformat(),
                 it.source, it.feed, json.dumps(it.categories), it.state,
                 json.dumps(it.districts), it.severity, json.dumps(it.matched_terms),
                 it.llm_summary, it.cluster_id, now, json.dumps(it.areas)))
        self.conn.commit()
        return new

    def tracking_start(self):
        """UTC datetime of the first run that stored anything (None if empty)."""
        row = self.conn.execute("SELECT MIN(first_seen) FROM items").fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None

    def known_ids(self) -> set[str]:
        return {r[0] for r in self.conn.execute("SELECT item_id FROM items")}

    def since(self, start: datetime) -> list[NewsItem]:
        rows = self.conn.execute(
            "SELECT * FROM items WHERE published >= ? ORDER BY published DESC",
            (start.isoformat(),)).fetchall()
        out = []
        for r in rows:
            it = NewsItem(title=strip_source(r[1], r[5] or ""), link=r[2], summary=r[3],
                          published=datetime.fromisoformat(r[4]), source=_source_label(r[5] or ""),
                          feed=r[6], item_id=r[0])
            it.categories = json.loads(r[7] or "[]")
            it.state = r[8] or ""
            it.districts = json.loads(r[9] or "[]")
            it.severity = r[10] or 0
            it.matched_terms = json.loads(r[11] or "[]")
            it.llm_summary = r[12] or ""
            it.cluster_id = r[13] or ""
            it.areas = json.loads(r[15] or "[]") if len(r) > 15 else []
            out.append(it)
        return out


    # -- prediction track record ---------------------------------------------
    def log_predictions(self, made_on, rows):
        """rows: dicts with category, district, expected, low, high, evidence. First run of the day wins."""
        from datetime import timedelta as _td
        for r in rows:
            self.conn.execute(
                "INSERT OR IGNORE INTO predictions_log VALUES (?,?,?,?,?,?,?,?,?)",
                (made_on.isoformat(), r["category"], r["district"], round(r["expected"], 2), r["low"], r["high"],
                 r.get("evidence", ""), (made_on + _td(days=1)).isoformat(), (made_on + _td(days=7)).isoformat()))
        self.conn.commit()

    def due_predictions(self, today):
        """Predictions whose 7-day window has fully ended."""
        return self.conn.execute(
            "SELECT made_on, category, district, expected, low, high, evidence, window_start, window_end "
            "FROM predictions_log WHERE window_end < ? ORDER BY made_on", (today.isoformat(),)).fetchall()

    def first_prediction_day(self):
        row = self.conn.execute("SELECT MIN(made_on) FROM predictions_log").fetchone()
        return row[0] if row else None
