//! Gate 243 — Entropy Forecast Engine: predicts future entropy balance (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Computes an integer drain rate from a window of EntryBalance observations and
//! forecasts how many epochs remain before entropy drops below ADAPTIVE_EVENT_COST.
//!
//! DrainRate — epochs_per_unit drain, derived as:
//!   observed_drain = (window_start_balance - window_end_balance).max(0)
//!   epochs_elapsed = window.len().saturating_sub(1).max(1)
//!   drain_per_epoch = observed_drain / epochs_elapsed (integer division)
//!
//! ForecastReport:
//!   epochs_until_exhaustion — None if drain_per_epoch == 0 (no drain observed)
//!                           — Some(n) where n = (balance - ADAPTIVE_EVENT_COST) / drain_per_epoch
//!   exhaustion_risk — Immediate / Imminent / Moderate / Low / None
//!
//! forecast_hash = SHA-256(prev_hash ‖ risk_byte ‖ drain_per_epoch_be8 ‖ epoch_be8)

use sha2::{Sha256, Digest};
use crate::entropy_budget::ADAPTIVE_EVENT_COST;

// ─── Exhaustion risk ─────────────────────────────────────────────────────────

/// Epochs-until-exhaustion mapped to a risk level.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ExhaustionRisk {
    Immediate = 0, // already below threshold or < 2 epochs
    Imminent  = 1, // 2–10 epochs
    Moderate  = 2, // 11–50 epochs
    Low       = 3, // 51–200 epochs
    None      = 4, // > 200 epochs or drain_per_epoch == 0
}

impl ExhaustionRisk {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Immediate => "immediate",
            Self::Imminent  => "imminent",
            Self::Moderate  => "moderate",
            Self::Low       => "low",
            Self::None      => "none",
        }
    }

    pub fn is_actionable(self) -> bool {
        matches!(self, Self::Immediate | Self::Imminent)
    }

    fn from_epochs(epochs: Option<u64>) -> Self {
        match epochs {
            None          => Self::None,
            Some(0..=1)   => Self::Immediate,
            Some(2..=10)  => Self::Imminent,
            Some(11..=50) => Self::Moderate,
            Some(51..=200)=> Self::Low,
            Some(_)       => Self::None,
        }
    }
}

// ─── Forecast report ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct ForecastReport {
    pub epoch:                  u64,
    pub current_balance:        u64,
    pub drain_per_epoch:        u64,
    pub epochs_until_exhaustion:Option<u64>,
    pub exhaustion_risk:        ExhaustionRisk,
    pub sample_count:           usize,
    pub forecast_hash:          [u8; 32],
    pub prev_forecast_hash:     [u8; 32],
}

pub const FORECAST_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Compute forecast ────────────────────────────────────────────────────────

/// `balances` — ordered slice of (epoch, entropy_balance) observations, oldest first.
/// `current` — latest observation (must be >= last in balances).
pub fn compute_forecast(
    balances:  &[(u64, u64)],
    current_epoch:   u64,
    current_balance: u64,
    prev_hash: &[u8; 32],
) -> ForecastReport {
    let sample_count = balances.len();

    let drain_per_epoch = if balances.len() < 2 {
        0u64
    } else {
        let start_balance = balances[0].1;
        let end_balance   = balances[balances.len() - 1].1;
        let observed_drain = start_balance.saturating_sub(end_balance);
        let epochs_elapsed = (balances.len() as u64).saturating_sub(1).max(1);
        observed_drain / epochs_elapsed
    };

    let epochs_until_exhaustion = if current_balance < ADAPTIVE_EVENT_COST {
        Some(0)
    } else if drain_per_epoch == 0 {
        None
    } else {
        let headroom = current_balance.saturating_sub(ADAPTIVE_EVENT_COST);
        Some(headroom / drain_per_epoch)
    };

    let exhaustion_risk = if current_balance < ADAPTIVE_EVENT_COST {
        ExhaustionRisk::Immediate
    } else {
        ExhaustionRisk::from_epochs(epochs_until_exhaustion)
    };

    let forecast_hash = compute_forecast_hash(
        prev_hash, exhaustion_risk, drain_per_epoch, current_epoch,
    );

    ForecastReport {
        epoch: current_epoch,
        current_balance,
        drain_per_epoch,
        epochs_until_exhaustion,
        exhaustion_risk,
        sample_count,
        forecast_hash,
        prev_forecast_hash: *prev_hash,
    }
}

