"""Operational read-outs: cache effectiveness and AI spend."""

import datetime

from fastapi import APIRouter, Depends

from app.cache import cache
from app.config import AI_DAILY_QUOTA
from app.db import connect
from app.quota import ai_calls_today
from app.security import current_user

router = APIRouter(tags=["admin"])


@router.get("/cache-stats")
def cache_stats():
    return cache.stats()


@router.get("/usage")
def usage(user_id: str = Depends(current_user)):
    """This user's AI spend: today's count against the quota, and a 7-day
    breakdown from the cost log."""
    since = (datetime.date.today() - datetime.timedelta(days=6)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            "SELECT day, COUNT(*) AS calls, "
            "       SUM(COALESCE(input_tokens, 0)) AS input_tokens, "
            "       SUM(COALESCE(output_tokens, 0)) AS output_tokens, "
            "       SUM(repairs) AS repairs, "
            "       SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END) AS failures "
            "FROM llm_calls WHERE user_id = ? AND day >= ? "
            "GROUP BY day ORDER BY day",
            (user_id, since),
        ).fetchall()
    return {
        "today": {"calls": ai_calls_today(user_id), "quota": AI_DAILY_QUOTA},
        "last_7_days": [dict(r) for r in rows],
    }
