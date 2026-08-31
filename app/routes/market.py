"""Public market routes. No auth: these numbers are the same for everyone."""

from fastapi import APIRouter, HTTPException, Response

from app.insight import get_market_insight
from app.llm import LLMError
from app.market import fetch_quotes
from app.schemas import MarketInsight

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


@router.get("/insight", response_model=MarketInsight)
def market_insight(response: Response):
    """Two beginner-level explanations of today's biggest moves.

    Identical for every user, so one Gemini call is cached and serves everyone
    (and the scheduler) for fifteen minutes.
    """
    try:
        insight, from_cache = get_market_insight()
    except LLMError:
        raise HTTPException(502, detail="Could not generate market commentary.")
    except Exception as exc:
        raise HTTPException(502, detail=f"Market data unavailable: {exc}")
    _cache_header(response, from_cache)
    return insight
