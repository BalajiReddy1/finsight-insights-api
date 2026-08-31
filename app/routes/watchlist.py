"""A user's followed tickers. Auth + database (real persistence)."""

import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.db import connect
from app.schemas import WatchlistItem
from app.security import current_user

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("")
def list_watchlist(user_id: str = Depends(current_user)):
    with connect() as conn:
        rows = conn.execute(
            "SELECT symbol, label, created_at FROM watchlist "
            "WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def add_watchlist(item: WatchlistItem, user_id: str = Depends(current_user)):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO watchlist (user_id, symbol, label, created_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, item.symbol.upper(), item.label, now),
            )
        except Exception:
            raise HTTPException(409, detail=f"{item.symbol} is already watched")
    return {"symbol": item.symbol.upper(), "label": item.label}


@router.delete("/{symbol}", status_code=204)
def remove_watchlist(symbol: str, user_id: str = Depends(current_user)):
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND symbol = ?",
            (user_id, symbol.upper()),
        )
    if cur.rowcount == 0:
        raise HTTPException(404, detail=f"{symbol} is not on the watchlist")
