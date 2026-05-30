"""TimeLock — stricter spending limits during quiet hours."""


class TimeLock:
    """Enforces stricter transaction limits during designated quiet hours.

    During quiet hours (e.g., 1 AM - 6 AM UTC), only small transactions are allowed.
    This prevents agents from making large unexpected spends at odd hours.
    """

    def __init__(
        self,
        quiet_hours: tuple[int, int] = (1, 6),
        max_amount: float = 0.10,
    ):
        self.quiet_start = quiet_hours[0]
        self.quiet_end = quiet_hours[1]
        self.max_amount = max_amount

    def is_quiet_hours(self, hour_utc: int) -> bool:
        """Check if the given hour falls within quiet hours."""
        if self.quiet_start <= self.quiet_end:
            return self.quiet_start <= hour_utc <= self.quiet_end
        else:
            # Wraps midnight (e.g., 22 - 4)
            return hour_utc >= self.quiet_start or hour_utc <= self.quiet_end

    def check(self, amount: float, hour_utc: int) -> bool:
        """Return True if the transaction is allowed at this hour."""
        if not self.is_quiet_hours(hour_utc):
            return True  # Normal hours — no restriction
        return amount <= self.max_amount

    def max_allowed(self, hour_utc: int) -> float:
        """Return max allowed amount for the given hour."""
        if self.is_quiet_hours(hour_utc):
            return self.max_amount
        return float("inf")
