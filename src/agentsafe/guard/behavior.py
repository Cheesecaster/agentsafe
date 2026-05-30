"""BehaviorHash — detect model/prompt/tool drift at runtime."""

import hashlib
import json


class BehaviorHash:
    """Tracks the registered behavior hash of an agent and detects drift.

    The behavior hash is computed from (model, system_prompt, available_tools).
    If any of these change at runtime, the hash no longer matches and
    the agent is flagged for review.

    This is adapted from brain.fi's behaviorHash approach but simplified
    for agent-level implementation.
    """

    def __init__(self, registered_hash: str | None = None):
        self._registered = registered_hash or ""
        self._is_registered = bool(registered_hash)

    @staticmethod
    def compute(
        model: str = "",
        system_prompt: str = "",
        tools: list[str] | None = None,
    ) -> str:
        """Compute a behavior hash from agent configuration."""
        data = {
            "model": model,
            "system_prompt": system_prompt,
            "tools": sorted(tools or []),
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    @property
    def is_registered(self) -> bool:
        return self._is_registered

    def matches_current(
        self,
        model: str = "",
        system_prompt: str = "",
        tools: list[str] | None = None,
    ) -> bool:
        """Check if current config matches the registered hash."""
        if not self._is_registered:
            return True  # No hash registered = can't check
        current = self.compute(model, system_prompt, tools)
        return current == self._registered

    def update(self, hash_value: str) -> None:
        """Update the registered hash (should only be called by owner)."""
        self._registered = hash_value
        self._is_registered = bool(hash_value)
