"""One narrow Gemini job per call, behind validation and a cost log.

`ask_json(...)` builds a prompt, calls Gemini, strips any code fence, parses
the JSON, validates it with a Pydantic model, and - if that fails - makes
exactly one repair call handing the model its own broken output and the
validation error. Every call, success or failure, appends a structured line to
the `llm_calls` table: model, token counts, duration, repair count. That table
is both the cost log and the quota counter.

Set LLM_STUB=true to build and test without spending a call.
"""

import datetime
import json
import re
import time
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app import config
from app.db import connect

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
T = TypeVar("T", bound=BaseModel)

STYLE_RULES = (
    "Write in English only, no Hindi or Hinglish. "
    "Do not use emojis or any pictographic characters. "
    "Do not use em dashes; use a comma, colon or semicolon."
)


class LLMError(Exception):
    """The model could not produce valid output after one repair attempt."""


@lru_cache(maxsize=1)
def _client():
    """One client, held for the process. Building it per call let CPython GC
    the temporary between `.models` and `.send`, closing its httpx client."""
    from google import genai

    if not config.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=config.GEMINI_API_KEY)


def _extract_json(text: str) -> str:
    fenced = _FENCE.search(text)
    if fenced:
        return fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    lstart, lend = text.find("["), text.rfind("]")
    if lstart != -1 and (start == -1 or lstart < start):
        start, end = lstart, lend
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


def _log_call(
    *, user_id, endpoint, meta, repairs, ok
) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    with connect() as conn:
        conn.execute(
            "INSERT INTO llm_calls "
            "(user_id, endpoint, model, input_tokens, output_tokens, "
            " duration_ms, repairs, ok, created_at, day) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                endpoint,
                config.GEMINI_MODEL,
                meta.get("input_tokens"),
                meta.get("output_tokens"),
                meta.get("duration_ms"),
                repairs,
                1 if ok else 0,
                now.isoformat(timespec="seconds"),
                now.date().isoformat(),
            ),
        )


def _call_model(contents: str) -> tuple[str, dict]:
    started = time.monotonic()
    res = _client().models.generate_content(
        model=config.GEMINI_MODEL, contents=contents
    )
    usage = getattr(res, "usage_metadata", None)
    meta = {
        "input_tokens": getattr(usage, "prompt_token_count", None),
        "output_tokens": getattr(usage, "candidates_token_count", None),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }
    return (res.text or "").strip(), meta


def ask_json(
    *,
    endpoint: str,
    user_id: str | None,
    prompt: str,
    model_cls: type[T],
    stub: T,
) -> T:
    """Return a validated `model_cls`. Raises LLMError on unrecoverable failure."""
    if config.LLM_STUB:
        _log_call(
            user_id=user_id,
            endpoint=endpoint,
            meta={"input_tokens": 0, "output_tokens": 0, "duration_ms": 0},
            repairs=0,
            ok=True,
        )
        return stub

    full_prompt = f"{prompt}\n\nStyle rules: {STYLE_RULES}\nReturn only the JSON."
    raw, meta = _call_model(full_prompt)
    repairs = 0
    try:
        return model_cls.model_validate_json(_extract_json(raw))
    except (ValidationError, json.JSONDecodeError, ValueError) as first_error:
        repairs = 1
        repair_prompt = (
            f"{full_prompt}\n\nYour previous answer was:\n{raw}\n\n"
            f"It was rejected for this reason:\n{first_error}\n"
            "Return only corrected JSON matching the schema."
        )
        repaired, meta = _call_model(repair_prompt)
        try:
            result = model_cls.model_validate_json(_extract_json(repaired))
            _log_call(user_id=user_id, endpoint=endpoint, meta=meta,
                      repairs=repairs, ok=True)
            return result
        except (ValidationError, json.JSONDecodeError, ValueError) as second_error:
            _log_call(user_id=user_id, endpoint=endpoint, meta=meta,
                      repairs=repairs, ok=False)
            raise LLMError(str(second_error)) from second_error
    finally:
        if repairs == 0:
            _log_call(user_id=user_id, endpoint=endpoint, meta=meta,
                      repairs=0, ok=True)
