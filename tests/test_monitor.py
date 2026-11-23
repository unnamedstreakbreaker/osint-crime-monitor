"""Run with:  python -m unittest discover tests"""
import unittest
from datetime import datetime, timedelta, timezone

from osint_monitor.analysis import category_trends, cluster
from osint_monitor.classifier import classify
from osint_monitor.fetcher import NewsItem, parse_feed

GNEWS_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>"Telangana police" - Google News</title>
<item><title>Cyberabad police bust fake trading app racket, 9 held - Sample Outlet</title>
<link>https://news.google.com/rss/articles/abc</link>
<pubDate>Mon, 23 Nov 2026 06:30:00 GMT</pubDate>
<description>&lt;a href="x"&gt;Cyberabad police bust fake trading app racket&lt;/a&gt;</description>
<source url="https://example.com">Sample Outlet</source></item>
</channel></rss>"""

HINDU_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Andhra Pradesh</title>
<item><title><![CDATA[ 300 kg ganja seized in Visakhapatnam ]]></title>
<link>https://example.com/ganja</link>
<description><![CDATA[ <p>Police seized ganja under NDPS Act.</p> ]]></description>
<pubDate>Mon, 23 Nov 2026 10:00:00 +0530</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>CERT-In advisory on new APK scam</title><link href="https://example.com/a"/>
<updated>2026-11-22T08:00:00Z</updated><summary>Beware of fake apps</summary></entry></feed>"""


def item(title, hours_ago=1, summary="", now=None):
    now = now or datetime.now(timezone.utc)
    return NewsItem(title=title, link="https://x/" + title, summary=summary,
                    published=now - timedelta(hours=hours_ago), source="t", feed="t")


class ParserTests(unittest.TestCase):
    def test_google_news_splits_source(self):
        [it] = parse_feed(GNEWS_RSS, "g")
        self.assertEqual(it.source, "Sample Outlet")
        self.assertTrue(it.title.startswith("Cyberabad police bust"))
        self.assertEqual(it.published.tzinfo is not None, True)

    def test_cdata_and_html_cleaned(self):
        [it] = parse_feed(HINDU_RSS, "h")
        self.assertEqual(it.title, "300 kg ganja seized in Visakhapatnam")
        self.assertEqual(it.summary, "Police seized ganja under NDPS Act.")

    def test_atom(self):
        [it] = parse_feed(ATOM, "a")
        self.assertEqual(it.link, "https://example.com/a")


class ClassifierTests(unittest.TestCase):
    def test_cyber_fraud_with_district(self):
        it = classify(item("Vizag pensioner loses Rs 1.2 crore in digital arrest scam"))
        self.assertEqual(it.categories[0], "Cyber fraud")
        self.assertEqual(it.districts, ["Visakhapatnam"])
        self.assertEqual(it.state, "Andhra Pradesh")
        self.assertGreaterEqual(it.severity, 4)

    def test_narcotics(self):
        it = classify(item("300 kg ganja seized in Khammam under NDPS Act"))
        self.assertIn("Narcotics", it.categories)
        self.assertEqual(it.state, "Telangana")

    def test_irrelevant_news_uncategorised(self):
        it = classify(item("Hyderabad to host international film festival next month"))
        self.assertEqual(it.categories, [])
        self.assertEqual(it.severity, 0)

    def test_word_boundaries(self):
        # "ied" must not match inside "studied"; "otp" alone is too weak
        it = classify(item("Student studied OTP systems at Warangal college"))
        self.assertEqual(it.categories, [])


class AnalysisTests(unittest.TestCase):
    def test_same_story_clusters_different_city_does_not(self):
        now = datetime.now(timezone.utc)
        a = classify(item("Retired official loses Rs 1.2 crore in digital arrest scam in Visakhapatnam", 2, now=now))
        b = classify(item("Vizag pensioner duped of Rs 1.2 crore in digital arrest fraud", 3, now=now))
        c = classify(item("Hyderabad doctor loses Rs 2.5 crore in digital arrest scam", 4, now=now))
        groups = cluster([a, b, c])
        self.assertEqual(a.cluster_id, b.cluster_id)
        self.assertNotEqual(a.cluster_id, c.cluster_id)
        self.assertEqual(len(groups), 2)

    def test_spike_detection(self):
        now = datetime.now(timezone.utc)
        towns = ["Guntur", "Nellore", "Kurnool", "Ongole"]
        items = [classify(item(f"{t} trader loses Rs {i+3} lakh in cyber fraud", 10 + i, now=now))
                 for i, t in enumerate(towns)]
        cluster(items)
        rows = category_trends(items, now)
        row = next(r for r in rows if r["category"] == "Cyber fraud")
        self.assertEqual(row["current"], 4)
        self.assertTrue(row["spike"])


if __name__ == "__main__":
    unittest.main()
