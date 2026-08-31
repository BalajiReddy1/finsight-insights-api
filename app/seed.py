"""Demo data so a stranger sees the service work without setting anything up.

Seeds a watchlist for the demo user (DEV_USER_ID). Safe to run twice.

    uv run python -m app.seed
"""

import datetime

from app.config import DEV_USER_ID
from app.db import connect, init_db

DEMO_WATCHLIST = [
    ("^NSEI", "NIFTY 50"),
    ("^BSESN", "SENSEX"),
    ("INR=X", "USD / INR"),
    ("RELIANCE.NS", "Reliance Industries"),
]


def seed() -> int:
    init_db()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute("DELETE FROM watchlist WHERE user_id = ?", (DEV_USER_ID,))
        conn.executemany(
            "INSERT INTO watchlist (user_id, symbol, label, created_at) "
            "VALUES (?, ?, ?, ?)",
            [(DEV_USER_ID, s, label, now) for s, label in DEMO_WATCHLIST],
        )
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM watchlist WHERE user_id = ?", (DEV_USER_ID,)
        ).fetchone()
    return count


if __name__ == "__main__":
    n = seed()
    print(f"seeded {n} watchlist entries for user {DEV_USER_ID!r}")
