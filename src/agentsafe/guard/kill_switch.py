"""KillSwitch — owner-controlled agent pause/resume."""

import json
import time
from pathlib import Path


class KillSwitch:
    """Owner-controlled pause/resume mechanism for agent spending.

    Once activated, all before_spend() calls return DENIED.
    The agent cannot resume itself — only the owner can.

    State is persisted to disk so it survives restarts.
    """

    def __init__(self, storage_path: str = "kill_switch.json"):
        self._storage = Path(storage_path)
        self._state = self._load()

    @property
    def is_active(self) -> bool:
        return self._state.get("active", False)

    @property
    def reason(self) -> str:
        return self._state.get("reason", "")

    @property
    def activated_at(self) -> float:
        return self._state.get("activated_at", 0)

    def activate(self, reason: str = "owner command") -> None:
        """Activate the kill switch. Agent is now paused."""
        self._state["active"] = True
        self._state["reason"] = reason
        self._state["activated_at"] = time.time()
        self._save()

    def resume(self) -> None:
        """Resume agent spending. Only callable by owner (not enforced by library)."""
        self._state["active"] = False
        self._state["reason"] = ""
        self._state["activated_at"] = 0
        self._save()

    def _load(self) -> dict:
        if self._storage.exists():
            try:
                with open(self._storage) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"active": False, "reason": "", "activated_at": 0}

    def _save(self) -> None:
        with open(self._storage, "w") as f:
            json.dump(self._state, f, indent=2)
