"""Covers the concepts and the scary cases. LLM is stubbed; no network for the
market routes is needed only where noted.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app import llm
from app.main import app

AUTH = {"Authorization": "Bearer test-token"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


# --- concept 3: authentication ---
def test_protected_route_needs_a_token(client):
    r = client.post("/coach/advisor", json={})
    assert r.status_code == 401
    assert r.json() == {"error": "Access token required"}


def test_bad_token_is_rejected(client):
    r = client.get("/watchlist", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


# --- concept 1 + 2: API + database (watchlist persists) ---
def test_watchlist_crud_and_persistence(client):
    assert client.post(
        "/watchlist", headers=AUTH, json={"symbol": "^nsei", "label": "NIFTY 50"}
    ).status_code == 201
    assert client.post(
        "/watchlist", headers=AUTH, json={"symbol": "^NSEI", "label": "dup"}
    ).status_code == 409

    body = client.get("/watchlist", headers=AUTH).json()
    assert body == [
        {"symbol": "^NSEI", "label": "NIFTY 50", "created_at": body[0]["created_at"]}
    ]

    # survives a fresh app instance on the same db file
    with TestClient(app) as fresh:
        assert len(fresh.get("/watchlist", headers=AUTH).json()) == 1

    assert client.delete("/watchlist/^NSEI", headers=AUTH).status_code == 204
    assert client.delete("/watchlist/^NSEI", headers=AUTH).status_code == 404


def test_input_validation_is_400(client):
    r = client.post("/watchlist", headers=AUTH, json={"symbol": ""})
    assert r.status_code == 400
    assert "error" in r.json()


# --- concept 5: LLM stub + cost log ---
def test_stub_llm_route_logs_a_cost_row(client):
    r = client.post("/coach/advisor", headers=AUTH, json={"score": 600})
    assert r.status_code == 200
    assert len(r.json()["quests"]) == 3

    usage = client.get("/usage", headers=AUTH).json()
    assert usage["today"]["calls"] == 1
    assert usage["last_7_days"][0]["calls"] == 1


# --- concept 5: repair retry on malformed model JSON ---
def test_repair_retry_then_success(client, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "LLM_STUB", False)
    monkeypatch.setattr(llm.config, "LLM_STUB", False)

    calls = {"n": 0}
    good = '{"mood":"ok","explanation":"because","quests":[' + ",".join(
        ['{"title":"t","description":"d","points":10}'] * 3
    ) + "]}"

    def fake_call(_contents):
        calls["n"] += 1
        raw = "not json" if calls["n"] == 1 else good
        return raw, {"input_tokens": 5, "output_tokens": 5, "duration_ms": 1}

    monkeypatch.setattr(llm, "_call_model", fake_call)

    r = client.post("/coach/advisor", headers=AUTH, json={"score": 700})
    assert r.status_code == 200
    assert calls["n"] == 2  # one call, one repair
    row = client.get("/usage", headers=AUTH).json()["last_7_days"][0]
    assert row["repairs"] == 1


# --- rate limiting / quota ---
def test_quota_returns_429_when_exceeded(client):
    # vary the input so each call is a real (stubbed) generation, not a cache hit
    for score in (500, 550, 600):  # AI_DAILY_QUOTA is 3 in tests
        r = client.post("/coach/advisor", headers=AUTH, json={"score": score})
        assert r.status_code == 200
    r = client.post("/coach/advisor", headers=AUTH, json={"score": 650})
    assert r.status_code == 429
    assert "quota" in r.json()["error"].lower()


# --- concept 6: PDF report stored on disk, served by link ---
def test_weekly_digest_creates_pdf_and_serves_by_link(client, monkeypatch):
    from app import reports

    # stub the browser render so the test needs no Chrome
    def fake_render(html_str, out_path):
        out_path = out_path.resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"%PDF-1.4 test")
        return out_path

    monkeypatch.setattr(reports, "render_pdf", fake_render)
    monkeypatch.setattr(reports, "_watchlist_quotes", lambda uid: [])
    monkeypatch.setattr(
        reports, "fetch_quotes", lambda: ([{"name": "NIFTY 50", "price": 1.0,
                                            "change_percent": 0.5}], True)
    )

    first = client.post("/reports/weekly-digest", headers=AUTH)
    assert first.status_code == 201
    rid = first.json()["id"]

    again = client.post("/reports/weekly-digest", headers=AUTH)
    assert again.status_code == 200 and again.json()["id"] == rid  # one per day

    meta = client.get(f"/reports/{rid}", headers=AUTH)
    assert meta.status_code == 200 and meta.json()["file"] == f"/reports/{rid}/file"

    dl = client.get(f"/reports/{rid}/file", headers=AUTH)
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/pdf"
    assert dl.content.startswith(b"%PDF")

    assert client.get("/reports/999", headers=AUTH).status_code == 404


# --- concept 7: caching ---
def test_cache_stats_endpoint(client):
    assert set(client.get("/cache-stats").json()) >= {"hits", "misses", "hit_rate"}
