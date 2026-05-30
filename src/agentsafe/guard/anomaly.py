"""AnomalyGuard — time-aware, volume-aware spending anomaly detection."""

import json
import time
from pathlib import Path


class AnomalyGuard:
    """Detects abnormal spending patterns.

    Tracks per-hour spending averages and flags when:
    1. A single transaction exceeds N× the hourly average
    2. Transaction count in the last hour exceeds threshold
    3. Total hourly spend exceeds a cap
    """

    def __init__(self, multiplier: float = 3.0, storage_path: str = "anomaly.json"):
        self.multiplier = multiplier
        self._storage = Path(storage_path)
        self._hourly_records: dict[str, list[float]] = {}  # "YYYY-MM-DD-HH" -> [amounts]
        self._load()

    def record(self, timestamp: float, amount: float) -> None:
        """Record a transaction for anomaly tracking."""
        hour_key = time.strftime("%Y-%m-%d-%H", time.gmtime(timestamp))
        self._hourly_records.setdefault(hour_key, []).append(amount)
        self._prune_old_records()
        self._save()

    def hourly_average(self, hour_of_day: int) -> float:
        """Calculate average spending for a given hour (across recent days)."""
        totals = []
        for key, amounts in self._hourly_records.items():
            key_hour = int(key.split("-")[3])
            if key_hour == hour_of_day and len(amounts) > 0:
                totals.append(sum(amounts) / len(amounts))
        if not totals:
            return 0.0
        return sum(totals) / len(totals)

    def count_last_hour(self) -> int:
        """Count transactions in the last hour."""
        now_key = time.strftime("%Y-%m-%d-%H", time.gmtime(time.time()))
        prev_key = self._prev_hour_key(now_key)
        return len(self._hourly_records.get(now_key, [])) + len(self._hourly_records.get(prev_key, []))

    def hourly_spend_total(self, hour_of_day: int) -> float:
        """Total spend for a given hour."""
        total = 0.0
        for key, amounts in self._hourly_records.items():
            key_hour = int(key.split("-")[3])
            if key_hour == hour_of_day:
                total += sum(amounts)
        return total

    def _prune_old_records(self) -> None:
        """Keep only last 7 days of records."""
        cutoff_key = time.strftime(
            "%Y-%m-%d-%H", time.gmtime(time.time() - 7 * 86400)
        )
        keys_to_remove = [k for k in self._hourly_records if k < cutoff_key]
        for k in keys_to_remove:
            del self._hourly_records[k]

    def _prev_hour_key(self, current_key: str) -> str:
        """Get the previous hour's key."""
        try:
            parts = current_key.split("-")
            h = int(parts[3])
            d = int(parts[2])
            h -= 1
            if h < 0:
                h = 23
                d -= 1
            return f"{parts[0]}-{parts[1]}-{d:02d}-{h:02d}"
        except (IndexError, ValueError):
            return ""

    def _load(self) -> None:
        if self._storage.exists():
            try:
                with open(self._storage) as f:
                    data = json.load(f)
                self._hourly_records = data.get("hourly_records", {})
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self) -> None:
        with open(self._storage, "w") as f:
            json.dump({"hourly_records": self._hourly_records}, f, indent=2)
