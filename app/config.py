"""Every setting, read only from the environment. Nothing secret is hard-coded."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.environ.get("FINSIGHT_DB", ROOT / "finsight.db"))
REPORTS_DIR = Path(os.environ.get("REPORTS_DIR", ROOT / "reports"))

# --- auth ---
# DEV_AUTH lets a stranger run the service without a Firebase project: any
# request carrying `Authorization: Bearer <DEV_AUTH_TOKEN>` is treated as the
# demo user. Firebase ID-token verification is still used when DEV_AUTH is off.
DEV_AUTH = os.environ.get("DEV_AUTH", "true").lower() == "true"
DEV_AUTH_TOKEN = os.environ.get("DEV_AUTH_TOKEN", "dev-demo-token")
DEV_USER_ID = os.environ.get("DEV_USER_ID", "demo-user")
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "")

# --- LLM (Gemini) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Overridable without a code change: models get retired under you.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
LLM_STUB = os.environ.get("LLM_STUB", "false").lower() == "true"
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "30"))

# --- quotas ---
AI_DAILY_QUOTA = int(os.environ.get("AI_DAILY_QUOTA", "50"))

# --- misc ---
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:8081").split(",")
    if o.strip()
]
SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "true").lower() == "true"
