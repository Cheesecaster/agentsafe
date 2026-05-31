"""Session ID generator."""

import hashlib
import random
import time


def generate_session_id(wallet: str = None, timestamp: float = None, random_data: str = None) -> str:
    """
    Generate a deterministic-yet-unique session ID.

    Args:
        wallet: Wallet address string.
        timestamp: Unix timestamp (defaults to current time).
        random_data: Additional entropy string (defaults to random hex).

    Returns:
        A SHA-256 hex digest string.
    """
    w = wallet if wallet is not None else "agent-default"
    ts = timestamp if timestamp is not None else time.time()
    rd = random_data if random_data is not None else random.randbytes(16).hex()
    data = f"{w}:{ts}:{rd}"
    return hashlib.sha256(data.encode()).hexdigest()
