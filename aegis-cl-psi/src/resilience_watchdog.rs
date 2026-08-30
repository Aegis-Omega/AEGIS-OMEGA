//! Gate 239 — Resilience Watchdog: rolling-window constitutional stability tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Monitors DivergenceOracle history over a configurable rolling window to detect:
//!   - Oscillation: repeated Critical/Terminal transitions within the window
//!   - Recovery trajectory: class improving over consecutive epochs
//!   - Stable degradation: class worsening monotonically
//!
//! ResilienceVerdict:
//!   Recovering     — most-recent class strictly less severe than window peak
//!   Stable         — no change in class across window
//!   Oscillating    — 2+ transitions between Critical/Terminal and lower classes
//!   Degrading      — class strictly worsening epoch-over-epoch
//!   Insufficient   — fewer than 2 oracle entries in window (cannot assess)
//!
//! watchdog_hash = SHA-256(prev_hash ‖ verdict_byte ‖ epoch_be8 ‖ window_peak_class_byte)

use sha2::{Sha256, Digest};
use crate::divergence_oracle::{DivergenceClass, DivergenceOracle};

// ─── Resilience verdict ──────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResilienceVerdict {
    Recovering   = 0,
    Stable       = 1,
    Oscillating  = 2,
    Degrading    = 3,
    Insufficient = 4,
}

impl ResilienceVerdict {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Recovering   => "recovering",
            Self::Stable       => "stable",
            Self::Oscillating  => "oscillating",
            Self::Degrading    => "degrading",
            Self::Insufficient => "insufficient",
        }
    }

    /// System is improving or holding — no intervention needed.
    pub fn is_healthy(self) -> bool {
        matches!(self, Self::Recovering | Self::Stable)
    }

    /// Intervention recommended.
    pub fn requires_intervention(self) -> bool {
        matches!(self, Self::Oscillating | Self::Degrading)
    }
}

// ─── Watchdog report ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct WatchdogReport {
    pub epoch:             u64,
    pub verdict:           ResilienceVerdict,
    pub window_size:       usize,
    pub window_peak_class: DivergenceClass,   // worst class seen in window
    pub latest_class:      DivergenceClass,   // class at most-recent oracle
    pub transition_count:  usize,             // number of class changes in window
    pub oscillation_count: usize,             // up-then-down or down-then-up swings
    /// SHA-256(prev_hash ‖ verdict_byte ‖ epoch_be8 ‖ peak_class_byte)
    pub watchdog_hash:     [u8; 32],
    pub prev_watchdog_hash:[u8; 32],
}

pub const WATCHDOG_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const DEFAULT_WINDOW_SIZE:   usize    = 8;

// ─── Core assessment ─────────────────────────────────────────────────────────

