"""Agentsafe Cloud API — FastAPI Backend with Web3 Auth (SiWE).

Authentication flow:
1. GET  /auth/nonce  → server returns random nonce
2. POST /auth/sign   → user signs message + wallet address + signature
3. Server verifies signature → returns JWT session token
4. JWT used in Authorization: Bearer <token> for all API calls

Usage:
    uvicorn agentsafe.api.server:app --host 0.0.0.0 --port 8050
"""

import json
import os
import time
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import jwt
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..safe_agent import SafeAgent, SpendResult

# ── Constants ─────────────────────────────────────────────────────────

JWT_SECRET = os.environ.get("AGENTSAFE_JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

DOMAIN = "agentsafe.app"
CHAIN_ID = 8453  # Base Mainnet

DB_PATH = os.environ.get("AGENTSAFE_DB_PATH", str(Path(__file__).parent / "db.json"))
NONCE_EXPIRY_SECONDS = 300  # 5 minutes

# ── App ───────────────────────────────────────────────────────────────

app = FastAPI(title="Agentsafe Cloud API", version="0.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-Memory Stores ─────────────────────────────────────────────────

# Wallet address -> nonce string (one-time use)
_pending_nonces: Dict[str, str] = {}
# Wallet address -> nonce timestamp
_nonce_timestamps: Dict[str, float] = {}
# Wallet address -> user profile
_user_db: Dict[str, dict] = {}
# Wallet address -> SafeAgent instance
_agent_cache: Dict[str, SafeAgent] = {}


def _load_db() -> Dict[str, dict]:
    if not os.path.exists(DB_PATH):
        return {}
    with open(DB_PATH) as f:
        return json.load(f)


def _save_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with open(DB_PATH, "w") as f:
        json.dump(_user_db, f, indent=2)


# ── SIWE Message ──────────────────────────────────────────────────────

def _build_siwe_message(address: str, nonce: str) -> str:
    """Build a Sign-In With Ethereum style message."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"agentsafe.app wants you to sign in with your Ethereum account:\n"
        f"{address}\n\n"
        f"I accept the Agentsafe Terms of Service: https://agentsafe.app/terms\n\n"
        f"URI: https://agentsafe.app\n"
        f"Version: 1\n"
        f"Chain ID: {CHAIN_ID}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {ts}\n"
        f"Resources:\n"
        f"- https://agentsafe.app/docs\n"
        f"- agentsafe://sessions/*"
    )


def _verify_signature(address: str, message: str, signature: str) -> bool:
    """Verify an Ethereum signature against a message."""
    try:
        msg = encode_defunct(text=message)
        recovered = Account.recover_message(msg, signature=signature)
        return recovered.lower() == address.lower()
    except Exception:
        return False


# ── JWT Helpers ───────────────────────────────────────────────────────

def _create_jwt(wallet_address: str) -> str:
    """Create a JWT session token for the wallet address."""
    payload = {
        "sub": wallet_address.lower(),
        "iat": int(time.time()),
        "exp": int(time.time()) + (JWT_EXPIRY_HOURS * 3600),
        "type": "session",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_jwt(token: str) -> str:
    """Decode and validate a JWT token. Returns the wallet address."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "session":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except (jwt.InvalidTokenError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid token")


def get_wallet(authorization: str = Header(default="")) -> str:
    """FastAPI dependency: extract & validate wallet from Bearer token."""
    token = authorization
    if token.startswith("Bearer "):
        token = token[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return _decode_jwt(token)


# ── User / Agent Helpers ──────────────────────────────────────────────

def _get_or_create_user(wallet_address: str) -> dict:
    """Get or create user profile for a wallet address."""
    addr = wallet_address.lower()
    if addr not in _user_db:
        _user_db[addr] = {
            "wallet": addr,
            "daily_budget": "1.00",
            "currency": "USDC",
            "allowed_destinations": [],
            "kill_switch": False,
            "created_at": time.time(),
            "total_spent": "0.00",
            "session_count": 0,
        }
        _save_db()
    return _user_db[addr]


def _get_agent(wallet_address: str) -> SafeAgent:
    """Get or create SafeAgent instance for a user."""
    addr = wallet_address.lower()
    if addr in _agent_cache:
        return _agent_cache[addr]

    user = _get_or_create_user(addr)
    agent = SafeAgent(
        daily_budget=user["daily_budget"],
        currency=user["currency"],
        allowlist=user["allowed_destinations"],
        storage_path=str(Path("~/.agentsafe").expanduser() / addr[:10]),
    )
    _agent_cache[addr] = agent
    return agent


# ── Auth Endpoints ────────────────────────────────────────────────────

class NonceResponse(BaseModel):
    nonce: str
    message: str
    expires_in: int  # seconds


class SignRequest(BaseModel):
    wallet_address: str
    signature: str


class SignResponse(BaseModel):
    token: str
    wallet_address: str
    expires_in: int


@app.get("/auth/nonce", response_model=NonceResponse)
async def get_nonce(wallet_address: str):
    """Get a one-time nonce to sign. Wallet address identifies the user."""
    addr = wallet_address.lower()

    # Revoke any pending nonce for this address
    if addr in _pending_nonces:
        del _pending_nonces[addr]
        if addr in _nonce_timestamps:
            del _nonce_timestamps[addr]

    nonce = secrets.token_urlsafe(16)
    _pending_nonces[addr] = nonce
    _nonce_timestamps[addr] = time.time()

    message = _build_siwe_message(addr, nonce)

    return NonceResponse(
        nonce=nonce,
        message=message,
        expires_in=NONCE_EXPIRY_SECONDS,
    )


@app.post("/auth/sign", response_model=SignResponse)
async def sign_in(request: SignRequest):
    """Verify signature and return JWT session token."""
    addr = request.wallet_address.lower()

    # Check pending nonce
    if addr not in _pending_nonces:
        raise HTTPException(status_code=400, detail="No pending nonce. Call /auth/nonce first.")

    nonce = _pending_nonces[addr]
    ts = _nonce_timestamps.get(addr, 0)

    # Check expiry
    if time.time() - ts > NONCE_EXPIRY_SECONDS:
        del _pending_nonces[addr]
        del _nonce_timestamps[addr]
        raise HTTPException(status_code=400, detail="Nonce expired. Get a new one.")

    # Build expected message and verify
    expected_message = _build_siwe_message(addr, nonce)
    if not _verify_signature(addr, expected_message, request.signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Consume nonce (one-time use)
    del _pending_nonces[addr]
    del _nonce_timestamps[addr]

    # Create or update user
    _get_or_create_user(addr)

    # Issue JWT
    token = _create_jwt(addr)

    return SignResponse(
        token=token,
        wallet_address=addr,
        expires_in=JWT_EXPIRY_HOURS * 3600,
    )


# ── API Endpoints ─────────────────────────────────────────────────────

class SpendCheckRequest(BaseModel):
    url: str = Field(description="Target URL for the spend")
    amount: float = Field(ge=0, description="Amount in USD to spend")
    method: str = Field(default="POST", description="HTTP method")
    action: str = Field(default="", description="Human-readable action")


class SpendCheckResponse(BaseModel):
    allowed: bool
    payment_header: Optional[str] = None
    reason: Optional[str] = None
    remaining_budget: Optional[str] = None
    risk_score: Optional[float] = None
    safety_proof: Optional[Dict[str, Any]] = None


class StatusResponse(BaseModel):
    wallet_address: str
    daily_budget: str
    spent_today: str
    remaining: str
    status: str
    kill_switch: bool
    total_spent: str
    session_count: int
    audit_entries: int
    created_at: float


@app.post("/v1/check", response_model=SpendCheckResponse)
async def check_spend(
    request: SpendCheckRequest,
    wallet: str = Depends(get_wallet),
):
    """Safety check before a spend. Requires valid JWT from wallet auth."""
    agent = _get_agent(wallet)

    from urllib.parse import urlparse
    try:
        host = urlparse(request.url).hostname or ""
    except Exception:
        host = request.url

    result: SpendResult = agent.before_spend(
        to=host,
        amount=request.amount,
        action=request.action,
    )

    if result.status == "APPROVED":
        signed_payload = None
        if result.safety_proof:
            signed_payload = result.safety_proof.get("signature", "")[:64]
            if not signed_payload and result.safety_proof.get("merkle_root"):
                signed_payload = result.safety_proof["merkle_root"][:64]

        return SpendCheckResponse(
            allowed=True,
            payment_header=signed_payload or f"agentsafe-safe-{int(time.time())}",
            remaining_budget=result.remaining_budget,
            risk_score=result.risk_score,
        )

    return SpendCheckResponse(
        allowed=False,
        reason=result.reason,
        remaining_budget=result.remaining_budget,
        risk_score=result.risk_score,
    )


@app.get("/v1/status", response_model=StatusResponse)
async def get_status(wallet: str = Depends(get_wallet)):
    """Returns current budget, audit, and safety state for authenticated wallet."""
    user = _get_or_create_user(wallet)
    agent = _get_agent(wallet)
    status = agent.status()

    return StatusResponse(
        wallet_address=wallet,
        daily_budget=user["daily_budget"],
        spent_today=status.get("spent_today", "0.00"),
        remaining=status.get("remaining", user["daily_budget"]),
        status="active" if not user["kill_switch"] else "terminated",
        kill_switch=user["kill_switch"],
        total_spent=user["total_spent"],
        session_count=user["session_count"],
        audit_entries=status.get("audit_entries", 0),
        created_at=user["created_at"],
    )


# ── Admin / User Management ──────────────────────────────────────────

class SetBudgetRequest(BaseModel):
    daily_budget: str = Field(..., description="New daily budget, e.g. '5.00'")


class SetDestinationsRequest(BaseModel):
    destinations: list[str] = Field(default_factory=list)


@app.put("/v1/budget")
async def set_budget(
    req: SetBudgetRequest,
    wallet: str = Depends(get_wallet),
):
    """Update daily budget limit for authenticated wallet."""
    user = _get_or_create_user(wallet)
    user["daily_budget"] = req.daily_budget
    _save_db()

    # Update agent cache
    if wallet in _agent_cache:
        _agent_cache[wallet].set_budget(req.daily_budget)

    return {"status": "updated", "daily_budget": req.daily_budget}


@app.get("/v1/usdc-balance")
async def get_usdc_balance(wallet: str = Depends(get_wallet)):
    """Check USDC balance on Base Mainnet for the authenticated wallet."""
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))
    usdc_address = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]

    contract = w3.eth.contract(address=usdc_address, abi=usdc_abi)
    balance = contract.functions.balanceOf(wallet).call()

    return {
        "wallet": wallet,
        "usdc_balance": balance / 1e6,  # USDC is 6 decimals
        "chain": "base-mainnet",
    }


