"""Telugu (తెలుగు) version of the dashboard.

Two parts:
  * Generated text (insights, predictions, why/where, focus) is written natively
    in Telugu from the same facts the English text uses (te_prediction, te_city_insights).
  * Fixed interface labels are swapped with UI_TE after the page is rendered
    (translate_page). News headlines are wrapped in markers and never touched:
    they stay in the language they were published in.
Place names stay in English so filters and links keep working.
"""
from __future__ import annotations

import re

NEWS_START, NEWS_END = "\x00", "\x01"


def news(s: str) -> str:
    """Mark news text (headlines, outlets) so translation leaves it alone."""
    return f"{NEWS_START}{s}{NEWS_END}"


CAT_TE = {
    "Cyber fraud": "సైబర్ మోసం",
    "Narcotics": "మాదకద్రవ్యాలు",
    "Left-wing extremism": "వామపక్ష తీవ్రవాదం",
    "Law and order": "శాంతిభద్రతలు",
    "Violent crime": "హింసాత్మక నేరాలు",
    "Crimes against women & children": "మహిళలు, పిల్లలపై నేరాలు",
    "Smuggling & illegal trade": "స్మగ్లింగ్, అక్రమ వ్యాపారం",
    "Advisories & alerts": "హెచ్చరికలు, సూచనలు",
    "Property crime": "ఆస్తి నేరాలు",
    "Road accidents": "రోడ్డు ప్రమాదాలు",
}

WHAT_TE = {
    "Cyber fraud": "ఆన్‌లైన్ మోసం కేసులు (మోసగాళ్ల చేతిలో డబ్బు పోగొట్టుకోవడం)",
    "Narcotics": "మాదకద్రవ్యాల స్వాధీనం, అరెస్టులు",
    "Left-wing extremism": "మావోయిస్టు కార్యకలాపాలు, ఎదురుకాల్పులు లేదా లొంగుబాట్లు",
    "Law and order": "శాంతిభద్రతల ఘటనలు (ఘర్షణలు, నిరసనలు, బెదిరింపులు)",
    "Violent crime": "హత్యలు, దోపిడీలు, దాడులు లేదా కిడ్నాప్‌లు",
    "Crimes against women & children": "మహిళలు, పిల్లలపై నేరాలు",
    "Smuggling & illegal trade": "స్మగ్లింగ్, అక్రమ వ్యాపార స్వాధీనాలు",
    "Advisories & alerts": "ప్రజలకు పోలీసు లేదా ప్రభుత్వ హెచ్చరికలు",
    "Property crime": "దొంగతనాలు, ఇళ్లలో చోరీలు, చోరీ సొత్తు రికవరీ",
    "Road accidents": "రోడ్డు ప్రమాదాలు, ట్రాఫిక్ మరణాలు",
}

