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

    def test_vizag_unique_area_tags_district(self):
        it = classify(item("Chain snatching in Gajuwaka, two held"))
        self.assertEqual(it.areas, ["Gajuwaka"])
        self.assertIn("Visakhapatnam", it.districts)
        self.assertEqual(it.state, "Andhra Pradesh")

    def test_context_area_needs_vizag_mention(self):
        self.assertEqual(classify(item("Beach road accident in Chennai, one killed")).areas, [])
        it = classify(item("Ganja seized near One Town police station in Visakhapatnam"))
        self.assertIn("One Town / Old Town", it.areas)

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


class ForecastTests(unittest.TestCase):
    def _clusters(self, per_day, cat_title, days, now):
        items = []
        for d in range(days):
            for k in range(per_day(d)):
                items.append(classify(item(f"{cat_title} case {d}-{k} reported", d * 24 + 3, now=now)))
        return {i.item_id: [i] for i in items}

    def test_steady_rate_forecast(self):
        from datetime import timezone as tz
        from osint_monitor.forecast import Outlook
        now = datetime(2026, 11, 23, 12, tzinfo=tz.utc)
        cl = self._clusters(lambda d: 3, "Hyderabad cyber fraud", 30, now)
        o = Outlook(cl, (now - timedelta(days=25)).date(), now.date(), tz.utc)
        p = o.project(o.total)
        self.assertAlmostEqual(p["expected"], 21, delta=1.5)   # 3/day x 7
        self.assertLessEqual(p["low"], 21); self.assertGreaterEqual(p["high"], 21)
        self.assertEqual(o.conf, "High")

    def test_rising_trend_detected(self):
        from datetime import timezone as tz
        from osint_monitor.forecast import Outlook
        now = datetime(2026, 11, 23, 12, tzinfo=tz.utc)
        cl = self._clusters(lambda d: 4 if d < 7 else 1, "Vizag ganja seized", 30, now)
        o = Outlook(cl, (now - timedelta(days=25)).date(), now.date(), tz.utc)
        self.assertEqual(o.project(o.total)["direction"], "up")

    def test_single_story_not_overconfident(self):
        from datetime import timezone as tz
        from osint_monitor.forecast import Outlook
        now = datetime(2026, 11, 23, 12, tzinfo=tz.utc)
        cl = self._clusters(lambda d: 5, "Hyderabad cyber fraud", 30, now)
        one = classify(item("Murder in Kurnool over land dispute", 30, now=now))
        cl[one.item_id] = [one]
        o = Outlook(cl, now.date(), now.date(), tz.utc)      # monitoring started today
        kurnool = next(r for r in o.district_rows(top=20) if r["key"] == "Kurnool")
        self.assertLess(kurnool["p_any"], 0.9)
        self.assertEqual(o.conf, "Low")


class ExplainTests(unittest.TestCase):
    def test_prediction_has_what_why_where(self):
        from datetime import timezone as tz
        from osint_monitor.forecast import Outlook
        from osint_monitor.explain import predictions
        now = datetime(2026, 11, 23, 12, tzinfo=tz.utc)
        titles = ["Gajuwaka man loses Rs {} lakh in digital arrest scam",
                  "MVP Colony retiree loses Rs {} lakh to digital arrest fraudsters in Visakhapatnam"]
        items = [classify(item(titles[k % 2].format(k + 5), 6 + k * 20, now=now)) for k in range(6)]
        o = Outlook({i.item_id: [i] for i in items}, (now - timedelta(days=3)).date(), now.date(), tz.utc)
        [p] = predictions(o, 1, "Visakhapatnam")
        self.assertEqual(p["headline"], "Cyber fraud in Visakhapatnam")
        self.assertIn("digital arrest", p["what"])
        self.assertIn("Gajuwaka", p["where"]); self.assertIn("MVP Colony", p["where"])
        self.assertTrue(any("last 7 days" in w for w in p["why"]))
        self.assertEqual(len(p["evidence"]), 6)
        # all six came from one outlet -> not independent enough to call strong
        self.assertEqual(p["evidence_grade"], "Limited")
        self.assertFalse(p["show_chance"])

    def test_evidence_grades_and_track_record(self):
        from datetime import timezone as tz, date
        from osint_monitor.forecast import Outlook
        from osint_monitor.explain import evidence, track_record, all_for_log
        from osint_monitor.store import Store
        now = datetime(2026, 11, 23, 12, tzinfo=tz.utc)
        items = []
        for k in range(6):
            it = classify(item(f"Hyderabad man loses Rs {k + 3} lakh in digital arrest scam", 6 + k * 30, now=now))
            it.source = ["Outlet A", "Outlet B", "Outlet C"][k % 3]
            items.append(it)
        o = Outlook({i.item_id: [i] for i in items}, (now - timedelta(days=20)).date(), now.date(), tz.utc)
        self.assertEqual(evidence(o, ("Cyber fraud", "Hyderabad"))["grade"], "Strong")
        # log a prediction 9 days ago and score it against what happened
        st = Store(":memory:")
        st.log_predictions(date(2026, 11, 14), [{"category": "Cyber fraud", "district": "Hyderabad",
                                                  "expected": 4, "low": 2, "high": 7, "evidence": "Strong"}])
        tr = track_record(st, o)
        self.assertEqual(tr["n"], 1)
        self.assertEqual(tr["recent"][0]["actual"], 4)      # cases on 17, 18, 19, 20 Nov
        self.assertTrue(tr["recent"][0]["hit"])
        self.assertEqual(all_for_log(o)[0]["category"], "*")


class TeluguTests(unittest.TestCase):
    def test_news_headlines_untouched_and_labels_translated(self):
        from osint_monitor.i18n import translate_page, news
        html = f'<h2>Predictions</h2><h4>{news("Road accidents rise in Vizag")}</h4><script>var x="Predictions"</script>'
        out = translate_page(html, "te")
        self.assertIn("అంచనాలు", out)                          # label translated
        self.assertIn("Road accidents rise in Vizag", out)      # headline kept as published
        self.assertIn('var x="Predictions"', out)               # scripts untouched
        self.assertNotIn("\x00", out)

    def test_prediction_text_in_telugu(self):
        from datetime import timezone as tz
        from osint_monitor.forecast import Outlook
        from osint_monitor.explain import predictions
        from osint_monitor.i18n import te_prediction
        now = datetime(2026, 11, 23, 12, tzinfo=tz.utc)
        items = [classify(item(f"Gajuwaka retiree loses Rs {k + 5} lakh in digital arrest scam", 6 + k * 20, now=now))
                 for k in range(4)]
        o = Outlook({i.item_id: [i] for i in items}, (now - timedelta(days=3)).date(), now.date(), tz.utc)
        p = te_prediction(predictions(o, 1)[0])
        self.assertEqual(p["headline"], "Visakhapatnamలో సైబర్ మోసం")
        self.assertIn("డిజిటల్ అరెస్ట్", p["insight"])
        self.assertIn("Gajuwaka", p["where"])
