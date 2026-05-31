"""Tests for the agentsafe FastAPI backend."""
import os
import pytest
from fastapi.testclient import TestClient

# Remove stale DB before tests
DB_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "src",
    "agentsafe",
    "api",
    "db.json",
)
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

from agentsafe.api.server import app

client = TestClient(app)

USER1_KEY = "***"
USER2_KEY = "sk-demo-agent42-456"
BASE_URL = "https://api.openai.com/v1/chat"


def _auth_headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def test_unauthenticated_request():
    """Requests without a valid Bearer token should be rejected."""
    r = client.get("/v1/status")
    assert r.status_code == 403

    r = client.post("/v1/check", json={"url": BASE_URL, "amount": 0.05})
    assert r.status_code == 403


def test_status_with_valid_key():
    r = client.get("/v1/status", headers=_auth_headers(USER1_KEY))
    assert r.status_code == 200
    body = r.json()
    assert body["api_key"] == USER1_KEY
    assert "daily_budget" in body
    assert "remaining" in body


def test_approved_spend():
    r = client.post(
        "/v1/check",
        json={"url": BASE_URL, "amount": 0.10},
        headers=_auth_headers(USER1_KEY),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is True
    assert "payment_header" in body


def test_budget_exceeded():
    # USER2 has $0.50 budget. Try to spend $400.
    r = client.post(
        "/v1/check",
        json={"url": BASE_URL, "amount": 400.0},
        headers=_auth_headers(USER2_KEY),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is False
    assert "reason" in body


def test_spend_decrements_budget():
    r = client.post(
        "/v1/check",
        json={"url": BASE_URL, "amount": 0.20},
        headers=_auth_headers(USER1_KEY),
    )
    assert r.json()["allowed"] is True

    status = client.get("/v1/status", headers=_auth_headers(USER1_KEY)).json()
    # Started with $1.00, spent $0.20 + $0.10 from earlier test = $0.70
    assert float(status["spent"]) >= 0.20


def test_multi_user_isolation():
    """Spend by USER1 must not affect USER2's budget."""
    r2_before = client.get("/v1/status", headers=_auth_headers(USER2_KEY)).json()

    # Spend on USER1
    client.post(
        "/v1/check",
        json={"url": BASE_URL, "amount": 0.30},
        headers=_auth_headers(USER1_KEY),
    )

    r2_after = client.get("/v1/status", headers=_auth_headers(USER2_KEY)).json()
    assert r2_before["spent"] == r2_after["spent"]


def test_invalid_token():
    r = client.get("/v1/status", headers=_auth_headers("sk-invalid-key-999"))
    assert r.status_code == 403
