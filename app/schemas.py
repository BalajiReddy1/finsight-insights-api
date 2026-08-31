"""Request and response models."""

from pydantic import BaseModel, Field


# --- market insight ---
class InsightItem(BaseModel):
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)


class MarketInsight(BaseModel):
    items: list[InsightItem]


# --- flashcards ---
class FlashcardRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=8000)
    key_points: list[str] = Field(default_factory=list)


class Flashcard(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)


class FlashcardSet(BaseModel):
    cards: list[Flashcard] = Field(min_length=3, max_length=5)


# --- coach ---
class Transaction(BaseModel):
    date: str = ""
    type: str = "debit"
    amount: float = 0
    category: str = "other"
    merchant: str = "unknown"


class Budget(BaseModel):
    category: str = "?"
    current_spend: float = 0
    monthly_limit: float = 1


class Goal(BaseModel):
    title: str = "?"
    saved_amount: float = 0
    target_amount: float = 1


class CoachRequest(BaseModel):
    transactions: list[Transaction] = Field(default_factory=list, max_length=50)
    budgets: list[Budget] = Field(default_factory=list, max_length=20)
    goals: list[Goal] = Field(default_factory=list, max_length=10)
    score: int = Field(default=400, ge=0, le=1000)
    streak: int = Field(default=0, ge=0)


class Quest(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    points: int = Field(ge=10, le=100)


class CoachAdvice(BaseModel):
    mood: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    quests: list[Quest] = Field(min_length=3, max_length=3)


# --- watchlist ---
class WatchlistItem(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    label: str = Field(min_length=1, max_length=60)