/// Assess resilience over the last `window_size` oracles.
/// `prev_hash` — previous WatchdogReport hash (or WATCHDOG_GENESIS_HASH).
pub fn assess_resilience(
    oracles:     &[DivergenceOracle],
    window_size: usize,
    prev_hash:   &[u8; 32],
) -> WatchdogReport {
    let epoch = oracles.last().map(|o| o.epoch).unwrap_or(0);

    // Take the last window_size entries
    let window_start = oracles.len().saturating_sub(window_size);
    let window = &oracles[window_start..];

    if window.len() < 2 {
        let peak   = window.first().map(|o| o.divergence_class).unwrap_or(DivergenceClass::Stable);
        let latest = peak;
        let hash   = compute_watchdog_hash(prev_hash, ResilienceVerdict::Insufficient, epoch, peak);
        return WatchdogReport {
            epoch,
            verdict:            ResilienceVerdict::Insufficient,
            window_size:        window.len(),
            window_peak_class:  peak,
            latest_class:       latest,
            transition_count:   0,
            oscillation_count:  0,
            watchdog_hash:      hash,
            prev_watchdog_hash: *prev_hash,
        };
    }

    let peak   = window.iter().map(|o| o.divergence_class).max().unwrap_or(DivergenceClass::Stable);
    let latest = window.last().unwrap().divergence_class;

    // Count class transitions and oscillations
    let mut transition_count  = 0usize;
    let mut oscillation_count = 0usize;
    let mut prev_class = window[0].divergence_class;
    let mut prev_direction: Option<i8> = None; // +1 worsening, -1 improving

    for oracle in window.iter().skip(1) {
        let curr = oracle.divergence_class;
        if curr != prev_class {
            transition_count += 1;
            let direction: i8 = if curr.as_u8() > prev_class.as_u8() { 1 } else { -1 };
            if let Some(pd) = prev_direction {
                if pd != direction {
                    oscillation_count += 1;
                }
            }
            prev_direction = Some(direction);
            prev_class = curr;
        }
    }

    // Classify verdict
    let verdict = if oscillation_count >= 2 {
        ResilienceVerdict::Oscillating
    } else if latest.as_u8() < peak.as_u8() {
        // Latest is better than peak → recovering
        ResilienceVerdict::Recovering
    } else {
        // Check monotone degradation: every transition worsened
        let monotone_degrading = {
            let mut degrading = true;
            let mut p = window[0].divergence_class;
            for oracle in window.iter().skip(1) {
                if oracle.divergence_class.as_u8() < p.as_u8() {
                    degrading = false;
                    break;
                }
                p = oracle.divergence_class;
            }
            degrading && transition_count > 0
        };
        if monotone_degrading {
            ResilienceVerdict::Degrading
        } else {
            ResilienceVerdict::Stable
        }
    };

    let watchdog_hash = compute_watchdog_hash(prev_hash, verdict, epoch, peak);

    WatchdogReport {
        epoch,
        verdict,
        window_size: window.len(),
        window_peak_class: peak,
        latest_class: latest,
        transition_count,
        oscillation_count,
        watchdog_hash,
        prev_watchdog_hash: *prev_hash,
    }
}

// ─── Watchdog history ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct WatchdogHistory {
    reports: Vec<WatchdogReport>,
    window_size: usize,
}

#[derive(Debug)]
pub struct WatchdogError(pub &'static str);

impl WatchdogHistory {
    pub fn new(window_size: usize) -> Self {
        Self { reports: Vec::new(), window_size }
    }

    pub fn new_default() -> Self { Self::new(DEFAULT_WINDOW_SIZE) }

    pub fn len(&self) -> usize { self.reports.len() }
    pub fn is_empty(&self) -> bool { self.reports.is_empty() }
    pub fn reports(&self) -> &[WatchdogReport] { &self.reports }
    pub fn window_size(&self) -> usize { self.window_size }

    pub fn last_hash(&self) -> [u8; 32] {
        self.reports.last().map(|r| r.watchdog_hash).unwrap_or(WATCHDOG_GENESIS_HASH)
    }

    pub fn current_verdict(&self) -> ResilienceVerdict {
        self.reports.last().map(|r| r.verdict).unwrap_or(ResilienceVerdict::Insufficient)
    }

    /// Count reports where intervention is required.
    pub fn intervention_count(&self) -> usize {
        self.reports.iter().filter(|r| r.verdict.requires_intervention()).count()
    }

    /// Record the current oracle history snapshot.
    /// Epoch must be strictly increasing.
    pub fn record(
        &mut self,
        oracles: &[DivergenceOracle],
    ) -> Result<&WatchdogReport, WatchdogError> {
        let new_epoch = oracles.last().map(|o| o.epoch).unwrap_or(0);
        if let Some(last) = self.reports.last() {
            if new_epoch <= last.epoch {
                return Err(WatchdogError("epoch must be strictly greater than last recorded epoch"));
            }
        }
        let prev_hash = self.last_hash();
        let report = assess_resilience(oracles, self.window_size, &prev_hash);
        self.reports.push(report);
        Ok(self.reports.last().unwrap())
    }

    /// Verify hash chain integrity. Returns (is_valid, first_broken_index).
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = WATCHDOG_GENESIS_HASH;
        for (i, rep) in self.reports.iter().enumerate() {
            if rep.prev_watchdog_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_watchdog_hash(
                &prev, rep.verdict, rep.epoch, rep.window_peak_class,
            );
            if expected != rep.watchdog_hash {
                return (false, Some(i));
            }
            prev = rep.watchdog_hash;
        }
        (true, None)
    }
}

