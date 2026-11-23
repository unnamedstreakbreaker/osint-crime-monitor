"""Configuration: feeds, regions, categories.

Everything here is public-source. Edit FEEDS / DISTRICTS / CATEGORIES to retarget
the monitor to another state or theme without touching the rest of the code.
"""
import os

DB_PATH = os.environ.get("OSINT_DB", "osint_monitor.db")
REPORT_DIR = os.environ.get("OSINT_REPORT_DIR", "reports")
DISPLAY_TZ = os.environ.get("OSINT_TZ", "Asia/Kolkata")

# Manual "Refresh now" button: URL of the refresh endpoint (Cloudflare Worker,
# see refresh-worker/). Empty = button opens the GitHub Actions page instead.
REFRESH_URL = os.environ.get("OSINT_REFRESH_URL", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "unnamedstreakbreaker/osint-crime-monitor")

# Optional LLM enrichment (summaries + better classification).
# Without a key the monitor runs fully rule-based.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.environ.get("OSINT_LLM_MODEL", "claude-haiku-5-5")

# ---------------------------------------------------------------------------
# Public RSS feeds. Google News search feeds are the easiest way to cover many
# outlets at once; add official sources (state police, PIB, CERT-In) as needed.
# ---------------------------------------------------------------------------
def _gnews(query: str) -> str:
    from urllib.parse import quote_plus
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"

FEEDS = {
    "gnews_ap_police": _gnews("Andhra Pradesh police"),
    "gnews_ts_police": _gnews("Telangana police"),
    "gnews_hyd_cyber": _gnews("Hyderabad cyber crime"),
    "gnews_ap_cyber": _gnews("Andhra Pradesh cyber fraud"),
    "gnews_ts_ganja": _gnews("Telangana ganja seized"),
    "gnews_ap_ganja": _gnews("Andhra Pradesh ganja seized"),
    "gnews_maoist": _gnews("Maoist Telangana OR Andhra Pradesh"),
    "gnews_digital_arrest": _gnews("digital arrest scam"),
    "gnews_vizag_police": _gnews("Visakhapatnam police"),
    "gnews_vizag_crime": _gnews("Vizag crime OR cyber OR ganja"),
    "thehindu_vizag": "https://www.thehindu.com/news/cities/Visakhapatnam/feeder/default.rss",
    "thehindu_ap": "https://www.thehindu.com/news/national/andhra-pradesh/feeder/default.rss",
    "thehindu_ts": "https://www.thehindu.com/news/national/telangana/feeder/default.rss",
}

