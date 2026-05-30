"""agentsafe — The seatbelt for autonomous agents that spend money via x402."""

from .safe_agent import SafeAgent, SpendResult
from .guard.budget import BudgetGuard
from .guard.trust import TrustRegistry
from .guard.anomaly import AnomalyGuard
from .guard.time_lock import TimeLock
from .guard.behavior import BehaviorHash
from .guard.kill_switch import KillSwitch
from .guard.audit_chain import AuditChain

__version__ = "0.1.0"
__all__ = [
    "SafeAgent", "SpendResult",
    "BudgetGuard", "TrustRegistry", "AnomalyGuard",
    "TimeLock", "BehaviorHash", "KillSwitch", "AuditChain",
]