TERM_TE = {
    "digital arrest": "డిజిటల్ అరెస్ట్", "malicious APK files": "హానికరమైన APK ఫైళ్లు",
    "mule bank accounts": "మ్యూల్ బ్యాంక్ ఖాతాలు", "part-time job offers": "పార్ట్-టైమ్ ఉద్యోగ ఆఫర్లు",
    "online task scams": "ఆన్‌లైన్ టాస్క్ మోసాలు", "loan apps": "లోన్ యాప్‌లు",
    "fake trading apps": "నకిలీ ట్రేడింగ్ యాప్‌లు", "investment scams": "పెట్టుబడి మోసాలు",
    "trading scams": "ట్రేడింగ్ మోసాలు", "courier scams": "కొరియర్ మోసాలు", "fake apps": "నకిలీ యాప్‌లు",
    "fake KYC updates": "నకిలీ KYC అప్‌డేట్లు", "OTP sharing": "OTP పంచుకోవడం", "UPI fraud": "UPI మోసం",
    "sextortion": "సెక్స్‌టార్షన్", "phishing": "ఫిషింగ్", "AI voice cloning": "AI వాయిస్ క్లోనింగ్",
    "counterfeit currency": "నకిలీ నోట్లు", "two-wheelers": "ద్విచక్ర వాహనాలు", "lorries": "లారీలు",
    "trucks": "ట్రక్కులు", "cars": "కార్లు", "buses": "బస్సులు", "speeding": "అతివేగం",
    "rash driving": "నిర్లక్ష్య డ్రైవింగ్", "drunk driving": "మద్యం తాగి వాహనం నడపడం",
    "collisions": "వాహనాలు ఢీకొనడం", "vehicles ramming": "వాహనాలు దూసుకెళ్లడం", "pillion riders": "వెనుక కూర్చున్నవారు",
    "hit-and-run": "ఢీకొట్టి పారిపోవడం", "house burglaries": "ఇళ్లలో చోరీలు", "burglaries": "చోరీలు",
    "break-ins": "చొరబడి దొంగతనాలు", "gold theft": "బంగారం చోరీ", "thefts": "దొంగతనాలు",
    "ganja": "గంజాయి", "deepfake": "డీప్‌ఫేక్", "QR codes": "QR కోడ్‌లు", "SIM swap": "సిమ్ స్వాప్",
    "e-SIM fraud": "ఇ-సిమ్ మోసం", "betting apps": "బెట్టింగ్ యాప్‌లు", "screen-sharing apps": "స్క్రీన్ షేరింగ్ యాప్‌లు",
    "fake police calls": "నకిలీ పోలీసు కాల్స్", "crypto": "క్రిప్టో", "voice clone": "వాయిస్ క్లోన్", "ganja trafficking": "గంజాయి రవాణా", "NDPS cases": "NDPS కేసులు", "MDMA": "MDMA",
    "PD Act detentions": "PD చట్టం కింద నిర్బంధాలు", "red sanders": "ఎర్రచందనం", "PDS rice": "రేషన్ బియ్యం",
    "maoist": "మావోయిస్టులు", "IEDs": "IEDలు", "encounter": "ఎదురుకాల్పులు", "surrender": "లొంగుబాటు",
    "murder": "హత్య", "unexplained deaths": "అనుమానాస్పద మరణాలు", "robbery": "దోపిడీ", "kidnap": "కిడ్నాప్",
    "bomb threat": "బాంబు బెదిరింపు", "hoax": "తప్పుడు బెదిరింపు", "dowry": "వరకట్నం", "POCSO cases": "పోక్సో కేసులు",
}

VICTIM_TE = {
    "retired people": "పదవీ విరమణ పొందినవారు", "senior citizens": "వృద్ధులు", "job seekers": "ఉద్యోగార్థులు",
    "students": "విద్యార్థులు", "IT employees": "ఐటీ ఉద్యోగులు", "doctors": "వైద్యులు", "teachers": "ఉపాధ్యాయులు",
    "women": "మహిళలు", "children and minors": "పిల్లలు, మైనర్లు", "farmers": "రైతులు",
    "traders and business owners": "వ్యాపారులు", "young people": "యువత", "devotees": "భక్తులు",
    "tourists": "పర్యాటకులు", "two-wheeler riders and pedestrians": "ద్విచక్ర వాహనదారులు, పాదచారులు",
}

FOCUS_TE = {
    "Cyber fraud": "పోలీసులు వీడియో కాల్‌లో ఎవరినీ 'డిజిటల్ అరెస్ట్' చేయరని ప్రజల్లో అవగాహన; మొదటి గంటలోనే డబ్బు "
                   "నిలిపివేయడానికి 1930 హెల్ప్‌లైన్‌ను ప్రచారం చేయడం; మ్యూల్ బ్యాంక్ ఖాతాలపై నిఘా",
    "Property crime": "{places}లో రాత్రి గస్తీ, బీట్ తనిఖీలు; చోరీ బంగారంపై తాకట్టు, నగల దుకాణాలను అప్రమత్తం చేయడం",
    "Road accidents": "{places}లో అతివేగం, మద్యం తాగి నడపడంపై తనిఖీలు; తరచూ ప్రమాదాలు జరిగే ప్రదేశాల (బ్లాక్ స్పాట్) సమీక్ష",
    "Narcotics": "ఏజెన్సీ ప్రాంతం (పాడేరు, అరకు, చింతపల్లి) నుంచి వచ్చే మార్గాల్లో చెక్‌పోస్టులు; పదే పదే నేరాలు చేసేవారిపై PIT-NDPS చర్యలు",
    "Violent crime": "{places}లో గుర్తించిన భూ, కుటుంబ వివాదాలు ముదరకముందే పర్యవేక్షణ",
    "Crimes against women & children": "{places}లో శక్తి బృందాలు, పాఠశాలలు, కళాశాలల్లో అవగాహన",
    "Smuggling & illegal trade": "హైవే ప్రవేశ మార్గాల్లో వాహన తనిఖీలు; నకిలీ నోట్లపై బ్యాంకులను అప్రమత్తం చేయడం",
    "Law and order": "{places}లో సమావేశాలు, నిరసనలకు ముందస్తు బందోబస్తు",
    "Left-wing extremism": "ఏజెన్సీ మండలాల్లో ఏరియా డామినేషన్ కొనసాగింపు; లొంగుబాట్లపై పర్యవేక్షణ",
}

