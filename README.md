# osint-crime-monitor: Open-Source Crime & Threat Monitor (AP & Telangana)

**Live brief:** https://unnamedstreakbreaker.github.io/osint-crime-monitor/ (updates every hour)
· JSON feed: https://unnamedstreakbreaker.github.io/osint-crime-monitor/incidents.json

Hosting is done by `.github/workflows/hourly.yml`: every hour GitHub Actions fetches the feeds,
saves history to `data/osint_monitor.db`, and deploys `site/` to GitHub Pages.
Optional: add an `ANTHROPIC_API_KEY` repo secret for Claude summaries.

Reads **public news feeds** every day, picks out crime and security stories, tags each one
with a category, district and severity, merges the same incident reported by several
outlets, detects week-on-week spikes, and produces a one-page **HTML daily brief**.

No external Python packages are needed: it uses only the standard library (Python 3.10+).

## Filters and "Refresh now"

The brief page has a filter bar: **Vizag only**, district, **Vizag area** (Gajuwaka, MVP Colony,
Madhurawada, Pendurthi, One Town…), category, severity, time window (6h to 7 days) and search.
Filters are saved in the link, so you can bookmark a view, e.g.
`https://unnamedstreakbreaker.github.io/osint-crime-monitor/#district=Visakhapatnam`.
Add or rename areas in `SUB_AREAS` in `osint_monitor/config.py`.

**Refresh now** fetches the news immediately instead of waiting for the hourly run.
The page then reloads by itself when the new brief is ready (about 2–3 minutes).

- *Without setup:* the button opens GitHub's "Run workflow" page. Only you, the repo owner, can click it there.
- *One-click for anyone (free, ~10 minutes, recommended):*
  1. GitHub → Settings → Developer settings → Fine-grained tokens → **Generate new token**.
     Repository access: *Only* `osint-crime-monitor`. Permissions: **Actions: Read and write**. Copy the token.
  2. dash.cloudflare.com → Workers & Pages → **Create → Worker** → name it `osint-refresh` → Deploy →
     **Edit code**, paste `refresh-worker/worker.js`, Deploy.
  3. Worker → Settings → Variables and Secrets: add `GITHUB_TOKEN` (Secret), `REPO` =
     `unnamedstreakbreaker/osint-crime-monitor`, `WORKFLOW` = `hourly.yml`,
     `ALLOWED_ORIGIN` = `https://unnamedstreakbreaker.github.io`.
  4. GitHub repo → Settings → Secrets and variables → Actions → **Variables** → New variable
     `OSINT_REFRESH_URL` = your Worker URL (e.g. `https://osint-refresh.<you>.workers.dev`).
  5. Run the workflow once. From then on the button refreshes in one click.

  The token never appears in the web page. The Worker only starts this one workflow, and it won't
  start a run while one is already going or within 5 minutes of the last one.

## Quick start

```bash
# 1. Offline demo on synthetic headlines (no internet needed)
python -m osint_monitor --demo
#    -> reports/brief_YYYYMMDD_demo.html

# 2. Real run on live public feeds
python -m osint_monitor
#    -> reports/brief_YYYYMMDD.html  (history kept in osint_monitor.db)

# Options
python -m osint_monitor --hours 48     # wider incident window
python -m osint_monitor --json         # also export incidents as JSON (for dashboards/APIs)

# Tests
python -m unittest discover tests
```

Run it once a day so the SQLite history builds up. Trend and spike detection needs
about 14 days of data to be meaningful.

**Schedule it**
- Linux/macOS cron, 7:00 AM daily: `0 7 * * * cd /path/osint-monitor && python3 -m osint_monitor`
- Windows: Task Scheduler → `python -m osint_monitor`, "Start in" = project folder

## What's in the brief

| Section | What it shows |
|---|---|
| KPIs | articles scanned, distinct incidents, high/critical count, spikes |
| Trends | incidents per category × state, this week vs last week, **SPIKE** flags |
| District hotspots | top districts/commissionerates by incident count |
| Modus operandi watch | scam techniques in the news (digital arrest, voice clone, APK, mule accounts…), with **NEW** for ones absent last week |
| Incidents | deduplicated list, highest severity first, with "also reported by" |

## How it works

```
RSS feeds ──► fetcher.py ──► classifier.py ──► store.py (SQLite) ──► analysis.py ──► report.py
             (stdlib XML)   keywords → category,   14-day history     cluster dupes     HTML brief
                            district, severity     for trends         trends, hotspots
                            (+ optional Claude)
```

- **Classification** is keyword-weighted, with word boundaries, so it is fast and explainable
  and nothing leaves the machine. Edit `osint_monitor/config.py` to add terms.
- **Severity (1–5)** = the strongest keyword signal, +1 for corroborating terms,
  +1 for scale markers (crore, gang, inter-state, deaths, ≥100 kg…). It is an estimate,
  not an assessment.
- **Deduplication** merges articles within 48 hours that share title words, district,
  category or figures (e.g. the same "Rs 1.2 crore"). Different districts are never merged.
- **Trends** count *incidents*, not articles, so one heavily covered story doesn't look like a crime wave.

## Optional: Claude enrichment

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OSINT_LLM_MODEL=claude-haiku-5-5   # default
python -m osint_monitor
```

Only *new, already-categorised* items are sent, for a neutral one-line summary and a
category/severity check. Use `--no-llm` to switch it off. If the department needs
everything on-premise, point `enrich_with_llm()` at a local model (Ollama, vLLM) instead.

## Customising

All tuning is in `osint_monitor/config.py`:
- `FEEDS`: add official sources (state police press releases, PIB, CERT-In) or more
  Google News queries using the `_gnews("...")` helper
- `DISTRICTS` / `STATE_ALIASES`: retarget to another state
- `CATEGORIES`: keyword → weight
- `EMERGING_TERMS`: scam techniques to watch

Environment variables: `OSINT_DB`, `OSINT_REPORT_DIR`, `OSINT_TZ` (default Asia/Kolkata).

## Scope and responsible use

- **Inputs are public news only.** The tool does not ingest case files, CCTNS data,
  call records or social-media accounts.
- It tracks **incidents and trends, not people**. It deliberately does not extract or profile
  named individuals, and the LLM prompt tells the model to leave private names out.
- News is unverified, so treat the brief as a lead list to corroborate, not as evidence.
- Any official use should go through the department's own IT/security approval.

## Roadmap ideas
- Telugu news sources (Eenadu, Sakshi) with Telugu keyword lists
- Telegram/email delivery of the brief at 7 AM
- Map view of district hotspots
- Feed the "modus operandi watch" into the complaint-triage assistant (project #1)
