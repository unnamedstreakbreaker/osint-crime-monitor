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

    what = CATEGORY_WHAT.get(cat, cat)
    if methods:
        what += f", especially {methods[0]}" + (f" and {methods[1]}" if len(methods) > 1 else "")

    return {
        "category": cat, "district": dist,
        "headline": f"{cat} in {dist}",
        "what": what,
        "expected": row["expected"], "low": row["low"], "high": row["high"],
        "chance": row["p_any"], "chance_text": _chance(row["p_any"]),
        "direction": row["direction"], "trend": row["trend"],
        "why": why,
        "where": where,
        "places": [n for n, _ in places.most_common(5)],
        "evidence": [{"title": l.title, "link": l.link, "source": l.source,
                      "when": l.published.astimezone(o.tz).strftime("%d %b"),
                      "place": ", ".join(n for d, n in l.places if d == dist) or dist}
                     for l in leads[:3]],
    }


def predictions(o, top: int = 6, district: str | None = None) -> list[dict]:
    rows = o.ranked(o.by_cat_district, top=200, min_expected=0.0 if district else 0.2)
    rows = [r for r in rows if r["key"][0] != "Advisories & alerts"]   # warnings aren't crimes
    if district:
        rows = [r for r in rows if r["key"][1] == district]
    return [explain(o, r["key"], r) for r in rows[:top]]
