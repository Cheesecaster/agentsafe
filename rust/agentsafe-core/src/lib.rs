use chrono::Utc;
use serde::{Deserialize, Serialize};

/// BudgetGuard — Daily spending cap with auto-reset.
///
/// Rust implementation:
/// - Zero allocation on check (pure arithmetic).
/// - Thread-safe state management via `Arc<RwLock>` (if used in async context).
/// - Auto-reset at midnight UTC.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BudgetGuard {
    pub daily_limit: f64,
    pub spent_today: f64,
    pub count: u32,
    #[serde(rename = "reset_at")]
    pub reset_at_timestamp: f64,
}

impl BudgetGuard {
    pub fn new(daily_limit: f64) -> Self {
        Self {
            daily_limit,
            spent_today: 0.0,
            count: 0,
            reset_at_timestamp: BudgetGuard::calc_next_midnight(),
        }
    }

    /// Check if amount is within remaining budget.
    /// O(1) complexity, zero allocations.
    pub fn check(&self, amount: f64) -> bool {
        self.spent_today + amount <= self.daily_limit
    }

    /// Record a successful spend.
    pub fn record(&mut self, amount: f64) -> Result<(), String> {
        if !self.check(amount) {
            return Err("Budget exceeded".to_string());
        }
        self.spent_today += amount;
        self.count += 1;
        Ok(())
    }

    /// Remaining budget for today.
    pub fn remaining(&self) -> f64 {
        (self.daily_limit - self.spent_today).max(0.0)
    }

    /// Check and reset if day has passed.
    pub fn maybe_reset(&mut self) {
        let now = Utc::now().timestamp_millis() as f64 / 1000.0;
        if now >= self.reset_at_timestamp {
            self.reset();
        }
    }

    fn reset(&mut self) {
        self.spent_today = 0.0;
        self.count = 0;
        self.reset_at_timestamp = BudgetGuard::calc_next_midnight();
    }

    fn calc_next_midnight() -> f64 {
        let now = Utc::now();
        let tomorrow = now.date_naive().succ_opt()
            .unwrap_or(now.date_naive())
            .and_hms_opt(0, 0, 0)
            .unwrap()
            .and_utc();
        tomorrow.timestamp_millis() as f64 / 1000.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_budget_check_and_record() {
        let mut guard = BudgetGuard::new(0.50);
        assert!(guard.check(0.30));
        assert!(guard.record(0.30).is_ok());
        assert!((guard.remaining() - 0.20).abs() < f64::EPSILON);
        assert!(guard.record(0.25).is_err()); // Exceeds limit
    }
}