GRADE_TE = {"Strong": "బలమైనది", "Moderate": "మోస్తరు", "Limited": "పరిమితం"}
CONF_TE = {"Low": "తక్కువ", "Medium": "మధ్యస్థం", "High": "ఎక్కువ"}


def cat(c: str) -> str:
    return CAT_TE.get(c, c)


def term(t: str) -> str:
    return TERM_TE.get(t, t)


def victim(v: str) -> str:
    return VICTIM_TE.get(v, v)


def rupees(v: float) -> str:
    if v >= 1e7:
        return f"₹{v / 1e7:.2f} కోట్లు".replace(".00 ", " ")
    if v >= 1e5:
        return f"₹{v / 1e5:.1f} లక్షలు".replace(".0 ", " ")
    return f"₹{v:,.0f}"


def chance(p: float) -> str:
    if p >= 0.95:
        return "చాలా ఎక్కువ అవకాశం (95% పైగా)"
    if p >= 0.75:
        return f"అవకాశం ఉంది ({p * 100:.0f}%)"
    if p >= 0.4:
        return f"సాధ్యమే ({p * 100:.0f}%)"
    return f"తక్కువ అవకాశం ({p * 100:.0f}%)"


def _where_phrase(places, dist):
    return f"{', '.join(places[:2])} పరిసరాల్లో" if places else f"{dist}లో"


