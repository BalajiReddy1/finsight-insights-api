"""Market commentary generation, shared by the route and the cron job.

Identical for every user, so the result is cached under one key and one Gemini
call serves everyone (and the scheduler) for fifteen minutes.
"""

from app.cache import TTL_MARKET_INSIGHT, cache
from app.llm import ask_json
from app.market import fetch_quotes
from app.schemas import InsightItem, MarketInsight

STUB = MarketInsight(
    items=[
        InsightItem(title="Stub mode", text="LLM_STUB is on; placeholder text."),
        InsightItem(title="Set GEMINI_API_KEY", text="Turn LLM_STUB off for real."),
    ]
)


def get_market_insight(force: bool = False) -> tuple[MarketInsight, bool]:
    """Return (insight, from_cache)."""
    if not force:
        cached = cache.get("market:insight")
        if cached is not None:
            return cached, True

    quotes, _ = fetch_quotes()
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
    insight = ask_json(
        endpoint="market/insight",
        user_id=None,
        prompt=prompt,
        model_cls=MarketInsight,
        stub=STUB,
    )
    cache.set("market:insight", insight, TTL_MARKET_INSIGHT)
    return insight, False
