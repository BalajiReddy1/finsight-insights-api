# My 10x Solution - Balaji Thukuntala

**Project:** FinSight Insights API
**Repository:** this repo
**Track:** FlyRank Internship, Backend AI Engineering, Capstone

---

## 1. The problem

An Indian college student who is trying to learn about money has to check
several places every day to get a basic read: one app for the NIFTY and SENSEX,
another for the USD/INR rate and gold, a news site for "why did the market move
today," and their own bank app to see what they spent. Nothing joins those up,
nothing explains the numbers at a beginner's level, and nothing turns "here is
your spending and here is the market" into a single plain-English coaching
note. The result is that most students skip the habit entirely.

**Who has this problem:** students and early-career people in India who want to
build financial literacy but do not have a finance background and will not sit
through a Bloomberg terminal.

FinSight is a financial-literacy app built by me with a college group. The app
(React Native) is the group's work; **this capstone is the backend service I
own** - the part that holds the AI key, collects market data, and turns it into
something a beginner can use. I have rebuilt it here as a standalone, hardened,
runnable-by-a-stranger service and added the pieces the internship taught.

## 2. The 10x claim

Getting a useful daily read - Indian index levels, the currency and gold moves,
a beginner-level explanation of the biggest movers, and a personalised money
coaching note - took roughly **15 minutes across four apps**. FinSight Insights
returns the same thing as **one API call in under two seconds** (cached), or as
a **weekly PDF digest** generated on a schedule with no request at all.

## 3. Non-goal

I am not building the React Native front end, any brokerage or trading feature,
or anything touching real money. One backend service, one problem.

## 4. The concepts (from the capstone brief, section 2)

At least five of the seven are required, with at most two swaps. This build
implements **all seven from the first table, so it uses no swaps**.

| # | Concept | Where it lives in the code |
|---|---------|----------------------------|
| 1 | API endpoints | `app/routes/` - typed request/response, correct status codes, `400` on bad input before any work |
| 2 | Database | `app/db.py` + SQLite: the LLM cost log, generated-report metadata, and a per-user watchlist all persist across restarts |
| 3 | Authentication | `app/security.py` - Firebase ID-token verification (issuer + audience checked), plus a documented `DEV_AUTH` bearer mode so a stranger can run it without a Firebase project |
| 4 | Background / cron jobs | `app/jobs.py` - APScheduler: a cron job that pre-warms the market-insight cache every 15 minutes, and a weekly job that renders the digest PDF off the request path |
| 5 | LLM integration with a cost log | `app/llm.py` - one narrow Gemini job per endpoint, output parsed and schema-validated with a single repair retry, and every call appends a structured cost line (model, input/output tokens, duration, repairs) to the database |
| 6 | Reporting (PDF) | `app/reports.py` - `POST /reports/weekly-digest` renders an HTML digest and prints it to a PDF with a headless browser; the file is stored on disk and served by link, never returned as bytes in JSON |
| 7 | Caching logic | `app/cache.py` - in-process TTL cache with per-response-type lifetimes and an `X-Cache: HIT/MISS` header; the market commentary is identical for every user, so one Gemini call serves everyone for 15 minutes |

Four of these (API, Database, Authentication, Caching) come from the first
table, so the "at least 3 from the first table" rule is met without needing any
swap.

### Additional work (stretch items from section 8)

Not required for the concept count, included because they are what makes the
service real:

- **Containerized stack** - `docker compose up` starts the API and its
  scheduler on a clean machine.
- **Test suite** - the scary cases are covered and run with one command: a bad
  token, malformed model JSON that triggers the repair retry, Yahoo Finance
  throttled (stale fallback served), and a user over their AI quota.
- **Rate limiting / quotas** - a per-user daily cap on AI calls, enforced at
  the boundary with an honest `429`, backed by the same cost-log table.

## 5. How to run it

_(filled in at milestone M4)_

## 6. Measuring the 10x

_(one number, before vs after - filled in at M4 once the demo path is fixed)_
