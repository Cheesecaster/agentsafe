"""Safety Proofs — Cryptographic verification of agent safety before spending.

Adopts Brain.fi architecture (Layer 5: Pre-execution Verification).
Instead of implicit checks, we generate a signed 'Safety Proof' that proves
the agent is authorized to spend at the time of transaction.
"""

import hashlib
import json
import time
import hmac
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from agentsafe.safe_agent import SafeAgent

class SafetyProofGenerator:
    """Generates and verifies Safety Proofs for agent transactions."""

    # A "secret" key known only to the SafeAgent instance to sign proofs.
    # In a real distributed system, this would be the agent's private key.
    def __init__(self, secret_key: str = "agentsafe-v0.3-proof-key"):
        self.secret_key = secret_key

    def generate(self, agent: "SafeAgent", amount: float, to: str, action: str) -> Dict[str, Any]:
        """Generate a signed Safety Proof indicating the agent is safe to spend."""
        ts = int(time.time())
        proof_body = {
            "ts": ts,
            "amount": amount,
            "to": to,
            "action": action,
            "checks": {
                "budget_enough": agent.budget.check(amount),
                "trust_verified": agent.trust.check(to) != "BLOCKED",
                "killswitch_off": not agent.kill_switch.is_active,
                "anomaly_ok": True, # Simplified for v0.3
                "behavior_pinned": True # Simplified
            },
            "merkle_root": agent.audit.merkle_root # Include current state fingerprint
        }

        body_str = json.dumps(proof_body, sort_keys=True)
        # Create signature
        signature = hmac.new(
            self.secret_key.encode(),
            body_str.encode(),
            hashlib.sha256
        ).hexdigest()

        proof_body["signature"] = signature
        
        return proof_body

    def verify(self, proof: Dict[str, Any]) -> bool:
        """Verify the signature and content of a safety proof."""
        signature = proof.pop("signature", None)
        if not signature:
            return False
            
        body_str = json.dumps(proof, sort_keys=True)
        expected_sig = hmac.new(
            self.secret_key.encode(),
            body_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return False

        # Verify internal consistency
        checks = proof.get("checks", {})
        if not all(checks.values()):
            return False
            
        # Verify expiration (e.g., proof valid for 60 seconds)
        if int(time.time()) - proof.get("ts", 0) > 60:
            return False

        return True
