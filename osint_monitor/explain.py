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
    "road accident", "road accidents", "accident", "fatal", "mishap", "road mishap", "killed in accident",
    "dies in road", "injured in road", "found dead", "murder", "murdered", "theft case", "held in theft",
    "stolen", "thief", "thieves", "property recovered", "stolen property",
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
    "fake note": "counterfeit currency", "fake notes": "counterfeit currency", "fake currency": "counterfeit currency",
    "lorry": "lorries", "truck": "trucks", "motorcycle": "two-wheelers", "two-wheeler": "two-wheelers",
    "bike": "two-wheelers", "pillion": "pillion riders", "speeding": "speeding", "rash driving": "rash driving",
    "collision": "collisions", "rams": "vehicles ramming", "lorry hits": "lorries", "hits motorcycle": "two-wheelers",
    "car hits": "cars", "bus hits": "buses", "gold recovered": "gold theft", "burglars": "burglaries", "break-in": "break-ins",
    "house burglary": "house burglaries", "burglary": "burglaries", "theft case": "thefts",
    "drunk driving": "drunk driving", "hit-and-run": "hit-and-run", "found dead": "unexplained deaths",
}

CATEGORY_WHAT = {
    "Cyber fraud": "Online fraud cases (money lost to scammers)",
    "Narcotics": "Drug seizures and arrests",
    "Left-wing extremism": "Maoist activity, encounters or surrenders",
    "Law and order": "Public-order incidents (clashes, protests, threats)",
    "Violent crime": "Murders, robberies, assaults or kidnappings",
    "Crimes against women & children": "Crimes against women and children",
    "Property crime": "Thefts, burglaries and recoveries of stolen property",
    "Road accidents": "Road accidents and traffic deaths",
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
        "facts": {"n7": n7, "n30": len(leads), "rank": rank, "nranking": len(ranking),
                  "next": (ranking[1], per_dist[ranking[1]]) if rank == 1 and len(ranking) > 1 else None,
                  "last3": last3, "prev4": prev4, "share": share, "cat_total_30": cat_total_30,
                  "methods": methods, "where_list": [(n, c) for n, c in places.most_common(5)],
                  "unspecified": unspecified, "conf": o.conf, "trend": row["trend"], "ev": ev},
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


def track_record(store, o, districts=None, city=None) -> dict:
    """Score predictions whose 7-day window has ended against what was actually reported."""
    from datetime import date as _date, timedelta as _td
    scored = []
    for made_on, cat, dist, exp, low, high, grade, ws, we in store.due_predictions(o.today):
        if cat == "*" and dist != (f"city:{city}" if city else "*"):
            continue
        if cat != "*" and districts is not None and dist not in districts:
            continue
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
    out = [enrich(o, explain(o, r["key"], r)) for r in rows[:max(top * 3, 12)]]
    rank = {"Strong": 0, "Moderate": 1, "Limited": 2}
    out.sort(key=lambda p: (rank[p["evidence_grade"]], -p["expected"]))
    return out[:top]


# ---------------------------------------------------------------------------
# Insights: who is targeted, money lost, plain-language commentary, focus points
# ---------------------------------------------------------------------------
import re as _re

VICTIMS = [  # (pattern, label) checked against title + summary
    (r"retire[de]|pensioner", "retired people"), (r"senior citizen|elderly|aged \d{2}|\b[6-9]\d-year-old", "senior citizens"),
    (r"job seeker|job aspirant|unemployed", "job seekers"), (r"student|degree|engineering|intermediate", "students"),
    (r"techie|software|it employee", "IT employees"), (r"doctor", "doctors"), (r"teacher|lecturer", "teachers"),
    (r"\bwoman\b|\bwomen\b|housewife|wife|sister|mother", "women"), (r"\bgirl|\bminor|child", "children and minors"),
    (r"farmer", "farmers"), (r"trader|businessm|shop owner|merchant", "traders and business owners"),
    (r"\byouth|\b1[6-9]-year-old|\b2[0-5]-year-old", "young people"), (r"devotee|pilgrim", "devotees"),
    (r"tourist", "tourists"), (r"motorist|biker|pedestrian|two-wheeler", "two-wheeler riders and pedestrians"),
]
_AMT = _re.compile(r"(?:rs\.?|₹|inr)\s*([\d,]+(?:\.\d+)?)\s*-?\s*(crore|cr\b|lakh|lakhs|lac)?", _re.I)

FOCUS = {
    "Cyber fraud": "Public awareness that police never 'digitally arrest' anyone over video calls; push the 1930 helpline so "
                   "money can be frozen in the first hour; watch for mule bank accounts",
    "Property crime": "Night patrols and beat checks in {places}; alert pawn and jewellery shops about stolen gold",
    "Road accidents": "Speed and drunk-driving checks at {places}; black-spot review for repeat locations",
    "Narcotics": "Check-posts on routes out of the Agency area (Paderu, Araku, Chintapalli); PIT-NDPS action on repeat offenders",
    "Violent crime": "Follow up land and family disputes flagged in {places} before they escalate",
    "Crimes against women & children": "Shakti teams and school/college awareness in {places}",
    "Smuggling & illegal trade": "Vehicle checks on highway entry points; alert banks to counterfeit notes",
    "Law and order": "Advance deployment for gatherings and protests in {places}",
    "Left-wing extremism": "Continue area domination in Agency mandals; track surrenders",
}


def _rupees(text: str) -> float:
    best = 0.0
    for num, unit in _AMT.findall(text):
        try:
            v = float(num.replace(",", ""))
        except ValueError:
            continue
        unit = (unit or "").lower()
        v *= 1e7 if unit.startswith("cr") else 1e5 if unit.startswith("la") else 1
        best = max(best, v)
    return best


def fmt_rupees(v: float) -> str:
    if v >= 1e7:
        return f"₹{v / 1e7:.2f} crore".replace(".00 ", " ")
    if v >= 1e5:
        return f"₹{v / 1e5:.1f} lakh".replace(".0 ", " ")
    return f"₹{v:,.0f}"


def profile(leads) -> dict:
    """Who is targeted and how much money, from the reports' own words."""
    victims = Counter()
    losses = []
    for l in leads:
        text = (l.title + " " + l.summary).lower()
        for pat, label in VICTIMS:
            if _re.search(pat, text):
                victims[label] += 1
        amt = _rupees(l.title + " " + l.summary)
        # the same case is often reported again at arrest time ("₹1.94 crore", "nearly ₹2 crore"): count it once
        if amt >= 10000 and not any(abs(amt - x) / max(amt, x) <= 0.05 for x in losses):
            losses.append(amt)
    return {"victims": [v for v, _ in victims.most_common(3)], "losses": losses}


def _insight(p, prof) -> str:
    cat, dist, n7 = p["category"], p["district"], p["n7"]
    where = (" around " + ", ".join(p["places"][:2])) if p["places"] else f" in {dist}"
    victims = (" targeting " + " and ".join(prof["victims"][:2])) if prof["victims"] else ""
    method = p["methods"][0] if p["methods"] else ""
    if cat == "Cyber fraud":
        s = f"{method.capitalize() if method else 'Online'} scams{victims} are the main pattern{where}"
        if prof["losses"]:
            s += f"; reported losses total {fmt_rupees(sum(prof['losses']))} across {len(prof['losses'])} case{'s' if len(prof['losses']) != 1 else ''}"
        return s + "."
    if cat == "Road accidents":
        return f"Road deaths and injuries keep recurring{where}" + (f", mostly involving {prof['victims'][0]}" if prof["victims"] else "") + "."
    if cat == "Property crime":
        return f"Thefts and burglaries{where}" + (f"{victims}" if victims else "") + "; arrests show active gangs rather than one-off cases." if n7 >= 2 else f"Thefts and burglaries reported{where}; watch for a repeat pattern."
    if cat == "Narcotics":
        return f"Ganja movement{where}" + (f" ({method})" if method and method != "ganja" else "") + "; seizures point to supply routes through the district."
    base = CATEGORY_WHAT.get(cat, cat)
    return f"{base}{(' (' + ', '.join(p['methods'][:2]) + ')') if p['methods'] else ''} reported{where}{victims}."


def enrich(o, p) -> dict:
    """Add at-a-glance fields and an insight line to a prediction from explain()."""
    leads = o.members.get((p["category"], p["district"]), [])
    prof = profile(leads[:20])
    today = o.today
    p["n7"] = sum(1 for l in leads if (today - l.published.astimezone(o.tz).date()).days < 7)
    p["methods"] = [m for m in p["what"].split("especially ", 1)[-1].split(" and ")] if "especially" in p["what"] else []
    p["victims"] = prof["victims"]
    p["losses_total"] = sum(prof["losses"])
    p["losses_n"] = len(prof["losses"])
    p["insight"] = _insight(p, prof)
    places = ", ".join(p["places"][:3]) or p["district"]
    p["focus"] = FOCUS.get(p["category"], "").format(places=places)
    p["where_short"] = (", ".join(p["places"][:3]) + f" ({p['district']})") if p["places"] else f"{p['district']} (no locality named in reports)"
    return p


def city_facts(o, preds, city) -> dict:
    today = o.today
    leads7 = [cl[0] for cl in o.clusters_of.values()
              if cl[0].categories and (today - cl[0].published.astimezone(o.tz).date()).days < 7]
    f = {"city": city["name"], "n": len(leads7)}
    if not leads7:
        return f
    cats = Counter(l.categories[0] for l in leads7).most_common()
    top_n = cats[0][1]
    f["leaders"] = [c for c, k in cats if k == top_n]
    f["top_n"] = top_n
    f["rest"] = [(c, k) for c, k in cats if k < top_n][:3]
    f["places"] = Counter(name for l in leads7 for d, name in l.places).most_common(4)
    dists = Counter(d for l in leads7 for d in l.districts if d in city["districts"]).most_common()
    f["dists"] = dists if len(dists) > 1 else []
    f["victims"] = profile(leads7)["victims"]
    cp = profile([l for l in leads7 if l.categories[0] == "Cyber fraud"])
    f["losses"] = cp["losses"]
    f["top"] = preds[0] if preds else None
    return f


def city_insights(o, preds, city) -> list[str]:
    """A short briefing: what dominates, where, who, how much, and what changed."""
    f = city_facts(o, preds, city)
    if not f["n"]:
        return [f"No incidents reported in and around {city['name']} in the last 7 days."]
    n, top_n, leaders, rest = f["n"], f["top_n"], f["leaders"], f["rest"]
    line = f"{n} incidents reported in and around {city['name']} this week. "
    if len(leaders) == 1:
        line += f"{leaders[0]} leads with {top_n} ({top_n / n * 100:.0f}%)"
    else:
        line += (", ".join(leaders[:-1]) + f" and {leaders[-1].lower()} are level with {top_n} each").capitalize()
    if rest:
        line += ("; then " if len(leaders) > 1 else ", followed by ") + ", ".join(f"{c.lower()} ({k})" for c, k in rest)
    out = [line + "."]
    if f["places"]:
        out.append("Localities named most often: " + ", ".join(f"{p} ({k})" if k > 1 else p for p, k in f["places"]) + ".")
    if f["dists"]:
        out.append("By district: " + ", ".join(f"{d} {k}" for d, k in f["dists"]) + ".")
    if f["victims"]:
        out.append("Most often targeted or affected: " + ", ".join(f["victims"]) + ".")
    if f["losses"]:
        out.append(f"Cyber fraud losses named in reports: {fmt_rupees(sum(f['losses']))} across {len(f['losses'])} case"
                   f"{'s' if len(f['losses']) != 1 else ''}; the largest single loss was {fmt_rupees(max(f['losses']))}.")
    top = f["top"]
    if top:
        out.append(f"Most likely next week: {top['category'].lower()} {('around ' + ', '.join(top['places'][:2])) if top['places'] else 'in ' + top['district']} "
                   f"(about {top['expected']:.0f}, evidence {top['evidence_grade'].lower()}).")
    return out
