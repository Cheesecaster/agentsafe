"""SafeAgent — Core orchestrator that chains all safety guards."""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .guard.budget import BudgetGuard
from .guard.trust import TrustRegistry
from .guard.anomaly import AnomalyGuard
from .guard.time_lock import TimeLock
from .guard.behavior import BehaviorHash
from .guard.kill_switch import KillSwitch
from .guard.audit_chain import AuditChain
from .guard.proof import SafetyProofGenerator


@dataclass
class SpendResult:
    """Result of a before_spend() check."""
    status: str          # "APPROVED", "ESCALATE", or "DENIED"
    reason: str
    remaining_budget: str
    risk_score: float = 0.0
    payment_header: Optional[str] = None
    safety_proof: Optional[Dict[str, Any]] = None


class SafeAgent:
    """Main safety gate for autonomous agents that spend money.

    Usage:
        agent = SafeAgent(daily_budget="0.50")
        result = agent.before_spend(to="api.example.com", amount=0.05)
        if result.status == "APPROVED":
            # proceed with payment
            agent.record_spent(0.05, "api.example.com")
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
    ):
        self.currency = currency
        self._daily_budget = float(daily_budget)
        self._quiet_hours = quiet_hours
        self._quiet_hours_max = float(quiet_hours_max)
        self._anomaly_multiplier = anomaly_multiplier

        storage = Path(os.path.expanduser(storage_path))
        storage.mkdir(parents=True, exist_ok=True)

        # Initialize all guards
        self.budget = BudgetGuard(self._daily_budget, storage / "budget.json")
        self.trust = TrustRegistry(
            allowlist=allowlist or [],
            blocklist=blocklist or [],
            storage_path=str(storage / "trust.json"),
        )
        self.anomaly = AnomalyGuard(
            multiplier=self._anomaly_multiplier,
            storage_path=str(storage / "anomaly.json"),
        )
        self.time_lock = TimeLock(
            quiet_hours=quiet_hours,
            max_amount=self._quiet_hours_max,
        )
        self.behavior = BehaviorHash(registered_hash=behavior_hash)
        self.kill_switch = KillSwitch(storage / "kill_switch.json")
        self.audit = AuditChain(storage / "audit.jsonl")
        self.proof_gen = SafetyProofGenerator()

        self.on_escalate = on_escalate

        # Track spending history for anomaly detection
        self._spend_history: list[tuple[float, float, str]] = []  # (ts, amount, to)

    def before_spend(self, to: str, amount: float, action: str = "") -> SpendResult:
        """Run all safety checks before a payment.

        Returns SpendResult with status APPROVED, ESCALATE, or DENIED.
        """
        now = time.time()
        hour = time.gmtime(now).tm_hour
        remaining = self.budget.remaining

        # ── Check 1: Kill Switch ──
        if self.kill_switch.is_active:
            return self._deny(reason=f"Kill switch active: {self.kill_switch.reason}")

        # ── Check 2: Budget ──
        if not self.budget.check(amount):
            return self._deny(
                reason=f"Budget exceeded. Remaining: {remaining} {self.currency}, need: {amount}"
            )

        # ── Check 3: Trust Registry ──
        trust_level = self.trust.check(to)
        if trust_level == "BLOCKED":
            self.audit.log("spend_denied", {"to": to, "amount": amount, "reason": "blocklisted"})
            return self._deny(reason=f"Counterparty blocklisted: {to}")

        # ── Check 4: Time Lock ──
        if not self.time_lock.check(amount, hour):
            return self._deny(
                reason=f"Quiet hours ({self._quiet_hours[0]}-{self._quiet_hours[1]} UTC). "
                       f"Max ${self.time_lock.max_amount}/tx, requested {amount}"
            )

        # ── Check 5: Anomaly Detection ──
        hourly_avg = self.anomaly.hourly_average(hour)
        count_last_hour = self.anomaly.count_last_hour()
        if amount > hourly_avg * self._anomaly_multiplier and hourly_avg > 0:
            risk = min(1.0, amount / (hourly_avg * 2))
            self._audit_and_escalate(
                to, amount, f"Anomalous amount: {amount} vs avg {hourly_avg:.2f}", risk
            )

        if count_last_hour > 10:
            self._audit_and_escalate(
                to, amount, f"High frequency: {count_last_hour} tx last hour", min(1.0, count_last_hour / 15.0)
            )

        # ── Check 6: Behavior Hash ──
        if self.behavior.is_registered and not self.behavior.matches_current():
            risk = 0.9
            self._audit_and_escalate(to, amount, "Behavior drift detected", risk)

        # ── Check 7: Unknown counterparty → ESCALATE ──
        if trust_level == "UNKNOWN" and amount >= self._quiet_hours_max:
            self.audit.log("spend_escalated", {"to": to, "amount": amount, "action": action})
            result = SpendResult(
                status="ESCALATE",
                reason=f"Unknown counterparty: {to}. Requires owner approval.",
                remaining_budget=f"{remaining:.2f}",
                risk_score=0.5,
            )
            if self.on_escalate:
                self.on_escalate(result)
            return result

        # ── All checks passed ──
        proof = self.proof_gen.generate(self, amount, to, action)
        self.audit.log("spend_approved", {"to": to, "amount": amount, "action": action, "proof_id": proof["signature"][:10]})
        return SpendResult(
            status="APPROVED",
            reason="All guards passed",
            remaining_budget=f"{remaining - amount:.2f}",
            risk_score=0.0,
            safety_proof=proof
        )

    def record_spent(self, amount: float, to: str, action: str = "") -> None:
        """Record a successful spend. Updates budget, trust, anomaly stats."""
        now = time.time()
        self.budget.record(amount)
        self.anomaly.record(now, amount)
        self.trust.add_interaction(to, success=True)
        self._spend_history.append((now, amount, to))

        self.audit.log("spend_recorded", {
            "to": to, "amount": amount, "action": action,
            "daily_spent": self.budget.spent_today,
        })

    def status(self) -> dict:
        """Return current safety status."""
        trust_stats = self.trust.stats
        return {
            "daily_budget": f"{self._daily_budget:.2f} {self.currency}",
            "spent_today": f"{self.budget.spent_today:.4f} {self.currency}",
            "remaining": f"{self.budget.remaining:.4f} {self.currency}",
            "status": "PAUSED" if self.kill_switch.is_active else "ACTIVE",
            "kill_switch": self.kill_switch.is_active,
            "trust_stats": trust_stats,
            "audit_entries": self.audit.count,
            "last_reset": self.budget.last_reset,
        }

    def _deny(self, reason: str) -> SpendResult:
        self.audit.log("spend_denied", {"reason": reason})
        return SpendResult(status="DENIED", reason=reason, remaining_budget=f"{self.budget.remaining:.2f}")

    def _audit_and_escalate(self, to: str, amount: float, reason: str, risk: float):
        self.audit.log("spend_escalated", {"to": to, "amount": amount, "reason": reason, "risk": risk})
        result = SpendResult(status="ESCALATE", reason=reason, remaining_budget=f"{self.budget.remaining:.2f}", risk_score=risk)
        if self.on_escalate:
            self.on_escalate(result)
        return result
