"""Classify news items: category, state/district, severity.

Rule-based by default (fast, explainable, no data leaves the machine).
If ANTHROPIC_API_KEY is set, items that matched a category are additionally
sent to Claude for a one-line summary and a category sanity check.
"""
from __future__ import annotations

import json
import re
import urllib.request

from . import config
from .fetcher import NewsItem


def _compile(terms):
    return {t: re.compile(r"(?<![a-z])" + re.escape(t.strip()) + r"(?![a-z])") for t in terms}


_CAT_PATTERNS = {cat: _compile(kw) for cat, kw in config.CATEGORIES.items()}
_DISTRICT_PATTERNS = {
    state: {d: list(_compile(aliases).values()) for d, aliases in dists.items()}
    for state, dists in config.DISTRICTS.items()
}
_STATE_PATTERNS = {s: list(_compile(a).values()) for s, a in config.STATE_ALIASES.items()}


def classify(item: NewsItem) -> NewsItem:
    text = " " + item.text.lower() + " "

    scores: dict[str, int] = {}
    peak: dict[str, int] = {}
    matched: list[str] = []
    for cat, patterns in _CAT_PATTERNS.items():
        for term, pat in patterns.items():
            if pat.search(text):
                w = config.CATEGORIES[cat][term]
                scores[cat] = scores.get(cat, 0) + w
                peak[cat] = max(peak.get(cat, 0), w)
                matched.append(term)

    # A category needs score >= 2 so a single weak word ("theft", "otp") doesn't count.
    item.categories = [c for c, s in sorted(scores.items(), key=lambda kv: -kv[1]) if s >= 2]
    item.matched_terms = sorted(set(matched))

    districts, states = [], set()
    for state, dmap in _DISTRICT_PATTERNS.items():
        for district, pats in dmap.items():
            if any(p.search(text) for p in pats):
                districts.append(district)
                states.add(state)
    for state, pats in _STATE_PATTERNS.items():
        if any(p.search(text) for p in pats):
            states.add(state)
    item.districts = districts
    item.state = " / ".join(sorted(states)) if states else "Other/National"

    # Severity 1-5: strongest single signal (1-3), +1 for corroborating terms,
    # +1 for scale markers (big money, organised gang, deaths, many arrests).
    if item.categories:
        main = item.categories[0]
        sev = peak[main]
        if len([t for t in matched if t in config.CATEGORIES[main]]) >= 3:
            sev += 1
        if _SCALE_RE.search(text):
            sev += 1
        item.severity = max(1, min(5, sev))
    else:
        item.severity = 0
    return item


_SCALE_RE = re.compile(
    r"crore|inter-state|interstate|racket|gang|busted|killed|dead|casualt|"
    r"\b\d{2,}\s+(?:arrested|held)|\b\d{3,}\s*kg")


# ---------------------------------------------------------------------------
# Optional LLM enrichment
# ---------------------------------------------------------------------------
_PROMPT = """You are assisting a police intelligence analyst who reads public news.
Given one news item, return JSON only, no prose:
{{"summary": "<one neutral sentence, max 30 words, focus on what happened, where, modus operandi>",
  "categories": [<zero or more of: {cats}>],
  "severity": <0-5 integer; 5 = mass-casualty / major organised crime, 0 = not crime related>}}
Do not include names of private individuals in the summary.

Title: {title}
Text: {summary}"""


def enrich_with_llm(item: NewsItem) -> NewsItem:
    if not config.ANTHROPIC_API_KEY:
        return item
    body = json.dumps({
        "model": config.LLM_MODEL,
        "max_tokens": 300,
        "messages": [{"role": "user", "content": _PROMPT.format(
            cats=", ".join(f'"{c}"' for c in config.CATEGORIES),
            title=item.title, summary=item.summary[:1500])}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"x-api-key": config.ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        raw = "".join(b.get("text", "") for b in data.get("content", []))
        parsed = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        item.llm_summary = parsed.get("summary", "")
        llm_cats = [c for c in parsed.get("categories", []) if c in config.CATEGORIES]
        if llm_cats:
            item.categories = llm_cats
        if isinstance(parsed.get("severity"), int):
            item.severity = max(0, min(5, parsed["severity"]))
    except Exception as exc:
        print(f"  [llm]  skipped '{item.title[:50]}…': {exc}")
    return item
