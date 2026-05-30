"""TrustRegistry — counterparty allowlist/blocklist with auto-promotion."""

import json
import os
from pathlib import Path


class TrustRegistry:
    """Tracks counterparty trust level and auto-promotes after N successful interactions.

    Levels:
    - TRUSTED: In allowlist or promoted after N successes
    - UNKNOWN: Never interacted
    - BLOCKED: In blocklist (permanent)
    """

    PROMOTE_THRESHOLD = 5  # successes before auto-trust

    def __init__(
        self,
        allowlist: list[str] | None = None,
        blocklist: list[str] | None = None,
        storage_path: str = "trust.json",
    ):
        self._allowlist = set(allowlist or [])
        self._blocklist = set(blocklist or [])
        self._storage = Path(storage_path)
        self._interactions: dict[str, int] = {}  # counterparty -> success count
        self._load()

    def check(self, counterparty: str) -> str:
        """Return trust level: TRUSTED, UNKNOWN, or BLOCKED."""
        if counterparty in self._blocklist:
            return "BLOCKED"
        if counterparty in self._allowlist:
            return "TRUSTED"
        if self._interactions.get(counterparty, 0) >= self.PROMOTE_THRESHOLD:
            self._allowlist.add(counterparty)
            return "TRUSTED"
        return "UNKNOWN"

    def add_interaction(self, counterparty: str, success: bool = True) -> None:
        """Record an interaction with a counterparty."""
        if success:
            self._interactions[counterparty] = self._interactions.get(counterparty, 0) + 1
            if self._interactions[counterparty] >= self.PROMOTE_THRESHOLD:
                self._allowlist.add(counterparty)
        else:
            # On failure, don't block immediately but don't count toward promotion
            pass
        self._save()

    def block(self, counterparty: str) -> None:
        """Permanently block a counterparty."""
        self._blocklist.add(counterparty)
        self._allowlist.discard(counterparty)
        self._save()

    def unblock(self, counterparty: str) -> None:
        """Remove from blocklist (does NOT auto-trust)."""
        self._blocklist.discard(counterparty)
        self._save()

    def promote(self, counterparty: str) -> None:
        """Manually trust a counterparty."""
        self._allowlist.add(counterparty)
        self._save()

    @property
    def stats(self) -> dict:
        return {
            "trusted": len(self._allowlist),
            "blocked": len(self._blocklist),
            "unknown_pending": sum(
                1 for c in self._interactions.values() if c < self.PROMOTE_THRESHOLD
            ),
        }

    def _load(self) -> None:
        if self._storage.exists():
            try:
                with open(self._storage) as f:
                    data = json.load(f)
                self._interactions = data.get("interactions", {})
                self._allowlist |= set(data.get("allowlist", []))
                self._blocklist |= set(data.get("blocklist", []))
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self) -> None:
        with open(self._storage, "w") as f:
            json.dump({
                "allowlist": sorted(self._allowlist),
                "blocklist": sorted(self._blocklist),
                "interactions": self._interactions,
            }, f, indent=2)
