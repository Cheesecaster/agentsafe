"""Budget guard — enforces daily spending limits."""

import json
import os
from datetime import date


class BudgetGuard:
    """Guards against exceeding a daily budget limit."""

    def __init__(self, daily_limit: float = 20.0, storage_path: str = None):
        self.daily_limit = daily_limit
        self.storage_path = storage_path
        self._spent_today = 0.0
        self._date_key = date.today().isoformat()
        self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, amount: float) -> bool:
        """Return True if adding *amount* would stay within the daily limit."""
        return (self._spent_today + amount) <= self.daily_limit

    def deduct(self, amount: float) -> None:
        """Record a spend. Raises ValueError if it would exceed the limit."""
        if not self.check(amount):
            raise ValueError(
                f"Budget exceeded: {amount} would bring total to "
                f"{self._spent_today + amount} (limit {self.daily_limit})"
            )
        self._spent_today += amount
        self._save_state()

    def spend(self, amount: float) -> None:
        """Record a spend (alias for deduct without check)."""
        self._spent_today += amount
        self._save_state()

    def record(self, amount: float) -> None:
        """Alias for deduct."""
        self.deduct(amount)

    def reset_daily(self) -> None:
        """Reset the daily counter."""
        self._spent_today = 0.0
        self._date_key = date.today().isoformat()
        self._save_state()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def remaining(self) -> float:
        """Remaining budget for today."""
        return max(0.0, self.daily_limit - self._spent_today)

    @property
    def spent_today(self) -> float:
        return self._spent_today

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        if self.storage_path is None:
            return
        try:
            with open(self.storage_path, "r") as f:
                state = json.load(f)
            stored_date = state.get("date_key", "")
            if stored_date == self._date_key:
                self._spent_today = float(state.get("spent_today", 0.0))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_state(self) -> None:
        if self.storage_path is None:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.storage_path)), exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(
                {"date_key": self._date_key, "spent_today": self._spent_today}, f
            )
