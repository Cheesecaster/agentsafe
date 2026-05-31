"""Agentsafe Cloud API — FastAPI Backend bridging the SDK to Safety Logic.

Serves as the middleware server that the SDK client (AgentsafeClient) connects to.
Maps API keys to individual user profiles and SafeAgent instances.

Usage:
    uvicorn agentsafe.api.server:app --host 0.0.0.0 --port 8050
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

from ..safe_agent import SafeAgent, SpendResult
from ..sdk_client import AgentsafeClient

# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(title="Agentsafe Cloud API", version="0.4.0")

# ── Simulated Database ───────────────────────────────────────────────

DB_PATH = os.environ.get("AGENTSAFE_DB_PATH", str(Path(__file__).parent / "db.json"))

# In-process cache: api_key -> UserDBEntry
_user_cache: Dict[str, "UserDBEntry"] = {}

# In-process cache: api_key -> SafeAgent instance (lazy-loaded)
_agent_cache: Dict[str, SafeAgent] = {}


class UserDBEntry:
    """A single user record stored in the simulated DB."""

    def __init__(
        self,
        api_key: str,
        email: str,
        daily_budget: str = "0.50",
        currency: str = "USDC",
        allowed_destinations: Optional[list] = None,
        created_at: Optional[float] = None,
    ):
        self.api_key = api_key
        self.email = email
        self.daily_budget = daily_budget
        self.currency = currency
        self.allowed_destinations = allowed_destinations or []
        self.created_at = created_at or time.time()

    def to_dict(self) -> dict:
        return {
            "api_key": self.api_key,
            "email": self.email,
            "daily_budget": self.daily_budget,
            "currency": self.currency,
            "allowed_destinations": self.allowed_destinations,
            "created_at": self.created_at,
        }


def _load_db() -> Dict[str, dict]:
    """Load the user database from the JSON file."""
    if not os.path.exists(DB_PATH):
        return {}
    with open(DB_PATH) as f:
        return json.load(f)


def _save_db(db: Dict[str, dict]) -> None:
    """Persist the user database."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)


def _get_user(api_key: str) -> UserDBEntry:
    """Look up a user by API key. Raises HTTP 401/404 on failure."""
    if api_key in _user_cache:
        return _user_cache[api_key]

    prefix_map = _load_db()
    # Support exact match and prefix-lookup (keys are hashed in prod)
    if api_key in prefix_map:
        entry = UserDBEntry(**prefix_map[api_key])
    else:
        # Fallback scan — small DB so this is fine
        for key, data in prefix_map.items():
            if data.get("api_key") == api_key:
                entry = UserDBEntry(**data)
                break
        else:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    _user_cache[api_key] = entry
    return entry


def _get_agent(api_key: str) -> SafeAgent:
    """Retrieve (or lazily create) the SafeAgent for a given user."""
    if api_key in _agent_cache:
        return _agent_cache[api_key]

    user = _get_user(api_key)
    agent = SafeAgent(
        daily_budget=user.daily_budget,
        currency=user.currency,
        allowlist=user.allowed_destinations,
        storage_path=str(Path("~/.agentsafe").expanduser() / api_key[:8]),
    )
    _agent_cache[api_key] = agent
    return agent


# ── Seed default users on startup ────────────────────────────────────

def _seed_default_users() -> None:
    """Create sample users if the database is empty."""
    if _load_db():
        return

    default_users = [
        {
            "api_key": "sk-demo-dev1-123",
            "email": "developer@example.com",
            "daily_budget": "1.00",
            "currency": "USDC",
            "allowed_destinations": ["api.example.com", "pay.stripe.com"],
            "created_at": time.time(),
        },
        {
            "api_key": "***",
            "email": "tester@example.com",
            "daily_budget": "0.50",
            "currency": "USDC",
            "allowed_destinations": [],
            "created_at": time.time(),
        },
    ]
    db = {u["api_key"]: u for u in default_users}
    _save_db(db)
    # Warm the cache
    for u in default_users:
        _user_cache[u["api_key"]] = UserDBEntry(**u)


