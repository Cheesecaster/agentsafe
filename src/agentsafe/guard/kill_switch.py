"""KillSwitch — emergency circuit breaker for the agent."""

import json
import os


class KillSwitch:
    """Hard-stop mechanism. Once activated, all spends are blocked.

    Args:
        storage_path: Directory for persisting state.
    """

    def __init__(self, storage_path: str = ""):
        self._active = False
        self._reason = ""
        self._storage_path = storage_path
        self._state_file = os.path.join(storage_path, "killswitch.json") if storage_path else ""
        self._try_load()

    def _try_load(self) -> None:
        if self._state_file and os.path.exists(self._state_file):
            try:
                with open(self._state_file) as f:
                    state = json.load(f)
                self._active = state.get("active", False)
                self._reason = state.get("reason", "")
            except (json.JSONDecodeError, IOError):
                pass

    def _try_save(self) -> None:
        if self._state_file:
            try:
                with open(self._state_file, "w") as f:
                    json.dump({
                        "active": self._active,
                        "reason": self._reason,
                    }, f)
            except IOError:
                pass

    def activate(self, reason: str = "Manual kill") -> None:
        """Activate the kill switch."""
        self._active = True
        self._reason = reason
        self._try_save()

    def deactivate(self) -> None:
        """Deactivate the kill switch."""
        self._active = False
        self._reason = ""
        self._try_save()

    def resume(self) -> None:
        """Alias for deactivate() — resume the agent after kill."""
        self.deactivate()

    def is_active(self) -> bool:
        """Check whether the kill switch is active (callable method)."""
        return self._active

    @property
    def reason(self) -> str:
        return self._reason