@app.post("/v1/kill")
async def kill_switch(wallet: str = Depends(get_wallet)):
    """Activate kill switch — stops all agent spending immediately."""
    user = _get_or_create_user(wallet)
    user["kill_switch"] = True
    _save_db()
    if wallet in _agent_cache:
        _agent_cache[wallet].activate_kill_switch()
    return {"status": "kill_switch_activated", "wallet": wallet}


@app.delete("/v1/kill")
async def deactivate_kill_switch(wallet: str = Depends(get_wallet)):
    """Deactivate kill switch — resume agent spending."""
    user = _get_or_create_user(wallet)
    user["kill_switch"] = False
    _save_db()
    if wallet in _agent_cache:
        _agent_cache[wallet].deactivate_kill_switch()
    return {"status": "kill_switch_deactivated", "wallet": wallet}


# ── Server entry point ──────────────────────────────────────────────

def start_server(host: str = "0.0.0.0", port: int = 8050) -> None:
    """Start the Agentsafe Cloud API server."""
    import uvicorn
    print(f"\n🌐 Agentsafe Cloud API: http://localhost:{port}")
    print(f"   Auth:      GET  http://localhost:{port}/auth/nonce")
    print(f"   Check:     POST http://localhost:{port}/v1/check")
    print(f"   Status:    GET  http://localhost:{port}/v1/status")
    print(f"   Balance:   GET  http://localhost:{port}/v1/usdc-balance")
    print(f"   Docs:      http://localhost:{port}/docs")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
