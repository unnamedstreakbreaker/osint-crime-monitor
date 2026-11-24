"""Daily incident series and a simple, explainable 7-day outlook.

What this is: a statistical outlook of how many *news-reported* incidents to
expect next week per category and per district/area, based on recent rates
and their trend. It is NOT a prediction of specific crimes or people.

Method (kept simple on purpose so an analyst can explain it):
  1. Count incidents (deduplicated clusters) per IST day.
  2. Days before monitoring began only contain whatever the feeds still showed,
     so they are under-counted. Those are marked "partial" and excluded from
     the rate, except a short look-back the feeds cover well.
  3. Daily rate = exponentially weighted mean of reliable days (recent days count
     more). For a category/district/area it is blended with a prior worth
     PRIOR_DAYS days: (its share of all incidents in 30 days) x (overall daily
     rate). With little history the prior dominates, so one story doesn't become
     "98% likely next week"; as reliable days build up, the group's own data wins.
  4. Trend = this half of the reliable window vs the previous half, clipped to
     0.5x–2x, only used once there are >= 10 reliable days.
  5. Expected next-7-day count = rate x trend x 7, with an 80% Poisson range.
     Chance of at least one incident = 1 - exp(-expected).
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta

from .fetcher import NewsItem

FEED_LOOKBACK_DAYS = 2      # feeds show the last ~2 days fully, so those count as reliable
HALF_LIFE_DAYS = 5          # EWMA half-life
PRIOR_DAYS = 7              # weight of the 30-day-average prior, in days
FORECAST_DAYS = 7


def _poisson_quantile(lam: float, q: float) -> int:
    if lam <= 0:
        return 0
    k, p = 0, math.exp(-lam)
    cdf = p
    while cdf < q and k < 1000:
        k += 1
        p *= lam / k
        cdf += p
    return k


def confidence(reliable_days: int) -> str:
    return "Low" if reliable_days < 7 else "Medium" if reliable_days < 21 else "High"


class Outlook:
    def __init__(self, clusters: dict[str, list[NewsItem]], tracking_start: date,
                 today: date, tz, history_days: int = 30):
        self.today = today
        self.tz = tz
        self.members = defaultdict(list)      # (category, district) -> lead items, newest first
        self.clusters_of = {}                 # lead item_id -> all articles reporting that incident
        self.days = [today - timedelta(days=i) for i in range(history_days - 1, -1, -1)]
        self.reliable_from = tracking_start - timedelta(days=FEED_LOOKBACK_DAYS)
        self.reliable_days = [d for d in self.days if d >= self.reliable_from]
        # today is still in progress -> leave it out of the rate
        self.rate_days = [d for d in self.reliable_days if d < today] or self.reliable_days

        self.total = defaultdict(int)
        self.by_cat = defaultdict(lambda: defaultdict(int))
        self.by_district = defaultdict(lambda: defaultdict(int))
        self.by_area = defaultdict(lambda: defaultdict(int))
        self.by_cat_district = defaultdict(lambda: defaultdict(int))
        for cl in clusters.values():
            lead = cl[0]
            if not lead.categories:
                continue
            d = lead.published.astimezone(tz).date()
            if d < self.days[0] or d > today:
                continue
            self.total[d] += 1
            for c in lead.categories:
                self.by_cat[c][d] += 1
            for dist in lead.districts:
                self.by_district[dist][d] += 1
                self.by_cat_district[(lead.categories[0], dist)][d] += 1
                self.members[(lead.categories[0], dist)].append(lead)
            self.clusters_of[lead.item_id] = cl
            for a in lead.areas:
                self.by_area[a][d] += 1

        for v in self.members.values():
            v.sort(key=lambda i: i.published, reverse=True)

    # -- core model ---------------------------------------------------------
    def _ewma(self, series, num=0.0, den=0.0) -> float:
        last = self.rate_days[-1]
        for d in self.rate_days:
            w = 0.5 ** ((last - d).days / HALF_LIFE_DAYS)
            num += w * series.get(d, 0)
            den += w
        return num / den if den else 0.0

    def _rate(self, series: dict[date, int]) -> float:
        if series is self.total:
            return self._ewma(series)
        total_30 = sum(self.total.values()) or 1
        share = sum(series.get(d, 0) for d in self.days) / total_30
        prior = share * self._ewma(self.total)
        return self._ewma(series, PRIOR_DAYS * prior, float(PRIOR_DAYS))

    def _trend(self, series: dict[date, int]) -> float:
        n = len(self.rate_days)
        if n < 10:
            return 1.0
        half = n // 2
        prev = sum(series.get(d, 0) for d in self.rate_days[-2 * half:-half])
        cur = sum(series.get(d, 0) for d in self.rate_days[-half:])
        if prev == 0:
            return 2.0 if cur >= 3 else 1.0
        return max(0.5, min(2.0, cur / prev))

    def project(self, series: dict[date, int]) -> dict:
        rate, trend = self._rate(series), self._trend(series)
        exp7 = rate * trend * FORECAST_DAYS
        last7 = sum(series.get(self.today - timedelta(days=i), 0) for i in range(1, 8))
        return {
            "daily_rate": rate, "trend": trend, "expected": exp7,
            "low": _poisson_quantile(exp7, 0.10), "high": _poisson_quantile(exp7, 0.90),
            "p_any": 1 - math.exp(-exp7), "last7": last7,
            "direction": "up" if trend > 1.15 else "down" if trend < 0.87 else "flat",
        }

    # -- views used by the report -------------------------------------------
    @property
    def n_reliable(self) -> int:
        return len(self.rate_days)

    @property
    def conf(self) -> str:
        return confidence(self.n_reliable)

    def daily_total(self):
        return [(d, self.total.get(d, 0), d < self.reliable_from) for d in self.days]

    def forecast_days(self, series=None):
        p = self.project(series if series is not None else self.total)
        per_day = p["daily_rate"] * p["trend"]
        lo, hi = _poisson_quantile(per_day, 0.10), _poisson_quantile(per_day, 0.90)
        return [(self.today + timedelta(days=i), per_day, lo, hi) for i in range(1, FORECAST_DAYS + 1)]

    def ranked(self, groups: dict, top: int = 10, min_expected: float = 0.3):
        rows = []
        for key, series in groups.items():
            p = self.project(series)
            if p["expected"] >= min_expected or p["last7"] > 0:
                rows.append({"key": key, **p})
        rows.sort(key=lambda r: (-r["expected"], -r["last7"]))
        return rows[:top]

    def category_rows(self, top=10):
        return self.ranked(self.by_cat, top)

    def district_rows(self, top=10):
        return self.ranked(self.by_district, top)

    def area_rows(self, top=10):
        return self.ranked(self.by_area, top, min_expected=0.0)

    def watchlist(self, top=8):
        """Most likely category x district combinations next week."""
        return self.ranked(self.by_cat_district, top, min_expected=0.2)
