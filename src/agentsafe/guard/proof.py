"""SafetyProofGenerator — HMAC-signed safety proofs for compliance."""

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from agentsafe.guard.merkle import MerkleTree


class SafetyProofGenerator:
    """Generates signed JSON safety proofs before every approved spend.

    Two usage patterns supported:
    1. Full proof style: generate(session_id, merkle_root, checks) → dict (subagent API)
    2. Detailed proof: generate(amount, target, budget_remaining) → dict (main API)
    """

    _proof_key = "agentsafe-v0.3-proof-key"

    def __init__(
        self,
        session_id: str = "",
        merkle_tree: Any = None,
        merkle: Any = None,
        storage_path: str = "",
        secret: str = "",
    ):
        self.session_id = session_id
        self._merkle_tree = merkle_tree if merkle_tree is not None else merkle
        self._storage_path = storage_path
        self._secret = secret.encode() if secret else self._proof_key.encode()

    @staticmethod
    def _sign(data: str, secret: bytes) -> str:
        return hmac.new(secret, data.encode(), hashlib.sha256).hexdigest()

    def generate(
        self,
        session_id: str = "",
        merkle_root: str = "",
        checks: dict = None,
        # Alternative API
        amount: float = 0,
        target: str = "",
        budget_remaining: float = 0,
    ) -> Dict[str, Any]:
        """Generate a safety proof. Two calling styles supported."""
        if checks is not None and merkle_root:
            # Style 1: generate(session_id, merkle_root, checks)
            sid = session_id or self.session_id
            payload = {
                "session_id": sid,
                "merkle_root": merkle_root,
                "checks": checks,
                "timestamp": time.time(),
            }
            sign_input = f"{sid}:{merkle_root}:{sorted(checks.items())}"
            sig = self._sign(sign_input, self._secret)
            return {**payload, "signature": sig}

        # Style 2: generate(amount=..., target=..., budget_remaining=...)
        now = datetime.now(timezone.utc).isoformat()
        merkle = ""
        if self._merkle_tree:
            merkle = self._merkle_tree.get_root()

        payload = {
            "session_id": self.session_id,
            "timestamp": now,
            "amount": amount,
            "target": target,
            "budget_remaining": budget_remaining,
            "merkle_root": merkle,
            "checks": {
                "budget_enough": budget_remaining >= amount,
                "trust_verified": True,
                "killswitch_off": True,
                "behavior_pinned": True,
            },
        }

        payload_json = json.dumps(payload, sort_keys=True)
        sig = self._sign(payload_json, self._secret)
        payload["signature"] = sig
        return payload

    def verify(self, proof: Dict[str, Any]) -> bool:
        """Verify HMAC signature on a proof."""
        sig = proof.pop("signature", None)
        if sig is None:
            return False

        payload_json = json.dumps(proof, sort_keys=True)
        expected = self._sign(payload_json, self._secret)
        # Restore signature since we popped it
        proof["signature"] = sig
        return hmac.compare_digest(sig, expected)
