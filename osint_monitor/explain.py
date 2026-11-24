"""Turn outlook numbers into plain-language predictions: what, how many, why, where.

Every sentence here is built from counts the analyst can check by opening the
evidence links. Nothing is inferred beyond the news reports themselves.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from . import config

# Words that only restate the category; they say nothing about the method used.
GENERIC_TERMS = {
    "cyber fraud", "cyber crime", "cybercrime", "online fraud", "cyber criminals", "fraudsters",
    "duped", "lost rs", "loses rs", "crore", "narcotic", "drugs seized", "smuggling", "smuggled",
    "attack", "killed", "alert", "awareness", "advisory", "protest", "tension", "theft",
}

TERM_LABEL = {
    "apk": "malicious APK files", "otp": "OTP sharing", "mule account": "mule bank accounts",
    "part-time job": "part-time job offers", "task scam": "online task scams", "loan app": "loan apps",
    "trading app": "fake trading apps", "fake trading": "fake trading apps", "fake app": "fake apps",
    "investment scam": "investment scams", "trading scam": "trading scams", "courier scam": "courier scams",
    "kyc update": "fake KYC updates", "pocso": "POCSO cases", "ied": "IEDs", "ndps": "NDPS cases",
    "mdma": "MDMA", "pds rice": "PDS rice", "pd act": "PD Act detentions", "upi fraud": "UPI fraud",
    "ganja trafficking": "ganja trafficking", "voice clone": "AI voice cloning", "ai voice": "AI voice cloning",
    "qr code": "QR codes", "sim swap": "SIM swap", "e-sim": "e-SIM fraud", "betting app": "betting apps",
    "screen sharing": "screen-sharing apps", "fake police": "fake police calls",
}

CATEGORY_WHAT = {
    "Cyber fraud": "Online fraud cases (money lost to scammers)",
    "Narcotics": "Drug seizures and arrests",
    "Left-wing extremism": "Maoist activity, encounters or surrenders",
    "Law and order": "Public-order incidents (clashes, protests, threats)",
    "Violent crime": "Murders, robberies, assaults or kidnappings",
    "Crimes against women & children": "Crimes against women and children",
    "Smuggling & illegal trade": "Smuggling and illegal trade seizures",
    "Advisories & alerts": "Police or government warnings to the public",
}


def evidence(o, key) -> dict:
    """How much independent reporting stands behind a prediction."""
    leads = o.members.get(key, [])
    clusters = [o.clusters_of.get(l.item_id, [l]) for l in leads]
    outlets = {a.source for cl in clusters for a in cl if a.source}
    days = {l.published.astimezone(o.tz).date() for l in leads}
    n, reports = len(leads), sum(len(cl) for cl in clusters)
    if n >= 5 and len(outlets) >= 3 and len(days) >= 3:
        grade = "Strong"
    elif n >= 3 and len(outlets) >= 2:
        grade = "Moderate"
    else:
        grade = "Limited"
    span = f"{min(days):%d %b}–{max(days):%d %b}" if len(days) > 1 else (f"{min(days):%d %b}" if days else "")
    text = (f"{n} incident{'s' if n != 1 else ''}, {reports} news report{'s' if reports != 1 else ''} "
            f"from {len(outlets)} outlet{'s' if len(outlets) != 1 else ''}" + (f", {span}" if span else ""))
    return {"grade": grade, "incidents": n, "reports": reports, "outlets": sorted(outlets),
            "days": len(days), "text": text}


EVIDENCE_RULE = ("Strong = 5+ separate incidents, reported by 3+ different outlets, on 3+ different days. "
                 "Moderate = 3+ incidents from 2+ outlets. Limited = anything less.")


def _chance(p: float) -> str:
    if p >= 0.95:
        return "very likely (over 95%)"
    if p >= 0.75:
        return f"likely ({p * 100:.0f}%)"
    if p >= 0.4:
        return f"possible ({p * 100:.0f}%)"
    return f"unlikely ({p * 100:.0f}%)"


def explain(o, key, row) -> dict:
    """o: forecast.Outlook, key: (category, district), row: o.project(...) + key."""
    cat, dist = key
    today = o.today
    leads = o.members.get(key, [])
    day = lambda it: it.published.astimezone(o.tz).date()
    last7 = [l for l in leads if (today - day(l)).days < 7]
    last3 = sum(1 for l in leads if (today - day(l)).days < 3)
    prev4 = sum(1 for l in leads if 3 <= (today - day(l)).days < 7)

    # how this district ranks for this category
    per_dist = Counter()
    for (c, d), items in o.members.items():
        if c == cat:
            per_dist[d] = sum(1 for l in items if (today - day(l)).days < 7)
    ranking = [d for d, n in per_dist.most_common() if n > 0]
    rank = ranking.index(dist) + 1 if dist in ranking else None
    cat_total_30 = sum(len(v) for (c, _), v in o.members.items() if c == cat)
    share = len(leads) / cat_total_30 if cat_total_30 else 0

    # methods (modus operandi) seen in these reports
    cat_terms = set(config.CATEGORIES.get(cat, {})) | set(config.EMERGING_TERMS)
    mo = Counter(t for l in leads[:20] for t in l.matched_terms if t in cat_terms and t not in GENERIC_TERMS)
    methods = list(dict.fromkeys(TERM_LABEL.get(t, t) for t, _ in mo.most_common(6)))[:4]

    # where inside the district
    places = Counter(name for l in leads[:30] for d, name in l.places if d == dist)
    unspecified = sum(1 for l in leads[:30] if not any(d == dist for d, _ in l.places))

    why = []
    n7 = len(last7)
    if n7:
        lead_in = f"{n7} {cat.lower()} report{'s' if n7 != 1 else ''} from {dist} in the last 7 days"
        if rank == 1 and len(ranking) > 1:
            lead_in += f", the most of any district (next: {ranking[1]}, {per_dist[ranking[1]]})"
        elif rank and len(ranking) == 1:
            lead_in += f", the only district reporting {cat.lower()} this week"
        elif rank:
            lead_in += f", #{rank} of {len(ranking)} districts reporting {cat.lower()}"
        why.append(lead_in + ".")
    else:
        why.append(f"No {cat.lower()} reports from {dist} this week, but {len(leads)} in the last 30 days, "
                   "so a recurrence is possible.")
    if n7 >= 2:
        if last3 > prev4 * 0.75 + 0.5:
            why.append(f"Picking up: {last3} in the last 3 days against {prev4} in the 4 days before.")
        elif last3 * 1.33 + 0.5 < prev4:
            why.append(f"Slowing: {last3} in the last 3 days against {prev4} in the 4 days before.")
        else:
            why.append(f"Steady: {last3} in the last 3 days, {prev4} in the 4 days before.")
    if share >= 0.15 and cat_total_30 >= 4:
        why.append(f"{dist} accounts for {share * 100:.0f}% of all {cat.lower()} reports this month.")
    if methods:
        why.append("Common methods in these reports: " + ", ".join(methods) + ".")
    why.append(f"Expected count = recent daily rate x 7"
               + (", pulled toward the long-run average because monitoring is new" if o.conf == "Low" else "")
               + (f", then x{row['trend']:.1f} for the trend" if abs(row["trend"] - 1) > 0.05 else "")
               + f". Confidence: {o.conf}.")

    where_list = [f"{n} ({c})" if c > 1 else n for n, c in places.most_common(5)]
    if where_list:
        where = "Most likely around " + ", ".join(where_list) + ", where recent cases were reported"
        if unspecified:
            where += f". {unspecified} other report{'s' if unspecified != 1 else ''} named only the district."
        else:
            where += "."
    else:
        where = f"Reports name only {dist}, not a specific locality."

    ev = evidence(o, key)
    show_chance = ev["grade"] != "Limited" and o.conf != "Low"

    what = CATEGORY_WHAT.get(cat, cat)
    if methods:
        what += f", especially {methods[0]}" + (f" and {methods[1]}" if len(methods) > 1 else "")

    return {
        "category": cat, "district": dist,
        "headline": f"{cat} in {dist}",
        "what": what,
        "expected": row["expected"], "low": row["low"], "high": row["high"],
        "chance": row["p_any"], "chance_text": _chance(row["p_any"]), "show_chance": show_chance,
        "evidence_grade": ev["grade"], "evidence_text": ev["text"], "outlets": ev["outlets"],
        "direction": row["direction"], "trend": row["trend"],
        "why": why,
        "where": where,
        "places": [n for n, _ in places.most_common(5)],
        "evidence": [{"title": l.title, "link": l.link, "source": l.source,
                      "when": l.published.astimezone(o.tz).strftime("%d %b"),
                      "place": ", ".join(n for d, n in l.places if d == dist) or dist,
                      "also": sorted({a.source for a in o.clusters_of.get(l.item_id, [l])} - {l.source})}
                     for l in leads[:12]],
    }


def all_for_log(o) -> list[dict]:
    """Every prediction made today (not just the ones shown), so the track record isn't cherry-picked."""
    rows = [{"category": "*", "district": "*", **o.project(o.total), "evidence": ""}]
    for r in o.ranked(o.by_cat_district, top=500, min_expected=0.2):
        cat, dist = r["key"]
        if cat == "Advisories & alerts":
            continue
        rows.append({"category": cat, "district": dist, **r, "evidence": evidence(o, r["key"])["grade"]})
    return rows