def te_prediction(p: dict) -> dict:
    """Rewrite the text fields of a prediction (from explain + enrich) in Telugu."""
    f = p["facts"]
    c, dist, ct = p["category"], p["district"], cat(p["category"])
    ev = f["ev"]
    why = []
    if f["n7"]:
        s = f"గత 7 రోజుల్లో {dist} నుంచి {f['n7']} {ct} నివేదికలు వచ్చాయి"
        if f["next"]:
            s += f"; ఏ జిల్లాలోనూ ఇన్ని లేవు (తర్వాత {f['next'][0]}: {f['next'][1]})"
        elif f["rank"] and f["nranking"] == 1:
            s += f"; ఈ వారం {ct} నమోదైన ఏకైక జిల్లా ఇదే"
        elif f["rank"]:
            s += f"; {ct} నమోదైన {f['nranking']} జిల్లాల్లో ఇది #{f['rank']}"
        why.append(s + ".")
    else:
        why.append(f"ఈ వారం {dist} నుంచి {ct} నివేదికలు లేవు, కానీ గత 30 రోజుల్లో {f['n30']} ఉన్నాయి; మళ్లీ జరిగే అవకాశం ఉంది.")
    if f["n7"] >= 2:
        l3, p4 = f["last3"], f["prev4"]
        if l3 > p4 * 0.75 + 0.5:
            why.append(f"పెరుగుతోంది: గత 3 రోజుల్లో {l3}, అంతకుముందు 4 రోజుల్లో {p4}.")
        elif l3 * 1.33 + 0.5 < p4:
            why.append(f"తగ్గుతోంది: గత 3 రోజుల్లో {l3}, అంతకుముందు 4 రోజుల్లో {p4}.")
        else:
            why.append(f"స్థిరంగా ఉంది: గత 3 రోజుల్లో {l3}, అంతకుముందు 4 రోజుల్లో {p4}.")
    if f["share"] >= 0.15 and f["cat_total_30"] >= 4:
        why.append(f"ఈ నెల మొత్తం {ct} నివేదికల్లో {f['share'] * 100:.0f}% {dist} నుంచే.")
    if f["methods"]:
        why.append("ఈ నివేదికల్లో ఎక్కువగా కనిపించిన పద్ధతులు: " + ", ".join(term(m) for m in f["methods"]) + ".")
    why.append("అంచనా సంఖ్య = ఇటీవలి రోజువారీ సగటు x 7"
               + (", పర్యవేక్షణ కొత్తది కాబట్టి దీర్ఘకాలిక సగటు వైపు సర్దుబాటు చేశాం" if f["conf"] == "Low" else "")
               + (f", తర్వాత ధోరణి కోసం x{f['trend']:.1f}" if abs(f["trend"] - 1) > 0.05 else "")
               + f". విశ్వసనీయత: {CONF_TE[f['conf']]}.")

    wl = f["where_list"]
    if wl:
        where = "ఎక్కువగా " + ", ".join(f"{n} ({k})" if k > 1 else n for n, k in wl) + " పరిసరాల్లో; ఇటీవలి కేసులు ఇక్కడే నమోదయ్యాయి"
        where += f". మరో {f['unspecified']} నివేదికల్లో జిల్లా పేరు మాత్రమే ఉంది." if f["unspecified"] else "."
    else:
        where = f"నివేదికల్లో {dist} పేరు మాత్రమే ఉంది, నిర్దిష్ట ప్రాంతం పేరు లేదు."

    methods_te = [term(m) for m in p.get("methods", [])]
    victims_te = [victim(v) for v in p.get("victims", [])]
    wp = _where_phrase(p["places"], dist)
    vic = (", ".join(victims_te[:2]) + " లక్ష్యంగా ") if victims_te else ""
    if c == "Cyber fraud":
        ins = f"{wp} {vic}{methods_te[0] if methods_te else 'ఆన్‌లైన్'} మోసాలే ప్రధాన ధోరణి"
        if p.get("losses_n"):
            ins += f"; నివేదికల ప్రకారం {p['losses_n']} కేసుల్లో మొత్తం నష్టం {rupees(p['losses_total'])}"
        ins += "."
    elif c == "Road accidents":
        ins = f"{wp} రోడ్డు ప్రమాదాల్లో మరణాలు, గాయాలు పదే పదే జరుగుతున్నాయి" + (
            f"; బాధితుల్లో ఎక్కువమంది {victims_te[0]}" if victims_te else "") + "."
    elif c == "Property crime":
        ins = (f"{wp} దొంగతనాలు, చోరీలు; అరెస్టులు ఇవి ఒక్కసారి జరిగినవి కాకుండా ముఠాల పనిగా సూచిస్తున్నాయి."
               if f["n7"] >= 2 else f"{wp} దొంగతనాలు, చోరీలు నమోదయ్యాయి; మళ్లీ జరుగుతాయేమో గమనించాలి.")
    elif c == "Narcotics":
        ins = f"{wp} గంజాయి రవాణా; స్వాధీనాలు జిల్లా గుండా సరఫరా మార్గాలను సూచిస్తున్నాయి."
    else:
        ins = f"{wp} {WHAT_TE.get(c, ct)}" + (f" ({', '.join(methods_te[:2])})" if methods_te else "") + " నమోదయ్యాయి."

    places = ", ".join(p["places"][:3]) or dist
    q = dict(p)
    q.update({
        "headline": f"{dist}లో {ct}",
        "category_label": ct,
        "what": WHAT_TE.get(c, ct),
        "why": why, "where": where, "insight": ins,
        "focus": FOCUS_TE.get(c, "").format(places=places),
        "where_short": (", ".join(p["places"][:3]) + f" ({dist})") if p["places"] else f"{dist} (నివేదికల్లో ప్రాంతం పేరు లేదు)",
        "chance_text": chance(p["chance"]),
        "evidence_grade_label": GRADE_TE[p["evidence_grade"]],
        "evidence_text": f"{ev['incidents']} ఘటనలు, {len(ev['outlets'])} మీడియా సంస్థల నుంచి {ev['reports']} వార్తా నివేదికలు"
                         + (f", {ev['text'].rsplit(', ', 1)[-1]}" if ev["days"] else ""),
        "victims_label": ", ".join(victims_te),
        "methods_label": ", ".join(methods_te),
        "losses_label": (f"{p['losses_n']} కేసుల్లో {rupees(p['losses_total'])}" if p.get("losses_n") else ""),
    })
    return q