# ---------------------------------------------------------------------------
# Regions: canonical district -> aliases (lower-case). Covers districts and the
# police commissionerates people actually name in news.
# ---------------------------------------------------------------------------
DISTRICTS = {
    "Andhra Pradesh": {
        "Visakhapatnam": ["visakhapatnam", "vizag", "vishakhapatnam", "gajuwaka"],
        "Anakapalli": ["anakapalli"],
        "Alluri Sitharama Raju": ["alluri sitharama raju", "asr district", "paderu", "araku"],
        "Vizianagaram": ["vizianagaram"],
        "Srikakulam": ["srikakulam"],
        "Parvathipuram Manyam": ["parvathipuram"],
        "East Godavari": ["east godavari", "rajamahendravaram", "rajahmundry"],
        "Kakinada": ["kakinada"],
        "Konaseema": ["konaseema", "amalapuram"],
        "West Godavari": ["west godavari", "bhimavaram"],
        "Eluru": ["eluru"],
        "Krishna": ["krishna district", "machilipatnam"],
        "NTR": ["ntr district", "vijayawada"],
        "Guntur": ["guntur"],
        "Palnadu": ["palnadu", "narasaraopet"],
        "Bapatla": ["bapatla", "chirala"],
        "Prakasam": ["prakasam", "ongole"],
        "Nellore": ["nellore"],
        "Tirupati": ["tirupati", "tirumala", "srikalahasti"],
        "Chittoor": ["chittoor"],
        "Annamayya": ["annamayya", "rayachoti", "madanapalle"],
        "YSR Kadapa": ["kadapa", "ysr district", "proddatur"],
        "Anantapur": ["anantapur", "anantapuramu"],
        "Sri Sathya Sai": ["sri sathya sai", "puttaparthi", "hindupur"],
        "Kurnool": ["kurnool"],
        "Nandyal": ["nandyal"],
        "Amaravati": ["amaravati"],
    },
    "Telangana": {
        "Hyderabad": ["hyderabad", "secunderabad", "old city", "banjara hills", "jubilee hills", "begumpet", "charminar"],
        "Cyberabad": ["cyberabad", "gachibowli", "madhapur", "kukatpally"],
        "Rachakonda": ["rachakonda", "lb nagar", "uppal"],
        "Rangareddy": ["rangareddy", "ranga reddy", "shamshabad", "himayatsagar", "rajendranagar", "narsingi", "shadnagar"],
        "Medchal-Malkajgiri": ["medchal", "malkajgiri"],
        "Sangareddy": ["sangareddy", "patancheru"],
        "Warangal": ["warangal", "hanamkonda", "kazipet"],
        "Karimnagar": ["karimnagar"],
        "Khammam": ["khammam"],
        "Bhadradri Kothagudem": ["bhadradri", "kothagudem", "bhadrachalam"],
        "Nizamabad": ["nizamabad"],
        "Adilabad": ["adilabad"],
        "Nalgonda": ["nalgonda", "miryalaguda"],
        "Mahabubnagar": ["mahabubnagar", "mahbubnagar"],
        "Mulugu": ["mulugu"],
        "Jayashankar Bhupalpally": ["bhupalpally"],
        "Peddapalli": ["peddapalli", "ramagundam"],
        "Siddipet": ["siddipet"],
        "Suryapet": ["suryapet"],
        "Kamareddy": ["kamareddy"],
        "Mancherial": ["mancherial"],
        "Komaram Bheem Asifabad": ["asifabad", "komaram bheem"],
    },
}

# ---------------------------------------------------------------------------
# Sub-areas inside a district (police-station / locality level).
#   "unique":  names that only exist here -> also tags the parent district
#   "context": common names (One Town, Beach Road...) -> only counted when the
#              story already mentions the parent district
# ---------------------------------------------------------------------------
SUB_AREAS = {
    "Visakhapatnam": {
        "unique": {
            "Gajuwaka": ["gajuwaka"],
            "MVP Colony": ["mvp colony", "mvp police"],
            "Madhurawada": ["madhurawada", "pm palem", "kommadi", "midhilapuri"],
            "Rushikonda / Yendada": ["rushikonda", "yendada", "sagar nagar"],
            "Bheemunipatnam": ["bheemunipatnam", "bheemili"],
            "Anandapuram": ["anandapuram"],
            "Pendurthi": ["pendurthi", "chinamushidiwada", "vepagunta"],
            "Simhachalam / Gopalapatnam": ["simhachalam", "gopalapatnam", "adavivaram"],
            "Dwaraka Nagar": ["dwaraka nagar", "dwarakanagar", "dwaraka police"],
            "Maddilapalem": ["maddilapalem"],
            "Seethammadhara": ["seethammadhara", "akkayyapalem"],
            "Arilova": ["arilova", "chinagadili"],
            "Kancharapalem": ["kancharapalem"],
            "Marripalem / NAD": ["marripalem", "nad junction", "nad kotha road"],
            "Allipuram / Jagadamba": ["allipuram", "jagadamba", "suryabagh"],
            "Maharanipeta": ["maharanipeta", "lawsons bay"],
            "Steel Plant / Kurmannapalem": ["steel plant", "ukkunagaram", "kurmannapalem", "vadlapudi"],
            "Duvvada / Aganampudi": ["duvvada", "aganampudi"],
            "Malkapuram / Sriharipuram": ["malkapuram", "sriharipuram"],
            "Visalakshinagar": ["visalakshinagar", "visalakshi nagar"],
            "Kailasagiri": ["kailasagiri"],
        },
        "context": {
            "One Town / Old Town": ["one town", "old town", "1-town"],
            "Two Town": ["two town", "2-town"],
            "Three Town": ["three town", "3-town"],
            "Beach Road / RK Beach": ["beach road", "rk beach", "r.k. beach"],
            "Port area": ["port area", "harbour", "fishing harbour"],
            "Airport": ["airport"],
            "Railway station": ["railway station"],
        },
    },
}