# ── Pydantic Models ─────────────────────────────────────────────────

class SpendCheckRequest(BaseModel):
    url: str = Field(description="Target URL for the spend")
    amount: float = Field(ge=0, description="Amount in USD to spend")
    method: str = Field(default="POST", description="HTTP method for the request")
    action: str = Field(default="", description="Human-readable action description")


class SpendCheckResponse(BaseModel):
    allowed: bool
    payment_header: Optional[str] = None
    reason: Optional[str] = None
    remaining_budget: Optional[str] = None
    risk_score: Optional[float] = None
    safety_proof: Optional[Dict[str, Any]] = None


class StatusResponse(BaseModel):
    daily_budget: str
    spent_today: str
    remaining: str
    status: str
    kill_switch: bool
    trust_stats: Dict[str, Any] = {}
    audit_entries: int
    last_reset: float


class UserStatusResponse(StatusResponse):
    email: str
    api_key_prefix: str


# ── Endpoints ────────────────────────────────────────────────────────

@app.on_event("startup")
def startup() -> None:
    _seed_default_users()


@app.post("/v1/check", response_model=SpendCheckResponse)
async def check_spend(
    request: SpendCheckRequest,
    authorization: str = Header(default=""),
):
    """Safety check before a spend. Equivalent to SafeAgent.before_spend().

    Requires a Bearer token in the Authorization header.
    Returns approval status and signed payment header on success.
    """
    # ── 1. Extract and validate Bearer token ──
    token = authorization
    if token.startswith("Bearer "):
        token = token[len("Bearer "):]
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    user = _get_user(token)
    agent = _get_agent(token)

    # ── 2. Derive destination host from URL ──
    try:
        from urllib.parse import urlparse
        host = urlparse(request.url).hostname or ""
    except Exception:
        host = request.url

    # ── 3. Run safety check ──
    result: SpendResult = agent.before_spend(
        to=host,
        amount=request.amount,
        action=request.action,
    )

    # ── 4. Build response ──
    if result.status == "APPROVED":
        # Construct a synthetic signed payload from the safety proof
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
    else:
        # Map ESCALATE/DENIED to a denied response
        return SpendCheckResponse(
            allowed=False,
            reason=result.reason,
            remaining_budget=result.remaining_budget,
            risk_score=result.risk_score,
        )


@app.get("/v1/status", response_model=UserStatusResponse)
async def get_status(authorization: str = Header(default="")):
    """Returns current budget, audit, and safety state for the authenticated user."""
    token = authorization
    if token.startswith("Bearer "):
        token = token[len("Bearer "):]
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    user = _get_user(token)
    agent = _get_agent(token)
    status = agent.status()

    return UserStatusResponse(
        email=user.email,
        api_key_prefix=token[:12] + "...",
        **status,
    )


# ── Admin-only helpers (for testing / seeding) ───────────────────────

@app.post("/admin/register")
async def admin_register(
    api_key: str,
    email: str,
    daily_budget: str = "0.50",
    currency: str = "USDC",
):
    """Register a new user (admin helper — do not expose in prod)."""
    db = _load_db()
    if api_key in db:
        raise HTTPException(status_code=409, detail="API key already registered")

    entry = {
        "api_key": api_key,
        "email": email,
        "daily_budget": daily_budget,
        "currency": currency,
        "allowed_destinations": [],
        "created_at": time.time(),
    }
    db[api_key] = entry
    _save_db(db)
    _user_cache[api_key] = UserDBEntry(**entry)

    return {"status": "registered", "api_key": api_key}


# ── Server entry point ──────────────────────────────────────────────

def start_server(host: str = "0.0.0.0", port: int = 8050) -> None:
    """Start the Agentsafe Cloud API server."""
    import uvicorn
    print(f"\n🌐 Agentsafe Cloud API: http://localhost:{port}")
    print(f"   Check:     POST http://localhost:{port}/v1/check")
    print(f"   Status:    GET  http://localhost:{port}/v1/status")
    print(f"   Docs:      http://localhost:{port}/docs")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