def te_city_insights(f: dict) -> list[str]:
    if not f["n"]:
        return [f"గత 7 రోజుల్లో {f['city']} మరియు పరిసరాల్లో ఎలాంటి ఘటనలు నమోదు కాలేదు."]
    n, top_n, leaders, rest = f["n"], f["top_n"], f["leaders"], f["rest"]
    line = f"ఈ వారం {f['city']} మరియు పరిసరాల్లో {n} ఘటనలు నమోదయ్యాయి. "
    if len(leaders) == 1:
        line += f"{cat(leaders[0])} {top_n} కేసులతో ({top_n / n * 100:.0f}%) ముందుంది"
    else:
        line += ", ".join(cat(c) for c in leaders) + f" ఒక్కొక్కటి {top_n} కేసులతో సమానంగా ఉన్నాయి"
    if rest:
        line += "; తర్వాత " + ", ".join(f"{cat(c)} ({k})" for c, k in rest)
    out = [line + "."]
    if f["places"]:
        out.append("ఎక్కువగా ప్రస్తావించిన ప్రాంతాలు: " + ", ".join(f"{p} ({k})" if k > 1 else p for p, k in f["places"]) + ".")
    if f["dists"]:
        out.append("జిల్లాల వారీగా: " + ", ".join(f"{d} {k}" for d, k in f["dists"]) + ".")
    if f["victims"]:
        out.append("ఎక్కువగా లక్ష్యంగా లేదా ప్రభావితమైనవారు: " + ", ".join(victim(v) for v in f["victims"]) + ".")
    if f["losses"]:
        out.append(f"నివేదికల్లో పేర్కొన్న సైబర్ మోసం నష్టాలు: {len(f['losses'])} కేసుల్లో {rupees(sum(f['losses']))}; "
                   f"అత్యధిక ఒక్క నష్టం {rupees(max(f['losses']))}.")
    t = f["top"]
    if t:
        out.append(f"వచ్చే వారం ఎక్కువ అవకాశం: {_where_phrase(t['places'], t['district'])} {cat(t['category'])} "
                   f"(సుమారు {t['expected']:.0f}, ఆధారం {GRADE_TE[t['evidence_grade']]}).")
    return out


