//! Gate 242 — Quorum Drift Detector: quorum transition tracking across epochs (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Detects quorum loss events and recovery trajectories from HealthReport sequences.
//! Tracks transitions between quorum_reached=true and quorum_reached=false.
//!
//! QuorumEvent — emitted on state change:
//!   QuorumLost     — quorum_reached flipped true→false
//!   QuorumRestored — quorum_reached flipped false→true
//!
//! QuorumDriftSummary per analysis window:
//!   loss_count         — number of QuorumLost events
//!   restoration_count  — number of QuorumRestored events
//!   longest_absence    — max consecutive epochs with quorum_reached=false
//!   is_currently_quorate — quorum_reached at last report
//!
//! drift_hash = SHA-256(prev_hash ‖ loss_count_be4 ‖ longest_absence_be4 ‖ epoch_be8)

use sha2::{Sha256, Digest};
use crate::swarm_health::{HealthVerdict, SwarmHealthReport};

// ─── Quorum event ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum QuorumEventKind {
    QuorumLost     = 0,
    QuorumRestored = 1,
}

impl QuorumEventKind {
    pub fn as_u8(self) -> u8 { self as u8 }
    pub fn as_str(self) -> &'static str {
        match self {
            Self::QuorumLost     => "quorum_lost",
            Self::QuorumRestored => "quorum_restored",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct QuorumEvent {
    pub epoch:       u64,
    pub kind:        QuorumEventKind,
    pub health_verdict: HealthVerdict,
}

// ─── Quorum drift summary ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct QuorumDriftSummary {
    pub epoch:                u64,
    pub loss_count:           usize,
    pub restoration_count:    usize,
    pub longest_absence:      usize,   // epochs
    pub current_absence_run:  usize,   // ongoing epochs without quorum (0 if quorate)
    pub is_currently_quorate: bool,
    pub events:               Vec<QuorumEvent>,
    pub drift_hash:           [u8; 32],
    pub prev_drift_hash:      [u8; 32],
}

pub const QUORUM_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Analysis function ───────────────────────────────────────────────────────

/// Analyze a sequence of health reports for quorum drift.
pub fn analyze_quorum_drift(
    reports:   &[SwarmHealthReport],
    prev_hash: &[u8; 32],
) -> QuorumDriftSummary {
    let epoch = reports.last().map(|r| r.epoch).unwrap_or(0);

    if reports.is_empty() {
        let hash = compute_drift_hash(prev_hash, 0, 0, epoch);
        return QuorumDriftSummary {
            epoch,
            loss_count: 0,
            restoration_count: 0,
            longest_absence: 0,
            current_absence_run: 0,
            is_currently_quorate: true,
            events: Vec::new(),
            drift_hash: hash,
            prev_drift_hash: *prev_hash,
        };
    }

    let mut events: Vec<QuorumEvent> = Vec::new();
    let mut loss_count        = 0usize;
    let mut restoration_count = 0usize;
    let mut longest_absence   = 0usize;
    let mut current_absence   = 0usize;
    let mut prev_quorate      = reports[0].quorum_reached;

    if !prev_quorate { current_absence = 1; }

    for rep in reports.iter().skip(1) {
        let q = rep.quorum_reached;
        if q != prev_quorate {
            if !q {
                // Lost quorum
                events.push(QuorumEvent { epoch: rep.epoch, kind: QuorumEventKind::QuorumLost, health_verdict: rep.verdict });
                loss_count += 1;
                current_absence = 1;
            } else {
                // Restored quorum
                events.push(QuorumEvent { epoch: rep.epoch, kind: QuorumEventKind::QuorumRestored, health_verdict: rep.verdict });
                restoration_count += 1;
                longest_absence = longest_absence.max(current_absence);
                current_absence = 0;
            }
            prev_quorate = q;
        } else if !q {
            current_absence += 1;
        }
    }

    // Update longest_absence if currently in an absence run
    if !reports.last().unwrap().quorum_reached {
        longest_absence = longest_absence.max(current_absence);
    } else {
        current_absence = 0;
    }

    let is_currently_quorate = reports.last().unwrap().quorum_reached;

    let drift_hash = compute_drift_hash(prev_hash, loss_count, longest_absence, epoch);

    QuorumDriftSummary {
        epoch,
        loss_count,
        restoration_count,
        longest_absence,
        current_absence_run: current_absence,
        is_currently_quorate,
        events,
        drift_hash,
        prev_drift_hash: *prev_hash,
    }
}

fn compute_drift_hash(
    prev:             &[u8; 32],
    loss_count:       usize,
    longest_absence:  usize,
    epoch:            u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update((loss_count as u32).to_be_bytes());
    h.update((longest_absence as u32).to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Drift history ───────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct DriftHistory {
    summaries: Vec<QuorumDriftSummary>,
}

#[derive(Debug)]
pub struct DriftError(pub &'static str);

impl DriftHistory {
    pub fn new() -> Self { Self { summaries: Vec::new() } }

    pub fn len(&self) -> usize { self.summaries.len() }
    pub fn is_empty(&self) -> bool { self.summaries.is_empty() }
    pub fn summaries(&self) -> &[QuorumDriftSummary] { &self.summaries }

    pub fn last_hash(&self) -> [u8; 32] {
        self.summaries.last().map(|s| s.drift_hash).unwrap_or(QUORUM_GENESIS_HASH)
    }

    pub fn total_loss_count(&self) -> usize {
        self.summaries.last().map(|s| s.loss_count).unwrap_or(0)
    }

    /// Record a new analysis over a report slice. Epoch must increase.
    pub fn record(
        &mut self,
        reports: &[SwarmHealthReport],
    ) -> Result<&QuorumDriftSummary, DriftError> {
        let new_epoch = reports.last().map(|r| r.epoch).unwrap_or(0);
        if let Some(last) = self.summaries.last() {
            if new_epoch <= last.epoch {
                return Err(DriftError("epoch must be strictly greater"));
            }
        }
        let prev_hash = self.last_hash();
        let summary = analyze_quorum_drift(reports, &prev_hash);
        self.summaries.push(summary);
        Ok(self.summaries.last().unwrap())
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = QUORUM_GENESIS_HASH;
        for (i, s) in self.summaries.iter().enumerate() {
            if s.prev_drift_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_drift_hash(&prev, s.loss_count, s.longest_absence, s.epoch);
            if expected != s.drift_hash {
                return (false, Some(i));
            }
            prev = s.drift_hash;
        }
        (true, None)
    }
}

impl Default for DriftHistory {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::swarm_health::{HealthSnapshot, assess_health, HEALTH_GENESIS_HASH};

    fn quorate_report(epoch: u64) -> SwarmHealthReport {
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

    fn non_quorate_report(epoch: u64) -> SwarmHealthReport {
        let snap = HealthSnapshot {
            epoch,
            node_count: 5,
            coherent_node_count: 2,
            continuously_coherent_count: 2,
            quorum_reached: false,
            continuous_quorum: false,
            mutation_authority_active: false,
            entropy_balance: 1000,
            drift_class_int: 0,
            is_continuously_coherent: true,
        };
        assess_health(&snap, &HEALTH_GENESIS_HASH)
    }

    // ── QuorumEventKind ───────────────────────────────────────────────────────

    #[test]
    fn kind_as_u8() {
        assert_eq!(QuorumEventKind::QuorumLost.as_u8(), 0);
        assert_eq!(QuorumEventKind::QuorumRestored.as_u8(), 1);
    }

    #[test]
    fn kind_as_str() {
        assert_eq!(QuorumEventKind::QuorumLost.as_str(), "quorum_lost");
        assert_eq!(QuorumEventKind::QuorumRestored.as_str(), "quorum_restored");
    }

    // ── analyze_quorum_drift ──────────────────────────────────────────────────

    #[test]
    fn empty_reports_gives_quorate_summary() {
        let s = analyze_quorum_drift(&[], &QUORUM_GENESIS_HASH);
        assert_eq!(s.loss_count, 0);
        assert!(s.is_currently_quorate);
        assert!(s.events.is_empty());
    }

    #[test]
    fn all_quorate_no_events() {
        let reports: Vec<_> = (1..=5).map(|i| quorate_report(i)).collect();
        let s = analyze_quorum_drift(&reports, &QUORUM_GENESIS_HASH);
        assert_eq!(s.loss_count, 0);
        assert_eq!(s.restoration_count, 0);
        assert_eq!(s.longest_absence, 0);
        assert!(s.events.is_empty());
        assert!(s.is_currently_quorate);
    }

    #[test]
    fn single_loss_event_detected() {
        let reports = vec![
            quorate_report(1),
            quorate_report(2),
            non_quorate_report(3),
            non_quorate_report(4),
        ];
        let s = analyze_quorum_drift(&reports, &QUORUM_GENESIS_HASH);
        assert_eq!(s.loss_count, 1);
        assert_eq!(s.restoration_count, 0);
        assert!(!s.is_currently_quorate);
        assert_eq!(s.longest_absence, 2);
        assert_eq!(s.events.len(), 1);
        assert_eq!(s.events[0].kind, QuorumEventKind::QuorumLost);
        assert_eq!(s.events[0].epoch, 3);
    }

    #[test]
    fn loss_then_restore_detected() {
        let reports = vec![
            quorate_report(1),
            non_quorate_report(2),
            non_quorate_report(3),
            quorate_report(4),
            quorate_report(5),
        ];
        let s = analyze_quorum_drift(&reports, &QUORUM_GENESIS_HASH);
        assert_eq!(s.loss_count, 1);
        assert_eq!(s.restoration_count, 1);
        assert!(s.is_currently_quorate);
        assert_eq!(s.longest_absence, 2);
        assert_eq!(s.events.len(), 2);
        assert_eq!(s.events[0].kind, QuorumEventKind::QuorumLost);
        assert_eq!(s.events[1].kind, QuorumEventKind::QuorumRestored);
    }

    #[test]
    fn multiple_oscillations_counted() {
        let reports = vec![
            quorate_report(1),
            non_quorate_report(2), // loss
            quorate_report(3),     // restore
            non_quorate_report(4), // loss
            quorate_report(5),     // restore
        ];
        let s = analyze_quorum_drift(&reports, &QUORUM_GENESIS_HASH);
        assert_eq!(s.loss_count, 2);
        assert_eq!(s.restoration_count, 2);
        assert_eq!(s.events.len(), 4);
    }

    #[test]
    fn longest_absence_computed_correctly() {
        let reports = vec![
            quorate_report(1),
            non_quorate_report(2),
            non_quorate_report(3),
            non_quorate_report(4), // absence of 3
            quorate_report(5),
            non_quorate_report(6), // absence of 1
        ];
        let s = analyze_quorum_drift(&reports, &QUORUM_GENESIS_HASH);
        assert_eq!(s.longest_absence, 3);
    }

    #[test]
    fn drift_hash_nonzero() {
        let reports = vec![quorate_report(1), quorate_report(2)];
        let s = analyze_quorum_drift(&reports, &QUORUM_GENESIS_HASH);
        assert_ne!(s.drift_hash, [0u8; 32]);
    }

    #[test]
    fn drift_hash_deterministic() {
        let reports: Vec<_> = (1..=4).map(|i| quorate_report(i)).collect();
        let s1 = analyze_quorum_drift(&reports, &QUORUM_GENESIS_HASH);
        let s2 = analyze_quorum_drift(&reports, &QUORUM_GENESIS_HASH);
        let s3 = analyze_quorum_drift(&reports, &QUORUM_GENESIS_HASH);
        assert_eq!(s1.drift_hash, s2.drift_hash);
        assert_eq!(s2.drift_hash, s3.drift_hash);
    }

    // ── DriftHistory ──────────────────────────────────────────────────────────

    #[test]
    fn new_history_empty() {
        let h = DriftHistory::new();
        assert!(h.is_empty());
        assert_eq!(h.total_loss_count(), 0);
    }

    #[test]
    fn record_grows_history() {
        let mut h = DriftHistory::new();
        let r1: Vec<_> = (1..=3).map(|i| quorate_report(i)).collect();
        let r2: Vec<_> = (1..=5).map(|i| quorate_report(i)).collect();
        h.record(&r1).unwrap();
        h.record(&r2).unwrap();
        assert_eq!(h.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = DriftHistory::new();
        let r: Vec<_> = (1..=3).map(|i| quorate_report(i)).collect();
        h.record(&r).unwrap();
        assert!(h.record(&r).is_err());
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = DriftHistory::new();
        for n in 1..=5u64 {
            let r: Vec<_> = (1..=n).map(|i| quorate_report(i)).collect();
            h.record(&r).unwrap();
        }
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
