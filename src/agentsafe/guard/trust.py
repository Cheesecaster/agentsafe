"""Trust guard — manages allowlists for destinations."""


class TrustGuard:
    """Guards against spending to untrusted destinations."""

    def __init__(self, initial_allowlist: list = None):
        self._allowlist: set = set()
        self._denylist: set = set()
        if initial_allowlist:
            for addr in initial_allowlist:
                self._allowlist.add(addr.lower())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, to: str) -> bool:
        """Return True if *to* is in the allowlist and not in the denylist."""
        addr = to.lower()
        if addr in self._denylist:
            return False
        # If allowlist is empty, treat everything as allowed (open trust)
        if not self._allowlist:
            return True
        return addr in self._allowlist

    def allow(self, to: str) -> None:
        """Add *to* to the allowlist."""
        self._allowlist.add(to.lower())
        self._denylist.discard(to.lower())

    def deny(self, to: str) -> None:
        """Add *to* to the denylist."""
        self._denylist.add(to.lower())

    def add_to_allowlist(self, to: str) -> None:
        """Alias for allow()."""
        self.allow(to)

    @property
    def allowlist(self) -> set:
        return set(self._allowlist)

    @property
    def denylist(self) -> set:
        return set(self._denylist)
