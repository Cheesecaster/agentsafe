"""BudgetGuard — daily spending cap with auto-reset."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


class BudgetGuard:
    """Enforces a daily spending cap. Non-overridable by the agent.

    The cap resets at midnight UTC. When budget is exhausted, the agent
    gracefully falls back to free mode — no error is thrown.
    """

    def __init__(self, daily_limit: float = 0.50, storage_path: str = "budget.json"):
        self.daily_limit = daily_limit
        self._storage = Path(storage_path)
        self._state = self._load()

    def check(self, amount: float) -> bool:
        """Return True if amount is within remaining budget."""
        self._maybe_reset()
        return self._state["spent"] + amount <= self.daily_limit

    def record(self, amount: float) -> None:
        """Record a successful spend."""
        self._maybe_reset()
        self._state["spent"] = round(self._state["spent"] + amount, 6)
        self._state["count"] += 1
        self._save()

    @property
    def spent_today(self) -> float:
        self._maybe_reset()
        return self._state["spent"]

    @property
    def remaining(self) -> float:
        self._maybe_reset()
        return max(0.0, self.daily_limit - self._state["spent"])

    @property
    def last_reset(self) -> float:
        return self._state["reset_at"]

    def _maybe_reset(self) -> None:
        if time.time() >= self._state["reset_at"]:
            self._state["spent"] = 0.0
            self._state["count"] = 0
            self._state["reset_at"] = self._next_midnight_utc()
            self._save()

    def _next_midnight_utc(self) -> float:
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        return (tomorrow + timedelta(days=1)).timestamp()

    def _load(self) -> dict:
        if self._storage.exists():
            try:
                with open(self._storage) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"spent": 0.0, "count": 0, "reset_at": self._next_midnight_utc()}

    def _save(self) -> None:
        with open(self._storage, "w") as f:
            json.dump(self._state, f, indent=2)
