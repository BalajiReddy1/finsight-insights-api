"""Public market routes. No auth: these numbers are the same for everyone."""

from fastapi import APIRouter, HTTPException, Response

from app.cache import TTL_MARKET_INSIGHT, cache
from app.llm import LLMError, ask_json
from app.market import fetch_quotes
from app.schemas import InsightItem, MarketInsight

router = APIRouter(prefix="/market", tags=["market"])

_INSIGHT_STUB = MarketInsight(
    items=[
        InsightItem(
            title="Stub mode",
            text="LLM_STUB is on, so this commentary is a placeholder.",
        ),
        InsightItem(
            title="Set GEMINI_API_KEY",
            text="Turn LLM_STUB off and set a key to get real commentary.",
        ),
    ]
)


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
    for fifteen minutes. This is the single biggest cost saving in the service.
    """
    cached = cache.get("market:insight")
    if cached is not None:
        _cache_header(response, True)
        return cached

    try:
        quotes, _ = fetch_quotes()
    except Exception as exc:
        raise HTTPException(502, detail=f"Market data unavailable: {exc}")

    summary = ", ".join(
        f"{q['name']} is {'up' if q['change_percent'] >= 0 else 'down'} "
        f"by {abs(q['change_percent']):.2f}%"
        for q in quotes
    )
    prompt = (
        "You are FinSight AI, a friendly financial mentor for Indian college "
        f"students. Today's market data: {summary}. Pick the two most "
        "interesting moves and, for each, write a short engaging insight. "
        'Return a JSON object {"items": [{"title": "...", "text": "..."}, ...]} '
        "with exactly two items. Each title is a short question or statement; "
        "each text is 2 to 3 sentences in plain English with a beginner takeaway."
    )

    try:
        insight = ask_json(
            endpoint="market/insight",
            user_id=None,
            prompt=prompt,
            model_cls=MarketInsight,
            stub=_INSIGHT_STUB,
        )
    except LLMError:
        raise HTTPException(
            502, detail="Could not generate market commentary right now."
        )

    cache.set("market:insight", insight, TTL_MARKET_INSIGHT)
    _cache_header(response, False)
    return insight
