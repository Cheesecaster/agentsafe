"""Behavior hash — generates fingerprints for actions."""

import hashlib


class BehaviorHash:
    """Computes a deterministic fingerprint for an action/destination pair."""

    @staticmethod
    def compute(action: str, to: str) -> str:
        """
        Compute a fingerprint string for the given action and destination.

        Returns a hex digest suitable for logging and verification.
        """
        data = f"{action}:{to.lower()}"
        return hashlib.sha256(data.encode()).hexdigest()
