"""Per-user daily AI quota, enforced at the boundary.

The `llm_calls` table already records one row per Gemini call with the user and
the day, so the quota check is one COUNT. A user over the limit gets an honest
429 before any model call is made.
"""

import datetime

from fastapi import Depends, HTTPException

from app.config import AI_DAILY_QUOTA
from app.db import connect
from app.security import current_user


def ai_calls_today(user_id: str) -> int:
    today = datetime.date.today().isoformat()
    with connect() as conn:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM llm_calls WHERE user_id = ? AND day = ?",
            (user_id, today),
        ).fetchone()
    return count


def within_quota(user_id: str = Depends(current_user)) -> str:
    """Dependency for AI routes: passes the user id through, or raises 429."""
    if ai_calls_today(user_id) >= AI_DAILY_QUOTA:
        raise HTTPException(
            429,
            detail=f"Daily AI quota of {AI_DAILY_QUOTA} calls reached. Resets at "
            "midnight UTC.",
        )
    return user_id
