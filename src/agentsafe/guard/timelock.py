"""TimeLock guard — restricts operations during quiet hours."""


class TimeLock:
    """Blocks spending during configured quiet hours."""

    def __init__(self, max_amount: float, quiet_hours: tuple = (1, 6)):
        """
        Args:
            max_amount: Maximum allowed spend outside quiet hours.
            quiet_hours: (start, end) tuple of hours (0-23) during which
                         spending is blocked.
        """
        self.max_amount = max_amount
        self.quiet_hours = quiet_hours

    def check(self, amount: float, current_hour: int) -> bool:
        """
        Return True if the spend is allowed at the given hour.

        During quiet hours, spending is blocked unless the amount is 0.
        Outside quiet hours, spending is allowed if amount <= max_amount.
        """
        start, end = self.quiet_hours
        in_quiet = False

        if start <= end:
            in_quiet = start <= current_hour < end
        else:
            # Wraps midnight, e.g. (22, 6)
            in_quiet = current_hour >= start or current_hour < end

        if in_quiet:
            return amount == 0
        return amount <= self.max_amount
