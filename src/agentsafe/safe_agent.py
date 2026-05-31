"""SafeAgent — Core orchestrator that chains all safety guards with session identity."""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .guard.budget import BudgetGuard
from .guard.trust import TrustRegistry
from .guard.anomaly import AnomalyGuard
from .guard.time_lock import TimeLock
from .guard.behavior import BehaviorHash
from .guard.kill_switch import KillSwitch
from .guard.audit_chain import AuditChain
from .guard.proof import SafetyProofGenerator
from .guard.session_id import generate_session_id, format_agent_header


@dataclass
class SpendResult:
    """Result of a before_spend() check."""
    status: str          # "APPROVED", "ESCALATE", or "DENIED"
    reason: str
    remaining_budget: str
    risk_score: float = 0.0
    payment_header: Optional[str] = None
    safety_proof: Optional[Dict[str, Any]] = None
    session_id: str = ""          # Unique agent session identifier
    agent_header: str = ""        # X-Agent-Session header value for merchant


class SafeAgent:
    """Main safety gate for autonomous agents that spend money.

    Generates a unique session_id on init. Every spend is attributed to this session
    via the X-Agent-Session HTTP header and Merkle audit log.
    """

    def __init__(
        self,
        daily_budget: str = "0.50",
        currency: str = "USDC",
        allowlist: Optional[list[str]] = None,
        blocklist: Optional[list[str]] = None,
        quiet_hours: tuple[int, int] = (1, 6),
        quiet_hours_max: str = "0.10",
        anomaly_multiplier: float = 3.0,
        behavior_hash: Optional[str] = None,
        on_escalate: Optional[Callable] = None,
        storage_path: str = "~/.agentsafe",
        session_seed: Optional[str] = None,
    ):
        self.currency = currency
        self._daily_budget = float(daily_budget)
        self._quiet_hours = quiet_hours
        self._quiet_hours_max = float(quiet_hours_max)
        self._anomaly_multiplier = anomaly_multiplier

        storage = Path(os.path.expanduser(storage_path))
        storage.mkdir(parents=True, exist_ok=True)

        # Generate unique session identity
        self.wallet_address = storage.name  # Use storage path name as wallet proxy
        self._session_id = generate_session_id(
            wallet_address=self.wallet_address,
            seed=session_seed,
        )

        # Initialize guards
        self.budget = BudgetGuard(
            daily_limit=float(daily_budget),
            storage_path=str(storage / "budget.json"),
        )
        self.trust = TrustRegistry(
            allowlist=allowlist,
            blocklist=blocklist,
            storage_path=str(storage / "trust.json"),
        )
        self.anomaly = AnomalyGuard(
            multiplier=anomaly_multiplier,
            storage_path=str(storage / "anomaly.json"),
        )
        self.time_lock = TimeLock(
            quiet_hours=quiet_hours,
            max_amount=float(quiet_hours_max),
        )
        self.behavior = BehaviorHash()
        self.kill_switch = KillSwitch(
            storage_path=str(storage / "killswitch.json"),
        )
        self.audit = AuditChain(
            storage_path=str(storage / "audit.jsonl"),
        )
        self.proof_gen = SafetyProofGenerator()

        self._on_escalate = on_escalate

    @property
    def session_id(self) -> str:
        """Unique session identity for this agent instance."""
        return self._session_id

    def before_spend(self, to: str, amount: float, action: str = "") -> SpendResult:
        """Run all safety checks before allowing a payment.

        Returns SpendResult with session_id + X-Agent-Session header.
        """
        now = time.time()
        checks = {
            "to": to,
            "amount": amount,
            "action": action,
        }

        # 1. Kill switch (fail fast)
        if self.kill_switch.is_active:
            return SpendResult(
                status="DENIED",
                reason="Kill switch is active — all spending halted.",
                remaining_budget="0.00",
                session_id=self._session_id,
            )

        # 2. Budget check
        if not self.budget.check(amount):
            return SpendResult(
                status="DENIED",
                reason=f"Budget exceeded ({amount} > {self.budget.remaining} remaining).",
                remaining_budget=str(self.budget.remaining),
                session_id=self._session_id,
            )

        # 3. Trust check
        trust_status = self.trust.check(to)
        if trust_status == "BLOCKED":
            return SpendResult(
                status="DENIED",
                reason=f"Destination {to} is blocked by trust registry.",
                remaining_budget=f"{self.budget.remaining:.2f}",
                session_id=self._session_id,
            )

        # 3b. Unknown counterparty → ESCALATE
        if trust_status == "UNKNOWN" and amount >= self._quiet_hours_max:
            self._log("SPEND_ESCALATED", {
                "to": to, "amount": amount, "action": action,
                "session_id": self._session_id,
            })
            return SpendResult(
                status="ESCALATE",
                reason=f"Unknown counterparty: {to}. Requires owner approval.",
                remaining_budget=f"{self.budget.remaining:.2f}",
                risk_score=0.5,
                session_id=self._session_id,
            )

        # 4. Anomaly detection
        from datetime import datetime, timezone
        hour_utc = datetime.now(timezone.utc).hour
        hourly_avg = self.anomaly.hourly_average(hour_utc)
        count_last_hour = self.anomaly.count_last_hour()
        if hourly_avg > 0 and amount > hourly_avg * self._anomaly_multiplier:
            self._log("ANOMALY_DETECTED", {
                "to": to, "amount": amount, "avg": hourly_avg,
                "session_id": self._session_id,
            })

        # 5. Time lock
        if not self.time_lock.check(amount, hour_utc):
            return SpendResult(
                status="DENIED",
                reason=f"Quiet hours: max ${self.time_lock.max_amount} allowed.",
                remaining_budget=str(self.budget.remaining),
                session_id=self._session_id,
            )

        # 6. Generate safety proof
        proof = self.proof_gen.generate(self, amount, to, action)

        # Build X-Agent-Session header for merchant identification
        merkle_root = self.audit.merkle_root
        agent_header = format_agent_header(
            session_id=self._session_id,
            wallet_address=self.wallet_address,
            merkle_root=merkle_root,
        )

        # Log approval
        self._log("SPEND_APPROVED", {
            **checks,
            "session_id": self._session_id,
            "proof_sig": proof.get("signature", "")[:16],
            "merkle_root": merkle_root[:16],
        })

        return SpendResult(
            status="APPROVED",
            reason="All safety checks passed.",
            remaining_budget=str(self.budget.remaining),
            risk_score=0.0,
            payment_header=agent_header,
            safety_proof=proof,
            session_id=self._session_id,
            agent_header=agent_header,
        )

    def record_spent(self, amount: float, to: str, action: str = "") -> None:
        """Record an actual spend — updates budget, anomaly, behavior, audit."""
        now = time.time()

        # Update budget
        self.budget.record(amount)

        # Update anomaly tracker
        self.anomaly.record(now, amount)

        # Update trust
        self.trust.add_interaction(to, success=True)

        # Update behavior hash
        behavior_str = action or f"paid {amount} to {to}"
        self.behavior.update(BehaviorHash.compute(system_prompt=behavior_str))

        # Log to audit chain (with session_id for merchant attribution)
        self._log("SPENT", {
            "amount": amount,
            "to": to,
            "action": action,
            "session_id": self._session_id,
            "ts_utc": now,
        })

    def _log(self, action: str, details: dict) -> str:
        """Log to audit chain."""
        return self.audit.log(action, details)

    def status(self) -> dict:
        """Get current agent status."""
        remaining_val = self.budget.remaining
        spent_val = self.budget.spent_today
        return {
            "session_id": self._session_id,
            "wallet_address": self.wallet_address,
            "daily_budget": f"{self._daily_budget:.2f} {self.currency}",
            "spent_today": f"{spent_val:.4f} {self.currency}",
            "remaining": f"{remaining_val:.4f} {self.currency}",
            "kill_switch": self.kill_switch.is_active,
            "audit_entries": self.audit.count,
            "merkle_root": self.audit.merkle_root[:32] if self.audit.merkle_root else "",
            "last_reset": self.budget.last_reset,
            "trust_stats": self.trust.stats,
        }

    def activate_kill_switch(self) -> None:
        """Emergency stop — halt all spending."""
        self.kill_switch.activate()
        self._log("KILL_SWITCH_ACTIVATED", {"session_id": self._session_id})

    def deactivate_kill_switch(self) -> None:
        """Resume spending."""
        self.kill_switch.deactivate()
        self._log("KILL_SWITCH_DEACTIVATED", {"session_id": self._session_id})

    def set_budget(self, daily_budget: str) -> None:
        """Update daily budget limit."""
        self._daily_budget = float(daily_budget)
        self.budget.daily_limit = float(daily_budget)

    def add_to_allowlist(self, destination: str) -> None:
        self.trust.allow(destination)

    def add_to_blocklist(self, destination: str) -> None:
        self.trust.block(destination)
