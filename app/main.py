"""FinSight Insights API - capstone ("Your 10x Solution").

A market-data and financial-coaching service for beginners. It holds the AI
key, collects Indian-market data politely, turns it into plain-English
explanations, and produces a weekly PDF digest on a schedule.

    uv run python -m app.seed              # demo data
    uv run uvicorn app.main:app --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import ALLOWED_ORIGINS
from app.db import init_db
from app.routes import admin, coach, learn, market, watchlist


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="FinSight Insights API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(HTTPException)
async def _http_exc(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def _validation_exc(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {"msg": "invalid request"}
    field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    return JSONResponse(
        status_code=400,
        content={"error": f"{field}: {first['msg']}" if field else first["msg"]},
    )


@app.get("/health", tags=["admin"])
def health():
    return {"status": "ok"}


app.include_router(market.router)
app.include_router(coach.router)
app.include_router(learn.router)
app.include_router(watchlist.router)
app.include_router(admin.router)
