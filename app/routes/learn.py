"""Flashcard generation for a learning module. Auth + daily AI quota."""

from fastapi import APIRouter, Depends, HTTPException, Response

from app.cache import TTL_FLASHCARDS, cache, make_key
from app.llm import LLMError, ask_json
from app.quota import within_quota
from app.schemas import Flashcard, FlashcardRequest, FlashcardSet

router = APIRouter(prefix="/learn", tags=["learn"])

_STUB = FlashcardSet(
    cards=[
        Flashcard(question="What is an SIP?", answer="A fixed regular investment."),
        Flashcard(question="Saving vs investing?", answer="Safety vs growth with risk."),
        Flashcard(question="Why start early?", answer="Compounding rewards time."),
    ]
)


@router.post("/flashcards", response_model=FlashcardSet)
def flashcards(
    body: FlashcardRequest,
    response: Response,
    user_id: str = Depends(within_quota),
):
    """Five study flashcards from a module's text. Cached on the module text,
    so the same module serves every user from one generation."""
    key = make_key("flashcards", body.title, body.content, tuple(body.key_points))
    cached = cache.get(key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached

    points = "\n".join(f"- {p}" for p in body.key_points) or "None provided."
    prompt = f"""You are a financial education assistant for Indian students.
From this module, generate exactly 5 flashcards.

MODULE TITLE: {body.title}
MODULE CONTENT:
{body.content[:2000]}
KEY TAKEAWAYS:
{points}

Return a JSON object {{"cards": [{{"question": "...", "answer": "..."}}, ...]}} with 5 cards.
Questions test understanding (max 15 words), not recall. Answers are 2 to 3 sentences,
simple enough for a college student with no finance background, using Indian context
(SIP, NIFTY, EPF) where it fits."""

    try:
        cards = ask_json(
            endpoint="learn/flashcards",
            user_id=user_id,
            prompt=prompt,
            model_cls=FlashcardSet,
            stub=_STUB,
        )
    except LLMError:
        raise HTTPException(502, detail="Could not generate flashcards right now.")

    cache.set(key, cards, TTL_FLASHCARDS)
    response.headers["X-Cache"] = "MISS"
    return cards