STATE_ALIASES = {
    "Andhra Pradesh": ["andhra pradesh", " a.p.", " ap "],
    "Telangana": ["telangana"],
}

# ---------------------------------------------------------------------------
# Categories: keyword -> weight. Weight feeds the severity score.
# ---------------------------------------------------------------------------
CATEGORIES = {
    "Cyber fraud": {
        "digital arrest": 3, "cyber fraud": 2, "cyber crime": 2, "cybercrime": 2,
        "online fraud": 2, "upi fraud": 2, "otp": 1, "phishing": 2,
        "loan app": 2, "investment scam": 2, "trading scam": 2, "sextortion": 3,
        "part-time job": 1, "task scam": 2, "fake app": 1, "mule account": 2,
        "kyc update": 1, "courier scam": 2, "cyber criminals": 2, "duped": 1,
        "lost rs": 1, "loses rs": 1, "apk": 2, "trading app": 2, "fake trading": 3,
        "fake investment": 2, "malicious link": 2, "fake link": 2, "fraudsters": 2,
        "voice clone": 3, "deepfake": 3, "betting app": 2, "file fraud": 1,
    },
    "Narcotics": {
        "ganja": 2, "narcotic": 2, "ndps": 2, "mdma": 3, "heroin": 3,
        "cocaine": 3, "drug peddler": 2, "drugs seized": 2, "hash oil": 2,
        "eagle": 1, "drug racket": 3, "opium": 2,
    },
    "Left-wing extremism": {
        "maoist": 3, "naxal": 3, "exchange of fire": 3, "ied": 3,
        "encounter": 2, "cpi (maoist)": 3, "surrender": 1, "greyhounds": 2,
    },
    "Law and order": {
        "clash": 2, "riot": 3, "stone pelting": 3, "communal": 3,
        "protest": 1, "bandh": 2, "dharna": 1, "section 163": 2,
        "prohibitory orders": 2, "lathi charge": 2, "mob": 2, "tension": 1,
    },
    "Violent crime": {
        "murder": 3, "murdered": 3, "killed": 2, "stabbed": 2, "attack": 1,
        "robbery": 2, "dacoity": 3, "chain snatching": 2, "kidnap": 3,
        "abducted": 3, "shot dead": 3, "assault": 2, "burglary": 1, "theft": 1,
    },
    "Crimes against women & children": {
        "pocso": 3, "sexual assault": 3, "rape": 3, "dowry": 2, "sexual harassment": 3, "harassed woman": 2,
        "stalking": 2, "acid attack": 3, "child marriage": 2, "trafficking": 3,
        "she teams": 1, "eve teasing": 2,
    },
    "Smuggling & illegal trade": {
        "red sanders": 3, "smuggling": 2, "smuggled": 2, "pds rice": 2,
        "gold seized": 2, "illicit liquor": 2, "sand mining": 2, "hawala": 3,
        "counterfeit": 2, "fake currency": 3, "gutka": 1, "poaching": 2,
    },
    "Advisories & alerts": {
        "advisory": 2, "alert": 1, "cert-in": 3, "warns public": 2, "warn public": 2,
        "police warn": 2, "cautions public": 2,
        "beware": 2, "awareness": 1, "rbi cautions": 2, "new scam": 3,
    },
}

# Terms we watch for as "emerging modus operandi" (shown even if rare).
EMERGING_TERMS = [
    "digital arrest", "deepfake", "voice clone", "ai voice", "qr code",
    "e-sim", "sim swap", "mule account", "crypto", "betting app",
    "courier scam", "task scam", "apk", "screen sharing", "fake police",
]
