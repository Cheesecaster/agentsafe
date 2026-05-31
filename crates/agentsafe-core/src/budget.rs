/// A high-performance Budget Guard implemented in Rust.
/// Tracks spending limits with nanosecond precision for high-frequency agents.
pub struct BudgetGuard {
    daily_limit_micro_usd: u64,
    spent_today_micro_usd: u64,
    // In production, this would be a timestamp to handle day-rolling automatically.
}

impl BudgetGuard {
    pub fn new(daily_limit_usd: f64) -> Self {
        Self {
            daily_limit_micro_usd: (daily_limit_usd * 1_000_000.0) as u64,
            spent_today_micro_usd: 0,
        }
    }

    /// Check if a transaction is allowed without committing it.
    pub fn check(&self, amount_usd: f64) -> bool {
        let amount_micro = (amount_usd * 1_000_000.0) as u64;
        self.spent_today_micro_usd + amount_micro <= self.daily_limit_micro_usd
    }

    /// Record a spend. Must be called after check() passes.
    pub fn spend(&mut self, amount_usd: f64) -> Result<u64, &'static str> {
        if !self.check(amount_usd) {
            return Err("Budget limit exceeded");
        }
        let amount_micro = (amount_usd * 1_000_000.0) as u64;
        self.spent_today_micro_usd += amount_micro;
        Ok(self.remaining_micro_usd())
    }

    /// Return remaining daily budget in micro-usd.
    pub fn remaining_micro_usd(&self) -> u64 {
        self.daily_limit_micro_usd - self.spent_today_micro_usd
    }

    /// Reset daily spend (simulates midnight rollover).
    pub fn reset_day(&mut self) {
        self.spent_today_micro_usd = 0;
    }

    pub fn get_limit(&self) -> u64 {
        self.daily_limit_micro_usd
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_budget() {
        let mut guard = BudgetGuard::new(100.0); // $100 limit
        assert!(guard.check(50.0));
        let rem = guard.spend(50.0).unwrap();
        assert_eq!(rem, 50_000_000); // 50 USD in micro

        assert!(guard.check(50.0));
        guard.spend(50.0).unwrap();

        assert!(!guard.check(1.0)); // Should fail
    }
}
