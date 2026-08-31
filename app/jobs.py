"""Concept 4: work off the request path.

Two scheduled jobs, no request involved:

  refresh_market_insight   every 15 minutes: regenerate the market commentary
                           so the first user of each window gets a warm cache
                           instead of waiting on Gemini.
  weekly_digests           Mondays 08:00 UTC: render the digest PDF for every
                           user who has a watchlist, so it is ready before they
                           ask.

APScheduler runs these in a background thread inside the same process. The
scheduler is started in the app lifespan and can be turned off with
SCHEDULER_ENABLED=false (the tests do).
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db import connect
from app.insight import get_market_insight
from app.reports import generate_digest

_scheduler: BackgroundScheduler | None = None


def refresh_market_insight() -> None:
    try:
        get_market_insight(force=True)
        print("[jobs] market insight refreshed")
    except Exception as exc:
        print(f"[jobs] market insight refresh failed: {exc}")


def weekly_digests() -> None:
    with connect() as conn:
        users = [
            r["user_id"]
            for r in conn.execute(
                "SELECT DISTINCT user_id FROM watchlist"
            ).fetchall()
        ]
    if not users:
        print("[jobs] weekly digests: no users with a watchlist")
        return
    try:
        insight, _ = get_market_insight()
    except Exception as exc:
        print(f"[jobs] weekly digests aborted, no insight: {exc}")
        return
    for user_id in users:
        try:
            rid = generate_digest(user_id, insight)
            print(f"[jobs] weekly digest {rid} for {user_id}")
        except Exception as exc:
            print(f"[jobs] weekly digest failed for {user_id}: {exc}")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        refresh_market_insight,
        CronTrigger.from_crontab("*/15 * * * *"),
        id="refresh_market_insight",
        replace_existing=True,
    )
    _scheduler.add_job(
        weekly_digests,
        CronTrigger.from_crontab("0 8 * * 1"),
        id="weekly_digests",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
