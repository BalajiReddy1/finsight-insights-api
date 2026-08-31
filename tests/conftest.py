import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.gettempdir())
os.environ["FINSIGHT_DB"] = str(_TMP / "finsight_test.db")
os.environ["REPORTS_DIR"] = str(_TMP / "finsight_test_reports")
os.environ["DEV_AUTH"] = "true"
os.environ["DEV_AUTH_TOKEN"] = "test-token"
os.environ["DEV_USER_ID"] = "test-user"
os.environ["LLM_STUB"] = "true"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["AI_DAILY_QUOTA"] = "3"

import pytest
from fastapi.testclient import TestClient

from app.cache import cache
from app.config import DB_PATH
from app.db import init_db
from app.main import app

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture()
def client():
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()
    cache.clear()  # the in-process cache is a singleton; reset it per test
    with TestClient(app) as c:
        yield c
    if DB_PATH.exists():
        DB_PATH.unlink()
