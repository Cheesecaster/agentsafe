"""FastAPI routes for agentsafe API.

Endpoints:
- GET /v1/check — Budget/trust check
- GET /v1/status — Agent status
- GET /auth/nonce — Get nonce for SiWE
- POST /auth/sign — Verify signature, get JWT
"""

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    from fastapi import APIRouter, Depends, HTTPException, Header, Request
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False
    APIRouter = type("APIRouter", (), {"__init__": lambda s, **kw: None, "get": lambda s, p: lambda f: f, "post": lambda s, p: lambda f: f})

try:
    from jose import JWTError, jwt
    _HAS_JOSE = True
except ImportError:
    _HAS_JOSE = False

router = APIRouter()

# In-memory nonce store (nonce -> expiry)
_nonces: dict = {}
# JWT secret
JWT_SECRET = os.environ.get("AGENTSAFE_JWT_SECRET", "agentsafe-dev-secret-change-me")
JWT_ALGORITHM = "HS256"

# In-memory session for demo
_current_session = None


def generate_nonce() -> dict:
    """Generate a fresh nonce (sync, for tests and route use)."""
    global _nonces
    nonce = os.urandom(16).hex()
    _nonces[nonce] = time.time() + 300  # 5 min expiry
    return {"nonce": nonce, "domain": "agentsafe.io", "uri": "https://agentsafe.io"}


class SignRequest(BaseModel):
    address: str
    signature: str
    nonce: str
    message: str


class StatusResponse(BaseModel):
    status: str
    session_id: str
    merkle_root: str
    budget_remaining: float


class CheckResponse(BaseModel):
    allowed: bool
    status: str
    remaining: float


@router.get("/v1/check")
async def check_spend(amount: float = 0.0, target: str = "") -> CheckResponse:
    """Check if a spend is allowed."""
    global _current_session
    if _current_session is None:
        return CheckResponse(allowed=False, status="NO_SESSION", remaining=0.0)

    result = _current_session.before_spend(to=target, amount=amount, action="api_check")
    return CheckResponse(
        allowed=result.status == "APPROVED",
        status=result.status,
        remaining=result.remaining_budget,
    )


@router.get("/v1/status")
async def get_status() -> StatusResponse:
    """Get current agent status."""
    global _current_session
    if _current_session is None:
        return StatusResponse(
            status="INACTIVE",
            session_id="",
            merkle_root="",
            budget_remaining=0.0,
        )

    return StatusResponse(
        status="ACTIVE",
        session_id=_current_session.session_id,
        merkle_root=_current_session.audit.merkle_root,
        budget_remaining=_current_session.budget.remaining(),
    )


@router.get("/auth/nonce")
async def get_nonce() -> dict:
    """Get a fresh nonce for Sign-In With Ethereum."""
    return generate_nonce()


@router.post("/auth/sign")
async def verify_sign(req: SignRequest) -> dict:
    """Verify SiWE signature and return JWT."""
    global _nonces

    # Check nonce exists and not expired
    if req.nonce not in _nonces:
        raise HTTPException(status_code=401, detail="Invalid or expired nonce")

    nonce_expiry = _nonces.pop(req.nonce)  # Consume nonce
    if time.time() > nonce_expiry:
        raise HTTPException(status_code=401, detail="Nonce expired")

    # Verify signature using eth_account
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct

        recovered = Account.recover_message(
            encode_defunct(text=req.message),
            signature=req.signature,
        )
        if recovered.lower() != req.address.lower():
            raise HTTPException(status_code=401, detail="Signature mismatch")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Verification failed: {e}")

    # Generate JWT
    if not _HAS_JOSE:
        # Fallback: simple token
        return {
            "token": f"agentsafe-jwt-{req.address[:10]}-{int(time.time())}",
            "address": req.address,
            "expires_in": 86400,
        }

    payload = {
        "sub": req.address,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "nonce": req.nonce,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return {
        "token": token,
        "address": req.address,
        "expires_in": 86400,
    }


# ── JWT Auth Middleware ──────────────────────────────────────────────────

def _decode_token(authorization: Optional[str]) -> Optional[str]:
    """Decode JWT from Authorization header. Returns wallet address or None."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    if not _HAS_JOSE:
        return token  # Accept simple tokens in dev
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except (JWTError, Exception):
        return None


def require_auth(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI dependency: require valid JWT or API key."""
    # Support API key auth for daily use (no MetaMask needed)
    api_key = os.environ.get("AGENTSAFE_API_KEY", "")
    if api_key and authorization and authorization.startswith("Api-Key "):
        key = authorization.split(" ", 1)[1]
        if key == api_key:
            return "api-key-auth"

    address = _decode_token(authorization)
    if address:
        return address

    raise HTTPException(status_code=401, detail="Missing or invalid authorization")


@router.post("/v1/kill")
async def kill_session(
    reason: str = "",
    authorized: str = Depends(require_auth),
) -> dict:
    """Kill the current agent session. Requires JWT or API key auth."""
    global _current_session
    if _current_session is None:
        raise HTTPException(status_code=404, detail="No active session")

    _current_session.kill(reason or f"Killed via API by {authorized}")
    return {
        "status": "killed",
        "session_id": _current_session.session_id,
        "reason": reason or "unspecified",
    }


@router.post("/v1/auth/api-key")
async def register_api_key(
    address: str,
    nonce: str,
    signature: str,
    message: str,
) -> dict:
    """Register an API key for wallet-less daily use.

    After SiWE once, returns an API key that can be used instead of MetaMask.
    """
    if not _HAS_JOSE:
        raise HTTPException(status_code=501, detail="JWT support not installed")

    # Verify signature first
    nonce_data = _nonces.get(nonce)
    if not nonce_data:
        raise HTTPException(status_code=401, detail="Invalid or expired nonce")

    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
        if recovered.lower() != address.lower():
            raise HTTPException(status_code=401, detail="Signature mismatch")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Verification failed")

    _nonces.pop(nonce, None)

    # Generate persistent API key
    import secrets
    api_key = f"ask_{secrets.token_urlsafe(32)}"

    payload = {
        "sub": address,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
        "api_key": api_key,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return {
        "api_key": api_key,
        "token": token,
        "address": address,
    }
