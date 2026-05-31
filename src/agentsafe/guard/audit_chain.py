"""Audit chain — immutable, chained log with Merkle root."""

from collections import OrderedDict
from .merkle import MerkleTree


class AuditChain:
    """An append-only audit log backed by a Merkle tree."""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path
        self._logs: OrderedDict = OrderedDict()
        self._counter = 0
        self._merkle = MerkleTree()

    def log(self, action: str, details: str) -> None:
        """Append a log entry. Uses positional args as specified."""
        self._counter += 1
        entry = {
            "id": self._counter,
            "action": action,
            "details": details,
        }
        self._logs[self._counter] = entry
        # Add to merkle tree
        self._merkle.append(f"{self._counter}:{action}:{details}")

    @property
    def merkle_root(self) -> str:
        """Current Merkle root of the audit log (property, no parens)."""
        return self._merkle.get_root()

    def get_recent_logs(self, n: int = 10) -> list:
        """Return the *n* most recent log entries."""
        items = list(self._logs.values())
        return items[-n:] if len(items) > n else items

    def __len__(self) -> int:
        return len(self._logs)