def track_record(store, o) -> dict:
    """Score predictions whose 7-day window has ended against what was actually reported."""
    from datetime import date as _date, timedelta as _td
    scored = []
    for made_on, cat, dist, exp, low, high, grade, ws, we in store.due_predictions(o.today):
        ws, we = _date.fromisoformat(ws), _date.fromisoformat(we)
        if ws < o.days[0]:
            continue  # older than the 30-day window we hold in memory
        series = o.total if cat == "*" else o.by_cat_district.get((cat, dist), {})
        actual = sum(series.get(ws + _td(days=i), 0) for i in range((we - ws).days + 1))
        scored.append({"made_on": made_on, "category": cat, "district": dist, "expected": exp,
                       "low": low, "high": high, "actual": actual, "evidence": grade,
                       "hit": low <= actual <= high})
    graded = [r for r in scored if r["category"] != "*"]
    by_grade = {}
    for g in ("Strong", "Moderate", "Limited"):
        rs = [r for r in graded if r["evidence"] == g]
        if rs:
            by_grade[g] = {"n": len(rs), "hits": sum(r["hit"] for r in rs)}
    first = store.first_prediction_day()
    first_check = (_date.fromisoformat(first) + _td(days=8)) if first else None
    return {"n": len(graded), "hits": sum(r["hit"] for r in graded), "by_grade": by_grade,
            "total_rows": [r for r in scored if r["category"] == "*"][-7:],
            "recent": sorted(graded, key=lambda r: r["made_on"], reverse=True)[:15],
            "first_check": first_check}


def predictions(o, top: int = 6, district: str | None = None) -> list[dict]:
    rows = o.ranked(o.by_cat_district, top=200, min_expected=0.0 if district else 0.2)
    rows = [r for r in rows if r["key"][0] != "Advisories & alerts"]   # warnings aren't crimes
    if district:
        rows = [r for r in rows if r["key"][1] == district]
    out = [explain(o, r["key"], r) for r in rows[:max(top * 3, 12)]]
    rank = {"Strong": 0, "Moderate": 1, "Limited": 2}
    out.sort(key=lambda p: (rank[p["evidence_grade"]], -p["expected"]))
    return out[:top]
