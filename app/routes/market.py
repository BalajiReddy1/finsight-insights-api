"""Public market routes. No auth: these numbers are the same for everyone."""

from fastapi import APIRouter, HTTPException, Response

from app.market import fetch_quotes

router = APIRouter(prefix="/market", tags=["market"])


def _cache_header(response: Response, from_cache: bool) -> None:
    response.headers["X-Cache"] = "HIT" if from_cache else "MISS"


@router.get("/pulse")
def market_pulse(response: Response):
    """The current levels: NIFTY 50, SENSEX, gold, USD/INR."""
    try:
        quotes, from_cache = fetch_quotes()
    except Exception as exc:
        raise HTTPException(502, detail=f"Market data unavailable: {exc}")

    _cache_header(response, from_cache)
    return [
        {
            "name": q["name"],
            "price": round(q["price"], 2),
            "change_percent": round(q["change_percent"], 2),
            "direction": "up" if q["change_percent"] >= 0 else "down",
        }
        for q in quotes
    ]