# ---------------------------------------------------------------------------
# Fixed interface labels. Longest first is applied automatically.
# ---------------------------------------------------------------------------
UI_TE = {
    # header & counters
    "crime and threat board": "నేర, ముప్పు పర్యవేక్షణ బోర్డు",
    "Incidents reported in": "ఇక్కడ నమోదైన ఘటనలు:",
    " city and the surrounding ": " నగరం, పరిసర ",
    " districts, from public news. Updated ": " జిల్లాలు; బహిరంగ వార్తల ఆధారంగా. చివరి అప్‌డేట్ ",
    "IST, every hour.": "IST, ప్రతి గంటకు.",
    "coming soon": "త్వరలో",
    "news reports today": "ఈరోజు వార్తా నివేదికలు",
    "incidents in 24 hours": "24 గంటల్లో ఘటనలు",
    "high or critical": "తీవ్రమైనవి",
    "incidents this week": "ఈ వారం ఘటనలు",
    # tiles
    "Trends and outlook": "ధోరణులు, అంచనా",
    "Open charts": "చార్టులు చూడండి",
    "incidents expected next 7 days": "ఘటనలు వచ్చే 7 రోజుల్లో అంచనా",
    "Confidence: Low": "విశ్వసనీయత: తక్కువ", "Confidence: Medium": "విశ్వసనీయత: మధ్యస్థం",
    "Confidence: High": "విశ్వసనీయత: ఎక్కువ",
    "next week": "వచ్చే వారం",
    "Live incidents": "తాజా ఘటనలు", "See all": "అన్నీ చూడండి",
    "in the last 24 hours": "గత 24 గంటల్లో",
    "No incidents in the last 24 hours.": "గత 24 గంటల్లో ఘటనలు లేవు.",
    " city</h2>": " నగరం</h2>", "incidents in 7 days": "7 రోజుల్లో ఘటనలు",
    "Latest: ": "తాజాది: ", "Areas: ": "ప్రాంతాలు: ",
    "Predictions": "అంచనాలు",
    "Next 7 days. Open for insights: type, where, who, why.": "వచ్చే 7 రోజులు. రకం, ప్రాంతం, బాధితులు, కారణం కోసం తెరవండి.",
    "evidence strong": "ఆధారం బలమైనది", "evidence moderate": "ఆధారం మోస్తరు", "evidence limited": "ఆధారం పరిమితం",
    "In and around": "చుట్టుపక్కల:", "Incidents in the last 7 days": "గత 7 రోజుల్లో ఘటనలు",
    " localities": " ప్రాంతాలు", "Weekly changes": "వారపు మార్పులు",
    "Building<small>baseline</small>": "సిద్ధమవుతోంది<small>ప్రాతిపదిక</small>",
    "Week-on-week changes and spike alerts start after 14 days of monitoring.":
        "14 రోజుల పర్యవేక్షణ తర్వాత వారం వారం మార్పులు, హెచ్చరికలు మొదలవుతాయి.",
    "Scam techniques": "మోసాల పద్ధతులు", "Mentioned in this week's news": "ఈ వారం వార్తల్లో ప్రస్తావించినవి",
    "None mentioned this week.": "ఈ వారం ఏవీ లేవు.",
    "Builds up as incidents come in.": "ఘటనలు వచ్చే కొద్దీ సిద్ధమవుతుంది.",
    # incidents pop-up
    "Incidents</h2>": "ఘటనలు</h2>",
    "Deduplicated, highest severity first. Filters are saved in the page link.":
        "నకిలీలు తొలగించి, తీవ్రమైనవి ముందు. ఫిల్టర్లు పేజీ లింక్‌లో సేవ్ అవుతాయి.",
    ">All<": ">అన్నీ<", " city only<": " నగరం మాత్రమే<",
    "Last 6 hours": "గత 6 గంటలు", "Last 24 hours": "గత 24 గంటలు", "Last 3 days": "గత 3 రోజులు",
    "Last 7 days": "గత 7 రోజులు", "Any severity": "ఏ తీవ్రత అయినా", "Elevated and above": "మోస్తరు, ఆపైన",
    "High and above": "ఎక్కువ, ఆపైన", "Critical only": "అత్యంత తీవ్రమైనవి మాత్రమే",
    "Search, e.g. ganja or digital arrest": "వెతకండి, ఉదా. ganja లేదా digital arrest",
    "No incidents match these filters. Try a longer time window.":
        "ఈ ఫిల్టర్లకు సరిపడే ఘటనలు లేవు. ఎక్కువ కాల వ్యవధి ఎంచుకోండి.",
    "Also reported by": "ఇవి కూడా ప్రచురించాయి:",
    ">Critical<": ">అత్యంత తీవ్రం<", ">High<": ">ఎక్కువ<", ">Elevated<": ">మోస్తరు<",
    ">Moderate<": ">సాధారణ<", ">Low<": ">తక్కువ<",
    # trends pop-up
    "Trends and 7-day outlook": "ధోరణులు, 7 రోజుల అంచనా",
    "Incidents per day and what to expect next week": "రోజువారీ ఘటనలు, వచ్చే వారం అంచనా",
    "Incidents per day in and around": "రోజువారీ ఘటనలు:",
    "Last 30 days and the next 7. Next week: about": "గత 30 రోజులు, వచ్చే 7 రోజులు. వచ్చే వారం: సుమారు",
    "incidents (likely": "ఘటనలు (అవకాశం ఉన్న పరిధి",
    "By category, last 14 days and next 7": "రకాల వారీగా: గత 14 రోజులు, వచ్చే 7 రోజులు",
    "in last 7 days,": "గత 7 రోజుల్లో,", "expected next 7": "వచ్చే 7 రోజుల్లో అంచనా",
    "Show data table": "డేటా పట్టిక చూపించు",
    "Outlook confidence": "అంచనా విశ్వసనీయత",
    "Only a few days of monitoring so far, so treat the outlook as a rough guide.":
        "ఇప్పటివరకు కొన్ని రోజుల పర్యవేక్షణ మాత్రమే, కాబట్టి ఈ అంచనాను సుమారుగా మాత్రమే తీసుకోండి.",
    "A couple of weeks of history. Rates are usable; trends are still settling.":
        "రెండు వారాల చరిత్ర ఉంది. సగటులు ఉపయోగపడతాయి; ధోరణులు ఇంకా స్థిరపడుతున్నాయి.",
    "Three or more weeks of history.": "మూడు వారాలకు పైగా చరిత్ర ఉంది.",
    "Incidents per day": "రోజువారీ ఘటనలు",
    "Before monitoring (incomplete)": "పర్యవేక్షణకు ముందు (అసంపూర్ణం)",
    "Outlook (expected, with likely range)": "అంచనా (సంభావ్య పరిధితో)",
    "Before monitoring: incomplete": "పర్యవేక్షణకు ముందు: అసంపూర్ణం",
    "Next 7 days (outlook)": "వచ్చే 7 రోజులు (అంచనా)",
    ">Today<": ">ఈరోజు<",
    "(before monitoring began: incomplete)": "(పర్యవేక్షణకు ముందు: అసంపూర్ణం)",
    "likely range": "సంభావ్య పరిధి", "(outlook)": "(అంచనా)", "expected ~": "అంచనా ~",
    "▲ rising": "▲ పెరుగుతోంది", "▼ easing": "▼ తగ్గుతోంది", "● steady": "● స్థిరంగా",
    # predictions pop-up
    "What is likely next week, why, and where": "వచ్చే వారం ఏం జరగొచ్చు, ఎందుకు, ఎక్కడ",
    "Key insights for": "ముఖ్యాంశాలు:",
    "Predictions for the next 7 days": "వచ్చే 7 రోజుల అంచనాలు",
    "Strongest evidence first. Limited means fewer than 3 incidents or a single outlet: worth watching, not acting on alone.":
        "బలమైన ఆధారం ఉన్నవి ముందు. 'పరిమితం' అంటే 3 కంటే తక్కువ ఘటనలు లేదా ఒకే మీడియా సంస్థ: గమనించదగినవి, వీటిపై మాత్రమే చర్య తీసుకోవద్దు.",
    "expected next 7 days": "వచ్చే 7 రోజుల్లో అంచనా",
    ">Crime type<": ">నేర రకం<", ">Where<": ">ఎక్కడ<", ">Expected<": ">అంచనా<", ">Who<": ">బాధితులు<",
    ">Method<": ">పద్ధతి<", ">Money lost<": ">నష్టపోయిన డబ్బు<", ">Evidence<": ">ఆధారం<",
    "Not stated in reports": "నివేదికల్లో పేర్కొనలేదు",
    "Suggested focus:": "దృష్టి పెట్టాల్సినవి:",
    "Why this is predicted": "ఈ అంచనాకు కారణం",
    "this is based on": "దీనికి ఆధారం",
    "At least one: ": "కనీసం ఒకటి: ",
    "Evidence: Strong": "ఆధారం: బలమైనది", "Evidence: Moderate": "ఆధారం: మోస్తరు", "Evidence: Limited": "ఆధారం: పరిమితం",
    "Track record: starts": "ట్రాక్ రికార్డ్ మొదలయ్యేది:",
    "Every day, every prediction (not only the ones shown here) is saved before the week happens. From":
        "ప్రతిరోజూ, ప్రతి అంచనా (ఇక్కడ చూపినవే కాదు) ఆ వారం జరగకముందే సేవ్ అవుతుంది. ఈ తేదీ నుంచి:",
    ", each one is checked against the incidents actually reported, and the hit rate appears here, good or bad.":
        ", ప్రతిదాన్ని నిజంగా నమోదైన ఘటనలతో పోల్చి, ఫలితం బాగున్నా బాగోకపోయినా ఇక్కడ చూపిస్తాం.",
    "past predictions": "గత అంచనాలు", "landed inside their stated range.": "చెప్పిన పరిధిలోనే వచ్చాయి.",
    "Method, sources and limits": "పద్ధతి, మూలాలు, పరిమితులు",
    "All combinations at a glance": "అన్ని కలయికలు ఒక్క చూపులో",
    "District outlook": "జిల్లాల వారీ అంచనా",
    ">Category in district<": ">జిల్లాలో నేర రకం<", ">District / Commissionerate<": ">జిల్లా / కమిషనరేట్<",
    ">Last 7 days<": ">గత 7 రోజులు<", ">Expected next 7 (range)<": ">వచ్చే 7 రోజుల అంచనా (పరిధి)<",
    ">Chance of at least one<": ">కనీసం ఒకటి జరిగే అవకాశం<", ">Trend<": ">ధోరణి<",
    # other pop-ups
    "Incidents by district, last 7 days": "జిల్లాల వారీ ఘటనలు, గత 7 రోజులు",
    "Most incidents in the last 7 days": "గత 7 రోజుల్లో ఎక్కువ ఘటనలు",
    ">Incidents<": ">ఘటనలు<", ">Top categories<": ">ప్రధాన రకాలు<",
    "Locality-level incidents and next-week outlook": "ప్రాంతాల వారీ ఘటనలు, వచ్చే వారం అంచనా",
    "This week against last week": "ఈ వారం, గత వారంతో పోలిక",
    ">Category<": ">రకం<", ">This week<": ">ఈ వారం<", ">Last week<": ">గత వారం<", ">Change<": ">మార్పు<",
    "building baseline": "ప్రాతిపదిక సిద్ధమవుతోంది",
    "Modus operandi in this week's news": "ఈ వారం వార్తల్లో నేర పద్ధతులు",
    "Scam and crime techniques mentioned in the news this week.": "ఈ వారం వార్తల్లో ప్రస్తావించిన మోసం, నేర పద్ధతులు.",
    "<b>New</b> means not seen in the previous week.": "<b>కొత్తది</b> అంటే గత వారం కనిపించనిది.",
    "No known techniques mentioned this week.": "ఈ వారం తెలిసిన పద్ధతులేవీ ప్రస్తావించలేదు.",
    # footer
    "Compiled automatically from public news. Unverified: corroborate before acting. Severity is a keyword-based estimate.":
        "బహిరంగ వార్తల నుంచి స్వయంచాలకంగా సేకరించింది. ధృవీకరించలేదు: చర్యకు ముందు నిర్ధారించుకోండి. తీవ్రత కీవర్డ్‌ల ఆధారిత అంచనా.",
    "News headlines are shown as published.": "వార్తా శీర్షికలు ప్రచురించిన భాషలోనే చూపిస్తున్నాం.",
    "Close": "మూసివేయి",
}
UI_TE.update({
    ">incomplete<": ">అసంపూర్ణం<", ">outlook<": ">అంచనా<", ">Note<": ">గమనిక<", ">Day<": ">రోజు<",
    "(likely ": "(పరిధి ", " locality<": " ప్రాంతం<", "Data: <a": "డేటా: <a", "Google News search:": "Google News శోధన:", " section<": " విభాగం<",
    "The Hindu, ": "ది హిందూ, ",
})
UI_TE.update({k: v for k, v in CAT_TE.items()})
UI_TE.update({k.replace("&", "&amp;"): v for k, v in CAT_TE.items() if "&" in k})
_UI_SORTED = sorted(UI_TE.items(), key=lambda kv: -len(kv[0]))
_PROTECT = re.compile(r"(<script.*?</script>|<style.*?</style>|\x00.*?\x01)", re.S)


def translate_page(html: str, lang: str) -> str:
    """Swap fixed labels into Telugu, leaving scripts, styles and news text alone; strip markers."""
    if lang == "te":
        parts = _PROTECT.split(html)
        for i, part in enumerate(parts):
            if part.startswith(("<script", "<style", NEWS_START)):
                continue
            for en, te in _UI_SORTED:
                part = part.replace(en, te)
            parts[i] = part
        html = "".join(parts)
        # chart tooltips: "3 incidents" -> "3 ఘటనలు"
        html = re.sub(r'(data-tip="[^"]*?)(\d+) incidents?', lambda m: f"{m.group(1)}{m.group(2)} ఘటనలు", html)
    return html.replace(NEWS_START, "").replace(NEWS_END, "")
