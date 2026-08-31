"""The personalised coach. Auth + daily AI quota."""

from fastapi import APIRouter, Depends, HTTPException, Response

from app.cache import TTL_COACH, cache, make_key
from app.llm import LLMError, ask_json
from app.quota import within_quota
from app.schemas import CoachAdvice, CoachRequest, Quest

router = APIRouter(prefix="/coach", tags=["coach"])

_STUB = CoachAdvice(
    mood="Your finances are a work in progress, and that is fine.",
    explanation="LLM_STUB is on, so this is placeholder coaching.",
    quests=[
        Quest(title="Track a transaction", description="Add one today.", points=10),
        Quest(title="Set a budget", description="Cover your top category.", points=20),
        Quest(title="Finish a module", description="Any Learn module.", points=20),
    ],
)


@router.post("/advisor", response_model=CoachAdvice)
def advisor(
    body: CoachRequest,
    response: Response,
    user_id: str = Depends(within_quota),
):
    """A coaching note plus three quests, targeting weaknesses in the user's
    own data. Cached on the data itself, so reopening the app does not spend a
    call; new advice is generated only when the finances actually change."""
    tx = "\n".join(
        f"  - {t.date or '?'}: {t.type} Rs{t.amount} on {t.category} ({t.merchant})"
        for t in body.transactions[:15]
    ) or "  none"
    budgets = "\n".join(
        f"  - {b.category}: Rs{b.current_spend} / Rs{b.monthly_limit} "
        f"({round(b.current_spend / max(b.monthly_limit, 1) * 100)}% used)"
        for b in body.budgets
    ) or "  none"
    goals = "\n".join(
        f"  - {g.title}: {round(g.saved_amount / max(g.target_amount, 1) * 100)}% "
        f"saved (Rs{g.saved_amount} of Rs{g.target_amount})"
        for g in body.goals[:3]
    ) or "  none"

    key = make_key("coach", user_id, body.score, body.streak, tx, budgets, goals)
    cached = cache.get(key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached

    prompt = f"""You are FinSight Sensei, a sharp, encouraging financial coach for Indian students.
Speak only in English. Tone: direct, motivating, data-driven, like a personal CFO.

FINSIGHT IQ SCORE: {body.score} / 1000
LEARNING STREAK: {body.streak} days

RECENT TRANSACTIONS:
{tx}

BUDGET USAGE THIS MONTH:
{budgets}

SAVINGS GOALS:
{goals}

Return a JSON object with keys:
  "mood": one punchy sentence, max 12 words
  "explanation": 2 to 3 sentences on why the IQ score is {body.score}, referencing specific data points
  "quests": exactly 3 objects, each {{"title": short action, "description": one sentence with the IQ reward, "points": integer 10 to 100}}
Quests must target real weaknesses in the data (over-budget category, missing goals, broken streak); if healthy, focus on wealth growth."""

    try:
        advice = ask_json(
            endpoint="coach/advisor",
            user_id=user_id,
            prompt=prompt,
            model_cls=CoachAdvice,
            stub=_STUB,
        )
    except LLMError:
        raise HTTPException(502, detail="Could not generate coaching right now.")

    cache.set(key, advice, TTL_COACH)
    response.headers["X-Cache"] = "MISS"
    return advice
