"""Duplicate clustering and trend / spike detection."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from . import config
from .fetcher import NewsItem

_STOP = set("""a an the of in on at to for and or by with from as is are was were be been
over after into near amid police case cases two three four five held arrested says said
district city man woman youth new""".split())


_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if w not in _STOP and len(w) > 2}


def _same_incident_score(a: NewsItem, b: NewsItem, ta: set[str], tb: set[str]) -> float:
    """0..1+ score that two articles describe the same incident."""
    if abs((a.published - b.published).total_seconds()) > 48 * 3600:
        return 0.0
    if a.districts and b.districts and not set(a.districts) & set(b.districts):
        return 0.0  # different places => different incidents
    score = len(ta & tb) / len(ta | tb) if ta and tb else 0.0
    if set(a.districts) & set(b.districts) and set(a.categories) & set(b.categories):
        score += 0.25
    na, nb = set(_NUM_RE.findall(a.title)), set(_NUM_RE.findall(b.title))
    if na & nb:
        score += 0.2  # same amount / quantity, e.g. "Rs 1.2 crore", "250 kg"
    return score


def cluster(items: list[NewsItem], threshold: float = 0.45) -> dict[str, list[NewsItem]]:
    """Group items that report the same incident (same story across outlets).

    Greedy clustering: title-token overlap, boosted by shared district +
    category and shared figures, and blocked across >48h or different districts.
    Returns cluster_id -> items (lead item first).
    """
    clusters: dict[str, list[NewsItem]] = {}
    for it in sorted(items, key=lambda i: (-i.severity, -i.published.timestamp())):
        toks = _tokens(it.title)
        best, best_score = None, 0.0
        for cid, members in clusters.items():
            lead = members[0]
            score = _same_incident_score(it, lead, toks, _tokens(lead.title))
            if score > best_score:
                best, best_score = cid, score
        if best and best_score >= threshold:
            it.cluster_id = best
            clusters[best].append(it)
        else:
            it.cluster_id = it.item_id
            clusters[it.item_id] = [it]
    return clusters


def category_trends(items: list[NewsItem], now: datetime, window_days: int = 7):
    """Compare incident counts in the last window vs the previous window.

    Counts clusters (incidents), not raw articles, so one heavily-covered
    story doesn't look like a crime wave.
    """
    cur_start = now - timedelta(days=window_days)
    prev_start = now - timedelta(days=2 * window_days)
    cur, prev = Counter(), Counter()
    seen_cur, seen_prev = set(), set()
    for it in items:
        for cat in it.categories:
            key = (cat, it.state)
            tag = (it.cluster_id, cat)
            if it.published >= cur_start:
                if tag not in seen_cur:
                    cur[key] += 1
                    seen_cur.add(tag)
            elif it.published >= prev_start:
                if tag not in seen_prev:
                    prev[key] += 1
                    seen_prev.add(tag)
    rows = []
    for key in set(cur) | set(prev):
        c, p = cur[key], prev[key]
        change = (c - p) / p if p else (1.0 if c else 0.0)
        spike = c >= 3 and (p == 0 or change >= 0.5)
        rows.append({"category": key[0], "state": key[1], "current": c,
                     "previous": p, "change": change, "spike": spike})
    rows.sort(key=lambda r: (-r["spike"], -r["current"], r["category"]))
    return rows


def district_hotspots(items: list[NewsItem], now: datetime, days: int = 7, top: int = 10):
    start = now - timedelta(days=days)
    counts: dict[str, Counter] = defaultdict(Counter)
    seen = set()
    for it in items:
        if it.published < start or not it.categories:
            continue
        for d in it.districts:
            if (it.cluster_id, d) in seen:
                continue
            seen.add((it.cluster_id, d))
            for cat in it.categories:
                counts[d][cat] += 1
    ranked = sorted(counts.items(), key=lambda kv: -sum(kv[1].values()))[:top]
    return [{"district": d, "total": sum(c.values()), "by_category": c.most_common(3)} for d, c in ranked]


def emerging_terms(items: list[NewsItem], now: datetime, days: int = 7):
    """Modus-operandi terms seen this week, with whether they were absent last week."""
    start, prev_start = now - timedelta(days=days), now - timedelta(days=2 * days)
    cur, prev = Counter(), Counter()
    for it in items:
        text = it.text.lower()
        for term in config.EMERGING_TERMS:
            if term in text:
                if it.published >= start:
                    cur[term] += 1
                elif it.published >= prev_start:
                    prev[term] += 1
    return [{"term": t, "count": n, "new": prev[t] == 0} for t, n in cur.most_common()]
