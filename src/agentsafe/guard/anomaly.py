"""Anomaly guard — detects unusual spending patterns."""

from collections import deque


class AnomalyGuard:
    """Guards against anomalous spending amounts based on historical data."""

    def __init__(self, threshold_multiplier: float = 3.0, window: int = 30):
        self.threshold_multiplier = threshold_multiplier
        self._window = window
        self._amounts: deque = deque(maxlen=window)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, timestamp: float, amount: float) -> None:  # noqa: ARG002
        """Record a spending event."""
        self._amounts.append(amount)

    def check(self, amount: float) -> bool:
        """Return True if *amount* is within normal bounds."""
        if len(self._amounts) < 2:
            return True
        avg = self.get_avg()
        # Simple std-dev-free heuristic: reject if > threshold_multiplier * avg
        if avg == 0:
            return amount == 0
        return amount <= self.threshold_multiplier * avg

    def get_avg(self) -> float:
        """Return the average of recorded amounts."""
        if not self._amounts:
            return 0.0
        return sum(self._amounts) / len(self._amounts)
