"""agentsafe — The seatbelt for autonomous agents that spend money via x402."""

from .safe_agent import SafeAgent, SpendResult
from .sdk_client import AgentsafeClient, X402Response
from .guard.budget import BudgetGuard
from .guard.trust import TrustRegistry
from .guard.anomaly import AnomalyGuard
from .guard.time_lock import TimeLock
from .guard.behavior import BehaviorHash
from .guard.kill_switch import KillSwitch
from .guard.audit_chain import AuditChain

# Optional x402 export (requires agentsafe[x402] extras)
try:
    from .x402 import X402Client, X402PaymentError
except ImportError:
    X402Client = None
    X402PaymentError = None

__version__ = "0.3.0"
__all__ = [
    "SafeAgent", "SpendResult",
    "AgentsafeClient", "X402Response",
    "BudgetGuard", "TrustRegistry", "AnomalyGuard",
    "TimeLock", "BehaviorHash", "KillSwitch", "AuditChain",
    "X402Client", "X402PaymentError",
]