fn compute_forecast_hash(
    prev:           &[u8; 32],
    risk:           ExhaustionRisk,
    drain_per_epoch:u64,
    epoch:          u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([risk.as_u8()]);
    h.update(drain_per_epoch.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Forecast history ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ForecastHistory {
    reports: Vec<ForecastReport>,
}

#[derive(Debug)]
pub struct ForecastError(pub &'static str);

impl ForecastHistory {
    pub fn new() -> Self { Self { reports: Vec::new() } }

    pub fn len(&self) -> usize { self.reports.len() }
    pub fn is_empty(&self) -> bool { self.reports.is_empty() }
    pub fn reports(&self) -> &[ForecastReport] { &self.reports }

    pub fn last_hash(&self) -> [u8; 32] {
        self.reports.last().map(|r| r.forecast_hash).unwrap_or(FORECAST_GENESIS_HASH)
    }

    pub fn actionable_count(&self) -> usize {
        self.reports.iter().filter(|r| r.exhaustion_risk.is_actionable()).count()
    }

    /// Record a forecast from the given balance window.
    /// Epoch must be strictly greater than last recorded epoch.
    pub fn record(
        &mut self,
        balances:        &[(u64, u64)],
        current_epoch:   u64,
        current_balance: u64,
    ) -> Result<&ForecastReport, ForecastError> {
        if let Some(last) = self.reports.last() {
            if current_epoch <= last.epoch {
                return Err(ForecastError("epoch must be strictly greater"));
            }
        }
        let prev_hash = self.last_hash();
        let report = compute_forecast(balances, current_epoch, current_balance, &prev_hash);
        self.reports.push(report);
        Ok(self.reports.last().unwrap())
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = FORECAST_GENESIS_HASH;
        for (i, rep) in self.reports.iter().enumerate() {
            if rep.prev_forecast_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_forecast_hash(
                &prev, rep.exhaustion_risk, rep.drain_per_epoch, rep.epoch,
            );
            if expected != rep.forecast_hash {
                return (false, Some(i));
            }
            prev = rep.forecast_hash;
        }
        (true, None)
    }
}

impl Default for ForecastHistory {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── ExhaustionRisk ────────────────────────────────────────────────────────

    #[test]
    fn risk_ordering() {
        assert!(ExhaustionRisk::Immediate < ExhaustionRisk::Imminent);
        assert!(ExhaustionRisk::Imminent  < ExhaustionRisk::Moderate);
        assert!(ExhaustionRisk::Moderate  < ExhaustionRisk::Low);
        assert!(ExhaustionRisk::Low       < ExhaustionRisk::None);
    }

    #[test]
    fn actionable_risks() {
        assert!(ExhaustionRisk::Immediate.is_actionable());
        assert!(ExhaustionRisk::Imminent.is_actionable());
        assert!(!ExhaustionRisk::Moderate.is_actionable());
        assert!(!ExhaustionRisk::Low.is_actionable());
        assert!(!ExhaustionRisk::None.is_actionable());
    }

    #[test]
    fn risk_as_u8() {
        assert_eq!(ExhaustionRisk::Immediate.as_u8(), 0);
        assert_eq!(ExhaustionRisk::None.as_u8(), 4);
    }

    // ── compute_forecast ──────────────────────────────────────────────────────

    #[test]
    fn no_drain_gives_none_exhaustion() {
        // Flat balance — no drain
        let balances: Vec<(u64, u64)> = (1..=5).map(|i| (i, 1000)).collect();
        let rep = compute_forecast(&balances, 6, 1000, &FORECAST_GENESIS_HASH);
        assert_eq!(rep.drain_per_epoch, 0);
        assert_eq!(rep.epochs_until_exhaustion, None);
        assert_eq!(rep.exhaustion_risk, ExhaustionRisk::None);
    }

    #[test]
    fn below_threshold_gives_immediate() {
        let rep = compute_forecast(&[], 1, 5, &FORECAST_GENESIS_HASH); // 5 < ADAPTIVE_EVENT_COST=10
        assert_eq!(rep.exhaustion_risk, ExhaustionRisk::Immediate);
        assert_eq!(rep.epochs_until_exhaustion, Some(0));
    }

    #[test]
    fn single_sample_no_drain_rate() {
        let balances = vec![(1, 1000)];
        let rep = compute_forecast(&balances, 2, 950, &FORECAST_GENESIS_HASH);
        assert_eq!(rep.drain_per_epoch, 0); // need at least 2 for drain rate
    }

    #[test]
    fn drain_rate_computed_correctly() {
        // Start=1000, end=900 over 5 epochs → drain = 100/4 = 25
        let balances: Vec<(u64, u64)> = vec![(1,1000),(2,975),(3,950),(4,925),(5,900)];
        let rep = compute_forecast(&balances, 6, 875, &FORECAST_GENESIS_HASH);
        assert_eq!(rep.drain_per_epoch, 25);
    }

    #[test]
    fn epochs_until_exhaustion_computed() {
        // drain=25/epoch, balance=510, threshold=10 → headroom=500 → 500/25=20
        let balances: Vec<(u64, u64)> = vec![(1,1000),(2,975),(3,950),(4,925),(5,900)];
        let rep = compute_forecast(&balances, 6, 510, &FORECAST_GENESIS_HASH);
        assert_eq!(rep.drain_per_epoch, 25);
        assert_eq!(rep.epochs_until_exhaustion, Some(20)); // (510-10)/25 = 20
        assert_eq!(rep.exhaustion_risk, ExhaustionRisk::Moderate);
    }

    #[test]
    fn imminent_risk_within_10_epochs() {
        // drain=100/epoch, balance=610 → headroom=600 → 600/100=6 → Imminent
        let balances: Vec<(u64, u64)> = vec![(1,1000),(2,900)];
        let rep = compute_forecast(&balances, 3, 610, &FORECAST_GENESIS_HASH);
        assert_eq!(rep.drain_per_epoch, 100);
        assert_eq!(rep.epochs_until_exhaustion, Some(6));
        assert_eq!(rep.exhaustion_risk, ExhaustionRisk::Imminent);
    }

    #[test]
    fn forecast_hash_nonzero() {
        let rep = compute_forecast(&[], 1, 1000, &FORECAST_GENESIS_HASH);
        assert_ne!(rep.forecast_hash, [0u8; 32]);
    }

    #[test]
    fn forecast_hash_deterministic() {
        let balances: Vec<(u64, u64)> = (1..=4).map(|i| (i, 1000u64 - i * 10)).collect();
        let r1 = compute_forecast(&balances, 5, 950, &FORECAST_GENESIS_HASH);
        let r2 = compute_forecast(&balances, 5, 950, &FORECAST_GENESIS_HASH);
        let r3 = compute_forecast(&balances, 5, 950, &FORECAST_GENESIS_HASH);
        assert_eq!(r1.forecast_hash, r2.forecast_hash);
        assert_eq!(r2.forecast_hash, r3.forecast_hash);
    }

    #[test]
    fn different_epochs_different_hash() {
        let r1 = compute_forecast(&[], 1, 1000, &FORECAST_GENESIS_HASH);
        let r2 = compute_forecast(&[], 2, 1000, &FORECAST_GENESIS_HASH);
        assert_ne!(r1.forecast_hash, r2.forecast_hash);
    }

    // ── ForecastHistory ───────────────────────────────────────────────────────

    #[test]
    fn new_history_empty() {
        let h = ForecastHistory::new();
        assert!(h.is_empty());
        assert_eq!(h.actionable_count(), 0);
    }

    #[test]
    fn record_grows_history() {
        let mut h = ForecastHistory::new();
        h.record(&[], 1, 1000).unwrap();
        h.record(&[], 2, 980).unwrap();
        assert_eq!(h.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = ForecastHistory::new();
        h.record(&[], 5, 1000).unwrap();
        assert!(h.record(&[], 5, 950).is_err());
    }

    #[test]
    fn actionable_count_tracks() {
        let mut h = ForecastHistory::new();
        h.record(&[], 1, 1000).unwrap();  // None risk (no drain)
        h.record(&[], 2, 3).unwrap();      // Immediate (below threshold)
        h.record(&[], 3, 5).unwrap();      // Immediate
        assert_eq!(h.actionable_count(), 2);
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = ForecastHistory::new();
        for i in 1u64..=5 {
            h.record(&[], i, 1000 - i * 50).unwrap();
        }
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
