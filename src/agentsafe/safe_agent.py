"""SafeAgent — the orchestrator that assembles all guard modules."""

import time
from dataclasses import dataclass
from typing import Optional

from .guard.budget import BudgetGuard
from .guard.trust import TrustGuard
from .guard.anomaly import AnomalyGuard
from .guard.kill_switch import KillSwitch
from .guard.timelock import TimeLock
from .guard.audit_chain import AuditChain
from .guard.merkle import MerkleTree
from .guard.behavior import BehaviorHash
from .guard.proof import SafetyProofGenerator
from .guard.session_id import generate_session_id


@dataclass
class ApprovalResult:
    """Result of a before_spend check."""
    approved: bool
    reason: str
    fingerprint: str = ""
    proof: dict = None


class SafeAgent:
    """
    Orchestrator that wires all guard modules together.

    Before any spend, the agent runs through:
      1. Kill-switch check
      2. Budget check
      3. Trust/allowlist check
      4. Anomaly detection
      5. Time-lock check
    If all pass, the action is approved and logged.
    """

    def __init__(
        self,
        daily_budget: str = "20.00",
        allowlist: list = None,
        storage_path: str = None,
    ):
        budget_float = float(daily_budget)
        self.budget = budget_float
        self.trust = TrustGuard(initial_allowlist=allowlist)
        self.anomaly = AnomalyGuard()
        self.time_lock = TimeLock(max_amount=budget_float, quiet_hours=(1, 6))
        self.kill_switch = KillSwitch()
        self.audit = AuditChain(storage_path=storage_path)
        self.session_id = generate_session_id(
            wallet="agent-default", timestamp=time.time()
        )
        self.merkle = MerkleTree()
        self._budget_guard = BudgetGuard(
            daily_limit=budget_float, storage_path=storage_path
        )
        self._proof_gen = SafetyProofGenerator()

        self.audit.log("init", f"SafeAgent created with budget={daily_budget}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def before_spend(self, to: str, amount: float, action: str) -> ApprovalResult:
        """
        Run all guards and return an ApprovalResult.

        Args:
            to: Destination address.
            amount: Spend amount.
            action: Action description.

        Returns:
            ApprovalResult with approved=True/False and reason.
        """
        # 1. Kill switch
        if self.kill_switch.is_active():
            return ApprovalResult(approved=False, reason="Kill switch activated")

        # 2. Budget check
        if not self._budget_guard.check(amount):
            return ApprovalResult(approved=False, reason="Budget limit exceeded")

        # 3. Trust check
        if not self.trust.check(to):
            return ApprovalResult(approved=False, reason="Destination not trusted")

        # 4. Anomaly check
        if not self.anomaly.check(amount):
            return ApprovalResult(approved=False, reason="Anomalous amount detected")

        # 5. Time-lock check
        current_hour = time.localtime().tm_hour
        if not self.time_lock.check(amount, current_hour):
            return ApprovalResult(approved=False, reason="Quiet hours active")

        # All guards passed — approve
        self._budget_guard.deduct(amount)
        self.anomaly.record(time.time(), amount)
        fingerprint = BehaviorHash.compute(action, to)
        self.audit.log(action, f"to={to} amount={amount}")
        self.merkle.append(f"{action}:{to}:{amount}")

        # Generate proof
        checks = {"budget": True, "trust": True, "anomaly": True, "timelock": True}
        proof = self._proof_gen.generate(self.session_id, self.audit.merkle_root, checks)

        return ApprovalResult(
            approved=True,
            reason="All guards passed",
            fingerprint=fingerprint,
            proof=proof,
        )
