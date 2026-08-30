//! Gate 249 — Epoch Health Ledger: tamper-evident running health record (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Records one HealthLedgerEntry per epoch, accumulating the DashboardFrame
//! hash into a running ledger_hash. Suitable for external attestation.
//!
//! HealthLedgerEntry:
//!   epoch          — u64
//!   frame_hash     — [u8; 32] from DashboardFrame
//!   condition      — OverallCondition byte (0–4)
//!   trend          — OverallTrend byte (0–3)
//!   ledger_hash    — SHA-256(prev_ledger_hash ‖ frame_hash ‖ condition_byte ‖ epoch_be8)
//!   prev_hash      — previous ledger_hash (LEDGER_GENESIS_HASH for first)
//!
//! HealthLedger:
//!   entries()        — &[HealthLedgerEntry]
//!   terminal_hash()  — last ledger_hash or LEDGER_GENESIS_HASH
//!   record(frame)    — append entry
//!   verify_chain()   — (bool, Option<usize>)
//!   worst_condition()— highest OverallCondition seen
//!   critical_epochs()— count of entries with trend=Critical

use sha2::{Sha256, Digest};
use crate::health_dashboard::{DashboardFrame, OverallTrend};
use crate::health_aggregator::OverallCondition;

// ─── Ledger entry ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct HealthLedgerEntry {
    pub epoch:       u64,
    pub frame_hash:  [u8; 32],
    pub condition:   OverallCondition,
    pub trend:       OverallTrend,
    pub ledger_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const LEDGER_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_ledger_hash(
    prev:       &[u8; 32],
    frame_hash: &[u8; 32],
    condition:  OverallCondition,
    epoch:      u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(frame_hash);
    h.update([condition.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Ledger ───────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct HealthLedger {
    entries: Vec<HealthLedgerEntry>,
}

#[derive(Debug)]
pub struct LedgerError(pub &'static str);

impl HealthLedger {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn len(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self) -> bool { self.entries.is_empty() }
    pub fn entries(&self) -> &[HealthLedgerEntry] { &self.entries }

    pub fn terminal_hash(&self) -> [u8; 32] {
        self.entries.last().map(|e| e.ledger_hash).unwrap_or(LEDGER_GENESIS_HASH)
    }

    /// Highest OverallCondition seen across all entries (worst = highest ordinal).
    pub fn worst_condition(&self) -> OverallCondition {
        self.entries.iter()
            .map(|e| e.condition)
            .max()
            .unwrap_or(OverallCondition::Optimal)
    }

    /// Count of entries where trend == Critical.
    pub fn critical_epoch_count(&self) -> usize {
        self.entries.iter().filter(|e| e.trend == OverallTrend::Critical).count()
    }

    /// Count of entries where trend == Thriving.
    pub fn thriving_epoch_count(&self) -> usize {
        self.entries.iter().filter(|e| e.trend == OverallTrend::Thriving).count()
    }

    /// Record a DashboardFrame into the ledger. Epoch must be strictly increasing.
    pub fn record(&mut self, frame: &DashboardFrame) -> Result<&HealthLedgerEntry, LedgerError> {
        if let Some(last) = self.entries.last() {
            if frame.epoch <= last.epoch {
                return Err(LedgerError("epoch must be strictly greater"));
            }
        }
        let prev_hash   = self.terminal_hash();
        let ledger_hash = compute_ledger_hash(
            &prev_hash, &frame.frame_hash, frame.vector.condition, frame.epoch);

        let entry = HealthLedgerEntry {
            epoch:       frame.epoch,
            frame_hash:  frame.frame_hash,
            condition:   frame.vector.condition,
            trend:       frame.overall_trend,
            ledger_hash,
            prev_hash,
        };
        self.entries.push(entry);
        Ok(self.entries.last().unwrap())
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = LEDGER_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_ledger_hash(&prev, &e.frame_hash, e.condition, e.epoch);
            if expected != e.ledger_hash {
                return (false, Some(i));
            }
            prev = e.ledger_hash;
        }
        (true, None)
    }
}

impl Default for HealthLedger {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::health_aggregator::{build_vector, VECTOR_GENESIS_HASH};
    use crate::health_dashboard::{build_frame, DASHBOARD_GENESIS_HASH};
    use crate::swarm_health::HealthVerdict;
    use crate::resilience_watchdog::ResilienceVerdict;
    use crate::constitutional_pulse::PulseVerdict;
    use crate::coherence_stability::StabilityGrade;
    use crate::momentum_tracker::MomentumDir;
    use crate::phase_transition::ConstitutionalPhase;

    fn good_frame(epoch: u64) -> DashboardFrame {
        let v = build_vector(epoch,
            HealthVerdict::Pass, ResilienceVerdict::Stable,
            PulseVerdict::Green, StabilityGrade::A,
            MomentumDir::Improving, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH);
        build_frame(epoch, v, ConstitutionalPhase::Nominal,
                    MomentumDir::Improving, 10, &DASHBOARD_GENESIS_HASH)
    }

    fn bad_frame(epoch: u64) -> DashboardFrame {
        let v = build_vector(epoch,
            HealthVerdict::Fail, ResilienceVerdict::Oscillating,
            PulseVerdict::Red, StabilityGrade::F,
            MomentumDir::Declining, ConstitutionalPhase::Critical,
            &VECTOR_GENESIS_HASH);
        build_frame(epoch, v, ConstitutionalPhase::Critical,
                    MomentumDir::Declining, -20, &DASHBOARD_GENESIS_HASH)
    }

    // ── HealthLedger basics ───────────────────────────────────────────────────

    #[test]
    fn new_ledger_empty() {
        let l = HealthLedger::new();
        assert!(l.is_empty());
        assert_eq!(l.terminal_hash(), LEDGER_GENESIS_HASH);
        assert_eq!(l.worst_condition(), OverallCondition::Optimal);
    }

    #[test]
    fn record_grows_ledger() {
        let mut l = HealthLedger::new();
        l.record(&good_frame(1)).unwrap();
        l.record(&good_frame(2)).unwrap();
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut l = HealthLedger::new();
        l.record(&good_frame(5)).unwrap();
        assert!(l.record(&good_frame(5)).is_err());
    }

    // ── Ledger hash ───────────────────────────────────────────────────────────

    #[test]
    fn ledger_hash_nonzero() {
        let mut l = HealthLedger::new();
        l.record(&good_frame(1)).unwrap();
        assert_ne!(l.terminal_hash(), [0u8; 32]);
    }

    #[test]
    fn ledger_hash_chain_links() {
        let mut l = HealthLedger::new();
        l.record(&good_frame(1)).unwrap();
        l.record(&good_frame(2)).unwrap();
        assert_eq!(l.entries()[1].prev_hash, l.entries()[0].ledger_hash);
    }

    #[test]
    fn ledger_hash_deterministic() {
        let f1 = good_frame(7);
        let f2 = good_frame(7);
        let f3 = good_frame(7);
        let mut l1 = HealthLedger::new();
        let mut l2 = HealthLedger::new();
        let mut l3 = HealthLedger::new();
        l1.record(&f1).unwrap();
        l2.record(&f2).unwrap();
        l3.record(&f3).unwrap();
        assert_eq!(l1.terminal_hash(), l2.terminal_hash());
        assert_eq!(l2.terminal_hash(), l3.terminal_hash());
    }

    #[test]
    fn different_frame_gives_different_hash() {
        let mut l1 = HealthLedger::new();
        let mut l2 = HealthLedger::new();
        l1.record(&good_frame(1)).unwrap();
        l2.record(&bad_frame(1)).unwrap();
        assert_ne!(l1.terminal_hash(), l2.terminal_hash());
    }

    // ── Condition and trend analytics ─────────────────────────────────────────

    #[test]
    fn worst_condition_tracks_emergency() {
        let mut l = HealthLedger::new();
        l.record(&good_frame(1)).unwrap();  // Optimal
        l.record(&bad_frame(2)).unwrap();   // Emergency
        l.record(&good_frame(3)).unwrap();  // Optimal
        assert_eq!(l.worst_condition(), OverallCondition::Emergency);
    }

    #[test]
    fn critical_epoch_count_tracked() {
        let mut l = HealthLedger::new();
        l.record(&bad_frame(1)).unwrap();   // Critical trend
        l.record(&good_frame(2)).unwrap();  // Thriving
        l.record(&bad_frame(3)).unwrap();   // Critical trend
        assert_eq!(l.critical_epoch_count(), 2);
    }

    #[test]
    fn thriving_epoch_count_tracked() {
        let mut l = HealthLedger::new();
        l.record(&good_frame(1)).unwrap();  // Thriving
        l.record(&bad_frame(2)).unwrap();   // Critical
        l.record(&good_frame(3)).unwrap();  // Thriving
        assert_eq!(l.thriving_epoch_count(), 2);
    }

    #[test]
    fn worst_condition_empty_is_optimal() {
        let l = HealthLedger::new();
        assert_eq!(l.worst_condition(), OverallCondition::Optimal);
    }

    // ── Chain verification ────────────────────────────────────────────────────

    #[test]
    fn verify_chain_clean() {
        let mut l = HealthLedger::new();
        for i in 1u64..=5 {
            l.record(&good_frame(i)).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn verify_chain_mixed_good_bad() {
        let mut l = HealthLedger::new();
        l.record(&good_frame(1)).unwrap();
        l.record(&bad_frame(2)).unwrap();
        l.record(&good_frame(3)).unwrap();
        l.record(&bad_frame(4)).unwrap();
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn entry_fields_match_frame() {
        let mut l = HealthLedger::new();
        let f = good_frame(10);
        l.record(&f).unwrap();
        let e = &l.entries()[0];
        assert_eq!(e.epoch, 10);
        assert_eq!(e.frame_hash, f.frame_hash);
        assert_eq!(e.condition, f.vector.condition);
        assert_eq!(e.trend, f.overall_trend);
    }
}
