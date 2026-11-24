"""Fetch and parse public RSS / Atom feeds using only the standard library."""
from __future__ import annotations

import hashlib
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

USER_AGENT = "Mozilla/5.0 (OSINT-Monitor/0.1; public news research)"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass
class NewsItem:
    title: str
    link: str
    summary: str
    published: datetime
    source: str
    feed: str
    item_id: str = ""
    # filled in by the classifier
    categories: list[str] = field(default_factory=list)
    state: str = ""
    districts: list[str] = field(default_factory=list)
    areas: list[str] = field(default_factory=list)
    places: list[tuple[str, str]] = field(default_factory=list)   # (district, locality named in the story)
    severity: int = 0
    matched_terms: list[str] = field(default_factory=list)
    llm_summary: str = ""
    cluster_id: str = ""

    def __post_init__(self):
        if not self.item_id:
            key = (self.link or self.title).strip().lower()
            self.item_id = hashlib.sha1(key.encode()).hexdigest()[:16]

    @property
    def text(self) -> str:
        return f"{self.title}. {self.summary}"


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(_TAG_RE.sub(" ", text))
    return _WS_RE.sub(" ", text).strip()


def strip_source(title: str, source: str) -> str:
    """Google News appends ' - Outlet' to titles; drop it (also a cut-off ' -' tail)."""
    if source and title.endswith(" - " + source):
        title = title[: -len(source) - 3]
    return title.rstrip(" -–")


def _parse_date(value: str | None) -> datetime:
    if value:
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                dt = None
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_feed(xml_bytes: bytes, feed_name: str) -> list[NewsItem]:
    root = ET.fromstring(xml_bytes)
    items: list[NewsItem] = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        fields: dict[str, str] = {}
        for child in node:
            name = _local(child.tag)
            if name == "link":
                fields.setdefault("link", (child.text or child.get("href") or "").strip())
            elif name == "source":
                fields["source"] = clean(child.text)
            else:
                fields.setdefault(name, child.text or "")
        title = clean(fields.get("title"))
        if not title:
            continue
        source = fields.get("source", "")
        # Google News titles look like "Headline - Outlet"
        if not source and " - " in title:
            title, source = title.rsplit(" - ", 1)
        items.append(NewsItem(
            title=strip_source(title, source),
            link=fields.get("link", ""),
            summary=clean(fields.get("description") or fields.get("summary") or fields.get("content")),
            published=_parse_date(fields.get("pubDate") or fields.get("published") or fields.get("updated")),
            source=source or ("The Hindu" if feed_name.startswith("thehindu") else feed_name),
            feed=feed_name,
        ))
    return items


def fetch_feed(url: str, feed_name: str, timeout: int = 20) -> list[NewsItem]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return parse_feed(resp.read(), feed_name)


def fetch_all(feeds: dict[str, str], log=print) -> list[NewsItem]:
    all_items: list[NewsItem] = []
    for name, url in feeds.items():
        try:
            items = fetch_feed(url, name)
            log(f"  [ok]   {name}: {len(items)} items")
            all_items.extend(items)
        except Exception as exc:  # one bad feed must not stop the run
            log(f"  [fail] {name}: {exc.__class__.__name__}: {exc}")
    return all_items
