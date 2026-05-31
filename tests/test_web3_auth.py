"""Tests for Web3 Auth Flow — SIWE (Sign-In With Ethereum) + JWT."""

import os
import json
import tempfile
import pytest
from httpx import AsyncClient, ASGITransport

from agentsafe.api.server import app
from agentsafe.safe_agent import SafeAgent

from eth_account import Account
import jwt

# Generate a random test wallet
TEST_ACCOUNT = Account.create()
TEST_WALLET = TEST_ACCOUNT.address.lower()
TEST_PK = TEST_ACCOUNT.key.hex()


@pytest.fixture(autouse=True)
def tmp_db():
    """Use a temporary DB for each test."""
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test_db.json")
        old = os.environ.get("AGENTSAFE_DB_PATH")
        os.environ["AGENTSAFE_DB_PATH"] = db_path
        yield
        if old:
            os.environ["AGENTSAFE_DB_PATH"] = old
        else:
            os.environ.pop("AGENTSAFE_DB_PATH", None)


@pytest.mark.asyncio
async def test_get_nonce():
    """GET /auth/nonce returns a nonce and message for the wallet."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/auth/nonce?wallet_address={TEST_WALLET}")
        assert resp.status_code == 200
        data = resp.json()
        assert "nonce" in data
        assert "message" in data
        assert data["message"].startswith("agentsafe.app wants you to sign in")
        assert TEST_WALLET in data["message"]


@pytest.mark.asyncio
async def test_sign_and_get_jwt():
    """Full flow: get nonce → sign → POST /auth/sign → JWT token."""
    # 1. Get nonce
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        nonce_resp = await client.get(f"/auth/nonce?wallet_address={TEST_WALLET}")
        assert nonce_resp.status_code == 200
        message = nonce_resp.json()["message"]

    # 2. Sign the message
    msg_bytes = message.encode()
    from eth_account.messages import encode_defunct
    signed = TEST_ACCOUNT.sign_message(encode_defunct(text=message))

    # 3. Submit signature
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        sign_resp = await client.post("/auth/sign", json={
            "wallet_address": TEST_WALLET,
            "signature": signed.signature.hex(),
        })
        assert sign_resp.status_code == 200
        data = sign_resp.json()
        assert "token" in data
        assert data["wallet_address"] == TEST_WALLET

    # 4. Verify the JWT
    from agentsafe.api.server import JWT_SECRET, JWT_ALGORITHM
    payload = jwt.decode(data["token"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == TEST_WALLET
    assert payload["type"] == "session"


@pytest.mark.asyncio
async def test_auth_required_for_api():
    """Endpoints reject requests without a valid token."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/status")
        assert resp.status_code == 401

        resp = await client.post("/v1/check", json={"url": "http://x.com", "amount": 0.01})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_full_authed_flow():
    """Get token → use it to call /v1/status."""
    # Authenticate
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        nonce_resp = await client.get(f"/auth/nonce?wallet_address={TEST_WALLET}")
        message = nonce_resp.json()["message"]

    from eth_account.messages import encode_defunct
    signed = TEST_ACCOUNT.sign_message(encode_defunct(text=message))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        sign_resp = await client.post("/auth/sign", json={
            "wallet_address": TEST_WALLET,
            "signature": signed.signature.hex(),
        })
        token = sign_resp.json()["token"]

    # Use token to get status
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status_resp = await client.get(
            "/v1/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["wallet_address"] == TEST_WALLET
        assert data["daily_budget"] == "1.00"


@pytest.mark.asyncio
async def test_nonce_replay_protection():
    """A nonce can only be used once. Second sign should fail."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        nonce_resp = await client.get(f"/auth/nonce?wallet_address={TEST_WALLET}")
        message = nonce_resp.json()["message"]

    from eth_account.messages import encode_defunct
    signed = TEST_ACCOUNT.sign_message(encode_defunct(text=message))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First use — should work
        r1 = await client.post("/auth/sign", json={
            "wallet_address": TEST_WALLET,
            "signature": signed.signature.hex(),
        })
        assert r1.status_code == 200

        # Get a NEW nonce for the same wallet
        n2 = await client.get(f"/auth/nonce?wallet_address={TEST_WALLET}")
        msg2 = n2.json()["message"]
        signed2 = TEST_ACCOUNT.sign_message(encode_defunct(text=msg2))

        # Try reusing the OLD signature — should fail
        r2 = await client.post("/auth/sign", json={
            "wallet_address": TEST_WALLET,
            "signature": signed.signature.hex(),
        })
        assert r2.status_code == 401  # Invalid signature for new nonce
