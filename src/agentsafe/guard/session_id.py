"""Session identity — generate deterministic session IDs for agent tracking.

Each agent session gets a unique ID that identifies WHO spent WHAT.
Used in:
  - X-Agent-Session HTTP header (merchant-side identification)
  - Merkle audit leaves (tamper-evident attribution)
  - On-chain events (AgentSpend on Base)
"""

import hashlib
import time
import secrets
from typing import Optional


def generate_session_id(
    wallet_address: str,
    seed: Optional[str] = None,
) -> str:
    """Generate a deterministic session ID from wallet + seed.

    Format: sess-{wallet[:8]}-{unix_ts}-{entropy[:8]}
    """
    ts = int(time.time())
    entropy = seed or secrets.token_hex(4)
    raw = f"{wallet_address.lower()}:{ts}:{entropy}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:12]
    short_wallet = wallet_address.lower().replace("0x", "")[:8]
    return f"sess-{short_wallet}-{ts}-{short_hash}"


def format_agent_header(
    session_id: str,
    wallet_address: str,
    merkle_root: str = "",
) -> str:
    """Build the X-Agent-Session header value.

    Format: {session_id}:{wallet}:{merkle_prefix}
    Merchant can parse this to identify the paying agent.
    """
    prefix = merkle_root[:16] if merkle_root else "0"
    return f"{session_id}:{wallet_address.lower()}:{prefix}"


def parse_agent_header(header_value: str) -> dict:
    """Parse X-Agent-Session header back into structured data."""
    parts = header_value.split(":")
    if len(parts) < 2:
        return {}
    return {
        "session_id": parts[0],
        "wallet_address": parts[1] if len(parts) > 1 else "",
        "merkle_prefix": parts[2] if len(parts) > 2 else "",
    }


def verify_session_ownership(header_value: str, expected_wallet: str) -> bool:
    """Verify that the header belongs to the expected wallet address."""
    parsed = parse_agent_header(header_value)
    return parsed.get("wallet_address", "").lower() == expected_wallet.lower()