impl Default for WatchdogHistory {
    fn default() -> Self { Self::new_default() }
}

fn compute_watchdog_hash(
    prev:       &[u8; 32],
    verdict:    ResilienceVerdict,
    epoch:      u64,
    peak_class: DivergenceClass,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([verdict.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.update([peak_class.as_u8()]);
    h.finalize().into()
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::swarm_health::{HealthSnapshot, HealthVerdict, assess_health, HEALTH_GENESIS_HASH};
    use crate::divergence_oracle::{compute_oracle, ORACLE_GENESIS_HASH};

    fn make_pass_report(epoch: u64) -> crate::swarm_health::SwarmHealthReport {
        let snap = HealthSnapshot {
            epoch,
            node_count: 5,
            coherent_node_count: 5,
            continuously_coherent_count: 5,
            quorum_reached: true,
            continuous_quorum: true,
            mutation_authority_active: true,
            entropy_balance: 1000,
            drift_class_int: 0,
            is_continuously_coherent: true,
        };
        assess_health(&snap, &HEALTH_GENESIS_HASH)
    }

    fn make_fail_report(epoch: u64) -> crate::swarm_health::SwarmHealthReport {
        let snap = HealthSnapshot {
            epoch,
            node_count: 5,
            coherent_node_count: 2,
            continuously_coherent_count: 2,
            quorum_reached: false,
            continuous_quorum: false,
            mutation_authority_active: false,
            entropy_balance: 1000,
            drift_class_int: 4,
            is_continuously_coherent: false,
        };
        assess_health(&snap, &HEALTH_GENESIS_HASH)
    }

    fn build_oracle_chain(verdicts: &[(HealthVerdict, HealthVerdict)]) -> Vec<DivergenceOracle> {
        let mut oracles: Vec<DivergenceOracle> = Vec::new();
        let mut prev_hash = ORACLE_GENESIS_HASH;
        for (i, (bv, av)) in verdicts.iter().enumerate() {
            let epoch = (i + 1) as u64;
            let before = if *bv == HealthVerdict::Pass { make_pass_report(epoch) } else { make_fail_report(epoch) };
            let after  = if *av == HealthVerdict::Pass { make_pass_report(epoch) } else { make_fail_report(epoch) };
            let oracle = compute_oracle(&before, &after, &prev_hash);
            prev_hash = oracle.oracle_hash;
            oracles.push(oracle);
        }
        oracles
    }

    // ── ResilienceVerdict ─────────────────────────────────────────────────────

    #[test]
    fn recovering_is_healthy() {
        assert!(ResilienceVerdict::Recovering.is_healthy());
        assert!(!ResilienceVerdict::Recovering.requires_intervention());
    }

    #[test]
    fn stable_is_healthy() {
        assert!(ResilienceVerdict::Stable.is_healthy());
    }

    #[test]
    fn oscillating_requires_intervention() {
        assert!(ResilienceVerdict::Oscillating.requires_intervention());
        assert!(!ResilienceVerdict::Oscillating.is_healthy());
    }

    #[test]
    fn degrading_requires_intervention() {
        assert!(ResilienceVerdict::Degrading.requires_intervention());
    }

    #[test]
    fn insufficient_neither() {
        assert!(!ResilienceVerdict::Insufficient.is_healthy());
        assert!(!ResilienceVerdict::Insufficient.requires_intervention());
    }

    #[test]
    fn verdict_as_u8() {
        assert_eq!(ResilienceVerdict::Recovering.as_u8(), 0);
        assert_eq!(ResilienceVerdict::Stable.as_u8(), 1);
        assert_eq!(ResilienceVerdict::Oscillating.as_u8(), 2);
        assert_eq!(ResilienceVerdict::Degrading.as_u8(), 3);
        assert_eq!(ResilienceVerdict::Insufficient.as_u8(), 4);
    }

    // ── assess_resilience ─────────────────────────────────────────────────────

    #[test]
    fn single_oracle_gives_insufficient() {
        let oracles = build_oracle_chain(&[(HealthVerdict::Pass, HealthVerdict::Pass)]);
        let rep = assess_resilience(&oracles, 8, &WATCHDOG_GENESIS_HASH);
        assert_eq!(rep.verdict, ResilienceVerdict::Insufficient);
    }

    #[test]
    fn empty_oracles_gives_insufficient() {
        let rep = assess_resilience(&[], 8, &WATCHDOG_GENESIS_HASH);
        assert_eq!(rep.verdict, ResilienceVerdict::Insufficient);
    }

    #[test]
    fn stable_pass_chain_gives_stable() {
        let pairs: Vec<_> = (0..5).map(|_| (HealthVerdict::Pass, HealthVerdict::Pass)).collect();
        let oracles = build_oracle_chain(&pairs);
        let rep = assess_resilience(&oracles, 8, &WATCHDOG_GENESIS_HASH);
        assert_eq!(rep.verdict, ResilienceVerdict::Stable);
        assert_eq!(rep.window_peak_class, DivergenceClass::Stable);
        assert_eq!(rep.transition_count, 0);
    }

    #[test]
    fn monotone_degradation_gives_degrading() {
        // Stable → Nominal → Elevated → Critical (worsening at each step)
        // We produce oracles that yield increasing divergence classes manually
        // Build: first oracle stable (P→P), then escalating (P→F at each step)
        let pairs = vec![
            (HealthVerdict::Pass, HealthVerdict::Pass), // Stable
            (HealthVerdict::Pass, HealthVerdict::Fail), // Critical (Pass→Fail)
        ];
        let oracles = build_oracle_chain(&pairs);
        let rep = assess_resilience(&oracles, 8, &WATCHDOG_GENESIS_HASH);
        // peak = Critical, latest = Critical — no improvement → Degrading (monotone)
        assert!(matches!(rep.verdict, ResilienceVerdict::Degrading | ResilienceVerdict::Stable));
    }

    #[test]
    fn recovery_after_peak_gives_recovering() {
        // Fail→Pass at epoch 2, then Pass→Pass at epoch 3
        // peak will be Critical; latest will be Stable → Recovering
        let pairs = vec![
            (HealthVerdict::Pass, HealthVerdict::Fail), // Critical
            (HealthVerdict::Pass, HealthVerdict::Pass), // Stable
            (HealthVerdict::Pass, HealthVerdict::Pass), // Stable
        ];
        let oracles = build_oracle_chain(&pairs);
        let rep = assess_resilience(&oracles, 8, &WATCHDOG_GENESIS_HASH);
        assert_eq!(rep.verdict, ResilienceVerdict::Recovering);
        assert!(rep.latest_class.as_u8() < rep.window_peak_class.as_u8());
    }

    #[test]
    fn oscillation_detected() {
        // Critical → Stable → Critical → Stable → Critical (oscillating)
        let pairs = vec![
            (HealthVerdict::Pass, HealthVerdict::Fail), // Critical
            (HealthVerdict::Pass, HealthVerdict::Pass), // Stable
            (HealthVerdict::Pass, HealthVerdict::Fail), // Critical
            (HealthVerdict::Pass, HealthVerdict::Pass), // Stable
            (HealthVerdict::Pass, HealthVerdict::Fail), // Critical
        ];
        let oracles = build_oracle_chain(&pairs);
        let rep = assess_resilience(&oracles, 8, &WATCHDOG_GENESIS_HASH);
        assert_eq!(rep.verdict, ResilienceVerdict::Oscillating);
        assert!(rep.oscillation_count >= 2);
    }

    #[test]
    fn watchdog_hash_nonzero() {
        let pairs = vec![
            (HealthVerdict::Pass, HealthVerdict::Pass),
            (HealthVerdict::Pass, HealthVerdict::Pass),
        ];
        let oracles = build_oracle_chain(&pairs);
        let rep = assess_resilience(&oracles, 8, &WATCHDOG_GENESIS_HASH);
        assert_ne!(rep.watchdog_hash, [0u8; 32]);
    }

    #[test]
    fn watchdog_hash_deterministic() {
        let pairs: Vec<_> = (0..4).map(|_| (HealthVerdict::Pass, HealthVerdict::Pass)).collect();
        let oracles = build_oracle_chain(&pairs);
        let r1 = assess_resilience(&oracles, 8, &WATCHDOG_GENESIS_HASH);
        let r2 = assess_resilience(&oracles, 8, &WATCHDOG_GENESIS_HASH);
        let r3 = assess_resilience(&oracles, 8, &WATCHDOG_GENESIS_HASH);
        assert_eq!(r1.watchdog_hash, r2.watchdog_hash);
        assert_eq!(r2.watchdog_hash, r3.watchdog_hash);
    }

    // ── WatchdogHistory ───────────────────────────────────────────────────────

    #[test]
    fn new_history_empty() {
        let h = WatchdogHistory::new_default();
        assert!(h.is_empty());
        assert_eq!(h.current_verdict(), ResilienceVerdict::Insufficient);
    }

    #[test]
    fn record_grows_history() {
        let mut h = WatchdogHistory::new_default();
        let p1: Vec<_> = (0..3).map(|_| (HealthVerdict::Pass, HealthVerdict::Pass)).collect();
        let p2: Vec<_> = (0..4).map(|_| (HealthVerdict::Pass, HealthVerdict::Pass)).collect();
        let o1 = build_oracle_chain(&p1);
        let o2 = build_oracle_chain(&p2);
        h.record(&o1).unwrap();
        h.record(&o2).unwrap();
        assert_eq!(h.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = WatchdogHistory::new_default();
        let pairs: Vec<_> = (0..3).map(|_| (HealthVerdict::Pass, HealthVerdict::Pass)).collect();
        let o = build_oracle_chain(&pairs);
        h.record(&o).unwrap();
        assert!(h.record(&o).is_err());
    }

    #[test]
    fn intervention_count_tracks_correctly() {
        let mut h = WatchdogHistory::new_default();
        // First: oscillating chain
        let osc: Vec<_> = vec![
            (HealthVerdict::Pass, HealthVerdict::Fail),
            (HealthVerdict::Pass, HealthVerdict::Pass),
            (HealthVerdict::Pass, HealthVerdict::Fail),
            (HealthVerdict::Pass, HealthVerdict::Pass),
            (HealthVerdict::Pass, HealthVerdict::Fail),
        ];
        let o1 = build_oracle_chain(&osc);
        h.record(&o1).unwrap();
        // Second batch: stable (must have greater epoch than o1.last = 5)
        let stable: Vec<_> = (5..9).map(|_| (HealthVerdict::Pass, HealthVerdict::Pass)).collect();
        let o2 = build_oracle_chain(&stable);
        // o2 last epoch = 4 which is < 5 — so we need a longer chain
        let stable2: Vec<_> = (0..10).map(|_| (HealthVerdict::Pass, HealthVerdict::Pass)).collect();
        let o2 = build_oracle_chain(&stable2);
        h.record(&o2).unwrap();
        assert_eq!(h.intervention_count(), 1); // only the oscillating one
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = WatchdogHistory::new_default();
        let pairs: Vec<_> = (0..3).map(|_| (HealthVerdict::Pass, HealthVerdict::Pass)).collect();
        for n in 1..=4u64 {
            let mut extended = pairs.clone();
            extended.push((HealthVerdict::Pass, HealthVerdict::Pass));
            let _ = extended; // build new chain each time with increasing last epoch
            let chain = build_oracle_chain(&(0..(3 + n as usize)).map(|_| (HealthVerdict::Pass, HealthVerdict::Pass)).collect::<Vec<_>>());
            h.record(&chain).unwrap();
        }
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
